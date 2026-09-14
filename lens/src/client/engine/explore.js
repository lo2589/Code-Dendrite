// dsh-cdd-lens — 类成员展开。
//
// 只展开卡片里的成员列表，不增删图上的节点：屏幕上有哪些节点只由 /screen 决定
// （见 engine/screen.js）。以前这里的 focus / expand / collapse / walk 各自往图里
// 加节点加边，是「按钮说 N、画出来不是 N」的来源之一，已全部移走。
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/engine/explore',
  factory: (require) => {
    var module = { exports: {} }
    var __runtime_api = require('dsh-cdd-lens/runtime/api')
    var api = __runtime_api.api
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var shared = __state_store.shared

    /**
     * @param ctx - the client context the views were mounted with.
     * @param engine - the engine being assembled.
     * @param session - the current session id, or null.
     * @param params - query parameters for one request.
     * @returns the methods this file contributes.
     */
    function exploreMethods(ctx, engine, session, params) {
      return {
        members: function (id) {
          var node = shared.graph.nodes[id]
          var ui = uiOf(shared.graph, id)
          if (node === undefined || ui === null) return Promise.resolve()
          if (ui.members) { ui.members = false; publish(); return Promise.resolve() }
          if (ui.memberList !== undefined) { ui.members = true; publish(); return Promise.resolve() }
          ui.loading = 'members'
          publish()
          return api('/members', params({ id: id })).then(function (body) {
            ui.memberList = body.members
            ui.members = true
            ui.loading = null
            publish()
          }).catch(function (error) {
            ui.loading = null
            ui.error = String(error.message)
            publish()
          })
        },
      }
    }

    module.exports = { exploreMethods }
    return module.exports
  },
})
