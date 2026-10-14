"""Stage the Docker build context for the hosted demo: only what app.py reads.

    python demo/skillc-a365-demo/deploy/build_context.py OUT_DIR

Copies src/skillc, scripts/run_interaction_cases.py, the demo (app, page, case contexts) and, from
benchmark/, only the case files that have a context in cases/ (no other benchmark data, in
particular no held-out set file without a showcase context). OUT_DIR must not exist.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent
ROOT = DEMO.parent.parent
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc")


def main(out: Path) -> int:
    if out.exists():
        sys.exit(f"{out} exists; pass a new directory")
    app = out / "app"
    shutil.copytree(ROOT / "src" / "skillc", app / "src" / "skillc", ignore=SKIP)
    (app / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "run_interaction_cases.py", app / "scripts")
    dest = app / "demo" / DEMO.name
    for name in ("app.py", "local_source.py"):
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DEMO / name, dest)
    for name in ("static", "cases"):
        shutil.copytree(DEMO / name, dest / name, ignore=SKIP)
    wanted = {p.stem for p in (DEMO / "cases").glob("*.json")}
    copied = 0
    for d in sorted((ROOT / "benchmark").glob("interaction_cases*")):
        for p in sorted(d.glob("*.json")):
            if p.stem in wanted:
                (app / "benchmark" / d.name).mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, app / "benchmark" / d.name)
                copied += 1
    shutil.copy2(HERE / "Dockerfile", out / "Dockerfile")
    print(f"staged {out} ({copied} benchmark case files for {len(wanted)} contexts)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
