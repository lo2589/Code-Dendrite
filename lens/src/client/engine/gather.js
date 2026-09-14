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
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf

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
     * shared.gather and moves the nodes; here is only when that flag is cleared.
     *
     * 以前这里的 gather() 会替用户自动展开 call 邻居——那是按钮之外往屏幕上加节点，
     * 而且没有任何调用方，已删除。屏幕上有什么只由 /screen 决定。
     */
    function gatherMethods(ctx, engine, session, params) {
      return {
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
