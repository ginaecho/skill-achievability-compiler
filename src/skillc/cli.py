"""skillc command-line interface.

  skillc compile SKILL.md [--profile P] [-o pack.json]   markdown -> pack
  skillc check   FILE     [--profile P] [--json]         pack.json or SKILL.md -> verdict
  skillc scan    DIR      [--profile P] [--json|--md]    batch-check a skill tree
  skillc audit   PATH     [--json]                       bundle security pre-pass
  skillc cost    FILE|DIR [--llm] [--json]                token economics of checking
  skillc ce      FILE     [--to ce|json]                  controlled English <-> pack
  skillc eval                                            corpus evaluation
  skillc profiles                                        list capability profiles

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
from .checker import Verdict, check, trace_artifact
from .evaluate import evaluate, format_report, load_corpus
from .frontend.ce import CEError
from .frontend.markdown import (
    CompileResult,
    compaction_manifest,
    compile_file,
    result_from_manifest,
)
from .frontend.providers import PROVIDERS
from .pack import PackError, pack_digest
from .profiles import builtin_profiles, load_profile


def _load_result(path: Path, args) -> tuple[dict, CompileResult | None]:
    """Return (pack, compile_result_or_None) for a .json pack, .ce or markdown."""
    res = None
    if path.suffix == ".json":
        pack = json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix == ".ce":
        from .frontend.ce import compile_ce
        pack = compile_ce(path.read_text(encoding="utf-8"))
    elif getattr(args, "llm", False):
        pack = _compact_with_llm(path, args)
    else:
        profile = load_profile(args.profile)
        if getattr(args, "tool", None):
            profile = profile.with_tools(args.tool)
        res = compile_file(path, profile)
        pack = res.pack
    if getattr(args, "contract", None):
        from .frontend.contract import bind_contract
        contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
        pack = bind_contract(pack, contract)
        if res is not None:
            res.pack = pack
            res.goal_source = "contract"
    provenance_path = getattr(args, "compaction_provenance", None)
    if provenance_path:
        if res is not None:
            raise ValueError("--compaction-provenance is only valid for a compiled JSON pack")
        manifest = json.loads(Path(provenance_path).read_text(encoding="utf-8"))
        res = result_from_manifest(pack, manifest)
    return pack, res


def _compact_with_llm(path: Path, args) -> dict:
    """Semantic compaction of a markdown skill (opt-in, untrusted)."""
    from .frontend.llm import compact, compact_ce
    from .frontend.prompts import RUNTIME_ABILITY_PROFILES
    abilities = [*RUNTIME_ABILITY_PROFILES[args.llm_runtime],
                 *(args.runtime_ability or [])]
    kwargs = {}
    if getattr(args, "runtime", None):
        from .frontend.runtime import load_runtime
        front, kwargs = compact_ce, {"runtime": load_runtime(args.runtime)}
    else:
        front = compact_ce if getattr(args, "via_ce", False) else compact
    if getattr(args, "vocabulary", None):
        if front is not compact:
            raise ValueError("--vocabulary applies to JSON compaction, not --runtime or --via-ce")
        kwargs["vocabulary"] = json.loads(Path(args.vocabulary).read_text(encoding="utf-8"))
    return front(path.read_text(encoding="utf-8"), model=args.model,
                 provider=args.llm_provider,
                 runtime_abilities=abilities or None, **kwargs)


def _check_loaded(pack, res, args):
    vocabulary = getattr(args, "vocabulary", None)
    states = (
        json.loads(Path(vocabulary).read_text(encoding="utf-8")).get("states")
        if vocabulary else None
    )
    source = getattr(args, "source", None)
    if source is None and getattr(args, "llm", False) and getattr(args, "file", None):
        source = args.file          # an LLM-compacted intent grounds on its own text
    evidence = [Path(source).read_text(encoding="utf-8")] if source else []
    if evidence and getattr(args, "contract", None):
        evidence.append(Path(args.contract).read_text(encoding="utf-8"))  # reviewed input
    return check_compiled(
        pack,
        res,
        scope="goal" if getattr(args, "goal_only", False) else "protocol",
        semantics="adversarial" if getattr(args, "adversarial", False) else "may",
        vocabulary_states=states,
        source_text="\n".join(evidence) or None,
    )


def check_compiled(pack: dict, res: CompileResult | None, *,
                   scope: str = "protocol", semantics: str = "may",
                   vocabulary_states: dict | None = None,
                   source_text: str | None = None) -> Verdict:
    """Decide a compiled pack, abstaining when compaction established no task
    or when a refutation rests only on names found in no input (the intent
    text, the environment's state vocabulary, or deterministic extraction)."""
    from .frontend.contracts import abstain_ungrounded

    verdict = _decide(pack, res, scope, semantics)
    extracted = {inv.tool for inv in res.invocations} if res else set()
    return abstain_ungrounded(verdict, states=vocabulary_states,
                              source_text=source_text, extracted=extracted, pack=pack)


def _decide(pack: dict, res: CompileResult | None, scope: str, semantics: str) -> Verdict:
    if (
        res is not None
        and res.goal_source == "tool_usage_only"
        and (scope == "goal" or not res.invocations)
    ):
        digest = pack_digest(pack)
        trace_artifact("schema", {
            "status": "passed",
            "pack": pack,
            "pack_digest": digest,
        })
        skipped = {
            "status": "skipped",
            "reason": "compaction did not establish the task goal or required operations",
        }
        for stage in ("capability", "interaction", "reachability"):
            trace_artifact(stage, skipped)
        return Verdict(
            False, "INCOMPLETE_COMPACTION",
            "deterministic extraction captured tool usage, not the task goal; "
            "supply a reviewed --contract, an embedded pack, or semantic compaction",
            unknown=True, decision_scope=scope, pack_digest=digest)
    return check(pack, semantics=semantics, scope=scope)


def cmd_compile(args) -> int:
    pack, res = _load_result(Path(args.file), args)
    out = json.dumps(pack, indent=2)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    if args.provenance_output:
        source = "llm" if args.llm else "compiled"
        manifest = compaction_manifest(res, goal_source=source)
        Path(args.provenance_output).write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
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
    pack, res = _load_result(Path(args.file), args)
    v = _check_loaded(pack, res, args)
    trace_artifact("verdict", v.to_dict())
    if args.json:
        out = v.to_dict()
        out["pack_name"] = pack.get("name", "?")
        if res is not None:
            out["compaction_goal_source"] = res.goal_source
        print(json.dumps(out, indent=2))
    else:
        _print_verdict(pack, res, v, verbose=args.verbose)
    if v.unknown:
        return 3
    return 0 if v.achievable else 1


def _print_verdict(pack: dict, res: CompileResult | None, v: Verdict,
                   verbose: bool) -> None:
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
    if verbose and v.achievable:
        print("  witness:", " -> ".join(f"{k}:{x}" for k, x in v.witness))


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
    from .tokens import (FAILURE_PROFILES, SUCCESSFUL_RUN_TURNS, CorpusEconomics,
                         RuntimeModel, check_cost, economics, estimate_tokens,
                         measured_cost)

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
        if v.refuted and v.reason in FAILURE_PROFILES:
            corpus.rows.append(economics(
                src, v.reason, name=name, model=model,
                verification=ver, price=args.price))
        else:
            run = replace(model, skill_tokens=estimate_tokens(src)).run_cost(
                SUCCESSFUL_RUN_TURNS)
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

    _print_cost_report(corpus, achievable, front)
    return 0


def _print_cost_report(corpus, achievable: list[tuple[str, int, int]],
                       front: str) -> None:
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
        print("  leverage (typical)    : "
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
    pack, _ = _load_result(path, args)
    if args.to == "json" or (args.to is None and path.suffix == ".ce"):
        print(json.dumps(pack, indent=2))
    else:
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
        if args.copilot:
            from .monitor_copilot import HOOKS_FILE, copilot_config, copilot_hooks
            cfg = copilot_config(args.runtime, args.thinking)
        else:
            cfg = Config(runtime=args.runtime, thinking=args.thinking)
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(cfg.dump(), indent=1) + "\n", encoding="utf-8")
        print(f"wrote {cfg_path}")
        if args.copilot:
            hooks_path = root / HOOKS_FILE
            hooks_path.parent.mkdir(parents=True, exist_ok=True)
            hooks_path.write_text(json.dumps(copilot_hooks(), indent=1) + "\n",
                                  encoding="utf-8")
            print(f"wrote {hooks_path} (Copilot CLI and the Copilot cloud agent read it; "
                  "the cloud agent needs skillc installed in copilot-setup-steps)")
            return 0
        print("add to .claude/settings.json:")
        print(json.dumps(HOOKS_SNIPPET, indent=1))
        return 0
    if args.action == "hook":
        if args.arg == "copilot":
            from .monitor_copilot import main as copilot_main
            return copilot_main(args.event or "")
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


def _probe_env(args):
    """Build an environment from the adapters the arguments name."""
    from .env import azure, mcp
    from .env.model import merge
    envs = []
    foundry_env = None
    if getattr(args, "foundry", False) or args.from_raw:
        # the Foundry control plane, live or from one of its exports; a --from-raw DIR that
        # is not a Foundry export falls through to the Azure replay below
        from .env import foundry
        foundry_env = foundry.probe_from_args(args)
        if foundry_env is not None:
            envs.append(foundry_env)
    if args.from_raw and foundry_env is None:
        envs.append(azure.probe(azure.replay_runner(args.from_raw), args.subscription,
                                mode="replay"))
    elif args.azure:
        envs.append(azure.probe(azure.live_runner(args.save_raw), args.subscription))
    if args.mcp_config:
        envs.append(mcp.probe(args.mcp_config, list_tools=args.list_tools))
    if args.claude:
        envs.append(_probe_claude(args, args.needs_from or []))
    if getattr(args, "self", False):
        from .env import selfprobe
        envs.append(selfprobe.self_probe_from_args(args))
    if not envs:
        raise ValueError("say what to probe: --azure, --from-raw DIR, --claude, --foundry, "
                         "--self and/or --mcp-config FILE")
    return merge(*envs)


def _probe_claude(args, intents):
    """The Claude runtime, asking about everything the given intents need."""
    from .env import claude
    from .env.reach import intent_needs, load_intent
    wanted = {"egress": list(args.host or []), "program": list(args.program or []),
              "pymodule": list(args.module or []), "path": list(args.path or []),
              "credential": []}
    for intent in intents:
        intent = load_intent(intent) if isinstance(intent, str) else intent
        for kind, values in intent_needs(intent).items():
            wanted.setdefault(kind, []).extend(values)
    tools = (json.loads(Path(args.tools_file).read_text(encoding="utf-8"))
             if args.tools_file else None)
    connectors = (json.loads(Path(args.connectors_file).read_text(encoding="utf-8"))
                  if args.connectors_file else None)
    return claude.probe(hosts=wanted["egress"], programs=wanted["program"],
                        modules=wanted["pymodule"], paths=wanted["path"],
                        credentials=[*claude.CREDENTIALS, *wanted["credential"]],
                        tools=tools, connectors=connectors,
                        check_egress=not args.no_egress)


def cmd_env(args) -> int:
    from .env.model import Environment, diff, merge
    from .env.report import env_summary, html_page
    if args.action == "probe":
        env = _probe_env(args)
        env.save(args.output)
        print(env_summary(env))
        print(f"wrote {args.output}")
        return 0
    if args.action == "show":
        env = Environment.load(args.file)
        print(env_summary(env))
        if args.html:
            Path(args.html).write_text(html_page(env), encoding="utf-8")
            print(f"wrote {args.html}")
        return 0
    if args.action == "diff":
        changes = diff(Environment.load(args.old), Environment.load(args.new))
        sign = {"added": "+", "removed": "-", "changed": "~"}
        for kind, lines in changes.items():
            for line in lines:
                print(f"{sign[kind]} {line}")
        return 0 if not any(changes.values()) else 1
    if args.action == "merge":
        merge(*(Environment.load(f) for f in args.files)).save(args.output)
        print(f"wrote {args.output}")
        return 0
    if args.action == "from-azd":
        from .env.azd import from_azure_yaml, intent_artifacts
        env = from_azure_yaml(args.azure_yaml)
        if args.output:
            env.save(args.output)
        if args.json:
            print(json.dumps(env.to_dict(), indent=1))
        elif not args.output:
            print(env_summary(env))
        if args.output:
            print(f"wrote {args.output}")
        artifacts = intent_artifacts(args.azure_yaml)
        print("intent artifacts: " + (", ".join(str(a) for a in artifacts) or "(none)"),
              file=sys.stderr)
        return 0
    from .env.reach import load_intent
    from .env.watch import watch
    intents = {Path(i).stem: load_intent(i) for i in args.intent or []}
    watch(args.dir, lambda: _probe_env(args), intents, args.interval,
          rounds=1 if args.once else None,
          on_report=lambda r: print(json.dumps(r, indent=1), flush=True))
    return 0


def cmd_reach(args) -> int:
    from .env.model import Environment
    from .env.reach import as_json, load_catalog, load_intent, reach
    from .env.report import english_plan, html_page, text_report
    intent = load_intent(args.intent)
    if args.env:
        env = Environment.load(args.env)
    elif args.claude:
        env = _probe_claude(args, [intent])
        if args.save_env:
            env.save(args.save_env)
            print(f"wrote {args.save_env}", file=sys.stderr)
    else:
        raise ValueError("say where to look: --env FILE, or --claude to probe this runtime")
    result = reach(intent, env, load_catalog(args.catalog) if args.catalog else None)
    print(as_json(result) if args.json else text_report(result))
    if args.plan:
        Path(args.plan).write_text(english_plan(result), encoding="utf-8")
        print(f"wrote {args.plan}", file=sys.stderr)
    if args.html:
        Path(args.html).write_text(html_page(env, result), encoding="utf-8")
        print(f"wrote {args.html}", file=sys.stderr)
    if result.blocked:
        return 1
    return 0 if result.complete else 3


def cmd_intent(args) -> int:
    """What a SKILL.md / agent.md needs from its runtime, as a skillc.intent/1."""
    from .env.nl import intent_from_text
    intent = intent_from_text(Path(args.file).read_text(encoding="utf-8"), source=args.file)
    if args.output:
        Path(args.output).write_text(json.dumps(intent, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
        return 0
    if args.json:
        print(json.dumps(intent, indent=1))
        return 0
    print(f"{intent['name']}: {intent['description'][:200]}")
    for kind, conds in (("needs", intent["goal"]), ("optional", intent["optional"])):
        for cond in conds:
            print(f"  {kind:<8} {cond}")
            for line in intent["evidence"].get(cond, [])[:2]:
                print(f"           {line}")
    return 0


def _add_probe_opts(sp) -> None:
    sp.add_argument("--azure", action="store_true",
                    help="probe Azure live with your `az login` (read-only commands only)")
    sp.add_argument("--subscription", help="Azure subscription id or name (default: current)")
    sp.add_argument("--save-raw", metavar="DIR",
                    help="also keep every raw az answer under DIR (replayable offline)")
    sp.add_argument("--from-raw", metavar="DIR",
                    help="replay a saved az export instead of calling Azure")
    sp.add_argument("--mcp-config", action="append", metavar="FILE",
                    help="MCP configuration to read (.mcp.json, claude_desktop_config.json, "
                         ".vscode/mcp.json); repeatable")
    sp.add_argument("--list-tools", action="store_true",
                    help="start the configured stdio MCP servers to list their tools")
    sp.add_argument("--needs-from", action="append", metavar="INTENT",
                    help="with --claude: probe what these intents' operations need")
    _add_claude_opts(sp)
    # hosted-agent probes (docs/HOSTED_AGENT.md): the Foundry control plane and the sandbox
    try:
        from .env import foundry
        foundry.add_probe_opts(sp)
    except ImportError:
        pass
    try:
        from .env import selfprobe
        selfprobe.add_self_opts(sp)
    except ImportError:
        pass


def _add_claude_opts(sp) -> None:
    sp.add_argument("--claude", action="store_true",
                    help="probe the Claude runtime: tools, permission rules, egress, "
                         "programs, modules, credentials (names only), paths, connectors")
    sp.add_argument("--host", action="append", help="with --claude: check egress to HOST")
    sp.add_argument("--program", action="append", help="with --claude: look for PROGRAM")
    sp.add_argument("--module", action="append", help="with --claude: look for a Python module")
    sp.add_argument("--path", action="append", help="with --claude: check PATH is writable")
    sp.add_argument("--tools-file", metavar="JSON",
                    help="with --claude: the session's tool names (default: claude-code profile)")
    sp.add_argument("--connectors-file", metavar="JSON",
                    help="with --claude: {connector: [tool, ...]} for connected MCP servers "
                         "not in any config file")
    sp.add_argument("--no-egress", action="store_true",
                    help="with --claude: do not send the egress requests")


def cmd_profiles(args) -> int:
    for name in builtin_profiles():
        p = load_profile(name)
        print(f"{p.name:<12} {len(p.tools):>3} tools, shell={p.shell}  -- {p.description}")
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
    sp.add_argument("--llm-provider", choices=PROVIDERS,
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
    sp.add_argument("--vocabulary", metavar="JSON",
                    help="environment manifest: with --llm the compacted pack reuses "
                         "its tool and state names (contracts are not shown); a "
                         "refutation resting only on conditions outside its states "
                         "becomes UNKNOWN")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="skillc",
                                 description="Skill Achievability Compiler")
    ap.add_argument("--version", action="version", version=f"skillc {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("compile", help="markdown -> achievability pack (JSON)")
    sp.add_argument("file")
    sp.add_argument("-o", "--output")
    sp.add_argument("-q", "--quiet", action="store_true")
    sp.add_argument("--provenance-output", metavar="JSON",
                    help="write compaction provenance beside the compiled pack")
    _add_compile_opts(sp)
    sp.set_defaults(fn=cmd_compile)

    sp = sub.add_parser("check", help="decide achievability of a pack or SKILL.md")
    sp.add_argument("file")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("-v", "--verbose", action="store_true")
    sp.add_argument("--compaction-provenance", metavar="JSON",
                    help="provenance emitted by compile --provenance-output")
    sp.add_argument("--source", metavar="FILE",
                    help="the original intent text: a refutation must name something "
                         "it (or the --vocabulary environment) contains, else UNKNOWN")
    decisions = sp.add_mutually_exclusive_group()
    decisions.add_argument("--adversarial", action="store_true",
                    help="require the goal under EVERY resolution of choices "
                         "marked external (must-achievability)")
    decisions.add_argument("--goal-only", action="store_true",
                           help="refute only with a protocol-independent goal certificate; "
                                "otherwise abstain on protocol rejection")
    _add_compile_opts(sp)
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
    sp.add_argument("arg", nargs="?", help="hook kind (prompt|pre|post for Claude Code, "
                                           "copilot for GitHub Copilot) or plan file")
    sp.add_argument("event", nargs="?", help="with `hook copilot`: the Copilot hook event "
                                             "(sessionStart, userPromptSubmitted, preToolUse, "
                                             "postToolUse, postToolUseFailure, agentStop)")
    sp.add_argument("--copilot", action="store_true",
                    help="init: configure for GitHub Copilot hooks (CLI and cloud agent) and "
                         "write .github/hooks/skillc.json instead of Claude Code hooks")
    sp.add_argument("--root", default=".", help="project directory (default: .)")
    sp.add_argument("--runtime", default="developer-sandbox",
                    help="init: runtime manifest name or JSON path")
    sp.add_argument("--thinking", choices=("stop", "warn", "off"), default="stop",
                    help="init: what reasoning that heads to the impossible does")
    sp.set_defaults(fn=cmd_monitor)

    sp = sub.add_parser("env", help="environment topology: probe, show, diff, merge, watch "
                                    "(docs/ENVIRONMENT.md)")
    env_sub = sp.add_subparsers(dest="action", required=True)
    e = env_sub.add_parser("probe", help="read the environment (Azure, MCP) into skillc.env/1")
    _add_probe_opts(e)
    e.add_argument("-o", "--output", default=".skillc/env/latest.json")
    e = env_sub.add_parser("show", help="summarise an environment file")
    e.add_argument("file")
    e.add_argument("--html", metavar="FILE", help="also write the topology as a page")
    e = env_sub.add_parser("diff", help="what changed between two snapshots")
    e.add_argument("old")
    e.add_argument("new")
    e = env_sub.add_parser("merge", help="combine environment files (e.g. Azure + MCP)")
    e.add_argument("files", nargs="+")
    e.add_argument("-o", "--output", required=True)
    e = env_sub.add_parser("from-azd", help="the environment an azd project declares in its "
                                            "azure.yaml (offline; every fact is declared)")
    e.add_argument("azure_yaml", metavar="AZURE_YAML")
    e.add_argument("-o", "--output", help="write the skillc.env/1 document here")
    e.add_argument("--json", action="store_true", help="print the document to stdout")
    e = env_sub.add_parser("watch", help="re-probe on a schedule; report what changed")
    _add_probe_opts(e)
    e.add_argument("--dir", default=".skillc/env", help="where snapshots are kept")
    e.add_argument("--intent", action="append", metavar="FILE|NAME",
                   help="intent to re-check after every probe; repeatable")
    e.add_argument("--interval", type=float, default=3600.0, help="seconds between probes")
    e.add_argument("--once", action="store_true", help="one round, then exit (cron, CI)")
    sp.set_defaults(fn=cmd_env)

    sp = sub.add_parser("reach", help="what an intent can achieve in an environment, "
                                      "and what blocks the rest")
    sp.add_argument("intent", help="skillc.intent/1 file, a built-in intent name, "
                                   "or a SKILL.md / agent.md")
    sp.add_argument("--env", help="skillc.env/1 file (from `skillc env probe`)")
    sp.add_argument("--save-env", metavar="FILE", help="with --claude: keep the probe")
    _add_claude_opts(sp)
    sp.add_argument("--catalog", help="operation catalogue name or skillc.ops/1 file")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--plan", metavar="FILE", help="write the English + CE plan (Markdown)")
    sp.add_argument("--html", metavar="FILE", help="write the visual report")
    sp.set_defaults(fn=cmd_reach)

    sp = sub.add_parser("intent", help="what a SKILL.md / agent.md needs from its runtime "
                                       "(natural-language front-end)")
    sp.add_argument("file", help="SKILL.md or agent.md")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("-o", "--output", help="write the skillc.intent/1 JSON here")
    sp.set_defaults(fn=cmd_intent)

    try:
        from .gate import add_parser as _add_gate_parser
        _add_gate_parser(sub)              # `skillc gate`: the deploy gate (docs/ENVIRONMENT.md)
    except ImportError:
        pass

    sp = sub.add_parser("profiles", help="list built-in capability profiles")
    sp.set_defaults(fn=cmd_profiles)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except (PackError, CEError, KeyError, FileNotFoundError,
            json.JSONDecodeError, RuntimeError, ValueError) as e:
        print(f"skillc: error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
