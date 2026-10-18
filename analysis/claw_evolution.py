"""Does the claw evolve? Per-run and per-configuration measures of claws arising by mutation, spreading and being used.

Usage:
    python analysis/claw_evolution.py Observations/<batch> [--take-over-count 50]

Reads every run folder in the batch (as written by headless/batch.js). Clawed prey are counted from the per-role logs
(groups_log, "Prey (burrowing)"), which count every prey organism carrying a claw. They are split by origin:
  seeded  - descendants of the seeded clawed prey: prey of species whose founder had a claw, in a lineage founded by a
            seeded clawed prey (species bodies come from species_summary, so this is an estimate)
  evolved - every other clawed prey: the claw arose by mutation. In runs with no seeded clawed prey this is exact.
A single-cell claw mutation rarely founds a new species, so species bodies alone would miss most evolved claws.

Writes to <batch>/claw_evolution/:
  runs.csv      one row per run
  configs.csv   one row per configuration (rates and medians over its runs)
  claw_share.png  share of prey carrying a claw over time, evolved and seeded, mean +- 1 std per configuration
  summary.png   how often claws evolved, took over, were used, and how the worlds ended

A take-over follows the group's definition (Burrowing_Into_Extinction): at least 50 clawed prey making up at least half
of all prey. An "all prey died after take-over" run is the group's evolutionary-suicide outcome.
"""
import argparse
import csv
import glob
import json
import os
import statistics
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ORIGIN_COLORS = {"evolved": "#d62728", "seeded": "#8c564b"}


def read_rows(folder, prefix):
    rows = []
    for path in sorted(glob.glob(os.path.join(folder, prefix + "*.csv"))):
        with open(path, newline="") as f:
            rows.extend(csv.DictReader(f))
    return rows


def body_role(s):
    killer, producer, mover = int(s["killer"]), int(s["producer"]), int(s["mover"])
    if killer > 0 and producer == 0:
        return "predator"
    if producer > 0 and mover == 0:
        return "plant"
    return "prey"


def analyse_run(folder, take_over_count):
    settings = json.load(open(os.path.join(folder, "settings.json")))
    status = json.load(open(os.path.join(folder, "status.json")))
    summary = {r["species"]: r for r in read_rows(folder, "species_summary")}
    founders = {name: s for name, s in summary.items() if not s["ancestor"]}
    seeded_claw_lineages = {name for name, s in founders.items() if int(s["claw"]) > 0 and int(s["start_tick"]) == 0}

    # every clawed prey and all prey per tick, and burrows, from the role grouping (organism counts)
    prey = defaultdict(float)
    clawed_total = defaultdict(float)
    burrows_total = 0
    for r in read_rows(folder, "groups_log"):
        if r["grouping"] == "role" and r["group"] in ("Prey (burrowing)", "Prey (non-burrowing)"):
            prey[int(r["tick"])] += float(r["population"])
            if r["group"] == "Prey (burrowing)":
                clawed_total[int(r["tick"])] += float(r["population"])
                burrows_total += int(r["burrows"] or 0)
    ticks = sorted(prey)

    # the seeded share, estimated from the species descended from the seeded clawed prey
    seeded = defaultdict(int)
    seeded_burrows = 0
    if seeded_claw_lineages:
        for r in read_rows(folder, "species_log"):
            s = summary.get(r["species"])
            if s and s["lineage"] in seeded_claw_lineages and int(s["claw"]) > 0 and body_role(s) == "prey":
                seeded[int(r["tick"])] += int(r["population"])
                seeded_burrows += int(r["burrows"] or 0)
    clawed = {"seeded": {t: min(seeded.get(t, 0), clawed_total[t]) for t in ticks}}
    clawed["evolved"] = {t: max(clawed_total[t] - clawed["seeded"][t], 0) for t in ticks}
    burrows = {"seeded": min(seeded_burrows, burrows_total)}
    burrows["evolved"] = burrows_total - burrows["seeded"]
    first_evolved = next((t for t in ticks if clawed["evolved"][t] > 0), None)

    def take_over(origins):
        for t in ticks:
            n = sum(clawed[o].get(t, 0) for o in origins)
            if n >= take_over_count and n >= prey[t] / 2:
                return t
        return None

    any_take_over = take_over(("evolved", "seeded"))
    evolved_take_over = take_over(("evolved",))
    prey_alive = [t for t in ticks if prey[t] > 0]
    prey_extinct = prey_alive[-1] + 100 if prey_alive and prey_alive[-1] < ticks[-1] else None
    end = status["tick"]
    late = [t for t in ticks if t >= 0.6 * end]
    share = lambda origin: (statistics.mean(clawed[origin].get(t, 0) / prey[t] for t in late if prey[t] > 0)
                            if any(prey[t] > 0 for t in late) else None)
    label = settings["settings"]["runLabel"]
    return {
        "run": os.path.basename(folder),
        "config": label,
        "seed": settings["settings"]["placementSeed"],
        "seeded_claws": bool(seeded_claw_lineages),
        "soil_seed": settings["settings"].get("soilSeed", ""),
        "outcome": status["state"],
        "end_tick": end,
        "claw_evolved": first_evolved is not None,
        "first_evolved_tick": first_evolved,
        "take_over_tick": any_take_over,
        "evolved_take_over_tick": evolved_take_over,
        "prey_extinct_tick": prey_extinct,
        "all_prey_died_after_take_over": any_take_over is not None and prey_extinct is not None and prey_extinct > any_take_over,
        "evolved_burrows": burrows["evolved"],
        "seeded_burrows": burrows["seeded"],
        "late_evolved_claw_share": share("evolved"),
        "late_seeded_claw_share": share("seeded"),
        "_series": {"ticks": ticks, "prey": [prey[t] for t in ticks],
                    "evolved": [clawed["evolved"].get(t, 0) for t in ticks],
                    "seeded": [clawed["seeded"].get(t, 0) for t in ticks]},
    }


def config_rows(runs):
    by_config = defaultdict(list)
    for r in runs:
        by_config[r["config"]].append(r)
    rows = []
    median = lambda values: statistics.median(values) if values else None
    for config, members in by_config.items():
        n = len(members)
        took = [r for r in members if r["take_over_tick"] is not None]
        rows.append({
            "config": config,
            "runs": n,
            "claw_evolved": sum(r["claw_evolved"] for r in members),
            "median_first_evolved_tick": median([r["first_evolved_tick"] for r in members if r["first_evolved_tick"] is not None]),
            "evolved_claws_took_over": sum(r["evolved_take_over_tick"] is not None for r in members),
            "any_claws_took_over": len(took),
            "all_prey_died_after_take_over": sum(r["all_prey_died_after_take_over"] for r in members),
            "prey_died_without_take_over": sum(r["prey_extinct_tick"] is not None and r["take_over_tick"] is None for r in members),
            "world_lasted": sum(r["outcome"] == "finished" for r in members),
            "median_evolved_burrows": median([r["evolved_burrows"] for r in members]),
            "median_seeded_burrows": median([r["seeded_burrows"] for r in members]),
            "median_late_evolved_claw_share": median([r["late_evolved_claw_share"] for r in members if r["late_evolved_claw_share"] is not None]),
            "median_late_seeded_claw_share": median([r["late_seeded_claw_share"] for r in members if r["late_seeded_claw_share"] is not None]),
        })
    return rows


def write_csv(path, rows):
    keys = [k for k in rows[0] if not k.startswith("_")]
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(keys)
        for r in rows:
            writer.writerow(["" if r[k] is None else (round(r[k], 3) if isinstance(r[k], float) else r[k]) for k in keys])


def plot_claw_share(runs, configs, path):
    """Share of prey carrying a claw over time, evolved and seeded, one panel per configuration."""
    ncols = min(4, len(configs))
    nrows = (len(configs) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.2 * ncols, 2.9 * nrows + 0.8), sharex=True, sharey=True, squeeze=False)
    for i, config in enumerate(configs):
        ax = axes[i // ncols][i % ncols]
        members = [r for r in runs if r["config"] == config]
        for origin in ("seeded", "evolved"):
            per_tick = defaultdict(list)
            for r in members:
                s = r["_series"]
                for t, p, n in zip(s["ticks"], s["prey"], s[origin]):
                    if p > 0:
                        per_tick[t].append(n / p)
            ticks = sorted(per_tick)
            if not ticks or not any(v for t in ticks for v in per_tick[t]):
                continue
            mean = [statistics.mean(per_tick[t]) for t in ticks]
            std = [statistics.stdev(per_tick[t]) if len(per_tick[t]) > 1 else 0 for t in ticks]
            ax.plot(ticks, mean, color=ORIGIN_COLORS[origin], linewidth=1.1, label="%s claws" % origin)
            ax.fill_between(ticks, [max(m - s, 0) for m, s in zip(mean, std)], [min(m + s, 1) for m, s in zip(mean, std)],
                            color=ORIGIN_COLORS[origin], alpha=0.15, linewidth=0)
        ax.set_title(config, fontsize=9, loc="left")
        ax.set_ylim(0, 1)
        ax.grid(axis="y", color="#e5e5e5", linewidth=0.8)
        if i % ncols == 0:
            ax.set_ylabel("Share of prey with a claw", fontsize=8)
        if i // ncols == nrows - 1:
            ax.set_xlabel("Tick", fontsize=8)
    for j in range(len(configs), nrows * ncols):
        axes[j // ncols][j % ncols].set_visible(False)
    handles = [plt.Line2D([], [], color=c, label="%s claws" % o) for o, c in ORIGIN_COLORS.items()]
    fig.legend(handles=handles, loc="upper center", ncol=2, fontsize=9, bbox_to_anchor=(0.5, 1 - 0.1 / fig.get_figheight()))
    fig.suptitle("Share of prey carrying a claw: mean +- 1 std over each configuration's runs (only runs with prey alive)",
                 y=1 - 0.02 / fig.get_figheight(), fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.55 / fig.get_figheight()))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_summary(rows, path):
    """Per configuration: claws evolved, evolved claws took over, any claws took over, prey died after a take-over,
    world lasted to the end, as fractions of its runs."""
    measures = [("claw_evolved", "Claw evolved by mutation", "#fcbba1"),
                ("evolved_claws_took_over", "Evolved claws took over", "#d62728"),
                ("any_claws_took_over", "Any claws took over", "#8c564b"),
                ("all_prey_died_after_take_over", "All prey died after a take-over", "#252525"),
                ("world_lasted", "World lasted to the end", "#2b5797")]
    fig, ax = plt.subplots(figsize=(max(9, 1.5 * len(rows)), 4.2))
    width = 0.8 / len(measures)
    for k, (key, label, color) in enumerate(measures):
        xs = [i + (k - (len(measures) - 1) / 2) * width for i in range(len(rows))]
        ax.bar(xs, [r[key] / r["runs"] for r in rows], width * 0.92, color=color, label=label)
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels([r["config"] for r in rows], fontsize=8, rotation=20, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Fraction of runs")
    ax.grid(axis="y", color="#e5e5e5", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.18))
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("batch", help="batch folder from headless/batch.js")
    parser.add_argument("--take-over-count", type=int, default=50, help="clawed prey needed for a take-over (default 50)")
    args = parser.parse_args()

    folders = sorted(os.path.dirname(p) for p in glob.glob(os.path.join(args.batch, "*", "status.json")))
    runs = []
    for folder in folders:
        status = json.load(open(os.path.join(folder, "status.json")))
        if status["state"] not in ("finished", "extinct"):
            print("skipping %s (%s)" % (os.path.basename(folder), status["state"]))
            continue
        runs.append(analyse_run(folder, args.take_over_count))
    if not runs:
        raise SystemExit("No finished runs in " + args.batch)
    configs = list(dict.fromkeys(r["config"] for r in sorted(runs, key=lambda r: r["run"])))
    out = os.path.join(args.batch, "claw_evolution")
    os.makedirs(out, exist_ok=True)
    write_csv(os.path.join(out, "runs.csv"), runs)
    rows = sorted(config_rows(runs), key=lambda r: configs.index(r["config"]))
    write_csv(os.path.join(out, "configs.csv"), rows)
    plot_claw_share(runs, configs, os.path.join(out, "claw_share.png"))
    plot_summary(rows, os.path.join(out, "summary.png"))
    for r in rows:
        print("%-24s claws evolved %2d/%d, evolved took over %2d, any took over %2d, all prey died after %2d, world lasted %2d"
              % (r["config"], r["claw_evolved"], r["runs"], r["evolved_claws_took_over"], r["any_claws_took_over"],
                 r["all_prey_died_after_take_over"], r["world_lasted"]))
    print("Saved to", out)


if __name__ == "__main__":
    main()
