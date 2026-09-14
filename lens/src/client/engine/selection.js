// dsh-cdd-lens — Engine methods for selection, highlight and dragging.
//
// 这里只改「选中谁、高亮谁、卡片放哪」，不增删任何节点或边——屏幕上有什么
// 只由 /screen 决定（engine/screen.js）。
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
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf

    function selectionMethods(ctx, engine, session, params) {
      return {
        reveal: function (id) {
          shared.selected = id
          shared.focused = id
          shared.lit = null
          var ui = uiOf(shared.graph, id)
          if (ui !== null) ui.viewedAt = shared.turn
          requestViewport(id, 'center')
          publish()
          return engine.source(id)
        },
        select: function (id) {
          // Clicking the already-focused node clears the emphasis, so getting
          // the whole picture back does not require hunting for empty canvas.
          if (shared.focused === id) { shared.focused = null; engine.releaseGather(); publish(); return Promise.resolve() }
          return engine.reveal(id)
        },
        blur: function () {
          shared.focused = null
          engine.releaseGather()
          publish()
        },
        /**
         * 链路聚焦：点一根线，高亮这根线和它前后两个节点。再点一次取消。
         * 只高亮，不改屏幕上的节点集合。
         */
        lightEdge: function (from, to, type) {
          var key = from + '→' + to + ':' + type
          if (shared.lit !== null && shared.lit !== undefined && shared.lit.key === key) {
            shared.lit = null
            publish()
            return
          }
          var nodes = {}
          var wires = {}
          nodes[from] = true
          nodes[to] = true
          wires[key] = true
          shared.lit = { key: key, type: type, nodes: nodes, wires: wires }
          publish()
        },

        /** Light every wire that touches one anchor, so its own are obvious. */
        lightNode: function (id) {
          if (shared.lit !== null && shared.lit !== undefined && shared.lit.key === id) { shared.lit = null; publish(); return }
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

        /** 点线时把线的起点带进视野（已在视野里就不动）。 */
        focusEdge: function (from) {
          requestViewport(from, 'ensure')
          publish()
        },
        blurEdge: function () {
          if (shared.lit === null || shared.lit === undefined) return
          shared.lit = null
          publish()
        },
        moveNode: function (id, point, commit) {
          shared.nodePositions[id] = { x: Math.round(point.x), y: Math.round(point.y) }
          // A drag during a gather takes the node out of the gathered column.
          if (shared.gather !== null && shared.gather !== undefined) {
            if (shared.gather.freed === undefined) shared.gather.freed = {}
            shared.gather.freed[id] = true
          }
          // 拖动中不 publish：卡片和它的线由 view/node.js + view/wireLayer.js 直接挪，
          // 不经过 React、不重排；松手才 publish 一次，重排一次。
          if (commit) { saveNodePosition(id, point); publish() }
        },
      }
    }

    module.exports = { selectionMethods }
    return module.exports
  },
})
