// dsh-cdd-lens — The board skin: what belongs in a box.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/skins/pcb/group',
  factory: (require) => {
    var module = { exports: {} }
    var __layout_grid = require('dsh-cdd-lens/layout/grid')
    var placeGroups = __layout_grid.placeGroups

    /**
     * One box per file, in the order the ranking put the files.
     *
     * The grid is shared with the layered skin; only this — what a box holds —
     * is the board skin's own. A file is the unit here because a trace between
     * two files is the thing worth seeing on a board.
     */
    function placeBoxes(graph, scope, metrics) {
      var byFile = scope.byFile
      var groups = scope.fileOrder.map(function (file) {
        return { key: file, label: file, ids: byFile[file] }
      })
      var laid = placeGroups(graph, groups, metrics)
      return {
        placed: laid.placed, fileBoxes: laid.boxes,
        rowBands: laid.rowBands, canvasY: laid.canvasY,
      }
    }

    module.exports = { placeBoxes }
    return module.exports
  },
})
