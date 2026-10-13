"""Telemetry: OpenTelemetry spans when the library is there, nothing otherwise.

    with span("skillc.gate", intent="finance", verdict="possible"):
        ...
    event("skillc.decision", tool="email_report", decision="deny")

A hosted agent's platform injects OpenTelemetry into Application Insights;
skillc's verdicts and decisions ride on it when `opentelemetry` is
importable and are silently dropped when it is not.  Nothing here ever
raises: a broken tracer is treated like an absent one, and the body of a
`span` runs exactly once either way.  Attribute values are coerced to the
types OpenTelemetry accepts (str, bool, int, float), everything else to str.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import Any

TRACER_NAME = "skillc"


def _attributes(attrs: dict[str, Any]) -> dict[str, Any]:
    return {k: v if isinstance(v, (str, bool, int, float)) else str(v)
            for k, v in attrs.items() if v is not None}


def _tracer() -> Any:
    """The OpenTelemetry tracer, or None when the library is absent or unusable."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(TRACER_NAME)
    except Exception:  # noqa: BLE001 - any failure means no telemetry, never an error
        return None


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[Any]:
    """A span named `name` around the block; yields the span object, or None
    when telemetry is unavailable.  Exceptions from the block propagate."""
    tracer = _tracer()
    cm = None
    if tracer is not None:
        try:
            cm = tracer.start_as_current_span(name, attributes=_attributes(attrs))
            current = cm.__enter__()
        except Exception:  # noqa: BLE001
            cm, current = None, None
    else:
        current = None
    try:
        yield current
    except BaseException as e:
        if cm is not None:
            with suppress(Exception):
                cm.__exit__(type(e), e, e.__traceback__)
        raise
    else:
        if cm is not None:
            with suppress(Exception):
                cm.__exit__(None, None, None)


def event(name: str, **attrs: Any) -> None:
    """A zero-duration span: a point in time with attributes."""
    with span(name, **attrs):
        pass
