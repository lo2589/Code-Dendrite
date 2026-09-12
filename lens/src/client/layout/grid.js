// dsh-cdd-lens — One grid of boxes, whatever the boxes are grouped by.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/grid',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * Boxes in rows, anchors down each box.
     *
     * The board drawing had this and the layered one did not: equal-width
     * boxes, as many across as the canvas allows, each row as tall as its
     * tallest box, a gutter between them for the traces. The layered drawing
     * packed its own way instead — blocks of varying width shelved left to
     * right — and the result was a field of cards at irregular spacing that
     * read as clutter no matter how well the wires were routed.
     *
     * So both now come through here. What differs between them is only what a
     * box means: one file, or one layer of one tree.
     *
     * @param graph - source of the node records.
     * @param groups - ordered [{ key, label, ids }]; one box each.
     * @param metrics - box metrics.
     * @returns placed anchors, the boxes around them, the row bands the
     *   gutters sit between, and how far down the drawing reaches.
     */
    function placeGroups(graph, groups, metrics) {
      var PAD = metrics.PAD
      var BOX_GAP_X = metrics.BOX_GAP_X
      var BOX_GAP_Y = metrics.BOX_GAP_Y
      var BOX_PAD = metrics.BOX_PAD
      var BOX_HEAD = metrics.BOX_HEAD
      var BOX_W = metrics.BOX_W
      var BOX_COLS = metrics.BOX_COLS
      var INNER_GAP_Y = metrics.INNER_GAP_Y
      var sizeOf = metrics.sizeOf

      var placed = []
      var boxes = []
      var rowBands = []
      var canvasY = PAD

      // Each box is as wide as the longest name it holds, and every anchor in
      // it is drawn to that width. Sized one by one they came out ragged: seven
      // different right edges in one box, and the exit badges that follow those
      // edges strung out in a zigzag instead of a column. Sized from the longest
      // name on the whole screen — which is what the board plugin does — a box
      // of short names is padded out to match some other box's longest.
      var innerOf = {}
      groups.forEach(function (group) {
        innerOf[group.key] = Math.max.apply(Math, group.ids.map(function (id) {
          return sizeOf(id).w
        }))
      })
      // Spaced by the widest box, so no box can reach into the next column
      // however long its own names are — and by that alone. Spreading the
      // columns to the full width of the canvas left two boxes marooned at
      // opposite edges with a screen of nothing between them; the gutter only
      // has to hold the exit badge of one column, the entry badge of the next,
      // and the wire that joins them, which is what LAYER_GAP_X measures.
      var widest = Math.max.apply(Math, groups.map(function (group) {
        return innerOf[group.key] + BOX_PAD * 2
      }))
      var stride = widest + metrics.LAYER_GAP_X

      for (var start = 0; start < groups.length; start += BOX_COLS) {
        var inRow = groups.slice(start, start + BOX_COLS)
        var layouts = inRow.map(function (group, col) {
          var inner = innerOf[group.key]
          // One anchor per row. Two columns made every box twice as wide, which
          // pushed the boxes apart, which made every wire longer — the width
          // was spent on emptiness and paid for in travel.
          var height = 0
          group.ids.forEach(function (id, i) {
            height += sizeOf(id, inner).h + (i === group.ids.length - 1 ? 0 : INNER_GAP_Y)
          })
          return {
            group: group, inner: inner,
            x: PAD + col * stride,
            w: inner + BOX_PAD * 2,
            h: BOX_HEAD + BOX_PAD + height + BOX_PAD,
          }
        })
        var rowHeight = Math.max.apply(Math, layouts.map(function (box) { return box.h }))
        layouts.forEach(function (box) {
          boxes.push({
            file: box.group.label, key: box.group.key,
            x: box.x, y: canvasY, w: box.w, h: box.h, count: box.group.ids.length,
          })
          var nodeY = canvasY + BOX_HEAD + BOX_PAD
          box.group.ids.forEach(function (id, localRow) {
            var size = sizeOf(id, box.inner)
            var node = graph.nodes[id]
            placed.push({
              id: id, node: node, anchor: node.anchor,
              x: box.x + BOX_PAD, y: nodeY, w: box.inner, h: size.h,
              rowIndex: start + localRow, innerRow: localRow,
              file: node.anchor.file, island: false,
              // Which frame this anchor belongs to, so the frame can follow it.
              boxKey: box.group.key,
              layer: node.layer, tree: node.tree,
              label: metrics.label[id],
            })
            nodeY += size.h + INNER_GAP_Y
          })
        })
        rowBands.push({ top: canvasY, bottom: canvasY + rowHeight })
        canvasY += rowHeight + BOX_GAP_Y
      }

      return { placed: placed, boxes: boxes, rowBands: rowBands, canvasY: canvasY }
    }

    module.exports = { placeGroups }
    return module.exports
  },
})
