// All skins emit from final geometry. No stage repairs SVG strings afterwards.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/emit',
  factory: (require) => {
    var geometry = require('dsh-cdd-lens/routing/geometry')
    /**
     * 两个端点之间的三次贝塞尔。
     *
     * 控制点沿水平方向外推，所以线离开出端口时是朝右的、进入入端口时是朝左的，
     * 两头都正对着小圈。这就是 jsoncrack 那种观感，也是它比折线好看的原因：
     * 没有硬折角，且起点方向明确告诉你是从哪里出来的。
     */
    function bezierPath(a, b) {
      var dx = Math.max(36, Math.abs(b.x - a.x) * .5)
      return 'M' + a.x + ',' + a.y
        + ' C' + (a.x + dx) + ',' + a.y
        + ' ' + (b.x - dx) + ',' + b.y
        + ' ' + b.x + ',' + b.y
    }

    /** 一条线上的一串点怎么连：两点用贝塞尔，多点用平滑折线。 */
    function pathFrom(pts) {
      if (pts.length < 2) return ''
      if (pts.length === 2) return bezierPath(pts[0], pts[1])
      var d = 'M' + pts[0].x + ',' + pts[0].y
      for (var i = 1; i < pts.length; i += 1) d += ' L' + pts[i].x + ',' + pts[i].y
      return d
    }

    /**
     * 一条线上放几个箭头，放在哪。
     *
     * 箭头是看方向的唯一线索，所以宁可多。短线上至少一个；线一长就按间距铺，
     * 最多 6 个——再多就把线糊成一条毛毛虫了。首尾各留 14px，免得箭头压在
     * 端口小圈或目标卡片上。
     */
    /** 贝塞尔上的一点和切线角（t 在 0..1）。 */
    function bezierAt(a, c1, c2, b, t) {
      var mt = 1 - t
      var x = mt*mt*mt*a.x + 3*mt*mt*t*c1.x + 3*mt*t*t*c2.x + t*t*t*b.x
      var y = mt*mt*mt*a.y + 3*mt*mt*t*c1.y + 3*mt*t*t*c2.y + t*t*t*b.y
      var dx = 3*mt*mt*(c1.x-a.x) + 6*mt*t*(c2.x-c1.x) + 3*t*t*(b.x-c2.x)
      var dy = 3*mt*mt*(c1.y-a.y) + 6*mt*t*(c2.y-c1.y) + 3*t*t*(b.y-c2.y)
      return { x: x, y: y, angle: Math.atan2(dy, dx) * 180 / Math.PI }
    }

    /** 这条线的控制点；多点（跨层）的线不适用，返回 null。 */
    function bezierControls(pts) {
      if (pts.length !== 2) return null
      var a = pts[0], b = pts[1]
      var dx = Math.max(36, Math.abs(b.x - a.x) * .5)
      return { a: a, c1: { x: a.x + dx, y: a.y }, c2: { x: b.x - dx, y: b.y }, b: b }
    }

    function arrowDistances(total, every) {
      if (total <= 0) return []
      if (total < every) return [total * .55]
      var step = Math.max(56, every)
      var count = Math.floor((total - 28) / step)
      if (count < 1) count = 1
      if (count > 6) count = 6
      var out = []
      for (var i = 1; i <= count; i += 1) out.push(total * i / (count + 1))
      return out
    }

    function emitWires(route,hops) {
      var wires=[],labels=[],junctions=[],arrows=[]
      route.polylines.forEach(function (line) {
        var pts=line.pts
        if (line.status==='blocked' || pts.length<2) return
        var minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity
        var see=function (x,y) { minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y) }
        pts.forEach(function (p) { see(p.x,p.y) })
        // 路径：两点走贝塞尔，跨层（有虚节点拐点）走折线。
        var d = pathFrom(pts)
        var arcs = []
        wires.push({ id:line.id,d:d,type:line.type,faded:line.faded,from:line.from,to:line.to,
          fromFile:line.fromFile,toFile:line.toFile,pts:pts,arcs:arcs,
          sourcePort:line.sourcePort,targetPort:line.targetPort,
          bounds:{minX:minX,minY:minY,maxX:maxX,maxY:maxY} })
        var total=geometry.length(pts),distances=arrowDistances(total,route.ARROW_EVERY)
        var curve = bezierControls(pts)
        distances.forEach(function (distance,j) {
          // 两点线走的是贝塞尔，箭头必须落在曲线上，不能按弦估。
          var at = curve !== null
            ? bezierAt(curve.a, curve.c1, curve.c2, curve.b, Math.min(1, Math.max(0, distance / total)))
            : geometry.atDistance(pts,distance)
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
