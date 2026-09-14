// dsh-cdd-lens — The vertical tree in the floating panel.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/tree',
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
    var visible = __graph_visible.visible
    var __view_record = require('dsh-cdd-lens/view/record')
    var dotClass = __view_record.dotClass
    var orderOf = __view_record.orderOf
    var short = __view_record.short
    var stateOf = __view_record.stateOf
    var turnLabel = __view_record.turnLabel
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf

    // ---- the vertical tree (floating panel) --------------------------------

    /**
     * Depth-first walk of the expanded graph, emitting rows with indents.
     *
     * Callers come first (they are "above" in the call direction), then the node
     * itself, then callees. Islands are emitted after a divider that names them
     * as unconnected rather than being folded into the tree.
     */
    function treeRows(graph) {
      var rows = []
      var seen = {}
      var shown = visible(graph)
      // Everything the session touched is shown whether or not an edge reaches
      // it. An anchor with no relations in the index is still an anchor the
      // agent opened, and dropping it would hide the very thing being reported.
      graph.order.forEach(function (id) { shown[id] = true })

      function walk(id, depth, direction) {
        if (seen[id] || !shown[id]) return
        seen[id] = true
        var node = graph.nodes[id]
        var ui = uiOf(graph, id) || {}
        if (node === undefined) return
        // Callers of an expanded node render ABOVE it at the same depth,
        // whichever direction the walk arrived from. Gating this on the arrival
        // direction meant pressing ↑ on anything below the root added the nodes
        // and drew none of them — the button looked dead.
        var openUp = Object.keys(ui.open).some(function (k) {
          return k.indexOf('up:') === 0 && ui.open[k] === true
        })
        if (openUp) {
          graph.edges.forEach(function (e) {
            if (e.to === id) walk(e.from, depth, 'up')
          })
        }
        rows.push({ id: id, depth: depth, node: node })
        if (ui.members && ui.memberList !== undefined) {
          ui.memberList.forEach(function (member) {
            rows.push({ id: member.id, depth: depth + 1, member: true, anchor: member })
          })
        }
        var openDown = Object.keys(ui.open).some(function (k) {
          return k.indexOf('down:') === 0 && ui.open[k] === true
        })
        if (openDown) {
          graph.edges.forEach(function (e) {
            if (e.from === id) walk(e.to, depth + 1, 'down')
          })
        }
      }

      if (graph.rootId !== null) walk(graph.rootId, 0, null)

      // Anchors the session touched that the root's subtree does not reach.
      // Each is walked as its own root, so a pair the code DOES connect nests
      // instead of being listed side by side as two unrelated things — the
      // edges are the whole point, and flattening them here threw them away
      // after the trouble of finding them.
      var roots = graph.order.filter(function (id) {
        if (seen[id] || !shown[id]) return false
        // Only a node nothing else in the graph reaches is a root of its own.
        return !graph.edges.some(function (e) {
          return e.to === id && graph.nodes[e.from] !== undefined && shown[e.from]
        })
      })
      if (roots.length > 0) {
        rows.push({ gap: true })
        roots.forEach(function (id) {
          var before = rows.length
          walk(id, 0, 'down')
          if (rows.length > before) rows[before].islandRow = true
        })
      }
      return rows
    }

    function TreeRow(props) {
      var engine = props.engine
      var row = props.row
      if (row.gap) {
        return h('div', { className: 'cddl-gap' }, [
          h('i', { key: 'l' }), '碰过但代码里没有边 · 不连', h('i', { key: 'r' }),
        ])
      }
      var anchor = row.member ? row.anchor : row.node
      var record = stateOf(row.id)
      var faded = record !== null && record !== undefined && !record.remembered
      var selected = shared.selected === row.id
      var ui = row.node !== undefined ? (uiOf(shared.graph, row.id) || {}) : {}
      var synthetic = row.node !== undefined && (ui.synthetic === true || ui.bridge === true)
      var cls = 'cddl-node'
        + (selected ? ' cddl-sel' : '')
        + (faded ? ' cddl-faded' : '')
        + (row.node !== undefined && ui.bridge === true ? ' cddl-bridge' : '')
        + (row.islandRow ? ' cddl-island' : '')

      var kids = [
        h('span', { key: 'i', className: 'cddl-ind', style: { width: (row.depth * 17) + 'px' } }),
      ]
      if (!row.member && !synthetic && (anchor.members > 0)) {
        kids.push(h('button', {
          key: 't', className: 'cddl-twist', title: anchor.members + ' 个成员',
          onClick: function (e) { e.stopPropagation(); engine.members(row.id) },
        }, ui.members ? '▾' : '▸'))
      } else {
        kids.push(h('span', { key: 't', className: 'cddl-twist' }, row.member ? '·' : ''))
      }
      var rank = orderOf(row.id)
      kids.push(rank === null
        ? h('span', { key: 'r', className: 'cddl-rank cddl-rank-none' }, '')
        : h('span', { key: 'r', className: 'cddl-rank', title: '第 ' + rank + ' 个被碰到' }, rank))
      kids.push(h('span', { key: 'd', className: dotClass(record) }))
      kids.push(h('span', { key: 's', className: 'cddl-sym', title: anchor.id }, anchor.symbol))
      if (!row.member && !synthetic && anchor.members > 0) {
        kids.push(h('span', { key: 'k', className: 'cddl-kind' }, '类 ' + anchor.members))
      }
      if (row.node !== undefined && ui.bridge === true) {
        kids.push(h('span', {
          key: 'br', className: 'cddl-kind cddl-bridgetag',
          title: 'agent 没打开过它。它出现在这里，是因为代码里它把上下两个碰过的 anchor 连起来了。',
        }, '桥'))
      }
      var badge = turnLabel(record)
      if (badge !== null) kids.push(React.cloneElement(badge, { key: 'b' }))
      if (faded) kids.push(h('span', { key: 'f', className: 'cddl-kind' }, '压缩'))
      var REL_ORDER = ['call', 'dataflow', 'inherit', 'dispatch', 'impact']
      var hop = function (direction, rel, count) {
        var slot = direction + ':' + rel
        var open = ui.open[slot] === true
        // 桥接点不许继续展开：它是布局借来的中间点，不是 agent 打开过的 anchor。
        var disabled = synthetic
        return h('button', {
          key: slot,
          disabled: disabled,
          'data-relation': rel,
          'data-count': count,
          title: synthetic
            ? '桥接节点只解释连接，不继续展开'
            : ((open ? '收起' : '展开') + (direction === 'up' ? '：谁在用它（' : '：它在用谁（') + count + '）'
              + ' · ' + rel + '\n按住 Shift 点：一路展开到底'),
          className: 'cddl-rel-' + rel + (open ? ' on' : '') + (disabled ? ' cddl-off' : ''),
          onClick: function (e) {
            e.stopPropagation()
            if (disabled) return
            if (open) { engine.collapse(row.id, direction, rel); return }
            if (e.shiftKey) engine.walk(row.id, direction, rel, 4)
            else engine.expand(row.id, direction, null, rel)
          },
        }, (direction === 'up' ? '↑' : '↓') + count)
      }
      var hopButtons = []
      REL_ORDER.forEach(function (rel) {
        var c = (anchor.peerCounts || {})[rel]
        // 没有数据的关系不出现——不画箭头、不写 0。
        if (c === undefined) return
        if (c.up > 0) hopButtons.push(hop('up', rel, c.up))
        if (c.down > 0) hopButtons.push(hop('down', rel, c.down))
      })
      kids.push(h('span', { key: 'h', className: 'cddl-hop' }, hopButtons.concat([
        h('button', {
          key: 'p', title: '固定',
          className: ui.pinned ? 'on' : '',
          onClick: function (e) { e.stopPropagation(); engine.pin(row.id) },
        }, ui.pinned ? '●' : '○'),
      ])))

      return h('div', {
        className: cls,
        onClick: function () { engine.select(row.id) },
      }, kids)
    }

    function Tree(props) {
      var engine = props.engine
      var rows = treeRows(shared.graph)
      if (rows.length === 0) {
        return h('div', { className: 'cddl-empty' },
          '还没有起点。到「目录」里翻一个函数，或者搜一个名字。')
      }
      var out = []
      var lastFile = null
      rows.forEach(function (row, i) {
        if (row.gap) { out.push(h(TreeRow, { key: 'gap' + i, row: row, engine: engine })); lastFile = null; return }
        var anchor = row.member ? row.anchor : row.node
        if (anchor.file !== lastFile) {
          lastFile = anchor.file
          out.push(h('div', {
            key: 'f' + i, className: 'cddl-filehdr',
            style: { paddingLeft: (row.depth * 17 + 2) + 'px' }, title: anchor.file,
          }, short(anchor.file)))
        }
        out.push(h(TreeRow, { key: row.id + ':' + i, row: row, engine: engine }))
      })
      return h('div', { className: 'cddl-tree' }, out)
    }

    module.exports = { treeRows, TreeRow, Tree }
    return module.exports
  },
})
