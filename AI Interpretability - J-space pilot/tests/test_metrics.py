import numpy as np
import pandas as pd
import pytest

from jspace_pilot.config import ExperimentConfig
from jspace_pilot.metrics import (
    accuracy_table,
    classify_outcome,
    paired_bootstrap_specificity,
    per_scenario_specificity,
    specificity_from_table,
)


def make_trials(correct: dict[tuple[str, str], list[int]]) -> pd.DataFrame:
    rows = []
    for (condition, task), values in correct.items():
        for i, v in enumerate(values):
            rows.append(dict(scenario_id=f"s{i}", condition=condition, task_type=task, is_correct=bool(v)))
    return pd.DataFrame(rows)


def test_specificity_hand_example():
    # 4 scenarios. Random: integration 3/4, retrieval 4/4. J: integration 1/4, retrieval 4/4.
    trials = make_trials({
        ("baseline", "integration"): [1, 1, 1, 1],
        ("baseline", "retrieval"): [1, 1, 1, 1],
        ("j_ablation", "integration"): [1, 0, 0, 0],
        ("j_ablation", "retrieval"): [1, 1, 1, 1],
        ("random_ablation", "integration"): [1, 1, 1, 0],
        ("random_ablation", "retrieval"): [1, 1, 1, 1],
    })
    acc = accuracy_table(trials)
    s = specificity_from_table(acc)
    assert s == pytest.approx((0.75 - 0.25) - (1.0 - 1.0))
    assert per_scenario_specificity(trials).mean() == pytest.approx(s)


def test_bootstrap_contains_estimate_and_is_reproducible():
    rng = np.random.default_rng(0)
    cells = {(c, t): rng.integers(0, 2, 24).tolist() for c in ("baseline", "j_ablation", "random_ablation") for t in ("integration", "retrieval")}
    trials = make_trials(cells)
    a, boot_a = paired_bootstrap_specificity(trials, n_bootstrap=500, seed=1)
    b, boot_b = paired_bootstrap_specificity(trials, n_bootstrap=500, seed=1)
    assert a == b and np.array_equal(boot_a, boot_b)
    assert a.ci_low <= a.estimate <= a.ci_high
    assert a.n_scenarios == 24


def test_incomplete_scenarios_rejected():
    trials = make_trials({("j_ablation", "integration"): [1, 1], ("j_ablation", "retrieval"): [1, 1],
                          ("random_ablation", "integration"): [1], ("random_ablation", "retrieval"): [1, 1]})
    with pytest.raises(ValueError):
        per_scenario_specificity(trials)


def test_outcome_rules():
    cfg = ExperimentConfig()
    good = make_trials({
        ("baseline", "integration"): [1] * 24, ("baseline", "retrieval"): [1] * 24,
        ("j_ablation", "integration"): [0] * 12 + [1] * 12, ("j_ablation", "retrieval"): [1] * 24,
        ("random_ablation", "integration"): [1] * 24, ("random_ablation", "retrieval"): [1] * 24,
    })
    acc = accuracy_table(good)
    boot, _ = paired_bootstrap_specificity(good, n_bootstrap=500, seed=0)
    assert classify_outcome(acc, boot, lens_validated=True, controls_matched=True, config=cfg).code == "A"
    assert classify_outcome(acc, boot, lens_validated=False, controls_matched=True, config=cfg).code == "D"
    assert classify_outcome(acc, boot, lens_validated=True, controls_matched=False, config=cfg).code == "C"

    null = make_trials({(c, t): [1] * 24 for c in ("baseline", "j_ablation", "random_ablation") for t in ("integration", "retrieval")})
    acc0 = accuracy_table(null)
    boot0, _ = paired_bootstrap_specificity(null, n_bootstrap=500, seed=0)
    assert classify_outcome(acc0, boot0, lens_validated=True, controls_matched=True, config=cfg).code == "B"
