"""Microsoft 365 Copilot chat: a declared environment, not a probed one.

Nothing on this PC records what Microsoft 365 Copilot can do for the signed-in user, so
the environment is the built-in manifest `m365-copilot` plus an optional overlay the owner
writes by hand, `~/.skillc/m365-copilot.json`:

    {"tools": {"<name>": "<what it does>", ...},     agents and connectors the owner added
     "remove_lacks": ["<substring>", ...]}           lacks entries those make untrue

`remove_lacks` drops every lacks entry that contains one of the substrings (ignoring case).
An overlay that does not have this shape is not applied, and the summary says why.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

NAME = "m365-copilot"
MODE = "declared, not probed"


def overlay_path() -> Path:
    return Path.home() / ".skillc" / "m365-copilot.json"


def base_manifest() -> dict:
    ref = resources.files("skillc").joinpath(f"data/runtimes/{NAME}.json")
    return json.loads(ref.read_text(encoding="utf-8"))


def read_overlay(path: Path | None = None) -> tuple[dict | None, str]:
    """(overlay, note): the overlay when present and well formed, else None and why."""
    path = Path(path) if path is not None else overlay_path()
    if not path.is_file():
        return None, "no overlay file"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"overlay not applied: unreadable ({type(e).__name__})"
    if not isinstance(data, dict):
        return None, "overlay not applied: not a JSON object"
    tools = data.get("tools", {})
    remove = data.get("remove_lacks", [])
    if not isinstance(tools, dict) or not all(
            isinstance(k, str) and k.strip() and isinstance(v, str) for k, v in tools.items()):
        return None, "overlay not applied: `tools` must map names to descriptions"
    if not isinstance(remove, list) or not all(isinstance(x, str) and x for x in remove):
        return None, "overlay not applied: `remove_lacks` must be a list of strings"
    return {"tools": dict(tools), "remove_lacks": list(remove)}, "overlay applied"


def merge(manifest: dict, overlay: dict | None) -> dict:
    """`manifest` with the overlay's tools added and the matching lacks entries removed."""
    out = json.loads(json.dumps(manifest))
    if not overlay:
        return out
    out["tools"].update(overlay.get("tools") or {})
    drop = [s.lower() for s in overlay.get("remove_lacks") or []]
    out["lacks"] = [e for e in out["lacks"] if not any(s in e.lower() for s in drop)]
    return out


def probe(overlay: Path | None = None) -> dict:
    """The declared environment, in the same summary shape as the other hosts."""
    data, note = read_overlay(overlay)
    m = merge(base_manifest(), data)
    builtin = set(base_manifest()["tools"])
    return {
        "runtime": "Microsoft 365 Copilot",
        "mode": MODE,
        "captured": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": [f"built-in manifest `{NAME}`",
                    f"overlay {(Path(overlay) if overlay else overlay_path()).name}: {note}"],
        "overlay_applied": data is not None,
        "tools": [{"name": t, "status": "declared",
                   "origin": "built-in" if t in builtin else "overlay"} for t in m["tools"]],
        "removed_lacks": sorted(set(base_manifest()["lacks"]) - set(m["lacks"])),
    }


def runtime_manifest(overlay: Path | None = None) -> dict:
    data, _note = read_overlay(overlay)
    return merge(base_manifest(), data)
