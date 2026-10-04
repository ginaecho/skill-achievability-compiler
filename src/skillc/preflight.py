"""Composite skill preflight for editor, hook, and host integrations."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .audit import Finding, audit_bundle
from .checker import Verdict, check
from .frontend.markdown import CompileResult, compile_file
from .pack import PackError
from .profiles import Profile

PREFLIGHT_SCHEMA = "skillc.preflight/1"


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    message: str
    path: str
    line: int = 0
    capability: str = ""

    def to_dict(self) -> dict:
        out = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
            "line": self.line,
        }
        if self.capability:
            out["capability"] = self.capability
        return out


@dataclass
class PreflightResult:
    skill_id: str
    path: str
    profile: str
    status: str
    verdict: str
    reason: str
    summary: str
    diagnostics: list[Diagnostic] = field(default_factory=list)
    frontier: tuple = ()
    witness: tuple = ()
    pack_digest: str = ""
    unknown: bool = False
    refuted: bool = False

    @property
    def admitted(self) -> bool:
        return self.status in ("admitted", "warning")

    def to_dict(self) -> dict:
        return {
            "schema": PREFLIGHT_SCHEMA,
            "skillId": self.skill_id,
            "path": self.path,
            "profile": self.profile,
            "status": self.status,
            "verdict": self.verdict,
            "reason": self.reason,
            "summary": self.summary,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "frontier": list(self.frontier),
            "witness": [list(step) for step in self.witness],
            "packDigest": self.pack_digest,
            "unknown": self.unknown,
            "refuted": self.refuted,
        }


_REASON_CODES = {
    "MISSING_CAPABILITY": "SKILLC001",
    "GOAL_UNSAT": "SKILLC002",
    "BLOCKED_GUARD": "SKILLC003",
    "NON_PROJECTABLE": "SKILLC004",
    "NON_CONFORMANT": "SKILLC005",
    "DYNAMIC_TOPOLOGY": "SKILLC101",
}


def _skill_file(path: Path) -> Path:
    return path / "SKILL.md" if path.is_dir() else path


def _verdict_diagnostics(path: Path, verdict: Verdict,
                         compiled: CompileResult) -> list[Diagnostic]:
    severity = "warning" if verdict.unknown else "error"
    code = _REASON_CODES.get(verdict.reason, "SKILLC000")
    invocation_lines = {i.tool: i.line for i in compiled.invocations}
    if verdict.reason == "MISSING_CAPABILITY" and verdict.frontier:
        return [Diagnostic(
            code, severity, f"Capability '{cap}' is unavailable",
            str(path), invocation_lines.get(cap, 0), capability=cap,
        ) for cap in verdict.frontier]
    return [Diagnostic(code, severity, verdict.detail or verdict.reason,
                       str(path))]


def _audit_diagnostics(findings: list[Finding]) -> list[Diagnostic]:
    return [Diagnostic("SKILLC201", finding.severity, finding.message,
                       finding.file, finding.line)
            for finding in findings]


def preflight_skill(path: str | Path, profile: Profile, *, skill_id: str = "",
                    audit: bool = True,
                    semantics: str = "may") -> PreflightResult:
    """Audit, compile, and check one skill for a concrete runtime profile."""
    source = _skill_file(Path(path))
    identity = skill_id or source.parent.name or source.stem

    if audit:
        findings = audit_bundle(source)
        errors = [finding for finding in findings if finding.severity == "error"]
        if errors:
            return PreflightResult(
                identity, str(source), profile.name, "audit-error", "ERROR",
                "AUDIT_ERROR", f"bundle audit found {len(errors)} error(s)",
                diagnostics=_audit_diagnostics(findings),
            )

    try:
        compiled = compile_file(source, profile)
        verdict = check(compiled.pack, semantics=semantics)
    except (PackError, ValueError, FileNotFoundError) as error:
        return PreflightResult(
            identity, str(source), profile.name, "error", "ERROR",
            "INVALID_SKILL", str(error),
            diagnostics=[Diagnostic("SKILLC202", "error", str(error),
                                    str(source))],
        )

    if verdict.unknown:
        status = "warning"
    elif verdict.refuted:
        status = "refuted"
    else:
        status = "admitted"
    diagnostics = [] if verdict.achievable else _verdict_diagnostics(
        source, verdict, compiled)
    return PreflightResult(
        identity, str(source), profile.name, status, verdict.label,
        verdict.reason, verdict.detail, diagnostics=diagnostics,
        frontier=verdict.frontier, witness=verdict.witness,
        pack_digest=verdict.pack_digest, unknown=verdict.unknown,
        refuted=verdict.refuted,
    )