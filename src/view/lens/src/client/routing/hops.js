// dsh-cdd-lens — Where one wire crosses another.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/hops',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * A crossing is not a join.
     */
    function markHops(route) {
      var polylines = route.polylines
      var HOP = route.HOP

      // ---- hops: a crossing is not a join ----------------------------------
      var hSegs = []
      var vSegs = []
      polylines.forEach(function (line) {
        if (line.status === 'blocked') return
        for (var i = 1; i < line.pts.length; i += 1) {
          var p = line.pts[i - 1]
          var q = line.pts[i]
          if (Math.abs(p.x - q.x) < 0.5 && Math.abs(p.y - q.y) < 0.5) continue
          if (Math.abs(p.y - q.y) < 0.5) hSegs.push({ line: line, p: p, q: q })
          else if (Math.abs(p.x - q.x) < 0.5) vSegs.push({ line: line, p: p, q: q })
        }
      })
      // Horizontal wires hop over vertical ones — one convention, applied
      // everywhere, so a hop always means the same thing.
      //
      // Only the verticals whose x falls inside this run are candidates, so the
      // verticals are sorted by x once and each run walks the slice it spans.
      // Comparing every horizontal against every vertical is the same count of
      // comparisons as wires squared, which at a thousand anchors was almost
      // half a second — on a layout that reruns on zoom and selection.
      var sorted = vSegs.slice().sort(function (l, r) { return l.p.x - r.p.x })
      var startAt = function (x) {
        var lo = 0
        var hi = sorted.length
        while (lo < hi) {
          var mid = (lo + hi) >> 1
          if (sorted[mid].p.x < x) lo = mid + 1
          else hi = mid
        }
        return lo
      }
      hSegs.forEach(function (h) {
        var y = h.p.y
        var lo = Math.min(h.p.x, h.q.x)
        var hi = Math.max(h.p.x, h.q.x)
        var xs = []
        for (var i = startAt(lo + HOP); i < sorted.length; i += 1) {
          var v = sorted[i]
          var x = v.p.x
          if (x >= hi - HOP) break
          if (v.line === h.line || (h.line.busKey && h.line.busKey === v.line.busKey)) continue
          var y0 = Math.min(v.p.y, v.q.y)
          var y1 = Math.max(v.p.y, v.q.y)
          if (y > y0 + 0.5 && y < y1 - 0.5) xs.push(x)
        }
        // Merge overlapping hop intervals, including repeated crossings at x.
        var spans = []
        xs.forEach(function (x) {
          var last = spans[spans.length - 1]
          if (last && x - HOP <= last.hi) last.hi = Math.max(last.hi, x + HOP)
          else spans.push({ lo:x-HOP, hi:x+HOP, y:y, radius:HOP })
        })
        spans.forEach(function (span) {
          var obstacles = route.obstacles || []
          var collides = function (up) {
            var top = up ? y-HOP : y, bottom = up ? y : y+HOP
            return obstacles.some(function (b) {
              return b.x < span.hi && b.x+b.w > span.lo && b.y < bottom && b.y+b.h > top
            })
          }
          span.up = !collides(true)
          span.gap = !span.up && collides(false)
        })
        h.hops = spans
      })

      return { hSegs: hSegs, vSegs: vSegs }
    }

    module.exports = { markHops }
    return module.exports
  },
})
