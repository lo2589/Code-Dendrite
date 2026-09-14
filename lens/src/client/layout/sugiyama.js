// dsh-cdd-lens — 分层布局（自研 Sugiyama）。唯一的布局，没有皮肤。
//
// 端口：从 /Users/a1/Workspace/WORKSPACE/visual_map/js/graph-layout.js 移植，
// 四步与原实现一致，只把 node 的取法换成 CDD 的 anchor 图：
//
//   1. 消环   —— DFS 找回向边，逻辑上反转它们使图变成 DAG
//   2. 分层   —— 最长路径法：layer[v] = max(layer[前驱]) + 1
//   3. 排序   —— 跨层长边拆成虚节点链，虚节点与真实节点一起做重心排序；
//                交叉数 = 每个层边界上「下层序号序列的严格逆序对数」
//   4. 坐标   —— 层定 x、层内序号定 y、各层垂直居中；
//                虚节点坐标输出成边的 bendPoints，直接喂给 routing/emit
//
// 为什么不用 ELK：纯 ELK 在这张图上性能差。自研这套 400 行、零依赖、确定性。
//
// 输入是 CDD 的图：`graph.nodes[id]` 就是 anchor 记录，`graph.ui[id]` 是按钮状态，
// 布局只读前者，一个字段都不写回。
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/sugiyama',
  factory: (require) => {
    var module = { exports: {} }

    var NODE_W = 180
    var NODE_H = 46
    var DUMMY_H = 10
    var GAP_X = 110
    var GAP_Y = 26
    var MARGIN = 40
    var SWEEPS = 12

    // 端口小圈往外探出的距离，必须和 styles/graph.js 里 .cddl-port 的
    // left/right 偏移（6px）对上：圈心 = 边界 ∓ 6。线的两端就停在这个圈心上，
    // 所以这个数字改了，那边也要改——线才不会悬在圈外面。
    var PORT_OFFSET = 6

    /** 端点：入在左、出在右，各外探 PORT_OFFSET。 */
    function portsFor(x, y, w, h) {
      return {
        in: { x: x - PORT_OFFSET, y: y + h / 2 },
        out: { x: x + w + PORT_OFFSET, y: y + h / 2 },
      }
    }

    /**
     * 把一个 CDD 图排成分层图。
     *
     * @param graph - { nodes: {id: anchor}, edges: [{from,to,types}] }。
     * @param included - 这一轮要画的 id（layoutScope 决定）。
     * @param metrics - boxMetrics 的结果，提供 sizeOf / label / PAD。
     * @returns { placed, polylines, fileBoxes, canvasY, crossings, layers }。
     */
    function sugiyama(graph, included, metrics, placedAt) {
      var ids = included.filter(function (id) { return graph.nodes[id] !== undefined })
      var idSet = {}
      ids.forEach(function (id) { idSet[id] = true })

      // 只画两端都在屏幕上的边。
      var edges = graph.edges.filter(function (e) {
        return idSet[e.from] === true && idSet[e.to] === true && e.from !== e.to
      })

      if (ids.length === 0) {
        return { placed: [], polylines: [], canvasY: MARGIN, crossings: 0, layers: 0 }
      }

      // ---------- 1. 消环：迭代 DFS，GRAY 邻居即回向边 ----------
      var out = {}
      ids.forEach(function (id) { out[id] = [] })
      edges.forEach(function (e) { out[e.from].push(e.to) })

      var WHITE = 0, GRAY = 1, BLACK = 2
      var color = {}
      ids.forEach(function (id) { color[id] = WHITE })
      var backEdge = {}
      ids.forEach(function (s) {
        if (color[s] !== WHITE) return
        color[s] = GRAY
        var stack = [[s, 0]]
        while (stack.length > 0) {
          var top = stack[stack.length - 1]
          var v = top[0]
          var adj = out[v]
          if (top[1] < adj.length) {
            var w = adj[top[1]]
            top[1] += 1
            if (color[w] === WHITE) { color[w] = GRAY; stack.push([w, 0]) }
            else if (color[w] === GRAY) { backEdge[v + '\u0000' + w] = true }
          } else {
            color[v] = BLACK
            stack.pop()
          }
        }
      })

      // ---------- 2. DAG 化 + 最长路径分层 ----------
      var dagEdges = edges.map(function (e) {
        var reversed = backEdge[e.from + '\u0000' + e.to] === true
        return { edge: e, from: reversed ? e.to : e.from, to: reversed ? e.from : e.to, reversed: reversed }
      })
      var dagOut = {}, dagIn = {}, indeg = {}
      ids.forEach(function (id) { dagOut[id] = []; dagIn[id] = []; indeg[id] = 0 })
      dagEdges.forEach(function (d) {
        dagOut[d.from].push(d.to)
        dagIn[d.to].push(d.from)
        indeg[d.to] += 1
      })
      var layerOf = {}
      var queue = ids.filter(function (id) { return indeg[id] === 0 })
      var left = 0
      while (queue.length > 0) {
        var v = queue.shift()
        left += 1
        var l = 0
        dagIn[v].forEach(function (p) { if (layerOf[p] + 1 > l) l = layerOf[p] + 1 })
        layerOf[v] = l
        dagOut[v].forEach(function (w) {
          indeg[w] -= 1
          if (indeg[w] === 0) queue.push(w)
        })
      }
      // 有环残留时把没排到的塞到最后一层，不让它们消失。
      var layerCount = 1
      ids.forEach(function (id) {
        if (layerOf[id] === undefined) layerOf[id] = 0
        if (layerOf[id] + 1 > layerCount) layerCount = layerOf[id] + 1
      })

      // ---------- 3a. 跨层边拆虚节点 ----------
      var layers = []
      for (var i = 0; i < layerCount; i += 1) layers.push([])
      ids.forEach(function (id) { layers[layerOf[id]].push(id) })

      var unitAdj = {}
      ids.forEach(function (id) { unitAdj[id] = {} })
      var segsByBoundary = []
      for (var b = 0; b < layerCount - 1; b += 1) segsByBoundary.push([])
      var dummyOfEdge = {}
      var reversedDummy = {}
      var dummySeq = 0

      function pushUnit(f, t, l) {
        segsByBoundary[l].push([f, t])
        unitAdj[f][t] = true
        unitAdj[t][f] = true
      }

      dagEdges.forEach(function (d, i) {
        var span = layerOf[d.to] - layerOf[d.from]
        if (span <= 1) { pushUnit(d.from, d.to, layerOf[d.from]); return }
        var chain = []
        for (var k = 1; k < span; k += 1) {
          var did = '\u0000vd' + (dummySeq++)
          chain.push(did)
          layers[layerOf[d.from] + k].push(did)
          unitAdj[did] = {}
        }
        dummyOfEdge[i] = d.reversed ? chain.slice().reverse() : chain
        if (d.reversed) chain.forEach(function (k) { reversedDummy[k] = true })
        var seq = [d.from].concat(chain).concat([d.to])
        for (var s = 0; s + 1 < seq.length; s += 1) pushUnit(seq[s], seq[s + 1], layerOf[d.from] + s)
      })

      // ---------- 3b. 重心排序 + 交叉计数 ----------
      function indexMap(layerNodes) {
        var m = {}
        layerNodes.forEach(function (id, i) { m[id] = i })
        return m
      }
      function sortLayer(layerNodes, neighborIndex) {
        var keys = layerNodes.map(function (id, i) {
          var sum = 0, cnt = 0
          Object.keys(unitAdj[id] || {}).forEach(function (nb) {
            if (neighborIndex[nb] !== undefined) { sum += neighborIndex[nb]; cnt += 1 }
          })
          return { id: id, i: i, key: cnt ? sum / cnt : i }
        })
        keys.sort(function (a, b) { return a.key - b.key || a.i - b.i })
        keys.forEach(function (k, i) { layerNodes[i] = k.id })
      }
      function countInversions(arr) {
        var inv = 0
        var buf = new Array(arr.length)
        function mergeSort(lo, hi) {
          if (hi - lo < 2) return
          var mid = (lo + hi) >> 1
          mergeSort(lo, mid); mergeSort(mid, hi)
          var i = lo, j = mid, k = lo
          while (i < mid && j < hi) {
            if (arr[i] <= arr[j]) buf[k++] = arr[i++]
            else { buf[k++] = arr[j++]; inv += mid - i }
          }
          while (i < mid) buf[k++] = arr[i++]
          while (j < hi) buf[k++] = arr[j++]
          for (var t = lo; t < hi; t += 1) arr[t] = buf[t]
        }
        mergeSort(0, arr.length)
        return inv
      }
      function countCrossings(order) {
        var pos = {}
        order.forEach(function (layer, l) { layer.forEach(function (id, i) { pos[id] = { l: l, i: i } }) })
        var c = 0
        for (var l = 0; l < order.length - 1; l += 1) {
          var bucket = segsByBoundary[l]
          if (bucket.length < 2) continue
          var segs = bucket.map(function (s) { return [pos[s[0]].i, pos[s[1]].i] })
          segs.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1] })
          c += countInversions(segs.map(function (s) { return s[1] }))
        }
        return c
      }

      var order = layers.map(function (l) { return l.slice() })
      var best = countCrossings(order)
      var bestOrder = order.map(function (l) { return l.slice() })
      for (var it = 0; it < SWEEPS; it += 1) {
        for (var l2 = 1; l2 < order.length; l2 += 1) sortLayer(order[l2], indexMap(order[l2 - 1]))
        for (var l3 = order.length - 2; l3 >= 0; l3 -= 1) sortLayer(order[l3], indexMap(order[l3 + 1]))
        var c2 = countCrossings(order)
        if (c2 < best) { best = c2; bestOrder = order.map(function (l) { return l.slice() }) }
      }
      order = bestOrder

      // ---------- 4. 坐标 ----------
      var isDummy = function (id) { return idSet[id] !== true }
      var sizes = {}
      var label = {}
      ids.forEach(function (id) {
        var size = metrics && metrics.sizeOf ? metrics.sizeOf(id, NODE_W * 2) : { w: NODE_W, h: NODE_H }
        sizes[id] = { w: size.w, h: size.h }
        label[id] = metrics && metrics.label ? metrics.label[id] : undefined
      })
      var rowH = function (id) { return isDummy(id) ? DUMMY_H : sizes[id].h }

      // 一列一个宽度：层内左沿对齐是分层图可读性的底线，逐个按文字定宽会排出
      // 七个不同的右沿。取全图最宽的那个名字定列宽，所有节点一样宽。
      var columnW = 0
      ids.forEach(function (id) { if (sizes[id].w > columnW) columnW = sizes[id].w })
      ids.forEach(function (id) { sizes[id].w = columnW })

      var layerHeights = order.map(function (l) {
        var total = 0
        l.forEach(function (id) { total += rowH(id) })
        return total + Math.max(0, l.length - 1) * GAP_Y
      })
      var maxH = 0
      layerHeights.forEach(function (h) { if (h > maxH) maxH = h })

      var placed = []
      var dummyPos = {}
      var placeOfId = {}
      // 反向边（回向边）的虚节点不放在行里：放到整张图下面的一条旁路上。
      // 放在行里的话，它从源节点的右侧端口一路横穿过去，会穿过同层其它盒子。
      var bypassY = MARGIN + maxH + 34
      // 已经画在屏幕上的节点位置冻结：点开上/下展开时，原来的节点不许跳。
      //
      // 以前每层都按自己的高度垂直居中，新节点一进来就把老层整体推走——
      // 实测点一次 ↓，父节点下移 81px。这里改成：有位置的照旧，没位置的往
      // 该层「已有内容的下方」排。整张图第一次画（没有任何位置）时行为不变。
      var frozen = {}
      if (typeof placedAt === 'function') {
        ids.forEach(function (id) {
          var at = placedAt(id)
          if (at === null || at === undefined) return
          if (typeof at.x !== 'number' || typeof at.y !== 'number') return
          frozen[id] = { x: at.x, y: at.y, w: at.w, h: at.h, layer: at.layer }
        })
      }
      var frozenCount = Object.keys(frozen).length
      // 冻结节点的层不动：它已经在那一列了，重算层只会让它在列之间跳。
      var frozenLayers = {}
      Object.keys(frozen).forEach(function (id) { frozenLayers[frozen[id].layer] = true })

      order.forEach(function (layerNodes, l) {
        var colX = MARGIN + l * (columnW + GAP_X)
        var y = MARGIN + (maxH - layerHeights[l]) / 2
        // 这一层里已经站着的节点，按它们的 y 排好，新节点接在下面。
        var standing = []
        if (frozenCount > 0) {
          layerNodes.forEach(function (id) {
            if (frozen[id] !== undefined) standing.push(frozen[id])
          })
          standing.sort(function (a, b) { return a.y - b.y })
          if (standing.length > 0) {
            var bottom = standing[standing.length - 1]
            y = bottom.y + bottom.h + GAP_Y
            colX = standing[0].x
          }
        }
        layerNodes.forEach(function (id) {
          if (isDummy(id)) {
            if (reversedDummy[id] === true) {
              // 底部旁路：只占 x，y 统一在图下方。
              dummyPos[id] = { x: colX + columnW / 2, y: bypassY }
              return
            }
            dummyPos[id] = { x: colX + columnW, y: y + DUMMY_H / 2 }
            y += DUMMY_H + GAP_Y
            return
          }
          if (frozen[id] !== undefined) {
            // 位置照旧，一个像素都不动；只把它记进 placeOfId 供布线用。
            var keep = frozen[id]
            // 宽度也用**它画着时的那一个**：新来一个名字更长的邻居会把全图
            // 列宽推大，跟着走的话老卡片会自己变宽——那也是一种跳变。
            var keepW = typeof keep.w === 'number' ? keep.w : sizes[id].w
            var keepRec = {
              id: id, node: graph.nodes[id], anchor: graph.nodes[id],
              x: keep.x, y: keep.y, w: keepW, h: sizes[id].h,
              file: graph.nodes[id].file,
              layer: keep.layer, tree: 0,
              label: label[id],
              ports: portsFor(keep.x, keep.y, keepW, sizes[id].h),
              flowDir: 'ltr',
              boxKey: graph.nodes[id].file,
              frozen: true,
            }
            placed.push(keepRec)
            placeOfId[id] = keepRec
            return
          }
          var w = sizes[id].w
          var h = sizes[id].h
          var rec = {
            id: id, node: graph.nodes[id], anchor: graph.nodes[id],
            x: colX, y: y, w: w, h: h,
            file: graph.nodes[id].file,
            layer: l, tree: 0,
            label: label[id],
            ports: portsFor(colX, y, w, h),
            flowDir: 'ltr',
            boxKey: graph.nodes[id].file,
          }
          placed.push(rec)
          placeOfId[id] = rec
          y += h + GAP_Y
        })
      })

      // ---------- 边 → polylines（emit 直接吃这个） ----------
      var polylines = []
      dagEdges.forEach(function (d, i) {
        var a = placeOfId[d.edge.from]
        var b = placeOfId[d.edge.to]
        if (a === undefined || b === undefined) return
        var dummies = (dummyOfEdge[i] || []).map(function (k) {
          var p = dummyPos[k]
          return p === undefined ? null : { x: p.x, y: p.y }
        }).filter(Boolean)
        var types = d.edge.types || ['call']
        // 反向边（回向边）走底部旁路。光有旁路点不够：直接从源节点的右侧端口
        // 连到旁路点，会横穿源节点自己那一层的其它盒子。所以拆成三段——
        //   从端口先下降到旁路高度（垂直，贴着端口那一列的右沿，不压任何盒子）
        //   → 沿旁路横走到目标那一列
        //   → 再垂直上升到目标端口
        var pts
        if (d.reversed && dummies.length > 0) {
          var startPort = a.ports.out
          var endPort = b.ports.in
          pts = [{ x: startPort.x, y: startPort.y }]
          pts.push({ x: startPort.x, y: bypassY })
          pts = pts.concat(dummies.slice(0, dummies.length - 1))
          pts.push({ x: endPort.x, y: bypassY })
          pts.push({ x: endPort.x, y: endPort.y })
        } else {
          pts = [a.ports.out].concat(dummies).concat([b.ports.in])
        }
        polylines.push({
          id: d.edge.from + '\u2192' + d.edge.to + ':' + types.join(','),
          from: d.edge.from, to: d.edge.to,
          type: types[0], types: types,
          reversed: d.reversed,
          faded: false,
          fromFile: a.file, toFile: b.file,
          pts: pts,
          sourcePort: { side: 'right', point: a.ports.out },
          targetPort: { side: 'left', point: b.ports.in },
          status: 'ok',
        })
      })

      return {
        placed: placed,
        polylines: polylines,
        canvasY: bypassY + 60,
        crossings: best,
        layers: layerCount,
        width: MARGIN * 2 + layerCount * columnW + Math.max(0, layerCount - 1) * GAP_X,
        height: MARGIN * 2 + maxH,
      }
    }

    module.exports = { sugiyama }
    return module.exports
  },
})
