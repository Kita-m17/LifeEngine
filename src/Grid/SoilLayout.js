const Hyperparams = require('../Hyperparameters.js');
const createSeededPerlin = require('../Utils/SeededPerlin.js');

/*
    Generates fertile patches connected by permanently infertile pathways, using a seeded
    noise generator so the same inputs always produce the same layout - needed so the group
    can reuse fixed observation layouts instead of a different random one every run.
    Shared by the browser world and the headless runner, so both lay out soil identically.

    seed - fixes the exact noise pattern. Same seed = same layout, every time.
    patch_threshold - cutoff on the noise value: a cell with noise above this becomes a
                    fertile patch, at or below it becomes a permanently infertile pathway
                    (fertility cap = 0). Raise this for smaller/sparser patches with wider
                    pathways; lower it for bigger, more connected fertile regions.
    resolution - how many noise "bumps" get stretched across the whole grid. Lower
                values give fewer, larger patches; higher values give many small,
                scattered ones.
*/
function generateSoil(grid_map, seed, patch_threshold=0, resolution=20) {
    let noise_gen = createSeededPerlin(seed);
    let cols = grid_map.cols;
    let rows = grid_map.rows;
    let cell_size = grid_map.cell_size;

    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {

            //map this cell's grid position into noise-space coordinates
            let xval = c/cols*(resolution/cell_size*(cols/rows));
            let yval = r/rows*(resolution/cell_size*(rows/cols));
            let noise = noise_gen.get(xval, yval); // noise value, roughly centered around 0

            //above threshold = fertile patch, otherwise a permanently infertile pathway
            let cap = noise > patch_threshold ? Hyperparams.maxFertility : 0;

            grid_map.setCellFertilityCap(c, r, cap); //the permanent ceiling for this cell
            grid_map.setCellFertility(c, r, cap); //start the cell's live fertility at that ceiling
        }
    }
}

module.exports = generateSoil;
