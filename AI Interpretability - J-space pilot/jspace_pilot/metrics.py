"""Accuracy, integration specificity S, paired bootstrap, and outcome rules.

Pure pandas/numpy so it can be unit-tested without a GPU.

Primary metric (spec §6)::

    S = (A[random, integration] - A[J, integration])
      - (A[random, retrieval]   - A[J, retrieval])

S > 0 means: relative to a matched random perturbation, J-lens ablation hurts
integration more than it hurts retrieval.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from jspace_pilot.config import CONDITIONS, TASK_TYPES, ExperimentConfig


def accuracy_table(trials: pd.DataFrame, column: str = "is_correct") -> pd.DataFrame:
    """Rows = condition, columns = task type, values = mean of ``column``."""
    table = trials.pivot_table(index="condition", columns="task_type", values=column, aggfunc="mean")
    return table.reindex(index=list(CONDITIONS), columns=list(TASK_TYPES))


def specificity_from_table(acc: pd.DataFrame) -> float:
    """S from a condition x task accuracy table."""
    integration_drop = acc.loc["random_ablation", "integration"] - acc.loc["j_ablation", "integration"]
    retrieval_drop = acc.loc["random_ablation", "retrieval"] - acc.loc["j_ablation", "retrieval"]
    return float(integration_drop - retrieval_drop)


def per_scenario_specificity(trials: pd.DataFrame, column: str = "is_correct") -> pd.Series:
    """S computed inside each scenario (one value per scenario_id).

    Because every scenario contributes exactly one trial to each of the four
    cells used by S, the mean of this series equals the pooled S.

    Raises:
        ValueError: if any scenario is missing one of the four required cells.
    """
    needed = trials[trials["condition"].isin(["j_ablation", "random_ablation"])]
    wide = needed.pivot_table(
        index="scenario_id", columns=["condition", "task_type"], values=column, aggfunc="mean"
    )
    required = [(c, t) for c in ("j_ablation", "random_ablation") for t in TASK_TYPES]
    missing = [col for col in required if col not in wide.columns]
    if missing or wide[required].isna().any().any():
        raise ValueError(f"incomplete scenarios for S (missing cells {missing})")
    return (wide[("random_ablation", "integration")] - wide[("j_ablation", "integration")]) - (
        wide[("random_ablation", "retrieval")] - wide[("j_ablation", "retrieval")]
    )


@dataclass(frozen=True)
class BootstrapResult:
    estimate: float
    ci_low: float
    ci_high: float
    n_scenarios: int
    n_bootstrap: int
    ci_level: float

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def paired_bootstrap_specificity(
    trials: pd.DataFrame,
    *,
    n_bootstrap: int = 2000,
    ci_level: float = 0.95,
    seed: int = 0,
    column: str = "is_correct",
) -> tuple[BootstrapResult, np.ndarray]:
    """Percentile bootstrap CI for S, resampling whole scenarios.

    Each resample draws ``n`` scenario_ids with replacement and keeps *all* of
    that scenario's trials together (the pairing across conditions and tasks is
    never broken).

    Returns:
        (summary, array of bootstrap S values)
    """
    per_scenario = per_scenario_specificity(trials, column).to_numpy()
    rng = np.random.default_rng(seed)
    n = len(per_scenario)
    draws = rng.integers(0, n, size=(n_bootstrap, n))
    boot = per_scenario[draws].mean(axis=1)
    tail = (1 - ci_level) / 2 * 100
    low, high = np.percentile(boot, [tail, 100 - tail])
    summary = BootstrapResult(
        estimate=float(per_scenario.mean()),
        ci_low=float(low),
        ci_high=float(high),
        n_scenarios=n,
        n_bootstrap=n_bootstrap,
        ci_level=ci_level,
    )
    return summary, boot


@dataclass(frozen=True)
class Outcome:
    code: str  # "A", "B", "C", "C'", "D", "E", "N"
    label: str
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def classify_outcome(
    acc: pd.DataFrame | None,
    boot: BootstrapResult | None,
    *,
    lens_validated: bool,
    controls_matched: bool,
    config: ExperimentConfig,
    concept_coverage: float | None = None,
) -> Outcome:
    """Map observed numbers onto the pre-registered outcomes of spec §11.

    Rules are applied in order; the first that fires wins.

    * D  - no validated lens (or no held-out run): technical result only.
    * N  - (concept selection) fewer than ``min_concept_coverage`` of test trials
           had any concept site to ablate: the task concepts are not in the
           J-lens readout, so C1 could not test H1. Itself informative: it fits
           the paper's "automatic processing does not route through J-space".
    * C  - test invalid / nonspecific: baseline below threshold on either task,
           controls not matched, or retrieval collapses under J-ablation.
    * A  - S > 0 and the CI lower bound is above 0.
    * C' - S < 0 and the CI upper bound is below 0 (contrary to H1).
    * B  - |S| small and CI narrow: useful negative.
    * E  - none of the above: inconclusive (CI includes 0 but is wide).
    """
    if not lens_validated or acc is None or boot is None:
        return Outcome("D", "No validated J-lens run: feasibility result only", ["lens not validated"])

    if concept_coverage is not None and concept_coverage < config.min_concept_coverage:
        return Outcome(
            "N",
            "Task concepts rarely appear in the J-lens readout: ablation test not informative",
            [f"only {concept_coverage:.0%} of test trials had a concept site (< {config.min_concept_coverage:.0%})"],
        )

    reasons: list[str] = []
    for task in TASK_TYPES:
        base = acc.loc["baseline", task]
        if base < config.baseline_min_accuracy:
            reasons.append(f"baseline {task} accuracy {base:.2f} < {config.baseline_min_accuracy}")
    if not controls_matched:
        reasons.append("random control not matched to J-ablation in L2 norm")
    retrieval_drop = acc.loc["baseline", "retrieval"] - acc.loc["j_ablation", "retrieval"]
    if retrieval_drop >= config.general_damage_drop:
        reasons.append(f"retrieval drops {retrieval_drop:.2f} under J-ablation (general damage)")
    if reasons:
        return Outcome("C", "Invalid or nonspecific test", reasons)

    s, low, high = boot.estimate, boot.ci_low, boot.ci_high
    ci_text = f"S = {s:+.3f}, {boot.ci_level:.0%} CI [{low:+.3f}, {high:+.3f}]"
    if s > 0 and low > 0:
        return Outcome("A", "Selective impairment of integration (supports H1)", [ci_text])
    if s < 0 and high < 0:
        return Outcome("C'", "Selective impairment of retrieval (contrary to H1)", [ci_text])
    if abs(s) <= config.null_max_abs_s and (high - low) <= config.null_max_ci_width:
        return Outcome("B", "No selectivity detected; CI narrow enough to be informative", [ci_text])
    return Outcome("E", "Inconclusive: CI includes zero and is too wide", [ci_text])
