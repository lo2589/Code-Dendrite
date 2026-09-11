// dsh-cdd-lens — The flow skin: one column per layer the index assigned.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/skins/flow/group',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * One column per layer, callers left of callees, with the corridor
     * between two columns reserved for the wires at placement time.
     *
     * The layer is not computed here. The host side derives it from the edge
     * tables — DFS finish order, then longest-path relaxation — and sends it
     * down on every node as `node.layer` (engine/fetch seats it there), which
     * is also what the tiers skin reads. Recomputing it client-side from the
     * edges that happen to be visible answered a different question: how the
     * drawing is wired, not how deep into the data a node sits.
     *
     * A node without a layer — or with no edge on screen at all, which is the
     * shape an island arrives in — shares one trailing column rather than
     * forcing the whole drawing to fall back. The corridor between two columns
     * is metrics.LAYER_GAP_X wide, reserved at placement time the way elk's
     * layered layout reserves it: room for an exit badge, an entry badge, and
     * the lanes between them. skins/flow/route is written against that
     * reservation.
     *
     * @param graph - the graph being drawn.
     * @param scope - what is on screen.
     * @param metrics - box metrics for this canvas.
     * @returns placed nodes, one labelled frame per column, and how far down
     *   the drawing reaches — the same shape the other two skins return.
     */
    function placeFlow(graph, scope, metrics) {
      var included = scope.included
      var PAD = metrics.PAD
      var NODE_W = metrics.NODE_W
      var LAYER_GAP_X = metrics.LAYER_GAP_X
      var BOX_PAD = metrics.BOX_PAD
      var BOX_HEAD = metrics.BOX_HEAD
      var INNER_GAP_Y = metrics.INNER_GAP_Y
      var sizeOf = metrics.sizeOf
      // A shallow margin above the columns so a wire crossing a column over
      // its first node has room that belongs to no node.
      var TOP_BAND = BOX_HEAD

      // Which nodes carry a layer at all — the same typeof check the layered
      // skin's `tiered` makes — and which of those the visible edges actually
      // touch. A node with neither goes to the trailing column.
      var includedSet = {}
      included.forEach(function (id) { includedSet[id] = true })
      var linked = {}
      graph.edges.forEach(function (edge) {
        if (includedSet[edge.from]) linked[edge.from] = true
        if (includedSet[edge.to]) linked[edge.to] = true
      })
      var seated = {}
      var maxLayer = -1
      included.forEach(function (id) {
        var node = graph.nodes[id]
        if (typeof node.layer !== 'number' || linked[id] !== true) return
        seated[id] = true
        if (node.layer > maxLayer) maxLayer = node.layer
      })
      var restLayer = maxLayer + 1
      var flowLayerOf = function (id) {
        return seated[id] === true ? graph.nodes[id].layer : restLayer
      }

      var byLayer = {}
      var columns = []
      included.forEach(function (id) {
        var L = flowLayerOf(id)
        if (byLayer[L] === undefined) { byLayer[L] = []; columns.push(L) }
        byLayer[L].push(id)
      })
      columns.sort(function (l, r) { return l - r })
      var colIndex = {}
      columns.forEach(function (L, i) { colIndex[L] = i })

      // One chain's nodes keep together: tree first, then the name. The
      // trailing column holds whatever the layering did not seat, in plain
      // symbol order — and stays in it; nothing routes to it, so ordering it
      // by wires would be noise.
      columns.forEach(function (L) {
        byLayer[L].sort(function (l, r) {
          var ln = graph.nodes[l]
          var rn = graph.nodes[r]
          var lt = L === restLayer ? 0 : (typeof ln.tree === 'number' ? ln.tree : 0)
          var rt = L === restLayer ? 0 : (typeof rn.tree === 'number' ? rn.tree : 0)
          return lt - rt || ln.anchor.symbol.localeCompare(rn.anchor.symbol)
        })
      })

      var size = {}
      included.forEach(function (id) { size[id] = sizeOf(id) })

      // ---- barycenter sweep -------------------------------------------------
      //
      // The order inside a column decides how often the wires cross: the
      // corridor router gives every wire its own lane, but a lane change still
      // costs a bend, and a fan of inverted pairs crosses however it is laned.
      // Which is to say the wiring has to participate in the placement — the
      // thing dagre and elk's layered layout both do and this column order did
      // not. So after the data order above, each column is re-sorted by where
      // its neighbours in the adjacent columns actually stand: a node sinks or
      // rises to the mean height of the anchors its edges lead to and come
      // from. A node with no edge into a neighbouring column, and any tie,
      // keeps the seat it had — the sweep may settle the picture, never
      // shuffle it.
      var adj = {}
      included.forEach(function (id) { adj[id] = [] })
      graph.edges.forEach(function (edge) {
        if (!includedSet[edge.from] || !includedSet[edge.to]) return
        if (Math.abs(colIndex[flowLayerOf(edge.from)] - colIndex[flowLayerOf(edge.to)]) !== 1) return
        adj[edge.from].push(edge.to)
        adj[edge.to].push(edge.from)
      })
      var yOf = {}
      var layColumn = function (ids) {
        var y = PAD + TOP_BAND
        ids.forEach(function (id) {
          yOf[id] = y
          y += size[id].h + INNER_GAP_Y
        })
      }
      columns.forEach(function (L) { layColumn(byLayer[L]) })
      var sweepColumn = function (L) {
        if (L === restLayer) return
        var keyed = byLayer[L].map(function (id, at) {
          var ns = adj[id]
          var key = yOf[id] + size[id].h / 2
          if (ns.length > 0) {
            var sum = 0
            ns.forEach(function (n) { sum += yOf[n] + size[n].h / 2 })
            key = sum / ns.length
          }
          return { id: id, key: key, at: at }
        })
        keyed.sort(function (l, r) { return l.key - r.key || l.at - r.at })
        byLayer[L] = keyed.map(function (k) { return k.id })
        layColumn(byLayer[L])
      }
      // One direction at a time, each column seated before the next is read.
      // Sweeping every column from one shared snapshot settles nothing: both
      // sides of a crossed fan flip together and the crossings survive the
      // flip. Left to right and back is one round; two rounds settle the fans
      // this drawing actually grows.
      var SWEEPS = 2
      for (var sweep = 0; sweep < SWEEPS; sweep += 1) {
        columns.forEach(sweepColumn)
        columns.slice().reverse().forEach(sweepColumn)
      }

      var placed = []
      var boxes = []
      var canvasY = PAD
      columns.forEach(function (L) {
        var ids = byLayer[L]
        var col = colIndex[L]
        var x = PAD + col * (NODE_W + LAYER_GAP_X)
        var y = PAD + TOP_BAND
        ids.forEach(function (id, row) {
          var node = graph.nodes[id]
          placed.push({
            id: id, node: node, anchor: node.anchor,
            // One width for every node, whatever its name measures at: equal
            // cells are what keep the corridors between the columns straight,
            // and the corridors are what the router promises are empty.
            x: x, y: y, w: NODE_W, h: size[id].h,
            rowIndex: row, innerRow: row,
            file: node.anchor.file, island: L === restLayer,
            // Which frame this anchor belongs to, so the frame can follow it.
            boxKey: 'L' + L,
            layer: node.layer, tree: node.tree,
            // The column this skin put it in. The router reads this rather
            // than the x coordinate, which a dragged node no longer agrees
            // with.
            flowLayer: L,
            label: metrics.label[id],
          })
          y += size[id].h + INNER_GAP_Y
        })
        boxes.push({
          file: L === restLayer ? '未入链 · ' + ids.length : 'L' + L + ' · ' + ids.length,
          key: 'L' + L,
          // Marked, so the canvas can draw a column guide rather than a box:
          // the flow frame is a reading aid, not a container.
          frame: 'flow',
          x: x - BOX_PAD, y: PAD + TOP_BAND - BOX_HEAD,
          w: NODE_W + BOX_PAD * 2,
          h: (y - INNER_GAP_Y) - (PAD + TOP_BAND) + BOX_HEAD + BOX_PAD,
          count: ids.length,
        })
        var bottom = y - INNER_GAP_Y + BOX_PAD
        if (bottom > canvasY) canvasY = bottom
      })

      // No rowBands: the channels this skin routes through run between the
      // columns, and layout/channels derives horizontal bands from rows this
      // drawing does not have.
      return { placed: placed, fileBoxes: boxes, rowBands: [], rows: [], canvasY: canvasY }
    }

    module.exports = { placeFlow }
    return module.exports
  },
})
