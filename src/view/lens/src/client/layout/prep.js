// dsh-cdd-lens — What gets drawn, in what order, and which way round.
//
// Everything decided before a coordinate exists: which nodes are on screen,
// which file each column belongs to and in what order, and which side of a
// node its wires enter and leave by. Three questions, one answer set, and no
// skin can place anything until all three are settled.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/prep',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __graph_visible = require('dsh-cdd-lens/graph/visible')
    var visible = __graph_visible.visible
    var __layout_camera = require('dsh-cdd-lens/layout/camera')
    var edgeFocusOf = __layout_camera.edgeFocusOf

    /**
     * What is on screen at all, and which file each anchor belongs to.
     */
    function layoutScope(graph) {

      var shown = visible(graph)

      // A file is the first visual unit. Session-touched anchors are always
      // present; manual +/- exploration may add more anchors and therefore a
      // new file box, while bridge-only implementation details stay hidden.
      var included = graph.order.filter(function (id) {
        var node = graph.nodes[id]
        return shown[id] && node !== undefined
          && (node.session || node.explored || node.pinned || id === shared.selected || id === graph.rootId)
      })
      if (included.length === 0 && graph.nodes[graph.rootId]) included.push(graph.rootId)
      var activeFocus = edgeFocusOf(graph)
      if (activeFocus !== null) {
        included = graph.order.filter(function (id) {
          return activeFocus.ids[id] === true && graph.nodes[id] !== undefined
        })
      }
      var byFile = {}
      var fileOrder = []
      included.forEach(function (id) {
        var file = graph.nodes[id].anchor.file
        if (byFile[file] === undefined) { byFile[file] = []; fileOrder.push(file) }
        byFile[file].push(id)
      })
      return { shown: shown, included: included, activeFocus: activeFocus, byFile: byFile, fileOrder: fileOrder }
    }

    /**
     * Relationship order, not source-line order and not row parity.
     */
    function rankFiles(graph, relationFilter, scope) {
      var included = scope.included
      var byFile = scope.byFile
      var fileOrder = scope.fileOrder

      // Relationship order, not source-line order and not row parity. Start at
      // a visible main (when present), then the session root, then every other
      // component. Each real caller -> callee edge advances one relationship
      // step. Cycles are harmless because a node is ranked only once.
      var includedSet = {}
      included.forEach(function (id) { includedSet[id] = true })
      var relationEdges = graph.edges.filter(function (edge) {
        if (!includedSet[edge.from] || !includedSet[edge.to]) return false
        return (edge.types || ['call']).some(function (type) {
          return relationFilter === undefined || relationFilter[type] !== false
        })
      })
      var outgoing = {}
      var indegree = {}
      included.forEach(function (id) { outgoing[id] = []; indegree[id] = 0 })
      relationEdges.forEach(function (edge) {
        outgoing[edge.from].push(edge.to)
        indegree[edge.to] += 1
      })
      var relationRank = {}
      var rankQueue = []
      var nextComponentRank = 0
      var rankFrom = function (seed) {
        if (!includedSet[seed] || relationRank[seed] !== undefined) return
        relationRank[seed] = nextComponentRank
        rankQueue.push(seed)
        while (rankQueue.length > 0) {
          var current = rankQueue.shift()
          outgoing[current].forEach(function (next) {
            if (relationRank[next] !== undefined) return
            relationRank[next] = relationRank[current] + 1
            rankQueue.push(next)
          })
        }
        nextComponentRank = Math.max.apply(Math, Object.keys(relationRank).map(function (id) { return relationRank[id] })) + 2
      }
      included.filter(function (id) {
        return graph.nodes[id].anchor.symbol.split && graph.nodes[id].anchor.symbol.split('.').pop() === 'main'
      }).forEach(rankFrom)
      rankFrom(graph.rootId)
      included.filter(function (id) { return indegree[id] === 0 }).forEach(rankFrom)
      included.forEach(rankFrom)

      // A file box follows the earliest relationship step of the anchors it
      // contains. The box is a visual boundary only; it no longer invents the
      // semantic order of nodes inside it.
      var depth = {}
      fileOrder.forEach(function (file) {
        depth[file] = Math.min.apply(Math, byFile[file].map(function (id) { return relationRank[id] }))
      })
      var arrival = {}
      fileOrder.forEach(function (file, i) { arrival[file] = i })
      fileOrder.sort(function (l, r) { return depth[l] - depth[r] || arrival[l] - arrival[r] })

      fileOrder.forEach(function (file) {
        byFile[file].sort(function (l, r) {
          var la = graph.nodes[l].anchor
          var ra = graph.nodes[r].anchor
          var lm = la.symbol.split('.').pop() === 'main' ? 0 : 1
          var rm = ra.symbol.split('.').pop() === 'main' ? 0 : 1
          return relationRank[l] - relationRank[r] || lm - rm
            || (la.start || 0) - (ra.start || 0) || la.symbol.localeCompare(ra.symbol)
        })
      })

      return { indegree: indegree, relationRank: relationRank }
    }

    /**
     * In/out sides propagated by real relations, not by row number.
     */
    function orientFlow(graph, scope, place, metrics, avail) {
      var included = scope.included
      var placed = place.placed
      var fileBoxes = place.fileBoxes
      var canvasY = place.canvasY
      var PAD = metrics.PAD
      var BOX_GAP_Y = metrics.BOX_GAP_Y
      var canvasWidth = metrics.canvasWidth

      var byId = {}
      placed.forEach(function (p) { byId[p.id] = p })

      // The alternating in/out sides this used to compute are gone: every box
      // is laid in the same grid and every port is on a side, so a node that
      // flipped put its entry where its callers leave from. The walk that
      // produced them is gone with them — it re-scanned every edge for every
      // node it reached, which is O(nodes x edges) and was the single most
      // expensive thing in a layout whose result was then overwritten.
      placed.forEach(function (p) { p.flowDir = 'ltr' })
      var boxOf = {}
      fileBoxes.forEach(function (box) { boxOf[box.file] = box })
      canvasWidth = Math.max(avail || 0, PAD * 2 + Math.max.apply(Math, placed.map(function (p) { return p.x + p.w })))
      canvasY = PAD + Math.max.apply(Math, placed.map(function (p) { return p.y + p.h })) + BOX_GAP_Y

      return { byId: byId, boxOf: boxOf, canvasWidth: canvasWidth, canvasY: canvasY }
    }

    module.exports = { layoutScope, rankFiles, orientFlow }
    return module.exports
  },
})
