// dsh-cdd-lens — 焦点不能丢：老卡片原地不动，新卡片只往空地放。
//
// 做法照 cytoscape-expand-collapse：展开时已有的东西回到原坐标，只给新来的找地方；
// 整体重排只在用户自己要求时做（「恢复自动布局」、改画布宽度、换会话）。
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/stable',
  factory: (require) => {
    var module = { exports: {} }

    // 上一次画出来的样子：每张卡片在哪、属于哪个框、画布多宽。
    var held = null

    /**
     * 记下这一张：下一次再变，就照这一张不动。
     *
     * 记列数，不记像素宽：展开后内容变高，画布右边冒出一条竖滚动条，宽度少十几像素。
     * 按像素比，这就成了"用户改了宽度"、整张重排——实测焦点卡一下跑了 692px。
     * 列数变了才是真的改了宽度。
     */
    function hold(placed, cols) {
      // 这一张没画、但以前画过的卡片也记着：关掉一种关系它就消失，再打开它会回来——
      // 回来时应该回到原来的地方，而不是被当成新卡片放到最下面（实测跑了 762px）。
      var cards = held !== null && held.cols === cols ? Object.assign({}, held.cards) : {}
      var drawn = {}
      placed.forEach(function (p) {
        cards[p.id] = { x: p.x, y: p.y, side: p.side === true, boxKey: p.boxKey }
        drawn[p.id] = true
      })
      held = { cols: cols, cards: cards, drawn: drawn }
    }

    /** 用户要求重排：忘掉上一张，下一次整体重新装箱。 */
    function forget() { held = null }

    function hit(a, b, gap) {
      return a.x < b.x + b.w + gap && b.x < a.x + a.w + gap && a.y < b.y + b.h + gap && b.y < a.y + a.h + gap
    }

    function keyOf(side, boxKey) { return (side ? 'side:' : 'tree:') + boxKey }

    function continuationOf(file) { return file + '#续' }

    /** 一个文件框：按里面卡片的实际位置围出来。 */
    function frameOf(box, g) {
      var top = Infinity
      var bottom = -Infinity
      var left = Infinity
      box.members.forEach(function (p) {
        top = Math.min(top, p.y)
        bottom = Math.max(bottom, p.y + p.h)
        left = Math.min(left, p.x)
      })
      var frame = {
        file: box.file, label: box.label, x: left - g.pad, y: top - g.head, w: g.cellW,
        h: bottom - top + g.head + g.pad, count: box.members.length, frame: box.side ? 'side' : 'tree',
      }
      if (box.boxKey !== box.file) frame.boxKey = box.boxKey
      return frame
    }

    /**
     * 同一个框里的老卡片：保持各自位置，只在卡片长高、压到下一张时把下一张往下让。
     * 不让就叠在一起——那比挪一点更糟。只往下推，从不往上拉。
     */
    function restack(members, innerY) {
      members.sort(function (a, b) { return a.y - b.y })
      for (var i = 1; i < members.length; i += 1) {
        var floor = members[i - 1].y + members[i - 1].h + innerY
        if (members[i].y < floor) members[i].y = floor
      }
    }

    /** 新卡片接在这个框的底下：框长高后不许碰到任何别的框。放不下返回 null。 */
    function tryTail(box, card, boxes, g, gap) {
      var last = box.members[box.members.length - 1]
      var at = { x: last.x, y: last.y + last.h + g.innerY, w: card.w, h: card.h }
      var grown = { x: box.frame.x, y: box.frame.y, w: box.frame.w, h: at.y + at.h + g.pad - box.frame.y }
      var keys = Object.keys(boxes)
      for (var i = 0; i < keys.length; i += 1) {
        if (keys[i] === box.key) continue
        if (hit(grown, boxes[keys[i]].frame, gap)) return null
      }
      return at
    }

    /** 放不进任何老框的新卡片：在整张图下面新开一片，按同一套网格一列一列排。 */
    function packBelow(groups, top, g) {
      var bottoms = []
      for (var c = 0; c < g.cols; c += 1) bottoms.push(top)
      groups.forEach(function (box) {
        var col = bottoms.indexOf(Math.min.apply(null, bottoms))
        var x = g.left + col * (g.cellW + g.gapX)
        var y = bottoms[col] === top ? top : bottoms[col] + g.anchorGap
        var ny = y + g.head
        box.members.forEach(function (p) {
          p.x = x + g.pad
          p.y = ny
          ny += p.h + g.innerY
        })
        bottoms[col] = ny - g.innerY + g.pad
      })
    }

    function boxFor(boxes, side, file, boxKey, labels) {
      var key = keyOf(side, boxKey)
      if (boxes[key] === undefined) {
        var base = labels[keyOf(side, file)] || file
        boxes[key] = {
          key: key, file: file, boxKey: boxKey, side: side, members: [],
          label: boxKey === file ? base : base + '（续）',
        }
      }
      return boxes[key]
    }

    /**
     * 把这次的完整装箱结果改成「老的不动、新的放空地」。
     *
     * @param graph - shared.graph。
     * @param laid - placeFileGrid 的结果（这次所有卡片的尺寸、所属文件都在里面，laid.grid 是网格参数）。
     * @param gap - 框与框之间至少空多少（和收框那一步同一个数，收框就不会再推老卡片）。
     * @param tools - { polylinesFor, portsFor }：连线和端口用 fileGrid 自己那一套，不另算。
     * @returns 和 laid 同形状；第一次画、换了会话、网格列数变了时原样交回 laid。
     */
    function holdLayout(graph, laid, gap, tools) {
      var g = laid.grid
      if (held === null || g === undefined || held.cols !== g.cols) return laid
      var labels = {}
      laid.boxes.forEach(function (b) { labels[keyOf(b.frame === 'side', b.file)] = b.label })

      var boxes = {}
      var fresh = []
      var ghosts = []
      laid.placed.forEach(function (p) {
        var at = held.cards[p.id]
        var card = Object.assign({}, p)
        // 以前画过、上一张没画：先放一边，等老卡片都归位了再看它的老位置还空不空。
        if (at !== undefined && held.drawn[p.id] !== true) {
          ghosts.push({ card: card, at: at })
          return
        }
        // 上次画过就原地不动——**换没换区都一样**。关系开关一拨，一张卡片可能从「树」掉进
        // 「旁边」或者反过来；以前把这种当成新卡片重新安置，实测一下就跑了 1617px，
        // 跑到负坐标时还逼得整张图一起平移。换区只改它属于哪个框，不改它在哪。
        if (at !== undefined) {
          card.x = at.x
          card.y = at.y
          var sameSide = at.side === (p.side === true)
          card.boxKey = sameSide && at.boxKey !== undefined ? at.boxKey : p.file
          boxFor(boxes, card.side === true, card.file, card.boxKey, labels).members.push(card)
        } else {
          fresh.push(card)
        }
      })
      // 一张老卡片都对不上：换了会话或者整张图都换了，没有焦点可保。
      if (Object.keys(boxes).length === 0) return laid

      var kept = 0
      Object.keys(boxes).forEach(function (key) {
        var box = boxes[key]
        kept += box.members.length
        restack(box.members, g.innerY)
        box.frame = frameOf(box, g)
      })

      // 回来的卡片：老位置没被占、回去以后它的框也不碰别的框，就回原位；否则当新卡片。
      // 每张的去向写进 notes，进布局日志：回原位了还是被谁挡住了，一眼看得见。
      var notes = []
      ghosts.forEach(function (ghost) {
        var card = ghost.card
        var spot = { x: ghost.at.x, y: ghost.at.y, w: card.w, h: card.h }
        var sameSide = ghost.at.side === (card.side === true)
        var boxKey = sameSide && ghost.at.boxKey !== undefined ? ghost.at.boxKey : card.file
        var key = keyOf(card.side === true, boxKey)
        var blocked = null
        Object.keys(boxes).forEach(function (k) {
          boxes[k].members.forEach(function (m) {
            if (blocked === null && hit(spot, m, g.innerY - 1)) blocked = '卡片 ' + String(m.id).split('::').pop()
          })
        })
        if (blocked === null) {
          var probe = { members: (boxes[key] ? boxes[key].members : []).concat([spot]), file: card.file, boxKey: boxKey, side: card.side === true }
          var grown = frameOf(probe, g)
          // 同一个文件自己的框（树区、旁边区、续框）不算障碍：它们本来就挨着，原位曾经就在它们旁边。
          // 以前把它们也算进去，卡片关掉再打开就回不了原位（实测被 side:record.js 挡住，跳了 762px）。
          Object.keys(boxes).forEach(function (k) {
            if (blocked === null && k !== key && boxes[k].file !== card.file && hit(grown, boxes[k].frame, gap)) blocked = '框 ' + k
          })
        }
        if (blocked !== null) {
          notes.push(String(card.id).split('::').pop() + ' 回不了原位（被' + blocked + '挡住）')
          fresh.push(card)
          return
        }
        notes.push(String(card.id).split('::').pop() + ' 回到原位')
        card.x = spot.x
        card.y = spot.y
        card.boxKey = boxKey
        var box = boxFor(boxes, card.side === true, card.file, boxKey, labels)
        box.members.push(card)
        box.members.sort(function (a, b) { return a.y - b.y })
        box.frame = frameOf(box, g)
        kept += 1
      })

      // 新卡片：先接主框，再接续框，都放不下才到下面另开。
      var belowOrder = []
      var below = {}
      fresh.forEach(function (p) {
        var side = p.side === true
        var tries = [keyOf(side, p.file), keyOf(side, continuationOf(p.file))]
        for (var i = 0; i < tries.length; i += 1) {
          var box = boxes[tries[i]]
          if (box === undefined) continue
          var at = tryTail(box, p, boxes, g, gap)
          if (at === null) continue
          p.x = at.x
          p.y = at.y
          p.boxKey = box.boxKey
          box.members.push(p)
          box.frame = frameOf(box, g)
          return
        }
        var boxKey = boxes[keyOf(side, p.file)] === undefined ? p.file : continuationOf(p.file)
        var key = keyOf(side, boxKey)
        if (below[key] === undefined) {
          below[key] = boxFor({}, side, p.file, boxKey, labels)
          belowOrder.push(key)
        }
        p.boxKey = boxKey
        below[key].members.push(p)
      })

      var bottom = Object.keys(boxes).reduce(function (m, key) {
        return Math.max(m, boxes[key].frame.y + boxes[key].frame.h)
      }, -Infinity)
      var groups = belowOrder.map(function (key) { return below[key] })
      if (groups.length > 0) packBelow(groups, bottom + g.anchorGap, g)
      groups.forEach(function (box) {
        box.frame = frameOf(box, g)
        boxes[box.key] = box
      })

      var frames = []
      var placed = []
      Object.keys(boxes).forEach(function (key) {
        frames.push(boxes[key].frame)
        boxes[key].members.forEach(function (p) {
          p.ports = tools.portsFor(p.x, p.y, p.w, p.h)
          placed.push(p)
        })
      })
      // 画布高只按真画出来的框算：整体装箱那次的高度这里没用上，沿用它底下会多出一大块空白。
      var canvasY = frames.reduce(function (m, f) { return Math.max(m, f.y + f.h) }, 0)
      // 「旁边」那行标题跟着旁边区第一个框走，不按这次没用上的整体装箱位置摆。
      var sideTop = frames.filter(function (f) { return f.frame === 'side' })
        .reduce(function (m, f) { return Math.min(m, f.y) }, Infinity)
      var rows = (laid.rows || []).map(function (r) {
        return isFinite(sideTop) ? Object.assign({}, r, { y: sideTop - 16 }) : Object.assign({}, r)
      })
      return Object.assign({}, laid, {
        placed: placed, boxes: frames, rows: rows, polylines: tools.polylinesFor(graph, placed),
        canvasY: canvasY, held: { kept: kept, fresh: fresh.length, below: groups.length, notes: notes },
      })
    }

    module.exports = { hold, forget, holdLayout }
    return module.exports
  },
})
