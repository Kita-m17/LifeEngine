// Stands in for the canvas Renderer when the world runs without a page (headless/run.js): it keeps the
// properties the environment reads and draws nothing
class NullRenderer {
    constructor(cell_size) {
        this.cell_size = cell_size;
        this.cells_to_render = new Set();
        this.cells_to_highlight = new Set();
        this.highlighted_cells = new Set();
    }

    fillWindow() {}
    fillShape() {}
    clear() {}
    renderFullGrid() {}
    renderCells() {}
    renderHighlights() {}
    addToRender() {}
}

module.exports = NullRenderer;
