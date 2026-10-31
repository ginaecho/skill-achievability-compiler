"""Evaluation figures for paper/skillachievability.tex.

Every number below is a measured count copied from a report in this
repository; the source file is named next to each block.  Rates are drawn
as 100*(x/n)% with a Wilson 95% interval, and every label states n.

    python paper/figures/eval/make_eval_figures.py

writes fig_usecases.pdf, fig_confusion.pdf, fig_paired.pdf and fig_cost.pdf
(vector, fonts embedded) next to this script, plus PNG previews.
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

OUT = Path(__file__).resolve().parent

# ---------------------------------------------------------------- style
NAVY = "#1F3A5F"      # skillc
AMBER = "#C98A18"     # direct LLM verdict (baseline)
GREEN = "#227850"
RED = "#B23434"
INK = "#1D2430"
MUTED = "#5F6B78"
GRID = "#E3E7EC"
# one accent per use-case category
CAT = {
    "A": ("#2E7D6B", "No LLM in the loop"),
    "B": ("#1F3A5F", "LLM writes the pack; truth by running"),
    "C": ("#7A4E9C", "LLM writes the pack; truth by people"),
    "D": ("#8A6D3B", "Watching a running agent"),
}

mpl.rcParams.update({
    "font.family": "Inter",
    "font.size": 6.8,
    "axes.titlesize": 7.2,
    "axes.titleweight": "semibold",
    "axes.titlelocation": "left",
    "axes.titlepad": 5,
    "axes.labelsize": 6.8,
    "axes.labelcolor": INK,
    "axes.edgecolor": "#C5CCD4",
    "axes.linewidth": 0.6,
    "xtick.color": MUTED,
    "ytick.color": INK,
    "xtick.labelsize": 6.2,
    "ytick.labelsize": 6.4,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0,
    "legend.fontsize": 6.4,
    "legend.frameon": False,
    "pdf.fonttype": 42,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03,
})


def wilson(x: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=240)
    plt.close(fig)


# ================================================================ data
# Each row: (category, label, size, correct, blocked caught, working refuted,
#            baseline correct, baseline caught, baseline refuted)
# A metric is (x, n), or None when it does not apply.
USE_CASES = [
    # --- A: packs read from the environment or written by hand
    ("A", "Hand-written test packs", "15 packs",
     (13, 15), (6, 8), (0, 7), None, None, None),            # skillc eval
    ("A", "Pre-flight in a real workspace", "7 tasks, 3 runs each",
     (21, 21), (12, 12), (0, 9), None, None, None),          # LOCAL_ENVIRONMENT_BENCHMARK.md:44-46
    ("A", "Microsoft Agent 365 workflows", "10 workflows, 123 checks",
     (123, 123), (92, 92), (0, 20), None, None, None),       # AGENT365_CASE_REPORT.md:35-38
    # --- B: public skills, LLM compaction, truth from running each skill blindly
    ("B", "Batch 1 of public skills", "74 skill-runtime pairs",
     (63, 74), (20, 28), (3, 46), None, None, None),         # I2L_BENCHMARK.md (held-out + fresh)
    ("B", "Batch 2", "115 pairs",
     (103, 115), (33, 35), (10, 80), None, None, None),      # LIBRARY_TEST.md, test 2 (ext)
    ("B", "Batch 3, three runtimes", "164 pairs",
     (141, 164), (38, 47), (14, 117), None, None, None),     # DIVERSITY_TEST.md, Q1 (div)
    ("B", "Batch 4", "94 pairs",
     (87, 94), (31, 35), (3, 59), None, None, None),         # P2G_GROUNDED_TEST.md (gr)
    ("B", "All four batches", "447 pairs",
     (394, 447), (122, 145), (30, 302), None, None, None),   # sums of the four rows
    # --- C: public skills, LLM compaction, truth from annotators (session runtime)
    ("C", "Sample 1 of public skills", "100 skills",
     (60, 100), (7, 31), (11, 69), None, None, None),         # COMPACTION_RELIABILITY.md:78 (set2)
    ("C", "Sample 2, labelled blind", "100 skills",
     (64, 100), (7, 18), (20, 82), None, None, None),         # COMPACTION_RELIABILITY.md:303 (set3)
    # --- D: a running agent
    ("D", "Guard on agent traces", "37 hazards, 97 safe steps",
     None, (10, 37), (2, 97), None, None, None),             # INTERACTION_BENCHMARK_REPORT.md:75,176
]


# ================================================================ Figure: use cases
def fig_usecases():
    rows, headers = [], []
    y = 0.0
    last = None
    for case in USE_CASES:
        if case[0] != last:
            y += 0.45 if last else 0.0
            headers.append((case[0], y))
            y += 0.85
            last = case[0]
        rows.append((case, y))
        y += 1.0
    ymax = y - 0.5

    fig = plt.figure(figsize=(5.5, 3.6))
    left, top, bot = 0.345, 0.915, 0.085
    w, gap = 0.200, 0.027
    axes = [fig.add_axes([left + i * (w + gap), bot, w, top - bot]) for i in range(3)]
    titles = ["Correct verdicts", "Blocked cases caught", "Working cases refuted"]
    subt = ["%, higher is better", "%, higher is better", "%, lower is better"]
    cols = [3, 4, 5]
    base_cols = [6, 7, 8]
    xlims = [(0.35, 1.0), (0.0, 1.0), (0.0, 0.36)]
    xticks = [([0.4, 0.6, 0.8, 1.0], ["40", "60", "80", "100"]),
              ([0, 0.25, 0.5, 0.75, 1.0], ["0", "25", "50", "75", "100"]),
              ([0, 0.1, 0.2, 0.3], ["0", "10", "20", "30"])]
    ylo, yhi = -0.9, ymax + 0.15

    def fy(yy):  # data y -> figure fraction
        return bot + (top - bot) * (1 - (yy - ylo) / (yhi - ylo))

    for k, ax in enumerate(axes):
        ax.set_ylim(yhi, ylo)
        span = xlims[k][1] - xlims[k][0]
        ax.set_xlim(*xlims[k])
        ax.set_xticks(*xticks[k])
        ax.set_yticks([])
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.grid(axis="x", color=GRID, lw=0.6, zorder=0)
        ax.set_axisbelow(True)
        ax.set_title(titles[k], fontsize=7.0, pad=9)
        ax.text(0, 1.012, subt[k], transform=ax.transAxes, fontsize=5.4, color=MUTED)
        for (case, yy) in rows:
            colr = CAT[case[0]][0]
            pooled = case[1].startswith("All four")
            ax.axhspan(yy - 0.48, yy + 0.48, color=colr,
                       alpha=0.10 if pooled else 0.045, lw=0, zorder=0)
            m = case[cols[k]]
            if m is None:
                ax.text(xlims[k][0] + span / 2, yy, "not measured", ha="center",
                        va="center", fontsize=5.3, color="#A7B0BA", style="italic")
            else:
                x, n = m
                p = x / n
                lo, hi = wilson(x, n)
                ax.plot([lo, hi], [yy, yy], color=colr, lw=1.8 if pooled else 1.2,
                        alpha=0.40, solid_capstyle="round", zorder=3)
                ax.scatter(p, yy, s=30 if pooled else 19, marker="D" if pooled else "o",
                           color=colr, edgecolor="white", lw=0.6, zorder=5)
                b = case[base_cols[k]]
                right = p < xlims[k][1] - span * 0.16
                if b is not None and b[0] / b[1] > p:
                    right = False
                if p - xlims[k][0] < span * 0.16:
                    right = True
                xt = p + span * (0.045 if right else -0.045)
                ax.text(xt, yy - 0.30, f"{100 * p:.0f}%", va="center",
                        ha="left" if right else "right", fontsize=5.9,
                        color=INK, fontweight="semibold" if pooled else "normal",
                        bbox=dict(boxstyle="square,pad=0.05", fc="white", ec="none",
                                  alpha=0.75), zorder=6)
            b = case[base_cols[k]]
            if b is not None:
                bx, bn = b
                ax.scatter(bx / bn, yy, s=22, marker="D", facecolor="white",
                           edgecolor=AMBER, lw=1.0, zorder=4)

    for cat, yy in headers:
        colr, name = CAT[cat]
        fig.text(0.010, fy(yy), f"{cat}", color="white", fontsize=6.2,
                 fontweight="bold", va="center", ha="center",
                 bbox=dict(boxstyle="round,pad=0.25", fc=colr, ec="none"))
        fig.text(0.030, fy(yy), name, color=colr, fontsize=6.5,
                 fontweight="bold", va="center")
    for case, yy in rows:
        pooled = case[1].startswith("All four")
        fig.text(0.030, fy(yy) + 0.0085, case[1], fontsize=6.25, va="center",
                 color=INK, fontweight="semibold" if pooled else "normal")
        fig.text(0.030, fy(yy) - 0.0145, case[2], fontsize=5.4, va="center",
                 color=MUTED)

    handles = [plt.Line2D([], [], marker="o", ls="-", color=NAVY, alpha=0.9,
                          markersize=4, lw=1.0, markeredgecolor="white")]
    fig.legend(handles, ["skillc's rate; the line is its 95% interval"],
               loc="lower center", ncol=1, bbox_to_anchor=(0.62, -0.02),
               handlelength=1.6)
    # every label must end left of the first panel
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    limit = axes[0].get_window_extent(rend).x0
    for t in fig.texts:
        ext = t.get_window_extent(rend)
        assert ext.x1 < limit - 2, f"label overlaps the plot: {t.get_text()!r}"
    save(fig, "fig_usecases")


# ================================================================ Figure: skillc vs a direct LLM verdict
# Same cases, gpt-5.4.  Accuracy = verdicts matching the truth, over decided cases.
# Tokens and time are per decision; None = not measured.
COMPARE = [
    # name, size, (skillc correct, n), (LLM correct, n), skillc tokens, LLM tokens,
    # skillc seconds, LLM seconds, note on what skillc's tokens are
    ("Real workspace, 7 tasks", "21 runs, no LLM",
     (21, 21), (20, 21), 0, 33047 / 21, 0.03226, 15.18),       # LOCAL_ENVIRONMENT_BENCHMARK.md:44-68
    ("Batches 1 and 4", "168 pairs, run to check",
     (150, 168), (152, 168), 8820, 3471, 0.0082, None),        # I2L_BENCHMARK.md:52-79; checker timed here
    ("Sample 1", "100 skills, people check",
     (60, 100), (77, 100), None, None, None, None),              # COMPACTION_RELIABILITY.md:78-81
    ("Sample 2, blind", "100 skills, people check",
     (64, 100), (74, 100), None, None, None, None),              # COMPACTION_RELIABILITY.md:303-307
]


def fig_compare():
    fig = plt.figure(figsize=(5.5, 1.95))
    left, top, bot = 0.215, 0.80, 0.17
    w, gap = 0.24, 0.025
    axes = [fig.add_axes([left + i * (w + gap), bot, w, top - bot]) for i in range(3)]
    n = len(COMPARE)
    ys = list(range(n))
    titles = ["a  Accuracy", "b  Tokens per decision", "c  Time per decision"]
    subs = ["% of all cases right", "log scale; 0 drawn at left", "log scale, seconds"]
    for k, ax in enumerate(axes):
        ax.set_ylim(n - 0.45, -0.6)
        ax.set_yticks([])
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.grid(axis="x", color=GRID, lw=0.6, zorder=0)
        ax.set_axisbelow(True)
        ax.set_title(titles[k], fontsize=7.0, pad=9)
        ax.text(0, 1.02, subs[k], transform=ax.transAxes, fontsize=5.4, color=MUTED)
        for y in ys:
            ax.axhspan(y - 0.46, y + 0.46, color="#1F3A5F", alpha=0.035, lw=0, zorder=0)
    # a: accuracy
    ax = axes[0]
    ax.set_xlim(0.5, 1.02)
    ax.set_xticks([0.5, 0.75, 1.0], ["50", "75", "100"])
    for y, row in enumerate(COMPARE):
        (sx, sn), (dx, dn) = row[2], row[3]
        sv, dv = sx / sn, dx / dn
        ax.plot([sv, dv], [y, y], color="#C9D1DA", lw=2.2, zorder=2)
        ax.scatter(sv, y, s=30, color=NAVY, zorder=4, edgecolor="white", lw=0.6)
        ax.scatter(dv, y, s=26, marker="D", facecolor="white", edgecolor=AMBER, lw=1.0, zorder=4)
        lo_first = sv <= dv
        ax.text(sv, y - 0.34, f"{100 * sv:.0f}", ha="right" if lo_first else "left",
                fontsize=5.8, color=NAVY, fontweight="semibold")
        ax.text(dv, y - 0.34, f"{100 * dv:.0f}", ha="left" if lo_first else "right",
                fontsize=5.8, color=AMBER)
    # b: tokens (log; zero drawn at the left edge)
    ax = axes[1]
    ax.set_xscale("log")
    ax.set_xlim(60, 30000)
    ax.set_xticks([100, 1000, 10000], ["100", "1k", "10k"])
    ax.minorticks_off()
    for y, row in enumerate(COMPARE):
        st_, dt = row[4], row[5]
        if st_ is None and dt is None:
            ax.text(math.sqrt(60 * 30000), y, "not measured", ha="center", va="center",
                    fontsize=5.3, color="#A7B0BA", style="italic")
            continue
        sp = 60 if st_ == 0 else st_
        ax.plot([sp, dt], [y, y], color="#C9D1DA", lw=2.2, zorder=2)
        ax.scatter(sp, y, s=30, color=NAVY, zorder=4, edgecolor="white", lw=0.6, clip_on=False)
        ax.scatter(dt, y, s=26, marker="D", facecolor="white", edgecolor=AMBER, lw=1.0, zorder=4)
        s_left = sp < dt
        ax.text(sp, y - 0.34, "0" if st_ == 0 else f"{st_:,.0f}",
                ha="left" if st_ == 0 else ("right" if s_left else "left"),
                fontsize=5.8, color=NAVY, fontweight="semibold")
        ax.text(dt, y - 0.34, f"{dt:,.0f}", ha="left" if s_left else "right",
                fontsize=5.8, color=AMBER)
    # c: time (log)
    ax = axes[2]
    ax.set_xscale("log")
    ax.set_xlim(0.003, 60)
    ax.set_xticks([0.01, 0.1, 1, 10], ["10 ms", "0.1 s", "1 s", "10 s"])
    ax.minorticks_off()
    for y, row in enumerate(COMPARE):
        sv, dv = row[6], row[7]
        if sv is None and dv is None:
            ax.text(math.sqrt(0.003 * 60), y, "not measured", ha="center", va="center",
                    fontsize=5.3, color="#A7B0BA", style="italic")
            continue
        if sv is not None and dv is not None:
            ax.plot([sv, dv], [y, y], color="#C9D1DA", lw=2.2, zorder=2)
        if sv is not None:
            ax.scatter(sv, y, s=30, color=NAVY, zorder=4, edgecolor="white", lw=0.6)
            ax.text(sv, y - 0.33, f"{1000 * sv:.0f} ms", ha="left", fontsize=5.8,
                    color=NAVY, fontweight="semibold")
        if dv is not None:
            ax.scatter(dv, y, s=26, marker="D", facecolor="white", edgecolor=AMBER, lw=1.0, zorder=4)
            ax.text(dv, y - 0.33, f"{dv:.0f} s", ha="right", fontsize=5.8, color=AMBER)
        else:
            ax.text(1.0, y, "LLM: not timed", ha="center", va="center", fontsize=5.3,
                    color="#A7B0BA", style="italic")
    def fy(y):
        return bot + (top - bot) * (1 - (y + 0.6) / (n - 0.45 + 0.6))
    for y, row in enumerate(COMPARE):
        fig.text(0.012, fy(y) + 0.035, row[0], fontsize=6.3, color=INK, va="center")
        fig.text(0.012, fy(y) - 0.03, row[1], fontsize=5.3, color=MUTED, va="center")
    handles = [plt.Line2D([], [], marker="o", ls="", color=NAVY, markersize=4.5),
               plt.Line2D([], [], marker="D", ls="", markersize=4,
                          markerfacecolor="white", markeredgecolor=AMBER)]
    fig.legend(handles, ["skillc: verdict with a witness, or a named blocker",
                         "direct LLM verdict: an answer only"],
               loc="lower center", ncol=2, bbox_to_anchor=(0.6, -0.06))
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    limit = axes[0].get_window_extent(rend).x0
    for t in fig.texts:
        assert t.get_window_extent(rend).x1 < limit - 2, f"label overlaps: {t.get_text()!r}"
    save(fig, "fig_compare")


# ================================================================ Figure: confusion matrices
# rows = truth, columns = verdict; counts
CONF = [
    ("a  Hand-written corpus", "15 packs",
     ["achievable", "impossible"], ["ACH", "IMP"],
     [[7, 0], [2, 6]]),                                   # skillc eval
    ("b  Pre-flight workspace", "21 runs",
     ["feasible", "blocked"], ["ACH", "IMP"],
     [[9, 0], [0, 12]]),                                  # LOCAL_ENVIRONMENT_BENCHMARK.md
    ("c  Agent 365, static", "63 checks",
     ["achievable", "impossible", "unknown"], ["ACH", "IMP", "UNK"],
     [[10, 0, 0], [0, 42, 0], [0, 0, 11]]),               # AGENT365_CASE_REPORT.md:36
    ("d  Real skills, executed", "447 pairs",
     ["achieved", "blocked"], ["ACH", "IMP"],
     [[272, 30], [23, 122]]),                             # div + ext + gr + held-out/fresh
    ("e  set3, blind labels", "100 files",
     ["achievable", "blocked"], ["ACH", "IMP", "none"],
     [[57, 20, 5], [10, 7, 1]]),                          # COMPACTION_RELIABILITY.md:303
]


def fig_confusion():
    good = LinearSegmentedColormap.from_list("good", ["#FFFFFF", "#2E7D6B"])
    bad = LinearSegmentedColormap.from_list("bad", ["#FFFFFF", "#B23434"])
    fig = plt.figure(figsize=(5.5, 1.72))
    cw, ch, top = 0.047, 0.168, 0.66
    label_w = 0.082
    x = label_w
    titles = ["a  Corpus", "b  Pre-flight", "c  Agent 365, static",
              "d  Batches 1-4, run", "e  Sample 2, blind"]
    for i, (_, sub, rlab, clab, M) in enumerate(CONF):
        nr, nc = len(M), len(M[0])
        ax = fig.add_axes([x, top - ch * nr, cw * nc, ch * nr])
        for r in range(nr):
            tot = sum(M[r]) or 1
            for c in range(nc):
                v = M[r][c]
                frac = v / tot
                cmap = good if r == c else bad
                colr = cmap(0.18 + 0.82 * frac) if v else "#F4F6F8"
                ax.add_patch(Rectangle((c, r), 1, 1, facecolor=colr,
                                       edgecolor="white", lw=1.3))
                txt = "white" if v and frac > 0.5 else INK
                ax.text(c + 0.5, r + 0.40, f"{v}", ha="center", va="center",
                        fontsize=6.3, fontweight="semibold", color=txt)
                ax.text(c + 0.5, r + 0.77, f"{100 * frac:.0f}%", ha="center",
                        va="center", fontsize=4.6, color=txt)
        ax.set_xlim(0, nc)
        ax.set_ylim(nr, 0)
        ax.set_xticks([c + 0.5 for c in range(nc)], clab, fontsize=5.3)
        ax.xaxis.tick_top()
        ax.set_yticks([r + 0.5 for r in range(nr)], rlab, fontsize=5.3)
        ax.tick_params(length=0, pad=1.5)
        for sp in ax.spines.values():
            sp.set_visible(False)
        fig.text(x - label_w + 0.008, 0.955, titles[i], fontsize=6.3,
                 fontweight="semibold", color=INK, va="top")
        fig.text(x - label_w + 0.008, 0.865, sub, fontsize=5.4, color=MUTED, va="top")
        x += cw * nc + label_w + 0.024
    fig.text(0.5, 0.02, "Rows: truth.  Columns: skillc's verdict "
             "(ACH achievable, IMP impossible, UNK unknown, none: no verdict).  "
             "Percentages are of the row.", ha="center", fontsize=5.3, color=MUTED)
    save(fig, "fig_confusion")


# ================================================================ Figure: paired comparison
# skillc against a direct gpt-5.4 verdict on the same cases
PAIRED = [
    ("Batches 1 and 4 (168 pairs)", (51, 63, 6, 105), (50, 63, 3, 105)),   # I2L_BENCHMARK.md
    ("Sample 1 (100 skills)", (7, 31, 11, 69), (29, 31, 18, 69)),   # COMPACTION_RELIABILITY.md:78-81
    ("Sample 2, blind (100 skills)", (7, 18, 20, 82), (16, 18, 20, 82)),       # COMPACTION_RELIABILITY.md:303,307
]


def fig_paired():
    fig, axes = plt.subplots(1, 2, figsize=(5.5, 1.5), gridspec_kw={"wspace": 0.08})
    for k, ax in enumerate(axes):
        for i, (lab, s, d) in enumerate(PAIRED):
            if k == 0:
                sv, dv = s[0] / s[1], d[0] / d[1]
            else:
                sv, dv = s[2] / s[3], d[2] / d[3]
            ax.plot([sv, dv], [i, i], color="#C9D1DA", lw=2.4, zorder=2,
                    solid_capstyle="round")
            ax.scatter(sv, i, s=30, color=NAVY, zorder=4, edgecolor="white", lw=0.6)
            ax.scatter(dv, i, s=26, marker="D", facecolor="white", edgecolor=AMBER,
                       lw=1.0, zorder=4)
            close = abs(sv - dv) < 0.06
            ax.text(sv, i - 0.33, f"{100 * sv:.0f}%", ha="center", fontsize=5.8,
                    color=NAVY, fontweight="semibold")
            ax.text(dv, i + (0.45 if close else -0.33), f"{100 * dv:.0f}%",
                    ha="center", fontsize=5.8, color=AMBER)
        ax.set_ylim(len(PAIRED) - 0.4, -0.75)
        ax.set_yticks(range(len(PAIRED)), [p[0] for p in PAIRED] if k == 0
                      else [""] * len(PAIRED), fontsize=6.1)
        ax.tick_params(axis="y", length=0)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.grid(axis="x", color=GRID, lw=0.6, zorder=0)
        ax.set_axisbelow(True)
        if k == 0:
            ax.set_xlim(0, 1.05)
            ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0], ["0", "25", "50", "75", "100%"])
            ax.set_title("a  Blocked cases caught (higher is better)")
        else:
            ax.set_xlim(0, 0.32)
            ax.set_xticks([0, 0.1, 0.2, 0.3], ["0", "10", "20", "30%"])
            ax.set_title("b  Working cases refuted (lower is better)")
    handles = [plt.Line2D([], [], marker="o", ls="", color=NAVY, markersize=4.5),
               plt.Line2D([], [], marker="D", ls="", markersize=4,
                          markerfacecolor="white", markeredgecolor=AMBER)]
    fig.legend(handles, ["skillc: verdict with a witness or a named blocker",
                         "direct LLM verdict: no witness"],
               loc="lower center", ncol=2, bbox_to_anchor=(0.55, -0.16))
    save(fig, "fig_paired")


# ================================================================ Figure: cost
# docs/TOKEN_ECONOMICS.md:66-98
def fig_cost():
    fig, axes = plt.subplots(1, 2, figsize=(5.5, 1.75),
                             gridspec_kw={"width_ratios": [1.35, 1.0], "wspace": 0.42})
    ax = axes[0]
    rows = [
        ("blocked: ungated agent run", 9486, 6887, 11554, AMBER),
        ("blocked: compaction + check", 6289, 4857, 8653, NAVY),
        ("working: ungated agent run", 13121, 10450, 18456, AMBER),
        ("working: compaction + check", 5028, 4600, 5787, NAVY),
    ]
    for i, (lab, med, lo, hi, c) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.plot([lo, hi], [y, y], color=c, lw=2.2, alpha=0.35,
                solid_capstyle="round", zorder=3)
        ax.scatter(med, y, s=26, color=c, zorder=4, edgecolor="white", lw=0.6)
        ax.text(hi + 450, y, f"{med:,}", va="center", fontsize=6.0, color=INK)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows][::-1], fontsize=6.2)
    ax.set_xlim(0, 21500)
    ax.set_xticks([0, 5000, 10000, 15000, 20000], ["0", "5k", "10k", "15k", "20k"])
    ax.set_xlabel("tokens per file (median, 95% CI), 31 + 31 files")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="x", color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.set_title("a  Measured tokens per file")

    ax = axes[1]
    left = 0
    for lab, n, c in (("honest stop", 21, GREEN), ("claimed\nsuccess", 10, RED)):
        ax.barh(0, n, 0.5, left=left, color=c, zorder=3)
        ax.text(left + n / 2, 0, f"{lab}\n{100 * n / 31:.0f}%", ha="center",
                va="center", color="white", fontsize=6.0, fontweight="semibold",
                linespacing=1.1)
        left += n
    ax.set_xlim(0, 31)
    ax.set_ylim(-0.6, 0.95)
    ax.set_yticks([])
    ax.set_xticks([0, 10, 20, 31])
    ax.set_xlabel("ungated agent, over 31 blocked files")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.text(0, 0.68, "saving on blocked files: 1.58× [1.01, 2.11]\n"
            "(earlier cost model: 87×)", fontsize=5.9, color=MUTED, va="center")
    ax.set_title("b  How the ungated agent ended")
    save(fig, "fig_cost")


if __name__ == "__main__":
    fig_usecases()
    fig_compare()
    fig_confusion()
    fig_paired()
    fig_cost()
    print("wrote", sorted(p.name for p in OUT.glob("fig_*.pdf")))
