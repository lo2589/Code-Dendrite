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
    function seatChain(graph, body) {
      var seat = function (id, layer, tree, seed) {
        var node = graph.nodes[id]
        if (node === undefined) return
        node.layer = layer
        node.tree = tree
        node.seed = seed === true
      }
      body.trees.forEach(function (tree, rank) {
        tree.nodes.forEach(function (n) { seat(n.id, n.layer, rank, n.seed) })
      })
      // An island is a tree of one. It still needs somewhere to stand,
      // and leaving it without a layer would drop the whole drawing back
      // to file boxes over one unconnected anchor.
      body.islands.forEach(function (n) {
        seat(n.id, 0, body.trees.length, n.seed)
      })
    }

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
         * The local picture in one request: the seeds, everything within `hops`
         * of them both ways, and the trees that grew out of it.
         *
         * Asking hop by hop is what left the graph as a pile of anchors with no
         * idea which layer any of them was on. The layer is the whole point, and
         * only the side holding the edge tables can work it out.
         * @param ids - the anchors to grow from; the session's edits, normally.
         * @param hops - how far each seed reaches in each direction, 1 to 3.
         * @returns the trees, largest-by-edits first, and the lone seeds.
         */
        chain: function (ids, hops) {
          if (ids === undefined || ids.length === 0) {
            shared.chain = { trees: [], islands: [] }
            return Promise.resolve(shared.chain)
          }
          return api('/chain', params({ ids: ids.join(','), hops: String(hops || 1) }))
            .then(function (body) {
              shared.chain = body
              // The stamp this graph was last seated against. Any later answer
              // carrying a different one means the index moved under the drawing.
              if (body.stamp !== undefined) shared.graphStamp = body.stamp
              seatChain(shared.graph, body)
              if (window.__cddLens !== undefined) {
                window.__cddLens.chain = {
                  seeds: body.seeds, hops: body.hops, islands: body.islands.length,
                  trees: body.trees.map(function (t) {
                    return { size: t.size, seeds: t.seeds, layers: t.layers.map(function (l) { return l.length }) }
                  }),
                }
              }
              publish()
              return body
            })
        },

        /**
         * Re-check every node on the graph against the index as it stands NOW.
         *
         * Triggered when any answer carries a stamp different from the one the
         * graph was seated against: anchors the rebuild dropped are removed
         * (not hidden — the code they named is gone), survivors get their
         * counts refreshed, and the graph takes the new stamp. Layers are left
         * alone here; re-seating is chain's job and it runs on the next focus.
         */
        revalidate: function () {
          if (shared.revalidating === true) return Promise.resolve()
          var ids = shared.graph.order.slice()
          if (ids.length === 0) return Promise.resolve()
          shared.revalidating = true
          return apiPost('/verify', params({}), { ids: ids }).then(function (body) {
            body.nodes.forEach(function (n) {
              if (n.missing === true) { removeNode(shared.graph, n.id); return }
              var node = shared.graph.nodes[n.id]
              if (node !== undefined) node.anchor = n
            })
            if (body.stamp !== undefined) shared.graphStamp = body.stamp
            shared.revalidating = false
            publish()
            return body
          }).catch(function (error) {
            shared.revalidating = false
            throw error
          })
        },

        context: function () {
          return api('/context', params()).then(function (body) {
            shared.context = body
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

    module.exports = { fetchMethods, seatChain }
    return module.exports
  },
})
