// dsh-cdd-lens — The flow skin: wires that live in the corridors the columns reserved.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/skins/flow/route',
  factory: (require) => {
    var module = { exports: {} }
    var __routing_hops = require('dsh-cdd-lens/routing/hops')
    var markHops = __routing_hops.markHops
    var __routing_emit = require('dsh-cdd-lens/routing/emit')
    var emitWires = __routing_emit.emitWires
    var __routing_avoid = require('dsh-cdd-lens/routing/avoid')
    var repairCrossings = __routing_avoid.repairCrossings
    var __view_record = require('dsh-cdd-lens/view/record')
    var stateOf = __view_record.stateOf

    /**
     * The column geometry the placement produced, rebuilt from the placed
     * nodes. Columns are keyed by the flowLayer the placement stamped on each
     * node, not by x coordinate: a node the user dragged keeps its layer even
     * where its position no longer agrees with it.
     */
    function columnsOf(orient) {
      var byId = orient.byId
      var byLayer = {}
      var order = []
      Object.keys(byId).forEach(function (id) {
        var p = byId[id]
        var L = typeof p.flowLayer === 'number' ? p.flowLayer : 0
        if (byLayer[L] === undefined) { byLayer[L] = []; order.push(L) }
        byLayer[L].push(p)
      })
      order.sort(function (l, r) { return l - r })
      var index = {}
      var left = []
      var right = []
      var members = []
      order.forEach(function (L, i) {
        index[L] = i
        left[i] = Math.min.apply(Math, byLayer[L].map(function (p) { return p.x }))
        right[i] = Math.max.apply(Math, byLayer[L].map(function (p) { return p.x + p.w }))
        members[i] = byLayer[L].slice().sort(function (l, r) { return l.y - r.y })
      })
      return { index: index, left: left, right: right, members: members, count: order.length }
    }

    /**
     * The heights at which a wire may cross a column without touching a node:
     * the middle of every gap between two stacked nodes, plus the small
     * margins above the first and below the last.
     *
     * This is the other half of the reservation the placement made: the
     * corridor between two columns is where a wire runs vertically, and these
     * gaps are where it may slip horizontally through a column on its way to
     * the next corridor — the staircase an elk-style layered layout builds
     * with dummy nodes, read off the nodes that are already there.
     */
    function gapLanesOf(members, gapY) {
      var lanes = []
      for (var i = 0; i <= members.length; i += 1) {
        if (i === 0) lanes.push(members[0].y - gapY / 2)
        else if (i === members.length) lanes.push(members[i - 1].y + members[i - 1].h + gapY / 2)
        else lanes.push((members[i - 1].y + members[i - 1].h + members[i].y) / 2)
      }
      return lanes
    }

    /**
     * Route the chosen relations through the reserved corridors.
     *
     * A wire only ever runs horizontally where no node stands: inside the
     * corridor between two columns, or through a gap between two nodes of the
     * column it crosses. Four shapes cover every relation:
     *
     *   near — one layer forward: out of the caller's right edge, down the
     *     corridor between the two columns, into the callee's left edge;
     *   same — both ends in one column: out of the right edge, down the
     *     corridor to the right, back into the right edge;
     *   far — several layers forward: a staircase. Down the corridor past the
     *     source to the height of a gap in the next column, across the column
     *     through that gap, down the next corridor, and so on until the
     *     corridor before the target, then in through its left edge;
     *   back — against the direction: the same staircase mirrored, out of the
     *     left edge and into the target's right edge.
     *
     * Earlier the long wires went round the whole drawing instead — up into a
     * band above everything, across the full canvas, and down — and the
     * picture grew a ladder of wires over and under it that said nothing. The
     * staircase keeps a long edge inside the columns it actually crosses.
     *
     * Every vertical run shares its corridor with the other wires that need
     * it, so each gets its own lane inside it, ordered by where it is going.
     * Crossings that remain are marked as hops, and whatever still cuts
     * through a box — possible once the user has dragged nodes out of their
     * columns — is re-routed by the same repair the board skin ends with,
     * whose detours are the only wires that still leave the drawing.
     *
     * @param edges - the relations to draw, from routing/select.
     * @param orient - byId, the placed node for every id.
     * @param relationFilter - relation kinds the viewer left switched on.
     * @param metrics - box metrics; PORT_STUB is the straight run out of a
     *   port, LAYER_GAP_X the corridor the placement reserved.
     * @returns the route (polylines, so a shift can move them) and the drawn
     *   wires, arrowheads and labels.
     */
    function routeFlow(edges, orient, relationFilter, metrics) {
      var byId = orient.byId
      var STUB = metrics.PORT_STUB
      var GAP = metrics.LAYER_GAP_X
      var CORRIDOR_MIN = metrics.CORRIDOR_MIN
      var SUBLANE_STEP = metrics.SUBLANE_STEP
      var cols = columnsOf(orient)

      // The x range a corridor owns. A corridor is named after the column it
      // follows; -1 is the margin left of the first column, which a backward
      // wire out of the first column leaves through. Outside the first and
      // last column the corridor is as wide as the placement promised.
      function corridor(c) {
        var lo = c < 0 ? cols.left[0] - GAP + STUB : cols.right[c] + STUB
        var hi = c < 0 || c >= cols.count - 1
          ? lo + GAP - STUB * 2
          : cols.left[c + 1] - STUB
        // Dragged nodes can pull two columns over each other; a corridor that
        // narrow still answers, and repairCrossings cleans up after it.
        return { lo: lo, hi: Math.max(hi, lo + CORRIDOR_MIN) }
      }

      // Lane requests per corridor, assigned once every wire has asked, so the
      // lanes can be ordered by where each run is headed instead of by which
      // wire asked first.
      var requests = {}
      function ask(c, sort) {
        var r = { sort: sort, x: null }
        ;(requests[c] = requests[c] || []).push(r)
        return r
      }

      var live = []
      edges.chosen.forEach(function (edge) {
        var a = byId[edge.from]
        var b = byId[edge.to]
        if (a === undefined || b === undefined || a === b) return
        ;(edge.types || ['call']).filter(function (type) {
          return relationFilter === undefined || relationFilter[type] !== false
        }).forEach(function (type) {
          live.push({ edge: edge, type: type, a: a, b: b })
        })
      })

      var columnOf = function (p) {
        return cols.index[typeof p.flowLayer === 'number' ? p.flowLayer : 0]
      }
      // Which columns each long wire has to cross, so every crossed column can
      // hand out its gap lanes once all of them are known.
      var crossings = {}
      live.forEach(function (w) {
        var ca = columnOf(w.a)
        var cb = columnOf(w.b)
        var ay = w.a.y + w.a.h / 2
        var by = w.b.y + w.b.h / 2
        w.lanes = {}
        w.crossY = {}
        if (cb === ca + 1) {
          w.kind = 'near'
          w.lanes[ca] = ask(ca, by)
        } else if (cb === ca) {
          w.kind = 'same'
          w.lanes[ca] = ask(ca, (ay + by) / 2)
        } else if (cb > ca + 1) {
          w.kind = 'far'
          for (var c = ca; c <= cb - 1; c += 1) w.lanes[c] = ask(c, by)
          for (var x = ca + 1; x <= cb - 1; x += 1) {
            ;(crossings[x] = crossings[x] || []).push(w)
          }
        } else {
          w.kind = 'back'
          for (var k = cb; k <= ca - 1; k += 1) w.lanes[k] = ask(k, by)
          for (var z = cb + 1; z <= ca - 1; z += 1) {
            ;(crossings[z] = crossings[z] || []).push(w)
          }
        }
      })

      Object.keys(requests).forEach(function (key) {
        var list = requests[key]
        list.sort(function (l, r) { return l.sort - r.sort })
        var corr = corridor(Number(key))
        list.forEach(function (r, i) {
          r.x = corr.lo + (i + 1) * (corr.hi - corr.lo) / (list.length + 1)
        })
      })

      // The gap each wire crosses a column through: the one nearest to where
      // it is going. Wires that share a gap fan out inside it, a few pixels
      // apart — the gap between two nodes is narrow, and a bundle that reads
      // as one strand is better than a wire through a node.
      Object.keys(crossings).forEach(function (key) {
        var c = Number(key)
        var lanes = gapLanesOf(cols.members[c], metrics.INNER_GAP_Y)
        var wires = crossings[key]
        var byGap = {}
        wires.forEach(function (w) {
          var by = w.b.y + w.b.h / 2
          var best = 0
          // A tie goes to the later gap: the margins above the first node and
          // below the last are for when the target really is up against the
          // column's edge, not for a target that has a gap between nodes
          // exactly as near.
          for (var i = 1; i < lanes.length; i += 1) {
            if (Math.abs(lanes[i] - by) <= Math.abs(lanes[best] - by)) best = i
          }
          ;(byGap[best] = byGap[best] || []).push(w)
          w.crossY[c] = best
        })
        Object.keys(byGap).forEach(function (gapKey) {
          var group = byGap[gapKey]
          var mid = lanes[Number(gapKey)]
          group.sort(function (l, r) {
            return (l.b.y + l.b.h / 2) - (r.b.y + r.b.h / 2)
          })
          var step = Math.min(SUBLANE_STEP, (metrics.INNER_GAP_Y - SUBLANE_STEP) / Math.max(1, group.length))
          group.forEach(function (w, i) {
            w.crossY[c] = mid + (i - (group.length - 1) / 2) * step
          })
        })
      })

      var polylines = []
      live.forEach(function (w) {
        var a = w.a
        var b = w.b
        var ay = a.y + a.h / 2
        var by = b.y + b.h / 2
        var pts
        var c
        if (w.kind === 'near') {
          pts = [
            { x: a.x + a.w, y: ay }, { x: w.lanes[columnOf(a)].x, y: ay },
            { x: w.lanes[columnOf(a)].x, y: by }, { x: b.x, y: by },
          ]
        } else if (w.kind === 'same') {
          pts = [
            { x: a.x + a.w, y: ay }, { x: w.lanes[columnOf(a)].x, y: ay },
            { x: w.lanes[columnOf(a)].x, y: by }, { x: b.x + b.w, y: by },
          ]
        } else if (w.kind === 'far') {
          // Right out of the source, then the staircase: vertical in one
          // corridor, across the next column through its gap, repeat.
          pts = [{ x: a.x + a.w, y: ay }, { x: w.lanes[columnOf(a)].x, y: ay }]
          for (c = columnOf(a) + 1; c <= columnOf(b) - 1; c += 1) {
            pts.push({ x: w.lanes[c - 1].x, y: w.crossY[c] })
            pts.push({ x: w.lanes[c].x, y: w.crossY[c] })
          }
          pts.push({ x: w.lanes[columnOf(b) - 1].x, y: by })
          pts.push({ x: b.x, y: by })
        } else {
          // Left out of the source, the mirrored staircase, into the target's
          // right edge.
          pts = [{ x: a.x, y: ay }, { x: w.lanes[columnOf(a) - 1].x, y: ay }]
          for (c = columnOf(a) - 1; c >= columnOf(b) + 1; c -= 1) {
            pts.push({ x: w.lanes[c].x, y: w.crossY[c] })
            pts.push({ x: w.lanes[c - 1].x, y: w.crossY[c] })
          }
          pts.push({ x: w.lanes[columnOf(b)].x, y: by })
          pts.push({ x: b.x + b.w, y: by })
        }
        polylines.push({
          id: w.edge.from + '→' + w.edge.to + ':' + w.type,
          type: w.type, pts: pts, fromFile: a.file, toFile: b.file,
          from: w.edge.from, to: w.edge.to,
          faded: stateOf(w.edge.to) !== null && stateOf(w.edge.to) !== undefined
            && !stateOf(w.edge.to).remembered,
        })
      })

      var route = { polylines: polylines, LANE_STEP: metrics.LANE_STEP, HOP: metrics.WIRE_HOP,
        WIRE_CORNER: metrics.WIRE_CORNER, ARROW_EVERY: metrics.ARROW_EVERY }
      repairCrossings(route, orient, metrics)
      var drawn = emitWires(route, markHops(route))
      return { route: route, drawn: drawn }
    }

    /** Same wires at a new origin: the polylines have already been moved. */
    function reemitFlow(route, orient, metrics) {
      var drawn = emitWires(route, markHops(route))
      return drawn
    }

    module.exports = { routeFlow, reemitFlow }
    return module.exports
  },
})
