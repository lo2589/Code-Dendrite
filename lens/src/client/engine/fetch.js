// dsh-cdd-lens — Engine methods that fetch from the host half.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/engine/fetch',
  factory: (require) => {
    var module = { exports: {} }
    var __runtime_api = require('dsh-cdd-lens/runtime/api')
    var api = __runtime_api.api
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var shared = __state_store.shared
    var __state_persist = require('dsh-cdd-lens/state/persist')
    var ensureNodePositions = __state_persist.ensureNodePositions
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var removeNode = __graph_model.removeNode
    var __runtime_api2 = require('dsh-cdd-lens/runtime/api')
    var apiPost = __runtime_api2.apiPost

    /**
     * The layer belongs on the node, so whatever draws the graph can ask a
     * node where it goes instead of working it out again. This only ever
     * writes stamps — nothing already in the graph is removed — so it is safe
     * to land on top of a graph the user has already expanded by hand, which
     * is exactly what explore.focus does with it.
     */
    /**
     * Everything that asks the host for something.
     *
     * @param ctx - the client context the views were mounted with.
     * @param engine - the engine being assembled; methods call each other
     *   through it, so it is passed in rather than closed over.
     * @param session - the current session id, or null.
     * @param params - query parameters for one request.
     * @returns the methods this file contributes.
     */
    function fetchMethods(ctx, engine, session, params) {
      return {
        /**
         * 索引在图画出来之后重建过：屏幕整份重算（/screen 用新索引算节点、边、按钮）。
         * 不在前端逐个删改节点——屏幕上有什么只由计算单元决定。
         */
        revalidate: function () {
          return engine.refresh()
        },

        context: function () {
          // 还没有会话、也没有仓库：不问。问了 host 只能猜一个仓库，猜错的代价是把别的项目整份索引读进内存。
          var sid = session()
          if ((sid === undefined || sid === null) && shared.root === undefined) {
            require('dsh-cdd-lens/runtime/debug').note('req', '/context 跳过：还没有会话')
            return Promise.resolve(undefined)
          }
          return api('/context', params()).then(function (body) {
            shared.context = body
            // host 答 no-session 时 root 是 null；不能记下来，否则每个请求都带 root=null。
            if (typeof body.root !== 'string') {
              require('dsh-cdd-lens/runtime/debug').note('res', '/context 没有仓库：' + (body.reason || 'no-root'))
              publish()
              return body
            }
            shared.root = body.root
            // First contact teaches the graph its stamp; a later context that
            // disagrees with it means the index was rebuilt behind the page.
            var stamp = body.stats === undefined ? undefined : body.stats.stamp
            if (stamp !== undefined && shared.graphStamp === undefined) shared.graphStamp = stamp
            ensureNodePositions(body.root)
            publish()
            if (stamp !== undefined && shared.graphStamp !== stamp && shared.graph.order.length > 0) {
              return engine.revalidate().then(function () { return body })
            }
            return body
          })
        },
        outline: function () {
          return api('/outline', params()).then(function (body) {
            shared.outline = body.dirs
            publish()
            return body
          })
        },
        fileSymbols: function (file) {
          return api('/file', params({ file: file })).then(function (body) {
            shared.fileCache = shared.fileCache || {}
            shared.fileCache[file] = body.symbols
            publish()
            return body.symbols
          })
        },
        anchor: function (id) {
          return api('/anchor', params({ id: id })).then(function (body) { return body.anchor })
        },
        source: function (id) {
          shared.sourceCache = shared.sourceCache || {}
          if (shared.sourceCache[id] !== undefined) { publish(); return Promise.resolve() }
          return api('/source', params({ id: id, pad: 0 })).then(function (body) {
            shared.sourceCache[id] = body.source
            publish()
          }).catch(function () { /* an unreadable file simply shows no source */ })
        },
        search: function (q) {
          if (q.length === 0) { shared.hits = null; publish(); return Promise.resolve() }
          return api('/search', params({ q: q, limit: 24 })).then(function (body) {
            shared.hits = body.hits
            publish()
          })
        },
        reindexStatus: function () {
          return api('/reindex-status', params()).then(function (body) {
            var wasRunning = shared.reindexing === true
            shared.reindexing = body.running
            shared.reindexTail = body.tail
            shared.reindexError = body.error
            publish()
            // The index landing is the interesting edge: reload context and the
            // session marks so the graph appears without anyone reloading a page.
            if ((wasRunning && !body.running) || (body.indexed && (shared.context === undefined || !shared.context.indexed))) {
              return engine.context()
            }
          }).catch(function () { /* a poll that fails is retried by the next tick */ })
        },
        reindex: function () {
          return api('/reindex', params()).then(function (body) {
            shared.reindexing = body.started === true
            shared.reindexError = body.error
            publish()
            var poll = function () {
              engine.reindexStatus().then(function () {
                if (shared.reindexing) setTimeout(poll, 700)
              })
            }
            setTimeout(poll, 700)
          })
        },
      }
    }

    module.exports = { fetchMethods }
    return module.exports
  },
})
