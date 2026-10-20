"""Analysis of the final-runs batch (headless/experiments/final_runs.json): outcomes per set, map and map type,
extinction events and evolutionary-suicide candidates, and the stories of a few runs.

Usage:
    python analysis/final_analysis.py [Observations/final-runs] [--out results]

Run folders are named <set>-<layout>_soilRegenRate=<rate>_seed1_soil<soil seed>_rep<n>, where
  set     main (claws can evolve, burrowing costs soil), noclaw (claws can't evolve), nocost (burrowing is free)
  map     layout x soil seed (15), map type: map x soil regen rate (60), 3 replicates each.

Per run, from the logs (sampled every 100 ticks):
  outcome          survived / extinct (everything died) and, separately, whether all prey died
  claw evolved     first tick a prey carries a claw (role "Prey (burrowing)" in groups_log)
  take-over        first tick with >= 50 clawed prey making up >= half of all prey (the group's definition)
  role extinctions last tick each role (plants, predators, prey) was alive, if it died out before the end

Extinctions are classified as
  early collapse     everything died before EARLY_TICKS, with no claw take-over: an overshoot crash
  after take-over    all prey died after clawed prey had taken over: the evolutionary-suicide candidates. "Strong"
                     when clawed prey were still at least half of the prey in the last LAST_WINDOW ticks before the prey
                     died (the trait that spread went down with the world). The soil (mean fertility and degraded
                     fraction) at take-over and before the collapse is recorded alongside, as evidence for or against
                     the burrowing having worn out the soil
  late, no take-over everything else

Writes figures/ and tables/ (CSV) under --out, and tables/numbers.json with the headline numbers.
"""
import argparse
import csv
import glob
import json
import math
import os
import re
import warnings
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SETS = ["main", "noclaw", "nocost"]
SET_NAMES = {"main": "main (claws, burrow cost)", "noclaw": "noclaw (control)", "nocost": "nocost (free burrowing)"}
SET_COLORS = {"main": "#1f77b4", "noclaw": "#7f7f7f", "nocost": "#2ca02c"}
LAYOUTS = ["dense", "medium", "sparse"]
REGENS = ["1", "2.5", "5", "10"]
SOILS = ["42", "7", "123", "2024", "99"]
ROLE_COLORS = {"Plants": "#2ca02c", "Predators": "#d62728", "Prey (non-burrowing)": "#1f77b4",
               "Prey (burrowing)": "#ff7f0e"}
ROLE_LABELS = {"Plants": "plants", "Predators": "predators", "Prey (non-burrowing)": "prey without claw",
               "Prey (burrowing)": "prey with claw"}
NAME_RE = re.compile(r"(main|noclaw|nocost)-(dense|medium|sparse)_soilRegenRate=([\d.]+)_seed1_soil(\d+)_rep(\d+)$")
TICKS = 250000
EARLY_TICKS = 30000
LAST_WINDOW = 5000
TAKE_OVER_COUNT = 50


def one(folder, prefix):
    paths = sorted(glob.glob(os.path.join(folder, prefix + "*.csv")))
    return paths[-1] if paths else None


def read_run(folder):
    m = NAME_RE.match(os.path.basename(folder.rstrip("/")))
    if not m:
        return None
    exp, layout, regen, soil, rep = m.groups()
    status = json.load(open(os.path.join(folder, "status.json")))
    roles = defaultdict(dict)  # role -> tick -> population
    # long runs write the groups log in numbered parts (groups_log_part1_..., groups_log_part2_...)
    for path in glob.glob(os.path.join(folder, "groups_log*.csv")):
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                if r["grouping"] == "role":
                    roles[r["group"]][int(r["tick"])] = int(r["population"])
    ts = {"tick": [], "soil_mean": [], "soil_degraded_frac": [], "burrows": [], "hidden": [], "population": []}
    with open(one(folder, "timeseries"), newline="") as f:
        for r in csv.DictReader(f):
            for k in ts:
                ts[k].append(float(r[k]) if r[k] != "" else float("nan"))
    config = {}
    with open(one(folder, "run_config"), newline="") as f:
        for r in csv.reader(f):
            if len(r) == 2:
                config[r[0]] = r[1]
    events = []
    with open(one(folder, "key_moments"), newline="") as f:
        for r in csv.DictReader(f):
            events.append((int(r["tick"]), r["type"], r["label"]))
    ticks = [int(t) for t in ts["tick"]]
    pops = {role: np.array([roles[role].get(t, 0) for t in ticks]) for role in ROLE_COLORS}
    return dict(folder=folder, name=os.path.basename(folder.rstrip("/")), set=exp, layout=layout, regen=regen,
                soil=soil, rep=int(rep), map=layout + "-" + soil, status=status, ticks=np.array(ticks), pops=pops,
                soil_mean=np.array(ts["soil_mean"]), degraded=np.array(ts["soil_degraded_frac"]),
                burrows=np.array(ts["burrows"]), hidden=np.array(ts["hidden"]),
                fertile=float(config.get("soil_fertile_frac", "nan")), events=events)


def last_alive(ticks, pop):
    alive = np.nonzero(pop > 0)[0]
    return int(ticks[alive[-1]]) if len(alive) else None


def measure(run):
    t = run["ticks"]
    p = run["pops"]
    claw, plain = p["Prey (burrowing)"], p["Prey (non-burrowing)"]
    prey = claw + plain
    end = int(t[-1])
    extinct = run["status"]["state"] == "extinct"
    res = dict(name=run["name"], set=run["set"], layout=run["layout"], regen=run["regen"], soil=run["soil"],
               rep=run["rep"], map=run["map"], fertile_frac=round(run["fertile"], 4), end_tick=end,
               extinct=int(extinct))
    # role extinctions: died out before the end of the run (a role alive in the last sample survived)
    for role, key in [("Plants", "plants"), ("Predators", "predators")]:
        la = last_alive(t, p[role])
        res[key + "_died"] = la if (la is not None and la < end) or extinct else ""
    la = last_alive(t, prey)
    prey_died = la is not None and (la < end or extinct)
    res["prey_died"] = la if prey_died else ""
    res["all_prey_died"] = int(prey_died)
    first_claw = np.nonzero(claw > 0)[0]
    res["claw_evolved"] = int(t[first_claw[0]]) if len(first_claw) else ""
    share = np.where(prey > 0, claw / np.maximum(prey, 1), 0)
    take = np.nonzero((claw >= TAKE_OVER_COUNT) & (share >= 0.5))[0]
    res["take_over"] = int(t[take[0]]) if len(take) else ""
    res["peak_claw_share"] = round(float(share.max()), 3) if len(share) else 0
    res["peak_clawed_prey"] = int(claw.max()) if len(claw) else 0
    res["final_plants"], res["final_predators"] = int(p["Plants"][-1]), int(p["Predators"][-1])
    res["final_prey_plain"], res["final_prey_claw"] = int(plain[-1]), int(claw[-1])
    res["final_claw_share"] = round(float(share[-1]), 3)
    res["claw_common_end"] = int(claw[-1] >= TAKE_OVER_COUNT)
    res["soil_mean_start"] = round(float(run["soil_mean"][0]), 3)
    res["soil_mean_min"] = round(float(np.nanmin(run["soil_mean"])), 3)
    res["total_burrows"] = int(np.nansum(run["burrows"]))
    # which role vanished first
    died = [(res[k], k) for k in ["plants_died", "predators_died", "prey_died"] if res[k] != ""]
    res["first_to_die"] = min(died)[1].replace("_died", "") if died else ""
    # extinction class
    cls, strong = "", 0
    if prey_died or extinct:
        stop = la if la is not None else end
        if res["take_over"] != "" and res["take_over"] < stop:
            cls = "after take-over"
            window = (t >= stop - LAST_WINDOW) & (t <= stop)
            late_share = float(np.nanmean(share[window])) if window.any() else 0
            i_take = int(np.searchsorted(t, res["take_over"]))
            soil_at_take = float(run["soil_mean"][i_take])
            soil_before = float(np.nanmean(run["soil_mean"][window])) if window.any() else soil_at_take
            res["claw_share_before_collapse"] = round(late_share, 3)
            res["soil_at_take_over"] = round(soil_at_take, 3)
            res["soil_before_collapse"] = round(soil_before, 3)
            res["degraded_at_take_over"] = round(float(run["degraded"][i_take]), 3)
            res["degraded_before_collapse"] = round(float(np.nanmean(run["degraded"][window])), 3) if window.any() else ""
            strong = int(late_share >= 0.5)
        elif extinct and end < EARLY_TICKS:
            cls = "early collapse"
        else:
            cls = "late, no take-over"
    res["extinction_class"] = cls
    res["suicide_strong"] = strong
    for k in ["claw_share_before_collapse", "soil_at_take_over", "soil_before_collapse", "degraded_at_take_over",
              "degraded_before_collapse"]:
        res.setdefault(k, "")
    return res


def fisher(a, b, c, d):
    """Two-sided Fisher's exact test for [[a, b], [c, d]]."""
    n, r1, c1 = a + b + c + d, a + b, a + c
    def p(x):
        return math.comb(r1, x) * math.comb(n - r1, c1 - x) / math.comb(n, c1)
    p0 = p(a)
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= p0 * (1 + 1e-9)))


def sign_test(wins, losses):
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def style():
    # Computer Modern (matplotlib's bundled cmr10), to match the report
    plt.rcParams.update({"font.family": "serif", "font.serif": ["cmr10", "DejaVu Serif"], "mathtext.fontset": "cm",
                         "axes.formatter.use_mathtext": True, "axes.unicode_minus": False, "font.size": 9, "axes.titlesize": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "savefig.dpi": 200, "savefig.bbox": "tight"})


def fig_outcomes(rows, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), sharey=False)
    w = 0.26
    for k, (metric, title) in enumerate([("extinct", "Runs that went extinct (%)"),
                                         ("claw_common_end", "Runs ending with at least 50 clawed prey (%)")]):
        ax = axes[k]
        for i, s in enumerate(SETS):
            vals = [100 * np.mean([r[metric] for r in rows if r["set"] == s and r["layout"] == l]) for l in LAYOUTS]
            bars = ax.bar(np.arange(3) + (i - 1) * w, vals, w - 0.03, color=SET_COLORS[s], label=SET_NAMES[s])
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, v + 1.5, "%d" % round(v), ha="center", fontsize=7)
        ax.set_xticks(range(3), LAYOUTS)
        ax.set_ylim(0, 105)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(frameon=False, fontsize=7, loc="upper left")
    fig.savefig(path)
    plt.close(fig)


def fig_by_regen(rows, path):
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.5), sharey=True)
    for k, l in enumerate(LAYOUTS):
        ax = axes[k]
        for s in SETS:
            vals = [100 * np.mean([r["extinct"] for r in rows if r["set"] == s and r["layout"] == l and r["regen"] == g])
                    for g in REGENS]
            ax.plot(range(4), vals, "-o", color=SET_COLORS[s], ms=4, lw=1.5, label=SET_NAMES[s])
        ax.set_xticks(range(4), [g + "%" for g in REGENS])
        ax.set_title(l)
        ax.set_xlabel("soil regen chance per tick")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("runs extinct (%)")
    axes[0].set_ylim(-3, 103)
    axes[1].legend(frameon=False, fontsize=7, loc="upper right")
    fig.savefig(path)
    plt.close(fig)


def fig_survival(runs, path):
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.5), sharey=True)
    grid = np.arange(0, TICKS + 1, 1000)
    for k, l in enumerate(LAYOUTS):
        ax = axes[k]
        for s in SETS:
            ends = [r["end_tick"] if r["extinct"] else TICKS + 1 for r in runs if r["set"] == s and r["layout"] == l]
            alive = [100 * np.mean([e > g for e in ends]) for g in grid]
            ax.step(grid / 1000, alive, where="post", color=SET_COLORS[s], lw=1.5, label=SET_NAMES[s])
        ax.set_title(l)
        ax.set_xlabel("tick (thousands)")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("worlds still alive (%)")
    axes[0].set_ylim(0, 103)
    axes[0].legend(frameon=False, fontsize=7, loc="lower left")
    fig.savefig(path)
    plt.close(fig)


def map_type_matrix(rows, s, metric):
    """15 maps (rows) x 4 regen rates: number of the 3 replicates with metric set."""
    m = np.zeros((15, 4))
    for i, (l, soil) in enumerate([(l, so) for l in LAYOUTS for so in SOILS]):
        for j, g in enumerate(REGENS):
            m[i, j] = sum(r[metric] for r in rows if r["set"] == s and r["layout"] == l and r["soil"] == soil
                          and r["regen"] == g)
    return m


def fig_map_types(rows, metric, title, path, cmap):
    labels = [l + " / soil " + so for l in LAYOUTS for so in SOILS]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 4.6), sharey=True)
    for k, s in enumerate(SETS):
        m = map_type_matrix(rows, s, metric)
        ax = axes[k]
        ax.imshow(m, cmap=cmap, vmin=0, vmax=3, aspect="auto")
        for i in range(15):
            for j in range(4):
                ax.text(j, i, "%d" % m[i, j], ha="center", va="center", fontsize=7,
                        color="white" if m[i, j] >= 2 else "black")
        ax.set_xticks(range(4), [g + "%" for g in REGENS])
        ax.set_title(SET_NAMES[s], fontsize=8)
        for y in (4.5, 9.5):
            ax.axhline(y, color="black", lw=0.8)
        ax.set_xlabel("soil regen chance")
        for sp in ax.spines.values():
            sp.set_visible(False)
    axes[0].set_yticks(range(15), labels, fontsize=7)
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_maps(map_rows, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8))
    ax = axes[0]
    labels = [m["map"] for m in map_rows]
    x = np.arange(len(labels))
    w = 0.27
    for i, s in enumerate(SETS):
        ax.bar(x + (i - 1) * w, [m[s + "_extinct"] for m in map_rows], w - 0.03, color=SET_COLORS[s], label=SET_NAMES[s])
    ax.set_xticks(x, labels, rotation=70, fontsize=6.5)
    ax.set_ylabel("extinct runs (of 12)")
    ax.set_title("Extinctions per map")
    ax.legend(frameon=False, fontsize=6.5)
    ax.grid(axis="y", alpha=0.3)
    ax = axes[1]
    for i, s in enumerate(SETS):
        # nudged sideways per set so overlapping points stay visible
        ax.scatter([100 * m["fertile_frac"] + (i - 1) * 0.6 for m in map_rows], [m[s + "_extinct"] for m in map_rows], s=18,
                   color=SET_COLORS[s], label=SET_NAMES[s], alpha=0.85, edgecolor="white", lw=0.5)
    ax.set_xlabel("fertile soil on the map (%)")
    ax.set_ylabel("extinct runs (of 12)")
    ax.set_title("Extinctions vs how fertile the map is")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_extinction_events(rows, path):
    ext = [r for r in rows if r["extinct"] or r["all_prey_died"]]
    classes = ["early collapse", "late, no take-over", "after take-over"]
    markers = {"early collapse": "v", "late, no take-over": "s", "after take-over": "o"}
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9), gridspec_kw={"width_ratios": [2.2, 1]})
    ax = axes[0]
    ypos = {(s, l): k for k, (s, l) in enumerate([(s, l) for s in SETS for l in LAYOUTS])}
    rng = np.random.default_rng(0)
    for r in ext:
        stop = r["prey_died"] if r["prey_died"] != "" else r["end_tick"]
        y = ypos[(r["set"], r["layout"])] + rng.uniform(-0.3, 0.3)
        face = SET_COLORS[r["set"]] if not r["suicide_strong"] else "black"
        ax.scatter(stop / 1000, y, marker=markers[r["extinction_class"]], s=16, color=face, alpha=0.8, lw=0)
    ax.set_yticks(list(ypos.values()), [s + " / " + l for s, l in ypos], fontsize=7)
    ax.set_xlabel("tick the prey (and usually the world) died (thousands)")
    ax.set_xlim(0, 255)
    ax.grid(axis="x", alpha=0.3)
    for c in classes:
        ax.scatter([], [], marker=markers[c], color="#555", label=c, s=16)
    ax.scatter([], [], marker="o", color="black", label="strong suicide candidate", s=16)
    ax.legend(frameon=False, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=4)
    ax.set_title("Every extinction event")
    ax = axes[1]
    bottom = np.zeros(3)
    ccol = {"early collapse": "#bbbbbb", "late, no take-over": "#777777", "after take-over": "#ff7f0e"}
    for c in classes:
        vals = np.array([sum(1 for r in ext if r["set"] == s and r["extinction_class"] == c) for s in SETS])
        ax.bar(range(3), vals, bottom=bottom, color=ccol[c], label=c, width=0.6)
        bottom += vals
    ax.set_xticks(range(3), SETS)
    ax.set_ylabel("runs where all prey died")
    ax.set_title("Kinds of extinction")
    ax.legend(frameon=False, fontsize=6.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_claw_share(runs, path):
    """Share of prey carrying a claw over time, mean over the runs with prey alive, per set (rows) and layout
    (columns), one line per soil regen rate."""
    grid = np.arange(0, TICKS + 1, 1000)
    regen_colors = {"1": "#fdae6b", "2.5": "#fd8d3c", "5": "#e6550d", "10": "#a63603"}
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 3.8), sharex=True, sharey=True)
    for i, s in enumerate(["main", "nocost"]):
        for k, l in enumerate(LAYOUTS):
            ax = axes[i, k]
            for g in REGENS:
                curves = []
                for r in runs:
                    if r["set"] != s or r["layout"] != l or r["regen"] != g:
                        continue
                    claw = r["pops"]["Prey (burrowing)"].astype(float)
                    prey = claw + r["pops"]["Prey (non-burrowing)"]
                    share = np.where(prey > 0, claw / np.maximum(prey, 1), np.nan)
                    curves.append(np.interp(grid, r["ticks"], share, right=np.nan))
                with warnings.catch_warnings():  # ticks after every run's prey died are all-NaN
                    warnings.simplefilter("ignore", RuntimeWarning)
                    mean = np.nanmean(np.array(curves), axis=0)
                ax.plot(grid / 1000, 100 * mean, color=regen_colors[g], lw=1.2, label=g + "% regen")
            ax.set_title(SET_NAMES[s].split(" ")[0] + " / " + l, fontsize=8)
            ax.grid(alpha=0.3)
            ax.set_ylim(0, 102)
        axes[i, 0].set_ylabel("prey with claw (%)")
    for ax in axes[1]:
        ax.set_xlabel("tick (thousands)")
    axes[0, 0].legend(frameon=False, fontsize=6.5, loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_story(run, res, title, path):
    t = run["ticks"] / 1000
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 4.6), sharex=True, gridspec_kw={"height_ratios": [2.2, 1, 1]})
    ax = axes[0]
    for role in ROLE_COLORS:
        ax.plot(t, run["pops"][role], color=ROLE_COLORS[role], lw=1, label=ROLE_LABELS[role])
    ax.set_ylabel("population")
    ax.legend(frameon=False, fontsize=7, ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    ax.set_title(title, fontsize=9, pad=18)
    claw, plain = run["pops"]["Prey (burrowing)"], run["pops"]["Prey (non-burrowing)"]
    prey = claw + plain
    share = np.where(prey > 0, claw / np.maximum(prey, 1), np.nan)
    axes[1].plot(t, 100 * share, color=ROLE_COLORS["Prey (burrowing)"], lw=1)
    axes[1].set_ylabel("prey with\nclaw (%)")
    axes[1].set_ylim(-3, 103)
    axes[2].plot(t, run["soil_mean"], color="#8c564b", lw=1, label="mean soil fertility")
    axes[2].set_ylabel("soil\nfertility")
    ax2 = axes[2].twinx()
    ax2.plot(t, run["hidden"], color="#9467bd", lw=0.6, alpha=0.6)
    ax2.set_ylabel("underground", color="#9467bd", fontsize=7)
    ax2.tick_params(axis="y", colors="#9467bd", labelsize=7)
    ax2.spines["top"].set_visible(False)
    axes[2].set_xlabel("tick (thousands)")
    marks = []
    if res["claw_evolved"] != "":
        marks.append((res["claw_evolved"], "claw evolves"))
    if res["take_over"] != "":
        marks.append((res["take_over"], "take-over"))
    for k, lab in [("predators_died", "predators gone"), ("prey_died", "prey gone"), ("plants_died", "plants gone")]:
        if res[k] != "":
            marks.append((res[k], lab))
    # marks close together (e.g. prey, predators and plants dying within a few thousand ticks) share one label
    merged = []
    for tick, lab in sorted(marks):
        if merged and tick - merged[-1][0] < 0.03 * t[-1] * 1000:
            merged[-1] = (merged[-1][0], merged[-1][1] + ", " + lab)
        else:
            merged.append((tick, lab))
    for tick, _ in marks:
        for a in axes:
            a.axvline(tick / 1000, color="black", lw=0.6, ls=":")
    for tick, lab in merged:
        axes[0].text(tick / 1000, axes[0].get_ylim()[1] * 0.97, " " + lab, fontsize=6.5, rotation=90, va="top",
                     bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=0.5))
    for a in axes:
        a.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("batch", nargs="?", default="Observations/final-runs")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()
    figs, tables = os.path.join(args.out, "figures"), os.path.join(args.out, "tables")
    os.makedirs(figs, exist_ok=True)
    os.makedirs(tables, exist_ok=True)
    style()

    runs = [r for r in (read_run(d) for d in sorted(glob.glob(os.path.join(args.batch, "*/")))) if r]
    print("read", len(runs), "runs")
    rows = [measure(r) for r in runs]
    by_name = {r["name"]: r for r in runs}
    write_csv(os.path.join(tables, "runs.csv"), rows)

    nums = {"runs": len(rows)}
    # outcomes per set x layout
    summary = []
    for s in SETS:
        for l in LAYOUTS + ["all"]:
            sel = [r for r in rows if r["set"] == s and (l == "all" or r["layout"] == l)]
            summary.append(dict(set=s, layout=l, runs=len(sel), extinct=sum(r["extinct"] for r in sel),
                                all_prey_died=sum(r["all_prey_died"] for r in sel),
                                claw_evolved=sum(r["claw_evolved"] != "" for r in sel),
                                take_over=sum(r["take_over"] != "" for r in sel),
                                claw_common_end=sum(r["claw_common_end"] for r in sel)))
    write_csv(os.path.join(tables, "outcomes_by_set_layout.csv"), summary)
    nums["outcomes"] = summary

    # tests: extinctions between sets, overall and per layout
    tests = []
    for a, b in [("main", "noclaw"), ("main", "nocost"), ("nocost", "noclaw")]:
        for l in LAYOUTS + ["all"]:
            sa = [r for r in rows if r["set"] == a and (l == "all" or r["layout"] == l)]
            sb = [r for r in rows if r["set"] == b and (l == "all" or r["layout"] == l)]
            ea, eb = sum(r["extinct"] for r in sa), sum(r["extinct"] for r in sb)
            tests.append(dict(comparison=a + " vs " + b, layout=l, extinct_a=ea, runs_a=len(sa), extinct_b=eb,
                              runs_b=len(sb), fisher_p=fisher(ea, len(sa) - ea, eb, len(sb) - eb)))
    # per layout x regen, main vs nocost and main vs noclaw
    for a, b in [("main", "noclaw"), ("main", "nocost")]:
        for l in LAYOUTS:
            for g in REGENS:
                sa = [r for r in rows if r["set"] == a and r["layout"] == l and r["regen"] == g]
                sb = [r for r in rows if r["set"] == b and r["layout"] == l and r["regen"] == g]
                ea, eb = sum(r["extinct"] for r in sa), sum(r["extinct"] for r in sb)
                tests.append(dict(comparison=a + " vs " + b, layout=l + " @ " + g + "%", extinct_a=ea, runs_a=len(sa),
                                  extinct_b=eb, runs_b=len(sb), fisher_p=fisher(ea, len(sa) - ea, eb, len(sb) - eb)))
    write_csv(os.path.join(tables, "tests_extinction.csv"), tests)
    nums["tests"] = tests

    # per map type (60): extinct replicates per set, paired comparisons across map types (sign test)
    mt_rows = []
    for l in LAYOUTS:
        for so in SOILS:
            for g in REGENS:
                row = dict(map_type=l + "-" + so + " @ " + g + "%", layout=l, soil=so, regen=g)
                for s in SETS:
                    sel = [r for r in rows if r["set"] == s and r["layout"] == l and r["soil"] == so and r["regen"] == g]
                    row[s + "_extinct"] = sum(r["extinct"] for r in sel)
                    row[s + "_claw_common"] = sum(r["claw_common_end"] for r in sel)
                mt_rows.append(row)
    write_csv(os.path.join(tables, "map_types.csv"), mt_rows)
    paired = {}
    for a, b in [("main", "noclaw"), ("main", "nocost")]:
        worse_b = sum(1 for m in mt_rows if m[b + "_extinct"] > m[a + "_extinct"])
        worse_a = sum(1 for m in mt_rows if m[a + "_extinct"] > m[b + "_extinct"])
        paired[a + " vs " + b] = dict(b_worse=worse_b, a_worse=worse_a, ties=60 - worse_a - worse_b,
                                      sign_p=sign_test(worse_b, worse_a))
    nums["map_type_paired"] = paired
    nums["map_types_any_extinction"] = {s: sum(1 for m in mt_rows if m[s + "_extinct"] > 0) for s in SETS}
    nums["map_types_all_extinct"] = {s: sum(1 for m in mt_rows if m[s + "_extinct"] == 3) for s in SETS}
    nums["map_types_split"] = {s: sum(1 for m in mt_rows if 0 < m[s + "_extinct"] < 3) for s in SETS}

    # per map (15): over the 4 regen rates x 3 replicates
    map_rows = []
    for l in LAYOUTS:
        for so in SOILS:
            sel = [r for r in rows if r["layout"] == l and r["soil"] == so]
            row = dict(map=l + "-" + so, layout=l, soil=so, fertile_frac=sel[0]["fertile_frac"])
            for s in SETS:
                ss = [r for r in sel if r["set"] == s]
                row[s + "_extinct"] = sum(r["extinct"] for r in ss)
                row[s + "_claw_common"] = sum(r["claw_common_end"] for r in ss)
            map_rows.append(row)
    write_csv(os.path.join(tables, "maps.csv"), map_rows)
    nums["maps"] = map_rows
    # fertile fraction vs extinctions (Spearman, by hand) per set
    def ranks(v):
        order = np.argsort(v)
        r = np.empty(len(v))
        r[order] = np.arange(len(v))
        for val in set(v):  # average ties
            idx = [i for i, x in enumerate(v) if x == val]
            r[idx] = np.mean(r[idx])
        return r
    nums["fertile_vs_extinct_spearman"] = {}
    for s in SETS:
        x, y = ranks([m["fertile_frac"] for m in map_rows]), ranks([m[s + "_extinct"] for m in map_rows])
        nums["fertile_vs_extinct_spearman"][s] = round(float(np.corrcoef(x, y)[0, 1]), 3)

    # extinction events
    ext = [r for r in rows if r["extinct"] or r["all_prey_died"]]
    write_csv(os.path.join(tables, "extinctions.csv"), ext,
              ["name", "set", "layout", "regen", "soil", "rep", "extinct", "end_tick", "first_to_die", "prey_died",
               "predators_died", "plants_died", "claw_evolved", "take_over", "peak_claw_share",
               "claw_share_before_collapse", "soil_at_take_over", "soil_before_collapse", "degraded_at_take_over",
               "degraded_before_collapse", "extinction_class",
               "suicide_strong"])
    nums["extinction_classes"] = {s: {c: sum(1 for r in ext if r["set"] == s and r["extinction_class"] == c)
                                      for c in ["early collapse", "late, no take-over", "after take-over"]} for s in SETS}
    nums["strong_suicide"] = {s: sum(r["suicide_strong"] for r in ext if r["set"] == s) for s in SETS}
    nums["prey_died_not_world"] = sum(1 for r in rows if r["all_prey_died"] and not r["extinct"])
    nums["first_to_die"] = {s: {k: sum(1 for r in ext if r["set"] == s and r["first_to_die"] == k)
                                for k in ["predators", "prey", "plants"]} for s in SETS}
    nums["extinct_tick_median"] = {s: float(np.median([r["end_tick"] for r in ext if r["set"] == s and r["extinct"]]))
                                   for s in SETS if any(r["extinct"] for r in ext if r["set"] == s)}
    # claw timing
    ce = [r["claw_evolved"] for r in rows if r["set"] != "noclaw" and r["claw_evolved"] != ""]
    to = [r["take_over"] for r in rows if r["set"] != "noclaw" and r["take_over"] != ""]
    nums["claw_evolved_median"], nums["take_over_median"] = float(np.median(ce)), float(np.median(to))
    nums["claw_evolved_runs"] = len(ce)
    nums["take_over_runs"] = len(to)
    surv = [r for r in rows if r["set"] == "main" and not r["extinct"]]
    nums["main_survivors"] = len(surv)
    nums["main_survivors_claw_common"] = sum(r["claw_common_end"] for r in surv)

    # figures
    fig_outcomes(rows, os.path.join(figs, "outcomes.png"))
    fig_by_regen(rows, os.path.join(figs, "extinction_by_regen.png"))
    fig_survival(rows, os.path.join(figs, "survival.png"))
    fig_map_types(rows, "extinct", "Extinct replicates (of 3) per map type", os.path.join(figs, "map_types_extinct.png"),
                  "Reds")
    fig_map_types(rows, "claw_common_end", "Replicates ending with at least 50 clawed prey (of 3) per map type",
                  os.path.join(figs, "map_types_claw.png"), "Oranges")
    fig_maps(map_rows, os.path.join(figs, "maps.png"))
    fig_claw_share(runs, os.path.join(figs, "claw_share.png"))
    fig_extinction_events(rows, os.path.join(figs, "extinction_events.png"))

    # stories: picked by rule, so the choice is reproducible
    res_by = {r["name"]: r for r in rows}
    def pick(cond, key):
        cands = [r for r in rows if cond(r)]
        return sorted(cands, key=key)[0] if cands else None
    stories = []
    s1 = pick(lambda r: r["set"] == "main" and r["suicide_strong"] and r["take_over"] != "",
              lambda r: -(r["prey_died"] - r["take_over"]))
    if s1:
        stories.append(("suicide", s1, "Evolutionary-suicide candidate: clawed prey take over, then all prey die out"))
    s2 = pick(lambda r: r["set"] == "main" and r["layout"] == "dense" and not r["extinct"] and r["claw_common_end"]
              and r["take_over"] != "",
              lambda r: r["take_over"])
    if s2:
        stories.append(("takeover", s2, "Claws take over and the world persists"))
    s3 = pick(lambda r: r["set"] == "noclaw" and r["layout"] == "sparse" and r["extinct"] and r["end_tick"] > EARLY_TICKS,
              lambda r: abs(r["end_tick"] - 100000))
    if s3:
        stories.append(("control", s3, "Control without claws: prey cannot hide and the world collapses"))
    # same map type, claws vs no claws in different replicates
    split = None
    for m in mt_rows:
        sel = [r for r in rows if r["set"] == "main" and r["layout"] == m["layout"] and r["soil"] == m["soil"]
               and r["regen"] == m["regen"]]
        if m["layout"] != "sparse" and not any(r["extinct"] for r in sel) and \
                any(r["take_over"] == "" for r in sel) and any(r["take_over"] != "" for r in sel):
            split = sel
            break
    if split:
        a = min((r for r in split if r["take_over"] != ""), key=lambda r: r["take_over"])
        b = next(r for r in split if r["take_over"] == "")
        stories.append(("split_a", a, "Same map, same start (1/2): this replicate's prey evolve claws that spread"))
        stories.append(("split_b", b, "Same map, same start (2/2): here the claw never spreads"))
    s5 = pick(lambda r: r["set"] == "nocost" and r["layout"] == "sparse" and r["regen"] == "1" and not r["extinct"]
              and r["claw_common_end"], lambda r: r["soil"])
    if s5:
        stories.append(("nocost", s5, "Free burrowing on sparse, slowly regrowing soil: claws spread and the world survives"))
    s6 = pick(lambda r: r["extinct"] and r["extinction_class"] == "early collapse", lambda r: r["end_tick"])
    if s6:
        stories.append(("early", s6, "Early overshoot collapse"))
    nums["stories"] = []
    for key, r, title in stories:
        # Computer Modern has no underscore glyph, so the run is named in words
        label = "%s, %s soil %s, %s%% regen, replicate %d" % (r["set"], r["layout"], r["soil"], r["regen"], r["rep"])
        fig_story(by_name[r["name"]], r, title + "\n" + label, os.path.join(figs, "story_" + key + ".png"))
        nums["stories"].append(dict(key=key, title=title, **{k: r[k] for k in r}))
    with open(os.path.join(tables, "numbers.json"), "w") as f:
        json.dump(nums, f, indent=1, default=str)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
