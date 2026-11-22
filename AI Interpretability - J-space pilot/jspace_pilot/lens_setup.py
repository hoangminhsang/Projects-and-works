"""Loading the official pre-fitted Jacobian lens and validating it against the model.

Every check returns plain dicts so the notebook can print them and the run can
write them to ``validation_log.json``. Nothing here is allowed to silently fall
back to a logit lens or a random matrix.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jlens
import torch
from huggingface_hub import hf_hub_download

from jspace_pilot.config import ExperimentConfig
from jspace_pilot.interventions import JLensBasis, effective_norm_gain
from jspace_pilot.model_io import LoadedModel

logger = logging.getLogger(__name__)


@dataclass
class LensStatus:
    """Outcome of lens loading + validation. ``is_valid`` gates the experiment."""

    is_valid: bool = False
    lens: jlens.JacobianLens | None = None
    local_path: str | None = None
    file_sha256: str | None = None
    checks: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "local_path": self.local_path,
            "file_sha256": self.file_sha256,
            "checks": self.checks,
            "error": self.error,
        }


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_lens(config: ExperimentConfig) -> LensStatus:
    """Download the checkpoint named in the config and load it with jlens."""
    status = LensStatus()
    try:
        path = hf_hub_download(config.lens_repo, config.lens_filename, revision=config.lens_revision)
        status.local_path = path
        status.file_sha256 = _sha256(path)
        status.lens = jlens.JacobianLens.load(path)
        logger.info("loaded %r from %s", status.lens, Path(path).name)
    except Exception as exc:  # network, missing file, wrong format...
        status.error = f"{type(exc).__name__}: {exc}"
        logger.error("lens loading failed: %s", status.error)
    return status


def check_compatibility(status: LensStatus, loaded: LoadedModel, required_layers: list[int]) -> None:
    """Shape, layer coverage and numeric sanity. Updates ``status`` in place."""
    lens = status.lens
    if lens is None:
        return
    checks = status.checks
    checks["lens_d_model"] = lens.d_model
    checks["model_d_model"] = loaded.d_model
    checks["lens_source_layers"] = f"{lens.source_layers[0]}..{lens.source_layers[-1]} ({len(lens.source_layers)} layers)"
    checks["lens_n_prompts"] = lens.n_prompts
    checks["d_model_matches"] = lens.d_model == loaded.d_model
    missing = [l for l in required_layers if l not in lens.source_layers]
    checks["required_layers"] = required_layers
    checks["required_layers_present"] = not missing
    finite = all(torch.isfinite(lens.jacobians[l]).all().item() for l in required_layers if l not in missing)
    checks["jacobians_finite"] = bool(finite)
    checks["jacobian_fro_norm_over_sqrt_d"] = {
        l: round(lens.jacobians[l].norm().item() / loaded.d_model**0.5, 3) for l in required_layers if l not in missing
    }


@torch.no_grad()
def readout_top_tokens(
    loaded: LoadedModel,
    lens: jlens.JacobianLens,
    input_ids: torch.Tensor,
    layers: list[int],
    position: int = -1,
    k: int = 8,
    use_jacobian: bool = True,
) -> dict[int, list[str]]:
    """Top-k lens tokens at one position for several layers.

    ``use_jacobian=False`` gives the plain logit lens (J = identity), shown in
    the notebook only for comparison.
    """
    with jlens.ActivationRecorder(loaded.lens_model.layers, at=layers) as recorder:
        loaded.lens_model.forward(input_ids)
        residuals = {l: recorder.activations[l][0, position].detach().float() for l in layers}
    table = {}
    for layer, h in residuals.items():
        z = lens.transport(h, layer) if use_jacobian else h
        top = loaded.lens_model.unembed(z).float().topk(k).indices.tolist()
        table[layer] = [loaded.tokenizer.decode([t]) for t in top]
    return table


@torch.no_grad()
def build_basis(status: LensStatus, loaded: LoadedModel, layers: list[int]) -> JLensBasis:
    """J-lens basis for the band; also records the norm-gain diagonality check."""
    assert status.lens is not None
    gain, off_diag = effective_norm_gain(
        loaded.final_norm, loaded.d_model, loaded.unembed_weight.device, loaded.unembed_weight.dtype
    )
    status.checks["final_norm_offdiag_ratio"] = off_diag
    status.checks["final_norm_is_diagonal"] = off_diag < 1e-3
    return JLensBasis(status.lens.jacobians, loaded.unembed_weight, gain, layers, loaded.device)


@torch.no_grad()
def check_basis_matches_lens(
    status: LensStatus, loaded: LoadedModel, basis: JLensBasis, input_ids: torch.Tensor, layer: int, k: int = 10, n_positions: int = 8
) -> float:
    """Top-k agreement between our ``v_t . h`` ranking and jlens' own readout
    ``unembed(J h)`` at the last ``n_positions`` positions. Should be ~1.0."""
    assert status.lens is not None
    with jlens.ActivationRecorder(loaded.lens_model.layers, at=[layer]) as recorder:
        loaded.lens_model.forward(input_ids)
        h = recorder.activations[layer][0, -n_positions:].detach().float()
    reference = loaded.lens_model.unembed(status.lens.transport(h, layer)).float().topk(k).indices
    ours = basis.top_tokens(h.to(basis.device), layer, k)
    overlap = [len(set(a.tolist()) & set(b.tolist())) / k for a, b in zip(reference.cpu(), ours.cpu(), strict=True)]
    value = float(sum(overlap) / len(overlap))
    status.checks[f"basis_vs_jlens_top{k}_overlap_L{layer}"] = value
    return value


def finalize_validity(status: LensStatus) -> bool:
    """The lens is valid only if every essential check passed."""
    c = status.checks
    essential = [
        status.lens is not None,
        c.get("d_model_matches", False),
        c.get("required_layers_present", False),
        c.get("jacobians_finite", False),
        c.get("final_norm_is_diagonal", False),
        all(v >= 0.9 for key, v in c.items() if key.startswith("basis_vs_jlens")),
        any(key.startswith("basis_vs_jlens") for key in c),
    ]
    status.is_valid = all(essential)
    return status.is_valid
