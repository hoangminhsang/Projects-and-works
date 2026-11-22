"""Experiment configuration.

Every knob that could change a result lives here, in one frozen dataclass, so a
run can be described completely by ``asdict(config)`` and written to
``run_metadata.json``. Nothing in this file may be edited after the held-out
test split has been run (see the pre-registration notes in the notebook).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

#: Root of the ``experiment/`` folder (this file lives in ``experiment/jspace_pilot``).
EXPERIMENT_ROOT = Path(__file__).resolve().parent.parent

CONDITIONS: tuple[str, ...] = ("baseline", "j_ablation", "random_ablation")
TASK_TYPES: tuple[str, ...] = ("integration", "retrieval")


@dataclass(frozen=True)
class AblationBand:
    """A candidate intervention site: a contiguous band of residual layers.

    Attributes:
        name: Short label used in logs ("medium", "light").
        first_layer: First residual block (inclusive) whose output is edited.
        last_layer: Last residual block (inclusive) whose output is edited.
    """

    name: str
    first_layer: int
    last_layer: int

    @property
    def layers(self) -> tuple[int, ...]:
        return tuple(range(self.first_layer, self.last_layer + 1))


@dataclass(frozen=True)
class ExperimentConfig:
    """All hyperparameters of the pilot. Frozen: create a new one to change it."""

    # --- reproducibility -------------------------------------------------
    seed: int = 42
    #: v2: tool 3 lists backups for several servers (harder retrieval, see agent.py).
    prompt_template_version: str = "soc-v2"

    # --- dataset -----------------------------------------------------------
    n_dev: int = 4  # minimum: 1 per action
    #: MINIMUM run: 1 per action = 4 held-out scenarios (~2 min). This only proves the pipeline runs;
    #: with n = 4 the CI on S is far too wide for any conclusion. Use >= 12 for a real result.
    n_test_per_action: int = 1
    #: Servers listed by tool 3: the alerted one + (n - 1) decoys with their own backups.
    n_backup_entries: int = 3

    # --- model ---------------------------------------------------------------
    model_id: str = "Qwen/Qwen3.5-4B"
    #: Pin the exact checkpoint the lens was fitted on. ``None`` = latest "main".
    model_revision: str | None = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
    dtype: str = "bfloat16"
    #: Number of residual blocks kept on the GPU; the rest are streamed from CPU
    #: RAM by accelerate. ``None`` = estimate from free VRAM at load time.
    n_gpu_layers: int | None = None
    #: VRAM (GiB) kept free for activations, the lens matrices and lens scoring.
    vram_reserve_gib: float = 1.8

    # --- Jacobian lens -------------------------------------------------------
    lens_repo: str = "neuronpedia/jacobian-lens"
    lens_revision: str = "qwen-n1000"
    lens_filename: str = (
        "qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt"
    )
    jlens_source: str = "https://github.com/anthropics/jacobian-lens"
    jlens_commit_tested: str = "581d398613e5602a5af361e1c34d3a92ea82ba8e"

    # --- intervention --------------------------------------------------------
    #: How C1 chooses which J-lens directions to remove.
    #:   "concept": observe first, then intervene. A clean pass reads the J-lens at
    #:              every (layer, position); wherever a PRE-REGISTERED task concept
    #:              token (``concept_words``) is in the lens top-``concept_top_n``,
    #:              its direction is removed there. (Primary, v2.)
    #:   "topk":    the v1 untargeted recipe (paper §3.5.2): the top-k lens tokens at
    #:              every site, excluding special / whitespace / punctuation tokens.
    selection: str = "concept"
    #: Decision-relevant concepts, fixed before any v2 data was seen. Every
    #: single-token spelling ("word", " word", "Word", " Word") is used.
    concept_words: tuple[str, ...] = (
        "high", "low", "medium", "risk", "critical", "service", "backup", "ready",
        "isolate", "isolation", "monitor", "monitoring", "fail", "failover",
        "revoke", "credentials", "safe", "true", "false",
    )
    #: A concept is "present" at a site if it ranks in the lens top-n there.
    concept_top_n: int = 20
    #: Candidate bands, tried IN THIS ORDER on the dev split only. Qwen3.5-4B has
    #: 32 blocks. "wide" = layers 8-24 (25-75% depth, where the paper finds the
    #: workspace); "mid" = 12-20 is the fallback if "wide" damages the model.
    candidate_bands: tuple[AblationBand, ...] = (
        AblationBand("wide", 8, 24),
        AblationBand("mid", 12, 20),
    )
    #: J-lens vectors removed per site in "topk" mode; the paper uses k=10.
    top_k: int = 10
    #: Tokens in the clean model's top-n next-token prediction at a position are
    #: never ablated there (paper §3.5.2: target internal reasoning, not report).
    protect_top_n_output: int = 10
    #: Positions before this index are never edited. The lens was fitted with the
    #: same cut (``jlens.fitting.SKIP_FIRST_N_POSITIONS``: attention sinks).
    first_editable_position: int = 16
    #: Ablation strength in [0, 1]. 1.0 = remove the whole projection (paper default).
    alpha: float = 1.0
    #: Singular values of the k selected J-lens vectors below span_rtol * max are
    #: treated as zero (near-duplicate tokens such as "backup" / " backup").
    span_rtol: float = 1e-4
    #: Base seed of the norm-matched Gaussian control; each (trial prompt, layer)
    #: derives its own seed from it, so draws do not depend on run order.
    random_control_seed: int = 1234

    # --- dev-split selection rule (pre-registered) ---------------------------
    #: A band is acceptable on dev if, under J-ablation, retrieval accuracy and
    #: the valid-output rate both stay at or above this value.
    dev_min_ablated_retrieval_acc: float = 0.5
    dev_min_valid_rate: float = 0.5
    #: Baseline must reach this accuracy on BOTH tasks for ablations to be
    #: interpretable (spec §6 "baseline feasibility").
    baseline_min_accuracy: float = 0.70

    # --- analysis (pre-registered) -------------------------------------------
    n_bootstrap: int = 2000
    ci_level: float = 0.95
    #: Outcome B ("useful negative") needs a CI this narrow and |S| this small.
    null_max_ci_width: float = 0.30
    null_max_abs_s: float = 0.10
    #: Retrieval accuracy falling this much under J-ablation = general damage.
    general_damage_drop: float = 0.25
    #: Outcome "N": if fewer than this fraction of test trials had ANY concept site
    #: to ablate, the task concepts are not in the J-space and C1 cannot test H1.
    min_concept_coverage: float = 0.5
    #: Secondary metric (pre-registered): S computed on the continuous answer margin
    #: log p(correct) - max log p(other letter), with the same paired bootstrap.
    secondary_metric: str = "correct_margin"

    # --- output ----------------------------------------------------------------
    results_root: str = str(EXPERIMENT_ROOT / "results")

    neutral_texts: tuple[str, ...] = field(
        default=(
            "The river runs through the valley for nearly two hundred kilometres before it "
            "reaches the sea. Farmers along its banks grow wheat, barley and sunflowers, and "
            "in late summer the fields turn a deep gold. Several small towns grew up at the old "
            "crossing points, where ferries once carried carts and cattle to the other side.",
            "To make a simple loaf of bread, mix flour, water, salt and yeast until a soft dough "
            "forms. Knead it for about ten minutes, then leave it covered in a warm place until it "
            "has doubled in size. Shape the dough, let it rise again, and bake it in a hot oven "
            "until the crust is brown and the loaf sounds hollow when tapped underneath.",
            "The committee met on Tuesday to review the annual budget. Members agreed to increase "
            "funding for the public library and to postpone the repairs to the community hall until "
            "next spring. A final vote on the proposal is expected at the next meeting, which will "
            "be held in the town council chamber and is open to the public.",
        )
    )

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable view (tuples of dataclasses become lists of dicts)."""
        return asdict(self)
