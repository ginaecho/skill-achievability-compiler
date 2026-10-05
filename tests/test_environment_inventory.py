import importlib.util
import time
from pathlib import Path

from skillc.env.model import Environment

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "demo"
    / "skillc-architecture-app"
    / "environment_inventory.py"
)
SPEC = importlib.util.spec_from_file_location("environment_inventory", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
EnvironmentInventory = MODULE.EnvironmentInventory


def _environment() -> Environment:
    env = Environment()
    principal = env.add_node("principal/test", "principal", "test agent")
    runtime = env.add_node(
        "runtime/test",
        "service",
        "test runtime",
        available=True,
        type="runtime",
    )
    for name in ("read", "send_email"):
        tool = env.add_node(f"tool/{name}", "tool", name)
        env.add_edge(runtime, tool, "exposes")
    deny = env.add_node(
        "deny/send",
        "deny",
        "deny send",
        actions=["send_email", "send_email(*)"],
    )
    env.add_edge(principal, deny, "denied", scope="/")
    env.add_node("program/az", "service", "az", available=True, type="program")
    return env


def _wait_for_refresh(inventory: EnvironmentInventory) -> dict:
    for _ in range(100):
        snapshot = inventory.snapshot()
        if not snapshot["refreshing"]:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("environment refresh did not finish")


def test_inventory_discovers_grants_and_keeps_a_snapshot(tmp_path):
    probes = []

    def probe(source):
        probes.append(source)
        return _environment()

    inventory = EnvironmentInventory(
        Path(__file__).resolve().parents[1],
        tmp_path,
        refresh_seconds=0,
        probe=probe,
    )
    inventory.start()
    snapshot = _wait_for_refresh(inventory)

    assert probes == [""]
    assert snapshot["grants"] == ["az", "read"]
    assert {item["name"]: item["status"] for item in snapshot["capabilities"]} == {
        "read": "approval",
        "send_email": "denied",
    }
    assert (tmp_path / "latest.json").is_file()

    cached = EnvironmentInventory(
        Path(__file__).resolve().parents[1],
        tmp_path,
        refresh_seconds=0,
        probe=lambda _: (_ for _ in ()).throw(AssertionError("unexpected probe")),
    )
    cached.start()
    assert cached.snapshot()["grants"] == ["az", "read"]


def test_manual_refresh_uses_the_current_source(tmp_path):
    sources = []
    inventory = EnvironmentInventory(
        Path(__file__).resolve().parents[1],
        tmp_path,
        refresh_seconds=0,
        probe=lambda source: sources.append(source) or _environment(),
    )

    assert inventory.request_refresh("Required tools: send_email.", "manual")
    assert not inventory.request_refresh("ignored", "manual")
    snapshot = _wait_for_refresh(inventory)

    assert sources == ["Required tools: send_email."]
    assert snapshot["last_reason"] == "manual"
