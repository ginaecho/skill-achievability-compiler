"""Verify a public-data notebook without executing submitted code on the host."""
import ast
import csv
import hashlib
import io
import itertools
import json
import re

from scripts.real_skills_runtime import OUTPUT_LIMIT, Sandbox
from scripts.real_skills_verifiers import _unique_fields

NOTEBOOK = "openai__skills__jupyter-notebook"
TITLE = "# Tutorial: Palette catalog summaries"


def _source(cell: dict) -> str:
    source = cell.get("source")
    if isinstance(source, str):
        return source
    if isinstance(source, list) and all(isinstance(line, str) for line in source):
        return "".join(source)
    raise ValueError("Cell source must be text or a list of text lines")


def notebook_code(actual: bytes, template: dict) -> list[str]:
    if len(actual) > 32768:
        raise ValueError("Notebook exceeds 32768 bytes")
    notebook = json.loads(actual.decode("utf-8"), object_pairs_hook=_unique_fields)
    if not isinstance(notebook, dict):
        raise ValueError("Notebook must be an object")
    for key in ("nbformat", "nbformat_minor"):
        if type(notebook.get(key)) is not int or notebook[key] != template[key]:
            raise ValueError("Preserve the public template's notebook format")
    if notebook.get("metadata") != template["metadata"]:
        raise ValueError("Preserve the public template's notebook metadata")
    cells = notebook.get("cells")
    if not isinstance(cells, list) or not cells or not all(isinstance(c, dict) for c in cells):
        raise ValueError("Notebook requires an ordered list of cells")
    seen, code, markdown = set(), [], []
    for cell in cells:
        identifier = cell.get("id")
        if (not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identifier)
                or identifier in seen or not isinstance(cell.get("metadata"), dict)):
            raise ValueError("Cells require unique valid identifiers and metadata objects")
        seen.add(identifier)
        source = _source(cell)
        if cell.get("cell_type") == "code":
            if ("execution_count" not in cell or cell["execution_count"] is not None
                    or cell.get("outputs") != []):
                raise ValueError("Deliver code cells with cleared counts and outputs")
            ast.parse(source)
            code.append(source)
        elif cell.get("cell_type") == "markdown":
            markdown.append(source)
        else:
            raise ValueError("Only ordinary Python code and Markdown cells are supported")
    if (cells[0].get("cell_type") != "markdown" or not _source(cells[0]).startswith(TITLE)
            or len(code) < 3 or len(markdown) < 3):
        raise ValueError("Use the requested title and at least three cells of each type")
    narrative = "\n".join(markdown).casefold()
    for section in ("audience", "prerequisites", "learning goals", "outline", "exercises"):
        if section not in narrative:
            raise ValueError(f"Missing required tutorial section: {section}")
    return code


def catalog_reference(raw: bytes) -> list[dict]:
    rows = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
    pairs = sorted((row["Primary (Hex)"].strip().upper(), row["Product Type"].strip())
                   for row in rows)
    groups = []
    for primary, grouped in itertools.groupby(pairs, key=lambda pair: pair[0]):
        products = [pair[1] for pair in grouped]
        groups.append({"primary": primary, "count": len(products),
                       "product_types": sorted(set(products))})
    return sorted(groups, key=lambda group: (-group["count"], group["primary"]))


def catalog_replays(raw: bytes) -> dict[str, bytes]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
    rows = list(reader)
    if not reader.fieldnames or not rows or not catalog_reference(raw):
        raise ValueError("The original public catalog must have a nonempty reference")
    changed = dict(rows[0])
    changed["Primary (Hex)"] = changed["Primary (Hex)"].lower()
    changed["Product Type"] = "  " + changed["Product Type"] + ", replay  "
    variants = {"colors.csv": raw}
    for name, records in (("changed.csv", [*reversed(rows), changed, dict(rows[0])]),
                          ("empty.csv", [])):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(records)
        variants[name] = stream.getvalue().encode("utf-8")
    return variants


def _valid_counts(value) -> bool:
    return (isinstance(value, list) and all(
        isinstance(row, dict) and type(row.get("count")) is int for row in value))


def verify_notebook(inputs: dict[str, bytes], actual: bytes, host: str) -> dict:
    if set(inputs) != {"tutorial-template.ipynb", "colors.csv"}:
        raise ValueError("Notebook verification requires the public template and catalog")
    template = json.loads(inputs["tutorial-template.ipynb"])
    variants = catalog_replays(inputs["colors.csv"])
    expected = {"top_level": catalog_reference(inputs["colors.csv"]),
                "replays": [catalog_reference(raw) for raw in variants.values()]}
    if len(json.dumps(expected).encode()) >= OUTPUT_LIMIT:
        raise ValueError("Notebook reference exceeds the isolated worker's output limit")
    identity = {"kind": "public_catalog_notebook_python_cell_replay",
                "actual_sha256": hashlib.sha256(actual).hexdigest(),
                "kernel_or_browser_tested": False}
    try:
        code = notebook_code(actual, template)
    except (ValueError, SyntaxError, RecursionError) as error:
        return {**identity, "passed": False, "error": str(error)}
    worker = (
        "import contextlib,json,os\n"
        "namespace={'__name__':'__notebook__'}\n"
        "with open(os.devnull,'w') as sink, contextlib.redirect_stdout(sink):\n"
        f" for index,code in enumerate({code!r}):\n"
        "  exec(compile(code,f'notebook-cell-{index}','exec'),namespace)\n"
        " result={'top_level':namespace['palette_summary'],'replays':[\n"
        "  namespace['summarize_palettes']('/inputs/'+name)\n"
        f"  for name in {list(variants)!r}]}}\n"
        "print(json.dumps(result,allow_nan=False))\n"
    )
    sandbox = Sandbox(host)
    try:
        sandbox.start({**variants, "answer.ipynb": actual}, [])
        result = sandbox.execute(worker)
    finally:
        sandbox.stop()
    if result["status"] != "completed" or result["exit_code"] != 0:
        return {**identity, "passed": False, "error": "Notebook code-cell replay failed",
                "runtime": result}
    try:
        observed = json.loads(result["output"], object_pairs_hook=_unique_fields)
    except ValueError as error:
        return {**identity, "passed": False, "error": f"Invalid replay output: {error}"}
    shape = (isinstance(observed, dict) and _valid_counts(observed.get("top_level"))
             and isinstance(observed.get("replays"), list)
             and all(_valid_counts(rows) for rows in observed["replays"]))
    return {**identity, "passed": bool(shape and observed == expected),
            "checks": 1 + len(variants), "code_cells_executed": len(code),
            "observed": observed,
            "expected_sha256": hashlib.sha256(json.dumps(
                expected, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "replay_inputs_sha256": {name: hashlib.sha256(raw).hexdigest()
                                     for name, raw in variants.items()},
            "error": None if shape and observed == expected else "Notebook results differ"}
