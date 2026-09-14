// dsh-cdd-lens — 树面板：屏幕（shared.screen）的文字版。
//
// 行 = 屏幕上的节点，按屏幕上的边缩进；不在当前树里的 seed 放在最后一段。
// 只读 shared.screen 和由它生成的 shared.graph，不筛选、不增删节点。
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
    var __view_record = require('dsh-cdd-lens/view/record')
    var dotClass = __view_record.dotClass
    var orderOf = __view_record.orderOf
    var short = __view_record.short
    var stateOf = __view_record.stateOf
    var turnLabel = __view_record.turnLabel
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf

    var REL_ORDER = ['call', 'dataflow', 'inherit', 'dispatch', 'impact']

    function treeRows(graph) {
      var screen = shared.screen
      if (screen === null || screen === undefined) return []
      var rows = []
      var seen = {}
      var inTree = {}
      var children = {}
      var hasParent = {}
      screen.nodes.forEach(function (id) { inTree[id] = true })
      graph.edges.forEach(function (e) {
        if (!inTree[e.from] || !inTree[e.to] || e.from === e.to) return
        if (children[e.from] === undefined) children[e.from] = []
        if (children[e.from].indexOf(e.to) < 0) children[e.from].push(e.to)
        hasParent[e.to] = true
      })
      var push = function (id, depth, extra) {
        var node = graph.nodes[id]
        if (node === undefined) return
        rows.push(Object.assign({ id: id, depth: depth, node: node }, extra || {}))
        var ui = uiOf(graph, id) || {}
        if (ui.members && ui.memberList !== undefined) {
          ui.memberList.forEach(function (member) {
            rows.push({ id: member.id, depth: depth + 1, member: true, anchor: member })
          })
        }
      }
      var walk = function (id, depth) {
        if (seen[id]) return
        seen[id] = true
        push(id, depth)
        ;(children[id] || []).slice().sort().forEach(function (kid) { walk(kid, depth + 1) })
      }
      screen.nodes.filter(function (id) { return !hasParent[id] }).forEach(function (id) { walk(id, 0) })
      // 环里的节点没有无父的入口，兜底再走一遍，一个都不漏。
      screen.nodes.forEach(function (id) { walk(id, 0) })
      if (screen.side.length > 0) {
        rows.push({ gap: true, count: screen.side.length })
        screen.side.forEach(function (id) { push(id, 0, { sideRow: true }) })
      }
      return rows
    }

    function hopButtons(engine, id) {
      var counts = (shared.screen && shared.screen.buttons && shared.screen.buttons[id]) || {}
      var out = []
      REL_ORDER.forEach(function (rel) {
        ['up', 'down'].forEach(function (dir) {
          var n = counts[rel + dir]
          if (!(n > 0)) return
          var open = engine.isOpen(id, rel, dir)
          out.push(h('button', {
            key: dir + ':' + rel,
            'data-relation': rel,
            'data-count': n,
            title: (open ? '收起' : '展开') + '：' + (rel === 'dataflow' ? (dir === 'up' ? '数据从谁流进来' : '数据流到谁那里去') : (dir === 'up' ? '谁在用它' : '它在用谁')) + '（' + n + '） · ' + rel,
            className: 'cddl-rel-' + rel + (open ? ' on' : ''),
            onClick: function (e) { e.stopPropagation(); engine.toggleOpen(id, rel, dir) },
          }, (dir === 'up' ? '↑' : '↓') + n))
        })
      })
      return out
    }

    function TreeRow(props) {
      var engine = props.engine
      var row = props.row
      if (row.gap) {
        return h('div', { className: 'cddl-gap' }, [
          h('i', { key: 'l' }), '不在当前树里的 seed · ' + row.count, h('i', { key: 'r' }),
        ])
      }
      var anchor = row.member ? row.anchor : row.node
      var record = stateOf(row.id)
      var faded = record !== null && record !== undefined && !record.remembered
      var ui = row.member ? {} : (uiOf(shared.graph, row.id) || {})
      var memberCount = !row.member && Array.isArray(anchor.own_methods) ? anchor.own_methods.length : 0
      var pinned = !row.member && engine.isPinned(row.id)
      var kids = [h('span', { key: 'i', className: 'cddl-ind', style: { width: (row.depth * 17) + 'px' } })]
      if (memberCount > 0) {
        kids.push(h('button', {
          key: 't', className: 'cddl-twist', title: memberCount + ' 个成员',
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
      if (memberCount > 0) kids.push(h('span', { key: 'k', className: 'cddl-kind' }, '类 ' + memberCount))
      var badge = turnLabel(record)
      if (badge !== null) kids.push(React.cloneElement(badge, { key: 'b' }))
      if (faded) kids.push(h('span', { key: 'f', className: 'cddl-kind' }, '压缩'))
      if (!row.member) {
        kids.push(h('span', { key: 'h', className: 'cddl-hop' }, hopButtons(engine, row.id).concat([
          h('button', {
            key: 'p', title: pinned ? '取消固定' : '固定', className: pinned ? 'on' : '',
            onClick: function (e) { e.stopPropagation(); engine.pin(row.id) },
          }, pinned ? '●' : '○'),
        ])))
      }
      return h('div', {
        className: 'cddl-node' + (shared.selected === row.id ? ' cddl-sel' : '') + (faded ? ' cddl-faded' : '') + (row.sideRow ? ' cddl-island' : ''),
        onClick: function () { engine.select(row.id) },
      }, kids)
    }

    function Tree(props) {
      var engine = props.engine
      var rows = treeRows(shared.graph)
      if (rows.length === 0) {
        return h('div', { className: 'cddl-empty' }, '还没有起点。到「目录」里翻一个函数，或者搜一个名字。')
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
