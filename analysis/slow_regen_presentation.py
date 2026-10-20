"""Presentation figures (vector PDF and SVG) and a mocked-up slide deck for the slow-regen batch.

Every number on the slides is computed here from the runs, so the deck and stats.json always agree with the data.
The figures answer the four presentation questions:
  1. did an extinction event occur?            q1_*
  2. mis-adaptation or failure to adapt?       q2_*
  3. the environment or the seeded species?    q3_*
  4. which features and traits mattered?       q4_*, story_*
plus passing_fast_regen (the final runs at 1-10%, for comparison only).

Usage:
    python analysis/slow_regen_presentation.py [Observations/slow-regen-runs] [--out presentation] [--cache DIR]
        [--final results/claws/tables/runs_dynamics.csv]
The slides are filled in from <out>/slides_template.html into <out>/slides.html, and printed to <out>/slides.pdf with
headless Brave when --brave is given.
"""
import argparse
import csv
import json
import os
import string
import subprocess
import sys
import warnings
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynamics_analysis as A  # noqa: E402
import dynamics_load  # noqa: E402
import slow_regen_analysis as S  # noqa: E402
from dynamics_analysis import SETS, SET_COLORS, LAYOUTS, TICKS, k, band, stack, group, fisher  # noqa: E402
from slow_regen_analysis import REGENS, FINAL_REGENS, REGEN_COLORS, LAYOUT_COLORS, PATHWAYS, PATH_COLORS  # noqa: E402

SET_LABELS = {"main": "claws, burrow cost (main)", "noclaw": "no claws (noclaw)",
              "nocost": "claws, free burrowing (nocost)"}
OUTCOMES = ["took over, then all prey died", "took over, then fell back", "took over and persisted",
            "never took over"]
OUTCOME_COLORS = dict(zip(OUTCOMES, ["#e34948", "#6250d6", "#008300", "#c3c2b7"]))
OUTCOME_MAP = {"took over, then the group died out": OUTCOMES[0], "took over, then fell back below half": OUTCOMES[1],
               "took over and persisted": OUTCOMES[2], "never took over": OUTCOMES[3],
               "group died out, never took over": OUTCOMES[3]}
BRAVE = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"


def style():
    A.style()
    plt.rcParams.update({"font.size": 11, "axes.titlesize": 11.5, "axes.labelsize": 11, "legend.fontsize": 10,
                         "xtick.labelsize": 10, "ytick.labelsize": 10, "lines.linewidth": 2.0,
                         "pdf.fonttype": 42, "svg.fonttype": "path"})


def save(fig, folder, name):
    fig.tight_layout()
    for ext in ("pdf", "svg"):
        fig.savefig(os.path.join(folder, f"{name}.{ext}"))
    plt.close(fig)


def bar_labels(ax, bars, values, fmt="{}"):
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.8, fmt.format(v), ha="center", va="bottom",
                fontsize=9.5, color="#333")


# ---- question 1: did an extinction event occur? -------------------------------------------------------------------

def fig_q1_extinct(runs, folder):
    fig, ax = plt.subplots(figsize=(7.6, 4.0))
    w = 0.26
    for i, s in enumerate(SETS):
        vals = [sum(r["extinct"] for r in group(runs, set=s, regen=rg)) for rg in REGENS]
        total = sum(r["extinct"] for r in group(runs, set=s))
        bars = ax.bar(np.arange(4) + (i - 1) * w, vals, w - 0.03, color=SET_COLORS[s],
                      label=f"{SET_LABELS[s]}: {total} of 180")
        bar_labels(ax, bars, vals)
    ax.set_xticks(range(4), [f"{rg}%" for rg in REGENS])
    ax.set_xlabel("soil regeneration (% chance per tick)")
    ax.set_ylabel("worlds extinct (of 45)")
    ax.set_ylim(0, 50)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right")
    save(fig, folder, "q1_extinctions_by_rate")


def fig_q1_survival(runs, folder):
    fig, ax = plt.subplots(figsize=(7.6, 4.0))
    x = k(TICKS)
    for rg in REGENS:
        g = group(runs, set="main", regen=rg)
        ax.plot(x, 100 * stack(g, lambda r: r["alive"].astype(float)).mean(axis=0), color=REGEN_COLORS[rg],
                label=f"main, {rg}%")
    for s in ["noclaw", "nocost"]:
        g = group(runs, set=s)
        ax.plot(x, 100 * stack(g, lambda r: r["alive"].astype(float)).mean(axis=0), color=SET_COLORS[s],
                ls=A.SET_STYLES[s], label=f"{s}, all rates")
    ax.set_ylim(0, 102)
    ax.set_xlim(0, 250)
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("worlds still alive (%)")
    ax.legend(loc="lower left", ncol=2)
    save(fig, folder, "q1_survival")


# ---- question 2: mis-adaptation or failure to adapt? --------------------------------------------------------------

def fig_q2_takeover(runs, folder):
    fig, ax = plt.subplots(figsize=(7.6, 4.0))
    x = k(TICKS)
    for s in ["main", "nocost"]:
        g = group(runs, set=s)
        takes = np.array([r["claw_take"] if r["claw_take"] is not None else np.inf for r in g])
        ax.plot(x, [100 * np.mean(takes <= t) for t in TICKS], color=SET_COLORS[s], ls=A.SET_STYLES[s],
                label=SET_LABELS[s])
        med = np.median(takes[np.isfinite(takes)])
        ax.axvline(med / 1000, color=SET_COLORS[s], lw=0.9, ls=A.SET_STYLES[s])
        ax.text(med / 1000 + 1.5, 8 if s == "main" else 16, f"median {s}: {med:,.0f}", fontsize=9.5, color="#333")
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 102)
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("runs in which the claw has\ntaken over (% of 180)")
    ax.legend(loc="lower right")
    save(fig, folder, "q2_claw_takeover")


def fig_q2_outcomes(runs, folder):
    fig, ax = plt.subplots(figsize=(9.0, 2.9))
    rows = ["main", "nocost"]
    for i, s in enumerate(rows):
        c = Counter(OUTCOME_MAP[r["claw_outcome"]] for r in group(runs, set=s))
        left = 0
        for o in OUTCOMES:
            v = c.get(o, 0)
            if v:
                ax.barh(i, v, left=left, color=OUTCOME_COLORS[o], edgecolor="white", linewidth=2, height=0.62)
                if v >= 5:
                    ax.text(left + v / 2, i, str(v), ha="center", va="center", fontsize=10.5,
                            color="#222" if o == OUTCOMES[3] else "white")
            left += v
    ax.set_yticks(range(2), [SET_LABELS[s] for s in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 180)
    ax.set_xlabel("runs (of 180)")
    ax.grid(axis="y", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=OUTCOME_COLORS[o]) for o in OUTCOMES]
    ax.legend(handles, OUTCOMES, loc="lower left", bbox_to_anchor=(0, 1.02), ncol=4, fontsize=9.5,
              handlelength=1.2, columnspacing=1.2)
    save(fig, folder, "q2_claw_outcomes")


def fig_q2_pathways(runs, folder):
    fig, ax = plt.subplots(figsize=(9.0, 3.1))
    order = ["plants died first", "prey died first", "predators died first", "early boom-bust"]
    for i, s in enumerate(SETS):
        ext = [r for r in group(runs, set=s) if r["extinct"]]
        c = Counter(r["pathway"] for r in ext)
        left = 0
        for p in order:
            v = c.get(p, 0)
            if v:
                ax.barh(i, v, left=left, color=PATH_COLORS[p], edgecolor="white", linewidth=2, height=0.62)
                if v >= 4:
                    ax.text(left + v / 2, i, str(v), ha="center", va="center", fontsize=10.5, color="white")
            left += v
    ax.set_yticks(range(3), [f"{SET_LABELS[s]}" for s in SETS])
    ax.invert_yaxis()
    ax.set_xlim(0, 140)
    ax.set_xlabel("extinct worlds, by the first role to die out")
    ax.grid(axis="y", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=PATH_COLORS[p]) for p in order]
    ax.legend(handles, order, loc="lower left", bbox_to_anchor=(0, 1.02), ncol=4, fontsize=9.5, handlelength=1.2)
    save(fig, folder, "q2_collapse_pathways")


def claw_gap(r):
    v = r["fitness"]["claw"][:600] - r["fitness"]["prey"][:600]
    return float(np.nanmean(v)) if np.any(~np.isnan(v)) else None


def fig_q2_fitness_gap(runs, folder):
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    rng = np.random.default_rng(1)
    for i, s in enumerate(["main", "nocost"]):
        v = np.array([g for r in group(runs, set=s) if (g := claw_gap(r)) is not None])
        ax.scatter(i + rng.uniform(-0.18, 0.18, len(v)), v, s=14, color=SET_COLORS[s], alpha=0.55, lw=0)
        q1, med, q3 = np.percentile(v, [25, 50, 75])
        ax.plot([i - 0.3, i + 0.3], [med, med], color="#222", lw=2.2)
        ax.plot([i, i], [q1, q3], color="#222", lw=1.2)
        ax.text(i + 0.33, med, f"median {med:+.3f}\n{(v > 0).sum()} of {len(v)} above 0", va="center", fontsize=9.5)
    ax.axhline(0, color="#555", lw=0.9)
    ax.set_xticks([0, 1], [SET_LABELS["main"], SET_LABELS["nocost"]])
    ax.set_xlim(-0.5, 1.95)
    ax.set_ylabel("fitness, clawed minus plain prey\n(mean over ticks 0-60,000)")
    ax.grid(axis="x", visible=False)
    save(fig, folder, "q2_claw_fitness_gap")


def fig_q2_noclaw(runs, folder):
    fig, ax = plt.subplots(figsize=(7.6, 3.4))
    w = 0.26
    for i, s in enumerate(SETS):
        vals = [sum(r["extinct"] for r in group(runs, set=s, layout=lay)) for lay in LAYOUTS]
        bars = ax.bar(np.arange(3) + (i - 1) * w, vals, w - 0.03, color=SET_COLORS[s], label=SET_LABELS[s])
        bar_labels(ax, bars, vals)
    ax.set_xticks(range(3), [f"{lay} maps" for lay in LAYOUTS])
    ax.set_ylabel("worlds extinct (of 60)")
    ax.set_ylim(0, 68)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left")
    save(fig, folder, "q3_extinctions_by_layout")


# ---- question 3: environment or seeded species? -------------------------------------------------------------------

def fig_q3_layout_rate(runs, folder):
    fig, axes = plt.subplots(1, 3, figsize=(10.0, 3.5), sharey=True)
    for ax, lay in zip(axes, LAYOUTS):
        for s in SETS:
            ys = [sum(r["extinct"] for r in group(runs, set=s, layout=lay, regen=rg)) for rg in REGENS]
            ax.plot(range(4), ys, color=SET_COLORS[s], ls=A.SET_STYLES[s], marker="o", ms=7, mec="white", mew=1.5,
                    label=SET_LABELS[s])
        ax.set_xticks(range(4), [f"{rg}%" for rg in REGENS])
        ax.set_ylim(-0.8, 15.8)
        ax.set_yticks([0, 5, 10, 15])
        ax.set_title(f"{lay} maps")
        ax.set_xlabel("soil regeneration")
    axes[0].set_ylabel("worlds extinct (of 15)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    for ext in ("pdf", "svg"):
        fig.savefig(os.path.join(folder, f"q3_extinctions_layout_rate.{ext}"))
    plt.close(fig)


# ---- question 4: which features mattered? -------------------------------------------------------------------------

def fig_q4_plants(runs, folder):
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    idx = np.arange(0, 1001, 25)
    for rg in REGENS:
        med = [np.median(v) if len(v := S.plant_ratio(runs, rg, i)) >= 8 else np.nan for i in idx]
        ax.plot(k(TICKS[idx]), med, color=REGEN_COLORS[rg], label=f"{rg}%")
    ax.axhline(100, color="#555", lw=0.8)
    ax.set_ylim(0, 115)
    ax.set_xlim(0, 100)
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("plants in main as % of the\nfree-burrowing twin (median)")
    ax.legend(title="soil regeneration", loc="lower left", ncol=4)
    save(fig, folder, "q4_plants_vs_twin")


def fig_q4_fert_min(runs, folder):
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    for i, rg in enumerate(REGENS):
        for j, lay in enumerate(LAYOUTS):
            g = group(runs, set="main", regen=rg, layout=lay)
            xs = i + (j - 1) * 0.27 + np.linspace(-0.08, 0.08, len(g))
            for xx, r in zip(xs, g):
                ax.plot(xx, r["fert_min"], "x" if r["extinct"] else "o", ms=5.5, color=LAYOUT_COLORS[lay],
                        mew=1.4 if r["extinct"] else 0.6, mec=LAYOUT_COLORS[lay] if r["extinct"] else "white")
        med = np.median([r["fert_min"] for r in group(runs, set="main", regen=rg)])
        ax.plot([i - 0.42, i + 0.42], [med, med], color="#222", lw=1.6)
    handles = [plt.Line2D([], [], color=LAYOUT_COLORS[lay], marker="s", ls="", ms=7) for lay in LAYOUTS]
    handles += [plt.Line2D([], [], color="#555", marker=m, ls="", ms=6) for m in ("o", "x")]
    handles += [plt.Line2D([], [], color="#222", lw=1.6)]
    ax.legend(handles, LAYOUTS + ["survived", "went extinct", "median"], loc="lower right", ncol=3, fontsize=9.5)
    ax.set_xticks(range(4), [f"{rg}%" for rg in REGENS])
    ax.set_xlabel("soil regeneration (% chance per tick)")
    ax.set_ylabel("lowest soil fertility\n(% of start, main)")
    ax.set_ylim(20, 102)
    ax.grid(axis="x", visible=False)
    save(fig, folder, "q4_lowest_fertility")


def fig_q4_burrows(runs, folder):
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    x = k(TICKS)
    for s in ["main", "nocost"]:
        g = group(runs, set=s)
        band(ax, x, stack(g, lambda r: np.where(r["alive"], A.window_sum(r["burrows"], 20) / 20, np.nan)),
             SET_COLORS[s], A.SET_STYLES[s], SET_LABELS[s], min_runs=10, alpha=0.18)
    ax.set_xlim(0, 150)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("burrows per 100 ticks\n(median, worlds alive)")
    ax.legend(loc="upper left")
    save(fig, folder, "q4_burrowing")


def fig_story(run, title, folder, name):
    plt.rcParams.update({"font.size": 10, "legend.fontsize": 9})
    S.fig_story(run, title, os.path.join(folder, name + ".pdf"))
    S.fig_story(run, title, os.path.join(folder, name + ".svg"))
    style()


# ---- numbers ------------------------------------------------------------------------------------------------------

def fmt_p(p):
    m, e = f"{p:.0e}".split("e")
    return f"{m}&times;10<sup>&minus;{int(e[1:])}</sup>"


def stats(runs, final_rows):
    d = {}
    ext = {s: [r for r in group(runs, set=s) if r["extinct"]] for s in SETS}
    for s in SETS:
        d[f"ext_{s}"] = len(ext[s])
        for rg in REGENS:
            d[f"ext_{s}_{rg}"] = sum(r["extinct"] for r in group(runs, set=s, regen=rg))
        for lay in LAYOUTS:
            d[f"ext_{s}_{lay}"] = sum(r["extinct"] for r in group(runs, set=s, layout=lay))
            for rg in REGENS:
                d[f"ext_{s}_{lay}_{rg}"] = sum(r["extinct"] for r in group(runs, set=s, layout=lay, regen=rg))
        d[f"final_{s}"] = sum(int(r["extinct"]) for r in final_rows if r["set"] == s)
        d[f"final_{s}_sparse"] = sum(int(r["extinct"]) for r in final_rows if r["set"] == s and r["layout"] == "sparse")
        pw = Counter(r["pathway"] for r in ext[s])
        for p in PATHWAYS:
            d[f"path_{s}_{p.split()[0]}"] = pw.get(p, 0)
        oc = Counter(OUTCOME_MAP[r["claw_outcome"]] for r in group(runs, set=s))
        for i, o in enumerate(OUTCOMES):
            d[f"claw_{s}_{i}"] = oc.get(o, 0)
        d[f"derived_died_{s}"] = sum(r["derived_outcome"] == "took over, then the group died out"
                                     for r in group(runs, set=s))
        d[f"derived_died_ext_{s}"] = sum(r["derived_outcome"] == "took over, then the group died out" for r in ext[s])
    for s in ["main", "nocost"]:
        takes = [r["claw_take"] for r in group(runs, set=s) if r["claw_take"] is not None]
        d[f"take_n_{s}"] = len(takes)
        d[f"take_med_{s}"] = f"{np.median(takes):,.0f}"
        gaps = np.array([g for r in group(runs, set=s) if (g := claw_gap(r)) is not None])
        d[f"gap_med_{s}"] = f"{np.median(gaps):+.3f}".replace("-", "&minus;")
        d[f"gap_pos_{s}"] = int((gaps > 0).sum())
        d[f"gap_n_{s}"] = len(gaps)
        d[f"burrows_{s}"] = f"{np.median([np.nanmean(r['burrows'][100:400]) for r in group(runs, set=s)]):.1f}"
    after = [r for r in ext["main"] if r["claw_take"] is not None and r["claw_take"] < r["last_prey"]]
    gaps = [r["end_tick"] - r["claw_take"] for r in after]
    d["after_take"] = len(after)
    d["after_gap_med"] = f"{np.median(gaps):,.0f}"
    d["after_gap_q1"], d["after_gap_q3"] = (f"{q / 1000:.1f}k" for q in np.percentile(gaps, [25, 75]))
    for s in SETS:
        d[f"end_med_{s}"] = f"{np.median([r['end_tick'] for r in ext[s]]):,.0f}"
    d["plants_first_share"] = f"{100 * d['path_main_plants'] / len(ext['main']):.0f}"
    d["main_survivors"] = 180 - len(ext["main"])
    main = group(runs, set="main")
    for rg in REGENS:
        d[f"fert_{rg}"] = f"{np.median([r['fert_min'] for r in group(main, regen=rg)]):.0f}"
        d[f"plants60_{rg}"] = f"{np.median(S.plant_ratio(runs, rg, 600)):.0f}"
        d[f"recovery_{rg}"] = f"{S.MIN_PLANT_FERTILITY / (float(rg) / 100):,.0f}"
    for rg in FINAL_REGENS:
        d[f"recovery_{rg}"] = f"{S.MIN_PLANT_FERTILITY / (float(rg) / 100):,.0f}"
    dense = group(main, layout="dense")
    d["fert_dense_ext"] = f"{np.median([r['fert_min'] for r in dense if r['extinct']]):.0f}"
    d["fert_dense_surv"] = f"{np.median([r['fert_min'] for r in dense if not r['extinct']]):.0f}"
    e = {s: len(ext[s]) for s in SETS}
    tests = {"main_nocost": ("main", "nocost"), "main_noclaw": ("main", "noclaw"), "noclaw_nocost": ("noclaw", "nocost")}
    for key, (a, b) in tests.items():
        d[f"p_{key}"] = fmt_p(fisher(e[a], 180 - e[a], e[b], 180 - e[b]))
    pf = {s: d[f"path_{s}_plants"] for s in SETS}
    d["p_plants_first"] = fmt_p(fisher(pf["main"], 180 - pf["main"], pf["nocost"], 180 - pf["nocost"]))
    d["p_mis"] = fmt_p(fisher(d["claw_main_0"], 180 - d["claw_main_0"], d["claw_nocost_0"], 180 - d["claw_nocost_0"]))
    d["pred_died_survived_main"] = sum(1 for r in main if r["pred_gone"] and not r["extinct"])
    return d


def story_stats(d, stories):
    for key, r in stories.items():
        d[f"{key}_take"] = f"{r['claw_take']:,}" if r["claw_take"] else "never"
        d[f"{key}_end"] = f"{r['end_tick']:,}"
        d[f"{key}_fert"] = f"{r['fert_min']:.0f}"
        d[f"{key}_state"] = "extinct" if r["extinct"] else "alive at 250,000"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default="Observations/slow-regen-runs")
    ap.add_argument("--out", default="presentation")
    ap.add_argument("--cache")
    ap.add_argument("--final", default="results/claws/tables/runs_dynamics.csv")
    ap.add_argument("--brave", action="store_true", help="print slides.html to slides.pdf with headless Brave")
    a = ap.parse_args()
    figs = os.path.join(a.out, "figures")
    os.makedirs(figs, exist_ok=True)
    style()
    A.REGENS, A.PATHWAYS, A.PATH_COLORS = REGENS, PATHWAYS, PATH_COLORS
    warnings.simplefilter("ignore", RuntimeWarning)
    runs = [S.prepare(r) for r in dynamics_load.load_all(a.root, a.cache or os.path.join(a.out, "cache"))]
    with open(a.final, newline="") as f:
        final_rows = list(csv.DictReader(f))

    fig_q1_extinct(runs, figs)
    fig_q1_survival(runs, figs)
    fig_q2_takeover(runs, figs)
    fig_q2_outcomes(runs, figs)
    fig_q2_pathways(runs, figs)
    fig_q2_fitness_gap(runs, figs)
    fig_q2_noclaw(runs, figs)
    fig_q3_layout_rate(runs, figs)
    fig_q4_plants(runs, figs)
    fig_q4_fert_min(runs, figs)
    fig_q4_burrows(runs, figs)
    for ext in ("pdf", "svg"):
        S.fig_fertility_layout(runs, os.path.join(figs, f"q4_soil_by_layout.{ext}"))
        S.fig_regen_both(runs, final_rows, os.path.join(figs, f"passing_fast_regen.{ext}"))
        S.fig_extinctions(runs, os.path.join(figs, f"q1_extinctions_heatmap.{ext}"))

    by_name = {r["name"]: r for r in runs}
    crash = min((r for r in group(runs, set="main", layout="dense", regen="0.01") if r["extinct"]),
                key=lambda r: r["fert_min"])
    name = lambda s, rg: f"{s}-dense_soilRegenRate={rg}_seed1_soil{crash['soil']}_rep{crash['rep']}"
    stories = {"crash": crash, "twin": by_name[name("nocost", "0.01")], "fast": by_name[name("main", "0.1")]}
    fig_story(crash, f"{A.story_label(crash)}: burrowing strips the soil and the world collapses", figs,
              "story_slow_soil_collapse")
    fig_story(stories["twin"], f"{A.story_label(stories['twin'])}: the same map with free burrowing", figs,
              "story_free_burrowing")
    fig_story(stories["fast"], f"{A.story_label(stories['fast'])}: the same map with faster regeneration", figs,
              "story_fast_soil_survives")

    d = stats(runs, final_rows)
    story_stats(d, stories)
    d["story_map"] = f"{crash['map']}, replicate {crash['rep']}"
    with open(os.path.join(a.out, "stats.json"), "w") as f:
        json.dump(d, f, indent=1, default=str)
    template = string.Template(open(os.path.join(a.out, "slides_template.html")).read())
    html = os.path.join(a.out, "slides.html")
    with open(html, "w") as f:
        # template names cannot hold dots: ext_main_0.01 is $ext_main_0_01 in the template
        f.write(template.substitute({key.replace(".", "_"): v for key, v in d.items()}))
    if a.brave:
        subprocess.run([BRAVE, "--headless", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=15000",
                        f"--print-to-pdf={os.path.abspath(os.path.join(a.out, 'slides.pdf'))}",
                        "file://" + os.path.abspath(html)], check=True, capture_output=True)
    print(json.dumps(d, indent=1, default=str))


if __name__ == "__main__":
    main()
