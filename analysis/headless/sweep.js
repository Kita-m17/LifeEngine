#!/usr/bin/env node
// Runs a batch of headless simulations described by a sweep file, several at once, one JSON result per run.
//
// Usage:
//   node analysis/headless/sweep.js analysis/headless/sweeps/evo_suicide.json [--jobs 8] [--out DIR] [--force]
//
// Results go to analysis/headless/results/<sweep name>/ unless --out is given. Runs that already have a result are
// skipped, so an interrupted sweep can be restarted; --force runs them again.
//
// A sweep file looks like this (only "conditions" is required):
//   {
//     "name": "evo_suicide",
//     "ticks": 100000, "every": 1000,
//     "seeds": [1, 2, 3],                  // placement seeds, one run per seed; or {"from": 1, "to": 20}
//     "base": {"burrowOnlyWhenClose": false},   // settings shared by every run
//     "grid": {"cols": 306, "rows": 140, "cell": 5},   // optional: the grid size (default 288 x 180, cell size 5)
//     "vary": {"predatorLifespanMultiplier": [3, 2]},   // optional: every combination is crossed with the conditions
//     "conditions": [
//       {"name": "harmless burrowing", "set": {"hideFertilityCost": 0}},
//       {"name": "soil cost 10", "set": {"hideFertilityCost": 10}},
//       {"name": "soil cost 10, no armour", "set": {"hideFertilityCost": 10}, "ablate": ["no_predator_armour"]}
//     ]
// "ablate" undoes built-in changes for that condition, see run_sim.js.
//   }

const path = require('path');
const fs = require('fs');
const os = require('os');
const {spawn} = require('child_process');

const RUN_SIM = path.join(__dirname, 'run_sim.js');

function parseArgs(argv) {
    const args = {file: null, jobs: os.availableParallelism ? os.availableParallelism() : os.cpus().length, out: null, force: false};
    for (let i = 0; i < argv.length; i++) {
        if (argv[i] === '--jobs') args.jobs = Number(argv[++i]);
        else if (argv[i] === '--out') args.out = argv[++i];
        else if (argv[i] === '--force') args.force = true;
        else args.file = argv[i];
    }
    if (!args.file) throw new Error('usage: node sweep.js SWEEP.json [--jobs N] [--out DIR] [--force]');
    return args;
}

function seedList(seeds) {
    if (!seeds) return [1];
    if (Array.isArray(seeds)) return seeds;
    const list = [];
    for (let s = seeds.from; s <= seeds.to; s++) list.push(s);
    return list;
}

// every combination of the "vary" values, e.g. {a: [1, 2], b: [3]} -> [{a: 1, b: 3}, {a: 2, b: 3}]
function combinations(vary) {
    let combos = [{}];
    for (const key in vary || {}) {
        const next = [];
        for (const combo of combos)
            for (const value of vary[key])
                next.push(Object.assign({}, combo, {[key]: value}));
        combos = next;
    }
    return combos;
}

const slug = (text) => String(text).toLowerCase().replace(/[^a-z0-9.]+/g, '-').replace(/^-|-$/g, '');

function planRuns(sweep, out_dir) {
    const runs = [];
    for (const combo of combinations(sweep.vary)) {
        for (const condition of sweep.conditions) {
            for (const seed of seedList(sweep.seeds)) {
                const set = Object.assign({}, sweep.base, combo, condition.set, {placementSeed: seed});
                const vary_part = Object.keys(combo).map(key => '__' + key + '=' + combo[key]).join('');
                runs.push({
                    file: path.join(out_dir, slug(condition.name) + vary_part + '__s' + seed + '.json'),
                    set: set,
                    ablate: condition.ablate || [],
                    meta: {sweep: sweep.name, condition: condition.name, vary: combo, seed: seed, ablate: condition.ablate || []},
                });
            }
        }
    }
    return runs;
}

function runOne(run, sweep) {
    return new Promise((resolve) => {
        const grid = sweep.grid || {};
        const extra = [];
        for (const key of ['cols', 'rows', 'cell'])
            if (grid[key] !== undefined) extra.push('--' + key, String(grid[key]));
        if (run.ablate.length) extra.push('--ablate', run.ablate.join(','));
        const child = spawn(process.execPath, [RUN_SIM, '--ticks', String(sweep.ticks || 100000),
            '--every', String(sweep.every || 1000), '--set', JSON.stringify(run.set), '--meta', JSON.stringify(run.meta),
            '--out', run.file, ...extra], {stdio: ['ignore', 'ignore', 'pipe']});
        let errors = '';
        child.stderr.on('data', (data) => errors += data);
        child.on('close', (code) => resolve({code, errors}));
    });
}

async function main() {
    const args = parseArgs(process.argv.slice(2));
    const sweep = JSON.parse(fs.readFileSync(args.file, 'utf8'));
    sweep.name = sweep.name || path.basename(args.file, '.json');
    const out_dir = args.out || path.join(__dirname, 'results', sweep.name);
    fs.mkdirSync(out_dir, {recursive: true});
    fs.writeFileSync(path.join(out_dir, 'sweep.json'), JSON.stringify(sweep, null, 2));

    const runs = planRuns(sweep, out_dir).filter(run => args.force || !fs.existsSync(run.file));
    console.log(`${sweep.name}: ${runs.length} runs to do, ${args.jobs} at a time, results in ${out_dir}`);
    let next = 0, done = 0, failed = 0;
    const start = Date.now();
    const worker = async () => {
        while (next < runs.length) {
            const run = runs[next++];
            const {code, errors} = await runOne(run, sweep);
            done++;
            const label = `${run.meta.condition} ${JSON.stringify(run.meta.vary)} seed ${run.meta.seed}`;
            if (code !== 0) {
                failed++;
                console.log(`[${done}/${runs.length}] FAILED ${label}\n${errors}`);
                continue;
            }
            const result = JSON.parse(fs.readFileSync(run.file, 'utf8'));
            const minutes = ((Date.now() - start) / 60000).toFixed(1);
            console.log(`[${done}/${runs.length}] ${label}: ` +
                (result.extinct_at !== null ? `everything died at ${result.extinct_at}` : `ran ${result.ticks_run} ticks`) +
                ` (${minutes} min)`);
        }
    };
    await Promise.all(Array.from({length: Math.min(args.jobs, runs.length)}, worker));
    console.log(`finished: ${done - failed} ok, ${failed} failed`);
    if (failed) process.exitCode = 1;
}

main();
