const CellStates = require("./Cell/CellStates");
const Organism = require("./Organism");
const Brain = require("./Perception/Brain")
const Directions = require("./Directions");
const Hyperparams = require("../Hyperparameters");
const EnvironmentParams = require("../EnvironmentParams");
const {mulberry32} = require("../Utils/SeededPerlin");
const SMALL_PREY = require("../../seeded species/prey_small.json");
const LARGE_PREY = require("../../seeded species/prey_large.json");

class RandomOrganismGenerator {

    static generate(env) {

        var center = env.grid_map.getCenter();
        var organism = new Organism(center[0], center[1], env, null);
        organism.anatomy.addDefaultCell(CellStates.mouth, 0, 0);

        var outermostLayer = RandomOrganismGenerator.organismLayers;
        var x, y;

        // iterate from center to edge of organism
        // layer 0 is the central cell of the organism
        for (var layer = 1; layer <= outermostLayer; layer++) {

            var someCellSpawned = false;
            var spawnChance = RandomOrganismGenerator.cellSpawnChance * 1 - ((layer - 1) / outermostLayer);

            // top
            y = -layer;
            for (x = -layer; x <= layer; x++)
                someCellSpawned = RandomOrganismGenerator.trySpawnCell(organism, x, y, spawnChance);

            // bottom
            y = layer;
            for (x = -layer; x <= layer; x++)
                someCellSpawned = RandomOrganismGenerator.trySpawnCell(organism, x, y, spawnChance);

            // left
            x = -layer;
            for (y = -layer + 1; y <= layer - 1; y++)
                someCellSpawned = RandomOrganismGenerator.trySpawnCell(organism, x, y, spawnChance);

            // right
            x = layer;
            for (y = -layer + 1; y < layer - 1; y++)
                someCellSpawned = RandomOrganismGenerator.trySpawnCell(organism, x, y, spawnChance);

            if (!someCellSpawned)
                break;
        }

        // randomize the organism's brain
        organism.brain.randomizeDecisions(true);

        return organism;
    }

    // places the starting organisms from EnvironmentParams at seeded random free spots, so the same placement seed (on
    // the same grid and soil) always gives the same layout. Plants only go where the soil lets them grow. add() puts
    // each organism in the world straight away so later ones can't overlap it. Returns how many of each were placed,
    // which can be fewer than asked for if the grid is too crowded. add() also gets the species name to give each
    // seeded species.
    static generateSeeded(env, add) {
        const rand = mulberry32(EnvironmentParams.placementSeed);
        const roles = [
            // role, count, constructor, species name (the file names in seeded species/)
            ['predators', EnvironmentParams.numPredators, RandomOrganismGenerator.createPredator, 'predator'],
            ['prey', EnvironmentParams.numPrey, RandomOrganismGenerator.createSmallPrey, 'prey_small'],
            ['large_prey', EnvironmentParams.numLargePrey, RandomOrganismGenerator.createLargePrey, 'prey_large'],
            ['plants', EnvironmentParams.numPlants, RandomOrganismGenerator.createPlant, 'plant'],
        ];
        const placed = {};
        for (const [role, count, create, species_name] of roles) {
            placed[role] = 0;
            for (let i = 0; i < count; i++) {
                for (let attempt = 0; attempt < RandomOrganismGenerator.placementAttempts; attempt++) {
                    const col = Math.floor(rand() * env.num_cols);
                    const row = Math.floor(rand() * env.num_rows);
                    const rotation = Math.floor(rand() * 4);
                    const direction = Math.floor(rand() * 4);
                    const org = create(env, col, row);
                    if (Hyperparams.rotationEnabled)
                        org.rotation = rotation;
                    org.direction = direction;
                    if (org.isClear(col, row) && org.canGrowAt(col, row)) {
                        add(org, species_name);
                        placed[role]++;
                        break;
                    }
                }
            }
        }
        return placed;
    }

    // the seeded predator: hunts prey and avoids other killers
    static createPredator(env, col, row) {
        const predator = new Organism(col, row, env);
        predator.is_predator = true;
        predator.move_range = 4;
        predator.move_speed = 1;
        predator.direction = Directions.right;

        const a = predator.anatomy;
        a.addDefaultCell(CellStates.mouth, 0, 0);   // centre
        a.addDefaultCell(CellStates.killer, 0, -1);   // left
        a.addDefaultCell(CellStates.mouth, 0, 1);   // right
        a.addDefaultCell(CellStates.mover, -1, 0);   // above centre

        const eyeTop = a.addDefaultCell(CellStates.eye, -2, 0);
        eyeTop.direction = Directions.left;

        const eyeBottom = a.addDefaultCell(CellStates.eye, 1, 0);
        eyeBottom.direction = Directions.right;

        predator.brain.decisions[CellStates.mouth.name] = Brain.Decision.chase;
        predator.brain.decisions[CellStates.mover.name] = Brain.Decision.chase;
        predator.brain.decisions[CellStates.eye.name] = Brain.Decision.chase;
        predator.brain.decisions[CellStates.killer.name] = Brain.Decision.retreat;
        return predator;
    }

    // the classic Life Engine starting plant: a mouth with two diagonal producers
    static createPlant(env, col, row) {
        const plant = new Organism(col, row, env);
        plant.anatomy.addDefaultCell(CellStates.mouth, 0, 0);
        plant.anatomy.addDefaultCell(CellStates.producer, 1, 1);
        plant.anatomy.addDefaultCell(CellStates.producer, -1, -1);
        return plant;
    }

    // the original burrowing prey without its claw, as saved in seeded species/prey_small.json:
    //         mouth
    //  mouth  mover  eye(looking up)
    static createSmallPrey(env, col, row) {
        return RandomOrganismGenerator.fromSaved(SMALL_PREY, env, col, row);
    }

    // a larger prey with no claw (two eyes, six mouths around a mover), saved in seeded species/prey_large.json
    static createLargePrey(env, col, row) {
        return RandomOrganismGenerator.fromSaved(LARGE_PREY, env, col, row);
    }

    // an organism saved from the editor (body, brain, mutability, birth distance), placed at col, row
    static fromSaved(raw, env, col, row) {
        const org = new Organism(col, row, env);
        org.loadRaw(raw);
        org.c = col;
        org.r = row;
        return org;
    }

    static trySpawnCell(organism, x, y, spawnChance) {

        var neighbors = organism.anatomy.getNeighborsOfCell(x, y);
        if (neighbors.length && Math.random() < spawnChance) {
            organism.anatomy.addRandomizedCell(CellStates.getRandomLivingType(), x, y);
            return true;
        }
        return false;
    }

}

RandomOrganismGenerator.organismLayers = 4;
RandomOrganismGenerator.cellSpawnChance = 0.75;
RandomOrganismGenerator.placementAttempts = 1000; // random spots tried per starting organism before giving up

module.exports = RandomOrganismGenerator;