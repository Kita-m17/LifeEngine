"""Plot the CSVs exported from the Statistics tab ("Export Metrics").

Usage:
    pip install matplotlib
    python analysis/plot_metrics.py [RUN ...] [--smooth 5] [--follow SPECIES] [--top 8] [--predator-lineage NAME]
                                    [--split KEY,...] [--skip-run-plots]

Each run is a folder under Observations/ holding the files from one run (timeseries, groups_log, species_log,
species_summary, key_moments). RUN can be a folder name inside Observations/ or a path; with no RUN, every run
folder in Observations/ is plotted. RUN can also be a batch folder from headless/batch.js, which plots every run in it
(batch runs are only plotted when named this way, not with no RUN). If there are several files of one kind (numbered parts from auto-save, or
several exports), all of them are read and duplicate rows are dropped.

Figures are saved as PNGs in <run>/plots/. With more than one run, a side-by-side comparison is saved to
Observations/comparison.png and every run's configuration (the run_config export) to Observations/run_configs.csv.
Runs whose configurations match apart from their seeds and label are treated as replicates: each such group is averaged
(mean +- 1 std, plus a CSV of the means of every metric) in Observations/averages/, with the group means compared in
comparison_means.png and, for the metrics of each per-run plot, in comparison_roles.png, comparison_claws.png,
comparison_burrow_soil.png, comparison_predators.png and comparison_traits.png.

With --split KEYS (run_config keys, e.g. --split soilPatchThreshold,soilPatchResolution for a batch that varies the soil
layout), the configurations are compared separately for each combination of those settings, in
averages/<key=value...>/, and heatmaps.png / heatmaps.csv in averages/ show every configuration against every
combination: the fraction of runs lasting to the end and late-run populations (runs that died count as 0). With more
runs than colours, the all-runs comparison.png is skipped. Runs exported without a run_config are never grouped.
"""
import argparse
import csv
import glob
import os
import re
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
    is killers prey couldn't see (including mobile producers with killer cells, which are now tagged prey and counted
    as Prey instead). Plants with killer cells are classified as Plants and show up in the killer
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


# Cross-run comparison. A panel is one metric: a label, a function giving its (ticks, values) for one run, and whether
# it is smoothed (rates and averages are, counts aren't, as in the per-run plots). Roles are compared rather than
# lineages because lineage names depend on each run's starting organisms.
ROLES = ("Plants", "Predators", "Prey (burrowing)", "Prey (non-burrowing)")


def panel(label, get, smoothed=False, count=False):
    return {"label": label, "get": get, "smooth": smoothed, "count": count}


def cached(run, key, make):
    """Per-run memo, so each groups_log grouping is only split into series once however many panels read it."""
    cache = run.setdefault("_cache", {})
    if key not in cache:
        cache[key] = make()
    return cache[key]


def role_series(run, field):
    return cached(run, ("role", field), lambda: group_series(run.get("groups") or [], "role", field))


def roles_total(roles, field):
    """Sum of a groups_log field over several roles (all of them when roles is None), per tick."""
    def get(run):
        totals = defaultdict(float)
        for name, (xs, ys) in role_series(run, field).items():
            if roles is None or name in roles:
                for x, y in zip(xs, ys):
                    totals[x] += y or 0
        ticks = sorted(totals)
        return ticks, [totals[t] for t in ticks]
    return get


def role_field(role, field):
    return lambda run: role_series(run, field).get(role, ([], []))


def ts_field(column, scale=1):
    def get(run):
        values = run["ts_cols"].get(column)
        if values is None:
            return [], []
        return run["ts_ticks"], [v * scale if v is not None else None for v in values]
    return get


def seeded_predators(run):
    """(ticks, seeded predator lineage population, evolved predator population), as in predators.png."""
    def make():
        lineages = cached(run, "lineage_pop", lambda: group_series(run.get("groups") or [], "lineage", "population"))
        seeded = defaultdict(float)
        for name in run.get("predator_lineages", []):
            for x, y in zip(*lineages.get(name, ([], []))):
                seeded[x] += y or 0
        xs, ys = role_series(run, "population").get("Predators", ([], []))
        return xs, [seeded[x] for x in xs], [max((y or 0) - seeded[x], 0) for x, y in zip(xs, ys)]
    return cached(run, "predators", make)


def runs_going(run):
    return run["ts_ticks"], [1] * len(run["ts_ticks"])


ROLE_FIELDS = ("population", "growth_rate", "fitness", "lifespan_at_death", "with_claw", "ever_burrowed", "hidden")


def compact(run, ts_rows, groups_rows):
    """Keeps only the series the cross-run figures read (timeseries columns, per-role fields and the seeded predator
    lineages), not every log row, so hundreds of runs fit in memory."""
    run["ts_ticks"] = [int(r["tick"]) for r in ts_rows]
    run["ts_cols"] = {c: [num(r[c]) for r in ts_rows] for c in (ts_rows[0] if ts_rows else {}) if c != "tick"}
    roles = [r for r in groups_rows if r["grouping"] == "role"]
    for field in ROLE_FIELDS:
        cached(run, ("role", field), lambda field=field: group_series(roles, "role", field))
    seeded = set(run["predator_lineages"])
    cached(run, "lineage_pop", lambda: group_series(
        [r for r in groups_rows if r["grouping"] == "lineage" and r["group"] in seeded], "lineage", "population"))
    seeded_predators(run)


# the overview: comparison.png, comparison_means.png and each configuration's replicates in averages/<label>.png
COMPARE_PANELS = [
    panel("Prey (burrowing)", role_field("Prey (burrowing)", "population")),
    panel("Prey (non-burrowing)", role_field("Prey (non-burrowing)", "population")),
    panel("Predators", role_field("Predators", "population")),
    panel("Plants", role_field("Plants", "population")),
    panel("Prey that have burrowed", role_field("Prey (burrowing)", "ever_burrowed")),
    panel("Burrows per sample", ts_field("burrows"), smoothed=True),
    panel("Avg. soil fertility", ts_field("soil_mean"), smoothed=True),
    panel("Killer cells per organism", ts_field("avg_killer"), smoothed=True),
    panel("Mutation rate (%)", ts_field("avg_mutation_rate"), smoothed=True),
    panel("Runs still going", runs_going, count=True),
]


def comparison_figures():
    """The averaged versions of the per-run plots, as {file name: (title, rows of panels)}. Lineage plots, the species
    timeline and the followed species have no equivalent across runs, since their names differ from run to run."""
    role_metrics = [("population", "population", False), ("growth_rate", "growth rate", True),
                    ("fitness", "fitness", True), ("lifespan_at_death", "lifespan at death", True)]
    claw_fields = [("population", "population"), ("with_claw", "with claw cells"),
                   ("ever_burrowed", "with claw cells that have burrowed"), ("hidden", "underground")]
    traits = [panel(c.capitalize() + " cells per organism", ts_field("avg_" + c), smoothed=True) for c in CELL_TYPES]
    traits += [panel("Body size (cells)", ts_field("avg_cells"), smoothed=True),
               panel("Mutation rate (%)", ts_field("avg_mutation_rate"), smoothed=True),
               panel("Living species", ts_field("species"))]
    return {
        "comparison_roles.png": ("Population, growth rate, fitness and lifespan at death by role", [
            [panel(role + ": " + label, role_field(role, field), smoothed=sm) for field, label, sm in role_metrics]
            for role in ROLES]),
        "comparison_claws.png": ("Claws used for burrowing vs. claws carried, by role", [
            [panel(title + ": " + label, roles_total(roles, field)) for field, label in claw_fields]
            for title, roles in CLAW_PANELS]),
        "comparison_burrow_soil.png": ("Burrowing and soil health", [
            [panel("Organisms with claw cells", ts_field("burrowers")), panel("Underground", ts_field("hidden"))],
            [panel("Avg. soil fertility", ts_field("soil_mean")),
             panel("Degraded tiles (%)", ts_field("soil_degraded_frac", 100))]]),
        "comparison_predators.png": ("Prey against seeded and evolved predators", [
            [panel("Prey (burrowing)", role_field("Prey (burrowing)", "population")),
             panel("Prey (non-burrowing)", role_field("Prey (non-burrowing)", "population"))],
            [panel("Seeded predators", lambda run: seeded_predators(run)[:2]),
             panel("Evolved predators (other lineages)", lambda run: (seeded_predators(run)[0], seeded_predators(run)[2]))]]),
        "comparison_traits.png": ("Population-average anatomy", [traits[i:i + 2] for i in range(0, len(traits), 2)]),
    }


def metric_series(run, p, window):
    """{tick: value} for one panel and run; empty if the run didn't log it."""
    xs, ys = p["get"](run)
    if p["smooth"]:
        ys = smooth(ys, window)
    return {x: y for x, y in zip(xs, ys) if y is not None}


def mean_std(series_list):
    """Per tick mean, standard deviation and number of runs, over the runs that reached that tick."""
    ticks = sorted({t for series in series_list for t in series})
    stats = []
    for t in ticks:
        values = [series[t] for series in series_list if t in series]
        mean = sum(values) / len(values)
        std = (sum((v - mean) ** 2 for v in values) / (len(values) - 1)) ** 0.5 if len(values) > 1 else 0.0
        stats.append((t, mean, std, len(values)))
    return stats


def plot_comparison_grid(groups, rows, path, window, title, show_replicates=False):
    """Every group on shared panels (a grid of rows), one colour per group. A group of several runs is drawn as its mean
    with a band of +-1 standard deviation (and, with show_replicates, each run faintly); a group of one is just that
    run. Means after a run has ended are over the runs still going; a "count" panel shows how many those are."""
    rows = [[p for p in row if any(metric_series(run, p, window) for _, members in groups for run in members)] for row in rows]
    rows = [row for row in rows if row]
    if not rows:
        return
    ncols = max(len(row) for row in rows)
    fig, axes = plt.subplots(len(rows), ncols, sharex=True, squeeze=False,
                             figsize=(11 if ncols == 1 else 5.5 * ncols, (2 if ncols == 1 else 2.6) * len(rows) + 1))
    for r, row in enumerate(rows):
        for c in range(len(row), ncols):
            axes[r][c].set_visible(False)
    for i, (name, members) in enumerate(groups):
        color = PALETTE[i % len(PALETTE)]
        label = name if len(members) == 1 else "%s (mean of %d)" % (name, len(members))
        for r, row in enumerate(rows):
            for c, p in enumerate(row):
                ax = axes[r][c]
                series_list = [s for s in (metric_series(run, p, window) for run in members) if s]
                stats = mean_std(series_list)
                if not stats:
                    continue
                ticks = [t for t, _, _, _ in stats]
                if p["count"]:
                    ax.plot(ticks, [n for _, _, _, n in stats], color=color, label=label)
                else:
                    if show_replicates and len(members) > 1:
                        for series in series_list:
                            ax.plot(sorted(series), [series[t] for t in sorted(series)], color=color, linewidth=0.6, alpha=0.35)
                    ax.plot(ticks, [m for _, m, _, _ in stats], color=color, label=label, linewidth=1.1)
                    if len(members) > 1:
                        ax.fill_between(ticks, [m - sd for _, m, sd, _ in stats], [m + sd for _, m, sd, _ in stats],
                                        color=color, alpha=0.15, linewidth=0)
                if ncols == 1:
                    ax.set_ylabel(p["label"], fontsize=8)
                else:
                    ax.set_title(p["label"], fontsize=9, loc="left")
    for c in range(ncols):
        bottom = max(r for r in range(len(rows)) if c < len(rows[r]))
        axes[bottom][c].set_xlabel("Tick")
        axes[bottom][c].xaxis.set_tick_params(labelbottom=True)
    if ncols == 1:
        axes[0][0].legend(fontsize=8, loc="upper right")
        axes[0][0].set_title(title)
        fig.tight_layout()
    else:
        handles, labels = axes[0][0].get_legend_handles_labels()
        columns = min(len(labels), max(2, int(fig.get_figwidth() / 2.8)))  # as many as fit across the figure
        rows = -(-len(labels) // columns)
        fig.legend(handles, labels, fontsize=9, loc="upper center", ncol=columns, bbox_to_anchor=(0.5, 1 - 0.25 / fig.get_figheight()))
        fig.suptitle(title + (" (rates smoothed over %d samples)" % window if window > 1 else ""), y=1 - 0.05 / fig.get_figheight())
        fig.tight_layout(rect=(0, 0, 1, 1 - (0.5 + 0.25 * rows) / fig.get_figheight()))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_comparison(groups, path, window, title, show_replicates=False):
    single = all(len(members) == 1 for _, members in groups)  # no runs to count when nothing is averaged
    panels = [p for p in COMPARE_PANELS if not (single and p["count"])]
    plot_comparison_grid(groups, [[p] for p in panels], path, window, title, show_replicates)


def write_group_means(name, members, path, window):
    """The averaged metrics of one group of replicate runs as a CSV: per tick mean, std and number of runs per metric,
    for every panel of the overview and the comparison figures."""
    panels = list(COMPARE_PANELS)
    for _, rows in comparison_figures().values():
        panels += [p for row in rows for p in row]
    columns = {}
    for p in panels:
        key = "".join(ch if ch.isalnum() else "_" for ch in p["label"].lower().replace("%", "pct")).strip("_")
        while "__" in key:
            key = key.replace("__", "_")
        if key in columns or p["count"]:
            continue
        stats = mean_std([s for s in (metric_series(run, p, window) for run in members) if s])
        if stats:
            columns[key] = {t: (m, sd, n) for t, m, sd, n in stats}
    ticks = sorted({t for col in columns.values() for t in col})
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["tick"] + [k + suffix for k in columns for suffix in ("_mean", "_std", "_n")])
        for t in ticks:
            row = [t]
            for col in columns.values():
                row += list(col.get(t, ("", "", "")))
            writer.writerow(row)


SHORT_KEYS = {"soilPatchThreshold": "density threshold", "soilPatchResolution": "patch resolution",
              "soilRegenRate": "soil regen", "hp_predatorMoveInterval": "predator move interval"}

# the late-run window the heatmaps average over, as a fraction of the longest run
LATE_FROM = 0.4

HEATMAP_METRICS = [
    ("Runs lasting to the end (fraction)", None),
    ("Plants", ("population", "Plants")),
    ("Predators", ("population", "Predators")),
    ("Prey (burrowing)", ("population", "Prey (burrowing)")),
    ("Prey (non-burrowing)", ("population", "Prey (non-burrowing)")),
    ("Prey that have burrowed", ("ever_burrowed", "Prey (burrowing)")),
]


def strip_split(label, keys):
    """A configuration label without the parts naming the split settings (batch labels end in _key=value)."""
    for key in keys:
        label = re.sub(r"_?%s=[^_]*" % re.escape(key), "", label)
    return label


def split_value(value):
    try:
        return (0, float(value))
    except ValueError:
        return (1, value)


def late_mean(members, field, role, end):
    """Mean over the late window of a role's value across the runs, with a run that has died counting as 0."""
    start = LATE_FROM * end
    totals = []
    for run in members:
        xs, ys = role_series(run, field).get(role, ([], []))
        values = [y or 0 for x, y in zip(xs, ys) if x >= start]
        samples = max(int((end - start) / 100), 1)  # the record samples every 100 ticks
        totals.append(sum(values) / samples)
    return sum(totals) / len(totals) if totals else None


def plot_heatmaps(named, keys, path_png, path_csv):
    """Every configuration (rows) against every combination of the split settings (columns): the fraction of runs that
    lasted to the end, and late-run populations averaged over all replicates (a run that died counts as 0)."""
    end = max(run["ts_ticks"][-1] for _, members in named for run in members if run["ts_ticks"])
    rows, cols, cells = [], [], {}
    for label, members in named:
        cfg = members[0]["config"]
        row = strip_split(label, keys)
        col = tuple(cfg.get(k, "") for k in keys)
        if row not in rows:
            rows.append(row)
        if col not in cols:
            cols.append(col)
        values = [sum(1 for run in members if run["ts_ticks"] and run["ts_ticks"][-1] >= end) / len(members)]
        values += [late_mean(members, field, role, end) for _, (field, role) in HEATMAP_METRICS[1:]]
        cells[(row, col)] = (values, len(members))
    cols.sort(key=lambda c: [split_value(v) for v in c])
    col_labels = [" / ".join(c) for c in cols]
    col_title = " / ".join(SHORT_KEYS.get(k, k) for k in keys)

    with open(path_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["configuration"] + list(keys) + ["runs"] + [m.lower().replace(" ", "_") for m, _ in HEATMAP_METRICS])
        for row in rows:
            for col in cols:
                if (row, col) in cells:
                    values, n = cells[(row, col)]
                    writer.writerow([row] + list(col) + [n] + ["" if v is None else round(v, 3) for v in values])

    ncols = 2
    nrows = (len(HEATMAP_METRICS) + 1) // 2
    fig, axes = plt.subplots(nrows, ncols, figsize=(max(7, 0.85 * len(cols) + 2.5) * ncols, (0.42 * len(rows) + 2.2) * nrows), squeeze=False)
    for i, (metric, _) in enumerate(HEATMAP_METRICS):
        ax = axes[i // ncols][i % ncols]
        grid = [[cells.get((r, c), ([None] * len(HEATMAP_METRICS), 0))[0][i] for c in cols] for r in rows]
        flat = [v for line in grid for v in line if v is not None]
        top = 1 if i == 0 else (max(flat) if flat and max(flat) > 0 else 1)
        image = ax.imshow([[v if v is not None else float("nan") for v in line] for line in grid], cmap="Blues",
                          vmin=0, vmax=top, aspect="auto")
        for r, line in enumerate(grid):
            for c, v in enumerate(line):
                if v is not None:
                    text = ("%.1f" if i == 0 else "%.0f") % v
                    ax.text(c, r, text, ha="center", va="center", fontsize=7, color="white" if v > 0.6 * top else "#1d1d1f")
        ax.set_xticks(range(len(cols)))
        ax.set_xticklabels(col_labels, fontsize=7, rotation=45 if len(cols) > 6 else 0, ha="right" if len(cols) > 6 else "center")
        ax.set_xlabel(col_title, fontsize=8)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels(rows, fontsize=8)
        ax.set_title(metric if i == 0 else metric + " (late-run mean)", fontsize=10, loc="left")
        fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    for j in range(len(HEATMAP_METRICS), nrows * ncols):
        axes[j // ncols][j % ncols].set_visible(False)
    fig.suptitle("Configurations across %s. Late run = ticks %d-%d; runs that died count as 0" %
                 (", ".join(SHORT_KEYS.get(k, k) for k in keys), LATE_FROM * end, end))
    fig.tight_layout()
    fig.savefig(path_png, dpi=150)
    plt.close(fig)


def write_averages(named, out, window, title_suffix=""):
    """Each configuration's replicates (mean +- 1 std, plus a CSV of every metric), and the configurations compared."""
    os.makedirs(out, exist_ok=True)
    for name, members in named:
        if len(members) > 1:
            safe = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in name)
            plot_comparison([(name, members)], os.path.join(out, safe + ".png"), window,
                            "%s%s: mean +- 1 std over %d replicates" % (name, title_suffix, len(members)), show_replicates=True)
            write_group_means(name, members, os.path.join(out, safe + ".csv"), window)
    plot_comparison(named, os.path.join(out, "comparison_means.png"), window, "Configuration comparison (replicate means)" + title_suffix)
    for file_name, (title, rows) in comparison_figures().items():
        plot_comparison_grid(named, rows, os.path.join(out, file_name), window, title + ": replicate means" + title_suffix)


# run_config keys that differ between replicates of one configuration (seeds, the label, and what was measured)
REPLICATE_KEYS = ("soilSeed", "placementSeed", "runLabel", "soil_fertile_frac")


def read_config(folder):
    """The run_config export of a run as {key: value}; empty for runs exported before it existed."""
    return {row["key"]: row["value"] for row in read_rows(folder, "run_config")}


def config_key(folder, config):
    """Runs with the same key are replicates: same settings, possibly different seeds. Runs without a config are
    only ever grouped with themselves."""
    if not config:
        return ("folder", folder)
    return tuple(sorted((k, v) for k, v in config.items() if k not in REPLICATE_KEYS and not k.startswith("placed_")))


def write_config_table(runs, path):
    """One row per run with its full configuration, and the settings that differ between runs printed."""
    keys = []
    for _, run in runs:
        for key in run["config"]:
            if key not in keys:
                keys.append(key)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["run"] + keys)
        for name, run in runs:
            writer.writerow([name] + [run["config"].get(key, "") for key in keys])
    varying = [k for k in keys if len({run["config"].get(k, "") for _, run in runs}) > 1]
    print("Settings that differ between runs:", ", ".join(varying) if varying else "none")


def detect_predator_lineages(summary_rows):
    """Seeded predator lineages from the species summary: founders (no ancestor) placed at tick 0 whose body has killer
    cells and no producer, the same rule the simulation uses to tag predators. Founders are named randomly, so this
    finds them whatever they're called."""
    founders = [r for r in summary_rows if not r["ancestor"]]
    predators = [r for r in founders if num(r.get("killer")) and not num(r.get("producer"))]
    seeded = [r for r in predators if int(r["start_tick"]) == 0]
    return sorted({r["species"] for r in seeded or predators})


CLAW_PANELS = [
    ("All organisms", None),
    ("Plants", ["Plants"]),
    ("Predators", ["Predators"]),
    ("Prey", ["Prey (burrowing)", "Prey (non-burrowing)"]),
]


def plot_claws(groups_rows, events, out):
    """Claws used for burrowing against claws carried for other reasons, one panel per role. 'Have burrowed' counts the
    organisms with claw cells that have hidden underground at least once in their life; the gap between that and 'with
    claw cells' is claws that aren't (yet) being used. Only prey burrow, so claws on plants and predators never are."""
    role_rows = [r for r in groups_rows if r["grouping"] == "role"]
    if not role_rows or "with_claw" not in role_rows[0]:
        print("  no per-role claw columns in groups_log (exported before they were added), skipping claws_by_role.png")
        return
    totals = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))  # panel -> field -> tick -> sum
    for r in role_rows:
        for title, roles in CLAW_PANELS:
            if roles is None or r["group"] in roles:
                for field in ("population", "with_claw", "ever_burrowed", "hidden"):
                    totals[title][field][int(r["tick"])] += num(r[field]) or 0
    lines = [("population", "Population", "#7f7f7f", 0.8), ("with_claw", "With claw cells", "#8c564b", 1.4),
             ("ever_burrowed", "With claw cells that have burrowed", "#e377c2", 1.4), ("hidden", "Underground", "#9467bd", 1.2)]
    fig, axes = plt.subplots(len(CLAW_PANELS), 1, sharex=True, figsize=(11, 3 * len(CLAW_PANELS) + 1))
    for ax, (title, _) in zip(axes, CLAW_PANELS):
        for field, label, color, width in lines:
            series = totals[title][field]
            ticks = sorted(series)
            ax.plot(ticks, [series[t] for t in ticks], color=color, linewidth=width, label=label)
        draw_events(ax, events)
        ax.set_ylabel("Organisms")
        ax.set_title(title, fontsize=10, loc="left")
    axes[0].legend(fontsize=8, loc="upper left")
    axes[-1].set_xlabel("Tick")
    fig.suptitle("Claws used for burrowing vs. claws carried, by role")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "claws_by_role.png"), dpi=150)
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
        if glob.glob(os.path.join(folder, "timeseries*.csv")):
            runs.append(os.path.abspath(folder))
        else:
            # a batch folder from headless/batch.js: every run inside it
            inner = sorted({os.path.dirname(p) for p in glob.glob(os.path.join(folder, "*", "timeseries*.csv"))})
            if not inner:
                raise SystemExit("No run logs in '%s' or the folders inside it" % folder)
            runs.extend(os.path.abspath(p) for p in inner)
    return list(dict.fromkeys(runs))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="*", help="run folders (names inside Observations/ or paths); default: all of them")
    parser.add_argument("--smooth", type=int, default=5, help="samples to average growth rate, fitness, lifespan at death and traits over (1 = off)")
    parser.add_argument("--follow", help="species name to plot with all its descendant species")
    parser.add_argument("--top", type=int, default=8, help="max lineages to draw")
    parser.add_argument("--split", help="comma-separated run_config keys (e.g. soilPatchThreshold,soilPatchResolution): "
                        "the configurations are compared separately for each combination of their values, in "
                        "averages/<key=value...>/, with heatmaps of every configuration against them in averages/")
    parser.add_argument("--skip-run-plots", action="store_true",
                        help="only redraw the cross-run comparisons and averages, not each run's own plots")
    parser.add_argument("--predator-lineage", action="append",
                        help="seeded predator lineage(s), used to separate evolved predators "
                             "(default: detected from the species summary)")
    args = parser.parse_args()

    folders = find_runs(args.runs)
    if not folders:
        raise SystemExit("No runs found in " + OBSERVATIONS)
    runs = []
    for folder in folders:
        out = os.path.join(folder, "plots")
        ts_rows = sorted(read_rows(folder, "timeseries"), key=lambda r: int(r["tick"]))
        groups_rows = read_rows(folder, "groups_log")
        events = read_rows(folder, "key_moments")
        summary_rows = read_rows(folder, "species_summary")
        predator_lineages = args.predator_lineage or detect_predator_lineages(summary_rows)
        print("%s: seeded predator lineage(s): %s" % (os.path.basename(folder), ", ".join(predator_lineages) or "none found"))

        if not args.skip_run_plots:
            os.makedirs(out, exist_ok=True)
            plot_groups(groups_rows, events, out, args.smooth, args.top)
            plot_burrow_soil(ts_rows, groups_rows, events, out)
            plot_claws(groups_rows, events, out)
            plot_predators(groups_rows, events, out, args.smooth, predator_lineages)
            plot_traits(ts_rows, events, out, args.smooth)
            plot_species_timeline(summary_rows, out)
            if args.follow:
                plot_followed(read_rows(folder, "species_log"), events, out, args.follow, args.smooth)
            print("Saved plots to", out)
        config = read_config(folder)
        # runs are named by folder (replicates share a label), with the label alongside when there is one
        name = os.path.basename(folder) + (" (%s)" % config["runLabel"] if config.get("runLabel") else "")
        run = {"config": config, "folder": folder, "predator_lineages": predator_lineages}
        compact(run, ts_rows, groups_rows)
        runs.append((name, run))

    if len(runs) > 1:
        # cross-run outputs go in the folder holding the runs (Observations/ normally)
        root = os.path.commonpath([os.path.dirname(run["folder"]) for _, run in runs])
        path = os.path.join(root, "comparison.png")
        if len(runs) <= len(PALETTE):
            plot_comparison([(name, [run]) for name, run in runs], path, args.smooth, "Run comparison")
            print("Saved comparison to", path)
        else:
            print("Not drawing every run in one comparison (%d runs); see the averages instead" % len(runs))
        write_config_table(runs, os.path.join(root, "run_configs.csv"))

        # runs with the same settings apart from their seeds are replicates: average them
        groups = {}
        for name, run in runs:
            groups.setdefault(config_key(run["folder"], run["config"]), []).append((name, run))
        named = []
        for i, members in enumerate(groups.values()):
            labels = {run["config"].get("runLabel") for _, run in members}
            label = labels.pop() if len(labels) == 1 and None not in labels and "" not in labels else None
            if not label:
                label = members[0][0] if len(members) == 1 else "config %d" % (i + 1)
            named.append((label, [run for _, run in members]))
        if any(len(members) > 1 for _, members in named):
            avg_dir = os.path.join(root, "averages")
            for name, members in named:
                if len(members) > 1:
                    print("Averaging %d replicates of '%s' (%s)" % (len(members), name, ", ".join(os.path.basename(r["folder"]) for r in members)))
            split_keys = [k.strip() for k in args.split.split(",") if k.strip()] if args.split else []
            if split_keys:
                parts = defaultdict(list)
                for name, members in named:
                    values = tuple(members[0]["config"].get(k, "") for k in split_keys)
                    parts[values].append((strip_split(name, split_keys), members))
                for values in sorted(parts, key=lambda vs: [split_value(v) for v in vs]):
                    folder_name = "_".join("%s=%s" % kv for kv in zip(split_keys, values))
                    suffix = " (%s)" % ", ".join("%s %s" % (SHORT_KEYS.get(k, k), v) for k, v in zip(split_keys, values))
                    write_averages(parts[values], os.path.join(avg_dir, folder_name), args.smooth, suffix)
                    print("Saved averages for", folder_name)
                os.makedirs(avg_dir, exist_ok=True)
                plot_heatmaps(named, split_keys, os.path.join(avg_dir, "heatmaps.png"), os.path.join(avg_dir, "heatmaps.csv"))
            else:
                write_averages(named, avg_dir, args.smooth)
            print("Saved averages to", avg_dir)


if __name__ == "__main__":
    main()
