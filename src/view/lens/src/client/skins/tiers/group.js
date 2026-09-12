// dsh-cdd-lens — The layered skin: what belongs in a box.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/skins/tiers/group',
  factory: (require) => {
    var module = { exports: {} }
    var __layout_grid = require('dsh-cdd-lens/layout/grid')
    var placeGroups = __layout_grid.placeGroups

    /**
     * Whether this drawing can be laid out by layer at all.
     *
     * `/chain` puts a layer on every node it reached. If it has not answered
     * yet, or answered for a different exploration than the one on screen, the
     * old file-box placement still has to be able to take over — a half-layered
     * picture would be worse than either.
     * @param graph - the graph being drawn.
     * @param included - the ids that will be drawn.
     * @returns true when every included node knows its layer.
     */
    function tiered(graph, included) {
      if (included.length === 0) return false
      return included.every(function (id) {
        var node = graph.nodes[id]
        return node !== undefined && typeof node.layer === 'number'
      })
    }

    /**
     * One vertical band per layer, trees stacked in the order `/chain` ranked
     * them.
     *
     * No file boxes. Grouping by file is what turned this view into the
     * directory listing next to it: a file is where an anchor is stored, not
     * what it has to do with anything else. The row an anchor sits in is its
     * distance from the thing that was edited, which is the question the
     * picture exists to answer.
     * @param graph - the graph being drawn.
     * @param scope - what is on screen.
     * @param metrics - box metrics for this canvas.
     * @returns placed nodes, the row bands wires travel between, the labelled
     *   rows, and how far down the drawing reaches.
     */
    function placeTiers(graph, scope, metrics) {
      var included = scope.included

      // One box per layer of one tree — the same grid the board drawing uses,
      // grouped by a different thing. Packing blocks of varying width onto
      // shelves instead gave irregular spacing that read as clutter however
      // well the wires were routed, so there is now one placement and two ways
      // of deciding what belongs in a box.
      var bands = {}
      var order = []
      included.forEach(function (id) {
        var node = graph.nodes[id]
        var tree = typeof node.tree === 'number' ? node.tree : 0
        var key = tree + ':' + node.layer
        if (bands[key] === undefined) {
          bands[key] = { tree: tree, layer: node.layer, ids: [] }
          order.push(key)
        }
        bands[key].ids.push(id)
      })
      order.sort(function (l, r) {
        return bands[l].tree - bands[r].tree || bands[l].layer - bands[r].layer
      })

      var groups = order.map(function (key) {
        var band = bands[key]
        // Anchors the session touched lead their box: they are why the rest of
        // it is on screen at all.
        band.ids.sort(function (l, r) {
          var ln = graph.nodes[l], rn = graph.nodes[r]
          return (ln.seed === true ? 0 : 1) - (rn.seed === true ? 0 : 1)
            || ln.anchor.symbol.localeCompare(rn.anchor.symbol)
        })
        return {
          key: key,
          label: 'T' + (band.tree + 1) + ' · L' + band.layer + ' · ' + band.ids.length,
          ids: band.ids,
        }
      })

      var laid = placeGroups(graph, groups, metrics)
      return {
        placed: laid.placed, fileBoxes: laid.boxes, rowBands: laid.rowBands,
        // The box header carries the layer's name, so there is no separate
        // row label to draw beside it any more.
        rows: [], canvasY: laid.canvasY,
      }
    }

    module.exports = { tiered, placeTiers }
    return module.exports
  },
})
