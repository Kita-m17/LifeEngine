"""Fills the blank results slides of the group's Canva deck with slow-regen figures and numbers.

Reads the deck PDF, draws the stat cards, captions and figures onto its five blank results slides (Does the claw evolve
and spread? / Do claws cause extinction or prevent it? / How does the soil shape the risk? / Mis-adaptation or failure
to adapt? / Does how fast soil heals decide the outcome?) at the positions of their placeholder boxes, and drops the
older filled copies of those slides. Every number is computed from the runs. Figures are written in the deck's sizes as
PDF (vector), SVG and 300 dpi PNG, for placing in Canva.

Usage:
    python analysis/slow_regen_deck.py ["Presentation Final/ARTIFICIAL LIFE - LIFE ENGINE.pdf"]
        [--root Observations/slow-regen-runs] [--cache DIR] [--out "Presentation Final/output"]
"""
import argparse
import io
import os
import sys
import warnings
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynamics_analysis as A  # noqa: E402
import dynamics_load  # noqa: E402
import slow_regen_analysis as S  # noqa: E402
from dynamics_analysis import SETS, LAYOUTS, TICKS, k, stack, group, fisher  # noqa: E402
from slow_regen_analysis import REGENS, PATHWAYS, PATH_COLORS  # noqa: E402

W, H = 1440, 817.92  # deck page width, and the top of its media box (Canva offsets it by 7.92 pt)
# deck colours
ORANGE, BLUE, GOLD, LAVENDER, GREEN = "#ff6b35", "#60d4ff", "#deb14d", "#b4b9e8", "#1fdc6a"
INK, MUTED, CARD, INNER, EDGE, YELLOW = "#e6edf3", "#8b98a8", "#141c25", "#121a22", "#2d3642", "#fcd56b"
# the same identities, dark enough to read on the white figure cards
SET_COLORS = {"main": "#f0561d", "noclaw": "#7179c4", "nocost": "#1a92cc"}
SET_LABELS = {"main": "Main (claws, burrowing costs soil)", "noclaw": "No-claw control",
              "nocost": "Free burrowing"}
SET_SHORT = {"main": "Main", "noclaw": "No-claw", "nocost": "Free burrowing"}
REGEN_COLORS = {rg: plt.get_cmap("Oranges")(0.5 + 0.5 * i / 3) for i, rg in enumerate(REGENS)}
LAYOUT_COLORS = {"dense": "#5c3a0e", "medium": "#a8742c", "sparse": "#dcb57a"}
ROLE_COLORS = {"plants": "#1a9a3c", "pred": "#e0287a", "prey": "#1a92cc", "claw": "#f0561d"}
OUTCOMES = ["took over, then all prey died", "took over, then fell back", "took over and persisted",
            "never took over"]
OUTCOME_COLORS = dict(zip(OUTCOMES, ["#f0561d", "#deb14d", "#1a92cc", "#4a5563"]))
OUTCOME_MAP = {"took over, then the group died out": OUTCOMES[0], "took over, then fell back below half": OUTCOMES[1],
               "took over and persisted": OUTCOMES[2], "never took over": OUTCOMES[3],
               "group died out, never took over": OUTCOMES[3]}
FONTS = "/System/Library/Fonts/Supplemental/"


def style():
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
                         "font.size": 14, "axes.titlesize": 15, "axes.titleweight": "bold", "axes.labelsize": 14,
                         "xtick.labelsize": 13, "ytick.labelsize": 13, "legend.fontsize": 13,
                         "legend.frameon": False, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#555", "axes.grid": True, "grid.color": "#e6e6e3", "grid.linewidth": 0.8,
                         "axes.axisbelow": True, "lines.linewidth": 2.4, "pdf.fonttype": 42, "svg.fonttype": "path",
                         "savefig.bbox": None, "figure.dpi": 100})


def save(fig, folder, name):
    for ext, kw in (("pdf", {}), ("svg", {}), ("png", {"dpi": 300})):
        fig.savefig(os.path.join(folder, f"{name}.{ext}"), **kw)
    plt.close(fig)
    return os.path.join(folder, f"{name}.pdf")


def alive_share(runs):
    return 100 * stack(runs, lambda r: r["alive"].astype(float)).mean(axis=0)


# ---- figures, each sized to its box on the slide (points / 72 = inches) -------------------------------------------

def fig_takeover(runs, folder, size):
    fig, ax = plt.subplots(figsize=size, layout="constrained")
    x = k(TICKS)
    for s, dy in (("main", 6), ("nocost", 16)):
        takes = np.array([r["claw_take"] if r["claw_take"] is not None else np.inf for r in group(runs, set=s)])
        ax.plot(x, [100 * np.mean(takes <= t) for t in TICKS], color=SET_COLORS[s],
                ls="-" if s == "main" else "--", label=f"{SET_LABELS[s]}: {np.isfinite(takes).sum()} of 180")
        med = np.median(takes[np.isfinite(takes)])
        ax.axvline(med / 1000, color=SET_COLORS[s], lw=1.2, ls=":")
        ax.text(med / 1000 + 1.5, dy, f"median {med:,.0f}", color=SET_COLORS[s], fontsize=13)
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 100)
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("runs where the claw\nhas taken over (%)")
    ax.legend(loc="upper left")
    return save(fig, folder, "slide7_claw_takeover")


def fig_extinction(runs, folder, size):
    fig, axes = plt.subplots(1, 2, figsize=size, layout="constrained", gridspec_kw={"width_ratios": [1.15, 1]})
    ax = axes[0]
    w = 0.27
    for i, s in enumerate(SETS):
        vals = [sum(r["extinct"] for r in group(runs, set=s, regen=rg)) for rg in REGENS]
        bars = ax.bar(np.arange(4) + (i - 1) * w, vals, w - 0.03, color=SET_COLORS[s], label=SET_SHORT[s])
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.6, str(v), ha="center", va="bottom", fontsize=11.5,
                    color="#333")
    ax.set_xticks(range(4), [f"{rg}%" for rg in REGENS])
    ax.set_xlabel("soil regrowth chance per tick")
    ax.set_ylabel("worlds extinct (of 45)")
    ax.set_ylim(0, 49)
    ax.grid(axis="x", visible=False)
    ax.set_title("Extinctions by regrowth rate", loc="left")
    ax.legend(loc="upper right", fontsize=12)
    ax = axes[1]
    x = k(TICKS)
    for s in SETS:
        ax.plot(x, alive_share(group(runs, set=s)), color=SET_COLORS[s], ls={"main": "-", "noclaw": "--",
                                                                             "nocost": ":"}[s], label=SET_SHORT[s])
    ax.set_xlim(0, 250)
    ax.set_ylim(0, 102)
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("worlds still alive (%)")
    ax.set_title("Survival over time", loc="left")
    ax.legend(loc="lower left", fontsize=12)
    return save(fig, folder, "slide8_extinctions")


def fig_soil(runs, folder, size):
    fig, axes = plt.subplots(1, 2, figsize=size, layout="constrained")
    ax = axes[0]
    for i, rg in enumerate(REGENS):
        for j, lay in enumerate(LAYOUTS):
            g = group(runs, set="main", regen=rg, layout=lay)
            xs = i + (j - 1) * 0.26 + np.linspace(-0.08, 0.08, len(g))
            for xx, r in zip(xs, g):
                ax.plot(xx, r["fert_min"], "x" if r["extinct"] else "o", ms=6, color=LAYOUT_COLORS[lay],
                        mew=1.6 if r["extinct"] else 0.6, mec=LAYOUT_COLORS[lay] if r["extinct"] else "white")
        med = np.median([r["fert_min"] for r in group(runs, set="main", regen=rg)])
        ax.plot([i - 0.42, i + 0.42], [med, med], color="#222", lw=2)
        ax.text(i, 23, f"{med:.0f}%", ha="center", fontsize=12.5, fontweight="bold", color="#222")
    handles = [plt.Line2D([], [], color=LAYOUT_COLORS[lay], marker="s", ls="", ms=8) for lay in LAYOUTS]
    handles += [plt.Line2D([], [], color="#555", marker=m, ls="", ms=7) for m in ("o", "x")]
    ax.legend(handles, LAYOUTS + ["survived", "extinct"], loc="lower right", ncol=2, fontsize=11.5,
              bbox_to_anchor=(1, 0.08), handletextpad=0.2, columnspacing=0.8)
    ax.set_xticks(range(4), [f"{rg}%" for rg in REGENS])
    ax.set_xlabel("soil regrowth chance per tick")
    ax.set_ylabel("lowest soil fertility (% of start)")
    ax.set_ylim(18, 102)
    ax.grid(axis="x", visible=False)
    ax.set_title("Lowest fertility per main world", loc="left")
    ax = axes[1]
    idx = np.arange(0, 1001, 25)
    for rg in REGENS:
        med = [np.median(v) if len(v := S.plant_ratio(runs, rg, i)) >= 8 else np.nan for i in idx]
        ax.plot(k(TICKS[idx]), med, color=REGEN_COLORS[rg], label=f"{rg}%")
    ax.axhline(100, color="#555", lw=1)
    ax.axvline(60, color="#999", lw=1, ls=":")
    ax.set_ylim(0, 112)
    ax.set_xlim(0, 100)
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("plants, % of free-burrowing twin")
    ax.set_title("Plants lost to burrowing (main)", loc="left")
    ax.legend(title="regrowth", loc="lower left", ncol=2, fontsize=11.5, title_fontsize=12)
    return save(fig, folder, "slide9_soil")


def fig_adapt(runs, folder, size):
    fig, axes = plt.subplots(2, 1, figsize=size, layout="constrained", gridspec_kw={"height_ratios": [1, 1.25]})
    ax = axes[0]
    for i, s in enumerate(["main", "nocost"]):
        c = Counter(OUTCOME_MAP[r["claw_outcome"]] for r in group(runs, set=s))
        left = 0
        for o in OUTCOMES:
            v = c.get(o, 0)
            if v:
                ax.barh(i, v, left=left, color=OUTCOME_COLORS[o], edgecolor="white", linewidth=2, height=0.66)
                if v >= 6:
                    ax.text(left + v / 2, i, str(v), ha="center", va="center", fontsize=13, fontweight="bold",
                            color="white")
            left += v
    ax.set_yticks([0, 1], ["Main", "Free\nburrowing"])
    ax.invert_yaxis()
    ax.set_xlim(0, 180)
    ax.set_xlabel("runs (of 180)")
    ax.grid(axis="y", visible=False)
    ax.set_title("What happened after the claw evolved", loc="left")
    handles = [plt.Rectangle((0, 0), 1, 1, color=OUTCOME_COLORS[o]) for o in OUTCOMES]
    ax.legend(handles, OUTCOMES, loc="upper left", bbox_to_anchor=(0, -0.42), ncol=2, fontsize=12,
              handlelength=1.1, columnspacing=1.2)
    ax = axes[1]
    w = 0.27
    for i, s in enumerate(SETS):
        vals = [sum(r["extinct"] for r in group(runs, set=s, layout=lay)) for lay in LAYOUTS]
        bars = ax.bar(np.arange(3) + (i - 1) * w, vals, w - 0.03, color=SET_COLORS[s], label=SET_SHORT[s])
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.8, str(v), ha="center", va="bottom", fontsize=12,
                    color="#333")
    ax.set_xticks(range(3), [f"{lay} maps" for lay in LAYOUTS])
    ax.set_ylabel("worlds extinct (of 60)")
    ax.set_ylim(0, 68)
    ax.grid(axis="x", visible=False)
    ax.set_title("Extinctions by soil layout", loc="left")
    ax.legend(loc="upper left", fontsize=12)
    return save(fig, folder, "slide10_adaptation")


def fig_heal(run, folder, name, size):
    fig, axes = plt.subplots(3, 1, figsize=size, sharex=True, layout="constrained",
                             gridspec_kw={"height_ratios": [2, 1, 1]})
    n = len(run["s"]["t"])
    x = k(TICKS[:n])
    ax = axes[0]
    names = {"plants": "plants", "pred": "predators", "prey": "prey", "claw": "clawed prey"}
    for role in ["plants", "pred", "prey", "claw"]:
        ax.plot(x, run["pop"][role][:n], color=ROLE_COLORS[role], lw=1.3, ls="--" if role == "prey" else "-",
                label=names[role])
    ax.set_yscale("symlog", linthresh=10)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("organisms")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 0.98), ncol=4, fontsize=11.5, handlelength=1.4,
              columnspacing=1.0)
    ax = axes[1]
    ax.plot(x, 100 * run["claw_share"][:n], color=ROLE_COLORS["claw"], lw=1.6)
    ax.set_ylim(0, 105)
    ax.set_ylabel("clawed\n(% of prey)")
    ax = axes[2]
    ax.plot(x, run["fert"][:n], color="#8a5a19", lw=2.2)
    ax.set_ylim(35, 103)
    ax.set_ylabel("soil fertility\n(% of start)")
    ax.set_xlabel("tick (thousands)")
    ax.set_xlim(0, 250)
    for a in axes:
        if run["claw_take"] is not None:
            a.axvline(run["claw_take"] / 1000, color="#888", lw=1, ls="--")
        if run["extinct"]:
            a.axvline(run["end_tick"] / 1000, color="#222", lw=1, ls=":")
    for a in axes:
        a.tick_params(labelsize=11.5)
        a.yaxis.label.set_size(12)
    axes[2].xaxis.label.set_size(12)
    return save(fig, folder, name)


# ---- slide drawing -------------------------------------------------------------------------------------------------

class Slide:
    """reportlab overlay in deck coordinates (origin top-left, points)."""

    def __init__(self):
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=(W, H))
        self.figs = []

    def box(self, x, y, w, h, fill, stroke=None, r=6, lw=1.4):
        c = self.c
        c.setFillColor(fill)
        if stroke:
            c.setStrokeColor(stroke)
            c.setLineWidth(lw)
        c.roundRect(x, H - y - h, w, h, r, stroke=1 if stroke else 0, fill=1)

    def text(self, x, y, segments, width=None, leading=None, align="left"):
        """segments: [(text, font, size, colour)], wrapped by words within width; y is the first baseline."""
        words = [(wd, f, s, col) for t, f, s, col in segments for wd in t.split(" ") if wd]
        lines, line, lw_ = [], [], 0
        for wd, f, s, col in words:
            ww = pdfmetrics.stringWidth(wd + " ", f, s)
            if width and line and lw_ + pdfmetrics.stringWidth(wd, f, s) > width:
                lines.append(line)
                line, lw_ = [], 0
            line.append((wd, f, s, col))
            lw_ += ww
        lines.append(line)
        size = max(s for _, _, s, _ in words)
        leading = leading or size * 1.2
        for i, ln in enumerate(lines):
            total = sum(pdfmetrics.stringWidth(wd + " ", f, s) for wd, f, s, _ in ln)
            xx = x - total / 2 if align == "center" else x
            for wd, f, s, col in ln:
                self.c.setFont(f, s)
                self.c.setFillColor(col)
                self.c.drawString(xx, H - (y + i * leading), wd)
                xx += pdfmetrics.stringWidth(wd + " ", f, s)
        return y + (len(lines) - 1) * leading

    def sup_line(self, x, y, parts, size):
        """One line of (text, colour[, superscript]) parts."""
        for part in parts:
            t, col, sup = (part + (False,))[:3]
            sz = size * 0.62 if sup else size
            self.c.setFont("Arial", sz)
            self.c.setFillColor(col)
            self.c.drawString(x, H - y + (size * 0.4 if sup else 0), t)
            x += pdfmetrics.stringWidth(t, "Arial", sz)

    def figure(self, path, x, y, w, h, pad=8, bg="#ffffff", bleed=0):
        self.box(x - bleed, y - bleed, w + 2 * bleed, h + 2 * bleed, bg, r=8)
        self.figs.append((path, x + pad, y + pad, w - 2 * pad, h - 2 * pad))

    def stat_card(self, x, y, w, h, number, colour, body, sub=None):
        self.box(x, y, w, h, CARD, EDGE)
        size = min(40, 40 * (w - 48) / pdfmetrics.stringWidth(number, "Arial-Bold", 40))
        self.text(x + 24, y + 58, [(number, "Arial-Bold", size, colour)])
        end = self.text(x + 24, y + 90, [(body, "Arial", 21, INK)], width=w - 44, leading=25)
        if sub:
            self.text(x + 24, end + 23, [(sub, "Arial", 15.5, MUTED)], width=w - 44, leading=19)

    def apply(self, page):
        self.c.showPage()
        self.c.save()
        self.buf.seek(0)
        page.merge_page(PdfReader(self.buf).pages[0])
        for path, x, y, w, h in self.figs:
            fp = PdfReader(path).pages[0]
            fw, fh = float(fp.mediabox.width), float(fp.mediabox.height)
            sc = min(w / fw, h / fh)
            tx, ty = x + (w - fw * sc) / 2, H - y - h + (h - fh * sc) / 2
            page.merge_transformed_page(fp, Transformation().scale(sc).translate(tx, ty))


def left_cards(sl, cards):
    for top, card in zip((189, 373, 556), cards):
        sl.stat_card(72, top, 454, 146, *card)


def right_panel(sl, fig, caption):
    sl.box(569, 189, 799, 513, CARD, EDGE)
    sl.figure(fig, 585, 203, 767, 400)
    sl.text(585, 640, caption, width=767, leading=29)


# ---- numbers -------------------------------------------------------------------------------------------------------

def numbers(runs):
    d = {}
    ext = {s: [r for r in group(runs, set=s) if r["extinct"]] for s in SETS}
    for s in SETS:
        d[f"ext_{s}"] = len(ext[s])
        d[f"ext_{s}_by_rate"] = [sum(r["extinct"] for r in group(runs, set=s, regen=rg)) for rg in REGENS]
        for lay in LAYOUTS:
            d[f"ext_{s}_{lay}"] = sum(r["extinct"] for r in group(runs, set=s, layout=lay))
            d[f"ext_{s}_{lay}_by_rate"] = [sum(r["extinct"] for r in group(runs, set=s, layout=lay, regen=rg))
                                           for rg in REGENS]
        oc = Counter(OUTCOME_MAP[r["claw_outcome"]] for r in group(runs, set=s))
        d[f"suicide_{s}"] = oc.get(OUTCOMES[0], 0)
        d[f"pathways_{s}"] = dict(Counter(r["pathway"] for r in ext[s]))
    for s in ["main", "nocost"]:
        takes = [r["claw_take"] for r in group(runs, set=s) if r["claw_take"] is not None]
        d[f"take_n_{s}"], d[f"take_med_{s}"] = len(takes), float(np.median(takes))
    e = {s: d[f"ext_{s}"] for s in SETS}
    p = lambda a, b: fisher(e[a], 180 - e[a], e[b], 180 - e[b])
    d["p"] = {"main_nocost": p("main", "nocost"), "main_noclaw": p("main", "noclaw"),
              "noclaw_nocost": p("noclaw", "nocost")}
    d["fert_min_by_rate"] = [float(np.median([r["fert_min"] for r in group(runs, set="main", regen=rg)]))
                             for rg in REGENS]
    d["plants60_by_rate"] = [float(np.median(S.plant_ratio(runs, rg, 600))) for rg in REGENS]
    d["recovery"] = {rg: S.MIN_PLANT_FERTILITY / (float(rg) / 100) for rg in REGENS}
    return d


def sci(p):
    m, e = f"{p:.0e}".split("e")
    return f"{m}×10^{int(e)}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", nargs="?", default="Presentation Final/ARTIFICIAL LIFE - LIFE ENGINE.pdf")
    ap.add_argument("--root", default="Observations/slow-regen-runs")
    ap.add_argument("--cache")
    ap.add_argument("--out", default="Presentation Final/output")
    a = ap.parse_args()
    figs = os.path.join(a.out, "figures")
    os.makedirs(figs, exist_ok=True)
    pdfmetrics.registerFont(TTFont("Arial", FONTS + "Arial.ttf"))
    pdfmetrics.registerFont(TTFont("Arial-Bold", FONTS + "Arial Bold.ttf"))
    A.style()
    style()
    A.REGENS, A.PATHWAYS, A.PATH_COLORS = REGENS, PATHWAYS, PATH_COLORS
    warnings.simplefilter("ignore", RuntimeWarning)
    runs = [S.prepare(r) for r in dynamics_load.load_all(a.root, a.cache or os.path.join(a.out, "cache"))]
    d = numbers(runs)
    by_name = {r["name"]: r for r in runs}
    crash = min((r for r in group(runs, set="main", layout="dense", regen="0.01") if r["extinct"]),
                key=lambda r: r["fert_min"])
    fast = by_name[f"main-dense_soilRegenRate=0.1_seed1_soil{crash['soil']}_rep{crash['rep']}"]

    inch = lambda w, h: (w / 72, h / 72)
    f7 = fig_takeover(runs, figs, inch(751, 384))
    f8 = fig_extinction(runs, figs, inch(751, 384))
    f9 = fig_soil(runs, figs, inch(751, 384))
    f10 = fig_adapt(runs, figs, inch(725, 514))
    f11a = fig_heal(crash, figs, "slide11_slow_soil", inch(514, 314))
    f11b = fig_heal(fast, figs, "slide11_fast_soil", inch(514, 314))

    reader = PdfReader(a.deck)
    pages = reader.pages
    # page index (0-based) of each blank results slide, and the older filled copy it replaces
    blank = {"claw": 7, "extinction": 9, "soil": 11, "adapt": 13, "heal": 15}
    old = [6, 8, 10, 12, 14]
    rg = lambda v: f"{v:g}"
    em, en = "–", "·"

    sl = Slide()
    left_cards(sl, [
        (f"{d['take_n_main']} of 180", ORANGE, "main runs: the claw evolved by mutation and took over the prey"),
        (f"{d['take_med_main']:,.0f} vs {d['take_med_nocost']:,.0f}", BLUE,
         "median take-over tick, main vs free burrowing"),
        ("Soil cost didn't slow it", GOLD, "the claw spreads just as fast either way")])
    right_panel(sl, f7, [("Claw take-over across all runs", "Arial-Bold", 23, BLUE),
                         (f" {en} {d['take_n_nocost']} of 180 with free burrowing", "Arial", 21, INK)])
    sl.apply(pages[blank["claw"]])

    sl = Slide()
    r = d["ext_main_by_rate"]
    left_cards(sl, [
        (f"{d['ext_main']} of 180", ORANGE, "main worlds went extinct",
         f"{r[0]}, {r[1]}, {r[2]} and {r[3]} of 45 from 0.01% to 0.1%"),
        (f"{d['ext_noclaw']} of 180", LAVENDER, "no-claw control worlds went extinct"),
        (f"{d['ext_nocost']} of 180", BLUE, "free-burrowing worlds went extinct")])
    p = d["p"]
    sl.box(569, 189, 799, 513, CARD, EDGE)
    sl.figure(f8, 585, 203, 767, 400)
    sl.text(585, 636, [("Claws prevent extinction when burrowing is free, and cause it when it damages the soil.",
                        "Arial-Bold", 21, INK)], width=767, leading=25)
    parts = []
    for (a_, ca), (b_, cb), key in ((("Main", ORANGE), ("free burrowing", BLUE), "main_nocost"),
                                    (("Main", ORANGE), ("no claws", LAVENDER), "main_noclaw"),
                                    (("No claws", LAVENDER), ("free burrowing", BLUE), "noclaw_nocost")):
        m, e = sci(p[key]).split("^")
        parts += [(a_, ca), (" vs ", MUTED), (b_, cb), (f": p = {m}", MUTED), (f"\u2212{-int(e)}", MUTED, True),
                  ("    ", MUTED)]
    sl.sup_line(585, 690, parts[:-1], 14.5)
    sl.apply(pages[blank["extinction"]])

    sl = Slide()
    fm, pl = d["fert_min_by_rate"], d["plants60_by_rate"]
    left_cards(sl, [
        (f"{fm[0]:.0f}{em}{fm[-1]:.0f}%", ORANGE, "of starting fertility at the median low in main",
         "0.01% to 0.1% regrowth; control soil stays at 100%"),
        (f"{min(pl[:2]):.0f}{em}{max(pl[:2]):.0f}%", GREEN,
         "plants vs free burrowing at tick 60,000 (slowest rates)"),
        ("Layout sets the baseline", GOLD,
         f"sparse maps die in every set; main also loses {d['ext_main_dense']} of 60 dense, "
         f"{d['ext_main_medium']} of 60 medium")])
    right_panel(sl, f9, [("Main only: ", "Arial-Bold", 21, INK),
                         ("lowest soil fertility per world, and plants relative to the same map with free burrowing",
                          "Arial", 21, MUTED)])
    sl.apply(pages[blank["soil"]])

    sl = Slide()
    sl.figure(f10, 72, 189, 745, 534, pad=10, bleed=2)
    sl.box(880, 262, 458, 162, INNER)
    sl.text(906, 318, [(f"{d['ext_noclaw_sparse']} of {d['ext_noclaw']}", "Arial-Bold", 50, INK)])
    sl.text(906, 356, [("no-claw extinctions were on sparse soil: predator–prey crashes with no claw to escape",
                        "Arial", 19, MUTED)], width=420, leading=23)
    sl.box(880, 543, 458, 162, INNER)
    sl.text(906, 599, [(f"{d['suicide_main']} vs {d['suicide_nocost']}", "Arial-Bold", 50, INK)])
    sl.text(906, 637, [("worlds where the claw took over, then every prey died: with vs without soil damage",
                        "Arial", 19, MUTED)], width=420, leading=23)
    sl.apply(pages[blank["adapt"]])

    sl = Slide()
    rc = d["recovery"]
    for x, run, colour, head, tail, f in (
            (104, crash, ORANGE, f"{d['ext_main_by_rate'][0]} of 45 extinct",
             f" {en} 0.01%: a burrow takes ~{rc['0.01']:,.0f} ticks to heal", f11a),
            (774, fast, BLUE, f"{d['ext_main_by_rate'][3]} of 45 extinct",
             f" {en} 0.1%: heals in ~{rc['0.1']:,.0f} ticks; dense maps all survive"
             if d["ext_main_dense_by_rate"][3] == 0 else f" {en} 0.1%: heals in ~{rc['0.1']:,.0f} ticks", f11b)):
        sl.box(x - 2, 268, 566, 430, CARD, EDGE)
        sl.text(x + 14, 297, [(head, "Arial-Bold", 18, colour), (tail, "Arial", 18, INK)], width=534, leading=22)
        sl.figure(f, x + 16, 334, 530, 352, pad=8)
    sl.text(W / 2, 760, [(f"Same map ({crash['map']}, replicate {crash['rep']}), same claw, same burrowing: "
                          "only the healing speed differs", "Arial-Bold", 24, YELLOW)], align="center")
    sl.apply(pages[blank["heal"]])

    writer = PdfWriter()
    for i, page in enumerate(pages):
        if i not in old:
            writer.add_page(page)
    out = os.path.join(a.out, "ARTIFICIAL LIFE - LIFE ENGINE (results filled).pdf")
    with open(out, "w+b") as f:
        writer.write(f)
    import json
    with open(os.path.join(a.out, "numbers.json"), "w") as f:
        json.dump(d, f, indent=1, default=float)
    print(out)


if __name__ == "__main__":
    main()
