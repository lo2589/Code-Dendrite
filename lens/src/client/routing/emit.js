// All skins emit from final geometry. No stage repairs SVG strings afterwards.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/emit',
  factory: (require) => {
    var geometry = require('dsh-cdd-lens/routing/geometry')
    function pointAtCorner(from, corner, to, radius) {
      var dx1 = corner.x - from.x
      var dy1 = corner.y - from.y
      var dx2 = to.x - corner.x
      var dy2 = to.y - corner.y
      var len1 = Math.abs(dx1) + Math.abs(dy1)
      var len2 = Math.abs(dx2) + Math.abs(dy2)
      if (len1 < 1 || len2 < 1) return null
      var turn = Math.abs(dx1) < .5 ? Math.abs(dy2) < .5 : Math.abs(dx2) < .5
      if (!turn) return null
      var r = Math.min(radius, len1 / 2, len2 / 2)
      if (r < 2) return null
      return {
        enter: { x: corner.x - Math.sign(dx1) * r, y: corner.y - Math.sign(dy1) * r },
        leave: { x: corner.x + Math.sign(dx2) * r, y: corner.y + Math.sign(dy2) * r },
      }
    }

    function appendHorizontal(d, from, to, base, originalTo, segments, see, arcs) {
      var seg = segments.get(base)
      if (!seg || seg.q !== originalTo || !seg.hops.length) return d + ' L' + to.x + ',' + to.y
      var forward = to.x > from.x
      var start = Math.min(from.x, to.x)
      var end = Math.max(from.x, to.x)
      var order = forward ? seg.hops : seg.hops.slice().reverse()
      order.forEach(function (span) {
        var spanLo = Math.max(span.lo, start)
        var spanHi = Math.min(span.hi, end)
        if (spanHi <= spanLo) return
        var before = forward ? spanLo : spanHi
        var after = forward ? spanHi : spanLo
        d += ' L' + before + ',' + from.y
        if (span.gap) d += ' M' + after + ',' + from.y
        else {
          var rx = (spanHi - spanLo) / 2
          var ry = span.radius
          d += ' A' + rx + ',' + ry + ' 0 0 ' + ((forward === span.up) ? 1 : 0) + ' ' + after + ',' + from.y
          see(spanLo, from.y + (span.up ? -ry : ry)); see(spanHi, from.y)
        }
        arcs.push(span)
      })
      return d + ' L' + to.x + ',' + to.y
    }

    function arrowDistances(total, every) {
      if (total <= 0) return []
      if (total < every * 1.45) return [total * .55]
      return [Math.max(16,total * .28), Math.min(total - 16,total * .72)]
    }

    function emitWires(route,hops) {
      var wires=[],labels=[],junctions=[],arrows=[],segments=new Map()
      var cornerRadius = route.CORNER || route.WIRE_CORNER || 10
      hops.hSegs.forEach(function (s) { segments.set(s.p,s) })
      route.polylines.forEach(function (line) {
        var pts=line.pts
        if (line.status==='blocked' || pts.length<2) return
        var minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity
        var see=function (x,y) { minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y) }
        pts.forEach(function (p) { see(p.x,p.y) })
        var corner = {}
        for (var c=1;c<pts.length-1;c++) {
          var cut = pointAtCorner(pts[c-1],pts[c],pts[c+1],cornerRadius)
          if (cut) corner[c] = cut
        }
        var d='M'+pts[0].x+','+pts[0].y,arcs=[],cursor=pts[0]
        for (var i=1;i<pts.length;i++) {
          var p=pts[i-1],q=pts[i]
          var target = corner[i] ? corner[i].enter : q
          if (Math.abs(cursor.y-target.y)<.5 && Math.abs(cursor.x-target.x)>=.5) {
            d = appendHorizontal(d,cursor,target,p,q,segments,see,arcs)
          } else {
            d+=' L'+target.x+','+target.y
          }
          if (corner[i]) {
            d+=' Q'+q.x+','+q.y+' '+corner[i].leave.x+','+corner[i].leave.y
            cursor=corner[i].leave
            see(q.x,q.y)
          } else {
            cursor=q
          }
        }
        wires.push({ id:line.id,d:d,type:line.type,faded:line.faded,from:line.from,to:line.to,
          fromFile:line.fromFile,toFile:line.toFile,pts:pts,arcs:arcs,
          sourcePort:line.sourcePort,targetPort:line.targetPort,
          bounds:{minX:minX,minY:minY,maxX:maxX,maxY:maxY} })
        var total=geometry.length(pts),distances=arrowDistances(total,route.ARROW_EVERY)
        distances.forEach(function (distance,j) {
          var at=geometry.atDistance(pts,distance)
          if (arcs.some(function (arc) { return Math.abs(at.y-arc.y)<0.5 && at.x>=arc.lo-2 && at.x<=arc.hi+2 })) return
          arrows.push({ id:line.id+':head'+j,wireId:line.id,from:line.from,to:line.to,type:line.type,
            x:at.x,y:at.y,angle:at.angle,faded:line.faded })
        })
        // Position by walked distance, so a two-point route is a valid route.
        var mid=geometry.atDistance(pts,total/2)
        labels.push({id:line.id,x:mid.x,y:mid.y,type:line.type})
      })
      return {wires:wires,labels:labels,junctions:junctions,arrows:arrows,unrouted:route.unrouted || []}
    }
    return {emitWires}
  },
})
