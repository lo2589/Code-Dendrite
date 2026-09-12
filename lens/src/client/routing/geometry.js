// Shared, structured geometry. SVG is output only, never a routing input.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/geometry',
  factory: (require) => {
    function compact(points) {
      var out = []
      points.forEach(function (p) {
        if (!Number.isFinite(p.x) || !Number.isFinite(p.y)) return
        var q = out[out.length - 1]
        if (q && Math.abs(p.x - q.x) < 1e-7 && Math.abs(p.y - q.y) < 1e-7) return
        while (out.length > 1) {
          var a = out[out.length - 2], b = out[out.length - 1]
          if ((a.x === b.x && b.x === p.x && (b.y - a.y) * (p.y - b.y) >= 0)
            || (a.y === b.y && b.y === p.y && (b.x - a.x) * (p.x - b.x) >= 0)) out.pop()
          else break
        }
        out.push({ x: p.x, y: p.y })
      })
      return out
    }
    function sideOf(node, p) {
      var sides = [['left', Math.abs(p.x - node.x)], ['right', Math.abs(p.x - node.x - node.w)],
        ['top', Math.abs(p.y - node.y)], ['bottom', Math.abs(p.y - node.y - node.h)]]
      sides.sort(function (a, b) { return a[1] - b[1] })
      return sides[0][0]
    }
    function portAt(node, side, stub) {
      var x = node.x + node.w / 2, y = node.y + node.h / 2
      var dx = side === 'left' ? -1 : side === 'right' ? 1 : 0
      var dy = side === 'top' ? -1 : side === 'bottom' ? 1 : 0
      if (dx) x += dx * node.w / 2
      if (dy) y += dy * node.h / 2
      return { side: side, point: { x: x, y: y }, exit: { x: x + dx * stub, y: y + dy * stub } }
    }
    function length(pts) {
      var n = 0
      for (var i = 1; i < pts.length; i++) n += Math.abs(pts[i].x - pts[i-1].x) + Math.abs(pts[i].y - pts[i-1].y)
      return n
    }
    function atDistance(pts, distance) {
      for (var i = 1; i < pts.length; i++) {
        var p = pts[i-1], q = pts[i], dx = q.x-p.x, dy = q.y-p.y, n = Math.abs(dx)+Math.abs(dy)
        if (n > 0 && (distance <= n || i === pts.length-1)) {
          var t = Math.max(0, Math.min(1, distance/n))
          return { x:p.x+dx*t, y:p.y+dy*t, angle:Math.atan2(dy,dx)*180/Math.PI, segment:i }
        }
        distance -= n
      }
      return { x:pts[0].x, y:pts[0].y, angle:0, segment:0 }
    }
    // Ports are attached to the SAME endpoint objects that translate with a route.
    function bindPorts(route, orient) {
      Object.keys(orient.byId).forEach(function (id) { orient.byId[id].routingPorts = [] })
      route.polylines.forEach(function (line) {
        if (line.status === 'blocked' || line.pts.length < 2) return
        ;[['from','sourcePort','out',0],['to','targetPort','in',line.pts.length-1]].forEach(function (spec) {
          var node = orient.byId[line[spec[0]]]
          if (!node) return
          var p = line.pts[spec[3]], side = sideOf(node,p)
          line[spec[1]] = { side:side, point:p }
          var existing = node.routingPorts.filter(function (port) { return port.side === side })[0]
          if (!existing) { existing = { side:side, in:false, out:false }; node.routingPorts.push(existing) }
          existing[spec[2]] = true
        })
      })
    }
    return { compact, sideOf, portAt, length, atDistance, bindPorts }
  },
})
