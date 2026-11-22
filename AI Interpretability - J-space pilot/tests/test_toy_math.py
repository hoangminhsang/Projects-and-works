"""Spec v2 §5.2 / §5.6 / §5.12 toy checks must all pass."""

import pytest

pytest.importorskip("torch")

from jspace_pilot.toy_math import test_projection_invariants as projection_invariants  # noqa: E402
from jspace_pilot.toy_math import toy_direction_ablation, verify_toy_autograd  # noqa: E402


def test_toy_autograd_jacobian():
    result = verify_toy_autograd()
    assert result["autograd_matches_analytic"]
    assert result["finite_diff_matches_analytic"]
    assert result["taylor_rule_holds"]
    assert result["f(x)"] == [8.0, 9.0]


def test_toy_direction_ablation_numbers():
    r = toy_direction_ablation()
    assert r["J h"] == [8.0, 9.0]
    assert r["score_before = w.(J h)"] == -1.0
    assert r["v = J^T w"] == [1.0, -2.0]
    assert r["v.h (should equal score)"] == -1.0
    assert r["h_ablated"] == pytest.approx([3.2, 1.6])
    assert r["v.h_ablated"] == pytest.approx(0.0, abs=1e-6)
    assert r["J h_ablated"] == pytest.approx([8.0, 8.0])
    assert r["score_after = w.(J h_ablated)"] == pytest.approx(0.0, abs=1e-5)


def test_projection_invariants_all_true():
    checks = projection_invariants()
    failed = [name for name, ok in checks.items() if not ok]
    assert not failed, failed
