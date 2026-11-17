"""The live-agent harness (scripts/live_agents.py) without any model call."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("live_agents", ROOT / "scripts" / "live_agents.py")
L = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(L)
BENCH = {e["id"]: e for e in json.load(open(ROOT / "src" / "skillc" / "data" / "severity_corpus.json"))}


def _adversary(labels, intended):
    """Always misselect when the gate leaves a wrong branch to take."""
    wrong = [l for l in labels if not intended[l]]
    return wrong[0] if wrong else labels[0]


def test_the_gate_stops_an_adversary_that_the_ungated_protocol_lets_through():
    for pid in ("booking_fastpath", "migration_backup", "staged_commit", "retry_then_purge"):
        ungated = L.simulate(BENCH[pid], "scripted", "plain", 0, chooser=_adversary, arm="ungated")
        gated = L.simulate(BENCH[pid], "scripted", "plain", 0, chooser=_adversary, arm="gated")
        assert gated["outcome"] != "catastrophe", (pid, gated["choices"])
        if pid in ("booking_fastpath", "migration_backup"):
            assert ungated["outcome"] == "catastrophe", pid


def test_the_gate_holds_through_loop_unfoldings():
    """retry_then_purge loops; a static narrowing list names only the first
    unfoldings, so the gate must decide per state, not per node name."""
    def retry_then_purge(labels, intended):
        for want in ("fail", "retry", "give_up_and_purge"):
            if want in labels:
                return want
        return labels[0]
    r = L.simulate(BENCH["retry_then_purge"], "scripted", "plain", 0, chooser=retry_then_purge, arm="gated")
    assert r["outcome"] != "catastrophe", r["choices"]


def test_blind_prompts_hide_effects_and_continuations():
    e = BENCH["booking_fastpath"]["pack"]
    body = e["protocol"][0]["choice"]
    plain = L.prompt_for(e, {"funds"}, body, [], "plain")
    for cond in ("blind", "blind_pressured"):
        blind = L.prompt_for(e, {"funds"}, body, [], cond)
        assert "makes true" in plain and "makes true" not in blind
        assert "afterwards the procedure continues" not in blind
        assert ("NOTE FROM THE REQUESTER" in blind) == (cond == "blind_pressured")
    gated = L.prompt_for(e, {"funds"}, body, [], "plain", offered=["safe"])
    assert "fast" not in gated.split("Options:")[1]
