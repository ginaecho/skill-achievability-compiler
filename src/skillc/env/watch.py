"""The watcher: a sibling process that keeps the environment snapshot fresh.

    skillc env watch --dir .skillc/env --azure --mcp-config .mcp.json \\
                     --intent building-topology [--interval 3600 | --once]

Each round probes the environment (read-only), stores a timestamped snapshot
and `latest.json`, diffs it against the previous snapshot, re-runs every
watched intent and reports the conditions whose status changed.  `--once`
does one round and exits, for cron or a CI schedule; without it the watcher
loops every `--interval` seconds.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

from .model import Environment, diff
from .reach import reach

LATEST = "latest.json"


def watch_once(directory: str | Path, probe: Callable[[], Environment],
               intents: dict[str, dict]) -> dict:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    previous = Environment.load(root / LATEST) if (root / LATEST).exists() else None
    env = probe()
    stamp = env.captured_at.replace(":", "").replace("-", "")
    env.save(root / f"env-{stamp}.json")
    env.save(root / LATEST)
    report = {"snapshot": str(root / f"env-{stamp}.json"),
              "environment_changes": diff(previous, env) if previous else None,
              "status_changes": {}}
    for name, intent in intents.items():
        result = reach(intent, env)
        path = root / f"reach-{name}.json"
        before = (json.loads(path.read_text(encoding="utf-8")).get("conditions", {})
                  if path.exists() else {})
        changed = {c: {"was": before.get(c), "now": s}
                   for c, s in result.status.items() if before.get(c) != s}
        if changed:
            report["status_changes"][name] = changed
        path.write_text(json.dumps(result.to_dict(), indent=1, default=str), encoding="utf-8")
    return report


def watch(directory: str | Path, probe: Callable[[], Environment], intents: dict[str, dict],
          interval: float, rounds: int | None = None,
          on_report: Callable[[dict], None] = print) -> None:
    done = 0
    while rounds is None or done < rounds:
        on_report(watch_once(directory, probe, intents))
        done += 1
        if rounds is None or done < rounds:
            time.sleep(interval)
