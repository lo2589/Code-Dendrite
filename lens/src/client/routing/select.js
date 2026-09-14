// dsh-cdd-lens — Drawing every relation is what makes the web; this picks.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/select',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf

    /**
     * Which relations get a wire: a trunk by default, the rest on demand.
     */
    function chooseEdges(graph, scope, orient) {
      var activeFocus = scope.activeFocus
      var byId = orient.byId

      // ---- which edges get drawn ------------------------------------------
      //
      // Drawing every relation is what makes the web, and no amount of clever
      // routing fixes it. Measured on this graph — 103 nodes, 227 call/dispatch
      // edges — the three-segment dogleg router produces 1326 geometric
      // crossings. Giving each edge its own corridor makes it WORSE (5265):
      // separate lanes mean more turns, and the turns are what cross.
      //
      // Only the edge count moves the number. A spanning tree over the same
      // nodes is 63 edges and 55 crossings — a 24x drop with identical node
      // placement. So the trunk is drawn by default and everything else is
      // reachable: selecting a node lights up all of ITS relations (32 edges,
      // 30 crossings), and the per-node up/down counts were always the hidden
      // ones. This is the flyline idea from board layout, where the same
      // problem has the same answer — except a router must connect every net
      // and we may simply not draw one.
      // 一条边算不算「打开」：这条边自己的关系类型对应的那个按钮开没开。
      // 展开状态按「方向:关系」存（ui.open['down:call']），所以必须看边的类型，
      // 不能只看方向——点开 call 的 ↓ 不该把 inherit 的边也点亮。
      var opened = function (ui, prefix, types) {
        if (ui === null || ui === undefined || ui.open === undefined) return false
        return types.some(function (t) {
          return ui.open[prefix + ':' + t] === true
        })
      }
      var drawable = graph.edges.filter(function (e) {
        var fromUI = uiOf(graph, e.from)
        var toUI = uiOf(graph, e.to)
        if (byId[e.from] === undefined || byId[e.to] === undefined) return false
        if (activeFocus !== null || e.always) return true
        var types = e.types || ['call']
        return opened(fromUI, 'down', types) || opened(toUI, 'up', types)
      })
      var chosen = drawable
      var hiddenCount = 0
      if (activeFocus !== null) {
        chosen = drawable.filter(function (edge) {
          return (edge.types || ['call']).some(function (type) {
            return activeFocus.keys[edge.from + '→' + edge.to + ':' + type] === true
          })
        })
        hiddenCount = drawable.length - chosen.length
      } else if (shared.wireMode !== 'all') {
        var keep = {}
        var focus = shared.selected
        // Every relation of the selected node, in both directions.
        drawable.forEach(function (e) {
          if (e.from === focus || e.to === focus) keep[e.from + '→' + e.to] = true
        })
        // One parent per node — the one the chain data means, not the nearest
        // placed caller. Geometric distance made the trunk a function of the
        // skin: move the nodes and a different edge becomes the parent, so the
        // same graph showed a different skeleton in every drawing. Consistency
        // across skins beats hugging one layout. The layer comes from the
        // index (DFS finish order, longest-path relaxed) and rides in on
        // node.layer, so the caller exactly one layer up is the real parent;
        // otherwise the smallest layer difference wins, with a forward step
        // preferred over a backward one of the same size, and nodes without a
        // layer are decided by the edge's place in graph.edges — stable, and
        // the same in every skin because it never touches a coordinate.
        var best = {}
        drawable.forEach(function (e) {
          var from = graph.nodes[e.from]
          var to = graph.nodes[e.to]
          var la = from === undefined ? undefined : from.layer
          var lb = to === undefined ? undefined : to.layer
          var d = typeof la === 'number' && typeof lb === 'number' ? lb - la : null
          var cost = d === null ? Infinity
            : d === 1 ? 0
            : Math.abs(d) + (d < 1 ? 0.5 : 0)
          // Strictly smaller wins, so a tie keeps the edge that came first —
          // the deterministic tiebreak, with no geometry involved.
          if (best[e.to] === undefined || cost < best[e.to].cost) best[e.to] = { e: e, cost: cost }
        })
        Object.keys(best).forEach(function (to) {
          var e = best[to].e
          keep[e.from + '→' + e.to] = true
        })
        chosen = drawable.filter(function (e) { return keep[e.from + '→' + e.to] === true })
        hiddenCount = drawable.length - chosen.length
      }
      shared.wireStats = { drawn: chosen.length, hidden: hiddenCount, total: drawable.length }

      return { chosen: chosen, hiddenCount: hiddenCount }
    }

    module.exports = { chooseEdges }
    return module.exports
  },
})
