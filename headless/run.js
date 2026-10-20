#!/usr/bin/env node
// Runs one simulation without a browser and writes the same CSV logs as the Statistics tab's "All" export
// (timeseries, species_log, groups_log, species_summary, key_moments, run_config), so analysis/plot_metrics.py reads
// them unchanged. It uses the simulation code in src/ as is; only the drawing is left out.
//
// Only the starting layout is seeded (soil seed and placement seed); the run itself is random, as in the browser.
//
// Usage:
//   node headless/run.js --out DIR [--settings FILE] [--ticks N] [--set NAME=VALUE ...]
//                        [--progress N] [--save-every N]
//
//   --out          folder for the CSV logs (created if needed)
//   --settings     JSON file: {"ticks": N, "grid": {"cols", "rows", "cell_size"}, "settings": {NAME: VALUE, ...}}
//                  (headless/batch.js writes one of these into each run folder)
//   --ticks        ticks to run (default 50000); the run also stops if everything dies
//   --set          a Run Setup or Evolution Controls setting, e.g. --set placementSeed=2 --set predatorMoveInterval=1
//   --progress     print progress every N ticks (default 5000)
//   --save-every   write the logs every N ticks, so a run that is stopped early keeps its data (default 25000)
//
// Ctrl-C saves the logs before exiting.

const fs = require('fs');
const path = require('path');
const settingsLib = require('./settings');
const WorldEnvironment = require('../src/Environments/WorldEnvironment');
const FossilRecord = require('../src/Stats/FossilRecord');
const WorldConfig = require('../src/WorldConfig');

const DEFAULTS = {ticks: 50000, progress: 5000, save_every: 25000};
const TICKS_PER_CHUNK = 200; // ticks between checks for Ctrl-C

function parseArgs(argv) {
    let args = {set: {}};
    for (let i = 0; i < argv.length; i++) {
        let arg = argv[i];
        let value = () => {
            if (i + 1 >= argv.length) throw new Error(arg + ' needs a value');
            return argv[++i];
        };
        if (arg === '--out') args.out = value();
        else if (arg === '--settings') args.settings = value();
        else if (arg === '--ticks') args.ticks = positiveInt(arg, value());
        else if (arg === '--progress') args.progress = positiveInt(arg, value());
        else if (arg === '--save-every') args.save_every = positiveInt(arg, value());
        else if (arg === '--set') {
            let pair = value();
            let eq = pair.indexOf('=');
            if (eq < 1) throw new Error('--set needs NAME=VALUE, got "' + pair + '"');
            args.set[pair.slice(0, eq)] = parseValue(pair.slice(eq + 1));
        }
        else if (arg === '--help' || arg === '-h') {
            console.log(fs.readFileSync(__filename, 'utf8').split('\n').slice(1, 22).map(l => l.replace(/^\/\/ ?/, '')).join('\n'));
            process.exit(0);
        }
        else throw new Error('Unknown argument "' + arg + '" (see --help)');
    }
    if (!args.out) throw new Error('--out is required (see --help)');
    return args;
}

function positiveInt(name, text) {
    let n = Number(text);
    if (!Number.isInteger(n) || n < 1) throw new Error(name + ' must be a positive whole number, got "' + text + '"');
    return n;
}

// numbers and true/false as such, anything else as text
function parseValue(text) {
    try {
        return JSON.parse(text);
    } catch (e) {
        return text;
    }
}

function main() {
    let args = parseArgs(process.argv.slice(2));
    let file = args.settings ? JSON.parse(fs.readFileSync(args.settings, 'utf8')) : {};
    let ticks = args.ticks || file.ticks || DEFAULTS.ticks;
    let progress = args.progress || DEFAULTS.progress;
    let save_every = args.save_every || DEFAULTS.save_every;
    let grid = Object.assign({}, settingsLib.DEFAULT_GRID, file.grid);
    settingsLib.checkGrid(grid);
    settingsLib.apply(Object.assign({}, file.settings, args.set));

    // a world that dies stays dead, so the run ends (in the browser it would reset and start again)
    WorldConfig.auto_reset = false;
    WorldConfig.auto_pause = false;

    let out = path.resolve(args.out);
    fs.mkdirSync(out, {recursive: true});
    let logs = new Logs(out);
    let env = new WorldEnvironment({running: false}, grid.cell_size, {cols: grid.cols, rows: grid.rows});
    // a full log is written as a numbered part and cleared from memory, like auto-save in the browser
    FossilRecord.on_log_full = (part) => {
        logs.write('species_log_part' + part, FossilRecord.speciesLogCSV(), env.total_ticks);
        logs.write('groups_log_part' + part, FossilRecord.groupsLogCSV(), env.total_ticks);
        return true;
    };
    env.OriginOfLife();

    let status = {state: 'running', tick: 0, target_ticks: ticks, grid: grid, started: new Date().toISOString()};
    let started_ms = Date.now();
    let last_report = {ms: started_ms, tick: 0};
    let stop_signal = null;
    for (let signal of ['SIGINT', 'SIGTERM'])
        process.on(signal, () => { stop_signal = signal; });

    let finish = (state) => {
        logs.exportAll(env);
        status.state = state;
        writeStatus(out, status, env, started_ms);
        console.log(state + ' at tick ' + env.total_ticks + ' after ' + formatDuration(Date.now() - started_ms) +
            ', logs in ' + out);
    };

    let step = () => {
        try {
            runChunk();
        } catch (e) {
            status.error = e.stack;
            try { finish('error'); } catch (ignored) {} // keep whatever was logged before the error
            console.error(e.stack);
            process.exitCode = 1;
        }
    };
    let runChunk = () => {
        let chunk_end = Math.min(env.total_ticks + TICKS_PER_CHUNK, ticks);
        while (env.total_ticks < chunk_end && env.organisms.length > 0) {
            env.update();
            let tick = env.total_ticks;
            if (tick % progress === 0) {
                let now = Date.now();
                console.log(progressLine(env, (tick - last_report.tick) / Math.max(now - last_report.ms, 1) * 1000));
                last_report = {ms: now, tick: tick};
                writeStatus(out, status, env, started_ms);
            }
            if (tick % save_every === 0 && tick < ticks)
                logs.exportAll(env);
        }
        if (env.organisms.length === 0) return finish('extinct');
        if (env.total_ticks >= ticks) return finish('finished');
        if (stop_signal) {
            finish('interrupted');
            process.exitCode = 130;
            return;
        }
        setImmediate(step); // lets Ctrl-C through between chunks
    };
    step();
}

// writes the logs as <name>_tick<T>.csv like the browser's downloads. Each save replaces the previous one, apart from
// the numbered parts of full logs, which are kept
class Logs {
    constructor(out) {
        this.out = out;
        this.previous = [];
    }

    write(name, csv, tick) {
        let file = path.join(this.out, name + '_tick' + tick + '.csv');
        let tmp = file + '.tmp';
        fs.writeFileSync(tmp, csv);
        fs.renameSync(tmp, file); // never leaves a half-written log if the run is killed
        return file;
    }

    exportAll(env) {
        let tick = env.total_ticks;
        let part = FossilRecord.log_part > 1 ? '_part' + FossilRecord.log_part : '';
        let written = [
            this.write('timeseries', FossilRecord.timeSeriesCSV(), tick),
            this.write('species_log' + part, FossilRecord.speciesLogCSV(), tick),
            this.write('groups_log' + part, FossilRecord.groupsLogCSV(), tick),
            this.write('species_summary', FossilRecord.speciesSummaryCSV(), tick),
            this.write('key_moments', FossilRecord.eventsCSV(), tick),
            this.write('run_config', FossilRecord.runConfigCSV(), tick),
        ];
        for (let file of this.previous) {
            if (!written.includes(file) && fs.existsSync(file))
                fs.unlinkSync(file);
        }
        this.previous = written;
    }
}

function roleCounts() {
    let samples = FossilRecord.group_samples;
    let sample = samples.length > 0 ? samples[samples.length - 1].role : null;
    let pop = (role) => sample && sample[role] ? sample[role].pop : 0;
    return {plants: pop('Plants'), predators: pop('Predators'), claw_prey: pop('Prey (burrowing)'),
        prey: pop('Prey (non-burrowing)')};
}

function progressLine(env, ticks_per_sec) {
    let roles = roleCounts();
    return 'tick ' + env.total_ticks + ' | pop ' + env.organisms.length + ' (plants ' + roles.plants + ', predators ' +
        roles.predators + ', prey ' + roles.prey + ', burrowing prey ' + roles.claw_prey + ') | species ' +
        FossilRecord.numExtantSpecies() + ' | ' + Math.round(ticks_per_sec) + ' ticks/s';
}

function writeStatus(out, status, env, started_ms) {
    status.tick = env.total_ticks;
    status.population = env.organisms.length;
    status.roles = roleCounts();
    status.elapsed_s = Math.round((Date.now() - started_ms) / 1000);
    status.updated = new Date().toISOString();
    fs.writeFileSync(path.join(out, 'status.json'), JSON.stringify(status, null, 2));
}

function formatDuration(ms) {
    let s = Math.round(ms / 1000);
    return s < 60 ? s + 's' : Math.floor(s / 60) + 'm ' + (s % 60) + 's';
}

try {
    main();
} catch (e) {
    console.error('Error: ' + e.message);
    process.exit(1);
}
