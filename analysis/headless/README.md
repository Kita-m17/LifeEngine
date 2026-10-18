# Headless experiments

These scripts run LifeEngine without the browser, using the same `src/` code, so batches of long runs finish in minutes
instead of hours. On this branch the headless world also calls `WorldEnvironment.regrowPlant` every tick, so plant
regrowth behaves exactly as in the browser.

## Files

| File | What it does |
|---|---|
| `run_sim.js` | Runs one simulation and saves the populations and soil every 1000 ticks as JSON. The header comment lists every option. |
| `sweep.js` | Runs every setup in a sweep file for several placement seeds, one run per CPU core at a time. An interrupted sweep picks up where it stopped. |
| `sweeps/*.json` | The sweep files behind the results below. Each one lists its settings, setups and seeds. |
| `plot_evo_suicide.py` | Classifies every run and draws the figures and `summary.csv`. The docstring explains the outcome rules and each figure. |
| `plot_steps.py` | One outcome bar per hand-picked setup, across result folders. |

Plotting needs `pip install matplotlib numpy`.

## Results (`results/jenna-testing/`)

Every run here is 100,000 ticks on this branch's code (commit `919202f`). Each sweep folder holds one JSON file per run,
a copy of its sweep file (`sweep.json`) and the figures in `figures/`. The PDF report summarises all of them.

| Folder | Runs | What it tests |
|---|---|---|
| `jenna_config` | 80 | The settings from `run_config_tick73074.csv` on its 306 x 140 grid: as exported, harmless burrowing, no burrowing, no plant regrowth |
| `evo_suicide` | 100 | Reference settings with burrowing off, harmless, and soil cost 3, 5 and 10 |
| `regrowth_sweep` | 180 | Plant regrowth at 0, 0.25% and 3% (1% is in `evo_suicide`) |
| `ablation_sweep` | 160 | Predator armour, the plant-claw rule and the plant-death change switched off one at a time with regrowth on, and all four off |
| `ablation_no_regrowth` | 60 | The same three switched off one at a time with regrowth off |
| `predator_sweep` | 96 | Predator lifespan multiplier 3, 1.5 and 1 (2 is in `evo_suicide`) |
| `hide_sweep` | 80 | 30-tick hides |
| `tuning_sweep` | 180 | Hide duration 150, soil cost 7, soil regrowth 0.025, stay hidden range 3 and 10 |

Each run's JSON contains `meta` (sweep, setup name, placement seed, switched-off changes), `settings` (what the sweep
set), `environment_params` and `hyperparams` (every value the run used), `extinct_at` (the tick every organism was dead,
or null) and `series`: one value per 1000 ticks for `t`, `predators`, `prey` (no claw), `claw_prey`, `plants`, `other`,
`hidden`, `burrows`, `soil` and `growable` (fertile soil only, % of maximum), `population`, `with_claw`, `regrown`, and
`soil_all` and `degraded` (the browser chart's whole-grid measures).

## Examples

```
# draw the figures for one sweep (into <folder>/figures/)
python analysis/headless/plot_evo_suicide.py analysis/headless/results/jenna-testing/jenna_config \
    --damage "her settings" --control "her settings, harmless burrowing" --baseline "her settings, no burrowing" \
    --browser-view "her settings"

# compare plant regrowth rates across two sweeps
python analysis/headless/plot_evo_suicide.py analysis/headless/results/jenna-testing/regrowth_sweep \
    analysis/headless/results/jenna-testing/evo_suicide --by plantRegrowthRate \
    --only "no burrowing" --only "harmless burrowing" --only "soil cost 10"

# rerun a sweep into a new folder (about 30 minutes per 100 runs on an 8-core laptop)
node analysis/headless/sweep.js analysis/headless/sweeps/jenna_config.json --out analysis/headless/results/my_rerun

# one run with any Run Setup or Evolution Controls setting, switching off the predator armour
node analysis/headless/run_sim.js --ticks 100000 --set '{"plantRegrowthRate":0,"placementSeed":3}' \
    --ablate no_predator_armour --out run.json
```

The simulation is random beyond the starting layout, so a rerun gives similar rates, not identical runs.
