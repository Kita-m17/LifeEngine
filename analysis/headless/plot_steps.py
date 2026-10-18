"""Outcome bars for hand-picked setups from different sweeps, e.g. to step from one version of the code to another.

Usage:
    python analysis/headless/plot_steps.py --out FILE [--title TEXT] --step LABEL DIR CONDITION [KEY=VALUE ...] ...

Each --step is one bar: the runs of CONDITION in the results folder DIR, optionally only those whose settings match
every KEY=VALUE (e.g. plantRegrowthRate=0). Runs are classified exactly as in plot_evo_suicide.py, and the number of
runs where every prey died after the claws took over is tested against the first step (Fisher's exact test).

Example:
    python analysis/headless/plot_steps.py --out steps.png \\
        --step "our branch" analysis/headless/results/evo_suicide "soil cost 10" \\
        --step "her branch, no regrowth" analysis/headless/results/jenna-testing/regrowth_sweep "soil cost 10" plantRegrowthRate=0
"""
import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plot_evo_suicide as pes  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


def matches(run, filters):
    for key, value in filters.items():
        actual = run["params"].get(key)
        if pes.fmt(actual) != value and str(actual) != value:
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, help="the PNG to write")
    parser.add_argument("--title", default="How each run ended")
    parser.add_argument("--step", nargs="+", action="append", required=True,
                        metavar="LABEL DIR CONDITION [KEY=VALUE]", help="one bar (repeat for each)")
    args = parser.parse_args()

    steps = []
    for spec in args.step:
        if len(spec) < 3:
            raise SystemExit("--step needs LABEL DIR CONDITION, got: " + " ".join(spec))
        label, folder, condition, *pairs = spec
        filters = dict(pair.split("=", 1) for pair in pairs)
        runs, _ = pes.load_runs([folder])
        group = [run for run in runs if run["condition"] == condition and matches(run, filters)]
        if not group:
            raise SystemExit(f"no runs of '{condition}' matching {filters} in {folder}")
        steps.append((label, group))

    first = steps[0][1]
    first_suicides = sum(run["outcome"] == pes.SUICIDE for run in first)
    fig, ax = plt.subplots(figsize=(8.5, 0.6 * len(steps) + 1.9))
    for row, (label, group) in enumerate(steps):
        counts = Counter(run["outcome"] for run in group)
        left = 0
        for outcome in pes.OUTCOMES:
            share = counts[outcome] / len(group) * 100
            if share:
                ax.barh(row, share, left=left, color=pes.OUTCOME_COLORS[outcome], edgecolor="white")
                if share >= 6:
                    ax.text(left + share / 2, row, str(counts[outcome]), ha="center", va="center", fontsize=9,
                            color="black" if outcome == pes.NO_TAKEOVER else "white")
            left += share
        suicides = counts[pes.SUICIDE]
        note = f"{suicides}/{len(group)}"
        if row:
            p = pes.fisher_two_sided(suicides, len(group) - suicides, first_suicides, len(first) - first_suicides)
            note += f"  p = {p:.2g}"
        ax.text(101.5, row, note, va="center", fontsize=8.5, color="#444")
        print(f"{label:45s} n={len(group):3d}  " + ", ".join(f"{o}: {counts[o]}" for o in pes.OUTCOMES if counts[o]))
    ax.set_yticks(range(len(steps)), [f"{label} (n={len(group)})" for label, group in steps])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of runs")
    ax.set_title(args.title, pad=20)
    ax.text(1.0, 1.01, "all prey died after take-over, p against the first bar", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8, color="#444")
    handles = [plt.Rectangle((0, 0), 1, 1, color=pes.OUTCOME_COLORS[o]) for o in pes.OUTCOMES]
    ax.legend(handles, pes.OUTCOMES, loc="upper center", bbox_to_anchor=(0.5, -0.12 - 0.02 * (8 - min(len(steps), 8))),
              ncol=2, fontsize=8.5)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    fig.savefig(args.out)
    plt.close(fig)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
