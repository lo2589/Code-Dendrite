// dsh-cdd-lens — Which anchors stay on screen: pins and recency.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/graph/visible',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared

    var STICKY_TURNS = 3

    function stickyByRecency(id) {
      var record = shared.trace[id]
      if (record === undefined) return false
      return shared.turn - record.lastTurn < STICKY_TURNS
    }

    function visible(graph) {
      var roots = []
      if (graph.rootId !== null && graph.nodes[graph.rootId] !== undefined) roots.push(graph.rootId)
      graph.order.forEach(function (id) {
        var node = graph.nodes[id]
        if (node.pinned || node.island || stickyByRecency(id)) roots.push(id)
      })
      var seen = {}
      var stack = roots.slice()
      while (stack.length > 0) {
        var id = stack.pop()
        if (seen[id]) continue
        seen[id] = true
        var node = graph.nodes[id]
        if (node === undefined) continue
        graph.edges.forEach(function (e) {
          // `always` edges join the session's own anchors; they show whether or
          // not anyone pressed expand. `autoUp`/`autoDown` are what gather pulled
          // in on selection: they must be drawn, but they are NOT the button's
          // state — the button only reads up/down (node.js:74,88).
          if (e.from === id && (node.down || node.autoDown || e.always)) stack.push(e.to)
          if (e.to === id && (node.up || node.autoUp || e.always)) stack.push(e.from)
        })
      }
      return seen
    }

    module.exports = { STICKY_TURNS, stickyByRecency, visible }
    return module.exports
  },
})
