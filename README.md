This is the readme for my evolution simulator, The Life Engine. 

For UCT Artificial Life Cource


# The Life Engine
[Play here!](https://thelifeengine.net/)

The life engine is a cellular automaton designed to simulate the long term processes of biological evolution. It allows organisms to eat, reproduce, mutate, and adapt.
Unlike genetic algorithms, the life engine does not manually select the most "fit" organism for some given task, but rather allows true natural selection to 
run its course. Organisms that survive, successfully produce offspring, and out-compete their neighbors naturally propogate througout the environment.

This is the second version of the [original evolution simulator](https://github.com/MaxRobinsonTheGreat/EvolutionSimulator), which I started in high school.


# How to Run and Modify the Code
 - [Install node and npm](https://nodejs.org/en/download/)
 - Download or clone this repository
 - Open a terminal or powershell comand prompt, go to the repository and run `npm install`
 - Run `npm run build` (or `npm run build-watch` for a better developer experience)
   - If you get a `Can't resolve jquery` error message run `npm install --save jquery`
 - Open `dist/index.html` in your browser. The simulation should start running.

To load custom creations (found in `/dist/assets`), you must have a simple web server that serves all files in the dist directory. I do this with python:
 - [Install python](https://www.python.org/downloads/)
 - run `python -m http.server --directory dist` from the repository root
 - Open `http://localhost:8000/` in your browser

### Npm build commands
- Production mode (minified): `npm run build`
- Watch mode (dev mode that auto-builds when you save a file): `npm run build-watch`
- Dev mode (better error messages): `npm run build-dev` 


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
Predators cannot eat food or kill non-prey organisms. Killing prey gives a predator one food unit per prey body cell, matching the food yield of eating food from a plant of the same size. Predators move according to the `Predator Movement Interval` hyperparameter (default 3 updates), chase prey they see through their normal directional eyes, and keep their heading longer after prey leave sight. Prey take at most one movement step per update, chase visible food when no predator is nearby, and retreat from visible predators or hide if they can burrow. Burrowing prey move according to the `Burrower Movement Interval` hyperparameter (default 3 updates).
Organisms with a killer cell and no producer cell are tagged as predators. When a clawed organism first develops a killer cell, it has a 50% chance to become a predator and a 50% chance to remain prey (the `Clawed killer becomes predator` chance in Run Setup). Every other organism that is not a plant (a producer that cannot move) is tagged as prey, so organisms that evolve to move, or predators that lose their killer cells, can be hunted. An offspring that switches between predator and non-predator always founds a new species, whatever its body.

## Run Setup
Each run's starting configuration (the soil layout and the seeded organisms), plus mechanics that can be isolated between runs, are in `src/EnvironmentParams.js`. There are two ways to change them:

- **In the browser:** open the **Run Setup** tab. Change the values, then press **Apply & Reset World** to rebuild the soil and place the starting organisms. **Save & Download** writes the settings to a `.json` file, **Load** reads one back, and **Reset to defaults** restores the values below.
- **In the code:** edit the `default` of a setting in the `FIELDS` list in `src/EnvironmentParams.js`, then rebuild (`npm run build`). The Run Setup tab is generated from this list, so a setting added there also gets an input automatically.

Settings marked *reset* only take effect when the world resets, because the soil and the starting organisms are placed then. Settings marked *live* take effect immediately. If one is changed partway through a run, the change is logged as a key moment, since the run no longer matches its starting configuration.

| Setting | Default | When | What it means |
|---|---|---|---|
| Run label | (empty) | live | A name for the configuration. It is written to the logs and used in plot legends and for averaged results. |
| Soil seed | 42 | reset | Fixes the soil layout. The same seed on the same grid size always gives the same layout. |
| Soil density (patch threshold) | 0 | reset | The noise cutoff for fertile soil, from -1 to 1. Raise it for less, sparser fertile soil with wider infertile pathways; lower it for more, better connected fertile soil. 0 makes about half the grid fertile. |
| Soil patch size (resolution) | 20 | reset | How many noise bumps are stretched across the grid. Lower values give fewer, bigger patches; higher values give many small, scattered ones. |
| Soil regen chance (%) | 0.05 | live | The percent chance each tick that an unoccupied soil cell regains fertility, up to its cap. |
| Soil regen amount | 1 | live | How much fertility a soil cell regains each time it regenerates. |
| Min plant fertility | 7 | live | The average soil fertility needed under a plant (a producer that cannot move) for it to be born or placed there. |
| Placement seed | 1 | reset | Fixes where the starting organisms are placed. Change it to get replicates of the same configuration. |
| Predators | 10 | reset | How many seeded predators to place. |
| Prey (no claw) | 10 | reset | How many seeded prey without a claw to place. |
| Prey (with claw) | 10 | reset | How many seeded burrowing prey to place. |
| Plants | 39 | reset | How many seeded plants to place. Plants only go where the soil is fertile enough for them to grow. |
| Clawed killer becomes predator (chance) | 0.5 | live | When a clawed organism gains its first killer cell, the chance that it becomes a predator instead of staying prey. 0.5 is a coin flip. 1 turns the coin flip off, so clawed organisms become predators like any other organism. 0 keeps them prey. |
| Claw cells are free | on | live | Claw cells don't count toward the food needed to reproduce. They still add lifespan and health, so claws can spread even when they are never used for burrowing. |
| Don't age while hidden | on | live | Ticks spent underground don't count toward an organism's lifespan. |
| Stay hidden near predators | on | live | A hidden organism stays underground while a predator is within the stay hidden range, for up to another hide duration. |
| Stay hidden range | 6 | live | How close (in cells) a predator has to be to keep a hidden organism underground. |
| Only burrow when predator is close | on | live | Prey with a claw only burrow when the predator they see is within the burrow trigger range. Further away, they run instead. |
| Burrow trigger range | 8 | live | How close (in cells) a seen predator has to be before prey with a claw burrow. |

The starting organisms are placed at seeded random free spots, in this order: predators, clawed prey, prey, then plants. If the grid is too crowded, fewer may be placed than asked for; the run config records how many were actually placed. Only the starting layout is seeded. The simulation itself still varies from run to run, so repeating a configuration with different placement seeds gives independent replicates.

**Reproducing a layout:** the soil pattern is stretched over the grid, so the same seeds on a different grid size give a different layout. To reproduce a layout exactly, turn off **Fill Window** in World Controls and fix the columns, rows and cell size.

**Logs and plots:** the **Run Config** export (`run_config` CSV, also included in **All** and in auto-save) records every setting above, the grid size, how many organisms of each role were placed, the fraction of fertile soil and all the Evolution Controls (prefixed `hp_`). `analysis/plot_metrics.py` uses it to label runs and list each run's settings in `run_configs.csv`. It treats runs whose settings match apart from the soil seed, placement seed and run label as replicates, and averages them in `averages/`.

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
