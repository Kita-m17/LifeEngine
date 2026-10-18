"""One row per run, coloured by the state of the prey at every sample: shows when claws took over, when prey died
out, and whether they came back.

Usage:
    python analysis/headless/plot_timeline.py RESULTS_DIR [--out FILE] [--only CONDITION ...]

RESULTS_DIR is a folder written by sweep.js. Each condition (in the sweep file's order) gets its own panel, with the
runs sorted by placement seed and each run's state at its last tick written on the right. The figure goes to
<RESULTS_DIR>/figures/run_timeline.png unless --out is given.

States (prey = prey with and without a claw):
    most prey have a claw     prey with a claw are at least half of all prey
    most prey have no claw
    no prey left              plants (and maybe predators) are alive, but no prey
    nothing alive             every organism is dead
"""
import argparse
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np

STATES = ["most prey have a claw", "most prey have no claw", "no prey left", "nothing alive"]
COLORS = ["#8c564b", "#1f77b4", "#c7c7c7", "#303030"]

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "savefig.bbox": "tight", "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False, "axes.titlesize": 11,
    "legend.frameon": False,
})


def label(run):
    meta = run["meta"]
    vary = ", ".join(f"{key} {value}" for key, value in (meta.get("vary") or {}).items())
    return meta["condition"] + (f" ({vary})" if vary else "")


def load(results_dir):
    """Runs grouped by condition, in the sweep file's order, each group sorted by placement seed."""
    groups = {}
    for path in glob.glob(os.path.join(results_dir, "*.json")):
        if os.path.basename(path) == "sweep.json":
            continue
        with open(path) as f:
            run = json.load(f)
        groups.setdefault(label(run), []).append(run)
    order = []
    sweep_file = os.path.join(results_dir, "sweep.json")
    if os.path.exists(sweep_file):
        with open(sweep_file) as f:
            order = [c["name"] for c in json.load(f)["conditions"]]
    rank = lambda name: next((i for i, c in enumerate(order) if name.startswith(c)), len(order))
    return {name: sorted(groups[name], key=lambda r: r["meta"]["seed"])
            for name in sorted(groups, key=lambda name: (rank(name), name))}


def states(run):
    s = run["series"]
    every = run["every"]
    row = np.full(run["ticks"] // every + 1, np.nan)
    for i, t in enumerate(s["t"]):
        prey = s["prey"][i] + s["claw_prey"][i]
        if s["population"][i] == 0:
            state = 3
        elif prey == 0:
            state = 2
        else:
            state = 0 if s["claw_prey"][i] >= 0.5 * prey else 1
        row[t // every] = state
    if run["extinct_at"] is not None:
        row[run["extinct_at"] // every:] = 3
    return row


def end_state(run):
    s = run["series"]
    if run["extinct_at"] is not None:
        return "all dead"
    prey = s["prey"][-1] + s["claw_prey"][-1]
    return "plants only" if prey == 0 else f"{prey} prey, {s['claw_prey'][-1]} clawed"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dir", help="results folder written by sweep.js")
    parser.add_argument("--out", help="the PNG to write (default: <dir>/figures/run_timeline.png)")
    parser.add_argument("--only", action="append", metavar="CONDITION", help="only these conditions (repeatable)")
    args = parser.parse_args()

    groups = load(args.dir)
    if args.only:
        groups = {name: runs for name, runs in groups.items() if name in args.only}
    if not groups:
        raise SystemExit("no runs found")
    heights = [len(runs) for runs in groups.values()]
    fig, axes = plt.subplots(len(groups), 1, figsize=(9, 0.2 * sum(heights) + 1.6 * len(groups) + 0.6),
                             sharex=True, gridspec_kw={"height_ratios": heights}, squeeze=False)
    ticks = max(run["ticks"] for runs in groups.values() for run in runs)
    for ax, (name, runs) in zip(axes[:, 0], groups.items()):
        grid = np.full((len(runs), ticks // runs[0]["every"] + 1), np.nan)
        for i, run in enumerate(runs):
            row = states(run)
            grid[i, :len(row)] = row
        ax.imshow(grid, aspect="auto", interpolation="nearest", cmap=ListedColormap(COLORS), vmin=-0.5, vmax=3.5,
                  extent=(0, ticks / 1000, len(runs) - 0.5, -0.5))
        for i in range(1, len(runs)):  # a gap between runs
            ax.axhline(i - 0.5, color="white", lw=1.2)
        ax.set_yticks(range(len(runs)))
        ax.set_yticklabels([f"seed {run['meta']['seed']}" for run in runs], fontsize=7.5)
        ax.tick_params(axis="y", length=0)
        for i, run in enumerate(runs):
            ax.text(ticks / 1000 * 1.013, i, end_state(run), va="center", fontsize=7.5, color="#333333")
        ax.set_title(f"{name} (n={len(runs)})", loc="left")
        ax.text(ticks / 1000 * 1.013, -0.9, f"at tick {ticks // 1000}k", fontsize=7.5, color="#55625b")
    axes[-1, 0].set_xlabel("tick (thousands)")
    every = runs[0]["every"]
    fig.legend(handles=[Patch(color=c, label=s) for c, s in zip(COLORS, STATES)], loc="lower center", ncol=4,
               bbox_to_anchor=(0.5, -0.02), fontsize=8.5)
    fig.suptitle(f"The state of the prey in every run, sampled every {every} ticks")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    out = args.out or os.path.join(args.dir, "figures", "run_timeline.png")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    fig.savefig(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
