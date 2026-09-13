// dsh-cdd-lens — The accumulating node/edge store: pure graph operations.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/graph/model',
  factory: (require) => {
    var module = { exports: {} }

    // ---- graph store ------------------------------------------------------
    //
    // Nodes and edges accumulate as you walk. Nothing is ever silently dropped:
    // collapsing hides descendants that no other branch and no pin is holding,
    // and the anchor's turn record survives regardless — a collapse must not
    // erase that the agent was there on turn 3.

    function emptyGraph() {
      return { nodes: {}, order: [], edges: [], rootId: null }
    }

    function addNode(graph, anchor) {
      if (graph.nodes[anchor.id] !== undefined) {
        // Refresh the counts; a reindex can change them under us.
        graph.nodes[anchor.id].anchor = anchor
        return false
      }
      // up/down 是按钮状态（用户按出来的）；autoUp/autoDown 是 gather 选中时
      // 自动拉进来的邻居。两者分开，按钮才不会被 gather 代按。
      graph.nodes[anchor.id] = {
        anchor: anchor, down: false, up: false, autoDown: false, autoUp: false,
        members: false, pinned: false,
      }
      graph.order.push(anchor.id)
      return true
    }

    function addEdge(graph, from, to, types) {
      for (var i = 0; i < graph.edges.length; i++) {
        if (graph.edges[i].from === from && graph.edges[i].to === to) {
          var found = graph.edges[i]
          ;(types || ['call']).forEach(function (type) {
            if (found.types.indexOf(type) < 0) found.types.push(type)
          })
          return found
        }
      }
      var edge = { from: from, to: to, types: types || ['call'] }
      graph.edges.push(edge)
      return edge
    }

    /**
     * Drop a node and every edge touching it. Revalidation is the only caller:
     * an anchor the rebuilt index no longer holds is not a node that went
     * invisible, it is a node that does not exist, and hiding it would keep
     * answering questions about code that is gone.
     */
    function removeNode(graph, id) {
      if (graph.nodes[id] === undefined) return false
      delete graph.nodes[id]
      graph.order = graph.order.filter(function (x) { return x !== id })
      graph.edges = graph.edges.filter(function (e) { return e.from !== id && e.to !== id })
      if (graph.rootId === id) graph.rootId = graph.order.length > 0 ? graph.order[0] : null
      return true
    }

    /** Ids reachable from the roots along currently expanded edges. */
    /**
     * How long an anchor the agent touched holds itself on the graph.
     *
     * Three turns after it was last mentioned. `node.session` alone kept every
     * anchor a session ever opened as a permanent root, so a long conversation
     * only ever accumulated — collapsing a branch freed nothing. Three turns is
     * long enough that the thing just being worked on never vanishes, and an
     * explicit pin overrides it and never expires.
     */

    module.exports = { emptyGraph, addNode, addEdge, removeNode }
    return module.exports
  },
})
