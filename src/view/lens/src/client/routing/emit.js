// All skins emit from final geometry. No stage repairs SVG strings afterwards.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/emit',
  factory: (require) => {
    var geometry = require('dsh-cdd-lens/routing/geometry')
    function emitWires(route,hops) {
      var wires=[],labels=[],junctions=[],arrows=[],segments=new Map()
      hops.hSegs.forEach(function (s) { segments.set(s.p,s) })
      route.polylines.forEach(function (line) {
        var pts=line.pts
        if (line.status==='blocked' || pts.length<2) return
        var minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity
        var see=function (x,y) { minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y) }
        pts.forEach(function (p) { see(p.x,p.y) })
        var d='M'+pts[0].x+','+pts[0].y,arcs=[]
        for (var i=1;i<pts.length;i++) {
          var p=pts[i-1],q=pts[i],seg=segments.get(p)
          if (seg && seg.q===q && seg.hops.length) {
            var forward=q.x>p.x,order=forward?seg.hops:seg.hops.slice().reverse()
            order.forEach(function (span) {
              var before=forward?span.lo:span.hi,after=forward?span.hi:span.lo
              d+=' L'+before+','+p.y
              if (span.gap) d+=' M'+after+','+p.y
              else {
                var rx=(span.hi-span.lo)/2,ry=span.radius
                d+=' A'+rx+','+ry+' 0 0 '+((forward===span.up)?1:0)+' '+after+','+p.y
                see(span.lo,p.y+(span.up?-ry:ry));see(span.hi,p.y)
              }
              arcs.push(span)
            })
          }
          d+=' L'+q.x+','+q.y
        }
        wires.push({ id:line.id,d:d,type:line.type,faded:line.faded,from:line.from,to:line.to,
          fromFile:line.fromFile,toFile:line.toFile,pts:pts,arcs:arcs,
          sourcePort:line.sourcePort,targetPort:line.targetPort,
          bounds:{minX:minX,minY:minY,maxX:maxX,maxY:maxY} })
        var total=geometry.length(pts),every=route.ARROW_EVERY,distances=[]
        // Keep the final head off the port badge, and always give short wires a head.
        for (var t=every*0.55;t<total;t+=every) distances.push(t)
        if (!distances.length) distances.push(total/2)
        distances.forEach(function (distance,j) {
          var at=geometry.atDistance(pts,distance)
          if (arcs.some(function (arc) { return Math.abs(at.y-arc.y)<0.5 && at.x>=arc.lo-2 && at.x<=arc.hi+2 })) return
          arrows.push({ id:line.id+':head'+j,from:line.from,to:line.to,type:line.type,
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
