#!/usr/bin/env python3
"""Severity evaluation for the WIP paper.

  (i)   tolerance degrees and severity counts over: the achievability corpus,
        its extension, the real-skill packs (deterministic front-end), and the
        purpose-built severity benchmark;
  (ii)  the MODULARITY experiment: sequential chains of benchmark protocols,
        whole-system exploration vs modular (interface-memoized) checking, and
        the cost of RE-CHECKING after the last segment changes.

Writes paper/WIP/results/severity.json and docs/SEVERITY_RESULTS.md.
"""
from __future__ import annotations
import copy, glob, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from skillc.severity import SeverityAnalyzer, analyze, BENIGN, FUTILE, CATASTROPHIC
from skillc.pack import Pack
from skillc.checker import initial_state, _mk_state

DATA = ROOT / "src" / "skillc" / "data"
OUT = ROOT / "paper" / "WIP" / "results"
OUT.mkdir(parents=True, exist_ok=True)
KMAX = 4


def load_corpora():
    sets = {}
    sets["corpus"] = [(e["id"], e["pack"]) for e in json.load(open(DATA / "corpus.json"))]
    sets["corpus_extended"] = [(e["id"], e["pack"]) for e in json.load(open(DATA / "corpus_extended.json"))]
    sets["severity_benchmark"] = [(e["id"], e["pack"]) for e in json.load(open(DATA / "severity_corpus.json"))]
    real = []
    try:
        from skillc.profiles import load_profile
        from skillc.frontend.markdown import compile_file
        prof = load_profile("claude-ai")
        for f in sorted(glob.glob(str(ROOT / "real-skills" / "**" / "SKILL.md"), recursive=True)):
            try:
                real.append((f.split("/")[-2], compile_file(f, prof).pack))
            except Exception as ex:  # noqa
                real.append((f.split("/")[-2] + " (compile error)", None))
    except Exception:
        pass
    sets["real_skills"] = real
    return sets


def structure(pack: dict) -> dict:
    caps = pack.get("capabilities", {})
    choices = 0; ext = 0; recs = 0
    def walk(steps):
        nonlocal choices, ext, recs
        for s in steps:
            if "choice" in s:
                choices += 1
                if s["choice"].get("external"): ext += 1
                for br in s["choice"]["branches"].values(): walk(br)
            if "rec" in s:
                recs += 1; walk(s["rec"]["body"])
    walk(pack.get("protocol", []))
    adds = set(a for c in caps.values() for a in c.get("add", []))
    perm = [n for n, c in caps.items() if any(d not in adds for d in c.get("del", []))]
    return {"caps": len(caps), "choices": choices, "external_choices": ext, "loops": recs,
            "delete_caps": sum(1 for c in caps.values() if c.get("del")),
            "irreversible_caps": sorted(set(perm) | set(pack.get("irreversible", [])))}


def run_sets(sets):
    rows = []
    for name, items in sets.items():
        for pid, pack in items:
            if pack is None:
                rows.append({"set": name, "id": pid, "error": "compile"}); continue
            st = structure(pack)
            try:
                r = analyze(pack, kmax=KMAX)
                d = r.to_dict()
                rows.append({"set": name, "id": pid, **st,
                             "k_star": d["tolerance_degree"], "kmax": KMAX,
                             "counts": d["counts"], "branches": d["branches"],
                             "choice_nodes": d["choice_nodes"], "pnr_action": d["pnr_action"],
                             "witness": d["hazard_witness"], "narrowing": d["narrowing"],
                             "configs": d["configs_explored"], "goal_queries": d["goal_queries"],
                             "elapsed_s": d["elapsed_s"]})
            except Exception as ex:
                rows.append({"set": name, "id": pid, **st, "error": f"{type(ex).__name__}: {ex}"})
    return rows


# ----------------------------------------------------------------------------
# Modularity experiment
# ----------------------------------------------------------------------------

def rename_pack(pack: dict, tag: str) -> dict:
    """Rename atoms, capabilities and labels so segments do not interact."""
    p = copy.deepcopy(pack)
    def rn(x): return f"{x}_{tag}"
    def rf(f):
        if isinstance(f, str): return rn(f)
        if isinstance(f, dict):
            return {k: ([rf(x) for x in v] if isinstance(v, list) else rf(v)) for k, v in f.items()}
        return f
    caps = {}
    for n, c in p["capabilities"].items():
        c2 = dict(c)
        c2["add"] = [rn(a) for a in c.get("add", [])]
        c2["del"] = [rn(a) for a in c.get("del", [])]
        if "pre" in c2 and c2["pre"] is not True: c2["pre"] = rf(c2["pre"])
        caps[rn(n)] = c2
    p["capabilities"] = caps
    def ws(steps):
        out = []
        for s in steps:
            s = copy.deepcopy(s)
            if "act" in s: s["act"]["cap"] = rn(s["act"]["cap"])
            if "goal" in s: s["goal"] = rf(s["goal"])
            if "choice" in s:
                s["choice"]["branches"] = {k: ws(v) for k, v in s["choice"]["branches"].items()}
                if "guards" in s["choice"]:
                    s["choice"]["guards"] = {k: rf(v) for k, v in s["choice"]["guards"].items()}
            if "rec" in s:
                s["rec"]["name"] = rn(s["rec"]["name"]); s["rec"]["body"] = ws(s["rec"]["body"])
            if "continue" in s: s["continue"] = rn(s["continue"])
            out.append(s)
        return out
    p["protocol"] = ws(p["protocol"])
    p["goal"] = rf(p["goal"])
    p["init_true"] = [rn(a) for a in p.get("init_true", [])]
    p["irreversible"] = [rn(a) for a in p.get("irreversible", [])]
    return p


def compose(packs: list[dict]) -> dict:
    """Sequential composition G1;G2;...;Gn of renamed packs (goal = conjunction)."""
    segs = [rename_pack(p, f"s{i}") for i, p in enumerate(packs)]
    out = {"name": "chain", "roles": sorted({r for s in segs for r in s["roles"]}),
           "capabilities": {}, "protocol": [], "init_true": [], "irreversible": []}
    goals = []
    for s in segs:
        out["capabilities"].update(s["capabilities"])
        out["protocol"] += s["protocol"]
        out["init_true"] += s.get("init_true", [])
        out["irreversible"] += s.get("irreversible", [])
        goals.append(s["goal"])
    out["goal"] = {"and": goals}
    return out, segs


def whole_system(chain: dict, k: int):
    """Naive whole-system exploration of the composed protocol (no interface memo)."""
    a = SeverityAnalyzer(Pack.load({x: v for x, v in chain.items() if x != "irreversible"}),
                         kmax=k, irreversible=chain.get("irreversible"))
    t0 = time.perf_counter()
    found, wit, pnr = a.hazard_within(list(a.p.protocol), initial_state(a.p), {}, k, set(), record=False)
    return {"hazard": found, "configs": a.configs, "goal_queries": a.goal_queries,
            "time_s": time.perf_counter() - t0}


def seg_analyzer(seg: dict, k: int) -> SeverityAnalyzer:
    return SeverityAnalyzer(Pack.load({x: v for x, v in seg.items() if x != "irreversible"}),
                            kmax=k, irreversible=seg.get("irreversible"))


def atoms_of(x) -> set:
    """all predicate atoms mentioned in a formula / step list / pack fragment"""
    out = set()
    if isinstance(x, str): out.add(x)
    elif isinstance(x, dict):
        for k2, v in x.items():
            if k2 in ("cmp",): continue
            out |= atoms_of(v)
    elif isinstance(x, list):
        for v in x: out |= atoms_of(v)
    return out


def relevant_atoms(segs: list[dict]) -> set:
    """cone of influence: atoms the given segments READ (guards, goals,
    choice guards) or WRITE.  Exit worlds are projected onto this set."""
    rel = set()
    for s in segs:
        for c in s["capabilities"].values():
            rel |= atoms_of(c.get("pre", True)) | set(c.get("add", [])) | set(c.get("del", []))
        rel |= atoms_of(s["goal"]) | atoms_of(s["protocol"]) | set(s.get("init_true", []))
    return rel


def whole_system_complete(chain: dict, k: int):
    """Whole-system COMPLETE enumeration of hazard-free terminations (like-for-
    like with the modular interface computation; no short-circuit)."""
    a = SeverityAnalyzer(Pack.load({x: v for x, v in chain.items() if x != "irreversible"}),
                         kmax=k, irreversible=chain.get("irreversible"))
    t0 = time.perf_counter()
    ex, h = a.exits(list(a.p.protocol), initial_state(a.p), {}, k)
    return {"hazard": h, "configs": a.configs, "goal_queries": a.goal_queries,
            "time_s": time.perf_counter() - t0, "exits": len(ex)}


def modular(segs: list[dict], k: int, start_frontier=None, project: bool = False):
    """TC_seq_interface: segment i is typed -- against ITS OWN goal -- only at
    the exit interface of segment i-1, the set of distinct
    (true-predicates, budget-left) pairs at which i-1 can end."""
    t0 = time.perf_counter()
    a0 = seg_analyzer(segs[0], k)
    frontier = start_frontier or {(initial_state(a0.p).true_preds, k)}
    per_seg = []; hazard = False; configs = 0; gq = 0
    for i, seg in enumerate(segs):
        a = seg_analyzer(seg, k)
        nxt = set()
        for preds, b in frontier:
            # the incoming world carries the previous segments' atoms; the
            # segment's own init atoms are added (disjoint by renaming)
            st = _mk_state(preds | frozenset(seg.get("init_true", [])), (), {}, ())
            ex, h = a.exits(list(seg["protocol"]), st, {}, b)
            hazard = hazard or h
            nxt |= ex
        per_seg.append({"interface_in": len(frontier), "configs": a.configs, "goal_queries": a.goal_queries})
        configs += a.configs; gq += a.goal_queries
        if project:
            # TC_seq_interface with I = exits projected onto the cone of
            # influence of the REMAINING segments (sound: later segments never
            # read the dropped atoms, so their behaviour is unchanged)
            rel = relevant_atoms(segs[i + 1:])
            nxt = {(frozenset(p & rel), b) for p, b in nxt}
        frontier = nxt
    return {"hazard": hazard, "configs": configs, "goal_queries": gq,
            "time_s": time.perf_counter() - t0, "per_segment": per_seg,
            "final_interface": len(frontier), "frontier": frontier}


def modularity_experiment(bench: dict[str, dict], k: int = 2, max_n: int = 6):
    """Chains G;G;...;G of a benchmark segment.  Whole-system: one exploration
    of the composed protocol against the conjunctive goal (goal reachability
    re-derived over the entire remaining chain at every branch).  Modular:
    each segment against its own goal at the incoming interface (TC_seq).
    Re-check: the LAST segment is replaced by its unsafe variant; whole-system
    must re-run from the start, modular re-checks the last segment only."""
    rows = []
    for family, safe_id, unsafe_id in (("deploy", "deploy_with_rollback", "deploy_no_rollback"),
                                        ("migration", "migration_backup", "migration_backup")):
        base = bench[safe_id]; alt = bench[unsafe_id]
        for n in range(1, max_n + 1):
            chain, segs = compose([base] * n)
            ws = whole_system(chain, k)
            wc = whole_system_complete(chain, k)
            md = modular(segs, k)
            mp = modular(segs, k, project=True)
            chain2, segs2 = compose([base] * (n - 1) + [alt])
            ws2 = whole_system(chain2, k)
            # modular re-check: prefix frontier is already known; only the last
            # segment is re-analysed
            prefix = modular(segs2[:-1], k, project=True) if n > 1 else None
            fr = prefix["frontier"] if prefix else None
            t0 = time.perf_counter()
            rm = modular([segs2[-1]], k, start_frontier=fr)
            rm_time = time.perf_counter() - t0
            rows.append({"family": family, "n": n, "k": k,
                         "whole_system": {x: ws[x] for x in ("hazard", "configs", "goal_queries", "time_s")},
                         "whole_system_complete": {x: wc[x] for x in ("hazard", "configs", "goal_queries", "time_s", "exits")},
                         "modular": {x: md[x] for x in ("hazard", "configs", "goal_queries", "time_s", "final_interface")},
                         "modular_projected": {x: mp[x] for x in ("hazard", "configs", "goal_queries", "time_s", "final_interface")},
                         "recheck_whole_system": {x: ws2[x] for x in ("hazard", "configs", "goal_queries", "time_s")},
                         "recheck_modular": {"hazard": rm["hazard"], "configs": rm["configs"],
                                             "goal_queries": rm["goal_queries"], "time_s": rm_time,
                                             "interface": len(fr) if fr else 1}})
            print(f"{family} n={n}: whole-hazard {ws['time_s']*1000:7.1f}ms | whole-complete gq={wc['goal_queries']:5d} {wc['time_s']*1000:8.1f}ms exits={wc['exits']:4d} | modular-concrete gq={md['goal_queries']:5d} {md['time_s']*1000:8.1f}ms iface={md['final_interface']:4d} | modular-projected gq={mp['goal_queries']:4d} {mp['time_s']*1000:7.1f}ms iface={mp['final_interface']} | recheck whole {ws2['time_s']*1000:7.1f}ms modular {rm_time*1000:6.1f}ms", flush=True)
    return rows


def md_table(rows):
    out = ["| set | pack | choices | loops | irreversible | k* | Benign | Futile | Catastrophic | PNR action | configs | ms |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            out.append(f"| {r['set']} | {r['id']} | – | – | – | error: {r['error']} | | | | | | |"); continue
        ks = "≥5" if r["k_star"] is None else str(r["k_star"])
        c = r["counts"]
        out.append(f"| {r['set']} | {r['id']} | {r['choices']} | {r['loops']} | {', '.join(r['irreversible_caps']) or '–'} | {ks} | {c['Benign']} | {c['Futile']} | {c['Catastrophic']} | {r['pnr_action'] or '–'} | {r['configs']} | {r['elapsed_s']*1000:.1f} |")
    return "\n".join(out)


def main():
    sets = load_corpora()
    rows = run_sets(sets)
    bench = {e["id"]: e["pack"] for e in json.load(open(DATA / "severity_corpus.json"))}
    print("== modularity experiment ==")
    mod = modularity_experiment(bench, k=2, max_n=6)
    json.dump({"kmax": KMAX, "rows": rows, "modularity": mod}, open(OUT / "severity.json", "w"), indent=1)

    # summary
    def summ(name):
        rs = [r for r in rows if r["set"] == name and "error" not in r]
        withc = [r for r in rs if r["choices"] > 0]
        irr = [r for r in rs if r["irreversible_caps"]]
        dist = {}
        for r in rs:
            key = "≥5" if r["k_star"] is None else str(r["k_star"])
            dist[key] = dist.get(key, 0) + 1
        return {"packs": len(rs), "with_choices": len(withc), "with_irreversible": len(irr), "k_star_dist": dist}
    summary = {s: summ(s) for s in sets}
    lines = ["# Severity evaluation results", "",
             f"kmax tested = {KMAX} (k* = ≥5 means no hazard within 4 misselections).", "",
             "## Summary per corpus", "", "| corpus | packs | with choices | with irreversible tools | k* distribution |", "|---|---|---|---|---|"]
    for s, v in summary.items():
        lines.append(f"| {s} | {v['packs']} | {v['with_choices']} | {v['with_irreversible']} | {v['k_star_dist']} |")
    lines += ["", "## Per-pack results", "", md_table(rows), "",
              "## Modularity experiment (k=2). Chains G;...;G of a benchmark segment. Whole-system re-derives goal reachability over the entire remaining chain at every branch; modular types each segment against its own goal at the incoming interface (TC_seq). Re-check: last segment replaced by its unsafe variant.", "",
              "| family | n | whole (hazard, short-circuit) ms | whole (complete) ms | whole exits | modular concrete ms | concrete interface | modular projected ms | projected interface | re-check whole ms | re-check modular ms |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in mod:
        lines.append(f"| {m['family']} | {m['n']} | {m['whole_system']['time_s']*1000:.1f} | {m['whole_system_complete']['time_s']*1000:.1f} | {m['whole_system_complete']['exits']} | {m['modular']['time_s']*1000:.1f} | {m['modular']['final_interface']} | {m['modular_projected']['time_s']*1000:.1f} | {m['modular_projected']['final_interface']} | {m['recheck_whole_system']['time_s']*1000:.1f} | {m['recheck_modular']['time_s']*1000:.1f} |")
    (ROOT / "docs" / "SEVERITY_RESULTS.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=1))
    print("wrote", OUT / "severity.json", "and docs/SEVERITY_RESULTS.md")


if __name__ == "__main__":
    main()
