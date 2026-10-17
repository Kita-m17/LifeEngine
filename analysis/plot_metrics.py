"""Plot the CSVs exported from the Statistics tab ("Export Metrics").

Usage:
    pip install matplotlib
    python analysis/plot_metrics.py [RUN ...] [--smooth 5] [--follow SPECIES] [--top 8] [--predator-lineage predator]

Each run is a folder under Observations/ holding the files from one run (timeseries, groups_log, species_log,
species_summary, key_moments). RUN can be a folder name inside Observations/ or a path; with no RUN, every run
folder in Observations/ is plotted. If there are several files of one kind (numbered parts from auto-save, or
several exports), all of them are read and duplicate rows are dropped.

Figures are saved as PNGs in <run>/plots/. With more than one run, a side-by-side comparison is saved to
Observations/comparison.png.
"""
import argparse
import csv
import glob
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OBSERVATIONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Observations")
PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#7f7f7f"]
ROLE_COLORS = {
    "Plants": "#2ca02c",
    "Predators": "#d62728",
    "Prey (burrowing)": "#8c564b",
    "Prey (non-burrowing)": "#1f77b4",
}
EVOLVED_PREDATOR_COLOR = "#9467bd"
EVENT_COLORS = {"burrow_start": "#8c564b", "burrow_end": "#8c564b", "total_extinction": "black"}
CELL_TYPES = ("producer", "mouth", "mover", "killer", "eye", "claw", "armor")


def read_rows(folder, prefix):
    rows = []
    seen = set()
    for path in sorted(glob.glob(os.path.join(folder, prefix + "*.csv"))):
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                key = tuple(row.values())
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
    return rows


def num(value):
    return float(value) if value not in ("", None) else None


def smooth(values, window):
    """Trailing mean that skips gaps (None), so sparse fitness / lifespan values stay readable."""
    if window <= 1:
        return values
    out = []
    for i in range(len(values)):
        chunk = [v for v in values[max(0, i - window + 1):i + 1] if v is not None]
        out.append(sum(chunk) / len(chunk) if chunk else None)
    return out


def growth_rate(pop_end, births, deaths):
    """Same as FossilRecord.perCapitaRates: (births - deaths) over the average of the start and end population."""
    pop_avg = (pop_end + (pop_end - births + deaths)) / 2
    return (births - deaths) / pop_avg if pop_avg > 0 else None


def draw_events(ax, events, include_species=False):
    for e in events:
        if not include_species and e["type"].startswith("species_"):
            continue
        ax.axvline(int(e["tick"]), color=EVENT_COLORS.get(e["type"], "#2ca02c"), linestyle="--", linewidth=0.8, alpha=0.7)


def label_events(ax, events):
    ymax = ax.get_ylim()[1]
    for e in events:
        if e["type"].startswith("species_"):
            continue
        ax.text(int(e["tick"]), ymax, " " + e["label"], rotation=90, va="top", fontsize=7, alpha=0.8)


def group_series(groups_rows, grouping, field):
    series = defaultdict(lambda: ([], []))
    for row in groups_rows:
        if row["grouping"] != grouping:
            continue
        xs, ys = series[row["group"]]
        xs.append(int(row["tick"]))
        ys.append(num(row.get(field, "")))
    return series


def top_groups(series, n):
    """The n groups with the highest peak, so lineages that never took off don't clutter the plot."""
    peaks = {name: max([y for y in ys if y is not None] or [0]) for name, (xs, ys) in series.items()}
    return sorted(peaks, key=peaks.get, reverse=True)[:n]


def plot_groups(groups_rows, events, out, window, top):
    for grouping in ("lineage", "role"):
        pop = group_series(groups_rows, grouping, "population")
        fit = group_series(groups_rows, grouping, "fitness")
        life = group_series(groups_rows, grouping, "lifespan_at_death")
        growth = group_series(groups_rows, grouping, "growth_rate")
        if not pop:
            continue
        names = top_groups(pop, top) if grouping == "lineage" else list(pop)
        fig, (ax1, ax4, ax2, ax3) = plt.subplots(4, 1, sharex=True, figsize=(11, 13))
        for name in names:
            color = ROLE_COLORS.get(name)
            ax1.plot(*pop[name], label=name, color=color)
            xs, ys = growth[name]
            ax4.plot(xs, smooth(ys, window), label=name, color=color)
            xs, ys = fit[name]
            ax2.plot(xs, smooth(ys, window), label=name, color=color)
            xs, ys = life[name]
            ax3.plot(xs, smooth(ys, window), label=name, color=color)
        ax1.set_ylabel("Population")
        ax4.set_ylabel("Growth rate\n(per capita, per 100 ticks)")
        ax4.axhline(0, color="#999", linewidth=0.8)
        ax2.set_ylabel("Fitness (avg offspring\nof organisms that died)")
        ax3.set_ylabel("Lifespan at death\n(ticks, organisms that died)")
        ax3.set_xlabel("Tick")
        for ax in (ax1, ax4, ax2, ax3):
            draw_events(ax, events)
        label_events(ax1, events)
        ax1.legend(fontsize=8, loc="upper left")
        ax1.set_title("Population, growth rate, fitness and lifespan at death by " + grouping + (" (smoothed over %d samples)" % window if window > 1 else ""))
        fig.tight_layout()
        fig.savefig(os.path.join(out, "groups_%s.png" % grouping), dpi=150)
        plt.close(fig)

        # stacked area: who makes up the world over time (a simple Muller-style view)
        ticks = sorted({x for xs, _ in pop.values() for x in xs})
        index = {t: i for i, t in enumerate(ticks)}
        stacks = []
        for name in names:
            ys = [0.0] * len(ticks)
            for x, y in zip(*pop[name]):
                ys[index[x]] = y or 0
            stacks.append(ys)
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.stackplot(ticks, stacks, labels=names, colors=[ROLE_COLORS.get(n) for n in names] if grouping == "role" else None, alpha=0.85)
        draw_events(ax, events)
        ax.set_xlabel("Tick")
        ax.set_ylabel("Population")
        ax.set_title("Population share by " + grouping)
        ax.legend(fontsize=8, loc="upper left")
        fig.tight_layout()
        fig.savefig(os.path.join(out, "stacked_%s.png" % grouping), dpi=150)
        plt.close(fig)


def plot_burrow_soil(ts_rows, groups_rows, events, out):
    if not ts_rows:
        return
    ticks = [int(r["tick"]) for r in ts_rows]
    fig, ax1 = plt.subplots(figsize=(11, 4))
    ax1.plot(ticks, [num(r["burrowers"]) for r in ts_rows], color="#8c564b", label="Organisms with claw cells")
    if "hidden" in ts_rows[0]:
        ax1.plot(ticks, [num(r["hidden"]) for r in ts_rows], color="#9467bd", label="Underground")
    role_pop = group_series(groups_rows, "role", "population")
    for name in ("Prey (burrowing)", "Prey (non-burrowing)", "Predators"):
        if name in role_pop:
            ax1.plot(*role_pop[name], color=ROLE_COLORS[name], alpha=0.5, linewidth=0.8, label=name)
    ax1.set_ylabel("Organisms")
    ax1.set_xlabel("Tick")
    soil = [num(r["soil_mean"]) for r in ts_rows]
    start = next((v for v in soil if v), None)
    if start:
        # both soil lines as percentages so they share an axis
        ax2 = ax1.twinx()
        ax2.plot(ticks, [100 * v / start if v is not None else None for v in soil], color="#2ca02c", label="Avg. soil fertility (% of start)")
        ax2.plot(ticks, [100 * num(r["soil_degraded_frac"]) if r["soil_degraded_frac"] != "" else None for r in ts_rows],
                 color="#ff7f0e", linestyle="--", label="Degraded tiles (%)")
        ax2.set_ylabel("Soil (%)")
        ax2.set_ylim(0, 105)
        ax2.legend(fontsize=8, loc="upper right")
    draw_events(ax1, events)
    ax1.legend(fontsize=8, loc="upper left")
    ax1.set_title("Burrowing (claw cells), prey and soil health")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "burrow_soil.png"), dpi=150)
    plt.close(fig)


def plot_followed(species_rows, events, out, root, window):
    parent = {r["species"]: r["ancestor"] for r in species_rows}
    memo = {}

    def descends(name):
        chain = []
        cur = name
        result = False
        while cur:
            if cur == root:
                result = True
                break
            if cur in memo:
                result = memo[cur]
                break
            chain.append(cur)
            cur = parent.get(cur, "")
        for n in chain:
            memo[n] = result
        return result

    totals = defaultdict(lambda: {"self": [0, 0, 0.0, 0.0, 0], "desc": [0, 0, 0.0, 0.0, 0]})  # pop, deaths, offspring, lifetime, births
    for r in species_rows:
        if not descends(r["species"]):
            continue
        g = totals[int(r["tick"])]["self" if r["species"] == root else "desc"]
        g[0] += int(r["population"])
        g[1] += int(r["deaths"])
        if r["fitness"] != "":
            g[2] += float(r["fitness"]) * int(r["deaths"])
        if r.get("lifespan_at_death", "") != "":
            g[3] += float(r["lifespan_at_death"]) * int(r["deaths"])
        if r.get("births", "") != "":
            g[4] += int(r["births"])
    if not totals:
        print("No rows found for species '%s'" % root)
        return
    ticks = sorted(totals)
    fig, (ax1, ax4, ax2, ax3) = plt.subplots(4, 1, sharex=True, figsize=(11, 13))
    for key, label in (("self", root), ("desc", root + " descendants")):
        ax1.plot(ticks, [totals[t][key][0] for t in ticks], label=label)
        grow = [growth_rate(totals[t][key][0], totals[t][key][4], totals[t][key][1]) for t in ticks]
        ax4.plot(ticks, smooth(grow, window), label=label)
        fit = [totals[t][key][2] / totals[t][key][1] if totals[t][key][1] else None for t in ticks]
        ax2.plot(ticks, smooth(fit, window), label=label)
        life = [totals[t][key][3] / totals[t][key][1] if totals[t][key][1] else None for t in ticks]
        ax3.plot(ticks, smooth(life, window), label=label)
    ax1.set_ylabel("Population")
    ax4.set_ylabel("Growth rate\n(per capita, per 100 ticks)")
    ax4.axhline(0, color="#999", linewidth=0.8)
    ax2.set_ylabel("Fitness (avg offspring\nof organisms that died)")
    ax3.set_ylabel("Lifespan at death\n(ticks, organisms that died)")
    ax3.set_xlabel("Tick")
    for ax in (ax1, ax4, ax2, ax3):
        draw_events(ax, [e for e in events if not e["type"].startswith("species_") or e["species"] == root], include_species=True)
    ax1.legend(fontsize=8)
    ax1.set_title("Species '%s' and its descendants" % root)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "followed_%s.png" % root), dpi=150)
    plt.close(fig)


def plot_predators(groups_rows, events, out, window, predator_lineages):
    """Prey against the seeded predator lineage and the predators that evolved in other lineages. Evolved predators
    are the Predators role minus the seeded lineage. Organisms are now tagged is_predator from their anatomy, so most
    evolved predators are tagged and visible to prey; runs from before that change had none tagged, so there this line
    is killers prey couldn't see. Either way the role is classified from anatomy, so it also counts mobile producers
    with killer cells, which stay untagged. Plants with killer cells are classified as Plants and show up in the killer
    cell plot of traits.png instead."""
    role_pop = group_series(groups_rows, "role", "population")
    lineage_pop = group_series(groups_rows, "lineage", "population")
    if "Predators" not in role_pop:
        return
    seeded = defaultdict(float)
    for name in predator_lineages:
        for x, y in zip(*lineage_pop.get(name, ([], []))):
            seeded[x] += y or 0
    xs, ys = role_pop["Predators"]
    fig, ax = plt.subplots(figsize=(11, 4))
    for name in ("Prey (burrowing)", "Prey (non-burrowing)"):
        if name in role_pop:
            ax.plot(*role_pop[name], color=ROLE_COLORS[name], label=name)
    ax.plot(sorted(seeded), [seeded[x] for x in sorted(seeded)], color=ROLE_COLORS["Predators"],
            label="Seeded predators (%s)" % ", ".join(predator_lineages))
    ax.plot(xs, smooth([max((y or 0) - seeded[x], 0) for x, y in zip(xs, ys)], window), color=EVOLVED_PREDATOR_COLOR,
            label="Evolved predators (other lineages)")
    draw_events(ax, events)
    ax.set_xlabel("Tick")
    ax.set_ylabel("Organisms")
    ax.set_title("Prey against seeded and evolved predators")
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "predators.png"), dpi=150)
    plt.close(fig)


def plot_traits(ts_rows, events, out, window):
    """Population-average anatomy, body size, mutation rate and species count."""
    if not ts_rows:
        return
    ticks = [int(r["tick"]) for r in ts_rows]
    panels = [("avg_" + c, c.capitalize() + " cells per organism") for c in CELL_TYPES]
    panels += [("avg_cells", "Body size (cells)"), ("avg_mutation_rate", "Mutation rate (%)"), ("species", "Living species")]
    panels = [(field, label) for field, label in panels if field in ts_rows[0]]
    fig, axes = plt.subplots(len(panels), 1, sharex=True, figsize=(11, 1.6 * len(panels) + 1))
    for ax, (field, label) in zip(axes, panels):
        ys = [num(r[field]) for r in ts_rows]
        ax.plot(ticks, ys if field == "species" else smooth(ys, window), color=PALETTE[0])
        ax.set_ylabel(label, fontsize=8)
        draw_events(ax, events)
    axes[-1].set_xlabel("Tick")
    axes[0].set_title("Population-average anatomy" + (" (smoothed over %d samples)" % window if window > 1 else ""))
    fig.tight_layout()
    fig.savefig(os.path.join(out, "traits.png"), dpi=150)
    plt.close(fig)


def plot_species_timeline(summary_rows, out):
    """One bar per species from its first to last tick, coloured by founding lineage."""
    if not summary_rows:
        return
    rows = sorted(summary_rows, key=lambda r: (r["lineage"], int(r["start_tick"])))
    lineages = list(dict.fromkeys(r["lineage"] for r in rows))
    colors = {name: PALETTE[i % len(PALETTE)] for i, name in enumerate(lineages)}
    fig, ax = plt.subplots(figsize=(11, max(4, 0.09 * len(rows))))
    for i, r in enumerate(rows):
        start = int(r["start_tick"])
        ax.plot([start, start + int(r["age"])], [i, i], color=colors[r["lineage"]], linewidth=2.2, solid_capstyle="round")
    ax.set_yticks([])
    ax.set_xlabel("Tick")
    ax.set_title("Species lifespans (%d species), coloured by founding lineage" % len(rows))
    ax.legend(handles=[plt.Line2D([], [], color=colors[n], linewidth=2.2, label=n) for n in lineages], fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "species_timeline.png"), dpi=150)
    plt.close(fig)


def plot_comparison(runs, path, window):
    """The same metrics for every run on shared panels, one colour per run. Roles are compared rather than lineages
    because lineage names depend on each run's starting organisms."""
    panels = [
        ("role", "Prey (burrowing)", "Prey (burrowing)"),
        ("role", "Prey (non-burrowing)", "Prey (non-burrowing)"),
        ("role", "Predators", "Predators"),
        ("role", "Plants", "Plants"),
        ("ts", "burrows", "Burrows per sample"),
        ("ts", "soil_mean", "Avg. soil fertility"),
        ("ts", "avg_killer", "Killer cells per organism"),
        ("ts", "avg_mutation_rate", "Mutation rate (%)"),
    ]
    fig, axes = plt.subplots(len(panels), 1, sharex=True, figsize=(11, 2 * len(panels) + 1))
    for i, (name, run) in enumerate(runs):
        color = PALETTE[i % len(PALETTE)]
        role_pop = group_series(run["groups"], "role", "population")
        ticks = [int(r["tick"]) for r in run["ts"]]
        for ax, (source, field, label) in zip(axes, panels):
            if source == "role" and field in role_pop:
                ax.plot(*role_pop[field], color=color, label=name)
            elif source == "ts" and run["ts"] and field in run["ts"][0]:
                ax.plot(ticks, smooth([num(r[field]) for r in run["ts"]], window), color=color, label=name)
            ax.set_ylabel(label, fontsize=8)
    axes[0].legend(fontsize=8, loc="upper right")
    axes[0].set_title("Run comparison")
    axes[-1].set_xlabel("Tick")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def find_runs(names):
    """Run folders named on the command line (inside Observations/ or as paths), or every run in Observations/."""
    if not names:
        return sorted({os.path.dirname(p) for p in glob.glob(os.path.join(OBSERVATIONS, "*", "timeseries*.csv"))})
    runs = []
    for name in names:
        folder = name if os.path.isdir(name) else os.path.join(OBSERVATIONS, name)
        if not os.path.isdir(folder):
            raise SystemExit("No run folder '%s' (looked in %s)" % (name, OBSERVATIONS))
        runs.append(os.path.abspath(folder))
    return list(dict.fromkeys(runs))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="*", help="run folders (names inside Observations/ or paths); default: all of them")
    parser.add_argument("--smooth", type=int, default=5, help="samples to average growth rate, fitness, lifespan at death and traits over (1 = off)")
    parser.add_argument("--follow", help="species name to plot with all its descendant species")
    parser.add_argument("--top", type=int, default=8, help="max lineages to draw")
    parser.add_argument("--predator-lineage", action="append",
                        help="seeded predator lineage(s), used to separate evolved predators (default: predator)")
    args = parser.parse_args()
    predator_lineages = args.predator_lineage or ["predator"]

    folders = find_runs(args.runs)
    if not folders:
        raise SystemExit("No runs found in " + OBSERVATIONS)
    runs = []
    for folder in folders:
        out = os.path.join(folder, "plots")
        os.makedirs(out, exist_ok=True)
        ts_rows = sorted(read_rows(folder, "timeseries"), key=lambda r: int(r["tick"]))
        groups_rows = read_rows(folder, "groups_log")
        events = read_rows(folder, "key_moments")

        plot_groups(groups_rows, events, out, args.smooth, args.top)
        plot_burrow_soil(ts_rows, groups_rows, events, out)
        plot_predators(groups_rows, events, out, args.smooth, predator_lineages)
        plot_traits(ts_rows, events, out, args.smooth)
        plot_species_timeline(read_rows(folder, "species_summary"), out)
        if args.follow:
            plot_followed(read_rows(folder, "species_log"), events, out, args.follow, args.smooth)
        print("Saved plots to", out)
        runs.append((os.path.basename(folder), {"ts": ts_rows, "groups": groups_rows}))

    if len(runs) > 1:
        path = os.path.join(OBSERVATIONS, "comparison.png")
        plot_comparison(runs, path, args.smooth)
        print("Saved comparison to", path)


if __name__ == "__main__":
    main()
