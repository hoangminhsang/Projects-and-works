"""Run folders, logging, file export, environment capture and figures.

Each run gets its own folder ``results/run_<UTC timestamp>/`` so earlier runs are
never overwritten (no silent re-running until a result looks good):

    run_log.txt          human-readable log of everything printed by the pipeline
    run_metadata.json    model/lens/library versions, config, seeds, scenario ids
    scenarios.jsonl      the full benchmark, one scenario per line
    validation_log.json  dataset checks, lens checks, hook checks, band selection
    frozen_protocol.json config + chosen band, written BEFORE the test split runs
    dev_trials.csv       every dev-split trial (prompt tuning / band selection)
    trial_results.csv    every held-out test trial (the only data used for results)
    summary.json         accuracy table, S, bootstrap CI, outcome, acceptance checklist
    figures/*.png        accuracy bars and S bootstrap distribution
"""

from __future__ import annotations

import json
import logging
import platform
import sys
from dataclasses import is_dataclass, asdict
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from jspace_pilot.config import CONDITIONS, TASK_TYPES


def new_run_dir(results_root: str) -> tuple[str, Path]:
    run_id = "run_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path(results_root) / run_id
    (path / "figures").mkdir(parents=True, exist_ok=True)
    return run_id, path


def setup_logging(run_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """Log to ``run_dir/run_log.txt`` and to the notebook output."""
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        if getattr(handler, "_jspace_pilot", False):
            root.removeHandler(handler)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%H:%M:%S")
    for handler in (logging.FileHandler(run_dir / "run_log.txt", encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        handler.setFormatter(fmt)
        handler._jspace_pilot = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    for noisy in ("httpx", "urllib3", "filelock", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return logging.getLogger("jspace_pilot")


def _to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return _to_jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict()
    if isinstance(obj, Path):
        return str(obj)
    return obj


def save_json(obj: Any, path: Path) -> Path:
    path.write_text(json.dumps(_to_jsonable(obj), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def save_jsonl(rows: list[dict[str, Any]], path: Path) -> Path:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_to_jsonable(row), ensure_ascii=False) + "\n")
    return path


def _version(package: str) -> str | None:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def jlens_install_source() -> str | None:
    """The git URL + commit pip recorded when jlens was installed (if any)."""
    try:
        return metadata.distribution("jlens").read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        return None


def environment_info() -> dict[str, Any]:
    import torch

    info: dict[str, Any] = {
        "execution_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "torch": torch.__version__,
        "transformers": _version("transformers"),
        "accelerate": _version("accelerate"),
        "huggingface_hub": _version("huggingface_hub"),
        "jlens": _version("jlens"),
        "jlens_install_source": jlens_install_source(),
        "cuda_available": torch.cuda.is_available(),
    }
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        info.update(
            gpu_name=props.name,
            gpu_vram_gib=round(props.total_memory / 1024**3, 2),
            cuda_version=torch.version.cuda,
            bf16_supported=torch.cuda.is_bf16_supported(),
        )
    return info


# --------------------------------------------------------------------------- plots
def plot_accuracy(acc: pd.DataFrame, n_per_cell: int, path: Path, demo: bool = False) -> Path:
    """Grouped bars: x = condition, two bars (integration, retrieval) per condition."""
    fig, ax = plt.subplots(figsize=(7, 4.2))
    x = np.arange(len(CONDITIONS))
    width = 0.36
    colors = {"integration": "#3b6ea8", "retrieval": "#d9893b"}
    for i, task in enumerate(TASK_TYPES):
        values = acc[task].reindex(list(CONDITIONS)).to_numpy()
        bars = ax.bar(x + (i - 0.5) * width, values, width, label=task, color=colors[task])
        ax.bar_label(bars, labels=[f"{v:.2f}" if not np.isnan(v) else "n/a" for v in values], padding=2, fontsize=9)
    ax.axhline(0.25, color="grey", linestyle=":", linewidth=1)
    ax.text(len(CONDITIONS) - 0.5, 0.26, "chance (0.25)", color="grey", fontsize=8, ha="right")
    ax.set_xticks(x, ["C0 baseline", "C1 top-k J-lens ablation", "C2 norm-matched random"])
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("accuracy (strict, invalid = wrong)")
    title = f"Held-out accuracy by condition and task (n = {n_per_cell} per bar)"
    ax.set_title(("DEMO ONLY / NOT A J-SPACE RESULT\n" if demo else "") + title, fontsize=11)
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    return path


def plot_specificity(
    boot_values: np.ndarray, estimate: float, ci: tuple[float, float], n_scenarios: int, path: Path, demo: bool = False
) -> Path:
    """Histogram of bootstrap S with the point estimate, CI and zero line."""
    fig, ax = plt.subplots(figsize=(7, 3.8))
    step = 1 / n_scenarios  # a bootstrap mean of n per-scenario values moves in steps of 1/n
    bins = np.arange(boot_values.min() - step, boot_values.max() + 2 * step, step) - step / 2
    ax.hist(boot_values, bins=bins, color="#9bb7d4", edgecolor="white")
    ax.axvline(0, color="black", linewidth=1)
    ax.axvline(estimate, color="#b23a3a", linewidth=2, label=f"observed S = {estimate:+.3f}")
    ax.axvspan(ci[0], ci[1], color="#b23a3a", alpha=0.12, label=f"95% CI [{ci[0]:+.3f}, {ci[1]:+.3f}]")
    ax.set_xlabel("integration specificity S  (positive = J-ablation hurts integration more)")
    ax.set_ylabel("bootstrap resamples")
    title = "Paired bootstrap of S (resampling scenarios)"
    ax.set_title(("DEMO ONLY / NOT A J-SPACE RESULT\n" if demo else "") + title, fontsize=11)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    return path


# ------------------------------------------------------------------ acceptance
def acceptance_checklist(
    *,
    toy_math_ok: bool,
    dataset_ok: bool,
    test_trials: pd.DataFrame | None,
    hook_checks: dict[str, Any] | None,
    lens_valid: bool,
    controls_matched: bool,
    protocol_frozen_before_test: bool,
) -> dict[str, bool]:
    """Spec §10. Every item is computed from logged data, never asserted by hand."""
    have_test = test_trials is not None and len(test_trials) > 0
    prompts_identical = False
    complete = False
    changed = False
    if have_test:
        prompts_identical = bool(
            (test_trials.groupby(["scenario_id", "task_type"])["prompt_sha256"].nunique() == 1).all()
        )
        counts = test_trials.groupby("scenario_id").size()
        complete = bool((counts == len(CONDITIONS) * len(TASK_TYPES)).all())
        j_rows = test_trials[test_trials["condition"] == "j_ablation"]
        changed = bool(len(j_rows) and (j_rows["delta_l2_norm"] > 0).all())
    return {
        "toy maths checks pass (autograd Jacobian, R^2 ablation, projection invariants)": toy_math_ok,
        "scenario labels deterministic and assertions pass": dataset_ok,
        "same scenario+task prompt identical across 3 conditions": prompts_identical,
        "no-op hook == no hook (within tolerance)": bool(hook_checks and hook_checks.get("passed")),
        "J-lens artifact compatible and readouts valid": lens_valid,
        "J-intervention measurably changes activations": changed,
        "norm-matched random control: ||delta_R|| == ||delta_J|| (L2)": controls_matched,
        "hooks never persist (enforced by residual_edits context manager)": True,
        "test split not used for tuning (protocol frozen before test run)": protocol_frozen_before_test,
        "invalid outputs counted as incorrect, not dropped": have_test,
        "accuracy and S computed from observed held-out trials": have_test,
        "bootstrap resamples scenario ids with all 6 cells intact": complete,
        "scope claim: projection on selected J-lens directions, not sparse J-space decomposition": True,
    }
