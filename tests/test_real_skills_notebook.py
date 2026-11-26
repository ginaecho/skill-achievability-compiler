import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts.real_skills_notebook import (
    TITLE, catalog_reference, catalog_replays, notebook_code, verify_notebook,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = (ROOT / "runs" / "20261106_real_skills" / "reviewed-palette"
           / "davila7__claude-code-templates__ui-ux-pro-max" / "colors.csv")
PUBLIC_TEMPLATE = json.loads((ROOT / "runs" / "20261106_real_skills" / "reviewed-notebook"
                              / "openai__skills__jupyter-notebook"
                              / "tutorial-template.ipynb").read_bytes())
TEMPLATE = {key: PUBLIC_TEMPLATE[key] for key in ("nbformat", "nbformat_minor", "metadata")}
PROGRAM = '''import csv
def summarize_palettes(path):
    groups = {}
    with open(path, newline='', encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            key = row['Primary (Hex)'].strip().upper()
            group = groups.setdefault(key, {'primary': key, 'count': 0, 'product_types': set()})
            group['count'] += 1
            group['product_types'].add(row['Product Type'].strip())
    return sorted((dict(row, product_types=sorted(row['product_types']))
                   for row in groups.values()), key=lambda row: (-row['count'], row['primary']))
'''


def notebook(program=PROGRAM):
    cells = []
    for kind, source in (
        ("markdown", TITLE + "\nAudience\nPrerequisites\nLearning goals"),
        ("code", program), ("markdown", "## Outline"),
        ("code", "palette_summary = summarize_palettes('/inputs/colors.csv')"),
        ("markdown", "## Exercises"), ("code", "assert isinstance(palette_summary, list)"),
    ):
        cell = {"id": f"cell-{len(cells)}", "cell_type": kind, "metadata": {}, "source": source}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        cells.append(cell)
    return {**TEMPLATE, "cells": cells}


@pytest.mark.parametrize("mutation", ["duplicate_id", "non_python", "saved_output"])
def test_notebook_rejects_artifacts_that_cannot_be_replayed_as_scaffolded(mutation):
    candidate = notebook()
    if mutation == "duplicate_id":
        candidate["cells"][1]["id"] = candidate["cells"][0]["id"]
    elif mutation == "non_python":
        candidate["cells"][1]["source"] = "%matplotlib inline"
    else:
        candidate["cells"][1]["outputs"] = [{"output_type": "stream", "text": "stale"}]
    with pytest.raises((ValueError, SyntaxError)):
        notebook_code(json.dumps(candidate).encode(), TEMPLATE)


def test_public_catalog_variants_change_counts_and_cover_quoted_names_and_empty_input():
    raw = CATALOG.read_bytes()
    variants = catalog_replays(raw)
    original, changed, empty = [catalog_reference(data) for data in variants.values()]
    assert sum(row["count"] for row in changed) == sum(row["count"] for row in original) + 2
    assert any(product.endswith(", replay") for row in changed for product in row["product_types"])
    assert changed != original and empty == []


@pytest.mark.skipif(os.environ.get("SKILLC_LOCAL_DOCKER") != "1",
                    reason="explicit local isolated-container fixture check")
def test_notebook_runs_actual_cells_and_rejects_hardcoded_catalog_results():
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
        text=True).strip()
    inputs = {"tutorial-template.ipynb": json.dumps(TEMPLATE).encode(),
              "colors.csv": CATALOG.read_bytes()}
    passed = verify_notebook(inputs, json.dumps(notebook()).encode(), host)
    assert passed["passed"] and passed["checks"] == 4
    assert passed["kernel_or_browser_tested"] is False
    hardcoded = ("def summarize_palettes(path):\n    return "
                 + repr(catalog_reference(inputs["colors.csv"])) + "\n")
    failed = verify_notebook(inputs, json.dumps(notebook(hardcoded)).encode(), host)
    assert not failed["passed"] and failed["error"] == "Notebook results differ"
