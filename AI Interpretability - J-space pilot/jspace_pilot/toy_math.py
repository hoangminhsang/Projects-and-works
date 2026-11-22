"""Toy mathematical checks that must pass before touching the real model.

Spec v2 §5.2 (Jacobian by autograd vs analytic vs finite differences),
§5.6 (Jacobian -> J-lens direction -> ablation in R^2), §5.8 (norm-matched
random control) and the §5.12 projection invariants. Each function returns a
plain dict so the notebook can print it and ``validation_log.json`` can store it.
"""

from __future__ import annotations

from typing import Any

import torch

from jspace_pilot.interventions import (
    calculate_jlens_direction,
    matched_random_perturbation,
    project_onto_span,
    remove_direction,
)

TOY_J = torch.tensor([[2.0, 1.0], [1.0, 3.0]])
TOY_H = torch.tensor([3.0, 2.0])
TOY_W = torch.tensor([1.0, -1.0])


def toy_function(x: torch.Tensor) -> torch.Tensor:
    """``f([x1, x2]) = [2 x1 + x2, x1 + 3 x2]``, a linear map R^2 -> R^2."""
    return torch.stack([2 * x[0] + x[1], x[0] + 3 * x[1]])


def toy_analytic_jacobian() -> torch.Tensor:
    """``df/dx = [[2, 1], [1, 3]]`` worked out by hand."""
    return TOY_J.clone()


def verify_toy_autograd(x: torch.Tensor | None = None, eps: float = 1e-3) -> dict[str, Any]:
    """Compare three ways of getting the Jacobian of :func:`toy_function`.

    1. by hand, 2. ``torch.autograd.functional.jacobian``, 3. central finite
    differences ``(f(x + eps e_j) - f(x - eps e_j)) / (2 eps)`` column by column.
    Also checks the first-order Taylor rule ``f(x + delta) - f(x) = J delta``.
    """
    x = TOY_H.clone() if x is None else x.float()
    analytic = toy_analytic_jacobian()
    autograd = torch.autograd.functional.jacobian(toy_function, x)
    finite = torch.stack(
        [(toy_function(x + eps * e) - toy_function(x - eps * e)) / (2 * eps) for e in torch.eye(2)], dim=1
    )
    delta = torch.tensor([0.1, 0.0])
    taylor_lhs = toy_function(x + delta) - toy_function(x)
    return {
        "x": x.tolist(),
        "f(x)": toy_function(x).tolist(),
        "J_analytic": analytic.tolist(),
        "J_autograd": autograd.tolist(),
        "J_finite_difference": finite.tolist(),
        "f(x+delta)-f(x)": taylor_lhs.tolist(),
        "J @ delta": (analytic @ delta).tolist(),
        "autograd_matches_analytic": bool(torch.allclose(autograd, analytic)),
        "finite_diff_matches_analytic": bool(torch.allclose(finite, analytic, atol=1e-3)),
        "taylor_rule_holds": bool(torch.allclose(taylor_lhs, analytic @ delta, atol=1e-5)),
    }


def toy_direction_ablation() -> dict[str, Any]:
    """The worked R^2 example of spec §5.6 (teaching only, not an AI result).

    J = [[2,1],[1,3]], h = [3,2], w = [1,-1]  ->  v = J^T w = [1,-2],
    v.h = -1 = w.(J h), h_ablated = [3.2, 1.6], score after = 0.
    """
    J, h, w = TOY_J, TOY_H, TOY_W
    v = calculate_jlens_direction(J, w.unsqueeze(0), 0)  # g = 1 here
    h_ablated = remove_direction(h, v, alpha=1.0)
    return {
        "J": J.tolist(),
        "h": h.tolist(),
        "w_token": w.tolist(),
        "J h": (J @ h).tolist(),
        "score_before = w.(J h)": float(w @ (J @ h)),
        "v = J^T w": v.tolist(),
        "v.h (should equal score)": float(v @ h),
        "projection of h on v": ((h @ v) / (v @ v) * v).tolist(),
        "h_ablated": h_ablated.tolist(),
        "v.h_ablated": float(v @ h_ablated),
        "||h_ablated - h||": float((h_ablated - h).norm()),
        "J h_ablated": (J @ h_ablated).tolist(),
        "score_after = w.(J h_ablated)": float(w @ (J @ h_ablated)),
    }


def test_projection_invariants(d: int = 64, k: int = 10, n: int = 32, seed: int = 0) -> dict[str, Any]:
    """Spec §5.12 maths checks on random data. Every value should be True."""
    gen = torch.Generator().manual_seed(seed)
    J = torch.randn(d, d, generator=gen) / d**0.5
    W_U = torch.randn(100, d, generator=gen)
    gain = torch.rand(d, generator=gen) + 0.5
    h = torch.randn(d, generator=gen)

    v = calculate_jlens_direction(J, W_U, 7, gain)
    lens_score = (gain * W_U[7]) @ (J @ h)  # w^T diag(g) J h, norm scale ignored

    H = torch.randn(n, d, generator=gen)
    V = torch.randn(n, k, d, generator=gen)
    V_dup = torch.cat([V, V[:, :1] * 3.0, V[:, 1:2] + 1e-7 * torch.randn(n, 1, d, generator=gen)], dim=1)
    proj, rank = project_onto_span(H, V)
    proj_dup, rank_dup = project_onto_span(H, V_dup)
    residual = H - proj
    single, _ = project_onto_span(h.unsqueeze(0), v.view(1, 1, d))

    magnitude = proj.norm(dim=-1)  # ||delta_J|| for alpha = 1
    delta_r = matched_random_perturbation(magnitude, d, torch.Generator().manual_seed(1))

    checks = {
        "v has shape [d]": tuple(v.shape) == (d,),
        "w^T diag(g) J h == v . h": bool(torch.allclose(lens_score, v @ h, atol=1e-4)),
        "alpha=0 leaves h unchanged": bool(torch.equal(remove_direction(h, v, alpha=0.0), h)),
        "alpha=1 gives v . h_new ~ 0": abs(float(v @ remove_direction(h, v, alpha=1.0))) < 1e-4,
        "k=1 span projection == remove_direction": bool(
            torch.allclose(h - single[0], remove_direction(h, v, alpha=1.0), atol=1e-4)
        ),
        "residual orthogonal to every selected vector": bool(
            torch.allclose(torch.einsum("pkd,pd->pk", V, residual), torch.zeros(n, k), atol=1e-3)
        ),
        "projection is idempotent (P P h = P h)": bool(torch.allclose(project_onto_span(proj, V)[0], proj, atol=1e-4)),
        "duplicate/near-duplicate vectors: same projection": bool(torch.allclose(proj_dup, proj, atol=1e-3)),
        "duplicate/near-duplicate vectors: rank stays k": bool((rank_dup == k).all() and (rank == k).all()),
        "||delta_random|| == ||delta_J||": bool(torch.allclose(delta_r.norm(dim=-1), magnitude, rtol=1e-5)),
        "no NaN/Inf anywhere": bool(all(torch.isfinite(t).all() for t in (proj, proj_dup, delta_r, v))),
    }
    return checks
