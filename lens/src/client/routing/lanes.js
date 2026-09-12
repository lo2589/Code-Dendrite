// dsh-cdd-lens — Separating segments that would otherwise overlap.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/lanes',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * Co-routed segments get their own track.
     */
    function spreadLanes(route, metrics) {
      var polylines = route.polylines
      var LANE_STEP = route.LANE_STEP
      var BOX_GAP_X = metrics.BOX_GAP_X
      var BOX_GAP_Y = metrics.BOX_GAP_Y

      // ---- lanes: co-routed segments get their own track -------------------
      var hGroups = {}
      var vGroups = {}
      polylines.forEach(function (line) {
        for (var i = 1; i < line.pts.length; i += 1) {
          var p = line.pts[i - 1]
          var q = line.pts[i]
          // Only interior segments may move; the first and last touch a node.
          if (i - 1 === 0 || i === line.pts.length - 1) continue
          // The run down a shared trunk is the ONE segment that must stay
          // exactly where its siblings are. Laning treats those overlapping
          // runs as co-routed wires and pushes each into its own track, which
          // is how a bus of four became four parallel lines a few pixels
          // apart, and how every branch point stopped being a place where
          // anything actually met.
          if (line.branchIndex !== undefined && i === line.branchIndex) continue
          // A zero-length segment satisfies BOTH tests. Classified as
          // horizontal it gets nudged into a lane, which drags a point off the
          // line and collapses the dogleg — two identical points and a wire
          // that no longer meets its own node.
          if (Math.abs(p.x - q.x) < 0.5 && Math.abs(p.y - q.y) < 0.5) continue
          if (Math.abs(p.y - q.y) < 0.5) {
            var hk = String(Math.round(p.y))
            ;(hGroups[hk] = hGroups[hk] || []).push({ p: p, q: q })
          } else if (Math.abs(p.x - q.x) < 0.5) {
            var vk = String(Math.round(p.x))
            ;(vGroups[vk] = vGroups[vk] || []).push({ p: p, q: q })
          }
        }
      })
      var spread = function (groups, axis, budget) {
        Object.keys(groups).forEach(function (key) {
          var list = groups[key]
          if (list.length < 2) return
          // Order by where each segment starts so neighbouring lanes belong to
          // wires heading the same way; interleaving them would add crossings.
          list.sort(function (l, r) {
            return (axis === 'y' ? Math.min(l.p.x, l.q.x) - Math.min(r.p.x, r.q.x)
              : Math.min(l.p.y, l.q.y) - Math.min(r.p.y, r.q.y))
          })
          var step = Math.min(LANE_STEP, budget / Math.max(1, list.length - 1))
          list.forEach(function (seg, i) {
            var off = (i - (list.length - 1) / 2) * step
            seg.p[axis] += off
            seg.q[axis] += off
          })
        })
      }
      spread(hGroups, 'y', Math.max(10, BOX_GAP_Y - 14))
      spread(vGroups, 'x', Math.max(10, BOX_GAP_X - 14))

    }

    module.exports = { spreadLanes }
    return module.exports
  },
})
