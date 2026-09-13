// dsh-cdd-lens — Orthogonal routing through the channels.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/ortho',
  factory: (require) => {
    var module = { exports: {} }
    var __view_record = require('dsh-cdd-lens/view/record')
    var stateOf = __view_record.stateOf

    /**
     * Wires as a schematic: out of a box, along channels, into the target.
     */
    function routeOrtho(edges, orient, relationFilter, channels, metrics) {
      var chosen = edges.chosen
      var byId = orient.byId
      var boxOf = orient.boxOf
      var vChannels = channels.vChannels
      var nearest = channels.nearest
      var innerLane = channels.innerLane
      var exitChannel = channels.exitChannel

      // ---- wires, drawn the way a schematic is -----------------------------
      //
      // Five rules, all of them things a circuit diagram settled long ago:
      //
      //   * a wire never runs under a module — it uses the channels between
      //     boxes, so a line inside a box always belongs to that box;
      //   * two wires travelling the same corridor get their own lane, because
      //     drawn on top of each other they read as one wire;
      //   * a crossing is drawn as a hop, so "crosses" and "joins" stop looking
      //     the same;
      //   * a real junction gets a filled dot, for the same reason;
      //   * direction markers repeat along the path, because on a long wire with
      //     four bends a single arrowhead at the far end tells you nothing about
      //     the middle.
      //
      // Points are shared objects between neighbouring segments, so nudging a
      // segment into its lane simply lengthens or shortens the two segments it
      // joins — the polyline stays connected with no extra bookkeeping.
      //
      // One spacing for every skin: these used to be written here as pixels,
      // and the flow skin carried its own copy, so a type-size change would
      // have had to find them all. They live in layout/metrics now.
      var LANE_STEP = metrics.LANE_STEP
      var HOP = metrics.WIRE_HOP
      var CORRIDOR_MIN = metrics.CORRIDOR_MIN
      // One spacing for both skins. This module carried its own 68 while the
      // layered one used 84, so the same wire got a different arrow density
      // depending on which drawing you were looking at.
      var ARROW_EVERY = metrics.ARROW_EVERY

      var polylines = []
      chosen.forEach(function (e) {
        var a = byId[e.from]
        var b = byId[e.to]
        var types = e.types.filter(function (type) {
          return relationFilter === undefined || relationFilter[type] !== false
        })
        types.forEach(function (type) {
          var pts
          if (a.file === b.file && a.innerRow === b.innerRow) {
            // Neighbours on one row inside one box: a short dogleg, all of it
            // inside the box it belongs to.
            var forward = a.x <= b.x
            var sx = forward ? a.x + a.w : a.x
            var sy = a.y + a.h / 2
            var tx = forward ? b.x : b.x + b.w
            var ty = b.y + b.h / 2
            var midX = sx + (tx - sx) / 2
            pts = [{ x: sx, y: sy }, { x: midX, y: sy }, { x: midX, y: ty }, { x: tx, y: ty }]
          } else if (a.file === b.file && boxOf[a.file] !== undefined) {
            // Same file, different rows. With one anchor per row this is now the
            // common case, and routing it through the channels OUTSIDE the box
            // would send a wire out the bottom and back in the top of the very
            // box it never leaves. It travels in the box's own side lane, which
            // holds no anchors.
            var boxS = boxOf[a.file]
            var down = a.y < b.y
            var sideL = boxS.x + CORRIDOR_MIN
            var sideR = boxS.x + boxS.w - CORRIDOR_MIN
            var ax = a.x + a.w / 2
            var bx = b.x + b.w / 2
            // When two anchors sit in the same column, putting every vertical
            // same-file relation on the same margin makes one unreadable rail.
            // Split upward and downward traffic, and use the target side when
            // there is a real horizontal move between columns.
            var useLeft = Math.abs(ax - bx) > CORRIDOR_MIN
              ? bx < ax
              : !down
            var lane = useLeft ? sideL : sideR
            var portA = useLeft ? a.x : a.x + a.w
            var portB = useLeft ? b.x : b.x + b.w
            pts = [
              { x: portA, y: a.y + a.h / 2 },
              { x: lane, y: a.y + a.h / 2 },
              { x: lane, y: b.y + b.h / 2 },
              { x: portB, y: b.y + b.h / 2 },
            ]
          } else {
            var boxA = boxOf[a.file]
            var boxB = boxOf[b.file]
            var downward = a.y < b.y
            var x1 = a.x + a.w / 2
            var y1 = downward ? a.y + a.h : a.y
            var x2 = b.x + b.w / 2
            var y2 = downward ? b.y : b.y + b.h
            if (boxA === undefined || boxB === undefined) {
              var mid = y1 + (y2 - y1) / 2
              pts = [{ x: x1, y: y1 }, { x: x1, y: mid }, { x: x2, y: mid }, { x: x2, y: y2 }]
            } else {
              // Leaving straight down from a node runs the wire through
              // whichever sibling sits below it in the same box — and the node
              // is painted on top, so the wire simply disappears under it. So a
              // wire leaves SIDEWAYS first, into the gap beside its column,
              // and only then travels vertically. Those inner gaps hold no
              // nodes, which is what makes them safe.
              var sideA = innerLane(a, boxA, b.x)
              var sideB = innerLane(b, boxB, a.x)
              var yOut = exitChannel(boxA, b.y)
              var yIn = exitChannel(boxB, a.y)
              var ayEdge = a.y + a.h / 2
              var byEdge = b.y + b.h / 2
              if (Math.abs(yOut - yIn) < 1) {
                pts = [
                  { x: sideA.port, y: ayEdge }, { x: sideA.lane, y: ayEdge },
                  { x: sideA.lane, y: yOut }, { x: sideB.lane, y: yOut },
                  { x: sideB.lane, y: byEdge }, { x: sideB.port, y: byEdge },
                ]
              } else {
                var lane = nearest(vChannels, (sideA.lane + sideB.lane) / 2)
                pts = [
                  { x: sideA.port, y: ayEdge }, { x: sideA.lane, y: ayEdge },
                  { x: sideA.lane, y: yOut }, { x: lane, y: yOut },
                  { x: lane, y: yIn }, { x: sideB.lane, y: yIn },
                  { x: sideB.lane, y: byEdge }, { x: sideB.port, y: byEdge },
                ]
              }
            }
          }
          polylines.push({
            id: e.from + '→' + e.to + ':' + type,
            type: type, pts: pts, fromFile: a.file, toFile: b.file,
            from: e.from, to: e.to,
            faded: stateOf(e.to) !== null && stateOf(e.to) !== undefined && !stateOf(e.to).remembered,
          })
        })
      })

      return { polylines: polylines, LANE_STEP: LANE_STEP, HOP: HOP, ARROW_EVERY: ARROW_EVERY }
    }

    module.exports = { routeOrtho }
    return module.exports
  },
})
