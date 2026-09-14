// dsh-cdd-lens — 前端只做一件事：把状态发给 /screen，按返回的屏幕画。
//
// 状态 shared.view = { tree, rels, pins: [{ id, at, until }], opens: [{ id, rel, dir }] }
//   按钮只改状态，不碰图。
// 屏幕 shared.screen = 后端计算单元（src/compute）的结果；shared.graph 由它原样生成：
//   节点 = screen.nodes ∪ screen.side 的 anchor 记录，边 = screen.edges（一条边一种类型）。
// 前端任何地方都不许再增删节点或边。
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/engine/screen',
  factory: (require) => {
    var module = { exports: {} }
    var __runtime_api = require('dsh-cdd-lens/runtime/api')
    var ROUTE = __runtime_api.ROUTE
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var emptyGraph = __graph_model.emptyGraph
    var addNode = __graph_model.addNode
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var requestViewport = __state_store.requestViewport
    var shared = __state_store.shared

    var RELATIONS = ['call', 'dataflow', 'inherit', 'dispatch', 'impact']
    var TREES = ['degree1', 'degree2', 'edit']

    function defaultView() {
      var rels = {}
      RELATIONS.forEach(function (r) { rels[r] = true })
      return { tree: 'degree2', rels: rels, pins: [], opens: [] }
    }

    function viewOf() {
      if (shared.view === null || shared.view === undefined) shared.view = defaultView()
      return shared.view
    }

    function activePin(id) {
      return viewOf().pins.filter(function (p) { return p.id === id && (p.until === null || p.until === undefined) })[0]
    }

    /** 屏幕 → shared.graph。已画过的位置、类成员的展开状态原样带过去（展开时节点不跳）。 */
    function applyScreen(body) {
      var before = shared.graph || emptyGraph()
      var graph = emptyGraph()
      var side = {}
      body.side.forEach(function (id) { side[id] = true })
      body.nodes.concat(body.side).forEach(function (id) {
        var anchor = body.anchors[id]
        if (anchor === undefined || anchor === null) return
        addNode(graph, anchor)
        var oldUi = before.ui[id]
        if (oldUi !== undefined) {
          graph.ui[id].members = oldUi.members
          graph.ui[id].memberList = oldUi.memberList
        }
        // 位置照旧，但只在「树里 / 旁边」没变时：从旁边进树的节点要按树重新排。
        var place = before.layout[id]
        if (place !== undefined && (place.side === true) === (side[id] === true)) graph.layout[id] = place
      })
      body.edges.forEach(function (e) { graph.edges.push({ from: e.from, to: e.to, types: [e.type] }) })
      graph.rootId = graph.order.length > 0 ? graph.order[0] : null
      shared.graph = graph
      shared.screen = body
      if (body.stamp !== undefined) shared.graphStamp = body.stamp
    }

    /** 高亮一个节点和它在屏幕上的相邻节点（展开后看得出刚出来的是哪一团）。 */
    function lightAround(id) {
      var nodes = {}
      var wires = {}
      nodes[id] = true
      shared.graph.edges.forEach(function (e) {
        if (e.from !== id && e.to !== id) return
        nodes[e.from] = true
        nodes[e.to] = true
        wires[e.from + '→' + e.to + ':' + e.types[0]] = true
      })
      shared.lit = { key: id, type: null, nodes: nodes, wires: wires }
    }

    function screenMethods(ctx, engine, session, params) {
      var inflight = false
      var again = false
      var waiting = []

      var send = function () {
        inflight = true
        again = false
        var url = ROUTE + '/screen?' + new URLSearchParams(params()).toString()
        return fetch(url, {
          method: 'POST', cache: 'no-store',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ state: viewOf() }),
        }).then(function (res) {
          return res.json().then(function (body) {
            if (!res.ok) throw new Error(body.error || ('HTTP ' + res.status))
            return body
          })
        }).then(function (body) {
          applyScreen(body)
          shared.screenError = null
          note('screen', 'tree=' + body.tree + ' 节点=' + body.nodes.length + ' 旁边=' + body.side.length
            + ' 边=' + body.edges.length + ' 违例=' + (body.violations || []).length)
        }).catch(function (error) {
          shared.screenError = String(error && error.message ? error.message : error)
          note('screen', 'FAILED ' + shared.screenError)
        }).then(function () {
          inflight = false
          // 状态在请求途中又变了：再算一次，用最新的状态。回调等最后一次落地才跑。
          if (again) { publish(); return send() }
          waiting.splice(0).forEach(function (fn) { fn() })
          publish()
        })
      }

      return {
        view: viewOf,

        /** 按当前状态重算屏幕。@param then - 屏幕落地后要做的事（可选）。 */
        refresh: function (then) {
          if (typeof then === 'function') waiting.push(then)
          if (inflight) { again = true; return Promise.resolve() }
          return send()
        },

        setTree: function (mode) {
          if (TREES.indexOf(mode) < 0) return Promise.resolve()
          viewOf().tree = mode
          return engine.refresh()
        },

        toggleRelation: function (rel) {
          if (RELATIONS.indexOf(rel) < 0) return Promise.resolve()
          var view = viewOf()
          view.rels[rel] = !view.rels[rel]
          return engine.refresh()
        },

        isOpen: function (id, rel, dir) {
          return viewOf().opens.some(function (o) { return o.id === id && o.rel === rel && o.dir === dir })
        },

        /** ↑N / ↓N：有这条展开就收起，没有就加上。数字、节点、边都由 /screen 给。 */
        toggleOpen: function (id, rel, dir) {
          var view = viewOf()
          var at = -1
          view.opens.forEach(function (o, i) { if (o.id === id && o.rel === rel && o.dir === dir) at = i })
          if (at >= 0) view.opens.splice(at, 1)
          else view.opens.push({ id: id, rel: rel, dir: dir })
          shared.selected = id
          requestViewport(id, 'ensure')
          note('btn', (at >= 0 ? '收起 ' : '展开 ') + rel + dir + ' ' + String(id).split('::').pop())
          return engine.refresh(function () { lightAround(id) })
        },

        isPinned: function (id) {
          return activePin(id) !== undefined
        },

        /** pin：人为固定，计数器不减；再点取消 pin，从这一轮起照常减。 */
        pin: function (id) {
          var view = viewOf()
          var turn = typeof shared.turn === 'number' ? shared.turn : 0
          var active = activePin(id)
          if (active === undefined) view.pins.push({ id: id, at: turn, until: null })
          else if (active.at >= turn) view.pins.splice(view.pins.indexOf(active), 1)
          else active.until = turn
          return engine.refresh()
        },

        /** 搜索、目录点中一个 anchor：相当于 pin 它——开什么树加进什么树，有什么边连什么边。 */
        focus: function (anchor) {
          if (anchor === null || anchor === undefined) return Promise.resolve()
          shared.wantGraph = (shared.wantGraph || 0) + 1
          shared.dockOpen = true
          shared.selected = anchor.id
          requestViewport(anchor.id, 'center')
          var ready = activePin(anchor.id) === undefined ? engine.pin(anchor.id) : engine.refresh()
          return ready.then(function () { return engine.source(anchor.id) })
        },

        /** 清空：去掉所有展开和 pin，回到只有树的屏幕。 */
        resetView: function () {
          var view = viewOf()
          view.opens = []
          view.pins = []
          shared.lit = null
          return engine.refresh()
        },
      }
    }

    module.exports = { TREES, RELATIONS, screenMethods }
    return module.exports
  },
})
