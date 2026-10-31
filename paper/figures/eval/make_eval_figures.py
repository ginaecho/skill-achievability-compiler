"""Evaluation figures for paper/skillachievability.tex.

Every number below is copied from a measured result in this repository; the
source file and line are given next to each block.  Nothing is computed from
a model of runtime cost except where a label says "modelled".

    python paper/figures/eval/make_eval_figures.py

writes fig_*.pdf (vector, fonts embedded) next to this script.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).resolve().parent

# ---------------------------------------------------------------- style
NAVY = "#1F3A5F"      # skillc (the paper's navy)
GREEN = "#227850"     # good outcome
AMBER = "#C98A18"     # LLM baselines
RED = "#B23434"       # bad outcome
STEEL = "#5B7896"     # deterministic baselines
GREY = "#9AA3AD"
LIGHT = "#E9EDF2"
INK = "#1D2430"
MUTED = "#5F6B78"

mpl.rcParams.update({
    "font.family": "Inter",
    "font.size": 7,
    "axes.titlesize": 8,
    "axes.titleweight": "semibold",
    "axes.titlelocation": "left",
    "axes.titlepad": 6,
    "axes.labelsize": 7.5,
    "axes.labelcolor": INK,
    "axes.edgecolor": "#C5CCD4",
    "axes.linewidth": 0.6,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelsize": 6.8,
    "ytick.labelsize": 6.8,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "legend.fontsize": 6.6,
    "legend.frameon": False,
    "pdf.fonttype": 42,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03,
})


def clean(ax, grid_axis="x"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if grid_axis:
        ax.grid(axis=grid_axis, color="#E3E7EC", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=220)
    plt.close(fig)


# ================================================================ Figure A
# What skillc does before and during a run: three measured settings.
def legend_below(ax, handles, labels, ncol=1, y=-0.30):
    ax.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.0, y),
              ncol=ncol, handlelength=0.9, handleheight=0.8, borderaxespad=0,
              columnspacing=1.0, labelspacing=0.35)


def box(c):
    return plt.Rectangle((0, 0), 1, 1, color=c)


def fig_capabilities():
    fig = plt.figure(figsize=(5.5, 2.75))
    # explicit placement keeps the three panels and their legends apart
    axa = fig.add_axes([0.065, 0.38, 0.27, 0.50])
    axb = fig.add_axes([0.50, 0.38, 0.18, 0.50])
    axc = fig.add_axes([0.735, 0.38, 0.21, 0.50])

    # (a) local pre-flight benchmark -- docs/LOCAL_ENVIRONMENT_BENCHMARK.md:44-46
    ax = axa
    methods = ["Plain LLM", "Guided LLM", "skillc"]
    colors = [AMBER, "#E8C27A", NAVY]
    metrics = [("correct\nverdict", [20, 19, 21], 21),
               ("early stop\n(blocked)", [7, 9, 12], 12),
               ("completed\n(feasible)", [9, 8, 9], 9)]
    tokens = ["33,047", "44,724", "0"]
    w = 0.27
    for m, (_, vals, den) in enumerate(metrics):
        for k, v in enumerate(vals):
            x = m + (k - 1) * w
            ax.bar(x, v / den * 100, w * 0.9, color=colors[k], zorder=3)
            ax.text(x, v / den * 100 + 2.5, f"{v}", ha="center", va="bottom",
                    fontsize=5.8, color=INK if k == 2 else MUTED,
                    fontweight="semibold" if k == 2 else "normal")
    ax.set_xticks(range(3), [m[0] for m in metrics])
    ax.tick_params(axis="x", length=0, pad=3)
    ax.set_ylim(0, 115)
    ax.set_yticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    clean(ax, "y")
    ax.set_title("a  Pre-flight, 7 workflows")
    legend_below(ax, [box(c) for c in colors],
                 [f"{m}: {t} tokens" for m, t in zip(methods, tokens)], y=-0.36)

    # (b) one skill, many runtimes -- docs/REAL_SKILLS_REPORT.md:52,73
    ax = axb
    rows = [("claude.ai", 42, 0),
            ("Claude Code\n(exact names)", 24, 18),
            ("Claude Code\n(equivalent names)", 36, 6)]
    for i, (_, ach, imp) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.barh(y, ach, 0.6, color=GREEN, zorder=3)
        ax.barh(y, imp, 0.6, left=ach, color=RED, zorder=3)
        ax.text(ach / 2, y, str(ach), ha="center", va="center", color="white",
                fontsize=6.4, fontweight="semibold")
        if imp:
            ax.text(ach + imp / 2, y, str(imp), ha="center", va="center",
                    color="white", fontsize=6.4, fontweight="semibold")
    ax.set_yticks(range(len(rows)), [r[0] for r in rows][::-1])
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 42)
    ax.set_xticks([0, 21, 42])
    ax.set_xlabel("public SKILL.md files", labelpad=2)
    clean(ax, "x")
    ax.set_title("b  Two runtimes")
    legend_below(ax, [box(GREEN), box(RED)],
                 ["ACHIEVABLE", "IMPOSSIBLE, names the missing tool"],
                 y=-0.36)
    ax.get_legend().set_bbox_to_anchor((-0.62, -0.36))

    # (c) the runtime gate -- docs/AGENT365_CASE_REPORT.md:35-38,
    #     docs/HOSTED_AGENT_COMPARISON.md:131-136
    ax = axc
    items = [  # label, value, denominator, colour, value text
        ("Agent 365: expected verdict", 123, 123, NAVY, "123/123"),
        ("Agent 365: denied calls\nstopped before the tool", 50, 50, NAVY, "50/50"),
        ("Hosted agent, no policy in\nprompt: unapproved sends", 0, 21, NAVY, "0/21"),
        ("same agent, no gate", 2, 21, AMBER, "2/21"),
    ]
    ys = [3.55, 2.35, 0.95, 0.1]
    for (lab, v, den, c, txt), y in zip(items, ys):
        ax.barh(y, 100, 0.34, color=LIGHT, zorder=2)
        ax.barh(y, v / den * 100, 0.34, color=c, zorder=3)
        ax.text(0, y + 0.27, lab, fontsize=5.9, color=INK if c == NAVY else MUTED,
                va="bottom", linespacing=1.15)
        ax.text(101.5, y, txt, fontsize=6.2, va="center",
                color=INK if c == NAVY else MUTED, fontweight="semibold")
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.25, 4.25)
    ax.axis("off")
    ax.set_title("c  As a gate", x=0.0)
    save(fig, "fig_capabilities")


# ================================================================ Figure B
# Real documents with an LLM front-end: recall vs false refutations.
# set2 -- docs/COMPACTION_RELIABILITY.md:78-82 (sample 0, n = 100: 31 BLOCKED, 69 ACHIEVABLE)
# set3 -- docs/COMPACTION_RELIABILITY.md:303-307 (sample 0, n = 100: 18 BLOCKED, 82 ACHIEVABLE)
def fig_tradeoff():
    set2 = [  # name, recall, false-refutation rate, kind
        ("skillc", 7 / 31, 11 / 69, "skillc"),
        ("planner only", 6 / 31, 10 / 69, "det"),
        ("tool lint", 5 / 31, 1 / 69, "det"),
        ("LLM verdict\n(gpt-5.4)", 29 / 31, 18 / 69, "llm"),
        ("LLM verdict\n(DeepSeek)", 29 / 31, 29 / 69, "llm"),
    ]
    set3 = [
        ("skillc, before fixes", 7 / 18, 20 / 82, "skillc_old"),
        ("skillc + fixes", 2 / 18, 1 / 82, "skillc"),
        ("requirement reader", 8 / 18, 7 / 82, "det"),
        ("skillc + fixes\n+ reader", 8 / 18, 8 / 82, "skillc"),
        ("LLM verdict\n(gpt-5.4)", 16 / 18, 20 / 82, "llm"),
    ]
    style = {"skillc": (NAVY, "o", 34), "skillc_old": ("#8FA3BC", "o", 26),
             "det": (STEEL, "s", 24), "llm": (AMBER, "D", 26)}

    fig, axes = plt.subplots(1, 2, figsize=(5.5, 2.45), sharey=True,
                             gridspec_kw={"wspace": 0.12})
    offsets2 = {"skillc": (6, 1), "planner only": (-12, -12), "tool lint": (6, 2),
                "LLM verdict\n(gpt-5.4)": (-22, -20), "LLM verdict\n(DeepSeek)": (-46, 2)}
    offsets3 = {"skillc, before fixes": (5, 4), "skillc + fixes": (4, -12),
                "requirement reader": (-66, -3), "skillc + fixes\n+ reader": (-4, 8),
                "LLM verdict\n(gpt-5.4)": (6, -4)}
    for ax, data, title, offs in (
            (axes[0], set2, "a  set2: 100 real files", offsets2),
            (axes[1], set3, "b  set3: 100 new files, blind labels", offsets3)):
        ax.add_patch(FancyBboxPatch((0, 0.6), 0.10, 0.45,
                                    boxstyle="round,pad=0,rounding_size=0.01",
                                    color="#EAF4EE", zorder=0, lw=0))
        ax.text(0.005, 1.03, "target: catch most,\nrefute few", fontsize=5.8,
                color=GREEN, va="top")
        for name, rec, fr, kind in data:
            c, mk, s = style[kind]
            ax.scatter(fr, rec, s=s, color=c, marker=mk, zorder=4,
                       edgecolor="white", linewidth=0.7)
            dx, dy = offs[name]
            ax.annotate(name, (fr, rec), xytext=(dx, dy),
                        textcoords="offset points", fontsize=5.9,
                        color=INK if kind == "skillc" else MUTED,
                        fontweight="semibold" if kind == "skillc" else "normal")
        ax.set_xlim(-0.01, 0.45)
        ax.set_ylim(-0.03, 1.05)
        ax.set_xticks([0, 0.1, 0.2, 0.3, 0.4], ["0", "10", "20", "30", "40%"])
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0], ["0", "25", "50", "75", "100%"])
        ax.set_xlabel("false IMPOSSIBLE on working files")
        clean(ax, "both")
        ax.set_title(title)
    axes[0].set_ylabel("blocked files caught (recall)")
    # the fix arrow on set3
    axes[1].annotate("", xy=(1 / 82, 2 / 18), xytext=(20 / 82, 7 / 18),
                     arrowprops=dict(arrowstyle="-|>", color="#8FA3BC",
                                     lw=0.9, shrinkA=5, shrinkB=5,
                                     connectionstyle="arc3,rad=-0.25"))
    handles = [plt.Line2D([], [], marker=m, ls="", color=c, markersize=4.5)
               for c, m in ((NAVY, "o"), (STEEL, "s"), (AMBER, "D"))]
    axes[0].legend(handles, ["skillc pipeline", "deterministic baseline",
                             "direct LLM verdict"],
                   loc="upper left", bbox_to_anchor=(0.50, 0.70),
                   handletextpad=0.3, borderaxespad=0.2)
    save(fig, "fig_tradeoff")


# ================================================================ Figure C
# The cost claim, measured -- docs/TOKEN_ECONOMICS.md:66-98
def fig_cost():
    fig, axes = plt.subplots(1, 2, figsize=(5.5, 2.0),
                             gridspec_kw={"width_ratios": [1.3, 1.0], "wspace": 0.45})
    ax = axes[0]
    rows = [  # label, median, lo, hi, color
        ("blocked: ungated agent run", 9486, 6887, 11554, AMBER),
        ("blocked: compaction + check", 6289, 4857, 8653, NAVY),
        ("working: ungated agent run", 13121, 10450, 18456, AMBER),
        ("working: compaction + check", 5028, 4600, 5787, NAVY),
    ]
    for i, (lab, med, lo, hi, c) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.plot([lo, hi], [y, y], color=c, lw=2.2, alpha=0.35,
                solid_capstyle="round", zorder=3)
        ax.scatter(med, y, s=30, color=c, zorder=4, edgecolor="white", lw=0.7)
        ax.text(hi + 400, y, f"{med:,}", va="center", fontsize=6.2, color=INK)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows][::-1])
    ax.set_xlim(0, 21500)
    ax.set_xticks([0, 5000, 10000, 15000, 20000], ["0", "5k", "10k", "15k", "20k"])
    ax.set_xlabel("tokens per file (median, 95% CI)")
    clean(ax, "x")
    ax.set_title("a  Measured tokens per file")

    ax = axes[1]
    outcomes = [("honest stop", 21, GREEN), ("claimed\nsuccess", 10, RED)]
    left = 0
    for lab, n, c in outcomes:
        ax.barh(0, n, 0.5, left=left, color=c, zorder=3)
        ax.text(left + n / 2, 0, f"{lab}\n{n}/31", ha="center", va="center",
                color="white", fontsize=6.0, fontweight="semibold", linespacing=1.1)
        left += n
    ax.set_xlim(0, 31)
    ax.set_ylim(-0.6, 0.9)
    ax.set_yticks([])
    ax.set_xticks([0, 10, 20, 31])
    ax.set_xlabel("31 blocked files")
    clean(ax, "x")
    ax.text(0, 0.62, "saving on blocked files: 1.58\u00d7 [1.01, 2.11]\n"
            "(earlier cost model: 87\u00d7)", fontsize=6.0, color=MUTED,
            va="center")
    ax.set_title("b  Ungated agent, blocked files")
    save(fig, "fig_cost")


if __name__ == "__main__":
    fig_capabilities()
    fig_tradeoff()
    fig_cost()
    print("wrote", sorted(p.name for p in OUT.glob("fig_*.pdf")))
