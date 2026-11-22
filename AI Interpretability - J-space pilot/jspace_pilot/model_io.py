"""Loading the model, tokenising prompts, and scoring A/B/C/D answers.

Design choices (all explained in the notebook):

* bf16 weights, never quantised: the pre-fitted lens was fitted on bf16
  activations, and quantisation would change them.
* Explicit device map: embedding, final norm, LM head and the first
  ``n_gpu_layers`` blocks on GPU 0; remaining blocks streamed from CPU RAM by
  accelerate. The LM head must be on the GPU because lens scoring reads its
  weight matrix directly.
* One forward pass per trial, no sampling, no KV cache: the answer is read
  from the next-token distribution at the last prompt position.
"""

from __future__ import annotations

import functools
import hashlib
import logging
import math
from dataclasses import dataclass, field
from typing import Any

import jlens
import torch
import transformers
from accelerate import init_empty_weights

from jspace_pilot.config import ExperimentConfig
from jspace_pilot.scenarios import LETTERS

logger = logging.getLogger(__name__)
GIB = 1024**3


def resolve_attr(obj: Any, dotted_path: str) -> Any:
    return functools.reduce(getattr, dotted_path.split("."), obj)


def _param_bytes(module: torch.nn.Module, bytes_per_param: int) -> int:
    return sum(p.numel() for p in module.parameters()) * bytes_per_param


@dataclass
class LoadedModel:
    """Everything downstream code needs about the model."""

    hf_model: torch.nn.Module
    tokenizer: Any
    lens_model: jlens.HFLensModel  # jlens' adapter: .layers, .forward(), .unembed()
    final_norm: torch.nn.Module
    unembed_weight: torch.Tensor  # [vocab, d_model], lives on the GPU (or CPU-only run)
    device: torch.device  # where inputs, lens scoring and edits happen
    n_gpu_layers: int
    device_map: dict[str, int | str] = field(repr=False)

    @property
    def n_layers(self) -> int:
        return self.lens_model.n_layers

    @property
    def d_model(self) -> int:
        return self.lens_model.d_model


def build_device_map(meta_model: torch.nn.Module, layout: jlens.Layout, n_gpu_layers: int) -> dict[str, int | str]:
    """Explicit device map for a model whose text decoder sits at ``layout.path``.

    Modules on the path to the text decoder that are not the decoder itself
    (e.g. a vision tower) go to CPU; the LM head, embedding, final norm and the
    first ``n_gpu_layers`` residual blocks go to GPU 0.
    """
    device_map: dict[str, int | str] = {}
    module, prefix = meta_model, ""
    for part in layout.path.split("."):
        for name, _ in module.named_children():
            if name != part:
                full_name = prefix + name
                device_map[full_name] = 0 if full_name == layout.lm_head else "cpu"
        module, prefix = getattr(module, part), prefix + part + "."
    for name, child in module.named_children():
        if name == layout.layers:
            for i in range(len(child)):
                device_map[f"{prefix}{name}.{i}"] = 0 if i < n_gpu_layers else "cpu"
        else:
            device_map[prefix + name] = 0
    return device_map


def estimate_gpu_layers(meta_model: torch.nn.Module, layout: jlens.Layout, reserve_gib: float, bytes_per_param: int = 2) -> int:
    """How many residual blocks fit in free VRAM after the always-on-GPU parts."""
    free_bytes, _ = torch.cuda.mem_get_info()
    text_module = resolve_attr(meta_model, layout.path)
    blocks = getattr(text_module, layout.layers)
    fixed = sum(
        _param_bytes(getattr(text_module, name), bytes_per_param)
        for name, _ in text_module.named_children()
        if name != layout.layers
    )
    lm_head = getattr(meta_model, layout.lm_head)
    embed = getattr(text_module, layout.embed)
    if lm_head.weight is not embed.weight:  # untied head costs extra memory
        fixed += _param_bytes(lm_head, bytes_per_param)
    per_block = _param_bytes(blocks[0], bytes_per_param)
    budget = free_bytes - reserve_gib * GIB - fixed
    n = max(0, min(len(blocks), math.floor(budget / per_block)))
    logger.info(
        "VRAM free %.2f GiB | fixed %.2f GiB | per block %.3f GiB | reserve %.1f GiB -> %d/%d blocks on GPU",
        free_bytes / GIB, fixed / GIB, per_block / GIB, reserve_gib, n, len(blocks),
    )
    return n


def load_model(config: ExperimentConfig) -> LoadedModel:
    """Load tokenizer + model with the device strategy described above."""
    dtype = getattr(torch, config.dtype)
    tokenizer = transformers.AutoTokenizer.from_pretrained(config.model_id, revision=config.model_revision)
    hf_config = transformers.AutoConfig.from_pretrained(config.model_id, revision=config.model_revision)

    with init_empty_weights():
        meta_model = transformers.AutoModelForCausalLM.from_config(hf_config)  # no memory used
    layout = jlens.from_hf(meta_model, tokenizer).layout  # public API, auto-detects layout
    n_blocks = hf_config.get_text_config().num_hidden_layers

    if torch.cuda.is_available():
        n_gpu = config.n_gpu_layers
        if n_gpu is None:
            n_gpu = estimate_gpu_layers(meta_model, layout, config.vram_reserve_gib)
        device_map: dict[str, int | str] = (
            {"": 0} if n_gpu >= n_blocks else build_device_map(meta_model, layout, n_gpu)
        )
        device = torch.device("cuda:0")
    else:
        logger.warning("No CUDA device: running fully on CPU (slow).")
        n_gpu, device_map, device = 0, {"": "cpu"}, torch.device("cpu")
    del meta_model

    hf_model = transformers.AutoModelForCausalLM.from_pretrained(
        config.model_id, revision=config.model_revision, dtype=dtype, device_map=device_map
    )
    hf_model.eval()
    lens_model = jlens.from_hf(hf_model, tokenizer)
    text_module = resolve_attr(hf_model, lens_model.layout.path)
    final_norm = getattr(text_module, lens_model.layout.norm)
    unembed_weight = getattr(hf_model, lens_model.layout.lm_head).weight
    if unembed_weight.device.type == "meta":
        raise RuntimeError("LM head weights are offloaded; lens scoring needs them resident.")
    return LoadedModel(
        hf_model=hf_model,
        tokenizer=tokenizer,
        lens_model=lens_model,
        final_norm=final_norm,
        unembed_weight=unembed_weight,
        device=device,
        n_gpu_layers=min(n_gpu, n_blocks),
        device_map=device_map,
    )


# ------------------------------------------------------------------- tokenisation
def render_prompt(tokenizer: Any, messages: list[dict[str, str]]) -> str:
    """Apply the chat template with thinking disabled (the answer must be the
    very first assistant token)."""
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )


@dataclass(frozen=True)
class PreparedPrompt:
    text: str
    input_ids: torch.Tensor  # [1, seq_len] on the model's input device
    sha256: str

    @property
    def n_tokens(self) -> int:
        return int(self.input_ids.shape[1])


def encode_text(loaded: LoadedModel, text: str) -> PreparedPrompt:
    """Tokenise without adding special tokens (the chat template already did)."""
    ids = loaded.tokenizer(text, return_tensors="pt", add_special_tokens=False).input_ids
    sha = hashlib.sha256(ids.numpy().tobytes()).hexdigest()[:16]
    return PreparedPrompt(text=text, input_ids=ids.to(loaded.lens_model.input_device), sha256=sha)


def letter_token_variants(tokenizer: Any) -> dict[str, list[int]]:
    """Token ids that spell each answer letter as ONE token ("A" and/or " A").

    We do not assume A-D are single tokens; we check, and fail loudly if a letter
    has no single-token spelling or two letters share a token.
    """
    variants: dict[str, list[int]] = {}
    for letter in LETTERS:
        ids = []
        for spelling in (letter, f" {letter}"):
            encoded = tokenizer.encode(spelling, add_special_tokens=False)
            if len(encoded) == 1:
                ids.append(encoded[0])
        if not ids:
            raise ValueError(f"letter {letter!r} has no single-token spelling")
        variants[letter] = sorted(set(ids))
    flat = [i for ids in variants.values() for i in ids]
    if len(flat) != len(set(flat)):
        raise ValueError(f"letters share token ids: {variants}")
    return variants


# ------------------------------------------------------------------------ forward
@torch.no_grad()
def final_block_residual(loaded: LoadedModel, input_ids: torch.Tensor) -> torch.Tensor:
    """Run the decoder once (prefill only, no cache) and return the last block's
    output residual, ``[seq_len, d_model]``. Any active edit hooks apply."""
    last = loaded.n_layers - 1
    with jlens.ActivationRecorder(loaded.lens_model.layers, at=[last]) as recorder:
        loaded.lens_model.forward(input_ids)
        return recorder.activations[last][0].detach()


@torch.no_grad()
def clean_pass(
    loaded: LoadedModel, input_ids: torch.Tensor, record_layers: list[int], first_position: int
) -> tuple[torch.Tensor, dict[int, torch.Tensor]]:
    """One unedited forward that returns the final-block residual ``[seq, d]``
    and the residuals of ``record_layers`` at positions ``>= first_position``
    (``{layer: [P, d]}``), used to locate concepts before intervening."""
    last = loaded.n_layers - 1
    with jlens.ActivationRecorder(loaded.lens_model.layers, at=[*record_layers, last]) as recorder:
        loaded.lens_model.forward(input_ids)
        final = recorder.activations[last][0].detach()
        layers = {l: recorder.activations[l][0, first_position:].detach() for l in record_layers}
    return final, layers


@torch.no_grad()
def logits_from_residual(loaded: LoadedModel, residual: torch.Tensor, chunk: int = 64) -> torch.Tensor:
    """Final norm + LM head on ``[n, d_model]`` residuals, chunked; fp32 on CPU."""
    return torch.cat(
        [loaded.lens_model.unembed(residual[i : i + chunk]).float().cpu() for i in range(0, len(residual), chunk)]
    )


@torch.no_grad()
def top_output_tokens(loaded: LoadedModel, residual: torch.Tensor, n: int, chunk: int = 64) -> torch.Tensor:
    """Top-``n`` next-token ids of the clean model at every position, ``[seq, n]``."""
    out = [
        loaded.lens_model.unembed(residual[i : i + chunk]).topk(n, dim=-1).indices
        for i in range(0, len(residual), chunk)
    ]
    return torch.cat(out).to(loaded.device)


@dataclass(frozen=True)
class ChoiceScore:
    """How the model answered one multiple-choice question.

    ``predicted_letter`` is the strict answer: the full-vocabulary top-1 token,
    mapped to a letter, or ``"INVALID"`` if that token is not a letter. This is
    exactly what one step of greedy decoding would output. ``restricted_letter``
    is the best of the four letters even if a non-letter token ranked higher.
    """

    predicted_letter: str
    restricted_letter: str
    top1_token: str
    letter_logprobs: dict[str, float]

    @property
    def invalid(self) -> bool:
        return self.predicted_letter == "INVALID"

    def margin(self, correct: str) -> float:
        """log p(correct) - max log p(other letter). Positive = correct letter wins."""
        others = [lp for letter, lp in self.letter_logprobs.items() if letter != correct]
        return self.letter_logprobs[correct] - max(others)


def score_choice(final_logits: torch.Tensor, variants: dict[str, list[int]], tokenizer: Any) -> ChoiceScore:
    """Score A/B/C/D from the next-token logits at the last prompt position."""
    logprobs = torch.log_softmax(final_logits.float(), dim=-1)
    top1 = int(logprobs.argmax())
    strict = next((letter for letter, ids in variants.items() if top1 in ids), "INVALID")
    letter_lp = {letter: float(torch.logsumexp(logprobs[ids], dim=0)) for letter, ids in variants.items()}
    return ChoiceScore(
        predicted_letter=strict,
        restricted_letter=max(letter_lp, key=letter_lp.__getitem__),
        top1_token=tokenizer.decode([top1]),
        letter_logprobs=letter_lp,
    )
