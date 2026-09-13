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
        if (node === undefined) return
        // Callers of an expanded node render ABOVE it at the same depth,
        // whichever direction the walk arrived from. Gating this on the arrival
        // direction meant pressing ↑ on anything below the root added the nodes
        // and drew none of them — the button looked dead.
        if (node.up) {
          graph.edges.forEach(function (e) {
            if (e.to === id) walk(e.from, depth, 'up')
          })
        }
        rows.push({ id: id, depth: depth, node: node })
        if (node.members && node.memberList !== undefined) {
          node.memberList.forEach(function (member) {
            rows.push({ id: member.id, depth: depth + 1, member: true, anchor: member })
          })
        }
        if (node.down) {
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
      var anchor = row.member ? row.anchor : row.node.anchor
      var record = stateOf(row.id)
      var faded = record !== null && record !== undefined && !record.remembered
      var selected = shared.selected === row.id
      var synthetic = row.node !== undefined && (row.node.synthetic === true || row.node.bridge === true)
      var cls = 'cddl-node'
        + (selected ? ' cddl-sel' : '')
        + (faded ? ' cddl-faded' : '')
        + (row.node !== undefined && row.node.bridge === true ? ' cddl-bridge' : '')
        + (row.islandRow ? ' cddl-island' : '')

      var kids = [
        h('span', { key: 'i', className: 'cddl-ind', style: { width: (row.depth * 17) + 'px' } }),
      ]
      if (!row.member && !synthetic && (anchor.members > 0)) {
        kids.push(h('button', {
          key: 't', className: 'cddl-twist', title: anchor.members + ' 个成员',
          onClick: function (e) { e.stopPropagation(); engine.members(row.id) },
        }, row.node.members ? '▾' : '▸'))
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
      if (row.node !== undefined && row.node.bridge === true) {
        kids.push(h('span', {
          key: 'br', className: 'cddl-kind cddl-bridgetag',
          title: 'agent 没打开过它。它出现在这里，是因为代码里它把上下两个碰过的 anchor 连起来了。',
        }, '桥'))
      }
      var badge = turnLabel(record)
      if (badge !== null) kids.push(React.cloneElement(badge, { key: 'b' }))
      if (faded) kids.push(h('span', { key: 'f', className: 'cddl-kind' }, '压缩'))
      var hop = function (dir, count, label) {
        var disabled = count === 0 || synthetic
        // A zero count is a fact about the index, not a button. Leaving it
        // clickable makes every press look broken; disabling it says the index
        // has no such edge, which is the actual answer.
        return h('button', {
          key: dir,
          disabled: disabled,
          title: synthetic
            ? '桥接节点只解释连接，不继续展开'
            : count === 0
            ? (dir === 'u' ? '索引里没有谁用它' : '索引里它没用任何东西')
            : ((row.node && row.node[dir === 'u' ? 'up' : 'down'] ? '收起' : '展开')
              + (dir === 'u' ? '：谁在用它（' : '：它在用谁（') + count + '）'),
          className: (row.node && row.node[dir === 'u' ? 'up' : 'down'] ? 'on' : '')
            + (disabled ? ' cddl-off' : ''),
          onClick: function (e) {
            e.stopPropagation()
            if (disabled) return
            var direction = dir === 'u' ? 'up' : 'down'
            if (row.node && row.node[direction]) engine.collapse(row.id, direction)
            else engine.expand(row.id, direction)
          },
        }, label + count)
      }
      kids.push(h('span', { key: 'h', className: 'cddl-hop' }, [
        hop('u', anchor.up, '↑'),
        hop('d', anchor.down, '↓'),
        h('button', {
          key: 'p', title: '固定',
          className: row.node && row.node.pinned ? 'on' : '',
          onClick: function (e) { e.stopPropagation(); engine.pin(row.id) },
        }, row.node && row.node.pinned ? '●' : '○'),
      ]))

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
        var anchor = row.member ? row.anchor : row.node.anchor
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
