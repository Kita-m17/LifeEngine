const CellStates = require("./Cell/CellStates");
const Organism = require("./Organism");
const Brain = require("./Perception/Brain")
const Directions = require("./Directions");
const Hyperparams = require("../Hyperparameters");
const EnvironmentParams = require("../EnvironmentParams");
const {mulberry32} = require("../Utils/SeededPerlin");

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
    // which can be fewer than asked for if the grid is too crowded.
    static generateSeeded(env, add) {
        const rand = mulberry32(EnvironmentParams.placementSeed);
        const roles = [
            ['predators', EnvironmentParams.numPredators, RandomOrganismGenerator.createPredator],
            ['claw_prey', EnvironmentParams.numClawPrey, RandomOrganismGenerator.createClawPrey],
            ['prey', EnvironmentParams.numPrey, RandomOrganismGenerator.createPrey],
            ['plants', EnvironmentParams.numPlants, RandomOrganismGenerator.createPlant],
        ];
        const placed = {};
        for (const [role, count, create] of roles) {
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
                        add(org);
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

    // prey around a central mover, the same body as the burrowing prey minus the claw:
    //         mouth
    //  mouth  mover  eye(looking up)
    static createPrey(env, col, row, direction=Directions.left) {
        const prey = RandomOrganismGenerator.newPrey(env, col, row, direction);
        prey.anatomy.addDefaultCell(CellStates.mover, 0, 0);
        const preyEye = prey.anatomy.addDefaultCell(CellStates.eye, 1, 0);
        preyEye.direction = Directions.up;
        prey.anatomy.addDefaultCell(CellStates.mouth, 0, -1);
        prey.anatomy.addDefaultCell(CellStates.mouth, -1, 0);
        prey.brain.decisions[CellStates.killer.name] = Brain.Decision.retreat;
        return prey;
    }

    // cross-shaped burrowing prey: the regular prey with a claw underneath
    //         mouth
    //  mouth  mover  eye(looking up)
    //         claw
    static createClawPrey(env, col, row) {
        const prey = RandomOrganismGenerator.createPrey(env, col, row, Directions.right);
        prey.anatomy.addDefaultCell(CellStates.claw, 0, 1);
        return prey;
    }

    static newPrey(env, col, row, direction) {
        const prey = new Organism(col, row, env);
        prey.is_prey = true;
        prey.move_range = 4;
        prey.move_speed = 1;
        prey.direction = direction;
        return prey;
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