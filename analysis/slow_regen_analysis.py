"""Population dynamics of the slow-regen batch (soil regeneration 0.01-0.1% per tick), for the slow-regen report.

Reuses the loading, series and most figures of dynamics_analysis.py and adds the figures that the slow soil needs:
extinctions by set, layout and regeneration rate, soil fertility over time, the burrow-soil-plant coupling, and the
comparison with the final runs (regeneration 1-10%).

Usage:
    python analysis/slow_regen_analysis.py [Observations/slow-regen-runs] [--out results/slow-regen] [--cache DIR]
        [--final results/claws/tables/runs_dynamics.csv] [--tarique results/claws/tarique]

Definitions as in dynamics_analysis.py, plus:
  soil fertility   mean fertility of the map as a share of its starting value; infertile ground stays at 0, so this is
                   the mean over the fertile ground relative to full. Only burrowing lowers it, so it stays at 100% in
                   noclaw and nocost
  collapse pathway of an extinct run, from the role that died out first: plants, prey or predators first, or early
                   boom-bust (everything dead before EARLY_TICKS with no claw take-over)
"""
import argparse
import csv
import json
import os
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
from dynamics_analysis import (SETS, SET_NAMES, SET_SHORT, SET_COLORS, SET_STYLES, ROLES, ROLE_NAMES, ROLE_COLORS,
                               ROLE_STYLES, SOIL_COLOR, LAYOUTS, TICKS, N, WINDOW, k, band, stack, group, med_iqr,
                               window_sum, late_mean, fisher)  # noqa: E402

REGENS = ["0.01", "0.025", "0.05", "0.1"]
FINAL_REGENS = ["1", "2.5", "5", "10"]
PATHWAYS = ["early boom-bust", "plants died first", "prey died first", "predators died first"]
PATH_COLORS = {"early boom-bust": "#8a8a85", "plants died first": "#008300", "prey died first": "#2a78d6",
               "predators died first": "#e34948"}
FIRST_KEYS = {"plants": "plants died first", "prey": "prey died first", "pred": "predators died first"}
REGEN_COLORS = {rg: plt.get_cmap("Blues")(0.35 + 0.65 * i / 3) for i, rg in enumerate(REGENS)}
LAYOUT_COLORS = {"dense": "#5c3a0e", "medium": "#a8742c", "sparse": "#dcb57a"}
MIN_PLANT_FERTILITY = 7
REGEN_AMOUNT = 1


def prepare(run):
    A.prepare(run)
    soil = A.pad(run["s"]["w_soil_mean"])
    run["fert"] = np.where(run["alive"], 100 * soil / soil[0], np.nan)
    run["fert_min"] = float(np.nanmin(run["fert"]))
    lasts = {"plants": run["last_plant"], "prey": run["last_prey"], "pred": run["last_pred"]}
    run["first_gone"] = min(lasts, key=lasts.get)
    if run["extinct"]:
        early = run["end_tick"] < A.EARLY_TICKS and run["claw_take"] is None
        run["pathway"] = "early boom-bust" if early else FIRST_KEYS[run["first_gone"]]
    return run


# ---- figures ------------------------------------------------------------------------------------------------------

def fig_extinctions(runs, path):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.4), gridspec_kw={"width_ratios": [1, 1.35]})
    ax = axes[0]
    rows = [(s, lay) for s in SETS for lay in LAYOUTS]
    m = np.array([[sum(r["extinct"] for r in group(runs, set=s, layout=lay, regen=rg)) for rg in REGENS]
                  for s, lay in rows])
    ax.imshow(m, cmap="Reds", vmin=-2, vmax=17, aspect="auto")
    for i in range(len(rows)):
        for j in range(len(REGENS)):
            ax.text(j, i, str(m[i, j]), ha="center", va="center", fontsize=8,
                    color="white" if m[i, j] >= 9 else "#222")
    ax.set_xticks(range(len(REGENS)), [f"{rg}%" for rg in REGENS])
    ax.set_yticks(range(len(rows)), [f"{SET_SHORT[s]}, {lay}" for s, lay in rows], fontsize=8)
    for y in (2.5, 5.5):
        ax.axhline(y, color="white", lw=3)
    ax.grid(False)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xlabel("soil regeneration (% per tick)")
    ax.set_title("(a) extinct runs (of 15)")
    ax = axes[1]
    x = k(TICKS)
    for rg in REGENS:
        g = group(runs, set="main", regen=rg)
        ax.plot(x, 100 * stack(g, lambda r: r["alive"].astype(float)).mean(axis=0), color=REGEN_COLORS[rg],
                label=f"main, {rg}%")
    for s in ["noclaw", "nocost"]:
        g = group(runs, set=s)
        ax.plot(x, 100 * stack(g, lambda r: r["alive"].astype(float)).mean(axis=0), color=SET_COLORS[s],
                ls=SET_STYLES[s], label=f"{SET_SHORT[s]}, all rates")
    ax.set_ylim(0, 102)
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("worlds alive (%)")
    ax.set_title("(b) survival over time")
    ax.legend(loc="lower left", fontsize=7.5, ncol=2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_regen_both(runs, final_rows, path):
    """Share of runs extinct against regeneration rate, both experiments on one log axis, per layout."""
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 2.9), sharey=True)
    xs = [float(r) for r in REGENS + FINAL_REGENS]
    for ax, lay in zip(axes, LAYOUTS):
        for s in SETS:
            ys = [100 * np.mean([r["extinct"] for r in group(runs, set=s, layout=lay, regen=rg)]) for rg in REGENS]
            ys += [100 * np.mean([int(r["extinct"]) for r in final_rows if r["set"] == s and r["layout"] == lay
                                  and r["regen"] == rg]) for rg in FINAL_REGENS]
            ax.plot(xs[:4], ys[:4], color=SET_COLORS[s], ls=SET_STYLES[s], marker="o", ms=4, label=SET_NAMES[s])
            ax.plot(xs[4:], ys[4:], color=SET_COLORS[s], ls=SET_STYLES[s], marker="o", ms=4)
        ax.axvspan(0.15, 0.7, color="#f1f0ec", lw=0)
        ax.set_xscale("log")
        ax.set_xticks(xs, ["0.01", "", "0.05", "0.1", "1", "", "5", "10"])
        ax.minorticks_off()
        ax.set_ylim(-3, 103)
        ax.set_xlabel("soil regeneration (% per tick)")
        ax.set_title(f"{lay} maps", pad=14)
        ax.text(0.031, 104, "slow-regen runs", fontsize=7.5, ha="center", va="bottom", color="#555")
        ax.text(3.1, 104, "final runs", fontsize=7.5, ha="center", va="bottom", color="#555")
    axes[0].set_ylabel("runs extinct (%)")
    handles = [plt.Line2D([], [], color=SET_COLORS[s], ls=SET_STYLES[s], marker="o", ms=4) for s in SETS]
    fig.legend(handles, [SET_NAMES[s] for s in SETS], loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def fig_fertility_layout(runs, path):
    """Main only (the one set where the soil changes): fertility and burrowing over time, per layout and rate."""
    rows = [("fert", "soil fertility (% of start)"), ("burrows", "burrows per 100 ticks"),
            ("alive", "worlds alive (%)")]
    fig, axes = plt.subplots(len(rows), 4, figsize=(9.2, 6.0), sharex=True, sharey="row")
    x = k(TICKS)
    for col, rg in enumerate(REGENS):
        for row, (key, label) in enumerate(rows):
            ax = axes[row, col]
            for lay in LAYOUTS:
                g = group(runs, set="main", regen=rg, layout=lay)
                if key == "alive":
                    ax.plot(x, 100 * stack(g, lambda r: r["alive"].astype(float)).mean(axis=0),
                            color=LAYOUT_COLORS[lay], label=lay)
                    continue
                if key == "burrows":
                    m = stack(g, lambda r: np.where(r["alive"], window_sum(r["burrows"], 20) / 20, np.nan))
                else:
                    m = stack(g, lambda r: r["fert"])
                band(ax, x, m, LAYOUT_COLORS[lay], label=lay, min_runs=3, alpha=0.18)
            if row == 0:
                ax.set_title(f"main, regeneration {rg}%")
            if col == 0:
                ax.set_ylabel(label)
            if row == len(rows) - 1:
                ax.set_xlabel("tick (thousands)")
    axes[0, 0].set_ylim(40, 102)
    axes[2, 0].set_ylim(0, 102)
    axes[0, 0].legend(loc="lower left", fontsize=7.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_population_soil(runs, path):
    rows = [("fert", "soil fertility (% of start)"), ("plants", "plants"), ("allprey", "prey (all)"),
            ("pred", "predators"), ("alive", "worlds alive (%)")]
    fig, axes = plt.subplots(len(rows), 4, figsize=(9.2, 8.4), sharex=True, sharey="row")
    x = k(TICKS)
    for col, rg in enumerate(REGENS):
        for row, (key, label) in enumerate(rows):
            ax = axes[row, col]
            for s in SETS:
                g = group(runs, set=s, regen=rg)
                if key == "alive":
                    ax.plot(x, 100 * stack(g, lambda r: r["alive"].astype(float)).mean(axis=0), color=SET_COLORS[s],
                            ls=SET_STYLES[s])
                    continue
                m = stack(g, lambda r: r["fert"]) if key == "fert" else stack(g, lambda r: r["pop_alive"][key])
                band(ax, x, m, SET_COLORS[s], SET_STYLES[s], min_runs=3)
            if row == 0:
                ax.set_title(f"soil regeneration {rg}% per tick")
            if col == 0:
                ax.set_ylabel(label)
            if row == len(rows) - 1:
                ax.set_xlabel("tick (thousands)")
    axes[0, 0].set_ylim(60, 102)
    axes[-1, 0].set_ylim(0, 102)
    handles = [plt.Line2D([], [], color=SET_COLORS[s], ls=SET_STYLES[s]) for s in SETS]
    fig.legend(handles, [SET_NAMES[s] for s in SETS], loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def plant_ratio(runs, rg, t):
    """Plants in main relative to nocost on the same map and replicate (0 once the main world died), median."""
    nocost = {(r["map"], r["rep"]): r for r in group(runs, set="nocost", regen=rg)}
    out = []
    for r in group(runs, set="main", regen=rg):
        o = nocost.get((r["map"], r["rep"]))
        if o is None or not o["alive"][t]:
            continue
        a = A.rolling(r["pop"]["plants"])[t]
        b = A.rolling(o["pop"]["plants"])[t]
        if b > 0:
            out.append(100 * a / b)
    return out


def fig_soil_plants(runs, path):
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 3.0))
    x = k(TICKS)
    ax = axes[0]
    for s in ["main", "nocost"]:
        g = group(runs, set=s)
        band(ax, x, stack(g, lambda r: np.where(r["alive"], window_sum(r["burrows"], 20) / 20, np.nan)),
             SET_COLORS[s], SET_STYLES[s], SET_NAMES[s], min_runs=10)
    ax.set_xlim(0, 150)
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("burrows per 100 ticks")
    ax.set_title("(a) burrowing, worlds alive")
    ax.legend(loc="upper left", fontsize=7)
    ax = axes[1]
    idx = np.arange(0, 1501, 25)
    for rg in REGENS:
        med = [np.median(v) if len(v := plant_ratio(runs, rg, i)) >= 8 else np.nan for i in idx]
        ax.plot(k(TICKS[idx]), med, color=REGEN_COLORS[rg], label=f"{rg}%")
    ax.axhline(100, color="#555", lw=0.7)
    ax.set_ylim(0, 115)
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("plants, main as % of nocost")
    ax.set_title("(b) plants lost to the burrow cost")
    ax.legend(title="regeneration", loc="lower left", fontsize=7, title_fontsize=7.5, ncol=2)
    ax = axes[2]
    for i, rg in enumerate(REGENS):
        for j, lay in enumerate(LAYOUTS):
            g = group(runs, set="main", regen=rg, layout=lay)
            xs = i + (j - 1) * 0.27 + np.linspace(-0.07, 0.07, len(g))
            for xx, r in zip(xs, g):
                ax.plot(xx, r["fert_min"], "x" if r["extinct"] else "o", ms=3.4, color=LAYOUT_COLORS[lay],
                        mew=1.0 if r["extinct"] else 0.4, mec=LAYOUT_COLORS[lay] if r["extinct"] else "white")
    handles = [plt.Line2D([], [], color=LAYOUT_COLORS[lay], marker="s", ls="", ms=5) for lay in LAYOUTS]
    handles += [plt.Line2D([], [], color="#555", marker=m, ls="", ms=4) for m in ("o", "x")]
    ax.legend(handles, LAYOUTS + ["survived", "extinct"], loc="lower right", fontsize=6.5, ncol=2)
    ax.set_xticks(range(4), [f"{rg}%" for rg in REGENS])
    ax.set_xlabel("soil regeneration rate")
    ax.set_ylabel("lowest soil fertility (% of start)")
    ax.set_title("(c) lowest fertility reached (main)")
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_collapse_aligned(runs, path):
    rows = [("plants", "plants"), ("allprey", "prey (all)"), ("pred", "predators"),
            ("claw_share", "prey with a claw (%)"), ("fert", "soil fertility (% of start)")]
    rel = np.arange(-400, 31)
    fig, axes = plt.subplots(len(rows), 3, figsize=(9.2, 8.6), sharex=True, sharey="row")
    for col, s in enumerate(SETS):
        g = [r for r in group(runs, set=s) if r["extinct"]]
        for row, (key, label) in enumerate(rows):
            ax = axes[row, col]
            for r in g:
                i0 = r["last_prey"] // 100
                idx = i0 + rel
                ok = (idx >= 0) & (idx < N)
                series = (100 * r["claw_share"] if key == "claw_share" else r["fert"] if key == "fert"
                          else r["pop"][key])
                y = np.full(len(rel), np.nan)
                y[ok] = series[idx[ok]]
                ax.plot(k(rel * 100), y, color=PATH_COLORS[r["pathway"]], alpha=0.4, lw=0.7)
            ax.axvline(0, color="#555", lw=0.7, ls=":")
            if row == 0:
                ax.set_title(f"{SET_NAMES[s]}: {len(g)} extinct")
            if col == 0:
                ax.set_ylabel(label)
            if row == len(rows) - 1:
                ax.set_xlabel("ticks from the last prey (thousands)")
    for row in range(3):
        axes[row, 0].set_yscale("symlog", linthresh=10)
        axes[row, 0].set_ylim(bottom=0)
    axes[3, 0].set_ylim(0, 102)
    axes[4, 0].set_ylim(30, 102)
    handles = [plt.Line2D([], [], color=PATH_COLORS[p], lw=2) for p in PATHWAYS]
    fig.legend(handles, PATHWAYS, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def fig_story(run, title, path, xmax=None):
    fig, axes = plt.subplots(4, 1, figsize=(7.2, 6.4), sharex=True, gridspec_kw={"height_ratios": [2.2, 1, 1, 1]})
    n = len(run["s"]["t"])
    x = k(TICKS[:n])
    ax = axes[0]
    for role in ROLES:
        ax.plot(x, run["pop"][role][:n], color=ROLE_COLORS[role], ls=ROLE_STYLES[role], lw=1.1, label=ROLE_NAMES[role])
    ax.set_yscale("symlog", linthresh=10)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("organisms")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4, fontsize=7.5)
    ax = axes[1]
    ax.plot(x, 100 * run["claw_share"][:n], color=ROLE_COLORS["claw"], label="prey with a claw (% of prey)")
    ax.plot(x, 100 * run["derived_share"][:n], color=ROLE_COLORS["pred"], ls="--",
            label="predators descended from prey (% of predators)")
    ax.set_ylim(0, 105)
    ax.set_ylabel("share (%)")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, fontsize=7.5)
    ax = axes[2]
    ax.plot(x, run["fert"][:n], color=SOIL_COLOR)
    ax.set_ylabel("soil fertility\n(% of start)")
    ax.set_ylim(min(90, np.nanmin(run["fert"][:n]) - 5), 102)
    ax = axes[3]
    ax.plot(x, window_sum(run["burrows"], 20)[:n] / 20, color="#555", lw=0.9)
    ax.set_ylim(0, max(5, 1.1 * np.nanmax(window_sum(run["burrows"], 20)[:n] / 20)))
    ax.set_ylabel("burrows per\n100 ticks")
    ax.set_xlabel("tick (thousands)")
    for a in axes:
        for t, ls in [(run["claw_take"], "--"), (run["derived_take"], "-.")]:
            if t is not None:
                a.axvline(t / 1000, color="#888", lw=0.8, ls=ls)
        if xmax:
            a.set_xlim(0, xmax)
    fig.suptitle(title, fontsize=9.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ---- numbers ------------------------------------------------------------------------------------------------------

def numbers(runs, final_rows):
    out = {"extinct": {}, "first_gone": {}, "pathways": {}}
    for s in SETS:
        g = group(runs, set=s)
        ext = [r for r in g if r["extinct"]]
        out["extinct"][s] = dict(total=len(ext), **{f"{lay}_{rg}": sum(r["extinct"] for r in
                                 group(g, layout=lay, regen=rg)) for lay in LAYOUTS for rg in REGENS},
                                 **{f"regen_{rg}": sum(r["extinct"] for r in group(g, regen=rg)) for rg in REGENS},
                                 **{f"layout_{lay}": sum(r["extinct"] for r in group(g, layout=lay)) for lay in LAYOUTS})
        out["pathways"][s] = dict(Counter(r["pathway"] for r in ext))
        out[s] = dict(
            end_tick_median=float(np.median([r["end_tick"] for r in ext])) if ext else None,
            end_tick_quartiles=[float(q) for q in np.percentile([r["end_tick"] for r in ext], [25, 75])] if ext else None,
            claw_outcomes=dict(Counter(r["claw_outcome"] for r in g)),
            derived_outcomes=dict(Counter(r["derived_outcome"] for r in g)),
            claw_take_median=float(np.median([r["claw_take"] for r in g if r["claw_take"]])) if s != "noclaw" else None,
            claw_take_before_collapse=sum(1 for r in ext if r["claw_take"] is not None and r["claw_take"] < r["last_prey"]),
            fert_min_median_by_regen={rg: float(np.median([r["fert_min"] for r in group(g, regen=rg)])) for rg in REGENS},
            late_plants_median=float(np.median([late_mean(r, "plants") for r in g])),
            claw_take_by_regen={rg: float(np.median([r["claw_take"] for r in group(g, regen=rg) if r["claw_take"]]
                                                    or [np.nan])) for rg in REGENS},
            claw_take_n=sum(1 for r in g if r["claw_take"]),
            predators_died_world_survived=sum(1 for r in g if r["pred_gone"] and not r["extinct"]),
            survivors=sum(1 for r in g if not r["extinct"]),
            burrows_late_survivors=float(np.median([np.mean(r["burrows"][-500:]) for r in g if not r["extinct"]]
                                                   or [np.nan])),
            fert_late_survivors=float(np.median([np.nanmean(r["fert"][-500:]) for r in g if not r["extinct"]]
                                                or [np.nan])))
        for role in ROLES:
            for key in ("fitness", "growth"):
                v = [np.nanmean(r[key][role][100:400]) for r in g if np.any(~np.isnan(r[key][role][100:400]))]
                out[s][f"{key}_{role}_10k_40k"] = float(np.median(v)) if v else None
    main = group(runs, set="main")
    ext = [r for r in main if r["extinct"]]
    out["main_fert_min"] = dict(extinct=float(np.median([r["fert_min"] for r in ext])),
                                survived=float(np.median([r["fert_min"] for r in main if not r["extinct"]])))
    for rg in REGENS:
        gs = group(main, regen=rg)
        out["main_fert_min"][rg] = dict(extinct=float(np.median([r["fert_min"] for r in gs if r["extinct"]] or [np.nan])),
                                        survived=float(np.median([r["fert_min"] for r in gs if not r["extinct"]] or [np.nan])))
    out["plant_ratio"] = {rg: {f"{t // 10}k": float(np.median(plant_ratio(runs, rg, t))) for t in (100, 200, 300, 400, 600)}
                          for rg in REGENS}
    # burrowing is the same in both claw sets while the worlds live: median burrows per 100 ticks, ticks 10k-40k
    out["burrows_10k_40k"] = {s: float(np.median([np.nanmean(r["burrows"][100:400]) for r in group(runs, set=s)]))
                              for s in ["main", "nocost"]}
    plants_first = {s: out["pathways"][s].get("plants died first", 0) for s in SETS}
    out["plants_first_tests"] = {
        "main_vs_nocost": fisher(plants_first["main"], 180 - plants_first["main"], plants_first["nocost"],
                                 180 - plants_first["nocost"]),
        "main_vs_noclaw": fisher(plants_first["main"], 180 - plants_first["main"], plants_first["noclaw"],
                                 180 - plants_first["noclaw"])}
    e = {s: out["extinct"][s]["total"] for s in SETS}
    out["extinct_tests"] = {"main_vs_nocost": fisher(e["main"], 180 - e["main"], e["nocost"], 180 - e["nocost"]),
                            "main_vs_noclaw": fisher(e["main"], 180 - e["main"], e["noclaw"], 180 - e["noclaw"]),
                            "noclaw_vs_nocost": fisher(e["noclaw"], 180 - e["noclaw"], e["nocost"], 180 - e["nocost"])}
    # the same sets at regeneration 1-10% (final runs)
    out["final"] = {s: dict(total=sum(int(r["extinct"]) for r in final_rows if r["set"] == s),
                            **{f"regen_{rg}": sum(int(r["extinct"]) for r in final_rows if r["set"] == s
                                                  and r["regen"] == rg) for rg in FINAL_REGENS},
                            **{f"layout_{lay}": sum(int(r["extinct"]) for r in final_rows if r["set"] == s
                                                    and r["layout"] == lay) for lay in LAYOUTS})
                    for s in SETS}
    # expected ticks for a burrowed cell (fertility 0) to regain plant-supporting fertility
    out["recovery_ticks"] = {rg: MIN_PLANT_FERTILITY / REGEN_AMOUNT / (float(rg) / 100) for rg in REGENS + FINAL_REGENS}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default="Observations/slow-regen-runs")
    ap.add_argument("--out", default="results/slow-regen")
    ap.add_argument("--cache")
    ap.add_argument("--final", default="results/claws/tables/runs_dynamics.csv")
    ap.add_argument("--tarique")
    a = ap.parse_args()
    figs, tabs = os.path.join(a.out, "figures"), os.path.join(a.out, "tables")
    os.makedirs(figs, exist_ok=True)
    os.makedirs(tabs, exist_ok=True)
    A.style()
    A.REGENS, A.PATHWAYS, A.PATH_COLORS = REGENS, PATHWAYS, PATH_COLORS
    warnings.simplefilter("ignore", RuntimeWarning)
    runs = [prepare(r) for r in dynamics_load.load_all(a.root, a.cache or os.path.join(a.out, "cache"))]
    with open(a.final, newline="") as f:
        final_rows = list(csv.DictReader(f))
    print(len(runs), "runs,", len(final_rows), "final runs")
    F = lambda name: os.path.join(figs, name)

    fig_extinctions(runs, F("extinctions.png"))
    fig_regen_both(runs, final_rows, F("regen_both.png"))
    fig_fertility_layout(runs, F("fertility_layout.png"))
    fig_population_soil(runs, F("population_soil.png"))
    A.fig_rate(runs, "growth", "growth rate per 100 ticks", "Growth rate of each role (median and interquartile range "
               "over runs, 5,000-tick windows)", F("growth_rate.png"), (-0.05, 0.05), 0)
    A.fig_rate(runs, "fitness", "fitness (offspring per death)", "Fitness of each role (median and interquartile "
               "range over runs, 5,000-tick windows)", F("fitness.png"), (0.6, 1.4), 1)
    A.fig_rate_early(runs, F("growth_fitness_early.png"))
    fig_soil_plants(runs, F("soil_plants.png"))
    A.fig_fertility(runs, F("fertile_share.png"))
    A.fig_pathways(runs, F("pathways.png"))
    fig_collapse_aligned(runs, F("collapse_aligned.png"))
    A.fig_trait_outcomes(runs, F("trait_outcomes.png"))
    if a.tarique:
        A.fig_tarique(A.read_tarique(a.tarique), F("tarique_sweeps.png"))

    by_name = {r["name"]: r for r in runs}
    stories = {}
    pick = lambda s, rg, soil="42", rep=1, lay="dense": by_name[f"{s}-{lay}_soilRegenRate={rg}_seed1_soil{soil}_rep{rep}"]
    # the soil collapse: the main dense run at the slowest rate whose fertility fell the furthest
    soil_crash = min((r for r in group(runs, set="main", layout="dense", regen="0.01") if r["extinct"]),
                     key=lambda r: r["fert_min"])
    twin = pick("nocost", "0.01", soil_crash["soil"], soil_crash["rep"])
    fast = pick("main", "0.1", soil_crash["soil"], soil_crash["rep"])
    stories.update(soil_crash=soil_crash["name"], twin=twin["name"], fast=fast["name"])
    fig_story(soil_crash, f"{A.story_label(soil_crash)}: burrowing strips the soil and the world collapses",
              F("story_soil_crash.png"))
    fig_story(twin, f"{A.story_label(twin)}: the same map with free burrowing", F("story_nocost_twin.png"))
    fig_story(fast, f"{A.story_label(fast)}: the same map with faster regeneration", F("story_fast_regen.png"))
    # a sparse main run in which the plants went first: the median-length one
    sparse = sorted((r for r in group(runs, set="main", layout="sparse") if r["pathway"] == "plants died first"),
                    key=lambda r: r["end_tick"])
    if sparse:
        r = sparse[len(sparse) // 2]
        stories["sparse_plants"] = r["name"]
        fig_story(r, f"{A.story_label(r)}: plants die out first on a sparse map", F("story_sparse_plants.png"))
    noclaw = sorted((r for r in group(runs, set="noclaw", layout="sparse") if r["extinct"] and r["end_tick"] > 60000),
                    key=lambda r: r["end_tick"])
    if noclaw:
        r = noclaw[len(noclaw) // 2]
        stories["noclaw_crash"] = r["name"]
        fig_story(r, f"{A.story_label(r)}: a predator-prey crash without claws", F("story_noclaw_crash.png"))

    rows = A.run_rows(runs)
    for row, r in zip(rows, runs):
        row["fert_min"] = round(r["fert_min"], 2)
        row["first_gone"] = r["first_gone"] if r["extinct"] else ""
    A.write_csv(os.path.join(tabs, "runs_dynamics.csv"), rows)
    nums = numbers(runs, final_rows)
    nums["stories"] = stories
    with open(os.path.join(tabs, "numbers.json"), "w") as f:
        json.dump(nums, f, indent=1, default=float)
    print(json.dumps({key: nums[key] for key in ("pathways", "stories")}))


if __name__ == "__main__":
    main()
