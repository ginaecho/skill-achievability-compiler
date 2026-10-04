"""skillc command-line interface.

  skillc compile SKILL.md [--profile P] [-o pack.json]   markdown -> pack
  skillc check   FILE     [--profile P] [--json]         pack.json or SKILL.md -> verdict
  skillc scan    DIR      [--profile P] [--json|--md]    batch-check a skill tree
  skillc audit   PATH     [--json]                       bundle security pre-pass
  skillc cost    FILE|DIR [--llm] [--json]                token economics of checking
  skillc ce      FILE     [--to ce|json]                  controlled English <-> pack
  skillc eval                                            corpus evaluation
  skillc profiles                                        list capability profiles
    skillc hook pre-session [--request FILE|-]              host skill admission

Exit codes: 0 achievable / all pass, 1 impossible / soundness violation,
2 usage or input error, 3 unknown (an abstention, never a refutation).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from . import __version__
from .checker import Verdict, check
from .evaluate import evaluate, format_report, load_corpus
from .frontend.ce import CEError
from .frontend.markdown import CompileResult, compile_file
from .hooks import HookRequestError, run_pre_session_hook
from .pack import Pack, PackError, pack_digest
from .profiles import builtin_profiles, load_profile


def _load_result(source: str | Path, args) -> tuple[dict, CompileResult | None]:
    """Return (pack, compile result) for a local file or MCP resource."""
    if getattr(args, "mcp_command", None):
        from .mcp import load_pack
        return load_pack(args.mcp_command, args.mcp_arg or [], str(source)), None

    path = Path(source)
    res = None
    if path.suffix == ".json":
        pack = json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix == ".ce":
        from .frontend.ce import compile_ce
        pack = compile_ce(path.read_text(encoding="utf-8"))
    else:
        profile = load_profile(args.profile)
        if getattr(args, "tool", None):
            profile = profile.with_tools(args.tool)
        if getattr(args, "llm", False):
            from .frontend.llm import RUNTIME_ABILITY_PROFILES, compact, compact_ce
            abilities = list(RUNTIME_ABILITY_PROFILES[args.llm_runtime])
            abilities.extend(args.runtime_ability or [])
            kwargs = {}
            if getattr(args, "runtime", None):
                from .frontend.runtime import load_runtime
                front, kwargs = compact_ce, {"runtime": load_runtime(args.runtime)}
            else:
                front = compact_ce if getattr(args, "via_ce", False) else compact
            pack = front(path.read_text(encoding="utf-8"), model=args.model,
                         provider=args.llm_provider,
                         runtime_abilities=abilities or None, **kwargs)
        else:
            res = compile_file(path, profile)
            pack = res.pack
    if getattr(args, "contract", None):
        from .frontend.contract import bind_contract
        contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
        pack = bind_contract(pack, contract)
        if res is not None:
            res.pack = pack
            res.goal_source = "contract"
    return pack, res


def _check_loaded(pack, res, args):
    scope = "goal" if getattr(args, "goal_only", False) else "protocol"
    if scope == "goal" and res is not None and res.goal_source == "tool_usage_only":
        return Verdict(
            False, "INCOMPLETE_COMPACTION",
            "deterministic extraction captured tool usage, not the task goal; "
            "supply a reviewed --contract, an embedded pack, or semantic compaction",
            unknown=True, decision_scope=scope, pack_digest=pack_digest(pack))
    return check(pack,
                 semantics="adversarial" if getattr(args, "adversarial", False) else "may",
                 scope=scope)


def cmd_compile(args) -> int:
    pack, res = _load_result(args.file, args)
    out = json.dumps(pack, indent=2)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    if res is not None and not args.quiet:
        _print_provenance(res, file=sys.stderr)
    return 0


def _print_provenance(res: CompileResult, file=sys.stdout) -> None:
    if res.embedded:
        print("[embedded skillc-pack block used verbatim]", file=file)
        return
    fm = sorted(t for t, s in res.declared.items() if s.startswith("frontmatter"))
    pl = sorted(t for t, s in res.declared.items() if s.startswith("prose"))
    if fm:
        print(f"declared (frontmatter): {', '.join(fm)}", file=file)
    if pl:
        print(f"declared (prose):       {', '.join(pl)}", file=file)
    if res.invocations:
        print("invocations:", file=file)
        for inv in res.invocations:
            note = "" if inv.raw.lower() == inv.tool else f"  [{inv.raw} -> {inv.tool}]"
            print(f"  line {inv.line:>4}: {inv.tool} ({inv.kind}){note}", file=file)
    for n in res.notes:
        print(f"read: {n}", file=file)
    for w in res.warnings:
        print(f"warning: {w}", file=file)


def cmd_check(args) -> int:
    pack, res = _load_result(args.file, args)
    v = _check_loaded(pack, res, args)
    if args.json:
        out = v.to_dict()
        out["pack_name"] = pack.get("name", "?")
        if res is not None:
            out["compaction_goal_source"] = res.goal_source
        print(json.dumps(out, indent=2))
    else:
        print(f"{pack.get('name', '?')}: {v.label}"
              + (f" [{v.reason}]" if not v.achievable else ""))
        if v.detail and not v.achievable:
            print(f"  {v.detail}")
        if v.unknown:
            print("  UNKNOWN is an abstention, not a refutation or permission to run.")
        if res is not None and v.refuted and v.reason == "MISSING_CAPABILITY":
            lines = {i.tool: i.line for i in reversed(res.invocations)}
            for capname in v.frontier:
                loc = f" (line {lines[capname]})" if capname in lines else ""
                print(f"  missing: {capname}{loc}")
        if v.assumed_conformant:
            print("  assumed conformant (participants of G with no declared "
                  "behaviour): " + ", ".join(v.assumed_conformant))
        if args.verbose and v.achievable:
            print("  witness:", " -> ".join(f"{k}:{x}" for k, x in v.witness))
    if v.unknown:
        return 3
    return 0 if v.achievable else 1


def cmd_scan(args) -> int:
    root = Path(args.dir)
    files = sorted(root.rglob(args.glob))
    if not files:
        print(f"no files matching {args.glob!r} under {root}", file=sys.stderr)
        return 2
    rows = []
    for f in files:
        rel = f.relative_to(root)
        try:
            pack, res = _load_result(f, args)
            v = _check_loaded(pack, res, args)
            rows.append({"skill": rel.as_posix(), "verdict": v.label,
                         "reason": v.reason if not v.achievable else "",
                         "frontier": list(v.frontier),
                         "unknown": v.unknown, "refuted": v.refuted,
                         "decision_scope": v.decision_scope,
                         "refutation_scope": v.refutation_scope})
        except (PackError, ValueError) as e:
            rows.append({"skill": rel.as_posix(), "verdict": "ERROR",
                         "reason": type(e).__name__, "frontier": [str(e)],
                         "unknown": False, "refuted": False})
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        w = max(len(r["skill"]) for r in rows)
        for r in rows:
            extra = f"  {r['reason']} {r['frontier']}" if r["reason"] else ""
            print(f"{r['skill']:<{w}}  {r['verdict']}{extra}")
        n_ok = sum(r["verdict"] == "ACHIEVABLE" for r in rows)
        n_unknown = sum(r["unknown"] for r in rows)
        n_refuted = sum(r["refuted"] for r in rows)
        print(f"\n{n_ok}/{len(rows)} achievable under profile "
              f"'{args.profile}'; {n_refuted} refuted, {n_unknown} unknown "
              f"(abstentions -- not refutations or permission to run)")
    return 0


def cmd_audit(args) -> int:
    from .audit import audit_tree
    results = audit_tree(args.path)
    n_err = 0
    if args.json:
        print(json.dumps({b: [f.to_dict() for f in fs]
                          for b, fs in results.items()}, indent=2))
        n_err = sum(f.severity == "error" for fs in results.values() for f in fs)
    else:
        for bundle, findings in results.items():
            if not findings and not args.quiet:
                print(f"{bundle}: clean")
                continue
            for f in findings:
                loc = f":{f.line}" if f.line else ""
                print(f"{bundle}: {f.severity.upper()} [{f.code}] {f.message} "
                      f"({f.file}{loc})")
                n_err += f.severity == "error"
        n = len(results)
        print(f"\naudited {n} bundle{'s' if n != 1 else ''}, "
              f"{n_err} error-severity finding{'s' if n_err != 1 else ''}")
    return 1 if n_err else 0


def cmd_cost(args) -> int:
    """What the check cost, against what running the skill unchecked would.

    Refuted skills get a failure-profile waste estimate; achievable ones get
    the honest denominator -- verification as a share of one successful run,
    which is what a healthy skill pays for the check that told it nothing.
    """
    from .frontend.llm import metered
    from .tokens import (CorpusEconomics, RuntimeModel, check_cost, economics,
                         estimate_tokens, measured_cost)

    # Two independent questions, two flags: --llm actually compacts with the
    # model and prices the usage the API reported for those calls; --price-llm
    # models what the LLM front-end *would* cost without spending a token.
    priced_llm = args.llm or args.price_llm

    # (name, source text, pack, usage blocks of the compaction calls)
    sources: list[tuple[str, str, dict, list[dict]]] = []
    if args.corpus:
        for spec in load_corpus():
            # `nl` is the spec's natural-language source: the actual
            # input a compaction front-end would be billed for.  The corpus
            # ships packs, so nothing is compacted and nothing is measured.
            sources.append((spec["id"], spec.get("nl", ""), spec["pack"], []))
    else:
        root = Path(args.path) if args.path else None
        if root is None:
            print("skillc: cost needs a path, or --corpus", file=sys.stderr)
            return 2
        files = [root] if root.is_file() else sorted(root.rglob(args.glob))
        if not files:
            print(f"no files matching {args.glob!r} under {root}", file=sys.stderr)
            return 2
        for f in files:
            text = f.read_text(encoding="utf-8") if f.suffix != ".json" else ""
            try:
                with metered() as usage:
                    pack, _ = _load_result(f, args)
            except (PackError, ValueError) as e:
                print(f"skillc: {f}: {type(e).__name__}: {e}", file=sys.stderr)
                continue
            sources.append((pack.get("name", f.stem), text, pack, usage))

    model = RuntimeModel(cache_hit_rate=args.cache_hit_rate)
    corpus = CorpusEconomics(price=args.price)
    achievable: list[tuple[str, int, int]] = []
    measured: list[bool] = []          # per priced skill: usage measured?
    for name, text, pack, usage in sources:
        try:
            v = check(pack)
        except (PackError, ValueError) as e:
            print(f"skillc: {name}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        src = text or json.dumps(pack)
        if args.llm and usage:
            ver = measured_cost(usage)
        else:
            ver = check_cost(src, llm=priced_llm, repair_rounds=args.repair_rounds)
        if priced_llm:
            measured.append(ver.measured)
        if v.refuted and v.reason in _WASTE_REASONS:
            corpus.rows.append(economics(
                src, v.reason, name=name, model=model,
                verification=ver, price=args.price))
        else:
            run = replace(model, skill_tokens=estimate_tokens(src)).run_cost(
                _SUCCESS_TURNS)
            achievable.append((name, ver.total_tokens, run.total_tokens))

    front = _front_end_label(priced_llm, measured)
    if args.json:
        out = corpus.to_dict()
        out["front_end"] = front
        out["not_refuted"] = [
            {"skill": n, "verification_tokens": vt,
             "successful_run_tokens": rt,
             "verification_share_of_one_run": round(vt / rt, 6) if rt else 0.0}
            for n, vt, rt in achievable]
        print(json.dumps(out, indent=2))
        return 0

    print(f"front-end: {front}   trusted checker: 0 tokens (z3, no model in "
          f"the decision path)")
    if corpus.rows:
        print(f"\n{'skill':<28} {'reason':<19} {'check':>7} "
              f"{'waste/run (lo-typ-hi)':>28} {'x':>7}")
        for e in corpus.rows:
            lo, ty, hi = (e.waste_low.total_tokens, e.waste_typical.total_tokens,
                          e.waste_high.total_tokens)
            lev = "inf" if not e.verification.total_tokens else \
                f"{ty / e.verification.total_tokens:.0f}x"
            print(f"{e.skill[:28]:<28} {e.reason:<19} "
                  f"{e.verification.total_tokens:>7,} "
                  f"{_fmt(lo) + '-' + _fmt(ty) + '-' + _fmt(hi):>28} {lev:>7}")
        t = corpus.totals()
        print(f"\nrefuted {t['skills_refuted']} skill(s) before execution")
        print(f"  tokens spent checking : {t['verification_tokens']:,} "
              f"(${t['verification_usd']:.4f})")
        w = t["waste_avoided_tokens"]
        u = t["waste_avoided_usd"]
        print(f"  tokens NOT wasted     : {w['typical']:,} typical "
              f"(${u['typical']:.4f}), band {w['low']:,}-{w['high']:,}")
        lev = t["leverage_typical"]
        print(f"  leverage (typical)    : "
              + ("unbounded -- the check spends no tokens at all"
                 if lev is None else f"{lev}x, per invocation avoided"))
    if achievable:
        vt = sum(v for _, v, _ in achievable)
        rt = sum(r for _, _, r in achievable)
        print(f"\n{len(achievable)} skill(s) not refuted -- the check bought "
              f"no savings, so this is what it cost them:")
        print(f"  tokens spent checking : {vt:,}")
        print(f"  one successful run    : {rt:,} (modelled)")
        share = (vt / rt * 100) if rt else 0.0
        print(f"  checking is {share:.1f}% of running each skill once")
    print("\nRuntime waste is a MODEL, not a measurement (see skillc.tokens): "
          "\nit prices a run that, if the refutation is right, never happens.")
    return 0


_WASTE_REASONS = ("MISSING_CAPABILITY", "BLOCKED_GUARD", "GOAL_UNSAT",
                  "NON_PROJECTABLE", "NON_CONFORMANT")
_SUCCESS_TURNS = 10


def _front_end_label(priced_llm: bool, measured: list[bool]) -> str:
    """Says "measured" only for usage a live API call actually reported."""
    if not priced_llm:
        return "deterministic front-end"
    if measured and all(measured):
        return "LLM compaction (measured)"
    if any(measured):
        return "LLM compaction (measured where the API reported usage, else modelled)"
    return "LLM compaction (modelled)"


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)


def cmd_eval(args) -> int:
    corpus = load_corpus()
    res = evaluate(corpus)
    print(format_report(res, corpus))
    ok = res.sound and res.fp_all_spurious(corpus)
    return 0 if ok else 1


def cmd_ce(args) -> int:
    """Render a pack (or any compiled input) as CE, or a .ce file as JSON."""
    from .frontend.ce import render_ce
    path = Path(args.file)
    if args.to == "json" or (args.to is None and path.suffix == ".ce"):
        pack, _ = _load_result(path, args)
        print(json.dumps(pack, indent=2))
    else:
        pack, _ = _load_result(path, args)
        sys.stdout.write(render_ce(pack))
    return 0


HOOKS_SNIPPET = {"hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command",
                                     "command": "skillc monitor hook prompt"}]}],
    "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command",
                                               "command": "skillc monitor hook pre"}]}],
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command",
                                                "command": "skillc monitor hook post"}]}]}}


def cmd_monitor(args) -> int:
    from .monitor import Config, Monitor
    root = Path(args.root)
    cfg_path = root / ".skillc" / "monitor.json"
    if args.action == "init":
        cfg = Config(runtime=args.runtime, thinking=args.thinking)
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(cfg.dump(), indent=1) + "\n", encoding="utf-8")
        print(f"wrote {cfg_path}")
        print("add to .claude/settings.json:")
        print(json.dumps(HOOKS_SNIPPET, indent=1))
        return 0
    if args.action == "hook":
        from .monitor_hook import main as hook_main
        return hook_main(args.arg)
    mon = Monitor(Config.load(cfg_path), root)
    if args.action == "plan":
        d, info = mon.check_plan(Path(args.arg).read_text(encoding="utf-8"))
        print(json.dumps({**d.to_dict(), **info}, indent=1))
        return 0 if d.action == "allow" else 1
    if args.action == "status":
        print(json.dumps({k: v for k, v in mon.state.__dict__.items() if k != "log"}
                         | {"log": mon.state.log[-10:]}, indent=1))
        return 0
    if args.action == "reset":
        mon.state_path.unlink(missing_ok=True)
        return 0
    raise KeyError(f"unknown monitor action {args.action!r}")


def cmd_profiles(args) -> int:
    for name in builtin_profiles():
        p = load_profile(name)
        print(f"{p.name:<12} {len(p.tools):>3} tools, shell={p.shell}  -- {p.description}")
    return 0


def cmd_hook_pre_session(args) -> int:
    """Run the versioned pre-session hook over a file or stdin request."""
    if args.stdio or args.request == "-":
        request = json.load(sys.stdin)
    else:
        request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    result = run_pre_session_hook(request)
    output = json.dumps(result, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 1 if result["decision"] == "block-session" else 0


def cmd_hook_agent_session(args) -> int:
    """Run preflight for one configured agent and emit host hook JSON."""
    request = {
        "schema": "skillc.hook.pre-session/1",
        "runtime": {
            "profile": "agent-frontmatter",
            "capabilities": [],
            "shell": True,
        },
        "skills": [{
            "id": Path(args.agent).stem,
            "path": args.agent,
            "audit": False,
        }],
        "policy": {
            "impossible": "block-session",
            "unknown": "warn",
            "auditError": "block-session",
        },
        "semantics": "may",
    }
    result = run_pre_session_hook(request)
    if result["decision"] == "block-session":
        messages = [
            diagnostic["message"]
            for skill in result["results"]
            if skill["action"] == "block-session"
            for diagnostic in skill["diagnostics"]
        ]
        response = {
            "continue": False,
            "stopReason": "skillc blocked this agent session: "
                          + "; ".join(messages),
        }
        exit_code = 2
    elif result["decision"] == "allow-with-warnings":
        response = {
            "continue": True,
            "systemMessage": "skillc admitted this agent with warnings.",
        }
        exit_code = 0
    else:
        response = {"continue": True}
        exit_code = 0
    print(json.dumps(response, separators=(",", ":")))
    return exit_code


def cmd_doctor(args) -> int:
    """Verify runtime dependencies and optional workspace integration."""
    import platform
    import shutil

    import yaml
    import z3

    failures = []
    print(f"skillc {__version__}")
    print(f"python {platform.python_version()} ({sys.executable})")
    print(f"pyyaml {yaml.__version__}")
    print(f"z3 {z3.get_version_string()}")
    executable = shutil.which("skillc")
    print(f"command {executable or 'not on PATH'}")
    if not executable:
        failures.append("skillc executable is not on PATH")

    if args.workspace:
        from .integrate import (HOOK_MARKER, discover_agents, resolve_agents)

        workspace = Path(args.workspace).resolve()
        scripts = [
            workspace / ".github/hooks/scripts/skillc-pre-session.ps1",
            workspace / ".github/hooks/scripts/skillc-pre-session.sh",
        ]
        for script in scripts:
            present = script.is_file()
            print(f"adapter {script.relative_to(workspace).as_posix()}: "
                  f"{'ok' if present else 'missing'}")
            if not present:
                failures.append(f"missing adapter: {script}")
        agents = resolve_agents(workspace, args.agent or [])
        if args.configured:
            agents.extend(
                agent for agent in discover_agents(workspace)
                if HOOK_MARKER in agent.read_text(encoding="utf-8")
                and agent not in agents
            )
        if args.configured and not agents:
            failures.append("no agents have a skillc hook")
        for agent in agents:
            configured = HOOK_MARKER in agent.read_text(encoding="utf-8")
            print(f"agent {agent.relative_to(workspace).as_posix()}: "
                  f"{'configured' if configured else 'missing hook'}")
            if not configured:
                failures.append(f"agent is missing skillc hook: {agent}")
                continue
            result = run_pre_session_hook({
                "schema": "skillc.hook.pre-session/1",
                "runtime": {
                    "profile": "agent-frontmatter",
                    "capabilities": [],
                    "shell": True,
                },
                "skills": [{
                    "id": agent.stem,
                    "path": str(agent),
                    "audit": False,
                }],
                "policy": {
                    "impossible": "block-session",
                    "unknown": "warn",
                    "auditError": "block-session",
                },
                "semantics": "may",
            })
            print(f"preflight {agent.name}: {result['decision']}")
            if result["decision"] == "block-session":
                failures.append(f"preflight blocks agent: {agent}")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    print("doctor: PASS")
    return 0


def cmd_integrate(args) -> int:
    """Install scoped SessionStart hooks for selected workspace agents."""
    from .integrate import (choose_agents, discover_agents, install_integration,
                            resolve_agents)

    workspace = Path(args.workspace).resolve()
    if args.all:
        selected = discover_agents(workspace)
    elif args.agent:
        selected = resolve_agents(workspace, args.agent)
    else:
        selected = choose_agents(discover_agents(workspace))
    result = install_integration(workspace, selected)
    print(f"installed shared adapters under {result.scripts[0].parent}")
    for agent in result.agents:
        print(f"enabled preflight: {agent.relative_to(workspace).as_posix()}")
    return 0


def _add_compile_opts(sp) -> None:
    sp.add_argument("--profile", default="claude-ai",
                    help="capability profile (built-in name or JSON path)")
    sp.add_argument("--tool", action="append", metavar="NAME",
                    help="grant an extra tool capability (repeatable)")
    sp.add_argument("--contract", metavar="JSON",
                    help="bind extraction to reviewed goal, capabilities, and initial state")
    sp.add_argument("--llm", action="store_true",
                    help="use the semantic LLM compaction front-end")
    sp.add_argument("--llm-provider", choices=("anthropic", "azure-openai"),
                    help="LLM provider (default: SKILLC_LLM_PROVIDER or anthropic)")
    sp.add_argument("--model",
                    help="Anthropic model or Azure OpenAI deployment name")
    sp.add_argument("--llm-runtime",
                    choices=("none", "consumer", "developer"), default="none",
                    help="runtime abilities supplied to semantic compaction")
    sp.add_argument("--runtime-ability", action="append", metavar="TEXT",
                    help="additional granted runtime ability (repeatable)")
    sp.add_argument("--runtime", metavar="NAME|JSON",
                    help="with --llm: compact via Controlled English bound to a "
                         "runtime manifest (e.g. developer-sandbox); tools are "
                         "granted only through the manifest")
    sp.add_argument("--via-ce", action="store_true",
                    help="with --llm: the model writes Controlled English, "
                         "which is parsed into the pack deterministically")


def _add_mcp_opts(sp) -> None:
    sp.add_argument("--mcp-command", metavar="COMMAND",
                    help="read FILE as a fact-pack resource URI from this "
                         "stdio MCP server command")
    sp.add_argument("--mcp-arg", action="append", default=[], metavar="ARG",
                    help="argument for the MCP server command (repeatable)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="skillc",
                                 description="Skill Achievability Compiler")
    ap.add_argument("--version", action="version", version=f"skillc {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("compile", help="markdown -> achievability pack (JSON)")
    sp.add_argument("file")
    sp.add_argument("-o", "--output")
    sp.add_argument("-q", "--quiet", action="store_true")
    _add_compile_opts(sp)
    _add_mcp_opts(sp)
    sp.set_defaults(fn=cmd_compile)

    sp = sub.add_parser("check", help="decide achievability of a pack or SKILL.md")
    sp.add_argument("file")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("-v", "--verbose", action="store_true")
    decisions = sp.add_mutually_exclusive_group()
    decisions.add_argument("--adversarial", action="store_true",
                    help="require the goal under EVERY resolution of choices "
                         "marked external (must-achievability)")
    decisions.add_argument("--goal-only", action="store_true",
                           help="refute only with a protocol-independent goal certificate; "
                                "otherwise abstain on protocol rejection")
    _add_compile_opts(sp)
    _add_mcp_opts(sp)
    sp.set_defaults(fn=cmd_check)

    sp = sub.add_parser("scan", help="batch-check every skill under a directory")
    sp.add_argument("dir")
    sp.add_argument("--glob", default="SKILL.md")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--goal-only", action="store_true",
                    help="use conservative goal-impossibility scope instead of protocol admission")
    _add_compile_opts(sp)
    sp.set_defaults(fn=cmd_scan)

    sp = sub.add_parser("audit",
                        help="skill-bundle security pre-pass (SkillSpector-like)")
    sp.add_argument("path")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("-q", "--quiet", action="store_true",
                    help="omit clean bundles from the listing")
    sp.set_defaults(fn=cmd_audit)

    sp = sub.add_parser(
        "cost",
        help="token economics: what checking cost vs. what running unchecked "
             "would waste")
    sp.add_argument("path", nargs="?",
                    help="a SKILL.md, a pack.json, or a directory")
    sp.add_argument("--corpus", action="store_true",
                    help="price the built-in evaluation corpus instead of a path")
    sp.add_argument("--price-llm", action="store_true",
                    help="price what the LLM front-end would cost, without "
                         "calling it (--llm calls it and prices what it used)")
    sp.add_argument("--glob", default="SKILL.md")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--price", default="mid", choices=("frontier", "mid", "small"),
                    help="price tier used to convert tokens to dollars")
    sp.add_argument("--repair-rounds", type=int, default=0,
                    help="repair rounds to price into a modelled LLM compaction "
                         "cost (a measured --llm run counts the calls it made)")
    sp.add_argument("--cache-hit-rate", type=float, default=0.0, metavar="R",
                    help="fraction of the re-read runtime prefix served from "
                         "cache; changes dollars, never token counts")
    _add_compile_opts(sp)
    sp.set_defaults(fn=cmd_cost)

    sp = sub.add_parser("ce", help="Controlled English: render a pack as CE, "
                                   "or parse a .ce file to a JSON pack")
    sp.add_argument("file")
    sp.add_argument("--to", choices=("ce", "json"),
                    help="output form (default: json for .ce input, else ce)")
    _add_compile_opts(sp)
    sp.set_defaults(fn=cmd_ce)

    sp = sub.add_parser("eval", help="run the corpus evaluation")
    sp.set_defaults(fn=cmd_eval)

    sp = sub.add_parser("monitor", help="runtime monitor: gate an agent's plan, "
                                        "reasoning and actions (docs/RUNTIME_MONITOR.md)")
    sp.add_argument("action", choices=("init", "hook", "plan", "status", "reset"))
    sp.add_argument("arg", nargs="?", help="hook kind (prompt|pre|post) or plan file")
    sp.add_argument("--root", default=".", help="project directory (default: .)")
    sp.add_argument("--runtime", default="developer-sandbox",
                    help="init: runtime manifest name or JSON path")
    sp.add_argument("--thinking", choices=("stop", "warn", "off"), default="stop",
                    help="init: what reasoning that heads to the impossible does")
    sp.set_defaults(fn=cmd_monitor)

    sp = sub.add_parser("profiles", help="list built-in capability profiles")
    sp.set_defaults(fn=cmd_profiles)

    sp = sub.add_parser("doctor", help="verify runtime and hook dependencies")
    sp.add_argument("--workspace", help="workspace containing installed hooks")
    sp.add_argument("--agent", action="append", metavar="NAME_OR_PATH",
                    help="configured agent to verify; repeatable")
    sp.add_argument("--configured", action="store_true",
                    help="verify every agent already carrying a skillc hook")
    sp.set_defaults(fn=cmd_doctor)

    sp = sub.add_parser(
        "integrate", help="add scoped pre-session hooks to existing agents")
    sp.add_argument("--workspace", default=".",
                    help="workspace root (default: current directory)")
    sp.add_argument("--agent", action="append", metavar="NAME_OR_PATH",
                    help="agent to configure; repeatable (prompts when omitted)")
    sp.add_argument("--all", action="store_true",
                    help="configure every agent under .github/agents")
    sp.set_defaults(fn=cmd_integrate)

    sp = sub.add_parser("hook", help="agent-host hook integrations")
    hook_sub = sp.add_subparsers(dest="hook_cmd", required=True)
    hp = hook_sub.add_parser(
        "pre-session", help="admit or filter skills before creating a session")
    hp.add_argument("--request", default="-", metavar="FILE",
                    help="JSON request file; default '-' reads stdin")
    hp.add_argument("--stdio", action="store_true",
                    help="read one JSON request from stdin")
    hp.add_argument("-o", "--output", help="write JSON response to this file")
    hp.set_defaults(fn=cmd_hook_pre_session)

    hp = hook_sub.add_parser(
        "agent-session", help="run one configured agent's host hook")
    hp.add_argument("--agent", required=True,
                    help="path to the selected agent markdown")
    hp.set_defaults(fn=cmd_hook_agent_session)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except (PackError, HookRequestError, CEError, KeyError, ValueError,
            FileNotFoundError,
            json.JSONDecodeError, RuntimeError) as e:
        print(f"skillc: error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
