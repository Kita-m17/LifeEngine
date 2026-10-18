# LifeEngine: findings to date

*Burrowing prey, claw cells, predators and soil. Summary of everything up to 18 October 2026, branch `observations-josh`.*

This document gathers the results of five browser runs and four headless batches on this branch (380 headless runs), the group's reports, and Jenna's `run_config_tick4452` study, with the nuances behind them. The detailed reports are alongside it in `Findings/`:

- `findings_summary.pdf`: browser runs and the first two batches
- `claw_evolution.pdf`: whether the claw evolves on its own
- the group's reports: `Burrowing_Into_Extinction.pdf` (Tarique), `Findings soil study (evolved burrowers).pdf` (Nik), `jenna-testing_burrowing_report.pdf` (Jenna), `config_tick4452_report.pdf` (Jenna, run_config_tick4452)

---

## 1. Main findings

1. **The claw evolves on its own, and spreads because burrowing helps.** It arises by mutation in every run, within about 1,000 ticks.
   - Starting with no claws, claws took over in 7 of 10 runs with burrowing and 1 of 10 without when claws cost food (p = 0.02).
   - When claws are free, they took over in 10 of 10 runs with burrowing and 2 of 10 without (p = 0.0007).
   - Without burrowing, claws stay on 1–2% of prey.
2. **The early plant crash decides whether a world survives, and soil decides whether plants get through it.**
   - The early crash follows the first predator boom.
   - Faster soil regrowth, denser soil and bigger fertile patches all improve survival.
   - On sparse soil with small patches, every run died out (0 of 30).
3. **Free claws are a loophole that predators exploit.**
   - Claw cells lower the food needed to reproduce while still adding lifespan and health.
   - About 90% of predators carry claws they never use.
   - Minimal, eyeless clawed predators can take over a world.
4. **Most extinctions are ecological, not evolutionary.**
   - Early collapses (before tick 30k) are overshoot by the seeded predators.
   - Some later collapses follow a newly evolved predator that spreads and then wipes out its prey. That pattern looks like evolutionary suicide but isn't proven.
5. **Evolutionary suicide through the soil is real, but its rate depends heavily on the settings.**
   - The clearest result is Jenna's `run_config_tick4452`. Claws evolved, took over, and then every prey died in **18 of 20 runs with soil cost 10, against 0 of 20 with harmless burrowing** (p = 3.4 × 10⁻⁹).
   - The key setting there is **minimum plant fertility 10**: plants need untouched soil, so a single burrow ruins a patch for about 100,000 ticks.
   - With this branch's defaults it is rare (2 of 20 evolved take-overs). Tarique found 21 of 40 and Nik 11 of 11 burrower take-overs, both with *Only burrow when predator is close* off.
6. **Each study changed several settings at once, often on different code, so the studies can't be compared directly.** Section 10 sets out which effects hold everywhere and which are confounded, and suggests a basis for the final runs.

---

## 2. How the simulation was changed along the way

Several results depend on these changes, so they are worth knowing when comparing with older runs or other branches.

| Change | What it does | Why it matters |
|---|---|---|
| **Tagging** | An organism is a predator if it has a killer cell and no producer. It is prey if it is neither a predator nor a plant (a plant is a producer that can't move). | Before this, evolved predators weren't tagged, so prey didn't flee them, and moving organisms from the plant lineage couldn't be eaten. |
| **Coin flip** (`clawPredatorChance`, 0.5) | A clawed organism that gains a killer cell becomes a predator with this chance. Other organisms always do. | This is how clawed prey turn into predators. Tarique's branch uses 1. |
| **Species include role** | An offspring that switches between predator and non-predator founds a new species. | Species were otherwise defined only by body (3 or more cells different from the founder). |
| **Claw tracking** | The per-role logs count organisms with claws, those that have ever burrowed, and those underground. | Separates claws that are used from claws that are only carried. |
| **Run Setup** (`src/EnvironmentParams.js`) | Seeded soil and placement, organism counts, soil regrowth, minimum plant fertility, the coin flip and the claw benefits, all logged in each run's `run_config`. | Lets runs be compared and averaged. Only the **starting layout** is seeded; each run is still random after that. |
| **Headless runner** (`headless/run.js`, `headless/batch.js`) | Runs the same `src/` code without drawing, several at a time. Experiment files describe the configurations and seeds. | A 30-run batch takes about 15 minutes, and 270 runs about 2½ hours. |
| **Bug fix** | Resizing the grid with Fill Window off didn't update the world's column and row counts. | Soil, placement and the logged grid size used the old size. |
| **Plotting** (`analysis/plot_metrics.py`, `analysis/claw_evolution.py`) | Per-run plots, replicate averages for every metric, a `--split` option for heatmaps across settings, and claws split into evolved and seeded. | |

**The three claw benefits** (all on by default here; together called "claws free" below unless stated otherwise):
- Claw cells don't count toward the food needed to reproduce.
- Organisms don't age while hidden.
- Hidden organisms stay down while a predator is near.

**Grid:** 384 × 193 cells, cell size 5. This is the browser's size on a 1920 × 1080 screen with Fill Window on, so the same soil seed gives the same layout in the browser and headless.

---

## 3. Browser runs (single runs)

### Before and after the tagging fix (`min burrow fertility 1`, `fixed tagging run`)
- **Before the fix:** evolved predators weren't recognised as predators, so prey didn't flee them, and moving organisms from the plant lineage couldn't be eaten. Predators starved, and prey were then killed by killers they didn't treat as predators.
- **After the fix:** the population plots looked more normal, but claw cells were common even in organisms that never burrowed. This led to tracking claw use by role.

### Claw tracking (`claw tracking`)
- Burrowing prey were the main prey for about 65k ticks, and were still burrowing when they crashed at about 67–70k and 148–150k.
- The predators that overexploited them came from **the burrowing prey's own lineage**, via the coin flip.
- Most predators and many plants carried claws they never used.

### Claws costing food (`claw dies out (not free)`)
- The 10 seeded predators boomed to about 270 by tick 4,000. All prey crashed: prey without claws fell by about 90%, and burrowing prey died out.
- Burrowing prey bred at about half the rate of other prey: the claw costs food, they can't eat underground, and they age while hidden. They peaked at 62 against about 400, so they had nothing left to recover from.
- **Not evolutionary suicide:** a predator boom overran every prey type, and the smallest, slowest-breeding group didn't come back.

### Claws free (`claws free`)
- Burrowing prey were the main prey from about 20k to 110k ticks, with 35–70% of them having burrowed.
- Every dominant predator came from the clawed-prey lineage. From about 80k ticks, 80–97% of predators carried claws, and **none ever burrowed**.
- **The eyeless clawed predator:** a mover, a killer and 3 claws, with no eye and no mouth.
  - With free claws it pays food for only 2 cells: 4 food, against 11 for the seeded predator.
  - Every cell, claws included, counts toward lifespan (5 × 150 × 3 = 2,250 ticks) and health.
  - Mouths are useless to predators, which only eat by killing, and eyes cost food.
  - So a cheap random walker that breeds about 3× as often beats a hunter.
- Plants nearly died out around 16k ticks (down to 35). The batches later showed this is the usual early crash.

---

## 4. Batch 1: one soil layout, six configurations (`Observations/claw-soil-predator`, 30 runs)

**Setup:**
- 6 configurations × 5 placement seeds, on one soil layout (seed 42, density 0, resolution 20, 55% fertile);
- up to 250k ticks;
- 10 predators, 10 prey, 10 clawed prey and 39 plants;
- predator lifespan multiplier 3.

| Config | Change from baseline | Lasted 250k | Burrowing prey* | Prey without claws* | Predators* | Plants* |
|---|---|---|---|---|---|---|
| soil-fast | soil regrowth 0.2% | **5/5** | **132** | 6 | 160 | 527 |
| baseline | claws free, regrowth 0.05%, predators move every 3 ticks | 3/5 | 78 | 4 | 185 | 331 |
| claw-off | all three claw benefits off | 3/5 | **2** | **98** | 87 | **786** |
| pred-2 | predators move every 2 ticks | 3/5 | 54 | 9 | 61 | 334 |
| pred-1 | predators move every tick | 3/5 | 20 | 26 | 41 | 330 |
| soil-slow | soil regrowth 0.01% | **0/5** | 47 | 1 | 21 | 173 |

\* Means over ticks 100k–250k, for runs still going (soil-slow: one run).

**Findings:**
- **How worlds die early:**
  1. Predators wipe out the first prey boom by about tick 4k.
  2. Uneaten food piles up (about 1k → 5k cells) and blocks plant offspring from being placed.
  3. Burrowing wears down about 20% of the fertile soil, which takes about 14k ticks to recover at the default rate.
- **The seeded predators died out in every run,** between 7k and 87k ticks. With claws free, 94% of later predators came from the clawed-prey lineage; with claw-off, about half did.
- **Free claws pile up** (about 1.6 claw cells per organism in baseline, about 0 in claw-off), and bodies grow (6.2 cells against 4.7).
- **Eyeless clawed predators came back on their own** in 3 runs (82–98% of predators), never with claw-off.
- **Faster predators end up scarcer:** pred-1 had the fewest predators, the highest mutation rate (12.7% against 8–9%) and the most variation between runs.

---

## 5. Batch 2: nine soil layouts (`Observations/soil-layouts`, 270 runs)

**Setup:**
- the same 6 configurations, each on 3 soil densities × 3 patch sizes;
- densities (threshold −0.1, 0, 0.1) give about 68%, 50% and 33% fertile soil;
- patch sizes (resolution 10, 20, 40) run from big to small patches;
- 5 replicates, each with its own placement seed **and** soil seed.

**Survival (runs lasting 250k), all configurations, out of 30:**

| Density ↓ / patch resolution → | 10 (big) | 20 | 40 (small) | Total |
|---|---|---|---|---|
| −0.1 (~68% fertile) | 24 | 24 | 20 | 68/90 |
| 0 (~50%) | 18 | 15 | 5 | 38/90 |
| 0.1 (~33%) | 12 | 5 | **0** | 17/90 |

**By configuration (out of 45):** soil-fast 35, claw-off 23, pred-2 23, baseline 21, pred-1 15, soil-slow 6.

**Findings:**
- **Density matters most, and small, scattered patches make it worse.** On sparse soil, big patches still keep some runs alive, probably because large connected fertile areas let plants survive the early crash.
- **The layout itself matters too.** Soil seed 123 survived 18 of 54 runs, against 24–28 for the other seeds. Patch resolution 10 varies a lot from seed to seed (44–76% fertile at density 0).
- **Fast soil regrowth helps most,** but fails on sparse soil with small patches.
- **The claw findings hold on every layout.** With claw-off, burrowing prey are about 0 and plants do best. With claws free, the number of burrowing prey rises with soil fertility.
- **Predators keep claws on every layout:** 86–93% of predators carry claws late in the runs with free claws, against 11% with claw-off.
- **Claw-off survives better on dense soil with small patches** (5/5 against 2/5 for baseline). Burrowing damage probably hurts more when fertile patches are small.
- **pred-1 changes the batch 1 conclusion.** On one layout it survived as often as baseline; across layouts it does worst apart from soil-slow, even on dense soil (8/15).

---

## 6. Extinctions and evolutionary suicide (160 whole-world extinctions)

### How worlds die
- **Plants usually die last:** in 101 of the 160 extinctions, plants outlived every animal by a median 2,700 ticks.
- **Food blocking is the cause,** confirmed with plants-only worlds:
  - with `foodBlocksReproduction` on, 2 of 3 died (at 30k and 47k ticks) and the third kept about 220 plants;
  - with it off, all three thrived with about 2,000 plants.
  - With nothing eating the food, it fills the space plants need for offspring.
- **So plant deaths are a knock-on effect.** What decides whether a world dies is the animal collapse before it.

### Three kinds of collapse
| Phase | Runs | What happens | Evolutionary suicide? |
|---|---|---|---|
| Early (before 30k) | 88 | The **seeded** predators boom and wipe out the first prey boom. They make up 82% of predators when the prey die out. | No: ecological overshoot before evolution matters |
| Predators die first | 11 | Mostly soil-slow and pred-1: predators starve, then prey starve on a shrinking food supply. | No: limited resources |
| Mid and late (30k and later) | 35 | **Evolved** predators wipe out the prey. Seeded predators make up 15% of predators in mid-phase collapses and 0% in late ones; predators come from the clawed-prey lineage (40–53%) and from plants (20–40%). | Possibly |

### Cases that point to evolutionary suicide
- **A new predator spreads, then everything collapses.** In about 10 of 22 late collapses, a predator species evolves, peaks, and the world dies within a few thousand ticks. For example, in a pred-1 run a predator evolved from plants at 224.9k ticks, peaked at 237.5k, and prey went extinct at 240.2k.
- **A lineage evolves the predator that ends it.** In 9 of 22 late collapses, the final predator came from the clawed-prey lineage itself, as in the browser `claw tracking` run.
- **A weaker hint: burrowing wearing down shared soil.** Claw-off survives better on dense soil with small patches, but across all layouts claw-off and baseline survive at about the same rate (23 and 21 of 45).

### Not evolutionary suicide
- Burrowing prey disappearing when claws cost food: selection against a costly trait.
- Seeded predators always dying out: they were replaced by evolved ones.
- Eyeless predators: they took over some worlds, but those worlds survived.

**Not proven:** new predator species appear all the time, including in worlds that survive. Proving suicide needs replays:
1. save the world before the mutant evolves;
2. rerun it many times with and without that species;
3. compare how often each version dies out.

The headless runner can't load a saved world yet.

---

## 7. Batch 3: does the claw evolve? (`Observations/claw-evolution`, 80 runs)

**Setup:**
- 8 configurations, every combination of:
  - **start:** seeded (10 prey + 10 clawed) or evolved (20 prey, no claws);
  - **claws:** free or costing food;
  - **burrowing:** working or impossible (`minBurrowFertility` 11, above the maximum fertility of 10).
- 10 runs each, every run with its own placement and soil seed, 150k ticks.
- **Predator lifespan multiplier 2**, following Tarique's report, so prey survive the early wave.
- Other claw benefits on; *Only burrow when predator is close* on.

| Configuration | Claws took over | Prey with a claw, late (median) | Lowest soil (median, % of start) | All prey died after take-over | World lasted |
|---|---|---|---|---|---|
| **evolved, cost, burrow** | **7/10** | 17% | 86% | 0 | 10/10 |
| evolved, cost, no burrow | 1/10 | 1% | 100% | 0 | 10/10 |
| **evolved, free, burrow** | **10/10** | **94%** | 73% | 2 | 8/10 |
| evolved, free, no burrow | 2/10 | 2% | 100% | 0 | 10/10 |
| seeded, cost, burrow | 9/10 | 38% seeded + 1% evolved | 75% | 1 | 9/10 |
| seeded, cost, no burrow | 2/10 | ~0% | 100% | 0 | 10/10 |
| seeded, free, burrow | 10/10 | 90% seeded + 2% evolved | 74% | 2 | 8/10 |
| seeded, free, no burrow | 8/10 | ~0% | 100% | 1 | 8/10 |

**Findings:**
- **Claws arise by mutation in all 80 runs,** within a median 750–2,050 ticks. Nik found about 1,200.
- **They spread because burrowing helps:** p = 0.02 when claws cost food and p = 0.0007 when they're free, comparing burrowing against no burrowing from no claws.
- **Free claws don't spread among prey on their own.** Even seeded free claws fade to about 0% of prey by about 30k ticks without burrowing. Prey behave differently from predators and plants, which keep free claws.
- **Free claws make burrowing claws spread much further** (94% against 17% of prey). Claws costing food are the cleaner test.
- **Burrowing damages the soil** (lowest 73% of start with free evolved claws) and lowers plants (a median low of 134 against 450 without burrowing).
- **Collapses after a take-over are rare:** 2 of 10 with free evolved claws, 0 when claws cost food.

---

## 8. The strongest result so far: Jenna's `run_config_tick4452` (40 runs)

**Setup** (`config_tick4452_report.pdf`, branch `jenna-testing`, commit b9cb8bd):
- Every setting comes from a browser export, `run_config_tick4452.csv`, on a 306 × 140 grid (54.3% fertile, soil seed 42).
- 20 placement seeds × 2 setups, each run to 150,000 ticks. The two setups differ **only** in the soil cost per burrow: 10, or 0 (harmless).
- Settings:
  - **Starting organisms:** 10 predators, 20 prey, 0 clawed prey, 39 plants. Claws must evolve.
  - **Claw benefits:** claws free, don't age while hidden on, stay hidden near predators **off**.
  - **Burrowing:** only when a predator is close **off**; hide duration 200 ticks.
  - **Plants:** minimum plant fertility **10** (the maximum); plant regrowth 1%.
  - **Soil:** regrowth chance 0.01% per tick.
  - **Predators:** lifespan multiplier 3; clawed killer coin flip 0.5.
  - **Movement:** burrowers move every tick, predators every 3 ticks.

**Results:**

| | Soil cost 10 | Harmless (cost 0) |
|---|---|---|
| Claws took over at least once | 20/20 (median first tick 11,000) | 18/20 (median first tick 18,000) |
| **All prey died after a take-over** | **18/20** (median tick 33,500) | **0/20** |
| No prey at tick 150,000 | 7/20 | 0/20 (p = 0.008) |
| Nothing alive at tick 150,000 | 5/20 | 0/20 (p = 0.047) |

**How a collapse unfolds:**
1. Clawed prey peak within a few thousand ticks of taking over.
2. Fertile soil falls to a median 59% of its maximum. The share of fertile soil still good enough for plants falls to a median 54%.
3. Plants drop from about 500 to almost none within about 15,000 ticks (median low 3, against 372 with harmless burrowing).
4. Prey run out of food and die, a median 21,000 ticks after the take-over. Predators die out too, in 19 of 20 runs.

**Why the plants crash:**
- A burrow removes 10 fertility, which empties the cell.
- Plants need fertility 10 under every cell, so one burrow makes a patch unusable.
- At 0.01% regrowth, an empty cell takes about 100,000 ticks to recover.
- Prey burrow where they feed, among the plants.

**What every take-over led to:** with soil cost 10, claws took over 22 times. All 18 take-overs that started before tick 110,000 ended with every prey dead. The other 4 started too late to tell within 150,000 ticks.

**Plant regrowth lets the world come back, but doesn't prevent the collapse.**
- New plants keep appearing, and their descendants evolve into prey. In 9 runs a new, almost clawless prey population had grown back by the end. The 7 runs where a large prey population came back each had 8–13 separate die-outs first.
- Claws took over a second time in 2 runs.
- Recovery took 70,000–105,000 ticks, in line with how long the soil takes to recover.

**The control matters:** prey died out in 3 harmless runs, but always before claws took over. After a take-over, the food web only crashed when burrowing damaged the soil.

**Caveats:**
- One soil layout and one grid.
- This setup differs from Jenna's earlier `run_config_tick73074` sweep (4 of 20 collapses) in five ways at once: minimum plant fertility 10 instead of 7, stay hidden off, predator lifespan 3 instead of 2, burrowers moving every tick, and 150,000 ticks. The perfect-soil rule for plants is the likely driver, but that hasn't been tested on its own.

---

## 9. How this compares with the group's reports

The settings each study used, as far as the reports give them ("–" means not stated):

| Setting | This branch (Josh) | Tarique | Nik | Jenna, tick73074 run settings | Jenna, reference settings | **Jenna, tick4452** |
|---|---|---|---|---|---|---|
| Code branch | `observations-josh` | `tarique-testing` | – | `jenna-testing` | `jenna-testing` | `jenna-testing` (b9cb8bd) |
| Starting prey (plain + clawed) | 10 + 10 (batches 1–2); 20 + 0 or 10 + 10 (batch 3) | 20 + 0 | 20 + 0 | 10 + 10 | 20 + 0 | **20 + 0** |
| Claws free | yes (1–2); both (3) | no | no | yes | no | **yes** |
| Don't age while hidden | on | on | – | – | – | on |
| Stay hidden near predators (range) | on (6) | on (6) | range 8 | range 10 | range 6 | **off** |
| Only burrow when predator is close | **on** | off | off | off | off | **off** |
| Hide duration / soil cost per burrow | 100 / 10 | 100 / 10 | 50 / 5 | 200 / 10 | 100 / 10 | **200 / 10 vs 0** |
| Min plant fertility | 7 | 7 | 7 (5 and 9 swept) | 7 | – | **10** |
| Soil regrowth chance | 0.05% (0.01 / 0.2 tested) | 0.05% | 0.05% | 0.01% | 0.05% | **0.01%** |
| Plant regrowth | none | none | none | 1% | 1% (swept) | **1%** |
| Predator lifespan multiplier | 3 (1–2); 2 (3) | 2 | – | 2 | 2 | **3** |
| Clawed killer becomes predator | 0.5 | 1 | – | 0.5 | 1 | 0.5 |
| Burrower move interval | 1 | 1 | – | 2 | – | 1 |
| Grid / soil layouts | 384 × 193, many soil seeds | 288 × 180, seed 42 | 200 × 150, maps 42 and 1003 | 306 × 140, seed 42 | 288 × 180, seed 42 | 306 × 140, seed 42 |
| Run length | 150k–250k | 100k | 150k | 100k | 100k | 150k |
| All prey died after an evolved take-over | 2/20 (batch 3) | 21/40 | 11/11 take-overs | 4/20 | 0/20 (regrowth on) | **18/20** |

**The code differs too, not just the settings.** `jenna-testing` adds:
- plant regrowth;
- armoured starting predators;
- no claws on plants;
- dead organisms leaving no food;
- a right-facing second prey.

Jenna's earlier report found that "dead plants leave no food" alone changed collapses from 4 to 12 of 20. A result on one branch may therefore not carry over to another, even with the same settings.

**Where the reports agree:**
- Claws evolve quickly by mutation.
- They spread when burrowing works and not when it is disabled.
- Burrowing wears down the soil.
- The early predator wave is what most often stops anything else from happening (Nik: prey gone by a median 5,500 ticks in most runs).

**Where they differ, and why:**
- **Collapse rate after a take-over:** 21/40 (Tarique) against 0/10 here when claws cost food. *Only burrow when predator is close* is the most likely reason. With it on, prey run from distant predators instead of burrowing, so soil damage is milder (lowest 86% here against about 70%).
- **Plant regrowth rescues worlds, unless plants need perfect soil** (Jenna). With 1% regrowth and minimum plant fertility 7, no setup collapsed. With minimum plant fertility 10 (tick4452), 18 of 20 still collapsed, because regrowth only places plants on soil good enough for them, and burrowing removes that soil. Regrowth then rebuilt some worlds afterwards.
- **Blind clawed prey** (Nik): 11 of 12 clawed prey in one replay had lost their eye to the claw mutation, and blind prey never burrow. This probably limits how far claws spread, and may explain runs where claws spread but burrowing stayed rare.
- **Soil layout:** Nik found the suicide pattern on map 42 but not on map 1003. Batch 2 here shows layout luck matters as much as the settings (seed 123). Results from a single soil seed should be treated with care.

---

## 10. What the settings do across studies, and a basis for the final runs

Most studies changed several settings at once, on different code, so no single study isolates every effect. Comparing them is still useful: some effects point the same way wherever they were tested.

### Settings with a consistent effect
| Setting | Effect | Evidence |
|---|---|---|
| **Soil cost per burrow** | The decisive switch. Harmless burrowing never caused a collapse after a take-over, in any study. Collapses rise with cost. | Tarique: cost 0 or 3 → 0/20, 5 → 4/20, 10 → 21/40. Nik: 11/11 with damage against 0/5 without. Jenna tick4452: 18/20 against 0/20. |
| **Burrowing switched off** | Claws don't spread, so there is nothing to collapse. Prey survive. | Josh batch 3: take-overs 1/10 and 2/10 against 7/10 and 10/10. Tarique: prey survive 17/20 without working claws. |
| **Min plant fertility** | The higher it is, the less soil damage plants can tolerate. At 10, one burrow ruins a patch. | Jenna tick4452: 18/20 at 10. Nik: 9 gives the fastest collapses but fewer take-overs, since plants fail before claws spread. |
| **Soil regrowth** | Slower recovery deepens and lengthens the damage. Faster recovery rescues worlds. | Josh batches 1–2: survival 6/45 slow, 21/45 default, 35/45 fast. Nik: slow regrowth gives the deepest soil drops. Jenna: about 100,000 ticks to recover at 0.01%. |
| **Plant regrowth** | Rescues worlds when plants can still grow on partly damaged soil; doesn't when they need perfect soil. | Jenna reference: 4/20 off, 0/20 at 1%. Jenna tick4452: 18/20 at 1% with min plant fertility 10. |
| **Predator strength** | Too strong and prey die before claws matter (failure to adapt). Too weak and burrowing doesn't pay. | Tarique: lifespan ×3 kills all prey in 7/8 runs even without burrowing; ×2 is the window. Josh: 88 of 160 extinctions before 30k at ×3. |
| **Hide duration** | Too short and the claw never pays, so it doesn't spread. | Tarique and Jenna: at 30 ticks, claws barely spread. |
| **Soil layout** | Luck matters as much as the settings. | Josh batch 2: 0/30 to 24/30 survival across layouts; seed 123 worse than others. Nik: map 42 gave the pattern, map 1003 didn't. |

### Settings whose effect is confounded or depends on others
- **Only burrow when predator is close.** Every study that found frequent collapses had it off, and this branch (on) found few. Off means more burrows and more soil damage. It was never varied alone, though.
- **Stay hidden near predators.** On in most studies, off in tick4452. Jenna's earlier report found its range is the strongest lever on how far claws spread (6, 12 and 17 of 20 take-overs at ranges 3, 6 and 10). In tick4452, claws took over anyway.
- **Predator lifespan ×3.** Tarique found it too strong without plant regrowth, yet tick4452 used ×3 and prey survived in harmless runs. Plant regrowth probably makes up for the stronger predators.
- **Claws free.** Makes claws spread further among prey (94% against 17%), but also lets predators pad themselves with claws (the eyeless predator loophole). tick4452 used free claws; Tarique and Nik didn't. A collapse with free claws still needs the soil damage (0/20 harmless), so free claws aren't the cause, but they change who carries claws.
- **Coin flip** (0.5 against 1): Tarique found little effect over 40k ticks.
- **Code differences** (plant regrowth, dead plants leaving no food, armoured predators): built into `jenna-testing`, so they come with any tick4452 result.

### A suggested basis for the final runs
**Base:** tick4452 is currently the strongest and cleanest demonstration:
- claws evolve and aren't seeded;
- a harmless-burrowing control with the same layouts;
- 18/20 against 0/20;
- a clear mechanism.

Using it as the base, the final runs would answer the brief best with these additions:
1. **Run it on one agreed branch, with the config file and branch commit recorded.** Today each result is tied to its own code. That means either merging `jenna-testing`'s changes into the shared branch, or doing the final runs on `jenna-testing`.
2. **Keep the harmless control, and add a no-burrowing control.** No burrowing shows the prey survive without the trait, which the evolutionary-suicide definition needs. Harmless burrowing shows the soil damage is the cause.
3. **Test the perfect-soil rule on its own:** min plant fertility 7, 8, 9 and 10, with everything else fixed. It's the likely driver but untested alone, and a reviewer may see 10 as tuned for collapse.
4. **Use several soil layouts,** at least 3–5 soil seeds, since layout luck was large in batch 2 and in Nik's two maps.
5. **Optionally, claws costing food.** This removes the free-claw loophole for predators and matches Tarique's and Nik's setups. If the collapse still happens, the claim is stronger.
6. **Report prey extinction after a take-over, and the state at the end of the run.** With plant regrowth on, prey can come back, so "extinct" needs both measures (as the tick4452 report does).

The batch runner here could run this as one experiment file: tick4452's settings as `base`, the controls as `configs`, `vary` over min plant fertility, and `soilSeeds`. It needs one change to apply `jenna-testing`'s code (plant regrowth), or the final runs could use Jenna's runner on that branch instead.

---

## 11. Nuances and caveats

- **Seeded claws versus evolved claws answer different questions.** Seeded claws show what decides survival once burrowers exist. Evolved claws show whether burrowing arises and then causes its own extinction. Batches 1–2 are about the first; batch 3 and the group's reports are about the second.
- **"Claws free" bundles three benefits.** Batches 1–2 switched all three together; batch 3 varied only the food cost.
- **Free claws mean different things for prey and for predators.** Among prey they don't spread without burrowing; predators and plants keep them as cheap padding.
- **Averages after extinctions:** batch 1 means over 100k–250k ticks include only runs still going. Batch 2 heatmaps count dead runs as 0. They aren't directly comparable.
- **Species bodies are founder bodies.** A one-cell claw mutation rarely makes a new species, so claws must be counted per organism (the per-role logs), not per species. The first claw-evolution analysis got this wrong and was fixed.
- **The evolved/seeded split in seeded starts is an estimate** based on species lineages.
- **The take-over rule triggers early in seeded starts,** since half the prey start clawed. Use the late share there.
- **Sample sizes:** 5–10 runs per cell. Differences of 2–3 runs can be chance; only the large effects (soil density, burrowing against no burrowing) are clearly significant.
- **The eyeless and clawed predator shares in batch 1** are estimated from species founder bodies.
- **Browser and headless use the same `src/` code** and the same soil layout for a given seed and grid, but browser runs are single runs.
- **"Prey extinct" can be temporary with plant regrowth on.** In tick4452, prey died out and came back 8–13 times in some runs. Report both the first die-out after a take-over and the state at the end.
- **Studies differ in code as well as settings,** so a rate from one branch shouldn't be compared with another branch's rate as if only one setting changed.

---

## 12. Open questions and next steps

0. **Agree on one branch and one base configuration for the final runs** (section 10 suggests tick4452 with added controls).
1. **Turn off *Only burrow when predator is close* for the evolved starts.** This tests whether evolved claws collapse worlds on this branch as often as in Tarique's runs.
2. **Add a harmless-burrowing control** (`hideFertilityCost` 0), to separate the claw's spread from its soil damage.
3. **Free claws for prey only.** Tests whether the clawed and eyeless predators come from the free-claw loophole.
4. **Remove the early plant crash** (`foodBlocksReproduction` off, plant regrowth as on Jenna's branch, or faster soil regrowth). Comparisons would then no longer depend on whether a world happens to survive.
5. **Measure whether clawed prey still out-reproduce clawless prey while a population declines.** This is the part of the evolutionary-suicide definition no report has tested yet.
6. **Replay suspected suicides:** add loading a saved world to the headless runner and rerun with and without the invading predator.
7. **Use dense or medium soil with big or medium patches, and several soil seeds,** for future comparisons.
8. **Vary min plant fertility on its own** (7–10), to show whether the perfect-soil rule drives the tick4452 collapses.

---

## 13. Where everything is

| What | Where |
|---|---|
| Browser runs | `Observations/claw tracking`, `claw dies out (not free)`, `claws free`, `fixed tagging run`, `min burrow fertility 1` |
| Batch 1 | `Observations/claw-soil-predator` (experiment `headless/experiments/claw_soil_predator.json`) |
| Batch 2 | `Observations/soil-layouts` (`headless/experiments/soil_layouts.json`), plotted with `--split soilPatchThreshold,soilPatchResolution` |
| Batch 3 | `Observations/claw-evolution` (`headless/experiments/claw_evolution.json`); claw measures in `claw_evolution/` |
| Replicate averages and comparison figures | `<batch>/averages/` |
| Running | `node headless/batch.js <experiment.json>`, then `python analysis/plot_metrics.py Observations/<batch>` |
| Settings and what they mean | `README.md` (Run Setup and Headless runs sections) |
| Jenna's tick4452 study | `Findings/config_tick4452_report.pdf`; data and sweep file on `jenna-testing` in `analysis/headless/results/jenna-testing/config_tick4452/` |
