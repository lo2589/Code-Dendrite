// dsh-cdd-lens — One anchor box.
//
// 卡片上的一切都来自 anchor 原始记录和 /screen：
//   ↑N / ↓N 的数字 = screen.buttons[id]（就是 len(关系+up/down)），点击只切换展开状态
//   pin = engine.pin（计数器不减）
// 这里不决定任何节点是否上屏。
//
// 画布上用 MemoNode：卡片自己的签名（位置、按钮、状态）没变就不重画——选中别的节点、
// 高亮一根线时，其它卡片不跟着跑一遍 React。
// 拖动不经过 React：直接挪这张卡片，线层只改它自己的线，松手才重排一次。
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/node',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __view_record = require('dsh-cdd-lens/view/record')
    var dotClass = __view_record.dotClass
    var stateOf = __view_record.stateOf
    var recordStateOf = __view_record.recordStateOf
    var turnLabel = __view_record.turnLabel
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note

    var REL_LABEL = { call: '调用', dataflow: '数据流', inherit: '继承', dispatch: '分派', impact: '影响' }
    var REL_ORDER = ['call', 'dataflow', 'inherit', 'dispatch', 'impact']

    function memberCountOf(anchor) {
      return Array.isArray(anchor.own_methods) ? anchor.own_methods.length : 0
    }

    function buttonsOf(id) {
      return (shared.screen && shared.screen.buttons && shared.screen.buttons[id]) || {}
    }

    function hopButtons(engine, id) {
      var counts = buttonsOf(id)
      var out = []
      REL_ORDER.forEach(function (rel) {
        // 上行在左、下行在右，同一关系两个方向挨着，颜色一致；数字是 0 的不画。
        ['up', 'down'].forEach(function (dir) {
          var n = counts[rel + dir]
          if (!(n > 0)) return
          var open = engine.isOpen(id, rel, dir)
          var busy = engine.isBusy(id, rel, dir)
          out.push(h('button', {
            key: dir + ':' + rel,
            title: (busy ? '正在展开…\n' : '') + REL_LABEL[rel] + ' · ' + (rel === 'dataflow' ? (dir === 'up' ? '数据从谁流进来' : '数据流到谁那里去') : (dir === 'up' ? '谁在用它' : '它在用谁')) + '（' + n + '）\n点一下：展开/收起',
            className: 'cddl-action-' + dir + ' cddl-rel-' + rel + (open ? ' on' : '') + (busy ? ' cddl-busy' : ''),
            'aria-busy': busy ? 'true' : 'false',
            'data-action': dir === 'up' ? 'expand-callers' : 'expand-callees',
            'data-relation': rel,
            'data-count': n,
            onClick: function (e) {
              e.stopPropagation()
              note('btn', '按下 ' + (dir === 'up' ? '↑' : '↓') + rel + ' count=' + n + (open ? ' [收起]' : '') + ' 节点=' + String(id).split('::').pop())
              engine.toggleOpen(id, rel, dir)
            },
          }, [
            h('span', { key: 'a', className: 'cddl-rel-arrow' }, busy ? '…' : (dir === 'up' ? '↑' : '↓')),
            h('span', { key: 'n', className: 'cddl-rel-count' }, n),
            h('span', { key: 'r', className: 'cddl-rel-name' }, rel),
          ]))
        })
      })
      return out
    }

    function openSlots(id) {
      var opens = (shared.view && shared.view.opens) || []
      return opens.filter(function (o) { return o.id === id }).map(function (o) { return o.dir + ':' + o.rel }).sort().join(' ') || 'none'
    }

    function busySlots(engine, id) {
      return Object.keys(buttonsOf(id)).filter(function (k) {
        var m = /^(.*)(up|down)$/.exec(k)
        return m !== null && engine.isBusy(id, m[1], m[2])
      }).join(' ')
    }

    function recordSig(r) {
      if (r === null || r === undefined) return ''
      var last = (r.events || [])[(r.events || []).length - 1] || {}
      return [r.state, r.remembered, r.firstTurn, r.firstStep, r.lastTurn, r.lastStep, r.approx, (r.events || []).length, last.agent, last.reason].join(',')
    }

    /**
     * 一张卡片画出来取决于什么。签名一样 → 画出来一样 → MemoNode 跳过这张卡片。
     * GraphNode 读到的每个 shared 字段都必须列在这里，漏一项卡片就会停在旧样子。
     */
    function nodeSig(engine, p) {
      var id = p.id
      var ui = uiOf(shared.graph, id) || {}
      // 只有被点亮的卡片自己变；其余变暗靠画布上的 cddl-litmode，不改卡片签名。
      var lit = shared.lit !== null && shared.lit !== undefined && shared.lit.nodes[id] === true ? 'L' : ''
      var members = ''
      if (ui.members && ui.memberList !== undefined) {
        members = ui.memberList.map(function (m) {
          return m.id + (shared.selected === m.id ? '*' : '') + recordSig(stateOf(m.id))
        }).join(';')
      }
      return [p.x, p.y, p.w, p.h, p.baseX, p.baseY, p.side ? 1 : 0, p.label, p.flowAxis,
        shared.selected === id ? 1 : 0, lit, engine.isPinned(id) ? 1 : 0, openSlots(id), busySlots(engine, id),
        JSON.stringify(buttonsOf(id)), recordSig(stateOf(id)), ui.members ? 1 : 0, members,
        // 过期状态也要进签名：它读的是 anchor 的 hash，索引换版后 hash 变了而这里不变，
        // 卡片就会一直停在"没变灰"的旧样子。
        recordStateOf(id)].join('|')
    }

    /** 拖动：卡片用 transform 跟着指针，线层只改这张卡片的线；松手 publish 一次、重排一次。 */
    function startDrag(event, engine, p, zoomProp) {
      var shell = event.currentTarget.parentElement
      var layer = require('dsh-cdd-lens/view/wireLayer')
      // Drag in the coordinates a position is SAVED in, not the ones it
      // is drawn at, or the node moves again on the next render.
      var baseX = p.baseX === undefined ? p.x : p.baseX
      var baseY = p.baseY === undefined ? p.y : p.baseY
      var start = { clientX: event.clientX, clientY: event.clientY }
      var latest = { x: baseX, y: baseY }
      var moved = false
      var wires = 0
      var frames = 0
      var t0 = Date.now()
      var move = function (e) {
        var zoom = shared.zoom || zoomProp || 1
        var dx = (e.clientX - start.clientX) / zoom
        var dy = (e.clientY - start.clientY) / zoom
        if (!moved && Math.abs(dx) + Math.abs(dy) < 4) return
        moved = true
        latest = { x: Math.max(4, baseX + dx), y: Math.max(4, baseY + dy) }
        var ox = latest.x - baseX
        var oy = latest.y - baseY
        if (shell) shell.style.transform = 'translate(' + ox + 'px,' + oy + 'px)'
        wires = layer.dragNode(p.id, ox, oy)
        frames += 1
        engine.moveNode(p.id, latest, false)
      }
      var up = function () {
        window.removeEventListener('pointermove', move)
        window.removeEventListener('pointerup', up)
        if (!moved) { engine.select(p.id); engine.lightNode(p.id); return }
        if (shell) {
          shell.style.transform = ''
          shell.style.left = (p.x + latest.x - baseX) + 'px'
          shell.style.top = (p.y + latest.y - baseY) + 'px'
        }
        note('btn', '拖动 ' + String(p.id).split('::').pop() + ' → ' + Math.round(latest.x) + ',' + Math.round(latest.y)
          + ' · ' + frames + ' 帧只改了卡片和它的 ' + wires + ' 根线 · ' + (Date.now() - t0) + 'ms · 松手重排一次')
        engine.moveNode(p.id, latest, true)
      }
      window.addEventListener('pointermove', move)
      window.addEventListener('pointerup', up)
    }

    function GraphNode(props) {
      var engine = props.engine
      var p = props.p
      var drag = useRef(null)
      // node 就是 anchor：不用再走 `.anchor` 那一跳。
      var anchor = p.node
      var ui = uiOf(shared.graph, p.id) || {}
      var record = stateOf(p.id)
      // 你最近一次看这个 anchor 时的那份代码，和现在还是不是同一份。
      var position = recordStateOf(p.id)
      var faded = record !== null && record !== undefined && !record.remembered
      var selected = shared.selected === p.id
      var memberCount = memberCountOf(anchor)
      var isClass = anchor.symbol_type === 'class' || memberCount > 0
      var pinned = engine.isPinned(p.id)

      var head = h('div', { className: 'cddl-gtop' + (isClass ? ' cddl-class-header' : ''), key: 'top' }, [
        h('span', { key: 'd', className: dotClass(record) }),
        h('span', { key: 's', className: 'cddl-sym', title: anchor.id },
          p.label || String(anchor.symbol).split('.').pop() || anchor.symbol),
        turnLabel(record) === null ? null : React.cloneElement(turnLabel(record), { key: 'b' }),
        isClass && memberCount > 0 ? h('button', {
          key: 'c', className: 'cddl-count',
          title: memberCount + ' 个成员',
          onClick: function (e) { e.stopPropagation(); engine.members(p.id) },
        }, (ui.members ? '▾ ' : '▸ ') + memberCount)
          : h('span', { key: 'l', className: 'cddl-lines' }, anchor.line_start + '–' + anchor.line_end),
        isClass ? h('span', { key: 'k', className: 'cddl-kind' }, '类') : null,
      ])

      var actions = h('div', { key: 'h', className: 'cddl-node-actions' }, hopButtons(engine, p.id).concat([
        h('button', {
          key: 'p',
          title: pinned ? '取消固定（之后计数器照常减）' : '固定：一直显示，计数器不减',
          className: 'cddl-action-pin' + (pinned ? ' on' : ''),
          'data-action': 'pin-anchor',
          onClick: function (e) { e.stopPropagation(); engine.pin(p.id) },
        }, 'pin'),
      ]))

      var members = null
      if (ui.members && ui.memberList !== undefined) {
        members = h('div', { className: 'cddl-members', key: 'm' },
          ui.memberList.map(function (member) {
            var mrec = stateOf(member.id)
            return h('div', {
              key: member.id,
              className: 'cddl-m' + (shared.selected === member.id ? ' cddl-sel' : ''),
              title: member.id,
              'data-anchor-id': member.id,
              onClick: function (e) { e.stopPropagation(); engine.select(member.id) },
            }, [
              h('span', { key: 'd', className: dotClass(mrec) }),
              h('span', { key: 's', className: 'cddl-sym' }, String(member.symbol).split('.').pop()),
              turnLabel(mrec) === null ? null : React.cloneElement(turnLabel(mrec), { key: 'b' }),
              h('span', { key: 'l', className: 'cddl-lines' }, member.start + '–' + member.end),
            ])
          }).concat([h('div', { key: 'more', className: 'cddl-more' }, '共 ' + ui.memberList.length + ' 个方法')]))
      }

      // 同一张卡片用在两处：画布上定位的，和轨迹栏里顺着流排的。只有位置不同。
      var flow = props.flow === true
      var vertical = p.flowAxis === 'vertical'
      // 出入口各一个小圈：入在左、出在右，不同口。线两头都停在圈上。
      var portViews = [
        h('span', { key: 'port-in', className: 'cddl-port cddl-port-in' + (vertical ? ' cddl-port-vtop' : ''), 'data-port': 'in', title: '关系进入此 Anchor' }),
        h('span', { key: 'port-out', className: 'cddl-port cddl-port-out' + (vertical ? ' cddl-port-vbottom' : ''), 'data-port': 'out', title: '关系离开此 Anchor' }),
      ]
      return h('div', {
        className: 'cddl-node-shell' + (p.side ? ' cddl-shell-island cddl-side' : '') + (flow ? ' cddl-node-flow' : '')
          + (position === 'stale' ? ' cddl-stale' : ''),
        style: flow ? { width: p.w + 'px' } : { left: p.x + 'px', top: p.y + 'px', width: p.w + 'px' },
        'data-node-id': p.id,
        // 这个节点你看过的那一版还作不作数：ok 作数 · stale 之后改过（整块变灰）·
        // unknown 判不了。图上只有 stale 变灰，判不了不许拿灰色冒充。
        'data-cdd-node-stale': position,
        'data-side': p.side ? 'true' : 'false',
        // 有哪些「方向:关系」开着，供外部测试读。
        'data-open': openSlots(p.id),
      }, [
        portViews,
        h('div', {
          key: 'n',
          className: 'cddl-gnode'
            + (shared.lit !== null && shared.lit !== undefined && shared.lit.nodes[p.id] === true ? ' cddl-lit' : '')
            + (selected ? ' cddl-sel' : '')
            + (faded ? ' cddl-faded' : '')
            + (p.side ? ' cddl-island' : '')
            + (pinned ? ' cddl-pinned' : '')
            + (isClass ? ' cddl-cls cddl-class' : ' cddl-fn'),
          title: anchor.id,
          'data-anchor-id': anchor.id,
          onPointerDown: function (event) {
            if (event.button !== 0) return
            if (event.target.closest && event.target.closest('button')) return
            event.preventDefault()
            event.stopPropagation()
            drag.current = true
            startDrag(event, engine, p, props.zoom)
          },
        }, [
          head,
          actions,
          members,
          record && record.state === 'working'
            ? h('div', { key: 'w', className: 'cddl-working' },
              ((record.events[record.events.length - 1] || {}).agent || 'Agent') + ' working · '
                + ((record.events[record.events.length - 1] || {}).reason || '正在处理此 Anchor'))
            : null,
        ]),
      ])
    }

    // 画布用这个：签名和 anchor 记录都没变就跳过。stub React（测试）没有 memo 时退回原组件。
    var MemoNode = typeof React.memo === 'function'
      ? React.memo(GraphNode, function (prev, next) {
        return prev.sig === next.sig && prev.engine === next.engine && prev.p.node === next.p.node
      })
      : GraphNode

    module.exports = { GraphNode, MemoNode, nodeSig }
    return module.exports
  },
})
