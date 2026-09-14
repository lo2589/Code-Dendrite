// dsh-cdd-lens — One anchor box.
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
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __graph_visible = require('dsh-cdd-lens/graph/visible')
    var stickyByRecency = __graph_visible.stickyByRecency
    var __view_record = require('dsh-cdd-lens/view/record')
    var dotClass = __view_record.dotClass
    var stateOf = __view_record.stateOf
    var turnLabel = __view_record.turnLabel
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note

    function GraphNode(props) {
      var engine = props.engine
      var p = props.p
      var zoom = props.zoom || 1
      var drag = useRef(null)
      // node 就是 anchor：不用再走 `.anchor` 那一跳。
      var anchor = p.node
      var ui = uiOf(shared.graph, p.id) || {}
      var record = stateOf(p.id)
      var faded = record !== null && record !== undefined && !record.remembered
      var selected = shared.selected === p.id
      var synthetic = ui.synthetic === true || ui.bridge === true || anchor.hidden === true
      var isClass = !synthetic && (anchor.kind === 'class' || anchor.members > 0)
      // A class and a function are two different things, and the card has to say
      // so in colour rather than in a 1.5px border nobody can see. `kind` rides
      // in on the anchor, so this reads the record instead of guessing.
      var isFn = !synthetic && !isClass

      var head = h('div', { className: 'cddl-gtop' + (isClass ? ' cddl-class-header' : ''), key: 'top' }, [
        h('span', { key: 'd', className: dotClass(record) }),
        h('span', { key: 's', className: 'cddl-sym', title: anchor.id },
          p.label || anchor.symbol.split('.').pop() || anchor.symbol),
        turnLabel(record) === null ? null : React.cloneElement(turnLabel(record), { key: 'b' }),
        isClass ? h('button', {
          key: 'c', className: 'cddl-count',
          title: anchor.members + ' 个成员',
          onClick: function (e) { e.stopPropagation(); engine.members(p.id) },
        }, (ui.members ? '▾ ' : '▸ ') + anchor.members)
          : h('span', { key: 'l', className: 'cddl-lines' }, anchor.line_start + '–' + anchor.line_end),
        isClass ? h('span', { key: 'k', className: 'cddl-kind' }, '类') : null,
      ])

      // 展开按钮按关系挂：anchor.peerCounts 是 worker 给的
      //   { call: {up, down}, inherit: {up, down}, … }
      // 只列出**有数据**的关系——某个关系是 0 就不在这里出现，不画箭头也不写数字。
      var REL_LABEL = {
        call: '调用', dataflow: '数据流', inherit: '继承',
        dispatch: '分派', impact: '影响',
      }
      var REL_ORDER = ['call', 'dataflow', 'inherit', 'dispatch', 'impact']
      var counts = anchor.peerCounts || {}

      function hopButton(direction, rel) {
        var n = counts[rel][direction]
        var slot = direction + ':' + rel
        var open = ui.open[slot] === true
        var arrow = direction === 'up' ? '↑' : '↓'
        var verb = direction === 'up' ? '谁在用它' : '它在用谁'
        return h('button', {
          key: slot,
          title: REL_LABEL[rel] + ' · ' + verb + '（' + n + '）'
            + '\n点一下：展开/收起一层'
            + '\n按住 Shift 点：一路展开到底（链式）',
          className: 'cddl-action-' + direction + ' cddl-rel-' + rel + (open ? ' on' : ''),
          'data-action': direction === 'up' ? 'expand-callers' : 'expand-callees',
          'data-relation': rel,
          'data-count': n,
          onClick: function (e) {
            e.stopPropagation()
            note('btn', '按下 ' + (direction === 'up' ? '↑' : '↓') + rel
              + ' count=' + n + (open ? ' [收起]' : '')
              + ' 节点=' + String(p.id).split('::').pop())
            if (open) { engine.collapse(p.id, direction, rel); return }
            if (e.shiftKey) engine.walk(p.id, direction, rel, 4)
            else engine.expand(p.id, direction, null, rel)
          },
        }, [
          h('span', { key: 'a', className: 'cddl-rel-arrow' }, arrow),
          h('span', { key: 'n', className: 'cddl-rel-count' }, n),
          h('span', { key: 'r', className: 'cddl-rel-name' }, rel),
        ])
      }

      var hopButtons = []
      REL_ORDER.forEach(function (rel) {
        var c = counts[rel]
        if (c === undefined) return
        // 上行在左、下行在右，同一关系两个方向挨着，颜色一致。
        if (c.up > 0) hopButtons.push(hopButton('up', rel))
        if (c.down > 0) hopButtons.push(hopButton('down', rel))
      })

      var actions = synthetic
        ? h('div', { key: 'h', className: 'cddl-node-actions cddl-node-actions-bridge' }, [
          h('span', {
            key: 'b', className: 'cddl-kind cddl-bridgetag',
            title: '它只是把两个真实 anchor 连起来的中间点，不参与继续展开。',
          }, '桥'),
        ])
        :
        h('div', { key: 'h', className: 'cddl-node-actions' }, hopButtons.concat([
          h('button', {
            key: 'p',
            title: ui.pinned
              ? '取消固定'
              : (stickyByRecency(p.id)
                ? '最近碰过，自动保留三轮；点一下改为永久固定'
                : '固定：折叠上级时也留在图上'),
            className: 'cddl-action-pin' + (ui.pinned ? ' on' : (stickyByRecency(p.id) ? ' auto' : '')),
            'data-action': 'pin-anchor',
            onClick: function (e) { e.stopPropagation(); engine.pin(p.id) },
          }, 'pin'),
        ]))

      var members = null
      if (!synthetic && ui.members && ui.memberList !== undefined) {
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
              h('span', { key: 's', className: 'cddl-sym' }, member.symbol.split('.').pop()),
              turnLabel(mrec) === null ? null : React.cloneElement(turnLabel(mrec), { key: 'b' }),
              h('span', { key: 'l', className: 'cddl-lines' }, member.start + '–' + member.end),
            ])
          }).concat([h('div', { key: 'more', className: 'cddl-more' }, '共 ' + ui.memberList.length + ' 个方法')]))
      }

      // 同一张卡片用在两处：画布上定位的，和轨迹栏里顺着流排的。只有位置不同，
      // 所以只切这一个标记——另写一个组件迟早会和这个跑偏。
      var flow = props.flow === true
      // 出入口各一个小圈：**入在左、出在右，不同口**。线从左边的小圈进、
      // 从右边的小圈出，两头都停在圈上——线必须明显连到圈上，不许悬空。
      //
      // 以前这里是 24×20 的方块角标，里面写「入」「出」两个字，而且入出可以
      // 落在同一条边（role='both'）上；那样两个方向挤在一个口，看不出谁进谁出。
      var vertical = p.flowAxis === 'vertical'
      var portViews = [
        h('span', {
          key: 'port-in',
          className: 'cddl-port cddl-port-in' + (vertical ? ' cddl-port-vtop' : ''),
          'data-port': 'in',
          title: '关系进入此 Anchor',
        }),
        h('span', {
          key: 'port-out',
          className: 'cddl-port cddl-port-out' + (vertical ? ' cddl-port-vbottom' : ''),
          'data-port': 'out',
          title: '关系离开此 Anchor',
        }),
      ]
      return h('div', {
        className: 'cddl-node-shell' + (p.island ? ' cddl-shell-island' : '')
          + (flow ? ' cddl-node-flow' : ''),
        style: flow
          ? { width: p.w + 'px' }
          : { left: p.x + 'px', top: p.y + 'px', width: p.w + 'px' },
        'data-node-id': p.id,
        // What this node believes about itself, readable from the outside. A
        // button that does not light up after it worked is indistinguishable
        // from one that did nothing, and guessing which was costing more than
        // the attribute does.
        // 有哪些「方向:关系」开着，供外部测试读。以前只报 up/down 两个方向，
        // 现在每个关系各开各的，所以按 key 全列出来。
        'data-open': Object.keys(ui.open).filter(function (k) {
          return ui.open[k] === true && k.indexOf('auto') !== 0
        }).sort().join(' ') || 'none',
      }, [
        portViews,
        h('div', {
          key: 'n',
          className: 'cddl-gnode'
            + (shared.lit === null || shared.lit === undefined ? ''
              : (shared.lit.nodes[p.id] === true ? ' cddl-lit' : ' cddl-unlit'))
            + (selected ? ' cddl-sel' : '')
            + (faded ? ' cddl-faded' : '')
            + (ui.island ? ' cddl-island' : '')
            + (synthetic ? ' cddl-bridge' : '')
            + (isClass ? ' cddl-cls cddl-class' : '')
            + (isFn ? ' cddl-fn' : ''),
          title: anchor.id,
          'data-anchor-id': anchor.id,
          onPointerDown: function (event) {
            if (event.button !== 0) return
            if (event.target.closest && event.target.closest('button')) return
            event.preventDefault()
            event.stopPropagation()
            // Drag in the coordinates a position is SAVED in, not the ones it
            // is drawn at. The drawing may have been moved to make room for
            // wires; folding that margin into the stored position would move
            // the node again on the next render, and again after that.
            var baseX = p.baseX === undefined ? p.x : p.baseX
            var baseY = p.baseY === undefined ? p.y : p.baseY
            var start = { clientX: event.clientX, clientY: event.clientY, x: baseX, y: baseY }
            var latest = { x: baseX, y: baseY }
            var moved = false
            drag.current = start
            var move = function (e) {
              var dx = (e.clientX - start.clientX) / zoom
              var dy = (e.clientY - start.clientY) / zoom
              if (!moved && Math.abs(dx) + Math.abs(dy) < 4) return
              moved = true
              latest = { x: Math.max(4, start.x + dx), y: Math.max(4, start.y + dy) }
              engine.moveNode(p.id, latest, false)
            }
            var up = function () {
              drag.current = null
              window.removeEventListener('pointermove', move)
              window.removeEventListener('pointerup', up)
              if (moved) engine.moveNode(p.id, latest, true)
              else { engine.select(p.id); engine.lightNode(p.id) }
            }
            window.addEventListener('pointermove', move)
            window.addEventListener('pointerup', up)
          },
        }, [
          // No path line here: the box header already names the file, and
          // repeating it inside every node was what squeezed the symbol into an
          // ellipsis. Hover still shows the fully qualified id.

          head,
          // The controls live in the card, on their own line under the name.
          // Floating them above it meant they overlapped whatever sat there,
          // and a node's own buttons reading as another node's is worse than
          // the two pixels of height they cost.
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

    /**
     * A horizontal scrollbar of our own, pinned to the bottom of the canvas.
     *
     * `scrollbar-gutter` reserves the vertical gutter and has no horizontal
     * counterpart, and this platform's native horizontal bar is an overlay: it
     * occupies no layout space and fades out when idle. So a drawing that
     * genuinely scrolls sideways reads as one that cannot, and the only way to
     * discover otherwise is to try. Drawn explicitly, the axis is simply there.
     */

    module.exports = { GraphNode }
    return module.exports
  },
})
