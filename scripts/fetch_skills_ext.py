#!/usr/bin/env python3
"""Re-fetch the external real-skill corpus from the raw URLs recorded in
real-skills-ext/PROVENANCE.json (the files themselves are not committed).

Usage:  python3 scripts/fetch_skills_ext.py
"""
import json, os, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROV = ROOT / "real-skills-ext" / "PROVENANCE.json"


def main() -> int:
    entries = json.load(open(PROV))
    n = 0
    for e in entries:
        dest = ROOT / e["path"]
        if dest.exists():
            n += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(e["url"], timeout=60) as r:
                dest.write_bytes(r.read())
            n += 1
        except Exception as ex:                                  # noqa: BLE001
            print(f"failed {e['url']}: {ex}", file=sys.stderr)
    print(f"{n}/{len(entries)} skills present under real-skills-ext/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
