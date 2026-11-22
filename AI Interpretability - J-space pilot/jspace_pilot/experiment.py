"""Running trials: one (scenario, task) -> baseline, J-ablation, random control.

Order of operations for one (scenario, task), all on ONE prompt tensor:

    1. clean pass   : unedited forward; record the final residual (-> C0 answer,
                      protected next-token guesses) and the band residuals
    2. locate       : read the J-lens on the clean band residuals and build the
                      concept plan ("observe first, then intervene")
    3. C1 J-ablation: remove the planned directions; record ||delta_J|| per site
    4. C2 random    : at the same sites, add Gaussian vectors with exactly C1's
                      recorded ||delta_J|| (spec §5.8)

The prompt hash is stored on every row so "same prompt in every condition" can
be audited in ``trial_results.csv``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd
import torch

from jspace_pilot.agent import build_messages
from jspace_pilot.concepts import ConceptPlan, locate_concepts
from jspace_pilot.config import CONDITIONS, TASK_TYPES, AblationBand, ExperimentConfig
from jspace_pilot.interventions import (
    INTERVENTION_KIND,
    EditRecord,
    JLensBasis,
    ResidualEditHook,
    residual_edits,
    site_seed,
)
from jspace_pilot.model_io import (
    LoadedModel,
    PreparedPrompt,
    clean_pass,
    encode_text,
    final_block_residual,
    logits_from_residual,
    render_prompt,
    score_choice,
    top_output_tokens,
)
from jspace_pilot.scenarios import Scenario

logger = logging.getLogger(__name__)


@dataclass
class ExperimentContext:
    """Model + lens state shared by every trial."""

    config: ExperimentConfig
    loaded: LoadedModel
    letter_variants: dict[str, list[int]]
    basis: JLensBasis | None = None
    band: AblationBand | None = None
    concept_ids: dict[int, str] | None = None  # "concept" selection
    excluded_ids: torch.Tensor | None = None  # "topk" selection: special / punctuation tokens
    lens_validated: bool = False
    run_id: str = ""

    def set_band(self, band: AblationBand, basis: JLensBasis) -> None:
        self.band, self.basis = band, basis

    @property
    def band_layers(self) -> list[int]:
        return list(self.band.layers) if self.band else []


@dataclass
class ConditionResult:
    residual: torch.Tensor  # final-block residual [seq, d]
    records: list[EditRecord]
    seconds: float


@dataclass
class TrialRecord:
    """One row of ``trial_results.csv``."""

    run_id: str
    scenario_id: str
    split: str
    task_type: str
    condition: str
    intervention_kind: str
    expected_letter: str
    predicted_letter: str
    restricted_letter: str
    is_correct: bool
    restricted_correct: bool
    invalid_output: bool
    top1_token: str
    correct_logprob: float
    correct_margin: float
    semantic_answer: str
    model_id: str
    model_revision: str
    seed: int
    lens_validated: bool
    selection: str
    intervention_band: str
    intervention_layers: str
    intervention_position: str
    alpha: float
    n_concept_sites: int  # (layer, position) sites with >= 1 concept in the clean lens readout
    concepts_found: str  # most frequent concept words at those sites
    n_edited_sites: int  # (layer, position) sites actually changed
    delta_l2_norm: float
    j_delta_l2_norm: float
    relative_delta_norm: float
    cosine_h_hnew: float
    j_span_rank: float
    random_in_j_span: float
    ablated_tokens_last_position: str
    prompt_sha256: str
    prompt_n_tokens: int
    elapsed_seconds: float


def prepare_prompt(ctx: ExperimentContext, scenario: Scenario, task_type: str) -> PreparedPrompt:
    return encode_text(ctx.loaded, render_prompt(ctx.loaded.tokenizer, build_messages(scenario, task_type)))


# ------------------------------------------------------------------ core runner
def _forward_with_hooks(ctx: ExperimentContext, input_ids: torch.Tensor, hooks: dict[int, ResidualEditHook]) -> ConditionResult:
    start = time.perf_counter()
    with residual_edits(ctx.loaded.lens_model.layers, hooks):
        residual = final_block_residual(ctx.loaded, input_ids)
    return ConditionResult(residual, [r for h in hooks.values() for r in h.records], time.perf_counter() - start)


@torch.no_grad()
def run_conditions(
    ctx: ExperimentContext,
    prompt: PreparedPrompt,
    conditions: Sequence[str] = CONDITIONS,
    alpha: float | None = None,
) -> tuple[dict[str, ConditionResult], ConceptPlan | None]:
    """Steps 1-4 of the module docstring for one prompt.

    ``conditions`` may also contain "noop". C1 is always computed when C2 is
    requested, because C2 re-uses C1's per-site change sizes.
    """
    cfg, loaded = ctx.config, ctx.loaded
    first = cfg.first_editable_position
    results: dict[str, ConditionResult] = {}

    start = time.perf_counter()
    final, band_residuals = clean_pass(loaded, prompt.input_ids, ctx.band_layers, first)
    results["baseline"] = ConditionResult(final, [], time.perf_counter() - start)
    protected = top_output_tokens(loaded, final, cfg.protect_top_n_output)  # [seq, n]

    if "noop" in conditions:
        layers = ctx.band_layers or [loaded.n_layers // 2]
        results["noop"] = _forward_with_hooks(ctx, prompt.input_ids, {l: ResidualEditHook(layer=l, mode="noop") for l in layers})

    wants_edit = any(c in conditions for c in ("j_ablation", "random_ablation"))
    if not wants_edit:
        return results, None
    if ctx.basis is None or ctx.band is None:
        raise RuntimeError("ablation requested but no validated band/basis is set")

    plan = None
    if cfg.selection == "concept":
        if ctx.concept_ids is None:
            raise RuntimeError("concept selection needs ctx.concept_ids")
        plan = locate_concepts(ctx.basis, band_residuals, protected[first:], ctx.concept_ids, cfg.concept_top_n)

    j_hooks = {
        layer: ResidualEditHook(
            layer=layer,
            mode="j_ablation",
            basis=ctx.basis,
            site_tokens=None if plan is None else plan.site_tokens[layer],
            protected=protected,
            excluded=ctx.excluded_ids,
            top_k=cfg.top_k,
            first_position=first,
            alpha=cfg.alpha if alpha is None else alpha,
            span_rtol=cfg.span_rtol,
        )
        for layer in ctx.band_layers
    }
    results["j_ablation"] = _forward_with_hooks(ctx, prompt.input_ids, j_hooks)

    if "random_ablation" in conditions:
        random_hooks = {
            layer: ResidualEditHook(
                layer=layer,
                mode="random_ablation",
                basis=ctx.basis,
                site_tokens=None if plan is None else plan.site_tokens[layer],  # only for the overlap diagnostic
                target_norms=j_hooks[layer].site_delta_norms,  # C1's recorded ||delta_J|| per site
                first_position=first,
                random_seed=site_seed(cfg.random_control_seed, layer, prompt.sha256),
                span_rtol=cfg.span_rtol,
            )
            for layer in ctx.band_layers
        }
        results["random_ablation"] = _forward_with_hooks(ctx, prompt.input_ids, random_hooks)
    return results, plan


def _summarise_edits(records: list[EditRecord], tokenizer: Any) -> dict[str, Any]:
    if not records:
        return dict(n_edited_sites=0, delta_l2_norm=0.0, j_delta_l2_norm=0.0, relative_delta_norm=0.0,
                    cosine_h_hnew=1.0, j_span_rank=0.0, random_in_j_span=0.0, ablated_tokens_last_position="")
    n = len(records)
    with_tokens = [r for r in records if r.last_position_tokens]
    shown = with_tokens[0] if with_tokens else None
    edited = [r for r in records if r.n_edited_sites]
    return dict(
        n_edited_sites=sum(r.n_edited_sites for r in records),
        delta_l2_norm=sum(r.delta_norm for r in records) / n,
        j_delta_l2_norm=sum(r.j_delta_norm for r in records) / n,
        relative_delta_norm=sum(r.delta_norm / r.h_norm for r in records) / n,
        cosine_h_hnew=sum(r.cosine for r in records) / n,
        j_span_rank=sum(r.span_rank for r in edited) / len(edited) if edited else 0.0,
        random_in_j_span=sum(r.random_in_j_span for r in edited) / len(edited) if edited else 0.0,
        ablated_tokens_last_position="" if shown is None else f"L{shown.layer}: " + " | ".join(
            tokenizer.decode([t]).strip() or repr(tokenizer.decode([t])) for t in shown.last_position_tokens
        ),
    )


def run_scenario_task(
    ctx: ExperimentContext,
    scenario: Scenario,
    task_type: str,
    conditions: Sequence[str] = CONDITIONS,
) -> list[TrialRecord]:
    """All requested conditions for one (scenario, task), sharing one prompt tensor."""
    cfg, loaded = ctx.config, ctx.loaded
    prompt = prepare_prompt(ctx, scenario, task_type)
    expected = scenario.correct_letter(task_type)
    results, plan = run_conditions(ctx, prompt, conditions)
    band = ctx.band
    rows: list[TrialRecord] = []
    for condition in conditions:
        result = results[condition]
        edited = condition != "baseline"
        score = score_choice(logits_from_residual(loaded, result.residual[-1:])[0], ctx.letter_variants, loaded.tokenizer)
        rows.append(
            TrialRecord(
                run_id=ctx.run_id,
                scenario_id=scenario.scenario_id,
                split=scenario.split,
                task_type=task_type,
                condition=condition,
                intervention_kind=(
                    INTERVENTION_KIND[condition].format(selection=cfg.selection)
                    if ctx.lens_validated or not edited else "demo_only"
                ),
                expected_letter=expected,
                predicted_letter=score.predicted_letter,
                restricted_letter=score.restricted_letter,
                is_correct=score.predicted_letter == expected,
                restricted_correct=score.restricted_letter == expected,
                invalid_output=score.invalid,
                top1_token=score.top1_token,
                correct_logprob=score.letter_logprobs[expected],
                correct_margin=score.margin(expected),
                semantic_answer=scenario.semantic_answer(task_type),
                model_id=cfg.model_id,
                model_revision=str(cfg.model_revision),
                seed=cfg.seed,
                lens_validated=ctx.lens_validated,
                selection=cfg.selection if edited else "none",
                intervention_band=band.name if band and edited else "none",
                intervention_layers=f"{band.first_layer}-{band.last_layer}" if band and edited else "none",
                intervention_position=f"prefill positions >= {cfg.first_editable_position}" if edited else "none",
                alpha=cfg.alpha if edited else 0.0,
                n_concept_sites=plan.total_sites if plan else 0,
                concepts_found=plan.summary() if plan else "",
                prompt_sha256=prompt.sha256,
                prompt_n_tokens=prompt.n_tokens,
                elapsed_seconds=round(result.seconds, 3),
                **_summarise_edits(result.records, loaded.tokenizer),
            )
        )
    return rows


def run_split(
    ctx: ExperimentContext,
    scenarios: Sequence[Scenario],
    conditions: Sequence[str] = CONDITIONS,
    task_types: Sequence[str] = TASK_TYPES,
    progress: Callable[[str], None] | None = print,
) -> pd.DataFrame:
    """Every (scenario, task) x condition. Prints one short line per scenario."""
    rows: list[TrialRecord] = []
    for i, scenario in enumerate(scenarios, start=1):
        for task in task_types:
            rows.extend(run_scenario_task(ctx, scenario, task, conditions))
        if progress:
            done = [r for r in rows if r.scenario_id == scenario.scenario_id]
            marks = " ".join(f"{r.task_type[0].upper()}/{r.condition[:4]}={'ok' if r.is_correct else 'x '}" for r in done)
            sites = next((r.n_concept_sites for r in done if r.condition == "j_ablation"), None)
            progress(f"[{i:>3}/{len(scenarios)}] {scenario.scenario_id}  {marks}" + (f"  sites={sites}" if sites is not None else ""))
    return pd.DataFrame([asdict(r) for r in rows])


@torch.no_grad()
def concept_localization(ctx: ExperimentContext, scenarios: Sequence[Scenario]) -> pd.DataFrame:
    """Clean passes only: where do the concepts appear in the J-lens? One row per
    (scenario, task, layer) with the number of sites and the words found."""
    if ctx.basis is None or ctx.band is None or ctx.concept_ids is None:
        raise RuntimeError("needs a validated basis, a band and concept ids")
    cfg = ctx.config
    rows = []
    for scenario in scenarios:
        for task in TASK_TYPES:
            prompt = prepare_prompt(ctx, scenario, task)
            final, band_residuals = clean_pass(ctx.loaded, prompt.input_ids, ctx.band_layers, cfg.first_editable_position)
            protected = top_output_tokens(ctx.loaded, final, cfg.protect_top_n_output)
            for layer in ctx.band_layers:
                plan = locate_concepts(
                    ctx.basis, {layer: band_residuals[layer]}, protected[cfg.first_editable_position :],
                    ctx.concept_ids, cfg.concept_top_n,
                )
                rows.append({
                    "scenario_id": scenario.scenario_id, "task_type": task, "layer": layer,
                    "n_sites": plan.n_sites[layer], "n_positions": prompt.n_tokens - cfg.first_editable_position,
                    "words": plan.summary(top=4),
                })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ validation
@torch.no_grad()
def hook_identity_checks(ctx: ExperimentContext, prompt: PreparedPrompt) -> dict[str, Any]:
    """Spec §5.4: no-hook vs no-hook (determinism), no-hook vs no-op hook, and
    no-hook vs J-hook with alpha = 0. All should give identical logits."""
    loaded = ctx.loaded
    last = lambda res: logits_from_residual(loaded, res.residual[-1:])  # noqa: E731
    first_run, _ = run_conditions(ctx, prompt, ("baseline", "noop"))
    second_run, _ = run_conditions(ctx, prompt, ("baseline",))
    reference = last(first_run["baseline"])
    result: dict[str, Any] = {
        "repeat_max_abs_diff": (reference - last(second_run["baseline"])).abs().max().item(),
        "noop_max_abs_diff": (reference - last(first_run["noop"])).abs().max().item(),
    }
    if ctx.basis is not None and ctx.band is not None:
        zero, _ = run_conditions(ctx, prompt, ("baseline", "j_ablation"), alpha=0.0)
        result["alpha0_max_abs_diff"] = (reference - last(zero["j_ablation"])).abs().max().item()
        result["alpha0_hook_fired"] = len(zero["j_ablation"].records) == len(ctx.band_layers)
    tolerance = 1e-3
    result["tolerance"] = tolerance
    result["passed"] = all(v <= tolerance for k, v in result.items() if k.endswith("max_abs_diff"))
    return result


@torch.no_grad()
def intervention_diagnostics(ctx: ExperimentContext, prompt: PreparedPrompt) -> dict[str, Any]:
    """Per-layer norms for C1 vs C2 on one prompt (spec §5.4 / §5.8)."""
    results, plan = run_conditions(ctx, prompt, CONDITIONS)
    out: dict[str, Any] = {"concept_sites_per_layer": plan.n_sites if plan else None,
                           "concepts_found": plan.summary(10) if plan else None}
    for condition in ("j_ablation", "random_ablation"):
        out[condition] = [
            {
                "layer": r.layer,
                "sites_edited": f"{r.n_edited_sites}/{r.n_positions}",
                "mean_||h||": round(r.h_norm, 2),
                "mean_||delta||": round(r.delta_norm, 4),
                "mean_||delta_J (C1)||": round(r.j_delta_norm, 4),
                "mean_cos(h,h_new)": round(r.cosine, 5),
                "rank(J vectors)": round(r.span_rank, 2),
                "random_in_J_span": round(r.random_in_j_span, 4),
            }
            for r in results[condition].records
        ]
    return out


@torch.no_grad()
def neutral_nll(ctx: ExperimentContext, texts: Sequence[str]) -> dict[str, float]:
    """Mean next-token NLL on plain prose under each condition (general damage check)."""
    totals = {c: 0.0 for c in CONDITIONS}
    count = 0
    first = ctx.config.first_editable_position
    for text in texts:
        prompt = encode_text(ctx.loaded, text)
        targets = prompt.input_ids[0, first + 1 :].cpu()
        results, _ = run_conditions(ctx, prompt, CONDITIONS)
        for condition in CONDITIONS:
            logits = logits_from_residual(ctx.loaded, results[condition].residual[first:-1])
            totals[condition] += torch.nn.functional.cross_entropy(logits, targets, reduction="sum").item()
        count += len(targets)
    return {c: totals[c] / count for c in CONDITIONS}


def band_is_acceptable(dev_trials: pd.DataFrame, config: ExperimentConfig) -> tuple[bool, dict[str, float]]:
    """Pre-registered dev rule: under J-ablation, retrieval accuracy and the
    valid-output rate must not collapse (otherwise the edit is general damage)."""
    j = dev_trials[dev_trials["condition"] == "j_ablation"]
    stats = {
        "j_retrieval_acc": float(j[j["task_type"] == "retrieval"]["is_correct"].mean()),
        "j_integration_acc": float(j[j["task_type"] == "integration"]["is_correct"].mean()),
        "j_valid_rate": float(1 - j["invalid_output"].mean()),
        "mean_concept_sites": float(j["n_concept_sites"].mean()),
    }
    ok = stats["j_retrieval_acc"] >= config.dev_min_ablated_retrieval_acc and stats["j_valid_rate"] >= config.dev_min_valid_rate
    return ok, stats
