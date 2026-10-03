"""Run `skillc reach --claude` on every case and keep its verdict and probe.

    python benchmark/claude_env/run_skillc.py [--out benchmark/claude_env/results]

Exit 0 / 3 (achievable, or achievable under assumptions) count as ACHIEVABLE;
exit 1 as BLOCKED.  The session's tool names and connected connectors are
given as files, since a cloud session's connectors are not in any config file.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
VERDICT = {0: "ACHIEVABLE", 3: "ACHIEVABLE", 1: "BLOCKED"}


def run(case: str, out: Path) -> dict:
    cmd = [sys.executable, "-c", "from skillc.cli import main; raise SystemExit(main())",
           "reach", str(HERE / "cases" / f"{case}.md"), "--claude", "--json",
           "--tools-file", str(HERE / "session" / "tools.json"),
           "--connectors-file", str(HERE / "session" / "connectors.json"),
           "--save-env", str(out / f"{case}.env.json")]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
    result = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else None
    return {"case": case, "exit": proc.returncode, "verdict": VERDICT.get(proc.returncode, "ERROR"),
            "status": (result or {}).get("conditions"),
            "blocked": [b["condition"] for b in (result or {}).get("blocked") or []],
            "assumptions": (result or {}).get("assumptions"),
            "error": proc.stderr.strip()[-500:] if proc.returncode == 2 else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=HERE / "results")
    args = ap.parse_args()
    args.out.mkdir(exist_ok=True)
    cases = [c["case"] for c in json.loads((HERE / "cases.json").read_text())["cases"]]
    rows = []
    for case in cases:
        rows.append(run(case, args.out))
        print(case, rows[-1]["verdict"], rows[-1]["blocked"] or "", flush=True)
    (args.out / "skillc.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
