// dsh-cdd-lens — One screen in, one drawing out.
//
// 画什么只认 shared.screen（后端计算单元 src/compute 的结果）：
//   screen.nodes → 分层布局（layout/sugiyama）
//   screen.side  → 不在当前树里的 seed，堆到树的下面，排成等宽的列
//   screen.edges → 一条不少地出线（一条边一种类型）
// 这里不做任何筛选：不看按钮状态、不看关系开关、不挑主干。
//
// 两段：结构（尺寸、分层、旁边的位置）只在图变了时重算并缓存；
// 拖动、选中、高亮这类不改图的更新只重放「坐标 → 接线 → 出线」，不重排。
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/layout',
  factory: (require) => {
    var module = { exports: {} }
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var placeOf = __graph_model.placeOf
    var setPlace = __graph_model.setPlace
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note
    var fact = __runtime_debug.fact
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
      return Object.assign({}, line, {
        pts: [a.ports.out].concat(middle).concat([b.ports.in]),
        sourcePort: { side: 'right', point: a.ports.out },
        targetPort: { side: 'left', point: b.ports.in },
      })
    }

    function bindPolylineSet(polylines, byId) {
      return polylines.map(function (line) { return bindPolylineEndpoints(line, byId) })
    }

    /** 屏幕上画什么：只认 shared.screen，不筛选。 */
    function screenScope(graph) {
      var screen = shared.screen || { nodes: [], side: [] }
      var has = function (id) { return graph.nodes[id] !== undefined }
      var included = screen.nodes.filter(has)
      var side = screen.side.filter(has)
      var fileOrder = []
      included.concat(side).forEach(function (id) {
        var file = graph.nodes[id].file
        if (fileOrder.indexOf(file) < 0) fileOrder.push(file)
      })
      return { included: included, side: side, fileOrder: fileOrder }
    }

    /**
     * 不在当前树里的 seed：堆到树的下面，排成等宽的列（每列左沿对齐，列间留足角标的净空）。
     * 画过的位置记住，下次照旧——树长高了旁边的节点也不跳；新来的接在已有的下面。
     */
    function placeSide(graph, side, metrics, top, avail) {
      if (side.length === 0) return []
      var gapX = metrics.LAYER_GAP_X
      var gapY = metrics.BOX_GAP_Y
      var width = side.reduce(function (m, id) { return Math.max(m, metrics.sizeOf(id).w) }, 0)
      var usable = Math.max(width, (avail || 0) - metrics.PAD * 2)
      var cols = Math.max(1, Math.floor((usable + gapX) / (width + gapX)))
      var known = {}
      var bottom = top - gapY
      side.forEach(function (id) {
        var at = placeOf(graph, id)
        if (at === null || at.side !== true || typeof at.x !== 'number' || typeof at.y !== 'number') return
        known[id] = at
        bottom = Math.max(bottom, at.y + at.h)
      })
      var col = 0
      var y = bottom + gapY
      var rowH = 0
      return side.map(function (id) {
        var node = graph.nodes[id]
        var h = metrics.sizeOf(id).h
        var rec = {
          id: id, node: node, anchor: node, w: width, h: h,
          file: node.file, tree: 0, label: metrics.label[id],
          flowDir: 'ltr', boxKey: node.file, side: true,
        }
        if (known[id] !== undefined) {
          rec.x = known[id].x
          rec.y = known[id].y
          rec.layer = known[id].layer
        } else {
          if (col >= cols) { col = 0; y += rowH + gapY; rowH = 0 }
          rec.x = metrics.PAD + col * (width + gapX)
          rec.y = y
          rec.layer = 'side:' + col
          col += 1
          if (h > rowH) rowH = h
        }
        rec.ports = portsFor(rec)
        return rec
      })
    }

    function relationStats(graph, wires) {
      var stats = {}
      graph.edges.forEach(function (e) {
        var type = e.types[0]
        if (stats[type] === undefined) stats[type] = { total: 0, drawn: 0 }
        stats[type].total += 1
      })
      wires.forEach(function (w) { if (stats[w.type] !== undefined) stats[w.type].drawn += 1 })
      return stats
    }

    /** 记住这次画出来的位置：已有同类（树 / 旁边）位置的不改，身份变了的重记。 */
    function rememberPlaces(graph, place) {
      place.placed.forEach(function (p) {
        var known = placeOf(graph, p.id)
        if (known !== null && (known.side === true) === (p.side === true)) return
        setPlace(graph, p.id, { x: p.x, y: p.y, w: p.w, h: p.h, layer: p.layer, ports: p.ports, side: p.side === true })
      })
    }

    // ---- 结构缓存：图没变就不重排 ----------------------------------------------
    var cached = { graph: null, screen: null, key: null, value: null }

    /** 会改变结构的东西：节点数、边数、画布宽度、类成员展开了多少行。 */
    function structureKey(graph, avail) {
      var memberRows = 0
      graph.order.forEach(function (id) {
        var ui = graph.ui[id]
        if (ui && ui.members && ui.memberList) memberRows += ui.memberList.length + 1
      })
      return [graph.order.length, graph.edges.length, avail || 0, memberRows].join('|')
    }

    function structure(graph, avail) {
      var key = structureKey(graph, avail)
      if (cached.graph === graph && cached.screen === shared.screen && cached.key === key) return cached.value
      var t0 = Date.now()
      var scope = screenScope(graph)
      var metrics = boxMetrics(graph, { included: scope.included.concat(scope.side), fileOrder: scope.fileOrder }, avail)
      // 树：分层布局；画过的树节点位置冻结（旁边的旧位置不算，进树要重新排）。
      var laid = sugiyama(graph, scope.included, metrics, function (id) {
        var known = placeOf(graph, id)
        if (known === null || known.side === true || typeof known.x !== 'number' || typeof known.y !== 'number') return null
        return known
      })
      var sideTop = laid.placed.length > 0 ? laid.canvasY : metrics.PAD
      var sidePlaced = placeSide(graph, scope.side, metrics, sideTop, avail)
      var value = { scope: scope, metrics: metrics, laid: laid, sidePlaced: sidePlaced }
      cached = { graph: graph, screen: shared.screen, key: key, value: value }
      note('layout', '重排结构：树 ' + scope.included.length + ' · 旁边 ' + scope.side.length + ' · 边 ' + graph.edges.length
        + ' · 层 ' + laid.layers + ' · ' + (Date.now() - t0) + 'ms')
      return value
    }

    /**
     * Turn one screen into one drawing.
     *
     * @param graph - shared.graph，由 /screen 原样生成。
     * @param _unused - 旧的关系筛选参数，已不再使用（筛选只在计算单元里）。
     * @param avail - the canvas viewport width in CSS pixels。
     */
    function layout(graph, _unused, avail) {
      if (graph.rootId === null) {
        return { nodes: [], wires: [], labels: [], junctions: [], arrows: [], rows: [], files: [], width: 0, height: 0 }
      }
      var s = structure(graph, avail)
      // 选中、高亮、按钮加载中这类 publish 不改画面位置：原样交回上一张，线层和卡片都认得出「没变」。
      var key = drawKeyOf(avail)
      if (lastDrawn.structure === s && lastDrawn.key === key) return lastDrawn.value
      var value = draw(graph, s, avail)
      lastDrawn = { structure: s, key: key, value: value }
      return value
    }

    // ---- 画面缓存：结构和下面这些输入都没变，就是同一张图 ------------------------
    var lastDrawn = { structure: null, key: null, value: null }

    /** 结构之外还会改变坐标的输入：画布宽、手工拖过的位置、收拢状态、链路聚焦（聚焦时不收拢）。 */
    function drawKeyOf(avail) {
      var gather = ''
      try { gather = JSON.stringify(shared.gather || null) } catch (e) { gather = String(Date.now()) }
      return [avail || 0, JSON.stringify(shared.nodePositions || {}), gather, shared.edgeFocus ? 1 : 0].join('\n')
    }

    function draw(graph, s, avail) {
      var metrics = s.metrics
      // 每次画都从缓存的结构拷一份记录出来：拖动、收拢、推开重叠只改这份拷贝。
      var placed = s.laid.placed.concat(s.sidePlaced).map(function (p) { return Object.assign({}, p) })
      var sideBottom = s.sidePlaced.reduce(function (m, p) { return Math.max(m, p.y + p.h) }, 0)
      var place = { placed: placed, rows: [], canvasY: Math.max(s.laid.canvasY, sideBottom + metrics.BOX_GAP_Y) }

      // 手工拖过的坐标原样生效；跑偏的拉回来，再推开重叠。
      applySavedPositions(place, shared.nodePositions || {})
      freeGatherDragged(place)
      reclaimStrays(place, metrics, avail)
      var orient = { byId: {} }
      place.placed.forEach(function (p) { orient.byId[p.id] = p })
      applyGather(graph, place, metrics)
      separateOverlaps(place, metrics)
      syncPorts(place)

      // ---- 出线：每条边一根线，一条不少 ----
      var polylines = bindPolylineSet(s.laid.polylines, orient.byId)
      var hops = { hSegs: new Map(), segments: [] }
      var drawn = emitWires({ polylines: polylines, hSegs: hops.hSegs, WIRE_CORNER: metrics.WIRE_CORNER, ARROW_EVERY: metrics.ARROW_EVERY }, hops)

      // ---- 尺寸：从画出来的东西反推 ----
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
      rememberPlaces(graph, place)

      var relations = relationStats(graph, drawn.wires)
      shared.wireStats = { drawn: drawn.wires.length, hidden: 0, total: graph.edges.length, relations: relations }
      fact('layout', place.placed.length + 'n/' + drawn.wires.length + 'w/' + (s.laid.layers || 0) + 'L')
      return {
        nodes: place.placed, wires: drawn.wires, labels: drawn.labels,
        junctions: drawn.junctions, arrows: drawn.arrows, unrouted: drawn.unrouted,
        rows: [], files: [],
        layers: s.laid.layers,
        crossings: s.laid.crossings,
        stats: { nodes: place.placed.length, wires: drawn.wires.length, relations: relations, wireTotal: graph.edges.length },
        arrowEvery: metrics.ARROW_EVERY,
        width: Math.max(avail || 0, fit.maxX + metrics.PAD),
        height: Math.max(360, fit.maxY + metrics.PAD),
      }
    }

    /** 手工拖过的坐标原样写上，不然每次重画都会把用户摆好的东西弹回去。 */
    function applySavedPositions(place, positions) {
      if (positions === null || positions === undefined) return
      place.placed.forEach(function (p) {
        var at = positions[p.id]
        if (at === undefined || typeof at.x !== 'number' || typeof at.y !== 'number') return
        p.x = at.x
        p.y = at.y
        p.manual = true
        p.ports = portsFor(p)
      })
    }

    module.exports = { layout }
    return module.exports
  },
})
