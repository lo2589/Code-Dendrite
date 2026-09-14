// dsh-cdd-lens — 文件框网格：节点按文件装进框，框铺成网格，宽度贴屏幕、只往下长。
//
// 用户原话：「用文件框把节点放了吧，乱堆着也看不清」，排法选的是 B（文件框网格）。
//   树里的节点  → 按文件装框；跨文件的边往外指得多的文件排前面；框逐个放进当前最矮的一格
//   旁边的 seed → 同样装框，放在树的下面，标「旁边」
//   框里的节点  → 按行号从上往下；一个文件节点多（> BIG）就在框里排两列、占两格
// 展开不跳：画过的卡片宽度不变（新来的长名字在卡片里折行）；画过的框留在原来那一格、
//           不高于原来的位置；框里画过的节点保持原来的先后，新节点接在后面。
// 线：每条边一根，从源节点右口到目标节点左口（emit 出贝塞尔）。
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/fileGrid',
  factory: (require) => {
    var module = { exports: {} }
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var placeOf = __graph_model.placeOf
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var BIG = 10
    var PORT_OFFSET = 0.5
    var SECTION_GAP = 36

    function portsFor(x, y, w, h) {
      return { in: { x: x - PORT_OFFSET, y: y + h / 2 }, out: { x: x + w + PORT_OFFSET, y: y + h / 2 } }
    }

    function shortFile(file) {
      var parts = String(file || '').split('/')
      return parts.length <= 2 ? String(file) : '…/' + parts.slice(-2).join('/')
    }

    /** 画过的位置（同一种：树 / 旁边），没有就是 null。 */
    function known(graph, id, side) {
      var at = placeOf(graph, id)
      if (at === null || typeof at.x !== 'number' || typeof at.y !== 'number') return null
      return (at.side === true) === side ? at : null
    }

    /** 文件 → 这个文件里的节点：画过的按原来的列、原来的上下，新的按行号接在后面。 */
    function byFileOf(graph, ids, side) {
      var out = {}
      ids.forEach(function (id) {
        var file = graph.nodes[id].file
        if (out[file] === undefined) out[file] = []
        out[file].push(id)
      })
      Object.keys(out).forEach(function (file) {
        out[file].sort(function (a, b) {
          var pa = known(graph, a, side)
          var pb = known(graph, b, side)
          if (pa !== null && pb !== null) return pa.x - pb.x || pa.y - pb.y
          if (pa !== null || pb !== null) return pa !== null ? -1 : 1
          return (graph.nodes[a].line_start || 0) - (graph.nodes[b].line_start || 0) || (a < b ? -1 : 1)
        })
      })
      return out
    }

    /** 文件的先后：跨文件的边往外指得多的排前面，线大多从前面的框指向后面的框。 */
    function fileOrderOf(graph, byFile) {
      var fileOf = {}
      Object.keys(byFile).forEach(function (file) { byFile[file].forEach(function (id) { fileOf[id] = file }) })
      var score = {}
      Object.keys(byFile).forEach(function (file) { score[file] = 0 })
      graph.edges.forEach(function (e) {
        var a = fileOf[e.from]
        var b = fileOf[e.to]
        if (a === undefined || b === undefined || a === b) return
        score[a] += 1
        score[b] -= 1
      })
      return Object.keys(score).sort(function (l, r) { return score[r] - score[l] || (l < r ? -1 : l > r ? 1 : 0) })
    }

    /** 画过的框在哪一格、多高：从框里画过的节点反推；对不上网格（格宽变了）就当没画过。 */
    function boxMemory(graph, byFile, g, side) {
      var memory = {}
      Object.keys(byFile).forEach(function (file) {
        var seen = byFile[file].map(function (id) { return known(graph, id, side) }).filter(Boolean)
        if (seen.length === 0) return
        var minX = Math.min.apply(null, seen.map(function (p) { return p.x }))
        var minY = Math.min.apply(null, seen.map(function (p) { return p.y }))
        var col = Math.round((minX - g.pad - g.left) / (g.cellW + g.gapX))
        var aligned = Math.abs(g.left + col * (g.cellW + g.gapX) + g.pad - minX) < 1
        if (col >= 0 && col < g.cols && aligned) memory[file] = { col: col, y: minY - g.head }
      })
      return memory
    }

    /** 一个框多大：节点竖排；节点多、网格又至少两格宽时，框里排两列。 */
    function measureBox(ids, g) {
      var inner = ids.length > BIG && g.cols >= 2 ? 2 : 1
      var perCol = Math.ceil(ids.length / inner)
      var tallest = 0
      for (var c = 0; c < inner; c += 1) {
        var part = ids.slice(c * perCol, (c + 1) * perCol)
        var h = part.reduce(function (sum, id) { return sum + g.size[id].h }, 0) + Math.max(0, part.length - 1) * g.innerY
        if (h > tallest) tallest = h
      }
      return { inner: inner, perCol: perCol, w: inner * g.cardW + (inner - 1) * g.innerX + 2 * g.pad, h: g.head + tallest + g.pad }
    }

    /** 框里的节点坐标。框里每一列算一层：同一层左沿对齐、宽度一致。 */
    function seatNodes(graph, file, ids, box, x, y, g, side, placed) {
      for (var c = 0; c < box.inner; c += 1) {
        var ny = y + g.head
        var nx = x + g.pad + c * (g.cardW + g.innerX)
        var layer = 'box:' + (side ? 'side:' : '') + file + ':' + c
        ids.slice(c * box.perCol, (c + 1) * box.perCol).forEach(function (id) {
          var h = g.size[id].h
          placed.push({
            id: id, node: graph.nodes[id], anchor: graph.nodes[id],
            x: nx, y: ny, w: g.cardW, h: h,
            file: file, layer: layer, tree: 0, label: g.label[id],
            ports: portsFor(nx, ny, g.cardW, h), flowDir: 'ltr', boxKey: file, side: side,
          })
          ny += h + g.innerY
        })
      }
    }

    /** 这个框放哪一格：画过的回原来那格（上面的框长高了才往下让）；新的放进最矮的格。 */
    function slotFor(heights, box, mem, g) {
      if (mem !== undefined && mem.col + box.inner <= g.cols) {
        return { col: mem.col, y: Math.max(mem.y, Math.max.apply(null, heights.slice(mem.col, mem.col + box.inner))) }
      }
      var best = { col: 0, y: Infinity }
      for (var col = 0; col + box.inner <= g.cols; col += 1) {
        var y = Math.max.apply(null, heights.slice(col, col + box.inner))
        if (y < best.y) best = { col: col, y: y }
      }
      return best
    }

    /**
     * 一段（树 / 旁边）：画过的框按原来的上下先放回去，新框再放进最矮的格。
     * @returns 这一段的底（最高那格的下沿）。
     */
    function packSection(graph, byFile, files, top, g, side, placed, boxes) {
      var memory = boxMemory(graph, byFile, g, side)
      var old = files.filter(function (f) { return memory[f] !== undefined })
        .sort(function (a, b) { return memory[a].y - memory[b].y || memory[a].col - memory[b].col })
      var fresh = files.filter(function (f) { return memory[f] === undefined })
      var heights = []
      for (var c = 0; c < g.cols; c += 1) heights.push(top)
      old.concat(fresh).forEach(function (file) {
        var ids = byFile[file]
        var box = measureBox(ids, g)
        var slot = slotFor(heights, box, memory[file], g)
        var x = g.left + slot.col * (g.cellW + g.gapX)
        for (var k = slot.col; k < slot.col + box.inner; k += 1) heights[k] = slot.y + box.h + g.gapY
        boxes.push({ file: file, label: shortFile(file), x: x, y: slot.y, w: box.w, h: box.h, count: ids.length, frame: side ? 'side' : 'tree' })
        seatNodes(graph, file, ids, box, x, slot.y, g, side, placed)
      })
      return Math.max.apply(null, heights) - g.gapY
    }

    function polylinesFor(graph, placed) {
      var byId = {}
      placed.forEach(function (p) { byId[p.id] = p })
      var out = []
      graph.edges.forEach(function (e) {
        var a = byId[e.from]
        var b = byId[e.to]
        if (a === undefined || b === undefined) return
        var types = e.types || ['call']
        out.push({
          id: e.from + '→' + e.to + ':' + types.join(','),
          from: e.from, to: e.to, type: types[0], types: types, reversed: false, faded: false,
          fromFile: a.file, toFile: b.file, pts: [a.ports.out, b.ports.in],
          sourcePort: { side: 'right', point: a.ports.out }, targetPort: { side: 'left', point: b.ports.in },
          status: 'ok',
        })
      })
      return out
    }

    /** 卡片宽：画过就沿用画过的宽（新来的长名字折行），没画过取最宽的名字。 */
    function cardWidth(graph, included, side, metrics) {
      var drawn = 0
      included.forEach(function (id) { var at = known(graph, id, false); if (at !== null && at.w > drawn) drawn = at.w })
      side.forEach(function (id) { var at = known(graph, id, true); if (at !== null && at.w > drawn) drawn = at.w })
      var size = {}
      var widest = 0
      included.concat(side).forEach(function (id) {
        size[id] = drawn > 0 ? metrics.sizeOf(id, drawn) : metrics.sizeOf(id)
        if (size[id].w > widest) widest = size[id].w
      })
      var cardW = drawn > 0 ? drawn : widest
      // 浏览器里真画出来的高度（同一个卡片宽量的）优先：按 CSS 估的高度估小了，卡片会撑出文件框、压到下一个框。
      var measured = shared.cardHeights || {}
      Object.keys(size).forEach(function (id) {
        var m = measured[id]
        if (m && Math.abs(m.w - cardW) < 1 && m.h > 0) size[id] = { w: size[id].w, h: m.h }
      })
      return { cardW: cardW, size: size }
    }

    /**
     * @param included - 树里的节点（screen.nodes）。
     * @param side - 旁边的 seed（screen.side）。
     * @returns { placed, polylines, boxes, rows, cols, canvasY }
     */
    function placeFileGrid(graph, included, side, metrics, avail) {
      var card = cardWidth(graph, included, side, metrics)
      var pad = metrics.BOX_PAD
      var gapX = metrics.BOX_GAP_X
      var cellW = card.cardW + 2 * pad
      var usable = Math.max(cellW, (avail || 0) - 2 * metrics.PAD)
      var g = {
        cols: Math.max(1, Math.floor((usable + gapX) / (cellW + gapX))),
        cellW: cellW, cardW: card.cardW, pad: pad, gapX: gapX, gapY: metrics.BOX_GAP_Y,
        head: metrics.BOX_HEAD, innerY: metrics.INNER_GAP_Y,
        // 框里两列的间距取「两格之间的距离」，排两列的框正好占满两格。
        innerX: 2 * pad + gapX,
        left: metrics.PAD, size: card.size, label: metrics.label,
      }
      var placed = []
      var boxes = []
      var rows = []
      var bottom = metrics.PAD
      if (included.length > 0) {
        var tree = byFileOf(graph, included, false)
        bottom = packSection(graph, tree, fileOrderOf(graph, tree), metrics.PAD, g, false, placed, boxes)
      }
      if (side.length > 0) {
        var labelY = included.length > 0 ? bottom + SECTION_GAP : metrics.PAD + 16
        rows.push({ x: metrics.PAD, y: labelY, label: '旁边 · 不在当前树里的 seed（' + side.length + '）', ids: side, island: false })
        var rest = byFileOf(graph, side, true)
        bottom = packSection(graph, rest, Object.keys(rest).sort(), labelY + 8, g, true, placed, boxes)
      }
      return { placed: placed, polylines: polylinesFor(graph, placed), boxes: boxes, rows: rows, cols: g.cols, canvasY: bottom }
    }

    module.exports = { placeFileGrid }
    return module.exports
  },
})
