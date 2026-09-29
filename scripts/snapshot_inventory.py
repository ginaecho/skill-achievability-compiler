"""Snapshot the software installed on this machine (the machine the runtimes describe):
Python distributions and their top-level import names, executables on PATH and global
npm packages. Written to src/skillc/data/runtimes/inventory.json.

  python scripts/snapshot_inventory.py
"""
import importlib.metadata as md
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src/skillc/data/runtimes/inventory.json"


def main() -> None:
    py = set()
    for d in md.distributions():
        name = (d.metadata["Name"] or "").lower()
        if name:
            py.add(name)
        top = d.read_text("top_level.txt") or ""
        py.update(t.strip().lower() for t in top.splitlines() if t.strip())
    exe = set()
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if os.path.isdir(p):
            exe.update(f.lower() for f in os.listdir(p)
                       if os.access(os.path.join(p, f), os.X_OK))
    npm = set()
    try:
        out = subprocess.run(["npm", "ls", "-g", "--depth=0", "--json"],
                             capture_output=True, text=True, timeout=60).stdout
        npm = {k.lower() for k in json.loads(out or "{}").get("dependencies", {})}
    except Exception:
        pass
    OUT.write_text(json.dumps({"snapshot_utc": datetime.now(timezone.utc).isoformat(),
                               "python": sorted(py), "executables": sorted(exe),
                               "npm": sorted(npm)}, indent=0) + "\n")
    print(len(py), len(exe), len(npm))


if __name__ == "__main__":
    main()
