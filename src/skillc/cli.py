"""skillc command-line interface.

  skillc compile SKILL.md [--profile P] [-o pack.json]   markdown -> pack
  skillc check   FILE     [--profile P] [--json]         pack.json or SKILL.md -> verdict
  skillc scan    DIR      [--profile P] [--json|--md]    batch-check a skill tree
  skillc audit   PATH     [--json]                       bundle security pre-pass
  skillc cost    FILE|DIR [--llm] [--json]                token economics of checking
  skillc eval                                            corpus evaluation
  skillc profiles                                        list capability profiles

Exit codes: 0 achievable / all pass, 1 impossible / soundness violation,
2 usage or input error, 3 unknown (an abstention: outside the decidable
fragment, never a refutation).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from . import __version__
from .checker import check
from .evaluate import evaluate, format_report, load_corpus
from .frontend.markdown import CompileResult, compile_file
from .pack import Pack, PackError
from .profiles import builtin_profiles, load_profile


def _load_result(path: Path, args) -> tuple[dict, CompileResult | None]:
    """Return (pack, compile_result_or_None) for a .json pack or markdown."""
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8")), None
    profile = load_profile(args.profile)
    if getattr(args, "tool", None):
        profile = profile.with_tools(args.tool)
    if getattr(args, "llm", False):
        from .frontend.llm import RUNTIME_ABILITY_PROFILES, compact
        abilities = list(RUNTIME_ABILITY_PROFILES[args.llm_runtime])
        abilities.extend(args.runtime_ability or [])
        pack = compact(path.read_text(encoding="utf-8"), model=args.model,
                       provider=args.llm_provider,
                       runtime_abilities=abilities or None)
        return pack, None
    res = compile_file(path, profile)
    return res.pack, res


def cmd_compile(args) -> int:
    pack, res = _load_result(Path(args.file), args)
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
    pack, res = _load_result(Path(args.file), args)
    v = check(pack, semantics="adversarial" if args.adversarial else "may")
    if args.json:
        out = v.to_dict()
        out["pack_name"] = pack.get("name", "?")
        print(json.dumps(out, indent=2))
    else:
        print(f"{pack.get('name', '?')}: {v.label}"
              + (f" [{v.reason}]" if not v.achievable else ""))
        if v.detail and not v.achievable:
            print(f"  {v.detail}")
        if v.unknown:
            print("  UNKNOWN is not a refutation: the pack falls outside the "
                  "decidable fragment, so no claim is made either way.")
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
            pack, _ = _load_result(f, args)
            v = check(pack)
            rows.append({"skill": rel.as_posix(), "verdict": v.label,
                         "reason": v.reason if not v.achievable else "",
                         "frontier": list(v.frontier),
                         "unknown": v.unknown, "refuted": v.refuted})
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
              f"(outside the decidable fragment -- not refutations)")
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
    from .tokens import (CorpusEconomics, RuntimeModel, check_cost, economics,
                         estimate_tokens)

    # Two independent questions, two flags: --llm actually compacts with the
    # model (and then prices what it really used); --price-llm prices what
    # the LLM front-end *would* cost without spending a token on it.
    priced_llm = args.llm or args.price_llm

    sources: list[tuple[str, str, dict]] = []      # (name, source text, pack)
    if args.corpus:
        for spec in load_corpus():
            # `nl` is the spec's natural-language source: the actual
            # input a compaction front-end would be billed for.
            sources.append((spec["id"], spec.get("nl", ""), spec["pack"]))
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
                pack, _ = _load_result(f, args)
            except (PackError, ValueError) as e:
                print(f"skillc: {f}: {type(e).__name__}: {e}", file=sys.stderr)
                continue
            sources.append((pack.get("name", f.stem), text, pack))

    model = RuntimeModel(cache_hit_rate=args.cache_hit_rate)
    corpus = CorpusEconomics(price=args.price)
    achievable: list[tuple[str, int, int]] = []
    for name, text, pack in sources:
        try:
            v = check(pack)
        except (PackError, ValueError) as e:
            print(f"skillc: {name}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        ver = check_cost(text or json.dumps(pack), llm=priced_llm,
                         repair_rounds=args.repair_rounds)
        src = text or json.dumps(pack)
        if v.refuted and v.reason in _WASTE_REASONS:
            corpus.rows.append(economics(
                src, v.reason, name=name, model=model,
                verification=ver, price=args.price))
        else:
            run = replace(model, skill_tokens=estimate_tokens(src)).run_cost(
                _SUCCESS_TURNS)
            achievable.append((name, ver.total_tokens, run.total_tokens))

    if args.json:
        out = corpus.to_dict()
        out["not_refuted"] = [
            {"skill": n, "verification_tokens": vt,
             "successful_run_tokens": rt,
             "verification_share_of_one_run": round(vt / rt, 6) if rt else 0.0}
            for n, vt, rt in achievable]
        print(json.dumps(out, indent=2))
        return 0

    front = ("LLM compaction (measured)" if args.llm else
             "LLM compaction (modelled)" if args.price_llm else
             "deterministic front-end")
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
    sp.set_defaults(fn=cmd_compile)

    sp = sub.add_parser("check", help="decide achievability of a pack or SKILL.md")
    sp.add_argument("file")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("-v", "--verbose", action="store_true")
    sp.add_argument("--adversarial", action="store_true",
                    help="require the goal under EVERY resolution of choices "
                         "marked external (must-achievability)")
    _add_compile_opts(sp)
    sp.set_defaults(fn=cmd_check)

    sp = sub.add_parser("scan", help="batch-check every skill under a directory")
    sp.add_argument("dir")
    sp.add_argument("--glob", default="SKILL.md")
    sp.add_argument("--json", action="store_true")
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
                    help="LLM compaction repair rounds to price in (--llm)")
    sp.add_argument("--cache-hit-rate", type=float, default=0.0, metavar="R",
                    help="fraction of the re-read runtime prefix served from "
                         "cache; changes dollars, never token counts")
    _add_compile_opts(sp)
    sp.set_defaults(fn=cmd_cost)

    sp = sub.add_parser("eval", help="run the corpus evaluation")
    sp.set_defaults(fn=cmd_eval)

    sp = sub.add_parser("profiles", help="list built-in capability profiles")
    sp.set_defaults(fn=cmd_profiles)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except (PackError, KeyError, FileNotFoundError, json.JSONDecodeError,
            RuntimeError) as e:
        print(f"skillc: error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
