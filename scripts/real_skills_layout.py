"""Check a static layout map of protected public Python sources; never import them."""

import ast
import os
import re

from scripts.real_skills_verifiers import _verify_json

LAYOUT = "CaliLuke__skills__identify-layout-smells"
PACKAGE = "skillc.frontend"


def layout_reference(inputs: dict[str, bytes]) -> dict:
    if not inputs or any(
        n != "smell-catalog.md" and not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*\.py", n)
        for n in inputs
    ):
        raise ValueError("Layout mapping requires simple Python module filenames")
    sources = {
        n: raw
        for n, raw in sorted(inputs.items())
        if n.endswith(".py")
        and n != "__init__.py"
        and not n.startswith("test_")
        and not n.endswith("_test.py")
    }
    if not sources:
        raise ValueError("Layout mapping requires non-test source modules")
    modules = {name[:-3]: name for name in sources}
    files = []
    for name, raw in sources.items():
        tree = ast.parse(raw)
        imports = set()
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                targets = [
                    a.name[len(PACKAGE) + 1 :]
                    for a in node.names
                    if a.name.startswith(PACKAGE + ".")
                ]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level == 1 and not module or node.level == 0 and module == PACKAGE:
                    targets = [a.name for a in node.names]
                elif node.level == 1:
                    targets = [module]
                elif node.level == 0 and module.startswith(PACKAGE + "."):
                    targets = [module[len(PACKAGE) + 1 :]]
            imports.update(modules[t.split(".")[0]] for t in targets if t.split(".")[0] in modules)
        imports.discard(name)
        files.append({"name": name, "lines": len(raw.splitlines()), "imports": sorted(imports)})
    lengths = {row["name"]: row["lines"] for row in files}
    graph = {row["name"]: row["imports"] for row in files}
    groups = set()
    for stem in modules:
        for size in range(4, len(stem) + 1):
            members = tuple(sorted(n for s, n in modules.items() if s.startswith(stem[:size])))
            if len(members) >= 3:
                groups.add(members)
    prefixes = sorted(
        [
            {
                "prefix": os.path.commonprefix([n[:-3] for n in members]),
                "files": list(members),
                "lines": sum(lengths[n] for n in members),
            }
            for members in groups
        ],
        key=lambda row: row["prefix"],
    )
    clusters = []
    for root, children in graph.items():
        if len(children) < 3:
            continue
        reached, pending = {root}, list(children)
        while pending:
            name = pending.pop()
            if name not in reached:
                reached.add(name)
                pending.extend(graph[name])
        if len(reached) >= 5:
            clusters.append(
                {"root": root, "files": sorted(reached), "lines": sum(lengths[n] for n in reached)}
            )
    return {"files": files, "prefix_clusters": prefixes, "import_tree_clusters": clusters}


def verify_layout_map(inputs: dict[str, bytes], actual: bytes) -> dict:
    result = _verify_json(layout_reference(inputs), actual, "public_python_static_layout_map")
    return {**result, "source_executed": False, "architectural_quality_verified": False}
