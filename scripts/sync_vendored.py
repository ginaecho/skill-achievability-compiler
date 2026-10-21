"""Sync src/skillc into every vendored copy under examples/hosted-agent-finance*/src/*/skillc.

The azure.yaml predeploy hooks stage the same copy (rm -rf + cp -r ../../src/skillc), so this
mirrors that: files are copied over, files absent from src/skillc are removed, __pycache__ is
ignored. `--check` changes nothing and exits 1 if any copy differs.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "skillc"


def files(base: Path) -> dict[str, Path]:
    return {
        p.relative_to(base).as_posix(): p
        for p in base.rglob("*")
        if p.is_file() and "__pycache__" not in p.relative_to(base).parts and p.suffix != ".pyc"
    }


def targets() -> list[Path]:
    return sorted(p for p in ROOT.glob("examples/hosted-agent-finance*/src/*/skillc") if p.is_dir())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="exit 1 if any copy differs; change nothing")
    args = ap.parse_args()
    src = files(SRC)
    dirty = False
    for dst in targets():
        cur = files(dst)
        missing = sorted(set(src) - set(cur))
        extra = sorted(set(cur) - set(src))
        changed = sorted(k for k in set(src) & set(cur) if src[k].read_bytes() != cur[k].read_bytes())
        rel = dst.relative_to(ROOT).as_posix()
        if not (missing or extra or changed):
            print(f"{rel}: up to date ({len(src)} files)")
            continue
        dirty = True
        if args.check:
            print(f"{rel}: DIFFERS  missing={len(missing)} changed={len(changed)} extra={len(extra)}")
            continue
        for k in missing + changed:
            (dst / k).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src[k], dst / k)
        for k in extra:
            cur[k].unlink()
        print(f"{rel}: synced  added={len(missing)} updated={len(changed)} removed={len(extra)}")
    if not targets():
        print("no vendored copies found")
    return 1 if (dirty and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
