"""Run the real SkillC pipeline and emit newline-delimited trace events."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import time
from pathlib import Path

START = time.perf_counter()
REAL_STDOUT = sys.__stdout__


def emit(event_type: str, **payload) -> None:
    event = {
        "type": event_type,
        "elapsed_ms": round((time.perf_counter() - START) * 1000),
        **payload,
    }
    REAL_STDOUT.write(json.dumps(event, separators=(",", ":")) + "\n")
    REAL_STDOUT.flush()


class EventStream(io.TextIOBase):
    def __init__(self, stream: str):
        self.stream = stream
        self.pending = ""

    def write(self, text: str) -> int:
        self.pending += text
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            emit("terminal", stream=self.stream, text=line)
        return len(text)

    def flush(self) -> None:
        if self.pending:
            emit("terminal", stream=self.stream, text=self.pending)
            self.pending = ""


class SkillCProfiler:
    def __init__(self, package_root: Path):
        self.package_root = package_root.resolve()
        self.seen: set[tuple[str, str]] = set()

    def __call__(self, frame, event: str, arg):
        if event != "call":
            return self
        path = Path(frame.f_code.co_filename).resolve()
        if self.package_root not in path.parents:
            return self
        module = path.relative_to(self.package_root).as_posix()
        function = frame.f_code.co_name
        key = module, function
        if key not in self.seen and not function.startswith("<"):
            self.seen.add(key)
            emit(
                "module",
                module=f"src/skillc/{module}",
                function=function,
                line=frame.f_code.co_firstlineno,
            )
        return self


def invoke(argv: list[str], package_root: Path) -> int:
    from skillc.cli import main

    display = "skillc " + " ".join(
        f'"{part}"' if " " in part else part for part in argv
    )
    emit("command", text=f"$ {display}")
    stdout = EventStream("stdout")
    stderr = EventStream("stderr")
    profiler = SkillCProfiler(package_root)
    try:
        sys.setprofile(profiler)
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(argv)
    finally:
        sys.setprofile(None)
        stdout.flush()
        stderr.flush()
    emit("command_exit", command=argv[0], exit_code=code)
    return code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--environment-grant", action="append", default=[])
    parser.add_argument("--environment-manifest", type=Path)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--model")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    package_root = repo_root / "src" / "skillc"
    sys.path.insert(0, str(repo_root / "src"))

    source_path = Path(args.source)
    source_text = source_path.read_text(encoding="utf-8")
    emit("phase", id="receive", label="Intent received", detail=source_path.name)
    emit(
        "artifact",
        stage="receive",
        title="Received source",
        content={
            "filename": source_path.name,
            "characters": len(source_text),
            "source": source_text,
        },
    )
    compile_mode = "Azure Foundry semantic compaction" if args.llm else "Deterministic compaction"
    emit("phase", id="compile", label=compile_mode, detail="Markdown to formal pack")
    pack_path = str(Path(args.source).with_name("compiled-pack.json"))
    provenance_path = str(Path(args.source).with_name("compaction-provenance.json"))
    compile_args = [
        "compile",
        args.source,
        "--profile",
        "none",
        "--quiet",
        "--output",
        pack_path,
        "--provenance-output",
        provenance_path,
    ]
    for grant in sorted(set(args.environment_grant)):
        compile_args.extend(["--tool", grant])
    if args.llm:
        compile_args.extend(["--llm", "--llm-provider", "azure-openai", "--model", args.model])
        if args.environment_manifest:
            compile_args.extend(["--vocabulary", str(args.environment_manifest)])
    compaction_usage: list[dict] = []
    if args.llm:
        from skillc.frontend.providers import metered

        with metered() as compaction_usage:
            compile_code = invoke(compile_args, package_root)
    else:
        compile_code = invoke(compile_args, package_root)
    if compile_code != 0:
        if args.llm:
            report_usage({"compaction": compaction_usage})
        emit(
            "artifact",
            stage="compile",
            title="Compaction output",
            content={"status": "error", "exit_code": compile_code},
        )
        emit("complete", exit_code=compile_code, verdict="ERROR")
        return compile_code
    emit("terminal", stream="stdout", text="# compiled-pack.json")
    pack = json.loads(Path(pack_path).read_text(encoding="utf-8"))
    provenance = json.loads(Path(provenance_path).read_text(encoding="utf-8"))
    emit(
        "artifact",
        stage="compile",
        title="Compaction output",
        content={"pack": pack, "provenance": provenance},
    )
    for line in Path(pack_path).read_text(encoding="utf-8").splitlines():
        emit("terminal", stream="stdout", text=line)

    emit(
        "phase",
        id="environment",
        label="Environment loaded",
        detail="cached skillc.env snapshot",
    )
    grants = sorted(set(args.environment_grant))
    manifest = (
        json.loads(args.environment_manifest.read_text(encoding="utf-8"))
        if args.environment_manifest else None
    )
    emit(
        "artifact",
        stage="environment",
        title="Observed environment input",
        content={"grants": grants, "grant_count": len(grants), "manifest": manifest},
    )
    profiler = SkillCProfiler(package_root)
    try:
        sys.setprofile(profiler)
        from skillc.frontend.contracts import bind_environment

        binding = bind_environment(pack, grants, manifest)
    finally:
        sys.setprofile(None)
    emit(
        "phase",
        id="bind",
        label="Requirements bound to grants",
        detail=(
            f"{len(binding.granted)}/{len(binding.required)} required capabilities granted"
        ),
    )
    emit(
        "binding",
        required=list(binding.required),
        environment_grants=grants,
        granted=list(binding.granted),
        unavailable=list(binding.unavailable),
    )
    emit(
        "artifact",
        stage="bind",
        title="Requirement-to-environment binding",
        content={
            "required": list(binding.required),
            "environment_grants": grants,
            "granted_requirements": list(binding.granted),
            "unavailable_requirements": list(binding.unavailable),
            "environment_contracts_applied": list(binding.contracts_applied),
            "goal_names_outside_environment_vocabulary": list(binding.unaligned),
            "bound_pack": binding.pack,
        },
    )
    bound_path = str(Path(args.source).with_name("environment-bound-pack.json"))
    Path(bound_path).write_text(
        json.dumps(binding.pack, indent=2) + "\n",
        encoding="utf-8",
    )
    emit("terminal", stream="stdout", text="# environment binding")
    emit(
        "terminal",
        stream="stdout",
        text=f"required: {', '.join(binding.required) or '(none)'}",
    )
    emit(
        "terminal",
        stream="stdout",
        text=f"granted required: {', '.join(binding.granted) or '(none)'}",
    )
    emit(
        "terminal",
        stream="stdout",
        text=f"required but unavailable: {', '.join(binding.unavailable) or '(none)'}",
    )
    if manifest and manifest.get("contracts"):
        emit(
            "terminal",
            stream="stdout",
            text=(
                f"environment contracts applied: {', '.join(binding.contracts_applied)}"
                if binding.contracts_applied else
                "environment contracts not applied; goal names outside the "
                f"environment vocabulary: {', '.join(binding.unaligned) or '(none)'}"
            ),
        )

    from skillc.checker import observe_check

    stage_titles = {
        "schema": "Static validation output",
        "capability": "Capability existence output",
        "interaction": "Interaction checking output",
        "reachability": "Goal reachability output",
        "verdict": "Final verdict",
    }
    stage_details = {
        "schema": ("Static validation", "Validate and normalize the bound pack"),
        "capability": ("Capability existence", "Compare required actions with grants"),
        "interaction": ("Interaction checking", "Projection and role conformance"),
        "reachability": ("Goal reachability", "Solver-backed may-reachability"),
        "verdict": ("Verdict emitted", "ACHIEVABLE, IMPOSSIBLE, or UNKNOWN"),
    }

    checked = {}

    def publish_check_artifact(stage: str, content: dict) -> None:
        label, detail = stage_details[stage]
        emit("phase", id=stage, label=label, detail=detail)
        emit(
            "artifact",
            stage=stage,
            title=stage_titles[stage],
            content=content,
        )
        checked[stage] = content

    with observe_check(publish_check_artifact):
        check_args = [
            "check",
            bound_path,
            "--compaction-provenance",
            provenance_path,
            "--json",
            "--verbose",
        ]
        if args.environment_manifest:
            check_args.extend(["--vocabulary", str(args.environment_manifest)])
        check_args.extend(["--source", args.source])
        check_code = invoke(check_args, package_root)
    if args.llm and "verdict" in checked:
        explanation_usage = explain(source_text, checked["verdict"], binding.pack["goal"], {
            "required_but_unavailable": list(binding.unavailable),
            "environment_contracts_applied": list(binding.contracts_applied),
            "goal_names_outside_environment_vocabulary": list(binding.unaligned),
        }, args.model)
        report_usage({"compaction": compaction_usage, "explanation": explanation_usage})
    verdict = {0: "ACHIEVABLE", 1: "IMPOSSIBLE", 3: "UNKNOWN"}.get(check_code, "ERROR")
    emit("complete", exit_code=check_code, verdict=verdict)
    return check_code


def explain(source: str, verdict: dict, goal, environment: dict, model: str) -> list[dict]:
    """Ask the LLM to explain the checker's verdict; return its token usage."""
    from skillc.frontend.llm import explain_verdict
    from skillc.frontend.providers import metered

    emit("phase", id="verdict", label="LLM explanation", detail="untrusted; the checker decided")
    with metered() as usage:
        try:
            text = explain_verdict(source, verdict, goal=goal, environment=environment,
                                   model=model, provider="azure-openai")
        except (RuntimeError, ValueError, OSError) as error:
            text = ""
            emit("terminal", stream="stderr", text=f"LLM explanation unavailable: {error}")
    if text:
        emit("explanation", text=text)
        emit("terminal", stream="stdout", text="# LLM explanation (untrusted; the checker decided)")
        emit("terminal", stream="stdout", text=text)
    return usage


def usage_totals(blocks: list[dict]) -> dict:
    cached = sum(int(block.get("cache_read_input_tokens", 0)) for block in blocks)
    uncached = sum(int(block.get("input_tokens", 0)) for block in blocks)
    output = sum(int(block.get("output_tokens", 0)) for block in blocks)
    return {"calls": len(blocks), "input_tokens": uncached + cached,
            "cached_input_tokens": cached, "output_tokens": output,
            "total_tokens": uncached + cached + output}


def report_usage(stages: dict[str, list[dict]]) -> None:
    per_stage = {stage: usage_totals(blocks) for stage, blocks in stages.items()}
    total = usage_totals([block for blocks in stages.values() for block in blocks])
    emit("usage", stages=per_stage, total=total)
    emit("terminal", stream="stdout", text="# LLM token usage")
    for stage, totals in {**per_stage, "total": total}.items():
        emit("terminal", stream="stdout", text=(
            f"{stage:<11} calls={totals['calls']} input={totals['input_tokens']} "
            f"(cached {totals['cached_input_tokens']}) output={totals['output_tokens']} "
            f"total={totals['total_tokens']}"))


if __name__ == "__main__":
    raise SystemExit(main())
