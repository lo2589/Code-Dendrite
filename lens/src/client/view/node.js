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

    function GraphNode(props) {
      var engine = props.engine
      var p = props.p
      var zoom = props.zoom || 1
      var drag = useRef(null)
      var anchor = p.node.anchor
      var record = stateOf(p.id)
      var faded = record !== null && record !== undefined && !record.remembered
      var selected = shared.selected === p.id
      var synthetic = p.node.synthetic === true || p.node.bridge === true || anchor.hidden === true
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
        }, (p.node.members ? '▾ ' : '▸ ') + anchor.members)
          : h('span', { key: 'l', className: 'cddl-lines' }, anchor.start + '–' + anchor.end),
        isClass ? h('span', { key: 'k', className: 'cddl-kind' }, '类') : null,
      ])

      // Read before the buttons are built, not after. `var` hoisting made
      // these undefined inside the action row when it moved into the card,
      // so the button never lit up and its tooltip said the wrong thing
      // while the expansion itself worked fine.
      var upOpen = p.node.up === true
      var downOpen = p.node.down === true

      var actions = synthetic
        ? h('div', { key: 'h', className: 'cddl-node-actions cddl-node-actions-bridge' }, [
          h('span', {
            key: 'b', className: 'cddl-kind cddl-bridgetag',
            title: '它只是把两个真实 anchor 连起来的中间点，不参与继续展开。',
          }, '桥'),
        ])
        :
        h('div', { key: 'h', className: 'cddl-node-actions' }, [
          h('button', {
            key: 'u',
            title: anchor.up === 0
              ? '索引里没有谁用它'
              : (upOpen ? '收起：谁在用它（' + anchor.up + '）' : '展开：谁在用它（' + anchor.up + '）'),
            disabled: anchor.up === 0,
            className: 'cddl-action-up' + (upOpen ? ' on' : ''),
            'data-action': 'expand-callers',
            onClick: function (e) {
              e.stopPropagation()
              if (upOpen) engine.collapse(p.id, 'up')
              else engine.expand(p.id, 'up')
            },
          }, '↑' + anchor.up),
          h('button', {
            key: 'd',
            title: anchor.down === 0
              ? '索引里它没用任何东西'
              : (downOpen ? '收起：它在用谁（' + anchor.down + '）' : '展开：它在用谁（' + anchor.down + '）'),
            disabled: anchor.down === 0,
            className: 'cddl-action-down' + (downOpen ? ' on' : ''),
            'data-action': 'expand-callees',
            onClick: function (e) {
              e.stopPropagation()
              if (downOpen) engine.collapse(p.id, 'down')
              else engine.expand(p.id, 'down')
            },
          }, '↓' + anchor.down),
          h('button', {
            key: 'p',
            title: p.node.pinned
              ? '取消固定'
              : (stickyByRecency(p.id)
                ? '最近碰过，自动保留三轮；点一下改为永久固定'
                : '固定：折叠上级时也留在图上'),
            className: 'cddl-action-pin' + (p.node.pinned ? ' on' : (stickyByRecency(p.id) ? ' auto' : '')),
            'data-action': 'pin-anchor',
            onClick: function (e) { e.stopPropagation(); engine.pin(p.id) },
          }, 'pin'),
        ])

      var members = null
      if (!synthetic && p.node.members && p.node.memberList !== undefined) {
        members = h('div', { className: 'cddl-members', key: 'm' },
          p.node.memberList.map(function (member) {
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
          }).concat([h('div', { key: 'more', className: 'cddl-more' }, '共 ' + p.node.memberList.length + ' 个方法')]))
      }

      // The same card is used twice: positioned on the canvas, and standing in
      // the flow of the stream rail. Only where it sits differs, so only that
      // is switched — a second component would drift from this one.
      var flow = props.flow === true
      var vertical = p.flowAxis === 'vertical'
      var ports = p.routingPorts
      if (!ports || !ports.length) ports = [
        {side:vertical?'top':'left',in:true,out:false},
        {side:vertical?'bottom':'right',in:false,out:true},
      ]
      var portViews = ports.map(function (port) {
        var role=port.in && port.out?'both':port.in?'in':'out'
        return h('span', {key:'port-'+port.side,
          className:'cddl-port cddl-port-'+role+' cddl-port-'+port.side,
          'data-port':role, 'data-port-side':port.side,
          title:role==='both'?'此处有进入和离开此 Anchor 的关系':port.in?'关系进入此 Anchor':'关系离开此 Anchor',
        }, role==='both'?'入出':port.in?'入':'出')
      })
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
        'data-open': (upOpen ? 'up' : '') + (downOpen ? 'down' : '') || 'none',
      }, [
        portViews,
        h('div', {
          key: 'n',
          className: 'cddl-gnode'
            + (shared.lit === null || shared.lit === undefined ? ''
              : (shared.lit.nodes[p.id] === true ? ' cddl-lit' : ' cddl-unlit'))
            + (selected ? ' cddl-sel' : '')
            + (faded ? ' cddl-faded' : '')
            + (p.node.island ? ' cddl-island' : '')
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
