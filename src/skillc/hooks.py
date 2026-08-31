"""Versioned host protocol for pre-session skill admission hooks."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .preflight import PreflightResult, preflight_skill
from .profiles import Profile, load_profile

PRE_SESSION_REQUEST_SCHEMA = "skillc.hook.pre-session/1"
PRE_SESSION_RESULT_SCHEMA = "skillc.hook.pre-session-result/1"


class HookRequestError(ValueError):
    """Raised when a hook request does not satisfy the public protocol."""


def _profile(runtime: dict) -> Profile:
    capabilities = runtime.get("capabilities")
    if capabilities is not None:
        if not isinstance(capabilities, list) or not all(
                isinstance(capability, str) for capability in capabilities):
            raise HookRequestError("runtime.capabilities must be a list of strings")
        return Profile.from_dict({
            "name": runtime.get("profile", "session-runtime"),
            "tools": capabilities,
            "shell": runtime.get("shell", False),
        })
    return load_profile(runtime.get("profile", "none"))


def _policy(request: dict) -> dict[str, str]:
    supplied = request.get("policy", {})
    if not isinstance(supplied, dict):
        raise HookRequestError("policy must be an object")
    result = {
        "impossible": supplied.get("impossible", "exclude"),
        "unknown": supplied.get("unknown", "warn"),
        "auditError": supplied.get("auditError", "exclude"),
    }
    allowed = {
        "impossible": {"exclude", "block-session", "allow"},
        "unknown": {"warn", "exclude", "block-session", "allow"},
        "auditError": {"exclude", "block-session", "allow"},
    }
    for key, value in result.items():
        if value not in allowed[key]:
            raise HookRequestError(
                f"policy.{key} must be one of {sorted(allowed[key])}")
    return result


def _action(result: PreflightResult, policy: dict[str, str]) -> str:
    if result.status == "admitted":
        return "allow"
    if result.unknown:
        return policy["unknown"]
    if result.status in ("audit-error", "error"):
        return policy["auditError"]
    return policy["impossible"]


def run_pre_session_hook(request: dict[str, Any]) -> dict:
    """Preflight proposed skills and return a host-ready admission decision."""
    if not isinstance(request, dict):
        raise HookRequestError("hook request must be an object")
    if request.get("schema") != PRE_SESSION_REQUEST_SCHEMA:
        raise HookRequestError(
            f"schema must be {PRE_SESSION_REQUEST_SCHEMA!r}")
    skills = request.get("skills")
    if not isinstance(skills, list):
        raise HookRequestError("skills must be a list")
    runtime = request.get("runtime", {})
    if not isinstance(runtime, dict):
        raise HookRequestError("runtime must be an object")

    profile = _profile(runtime)
    policy = _policy(request)
    semantics = request.get("semantics", "may")
    if semantics not in ("may", "adversarial"):
        raise HookRequestError("semantics must be 'may' or 'adversarial'")

    admitted: list[str] = []
    excluded: list[dict] = []
    warnings: list[dict] = []
    results: list[dict] = []
    blocked = False
    for skill in skills:
        if not isinstance(skill, dict) or not isinstance(skill.get("path"), str):
            raise HookRequestError("each skill needs a string path")
        skill_id = skill.get("id") or Path(skill["path"]).parent.name
        if not isinstance(skill_id, str):
            raise HookRequestError("each skill id must be a string")
        result = preflight_skill(skill["path"], profile, skill_id=skill_id,
                                 audit=skill.get("audit", True),
                                 semantics=semantics)
        action = _action(result, policy)
        item = result.to_dict()
        item["action"] = action
        results.append(item)
        if action in ("allow", "warn"):
            admitted.append(skill_id)
            if action == "warn":
                warnings.append(item)
        else:
            excluded.append(item)
            blocked = blocked or action == "block-session"

    if blocked:
        decision = "block-session"
    elif excluded:
        decision = "allow-with-filtering"
    elif warnings:
        decision = "allow-with-warnings"
    else:
        decision = "allow"
    return {
        "schema": PRE_SESSION_RESULT_SCHEMA,
        "decision": decision,
        "profile": profile.name,
        "admittedSkills": admitted,
        "excludedSkills": excluded,
        "warnings": warnings,
        "results": results,
    }