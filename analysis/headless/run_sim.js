#!/usr/bin/env node
// Runs one simulation without the browser, using the same src/ code as the web page, and writes a time series of
// the populations and the soil to a JSON file (or stdout). Much faster than the browser, so it is used for batches of
// runs (see sweep.js) and the evolutionary suicide figures (see plot_evo_suicide.py).
//
// Usage:
//   node analysis/headless/run_sim.js [--ticks 100000] [--every 1000] [--set JSON] [--out FILE]
//                                     [--cols 288] [--rows 180] [--cell 5] [--meta JSON] [--ablate LIST]
//
// --set overrides settings for this run. Keys are looked up in EnvironmentParams (Run Setup) first, then in
// Hyperparameters (Evolution Controls), e.g. --set '{"placementSeed":3,"hideFertilityCost":0}'.
// The grid defaults to 288 x 180 cells of size 5, about what a 1440 x 900 window gives in the browser.
// Only the starting layout is seeded: Math.random is not, so repeating a run gives a different outcome.
//
// On branches whose world regrows plants (WorldEnvironment.regrowPlant), the headless world calls that same method
// every tick, so it can't drift from the browser.
//
// --ablate undoes one of the plant regrowth branch's built-in changes for this run only (in memory, the source isn't
// changed), so each change can be measured on its own. A comma-separated list of:
//   no_predator_armour  the starting predators are built without their two armour cells
//   plants_leave_food   organisms that are neither predator nor prey (plants) turn into food when they die, as before
//   claws_on_plants     claw and producer cells may be on the same organism again

const path = require('path');
const fs = require('fs');

const SRC = path.join(__dirname, '..', '..', 'src');
const Hyperparams = require(path.join(SRC, 'Hyperparameters'));
const EnvironmentParams = require(path.join(SRC, 'EnvironmentParams'));
const GridMap = require(path.join(SRC, 'Grid', 'GridMap'));
const Organism = require(path.join(SRC, 'Organism', 'Organism'));
const Anatomy = require(path.join(SRC, 'Organism', 'Anatomy'));
const CellStates = require(path.join(SRC, 'Organism', 'Cell', 'CellStates'));
const WorldEnvironment = require(path.join(SRC, 'Environments', 'WorldEnvironment'));
const RandomOrganismGenerator = require(path.join(SRC, 'Organism', 'RandomOrganismGenerator'));
const FossilRecord = require(path.join(SRC, 'Stats', 'FossilRecord'));
const createSeededPerlin = require(path.join(SRC, 'Utils', 'SeededPerlin'));

function parseArgs(argv) {
    const args = {ticks: 100000, every: 1000, cols: 288, rows: 180, cell: 5, set: {}, meta: null, out: null, ablate: []};
    for (let i = 0; i < argv.length; i++) {
        const key = argv[i].replace(/^--/, '');
        const value = argv[++i];
        if (value === undefined || !(key in args))
            throw new Error('unknown or incomplete argument: ' + argv[i - 1]);
        if (key === 'set' || key === 'meta')
            args[key] = JSON.parse(value);
        else if (key === 'out')
            args.out = value;
        else if (key === 'ablate')
            args.ablate = value.split(',').map(name => name.trim()).filter(Boolean);
        else
            args[key] = Number(value);
    }
    return args;
}

// EnvironmentParams first (Run Setup), then Hyperparams (Evolution Controls). Unknown keys are an error, so a typo
// doesn't silently run the default instead
function applySettings(set) {
    Hyperparams.setDefaults();
    EnvironmentParams.setDefaults();
    for (const key in set) {
        if (EnvironmentParams.FIELDS.some(field => field.key === key))
            EnvironmentParams[key] = set[key];
        else if (key in Hyperparams && typeof Hyperparams[key] !== 'function')
            Hyperparams[key] = set[key];
        else
            throw new Error('unknown setting: ' + key);
    }
}

// in-memory switches that undo the plant regrowth branch's built-in changes (see --ablate above)
const ABLATIONS = {
    no_predator_armour() {
        const create = RandomOrganismGenerator.createPredator;
        RandomOrganismGenerator.createPredator = function () {
            const predator = create.apply(this, arguments);
            for (const cell of predator.anatomy.cells.filter(cell => cell.state === CellStates.armor))
                predator.anatomy.removeCell(cell.loc_col, cell.loc_row);
            return predator;
        };
    },
    plants_leave_food() {
        const die = Organism.prototype.die;
        Organism.prototype.die = function () {
            const leaves_food = !this.is_predator && !this.is_prey;
            const spots = leaves_food ? this.anatomy.cells.map(cell =>
                [this.c + cell.rotatedCol(this.rotation), this.r + cell.rotatedRow(this.rotation)]) : [];
            const result = die.apply(this, arguments);
            for (const [c, r] of spots)
                this.env.changeCell(c, r, CellStates.food, null);
            return result;
        };
    },
    claws_on_plants() {
        Anatomy.prototype.canAddCellType = function () { return true; };
    },
};

function applyAblations(names) {
    for (const name of names) {
        if (!ABLATIONS[name])
            throw new Error('unknown ablation: ' + name + ' (known: ' + Object.keys(ABLATIONS).join(', ') + ')');
        if (name === 'no_predator_armour' && !RandomOrganismGenerator.createPredator)
            throw new Error('this code has no createPredator to change');
        if (name === 'claws_on_plants' && !Anatomy.prototype.canAddCellType)
            throw new Error('this code already allows claws on plants');
        ABLATIONS[name]();
    }
}

// the world's own plant regrowth, on branches that have it
const regrowPlant = WorldEnvironment.prototype.regrowPlant || null;

// the parts of WorldEnvironment that organisms use, without the renderer, controls or stats panel
class HeadlessEnvironment {
    constructor(cols, rows, cell_size) {
        this.num_cols = cols;
        this.num_rows = rows;
        this.grid_map = new GridMap(cols, rows, cell_size);
        this.renderer = {cell_size: cell_size, addToRender() {}, renderFullGrid() {}};
        this.organisms = [];
        this.total_ticks = 0;
        this.regrown = 0;
        this.generateSoil();
        FossilRecord.setEnv(this);
    }

    // same as EnvironmentController.generateFertilityTerrain, with the settings from EnvironmentParams
    generateSoil() {
        const noise = createSeededPerlin(EnvironmentParams.soilSeed);
        const resolution = EnvironmentParams.soilPatchResolution;
        const cell_size = this.renderer.cell_size;
        for (let r = 0; r < this.num_rows; r++) {
            for (let c = 0; c < this.num_cols; c++) {
                const x = c / this.num_cols * (resolution / cell_size * (this.num_cols / this.num_rows));
                const y = r / this.num_rows * (resolution / cell_size * (this.num_rows / this.num_cols));
                const cap = noise.get(x, y) > EnvironmentParams.soilPatchThreshold ? Hyperparams.maxFertility : 0;
                this.grid_map.setCellFertilityCap(c, r, cap);
                this.grid_map.setCellFertility(c, r, cap);
            }
        }
    }

    originOfLife() {
        return RandomOrganismGenerator.generateSeeded(this, (organism) => {
            this.addOrganism(organism);
            FossilRecord.addSpecies(organism, null);
        });
    }

    // same order as WorldEnvironment.update: organisms born this tick wait for the next one
    update() {
        const count = this.organisms.length;
        const survivors = [];
        for (let i = 0; i < count; i++) {
            const org = this.organisms[i];
            if (org.living && org.update())
                survivors.push(org);
        }
        for (let i = count; i < this.organisms.length; i++) {
            if (this.organisms[i].living)
                survivors.push(this.organisms[i]);
        }
        this.organisms = survivors;
        this.grid_map.regenerateFertility();
        if (regrowPlant) {
            const before = this.organisms.length;
            regrowPlant.call(this);
            this.regrown += this.organisms.length - before;
        }
        this.total_ticks++;
    }

    changeCell(c, r, state, owner) {
        this.grid_map.setCellType(c, r, state);
        this.grid_map.setCellOwner(c, r, owner);
    }

    addOrganism(organism) {
        organism.updateGrid();
        this.organisms.push(organism);
    }

    canAddOrganism() {
        return Hyperparams.maxOrganisms < 0 || this.organisms.length < Hyperparams.maxOrganisms;
    }
}

function role(org) {
    if (org.is_predator) return 'predators';
    if (org.isPlant()) return 'plants';
    if (org.is_prey) return org.anatomy.has_claw ? 'claw_prey' : 'prey';
    return 'other';
}

const COLUMNS = ['t', 'predators', 'prey', 'claw_prey', 'plants', 'other', 'hidden', 'burrows', 'soil', 'growable',
    'population', 'with_claw', 'regrown', 'soil_all', 'degraded'];

// one row of the time series. soil is the mean fertility of the soil that can be fertile, as a percent of the most it
// can hold; growable is the percent of that soil fertile enough for a plant to grow.
// soil_all and degraded are what the browser's "Burrowing & Soil Health" chart shows: the mean fertility of every cell
// (the permanently infertile pathways included) as a percent of the maximum, and the percent of every cell below half
// of the starting value of that mean. with_claw counts organisms of any role with a claw cell; regrown counts plants
// the world added since the last sample
function sample(env, burrows) {
    const row = {t: env.total_ticks, predators: 0, prey: 0, claw_prey: 0, plants: 0, other: 0, hidden: 0, burrows: burrows,
        population: env.organisms.length, with_claw: 0, regrown: env.regrown};
    env.regrown = 0;
    for (const org of env.organisms) {
        row[role(org)]++;
        if (org.isHidden()) row.hidden++;
        if (org.anatomy.has_claw) row.with_claw++;
    }
    let fertility = 0, growable = 0, cells = 0, all_fertility = 0, all_cells = 0;
    for (const col of env.grid_map.grid) {
        for (const cell of col) {
            all_cells++;
            all_fertility += cell.fertility;
            if (cell.fertility_cap <= 0) continue;
            cells++;
            fertility += cell.fertility;
            if (cell.fertility >= EnvironmentParams.minPlantFertility) growable++;
        }
    }
    const all_mean = all_cells ? all_fertility / all_cells : 0;
    if (env.initial_all_mean === undefined) env.initial_all_mean = all_mean;
    let degraded = 0;
    for (const col of env.grid_map.grid)
        for (const cell of col)
            if (cell.fertility < env.initial_all_mean * 0.5) degraded++;
    row.soil = cells ? Math.round(1000 * fertility / (cells * Hyperparams.maxFertility)) / 10 : 0;
    row.growable = cells ? Math.round(1000 * growable / cells) / 10 : 0;
    row.soil_all = Math.round(1000 * all_mean / Hyperparams.maxFertility) / 10;
    row.degraded = all_cells ? Math.round(1000 * degraded / all_cells) / 10 : 0;
    return row;
}

function run(args) {
    applySettings(args.set);
    applyAblations(args.ablate);
    FossilRecord.updateData = function () {}; // the stats panel's sampling isn't needed here

    // count burrows between samples (in memory only, the source isn't changed)
    let burrows = 0;
    const hide = Organism.prototype.hide;
    Organism.prototype.hide = function () {
        burrows++;
        return hide.apply(this, arguments);
    };

    const env = new HeadlessEnvironment(args.cols, args.rows, args.cell);
    const placed = env.originOfLife();
    const series = {};
    for (const column of COLUMNS) series[column] = [];
    const record = () => {
        const row = sample(env, burrows);
        burrows = 0;
        for (const column of COLUMNS) series[column].push(row[column]);
    };

    record();
    let extinct_at = null;
    while (env.total_ticks < args.ticks) {
        env.update();
        if (env.organisms.length === 0) {
            extinct_at = env.total_ticks;
            record();
            break;
        }
        if (env.total_ticks % args.every === 0)
            record();
    }

    const hyperparams = {};
    for (const key in Hyperparams) {
        if (typeof Hyperparams[key] !== 'object' && typeof Hyperparams[key] !== 'function')
            hyperparams[key] = Hyperparams[key];
    }
    return {
        meta: args.meta,
        settings: args.set,
        ticks: args.ticks,
        every: args.every,
        grid: {cols: args.cols, rows: args.rows, cell_size: args.cell},
        ablate: args.ablate,
        plant_regrowth_in_code: !!regrowPlant,
        placed: placed,
        environment_params: EnvironmentParams.toJson(),
        hyperparams: hyperparams,
        ticks_run: env.total_ticks,
        extinct_at: extinct_at, // the tick every organism was dead, null if something survived
        series: series,
    };
}

if (require.main === module) {
    const args = parseArgs(process.argv.slice(2));
    const result = JSON.stringify(run(args));
    if (args.out) {
        fs.mkdirSync(path.dirname(path.resolve(args.out)), {recursive: true});
        fs.writeFileSync(args.out, result);
    }
    else {
        process.stdout.write(result + '\n');
    }
}

module.exports = {run};
