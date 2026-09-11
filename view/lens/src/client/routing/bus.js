// dsh-cdd-lens — Collapsing parallel departures into a trunk.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/bus',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * One trunk out of a node, branches off it.
     */
    function mergeBuses(route) {
      var polylines = route.polylines

      // ---- buses: one trunk out of a node, branches off it ------------------
      //
      // Forty-one wires each taking their own path put dozens of parallel lines
      // in the same narrow channel. Crossings were low — parallel lines do not
      // cross — and the picture was still unreadable, which is what made
      // crossing count the wrong measure: side by side and indistinguishable is
      // worse than crossing and traceable.
      //
      // A schematic answers this with a bus. Everything leaving one node in one
      // direction shares a single trunk, and each destination leaves it at its
      // own branch point, marked with a filled dot. N lines in a corridor become
      // one line plus N short stubs, and the dot says "this is where that one
      // goes" — a crossing, drawn as a hop, never means that.
      var busGroups = {}
      polylines.forEach(function (line) {
        if (line.pts.length < 5) return
        // Only the cross-box shape (port, lane, channel, …) can share a trunk;
        // the short in-box routes have nothing to pool.
        var key = [line.from,line.type,line.pts[0].x,line.pts[0].y,line.pts[1].x,
          line.pts[2].y > line.pts[0].y ? 'down' : 'up'].join('|')
        ;(busGroups[key] = busGroups[key] || []).push(line)
      })
      Object.keys(busGroups).forEach(function (key) {
        var members = busGroups[key]
        if (members.length < 2) return
        // Every member already leaves through the same port and side lane; the
        // trunk is that lane, run to the farthest branch.
        var laneX = members[0].pts[1].x
        var startY = members[0].pts[0].y
        var branches = members.map(function (line) {
          return { line: line, y: line.pts[2].y }
        }).sort(function (l, r) {
          return Math.abs(l.y - startY) - Math.abs(r.y - startY)
        })
        branches.forEach(function (branch) {
          var line = branch.line
          // Redraw as: stay on the trunk to my own branch point, then leave.
          var tail = line.pts.slice(3)
          line.pts = [
            { x: line.pts[0].x, y: startY },
            { x: laneX, y: startY },
            { x: laneX, y: branch.y },
          ].concat(tail)
          // Remember WHERE in the polyline the branch is, not the coordinates
          // it had at this moment. Lane assignment runs after this and nudges
          // the points; a captured pair of numbers then marks the spot the wire
          // used to be, which is how four of these dots ended up floating in
          // empty canvas.
          line.branchIndex = 2
          line.busKey = key
        })
      })

    }

    module.exports = { mergeBuses }
    return module.exports
  },
})
