const FossilRecord = require("../FossilRecord");
const ChartController = require("./ChartController");
const Hyperparams = require("../../Hyperparameters");

// the role filter in #claw-role: which roles each option covers
const CLAW_GROUPS = {
    all: {label: "All Organisms", roles: FossilRecord.ROLES},
    Plants: {label: "Plants", roles: ['Plants']},
    Predators: {label: "Predators", roles: ['Predators']},
    Prey: {label: "Prey", roles: ['Prey (burrowing)', 'Prey (non-burrowing)']},
};

class BurrowSoilChart extends ChartController {
    constructor(panel) {
        let group = CLAW_GROUPS[panel.claw_role] || CLAW_GROUPS.all;
        super("Burrowing & Soil Health: " + group.label,
            "Organisms",
            "With claw cells is how many organisms in the group have at least one claw cell, and have burrowed is how many " +
            "of those have hidden underground at least once in their life. The gap between the two is claws carried without " +
            "being used to burrow (only prey burrow, so claws on plants and predators are never used). Underground is how many " +
            "are hidden when sampled. Soil (right axis) is average fertility as a % of the maximum, and degraded tiles are " +
            "those below half the starting average.");
        this.roles = group.roles;
        this.chart.options.axisY2 = {
            title: "Soil (%)",
            minimum: 0,
            maximum: 100,
        };
    }

    setData() {
        this.clear();
        let series = [
            ["population", "Population", '#7f7f7f', "primary"],
            ["with_claw", "With claw cells", '#8c564b', "primary"],
            ["ever_burrowed", "With claw cells that have burrowed", '#e377c2', "primary"],
            ["hidden", "Underground", '#9467bd', "primary"],
            ["soil_mean", "Avg. soil fertility (%)", '#2ca02c', "secondary"],
            ["soil_degraded", "Degraded tiles (%)", '#ff7f0e', "secondary"],
        ];
        for (let [name, legend, color, axis] of series) {
            this.data.push({
                type: "line",
                markerType: "none",
                lineDashType: name === "soil_degraded" ? "dash" : "solid",
                lineThickness: name === "population" ? 1 : 2,
                color: color,
                showInLegend: true,
                axisYType: axis,
                name: name,
                legendText: legend,
                dataPoints: []
            });
        }
        this.addAllDataPoints();
    }

    // sums a field over the selected roles; null for samples recorded before the field existed
    groupTotal(sample, field) {
        if (!sample || !sample.role) return null;
        let total = 0;
        for (let role of this.roles) {
            let g = sample.role[role];
            if (!g) continue;
            if (g[field] === undefined) return null;
            total += g[field];
        }
        return total;
    }

    addDataPoint(i) {
        var t = FossilRecord.tick_record[i];
        var sample = FossilRecord.group_samples[i];
        var soil = FossilRecord.soil_means[i];
        var degraded = FossilRecord.soil_degraded_fracs[i];
        this.data[0].dataPoints.push({x:t, y:this.groupTotal(sample, 'pop')});
        this.data[1].dataPoints.push({x:t, y:this.groupTotal(sample, 'with_claw')});
        this.data[2].dataPoints.push({x:t, y:this.groupTotal(sample, 'ever_burrowed')});
        this.data[3].dataPoints.push({x:t, y:this.groupTotal(sample, 'hidden')});
        this.data[4].dataPoints.push({x:t, y:soil === null || soil === undefined ? null : 100 * soil / Hyperparams.maxFertility});
        this.data[5].dataPoints.push({x:t, y:degraded === null || degraded === undefined ? null : 100 * degraded});
    }
}

module.exports = BurrowSoilChart;
