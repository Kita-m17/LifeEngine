const Hyperparams = require("../../Hyperparameters");
const Directions = require("../Directions");
const CellStates = require("../Cell/CellStates");

const Decision = {
    neutral: 0,
    retreat: 1,
    chase: 2,
    getRandom: function(){
        return Math.floor(Math.random() * 3);
    },
    getRandomNonNeutral: function() {
        return Math.floor(Math.random() * 2)+1;
    }
}

class Brain {
    constructor(owner){
        this.owner = owner;
        this.observations = [];

        // corresponds to CellTypes
        this.decisions = {};
        for (let cell of CellStates.all) {
            this.decisions[cell.name] = Decision.neutral;
        }
        this.decisions[CellStates.food.name] = Decision.chase;
        this.decisions[CellStates.killer.name] = Decision.retreat;
    }

    copy(brain) {
        for (let dec in brain.decisions) {
            this.decisions[dec] = brain.decisions[dec];
        }
    }

    randomizeDecisions(randomize_all=false) {
        // randomize the non obvious decisions
        if (randomize_all) {
            this.decisions[CellStates.food.name] = Decision.getRandom();
            this.decisions[CellStates.killer.name] = Decision.getRandom();
        }
        this.decisions[CellStates.mouth.name] = Decision.getRandom();
        this.decisions[CellStates.producer.name] = Decision.getRandom();
        this.decisions[CellStates.mover.name] = Decision.getRandom();
        this.decisions[CellStates.armor.name] = Decision.getRandom();
        this.decisions[CellStates.eye.name] = Decision.getRandom();
    }

    observe(observation) {
        this.observations.push(observation);
    }

    decide() {
        var decision = Decision.neutral;
        var closest = Hyperparams.lookRange + 1;
        var move_direction = 0;
        for (var obs of this.observations) {
            if (obs.cell == null || obs.cell.owner == this.owner) {
                continue;
            }

            const other = obs.cell.owner;
            if (this.owner.is_predator) {
                if (other && other.is_prey && other.living && !other.isHidden() && obs.distance < closestPreyDistance) {
                    closestPreyDistance = obs.distance;
                    preyDirection = obs.direction;
                }
                continue;
            }
            if (this.owner.is_prey) {
                if (other && other.is_predator && obs.distance <= 2 &&
                    obs.distance < closestPredatorDistance) {
                    closestPredatorDistance = obs.distance;
                    predatorDirection = obs.direction;
                }
                else if (obs.cell.state == CellStates.food && obs.distance < closestFoodDistance) {
                    closestFoodDistance = obs.distance;
                    foodDirection = obs.direction;
                }
                continue;
            }

            if (obs.distance < closest) {
                decision = this.decisions[obs.cell.state.name];
                move_direction = obs.direction;
                closest = obs.distance;
            }
        }
        this.observations = [];
        if (decision == Decision.chase) {
            this.owner.changeDirection(move_direction);
            return true;
        }
        else if (decision == Decision.retreat) {
            this.owner.changeDirection(Directions.getOppositeDirection(move_direction));
            return true;
        }
        return false;
    }

    mutate() {
        this.decisions[CellStates.getRandomName()] = Decision.getRandom();
        this.decisions[CellStates.empty.name] = Decision.neutral; // if the empty cell has a decision it gets weird
    }
    
    serialize() {
        return {decisions: this.decisions};
    }
}

Brain.Decision = Decision;

module.exports = Brain;