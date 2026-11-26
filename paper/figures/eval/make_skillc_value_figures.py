r"""Build the evaluation's figures, task table and macros for three models.

Run from the repository root:
    python paper\figures\eval\make_skillc_value_figures.py

Reads only the retained run summaries under runs\20261106_real_skills. No model
calls, downloads, or execution of benchmark inputs are performed.
"""
import json
import math
import statistics
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "runs" / "20261106_real_skills"
OUT = Path(__file__).resolve().parent
LATEST = "summary-sonnet-20261125.json"

MODELS = {"gpt-5.3-codex": "Codex", "gpt-5.6-sol": "Sol", "claude-sonnet-5": "Sonnet",
          "claude-opus-5.5": "Opus"}
MODEL_NAMES = {v: k for k, v in MODELS.items()}
ORDER = ("Codex", "Sol", "Sonnet", "Opus")
STYLE = {"Codex": ("#2E6FD8", "o"), "Sol": ("#E8692F", "s"), "Sonnet": ("#8E5BC8", "D"),
         "Opus": ("#1FA97A", "^")}
# (collection, skill id) -> (display name, unreachable, original 14 or new 6)
TASKS = {
    ("pilot-guarded", "AgentCTO__claude-skills__incremental-writes"):
        ("Protected-file edit", True, "original"),
    ("reviewed-instructions-continued", "CaliLuke__skills__multi-agent-setup"):
        ("Instruction-file migration", True, "original"),
    ("reviewed-gh-fetch", "trailofbits__skills__gh-cli"):
        ("Pinned remote file fetch", True, "new"),
    ("reviewed-shopify-signature", "davila7__claude-code-templates__shopify-development"):
        ("Webhook signature with app secret", True, "new"),
    ("reviewed-personal-command", "davila7__claude-code-templates__command-development"):
        ("Personal slash command", True, "new"),
    ("reviewed-skill-name", "openai__skills__skill-creator"):
        ("Protected skill-name fix", True, "new"),
    ("pilot-guarded", "CaliLuke__skills__fowler-refactoring"):
        ("Writable refactoring", False, "original"),
    ("reviewed-tasks", "trailofbits__skills__mutation-testing"):
        ("Mutation inventory", False, "original"),
    ("reviewed-palette", "davila7__claude-code-templates__ui-ux-pro-max"):
        ("Palette contrast audit", False, "original"),
    ("reviewed-property", "trailofbits__skills__property-based-testing"):
        ("Property counterexample", False, "original"),
    ("reviewed-batch", "github__awesome-copilot__batch-script-progress"):
        ("Batch progress events", False, "original"),
    ("reviewed-sql", "anthropics__knowledge-work-plugins__sql-queries"):
        ("SQL genre ranking (a)", False, "original"),
    ("reviewed-sql", "anthropics__knowledge-work-plugins__write-query"):
        ("SQL genre ranking (b)", False, "original"),
    ("reviewed-notebook", "openai__skills__jupyter-notebook"):
        ("Notebook tutorial", False, "original"),
    ("reviewed-captions", "github__awesome-copilot__caption-qa"):
        ("Caption CI checker", False, "original"),
    ("reviewed-index", "github__awesome-copilot__update-markdown-file-index"):
        ("Markdown index update", False, "original"),
    ("reviewed-sweep", "NVIDIA__skills__bionemo-complexa-sweep"):
        ("Sweep-summary ranking", False, "original"),
    ("reviewed-symbolic", "k-dense-ai__claude-scientific-skills__sympy"):
        ("Rational-root CLI", False, "original"),
    ("reviewed-shopify-port", "davila7__claude-code-templates__shopify-development"):
        ("Webhook check port", False, "new"),
    ("reviewed-devcontainer", "trailofbits__skills__devcontainer-setup"):
        ("Dev-container config", False, "new"),
}
QUARANTINED = {
    ("reviewed-layout", "CaliLuke__skills__identify-layout-smells"): "Layout map",
    ("reviewed-metadata", "sickn33__agentic-awesome-skills__fixing-metadata"): "Preview metadata",
}
QUARANTINE_FILES = {"reviewed-layout": "summary_frozen_oracle.json",
                    "reviewed-metadata": "summary.json"}
ACHIEVED = "verified_goal_achieved"
NOT_ACHIEVED = "verified_goal_not_achieved_with_runtime_evidence"
NAVY, GREEN, AMBER, RED, GREY = "#1F3A5F", "#227850", "#C98A18", "#B23434", "#8A94A6"


def tokens(stage):
    usage = stage.get("usage")
    if not usage:
        return None
    d = usage["disjoint_tokens"]
    return d["input"] + d["cache_read"] + d["cache_write"] + d["output"]


def load(collection, name):
    summary = json.loads((RUNS / collection / name).read_text(encoding="utf-8"))
    rows = []
    for trial in summary["trials"]:
        compaction = trial["stages"].get("compaction", {})
        execution = trial["stages"].get("execution", {})
        rows.append({
            "task": (collection, trial["source"]), "source": trial["source"],
            "model": MODELS[trial["model"]], "repeat": trial["repeat"],
            "verdict": compaction.get("verdict"), "outcome": execution.get("outcome"),
            "compile_tokens": tokens(compaction), "execute_tokens": tokens(execution),
            "compile_s": compaction.get("seconds"), "execute_s": execution.get("seconds"),
            "rerun": False,
        })
    return rows


def apply_compaction_rerun(rows):
    """Replace the one failed Sol compaction with its recorded rerun (a reported deviation)."""
    folder = RUNS / "reviewed-instructions-continued"
    record = json.loads((folder / "compaction_rerun_20261125.json").read_text(encoding="utf-8"))
    result = json.loads((folder / "compaction-rerun-20261125" / "result.json")
                        .read_text(encoding="utf-8"))
    assert record["protocol_deviation"] and not record["execution_rerun"]
    row, = [r for r in rows if r["source"] == record["source"]
            and r["model"] == MODELS[record["model"]] and r["repeat"] == record["repeat"]]
    assert row["verdict"] is None and row["compile_tokens"] is None
    row.update(verdict=result["verdict"], compile_tokens=tokens(result),
               compile_s=result["seconds"], rerun=True)


def label(row):
    """Impossible is the positive class: TP is a correct block."""
    if row["outcome"] not in (ACHIEVED, NOT_ACHIEVED):
        return "unresolved"
    if row["verdict"] not in ("ACHIEVABLE", "IMPOSSIBLE"):
        return "no_prediction"
    blocked, achieved = row["verdict"] == "IMPOSSIBLE", row["outcome"] == ACHIEVED
    return {(True, False): "TP", (True, True): "FP",
            (False, False): "FN", (False, True): "TN"}[(blocked, achieved)]


def sensitivity_label(row):
    """Figure 3 only: an execution without an outcome counts as failed."""
    if row["outcome"] in ("budget_exhausted", "no_sandbox_action"):
        return label({**row, "outcome": NOT_ACHIEVED})
    return label(row)


def truth_label(row):
    """Primary scoring: the verdict against the task's reachability by construction.

    Every task is unreachable or reachable by its declared environment, as the
    prefreeze barrier controls show, and every execution with an outcome agrees.
    This scores all 100 trials of every model, including executions without an
    outcome."""
    # Fail-closed, as the host rule requires: only an achievable verdict lets the
    # execution run, so a gate without a valid verdict blocks.
    blocked, unreachable = row["verdict"] != "ACHIEVABLE", TASKS[row["task"]][1]
    return {(True, True): "TP", (True, False): "FP",
            (False, True): "FN", (False, False): "TN"}[(blocked, unreachable)]


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def wilson(k, n, z=1.96):
    if not n:
        return (math.nan, math.nan, math.nan)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def load_all():
    rows = []
    original = sorted({c for (c, _), v in TASKS.items() if v[2] == "original"})
    for collection in original:
        rows += load(collection, "summary.json")
    frozen = Counter(label(r) for r in rows)
    # The frozen Codex/Sol primary counts before any later change; stop on drift.
    assert (frozen["TN"], frozen["FN"], frozen["TP"], frozen["FP"]) == (119, 14, 5, 0), frozen
    apply_compaction_rerun(rows)
    for collection in sorted({c for c, _ in TASKS}):
        rows += load(collection, LATEST)
    keys = Counter((r["task"], r["model"], r["repeat"]) for r in rows)
    assert all(v == 1 for v in keys.values()), "duplicate trial"
    assert {r["task"] for r in rows} == set(TASKS)
    for model in ORDER:
        assert sum(r["model"] == model for r in rows) == 100, model
    quarantined = [r for c, name in QUARANTINE_FILES.items() for r in load(c, name)]
    return rows, quarantined


def counts(rows, labeller=None):
    labeller = labeller or truth_label
    return Counter(labeller(r) for r in rows)


def confusion_figure(rows):
    fig, axes = plt.subplots(1, 4, figsize=(10.4, 3.0))
    result = {}
    for ax, model in zip(axes, ORDER, strict=True):
        group = [r for r in rows if r["model"] == model]
        c = counts(group)
        assert sum(c[k] for k in ("TP", "FP", "FN", "TN")) == len(group) == 100
        result[model] = c
        cells = (("TP", "correct\nblock", NAVY, 0, 1), ("FP", "wrong\nblock", RED, 1, 1),
                 ("FN", "wrong\nallow", AMBER, 0, 0), ("TN", "correct\nallow", GREEN, 1, 0))
        for key, words, color, x, y in cells:
            n = c[key]
            ax.add_patch(Rectangle((x, y), 1, 1, facecolor=color,
                                   alpha=0.92 if n else 0.18, edgecolor="white", lw=2))
            ink = "white" if n else "#333333"
            ax.text(x + .5, y + .62, str(n), ha="center", va="center",
                    fontsize=12, weight="bold", color=ink)
            ax.text(x + .5, y + .28, f"{key}: {words}", ha="center", va="center",
                    fontsize=6.3, color=ink)
        ax.set_xlim(0, 2)
        ax.set_ylim(0, 2)
        ax.set_aspect("equal")
        ax.set_xticks([.5, 1.5], ["unreachable", "reachable"], fontsize=8)
        ax.set_yticks([.5, 1.5], ["allowed", "blocked"], fontsize=8)
        ax.tick_params(length=0)
        for side in ax.spines.values():
            side.set_visible(False)
        ax.set_xlabel("task", fontsize=8)
        if ax is axes[0]:
            ax.set_ylabel("gate verdict", fontsize=8)
        tp, fp, fn = c["TP"], c["FP"], c["FN"]
        precision = f"{tp / (tp + fp):.0%}" if tp + fp else "undefined"
        ax.set_title(f"{MODEL_NAMES[model]} (n={len(group)})\nprecision {precision}, "
                     f"recall {tp / (tp + fn):.0%}", fontsize=8.5)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig_skillc_confusion.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return result


def interval_figure(rows):
    """Per-model rates with Wilson 95% intervals over decided trials, by task subset."""
    subsets = (("All 20 tasks", lambda r: True),
               ("Original 14 tasks", lambda r: TASKS[r["task"]][2] == "original"),
               ("New 6 tasks", lambda r: TASKS[r["task"]][2] == "new"))
    panels = (("Accuracy", lambda c: (c["TP"] + c["TN"], sum(
                  c[k] for k in ("TP", "FP", "FN", "TN"))), 100),
              ("Unreachable tasks caught", lambda c: (c["TP"], c["TP"] + c["FN"]), 100),
              ("Reachable tasks blocked", lambda c: (c["FP"], c["FP"] + c["TN"]), 40))
    fig, axes = plt.subplots(1, 3, figsize=(8.6, 3.5), sharey=True)
    offsets = {"Codex": .36, "Sol": .12, "Sonnet": -.12, "Opus": -.36}
    ticks = []
    for i, (title, keep) in enumerate(subsets):
        y = -i * 1.4
        subset = [r for r in rows if keep(r)]
        per_model = len(subset) // len(ORDER)
        unreachable = sum(TASKS[r["task"]][1] for r in subset) // len(ORDER)
        ticks.append((y, f"{title}\n{per_model} trials per model, {unreachable} unreachable"))
        for model in ORDER:
            c = counts([r for r in subset if r["model"] == model])
            color, marker = STYLE[model]
            for ax, (_, rate, _) in zip(axes, panels, strict=True):
                k, n = rate(c)
                p, lo, hi = wilson(k, n)
                yy = y + offsets[model]
                ax.plot([lo * 100, hi * 100], [yy, yy], color=color, alpha=.45, lw=2.4,
                        solid_capstyle="round")
                ax.plot(p * 100, yy, marker=marker, color=color, ms=6.5, zorder=3,
                        markeredgecolor="white", markeredgewidth=.6)
                ax.text(hi * 100 + 1.5, yy, f"{k}/{n}", va="center", fontsize=7.8,
                        color="#444444")
    for ax, (title, _, limit) in zip(axes, panels, strict=True):
        ax.set_title(title, fontsize=10, loc="left")
        ax.set_xlim(0, limit)
        step = 25 if limit == 100 else 10
        ax.set_xticks(range(0, limit + 1, step),
                      [f"{v}%" if v == limit else str(v) for v in range(0, limit + 1, step)],
                      fontsize=8)
        ax.grid(axis="x", color="#DDDDDD", lw=.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].set_yticks([t[0] for t in ticks], [t[1] for t in ticks], fontsize=9)
    axes[0].set_ylim(-3.5, .7)
    handles = [Line2D([], [], color=STYLE[m][0], marker=STYLE[m][1], lw=0, ms=7,
                      label=f"compaction by {MODEL_NAMES[m]}") for m in ORDER]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=8.5,
               bbox_to_anchor=(.55, -.06))
    fig.tight_layout(rect=(0, .07, 1, 1))
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig_skillc_models.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)


def category_panel(ax, rows):
    """Per-trial execution tokens avoided versus gate cost, by task type and model."""
    groups = [(f"{kind} tasks\n{MODEL_NAMES[m]}",
               [r for r in rows if TASKS[r["task"]][1] == unreachable and r["model"] == m])
              for kind, unreachable in (("6 unreachable", True), ("14 reachable", False))
              for m in ORDER]
    k = 1000
    y = list(range(len(groups)))[::-1]
    for yi, (_, group) in zip(y, groups, strict=True):
        n = len(group)
        cost = sum(r["compile_tokens"] or 0 for r in group) / n / k
        saved = sum(r["execute_tokens"] for r in group if truth_label(r) == "TP") / n / k
        ax.barh(yi + .19, saved, height=.36, facecolor="white", edgecolor=NAVY,
                hatch="///", lw=1.2)
        ax.barh(yi - .19, cost, height=.36, color=GREY)
        ax.text(saved + .15, yi + .19, f"{saved:.1f}k", va="center", fontsize=7, color=NAVY)
        ax.text(cost + .15, yi - .19, f"{cost:.1f}k", va="center", fontsize=7,
                color="#444444")
        net = saved - cost
        ax.text(26.6, yi, f"{net:+.1f}k", va="center", ha="right", fontsize=7.5,
                weight="bold", color=GREEN if net > 0 else RED)
    ax.set_yticks(y, [g[0] for g in groups], fontsize=7)
    ax.set_xlim(0, 27)
    ax.text(26.6, len(groups) - .35, "net", ha="right", fontsize=7.5, weight="bold")
    ax.set_xlabel("mean tokens per trial (thousands)", fontsize=8.5)
    ax.legend(handles=[Patch(facecolor="white", edgecolor=NAVY, hatch="///",
                             label="execution tokens avoided by blocking"),
                       Patch(color=GREY, label="gate cost (compaction + check)")],
              fontsize=7.5, loc="upper center", frameon=False,
              bbox_to_anchor=(.45, -.2), ncol=1)
    ax.set_title("(b) Avoided versus cost, per trial", fontsize=10, loc="left")
    ax.spines[["top", "right"]].set_visible(False)


def token_figure(rows, stats):
    fig = plt.figure(figsize=(8.8, 7.4))
    grid = fig.add_gridspec(2, 2, width_ratios=[1, 1.15], height_ratios=[1, 1],
                            hspace=.55, wspace=.5)
    left, middle = fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])
    right = fig.add_subplot(grid[1, :])
    category_panel(middle, rows)
    k = 1000
    wasted = (stats["tp_exec"] + stats["fn_exec"]) / k
    saved, still = stats["tp_exec"] / k, stats["fn_exec"] / k
    left.bar(0, wasted, color=AMBER, width=.62)
    left.bar(1, still, color=AMBER, width=.62)
    left.bar(1, saved, bottom=still, width=.62, facecolor="white", edgecolor=NAVY,
             hatch="///", lw=1.4)
    left.text(0, wasted * 1.02, f"{wasted:,.1f}k", ha="center", va="bottom", fontsize=9)
    left.text(1, still / 2, f"not avoided\n{still:,.1f}k", ha="center", va="center",
              fontsize=7.5, color="white", weight="bold")
    left.text(1, still + saved / 2, f"avoided\n{saved:,.1f}k\n({saved / wasted:.0%})",
              ha="center", va="center", fontsize=8.5, color=NAVY, weight="bold",
              bbox={"facecolor": "white", "edgecolor": "none", "pad": 1})
    left.set_xticks([0, 1], ["without gate", "with gate"], fontsize=9)
    left.set_xlim(-.6, 1.6)
    left.set_ylim(0, wasted * 1.18)
    left.set_ylabel(f"execution tokens of the {stats['n_failed']}\n"
                    "unreachable-task executions (thousands)", fontsize=8.5)
    left.set_title("(a) Unreachable tasks: tokens avoided", fontsize=10, loc="left")
    net = (stats["gate"] - stats["tp_exec"]) / k
    left.text(.5, -.22, f"Gate cost (compaction + check), paid on all {stats['trials']} "
              f"trials: {stats['gate'] / k:,.0f}k tokens\nso on this cohort the gate "
              f"costs {net:,.0f}k more than it avoids", transform=left.transAxes,
              ha="center", va="top", fontsize=8, color="#444444")
    left.spines[["top", "right"]].set_visible(False)

    p = [i / 200 for i in range(2, 201)]
    for recall, style, name in ((stats["recall"], "-", "measured recall"),
                                (1.0, "--", "perfect recall")):
        right.plot(p, [1 / (x * recall) for x in p], style, color=NAVY, lw=1.6,
                   label=f"break-even, {name} ({recall:.0%})")
    right.fill_between(p, [1 / (x * stats["recall"]) for x in p], 300,
                       color=GREEN, alpha=.10, lw=0)
    right.text(.40, 22, "gate saves tokens", color=GREEN, fontsize=9, weight="bold")
    right.text(.98, .40, "gate costs tokens", color=RED, fontsize=9, weight="bold",
               ha="right")
    right.scatter([stats["p_fail"]], [stats["ratio"]], s=60, color=RED, zorder=5,
                  label="this cohort (measured)")
    right.annotate(f"this cohort: p = {stats['p_fail']:.0%},\nratio = {stats['ratio']:.1f}",
                   (stats["p_fail"], stats["ratio"]), xytext=(.36, .38), fontsize=8,
                   arrowprops={"arrowstyle": "->", "color": "#555555"})
    right.axhline(stats["success_ratio"], color=GREY, lw=1, ls=":")
    right.text(.995, stats["success_ratio"] * .93, "failed execution = median achieved execution",
               ha="right", va="top", fontsize=7.5, color="#555555")
    right.set_yscale("log")
    right.set_xlim(0, 1)
    right.set_ylim(.3, 300)
    right.set_xlabel("share of trials whose task is unreachable", fontsize=8.5)
    right.set_ylabel("tokens of a failed execution / gate tokens", fontsize=8.5)
    right.set_title("(c) When does the gate pay off?", fontsize=10, loc="left")
    right.legend(fontsize=7.5, loc="upper right", frameon=False)
    right.spines[["top", "right"]].set_visible(False)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig_skillc_tokens.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)


def fmt_int(value):
    return "--" if value is None else f"{round(value):,}"


def cell(group, quarantined=False):
    """Achieved/verified and blocked/verdicts for one task and model."""
    verified = [r for r in group if r["outcome"] in (ACHIEVED, NOT_ACHIEVED)]
    achieved = sum(r["outcome"] == ACHIEVED for r in verified)
    blocked = sum(r["verdict"] != "ACHIEVABLE" for r in group)
    mark = "$^\\ddagger$" if any(
        r["verdict"] not in ("ACHIEVABLE", "IMPOSSIBLE") for r in group) else ""
    if any(r["outcome"] not in (ACHIEVED, NOT_ACHIEVED) for r in group):
        mark += "$^\\dagger$"
    if any(r["rerun"] for r in group):
        mark += "$^\\S$"
    return f"{achieved}/{len(verified)} & {blocked}/{len(group)}{mark}"


def task_rows(rows, keys, names):
    lines = []
    for key in keys:
        group = [r for r in rows if r["task"] == key]
        cells = " & ".join(cell([r for r in group if r["model"] == m]) for m in ORDER)
        models = sorted({r["model"] for r in group})
        if len(models) < len(ORDER):
            cells = " & ".join(cell([r for r in group if r["model"] == m])
                               if m in models else "\\multicolumn{2}{c}{--}" for m in ORDER)
        lines.append(f"{names[key]} & {cells} & "
                     f"{fmt_int(median(r['compile_tokens'] for r in group))} & "
                     f"{fmt_int(median(r['execute_tokens'] for r in group))}\\\\")
    return lines


def task_table(rows, quarantined):
    names = {k: v[0] for k, v in TASKS.items()}
    unreachable = [k for k, v in TASKS.items() if v[1]]
    reachable = [k for k, v in TASKS.items() if not v[1]]
    total = {m: counts([r for r in rows if r["model"] == m]) for m in ORDER}
    body = [
        "\\begin{tabular}{@{}l cc cc cc cc rr@{}}",
        "\\toprule",
        "& " + " & ".join(f"\\multicolumn{{2}}{{c}}{{{MODEL_NAMES[m]}}}" for m in ORDER)
        + " & \\multicolumn{2}{c}{Median tokens}\\\\",
        "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}\\cmidrule(lr){8-9}"
        "\\cmidrule(l){10-11}",
        "Task & " + " & ".join("Ach. & Blk." for _ in ORDER) + " & Gate & Execution\\\\",
        "\\midrule",
        "\\multicolumn{11}{@{}l}{\\emph{Unreachable tasks: every block is correct (TP), "
        "every allow a miss (FN)}}\\\\",
        *task_rows(rows, unreachable, names),
        "\\midrule",
        "\\multicolumn{11}{@{}l}{\\emph{Reachable tasks: every block is wrong (FP)}}\\\\",
        *task_rows(rows, reachable, names),
        "\\midrule",
        "\\textbf{TP\\,/\\,FN\\,/\\,FP\\,/\\,TN} & "
        + " & ".join(f"\\multicolumn{{2}}{{c}}{{\\textbf{{{total[m]['TP']}\\,/\\,"
                     f"{total[m]['FN']}\\,/\\,{total[m]['FP']}\\,/\\,{total[m]['TN']}}}}}"
                     for m in ORDER)
        + f" & {fmt_int(median(r['compile_tokens'] for r in rows))} & "
          f"{fmt_int(median(r['execute_tokens'] for r in rows))}\\\\",
        "\\midrule",
        "\\multicolumn{11}{@{}l}{\\emph{Quarantined: ambiguous measurement rule, "
        "outside all counts}}\\\\",
        *task_rows(quarantined, list(QUARANTINED), QUARANTINED),
        "\\bottomrule",
        "\\end{tabular}",
    ]
    (OUT / "skillc_task_table.tex").write_text(
        "% Generated by make_skillc_value_figures.py; do not edit by hand.\n"
        + "\n".join(body) + "\n", encoding="utf-8")


def pct(value):
    return f"{value:.0%}".replace("%", "\\%")


def main():
    rows, quarantined = load_all()
    c = counts(rows)
    by = {key: [r for r in rows if truth_label(r) == key]
          for key in ("TP", "FN", "TN", "FP")}
    failed = by["TP"] + by["FN"]
    gate = sum(r["compile_tokens"] or 0 for r in rows)
    trials = sum(r["compile_tokens"] is not None for r in rows)
    judged = sum(c[k] for k in ("TP", "FP", "FN", "TN"))
    mean_gate = gate / trials
    stats = {
        "tp_exec": sum(r["execute_tokens"] for r in by["TP"]),
        "fn_exec": sum(r["execute_tokens"] for r in by["FN"]),
        "gate": gate, "trials": trials, "n_failed": len(failed),
        "recall": c["TP"] / (c["TP"] + c["FN"]), "p_fail": len(failed) / judged,
        "ratio": sum(r["execute_tokens"] for r in failed) / len(failed) / mean_gate,
        "success_ratio": median(r["execute_tokens"] for r in by["TN"]) / mean_gate,
    }
    fig3 = confusion_figure(rows)
    interval_figure(rows)
    token_figure(rows, stats)
    task_table(rows, quarantined)
    waste = stats["tp_exec"] + stats["fn_exec"]
    macros = {
        "ValueTrials": len(rows), "ValueJudged": judged,
        "ValueDecided": sum(label(r) in ("TP", "FP", "FN", "TN") for r in rows), "ValueTP": c["TP"],
        "ValueFN": c["FN"], "ValueFP": c["FP"], "ValueTN": c["TN"],
        "ValueFailed": len(failed),
        "ValueUnresolved": counts(rows, label)["unresolved"],
        "ValuePrecision": pct(c["TP"] / (c["TP"] + c["FP"])),
        "ValueRecall": pct(stats["recall"]),
        "ValueSpecificity": pct(c["TN"] / (c["TN"] + c["FP"])),
        "ValueWasteK": f"{waste / 1000:,.1f}", "ValueAvoidedK": f"{stats['tp_exec'] / 1000:,.1f}",
        "ValueMissedK": f"{stats['fn_exec'] / 1000:,.1f}",
        "ValueAvoidedShare": pct(stats["tp_exec"] / waste),
        "ValueGateK": f"{gate / 1000:,.0f}", "ValueGateTrials": trials,
        "ValueGateMedian": fmt_int(median(r["compile_tokens"] for r in rows)),
        "ValueExecMedian": fmt_int(median(r["execute_tokens"] for r in rows)),
        "ValueFailedMedian": fmt_int(median(r["execute_tokens"] for r in failed)),
        "ValueFailShare": pct(stats["p_fail"]), "ValueRatio": f"{stats['ratio']:.1f}",
        "ValueBreakEvenRatio": f"{1 / (stats['p_fail'] * stats['recall']):.0f}",
        "ValueBreakEvenPerfect": f"{1 / stats['p_fail']:.1f}",
        "ValueNetK": f"{(gate - stats['tp_exec']) / 1000:,.0f}",
    }
    for model in ORDER:
        m = counts([r for r in rows if r["model"] == model])
        macros[f"Value{model}TP"] = m["TP"]
        macros[f"Value{model}FN"] = m["FN"]
        macros[f"Value{model}FP"] = m["FP"]
        macros[f"Value{model}TN"] = m["TN"]
        macros[f"Value{model}Unresolved"] = counts(
            [r for r in rows if r["model"] == model], label)["unresolved"]
        macros[f"Value{model}Failed"] = m["TP"] + m["FN"]
        macros[f"Value{model}Invalid"] = sum(
            r["model"] == model and r["verdict"] not in ("ACHIEVABLE", "IMPOSSIBLE") for r in rows)
        macros[f"Value{model}Reachable"] = m["FP"] + m["TN"]
        d = counts([r for r in rows if r["model"] == model], label)
        macros[f"Value{model}DecidedRecall"] = pct(d["TP"] / (d["TP"] + d["FN"]))
        macros[f"Value{model}DecidedFailed"] = d["TP"] + d["FN"]
        macros[f"Value{model}Recall"] = pct(m["TP"] / (m["TP"] + m["FN"]))
        macros[f"Value{model}FigFN"] = fig3[model]["FN"]
        macros[f"Value{model}FigRecall"] = pct(
            fig3[model]["TP"] / (fig3[model]["TP"] + fig3[model]["FN"]))
        for subset in ("original", "new"):
            s = counts([r for r in rows if r["model"] == model and TASKS[r["task"]][2] == subset])
            macros[f"Value{model}{subset.title()}TP"] = s["TP"]
            macros[f"Value{model}{subset.title()}Failed"] = s["TP"] + s["FN"]
    (OUT / "skillc_value_numbers.tex").write_text(
        "% Generated by make_skillc_value_figures.py; do not edit by hand.\n"
        + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in macros.items()),
        encoding="utf-8")
    print(json.dumps(macros, indent=1))


if __name__ == "__main__":
    main()
