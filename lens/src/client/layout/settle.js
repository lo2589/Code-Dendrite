// dsh-cdd-lens — 文件框最后收一遍：框永远不叠。
//
// 用户：「你先把框不重叠搞定吧，文件框到处乱叠」。
// 文件框网格排的时候框不叠，但排完之后节点还会被挪（实测卡片更高、手工拖动……），
// 框却停在排版时的位置，节点就撑出框、压到别的框上。所以画线之前再收一遍：
//   1. 每个框按框里（没被手工拖过的）节点的实际位置重算，节点撑出去多少框长多少
//   2. 从上往下，压住前面已经放好的框，就连同框里的节点整体往下推，保留框间距
//   3. 「旁边」标题跟到树的框下面，旁边的框从标题下面开始
// 手工拖过的节点不算进任何框，留在用户放的位置。
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/settle',
  factory: (require) => {
    var module = { exports: {} }
    var SECTION_GAP = 36

    function keyOf(frameSide, file) {
      return (frameSide ? 'side:' : 'tree:') + file
    }

    /** 两个矩形靠得比 gap 还近（含重叠）。刚好隔 gap 的不算。 */
    function tooClose(a, b, gap) {
      return a.x < b.x + b.w + gap - 1 && b.x < a.x + a.w + gap - 1
        && a.y < b.y + b.h + gap - 1 && b.y < a.y + a.h + gap - 1
    }

    /** 框 = 排版时的框 ∪ 框里节点的实际范围（左右留 pad、上面留框头、下面留 pad）。 */
    function grow(base, members, pad, head) {
      if (members.length === 0) return Object.assign({}, base)
      var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      members.forEach(function (p) {
        if (p.x < minX) minX = p.x
        if (p.y < minY) minY = p.y
        if (p.x + p.w > maxX) maxX = p.x + p.w
        if (p.y + p.h > maxY) maxY = p.y + p.h
      })
      var x = Math.min(base.x, minX - pad)
      var y = Math.min(base.y, minY - head)
      return Object.assign({}, base, {
        x: x, y: y,
        w: Math.max(base.x + base.w, maxX + pad) - x,
        h: Math.max(base.y + base.h, maxY + pad) - y,
      })
    }

    /**
     * 一段（树 / 旁边）：按从上到下、从左到右的顺序，压住前面已经放好的框就往下推到它下面。
     * @returns 这一段最下面那个框的下沿；没有框时是 floor。
     */
    function settleSection(boxes, membersOf, floor, gap) {
      var done = []
      boxes.slice().sort(function (a, b) { return a.y - b.y || a.x - b.x }).forEach(function (box) {
        var dy = Math.max(0, floor - box.y)
        for (var guard = 0; guard < boxes.length + 1; guard += 1) {
          var moved = { x: box.x, y: box.y + dy, w: box.w, h: box.h }
          var hit = null
          for (var i = 0; i < done.length; i += 1) if (tooClose(moved, done[i], gap)) { hit = done[i]; break }
          if (hit === null) break
          dy = hit.y + hit.h + gap - box.y
        }
        if (dy > 0) {
          box.y += dy
          membersOf(box).forEach(function (p) { p.y += dy })
        }
        done.push(box)
      })
      return done.reduce(function (m, b) { return Math.max(m, b.y + b.h) }, floor)
    }

    /**
     * @param place - { placed }：节点坐标，会被原地移动。
     * @param laid - 文件框网格的结果：{ boxes, rows }。
     * @param metrics - 读 BOX_PAD、BOX_HEAD、BOX_GAP_X、BOX_GAP_Y。
     * @returns { boxes, rows }：收过之后的框和「旁边」标题。
     */
    function settleBoxes(place, laid, metrics) {
      var byBox = {}
      place.placed.forEach(function (p) {
        if (p.manual === true) return
        var key = keyOf(p.side === true, p.file)
        if (byBox[key] === undefined) byBox[key] = []
        byBox[key].push(p)
      })
      var membersOf = function (b) { return byBox[keyOf(b.frame === 'side', b.file)] || [] }
      var boxes = (laid.boxes || []).map(function (b) { return grow(b, membersOf(b), metrics.BOX_PAD, metrics.BOX_HEAD) })
      var rows = (laid.rows || []).map(function (r) { return Object.assign({}, r) })
      var gap = Math.min(metrics.BOX_GAP_X, metrics.BOX_GAP_Y)
      var tree = boxes.filter(function (b) { return b.frame !== 'side' })
      var side = boxes.filter(function (b) { return b.frame === 'side' })
      var treeBottom = settleSection(tree, membersOf, -Infinity, gap)
      if (side.length > 0) {
        var labelY = rows.length > 0 ? rows[0].y : -Infinity
        if (tree.length > 0) labelY = Math.max(labelY, treeBottom + SECTION_GAP)
        if (rows.length > 0) rows[0].y = labelY
        settleSection(side, membersOf, labelY + 8, gap)
      }
      return { boxes: boxes, rows: rows }
    }

    module.exports = { settleBoxes }
    return module.exports
  },
})
