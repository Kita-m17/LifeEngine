"""Figures for the evolutionary suicide experiments run with sweep.js.

Usage:
    pip install matplotlib numpy
    python analysis/headless/plot_evo_suicide.py RESULTS_DIR [RESULTS_DIR ...] [--out DIR]
        [--damage "soil cost 10"] [--control "harmless burrowing"] [--baseline "no burrowing"]
        [--by predatorLifespanMultiplier] [--focus 2] [--only CONDITION ...] [--example-seed N]
        [--label NAME ...] [--browser-view CONDITION ...] [--highlight-seed 1] [--rename OLD=NEW ...]

RESULTS_DIR is a folder written by sweep.js (e.g. analysis/headless/results/evo_suicide). Several folders can be
plotted together, e.g. evo_suicide and predator_sweep to compare predator lifespans. Figures go to
<first RESULTS_DIR>/figures/ unless --out is given.

To compare the same sweep run on two versions of the code, give each folder a --label (in the same order) and use
--by source: the suicide map then has one row per folder.

Every run is sorted into one outcome:
    claws took over, then all prey died out   evolutionary suicide
    claws took over, then were lost           the claw disappeared but prey without it carried on
    claws took over and persisted
    claws never took over                     prey survived without the claw spreading
    prey died out, claws never took over      the food web crashed for other reasons
"Took over" means at least TAKEOVER_MIN prey with a claw, making up at least TAKEOVER_SHARE of all prey. A run that
ends with at most COLLAPSE_PREY prey and COLLAPSE_PLANTS plants counts as all prey dying out (it is beyond recovery).

Figures:
    outcomes.png           how many runs of each setup ended in each outcome
    example_run.png        one starting layout run with damaging and with harmless burrowing, side by side
    after_takeover.png     every run lined up on the moment the claws took over: does the soil and food hold up?
    collapse_sequence.png  every evolutionary suicide lined up on the moment the last prey died
    ensemble.png           claw share, soil and plants over time for every run of every setup (no median: the
                           outcomes split into groups, so a median would describe none of them)
    suicide_map.png        (with --by, or several values of a varied setting) how often each setup ends in suicide
    browser_view.png       (with --browser-view) the chosen setups in the measures of the browser's "Burrowing & Soil
                           Health" chart: population, organisms with claws, soil over the whole grid, degraded tiles
Also summary.csv, one row per setup.
"""
import argparse
import csv
import glob
import json
import os
from collections import Counter, OrderedDict
from math import comb

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

TAKEOVER_MIN = 50
TAKEOVER_SHARE = 0.5
COLLAPSE_PREY = 2
COLLAPSE_PLANTS = 5

SUICIDE = "claws took over, then all prey died out"
LOST = "claws took over, then were lost"
PERSIST = "claws took over and persisted"
NO_TAKEOVER = "claws never took over"
CRASHED = "prey died out, claws never took over"
OUTCOMES = [SUICIDE, LOST, PERSIST, NO_TAKEOVER, CRASHED]
OUTCOME_COLORS = {SUICIDE: "#d62728", LOST: "#1f77b4", PERSIST: "#2ca02c", NO_TAKEOVER: "#a6a6a6", CRASHED: "#404040"}

CLAW_COLOR = "#8c564b"
PREY_COLOR = "#1f77b4"
PREDATOR_COLOR = "#d62728"
PLANT_COLOR = "#2ca02c"
SOIL_COLOR = "#d08c2c"

# a median is only drawn where at least this share of the runs still have a value (runs end when everything dies)
MEDIAN_MIN_SHARE = 0.5
NICE_NAMES = {"predatorLifespanMultiplier": "predator lifespan multiplier", "hideFertilityCost": "soil cost per burrow",
              "hideDuration": "hide duration (ticks)", "plantRegrowthRate": "plant regrowth (% chance per tick)",
              "source": "code"}

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "savefig.bbox": "tight", "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 11, "legend.frameon": False,
})


# ---- loading and classifying -----------------------------------------------------------------------------------

def load_runs(dirs, labels=None):
    runs, condition_order = [], []
    for index, d in enumerate(dirs):
        source = labels[index] if labels and index < len(labels) else os.path.basename(os.path.normpath(d))
        sweep_file = os.path.join(d, "sweep.json")
        if os.path.exists(sweep_file):
            with open(sweep_file) as f:
                for condition in json.load(f).get("conditions", []):
                    if condition["name"] not in condition_order:
                        condition_order.append(condition["name"])
        for path in sorted(glob.glob(os.path.join(d, "*.json"))):
            if os.path.basename(path) == "sweep.json":
                continue
            with open(path) as f:
                raw = json.load(f)
            if "series" not in raw:
                continue
            series = {key: np.array(values, dtype=float) for key, values in raw["series"].items()}
            run = {
                "file": path,
                "condition": raw["meta"]["condition"],
                "seed": raw["meta"]["seed"],
                "vary": raw["meta"].get("vary") or {},
                "params": dict(raw["hyperparams"], **raw["environment_params"]),
                "ticks": raw["ticks"],
                "extinct_at": raw["extinct_at"],
                "source": source,
                "s": series,
            }
            run.update(classify(run))
            runs.append(run)
            if run["condition"] not in condition_order:
                condition_order.append(run["condition"])
    return runs, condition_order


def classify(run):
    s = run["s"]
    t, claw = s["t"], s["claw_prey"]
    all_prey = s["prey"] + s["claw_prey"]
    result = {"takeover_t": None, "collapse_t": None, "claws_lost_t": None}
    gone = np.flatnonzero(all_prey[1:] == 0) + 1
    beyond_recovery = all_prey[-1] <= COLLAPSE_PREY and s["plants"][-1] <= COLLAPSE_PLANTS
    result["prey_survived"] = len(gone) == 0 and not beyond_recovery
    took_over = np.flatnonzero((claw >= TAKEOVER_MIN) & (claw >= TAKEOVER_SHARE * all_prey))
    if len(took_over) == 0:
        result["outcome"] = CRASHED if len(gone) else NO_TAKEOVER
        return result
    i = took_over[0]
    result["takeover_t"] = t[i]
    gone_after = np.flatnonzero(all_prey[i:] == 0)
    lost_after = np.flatnonzero(claw[i:] == 0)
    if len(gone_after) or beyond_recovery:
        result["outcome"] = SUICIDE
        result["collapse_t"] = t[i + gone_after[0]] if len(gone_after) else t[-1]
    elif len(lost_after):
        result["outcome"] = LOST
        result["claws_lost_t"] = t[i + lost_after[0]]
    else:
        result["outcome"] = PERSIST
    return result


def by_value(run, by):
    if by == "source":
        return run["source"]
    return run["params"].get(by) if by else None


def fmt(value):
    if value is None:
        return "not in this code"
    return f"{value:g}" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)


def nice(by, value=None):
    name = NICE_NAMES.get(by, by)
    return name if value is None else f"{name} = {fmt(value)}"


def ordered_values(runs, by):
    """The values of --by: largest number first, or in folder order for labels and missing settings."""
    seen = []
    for run in runs:
        value = by_value(run, by)
        if value not in seen:
            seen.append(value)
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in seen):
        return sorted(seen, reverse=True)
    return seen


def robust_median(matrix):
    """Median across runs, left out where fewer than MEDIAN_MIN_SHARE of the runs have a value."""
    matrix = np.asarray(matrix, dtype=float)
    enough = np.sum(~np.isnan(matrix), axis=0) >= MEDIAN_MIN_SHARE * matrix.shape[0]
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            median = np.nanmedian(matrix, axis=0)
    return np.where(enough, median, np.nan)


def fisher_two_sided(a, b, c, d):
    """Fisher's exact test for the table [[a, b], [c, d]] (e.g. suicides vs not, in two setups)."""
    n1, n2, k = a + b, c + d, a + c
    total = comb(n1 + n2, k)
    prob = lambda x: comb(n1, x) * comb(n2, k - x) / total
    observed = prob(a)
    return min(1.0, sum(prob(x) for x in range(max(0, k - n2), min(k, n1) + 1) if prob(x) <= observed * (1 + 1e-9)))


def padded(runs, key, fill_after_end):
    """Stack one series from every run into a matrix, padding runs that ended early (everything died)."""
    length = max(len(run["s"]["t"]) for run in runs)
    t = next(run["s"]["t"] for run in runs if len(run["s"]["t"]) == length)
    out = np.full((len(runs), length), np.nan)
    for row, run in enumerate(runs):
        values = series_of(run, key)
        out[row, :len(values)] = values
        out[row, len(values):] = fill_after_end
    return t, out


def series_of(run, key):
    s = run["s"]
    if key == "claw_share":
        all_prey = s["prey"] + s["claw_prey"]
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(all_prey > 0, 100 * s["claw_prey"] / all_prey, np.nan)
    if key == "all_prey":
        return s["prey"] + s["claw_prey"]
    return s[key]


# ---- figures -------------------------------------------------------------------------------------------------------

def label_of(condition, runs):
    """e.g. 'soil cost 10' -> 'soil cost 10 (n=20)'"""
    return f"{condition} (n={sum(1 for run in runs if run['condition'] == condition)})"


def plot_outcomes(runs, conditions, out, title_note, args):
    fig, ax = plt.subplots(figsize=(8, 0.6 * len(conditions) + 1.8))
    for row, condition in enumerate(conditions):
        group = [run for run in runs if run["condition"] == condition]
        counts = Counter(run["outcome"] for run in group)
        left = 0
        for outcome in OUTCOMES:
            share = counts[outcome] / len(group) * 100 if group else 0
            if share:
                ax.barh(row, share, left=left, color=OUTCOME_COLORS[outcome], edgecolor="white")
                if counts[outcome] and share >= 6:
                    ax.text(left + share / 2, row, str(counts[outcome]), ha="center", va="center",
                            color="white" if outcome in (SUICIDE, LOST, PERSIST, CRASHED) else "black", fontsize=9)
            left += share
    ax.set_yticks(range(len(conditions)), [label_of(c, runs) for c in conditions])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of runs")
    ax.set_title("How each run ended" + title_note, pad=20)
    handles = [plt.Rectangle((0, 0), 1, 1, color=OUTCOME_COLORS[o]) for o in OUTCOMES]
    ax.legend(handles, OUTCOMES, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2, fontsize=8.5)
    test = suicide_test(runs, args)
    if test:
        ax.text(0.5, 1.01, test, transform=ax.transAxes, ha="center", va="bottom", fontsize=8.5, color="#444")
    fig.savefig(os.path.join(out, "outcomes.png"))
    plt.close(fig)


def suicide_test(runs, args):
    damage = [run for run in runs if run["condition"] == args.damage]
    control = [run for run in runs if run["condition"] == args.control]
    if not damage or not control:
        return None
    a = sum(run["outcome"] == SUICIDE for run in damage)
    c = sum(run["outcome"] == SUICIDE for run in control)
    p = fisher_two_sided(a, len(damage) - a, c, len(control) - c)
    return f"all prey died after take-over: {args.damage} {a}/{len(damage)} vs {args.control} {c}/{len(control)} (Fisher p = {p:.2g})"


def pick_example(runs, args):
    damage = {run["seed"]: run for run in runs if run["condition"] == args.damage}
    control = {run["seed"]: run for run in runs if run["condition"] == args.control}
    if args.example_seed is not None:
        seed = args.example_seed
        return (damage.get(seed), control.get(seed)) if seed in damage and seed in control else (None, None)
    # the clearest pair: a suicide where no prey ever came back, next to claws that took over and persisted, with
    # both take-overs inside the window example_run.png shows, then the quickest collapse
    pairs = [(damage[s], control[s]) for s in damage if s in control
             and damage[s]["outcome"] == SUICIDE and control[s]["outcome"] == PERSIST]
    if not pairs:
        pairs = [(damage[s], control[s]) for s in damage if s in control and damage[s]["outcome"] == SUICIDE]
    if not pairs:
        return None, None

    def unclear(pair):
        run, other = pair
        t = list(run["s"]["t"])
        after = run["s"]["prey"][t.index(run["collapse_t"]):] + run["s"]["claw_prey"][t.index(run["collapse_t"]):]
        prey_came_back = after.max() > COLLAPSE_PREY
        outside = other["takeover_t"] is None or other["takeover_t"] > example_window(run, other, args)
        return (prey_came_back, outside, run["collapse_t"], run["seed"])
    return min(pairs, key=unclear)


def example_window(damage, control, args):
    full = max(damage["s"]["t"][-1], control["s"]["t"][-1])
    end = damage["collapse_t"] if damage["collapse_t"] is not None else full
    return args.example_ticks or min(full, max(20000, 1.5 * end))


def plot_example(runs, out, args):
    damage, control = pick_example(runs, args)
    if damage is None:
        print("example_run.png skipped: no seed has an evolutionary suicide with damaging burrowing and a run without")
        return
    fig, axes = plt.subplots(3, 2, figsize=(12, 8), sharex="col", sharey="row")
    # both columns show the same stretch: up to a while after the collapse, so the collapse isn't squashed
    full = max(damage["s"]["t"][-1], control["s"]["t"][-1])
    x_max = example_window(damage, control, args) / 1000
    for col, run in enumerate([damage, control]):
        title = run["condition"]
        s, t = run["s"], run["s"]["t"] / 1000
        ax = axes[0, col]
        ax.plot(t, s["claw_prey"], color=CLAW_COLOR, label="prey with a claw")
        ax.plot(t, s["prey"], color=PREY_COLOR, label="prey without a claw")
        ax.plot(t, s["predators"], color=PREDATOR_COLOR, label="predators")
        ax.set_title(f"{title}: {run['outcome']}", fontsize=10.5)
        ax = axes[1, col]
        ax.plot(t, series_of(run, "claw_share"), color=CLAW_COLOR)
        ax.set_ylim(0, 105)
        ax = axes[2, col]
        ax.plot(t, s["plants"], color=PLANT_COLOR, label="plants")
        soil_ax = ax.twinx()
        soil_ax.plot(t, s["soil"], color=SOIL_COLOR, label="soil fertility")
        soil_ax.plot(t, s["growable"], color=SOIL_COLOR, ls="--", lw=1, label="soil fertile enough for plants")
        soil_ax.set_ylim(0, 105)
        soil_ax.spines["right"].set_visible(True)
        soil_ax.spines["top"].set_visible(False)
        if col == 1:
            soil_ax.set_ylabel("soil (%)", color=SOIL_COLOR)
        else:
            soil_ax.set_yticklabels([])
        ax.set_xlabel("tick (thousands)")
        ax.set_xlim(0, x_max)
        shown = lambda when: when is not None and when / 1000 <= x_max
        for row in range(3):
            if shown(run["takeover_t"]):
                axes[row, col].axvline(run["takeover_t"] / 1000, color="#999", ls="--", lw=1)
            if shown(run["collapse_t"]):
                axes[row, col].axvline(run["collapse_t"] / 1000, color="black", ls=":", lw=1.2)
        if shown(run["takeover_t"]):
            axes[0, col].annotate("claws take over", (run["takeover_t"] / 1000, 1), xycoords=("data", "axes fraction"),
                                  xytext=(3, -12), textcoords="offset points", fontsize=8, color="#666")
        if shown(run["collapse_t"]):
            axes[0, col].annotate("last prey dies", (run["collapse_t"] / 1000, 1), xycoords=("data", "axes fraction"),
                                  xytext=(-3, -12), textcoords="offset points", fontsize=8, ha="right")
        if col == 0:
            lines = ax.get_lines()[:1] + soil_ax.get_lines()[:2]
            ax.legend(lines, [l.get_label() for l in lines], loc="upper right", fontsize=8.5)
    axes[0, 0].legend(loc="upper right", fontsize=8.5)
    axes[0, 0].set_ylabel("organisms")
    axes[1, 0].set_ylabel("prey with a claw (% of prey)")
    axes[2, 0].set_ylabel("plants", color=PLANT_COLOR)
    fig.suptitle(f"Same starting layout (placement seed {damage['seed']}): the only difference is whether burrowing "
                 f"damages the soil" + (f" (first {x_max:g}k of {full / 1000:g}k ticks)" if x_max < full / 1000 else ""),
                 fontsize=11.5)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "example_run.png"))
    plt.close(fig)


def plot_aligned(runs, conditions, out, args, align, filename, window, title):
    """Line every run up on an event (take-over or collapse) and show what happens around it."""
    if align == "takeover_t":
        columns = [c for c in conditions if any(r["condition"] == c and r["takeover_t"] is not None for r in runs)]
        columns = [c for c in columns if c != args.baseline]
    else:
        columns = [args.damage]
    columns = [c for c in columns if any(r["condition"] == c and r[align] is not None for r in runs)]
    if not columns:
        print(f"{filename} skipped: no runs with that event")
        return
    rows = [("claw_prey", "prey with a claw", CLAW_COLOR), ("soil", "soil fertility (% of max)", SOIL_COLOR),
            ("plants", "plants", PLANT_COLOR)]
    fig, axes = plt.subplots(len(rows), len(columns), figsize=(max(6.5, 3.6 * len(columns) + 1), 7.5), sharex=True,
                             sharey="row", squeeze=False)
    rel = np.arange(window[0], window[1] + 1, 1000)
    for col, condition in enumerate(columns):
        group = [r for r in runs if r["condition"] == condition and r[align] is not None]
        for row, (key, ylabel, color) in enumerate(rows):
            ax = axes[row, col]
            stack = []
            for run in group:
                t, values = run["s"]["t"], series_of(run, key)
                aligned = np.full(len(rel), np.nan)
                for j, dt in enumerate(rel):
                    idx = np.searchsorted(t, run[align] + dt)
                    if idx < len(t) and t[idx] == run[align] + dt:
                        aligned[j] = values[idx]
                    elif run[align] + dt > t[-1] and run["extinct_at"] is not None and key != "soil":
                        aligned[j] = 0  # everything had died
                stack.append(aligned)
                ax.plot(rel / 1000, aligned, color=OUTCOME_COLORS[run["outcome"]], alpha=0.35, lw=0.8)
            if stack:
                ax.plot(rel / 1000, robust_median(stack), color="black", lw=2, label="median")
            ax.axvline(0, color="#999", ls="--", lw=1)
            if key == "soil":
                ax.set_ylim(0, 105)
            if col == 0:
                ax.set_ylabel(ylabel, color=color)
            if row == 0:
                ax.set_title(f"{condition} ({len(group)} runs)")
            if row == len(rows) - 1:
                ax.set_xlabel(("ticks since the claws took over" if align == "takeover_t" else
                               "ticks before / after the last prey died") + " (thousands)")
    shown = [o for o in OUTCOMES if any(r["outcome"] == o and r["condition"] in columns and r[align] is not None
                                         for r in runs)]
    handles = [plt.Line2D([], [], color=OUTCOME_COLORS[o], lw=2) for o in shown] + [plt.Line2D([], [], color="black", lw=2)]
    fig.legend(handles, shown + ["median"], loc="lower center", ncol=min(4, len(shown) + 1), fontsize=8.5,
               bbox_to_anchor=(0.5, -0.03))
    fig.suptitle(title, fontsize=11.5)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(os.path.join(out, filename))
    plt.close(fig)


def plot_ensemble(runs, conditions, out):
    rows = [("claw_share", "prey with a claw (% of prey)", 0), ("soil", "soil fertility (% of max)", np.nan),
            ("plants", "plants", 0)]
    fig, axes = plt.subplots(len(rows), len(conditions), figsize=(3.4 * len(conditions) + 1, 7.5), sharex=True,
                             sharey="row", squeeze=False)
    for col, condition in enumerate(conditions):
        group = [run for run in runs if run["condition"] == condition]
        if not group:
            continue
        for row, (key, ylabel, fill) in enumerate(rows):
            ax = axes[row, col]
            t, matrix = padded(group, key, np.nan if key == "claw_share" else fill)
            for run, values in zip(group, matrix):
                ax.plot(t / 1000, values, color=OUTCOME_COLORS[run["outcome"]], alpha=0.35, lw=0.8)
            if key in ("soil", "claw_share"):
                ax.set_ylim(0, 105)
            if col == 0:
                ax.set_ylabel(ylabel)
            if row == 0:
                ax.set_title(label_of(condition, runs))
            if row == len(rows) - 1:
                ax.set_xlabel("tick (thousands)")
    handles = [plt.Line2D([], [], color=OUTCOME_COLORS[o], lw=2) for o in OUTCOMES]
    fig.legend(handles, OUTCOMES, loc="lower center", ncol=3, fontsize=8.5, bbox_to_anchor=(0.5, -0.05))
    fig.suptitle("Every run, coloured by how it ended", fontsize=11.5)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(os.path.join(out, "ensemble.png"))
    plt.close(fig)


def plot_browser_view(runs, conditions, out, highlight_seed):
    """The browser's "Burrowing & Soil Health" chart measures, for every run of the chosen setups."""
    conditions = [c for c in conditions if any(r["condition"] == c and "soil_all" in r["s"] for r in runs)]
    if not conditions:
        print("browser_view.png skipped: these runs don't have the browser chart's measures (rerun with the new run_sim.js)")
        return
    rows = [("population", "population", 0), ("with_claw", "with claw cells", 0),
            ("soil_all", "avg. soil fertility (%)", np.nan), ("degraded", "degraded tiles (%)", np.nan)]
    fig, axes = plt.subplots(len(rows), len(conditions), figsize=(4.2 * len(conditions) + 1, 9), sharex=True,
                             sharey="row", squeeze=False)
    for col, condition in enumerate(conditions):
        group = [r for r in runs if r["condition"] == condition]
        for row, (key, ylabel, fill) in enumerate(rows):
            ax = axes[row, col]
            t, matrix = padded(group, key, fill)
            for run, values in zip(group, matrix):
                highlight = run["seed"] == highlight_seed
                ax.plot(t / 1000, values, color="black" if highlight else OUTCOME_COLORS[run["outcome"]],
                        alpha=0.9 if highlight else 0.35, lw=1.4 if highlight else 0.8, zorder=3 if highlight else 2)
            if key in ("soil_all", "degraded"):
                ax.set_ylim(0, 100)
            if col == 0:
                ax.set_ylabel(ylabel)
            if row == 0:
                ax.set_title(label_of(condition, runs))
            if row == len(rows) - 1:
                ax.set_xlabel("tick (thousands)")
    shown = [o for o in OUTCOMES if any(r["outcome"] == o and r["condition"] in conditions for r in runs)]
    handles = [plt.Line2D([], [], color=OUTCOME_COLORS[o], lw=2) for o in shown] + \
              [plt.Line2D([], [], color="black", lw=1.4)]
    fig.legend(handles, shown + [f"placement seed {highlight_seed}"], loc="lower center", ncol=3, fontsize=8.5,
               bbox_to_anchor=(0.5, -0.04))
    fig.suptitle("In the browser chart's measures (soil and degraded tiles count the whole grid, "
                 "including the permanently infertile paths)", fontsize=11)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(os.path.join(out, "browser_view.png"))
    plt.close(fig)


def plot_suicide_map(runs, conditions, by, out, args):
    values = ordered_values(runs, by)
    fig, ax = plt.subplots(figsize=(2.3 * len(conditions) + 1.5, 1.1 * len(values) + 1.6))
    share = np.full((len(values), len(conditions)), np.nan)
    for i, value in enumerate(values):
        for j, condition in enumerate(conditions):
            group = [r for r in runs if by_value(r, by) == value and r["condition"] == condition]
            if not group:
                continue
            n = len(group)
            suicides = sum(r["outcome"] == SUICIDE for r in group)
            took_over = sum(r["takeover_t"] is not None for r in group)
            alive = sum(r["prey_survived"] for r in group)
            share[i, j] = suicides / n
            text = (f"prey survived {alive}/{n}" if condition == args.baseline else
                    f"suicide {suicides}/{n}\ntook over {took_over}/{n}")
            ax.text(j, i, text, ha="center", va="center", fontsize=9,
                    color="white" if share[i, j] > 0.45 else "black")
    image = ax.imshow(share, cmap="Reds", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(conditions)), conditions)
    ax.set_yticks(range(len(values)), [fmt(v) for v in values])
    ax.set_ylabel(nice(by))
    ax.spines[:].set_visible(False)
    fig.colorbar(image, ax=ax, label="share of runs ending in evolutionary suicide", fraction=0.04)
    ax.set_title("Where evolutionary suicide happens\n"
                 f"('{args.baseline}': how often prey survive 100k ticks when the claw can't do anything)")
    fig.savefig(os.path.join(out, "suicide_map.png"))
    plt.close(fig)


def write_summary(runs, conditions, by, out):
    path = os.path.join(out, "summary.csv")
    values = ordered_values(runs, by)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(([by] if by else []) + ["condition", "runs", "prey_never_died_out", "claws_took_over"] +
                        OUTCOMES + ["median_takeover_tick", "median_collapse_tick", "median_lowest_soil",
                                    "median_lowest_plants"])
        for value in values:
            for condition in conditions:
                group = [r for r in runs if by_value(r, by) == value and r["condition"] == condition]
                if not group:
                    continue
                counts = Counter(r["outcome"] for r in group)
                med = lambda xs: float(np.median(xs)) if xs else ""
                row = ([fmt(value)] if by else []) + [condition, len(group),
                       sum(r["prey_survived"] for r in group),
                       sum(r["takeover_t"] is not None for r in group)] + [counts[o] for o in OUTCOMES] + [
                       med([r["takeover_t"] for r in group if r["takeover_t"] is not None]),
                       med([r["collapse_t"] for r in group if r["collapse_t"] is not None]),
                       med([float(r["s"]["soil"].min()) for r in group]),
                       med([float(r["s"]["plants"][3:].min()) if len(r["s"]["plants"]) > 3 else 0 for r in group])]
                writer.writerow(row)
                print(("" if not by else f"{nice(by, value)}  ") + f"{condition:22s} n={len(group):3d}  " +
                      ", ".join(f"{o}: {counts[o]}" for o in OUTCOMES if counts[o]))
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="+", help="results folders written by sweep.js")
    parser.add_argument("--out", help="folder for the figures (default: <first dir>/figures)")
    parser.add_argument("--damage", default="soil cost 10", help="the condition where burrowing damages the soil")
    parser.add_argument("--control", default="harmless burrowing", help="the same burrowing without the soil damage")
    parser.add_argument("--baseline", default="no burrowing", help="the condition where burrowing is switched off")
    parser.add_argument("--by", help="a setting that differs between runs (default: the one the sweeps varied)")
    parser.add_argument("--focus", help="the value of --by to draw the single-setting figures for "
                                        "(default: the value with the most runs)")
    parser.add_argument("--label", action="append", metavar="NAME",
                        help="a name for each results folder, in order (used by --by source)")
    parser.add_argument("--browser-view", action="append", metavar="CONDITION",
                        help="draw browser_view.png for this condition (repeat for several)")
    parser.add_argument("--highlight-seed", type=int, default=1, help="placement seed drawn in black in browser_view.png")
    parser.add_argument("--rename", action="append", metavar="OLD=NEW", default=[],
                        help="replace OLD with NEW in condition names before plotting (other options use the new names)")
    parser.add_argument("--only", action="append", metavar="CONDITION",
                        help="plot only this condition (repeat for several, in the order given)")
    parser.add_argument("--example-seed", type=int, help="placement seed for example_run.png")
    parser.add_argument("--example-ticks", type=float, help="how many ticks example_run.png shows (default: until a "
                                                             "while after the collapse)")
    args = parser.parse_args()

    runs, conditions = load_runs(args.dirs, args.label)
    if not runs:
        raise SystemExit("no runs found in " + ", ".join(args.dirs))
    for pair in args.rename:
        old, new = pair.split("=", 1)
        for run in runs:
            run["condition"] = run["condition"].replace(old, new)
        conditions = list(dict.fromkeys(c.replace(old, new) for c in conditions))
    if args.baseline in conditions:  # the baseline goes first, whichever folder it came from
        conditions = [args.baseline] + [c for c in conditions if c != args.baseline]
    if args.only:
        missing = [name for name in args.only if name not in conditions]
        if missing:
            raise SystemExit("no runs for: " + ", ".join(missing) + "\nconditions found: " + ", ".join(conditions))
        conditions = args.only
        runs = [run for run in runs if run["condition"] in conditions]
    by = args.by
    if not by:
        varied = {key for run in runs for key in run["vary"]}
        by = varied.pop() if len(varied) == 1 else None
    out = args.out or os.path.join(args.dirs[0], "figures")
    os.makedirs(out, exist_ok=True)

    write_summary(runs, conditions, by, out)
    focus_runs, note = runs, ""
    if by:
        plot_suicide_map(runs, conditions, by, out, args)
        counts = Counter(by_value(run, by) for run in runs)
        first_dir = Counter(by_value(run, by) for run in runs if os.path.dirname(run["file"]) == os.path.normpath(args.dirs[0]))
        if args.focus is not None:
            matches = [v for v in counts if fmt(v) == args.focus or str(v) == args.focus]
            if not matches:
                raise SystemExit(f"--focus {args.focus}: values of {by} are " + ", ".join(fmt(v) for v in counts))
            focus = matches[0]
        else:
            focus = max(counts, key=lambda v: (counts[v], first_dir[v]))
        focus_runs = [run for run in runs if by_value(run, by) == focus]
        note = f" ({nice(by, focus)})"
    test = suicide_test(focus_runs, args)
    if test:
        print(test)
    plot_outcomes(focus_runs, conditions, out, note, args)
    plot_example(focus_runs, out, args)
    plot_aligned(focus_runs, conditions, out, args, "takeover_t", "after_takeover.png", (-10000, 60000),
                 "What happens after the claws take over" + note)
    plot_aligned(focus_runs, conditions, out, args, "collapse_t", "collapse_sequence.png", (-40000, 2000),
                 "Every evolutionary suicide, lined up on the moment the last prey died" + note)
    plot_ensemble(focus_runs, conditions, out)
    if args.browser_view:
        plot_browser_view(focus_runs, args.browser_view, out, args.highlight_seed)
    print("figures in", out)


if __name__ == "__main__":
    main()
