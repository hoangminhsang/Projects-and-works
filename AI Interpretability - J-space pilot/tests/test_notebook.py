"""The notebook and the package must agree (catches stale or renamed imports)."""

import json
import re

import jspace_pilot
from jspace_pilot.preflight import NOTEBOOK, notebook_import_problems


def test_every_notebook_import_exists():
    assert notebook_import_problems() == []


def test_notebook_expects_this_package_version():
    source = "".join("".join(c["source"]) for c in json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"])
    match = re.search(r'NOTEBOOK_CODE_VERSION = "([^"]+)"', source)
    assert match, "notebook must declare NOTEBOOK_CODE_VERSION"
    assert match.group(1) == jspace_pilot.__version__


def test_notebook_code_cells_compile():
    for index, cell in enumerate(json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]):
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), f"cell {index}", "exec")
