"""Figures for the presentation, drawn in the Life Engine's neon colour scheme.

Usage (from the repository root):
    python Presentation/deck/make_figures.py

Reads the batches in Observations/ and writes PNGs to Presentation/deck/figures/.
"""
import collections
import csv
import glob
import json
import os
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OBS = os.path.join(ROOT, "Observations")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import claw_evolution  # noqa: E402

# the Life Engine's "neon" cell colours (src/Rendering/ColorScheme.js)
BG = "#0E1318"
PANEL = "#121A22"
INK = "#E6EDF3"
MUTED = "#8B98A8"
GRID = "#223040"
CLAW = "#FF6B35"
PREY = "#60D4FF"
KILLER = "#F82380"
PRODUCER = "#15DE59"
MOUTH = "#DEB14D"
ARMOR = "#7230DB"
EYE = "#B6C1EA"
FOOD = "#2F7AB7"

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": PANEL, "savefig.facecolor": BG,
    "axes.edgecolor": GRID, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "grid.color": GRID, "grid.linewidth": 0.8,
    "font.size": 13, "axes.titlesize": 14, "axes.labelsize": 13, "legend.fontsize": 12,
    "font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False,
})


def rows(folder, prefix):
    out = []
    for path in sorted(glob.glob(os.path.join(folder, prefix + "*.csv"))):
        with open(path, newline="") as f:
            out.extend(csv.DictReader(f))
    return out


def role_pops(folder):
    pop = collections.defaultdict(dict)
    for r in rows(folder, "groups_log"):
        if r["grouping"] == "role":
            pop[r["group"]][int(r["tick"])] = float(r["population"])
    return pop


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, name), dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


def thousands(ax):
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: "%dk" % (x / 1000) if x else "0"))


def status(folder):
    return json.load(open(os.path.join(folder, "status.json")))


def extinction_timing():
    """When the 160 whole-world extinctions of batches 1 and 2 happened."""
    ends = []
    for folder in glob.glob(os.path.join(OBS, "claw-soil-predator", "*_seed*")) + glob.glob(os.path.join(OBS, "soil-layouts", "*_seed*")):
        s = status(folder)
        if s["state"] == "extinct":
            ends.append(s["tick"])
    fig, ax = plt.subplots(figsize=(10, 4.2))
    bins = list(range(0, 260000, 10000))
    phases = [(0, 30000, KILLER, "early: seeded predators overshoot"), (30000, 100000, MOUTH, "30k–100k"),
              (100000, 260000, CLAW, "late: evolved predators")]
    for lo, hi, color, label in phases:
        part = [e for e in ends if lo <= e < hi]
        ax.hist(part, bins=bins, color=color, edgecolor=BG, linewidth=1.5, label="%s (%d)" % (label, len(part)))
    ax.set_xlabel("Tick the world died")
    ax.set_ylabel("Runs")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    thousands(ax)
    ax.legend(loc="upper right")
    save(fig, "extinction_timing.png")
    return len(ends)


def early_wave():
    """Browser run with claws costing food: the seeded predators' boom wipes out the burrowing prey."""
    pop = role_pops(os.path.join(OBS, "claw dies out (not free)"))
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for role, color, label in (("Predators", KILLER, "Predators"), ("Prey (non-burrowing)", PREY, "Prey without claws"),
                               ("Prey (burrowing)", CLAW, "Prey with claws")):
        ticks = sorted(t for t in pop[role] if t <= 12000)
        ax.plot(ticks, [pop[role][t] for t in ticks], color=color, linewidth=2.6, label=label)
    ax.set_xlabel("Tick")
    ax.set_ylabel("Organisms")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    thousands(ax)
    ax.legend(loc="upper right")
    save(fig, "early_wave.png")


def collapse_chain():
    """One run where claws evolved, took over, wore down the soil, the plants crashed and the prey died out."""
    folder = os.path.join(OBS, "claw-evolution", "evolved-free-burrow_seed6_soil11")
    pop = role_pops(folder)
    ts = {int(r["tick"]): r for r in rows(folder, "timeseries")}
    start = float(ts[100]["soil_mean"])
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True, gridspec_kw={"height_ratios": [2.3, 1]})
    for role, color, label in (("Plants", PRODUCER, "Plants"), ("Prey (burrowing)", CLAW, "Prey with claws"),
                               ("Prey (non-burrowing)", PREY, "Prey without claws"), ("Predators", KILLER, "Predators")):
        ticks = sorted(pop[role])
        ax.plot(ticks, [pop[role][t] for t in ticks], color=color, linewidth=2.2, label=label)
    ax.set_ylabel("Organisms")
    ax.grid(axis="y")
    ax.legend(loc="upper right", ncol=2)
    ticks = sorted(t for t in ts if ts[t]["soil_mean"])
    ax2.plot(ticks, [100 * float(ts[t]["soil_mean"]) / start for t in ticks], color=MOUTH, linewidth=2.4)
    ax2.set_ylabel("Soil (% of start)")
    ax2.set_ylim(70, 102)
    ax2.grid(axis="y")
    ax2.set_xlabel("Tick")
    thousands(ax2)
    for a in (ax, ax2):
        a.set_axisbelow(True)
    fig.tight_layout()
    save(fig, "collapse_chain.png")


def claw_spread():
    """Starting with no claws: the share of prey carrying an evolved claw, with burrowing and without."""
    batch = os.path.join(OBS, "claw-evolution")
    runs = {}
    for folder in sorted(glob.glob(os.path.join(batch, "evolved-*_seed*"))):
        r = claw_evolution.analyse_run(folder, 50)
        runs.setdefault(r["config"], []).append(r)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True)
    for ax, cost, title in ((axes[0], "cost", "Claws cost food"), (axes[1], "free", "Claws are free")):
        for burrow, color, label in (("burrow", CLAW, "burrowing works"), ("noburrow", MUTED, "burrowing switched off")):
            members = runs["evolved-%s-%s" % (cost, burrow)]
            per_tick = collections.defaultdict(list)
            for r in members:
                s = r["_series"]
                for t, p, n in zip(s["ticks"], s["prey"], s["evolved"]):
                    if p > 0:
                        per_tick[t].append(n / p)
            ticks = sorted(per_tick)
            mean = [statistics.mean(per_tick[t]) for t in ticks]
            sd = [statistics.stdev(per_tick[t]) if len(per_tick[t]) > 1 else 0 for t in ticks]
            took = sum(r["evolved_take_over_tick"] is not None for r in members)
            ax.fill_between(ticks, [max(m - s, 0) for m, s in zip(mean, sd)], [min(m + s, 1) for m, s in zip(mean, sd)],
                            color=color, alpha=0.18, linewidth=0)
            ax.plot(ticks, mean, color=color, linewidth=2.4, label="%s · took over in %d/10" % (label, took))
        ax.set_title(title, loc="left", color=INK)
        ax.set_ylim(0, 1)
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
        ax.set_xlabel("Tick")
        ax.grid(axis="y")
        ax.set_axisbelow(True)
        thousands(ax)
        ax.legend(loc="upper left" if cost == "cost" else "center right")
    axes[0].set_ylabel("Prey carrying a claw")
    fig.tight_layout()
    save(fig, "claw_spread.png")


def soil_survival():
    """Batch 2: runs lasting 250k ticks by soil density and patch size, and by soil regrowth."""
    cells = collections.defaultdict(lambda: [0, 0])
    regen = collections.defaultdict(lambda: [0, 0])
    for folder in glob.glob(os.path.join(OBS, "soil-layouts", "*_seed*")):
        se = json.load(open(os.path.join(folder, "settings.json")))["settings"]
        ok = status(folder)["state"] == "finished"
        c = cells[(se["soilPatchThreshold"], se["soilPatchResolution"])]
        c[0] += ok
        c[1] += 1
        label = se["runLabel"].split("_")[0]
        if label in ("soil-slow", "baseline", "soil-fast"):
            regen[label][0] += ok
            regen[label][1] += 1
    thr = [-0.1, 0, 0.1]
    res = [10, 20, 40]
    cmap = LinearSegmentedColormap.from_list("soil", [PANEL, "#1C5E3A", PRODUCER])
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.6), gridspec_kw={"width_ratios": [1.15, 1]})
    grid = [[cells[(t, r)][0] / cells[(t, r)][1] for r in res] for t in thr]
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=1)
    for i, t in enumerate(thr):
        for j, r in enumerate(res):
            ok, n = cells[(t, r)]
            ax.text(j, i, "%d/%d" % (ok, n), ha="center", va="center", fontsize=15, fontweight="bold",
                    color=BG if grid[i][j] > 0.55 else INK)
    ax.set_xticks(range(3))
    ax.set_xticklabels(["big", "medium", "small"])
    ax.set_yticks(range(3))
    ax.set_yticklabels(["dense\n68% fertile", "medium\n50%", "sparse\n33%"])
    ax.set_xlabel("Fertile patch size")
    ax.set_title("All configurations", loc="left")
    for side in ax.spines.values():
        side.set_visible(False)
    ax.tick_params(length=0)
    order = [("soil-slow", "slow\n0.01%"), ("baseline", "default\n0.05%"), ("soil-fast", "fast\n0.2%")]
    values = [regen[k][0] for k, _ in order]
    bars = ax2.bar(range(3), values, color=[MOUTH, "#9C8A55", PRODUCER], width=0.62)
    for b, (k, _) in zip(bars, order):
        ax2.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.8, "%d/%d" % tuple(regen[k]), ha="center", fontsize=14,
                 fontweight="bold")
    ax2.set_xticks(range(3))
    ax2.set_xticklabels([label for _, label in order])
    ax2.set_xlabel("Soil regrowth chance per tick")
    ax2.set_ylim(0, 48)
    ax2.set_title("Runs lasting 250k, by soil regrowth", loc="left")
    ax2.grid(axis="y")
    ax2.set_axisbelow(True)
    fig.tight_layout()
    save(fig, "soil_survival.png")


def group_evidence():
    """The control experiments from the group's reports: soil damage and plant regrowth decide the collapse."""
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    # Tarique: all prey died after claws took over, by soil cost per burrow
    costs = [("0\nharmless", 0, 20), ("3", 0, 20), ("5", 4, 20), ("10", 21, 40)]
    ax = axes[0]
    bars = ax.bar(range(4), [a / n for _, a, n in costs], color=[MUTED, "#B5562A", "#E2643A", CLAW], width=0.62)
    for b, (_, a, n) in zip(bars, costs):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03, "%d/%d" % (a, n), ha="center", fontweight="bold")
    ax.set_xticks(range(4))
    ax.set_xticklabels([c for c, _, _ in costs])
    ax.set_xlabel("Soil removed per burrow")
    ax.set_title("Prey extinct after claws took over", loc="left", fontsize=13)
    # Nik: burrower populations that died after spreading
    ax = axes[1]
    nik = [("soil damage\n(cost 5)", 11, 11), ("no soil damage\n(cost 0)", 0, 5)]
    bars = ax.bar(range(2), [a / n for _, a, n in nik], color=[CLAW, MUTED], width=0.55)
    for b, (_, a, n) in zip(bars, nik):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03, "%d/%d" % (a, n), ha="center", fontweight="bold")
    ax.set_xticks(range(2))
    ax.set_xticklabels([c for c, _, _ in nik])
    ax.set_title("Burrowers extinct after spreading", loc="left", fontsize=13)
    # Jenna: collapses by plant regrowth rate (reference settings, soil cost 10)
    ax = axes[2]
    jen = [("off", 4, 20), ("0.25%", 2, 20), ("1%", 0, 20), ("3%", 0, 20)]
    bars = ax.bar(range(4), [a / n for _, a, n in jen], color=[CLAW, "#C99A3E", PRODUCER, PRODUCER], width=0.62)
    for b, (_, a, n) in zip(bars, jen):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03, "%d/%d" % (a, n), ha="center", fontweight="bold")
    ax.set_xticks(range(4))
    ax.set_xticklabels([c for c, _, _ in jen])
    ax.set_xlabel("Plant regrowth chance per tick")
    ax.set_title("Prey extinct after claws took over", loc="left", fontsize=13)
    for ax in axes:
        ax.set_ylim(0, 1.15)
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
        ax.grid(axis="y")
        ax.set_axisbelow(True)
    fig.tight_layout()
    save(fig, "group_evidence.png")


def predator_claws():
    """Batch 2: late in the runs, the share of predators carrying claws they never burrow with."""
    acc = collections.defaultdict(lambda: [0.0, 0.0])
    for path in glob.glob(os.path.join(OBS, "soil-layouts", "averages", "*", "*.csv")):
        if os.path.basename(path).startswith("heatmaps"):
            continue
        cfg = os.path.basename(path)[:-4]
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                if int(r["tick"]) >= 100000 and r.get("predators_with_claw_cells_mean") and r.get("predators_population_mean"):
                    acc[cfg][0] += float(r["predators_with_claw_cells_mean"])
                    acc[cfg][1] += float(r["predators_population_mean"])
    order = ["baseline", "soil-fast", "pred-2", "pred-1", "soil-slow", "claw-off"]
    values = [acc[c][0] / acc[c][1] for c in order]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    bars = ax.bar(range(len(order)), values, color=[CLAW] * 5 + [MUTED], width=0.62)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, "%d%%" % round(v * 100), ha="center", fontweight="bold")
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, fontsize=11)
    ax.set_ylim(0, 1.1)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    ax.set_ylabel("Predators carrying claws")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    save(fig, "predator_claws.png")


if __name__ == "__main__":
    print("extinctions:", extinction_timing())
    early_wave()
    collapse_chain()
    claw_spread()
    soil_survival()
    group_evidence()
    predator_claws()
