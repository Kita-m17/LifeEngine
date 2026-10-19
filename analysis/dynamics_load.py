"""Loads the final-runs logs into one array bundle per run (cached as .npz), for dynamics_analysis.py.

Per run, on the 100-tick sampling grid of the logs:
  role series     population, fitness, growth, birth and death rate, clawed organisms, burrows, hidden, for each role
                  (Plants, Predators, Prey (non-burrowing) = prey without a claw, Prey (burrowing) = prey with a claw)
  lineage series  population of each seeded lineage (plant, predator, prey_small, prey_large): predators that are not
                  of the predator lineage descend from prey that gained a killer cell (preyPredatorChance)
  hunters         population-weighted mean killer, eye and mover cells of the organisms that carry a killer cell and
                  move (predators, plus the occasional armed prey), from species_log and species_summary
  world           soil_mean, soil_degraded_frac, fitness_all, growth_rate (timeseries)

Usage (normally called from dynamics_analysis.py):
    python analysis/dynamics_load.py Observations/final-runs --cache DIR
"""
import argparse
import glob
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

ROLES = ["Plants", "Predators", "Prey (non-burrowing)", "Prey (burrowing)"]
ROLE_KEYS = {"Plants": "plants", "Predators": "pred", "Prey (non-burrowing)": "prey", "Prey (burrowing)": "claw"}
ROLE_FIELDS = ["population", "fitness", "growth_rate", "birth_rate", "death_rate", "with_claw", "burrows", "hidden",
               "births", "deaths"]
LINEAGES = ["plant", "predator", "prey_small", "prey_large"]
WORLD_FIELDS = ["soil_mean", "soil_degraded_frac", "fitness_all", "growth_rate", "population"]
NAME_RE = re.compile(r"(main|noclaw|nocost)-(dense|medium|sparse)_soilRegenRate=([\d.]+)_seed1_soil(\d+)_rep(\d+)$")


def parts(folder, prefix):
    return sorted(glob.glob(os.path.join(folder, prefix + "*.csv")))


def load_folder(folder):
    m = NAME_RE.match(os.path.basename(folder.rstrip("/")))
    exp, layout, regen, soil, rep = m.groups()
    status = json.load(open(os.path.join(folder, "status.json")))
    ts = pd.read_csv(parts(folder, "timeseries")[-1])
    t = ts["tick"].to_numpy(dtype=np.int64)
    out = {"t": t}
    for f in WORLD_FIELDS:
        out["w_" + f] = ts[f].to_numpy(dtype=float)

    g = pd.concat([pd.read_csv(p) for p in parts(folder, "groups_log")], ignore_index=True)
    g = g.drop_duplicates(["tick", "grouping", "group"], keep="last")
    for grouping, names, keyfn in [("role", ROLES, lambda n: ROLE_KEYS[n]), ("lineage", LINEAGES, lambda n: "lin_" + n)]:
        sub = g[g["grouping"] == grouping]
        for name in names:
            rows = sub[sub["group"] == name].set_index("tick").reindex(t)
            fields = ROLE_FIELDS if grouping == "role" else ["population"]
            for f in fields:
                col = rows[f].to_numpy(dtype=float)
                if f in ("population", "with_claw", "burrows", "hidden", "births", "deaths"):
                    col = np.nan_to_num(col, nan=0.0)
                out[f"{keyfn(name)}_{f}"] = col

    # hunting apparatus of killer-bearing movers, weighted by population
    summary = pd.read_csv(parts(folder, "species_summary")[-1], usecols=["species", "killer", "eye", "mover", "producer"])
    armed = summary[(summary["killer"] > 0) & (summary["mover"] > 0)].set_index("species")
    sums = {k: np.zeros(len(t)) for k in ("n", "killer", "eye", "mover")}
    if len(armed):
        for p in parts(folder, "species_log"):
            sl = pd.read_csv(p, usecols=["tick", "species", "population"])
            sl = sl[sl["species"].isin(armed.index)]
            if not len(sl):
                continue
            sl = sl.join(armed, on="species")
            idx = np.searchsorted(t, sl["tick"].to_numpy())
            ok = (idx < len(t))
            idx, sl = idx[ok], sl[ok]
            ok = t[idx] == sl["tick"].to_numpy()
            idx, sl = idx[ok], sl[ok]
            pop = sl["population"].to_numpy(dtype=float)
            np.add.at(sums["n"], idx, pop)
            for k in ("killer", "eye", "mover"):
                np.add.at(sums[k], idx, pop * sl[k].to_numpy(dtype=float))
    with np.errstate(invalid="ignore", divide="ignore"):
        for k in ("killer", "eye", "mover"):
            out["hunt_" + k] = np.where(sums["n"] > 0, sums[k] / sums["n"], np.nan)
    out["hunt_n"] = sums["n"]

    config = {}
    for line in open(parts(folder, "run_config")[-1]):
        bits = line.rstrip("\n").split(",", 1)
        if len(bits) == 2:
            config[bits[0]] = bits[1]
    meta = dict(name=os.path.basename(folder.rstrip("/")), set=exp, layout=layout, regen=regen, soil=soil,
                rep=int(rep), map=layout + "-" + soil, state=status["state"], end_tick=int(t[-1]),
                fertile=float(config.get("soil_fertile_frac", "nan")))
    return meta, out


def cache_one(args):
    folder, cache = args
    name = os.path.basename(folder.rstrip("/"))
    path = os.path.join(cache, name + ".npz")
    if not os.path.exists(path):
        meta, out = load_folder(folder)
        np.savez_compressed(path, meta=json.dumps(meta), **out)
    return path


def load_all(root, cache, workers=8):
    os.makedirs(cache, exist_ok=True)
    folders = sorted(f for f in glob.glob(os.path.join(root, "*")) if NAME_RE.match(os.path.basename(f)))
    paths = [os.path.join(cache, os.path.basename(f) + ".npz") for f in folders]
    missing = [(f, cache) for f, p in zip(folders, paths) if not os.path.exists(p)]
    if missing:
        with ProcessPoolExecutor(workers) as ex:
            list(ex.map(cache_one, missing))
    runs = []
    for p in paths:
        z = np.load(p)
        meta = json.loads(str(z["meta"]))
        meta["s"] = {k: z[k] for k in z.files if k != "meta"}
        runs.append(meta)
    return runs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="Observations/final-runs")
    ap.add_argument("--cache", required=True)
    a = ap.parse_args()
    runs = load_all(a.root, a.cache)
    print(len(runs), "runs loaded", file=sys.stderr)
