"""Preflight checks: catch set-up problems BEFORE the model is loaded.

Run from the notebook (section 03) or from a terminal:

    python -m jspace_pilot.preflight

Each check returns OK, WARN (the run can continue) or FAIL (fix first), with a
one-line hint on how to fix it.
"""

from __future__ import annotations

import ast
import importlib
import json
import shutil
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from jspace_pilot.config import EXPERIMENT_ROOT, ExperimentConfig

NOTEBOOK = EXPERIMENT_ROOT / "ai_welfare_jspace_pilot.ipynb"
REQUIRED = ("torch", "transformers", "accelerate", "huggingface_hub", "jlens", "numpy", "pandas", "matplotlib", "pytest")


@dataclass
class Check:
    name: str
    status: str  # "OK" | "WARN" | "FAIL"
    detail: str
    fix: str = ""


def notebook_import_problems(notebook: Path = NOTEBOOK) -> list[str]:
    """Names the notebook imports from ``jspace_pilot`` that do not exist in the code.

    This is the check that would have caught "cannot import name 'run_forward'".
    """
    cells = json.loads(notebook.read_text(encoding="utf-8"))["cells"]
    problems = []
    for index, cell in enumerate(cells):
        if cell["cell_type"] != "code":
            continue
        for node in ast.walk(ast.parse("".join(cell["source"]))):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("jspace_pilot"):
                module = importlib.import_module(node.module)
                problems += [f"cell {index}: {node.module}.{a.name}" for a in node.names if not hasattr(module, a.name)]
    return problems


def _check_packages() -> list[Check]:
    checks = []
    for name in REQUIRED:
        try:
            importlib.import_module(name)
            version = metadata.version(name) if name != "jlens" else metadata.version("jlens")
            checks.append(Check(f"package {name}", "OK", version))
        except Exception as exc:  # noqa: BLE001 - report any import failure
            checks.append(Check(f"package {name}", "FAIL", f"{type(exc).__name__}: {exc}",
                                "pip install -r requirements.txt (in the SAME environment as the notebook kernel)"))
    try:
        major, minor = (int(x) for x in metadata.version("transformers").split(".")[:2])
        if (major, minor) < (5, 5):
            checks.append(Check("transformers >= 5.5", "FAIL", metadata.version("transformers"), "pip install -U 'transformers>=5.5'"))
    except Exception:  # noqa: BLE001
        pass
    return checks


def _check_jlens_api() -> Check:
    try:
        import jlens

        missing = [n for n in ("JacobianLens", "ActivationRecorder", "from_hf", "Layout") if not hasattr(jlens, n)]
        if missing:
            return Check("jlens API", "FAIL", f"missing {missing}", "install jlens from requirements.txt (pinned commit)")
        return Check("jlens API", "OK", "JacobianLens, ActivationRecorder, from_hf, Layout")
    except Exception as exc:  # noqa: BLE001
        return Check("jlens API", "FAIL", str(exc), "pip install -r requirements.txt")


def _check_notebook() -> Check:
    if not NOTEBOOK.exists():
        return Check("notebook matches code", "WARN", f"{NOTEBOOK.name} not found")
    try:
        problems = notebook_import_problems()
    except Exception as exc:  # noqa: BLE001
        return Check("notebook matches code", "FAIL", f"{type(exc).__name__}: {exc}", "re-download the experiment folder")
    if problems:
        return Check("notebook matches code", "FAIL", "; ".join(problems),
                     "the notebook file is older/newer than jspace_pilot/: close and reopen it (File > Revert)")
    return Check("notebook matches code", "OK", "every jspace_pilot import in the notebook exists")


def _check_results_dir(config: ExperimentConfig) -> Check:
    root = Path(config.results_root)
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".write_test"
        probe.write_text("ok")
        probe.unlink()
        return Check("results folder writable", "OK", str(root))
    except Exception as exc:  # noqa: BLE001
        return Check("results folder writable", "FAIL", str(exc), "check folder permissions / Drive mount")


def _check_gpu(config: ExperimentConfig) -> list[Check]:
    import torch

    if not torch.cuda.is_available():
        return [Check("CUDA GPU", "WARN", "no CUDA device: model sections will be skipped (design/demo mode)",
                      "on Colab: Runtime > Change runtime type > L4 / A100")]
    props = torch.cuda.get_device_properties(0)
    free, total = (x / 1024**3 for x in torch.cuda.mem_get_info())
    checks = [Check("CUDA GPU", "OK", f"{props.name}, {total:.1f} GiB")]
    major, _ = torch.cuda.get_device_capability(0)
    if major < 8:
        checks.append(Check("native bf16", "WARN", "this GPU has no native bf16 (e.g. T4): slow", "prefer L4 / A100"))
    used = total - free
    if used > 2.5:
        checks.append(Check("free VRAM", "WARN", f"{free:.1f} of {total:.1f} GiB free: {used:.1f} GiB already used by another process",
                            "an old notebook kernel may still hold the model: restart/shut down other kernels"))
    else:
        checks.append(Check("free VRAM", "OK", f"{free:.1f} GiB free"))
    return checks


def _check_model_cache(config: ExperimentConfig) -> Check:
    try:
        from huggingface_hub import try_to_load_from_cache

        cached = try_to_load_from_cache(config.model_id, "model.safetensors.index.json", revision=config.model_revision)
        if isinstance(cached, str):
            return Check("model in local cache", "OK", config.model_id)
        free_gib = shutil.disk_usage(Path.home()).free / 1024**3
        status = "WARN" if free_gib > 15 else "FAIL"
        return Check("model in local cache", status, f"not cached: ~9 GB download on first load ({free_gib:.0f} GiB disk free)",
                     "needs internet + >= 15 GiB free disk")
    except Exception as exc:  # noqa: BLE001
        return Check("model in local cache", "WARN", f"could not check: {exc}")


def run_preflight(config: ExperimentConfig | None = None) -> list[Check]:
    config = config or ExperimentConfig()
    checks = [Check("python", "OK", sys.version.split()[0] + f"  ({sys.executable})")]
    checks += _check_packages()
    if all(c.status == "OK" for c in checks if c.name.startswith("package")):
        checks.append(_check_jlens_api())
        checks += _check_gpu(config)
        checks.append(_check_model_cache(config))
    checks.append(_check_notebook())
    checks.append(_check_results_dir(config))
    return checks


def print_report(checks: list[Check]) -> bool:
    """Print a table; return True if nothing FAILed."""
    icon = {"OK": "✓", "WARN": "!", "FAIL": "✗"}
    for c in checks:
        print(f"  {icon[c.status]} {c.status:<4} {c.name:<24} {c.detail}")
        if c.fix and c.status != "OK":
            print(f"         -> fix: {c.fix}")
    ok = not any(c.status == "FAIL" for c in checks)
    print("\nPREFLIGHT:", "PASSED" if ok else "FAILED - fix the ✗ items above before running the experiment")
    return ok


if __name__ == "__main__":
    sys.exit(0 if print_report(run_preflight()) else 1)
