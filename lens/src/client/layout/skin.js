// dsh-cdd-lens — Which of the three drawings the graph is rendered as.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/skin',
  factory: (require) => {
    var module = { exports: {} }
    var __skins_tiers_group = require('dsh-cdd-lens/skins/tiers/group')
    var tiered = __skins_tiers_group.tiered

    var SKINS = ['auto', 'tiers', 'pcb', 'flow']

    /**
     * Layers, file boxes, or direction columns — and who decides.
     *
     * All three drawings already exist. Layers read as a call chain: a column
     * per step, wires straight across. File boxes read as a board: anchors
     * grouped by the file that holds them, traces merged into buses and hopped
     * over each other where they cross. Flow reads as direction: a column per
     * BFS step of the call graph with the wire corridors reserved between the
     * columns. Which one is right depends on the question being asked.
     *
     * `auto` keeps the old rule — layers when `/chain` has assigned every node
     * a layer, file boxes when it has not. `tiers` asks for layers and falls
     * back to the board when no layer was assigned, because drawing half of
     * each is worse than either alone. `pcb` and `flow` need nothing the graph
     * does not always have, so they are honoured as asked.
     *
     * @param graph - the graph about to be drawn.
     * @param included - the ids on screen.
     * @param wanted - 'auto' | 'tiers' | 'pcb' | 'flow'.
     * @returns the skin to lay out with: 'tiers' | 'pcb' | 'flow'.
     */
    function skinFor(graph, included, wanted) {
      if (wanted === 'pcb') return 'pcb'
      if (wanted === 'flow') return 'flow'
      var canLayer = tiered(graph, included)
      if (wanted === 'tiers') return canLayer ? 'tiers' : 'pcb'
      return canLayer ? 'tiers' : 'pcb'
    }

    /** The question older callers still ask: layers, or file boxes. */
    function byLayerFor(graph, included, wanted) {
      return skinFor(graph, included, wanted) === 'tiers'
    }

    module.exports = { SKINS, skinFor, byLayerFor }
    return module.exports
  },
})
