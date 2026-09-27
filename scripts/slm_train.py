"""CPU training of the small-model arms (runs/20260928_div/PLAN.md, amendment B).

Weights: GPT-2 medium (355M) and RoBERTa-base (125M) from the legacy Hugging Face S3
bucket, the only model host reachable from this sandbox (see amendment B).

Task per row of runs/20260928_div/slm/rows.jsonl: predict the requirement class `cls`
(11 classes, macro-F1) and `core` (accuracy) from the term and its context line.

Arms (all with two linear heads, cls and core, on the model's pooled state):
  retrieval  frozen encoder, mean-pooled embeddings, cosine k-NN vote (k=8)
  lora       LoRA r=8 on attention, 3 epochs
  neologism  frozen model; one new token <t:term> per training term, whose
             embedding rows (and the heads) are the only trained parameters;
             a test term never seen in training keeps its ordinary spelling
Splits: unseen_terms (5 folds, as frozen) and org5 (organisations hashed into 5 groups).

  python scripts/slm_train.py ARM --model gpt2-medium|roberta-base [--folds unseen_terms,org5]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
SLM = ROOT / "runs" / "20260928_div" / "slm"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from skillc.frontend.policyindex import CLASSES  # noqa: E402
from slm_arms import arm_lexical, arm_lookup, arm_majority, macro_f1  # noqa: E402

MODELS = Path("/tmp/claude-0/-home-user-skill-achievability-compiler/"
              "a1321181-416f-5422-8c3b-9ffc8650b51c/scratchpad/models")
CI = {c: i for i, c in enumerate(CLASSES)}
MAXLEN = 64


def load():
    rows = [json.loads(x) for x in (SLM / "rows.jsonl").read_text().splitlines()]
    sp = json.loads((SLM / "splits.json").read_text())
    h = lambda s: int(hashlib.sha256(s.encode()).hexdigest(), 16)
    org5 = {str(k): [i for i, r in enumerate(rows) if h("org:" + r["org"]) % 5 == k]
            for k in range(5)}
    return rows, {"unseen_terms": sp["unseen_terms"], "org5": org5}


def text(r, term=None):
    return f"term: {term or r['term']}\ncontext: {r['context']}"


class Net(torch.nn.Module):
    def __init__(self, base, hidden, decoder: bool):
        super().__init__()
        self.base, self.decoder = base, decoder
        self.cls = torch.nn.Linear(hidden, len(CLASSES))
        self.core = torch.nn.Linear(hidden, 2)

    def pooled(self, enc):
        out = self.base(**enc).last_hidden_state
        m = enc["attention_mask"].unsqueeze(-1).float()
        return (out * m).sum(1) / m.sum(1)

    def forward(self, enc):
        h = self.pooled(enc)
        return self.cls(h), self.core(h)


def build(model: str):
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODELS / model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    base = AutoModel.from_pretrained(MODELS / model)
    return tok, base, base.config.hidden_size, model.startswith("gpt2")


def batches(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def encode(tok, texts):
    return tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=MAXLEN)


def train(net, tok, rows, params, epochs=3, lr=2e-4, bs=16, term_fn=None, seed=0):
    opt = torch.optim.AdamW(params, lr=lr)
    random.seed(seed)
    net.train()
    ce = torch.nn.CrossEntropyLoss()
    for _ in range(epochs):
        order = rows[:]
        random.shuffle(order)
        for b in batches(order, bs):
            enc = encode(tok, [text(r, term_fn(r) if term_fn else None) for r in b])
            lc, lk = net(enc)
            loss = ce(lc, torch.tensor([CI[r["cls"]] for r in b])) + \
                ce(lk, torch.tensor([int(r["core"]) for r in b]))
            loss.backward()
            opt.step()
            opt.zero_grad()
    net.eval()


@torch.no_grad()
def predict(net, tok, rows, term_fn=None):
    pc, pk = [], []
    for b in batches(rows, 32):
        lc, lk = net(encode(tok, [text(r, term_fn(r) if term_fn else None) for r in b]))
        pc += [CLASSES[i] for i in lc.argmax(-1).tolist()]
        pk += [bool(i) for i in lk.argmax(-1).tolist()]
    return pc, pk


@torch.no_grad()
def embed(net, tok, rows):
    return torch.cat([torch.nn.functional.normalize(net.pooled(encode(tok, [text(r) for r in b])), dim=-1)
                      for b in batches(rows, 32)])


def arm_retrieval(model):
    tok, base, hid, dec = build(model)
    net = Net(base, hid, dec).eval()
    cache = {}

    def run(train_rows, test_rows):
        key = id(train_rows)
        E = embed(net, tok, train_rows)
        Et = embed(net, tok, test_rows)
        top = (Et @ E.T).topk(8, dim=-1)
        pc, pk = [], []
        for sims, idx in zip(top.values.tolist(), top.indices.tolist()):
            vc, vk = {}, {}
            for s, j in zip(sims, idx):
                vc[train_rows[j]["cls"]] = vc.get(train_rows[j]["cls"], 0) + s
                vk[train_rows[j]["core"]] = vk.get(train_rows[j]["core"], 0) + s
            pc.append(max(vc, key=vc.get))
            pk.append(max(vk, key=vk.get))
        return pc, pk
    return run


def arm_lora(model, epochs=3):
    def run(train_rows, test_rows):
        from peft import LoraConfig, get_peft_model
        tok, base, hid, dec = build(model)
        targets = ["c_attn"] if dec else ["query", "value"]
        base = get_peft_model(base, LoraConfig(r=8, lora_alpha=16, target_modules=targets,
                                               lora_dropout=0.05))
        net = Net(base, hid, dec)
        params = [p for p in net.parameters() if p.requires_grad]
        train(net, tok, train_rows, params, epochs=epochs, lr=3e-4)
        return predict(net, tok, test_rows)
    return run


def arm_neologism(model, epochs=3):
    def run(train_rows, test_rows):
        tok, base, hid, dec = build(model)
        new = sorted({f"<t:{r['term']}>" for r in train_rows})
        tok.add_tokens(new)
        base.resize_token_embeddings(len(tok))
        first = len(tok) - len(new)
        for p in base.parameters():
            p.requires_grad = False
        emb = base.get_input_embeddings().weight
        emb.requires_grad = True
        emb.register_hook(lambda g: torch.cat([torch.zeros_like(g[:first]), g[first:]]))
        net = Net(base, hid, dec)
        known = {r["term"] for r in train_rows}
        tf = lambda r: f"<t:{r['term']}>" if r["term"] in known else r["term"]
        params = [emb] + list(net.cls.parameters()) + list(net.core.parameters())
        train(net, tok, train_rows, params, epochs=epochs, lr=1e-3, term_fn=tf)
        return predict(net, tok, test_rows, term_fn=tf)
    return run


def evaluate(rows, folds, fn, log):
    per = {}
    for split, fs in folds.items():
        agg = {"n": 0, "cls_true": [], "cls_pred": [], "core_hits": 0}
        for name, test in fs.items():
            t0 = time.time()
            ts = set(test)
            tr = [rows[i] for i in range(len(rows)) if i not in ts]
            te = [rows[i] for i in test]
            pc, pk = fn(tr, te)
            agg["cls_true"] += [r["cls"] for r in te]
            agg["cls_pred"] += pc
            agg["core_hits"] += sum(a == r["core"] for a, r in zip(pk, te))
            agg["n"] += len(te)
            log(f"{split} fold {name}: n={len(te)} {time.time() - t0:.0f}s")
        per[split] = {"rows": agg["n"],
                      "cls_macro_f1": macro_f1(agg["cls_true"], agg["cls_pred"], CLASSES),
                      "cls_accuracy": round(sum(a == b for a, b in zip(agg["cls_true"], agg["cls_pred"])) / agg["n"], 4),
                      "core_accuracy": round(agg["core_hits"] / agg["n"], 4)}
    return per


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arm", choices=("baselines", "retrieval", "lora", "neologism"))
    ap.add_argument("--model", default="gpt2-medium")
    ap.add_argument("--folds", default="unseen_terms,org5")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--epochs", type=int, default=3)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    torch.manual_seed(0)
    rows, folds = load()
    folds = {k: v for k, v in folds.items() if k in a.folds.split(",")}
    tag = a.arm if a.arm == "baselines" else f"{a.arm}_{a.model}"
    logf = (SLM / f"train_{tag}.log").open("w")
    log = lambda m: (print(m, flush=True), logf.write(m + "\n"), logf.flush())
    if a.arm == "baselines":
        res = {n: evaluate(rows, folds, f, log) for n, f in
               (("majority", arm_majority), ("index_lookup", arm_lookup),
                ("lexical_tfidf_lr", arm_lexical))}
    else:
        fn = (arm_retrieval(a.model) if a.arm == "retrieval" else
              {"lora": arm_lora, "neologism": arm_neologism}[a.arm](a.model, a.epochs))
        res = {tag: evaluate(rows, folds, fn, log)}
    (SLM / f"results_{tag}.json").write_text(json.dumps(res, indent=1) + "\n")
    log(json.dumps(res))


if __name__ == "__main__":
    main()
