"""Small-model arms for the term -> requirement task (runs/20260928_div/PLAN.md, step 3).

Input: runs/20260928_div/slm/{rows.jsonl, splits.json} from scripts/slm_dataset.py.
Task per row: predict `cls` (11 classes, macro-F1) and `core` (accuracy) from the term
and its context line. Two splits: leave_org_out (held-out repositories) and
unseen_terms (test terms never seen in training).

  python scripts/slm_arms.py baseline                 # runs anywhere (scikit-learn)
  python scripts/slm_arms.py retrieval --model M      # needs model weights
  python scripts/slm_arms.py lora --model M           # needs weights + peft (+ GPU)
  python scripts/slm_arms.py neologism --model M      # needs weights (+ GPU)

The three model arms share one prompt: "term: <t>\ncontext: <c>\nrequirement:" and
score each class name by its log-likelihood as a continuation (and "core"/"optional"
likewise), so no arm needs a new classification head.
  retrieval  frozen base model; the prompt is prefixed with the k=8 most similar
             training rows (by mean-pooled hidden state), each with its labels
  lora       LoRA (r=8) on attention projections, 2 epochs over training rows
  neologism  one new token per training term (<t:term>), only those embedding rows
             are trained; the base model is frozen. Unseen test terms keep their
             ordinary spelling, which is the point of the unseen_terms split.
Results go to runs/20260928_div/slm/results_<arm>.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLM = ROOT / "runs" / "20260928_div" / "slm"
sys.path.insert(0, str(ROOT / "src"))
from skillc.frontend.policyindex import CLASSES  # noqa: E402


def load():
    rows = [json.loads(ln) for ln in (SLM / "rows.jsonl").read_text().splitlines()]
    splits = json.loads((SLM / "splits.json").read_text())
    return rows, splits


def folds(rows, splits):
    """(split, fold, train_idx, test_idx) for both splits."""
    n = len(rows)
    for split, fs in splits.items():
        for name, test in fs.items():
            t = set(test)
            yield split, name, [i for i in range(n) if i not in t], sorted(t)


def macro_f1(y, p, labels):
    f = []
    for c in labels:
        tp = sum(a == c and b == c for a, b in zip(y, p))
        fp = sum(a != c and b == c for a, b in zip(y, p))
        fn = sum(a == c and b != c for a, b in zip(y, p))
        if tp + fp + fn:
            f.append(2 * tp / (2 * tp + fp + fn))
    return round(sum(f) / len(f), 4) if f else None


def summarise(per_fold):
    out = {}
    for split in {k[0] for k in per_fold}:
        fs = [v for k, v in per_fold.items() if k[0] == split]
        n = sum(v["n"] for v in fs)
        out[split] = {"folds": len(fs), "rows": n,
                      "cls_macro_f1": round(sum(v["cls_f1"] * v["n"] for v in fs) / n, 4),
                      "cls_accuracy": round(sum(v["cls_acc"] * v["n"] for v in fs) / n, 4),
                      "core_accuracy": round(sum(v["core_acc"] * v["n"] for v in fs) / n, 4)}
    return out


def evaluate(rows, splits, predict):
    """predict(train_rows, test_rows) -> (cls_preds, core_preds)."""
    per = {}
    for split, name, tr, te in folds(rows, splits):
        train, test = [rows[i] for i in tr], [rows[i] for i in te]
        pc, pk = predict(train, test)
        yc, yk = [r["cls"] for r in test], [r["core"] for r in test]
        per[(split, name)] = {"n": len(test), "cls_f1": macro_f1(yc, pc, CLASSES) or 0,
                              "cls_acc": sum(a == b for a, b in zip(yc, pc)) / len(test),
                              "core_acc": sum(a == b for a, b in zip(yk, pk)) / len(test)}
    return summarise(per)


def text(r):
    return f"{r['term']} || {r['context']}"


def arm_majority(train, test):
    c = Counter(r["cls"] for r in train).most_common(1)[0][0]
    k = Counter(r["core"] for r in train).most_common(1)[0][0]
    return [c] * len(test), [k] * len(test)


def arm_lookup(train, test):
    """The policy index as a classifier: majority label of the same term in training,
    else the global majority (so it cannot help on unseen_terms, by construction)."""
    by = {}
    for r in train:
        by.setdefault(r["term"], []).append(r)
    gc, gk = arm_majority(train, [None])
    pc, pk = [], []
    for r in test:
        ms = by.get(r["term"])
        pc.append(Counter(m["cls"] for m in ms).most_common(1)[0][0] if ms else gc[0])
        pk.append(Counter(m["core"] for m in ms).most_common(1)[0][0] if ms else gk[0])
    return pc, pk


def arm_lexical(train, test):
    """Character n-gram TF-IDF of term + context, logistic regression."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True)
    X = vec.fit_transform([text(r) for r in train])
    Xt = vec.transform([text(r) for r in test])
    out = []
    for key in ("cls", "core"):
        y = [r[key] for r in train]
        if len(set(y)) < 2:
            out.append([y[0]] * len(test))
            continue
        m = LogisticRegression(max_iter=2000, class_weight="balanced").fit(X, y)
        out.append(list(m.predict(Xt)))
    return out[0], out[1]


def baseline() -> dict:
    rows, splits = load()
    res = {name: evaluate(rows, splits, f) for name, f in
           (("majority", arm_majority), ("index_lookup", arm_lookup),
            ("lexical_tfidf_lr", arm_lexical))}
    (SLM / "results_baseline.json").write_text(json.dumps(res, indent=1) + "\n")
    return res


# --- model arms (need weights; not runnable in the current environment) ------------

PROMPT = "term: {term}\ncontext: {context}\nrequirement:"


def _need(model: str):
    try:
        import torch  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        raise SystemExit(f"model arms need torch + transformers: {e}")
    try:
        tok = AutoTokenizer.from_pretrained(model)
        lm = AutoModelForCausalLM.from_pretrained(model)
    except OSError as e:
        raise SystemExit(f"cannot load weights for {model!r} (network policy?): {e}")
    return tok, lm


def _score(tok, lm, prompts, options):
    """Pick, for each prompt, the option with the highest continuation log-likelihood."""
    import torch
    out = []
    for p in prompts:
        best, bl = None, -1e30
        for o in options:
            ids = tok(p + " " + str(o), return_tensors="pt").input_ids
            n = len(tok(p).input_ids)
            with torch.no_grad():
                logits = lm(ids).logits[0, :-1]
            lp = torch.log_softmax(logits, -1)[range(n - 1, ids.shape[1] - 1), ids[0, n:]].sum()
            if lp > bl:
                best, bl = o, float(lp)
        out.append(best)
    return out


def model_arm(arm: str, model: str) -> dict:
    tok, lm = _need(model)
    rows, splits = load()
    core_opts = ["core", "optional"]

    def predict(train, test):
        import torch
        prompts = [PROMPT.format(**r) for r in test]
        if arm == "retrieval":
            def emb(rs):
                with torch.no_grad():
                    return torch.stack([lm(**tok(PROMPT.format(**r), return_tensors="pt"),
                                           output_hidden_states=True).hidden_states[-1][0].mean(0)
                                        for r in rs])
            E, Et = emb(train), emb(test)
            sims = torch.nn.functional.normalize(Et, dim=-1) @ torch.nn.functional.normalize(E, dim=-1).T
            prompts = ["\n\n".join(PROMPT.format(**train[j]) + f" {train[j]['cls']}, "
                                   f"{'core' if train[j]['core'] else 'optional'}"
                                   for j in sims[i].topk(min(8, len(train))).indices.tolist())
                       + "\n\n" + prompts[i] for i in range(len(test))]
        elif arm in ("lora", "neologism"):
            _finetune(arm, tok, lm, train)
            if arm == "neologism":
                known = {r["term"] for r in train}
                prompts = [PROMPT.format(term=f"<t:{r['term']}>" if r["term"] in known else r["term"],
                                         context=r["context"]) for r in test]
        pc = _score(tok, lm, prompts, CLASSES)
        pk = [x == "core" for x in _score(tok, lm, prompts, core_opts)]
        return pc, pk

    res = {arm: evaluate(rows, splits, predict), "model": model}
    (SLM / f"results_{arm}.json").write_text(json.dumps(res, indent=1) + "\n")
    return res


def _finetune(arm, tok, lm, train, epochs=2, lr=1e-4):
    import torch
    if arm == "lora":
        from peft import LoraConfig, get_peft_model
        lm = get_peft_model(lm, LoraConfig(r=8, lora_alpha=16, target_modules=["q_proj", "v_proj"]))
        params = [p for p in lm.parameters() if p.requires_grad]
        fmt = lambda r: PROMPT.format(**r)
    else:
        new = sorted({f"<t:{r['term']}>" for r in train})
        tok.add_tokens(new)
        lm.resize_token_embeddings(len(tok))
        first = len(tok) - len(new)
        for p in lm.parameters():
            p.requires_grad = False
        emb = lm.get_input_embeddings().weight
        emb.requires_grad = True
        emb.register_hook(lambda g: torch.cat([torch.zeros_like(g[:first]), g[first:]]))
        params = [emb]
        fmt = lambda r: PROMPT.format(term=f"<t:{r['term']}>", context=r["context"])
    opt = torch.optim.AdamW(params, lr=lr)
    lm.train()
    for _ in range(epochs):
        for r in train:
            s = fmt(r) + f" {r['cls']}, {'core' if r['core'] else 'optional'}"
            ids = tok(s, return_tensors="pt").input_ids
            loss = lm(ids, labels=ids).loss
            loss.backward()
            opt.step()
            opt.zero_grad()
    lm.eval()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arm", choices=("baseline", "retrieval", "lora", "neologism"))
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B")
    a = ap.parse_args()
    res = baseline() if a.arm == "baseline" else model_arm(a.arm, a.model)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
