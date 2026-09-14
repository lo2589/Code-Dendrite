// dsh-cdd-lens — One graph in, one drawing out: the stages in order.
//
// 只有一条路径，没有皮肤。分层由 layout/sugiyama 自己算——不再问服务端要 `/chain`。
//
// 这条管线是照 /Users/a1/Workspace/WORKSPACE/visual_map 重写的：
//   数据(graph) → 分层布局(sugiyama) → 边折线(polylines) → emit 成 SVG 路径
// visual_map 里布局与布线解耦，靠的是 `edge.bendPoints` 这一个契约；这里也一样，
// sugiyama 把跨层边的拐点算好放进 pts，emit 只管照着画。
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/layout',
  factory: (require) => {
    var module = { exports: {} }
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note
    var fact = __runtime_debug.fact
    var placeOf = __graph_model.placeOf
    var setPlace = __graph_model.setPlace
    var __layout_prep = require('dsh-cdd-lens/layout/prep')
    var layoutScope = __layout_prep.layoutScope
    var __layout_metrics = require('dsh-cdd-lens/layout/metrics')
    var boxMetrics = __layout_metrics.boxMetrics
    var __layout_sugiyama = require('dsh-cdd-lens/layout/sugiyama')
    var sugiyama = __layout_sugiyama.sugiyama
    var __layout_space = require('dsh-cdd-lens/layout/space')
    var reclaimStrays = __layout_space.reclaimStrays
    var separateOverlaps = __layout_space.separateOverlaps
    var fitExtent = __layout_space.fitExtent
    var shiftDrawing = __layout_space.shiftDrawing
    var __layout_gather = require('dsh-cdd-lens/layout/gather')
    var applyGather = __layout_gather.applyGather
    var freeGatherDragged = __layout_gather.freeGatherDragged
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __routing_select = require('dsh-cdd-lens/routing/select')
    var chooseEdges = __routing_select.chooseEdges
    var __routing_emit = require('dsh-cdd-lens/routing/emit')
    var emitWires = __routing_emit.emitWires
    var PORT_OFFSET = 0.5

    function portsFor(p) {
      return {
        in: { x: p.x - PORT_OFFSET, y: p.y + p.h / 2 },
        out: { x: p.x + p.w + PORT_OFFSET, y: p.y + p.h / 2 },
      }
    }

    function syncPorts(place) {
      place.placed.forEach(function (p) { p.ports = portsFor(p) })
    }

    function bindPolylineEndpoints(line, byId) {
        var a = byId[line.from]
        var b = byId[line.to]
        if (a === undefined || b === undefined) return line
        var middle = (line.pts || []).slice(1, -1).map(function (pt) { return { x: pt.x, y: pt.y } })
        var pts = [a.ports.out].concat(middle).concat([b.ports.in])
        return Object.assign({}, line, {
          pts: pts,
          sourcePort: { side: 'right', point: a.ports.out },
          targetPort: { side: 'left', point: b.ports.in },
        })
    }

    function bindPolylineSet(polylines, byId) {
      return polylines.map(function (line) { return bindPolylineEndpoints(line, byId) })
    }

    function allowedTypes(types, relationFilter) {
      if (relationFilter === undefined || relationFilter === null) return types
      return types.filter(function (type) { return relationFilter[type] !== false })
    }

    function finalPolylines(lines, picked, byId, relationFilter) {
      return bindPolylineSet(lines.filter(function (line) {
        var types = allowedTypes(line.types || [line.type || 'call'], relationFilter)
        return types.length > 0
          && picked[line.from + '\u0000' + line.to] === true
      }).map(function (line) {
        var types = allowedTypes(line.types || [line.type || 'call'], relationFilter)
        return Object.assign({}, line, {
          id: line.from + '\u2192' + line.to + ':' + types.join(','),
          type: types[0],
          types: types,
        })
      }), byId)
    }

    /**
     * Turn one graph into one drawing.
     *
     * @param graph - nodes and edges to draw。
     * @param relationFilter - relation kinds the viewer left switched on。
     * @param avail - the canvas viewport width in CSS pixels。
     * @returns nodes, wires, labels, junctions, arrows, file boxes and size。
     */
    function layout(graph, relationFilter, avail) {
      if (graph.rootId === null) {
        note('layout', 'rootId=null，没有起点可用（nodes=' + Object.keys(graph.nodes).length + '）')
        return { nodes: [], wires: [], labels: [], junctions: [], arrows: [], rows: [], files: [], width: 0, height: 0 }
      }
      var scope = layoutScope(graph)
      var metrics = boxMetrics(graph, scope, avail)

      // ---- 会话自己的边要画出来，不管有没有人按过按钮 ----
      //
      // 这是删掉 /among 之后必须补上的一件事：那条路由以前给 bridge 边打
      // `always`。没有它，一个刚 ingest 出来的图里每条边两端都没被按过，
      // select.js 就把它们全部滤掉——画面上就是「一堆卡片，一根线都没有」。
      //
      // 判据不是「谁打的标记」，而是这个节点本身有没有被这次会话碰过：
      // 两个 anchor 都是会话自己的，它们之间的关系就是这次会话要看的答案。
      graph.edges.forEach(function (e) {
        if (e.always === true) return
        var fromUI = uiOf(graph, e.from)
        var toUI = uiOf(graph, e.to)
        var fromSession = fromUI !== null && (fromUI.session === true || fromUI.explored === true)
        var toSession = toUI !== null && (toUI.session === true || toUI.explored === true)
        if (fromSession && toSession) e.always = true
      })

      // ---- 分层布局：消环 → 分层 → 排序 → 坐标，一次全出 ----
      var laid = sugiyama(graph, scope.included, metrics, function (id) {
        var known = placeOf(graph, id)
        // 只认已经真正画过的那一次位置。node 上没有位置 = 它还没上过屏幕。
        if (known === null || typeof known.x !== 'number' || typeof known.y !== 'number') return null
        return known
      })
      var place = {
        placed: laid.placed,
        rows: [],
        canvasY: laid.canvasY,
      }

      // 手工拖过的坐标原样生效；跑偏的拉回来，再推开重叠。
      // 注意顺序：先应用保存的位置，再分离重叠——反过来的话保存的位置会被覆盖。
      applySavedPositions(graph, place, shared.nodePositions || {})
      freeGatherDragged(place)
      reclaimStrays(place, metrics, avail)

      var orient = { byId: {} }
      place.placed.forEach(function (p) { orient.byId[p.id] = p })

      // 选中节点的上下游坐到它旁边，收拢之后才推重叠——反过来的话
      // 收拢列里刚排好的卡片会被分离过程推走。
      applyGather(graph, place, metrics)
      separateOverlaps(place, metrics)
      syncPorts(place)

      // ---- 布线：哪条边值得画 ----
      var edges = chooseEdges(graph, scope, orient, relationFilter)
      var picked = {}
      edges.chosen.forEach(function (e) { picked[e.from + '\u0000' + e.to] = true })

      // ---- 出线：sugiyama 的折线按 id 挂上关系类型，再交给 emit ----
      var polylines = finalPolylines(laid.polylines, picked, orient.byId, relationFilter)
      var kept = {}
      polylines.forEach(function (p) { kept[p.from] = true; kept[p.to] = true })
      // 被 select 滤掉的边不画，但线两端的节点仍然要留着。
      var hops = { hSegs: new Map(), segments: [] }
      var drawn = emitWires({ polylines: polylines, hSegs: hops.hSegs, WIRE_CORNER: metrics.WIRE_CORNER, ARROW_EVERY: metrics.ARROW_EVERY }, hops)

      // ---- 尺寸：从画出来的东西反推 ----
      // 手工坐标可能把某个节点放到负坐标（画布原点左边/上边）。那时整张图
      // 往右下挪一屏边距，挪完再重新出线——布线不变，只是原点移了位置。
      var fit = fitExtent(place, drawn, metrics)
      if (fit.dx > 0 || fit.dy > 0) {
        shiftDrawing(place, { polylines: polylines }, fit.dx, fit.dy)
        syncPorts(place)
        orient.byId = {}
        place.placed.forEach(function (p) { orient.byId[p.id] = p })
        polylines = bindPolylineSet(polylines, orient.byId)
        drawn = emitWires({ polylines: polylines, hSegs: hops.hSegs, WIRE_CORNER: metrics.WIRE_CORNER, ARROW_EVERY: metrics.ARROW_EVERY }, hops)
        fit = fitExtent(place, drawn, metrics)
      }
      // 只记录第一次上屏的位置。之后普通布局、选中、高亮、过滤、画布尺寸变化
      // 都不许改它；只有用户拖动走 shared.nodePositions 才能覆盖。
      place.placed.forEach(function (p) {
        if (placeOf(graph, p.id) !== null) return
        setPlace(graph, p.id, {
          x: p.x, y: p.y, w: p.w, h: p.h, layer: p.layer,
          ports: p.ports,
        })
      })

      var maxX = fit.maxX, maxY = fit.maxY

      fact('layout', place.placed.length + 'n/' + drawn.wires.length + 'w/' + (laid.layers || 0) + 'L')
      note('layout', 'in=' + Object.keys(graph.nodes).length + ' edges=' + graph.edges.length
        + ' -> placed=' + place.placed.length + ' wires=' + drawn.wires.length + ' layers=' + laid.layers)
      return {
        nodes: place.placed, wires: drawn.wires, labels: drawn.labels,
        junctions: drawn.junctions, arrows: drawn.arrows, unrouted: drawn.unrouted,
        rows: [], files: [],
        layers: laid.layers,
        crossings: laid.crossings,
        stats: {
          nodes: place.placed.length,
          wires: drawn.wires.length,
          relations: edges.stats.relations,
          wireTotal: edges.stats.total,
        },
        width: Math.max(avail || 0, maxX + metrics.PAD),
        height: Math.max(360, maxY + metrics.PAD),
      }
    }

    /**
     * 手工拖过的坐标原样写上。
     *
     * 分层布局先给出建议位置，用户拖过的那一个覆盖它——不然每次重画都会把用户
     * 摆好的东西弹回去。
     */
    function applySavedPositions(graph, place, positions) {
      if (positions === null || positions === undefined) return
      place.placed.forEach(function (p) {
        var at = positions[p.id]
        if (at === undefined || typeof at.x !== 'number' || typeof at.y !== 'number') return
        p.x = at.x
        p.y = at.y
        p.manual = true
        p.ports = {
          in: { x: p.x, y: p.y + p.h / 2 },
          out: { x: p.x + p.w, y: p.y + p.h / 2 },
        }
      })
    }

    module.exports = { layout }
    return module.exports
  },
})
