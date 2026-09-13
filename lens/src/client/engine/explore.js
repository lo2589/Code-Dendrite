// dsh-cdd-lens — Engine methods that grow and shrink the graph.
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
    var addEdge = __graph_model.addEdge
    var addNode = __graph_model.addNode
    var emptyGraph = __graph_model.emptyGraph
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var requestViewport = __state_store.requestViewport
    var shared = __state_store.shared

    /**
     * Walking the graph: what is on it and how much of it.
     *
     * @param ctx - the client context the views were mounted with.
     * @param engine - the engine being assembled; methods call each other
     *   through it, so it is passed in rather than closed over.
     * @param session - the current session id, or null.
     * @param params - query parameters for one request.
     * @returns the methods this file contributes.
     */
    function exploreMethods(ctx, engine, session, params) {
      return {
        /**
         * Make an anchor the exploration root, replacing whatever was there.
         *
         * Also asks both views to show the graph: picking a function in the
         * directory is a request to SEE it, and leaving the panel on the
         * directory tab builds the graph where nobody can see it.
         */
        focus: function (anchor) {
          shared.wantGraph = (shared.wantGraph || 0) + 1
          shared.dockOpen = true
          shared.edgeFocus = null
          var graph = emptyGraph()
          addNode(graph, anchor)
          graph.rootId = anchor.id
          shared.graph = graph
          shared.selected = anchor.id
          requestViewport(anchor.id, 'fit')
          publish()
          return engine.expand(anchor.id, 'down').then(function () {
            return engine.expand(anchor.id, 'up')
          }).then(function () {
            // /neighbors says who the neighbours are, not where they stand.
            // The layer is computed host-side over the edge tables (DFS finish
            // order, longest-path relaxed) and only /chain returns it, so a
            // graph built by hand arrived layerless: the flow skin could only
            // pile it into the trailing column and the layered skin never
            // engaged. Seating after the expands covers everything they pulled
            // in and removes nothing — seatChain writes stamps only — and the
            // publish inside chain() re-runs the layout with them. A failed
            // chain leaves the graph exactly as the expands built it.
            return engine.chain([anchor.id], 1).catch(function () { return null })
          }).then(function () {
            requestViewport(anchor.id, 'fit')
            publish()
            return engine.source(anchor.id)
          })
        },
        /** Add an anchor beside the current exploration without resetting it. */
        add: function (anchor) {
          // No chain here on purpose: layering is computed over the seeded
          // neighbourhood, and re-seeding per added anchor would re-layer the
          // graph the user already arranged — every add would reshuffle the
          // picture it was meant to extend. The next focus or session ingest
          // seats everything at once; until then the flow skin parks the added
          // anchor in its trailing column, which is the honest place for it.
          addNode(shared.graph, anchor)
          if (shared.graph.rootId === null) shared.graph.rootId = anchor.id
          shared.selected = anchor.id
          publish()
          return engine.source(anchor.id)
        },
        /**
         * 展开一个方向。
         *
         * `auto` 是 gather 在选中节点时替你把邻居拉进来的那条路。它**不许**写
         * `node.up` / `node.down`——那是按钮的状态。以前它写了，于是你点中一个
         * 节点，两个按钮就已经是"按下"的样子、标题写着"收起"；你第一次按 ↓ 其实
         * 是在把它**收起来**（63 个节点掉到 38 个），数字和看到的东西当然对不上。
         *
         * 自动拉进来的东西仍然要画出来，所以走一个独立的标记 `autoUp`/`autoDown`，
         * 只有 visible() 认它。你亲手按的那一下才把 `up`/`down` 打开，按钮从此
         * 反映的是你自己的动作。
         */
        expand: function (id, direction, auto) {
          var node = shared.graph.nodes[id]
          if (node === undefined) return Promise.resolve()
          if (!auto) {
            shared.selected = id
            requestViewport(id, 'center')
            node['manual' + direction] = false
          }
          if (node[direction] || node['auto' + direction]) return Promise.resolve()
          node.loading = direction
          publish()
          return api('/neighbors', params({ id: id, dir: direction })).then(function (body) {
            body.peers.forEach(function (peer) {
              addNode(shared.graph, peer)
              shared.graph.nodes[peer.id].explored = true
              if (direction === 'down') addEdge(shared.graph, id, peer.id, peer.types)
              else addEdge(shared.graph, peer.id, id, peer.types)
            })
            if (auto) node['auto' + direction] = true
            else node[direction] = true
            node.loading = null
            publish()
            // Expand assigns no layer: a layer is a whole-graph fact and only
            // /chain computes it. What expand DOES owe the drawing is accuracy —
            // if the index moved since this graph was seated, every node on it
            // is re-checked against the rebuilt tables before anything else.
            if (body.stamp !== undefined && shared.graphStamp !== undefined && body.stamp !== shared.graphStamp) {
              return engine.revalidate()
            }
          }).catch(function (error) {
            node.loading = null
            node.error = String(error.message)
            publish()
          })
        },
        /** Hide one explored direction without deleting its cached nodes or edges. */
        collapse: function (id, direction) {
          var node = shared.graph.nodes[id]
          if (node === undefined) return
          shared.selected = id
          node[direction] = false
          // 用户亲手收起就是真的收起：gather 自动拉进来的那一批也一起收掉，
          // 否则 visible() 还认着 autoDown，节点赖在图上不走。
          node['auto' + direction] = false
          node['manual' + direction] = true
          requestViewport(id, 'center')
          publish()
        },
        members: function (id) {
          var node = shared.graph.nodes[id]
          if (node === undefined) return Promise.resolve()
          if (node.members) { node.members = false; publish(); return Promise.resolve() }
          if (node.memberList !== undefined) { node.members = true; publish(); return Promise.resolve() }
          node.loading = 'members'
          publish()
          return api('/members', params({ id: id })).then(function (body) {
            node.memberList = body.members
            node.members = true
            node.loading = null
            publish()
          }).catch(function (error) {
            node.loading = null
            node.error = String(error.message)
            publish()
          })
        },
        pin: function (id) {
          var node = shared.graph.nodes[id]
          if (node === undefined) return
          node.pinned = !node.pinned
          publish()
        },
      }
    }

    module.exports = { exploreMethods }
    return module.exports
  },
})
