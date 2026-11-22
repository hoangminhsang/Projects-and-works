"""J-lens-indexed ablation, the norm-matched random control, and safe hooks.

Notation (one layer l, one token position):

    h        residual-stream vector (output of block l), shape [d]
    J_l      fitted average Jacobian from the official jlens checkpoint, [d, d]
    w_t      row t of the unembedding W_U, [d]
    g        per-dimension gain of the final RMSNorm, [d]
    v_t      J-lens vector of token t:  v_t = J_l^T (g * w_t)        [d]

Why ``g`` appears: the lens readout is ``W_U norm(J_l h)`` and an RMSNorm is
``norm(x) = g * x / rms(x)``, so the lens logit of token t is
``(g * w_t)^T J_l h / rms(J_l h) = (v_t . h) / rms``. The factor ``1/rms`` is
the same for every token at a position, so ranking tokens by ``v_t . h`` is
exactly the lens ranking, and removing the projection on ``v_t`` drives that
token's lens logit to exactly 0. (Spec §5.5's ``J^T w`` is the special case
``g = 1``; it ignores the norm and would not zero the lens logit.)

Main intervention (C1). Which vectors V = [v_1 .. v_k] are removed at a site:
    * "concept" selection (primary): a CLEAN pass first reads the lens at every
      (layer, position); the pre-registered task-concept tokens that rank in the
      lens top-n there (and are not the clean model's own next-token guesses)
      form V for that site. Sites with no concept present are left untouched.
    * "topk" selection (paper §3.5.2): the top-k lens tokens at the site, minus
      protected and excluded (special / punctuation) tokens.
    Then  h_J = h - alpha * P_V h,  P_V = orthogonal projection onto span(V),
    computed from an SVD of V (numerically stable, rank-revealing).

    NOTE (spec §5.9): this is an orthogonal projection onto the span of the top-k
    J-lens vectors. It is NOT the paper's sparse non-negative J-space
    decomposition (gradient pursuit), and it also removes components with
    negative coefficients. Claims must say "top-k J-lens-direction ablation".

Control (C2, spec §5.8), at the same site:
    m = ||h_J - h|| RECORDED IN THE C1 RUN at this (layer, position),
    r ~ N(0, I_d),  delta_R = -m * r / ||r||
    -> a norm-matched random perturbation (NOT a projection removal). Re-using
    C1's recorded m (instead of re-measuring on C2's own, already perturbed
    activations) is what makes ||delta_R|| == ||delta_J|| hold at every site.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Literal

import torch

EditMode = Literal["noop", "j_ablation", "random_ablation"]

#: Value written to the ``intervention_kind`` CSV column for each condition.
INTERVENTION_KIND: dict[str, str] = {
    "baseline": "none",
    "noop": "noop_hook",
    "j_ablation": "targeted_{selection}_j_directions",  # filled with config.selection
    "random_ablation": "norm_matched_random",
}


# ----------------------------------------------------------- single-direction maths
def calculate_jlens_direction(
    jacobian: torch.Tensor, unembed: torch.Tensor, token_id: int, norm_gain: torch.Tensor | None = None
) -> torch.Tensor:
    """J-lens vector of one token: ``v = J^T (g * w_token)``.

    Args:
        jacobian: ``J_l``, shape ``[d, d]``.
        unembed: ``W_U``, shape ``[V, d]``.
        token_id: vocabulary index of the token.
        norm_gain: final-norm gain ``g`` ``[d]``; ``None`` means ``g = 1``
            (the spec's simplified ``J^T w``).

    Returns:
        ``v`` with shape ``[d]`` (fp32).
    """
    d = jacobian.shape[0]
    if jacobian.shape != (d, d) or unembed.shape[1] != d:
        raise ValueError(f"shape mismatch: J {tuple(jacobian.shape)}, W_U {tuple(unembed.shape)}")
    row = unembed[token_id].float()
    if norm_gain is not None:
        row = row * norm_gain.float()
    return jacobian.float().T @ row


def remove_direction(
    h: torch.Tensor, direction: torch.Tensor, alpha: float = 1.0, center: torch.Tensor | None = None
) -> torch.Tensor:
    """Remove ``alpha`` times the projection of ``h`` (optionally centred) onto one direction.

    ``h_new = h - alpha * ((h - mu) . v / (v . v)) * v``   (spec §5.7)

    Args:
        h: activation ``[d]``.
        direction: ``v`` ``[d]`` (any non-zero length).
        alpha: strength in ``[0, 1]``; 0 = no change, 1 = full removal.
        center: optional ``mu`` ``[d]`` (from calibration data only).

    Returns:
        ``h_new`` ``[d]``.
    """
    if h.ndim != 1 or direction.ndim != 1 or h.shape != direction.shape:
        raise ValueError("h and direction must have identical shape [d_model]")
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be in [0, 1] in this pilot")
    x = h if center is None else h - center
    denom = torch.dot(direction, direction)
    if denom <= 1e-12:
        raise ValueError("direction has (nearly) zero norm")
    return h - alpha * (torch.dot(x, direction) / denom) * direction


def matched_random_perturbation(
    magnitude: torch.Tensor, d_model: int, generator: torch.Generator, device: torch.device | None = None
) -> torch.Tensor:
    """``delta_R = -m * r / ||r||`` with ``r ~ N(0, I_d)``, one fresh ``r`` per row.

    Args:
        magnitude: ``m`` per row, shape ``[P]`` (or a scalar tensor for one row).
        d_model: dimension ``d``.
        generator: seeded CPU generator (reproducible draws).

    Returns:
        ``[P, d]`` perturbations whose row norms equal ``magnitude`` exactly
        (up to float rounding).
    """
    m = magnitude.reshape(-1, 1).float()
    r = torch.randn(m.shape[0], d_model, generator=generator)
    unit = r / r.norm(dim=-1, keepdim=True)
    return -(m.cpu() * unit).to(device or magnitude.device)


# --------------------------------------------------------- multi-direction maths
def project_onto_span(h: torch.Tensor, vectors: torch.Tensor, rtol: float = 1e-4) -> tuple[torch.Tensor, torch.Tensor]:
    """Orthogonal projection of each ``h[p]`` onto ``span(vectors[p])``, via SVD.

    The SVD ``V = U S Q`` gives an orthonormal basis ``Q`` of the row space of
    ``V`` without forming ``V V^T`` (which would square the condition number).
    Singular values below ``rtol * max`` are treated as zero, so near-duplicate
    vectors (e.g. tokens "backup" and " backup") do not blow up.

    Args:
        h: ``[P, d]`` activations.
        vectors: ``[P, k, d]`` spanning vectors (need not be orthogonal or
            linearly independent).
        rtol: relative singular-value cut-off.

    Returns:
        (projection ``[P, d]``, effective rank ``[P]``)
    """
    _, singular, basis = torch.linalg.svd(vectors, full_matrices=False)  # basis: [P, k, d]
    keep = singular > rtol * singular.amax(dim=-1, keepdim=True)  # [P, k]
    basis = basis * keep.unsqueeze(-1)
    coords = torch.einsum("pkd,pd->pk", basis, h)
    return torch.einsum("pk,pkd->pd", coords, basis), keep.sum(dim=-1)


@torch.no_grad()
def effective_norm_gain(final_norm: torch.nn.Module, d_model: int, device: torch.device, dtype: torch.dtype) -> tuple[torch.Tensor, float]:
    """Read the final norm's per-dimension gain without assuming its formula.

    Feeding one-hot rows e_i through an RMSNorm gives ``c * g_i`` on the
    diagonal (``c`` is the same for every row) and zeros elsewhere. Only the
    *relative* gain matters for ranking and for projections, so ``c`` is
    irrelevant. The largest off-diagonal magnitude is returned as a check that
    the norm really is diagonal (it would not be for a LayerNorm with mean
    subtraction).

    Returns:
        (gain ``[d]`` fp32, max |off-diagonal| / max |diagonal|)
    """
    eye = torch.eye(d_model, device=device, dtype=dtype)
    out = final_norm(eye).float()
    diagonal = out.diagonal().clone()
    off_diagonal = (out - torch.diag(diagonal)).abs().max().item()
    return diagonal, off_diagonal / diagonal.abs().max().item()


def site_seed(base_seed: int, layer: int, prompt_key: str) -> int:
    """Deterministic seed for one (trial prompt, layer): independent of run order."""
    digest = hashlib.sha256(f"{base_seed}|{layer}|{prompt_key}".encode()).hexdigest()
    return int(digest[:15], 16)


# ------------------------------------------------------------------- J-lens basis
class JLensBasis:
    """Per-layer J-lens scoring and J-lens vectors for a band of layers."""

    def __init__(
        self,
        jacobians: Mapping[int, torch.Tensor],
        unembed_weight: torch.Tensor,
        norm_gain: torch.Tensor,
        layers: Sequence[int],
        device: torch.device,
        chunk: int = 64,
    ) -> None:
        missing = [l for l in layers if l not in jacobians]
        if missing:
            raise ValueError(f"lens has no Jacobian for layers {missing}")
        self.device = device
        self.J = {l: jacobians[l].to(device=device, dtype=torch.float32) for l in layers}
        self.unembed = unembed_weight  # [V, d], shared with the model: no copy
        self.gain = norm_gain.to(device=device, dtype=torch.float32)
        self.chunk = chunk

    @torch.no_grad()
    def top_tokens(
        self,
        h: torch.Tensor,
        layer: int,
        k: int,
        protected: torch.Tensor | None = None,
        excluded: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Top-``k`` token ids by lens score ``v_t . h`` at each row of ``h`` (``[P, d]``).

        ``protected`` (``[P, n]`` token ids) are excluded at their own row;
        ``excluded`` (``[E]`` token ids) are excluded at every row.
        Scores are computed chunk by chunk so a ``[P, vocab]`` matrix never
        exists in memory.
        """
        out = []
        for start in range(0, len(h), self.chunk):
            transported = (h[start : start + self.chunk] @ self.J[layer].T) * self.gain  # g * (J h)
            scores = transported.to(self.unembed.dtype) @ self.unembed.T  # [c, V]
            if protected is not None:
                scores.scatter_(1, protected[start : start + self.chunk], float("-inf"))
            if excluded is not None:
                scores[:, excluded] = float("-inf")
            out.append(scores.topk(k, dim=-1).indices)
        return torch.cat(out)

    @torch.no_grad()
    def vectors(self, layer: int, token_ids: torch.Tensor) -> torch.Tensor:
        """J-lens vectors ``v_t = J^T (g * w_t)`` for ``token_ids`` of any shape -> ``[..., d]``."""
        rows = self.unembed[token_ids].float() * self.gain
        return rows @ self.J[layer]


# --------------------------------------------------------------------------- hooks
@dataclass
class EditRecord:
    """Diagnostics from one hook call (one layer, all editable positions)."""

    layer: int
    n_positions: int  # editable positions (>= first_position)
    n_edited_sites: int  # positions where ||delta|| > 0
    h_norm: float  # mean ||h|| over editable positions
    delta_norm: float  # mean ||delta|| over editable positions (0 where untouched)
    j_delta_norm: float  # mean ||delta_J|| over editable positions (C1's value; C2 re-uses it)
    cosine: float  # mean cos(h, h + delta)
    span_rank: float  # mean effective rank of the J-lens vectors at edited sites
    random_in_j_span: float  # mean ||P_V delta_R|| / ||delta_R|| at edited sites (C2 only)
    last_position_tokens: list[int] = field(default_factory=list)  # J tokens targeted at final position


class ResidualEditHook:
    """Forward hook that replaces one block's output residual with an edited copy.

    Conditions:

    * ``noop``            - returns the output untouched (hook plumbing test)
    * ``j_ablation``      - subtracts ``alpha * P_V h``. V comes from
                            ``site_tokens`` (concept plan, fixed by a clean pass)
                            or, if that is ``None``, from the top-k lens tokens.
    * ``random_ablation`` - adds ``-m * r / ||r||`` with ``m = target_norms``
                            (the per-site ||delta_J|| recorded in the C1 run).

    Only positions ``>= first_position`` are edited, during the single prefill
    forward pass (no decode step, no KV cache). Maths runs in fp32; the result
    is cast back and written into a clone (never in place). After the call,
    ``site_delta_norms`` holds ||delta|| per editable position (CPU, fp32).
    """

    def __init__(
        self,
        *,
        layer: int,
        mode: EditMode,
        basis: JLensBasis | None = None,
        site_tokens: torch.Tensor | None = None,
        protected: torch.Tensor | None = None,
        excluded: torch.Tensor | None = None,
        top_k: int = 10,
        target_norms: torch.Tensor | None = None,
        first_position: int = 16,
        alpha: float = 1.0,
        random_seed: int | None = None,
        span_rtol: float = 1e-4,
    ) -> None:
        if mode == "j_ablation" and basis is None:
            raise ValueError("j_ablation needs a JLensBasis")
        if mode == "random_ablation" and (target_norms is None or random_seed is None):
            raise ValueError("random_ablation needs target_norms (from the C1 run) and a random_seed")
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be in [0, 1]")
        self.layer, self.mode, self.basis = layer, mode, basis
        self.site_tokens, self.protected, self.excluded, self.top_k = site_tokens, protected, excluded, top_k
        self.target_norms = target_norms
        self.first_position, self.alpha = first_position, alpha
        self.random_seed, self.span_rtol = random_seed, span_rtol
        self.records: list[EditRecord] = []
        self.site_delta_norms: torch.Tensor | None = None

    def _vectors(self, h: torch.Tensor, positions: slice) -> tuple[torch.Tensor, torch.Tensor]:
        """J-lens vectors per site, ``[P, k, d]``, and the token ids ``[P, k]`` (-1 = none)."""
        assert self.basis is not None
        if self.site_tokens is not None:
            tokens = self.site_tokens.to(self.basis.device)
            if tokens.shape[0] != len(h):
                raise ValueError(f"concept plan has {tokens.shape[0]} positions, residual has {len(h)}")
            vectors = self.basis.vectors(self.layer, tokens.clamp_min(0)) * (tokens >= 0).unsqueeze(-1)
            return vectors, tokens
        protected = None if self.protected is None else self.protected[positions]
        tokens = self.basis.top_tokens(h, self.layer, self.top_k, protected, self.excluded)
        return self.basis.vectors(self.layer, tokens), tokens

    @torch.no_grad()
    def __call__(self, module: torch.nn.Module, args: tuple, output):
        if self.mode == "noop":
            return None  # PyTorch keeps the original output
        hidden = output if torch.is_tensor(output) else output[0]
        if hidden.ndim != 3 or hidden.shape[0] != 1:
            raise ValueError(f"edit hooks expect [1, seq, d] residuals, got {tuple(hidden.shape)}")
        seq_len = hidden.shape[1]
        if seq_len <= self.first_position:
            return None
        positions = slice(self.first_position, seq_len)
        device = self.basis.device if self.basis is not None else hidden.device
        h = hidden[0, positions].to(device=device, dtype=torch.float32)

        vectors = tokens = None
        rank = torch.zeros(len(h), device=device)
        if self.basis is not None and (self.mode == "j_ablation" or self.site_tokens is not None):
            vectors, tokens = self._vectors(h, positions)

        if self.mode == "j_ablation":
            assert vectors is not None
            projection, rank = project_onto_span(h, vectors, self.span_rtol)
            delta = -self.alpha * projection
            j_norm = delta.norm(dim=-1)
            random_in_span = 0.0
        else:
            j_norm = self.target_norms.to(device=device, dtype=torch.float32)  # type: ignore[union-attr]
            if j_norm.shape[0] != len(h):
                raise ValueError(f"target_norms has {j_norm.shape[0]} positions, residual has {len(h)}")
            generator = torch.Generator().manual_seed(self.random_seed)  # type: ignore[arg-type]
            delta = matched_random_perturbation(j_norm, h.shape[1], generator, device)
            random_in_span = 0.0
            if vectors is not None:  # how much of the random change falls along the J directions
                in_span, rank = project_onto_span(delta, vectors, self.span_rtol)
                ratio = in_span.norm(dim=-1) / delta.norm(dim=-1).clamp_min(1e-12)
                edited = j_norm > 1e-6
                random_in_span = ratio[edited].mean().item() if edited.any() else 0.0

        edited = delta.norm(dim=-1) > 1e-6
        h_new = h + delta
        self.site_delta_norms = delta.norm(dim=-1).cpu()
        self.records.append(
            EditRecord(
                layer=self.layer,
                n_positions=len(h),
                n_edited_sites=int(edited.sum()),
                h_norm=h.norm(dim=-1).mean().item(),
                delta_norm=delta.norm(dim=-1).mean().item(),
                j_delta_norm=j_norm.mean().item(),
                cosine=torch.nn.functional.cosine_similarity(h, h_new, dim=-1).mean().item(),
                span_rank=rank[edited].float().mean().item() if edited.any() else 0.0,
                random_in_j_span=random_in_span,
                last_position_tokens=[] if tokens is None else [t for t in tokens[-1].tolist() if t >= 0],
            )
        )
        new_hidden = hidden.clone()
        new_hidden[0, positions] = h_new.to(device=hidden.device, dtype=hidden.dtype)
        return new_hidden if torch.is_tensor(output) else (new_hidden, *output[1:])


def count_forward_hooks(blocks: Sequence[torch.nn.Module]) -> int:
    return sum(len(block._forward_hooks) for block in blocks)


@contextmanager
def residual_edits(blocks: Sequence[torch.nn.Module], hooks: Mapping[int, ResidualEditHook]) -> Iterator[Mapping[int, ResidualEditHook]]:
    """Attach ``hooks`` (block index -> hook) for the duration of a ``with`` block.

    Hooks are removed in ``finally``, so an exception inside the block cannot
    leak an intervention into the next condition. On exit we also assert the
    hook count is back to what it was before.
    """
    before = count_forward_hooks(blocks)
    handles = []
    try:
        for index, hook in hooks.items():
            handles.append(blocks[index].register_forward_hook(hook))
        yield hooks
    finally:
        for handle in handles:
            handle.remove()
        after = count_forward_hooks(blocks)
        if after != before:
            raise RuntimeError(f"hook leak: {after} forward hooks after exit, {before} before")
