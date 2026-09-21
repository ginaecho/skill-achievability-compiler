"""Replay the prior ten packs without changing them or making model calls."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.benchmark_compaction import score, sha, write_json
from scripts.benchmark_semantics import audit_goal_reachability
from skillc import check

rows = []
source = ROOT / "runs" / "20260921_110234Z_real_rejection_benchmark" / "packs"
for path in sorted(source.glob("*.json")):
    pack = json.loads(path.read_text())
    oracle = audit_goal_reachability(pack)
    for scope in ("protocol", "goal"):
        verdict = check(pack, scope=scope)
        rows.append({
            "id": path.stem, "category": "prior_five_sources",
            "truth": oracle["truth"], "oracle": oracle, "scope": scope,
            "predicted": verdict.label, "reason": verdict.reason,
            "pack_sha256": sha(path), "verdict": verdict.to_dict(),
        })
metrics = {
    scope: score([row for row in rows if row["scope"] == scope])
    for scope in ("protocol", "goal")
}
write_json(Path(__file__).with_name("prior_pack_replay.json"),
           {"rows": rows, "metrics": metrics})
print(json.dumps(metrics, indent=2))
