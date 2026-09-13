// dsh-cdd-lens — Gather on selection: when the neighbourhood flies in and back.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/engine/gather',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var shared = __state_store.shared

    // Must match the .cddl-gathering transition in styles/graph.js — the CSS
    // owns how the flight looks, this owns how long the class stays on.
    var GATHER_MS = 260

    /**
     * Turn the transition class on for one flight, then off again.
     *
     * The class used to stay on for the whole gather, which put a 260ms
     * transition under every relayout that happened while it ran — a drag
     * rubber-banded behind the pointer and felt like the node was locked. The
     * class is a flight window now: it opens when the seats change and closes
     * GATHER_MS later, so a settled drawing — gathered or not — never
     * animates. A later stamp re-opens the window and the old timer walks
     * away.
     */
    function stampFlight() {
      var until = Date.now() + GATHER_MS
      shared.gatherAnimUntil = until
      setTimeout(function () {
        if (shared.gatherAnimUntil !== until) return
        shared.gatherAnimUntil = 0
        publish()
      }, GATHER_MS + 40)
    }

    /**
     * The state half of the gather overlay. layout/gather reads
     * shared.gather and moves the nodes; here is only WHEN that flag is set.
     *
     * Selecting a node sets it; the view watches shared.selected and calls in
     * here, so every path that selects — click, search, directory, a trace
     * landing — gathers the same way. If the neighbourhood was never fetched,
     * both directions are pulled in first: animating half the answer would
     * show a caller column and pretend there were no callees.
     */
    function gatherMethods(ctx, engine, session, params) {
      return {
        gather: function (id) {
          var node = shared.graph.nodes[id]
          if (node === undefined) return Promise.resolve()
          if (shared.gather !== null && shared.gather !== undefined && shared.gather.focus === id) {
            return Promise.resolve()
          }
          // freed: ids the user dragged out of the column while it was up.
          // They stay where they were dropped until the gather itself ends.
          shared.gather = { focus: id, freed: {} }
          stampFlight()
          publish()
          var loads = []
          var anchor = node.anchor || {}
          // `auto=true`：拉邻居，但不碰按钮状态。选中一个节点不等于替用户按了
          // 上下键——以前它直接写 node.up/node.down，于是你点中节点时两个按钮
          // 已经是"收起"态，你按的第一下其实是在收起来。
          if (node.up !== true && node.autoUp !== true && anchor.up !== 0) loads.push(engine.expand(id, 'up', true))
          if (node.down !== true && node.autoDown !== true && anchor.down !== 0) loads.push(engine.expand(id, 'down', true))
          if (loads.length === 0) return Promise.resolve()
          return Promise.all(loads).then(function () {
            // The selection may have moved on while the neighbours loaded;
            // only the focus that asked gets to announce their arrival.
            if (shared.gather !== null && shared.gather !== undefined && shared.gather.focus === id) {
              // Late arrivals fly in too.
              stampFlight()
              publish()
            }
          })
        },
        releaseGather: function () {
          var active = shared.gather !== null && shared.gather !== undefined
          var animating = (shared.gatherAnimUntil || 0) > Date.now()
          if (!active && !animating) return
          shared.gather = null
          // One flight window for the trip back.
          stampFlight()
          publish()
        },
      }
    }

    module.exports = { gatherMethods }
    return module.exports
  },
})
