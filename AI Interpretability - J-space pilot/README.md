# J-space Pilot: Does the "Global Workspace" of an LLM Carry Tool-Information Integration?

> **A pre-registered interpretability experiment on Qwen3.5-4B using the official Jacobian lens (J-lens).**
> It asks whether removing the J-lens directions of task concepts from the residual stream hurts an
> agent's ability to *combine* facts from several tools more than its ability to *retrieve* a single
> fact — compared with a random edit of exactly the same size.

![python](https://img.shields.io/badge/python-%E2%89%A53.10-blue)
![torch](https://img.shields.io/badge/torch-%E2%89%A52.4-ee4c2c)
![tests](https://img.shields.io/badge/tests-33%20passing-brightgreen)
![status](https://img.shields.io/badge/status-pilot%20%2F%20inconclusive-orange)

---

## Table of contents
1. [Motivation](#1-motivation)
2. [Research question & hypotheses](#2-research-question--hypotheses)
3. [Experimental design](#3-experimental-design)
4. [The intervention in detail](#4-the-intervention-in-detail)
5. [Metrics & pre-registered outcomes](#5-metrics--pre-registered-outcomes)
6. [Results so far](#6-results-so-far)
7. [Repository layout](#7-repository-layout)
8. [Installation](#8-installation)
9. [Running the experiment](#9-running-the-experiment)
10. [Configuration](#10-configuration)
11. [Testing & validation safeguards](#11-testing--validation-safeguards)
12. [Output files](#12-output-files)
13. [Limitations & next steps](#13-limitations--next-steps)
14. [Scope](#14-scope)
15. [References](#15-references)

---

## 1. Motivation

**Global Workspace Theory (GWT)** proposes that a mind has a small, shared "workspace" where
information from specialised processes is brought together for flexible, deliberate reasoning,
while simple automatic tasks bypass it.

A 2026 paper (Gurnee et al.) found an analogous structure inside language models — the
**J-space** — readable with a tool called the **Jacobian lens (J-lens)**. Ablating it impaired
flexible reasoning but not simple copying.

This project tests whether the same dissociation shows up in an **LLM agent's decision step**:
does an agent that must *integrate* outputs from three tools rely on J-space more than when it only
has to *look up* one value?

## 2. Research question & hypotheses

| | Statement |
|---|---|
| **H1** | Removing the J-lens directions of task concepts hurts **integration** (combining 3 tool outputs into a decision) more than **retrieval** (copying one value), and more than a norm-matched random edit does. |
| **H0** | No such selective difference is detectable. |

## 3. Experimental design

### 3.1 Synthetic SOC incident-response benchmark (`scenarios.py`)

Each scenario is a set of facts about one alerted server. A **deterministic rule** (no LLM involved)
produces the ground-truth labels:

```
risk != "high"                                  -> monitor
risk == "high", not critical                    -> isolate_now
risk == "high", critical,  backup_ready         -> failover_then_isolate
risk == "high", critical,  not backup_ready     -> contain_and_plan
```

- The **test split is stratified** (equal scenarios per action) and **counterbalanced**
  (each answer letter A–D is correct equally often), so a position-biased model cannot score by chance.
- Server and backup IDs are unique across the whole dataset — no leakage between dev and test.

### 3.2 Scripted agent (`agent.py`)

Deliberately *not* autonomous. A controller always calls the same three fake tools in the same order
and stores their JSON outputs verbatim in memory:

```text
[1] get_alert       -> {"server_id": "CRM-58", "risk": "high"}
[2] get_asset_info  -> {"server_id": "CRM-58", "critical_service": false}
[3] get_backup_info -> {"backups": [
        {"server_id": "CRM-58", "backup_ready": true,  "backup_id": "BK-796"},
        {"server_id": "OPS-71", "backup_ready": true,  "backup_id": "BK-961"},
        {"server_id": "FIN-66", "backup_ready": false, "backup_id": "BK-875"}]}
```

The model then answers **one** multiple-choice question. The system prompt and memory are
byte-identical across tasks; only the question differs:

| Task | Question | Answer in example |
|---|---|---|
| **Integration** | Which action is correct for the alerted server? | *Isolate the server immediately* |
| **Retrieval** | Which `backup_id` does tool 3 list for the alerted server? | `BK-796` (decoys `BK-961`, `BK-875` are present in memory, so it's a real lookup) |

### 3.3 Conditions

Every (scenario, task) pair runs under three conditions on the **same prompt**:

| Code | Condition | What happens |
|---|---|---|
| **C0** | `baseline` | Clean forward pass |
| **C1** | `j_ablation` | Remove the J-lens directions of pre-registered task concepts at the sites where they appear |
| **C2** | `random_ablation` | Add a Gaussian perturbation with **exactly C1's L2 norm** at every (layer, position) |

### 3.4 Dev/test protocol

1. **Dev split** selects the ablation layer band with a pre-registered rule (try `wide` = layers 8–24
   first, fall back to `mid` = 12–20 if J-ablation damages retrieval or valid-output rate).
2. The full protocol is **frozen** to `frozen_protocol.json` with a timestamp.
3. Only then is the **held-out test split** run.

## 4. The intervention in detail

**"Observe first, then intervene"** (v2, `selection="concept"`):

1. **Locate** — on the clean pass, read the J-lens at every (layer, position) in the band. Mark every
   site where a pre-registered concept token (`backup`, `risk`, `critical`, `isolate`, `true`, `false`, …,
   all single-token spellings) ranks in the lens top-20. (`concepts.py`)
2. **Direction** — for token *t* at layer *ℓ*, the J-lens direction is
   **v = Jᵀ (g ⊙ wₜ)**, where *J* is the lens Jacobian, *g* the effective final-norm gain and *wₜ*
   the unembedding row. (`interventions.calculate_jlens_direction`)
3. **Remove** — project the residual state off the span of the selected vectors (SVD-based, near-duplicate
   directions such as `backup`/` backup` are collapsed with `span_rtol`), with strength `alpha`.
4. **Protect** — tokens in the clean model's top-10 next-token prediction at a position are never ablated
   there, and the first 16 positions (attention sinks) are never edited.
5. **Control** — C2 replays C1's recorded per-site edit norm with a seeded Gaussian direction, so the
   two conditions differ *only* in direction, not magnitude.

A legacy v1 mode (`selection="topk"`) removes the untargeted top-k lens tokens at every site (paper §3.5.2).

## 5. Metrics & pre-registered outcomes

**Primary metric — integration specificity S** (`metrics.py`):

```
S = (A[random, integration] − A[J, integration])
  − (A[random, retrieval]   − A[J, retrieval])
```

S > 0 means J-ablation hurts integration *more* than retrieval, relative to the matched random control.
A 95 % CI is computed with a **paired bootstrap over whole scenarios** (2 000 resamples), so pairing
across conditions and tasks is never broken.

**Secondary metric** — the same S computed on the continuous answer margin
`log p(correct) − max log p(other letter)`.

**Outcome rules** (applied in order, first match wins):

| Code | Meaning |
|---|---|
| **D** | No validated lens — feasibility result only |
| **N** | Concepts appear in < 50 % of test trials — C1 cannot test H1 |
| **C** | Invalid: baseline < 70 %, control not norm-matched, or retrieval collapses |
| **A** | S > 0 and CI lower bound > 0 — **supports H1** |
| **C′** | S < 0 and CI upper bound < 0 — contrary to H1 |
| **B** | \|S\| ≤ 0.10 and CI width ≤ 0.30 — useful negative |
| **E** | Inconclusive |

## 6. Results so far

| Run | Version | Test scenarios | Outcome | Notes |
|---|---|---|---|---|
| `run_20261109T171915Z` | v1 | 24 | **C (invalid)** | Random control was 1.68× larger than the J edit (bug); removed directions were mostly formatting tokens |
| `run_20261109T175937Z`, `…180159Z` | v2 | — | aborted | Notebook code error at start |
| `run_20261109T180715Z` | v2 | 96 (2 run) | stopped | Too slow on local hardware; no results saved |
| `run_20261109T182530Z` | v2 | 4 | **Inconclusive** | All 13 acceptance checks passed |

**Key findings from the latest v2 run:**

- ✅ Pipeline fully validated: lens agrees with `jlens` reference (98.75 % top-10 at L8, 100 % at L24),
  no-op hooks change nothing, control/J edit norm ratio = **1.000**, protocol frozen before test.
- ✅ Task concepts **are** visible in the J-lens: ~800–1 000 concept sites per prompt
  (`backup` ≈ 670, `risk` ≈ 270, `monitoring` ≈ 250, …), increasing toward layers 23–24.
- ⚠️ Removing them barely moves the model: ~0.6 % change in residual norm (cosine 0.9997),
  no change in neutral-text loss.

| Accuracy | Integration | Retrieval |
|---|---|---|
| C0 baseline | 1.00 | 1.00 |
| C1 J edit | 1.00 | 1.00 |
| C2 random | 1.00 | 1.00 |

| Margin (log units) | Integration | Retrieval |
|---|---|---|
| C0 baseline | 4.06 | 5.84 |
| C1 J edit | 3.97 | 5.91 |
| C2 random | 3.91 | 5.81 |

Margin S = **+0.03**, 95 % CI [−0.25, +0.31].

**Interpretation:** the automatic label "B" is **not trustworthy** — accuracy was at ceiling (100 %)
and n = 4, so S was forced to 0. The honest conclusion is that token-level concept removal is too weak an
intervention on this model; the result neither supports nor rejects H1. Full write-ups:
[`EXPERIMENT_REPORT.txt`](results/run_20261109T182530Z/EXPERIMENT_REPORT.txt) and
[`WHY_INCONCLUSIVE_AND_CONSTRAINTS.txt`](results/run_20261109T182530Z/WHY_INCONCLUSIVE_AND_CONSTRAINTS.txt).

## 7. Repository layout

```
experiment/
├── ai_welfare_jspace_pilot.ipynb   # study guide + experiment runner (start here)
├── jspace_pilot/
│   ├── config.py          # every hyperparameter in one frozen dataclass
│   ├── scenarios.py       # decision rule + stratified, counterbalanced benchmark
│   ├── agent.py           # 3 fake tools, oracle memory, prompt construction
│   ├── validation.py      # dataset assertions (before any model is loaded)
│   ├── model_io.py        # bf16 loading, explicit device map / CPU offload, A–D scoring
│   ├── lens_setup.py      # load + validate the official pre-fitted J-lens
│   ├── interventions.py   # J-lens direction, span projection, norm-matched control, hooks
│   ├── concepts.py        # concept words → token ids, concept localisation
│   ├── toy_math.py        # autograd vs finite-difference Jacobian, projection invariants
│   ├── experiment.py      # trials, hook identity checks, diagnostics, dev band selection
│   ├── metrics.py         # accuracy, S, paired bootstrap, outcome rules
│   ├── reporting.py       # run folder, logging, CSV/JSON export, figures, checklist
│   └── preflight.py       # environment / GPU / model-cache / version checks
├── tests/                 # 33 unit tests (torch tests auto-skip without torch)
├── tools/smoke_notebook.py# executes every notebook cell with a tiny model on CPU
├── results/run_*/         # one folder per run
├── requirements.txt
└── pyproject.toml
```

Modules that need only numpy/pandas (`config`, `scenarios`, `agent`, `validation`, `metrics`) import
without torch, so the benchmark and statistics can be tested on any machine.

## 8. Installation

**Requirements:** Python ≥ 3.10, a CUDA GPU (≥ 12 GB VRAM recommended; less works via automatic CPU
offload, just slower), and ~10 GB disk for the model.

```bash
git clone <this-repo-url>
cd experiment
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt   # install CUDA torch first from https://pytorch.org if needed
```

`requirements.txt` pins the official Jacobian-lens reference implementation
(`anthropics/jacobian-lens@581d398`). The model (`Qwen/Qwen3.5-4B`) and the pre-fitted lens
(`neuronpedia/jacobian-lens`, revision `qwen-n1000`) are downloaded from Hugging Face on first run,
both pinned to exact revisions.

## 9. Running the experiment

### Before every run (≈ 30 s)
```bash
python -m jspace_pilot.preflight      # packages, jlens API, GPU/VRAM, model cache, notebook ↔ code match
python -m pytest -q                   # 33 tests: data, statistics, hook maths, notebook consistency
python tools/smoke_notebook.py        # optional (~5 min, CPU): runs every notebook cell with a tiny model
```

### Locally
```bash
jupyter lab ai_welfare_jspace_pilot.ipynb
```
Run all cells. The notebook re-runs preflight and tests (section 03), reloads `jspace_pilot/`, and
stops with a clear message if the notebook and code versions don't match.

### Google Colab (recommended for full-size runs)
1. Upload the `experiment/` folder to Google Drive as `MyDrive/jspace_experiment/`.
2. Open the notebook in Colab and pick an **L4** or **A100** runtime.
3. *Runtime → Run all.* Results are written to `MyDrive/jspace_experiment/results/run_<UTC>/`.

## 10. Configuration

All knobs live in `jspace_pilot/config.py` (`ExperimentConfig`, frozen). Most relevant:

| Field | Default | Meaning |
|---|---|---|
| `n_test_per_action` | `1` | Held-out scenarios per action. **1 = smoke run only; use ≥ 12 for real results** |
| `n_backup_entries` | `3` | Servers listed by tool 3 (alerted + decoys) |
| `model_id` / `model_revision` | `Qwen/Qwen3.5-4B` / pinned SHA | Model checkpoint the lens was fitted on |
| `selection` | `"concept"` | `"concept"` (v2) or `"topk"` (v1) |
| `concept_words` | 19 words | Pre-registered decision concepts |
| `concept_top_n` | `20` | Concept is "present" if in lens top-n at a site |
| `candidate_bands` | `wide 8–24`, `mid 12–20` | Layer bands tried on dev, in order |
| `alpha` | `1.0` | Ablation strength (1.0 = remove full projection) |
| `protect_top_n_output` | `10` | Never ablate the model's own top-n predictions |
| `first_editable_position` | `16` | Skip attention-sink positions |
| `n_bootstrap` / `ci_level` | `2000` / `0.95` | Bootstrap settings |

> Pre-registration rule: nothing in `config.py` may be changed after the held-out test split has been run.

## 11. Testing & validation safeguards

- **Unit tests** — dataset balance and uniqueness, decision rule, bootstrap maths, hook arithmetic,
  concept tokenisation, notebook/code consistency.
- **Toy maths checks** (`toy_math.py`) — autograd vs finite-difference Jacobian, 2-D R² ablation example,
  projection invariants.
- **Lens validation** — top-k agreement between this code's lens readout and the `jlens` reference.
- **Hook identity checks** — a no-op hook and an `alpha = 0` hook must leave logits bit-identical.
- **Control matching** — per-site random/J norm ratio must equal 1.
- **Dataset validation** — run before the model is loaded.
- **Frozen protocol** — settings are written with a timestamp before the test split runs.

## 12. Output files

Each run creates `results/run_<UTC timestamp>/`:

| File | Contents |
|---|---|
| `trial_results.csv` | One row per test trial (scenario × task × condition) |
| `dev_trials.csv` | Dev trials used for band selection |
| `concept_localization_dev.csv` | Where concepts appear in the clean J-lens |
| `summary.json` | Accuracy tables, S, margin S, bootstrap CI, outcome, acceptance checklist |
| `validation_log.json` | Toy-math, lens and hook checks |
| `frozen_protocol.json` | Settings saved before the test run |
| `run_metadata.json` | Model, lens, package versions, seeds, hardware |
| `scenarios.jsonl` | Every scenario used |
| `run_log.txt` | Timeline of the run |
| `figures/` | `accuracy_by_condition.png`, `specificity_bootstrap.png` |

## 13. Limitations & next steps

**Limitations of the current run**
- Intervention too weak (~0.6 % of the residual state); facts are also re-readable from the prompt via attention.
- Ceiling effect: 100 % baseline accuracy, so accuracy could only decrease.
- n = 4 test scenarios — far too small for inference.
- Outcome rule "B" lacks a ceiling / minimum-n check.

**Planned improvements**
1. Require n ≥ 24 and baseline < 95 % for outcome "B"; otherwise report "E".
2. Add a **directed J-lens coordinate swap** (paper §2.5, §3.5.1), e.g. swap `true` ↔ `false` at the
   alerted server's `backup_ready`. Prediction under H1: the integration answer flips, retrieval does not.
3. Optionally add a pre-registered dose–response (`alpha > 1`).
4. Make the task harder (baseline ≈ 70–85 %) and run ≥ 12 scenarios per action (48 total) — only
   `n_test_per_action` needs to change.

## 14. Scope

This removes task-concept J-lens directions at the sites where the clean lens shows them, at **one
decision step of a scripted tool-use workflow**. It is **not** a full J-space ablation, and it is **not**
a test of consciousness, sentience or AI welfare.

## 15. References

- Gurnee et al. (2026) — the J-space / Jacobian lens paper this pilot builds on.
- Jacobian lens reference implementation: <https://github.com/anthropics/jacobian-lens>
- Pre-fitted lens: [`neuronpedia/jacobian-lens`](https://huggingface.co/neuronpedia/jacobian-lens) (revision `qwen-n1000`)
- Model: [`Qwen/Qwen3.5-4B`](https://huggingface.co/Qwen/Qwen3.5-4B)
