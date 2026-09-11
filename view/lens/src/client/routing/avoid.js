// dsh-cdd-lens — Rerouting the runs that cut through a box.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/avoid',
  factory: (require) => {
    var geometry = require('dsh-cdd-lens/routing/geometry')

    // Boundary contact is allowed; entering ANY card interior is not.
    // Endpoints lie on the boundary and need no whole-node exemption.
    var TOUCH_SLACK = 0

    /** Every drawn box, so a run can be tested against all of them. */
    function boxesOf(orient) {
      var byId = orient.byId
      return Object.keys(byId).map(function (id) { return byId[id] })
    }

    /**
     * Boxes bucketed by position, so a segment asks about its own neighbourhood.
     *
     * Testing every segment against every box is fine at forty anchors and half
     * a second at a thousand: the count of comparisons is segments times boxes,
     * and both grow with the graph. A run only ever passes near a handful of
     * boxes, and the grid layout means those are easy to find.
     */
    function boxIndex(boxes) {
      var CELL = 256
      var cells = {}
      var key = function (cx, cy) { return cx + ':' + cy }
      boxes.forEach(function (r) {
        var x0 = Math.floor(r.x / CELL), x1 = Math.floor((r.x + r.w) / CELL)
        var y0 = Math.floor(r.y / CELL), y1 = Math.floor((r.y + r.h) / CELL)
        for (var cx = x0; cx <= x1; cx += 1) {
          for (var cy = y0; cy <= y1; cy += 1) {
            var k = key(cx, cy)
            if (cells[k] === undefined) cells[k] = []
            cells[k].push(r)
          }
        }
      })
      return {
        near: function (p, q, out) {
          out.length = 0
          var seen = {}
          var x0 = Math.floor(Math.min(p.x, q.x) / CELL), x1 = Math.floor(Math.max(p.x, q.x) / CELL)
          var y0 = Math.floor(Math.min(p.y, q.y) / CELL), y1 = Math.floor(Math.max(p.y, q.y) / CELL)
          for (var cx = x0; cx <= x1; cx += 1) {
            for (var cy = y0; cy <= y1; cy += 1) {
              var list = cells[key(cx, cy)]
              if (list === undefined) continue
              for (var i = 0; i < list.length; i += 1) {
                var r = list[i]
                if (seen[r.id] === true) continue
                seen[r.id] = true
                out.push(r)
              }
            }
          }
          return out
        },
      }
    }

    /** Test every segment, including internal runs through its own endpoints. */
    function blockedBy(pts, boxes, fromId, toId, index) {
      var scratch = []
      for (var i = 1; i < pts.length; i += 1) {
        var p = pts[i - 1]
        var q = pts[i]
        var near = index === undefined ? boxes : index.near(p, q, scratch)
        for (var k = 0; k < near.length; k += 1) {
          var r = near[k]
          var x1 = r.x + TOUCH_SLACK, y1 = r.y + TOUCH_SLACK
          var x2 = r.x + r.w - TOUCH_SLACK, y2 = r.y + r.h - TOUCH_SLACK
          if (x2 <= x1 || y2 <= y1) continue
          if ((p.x > x1 && p.x < x2 && p.y > y1 && p.y < y2)
            || (q.x > x1 && q.x < x2 && q.y > y1 && q.y < y2)) return true
          if (Math.abs(p.y - q.y) < .5) {
            if (p.y > y1 && p.y < y2
              && Math.max(p.x, q.x) > x1 && Math.min(p.x, q.x) < x2) return true
          } else if (Math.abs(p.x - q.x) < .5) {
            if (p.x > x1 && p.x < x2
              && Math.max(p.y, q.y) > y1 && Math.min(p.y, q.y) < y2) return true
          }
        }
      }
      return false
    }

    // A* over a coordinate-compressed orthogonal visibility grid. The queue is
    // lazy: only reached grid points and their four neighbours are evaluated.
    function searchPath(starts, ends, boxes, stub, index, preferred) {
      var clearance = stub / 2
      var xs = [], ys = []
      starts.concat(ends).forEach(function (p) { xs.push(p.exit.x); ys.push(p.exit.y) })
      boxes.forEach(function (b) { xs.push(b.x-clearance,b.x+b.w+clearance); ys.push(b.y-clearance,b.y+b.h+clearance) })
      xs = Array.from(new Set(xs)).sort(function (a,b) { return a-b })
      ys = Array.from(new Set(ys)).sort(function (a,b) { return a-b })
      var nx = xs.length, xids = new Map(), yids = new Map()
      xs.forEach(function (x,i) { xids.set(x,i) }); ys.forEach(function (y,i) { yids.set(y,i) })
      var idOf = function (p) { return yids.get(p.y)*nx+xids.get(p.x) }
      var pointOf = function (id) { return { x:xs[id%nx],y:ys[Math.floor(id/nx)] } }
      var targets = new Map()
      ends.forEach(function (p) { targets.set(idOf(p.exit),p) })
      var heap = [], best = new Map(), previous = new Map(), origins = new Map(), links = new Map()
      var push = function (item) {
        heap.push(item)
        var i = heap.length-1
        while (i>0) { var j=(i-1)>>1; if (heap[j].f<=item.f) break; heap[i]=heap[j]; i=j }
        heap[i]=item
      }
      var pop = function () {
        var first=heap[0],last=heap.pop()
        if (heap.length) {
          var i=0
          while (i*2+1<heap.length) {
            var c=i*2+1
            if (c+1<heap.length && heap[c+1].f<heap[c].f) c++
            if (heap[c].f>=last.f) break
            heap[i]=heap[c];i=c
          }
          heap[i]=last
        }
        return first
      }
      var estimate = function (p) {
        var result=Infinity
        ends.forEach(function (t) { result=Math.min(result,Math.abs(t.exit.x-p.x)+Math.abs(t.exit.y-p.y)) })
        return result
      }
      starts.forEach(function (p) {
        var id=idOf(p.exit),dir=p.side==='left'||p.side==='right'?1:2,key=id*3+dir
        var g=stub+(preferred && p.side!==preferred[0]?stub:0)
        if (best.has(key) && best.get(key)<=g) return
        best.set(key,g);origins.set(key,p);push({key:key,id:id,dir:dir,g:g,f:g+estimate(p.exit)})
      })
      var winner=null,winCost=Infinity
      while (heap.length) {
        var state=pop()
        if (state.f>=winCost) break
        if (best.get(state.key)!==state.g) continue
        var p=pointOf(state.id),target=targets.get(state.id)
        if (target) {
          var endDir=target.side==='left'||target.side==='right'?1:2
          var total=state.g+stub+(endDir!==state.dir?stub:0)+(preferred && target.side!==preferred[1]?stub:0)
          if (total<winCost) { winCost=total;winner={state:state,target:target} }
        }
        var xi=state.id%nx,yi=Math.floor(state.id/nx)
        ;[[xi-1,yi,1],[xi+1,yi,1],[xi,yi-1,2],[xi,yi+1,2]].forEach(function (next) {
          if (next[0]<0 || next[0]>=nx || next[1]<0 || next[1]>=ys.length) return
          var id=next[1]*nx+next[0],q=pointOf(id)
          var link=Math.min(id,state.id)+':'+Math.max(id,state.id)
          if (!links.has(link)) links.set(link,!blockedBy([p,q],boxes,null,null,index))
          if (!links.get(link)) return
          var g=state.g+Math.abs(q.x-p.x)+Math.abs(q.y-p.y)+(state.dir!==next[2]?stub:0)
          var key=id*3+next[2]
          if (best.has(key) && best.get(key)<=g) return
          best.set(key,g);previous.set(key,state.key);origins.set(key,origins.get(state.key))
          push({key:key,id:id,dir:next[2],g:g,f:g+estimate(q)})
        })
      }
      if (!winner) return null
      var key=winner.state.key,reverse=[]
      var origin=origins.get(key)
      while (key!==undefined) { reverse.push(pointOf(Math.floor(key/3)));key=previous.get(key) }
      return geometry.compact([origin.point].concat(reverse.reverse(),[winner.target.point]))
    }

    /** Search local obstacles first; expand only if the local route is blocked. */
    function clearPath(a,b,boxes,stub,fromId,toId,index,preferred) {
      index=index || boxIndex(boxes)
      var sides=['right','left','bottom','top']
      var ports=function (node) {
        return sides.map(function (side) { return geometry.portAt(node,side,stub) })
          .filter(function (p) { return !blockedBy([p.point,p.exit],boxes,null,null,index) })
      }
      var starts=ports(a),ends=ports(b)
      if (!starts.length || !ends.length) return null
      // All simple doglegs compete by length and turns before searching a grid.
      var best=null,cost=Infinity
      starts.forEach(function (s) { ends.forEach(function (t) {
        ;[[s.exit,{x:t.exit.x,y:s.exit.y},t.exit],
          [s.exit,{x:s.exit.x,y:t.exit.y},t.exit]].forEach(function (middle) {
          var candidate=geometry.compact([s.point].concat(middle,[t.point]))
          var n=geometry.length(candidate)+stub*Math.max(0,candidate.length-2)
            +(preferred && s.side!==preferred[0]?stub:0)+(preferred && t.side!==preferred[1]?stub:0)
          if (n<cost && !blockedBy(candidate,boxes,fromId,toId,index)) { cost=n;best=candidate }
        })
      }) })
      if (best) return best
      var margin=stub*4
      for (;;) {
        var local=boxes.filter(function (r) {
          return r.x+r.w>=Math.min(a.x,b.x)-margin && r.x<=Math.max(a.x+a.w,b.x+b.w)+margin
            && r.y+r.h>=Math.min(a.y,b.y)-margin && r.y<=Math.max(a.y+a.h,b.y+b.h)+margin
        })
        var result=searchPath(starts,ends,local,stub,boxIndex(local),preferred)
        if (result && !blockedBy(result,boxes,fromId,toId,index)) return result
        if (local.length===boxes.length) return null
        margin*=2
      }
    }

    /** Repair the source of truth BEFORE hops, decorations and SVG emission. */
    function repairCrossings(route,orient,metrics) {
      var boxes=boxesOf(orient),index=boxIndex(boxes),fixed=0
      route.obstacles=boxes
      route.unrouted=[]
      var reuse=new Map()
      route.polylines.forEach(function (line) {
        line.pts=geometry.compact(line.pts)
        var a=orient.byId[line.from],b=orient.byId[line.to]
        if (!a || !b) { line.status='blocked';route.unrouted.push(line);return }
        if (line.pts.length>=2 && !blockedBy(line.pts,boxes,line.from,line.to,index)) { line.status='routed';return }
        var key=line.from+'→'+line.to
        var preferred=line.pts.length ? [geometry.sideOf(a,line.pts[0]),geometry.sideOf(b,line.pts[line.pts.length-1])] : ['right','left']
        if (!reuse.has(key)) reuse.set(key,clearPath(a,b,boxes,metrics.PORT_STUB,line.from,line.to,index,preferred))
        var found=reuse.get(key)
        if (!found) { line.status='blocked';line.pts=[];route.unrouted.push(line);return }
        line.pts=found.map(function (p) { return {x:p.x,y:p.y} })
        line.status='routed';delete line.branchIndex;delete line.busKey;fixed++
      })
      geometry.bindPorts(route,orient)
      return fixed
    }
    return { boxesOf,boxIndex,blockedBy,searchPath,clearPath,repairCrossings }
  },
})
