"""Builds a growth-rate slide for the group's Canva deck: populations look stable right up to the collapse.

For every main world that went extinct (leaving out the early boom-bust crashes), lines the run up on the tick its last
prey died and plots the median growth rate of plants, prey and predators, with soil fertility on the same time axis.
Growth sits at zero (births match deaths) for most of a doomed world's life and only turns negative in the last few
thousand ticks, while the soil has been falling for tens of thousands of ticks before that.

Writes, in the deck's style and sizes:
  figures/slide_growth_rate.{pdf,svg,png}   the figure, for placing in Canva
  slide_growth_rate.{pdf,png}               the finished slide on its own
  <deck> (growth slide).pdf                 the deck with the slide inserted after --after
  growth_numbers.json                       every number on the slide

Definitions:
  growth rate   (births - deaths) / population over a trailing 2,000-tick window, as % per 1,000 ticks; prey counts
                plain and clawed prey together
  final decline the stretch after the last window in which prey births kept up with deaths, to the last prey
  soil warning  ticks between soil fertility first falling below 90% of its start and the last prey; and the soil
                fertility left when the final decline began

Usage:
    python analysis/growth_rate_slide.py ["Presentation Final/ARTIFICIAL LIFE - LIFE ENGINE 2.pdf"] [--after 9]
        [--root Observations/slow-regen-runs] [--cache DIR] [--out "Presentation Final/output"]
"""
import argparse
import json
import os
import subprocess
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynamics_analysis as A  # noqa: E402
import dynamics_load  # noqa: E402
import slow_regen_analysis as S  # noqa: E402
import slow_regen_deck as D  # noqa: E402
from dynamics_analysis import N, k, group, pad, window_sum  # noqa: E402
from slow_regen_deck import W, H, ORANGE, BLUE, GOLD, INK, MUTED, Slide, left_cards, right_panel  # noqa: E402

WIN = 20  # samples (2,000 ticks)
SPAN = 600  # samples (60,000 ticks) shown before the last prey
SOIL_WARN = 90  # % of starting fertility
ROLE_KEYS = {"plants": ["plants"], "prey": ["prey", "claw"], "pred": ["pred"]}
ROLE_LABELS = {"plants": "plants", "prey": "prey (with and without claw)", "pred": "predators"}
ROLE_COLORS = {"plants": D.ROLE_COLORS["plants"], "prey": D.ROLE_COLORS["prey"], "pred": D.ROLE_COLORS["pred"]}
BG, GRID = "#0e1318", "#16202a"


def growth(run, roles):
    """% per 1,000 ticks over a trailing WIN window; NaN once the world is dead or the group averages under 10."""
    s = run["s"]
    b, d, p = (sum(pad(s[f"{r}_{f}"], 0.0) for r in roles) for f in ("births", "deaths", "population"))
    sb, sd, sp = window_sum(b, WIN), window_sum(d, WIN), window_sum(p, WIN)
    return np.where((sp >= 10 * WIN) & run["alive"], 1000 * (sb - sd) / sp, np.nan)


def aligned(run, series):
    """series[-SPAN..0] samples around the last prey."""
    idx = run["last_prey"] // 100 + np.arange(-SPAN, 1)
    ok = (idx >= 0) & (idx < N)
    y = np.full(len(idx), np.nan)
    y[ok] = series[idx[ok]]
    return y


def collapsed(runs, s):
    return [r for r in group(runs, set=s) if r["extinct"] and r["pathway"] != "early boom-bust"]


def numbers(runs):
    d = {"early_excluded": sum(1 for r in group(runs, set="main") if r["extinct"]) - len(collapsed(runs, "main"))}
    for s in A.SETS:
        g = collapsed(runs, s)
        decline, life_share, warn, soil_at = [], [], [], []
        for r in g:
            end = r["last_prey"] // 100
            gp = growth(r, ROLE_KEYS["prey"])[:end + 1]
            kept_up = np.where(gp >= 0)[0]
            last = kept_up[-1] if len(kept_up) else 0
            decline.append((end - last) * 100)
            soil_at.append(r["fert"][last])
            life_share.append((end - last) / max(end, 1))
            below = np.where(r["fert"][:end + 1] < SOIL_WARN)[0]
            if len(below):
                warn.append((end - below[0]) * 100)
        d[s] = {"worlds": len(g), "decline_median": float(np.median(decline)),
                "decline_iqr": [float(v) for v in np.percentile(decline, [25, 75])],
                "decline_life_share_median": float(np.median(life_share)),
                "soil_at_decline_median": float(np.median(soil_at)),
                "soil_at_decline_iqr": [float(v) for v in np.percentile(soil_at, [25, 75])],
                "soil_warn_worlds": len(warn),
                "soil_warn_median": float(np.median(warn)) if warn else None,
                "soil_warn_iqr": [float(v) for v in np.percentile(warn, [25, 75])] if warn else None}
        # mean growth of each role from 60,000 to 20,000 ticks before the last prey, median over worlds
        for role, keys in ROLE_KEYS.items():
            vals = [np.nanmean(aligned(r, growth(r, keys))[:-200]) for r in g]
            vals = [v for v in vals if np.isfinite(v)]
            d[s][f"growth_{role}_60k_20k"] = float(np.median(vals)) if vals else None
    return d


def fig_growth(runs, folder, size):
    g = collapsed(runs, "main")
    x = k(np.arange(-SPAN, 1) * 100)
    fig, axes = plt.subplots(2, 1, figsize=size, sharex=True, layout="constrained",
                             gridspec_kw={"height_ratios": [1.5, 1]})
    ax = axes[0]
    for role in ["plants", "pred", "prey"]:
        M = np.array([aligned(r, growth(r, ROLE_KEYS[role])) for r in g])
        if role == "prey":
            lo, hi = np.nanpercentile(M, [25, 75], axis=0)
            ax.fill_between(x, lo, hi, color=ROLE_COLORS[role], alpha=0.15, lw=0)
        ax.plot(x, np.nanmedian(M, axis=0), color=ROLE_COLORS[role], label=ROLE_LABELS[role])
    ax.axhline(0, color="#333", lw=1.2)
    ax.set_ylim(-42, 12)
    ax.set_ylabel("growth rate\n(% per 1,000 ticks)")
    ax.set_title(f"Main worlds that went extinct ({len(g)}), lined up on the last prey", loc="left")
    ax.legend(loc="lower left", ncol=3, fontsize=12, handlelength=1.4, columnspacing=1.2)
    ax = axes[1]
    F = np.array([aligned(r, r["fert"]) for r in g])
    lo, hi = np.nanpercentile(F, [25, 75], axis=0)
    ax.fill_between(x, lo, hi, color="#8a5a19", alpha=0.18, lw=0)
    ax.plot(x, np.nanmedian(F, axis=0), color="#8a5a19")
    ax.axhline(SOIL_WARN, color="#999", lw=1, ls=":")
    ax.set_ylim(40, 102)
    ax.set_ylabel("soil fertility\n(% of start)")
    ax.set_xlabel("ticks before the last prey died (thousands)")
    ax.set_xlim(x[0], 0)
    for a in axes:
        a.axvline(0, color="#222", lw=1, ls=":")
    return D.save(fig, folder, "slide_growth_rate")


def background(sl, number):
    c = sl.c
    c.setFillColor(BG)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setStrokeColor(GRID)
    c.setLineWidth(2.2)
    for x in range(0, int(W) + 1, 36):
        c.line(x, 0, x, H)
    for y in range(0, int(H) + 1, 36):
        c.line(0, H - y, W, H - y)
    sl.text(72, 88, [("Stable until the crash", "Arial-Bold", 48, "#ffffff")])
    sl.text(1361, 776, [(str(number), "Arial", 15, "#4a5563")])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", nargs="?", default="Presentation Final/ARTIFICIAL LIFE - LIFE ENGINE 2.pdf")
    ap.add_argument("--after", type=int, default=9, help="slide number the new slide follows")
    ap.add_argument("--root", default="Observations/slow-regen-runs")
    ap.add_argument("--cache")
    ap.add_argument("--out", default="Presentation Final/output")
    a = ap.parse_args()
    figs = os.path.join(a.out, "figures")
    os.makedirs(figs, exist_ok=True)
    pdfmetrics.registerFont(TTFont("Arial", D.FONTS + "Arial.ttf"))
    pdfmetrics.registerFont(TTFont("Arial-Bold", D.FONTS + "Arial Bold.ttf"))
    A.style()
    D.style()
    A.REGENS, A.PATHWAYS, A.PATH_COLORS = S.REGENS, S.PATHWAYS, S.PATH_COLORS
    warnings.simplefilter("ignore", RuntimeWarning)
    runs = [S.prepare(r) for r in dynamics_load.load_all(a.root, a.cache or os.path.join(a.out, "cache"))]
    d = numbers(runs)
    m, nc = d["main"], d["noclaw"]
    fig = fig_growth(runs, figs, (767 / 72, 400 / 72))

    sl = Slide()
    background(sl, a.after + 1)
    left_cards(sl, [
        ("≈ 0%", ORANGE, "net growth of every role until ~20,000 ticks before the end",
         "births matched deaths: the populations looked stable"),
        (f"~{m['decline_median']:,.0f} ticks", BLUE, "from births falling behind deaths to the last prey",
         f"median, main; {nc['decline_median']:,.0f} in the no-claw control"),
        (f"{m['soil_at_decline_median']:.0f}%", GOLD, "of the starting soil was left when the crash began",
         "median: the soil ran down first, unseen in growth")])
    right_panel(sl, fig, [("No early warning in growth: ", "Arial-Bold", 21, INK),
                          ("near zero while the soil runs down, then every population crashes together",
                           "Arial", 21, MUTED)])
    page = PdfWriter().add_blank_page(W, H)
    sl.apply(page)
    page.mediabox = RectangleObject([0, H - 810, W, H])

    single = os.path.join(a.out, "slide_growth_rate.pdf")
    w = PdfWriter()
    w.add_page(page)
    with open(single, "wb") as f:
        w.write(f)
    subprocess.run(["pdftoppm", "-r", "150", "-png", "-singlefile", single, single[:-4]], check=False)

    deck = PdfWriter()
    for i, p in enumerate(PdfReader(a.deck).pages):
        deck.add_page(p)
        if i == a.after - 1:
            deck.add_page(PdfReader(single).pages[0])
    out = os.path.join(a.out, os.path.basename(a.deck)[:-4] + " (growth slide).pdf")
    with open(out, "wb") as f:
        deck.write(f)
    with open(os.path.join(a.out, "growth_numbers.json"), "w") as f:
        json.dump(d, f, indent=1)
    print(json.dumps(d, indent=1))
    print(out)


if __name__ == "__main__":
    main()
