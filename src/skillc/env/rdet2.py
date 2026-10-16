"""Rdet2: the requirement reader with strict mentions (PLAN Addendum E-a).

    refute_text_rdet2(text, manifest)
        == evaluate(intent_from_text(text, reader="rdet2"), manifest)

`manifest.refute_text` stays the Rdet reader as frozen for set3."""
from __future__ import annotations

from .manifest import Evaluation, evaluate
from .nl import intent_from_text


def refute_text_rdet2(text: str, manifest, name: str | None = None) -> Evaluation:
    """Read `text` with the Rdet2 reader, then evaluate it against `manifest`."""
    return evaluate(intent_from_text(text, name=name, reader="rdet2"), manifest)
