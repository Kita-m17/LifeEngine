# Digging Their Own Graves: The Life Engine with soil, claws and burrowing

A UCT Artificial Life project by Jenna Rigby, Tarique Mackay, Joshua Diegaardt and Nikita Martin, built on
[The Life Engine](https://github.com/MaxRobinsonTheGreat/EvolutionSimulatorV2) by Max Robinson.

Our question: can a trait that saves each individual doom the population? Prey can evolve a **claw** that lets them
burrow out of a predator's sight, but every burrow strips fertility from the soil, and plants (the prey's food) only
grow on fertile soil. We added soil, predator and prey roles, claws and burrowing, detailed logging and a headless
runner to test whether the claw spreads and then drives its own population extinct (evolutionary suicide).

The original Life Engine is a cellular automaton for long-term evolution: organisms eat, reproduce, mutate and adapt,
with no fitness function, only natural selection. The original rules are described under
[How the Simulation Works](#how-the-simulation-works), with our changes folded in.


# What we changed

### Soil and fertility
- Every grid cell has a **fertility** (0 to 10) and a **fertility cap**. `src/Grid/SoilLayout.js` lays out the caps
  from seeded Perlin noise: cells above a threshold are fertile patches (cap 10), the rest are permanently infertile
  pathways (cap 0). The **soil seed**, **density** (threshold) and **patch size** (resolution) fix the layout, so the
  same seeds on the same grid always give the same map, in the browser and headless.
- **Plants need fertile soil.** A plant (a producer that cannot move) can only be born or placed where the average
  fertility under its body is at least **Min plant fertility** (default 7). Mobile organisms can go anywhere.
- **Soil heals slowly.** Each tick, every unoccupied cell below its cap has a **Soil regen chance** (a percent per
  tick) of gaining **Soil regen amount** fertility. Infertile pathways never recover.
- Burrowing is the only thing that lowers fertility (see below).

### Predator and prey roles: tags and altered brains
- **Tagging.** Every organism carries a role: **plant** (producer, no mover), **predator** (killer cell, no producer)
  or **prey** (everything else). Roles are inherited. When a prey first gains a killer cell it flips a coin
  (**Prey killer becomes predator**, default 0.5) to become a predator or stay prey. A switch of role always founds a
  new species. The seeded species (`seeded species/*.json`: `predator`, `prey_small`, `prey_large`, `plant`) name
  their lineages, so descendants can be traced back.
- **Who eats what.** Predators cannot eat food and only kill prey. A kill gives one food unit per prey body cell.
  Dead predators and prey leave empty cells; dead plants still leave food. Predators live longer
  (**Predator Lifespan Multiplier**, default 2).
- **Altered brains** (`src/Organism/Perception/Brain.js`). Predators and prey no longer use the evolved
  cell-type decision maps:
  - Predators chase the nearest prey they can see (not hidden prey), and keep their heading three times longer once
    prey leave sight.
  - Prey retreat from the nearest predator they see, or **burrow** if they have a claw (see below). With no predator
    in sight they chase the nearest food.
  - Plants and untagged organisms keep the original evolvable brain.
- **Movement speed.** Predators move every **Predator Movement Interval** updates (default 3), clawed prey every
  **Burrower Movement Interval** updates (default 1), and prey take at most one step per update.

### Claw cells and burrowing
- A new body cell, the **claw** (`src/Organism/Cell/BodyCells/ClawCell.js`). No seeded organism has one; it can only
  appear by mutation. **Claw cells can evolve** switches it off for the no-claw control.
- **Burrowing.** A clawed prey that sees a predator digs underground for **hideDuration** ticks (100), as long as
  the soil under it has at least **minBurrowFertility** (1) on average. While hidden it is invisible to predators,
  doesn't move and, with **Don't age while hidden**, doesn't age. With **Stay hidden near predators** it stays down
  for up to another 100 ticks while a predator is within range. **Only burrow when predator is close** (off in our
  runs) makes it run from predators that are further away.
- **The cost.** Every burrow removes **hideFertilityCost** (10) fertility from each cell under the prey's body, down
  to 0. Setting it to 0 gives the free-burrowing control. **Claw cells are free** (off in our runs) makes claws
  cost nothing to reproduce.

### Logging
The Statistics tab can export everything as CSV (**All**, plus auto-save). The headless runner writes the same files.
Samples are taken every 100 ticks.
- `timeseries`: population, species, mutation rate, average cells, fitness, lifespan at death, growth, birth and
  death rates, burrowers and clawed organisms, hidden organisms and burrows, mean soil fertility
  (`soil_mean`) and the share of degraded soil (`soil_degraded_frac`), and the average count of each cell type.
- `groups_log`: the same measures per **role** (plants, predators, prey with and without a claw) and per
  **lineage**: population, births, deaths, fitness, lifespan at death, birth, death and growth rates, burrows, and
  counts with a claw, ever burrowed and hidden.
- `species_log` and `species_summary`: per-species series, and one row per species (life span, peak population,
  fitness, burrows, cell make-up).
- `key_moments`: events with their tick: the claw evolving, the first burrow, the last clawed organism dying,
  the soil losing 25, 50 and 75% of its fertility, species becoming established or extinct, total extinction, and
  settings changed mid-run.
- `run_config`: every setting of the run, the grid size, organisms placed and the fertile share of the soil.

Definitions:
- **Growth rate:** (births − deaths) / average population over the interval.
- **Fitness:** offspring per organism that died.

The Statistics tab also charts growth, fitness, lifespan and population by role or lineage, and burrows against soil
fertility.


# How to Run the Code

### In the browser
 - [Install node and npm](https://nodejs.org/en/download/)
 - Download or clone this repository
 - Open a terminal or PowerShell prompt, go to the repository and run `npm install`
 - Run `npm run build` (or `npm run build-watch` for a better developer experience)
   - If you get a `Can't resolve jquery` error message run `npm install --save jquery`
 - Open `dist/index.html` in your browser. The simulation should start running.
 - Set up a run in the **Run Setup** tab (see [Run Setup](#run-setup)), press **Apply & Reset World**, and export the
   logs from the Statistics tab.

To load custom creations (found in `/dist/assets`), you must have a simple web server that serves all files in the dist directory. One way to do this is with Python:
 - [Install python](https://www.python.org/downloads/)
 - run `python -m http.server --directory dist` from the repository root
 - Open `http://localhost:8000/` in your browser

### Our experiments
The final experiments are in `headless/experiments/`. They all start from the same seeded species, and claws start
absent:
- `final_runs.json`: 540 runs over 15 soil maps (3 layouts × 5 soil seeds), soil regen 1–10%, 3 replicates, three sets.
- `slow_regen_main.json`, `slow_regen_noclaw.json`, `slow_regen_nocost.json`: the same design at soil regen
  0.01–0.1% per tick, the results in our presentation.

The three sets are:
- **main:** claws can evolve and burrowing costs soil.
- **noclaw:** claws can never evolve.
- **nocost:** burrowing is free.

Run them with `node headless/batch.js headless/experiments/slow_regen_main.json` (no build needed; tested with Node 24).
Logs go to `Observations/` (not tracked by git). Runs are 250,000 ticks long, so a full set takes several hours.

The analysis scripts need Python 3 with `numpy`, `pandas`, `matplotlib` and `scipy`; the slide scripts also need
`pypdf` and `reportlab`:
- `analysis/plot_metrics.py`: per-run and averaged plots of any batch.
- `analysis/final_analysis.py`: extinction tables and figures for `final_runs`.
- `analysis/slow_regen_analysis.py Observations/slow-regen-runs`: the slow-regen report (extinctions, soil,
  collapse pathways, growth and fitness, claw outcomes).
- `analysis/slow_regen_deck.py`, `analysis/growth_rate_slide.py`: figures and slides for the presentation.

### Headless runs
The simulation can run without a browser, which is much faster and lets several runs go at once. It uses the same code in `src/`, leaving out only the drawing, and writes the same CSV logs as the Statistics tab's **All** export, so `analysis/plot_metrics.py` reads them unchanged. Only the starting layout is seeded; each run is still random, as in the browser.

- **One run:** `node headless/run.js --out Observations/my-run --ticks 50000 --set placementSeed=2 --set predatorMoveInterval=1`. Any Run Setup key (`src/EnvironmentParams.js`), Evolution Controls name (`src/Hyperparameters.js`) or `speciesThreshold` can be set with `--set`. Anything not set uses its default. The run stops at the tick limit or when everything dies. It saves its logs every 25,000 ticks and when you press Ctrl-C.
- **A batch of runs:** describe the configurations to test in an experiment file, then run `node headless/batch.js headless/experiments/claw_soil_predator.json`. It runs every configuration once per placement seed, several at a time (CPU cores - 1 by default, change with `--jobs N`). Each run goes to `Observations/<experiment name>/<label>_seed<N>/`. Add `--dry-run` to list the runs first, or `--only label1,label2` to run some configurations. Running the same command again skips finished runs, so a stopped batch carries on where it left off. A configuration can set values (`"set"`) or try several (`"vary"`, one configuration per value or combination). Setting names are checked before anything runs, so a typo stops the batch straight away. See the top of `headless/batch.js` for the file format.
- **Plotting a batch:** `python analysis/plot_metrics.py Observations/<experiment name>` plots every run and compares them, and averages the replicates in `averages/`. For a batch that runs every configuration under several settings (a top-level `"vary"`, like `headless/experiments/soil_layouts.json`), add `--split` with those settings, e.g. `--split soilPatchThreshold,soilPatchResolution`. The configurations are then compared separately for each combination, and `averages/heatmaps.png` shows every configuration against every combination.
- **Different soil per replicate:** `"soilSeeds"` in an experiment file gives each placement seed its own soil seed (paired in order), so replicates also differ in their soil layout. `"replicates": N` runs each seed (or seed pair) N times, in `_rep<N>` folders, for replicates that share a starting layout and differ only in the run itself.

The grid defaults to 384 x 193 cells with cell size 5. This is the size the browser gives on a 1920 x 1080 screen with Fill Window on, so the same soil seed gives the same layout as those browser runs. Change it with `"grid"` in the experiment file.

### Npm build commands
- Production mode (minified): `npm run build`
- Watch mode (dev mode that auto-builds when you save a file): `npm run build-watch`
- Dev mode (better error messages): `npm run build-dev` 


# File Structure
Run logs (`Observations/`), analysis results (`results/`) and presentation files are git-ignored, so they are not
listed here.

```
LifeEngine/
├── src/                          simulation code, shared by the browser and the headless runner
│   ├── index.js, Engine.js       entry point and main loop
│   ├── EnvironmentParams.js      Run Setup settings (soil, seeded organisms, claw switches); defaults = final runs
│   ├── Hyperparameters.js        Evolution Controls (lifespans, mutation, movement intervals, burrow cost)
│   ├── WorldConfig.js            world options (headless flag, auto reset, brush size)
│   ├── Environments/             WorldEnvironment (soil, regeneration, placing seeded organisms), organism editor
│   ├── Grid/                     GridMap (cells and fertility), SoilLayout (seeded soil patches), Neighbors
│   ├── Organism/
│   │   ├── Organism.js           roles and tagging, reproduction, burrowing and hiding, movement
│   │   ├── Anatomy.js, RandomOrganismGenerator.js   bodies, and loading the seeded species
│   │   ├── Cell/                 cell states, grid cells (fertility), body cells incl. ClawCell.js
│   │   └── Perception/           Brain.js (predator chase, prey retreat or burrow), observations
│   ├── Stats/                    FossilRecord (species, logging, CSV export), StatsPanel and Charts/
│   ├── Controllers/              UI controls, including the Run Setup tab
│   ├── Rendering/                drawing, plus NullRenderer for headless runs
│   └── Utils/                    Perlin and seeded Perlin noise, save helpers
├── dist/                         browser app (index.html, css, img, assets); npm run build writes js/bundle.js here
├── headless/                     headless runner
│   ├── run.js                    one run, writes the CSV logs
│   ├── batch.js                  a batch of runs from an experiment file, in parallel
│   ├── settings.js               applies settings, checks their names, default grid
│   └── experiments/              experiment files: final_runs, slow_regen_{main,noclaw,nocost}, earlier tests
├── seeded species/               the starting organisms: predator, prey_small, prey_large, plant
├── experiment params/            slow_regen_parameters.json: every parameter of the final runs
├── analysis/                     Python analysis and plotting
│   ├── plot_metrics.py           per-run and averaged plots of any batch
│   ├── dynamics_load.py, dynamics_analysis.py   loading runs, growth, fitness, collapse pathways
│   ├── final_analysis.py         analysis of the 1–10% regen runs
│   ├── slow_regen_analysis.py    analysis of the final (slow-regen) runs
│   ├── slow_regen_deck.py, growth_rate_slide.py, slow_regen_presentation.py   presentation figures and slides
│   ├── claw_evolution.py         claw spread over time
│   └── headless/                 earlier JSON-based runner and parameter sweeps (evolutionary suicide, hiding, predators)
├── docs/metrics/                 screenshots of the Statistics tab
├── Changelog.md, LICENSE         from the original Life Engine
└── package.json, webpack.config.js   npm and build setup
```


# How the Simulation Works
## The Environment
The environment is a simple grid system made up of cells, which at every tick have a certain type. The environment is populated by organisms, which are structures of multiple cells.

## Cells
A cell can be one of the following types.
### Independent Cells
Independent cells are not part of organisms. 
- Empty - Dark blue, inert.
- Food - Grayish-blue, provides nourishment for organisms.
- Wall - Gray, blocks organisms movement and reproduction.
### Organism Cells
Organism Cells are only found in organisms, and cannot exist on their own in the grid.
- Mouth - Orange, eats food in directly adjacent cells.
- Producer - Green, randomly generates food in directly adjacent empty cells.
- Mover - Light blue, allows the organism to move and rotate randomly.
- Killer - Red, harms organisms in directly adjacent cells (besides itself).
- Armor - Purple, negates the effects of killer cells.
- Eye - Light purple with a slit, allows the organism to see and move intelligently. See further description below.

## Organisms
Organisms are structures of cells that eat food, reproduce, and die.
When an organism dies, every cell in the grid that was occupied by a cell in its body will be changed to food.
Their lifespan is calculated by multiplying the number of cells they have by the hyperparameter `Lifespan Multiplier`. Predators additionally multiply that lifespan by the `Predator Lifespan Multiplier` hyperparameter, which defaults to 2; other organisms survive for the calculated number of ticks unless killed by another organism.
When touched by a killer cell, an organism will take damage. Once it has taken as much damage as it has cells in its body, it will die. If the hyperparameter `One touch kill` is on, an organism will immediatly die when touched by a killer cell.
Predators cannot eat food or kill non-prey organisms. Killing prey gives a predator one food unit per prey body cell, matching the food yield of eating food from a plant of the same size. Predators move according to the `Predator Movement Interval` hyperparameter (default 3 updates), chase prey they see through their normal directional eyes, and keep their heading longer after prey leave sight. Prey take at most one movement step per update, chase visible food when no predator is nearby, and retreat from visible predators or hide if they can burrow. Burrowing prey move according to the `Burrower Movement Interval` hyperparameter (default 1, every update).
Organisms with a killer cell and no producer cell are tagged as predators. When a prey, with or without a claw, first develops a killer cell, it has a 50% chance to become a predator and a 50% chance to remain prey (the `Prey killer becomes predator` chance in Run Setup). Its offspring keep whichever role it ended up with. Every other organism that is not a plant (a producer that cannot move) is tagged as prey, so organisms that evolve to move, or predators that lose their killer cells, can be hunted. An offspring that switches between predator and non-predator always founds a new species, whatever its body.

## Run Setup
Each run's starting configuration (the soil layout and the seeded organisms), plus mechanics that can be isolated between runs, are in `src/EnvironmentParams.js`. There are two ways to change them:

- **In the browser:** open the **Run Setup** tab. Change the values, then press **Apply & Reset World** to rebuild the soil and place the starting organisms. **Save & Download** writes the settings to a `.json` file, **Load** reads one back, and **Reset to defaults** restores the values below.
- **In the code:** edit the `default` of a setting in the `FIELDS` list in `src/EnvironmentParams.js`, then rebuild (`npm run build`). The Run Setup tab is generated from this list, so a setting added there also gets an input automatically.

Settings marked *reset* only take effect when the world resets, because the soil and the starting organisms are placed then. Settings marked *live* take effect immediately. If one is changed partway through a run, the change is logged as a key moment, since the run no longer matches its starting configuration.

| Setting | Default | Final runs | When | What it means |
|---|---|---|---|---|
| Run label | (empty) | `<set>-<layout>` | live | A name for the configuration. It is written to the logs and used in plot legends and for averaged results. |
| Soil seed | 42 | 42, 7, 123, 2024, 99 | reset | Fixes the soil layout. The same seed on the same grid size always gives the same layout. |
| Soil density (patch threshold) | 0 | -0.1 / 0 / 0.1 (dense / medium / sparse) | reset | The noise cutoff for fertile soil, from -1 to 1. Raise it for less, sparser fertile soil with wider infertile pathways; lower it for more, better connected fertile soil. 0 makes about half the grid fertile. |
| Soil patch size (resolution) | 20 | 10 / 20 / 40 (dense / medium / sparse) | reset | How many noise bumps are stretched across the grid. Lower values give fewer, bigger patches; higher values give many small, scattered ones. |
| Soil regen chance (%) | 0.05 | 0.01, 0.025, 0.05, 0.1 | live | The percent chance each tick that an unoccupied soil cell regains fertility, up to its cap. |
| Soil regen amount | 1 | 1 | live | How much fertility a soil cell regains each time it regenerates. |
| Min plant fertility | 7 | 7 | live | The average soil fertility needed under a plant (a producer that cannot move) for it to be born or placed there. |
| Placement seed | 1 | 1 (3 replicates each) | reset | Fixes where the starting organisms are placed. Change it to get replicates of the same configuration. |
| Predators | 10 | 10 | reset | How many seeded predators to place. |
| Prey (small) | 10 | 10 | reset | How many of the original burrowing prey, without the claw, to place (`seeded species/prey_small.json`). |
| Prey (large) | 10 | 10 | reset | How many of the larger prey to place (`seeded species/prey_large.json`). Neither seeded prey has a claw, so any claw has to evolve. |
| Plants | 39 | 39 | reset | How many seeded plants to place. Plants only go where the soil is fertile enough for them to grow. |
| Prey killer becomes predator (chance) | 0.5 | 0.5 | live | When a prey (with or without a claw) gains its first killer cell, the chance that it becomes a predator instead of staying prey. 0.5 is a coin flip. 1 turns the coin flip off, so prey with a killer cell always become predators. 0 keeps them prey. |
| Claw cells can evolve | on | on (off in noclaw) | live | Off removes claws from the cell types a mutation can add, so claws never evolve. This is the no-claw control. |
| Claw cells are free | off | off | live | On makes claw cells not count toward the food needed to reproduce. They still add lifespan and health, so claws could then spread even when they are never used for burrowing. |
| Don't age while hidden | on | on | live | Ticks spent underground don't count toward an organism's lifespan. |
| Stay hidden near predators | on | on | live | A hidden organism stays underground while a predator is within the stay hidden range, for up to another hide duration. |
| Stay hidden range | 6 | 6 | live | How close (in cells) a predator has to be to keep a hidden organism underground. |
| Only burrow when predator is close | off | off | live | On makes prey with a claw only burrow when the predator they see is within the burrow trigger range, and run when it is further away. Off, they burrow whenever they see a predator. |
| Burrow trigger range | 8 | 8 (unused) | live | How close (in cells) a seen predator has to be before prey with a claw burrow, when the setting above is on. |

The defaults are the main set of our final runs (`headless/experiments/slow_regen_main.json`) on the medium layout, so
**Reset to defaults** gives one of those runs. The **Final runs** column shows the values those runs used; where it
lists several, every combination was run. The noclaw set turns **Claw cells can evolve** off, and the nocost set sets
the Evolution Control **hideFertilityCost** to 0. The other Evolution Controls the runs depend on are also at their
defaults:
- **Predator Lifespan Multiplier:** 2.
- **Predator Movement Interval:** 3.
- **Burrower Movement Interval:** 1.
- **hideDuration:** 100.
- **hideFertilityCost:** 10.
- **minBurrowFertility:** 1.

The grid is 384 × 193 cells with cell size 5, and each run is 250,000 ticks. The full parameter list is in
`experiment params/slow_regen_parameters.json`.

The starting organisms are placed at seeded random free spots, in this order: predators, small prey, large prey, then plants. The seeded species are named after their files in `seeded species/` (`predator`, `prey_small`, `prey_large`, `plant`), and their descendants carry that name as their lineage. If the grid is too crowded, fewer may be placed than asked for; the run config records how many were actually placed. Only the starting layout is seeded. The simulation itself still varies from run to run, so repeating a configuration with different placement seeds gives independent replicates.

**Reproducing a layout:** the soil pattern is stretched over the grid, so the same seeds on a different grid size give a different layout. To reproduce a layout exactly, turn off **Fill Window** in World Controls and fix the columns, rows and cell size.

**Logs and plots:** the **Run Config** export (`run_config` CSV, also included in **All** and in auto-save) records every setting above, the grid size, how many organisms of each role were placed, the fraction of fertile soil, the species threshold and all the Evolution Controls (prefixed `hp_`). `analysis/plot_metrics.py` uses it to label runs and list each run's settings in `run_configs.csv`. It treats runs whose settings match apart from the soil seed, placement seed and run label as replicates, and averages them in `averages/`.

## Reproduction
Once an organism has collected 1.5 times its normal reproduction food requirement (its cell count, plus any extra mover cost), it will attempt to reproduce.
First, offspring is formed by cloning the current organism and possibly mutating it (see below).
The offspring birth location is then chosen a certain number of cells in a random direction (up, down, left, right). This number is calculated programmatically such that it is far enough away that it can't intersect with it's parent.
Additionally, a random value between 1 and 3 is added to the location to introduce a little variance.
Reproduction can fail if the offspring attempts to occupy non-empty cells, like other organisms and food. If reproduction fails, the food required to produce a child is wasted.

## Mutation
Offspring can mutate their anatomies in 3 different ways: change a cell, lose a cell, or add a cell. Changing a cell sets a random cell to a random type. Losing a cell removes a random cell. Note that this can result in organisms with "gaps" and cells disconnected from the rest of its body. I consider this a feature, not a bug.
To add a cell the organism first selects a cell it already has in its body, then grows a new cell with a random type in a location adjacent to the selected cell.

If an organism mutates, there is a 10% chance that mutation will alter the movement patterns of the organism (see below).

## Movement and Rotation
Organisms with mover cells (light blue) are permitted to move freely about the grid. Only a single mover cell is required and adding more doesn't do anything. By default, an organism selects a random direction and moves one cell per tick in that direction for a certain number of ticks. This number is called "Move range", and it can mutate over time.

Organims can also rotate around a central pivot cell. This cell can never be removed by mutation, though it can change type. Movers rotate randomly when they change direction, and their rotation is not necessarily the same as their movement direction, ie, they aren't always facing the direction they are moving. Offspring of all organisms (including static ones) rotate randomly during reproduction. This rotation can be toggled in the simulation controls.

## Eyes and Brains
Any organism can evolve eyes, but when an organism has both eyes and mover cells it is given a brain. The eye, unlike other cells, has a direction, which is denoted by the direction of the slit in the cell. It "looks" forward in this direction and "sees" the first non-empty cell within a certain range. It checks the type of the cell and informs the brain, which then decideds how to move. The brain can either ignore (keep moving in whatever direction), chase (move towards the observed cell), or retreat (move in the opposite direction of the observed cell). The brain maps different observed cell types to different actions. For instance, the brain will chase when it sees food and retreat when it sees a killer cell. These behaviors can mutate over time. 
