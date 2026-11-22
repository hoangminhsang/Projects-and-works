"""Run EVERY code cell of the notebook, in order, with a tiny random model on CPU.

Proves the notebook runs top to bottom without errors (imports, variables,
columns, files) in a few minutes, without a GPU and without the 9 GB model.
Numbers it produces are meaningless (random weights, fake lens).

Usage (from the experiment/ folder):
    python tools/smoke_notebook.py [path/to/notebook.ipynb]
"""
import json, sys, tempfile, traceback
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import jlens, torch, transformers

NOTEBOOK = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "ai_welfare_jspace_pilot.ipynb"
SP = Path(tempfile.mkdtemp(prefix="jspace_smoke_"))

def tiny_load_model(cfg):
    tok = transformers.AutoTokenizer.from_pretrained(cfg.model_id, revision=cfg.model_revision)
    torch.manual_seed(0)
    hf = transformers.LlamaForCausalLM(transformers.LlamaConfig(vocab_size=len(tok), hidden_size=64, intermediate_size=128,
        num_hidden_layers=26, num_attention_heads=4, num_key_value_heads=4)).eval()
    lm = jlens.from_hf(hf, tok)
    import jspace_pilot.model_io as model_mod
    return model_mod.LoadedModel(hf, tok, lm, hf.model.norm, hf.lm_head.weight, torch.device("cpu"), 0, {})

def fake_load_lens(cfg):
    torch.manual_seed(1)
    import jspace_pilot.lens_setup as lens_mod
    return lens_mod.LensStatus(lens=jlens.JacobianLens({l: torch.eye(64) + 0.05 * torch.randn(64, 64) for l in range(25)},
                                                       n_prompts=1, d_model=64), file_sha256="fake")

def apply_patches():
    """The notebook's setup cell reloads jspace_pilot, so re-patch after every cell (idempotent)."""
    import importlib
    cfg = importlib.import_module("jspace_pilot.config")
    if not getattr(cfg.ExperimentConfig, "_smoke", False):
        original = cfg.ExperimentConfig
        factory = lambda: replace(original(), n_dev=4, n_test_per_action=2, concept_top_n=3000,  # noqa: E731
                                  n_bootstrap=200, results_root=str(SP / "smoke_results"))
        factory._smoke = True
        cfg.ExperimentConfig = factory
    importlib.import_module("jspace_pilot.model_io").load_model = tiny_load_model
    importlib.import_module("jspace_pilot.lens_setup").load_lens = fake_load_lens


apply_patches()

nb = json.load(open(NOTEBOOK))
ns = {"display": lambda *a, **k: [print(x) for x in a], "__name__": "__main__"}
n = 0
for i, cell in enumerate(nb["cells"]):
    if cell["cell_type"] != "code":
        continue
    n += 1
    src = "".join(cell["source"])
    try:
        exec(compile(src, f"cell{i}", "exec"), ns)
        apply_patches()
    except Exception:
        print(f"\n!!! FAILED at notebook cell {i} (code cell #{n}):\n{src[:300]}\n")
        traceback.print_exc()
        sys.exit(1)
print(f"\nSMOKE TEST PASSED: ALL {n} CODE CELLS RAN OK | outcome={ns['OUTCOME'].code} | full_run={ns['FULL_RUN']} | coverage={ns['CONCEPT_COVERAGE']}")
