"""Bridge to the VERIFIED KERNEL (paper/WIP/proof/Kernel.v, extracted to OCaml).

The kernel decides budgeted hazard reachability for the boolean fragment of
the pack language -- propositional preconditions/effects and goal, agent
choices with explicit or rational guards, named recursion -- with the
Coq-verified decision procedure `decide_mu` (Mu.v) run on the elaborated
protocol.  The elaboration (this exporter plus `elab` in Kernel.v) is the
trusted front end; the reachability decision is the verified part.

Export format (S-expression):
  (pack (atoms N) (caps ((pre F) (add i j) (del k)) ...) (goal F)
        (init i j ...) (kmax K) (proto RAW))
  F   ::= true | (atom i) | (and F F) | (or F F) | (not F)
  RAW ::= end | (act cap irr role RAW) | (choice p q ((label G RAW) ...))
        | (mu RAW) | (var i)              G ::= none | F
"""
from __future__ import annotations
import os, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KERNEL_BIN = ROOT / "paper" / "WIP" / "proof" / "kernel" / "skillc_kernel"


class NotBoolean(Exception):
    pass


def _f(f, atoms) -> str:
    if f is True or f is None:
        return "true"
    if isinstance(f, str):
        return f"(atom {atoms[f]})"
    if isinstance(f, dict) and len(f) == 1:
        (k, v), = f.items()
        if k == "and":
            out = "true"
            for x in reversed(v):
                out = f"(and {_f(x, atoms)} {out})"
            return out
        if k == "or":
            out = "(not true)"
            for x in reversed(v):
                out = f"(or {_f(x, atoms)} {out})"
            return out
        if k == "not":
            return f"(not {_f(v, atoms)})"
    raise NotBoolean(f"non-boolean formula {f!r}")


def _collect_atoms(pack: dict) -> list[str]:
    atoms: list[str] = []

    def add(x):
        if x not in atoms:
            atoms.append(x)

    def walk(f):
        if isinstance(f, str):
            add(f)
        elif isinstance(f, dict):
            for v in f.values():
                walk(v)
        elif isinstance(f, list):
            for x in f:
                walk(x)

    for a in pack.get("init_true", []) or []:
        add(a)
    for c in pack["capabilities"].values():
        if c.get("asg") or c.get("nd") or c.get("assigns") or c.get("nondet"):
            raise NotBoolean("arithmetic effect")
        walk(c.get("pre"))
        for a in c.get("add", []) or []:
            add(a)
        for a in c.get("del", []) or []:
            add(a)
    walk(pack["goal"])

    def walk_steps(steps):
        for s in steps:
            if "choice" in s:
                for g in (s["choice"].get("guards") or {}).values():
                    walk(g)
                for br in s["choice"]["branches"].values():
                    walk_steps(br)
            elif "rec" in s:
                walk_steps(s["rec"]["body"])
    walk_steps(pack["protocol"])
    return atoms


def to_sexpr(pack: dict, kmax: int = 4, irreversible=None) -> str:
    """Raise NotBoolean if the pack is outside the kernel's fragment."""
    from .severity import permanent_deletes
    from .pack import Pack
    p = Pack.load({k: v for k, v in pack.items() if k != "irreversible"})
    perm = set(permanent_deletes(p)) | set(irreversible or pack.get("irreversible") or [])
    atoms = _collect_atoms(pack)
    idx = {a: i for i, a in enumerate(atoms)}
    caps = list(pack["capabilities"].keys())
    cidx = {c: i for i, c in enumerate(caps)}
    roles = {r: i for i, r in enumerate(pack["roles"])}
    labels: dict[str, int] = {}

    def lab(l):
        if l not in labels:
            labels[l] = len(labels)
        return labels[l]

    def tree(steps, binders):
        if not steps:
            return "end"
        s, rest = steps[0], steps[1:]
        if "act" in s:
            cap = s["act"]["cap"]
            if cap not in cidx:
                raise NotBoolean(f"undeclared capability {cap}")
            owner = pack["capabilities"][cap].get("owner", pack["roles"][0])
            irr = "1" if cap in perm else "0"
            return f"(act {cidx[cap]} {irr} {roles[owner]} {tree(rest, binders)})"
        if "msg" in s:
            return tree(rest, binders)
        if "choice" in s:
            b = s["choice"]
            if b.get("external"):
                raise NotBoolean("environment choice")
            guards = b.get("guards") or {}
            brs = []
            for l, br in b["branches"].items():
                g = "none" if l not in guards else _f(guards[l], idx)
                brs.append(f"({lab(l)} {g} {tree(list(br) + rest, binders)})")
            q = b.get("to", b["by"])
            return f"(choice {roles[b['by']]} {roles.get(q, roles[b['by']])} ({' '.join(brs)}))"
        if "rec" in s:
            name = s["rec"]["name"]
            return f"(mu {tree(list(s['rec']['body']) + rest, [name] + binders)})"
        if "continue" in s:
            return f"(var {binders.index(s['continue'])})"
        raise NotBoolean(f"unsupported step {list(s)[0]}")

    caps_s = " ".join(
        f"((pre {_f(c.get('pre'), idx)}) (add {' '.join(str(idx[a]) for a in c.get('add', []) or [])})"
        f" (del {' '.join(str(idx[a]) for a in c.get('del', []) or [])}))"
        for c in pack["capabilities"].values())
    init = " ".join(str(idx[a]) for a in pack.get("init_true", []) or [])
    return (f"(pack (atoms {len(atoms)}) (caps {caps_s}) (goal {_f(pack['goal'], idx)}) "
            f"(init {init}) (kmax {kmax}) (proto {tree(list(pack['protocol']), [])}))")


def kernel_available() -> bool:
    return KERNEL_BIN.exists() and os.access(KERNEL_BIN, os.X_OK)


def run_kernel(pack: dict, kmax: int = 4, irreversible=None) -> dict:
    """Returns {'first_hazard': k|None, 'tolerance_degree': k-1|None} or {'skipped': reason}."""
    try:
        sx = to_sexpr(pack, kmax, irreversible)
    except NotBoolean as e:
        return {"skipped": str(e)}
    if not kernel_available():
        return {"skipped": "kernel binary not built"}
    r = subprocess.run([str(KERNEL_BIN)], input=sx, capture_output=True, text=True, timeout=600)
    out = r.stdout.strip()
    if r.returncode != 0 or not out:
        return {"skipped": f"kernel error: {r.stderr.strip()[:200]}"}
    if out == "none":
        return {"first_hazard": None, "tolerance_degree": None}
    k = int(out.split()[-1])
    return {"first_hazard": k, "tolerance_degree": k - 1}
