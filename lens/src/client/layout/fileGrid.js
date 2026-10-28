// dsh-cdd-lens — 文件框网格，按用户定的排法：
//
//   1. 算显示区域：能放几列 = 可用宽度 ÷ 一格宽
//   2. 算每个文件框大小：框里 anchor 单列竖排
//   3. 从左往右轮着摆，第一行顶端对齐；
//      后面的行「根据上一个排」：放在那一列上一个框的下面，中间空一个 anchor 的高度
//   4. 先算距离：文件夹之间、文件之间边多的挨着放（顺序挨着 → 格子挨着）
//   5. 每排一行先看各列底边：比最短那列的底边高出「平均文件框高度的一半」的列这一行不填，
//      尽量让一行的文件框底边一致；下一行重算（用户：「比最短边高1/2平均文件框的，就不填，尽量让一行的文件框底边一致」）
//   展开不跳：画过的文件保持原来的先后，新文件接在后面（换会话、恢复自动布局时重新算）
// 旁边的 seed 同样排，放在树的下面。线：每条边一根，从源节点右口到目标节点左口。
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
    var PORT_OFFSET = 0.5
    var SECTION_GAP = 36

    function portsFor(x, y, w, h) {
      return { in: { x: x - PORT_OFFSET, y: y + h / 2 }, out: { x: x + w + PORT_OFFSET, y: y + h / 2 } }
    }

    function shortFile(file) {
      var parts = String(file || '').split('/')
      return parts.length <= 2 ? String(file) : '…/' + parts.slice(-2).join('/')
    }

    function dirOf(file) {
      var parts = String(file || '').split('/')
      return parts.length > 1 ? parts.slice(0, -1).join('/') : '.'
    }

    /** 画过的位置（同一种：树 / 旁边），没有就是 null。 */
    function known(graph, id, side) {
      var at = placeOf(graph, id)
      if (at === null || typeof at.x !== 'number' || typeof at.y !== 'number') return null
      return (at.side === true) === side ? at : null
    }

    /** 文件 → 框里的 anchor（单列）：画过的按原来的上下，新的按行号接在后面。 */
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
          if (pa !== null && pb !== null) return pa.y - pb.y
          if (pa !== null || pb !== null) return pa !== null ? -1 : 1
          return (graph.nodes[a].line_start || 0) - (graph.nodes[b].line_start || 0) || (a < b ? -1 : 1)
        })
      })
      return out
    }

    /** 文件两两之间的边数（不分方向）。 */
    function fileWeights(graph, byFile) {
      var fileOf = {}
      Object.keys(byFile).forEach(function (file) { byFile[file].forEach(function (id) { fileOf[id] = file }) })
      var w = {}
      graph.edges.forEach(function (e) {
        var a = fileOf[e.from]
        var b = fileOf[e.to]
        if (a === undefined || b === undefined || a === b) return
        var k = a < b ? a + '\0' + b : b + '\0' + a
        w[k] = (w[k] || 0) + 1
      })
      return function (a, b) { return a === b ? 0 : w[a < b ? a + '\0' + b : b + '\0' + a] || 0 }
    }

    /**
     * 交流多的挨着：先放和全体交流最多的；之后每次挑和「刚放的一格宽度内那几个」交流最多的，
     * 平手看和已经放好的全体交流多少，再平手按路径。
     * @param window - 往回看几个（= 列数：左边邻居和上面邻居都在这个范围里）。
     */
    function greedyOrder(items, weight, window) {
      var rest = items.slice().sort()
      if (rest.length === 0) return []
      var total = function (x) { return rest.reduce(function (s, y) { return s + weight(x, y) }, 0) }
      var first = rest.slice().sort(function (a, b) { return total(b) - total(a) || (a < b ? -1 : 1) })[0]
      var order = [first]
      rest.splice(rest.indexOf(first), 1)
      while (rest.length > 0) {
        var recent = order.slice(-Math.max(1, window))
        var best = rest[0]
        var bestScore = -1
        rest.forEach(function (x) {
          var near = recent.reduce(function (s, y) { return s + weight(x, y) }, 0)
          var all = order.reduce(function (s, y) { return s + weight(x, y) }, 0)
          var score = near * 100000 + all
          if (score > bestScore) { best = x; bestScore = score }
        })
        order.push(best)
        rest.splice(rest.indexOf(best), 1)
      }
      return order
    }

    /** 先排文件夹（文件夹之间边多的挨着），文件夹里再排文件（文件之间边多的挨着）。 */
    function communicationOrder(files, weight, cols) {
      var folders = {}
      files.forEach(function (f) { (folders[dirOf(f)] = folders[dirOf(f)] || []).push(f) })
      var folderWeight = function (a, b) {
        var s = 0
        folders[a].forEach(function (x) { folders[b].forEach(function (y) { s += weight(x, y) }) })
        return s
      }
      var out = []
      greedyOrder(Object.keys(folders), folderWeight, 1).forEach(function (dir) {
        out = out.concat(greedyOrder(folders[dir], weight, cols))
      })
      return out
    }

    /** 这一段框的先后：画过的保持原来的先后，新文件按交流顺序接在后面；记下来给下次用。 */
    function stableOrder(section, files, weight, cols) {
      shared.boxOrder = shared.boxOrder || {}
      var present = {}
      files.forEach(function (f) { present[f] = true })
      var kept = (shared.boxOrder[section] || []).filter(function (f) { return present[f] === true })
      var keptSet = {}
      kept.forEach(function (f) { keptSet[f] = true })
      var fresh = communicationOrder(files.filter(function (f) { return keptSet[f] !== true }), weight, cols)
      var order = kept.concat(fresh)
      shared.boxOrder[section] = order
      return order
    }

    function boxHeight(ids, g) {
      return g.head + ids.reduce(function (s, id) { return s + g.size[id].h }, 0) + Math.max(0, ids.length - 1) * g.innerY + g.pad
    }

    /**
     * 这一行填哪几列：底边比最短那列高出「平均文件框高度的一半」以上的列不填，尽量让一行底边一致。
     * 门槛跟着框的实际大小走：框普遍矮，差一点就算差得多；框普遍高，差同样多不算什么。
     * 例：底边 [45, 30, 30, 25]、平均框高 30 → 门槛 25 + 15 = 40 → 45 不填，填后 3 列。
     * @param bottoms - 每列现在的底边（还没放框的列 = 这一段的顶）。
     * @param avgBox - 这一段文件框的平均高度（像素）。
     * @returns 这一行要填的列号，从左往右。
     */
    function eligibleColumns(bottoms, avgBox) {
      if (bottoms.length === 0) return []
      var shortest = Math.min.apply(null, bottoms)
      var out = []
      bottoms.forEach(function (b, col) { if (b - shortest <= avgBox / 2 + 1e-6) out.push(col) })
      return out
    }

    /**
     * 一段（树 / 旁边）：一行一行排。每行先挑出不太长的列（eligibleColumns，比最短底边高出平均框高一半的不填），从左往右每列放一个框，
     * 放在那一列上一个框的下面、空一个 anchor 的高度；这一行放完再重算下一行。第一行各列一样高，顶端对齐。
     * @returns 这一段最下面那个框的下沿；没有框时是 top。
     */
    function packSection(graph, byFile, order, top, g, side, placed, boxes) {
      var bottoms = []
      var used = []
      for (var c = 0; c < g.cols; c += 1) { bottoms.push(top); used.push(false) }
      var avgBox = order.length === 0 ? 0 : order.reduce(function (sum, f) { return sum + boxHeight(byFile[f], g) }, 0) / order.length
      var k = 0
      while (k < order.length) {
        eligibleColumns(bottoms, avgBox).forEach(function (col) {
          if (k >= order.length) return
          var file = order[k]
          k += 1
          var ids = byFile[file]
          var y = used[col] ? bottoms[col] + g.anchorGap : top
          var x = g.left + col * (g.cellW + g.gapX)
          var h = boxHeight(ids, g)
          boxes.push({ file: file, label: shortFile(file), x: x, y: y, w: g.cellW, h: h, count: ids.length, frame: side ? 'side' : 'tree' })
          var ny = y + g.head
          ids.forEach(function (id) {
            var nh = g.size[id].h
            placed.push({
              id: id, node: graph.nodes[id], anchor: graph.nodes[id],
              x: x + g.pad, y: ny, w: g.cardW, h: nh,
              file: file, layer: 'box:' + (side ? 'side:' : '') + file, tree: 0, label: g.label[id],
              ports: portsFor(x + g.pad, ny, g.cardW, nh), flowDir: 'ltr', boxKey: file, side: side,
            })
            ny += nh + g.innerY
          })
          bottoms[col] = y + h
          used[col] = true
        })
      }
      return Math.max.apply(null, bottoms)
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

    /** 卡片宽：画过就沿用画过的宽（新来的长名字折行），没画过取最宽的名字；高度优先用浏览器实测的。 */
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
      var heights = Object.keys(card.size).map(function (id) { return card.size[id].h })
      var g = {
        cols: Math.max(1, Math.floor((usable + gapX) / (cellW + gapX))),
        cellW: cellW, cardW: card.cardW, pad: pad, gapX: gapX,
        // 同一列上下两个框之间空一个 anchor 的高度：取所有卡片的平均高度。
        anchorGap: heights.length > 0 ? heights.reduce(function (sum, h) { return sum + h }, 0) / heights.length : metrics.BOX_GAP_Y,
        head: metrics.BOX_HEAD, innerY: metrics.INNER_GAP_Y,
        left: metrics.PAD, size: card.size, label: metrics.label,
      }
      var placed = []
      var boxes = []
      var rows = []
      var bottom = metrics.PAD
      if (included.length > 0) {
        var tree = byFileOf(graph, included, false)
        var treeOrder = stableOrder('tree', Object.keys(tree), fileWeights(graph, tree), g.cols)
        bottom = packSection(graph, tree, treeOrder, metrics.PAD, g, false, placed, boxes)
      }
      if (side.length > 0) {
        var labelY = included.length > 0 ? bottom + SECTION_GAP : metrics.PAD + 16
        rows.push({ x: metrics.PAD, y: labelY, label: '旁边 · 不在当前树里的 seed（' + side.length + '）', ids: side, island: false })
        var rest = byFileOf(graph, side, true)
        var sideOrder = stableOrder('side', Object.keys(rest), fileWeights(graph, rest), g.cols)
        bottom = packSection(graph, rest, sideOrder, labelY + 8, g, true, placed, boxes)
      }
      // grid 一并交出去：增量布局（stable.js）给新卡片找位置时要用同一套尺寸。
      return { placed: placed, polylines: polylinesFor(graph, placed), boxes: boxes, rows: rows, cols: g.cols, canvasY: bottom, grid: g }
    }

    module.exports = { placeFileGrid, polylinesFor, portsFor, greedyOrder, communicationOrder, eligibleColumns }
    return module.exports
  },
})
