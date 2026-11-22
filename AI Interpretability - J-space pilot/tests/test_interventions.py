"""Hook and projection maths on tiny tensors (no real model needed)."""

import pytest

torch = pytest.importorskip("torch")

from jspace_pilot.interventions import (  # noqa: E402
    JLensBasis,
    ResidualEditHook,
    calculate_jlens_direction,
    count_forward_hooks,
    effective_norm_gain,
    matched_random_perturbation,
    project_onto_span,
    remove_direction,
    residual_edits,
    site_seed,
)


def test_remove_direction_toy_example():
    # h = (3, 4, 1, 0), v = (1, 1, 0, 0) -> h.v / v.v = 3.5 -> h_new = (-0.5, 0.5, 1, 0)
    h = torch.tensor([3.0, 4.0, 1.0, 0.0])
    v = torch.tensor([1.0, 1.0, 0.0, 0.0])
    assert torch.allclose(remove_direction(h, v), torch.tensor([-0.5, 0.5, 1.0, 0.0]))
    assert torch.equal(remove_direction(h, v, alpha=0.0), h)
    with pytest.raises(ValueError):
        remove_direction(h, v, alpha=1.5)
    with pytest.raises(ValueError):
        remove_direction(h, torch.zeros(4))


def test_remove_direction_with_center():
    h, mu, v = torch.tensor([3.0, 2.0]), torch.tensor([1.0, 0.0]), torch.tensor([1.0, 0.0])
    # (h - mu).v / v.v = 2 -> h_new = h - 2 v = (1, 2)
    assert torch.allclose(remove_direction(h, v, center=mu), torch.tensor([1.0, 2.0]))


def test_jlens_direction_with_and_without_gain():
    J = torch.tensor([[2.0, 1.0], [1.0, 3.0]])
    W = torch.tensor([[1.0, -1.0]])
    assert torch.allclose(calculate_jlens_direction(J, W, 0), torch.tensor([1.0, -2.0]))
    g = torch.tensor([2.0, 1.0])  # v = J^T (g * w) = J^T [2, -1] = [3, -1]
    assert torch.allclose(calculate_jlens_direction(J, W, 0, g), torch.tensor([3.0, -1.0]))


def test_projection_removes_span_and_handles_duplicates():
    torch.manual_seed(0)
    h = torch.randn(5, 16)
    v = torch.randn(5, 3, 16)
    v_dup = torch.cat([v, v[:, :1] * 2], dim=1)  # exactly dependent 4th vector
    proj, rank = project_onto_span(h, v)
    proj_dup, rank_dup = project_onto_span(h, v_dup)
    assert torch.allclose(proj, proj_dup, atol=1e-5)
    assert (rank == 3).all() and (rank_dup == 3).all()
    assert torch.allclose(v @ (h - proj).unsqueeze(-1), torch.zeros(5, 3, 1), atol=1e-4)


def test_matched_random_perturbation_norms_and_reproducibility():
    m = torch.tensor([0.0, 1.0, 5.5])
    a = matched_random_perturbation(m, 32, torch.Generator().manual_seed(3))
    b = matched_random_perturbation(m, 32, torch.Generator().manual_seed(3))
    assert torch.equal(a, b)
    assert torch.allclose(a.norm(dim=-1), m, atol=1e-6)
    assert site_seed(1, 2, "x") == site_seed(1, 2, "x") != site_seed(1, 3, "x")


def test_rmsnorm_gain_is_recovered():
    norm = torch.nn.RMSNorm(8)
    with torch.no_grad():
        norm.weight.copy_(torch.arange(1.0, 9.0))
    gain, off_diag = effective_norm_gain(norm, 8, torch.device("cpu"), torch.float32)
    assert off_diag < 1e-6
    assert torch.allclose(gain / gain[0], torch.arange(1.0, 9.0))


class Stack(torch.nn.Module):
    def __init__(self, d=8, n=3):
        super().__init__()
        torch.manual_seed(0)
        self.layers = torch.nn.ModuleList(torch.nn.Linear(d, d) for _ in range(n))

    def forward(self, x):
        for layer in self.layers:
            x = x + layer(x)
        return x


def make_basis(d=8, vocab=20):
    torch.manual_seed(1)
    jac = {l: torch.eye(d) + 0.1 * torch.randn(d, d) for l in range(3)}
    return JLensBasis(jac, torch.randn(vocab, d), torch.rand(d) + 0.5, [0, 1, 2], torch.device("cpu"))


def test_basis_scores_equal_lens_logit_ranking():
    basis = make_basis()
    h = torch.randn(4, 8)
    lens_logits = ((h @ basis.J[1].T) * basis.gain) @ basis.unembed.T  # w^T diag(g) J h
    all_ids = torch.arange(20).expand(4, 20)
    dots = torch.einsum("pvd,pd->pv", basis.vectors(1, all_ids), h)  # v_t . h
    assert torch.allclose(lens_logits, dots, atol=1e-4)
    assert torch.equal(basis.top_tokens(h, 1, 3), lens_logits.topk(3).indices)


def test_noop_and_alpha_zero_are_identity():
    model, x = Stack(), torch.randn(1, 6, 8)
    reference = model(x)
    with residual_edits(model.layers, {1: ResidualEditHook(layer=1, mode="noop")}):
        assert torch.equal(model(x), reference)
    zero = {1: ResidualEditHook(layer=1, mode="j_ablation", basis=make_basis(), top_k=2, first_position=2, alpha=0.0)}
    with residual_edits(model.layers, zero):
        assert torch.equal(model(x), reference)
    assert len(zero[1].records) == 1


def test_random_control_replays_c1_norms_exactly():
    model, x = Stack(), torch.randn(1, 6, 8)
    basis = make_basis()
    j_hooks = {l: ResidualEditHook(layer=l, mode="j_ablation", basis=basis, top_k=2, first_position=2) for l in (0, 1, 2)}
    with residual_edits(model.layers, j_hooks):
        model(x)
    r_hooks = {
        l: ResidualEditHook(layer=l, mode="random_ablation", target_norms=j_hooks[l].site_delta_norms,
                            first_position=2, random_seed=site_seed(0, l, "p"))
        for l in (0, 1, 2)
    }
    with residual_edits(model.layers, r_hooks):
        model(x)
    for l in (0, 1, 2):  # every layer, every site: ||delta_R|| == C1's ||delta_J||
        assert torch.allclose(r_hooks[l].site_delta_norms, j_hooks[l].site_delta_norms, rtol=1e-4, atol=1e-6)
        assert r_hooks[l].records[0].n_positions == 4  # positions 2..5
    assert count_forward_hooks(model.layers) == 0
    with pytest.raises(ValueError):
        ResidualEditHook(layer=0, mode="random_ablation", random_seed=0)  # no target_norms


def test_concept_plan_edits_only_planned_sites():
    model, x = Stack(), torch.randn(1, 6, 8)
    basis = make_basis()
    plan = torch.full((4, 2), -1, dtype=torch.long)  # positions 2..5
    plan[1] = torch.tensor([3, 7])  # only position 3 gets two concept directions
    hook = ResidualEditHook(layer=1, mode="j_ablation", basis=basis, site_tokens=plan, first_position=2)
    captured = {}
    with residual_edits(model.layers, {1: hook}):
        handle = model.layers[1].register_forward_hook(lambda _m, _a, out: captured.setdefault("h", out.detach().clone()))
        model(x)
        handle.remove()
    norms = hook.site_delta_norms
    assert norms[1] > 0 and torch.all(norms[[0, 2, 3]] == 0)
    assert hook.records[0].n_edited_sites == 1
    v = basis.vectors(1, torch.tensor([3, 7]))
    assert torch.allclose(v @ captured["h"][0, 3], torch.zeros(2), atol=1e-4)


def test_excluded_tokens_never_selected():
    basis = make_basis()
    h = torch.randn(5, 8)
    banned = basis.top_tokens(h, 1, 3).flatten().unique()
    assert not torch.isin(basis.top_tokens(h, 1, 3, excluded=banned), banned).any()


def test_only_target_positions_change():
    model, x = Stack(), torch.randn(1, 6, 8)
    captured = {}

    def grab(_m, _a, out):
        captured.setdefault("outs", []).append(out.detach().clone())

    for mode in ("baseline", "j_ablation"):
        handles = []
        hooks = {} if mode == "baseline" else {1: ResidualEditHook(layer=1, mode="j_ablation", basis=make_basis(), top_k=2, first_position=3)}
        with residual_edits(model.layers, hooks):
            handles.append(model.layers[1].register_forward_hook(grab))
            model(x)
            handles[0].remove()
    clean, edited = captured["outs"]
    assert torch.equal(clean[0, :3], edited[0, :3])  # positions < 3 untouched
    assert not torch.equal(clean[0, 3:], edited[0, 3:])


def test_hooks_removed_even_after_exception():
    model = Stack()
    with pytest.raises(RuntimeError):
        with residual_edits(model.layers, {0: ResidualEditHook(layer=0, mode="noop")}):
            raise RuntimeError("boom")
    assert count_forward_hooks(model.layers) == 0


def test_j_ablation_zeroes_projection_on_selected_vectors():
    model, x = Stack(), torch.randn(1, 6, 8)
    basis = make_basis()
    captured = {}

    def grab(_m, _a, out):
        captured["h"] = out.detach().clone()

    hook = ResidualEditHook(layer=1, mode="j_ablation", basis=basis, top_k=2, first_position=2)
    with residual_edits(model.layers, {1: hook}):
        handle = model.layers[1].register_forward_hook(grab)  # runs after the edit hook
        model(x)
        handle.remove()
    tokens = torch.tensor(hook.records[0].last_position_tokens)
    v = basis.vectors(1, tokens)
    assert torch.allclose(v @ captured["h"][0, -1], torch.zeros(2), atol=1e-4)
