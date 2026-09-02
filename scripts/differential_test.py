#!/usr/bin/env python3
"""Differential test: the tool's analyzer against the Coq-extracted kernel.

`Kernel.v` instantiates the mechanized decision procedure (`decide_mu`) on the
boolean fragment and is proved correct; `src/skillc/severity.py` is the
hand-written analyzer the tool actually runs. They share no code. Random
protocols in the shared fragment therefore test what no hand-picked benchmark
can: whether the implementation computes the tolerance degree its own
mechanized theory defines.

Generated packs stay inside the kernel's fragment (propositional
preconditions and effects, agent choices with explicit or rational guards,
named recursion, no environment choice, no arithmetic) and are otherwise
unconstrained: nested choices, loops, irreversible tools, unreachable goals.
Any disagreement is written to paper/WIP/results/differential_failures.json
with the pack that produced it.
"""
from __future__ import annotations
import argparse, json, random, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from skillc.severity import analyze
from skillc.kernel import run_kernel, kernel_available

OUT = ROOT / "paper" / "WIP" / "results"


def gen_pack(rng: random.Random, idx: int) -> dict:
    n_atoms = rng.randint(2, 5)
    atoms = [f"p{i}" for i in range(n_atoms)]
    n_caps = rng.randint(2, 5)
    caps = {}
    for i in range(n_caps):
        add = rng.sample(atoms, rng.randint(0, min(2, n_atoms)))
        rest = [a for a in atoms if a not in add]
        dele = rng.sample(rest, rng.randint(0, min(1, len(rest))))
        c = {"owner": "agent"}
        if add:
            c["add"] = add
        if dele:
            c["del"] = dele
        if rng.random() < 0.35:
            c["pre"] = rng.choice(atoms)
        caps[f"t{i}"] = c
    names = list(caps)

    def act():
        return {"act": {"cap": rng.choice(names), "by": "agent"}}

    loop_id = [0]

    def steps(depth: int, in_loop: bool) -> list:
        out = []
        for _ in range(rng.randint(1, 3)):
            r = rng.random()
            if r < 0.55 or depth >= 2:
                out.append(act())
            elif r < 0.9:
                k = rng.randint(2, 3)
                branches = {f"b{j}": steps(depth + 1, in_loop) for j in range(k)}
                ch = {"by": "agent", "branches": branches}
                if rng.random() < 0.4:
                    ch["guards"] = {l: rng.choice(atoms) if rng.random() < 0.7
                                    else {"not": rng.choice(atoms)} for l in branches}
                out.append({"choice": ch})
            elif not in_loop and depth == 0 and loop_id[0] == 0:
                loop_id[0] += 1
                name = "L"
                body = steps(depth + 1, True)
                if rng.random() < 0.6:
                    body.append({"choice": {"by": "agent", "branches": {
                        "again": [{"continue": name}], "stop": [act()]}}})
                out.append({"rec": {"name": name, "body": body}})
            else:
                out.append(act())
        return out

    goal_atoms = rng.sample(atoms, rng.randint(1, min(3, n_atoms)))
    goal = goal_atoms[0] if len(goal_atoms) == 1 else {"and": goal_atoms}
    pack = {"name": f"rand{idx}", "roles": ["agent"], "capabilities": caps,
            "protocol": steps(0, False), "goal": goal,
            "init_true": rng.sample(atoms, rng.randint(0, 2))}
    if rng.random() < 0.5:
        pack["irreversible"] = rng.sample(names, rng.randint(1, min(2, len(names))))
    return pack


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20260902)
    ap.add_argument("--kmax", type=int, default=3)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    if not kernel_available():
        print("kernel binary not built: run `make binary` in paper/WIP/proof", file=sys.stderr)
        return 2
    rng = random.Random(args.seed)
    agree = disagree = skipped = 0
    fails, t0 = [], time.time()
    for i in range(args.n):
        pack = gen_pack(rng, i)
        try:
            a = analyze(pack, kmax=args.kmax).tolerance_degree
        except Exception as e:                                     # noqa: BLE001
            fails.append({"kind": "analyzer-crash", "error": str(e)[:200], "pack": pack}); continue
        k = run_kernel(pack, kmax=args.kmax)
        if "skipped" in k:
            skipped += 1
            continue
        if k["tolerance_degree"] == a:
            agree += 1
        else:
            disagree += 1
            fails.append({"kind": "disagreement", "analyzer": a, "kernel": k["tolerance_degree"], "pack": pack})
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"generated": args.n, "compared": agree + disagree, "agree": agree, "disagree": disagree,
           "outside_fragment": skipped, "kmax": args.kmax, "seed": args.seed,
           "seconds": round(time.time() - t0, 1), "failures": fails[:20]}
    prev = json.load(open(OUT / "differential.json")) if (OUT / "differential.json").exists() else {}
    pc = prev.get("cumulative", {})
    res["cumulative"] = {
        "compared": res["compared"] + pc.get("compared", prev.get("compared", 0)),
        "agree": res["agree"] + pc.get("agree", prev.get("agree", 0)),
        "disagree": res["disagree"] + pc.get("disagree", prev.get("disagree", 0)),
        "runs": pc.get("runs", ([{"n": prev["generated"], "kmax": prev["kmax"], "seed": prev["seed"],
                                  "agree": prev["agree"], "disagree": prev["disagree"]}] if prev else []))
                + [{"n": args.n, "kmax": args.kmax, "seed": args.seed,
                    "agree": res["agree"], "disagree": res["disagree"]}]}
    json.dump(res, open(OUT / "differential.json", "w"), indent=1)
    if fails:
        json.dump(fails, open(OUT / "differential_failures.json", "w"), indent=1)
    if not args.quiet:
        print(json.dumps({k: v for k, v in res.items() if k != "failures"}, indent=1))
        for f in fails[:3]:
            print("FAILURE:", json.dumps(f)[:600])
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
