// dsh-cdd-lens — Edge kinds, the line-focus camera, and the layout it derives.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/camera',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared

    // ---- the spread-out graph (conversation.view) ---------------------------
    //
    // A layered layout: callers above the selection, callees below, one row per
    // hop, orthogonal wires. Positions are computed from measured text rather
    // than a physics simulation — a node must not drift when a sibling expands.

    var CHAR = 6.9
    var ROW = 126
    var GAPX = 26
    var MAX_PER_ROW = 4

    function edgeHasType(edge, type) {
      return (edge.types || []).indexOf(type) >= 0
    }

    function dependencyEdge(edge) {
      return !edgeHasType(edge, 'dataflow')
        || (edge.types || []).some(function (type) { return type !== 'dataflow' })
    }

    /** Nodes/edges shown by the temporary line-focus camera. */
    function edgeFocusOf(graph) {
      var wanted = shared.edgeFocus
      if (wanted === null || wanted === undefined) return null
      var ids = {}
      var keys = {}
      ids[wanted.from] = true
      ids[wanted.to] = true
      keys[wanted.from + '→' + wanted.to + ':' + wanted.type] = true

      if (wanted.type === 'dataflow') {
        // A data value is followed end to end. Both directions are visited so
        // clicking the middle of a producer/consumer chain still reveals its
        // origin and every eventual consumer.
        var queue = [wanted.from, wanted.to]
        while (queue.length > 0) {
          var current = queue.shift()
          graph.edges.forEach(function (edge) {
            if (!edgeHasType(edge, 'dataflow')) return
            if (edge.from !== current && edge.to !== current) return
            keys[edge.from + '→' + edge.to + ':dataflow'] = true
            ;[edge.from, edge.to].forEach(function (id) {
              if (ids[id]) return
              ids[id] = true
              queue.push(id)
            })
          })
        }
      } else {
        var walk = function (start, direction) {
          var frontier = [start]
          for (var hop = 0; hop < 3; hop += 1) {
            var next = []
            frontier.forEach(function (current) {
              graph.edges.forEach(function (edge) {
                if (!dependencyEdge(edge)) return
                var matches = direction === 'up' ? edge.to === current : edge.from === current
                if (!matches) return
                var id = direction === 'up' ? edge.from : edge.to
                ;(edge.types || ['call']).forEach(function (type) {
                  if (type !== 'dataflow') keys[edge.from + '→' + edge.to + ':' + type] = true
                })
                if (!ids[id]) { ids[id] = true; next.push(id) }
              })
            })
            frontier = next
          }
        }
        walk(wanted.from, 'up')
        walk(wanted.to, 'down')
      }
      return { ids: ids, keys: keys, type: wanted.type }
    }

    /**
     * @param avail - the canvas viewport's real width in CSS pixels. Everything
     *   that decides how wide the drawing gets is derived from it. The previous
     *   version divided a hardcoded 1580 to choose the column count, which is a
     *   viewport that does not exist here: the canvas actually gets about 977
     *   (the window minus dsh's sidebar, minus the space reserved for a
     *   neighbouring plugin's rail, minus this view's own source column). So the
     *   layout produced a drawing wider than the space it had, and no amount of
     *   font or routing work could make that readable.
     */
    /**
     * Temporary camera layout: a top-to-bottom relationship chain.
     *
     * It never writes shared.nodePositions, so leaving the camera restores
     * every user coordinate exactly.
     * @param graph - the graph being drawn.
     * @param scope - what is on screen.
     * @param place - the boxes and nodes already positioned.
     * @param rank - relationship ranking for this graph.
     * @param metrics - box metrics for this canvas.
     */
    function cameraLayout(graph, scope, place, rank, metrics) {
      var activeFocus = scope.activeFocus
      var included = scope.included
      var placed = place.placed
      var indegree = rank.indegree
      var NODE_W = metrics.NODE_W
      var PAD = metrics.PAD

      if (activeFocus === null) {
        // Auto-layout provides first positions only. Once the user moves an
        // anchor, that coordinate wins across refresh, expansion and reindex.
        placed.forEach(function (p) {
          var point = shared.nodePositions[p.id]
          if (point === undefined) return
          p.x = point.x
          p.y = point.y
          // Marked, because everything downstream has to tell a coordinate the
          // user chose from one the layout produced: which box yields when two
          // collide, and which one may be pulled back when it ends up stranded.
          p.manual = true
        })
      } else {
        // Temporary camera layout. It derives a top-to-bottom relationship
        // chain: every caller/callee step flips the node's in/out side.
        // without touching shared.nodePositions, so exit restores every user
        // coordinate exactly.
        var focusedEdges = []
        graph.edges.forEach(function (edge) {
          ;(edge.types || ['call']).forEach(function (type) {
            var key = edge.from + '→' + edge.to + ':' + type
            if (activeFocus.keys[key]) focusedEdges.push({ from: edge.from, to: edge.to, type: type })
          })
        })
        var indegree = {}
        included.forEach(function (id) { indegree[id] = 0 })
        focusedEdges.forEach(function (edge) {
          if (indegree[edge.to] !== undefined && indegree[edge.from] !== undefined) indegree[edge.to] += 1
        })
        var depthById = {}
        var queue = included.filter(function (id) { return indegree[id] === 0 })
        if (queue.length === 0 && shared.edgeFocus) queue.push(shared.edgeFocus.from)
        queue.forEach(function (id) { depthById[id] = 0 })
        while (queue.length > 0) {
          var current = queue.shift()
          focusedEdges.forEach(function (edge) {
            if (edge.from !== current || depthById[edge.to] !== undefined) return
            depthById[edge.to] = depthById[current] + 1
            queue.push(edge.to)
          })
        }
        var nextDepth = 0
        included.forEach(function (id) {
          if (depthById[id] === undefined) depthById[id] = nextDepth++
        })
        var levels = {}
        placed.forEach(function (p) {
          var level = depthById[p.id] || 0
          ;(levels[level] = levels[level] || []).push(p)
        })
        Object.keys(levels).sort(function (l, r) { return Number(l) - Number(r) }).forEach(function (level) {
          levels[level].forEach(function (p, row) {
            p.x = PAD + 46 + row * (NODE_W + 76)
            p.y = PAD + 46 + Number(level) * (Math.max(72, p.h) + 62)
          })
        })
      }

    }

    module.exports = { CHAR, ROW, GAPX, MAX_PER_ROW, edgeHasType, dependencyEdge, edgeFocusOf, cameraLayout }
    return module.exports
  },
})
