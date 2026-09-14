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
    var uiOf = __graph_model.uiOf
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note
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
          return engine.expand(anchor.id, 'down', null, 'call').then(function () {
            return engine.expand(anchor.id, 'up', null, 'call')
          }).then(function () {
            // 层不再问服务端要了：layout/sugiyama 从图自己算。这里只把视图摆正。
            requestViewport(anchor.id, 'fit')
            publish()
            return engine.source(anchor.id)
          })
        },
        /** Add an anchor beside the current exploration without resetting it. */
        add: function (anchor) {
          // 不重新分层：分层是整图的事，每加一个 anchor 就重排会把用户已经摆好
          // 的图重洗一遍——那正是「加一个却全变了」的来源。下次 focus 或会话
          // ingest 会一起摆；在那之前按当前图重画即可。
          addNode(shared.graph, anchor)
          if (shared.graph.rootId === null) shared.graph.rootId = anchor.id
          shared.selected = anchor.id
          publish()
          return engine.source(anchor.id)
        },
        /**
         * 展开一个关系的一个方向。
         *
         * 按钮是**按关系分开**的：一个 anchor 有几个关系就挂几个按钮，各带各的
         * 数字、各是各的颜色（见规则文档 §2.3）。所以状态也按关系分开存：
         * `ui.open['down:call']`、`ui.open['up:inherit']`，互不影响——点开 call
         * 的 ↓ 不会把 inherit 的 ↓ 也点亮。
         *
         * `auto` 是 gather 在选中节点时替你把邻居拉进来的那条路。它**不许**写
         * `ui.open`——那是按钮的状态。以前它写了，于是你点中一个节点，按钮就已经
         * 是"按下"的样子、标题写着"收起"；你第一次按 ↓ 其实是在把它**收起来**。
         * 自动拉进来的东西仍然要画出来，所以走独立的 `autoDown`/`autoUp` 标记。
         *
         * @param direction - 'up' | 'down'。
         * @param auto - true 表示这次不是用户按的。
         * @param relation - 'call' | 'dataflow' | 'inherit' | 'dispatch' | 'impact'。
         */
        expand: function (id, direction, auto, relation) {
          var rel = relation || 'call'
          var t0 = Date.now()
          var node = shared.graph.nodes[id]
          var ui = uiOf(shared.graph, id)
          note('expand', 'start ' + direction + ':' + rel + ' 节点=' + String(id).split('::').pop()
            + ' 存在=' + (node !== undefined) + ' ui=' + (ui !== null))
          if (node === undefined || ui === null) {
            note('expand', 'ABORT 节点或 ui 不存在 —— 按钮指向了一个已经不在图上的 anchor')
            return Promise.resolve()
          }
          var slot = direction + ':' + rel
          var autoSlot = 'auto' + direction + ':' + rel
          if (!auto) {
            shared.selected = id
            // 展开锁定：只在被展开的节点已经不在视野里时才挪视口。
            requestViewport(id, 'ensure')
          }
          if (ui.open[slot] === true || ui.open[autoSlot] === true) {
            note('expand', 'SKIP 这个方向已经开着（' + slot + '）')
            return Promise.resolve()
          }
          // 桥接点只解释连接，不参与继续展开：它是布局借来的中间点，
          // 不是 agent 打开过的 anchor，展开它等于替用户往下走。
          if (ui.synthetic === true || ui.bridge === true) {
            note('expand', 'SKIP 桥接点不许展开')
            return Promise.resolve()
          }
          ui.loading = slot
          publish()
          note('expand', '请求 /expand ' + direction + ':' + rel)
          return api('/expand', params({ id: id, dir: direction, rel: rel })).then(function (body) {
            note('expand', '返回 peers=' + ((body.peers || []).length) + ' (' + (Date.now() - t0) + 'ms)')
            var fresh = 0, wired = 0
            body.peers.forEach(function (peer) {
              var known = shared.graph.nodes[peer.id] !== undefined
              addNode(shared.graph, peer)
              if (!known) fresh += 1
              var peerUI = uiOf(shared.graph, peer.id)
              if (peerUI !== null) peerUI.explored = true
              var types = [rel]
              if (direction === 'down') addEdge(shared.graph, id, peer.id, types)
              else addEdge(shared.graph, peer.id, id, types)
              wired += 1
            })
            ui.open[auto ? autoSlot : slot] = true
            ui.loading = null
            // 点亮刚展开的这一团：哪些是刚出来的，一眼能看清。
            lightNeighbourhood(id)
            publish()
            note('expand', '完成 新增节点=' + fresh + ' 建边=' + wired
              + ' 图上 nodes=' + Object.keys(shared.graph.nodes).length
              + ' edges=' + shared.graph.edges.length
              + ' 高亮 nodes=' + Object.keys(shared.lit.nodes).length
              + ' wires=' + Object.keys(shared.lit.wires).length
              + ' 共' + (Date.now() - t0) + 'ms')
            // 索引在图画出来之后动过，就先把每个节点对着新表核一遍。
            if (body.stamp !== undefined && shared.graphStamp !== undefined && body.stamp !== shared.graphStamp) {
              return engine.revalidate()
            }
          }).catch(function (error) {
            ui.loading = null
            ui.error = String(error.message)
            publish()
            note('expand', 'FAILED ' + direction + ':' + rel + ' -> ' + String(error && error.message))
          })
        },
        /** 收起一个「方向:关系」，不删缓存的节点和边。 */
        collapse: function (id, direction, relation) {
          var rel = relation || 'call'
          var ui = uiOf(shared.graph, id)
          if (ui === null) return
          shared.selected = id
          ui.open[direction + ':' + rel] = false
          // 用户亲手收起就是真的收起：gather 自动拉进来的那一批也一起收掉，
          // 否则 visible() 还认着 auto 标记，节点赖在图上不走。
          ui.open['auto' + direction + ':' + rel] = false
          if (shared.lit !== null && shared.lit.key === id) shared.lit = null
          requestViewport(id, 'ensure')
          publish()
        },
        /**
         * 链式展开：`a → b → c → d` 一路走，一次请求拿整条链。
         *
         * 服务端 BFS 到底（见 worker 的 walk），回来的是节点表 + 边表，直接并进图。
         * 中间那些层不需要用户再点一次。
         *
         * @param depth - 最多走几跳，1..8。
         */
        walk: function (id, direction, relation, depth) {
          var rel = relation || 'call'
          var ui = uiOf(shared.graph, id)
          if (shared.graph.nodes[id] === undefined || ui === null) return Promise.resolve()
          ui.loading = 'walk:' + direction + ':' + rel
          publish()
          note('walk', '请求 /walk ' + direction + ':' + rel + ' depth=' + (depth || 4))
          return api('/walk', params({
            id: id, dir: direction, rel: rel, depth: String(depth || 4),
          })).then(function (body) {
            body.nodes.forEach(function (n) {
              var known = shared.graph.nodes[n.id] !== undefined
              addNode(shared.graph, n)
              if (!known) {
                var nui = uiOf(shared.graph, n.id)
                if (nui !== null) nui.explored = true
              }
            })
            body.edges.forEach(function (e) { addEdge(shared.graph, e.from, e.to, e.types || [rel]) })
            ui.open[direction + ':' + rel] = true
            ui.loading = null
            lightNeighbourhood(id)
            publish()
            note('walk', '完成 nodes=' + body.nodes.length + ' edges=' + body.edges.length
              + ' 图上 nodes=' + Object.keys(shared.graph.nodes).length)
            return body
          }).catch(function (error) {
            ui.loading = null
            ui.error = String(error.message)
            publish()
          })
        },
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
        pin: function (id) {
          var ui = uiOf(shared.graph, id)
          if (ui === null) return
          ui.pinned = !ui.pinned
          publish()
        },
      }
    }

        /**
     * 点亮「刚展开的这个节点 + 它的直接邻居」。
     *
     * 展开之后图上多了东西，不加高亮就看不清哪一块是刚出来的。这里把这一团
     * （节点 + 它们之间的边）标成 lit，其余变暗——一眼能看出刚展开的是哪一块。
     */
    function lightNeighbourhood(id) {
      var nodes = {}
      var wires = {}
      nodes[id] = true
      shared.graph.edges.forEach(function (e) {
        if (e.from !== id && e.to !== id) return
        nodes[e.from] = true
        nodes[e.to] = true
        ;(e.types || ['call']).forEach(function (type) {
          wires[e.from + '\u2192' + e.to + ':' + type] = true
        })
      })
      shared.lit = { key: id, type: null, nodes: nodes, wires: wires }
    }

    module.exports = { exploreMethods }
    return module.exports
  },
})
