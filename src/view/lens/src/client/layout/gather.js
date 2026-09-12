// dsh-cdd-lens — The gather overlay: a selected node's neighbours at its side.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/gather',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared

    /** Does a sit on top of b? */
    function overlapping(a, b, margin) {
      return Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) + margin > 0
        && Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) + margin > 0
    }

    /**
     * A node the user dragged out of a running gather is free of both the
     * overlay and its frame.
     *
     * The overlay re-seats its nodes on every layout — which is what made a
     * gathered card undraggable: moveNode wrote the coordinate, the next
     * layout put the card straight back beside the focus, and the wires never
     * saw it move. engine/selection marks the dragged id in gather.freed;
     * here that mark strips the frame membership before restackBoxes can seat
     * the card again, and applyGather below leaves it where it was dropped.
     * Releasing the gather clears the mark, and the next layout seats the
     * node exactly as if none of this had happened.
     *
     * @param place - the positioned nodes, marked in place.
     * @returns how many nodes are freed.
     */
    function freeGatherDragged(place) {
      var gather = shared.gather
      if (gather === null || gather === undefined || gather.freed === undefined) return 0
      var freed = 0
      place.placed.forEach(function (p) {
        if (gather.freed[p.id] !== true) return
        p.boxKey = undefined
        freed += 1
      })
      return freed
    }

    /**
     * Pull the selected node's callers to its left and its callees to its
     * right, as two columns hugging it.
     *
     * An overlay, not a placement: it runs after the skin, the hand-placed
     * coordinates and the restack have all had their say, and it wins over
     * them, because a node whose neighbours sit two screens away answers the
     * one question the drawing exists for — what does this touch — only if
     * you can see them. Nothing is recorded for the trip back. The override
     * is recomputed from scratch on every layout, so releasing it is simply
     * running the same layout without it: wherever the skin and the user say
     * the nodes stand NOW is where they return to, and a drag or an expansion
     * mid-gather can never resurrect a stale coordinate as a ghost.
     *
     * The edge-focus camera is itself an answer to "what is around this
     * relation"; gathering on top of it would rearrange the chain it is
     * showing, so the overlay steps aside while it is active.
     *
     * @param graph - the graph being drawn.
     * @param place - the positioned nodes, moved in place.
     * @param metrics - box metrics; the column gap and spacing come from it.
     * @returns how many nodes were moved.
     */
    function applyGather(graph, place, metrics) {
      var gather = shared.gather
      if (gather === null || gather === undefined) return 0
      if (shared.edgeFocus !== null && shared.edgeFocus !== undefined) return 0
      var byId = {}
      place.placed.forEach(function (p) { byId[p.id] = p })
      var focus = byId[gather.focus]
      if (focus === undefined) return 0

      // A node that is both caller and callee keeps one seat — the upstream
      // one, since that is the side that explains where it came from.
      var seen = {}
      var ups = []
      var downs = []
      graph.edges.forEach(function (e) {
        if (e.to === gather.focus && e.from !== gather.focus
          && byId[e.from] !== undefined && seen[e.from] !== true) {
          seen[e.from] = true
          ups.push(byId[e.from])
        }
        if (e.from === gather.focus && e.to !== gather.focus
          && byId[e.to] !== undefined && seen[e.to] !== true) {
          seen[e.to] = true
          downs.push(byId[e.to])
        }
      })

      var GAP = metrics.LAYER_GAP_X
      var INNER_GAP_Y = metrics.INNER_GAP_Y
      var NEAR = metrics.PORT_STUB
      var freed = gather.freed || {}
      var moved = 0
      var seated = []

      var seatColumn = function (nodes, rightward) {
        if (nodes.length === 0) return
        // In the order they already stand, top to bottom: the gather moves
        // them as little as it can.
        var ordered = nodes.slice().sort(function (l, r) { return l.y - r.y || l.x - r.x })
        var total = ordered.reduce(function (acc, p) { return acc + p.h }, 0)
          + INNER_GAP_Y * (ordered.length - 1)
        var y = focus.y + focus.h / 2 - total / 2
        ordered.forEach(function (p) {
          // Dragged out of the column by the user mid-gather: it stays where
          // it was dropped and takes no seat here.
          if (freed[p.id] === true) return
          var x = rightward ? focus.x + focus.w + GAP : focus.x - GAP - p.w
          var y0 = y
          y += p.h + INNER_GAP_Y
          // Already there, near enough: an animation about nothing is noise.
          if (Math.abs(p.x - x) < NEAR && Math.abs(p.y - y0) < NEAR) return
          p.x = x
          p.y = y0
          p.gathered = true
          // Out of its frame: the frame would otherwise restack it straight
          // back into its old slot on this very pass.
          p.boxKey = undefined
          // Re-stamped with the column it now stands in. The flow router
          // reads its corridors off flowLayer, and a card beside the focus
          // that still claims its old layer would be routed to through the
          // corridors of a column it no longer occupies — the long way round
          // that this overlay exists to abolish.
          if (typeof focus.flowLayer === 'number') {
            p.flowLayer = focus.flowLayer + (rightward ? 1 : -1)
          }
          seated.push(p)
          moved += 1
        })
      }
      seatColumn(ups, false)
      seatColumn(downs, true)

      // What a gathered node may not land on: the focus, and every node that
      // stays in its frame — read AFTER the seating stripped the movers, or a
      // moved node would collide with the ghost of where it stood. The frames
      // own their columns — restackBoxes puts their members back every layout —
      // so the gathered column gives way vertically instead of asking the
      // frame to move.
      var solid = place.placed.filter(function (p) { return p.boxKey !== undefined })
      // Frames do not move, so where the column lands on one, the column
      // slides down past whatever stands there — the focus stays the anchor
      // horizontally, and the hug stays readable even when the column grows
      // longer than the space beside the focus.
      seated.forEach(function (p) {
        var guard = 0
        var hit = true
        while (hit && guard < 50) {
          hit = false
          guard += 1
          for (var i = 0; i < solid.length; i += 1) {
            if (overlapping(p, solid[i], 1)) {
              p.y = solid[i].y + solid[i].h + INNER_GAP_Y
              hit = true
            }
          }
          for (var k = 0; k < seated.length; k += 1) {
            if (seated[k] !== p && overlapping(p, seated[k], 1)) {
              p.y = seated[k].y + seated[k].h + INNER_GAP_Y
              hit = true
            }
          }
        }
      })
      return moved
    }

    module.exports = { applyGather, freeGatherDragged }
    return module.exports
  },
})
