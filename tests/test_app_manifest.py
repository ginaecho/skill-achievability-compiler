import importlib.util
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "demo" / "skillc-architecture-app"
sys.path.insert(0, str(APP))
SPEC = importlib.util.spec_from_file_location("atlas_app", APP / "app.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules["atlas_app"] = MODULE
SPEC.loader.exec_module(MODULE)

MANIFEST = {
    "name": "fares", "description": "A fare runtime.",
    "tools": {"book_fare": "books a fare"},
    "contracts": {"book_fare": {"add": ["booked"],
                                "nondet": {"price": {"cmp": ["price", ">=", 800]}}}},
    "states": {"booked": "booked", "price": "price"},
    "init_true": ["searched"],
}


def test_manifest_validation_keeps_contracts_states_and_initial_state():
    manifest = MODULE._validate_manifest(MANIFEST)

    assert manifest["contracts"] == MANIFEST["contracts"]
    assert manifest["states"] == MANIFEST["states"]
    assert manifest["init_true"] == ["searched"]


def test_manifest_validation_rejects_malformed_contracts():
    with pytest.raises(ValueError, match="contracts"):
        MODULE._validate_manifest({**MANIFEST, "contracts": {"book_fare": "anything"}})


def test_no_manifest_is_allowed():
    assert MODULE._validate_manifest(None) is None
