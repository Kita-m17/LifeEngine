"""Population dynamics of the final-runs batch: growth rate and fitness of each role over time, how populations move
with the soil, how the roles interact, and which interactions drive the extinctions (evolutionary suicide in its
general sense, between any pair of roles, not only burrowing prey and plants).

Usage:
    python analysis/dynamics_analysis.py [Observations/final-runs] [--out results/claws] [--cache DIR]
        [--tarique DIR]

--cache keeps one .npz per run (see dynamics_load.py) so a re-run takes seconds; default <out>/cache.
--tarique is a folder holding Tarique's sweep summaries (evo_suicide.csv, hide_sweep.csv, tuning_sweep.csv, written by
analysis/headless/plot_evo_suicide.py on the tarique-testing branch); the sweep figure is skipped without it.

Definitions (as in final_analysis.py and plot_evo_suicide.py where they overlap):
  growth rate   (births - deaths) / population, per 100 ticks, pooled over a 5,000-tick window
  fitness       offspring per organism that died, pooled over the same window (1 = replacement)
  take-over     a trait is carried by at least TAKE_OVER_COUNT organisms making up at least half of its group
  soil damage   share of the ground that was fertile at the start (above half the mean fertility) that has since been
                degraded below that; only burrowing lowers the soil, so it is zero in noclaw and nocost
  derived predators  predators that are not of the seeded predator lineage: prey that gained a killer cell and became
                predators (preyPredatorChance), and their descendants

Collapse pathways (extinct runs, from the order and timing of the role extinctions):
  early boom-bust          everything died before EARLY_TICKS with no claw take-over (the starting overshoot)
  predator-prey crash      prey and predators died out within GAP ticks of each other: predators ate the prey down
                           and starved
  predators lost first     predators died out more than GAP ticks before the prey, which then died out on their own
                           (the prey-plant side of the web failed)

Writes figures/ and tables/ under --out and tables/numbers.json with the numbers quoted in the report.
"""
import argparse
import csv
import json
import os
import sys
import warnings
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynamics_load  # noqa: E402

SETS = ["main", "noclaw", "nocost"]
SET_NAMES = {"main": "main (claws, burrow cost 10)", "noclaw": "noclaw (no claws)", "nocost": "nocost (free burrowing)"}
SET_SHORT = {"main": "main", "noclaw": "noclaw", "nocost": "nocost"}
SET_COLORS = {"main": "#2a78d6", "noclaw": "#eb6834", "nocost": "#1baf7a"}
SET_STYLES = {"main": "-", "noclaw": "--", "nocost": ":"}
ROLES = ["plants", "pred", "prey", "claw"]
ROLE_NAMES = {"plants": "plants", "pred": "predators", "prey": "prey without a claw", "claw": "prey with a claw",
              "allprey": "all prey"}
ROLE_COLORS = {"plants": "#008300", "pred": "#e34948", "prey": "#2a78d6", "claw": "#eda100", "allprey": "#2a78d6"}
ROLE_STYLES = {"plants": "-", "pred": "-", "prey": "--", "claw": "-"}
SOIL_COLOR = "#8a5a19"
REGENS = ["1", "2.5", "5", "10"]
LAYOUTS = ["dense", "medium", "sparse"]
PATHWAYS = ["early boom-bust", "predator-prey crash", "predators lost first"]
PATH_COLORS = {"early boom-bust": "#8a8a85", "predator-prey crash": "#e34948", "predators lost first": "#2a78d6"}
OUTCOMES = ["took over, then the group died out", "took over, then fell back below half", "took over and persisted",
            "never took over", "group died out, never took over"]
OUTCOME_COLORS = dict(zip(OUTCOMES, ["#e34948", "#6250d6", "#008300", "#c3c2b7", "#4a4a47"]))

N = 2501  # samples of a full 250,000-tick run (every 100 ticks)
TICKS = np.arange(N) * 100
WINDOW = 50  # samples (5,000 ticks) for growth and fitness
TAKE_OVER_COUNT = 50
DERIVED_COUNT = 20
EARLY_TICKS = 30000
GAP = 5000


def style():
    plt.rcParams.update({"font.family": "serif", "font.serif": ["cmr10", "DejaVu Serif"], "mathtext.fontset": "cm",
                         "axes.formatter.use_mathtext": True, "axes.unicode_minus": False, "font.size": 9,
                         "axes.titlesize": 9.5, "axes.labelsize": 9, "legend.fontsize": 8, "legend.frameon": False,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#555",
                         "axes.grid": True, "grid.color": "#e6e6e3", "grid.linewidth": 0.6, "axes.axisbelow": True,
                         "lines.linewidth": 1.6, "savefig.dpi": 200, "savefig.bbox": "tight"})


# ---- per-run series ---------------------------------------------------------------------------------------------

def pad(values, fill=np.nan):
    out = np.full(N, fill, dtype=float)
    out[:min(N, len(values))] = values[:N]
    return out


def window_sum(x, w=WINDOW):
    x = np.nan_to_num(x)
    c = np.concatenate([[0], np.cumsum(x)])
    out = np.full(len(x), np.nan)
    out[w - 1:] = c[w:] - c[:-w]
    return out


def rolling(x, w=20):
    c = np.concatenate([[0], np.cumsum(x)])
    out = np.empty(len(x))
    out[w - 1:] = (c[w:] - c[:-w]) / w
    out[:w - 1] = c[1:w] / np.arange(1, w)
    return out


def prepare(run):
    """Adds padded, derived series to a run: populations (0 after the world died), window growth and fitness."""
    s = run["s"]
    n = len(s["t"])
    p = {}
    for role in ROLES:
        p[role] = pad(s[role + "_population"], 0.0)
    p["allprey"] = p["prey"] + p["claw"]
    alive = np.zeros(N, bool)
    alive[:n] = True
    run["alive"] = alive
    run["pop"] = p
    # populations of worlds still alive, smoothed over 2,000 ticks, for the time-series medians
    run["pop_alive"] = {key: np.where(alive, rolling(v), np.nan) for key, v in p.items()}
    g, f = {}, {}
    for role in ROLES:
        births, deaths, pop = (pad(s[role + "_births"], 0.0), pad(s[role + "_deaths"], 0.0),
                               pad(s[role + "_population"], 0.0))
        fit = pad(s[role + "_fitness"])
        offspring = np.nan_to_num(fit) * deaths
        sb, sd, sp, so = window_sum(births), window_sum(deaths), window_sum(pop), window_sum(offspring)
        with np.errstate(invalid="ignore", divide="ignore"):
            enough = sp >= 10 * WINDOW  # at least 10 organisms on average over the window
            g[role] = np.where(enough & alive, (sb - sd) / sp, np.nan)
            f[role] = np.where(enough & alive & (sd >= 10), so / sd, np.nan)
    run["growth"], run["fitness"] = g, f
    deg = pad(s["w_soil_degraded_frac"])
    d0 = deg[0]
    run["soil_damage"] = np.where(alive, np.clip((deg - d0) / max(1 - d0, 1e-9), 0, None), np.nan)
    pred, lin = p["pred"], pad(s["lin_predator_population"], 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        run["derived_share"] = np.where(pred > 0, np.clip(pred - lin, 0, None) / pred, np.nan)
        run["claw_share"] = np.where(p["allprey"] > 0, p["claw"] / p["allprey"], np.nan)
    run["hunt_eye"] = pad(s["hunt_eye"])
    run["burrows"] = pad(s["claw_burrows"], 0.0) + pad(s["prey_burrows"], 0.0)
    measure(run)
    return run


def first_tick(mask):
    i = np.flatnonzero(mask)
    return int(TICKS[i[0]]) if len(i) else None


def last_alive(pop):
    i = np.flatnonzero(pop > 0)
    return int(TICKS[i[-1]]) if len(i) else 0


def measure(run):
    p = run["pop"]
    extinct = run["state"] == "extinct"
    run["extinct"] = extinct
    run["claw_take"] = first_tick((p["claw"] >= TAKE_OVER_COUNT) & (p["claw"] >= 0.5 * p["allprey"]))
    pred, der = p["pred"], np.nan_to_num(run["derived_share"])
    run["derived_take"] = first_tick((pred >= DERIVED_COUNT) & (der >= 0.5))
    lin = pad(run["s"]["lin_predator_population"], 0.0)
    run["seeded_pred_gone"] = first_tick((TICKS > 1000) & (lin == 0) & run["alive"])
    run["last_prey"], run["last_pred"], run["last_plant"] = (last_alive(p["allprey"]), last_alive(pred),
                                                             last_alive(p["plants"]))
    pathway = ""
    if extinct:
        if run["end_tick"] < EARLY_TICKS and run["claw_take"] is None:
            pathway = "early boom-bust"
        elif run["last_pred"] < run["last_prey"] - GAP:
            pathway = "predators lost first"
        else:
            pathway = "predator-prey crash"
    run["pathway"] = pathway
    # trait outcomes in the spirit of plot_evo_suicide.classify
    end = run["end_tick"]
    prey_gone = extinct or run["last_prey"] < end - 100
    pred_gone = extinct or run["last_pred"] < end - 100
    run["prey_gone"], run["pred_gone"] = prey_gone, pred_gone
    run["claw_outcome"] = trait_outcome(run["claw_take"], run["claw_share"], run["last_prey"], prey_gone)
    run["derived_outcome"] = trait_outcome(run["derived_take"], run["derived_share"], run["last_pred"], pred_gone)


def trait_outcome(take, share, group_last, group_gone):
    """As plot_evo_suicide.classify, for any trait in any group: did the group die out after the trait took over?"""
    if take is None:
        return OUTCOMES[4] if group_gone else OUTCOMES[3]
    if group_gone and group_last >= take:
        return OUTCOMES[0]
    alive = share[~np.isnan(share)]
    if len(alive) and alive[-1] < 0.5:
        return OUTCOMES[1]
    return OUTCOMES[2]


# ---- aggregation --------------------------------------------------------------------------------------------------

def stack(runs, getter):
    return np.vstack([getter(r) for r in runs]) if runs else np.full((1, N), np.nan)


def med_iqr(matrix, min_runs=5):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        q = np.nanpercentile(matrix, [25, 50, 75], axis=0)
    ok = np.sum(~np.isnan(matrix), axis=0) >= min_runs
    return [np.where(ok, x, np.nan) for x in q]


def k(ticks):
    return np.asarray(ticks) / 1000


def band(ax, x, matrix, color, ls="-", label=None, min_runs=5, alpha=0.14):
    lo, mid, hi = med_iqr(matrix, min_runs)
    ax.fill_between(x, lo, hi, color=color, alpha=alpha, lw=0)
    ax.plot(x, mid, color=color, ls=ls, label=label)


def group(runs, **kw):
    return [r for r in runs if all(r[key] == v for key, v in kw.items())]


# ---- figures ------------------------------------------------------------------------------------------------------

def fig_rate(runs, key, ylabel, title, path, ylim, ref):
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.0), sharex=True)
    for ax, role in zip(axes.flat, ROLES):
        for s in SETS:
            g = group(runs, set=s)
            if role == "claw" and s == "noclaw":
                continue
            band(ax, k(TICKS), stack(g, lambda r: r[key][role]), SET_COLORS[s], SET_STYLES[s], SET_NAMES[s])
        ax.axhline(ref, color="#555", lw=0.7)
        ax.set_title(ROLE_NAMES[role])
        ax.set_ylim(*ylim)
    for ax in axes[1]:
        ax.set_xlabel("tick (thousands)")
    for ax in axes[:, 0]:
        ax.set_ylabel(ylabel)
    axes[0, 0].legend(loc="upper right")
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_rate_early(runs, path):
    """Growth and fitness in the first 60,000 ticks, where the claw invades and the predators turn over."""
    fig, axes = plt.subplots(2, 4, figsize=(9.2, 4.2), sharex=True, sharey="row")
    x = k(TICKS)
    for col, role in enumerate(ROLES):
        for row, (key, ref, lim) in enumerate([("growth", 0, (-0.06, 0.08)), ("fitness", 1, (0.5, 1.5))]):
            ax = axes[row, col]
            for s in SETS:
                if role == "claw" and s == "noclaw":
                    continue
                band(ax, x, stack(group(runs, set=s), lambda r: r[key][role]), SET_COLORS[s], SET_STYLES[s],
                     SET_NAMES[s])
            ax.axhline(ref, color="#555", lw=0.7)
            ax.set_xlim(0, 60)
            ax.set_ylim(*lim)
            if row == 0:
                ax.set_title(ROLE_NAMES[role])
            else:
                ax.set_xlabel("tick (thousands)")
    axes[0, 0].set_ylabel("growth rate per 100 ticks")
    axes[1, 0].set_ylabel("fitness (offspring per death)")
    handles = [plt.Line2D([], [], color=SET_COLORS[s], ls=SET_STYLES[s]) for s in SETS]
    fig.legend(handles, [SET_NAMES[s] for s in SETS], loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def fig_claw_advantage(runs, path):
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 2.9))
    x = k(TICKS)
    ax = axes[0]
    for s in ["main", "nocost"]:
        band(ax, x, stack(group(runs, set=s), lambda r: 100 * r["claw_share"]), SET_COLORS[s], SET_STYLES[s],
             SET_NAMES[s])
    ax.set_ylabel("prey with a claw (% of prey)")
    ax.set_xlabel("tick (thousands)")
    ax.set_ylim(0, 100)
    ax.set_xlim(0, 120)
    ax.set_title("(a) spread of the claw")
    ax.legend(loc="lower right")
    ax = axes[1]
    for s in ["main", "nocost"]:
        band(ax, x, stack(group(runs, set=s), lambda r: r["fitness"]["claw"] - r["fitness"]["prey"]), SET_COLORS[s],
             SET_STYLES[s], min_runs=8)
    ax.axhline(0, color="#555", lw=0.7)
    ax.set_xlim(0, 120)
    ax.set_ylim(-0.4, 0.4)
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("fitness, clawed minus clawless prey")
    ax.set_title("(b) fitness advantage while both coexist")
    ax = axes[2]
    for j, s in enumerate(["main", "nocost"]):
        for i, rg in enumerate(REGENS):
            vals = [r["claw_take"] / 1000 for r in group(runs, set=s, regen=rg) if r["claw_take"] is not None]
            xs = i + (j - 0.5) * 0.3
            ax.plot(xs + np.linspace(-0.08, 0.08, len(vals)), vals, "o", ms=2.5, color=SET_COLORS[s], alpha=0.4,
                    mec="none")
            ax.plot([xs - 0.12, xs + 0.12], [np.median(vals)] * 2, color=SET_COLORS[s], lw=2.2,
                    label=SET_NAMES[s] if i == 0 else None)
    ax.set_xticks(range(4), [f"{r}%" for r in REGENS])
    ax.set_xlabel("soil regeneration rate")
    ax.set_ylabel("claw take-over tick (thousands)")
    ax.set_title("(c) take-over time by regeneration rate")
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_population_soil(runs, path):
    rows = [("soil", "fertile ground damaged (%)"), ("plants", "plants"), ("allprey", "prey (all)"),
            ("pred", "predators")]
    fig, axes = plt.subplots(len(rows), 4, figsize=(9.2, 7.6), sharex=True, sharey="row")
    x = k(TICKS)
    for col, rg in enumerate(REGENS):
        for row, (key, label) in enumerate(rows):
            ax = axes[row, col]
            for s in SETS:
                g = group(runs, set=s, regen=rg)
                if key == "soil":
                    m = stack(g, lambda r: 100 * r["soil_damage"])
                else:
                    m = stack(g, lambda r: r["pop_alive"][key])
                band(ax, x, m, SET_COLORS[s], SET_STYLES[s], SET_NAMES[s], min_runs=3)
            if row == 0:
                ax.set_title(f"soil regeneration {rg}% per tick")
            if col == 0:
                ax.set_ylabel(label)
            if row == len(rows) - 1:
                ax.set_xlabel("tick (thousands)")
    axes[0, 0].set_ylim(0, 10)
    handles = [plt.Line2D([], [], color=SET_COLORS[s], ls=SET_STYLES[s]) for s in SETS]
    fig.legend(handles, [SET_NAMES[s] for s in SETS], loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def fig_population_soil_sparse(runs, path):
    """The same as population_soil, sparse maps only, where the extinctions happen."""
    rows = [("soil", "fertile ground damaged (%)"), ("plants", "plants"), ("allprey", "prey (all)"),
            ("pred", "predators"), ("alive", "worlds alive (%)")]
    fig, axes = plt.subplots(len(rows), 4, figsize=(9.2, 8.4), sharex=True, sharey="row")
    x = k(TICKS)
    for col, rg in enumerate(REGENS):
        for row, (key, label) in enumerate(rows):
            ax = axes[row, col]
            for s in SETS:
                g = group(runs, set=s, regen=rg, layout="sparse")
                if key == "alive":
                    ax.plot(x, 100 * stack(g, lambda r: r["alive"].astype(float)).mean(axis=0), color=SET_COLORS[s],
                            ls=SET_STYLES[s])
                    continue
                m = (stack(g, lambda r: 100 * r["soil_damage"]) if key == "soil"
                     else stack(g, lambda r: r["pop_alive"][key]))
                band(ax, x, m, SET_COLORS[s], SET_STYLES[s], min_runs=3)
            if row == 0:
                ax.set_title(f"sparse maps, regeneration {rg}%")
            if col == 0:
                ax.set_ylabel(label)
            if row == len(rows) - 1:
                ax.set_xlabel("tick (thousands)")
    axes[0, 0].set_ylim(0, 10)
    axes[-1, 0].set_ylim(0, 102)
    handles = [plt.Line2D([], [], color=SET_COLORS[s], ls=SET_STYLES[s]) for s in SETS]
    fig.legend(handles, [SET_NAMES[s] for s in SETS], loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def late_mean_alive(run, key, start=50000):
    x = run["pop"][key][start // 100:][run["alive"][start // 100:]]
    return float(np.mean(x)) if len(x) else np.nan


def late_mean(run, key, start=50000):
    x = run["pop"][key][start // 100:]
    return float(np.mean(x))


def fig_soil_coupling(runs, map_type_rows, path):
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 2.9))
    x = k(TICKS)
    main = group(runs, set="main")
    reds = plt.get_cmap("Blues")
    regen_colors = {rg: reds(0.35 + 0.65 * i / 3) for i, rg in enumerate(REGENS)}
    ax = axes[0]
    for rg in REGENS:
        g = group(main, regen=rg)
        lo, mid, hi = med_iqr(stack(g, lambda r: window_sum(r["burrows"]) / WINDOW))
        ax.plot(x, mid, color=regen_colors[rg], label=f"{rg}%")
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("burrows per 100 ticks")
    ax.set_title("(a) burrowing (main)")
    ax.legend(title="regeneration", loc="upper left", ncol=2)
    ax = axes[1]
    for rg in REGENS:
        g = group(main, regen=rg)
        xs = [np.nanmean(window_sum(r["burrows"])[-500:]) / WINDOW if r["alive"][-1] else np.nan for r in g]
        ys = [100 * np.nanmean(r["soil_damage"][-500:]) if r["alive"][-1] else np.nan for r in g]
        ax.plot(xs, ys, "o", ms=3.5, color=regen_colors[rg], mec="white", mew=0.4, label=f"{rg}%")
    ax.set_xlabel("burrows per 100 ticks (last 50k ticks)")
    ax.set_ylabel("fertile ground damaged (%)")
    ax.set_title("(b) soil damage follows burrowing")
    ax = axes[2]
    markers = {"dense": "o", "medium": "s", "sparse": "^"}
    for i, rg in enumerate(REGENS):
        rows = [row for row in map_type_rows if row["regen"] == rg]
        for j, layout in enumerate(LAYOUTS):
            vals = [row["plants_diff"] for row in rows if row["layout"] == layout and not np.isnan(row["plants_diff"])]
            xs = i + (j - 1) * 0.22 + np.linspace(-0.05, 0.05, len(vals))
            ax.plot(xs, np.clip(vals, -60, 60), markers[layout], ms=3.5, color=regen_colors[rg], mec="white", mew=0.4,
                    label=layout if i == 0 else None)
        allv = [row["plants_diff"] for row in rows if not np.isnan(row["plants_diff"])]
        ax.plot([i - 0.32, i + 0.32], [np.median(allv)] * 2, color="#222", lw=1.6)
    ax.axhline(0, color="#555", lw=0.7)
    ax.set_ylim(-62, 62)
    ax.set_xticks(range(4), [f"{r}%" for r in REGENS])
    ax.set_xlabel("soil regeneration rate")
    ax.set_ylabel("plants, main vs nocost (% difference)")
    ax.set_title("(c) the soil cost to plants")
    ax.legend(loc="upper left", fontsize=7, ncol=3)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_fertility(runs, path):
    """Late populations against the fertile share of the map: the static side of soil fertility."""
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 2.8), sharex=True)
    for ax, key in zip(axes, ["plants", "allprey", "pred"]):
        for s in SETS:
            g = group(runs, set=s)
            ax.plot([100 * r["fertile"] for r in g], [late_mean(r, key) for r in g], "o", ms=3, alpha=0.6,
                    mec="none", color=SET_COLORS[s], label=SET_NAMES[s])
        ax.set_xlabel("fertile share of the map (%)")
        ax.set_title(f"mean {ROLE_NAMES[key]}, ticks 50k to 250k")
    axes[0].set_ylabel("organisms (0 once extinct)")
    axes[0].legend(loc="upper left", markerscale=1.6)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def response_points(runs, focal, other, step=10, start=5000):
    """Per 1,000 ticks: per-capita growth of `focal` over the next 1,000 ticks against other/focal density."""
    xs, ys = [], []
    for r in runs:
        s = r["s"]
        n = len(s["t"])
        parts = ["prey", "claw"] if focal == "allprey" else [focal]
        b = sum(pad(s[q + "_births"], 0.0) for q in parts)
        d = sum(pad(s[q + "_deaths"], 0.0) for q in parts)
        pf = r["pop"][focal]
        po = r["pop"][other]
        for i in range(start // 100, n - step, step):
            f = pf[i:i + step].mean()
            if f < 10:
                continue
            xs.append(po[i] / max(pf[i], 1))
            ys.append((b[i:i + step].sum() - d[i:i + step].sum()) / f)
    return np.array(xs), np.array(ys)


def binned(ax, xs, ys, bins, color, ls, label, min_n=30):
    idx = np.digitize(xs, bins)
    cx, cy, lo, hi = [], [], [], []
    for b in range(1, len(bins)):
        sel = ys[idx == b]
        if len(sel) < min_n:
            continue
        cx.append(np.sqrt(bins[b - 1] * bins[b]) if bins[0] > 0 else (bins[b - 1] + bins[b]) / 2)
        cy.append(np.mean(sel))
        se = np.std(sel) / np.sqrt(len(sel))
        lo.append(cy[-1] - 1.96 * se)
        hi.append(cy[-1] + 1.96 * se)
    ax.fill_between(cx, lo, hi, color=color, alpha=0.15, lw=0)
    ax.plot(cx, cy, color=color, ls=ls, marker="o", ms=3, label=label)


def fig_interactions(runs, path):
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 3.0))
    bins = np.geomspace(0.05, 20, 22)
    ax = axes[0]
    for s in SETS:
        xs, ys = response_points(group(runs, set=s), "allprey", "pred")
        binned(ax, xs, ys, bins, SET_COLORS[s], SET_STYLES[s], SET_NAMES[s])
    ax.set_xscale("log")
    ax.axhline(0, color="#555", lw=0.7)
    ax.set_xlabel("predators per prey")
    ax.set_ylabel("per-capita growth per 1,000 ticks")
    ax.set_title("(a) prey growth against predation")
    ax.legend(loc="upper left", fontsize=7)
    ax = axes[1]
    for s in SETS:
        xs, ys = response_points(group(runs, set=s), "pred", "allprey")
        binned(ax, xs, ys, bins, SET_COLORS[s], SET_STYLES[s], SET_NAMES[s])
    ax.set_xscale("log")
    ax.axhline(0, color="#555", lw=0.7)
    ax.set_xlabel("prey per predator")
    ax.set_title("(b) predator growth against prey")
    ax = axes[2]
    for s in SETS:
        xs, ys = response_points(group(runs, set=s), "plants", "allprey")
        binned(ax, xs, ys, bins, SET_COLORS[s], SET_STYLES[s], SET_NAMES[s])
    ax.set_xscale("log")
    ax.axhline(0, color="#555", lw=0.7)
    ax.set_xlabel("prey per plant")
    ax.set_title("(c) plant growth against grazing")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def log_changes(run, key, step=10):
    x = run["pop"][key][: len(run["s"]["t"])][::step]
    return np.diff(np.log(x + 1))


def xcorr(a, b, lags):
    out = []
    for lag in lags:
        if lag >= 0:
            x, y = a[: len(a) - lag], b[lag:]
        else:
            x, y = a[-lag:], b[: len(b) + lag]
        if len(x) < 30 or np.std(x) == 0 or np.std(y) == 0:
            out.append(np.nan)
        else:
            out.append(np.corrcoef(x, y)[0, 1])
    return np.array(out)


def volatility(run, key, start=EARLY_TICKS):
    """Standard deviation of the 1,000-tick changes in log population, while the world was alive after `start`."""
    n = len(run["s"]["t"])
    x = run["pop"][key][start // 100:n][::10]
    if len(x) < 20 or np.mean(x) < 5:
        return np.nan
    return float(np.std(np.diff(np.log(x + 1))))


def fig_volatility(runs, path):
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 2.8), sharey=True)
    for ax, key in zip(axes, ["plants", "allprey", "pred"]):
        for j, s in enumerate(SETS):
            for i, rg in enumerate(REGENS):
                vals = [volatility(r, key) for r in group(runs, set=s, regen=rg)]
                vals = [v for v in vals if not np.isnan(v)]
                xs = i + (j - 1) * 0.26
                ax.plot(xs + np.linspace(-0.07, 0.07, len(vals)), vals, "o", ms=2.2, color=SET_COLORS[s], alpha=0.35,
                        mec="none")
                ax.plot([xs - 0.1, xs + 0.1], [np.median(vals)] * 2, color=SET_COLORS[s], lw=2.2,
                        label=SET_NAMES[s] if i == 0 else None)
        ax.set_xticks(range(4), [f"{r}%" for r in REGENS])
        ax.set_xlabel("soil regeneration rate")
        ax.set_title(ROLE_NAMES[key])
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("volatility (sd of 1,000-tick log change)")
    axes[1].legend(loc="upper center", fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_cross_correlation(runs, path):
    lags = np.arange(-15, 16)
    pairs = [("allprey", "pred", "(a) prey leads predators"), ("plants", "allprey", "(b) plants lead prey"),
             ("pred", "plants", "(c) predators lead plants")]
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 2.8), sharey=True)
    for ax, (a, b, title) in zip(axes, pairs):
        for s in SETS:
            g = [r for r in group(runs, set=s) if len(r["s"]["t"]) > 400]
            m = np.vstack([xcorr(log_changes(r, a), log_changes(r, b), lags) for r in g])
            lo, mid, hi = med_iqr(m)
            ax.fill_between(lags, lo, hi, color=SET_COLORS[s], alpha=0.12, lw=0)
            ax.plot(lags, mid, color=SET_COLORS[s], ls=SET_STYLES[s], label=SET_NAMES[s])
        ax.axhline(0, color="#555", lw=0.7)
        ax.axvline(0, color="#999", lw=0.7)
        ax.set_xlabel(f"lag of {ROLE_NAMES[b]} (thousand ticks)")
        ax.set_title(title)
    axes[0].set_ylabel("correlation of 1,000-tick changes")
    axes[0].legend(loc="lower left", fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_predator_turnover(runs, path):
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 2.8))
    x = k(TICKS)
    ax = axes[0]
    for s in SETS:
        band(ax, x, stack(group(runs, set=s), lambda r: 100 * r["derived_share"]), SET_COLORS[s], SET_STYLES[s],
             SET_NAMES[s])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 102)
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("predators descended from prey (%)")
    ax.set_title("(a) prey-derived predators take over")
    ax.legend(loc="lower right", fontsize=7)
    ax = axes[1]
    for s in SETS:
        band(ax, x, stack(group(runs, set=s), lambda r: r["hunt_eye"]), SET_COLORS[s], SET_STYLES[s])
    ax.set_xlim(0, 100)
    ax.set_xlabel("tick (thousands)")
    ax.set_ylabel("eye cells per predator")
    ax.set_title("(b) the hunters get cheaper")
    ax = axes[2]
    bins = np.arange(0, 110, 5)
    for s in SETS:
        vals = [r["seeded_pred_gone"] / 1000 for r in group(runs, set=s) if r["seeded_pred_gone"]]
        ax.hist(vals, bins=bins, histtype="step", color=SET_COLORS[s], ls=SET_STYLES[s], lw=1.6)
    ax.set_xlabel("tick the lineage died out (thousands)")
    ax.set_ylabel("runs")
    ax.set_title("(c) end of the seeded predators")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_collapse_aligned(runs, path):
    rows = [("allprey", "prey (all)"), ("claw_share", "prey with a claw (%)"), ("pred", "predators"),
            ("plants", "plants"), ("soil", "fertile ground damaged (%)")]
    rel = np.arange(-400, 31)  # samples relative to the last prey
    fig, axes = plt.subplots(len(rows), 3, figsize=(9.2, 8.6), sharex=True, sharey="row")
    for col, s in enumerate(SETS):
        g = [r for r in group(runs, set=s) if r["extinct"]]
        for row, (key, label) in enumerate(rows):
            ax = axes[row, col]
            for r in g:
                i0 = r["last_prey"] // 100
                idx = i0 + rel
                ok = (idx >= 0) & (idx < N)
                if key == "claw_share":
                    series = 100 * r["claw_share"]
                elif key == "soil":
                    series = 100 * r["soil_damage"]
                else:
                    series = r["pop"][key]
                y = np.full(len(rel), np.nan)
                y[ok] = series[idx[ok]]
                ax.plot(k(rel * 100), y, color=PATH_COLORS[r["pathway"]], alpha=0.45, lw=0.8)
            ax.axvline(0, color="#555", lw=0.7, ls=":")
            if row == 0:
                ax.set_title(f"{SET_NAMES[s]}: {len(g)} extinct")
            if col == 0:
                ax.set_ylabel(label)
            if row == len(rows) - 1:
                ax.set_xlabel("ticks from the last prey (thousands)")
    axes[1, 0].set_ylim(0, 102)
    axes[4, 0].set_ylim(0, 10)
    handles = [plt.Line2D([], [], color=PATH_COLORS[p], lw=2) for p in PATHWAYS]
    fig.legend(handles, PATHWAYS, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def stacked_bars(ax, labels, counts_list, cats, colors, totals=None):
    for row, counts in enumerate(counts_list):
        left = 0
        n = sum(counts.values()) if totals is None else totals[row]
        for c in cats:
            v = counts.get(c, 0)
            if v:
                ax.barh(row, v, left=left, color=colors[c], edgecolor="white", linewidth=1, height=0.7)
                if v / max(n, 1) > 0.06:
                    ax.text(left + v / 2, row, str(v), ha="center", va="center", fontsize=7.5,
                            color="white" if colors[c] not in ("#c3c2b7",) else "#222")
            left += v
    ax.set_yticks(range(len(labels)), labels)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)


def fig_pathways(runs, path):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 2.6), gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axes[0]
    labels, counts = [], []
    for s in SETS:
        g = [r for r in group(runs, set=s) if r["extinct"]]
        labels.append(f"{SET_SHORT[s]} ({len(g)})")
        counts.append(Counter(r["pathway"] for r in g))
    stacked_bars(ax, labels, counts, PATHWAYS, PATH_COLORS)
    ax.set_xlabel("extinct runs (of 180)")
    ax.set_title("(a) collapse pathway by set")
    ax = axes[1]
    labels, counts = [], []
    for s in SETS:
        for rg in REGENS:
            g = [r for r in group(runs, set=s, regen=rg) if r["extinct"]]
            labels.append(f"{SET_SHORT[s]}, {rg}%")
            counts.append(Counter(r["pathway"] for r in g))
    stacked_bars(ax, labels, counts, PATHWAYS, PATH_COLORS)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_xlabel("extinct runs (of 45)")
    ax.set_title("(b) by set and soil regeneration rate")
    handles = [plt.Rectangle((0, 0), 1, 1, color=PATH_COLORS[p]) for p in PATHWAYS]
    fig.legend(handles, PATHWAYS, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def fig_trait_outcomes(runs, path):
    fig, ax = plt.subplots(figsize=(9.2, 2.6))
    labels, counts = [], []
    for s in ["main", "nocost"]:
        labels.append(f"claw in prey, {SET_SHORT[s]}")
        counts.append(Counter(r["claw_outcome"] for r in group(runs, set=s)))
    for s in SETS:
        labels.append(f"prey-derived predators, {SET_SHORT[s]}")
        counts.append(Counter(r["derived_outcome"] for r in group(runs, set=s)))
    stacked_bars(ax, labels, counts, OUTCOMES, OUTCOME_COLORS)
    ax.set_xlabel("runs (of 180)")
    ax.set_xlim(0, 180)
    handles = [plt.Rectangle((0, 0), 1, 1, color=OUTCOME_COLORS[o]) for o in OUTCOMES]
    fig.legend(handles, OUTCOMES, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.16))
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def story_label(r):
    return f"{r['set']}, {r['map']}, regeneration {r['regen']}%, replicate {r['rep']}"


def fig_story(run, title, path, xmax=None):
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 5.4), sharex=True, gridspec_kw={"height_ratios": [2.2, 1, 1]})
    n = len(run["s"]["t"])
    x = k(TICKS[:n])
    ax = axes[0]
    for role in ROLES:
        ax.plot(x, run["pop"][role][:n], color=ROLE_COLORS[role], ls=ROLE_STYLES[role], lw=1.1, label=ROLE_NAMES[role])
    ax.set_yscale("symlog", linthresh=10)
    ax.set_ylabel("organisms")
    ax.legend(loc="upper right", ncol=4, fontsize=7.5)
    ax = axes[1]
    ax.plot(x, 100 * run["claw_share"][:n], color=ROLE_COLORS["claw"], label="prey with a claw (% of prey)")
    ax.plot(x, 100 * run["derived_share"][:n], color=ROLE_COLORS["pred"], ls="--",
            label="predators descended from prey (%)")
    ax.set_ylim(0, 105)
    ax.set_ylabel("share (%)")
    ax.legend(loc="lower right", fontsize=7.5)
    ax = axes[2]
    ax.plot(x, 100 * run["soil_damage"][:n], color=SOIL_COLOR)
    ax.set_ylabel("fertile ground\ndamaged (%)")
    ax.set_xlabel("tick (thousands)")
    ax.set_ylim(0, max(5, 1.15 * np.nanmax(100 * run["soil_damage"][:n])))
    for a in axes:
        for t, ls in [(run["claw_take"], "--"), (run["derived_take"], "-.")]:
            if t is not None:
                a.axvline(t / 1000, color="#888", lw=0.8, ls=ls)
        if xmax:
            a.set_xlim(0, xmax)
    axes[0].set_title(title, fontsize=9.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_tarique(tables, path):
    evo, hide, tune = tables
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.0), gridspec_kw={"width_ratios": [1, 1, 1.1]})
    suicide = "claws took over, then all prey died out"
    cost = {"harmless burrowing": 0, "soil cost 3": 3, "soil cost 5": 5, "soil cost 10": 10}
    blues = plt.get_cmap("Blues")
    lifespans = sorted({float(r["predatorLifespanMultiplier"]) for r in evo})
    ax = axes[0]
    for i, life in enumerate(lifespans):
        pts = sorted((cost[r["condition"]], 100 * int(r[suicide]) / int(r["runs"]))
                     for r in evo if float(r["predatorLifespanMultiplier"]) == life and r["condition"] in cost)
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", ms=4,
                color=blues(0.35 + 0.65 * i / max(1, len(lifespans) - 1)), label=f"{life:g}")
    ax.set_xlabel("soil cost per burrow")
    ax.set_ylabel("runs ending in suicide (%)")
    ax.set_title("(a) burrow cost and predator lifespan")
    ax.legend(title="predator lifespan", fontsize=7, title_fontsize=7.5, loc="upper left")
    ax = axes[1]
    for j, dur in enumerate(["30", "100"]):
        rows = [r for r in hide if r["hideDuration"] == dur and r["condition"] in cost]
        rows.sort(key=lambda r: cost[r["condition"]])
        xs = np.arange(len(rows)) + (j - 0.5) * 0.36
        ax.bar(xs, [100 * int(r[suicide]) / int(r["runs"]) for r in rows], width=0.34,
               color=blues(0.45 if dur == "30" else 0.9), label=f"hide {dur} ticks")
        ax.set_xticks(np.arange(len(rows)), [str(cost[r["condition"]]) for r in rows])
    ax.set_xlabel("soil cost per burrow")
    ax.set_title("(b) hide duration")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(axis="x", visible=False)
    ax = axes[2]
    rows = list(tune)
    ax.barh(range(len(rows)), [100 * int(r[suicide]) / int(r["runs"]) for r in rows], color=blues(0.75), height=0.65)
    ax.set_yticks(range(len(rows)), [r["condition"] for r in rows], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("runs ending in suicide (%)")
    ax.set_title("(c) tuning sweep (soil cost 10 unless harmless)")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ---- tables and numbers ------------------------------------------------------------------------------------------

def write_csv(path, rows, fields=None):
    if not rows:
        return
    fields = fields or list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def fisher(a, b, c, d):
    import math
    n, r1, c1 = a + b + c + d, a + b, a + c
    p = lambda x: math.comb(r1, x) * math.comb(n - r1, c1 - x) / math.comb(n, c1)
    p0 = p(a)
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= p0 * (1 + 1e-9)))


def hazard_by_claw_state(runs):
    """Extinctions per million run-ticks after EARLY_TICKS, split by whether clawed prey had taken over."""
    rows = []
    for s in SETS:
        for layout in LAYOUTS + ["all"]:
            g = group(runs, set=s) if layout == "all" else group(runs, set=s, layout=layout)
            before = after = eb = ea = 0
            for r in g:
                end = r["end_tick"]
                take = r["claw_take"] if r["claw_take"] is not None else 10 ** 9
                before += max(0, min(take, end) - EARLY_TICKS)
                after += max(0, end - max(take, EARLY_TICKS))
                if r["extinct"] and end >= EARLY_TICKS:
                    if end < take:
                        eb += 1
                    else:
                        ea += 1
            rows.append(dict(set=s, layout=layout, ticks_before_takeover=before, extinct_before=eb,
                             rate_before=round(eb / before * 1e6, 3) if before else "",
                             ticks_after_takeover=after, extinct_after=ea,
                             rate_after=round(ea / after * 1e6, 3) if after else ""))
    return rows


def run_rows(runs):
    rows = []
    for r in runs:
        rows.append(dict(name=r["name"], set=r["set"], layout=r["layout"], regen=r["regen"], soil=r["soil"],
                         rep=r["rep"], fertile_frac=round(r["fertile"], 4), extinct=int(r["extinct"]),
                         end_tick=r["end_tick"], pathway=r["pathway"], claw_take_over=r["claw_take"] or "",
                         derived_take_over=r["derived_take"] or "", seeded_predators_gone=r["seeded_pred_gone"] or "",
                         last_prey=r["last_prey"], last_predator=r["last_pred"], last_plant=r["last_plant"],
                         claw_outcome=r["claw_outcome"], derived_outcome=r["derived_outcome"],
                         max_soil_damage=round(float(np.nanmax(r["soil_damage"])), 4),
                         late_plants=round(late_mean(r, "plants"), 1), late_prey=round(late_mean(r, "allprey"), 1),
                         late_predators=round(late_mean(r, "pred"), 1),
                         mean_fitness_claw_minus_plain_60k=round(float(np.nanmean(
                             r["fitness"]["claw"][:600] - r["fitness"]["prey"][:600])), 4)
                         if np.any(~np.isnan(r["fitness"]["claw"][:600] - r["fitness"]["prey"][:600])) else ""))
    return rows


def map_type_rows(runs):
    by = defaultdict(list)
    for r in runs:
        by[(r["layout"], r["soil"], r["regen"])].append(r)
    rows = []
    for (layout, soil, regen), g in sorted(by.items()):
        main, nocost = [r for r in g if r["set"] == "main"], [r for r in g if r["set"] == "nocost"]
        pm = np.mean([late_mean(r, "plants") for r in main])
        pn = np.mean([late_mean(r, "plants") for r in nocost])
        pm = np.nanmean([late_mean_alive(r, "plants") for r in main])
        pn = np.nanmean([late_mean_alive(r, "plants") for r in nocost])
        pym = np.nanmean([late_mean_alive(r, "allprey") for r in main])
        pyn = np.nanmean([late_mean_alive(r, "allprey") for r in nocost])
        rows.append(dict(layout=layout, soil=soil, regen=regen,
                         soil_damage_main=round(100 * np.mean([np.nanmean(r["soil_damage"][500:]) for r in main]), 3),
                         plants_main=round(pm, 1), plants_nocost=round(pn, 1),
                         plants_diff=round(100 * (pm - pn) / pn, 2) if pn else np.nan,
                         prey_diff=round(100 * (pym - pyn) / pyn, 2) if pyn else np.nan,
                         extinct_main=sum(r["extinct"] for r in main), extinct_nocost=sum(r["extinct"] for r in nocost)))
    return rows


def spearman(x, y):
    from scipy.stats import spearmanr
    ok = ~(np.isnan(x) | np.isnan(y))
    rho, p = spearmanr(np.asarray(x)[ok], np.asarray(y)[ok])
    return float(rho), float(p)


def numbers(runs, mt_rows, hazard):
    out = {}
    for s in SETS:
        g = group(runs, set=s)
        ext = [r for r in g if r["extinct"]]
        out[s] = dict(extinct=len(ext), pathways=dict(Counter(r["pathway"] for r in ext)),
                      claw_outcomes=dict(Counter(r["claw_outcome"] for r in g)),
                      derived_outcomes=dict(Counter(r["derived_outcome"] for r in g)),
                      seeded_predators_gone=sum(1 for r in g if r["seeded_pred_gone"]),
                      median_seeded_gone=float(np.median([r["seeded_pred_gone"] for r in g if r["seeded_pred_gone"]])),
                      median_derived_take=float(np.median([r["derived_take"] for r in g if r["derived_take"]])),
                      derived_take=sum(1 for r in g if r["derived_take"]),
                      claw_take_before_collapse=sum(1 for r in ext if r["claw_take"] is not None
                                                    and r["claw_take"] < r["last_prey"]),
                      gap_pred_prey_median=float(np.median([r["last_prey"] - r["last_pred"] for r in ext])),
                      late_plants_median=float(np.median([late_mean(r, "plants") for r in g])),
                      late_prey_median=float(np.median([late_mean(r, "allprey") for r in g])),
                      late_pred_median=float(np.median([late_mean(r, "pred") for r in g])))
        for role in ROLES:
            vals = [np.nanmean(r["fitness"][role][500:]) for r in g if np.any(~np.isnan(r["fitness"][role][500:]))]
            gv = [np.nanmean(r["growth"][role][500:]) for r in g if np.any(~np.isnan(r["growth"][role][500:]))]
            out[s]["fitness_" + role] = float(np.median(vals)) if vals else None
            out[s]["growth_" + role] = float(np.median(gv)) if gv else None
            ev = [np.nanmean(r["fitness"][role][50:200]) for r in g if np.any(~np.isnan(r["fitness"][role][50:200]))]
            out[s]["fitness_early_" + role] = float(np.median(ev)) if ev else None
        for key in ["plants", "allprey", "pred"]:
            out[s]["volatility_" + key] = float(np.nanmedian([volatility(r, key) for r in g]))
        before, after = [], []
        for r in g:
            if r["derived_take"] is None:
                continue
            i = r["derived_take"] // 100
            with np.errstate(invalid="ignore", divide="ignore"):
                ratio = r["pop"]["pred"] / np.maximum(r["pop"]["allprey"], 1)
            before.append(np.mean(ratio[max(0, i - 100):i]) if i > 0 else np.nan)
            after.append(np.mean(ratio[i:i + 100]))
        out[s]["pred_per_prey_before_derived"] = float(np.nanmedian(before))
        out[s]["pred_per_prey_after_derived"] = float(np.nanmedian(after))
        out[s]["predators_died_world_survived"] = sum(1 for r in g if r["pred_gone"] and not r["extinct"])
        adv = [np.nanmean(r["fitness"]["claw"][:600] - r["fitness"]["prey"][:600]) for r in g]
        adv = [a for a in adv if not np.isnan(a)]
        if adv:
            out[s]["claw_advantage_median"] = float(np.median(adv))
            out[s]["claw_advantage_positive"] = int(sum(a > 0 for a in adv))
            out[s]["claw_advantage_n"] = len(adv)
        dmg = {rg: float(np.median([100 * np.nanmax(r["soil_damage"]) for r in group(g, regen=rg)])) for rg in REGENS}
        out[s]["max_soil_damage_median_by_regen"] = dmg
        out[s]["max_soil_damage_max"] = float(max(100 * np.nanmax(r["soil_damage"]) for r in g))
        for layout in LAYOUTS:
            out[s]["max_soil_damage_median_" + layout] = float(np.median(
                [100 * np.nanmax(r["soil_damage"]) for r in group(g, layout=layout)]))
    x = np.array([r["soil_damage_main"] for r in mt_rows])
    y = np.array([r["plants_diff"] for r in mt_rows])
    out["soil_damage_vs_plants_diff"] = spearman(x, y)
    out["plants_diff_median"] = float(np.nanmedian(y))
    out["plants_diff_by_regen"] = {rg: dict(median=float(np.nanmedian([r["plants_diff"] for r in mt_rows if r["regen"] == rg])),
                                            negative=int(sum(r["plants_diff"] < 0 for r in mt_rows if r["regen"] == rg)),
                                            n=int(sum(not np.isnan(r["plants_diff"]) for r in mt_rows if r["regen"] == rg)),
                                            by_layout={l: float(np.nanmedian([r["plants_diff"] for r in mt_rows
                                                                              if r["regen"] == rg and r["layout"] == l]))
                                                       for l in LAYOUTS},
                                            prey_median=float(np.nanmedian([r["prey_diff"] for r in mt_rows if r["regen"] == rg])))
                                   for rg in REGENS}
    out["plants_diff_negative"] = int(np.sum(y < 0))
    out["map_types"] = len(mt_rows)
    regen_num = np.array([float(r["regen"]) for r in mt_rows])
    out["soil_damage_vs_regen"] = spearman(regen_num, x)
    f = np.array([r["fertile"] for r in runs])
    for key in ["plants", "allprey", "pred"]:
        out["fertile_vs_late_" + key] = spearman(f, np.array([late_mean(r, key) for r in runs]))
    # predators lost first: claws vs no claws
    lost = {s: sum(1 for r in group(runs, set=s) if r["pathway"] == "predators lost first") for s in SETS}
    out["pred_lost_first_tests"] = {
        "main_vs_noclaw": fisher(lost["main"], 180 - lost["main"], lost["noclaw"], 180 - lost["noclaw"]),
        "nocost_vs_noclaw": fisher(lost["nocost"], 180 - lost["nocost"], lost["noclaw"], 180 - lost["noclaw"])}
    crash = {s: sum(1 for r in group(runs, set=s) if r["pathway"] == "predator-prey crash") for s in SETS}
    out["pp_crash_tests"] = {
        "main_vs_noclaw": fisher(crash["main"], 180 - crash["main"], crash["noclaw"], 180 - crash["noclaw"]),
        "nocost_vs_noclaw": fisher(crash["nocost"], 180 - crash["nocost"], crash["noclaw"], 180 - crash["noclaw"])}
    out["hazard"] = hazard
    return out


def read_tarique(folder):
    tables = []
    for name in ["evo_suicide", "hide_sweep", "tuning_sweep"]:
        with open(os.path.join(folder, name + ".csv"), newline="") as f:
            tables.append(list(csv.DictReader(f)))
    return tables


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default="Observations/final-runs")
    ap.add_argument("--out", default="results/claws")
    ap.add_argument("--cache")
    ap.add_argument("--tarique")
    a = ap.parse_args()
    figs, tabs = os.path.join(a.out, "figures"), os.path.join(a.out, "tables")
    os.makedirs(figs, exist_ok=True)
    os.makedirs(tabs, exist_ok=True)
    style()
    runs = [prepare(r) for r in dynamics_load.load_all(a.root, a.cache or os.path.join(a.out, "cache"))]
    print(len(runs), "runs")
    F = lambda name: os.path.join(figs, name)

    fig_rate(runs, "growth", "growth rate per 100 ticks", "Growth rate of each role (median and interquartile range "
             "over runs, 5,000-tick windows)", F("growth_rate.png"), (-0.04, 0.05), 0)
    fig_rate(runs, "fitness", "fitness (offspring per death)", "Fitness of each role (median and interquartile range "
             "over runs, 5,000-tick windows)", F("fitness.png"), (0.6, 1.4), 1)
    fig_rate_early(runs, F("growth_fitness_early.png"))
    fig_claw_advantage(runs, F("claw_advantage.png"))
    fig_population_soil(runs, F("population_soil.png"))
    fig_population_soil_sparse(runs, F("population_soil_sparse.png"))
    mt = map_type_rows(runs)
    fig_soil_coupling(runs, mt, F("soil_coupling.png"))
    fig_fertility(runs, F("fertility.png"))
    fig_interactions(runs, F("interactions.png"))
    fig_cross_correlation(runs, F("cross_correlation.png"))
    fig_volatility(runs, F("volatility.png"))
    fig_predator_turnover(runs, F("predator_turnover.png"))
    fig_collapse_aligned(runs, F("collapse_aligned.png"))
    fig_pathways(runs, F("pathways.png"))
    fig_trait_outcomes(runs, F("trait_outcomes.png"))

    by_name = {r["name"]: r for r in runs}
    lost = max((r for r in group(runs, set="main") if r["pathway"] == "predators lost first"),
               key=lambda r: r["last_prey"] - r["last_pred"])
    fig_story(lost, f"{story_label(lost)}: predators die out, prey follow "
                    f"{(lost['last_prey'] - lost['last_pred']) / 1000:.0f}k ticks later", F("story_pred_lost.png"))
    crash = by_name.get("main-sparse_soilRegenRate=1_seed1_soil2024_rep2")
    if crash:
        fig_story(crash, f"{story_label(crash)}: claw take-over, then a predator-prey crash",
                  F("story_claw_crash.png"))
    noclaw = sorted((r for r in group(runs, set="noclaw", layout="sparse") if r["pathway"] == "predator-prey crash"
                     and r["end_tick"] > 80000), key=lambda r: r["end_tick"])
    if noclaw:
        noclaw = noclaw[len(noclaw) // 2]
        fig_story(noclaw, f"{story_label(noclaw)}: predator-prey crash without claws", F("story_noclaw_crash.png"))
    survivor = sorted((r for r in group(runs, set="main", layout="sparse") if not r["extinct"]),
                      key=lambda r: (r["soil"] != "2024", r["regen"] != "1", r["rep"]))
    if survivor:
        r = survivor[0]
        fig_story(r, f"{story_label(r)}: claws take over and the world survives", F("story_survivor.png"))
    nums_stories = dict(pred_lost=lost["name"], claw_crash=crash["name"] if crash else None,
                        noclaw_crash=noclaw["name"] if noclaw else None, survivor=survivor[0]["name"] if survivor else None)
    if a.tarique:
        fig_tarique(read_tarique(a.tarique), F("tarique_sweeps.png"))

    rows = run_rows(runs)
    write_csv(os.path.join(tabs, "runs_dynamics.csv"), rows)
    write_csv(os.path.join(tabs, "map_types_soil.csv"), mt)
    hz = hazard_by_claw_state(runs)
    write_csv(os.path.join(tabs, "hazard_claw_state.csv"), hz)
    nums = numbers(runs, mt, hz)
    nums["stories"] = nums_stories
    with open(os.path.join(tabs, "numbers.json"), "w") as f:
        json.dump(nums, f, indent=1, default=float)
    print(json.dumps({s: {k: v for k, v in nums[s].items() if k in ("extinct", "pathways")} for s in SETS}))


if __name__ == "__main__":
    main()
