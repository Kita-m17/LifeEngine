// The starting configuration of a run (soil layout and seeded organisms) plus mechanics that can be isolated and
// changed between runs. Every value is exported with the logs (run_config CSV) so runs can be compared, and runs that
// only differ in their seeds can be averaged as replicates.
//
// Change a default here or in the Run Setup tab. "reset" settings take effect the next time the world resets (the soil
// and the starting organisms are placed then); "live" settings take effect straight away.
//
// The layout is deterministic for a given seed AND grid size: the soil noise is stretched over the grid, so the same
// seed on a different window size gives a different layout. Turn off "Fill Window" and fix the columns, rows and cell
// size in World Controls to reproduce a layout exactly. Only the layout is seeded; the run itself still varies.

const FIELDS = [
    {key: 'runLabel', group: 'Run', type: 'text', default: '', applies: 'live', label: 'Run label',
        title: 'A name for this configuration. Written to the logs and used in plot legends.'},

    // soil layout: fertile patches separated by permanently infertile pathways, from seeded noise
    {key: 'soilSeed', group: 'Soil', type: 'int', default: 42, applies: 'reset', label: 'Soil seed',
        title: 'Fixes the soil layout. The same seed (and grid size) always gives the same layout.'},
    {key: 'soilPatchThreshold', group: 'Soil', type: 'float', default: 0, min: -1, max: 1, step: 0.05, applies: 'reset',
        label: 'Soil density (patch threshold)',
        title: 'Noise cutoff for fertile soil. Raise it for less, sparser fertile soil with wider infertile pathways; lower it for more, better connected fertile soil. 0 makes about half the grid fertile.'},
    {key: 'soilPatchResolution', group: 'Soil', type: 'int', default: 20, min: 1, step: 1, applies: 'reset',
        label: 'Soil patch size (resolution)',
        title: 'How many noise bumps are stretched across the grid. Lower gives fewer, bigger patches; higher gives many small, scattered ones.'},
    {key: 'soilRegenRate', group: 'Soil', type: 'float', default: 0.05, min: 0, max: 100, step: 0.01, applies: 'live',
        label: 'Soil regen chance (%)', title: 'Percent chance each tick that an unoccupied soil cell regains fertility, up to its cap.'},
    {key: 'soilRegenAmount', group: 'Soil', type: 'float', default: 1, min: 0, step: 0.1, applies: 'live',
        label: 'Soil regen amount', title: 'Fertility a soil cell regains each time it regenerates.'},
    {key: 'minPlantFertility', group: 'Soil', type: 'float', default: 7, min: 0, step: 0.5, applies: 'live',
        label: 'Min plant fertility',
        title: 'Average soil fertility needed under a plant (a producer that cannot move) for it to be born or placed there.'},

    // starting organisms, placed at seeded random free spots (plants only where they can grow)
    {key: 'placementSeed', group: 'Organisms', type: 'int', default: 1, applies: 'reset', label: 'Placement seed',
        title: 'Fixes where the starting organisms are placed. Change it for replicates of the same configuration.'},
    {key: 'numPredators', group: 'Organisms', type: 'int', default: 10, min: 0, step: 1, applies: 'reset', label: 'Predators'},
    {key: 'numPrey', group: 'Organisms', type: 'int', default: 10, min: 0, step: 1, applies: 'reset', label: 'Prey (no claw)'},
    {key: 'numClawPrey', group: 'Organisms', type: 'int', default: 10, min: 0, step: 1, applies: 'reset', label: 'Prey (with claw)'},
    {key: 'numPlants', group: 'Organisms', type: 'int', default: 39, min: 0, step: 1, applies: 'reset', label: 'Plants'},

    // mechanics
    {key: 'clawPredatorChance', group: 'Mechanics', type: 'float', default: 0.5, min: 0, max: 1, step: 0.1, applies: 'live',
        label: 'Clawed killer becomes predator (chance)',
        title: 'When a clawed organism gains its first killer cell, the chance it becomes a predator instead of staying prey. 0.5 is the coin flip; 1 turns the coin flip off (clawed organisms become predators like any other); 0 keeps them prey.'},
    {key: 'clawCellsFree', group: 'Mechanics', type: 'bool', default: true, applies: 'live', label: 'Claw cells are free',
        title: 'Claw cells do not count toward the food an organism needs to reproduce (they still add lifespan and health).'},
    {key: 'hibernateWhileHidden', group: 'Mechanics', type: 'bool', default: true, applies: 'live', label: "Don't age while hidden",
        title: 'Ticks spent hidden underground do not count toward how long an organism can live.'},
    {key: 'stayHiddenNearPredator', group: 'Mechanics', type: 'bool', default: true, applies: 'live', label: 'Stay hidden near predators',
        title: 'A hidden organism stays underground while a predator is within the range below, for up to another hide duration.'},
    {key: 'stayHiddenRange', group: 'Mechanics', type: 'int', default: 6, min: 1, max: 50, step: 1, applies: 'live', label: 'Stay hidden range',
        title: 'How close (in cells) a predator has to be to keep a hidden organism underground.'},
    {key: 'burrowOnlyWhenClose', group: 'Mechanics', type: 'bool', default: true, applies: 'live', label: 'Only burrow when predator is close',
        title: 'Prey with a claw only burrow when the predator they see is within the range below. Further away, they run instead.'},
    {key: 'burrowTriggerRange', group: 'Mechanics', type: 'int', default: 8, min: 1, max: 50, step: 1, applies: 'live', label: 'Burrow trigger range',
        title: 'How close (in cells) a seen predator has to be before prey with a claw burrow.'},
];

// names these settings had in Hyperparameters, so older controls files and saved worlds still load them
const LEGACY_KEYS = {
    fertilityTerrainSeed: 'soilSeed',
    fertilityPatchThreshold: 'soilPatchThreshold',
    fertilityPatchResolution: 'soilPatchResolution',
    fertilityRegenRate: 'soilRegenRate',
};

const EnvironmentParams = {
    FIELDS: FIELDS,

    setDefaults() {
        for (let field of FIELDS)
            this[field.key] = field.default;
    },

    // accepts both current keys and the old Hyperparameters names; unknown keys are ignored
    loadJsonObj(obj) {
        if (!obj) return;
        for (let key in obj) {
            let name = LEGACY_KEYS[key] || key;
            if (FIELDS.some(f => f.key === name))
                this[name] = obj[key];
        }
    },

    toJson() {
        let json = {};
        for (let field of FIELDS)
            json[field.key] = this[field.key];
        return json;
    },
};

EnvironmentParams.setDefaults();

module.exports = EnvironmentParams;
