"""Small-model arms with more data, amendment C (runs/20260928_div/slm/PLAN_C.md).

Gold rows (report-grounded, rows.jsonl) are the only evaluation data. Silver rows
(document-only labels, silver_rows.jsonl) are added to training, with a leakage filter.
In each fold, silver rows are dropped when their term (unseen_terms) or organisation (org5)
belongs to the test fold.

Arms:
  A0   lexical TF-IDF + LR (class-balanced), gold only
  A1   A0 + silver
  B1g  SetFit-style: SupCon fine-tuning of distilroberta-base on gold, then LR heads on the
       tuned embeddings: cls unweighted + post-hoc logit adjustment (tau = 1), core balanced
  B1   B1g on gold + silver
  B2   B1 + neologism: one <t:term> token per training term, initialised to the mean of the
       term's subword embeddings and trained with the encoder; unseen terms keep their spelling
For B1 and B2 we also report kNN (k = 16) over the tuned embeddings, and the ensemble
(mean of the embedding-LR and A1 class probabilities).

  python scripts/slm_train2.py ARM [--folds unseen_terms,org5] [--steps 200] [--threads 4]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SLM = ROOT / "runs" / "20260928_div" / "slm"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from skillc.frontend.policyindex import CLASSES  # noqa: E402
from slm_arms import macro_f1  # noqa: E402

MODEL = Path("/tmp/claude-0/-home-user-skill-achievability-compiler/"
             "a1321181-416f-5422-8c3b-9ffc8650b51c/scratchpad/models/distilroberta-base")
CI = {c: i for i, c in enumerate(CLASSES)}
MAXLEN, BS, TEMP, LR, K = 64, 32, 0.1, 3e-5, 16


def h(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16)


def load(silver: bool):
    gold = [json.loads(x) for x in (SLM / "rows.jsonl").read_text().splitlines()]
    sil = ([json.loads(x) for x in (SLM / "silver_rows.jsonl").read_text().splitlines()]
           if silver else [])
    folds = {"unseen_terms": lambda r: h("term:" + r["term"]) % 5,
             "org5": lambda r: h("org:" + r["org"]) % 5}
    return gold, sil, folds


def text(r, term=None):
    return f"term: {term or r['term']}\ncontext: {r['context']}"


# ---------------------------------------------------------------- lexical (A0, A1)

def lexical(train, test):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True)
    X = vec.fit_transform([f"{r['term']} || {r['context']}" for r in train])
    Xt = vec.transform([f"{r['term']} || {r['context']}" for r in test])
    mc = LogisticRegression(max_iter=3000, class_weight="balanced").fit(X, [r["cls"] for r in train])
    mk = LogisticRegression(max_iter=3000, class_weight="balanced").fit(X, [r["core"] for r in train])
    P = np.zeros((len(test), len(CLASSES)))
    P[:, [CI[c] for c in mc.classes_]] = mc.predict_proba(Xt)
    return P, list(mk.predict(Xt))


# ---------------------------------------------------------------- contrastive (B*)

def supcon(z, y):
    """Supervised contrastive loss (Khosla et al. 2020) on L2-normalised embeddings."""
    import torch
    sim = z @ z.T / TEMP
    n = len(y)
    eye = torch.eye(n, dtype=torch.bool)
    pos = (y[:, None] == y[None, :]) & ~eye
    sim = sim.masked_fill(eye, -1e9)
    logp = sim - torch.logsumexp(sim, dim=1, keepdim=True)
    has = pos.any(1)
    return -((logp * pos).sum(1)[has] / pos.sum(1)[has]).mean()


def sampler(rows, rng):
    """Square-root class-balanced sampling of batches of size BS."""
    by = {}
    for r in rows:
        by.setdefault(r["cls"], []).append(r)
    cls = sorted(by)
    w = np.array([math.sqrt(len(by[c])) for c in cls])
    w = w / w.sum()
    while True:
        cs = rng.choice(len(cls), size=BS, p=w)
        yield [by[cls[c]][rng.integers(len(by[cls[c]]))] for c in cs]


class Encoder:
    def __init__(self, neologism_terms=None):
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(MODEL)
        self.model = AutoModel.from_pretrained(MODEL)
        self.known = set()
        if neologism_terms:
            new = sorted(neologism_terms)
            ids = [self.tok(t, add_special_tokens=False).input_ids for t in new]
            self.tok.add_tokens([f"<t:{t}>" for t in new])
            self.model.resize_token_embeddings(len(self.tok))
            emb = self.model.get_input_embeddings().weight
            with torch.no_grad():                       # subword-mean initialisation
                base = len(self.tok) - len(new)
                for k, sub in enumerate(ids):
                    if sub:
                        emb[base + k] = emb[sub].mean(0)
            self.known = set(new)

    def term(self, r):
        return f"<t:{r['term']}>" if r["term"] in self.known else None

    def encode(self, rows, grad=False):
        torch = self.torch
        enc = self.tok([text(r, self.term(r)) for r in rows], return_tensors="pt",
                       padding=True, truncation=True, max_length=MAXLEN)
        ctx = torch.enable_grad() if grad else torch.no_grad()
        with ctx:
            out = self.model(**enc).last_hidden_state
            m = enc["attention_mask"].unsqueeze(-1).float()
            z = (out * m).sum(1) / m.sum(1)
            return torch.nn.functional.normalize(z, dim=-1)

    def fit(self, rows, steps, seed=0):
        torch = self.torch
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        opt = torch.optim.AdamW(self.model.parameters(), lr=LR)
        self.model.train()
        it = sampler(rows, rng)
        for _ in range(steps):
            b = next(it)
            loss = supcon(self.encode(b, grad=True), torch.tensor([CI[r["cls"]] for r in b]))
            loss.backward()
            opt.step()
            opt.zero_grad()
        self.model.eval()

    def embed(self, rows):
        return np.concatenate([self.encode(rows[i:i + 64]).numpy()
                               for i in range(0, len(rows), 64)])


def heads(E, train, Et):
    """cls: unweighted LR + post-hoc logit adjustment (Menon et al. 2021, tau=1), which is the
    prior correction; adding class weights as well would correct twice. core: balanced LR."""
    from sklearn.linear_model import LogisticRegression
    y = [r["cls"] for r in train]
    mc = LogisticRegression(max_iter=3000, C=1.0).fit(E, y)
    logits = mc.decision_function(Et)
    if logits.ndim == 1:
        logits = np.stack([-logits, logits], 1)
    prior = Counter(y)
    adj = np.array([math.log(prior[c] / len(y)) for c in mc.classes_])
    P = np.zeros((len(Et), len(CLASSES)))
    ex = np.exp(logits - adj - (logits - adj).max(1, keepdims=True))
    P[:, [CI[c] for c in mc.classes_]] = ex / ex.sum(1, keepdims=True)
    mk = LogisticRegression(max_iter=3000, class_weight="balanced").fit(E, [r["core"] for r in train])
    return P, list(mk.predict(Et))


def knn(E, train, Et):
    S = Et @ E.T
    idx = np.argsort(-S, axis=1)[:, :K]
    P = np.zeros((len(Et), len(CLASSES)))
    for i, row in enumerate(idx):
        for j in row:
            P[i, CI[train[j]["cls"]]] += max(S[i, j], 0)
    return P / np.maximum(P.sum(1, keepdims=True), 1e-9)


# ---------------------------------------------------------------- evaluation

def score(test, P, core_pred):
    y = [r["cls"] for r in test]
    p = [CLASSES[i] for i in P.argmax(1)]
    return y, p, [a == r["core"] for a, r in zip(core_pred, test)]


def summarise(y, p, core_hits, gold):
    big = [c for c, n in Counter(r["cls"] for r in gold).items() if n >= 20]
    keep = [i for i, c in enumerate(y) if c in big]
    return {"rows": len(y), "cls_macro_f1": macro_f1(y, p, CLASSES),
            "cls_macro_f1_classes_ge20": macro_f1([y[i] for i in keep], [p[i] for i in keep], big),
            "cls_accuracy": round(sum(a == b for a, b in zip(y, p)) / len(y), 4),
            "core_accuracy": round(sum(core_hits) / len(core_hits), 4)}


def run(arm, split_names, steps, log):
    silver = arm in ("A1", "B1", "B2")
    gold, sil, folds = load(silver)
    res = {}
    for split in split_names:
        f = folds[split]
        acc = {}
        for k in range(5):
            t0 = time.time()
            test = [r for r in gold if f(r) == k]
            tr_gold = [r for r in gold if f(r) != k]
            tr_sil = [r for r in sil if f(r) != k]            # leakage filter (term / org)
            if split == "unseen_terms":
                tt = {r["term"] for r in test}
                tr_sil = [r for r in tr_sil if r["term"] not in tt]
            train = tr_gold + tr_sil
            outs = {}
            if arm in ("A0", "A1"):
                outs[arm] = lexical(train, test)
            else:
                enc = Encoder({r["term"] for r in train} if arm == "B2" else None)
                enc.fit(train, steps, seed=k)
                E, Et = enc.embed(train), enc.embed(test)
                Pl, kl = heads(E, train, Et)
                outs[arm] = (Pl, kl)
                outs[arm + "+knn"] = (knn(E, train, Et), kl)
                if arm != "B1g":
                    Px, kx = lexical(train, test)
                    outs[arm + "+ens"] = ((Pl + Px) / 2, kl)
            for name, (P, kp) in outs.items():
                y, p, ch = score(test, P, kp)
                a = acc.setdefault(name, ([], [], []))
                a[0].extend(y), a[1].extend(p), a[2].extend(ch)
            log(f"{arm} {split} fold {k}: test={len(test)} train={len(tr_gold)}+{len(tr_sil)} "
                f"{time.time() - t0:.0f}s")
        for name, (y, p, ch) in acc.items():
            res.setdefault(name, {})[split] = summarise(y, p, ch, gold)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arm", choices=("A0", "A1", "B1g", "B1", "B2"))
    ap.add_argument("--folds", default="unseen_terms,org5")
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    import torch
    torch.set_num_threads(a.threads)
    random.seed(0)
    logf = (SLM / f"train2_{a.arm}.log").open("w")
    log = lambda m: (print(m, flush=True), logf.write(m + "\n"), logf.flush())
    res = run(a.arm, a.folds.split(","), a.steps, log)
    (SLM / f"results2_{a.arm}.json").write_text(json.dumps(res, indent=1) + "\n")
    log(json.dumps(res))


if __name__ == "__main__":
    main()
