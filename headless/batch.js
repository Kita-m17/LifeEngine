#!/usr/bin/env node
// Runs every configuration of an experiment file with several placement seeds, in parallel, one headless/run.js
// process per run. Each run's logs go to Observations/<experiment name>/<label>_seed<N>/, ready for
//   python analysis/plot_metrics.py Observations/<experiment name>
// which plots every run and averages the replicates (runs that only differ in their seeds).
//
// Usage:
//   node headless/batch.js EXPERIMENT.json [--jobs N] [--only LABEL,...] [--dry-run] [--force]
//
//   --jobs      runs at the same time (default: CPU cores - 1)
//   --only      run only these configuration labels
//   --dry-run   list the runs and their settings without running anything
//   --force     rerun runs that already finished (otherwise they are skipped, so a stopped batch can be resumed)
//
// Experiment file (see headless/experiments/ for an example):
//   {
//     "name": "folder name under Observations/",
//     "ticks": 50000,                         ticks per run (a configuration can set its own)
//     "seeds": [1, 2, 3],                     placement seeds: one run per seed per configuration
//     "soilSeeds": [42, 7, 123],              optional: a soil seed for each placement seed (paired in order), so each
//                                             replicate also has its own soil layout
//     "replicates": 3,                        optional: runs per seed (pair), each in its own _rep<N> folder, so
//                                             replicates can share a placement and differ only in the run itself
//     "grid": {"cols": 384, "rows": 193, "cell_size": 5},     optional, this is the default
//     "base": {NAME: VALUE, ...},             settings shared by every configuration (defaults otherwise)
//     "vary": {NAME: [VALUE, ...], ...},      optional: every configuration is run with each value (or combination)
//     "configs": [
//       {"label": "baseline"},
//       {"label": "pred-1", "set": {"predatorMoveInterval": 1}},
//       {"label": "soil", "vary": {"soilRegenRate": [0.01, 0.2]}}   one configuration per value (or combination)
//     ]
//   }
// NAME is a Run Setup key (src/EnvironmentParams.js), an Evolution Controls name (src/Hyperparameters.js) or
// speciesThreshold. Every run is checked before any starts. Ctrl-C stops the batch; running runs save their logs.

const fs = require('fs');
const os = require('os');
const path = require('path');
const {spawn} = require('child_process');
const settingsLib = require('./settings');

const ROOT = path.dirname(__dirname);
const OBSERVATIONS = path.join(ROOT, 'Observations');
const RUNNER = path.join(__dirname, 'run.js');
const DONE = ['finished', 'extinct'];

function parseArgs(argv) {
    let args = {jobs: Math.max(os.cpus().length - 1, 1), only: null, dry_run: false, force: false};
    for (let i = 0; i < argv.length; i++) {
        let arg = argv[i];
        if (arg === '--jobs') {
            args.jobs = Number(argv[++i]);
            if (!Number.isInteger(args.jobs) || args.jobs < 1) throw new Error('--jobs must be a positive whole number');
        }
        else if (arg === '--only') args.only = (argv[++i] || '').split(',').map(s => s.trim()).filter(s => s);
        else if (arg === '--dry-run') args.dry_run = true;
        else if (arg === '--force') args.force = true;
        else if (arg === '--help' || arg === '-h') {
            console.log(fs.readFileSync(__filename, 'utf8').split('\n').slice(1, 30).map(l => l.replace(/^\/\/ ?/, '')).join('\n'));
            process.exit(0);
        }
        else if (arg.startsWith('--')) throw new Error('Unknown argument "' + arg + '" (see --help)');
        else if (!args.experiment) args.experiment = arg;
        else throw new Error('Only one experiment file can be given');
    }
    if (!args.experiment) throw new Error('Give an experiment file (see --help)');
    return args;
}

function safeName(text) {
    return String(text).replace(/[^A-Za-z0-9._=-]+/g, '_');
}

// every combination of the values in vary, e.g. {a: [1, 2], b: [3]} -> [{a: 1, b: 3}, {a: 2, b: 3}]
function combinations(vary) {
    let combos = [{}];
    for (let key in vary) {
        let values = vary[key];
        if (!Array.isArray(values) || values.length === 0)
            throw new Error('"vary.' + key + '" must be a non-empty list of values');
        combos = combos.flatMap(combo => values.map(v => Object.assign({}, combo, {[key]: v})));
    }
    return combos;
}

// the runs an experiment describes: one per configuration (or vary combination) per seed, checked before anything runs
function expand(experiment) {
    if (!experiment.name) throw new Error('The experiment needs a "name" (its folder under Observations/)');
    if (!Array.isArray(experiment.configs) || experiment.configs.length === 0)
        throw new Error('The experiment needs a non-empty "configs" list');
    let seeds = experiment.seeds || [1];
    if (!Array.isArray(seeds) || seeds.some(s => !Number.isInteger(s)))
        throw new Error('"seeds" must be a list of whole numbers');
    let soil_seeds = experiment.soilSeeds || null;
    if (soil_seeds && (!Array.isArray(soil_seeds) || soil_seeds.length !== seeds.length || soil_seeds.some(s => !Number.isInteger(s))))
        throw new Error('"soilSeeds" must be a list of whole numbers, one for each of "seeds"');
    let replicates = experiment.replicates === undefined ? 1 : experiment.replicates;
    if (!Number.isInteger(replicates) || replicates < 1)
        throw new Error('"replicates" must be a whole number of at least 1');
    let grid = Object.assign({}, settingsLib.DEFAULT_GRID, experiment.grid);
    settingsLib.checkGrid(grid);

    let runs = [];
    let labels = new Set();
    for (let config of experiment.configs) {
        if (!config.label) throw new Error('Every configuration needs a "label"');
        for (let combo of combinations(Object.assign({}, experiment.vary, config.vary))) {
            let label = config.label + Object.keys(combo).map(k => '_' + k + '=' + combo[k]).join('');
            if (labels.has(label)) throw new Error('Two configurations are labelled "' + label + '"');
            labels.add(label);
            let ticks = config.ticks || experiment.ticks || 50000;
            for (let [i, seed] of seeds.entries()) {
                let seeded = {runLabel: label, placementSeed: seed};
                if (soil_seeds) seeded.soilSeed = soil_seeds[i];
                let settings = Object.assign({}, experiment.base, config.set, combo, seeded);
                try {
                    settingsLib.split(settings);
                } catch (e) {
                    throw new Error('Configuration "' + label + '": ' + e.message);
                }
                let name = safeName(label) + '_seed' + seed + (soil_seeds ? '_soil' + soil_seeds[i] : '');
                for (let rep = 1; rep <= replicates; rep++) {
                    runs.push({
                        label: label,
                        config_label: config.label,
                        seed: seed,
                        dir: path.join(OBSERVATIONS, safeName(experiment.name), name + (replicates > 1 ? '_rep' + rep : '')),
                        file: {ticks: ticks, grid: grid, settings: settings},
                    });
                }
            }
        }
    }
    return runs;
}

function readStatus(dir) {
    try {
        return JSON.parse(fs.readFileSync(path.join(dir, 'status.json'), 'utf8'));
    } catch (e) {
        return null;
    }
}

function readSettings(dir) {
    try {
        return JSON.parse(fs.readFileSync(path.join(dir, 'settings.json'), 'utf8'));
    } catch (e) {
        return null;
    }
}

// a folder that holds logs from different settings would mix two runs, so it is never reused without --force
function prepare(run, force) {
    let existing = readSettings(run.dir);
    let same = existing && JSON.stringify(existing) === JSON.stringify(run.file);
    let status = readStatus(run.dir);
    if (same && status && DONE.includes(status.state) && !force) return 'skip';
    let has_logs = fs.existsSync(run.dir) && fs.readdirSync(run.dir).some(f => f.endsWith('.csv'));
    if (has_logs && !same && !force)
        throw new Error(run.dir + ' already holds a run with different settings. Use a new experiment name, or --force to replace it');
    if (has_logs) // a stopped or replaced run starts again from scratch
        for (let f of fs.readdirSync(run.dir))
            if (f.endsWith('.csv') || f === 'status.json' || f === 'run.log') fs.unlinkSync(path.join(run.dir, f));
    fs.mkdirSync(run.dir, {recursive: true});
    fs.writeFileSync(path.join(run.dir, 'settings.json'), JSON.stringify(run.file, null, 2));
    return 'run';
}

function formatDuration(ms) {
    let s = Math.round(ms / 1000);
    if (s < 60) return s + 's';
    let m = Math.floor(s / 60);
    return m < 60 ? m + 'm ' + (s % 60) + 's' : Math.floor(m / 60) + 'h ' + (m % 60) + 'm';
}

function launch(run, on_exit) {
    let name = path.basename(run.dir);
    let log = fs.createWriteStream(path.join(run.dir, 'run.log'));
    let child = spawn(process.execPath, [RUNNER, '--settings', path.join(run.dir, 'settings.json'), '--out', run.dir],
        {stdio: ['ignore', 'pipe', 'pipe']});
    let pass = (stream, to) => {
        let buffered = '';
        stream.on('data', (data) => {
            log.write(data);
            buffered += data;
            let lines = buffered.split('\n');
            buffered = lines.pop();
            for (let line of lines) to.write('[' + name + '] ' + line + '\n');
        });
    };
    pass(child.stdout, process.stdout);
    pass(child.stderr, process.stderr);
    child.on('close', (code) => {
        log.end();
        on_exit(code);
    });
    return child;
}

function main() {
    let args = parseArgs(process.argv.slice(2));
    let experiment = JSON.parse(fs.readFileSync(args.experiment, 'utf8'));
    let runs = expand(experiment);
    if (args.only) {
        let unknown = args.only.filter(l => !runs.some(r => r.label === l || r.config_label === l));
        if (unknown.length > 0) throw new Error('No configuration labelled ' + unknown.join(', '));
        runs = runs.filter(r => args.only.includes(r.label) || args.only.includes(r.config_label));
    }
    let batch_dir = path.join(OBSERVATIONS, safeName(experiment.name));

    if (args.dry_run) {
        for (let run of runs) {
            let status = readStatus(run.dir);
            console.log(path.relative(ROOT, run.dir) + '  ' + run.file.ticks + ' ticks' +
                (status ? '  [' + status.state + ' at tick ' + status.tick + ']' : ''));
            console.log('    ' + JSON.stringify(run.file.settings));
        }
        console.log(runs.length + ' runs, ' + args.jobs + ' at a time');
        return;
    }

    let queue = runs.filter(run => prepare(run, args.force) === 'run');
    let skipped = runs.length - queue.length;
    if (skipped > 0) console.log('Skipping ' + skipped + ' finished run(s) (--force reruns them)');
    if (queue.length === 0) {
        console.log('Nothing to run.');
        return;
    }
    fs.mkdirSync(batch_dir, {recursive: true});
    fs.copyFileSync(args.experiment, path.join(batch_dir, 'experiment.json'));
    console.log('Running ' + queue.length + ' run(s), ' + Math.min(args.jobs, queue.length) + ' at a time, into ' +
        path.relative(ROOT, batch_dir));

    let started_ms = Date.now();
    let results = [];
    let running = 0;
    let stopping = false;
    let pending = queue.slice();
    process.on('SIGINT', () => {
        if (!stopping) console.log('\nStopping: running runs are saving their logs, no new runs will start');
        stopping = true; // the runs get the Ctrl-C too, save their logs and exit
    });

    let next = () => {
        while (!stopping && running < args.jobs && pending.length > 0) {
            let run = pending.shift();
            let run_started = Date.now();
            running++;
            launch(run, (code) => {
                running--;
                let status = readStatus(run.dir) || {};
                results.push({run: run, state: status.state || (code === 0 ? 'finished' : 'failed'), tick: status.tick,
                    time: Date.now() - run_started});
                console.log('Done ' + path.basename(run.dir) + ': ' + (status.state || 'failed') + ' at tick ' +
                    status.tick + ' (' + results.length + '/' + queue.length + ')');
                next();
            });
        }
        if (running === 0) summary();
    };

    let summary = () => {
        console.log('\nBatch finished in ' + formatDuration(Date.now() - started_ms));
        for (let r of results.sort((a, b) => a.run.dir.localeCompare(b.run.dir)))
            console.log('  ' + path.basename(r.run.dir).padEnd(40) + String(r.state).padEnd(12) + 'tick ' +
                String(r.tick).padEnd(8) + formatDuration(r.time));
        if (pending.length > 0)
            console.log(pending.length + ' run(s) not started. Run the same command again to continue.');
        console.log('\nPlot with:\n  python analysis/plot_metrics.py "' + path.relative(ROOT, batch_dir) + '"');
        if (results.some(r => !DONE.includes(r.state))) process.exitCode = 1;
    };
    next();
}

try {
    main();
} catch (e) {
    console.error('Error: ' + e.message);
    process.exit(1);
}
