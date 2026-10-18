// Settings for headless runs: a flat {name: value} object mixing Run Setup settings (src/EnvironmentParams.js),
// Evolution Controls (src/Hyperparameters.js) and the species threshold. Names are checked against those files so a
// typo in an experiment fails before anything runs, instead of being silently ignored.

const EnvironmentParams = require('../src/EnvironmentParams.js');
const Hyperparams = require('../src/Hyperparameters.js');
const FossilRecord = require('../src/Stats/FossilRecord.js');

// the secondary screen (1920x1080) with Fill Window on and cell size 5, the size the browser runs used, so the
// same soil seed gives the same layout here as in those runs
const DEFAULT_GRID = {cols: 384, rows: 193, cell_size: 5};

const SPECIES_THRESHOLD = 'speciesThreshold';
const DEFAULT_SPECIES_THRESHOLD = FossilRecord.species_threshold;

function describe(key) {
    let field = EnvironmentParams.FIELDS.find(f => f.key === key);
    if (field) return {where: 'environment', field: field};
    if (key in Hyperparams && typeof Hyperparams[key] !== 'function' && typeof Hyperparams[key] !== 'object')
        return {where: 'hyperparams', type: typeof Hyperparams[key]};
    if (key === SPECIES_THRESHOLD) return {where: 'species', field: {type: 'int', min: 1}};
    return null;
}

function checkValue(key, value, info) {
    let field = info.field;
    let type = field ? field.type : info.type;
    let ok = {
        int: Number.isInteger(value),
        float: typeof value === 'number' && isFinite(value),
        number: typeof value === 'number' && isFinite(value),
        bool: typeof value === 'boolean',
        boolean: typeof value === 'boolean',
        text: typeof value === 'string',
    }[type];
    if (!ok)
        throw new Error('"' + key + '" must be ' + (type === 'bool' || type === 'boolean' ? 'true or false' : 'a ' + type) +
            ', got ' + JSON.stringify(value));
    if (field && field.min !== undefined && value < field.min)
        throw new Error('"' + key + '" must be at least ' + field.min + ', got ' + value);
    if (field && field.max !== undefined && value > field.max)
        throw new Error('"' + key + '" must be at most ' + field.max + ', got ' + value);
}

// splits flat settings into the Run Setup and Evolution Controls parts, throwing on unknown names or bad values
function split(flat) {
    let out = {environment: {}, hyperparams: {}, speciesThreshold: null};
    for (let key in flat) {
        let info = describe(key);
        if (!info)
            throw new Error('Unknown setting "' + key + '". Use a key from src/EnvironmentParams.js FIELDS, a name from ' +
                'src/Hyperparameters.js, or ' + SPECIES_THRESHOLD);
        checkValue(key, flat[key], info);
        if (info.where === 'environment') out.environment[key] = flat[key];
        else if (info.where === 'hyperparams') out.hyperparams[key] = flat[key];
        else out.speciesThreshold = flat[key];
    }
    return out;
}

// sets every setting to its default, then applies the given ones
function apply(flat) {
    let parts = split(flat);
    EnvironmentParams.setDefaults();
    Hyperparams.setDefaults();
    EnvironmentParams.loadJsonObj(parts.environment);
    Hyperparams.loadJsonObj(parts.hyperparams);
    FossilRecord.species_threshold = parts.speciesThreshold || DEFAULT_SPECIES_THRESHOLD;
}

function checkGrid(grid) {
    for (let key of ['cols', 'rows', 'cell_size']) {
        if (!Number.isInteger(grid[key]) || grid[key] < 1)
            throw new Error('grid.' + key + ' must be a positive whole number, got ' + JSON.stringify(grid[key]));
    }
}

module.exports = {DEFAULT_GRID, split, apply, checkGrid};
