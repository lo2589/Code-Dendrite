// dsh-cdd-lens — The layered skin: how a wire gets from box to box.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/skins/tiers/route',
  factory: (require) => {
    var module = { exports: {} }
    var repairCrossings = require('dsh-cdd-lens/routing/avoid').repairCrossings
    var emitWires = require('dsh-cdd-lens/routing/emit').emitWires
    var markHops = require('dsh-cdd-lens/routing/hops').markHops

    /**
     * Route the chosen relations through the gaps between layers.
     *
     * A curve drawn straight from one node's edge to another's crosses whatever
     * stands between them, which on a layered drawing is every node in every
     * layer it spans. A wire here leaves the bottom of its source, drops into
     * the gap below that layer, runs sideways there, and comes down into the top
     * of its target — so the only place a wire is ever horizontal is a gap where
     * nothing is standing.
     *
     * Wires sharing a gap get their own height in it, ordered by where they are
     * going, so parallel departures do not lie on top of each other.
     * @param edges - the relations to draw, from routing/select.
     * @param orient - byId, the placed node for every id.
     * @param relationFilter - relation kinds the viewer left switched on.
     * @param metrics - box metrics; its BOX_GAP_Y is the room between layers.
     * @returns wires, arrowheads and labels, ready to draw.
     */
    function routeTiers(edges, orient, relationFilter, metrics) {
      var byId = orient.byId
      var live = []
      edges.chosen.forEach(function (edge) {
        var a = byId[edge.from]
        var b = byId[edge.to]
        if (a === undefined || b === undefined) return
        var types = (edge.types || []).filter(function (type) {
          return relationFilter === undefined || relationFilter[type] !== false
        })
        types.forEach(function (type) {
          live.push({ edge: edge, type: type, a: a, b: b })
        })
      })

      // Calls read left to right: a wire leaves the caller's right edge and
      // arrives at the callee's left edge. The only place it may travel
      // vertically is the corridor between two layers, so it never runs
      // through a column it has no business in.
      //
      // Everything crossing the same corridor shares it, so each wire gets its
      // own vertical line inside it rather than all of them stacking on the
      // middle.
      var lanes = {}
      live.forEach(function (w) {
        var key = Math.round(w.a.x + w.a.w) + ':' + Math.round(w.b.x)
        if (lanes[key] === undefined) lanes[key] = []
        lanes[key].push(w)
      })
      Object.keys(lanes).forEach(function (key) {
        var list = lanes[key]
        list.sort(function (l, r) { return (l.b.y + l.b.h / 2) - (r.b.y + r.b.h / 2) })
        var left = Number(key.split(':')[0])
        var right = Number(key.split(':')[1])
        var room = Math.max(metrics.LANE_STEP, right - left - metrics.CORRIDOR_MIN)
        var step = room / (list.length + 1)
        list.forEach(function (w, i) { w.mid = left + step * (i + 1) })
      })

      var STUB = metrics.PORT_STUB
      var polylines = []
      live.forEach(function (w) {
        var a = w.a
        var b = w.b
        var forward = b.x > a.x + a.w
        var pts
        if (forward) {
          var y1 = a.y + a.h / 2
          var y2 = b.y + b.h / 2
          var x1 = a.x + a.w
          var x2 = b.x
          // Straight out of the exit port, straight into the entry port, and
          // only the corridor between the two columns in between.
          var mid = w.mid === undefined ? x1 + (x2 - x1) / 2 : w.mid
          mid = Math.min(Math.max(mid, x1 + STUB), x2 - STUB)
          pts = [
            { x: x1, y: y1 }, { x: mid, y: y1 },
            { x: mid, y: y2 }, { x: x2, y: y2 },
          ]
        } else {
          // Backwards or sideways: down out of the source, along under both, up
          // into the target. It never crosses a column because it never enters
          // one.
          var below = Math.max(a.y + a.h, b.y + b.h) + STUB * 2
          var ax = a.x + a.w / 2
          var bx = b.x + b.w / 2
          pts = [
            { x: ax, y: a.y + a.h }, { x: ax, y: below },
            { x: bx, y: below }, { x: bx, y: b.y + b.h },
          ]
        }
        polylines.push({id:w.edge.from+'→'+w.edge.to+':'+w.type,
          from:w.edge.from,to:w.edge.to,type:w.type,pts:pts,
          fromFile:a.file,toFile:b.file,faded:w.edge.faded===true})
      })
      var route = {polylines:polylines,LANE_STEP:metrics.LANE_STEP,HOP:metrics.WIRE_HOP,ARROW_EVERY:metrics.ARROW_EVERY}
      repairCrossings(route,orient,metrics)
      var drawn = emitWires(route,markHops(route))
      drawn.route = route
      return drawn
    }

    module.exports = { routeTiers }
    return module.exports
  },
})
