"""Baselines P (planner only) and T (tool lint) of experiment R."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skillc import check  # noqa: E402
from skillc.baselines import planner_only, tool_lint  # noqa: E402


def _pack(caps, protocol, goal, init=()):
    return {"name": "t", "roles": ["agent"], "capabilities": caps,
            "protocol": protocol, "goal": goal, "init_true": list(init)}


def act(c):
    return {"act": {"cap": c, "by": "agent"}}


def test_planner_ignores_protocol_order():
    # `deploy` needs `built`, but the protocol runs it before `build`:
    # the checker refutes, the planner (no order) does not.
    caps = {"build": {"owner": "agent", "add": ["built"]},
            "deploy": {"owner": "agent", "pre": "built", "add": ["deployed"]}}
    p = _pack(caps, [act("deploy"), act("build")], "deployed")
    assert check(p).label == "IMPOSSIBLE"
    assert planner_only(p)["label"] == "ACHIEVABLE"


def test_planner_refutes_unestablishable_goal():
    caps = {"build": {"owner": "agent", "add": ["built"]}}
    r = planner_only(_pack(caps, [act("build")], {"and": ["built", "signed"]}))
    assert r["label"] == "IMPOSSIBLE" and r["frontier"] == ["signed"]


def test_planner_chains_preconditions_and_frees_numbers():
    caps = {"a": {"owner": "agent", "pre": {"cmp": ["n", ">", 3]}, "add": ["x"]},
            "b": {"owner": "agent", "pre": {"and": ["x", "init"]}, "add": ["y"]},
            "c": {"owner": "agent", "pre": {"not": "never"}, "add": ["z"]},
            "dead": {"owner": "agent", "pre": False, "add": ["w"]}}
    p = _pack(caps, [], {"and": ["y", "z"]}, init=["init"])
    assert planner_only(p)["label"] == "ACHIEVABLE"
    assert planner_only(_pack(caps, [], "w"))["label"] == "IMPOSSIBLE"


def test_planner_contradictory_goal():
    caps = {"a": {"owner": "agent", "add": ["x"]}}
    assert planner_only(_pack(caps, [act("a")],
                              {"and": ["x", {"not": "x"}]}))["label"] == "IMPOSSIBLE"


def test_lint_only_reads_withdrawn_and_blocked():
    # goal unreachable and order wrong, but nothing withdrawn: lint says ACHIEVABLE
    caps = {"a": {"owner": "agent", "pre": "q", "add": ["x"]}}
    p = _pack(caps, [act("a")], "never")
    assert tool_lint(p, {}, {})["label"] == "ACHIEVABLE"
    # withdrawn tool invoked inside a skippable branch still counts
    p2 = _pack({}, [{"choice": {"by": "agent", "observed": True, "branches": {
        "go": [act("gpu_train")], "skip": []}}}], True)
    r = tool_lint(p2, {"gpu_train": "gpu"}, {})
    assert r["label"] == "IMPOSSIBLE" and r["frontier"] == ["gpu_train"]
    # a withdrawn tool the protocol never invokes does not count
    assert tool_lint(p, {"other": "x"}, {"zz": ["k"]})["label"] == "ACHIEVABLE"
    assert tool_lint(p, {}, {"a": ["aws_account"]})["reason"] == "BLOCKED"
