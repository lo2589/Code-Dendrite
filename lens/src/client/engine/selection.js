// dsh-cdd-lens — Engine methods for selection, edge focus and dragging.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/engine/selection',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var requestViewport = __state_store.requestViewport
    var shared = __state_store.shared
    var __state_persist = require('dsh-cdd-lens/state/persist')
    var saveNodePosition = __state_persist.saveNodePosition

    /**
     * What is selected, focused, or being dragged.
     *
     * @param ctx - the client context the views were mounted with.
     * @param engine - the engine being assembled; methods call each other
     *   through it, so it is passed in rather than closed over.
     * @param session - the current session id, or null.
     * @param params - query parameters for one request.
     * @returns the methods this file contributes.
     */
    function selectionMethods(ctx, engine, session, params) {
      return {
        reveal: function (id) {
          shared.selected = id
          shared.focused = id
          shared.edgeFocus = null
          shared.lit = null
          requestViewport(id, 'center')
          publish()
          return engine.source(id)
        },
        select: function (id) {
          // Clicking the already-focused node clears the emphasis, so getting
          // the whole picture back does not require hunting for empty canvas.
          // The gathered neighbours fly home with it.
          if (shared.focused === id) { shared.focused = null; engine.releaseGather(); publish(); return Promise.resolve() }
          // `focused` is set only by a human click. `selected` also moves on its
          // own when a trace loads, and dimming everything else off THAT made
          // 88% of the wires grey the moment the tab opened — an emphasis that
          // is always on is just a washed-out picture.
          return engine.reveal(id)
        },
        blur: function () {
          shared.focused = null
          engine.releaseGather()
          publish()
        },
        /**
         * Light up what a wire belongs to.
         *
         * A dataflow edge is one link in a run: the value came from somewhere
         * and goes on somewhere, and seeing only the two ends of one hop tells
         * you almost nothing. So dataflow lights the whole run it belongs to,
         * following the same relation kind in both directions. A call is not
         * like that — `a` calls `b` and that is the whole fact — so it lights
         * its two ends and stops.
         * @param from - the wire's source anchor id.
         * @param to - the wire's target anchor id.
         * @param type - the relation kind the wire is drawing.
         */
        lightEdge: function (from, to, type) {
          var was = shared.lit
          if (was !== null && was.key === from + '→' + to + ':' + type) {
            shared.lit = null
            publish()
            return
          }
          var nodes = {}
          var wires = {}
          var mark = function (f, t) {
            nodes[f] = true
            nodes[t] = true
            wires[f + '→' + t + ':' + type] = true
          }
          mark(from, to)
          if (type === 'dataflow') {
            // Walk the run, both ways, along this kind only.
            var seen = {}
            var queue = [from, to]
            while (queue.length > 0) {
              var at = queue.shift()
              if (seen[at]) continue
              seen[at] = true
              shared.graph.edges.forEach(function (e) {
                if ((e.types || []).indexOf(type) < 0) return
                if (e.from === at || e.to === at) {
                  mark(e.from, e.to)
                  queue.push(e.from === at ? e.to : e.from)
                }
              })
            }
          }
          shared.lit = { key: from + '→' + to + ':' + type, type: type, nodes: nodes, wires: wires }
          publish()
        },

        /** Light every wire that touches one anchor, so its own are obvious. */
        lightNode: function (id) {
          if (shared.lit !== null && shared.lit.key === id) { shared.lit = null; publish(); return }
          var nodes = {}
          var wires = {}
          nodes[id] = true
          shared.graph.edges.forEach(function (e) {
            if (e.from !== id && e.to !== id) return
            nodes[e.from] = true
            nodes[e.to] = true
            ;(e.types || []).forEach(function (type) {
              wires[e.from + '→' + e.to + ':' + type] = true
            })
          })
          shared.lit = { key: id, type: null, nodes: nodes, wires: wires }
          publish()
        },

        focusEdge: function (from, to, type) {
          var before = shared.edgeFocus
          if (before && before.from === from && before.to === to && before.type === type) {
            shared.edgeFocus = null
          } else {
            shared.edgeFocus = { from: from, to: to, type: type }
            shared.focused = null
            requestViewport(from, 'center')
          }
          publish()
        },
        blurEdge: function () {
          if (shared.edgeFocus === null || shared.edgeFocus === undefined) return
          shared.edgeFocus = null
          shared.lit = null
          publish()
        },
        moveNode: function (id, point, commit) {
          shared.nodePositions[id] = { x: Math.round(point.x), y: Math.round(point.y) }
          // A drag during a gather takes the node out of the gathered column:
          // the overlay re-seats its members on every layout, so without the
          // mark the next pass would put the card straight back and the drag
          // would move nothing — the lock the user reported.
          if (shared.gather !== null && shared.gather !== undefined) {
            if (shared.gather.freed === undefined) shared.gather.freed = {}
            shared.gather.freed[id] = true
          }
          if (commit) saveNodePosition(id, point)
          publish()
        },
      }
    }

    module.exports = { selectionMethods }
    return module.exports
  },
})
