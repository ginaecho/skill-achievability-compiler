"""Building sketches (scribble or plain text) read into building graphs, and pictures sent to a
model through the guarded providers."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from skillc.cli import main
from skillc.env.twin_sketch import read_sketch
from skillc.frontend import providers

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "building-twin"
SCRIBBLE = EXAMPLES / "campus-sketch.txt"
PROSE = EXAMPLES / "campus-description.txt"


def _verdicts(path):
    pytest.importorskip("rdflib")
    from skillc.env.twin import load_twin, verify_all
    twin = load_twin(path)
    return {sc: {r.target: (r.verdict, sorted(e.key for e in r.missing))
                 for r in verify_all(twin, sc)} for sc in ("setpoint", "schedule")}


def test_scribble_and_prose_describe_the_same_building():
    a = read_sketch(SCRIBBLE.read_text(encoding="utf-8"))
    b = read_sketch(PROSE.read_text(encoding="utf-8"))
    assert sorted(a.entities) == sorted(b.entities)
    assert not a.ignored and not b.ignored
    assert _verdicts(SCRIBBLE) == _verdicts(PROSE)


def test_the_verifiers_find_each_planted_gap():
    v = _verdicts(SCRIBBLE)
    assert v["setpoint"]["ex:sp-11"] == ("ACHIEVABLE", [])
    assert v["setpoint"]["ex:sp-12"] == ("IMPOSSIBLE", ["min_max_units"])
    assert v["setpoint"]["ex:sp-21"] == ("IMPOSSIBLE", ["external_reference"])
    assert v["schedule"]["ex:zone-11"] == ("ACHIEVABLE", [])
    assert v["schedule"]["ex:zone-12"] == ("IMPOSSIBLE", ["operating_policy"])


def test_arrows_feed_but_between_places_mean_contains():
    s = read_sketch("AHU-1 -> VAV-1 -> Zone 1 -> Room 101, Room 102\n")
    assert "brick:feeds ex:vav-1" in s.entities["ahu-1"].facts
    assert "brick:feeds ex:zone-1" in s.entities["vav-1"].facts
    assert s.entities["room-101"].facts == ["brick:isPartOf ex:zone-1"]
    assert s.entities["ahu-1"].cls == "brick:AHU" and s.entities["zone-1"].cls == "brick:HVAC_Zone"


def test_nothing_is_guessed_from_lines_it_cannot_read():
    s = read_sketch("AHU-1 -> VAV-1\nthe chiller is probably fine\nSP-1 on VAV-1\n")
    assert [n for n, _t in s.ignored] == [2]
    assert "not understood" in s.summary()
    pytest.importorskip("rdflib")
    from rdflib import Dataset
    ds = Dataset()
    ds.parse(data=s.trig(), format="trig")       # always valid TriG
    assert "chiller" not in s.trig()


def test_attributes_are_only_what_is_written():
    s = read_sketch("SP-1 on VAV-1: priority 8\n")
    facts = " ".join(s.entities["sp-1"].facts)
    assert "activePriority 8" in facts
    assert "minPresentValue" not in facts and "BACnetReference" not in facts


def test_cli_checks_a_sketch_like_a_graph(capsys):
    pytest.importorskip("rdflib")
    assert main(["twin", "explore", str(SCRIBBLE)]) == 0
    out = capsys.readouterr().out
    assert "AHU --feeds--> VAV" in out and "Zone_Air_Temperature_Setpoint" in out


# --- pictures through the guarded providers ----------------------------------------------

class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_azure_request_carries_the_picture_and_no_url(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["body"] = json.loads(req.data)
        return _Response(json.dumps({"choices": [{"message": {"content": "AHU-1 -> VAV-1"}}],
                                     "usage": {"prompt_tokens": 900,
                                               "completion_tokens": 10}}).encode())

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    out = providers.complete("azure-openai", "system", "Transcribe.", "gpt-demo", 30,
                             json_mode=False, image=(b"\x89PNG fake", "image/png"))
    assert out == "AHU-1 -> VAV-1"
    content = seen["body"]["messages"][1]["content"]
    assert content[0] == {"type": "text", "text": "Transcribe."}
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "response_format" not in seen["body"]


def test_anthropic_request_carries_the_picture(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["body"] = json.loads(req.data)
        return _Response(json.dumps({"content": [{"type": "text", "text": "ok"}]}).encode())

    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    providers.complete("anthropic", "system", "Transcribe.", None, 30,
                       image=(b"jpegbytes", "image/jpeg"))
    block = seen["body"]["messages"][0]["content"][0]
    assert block["type"] == "image" and block["source"]["media_type"] == "image/jpeg"


def test_unsupported_picture_types_are_refused():
    with pytest.raises(ValueError, match="unsupported image type"):
        providers._b64((b"<svg/>", "image/svg+xml"))
