// dsh-cdd-lens — 按钮 → 图。每一步都记带时间的 log（runtime/debug）。
//
// 展开（点 ⬆️ / ⬇️）走直线：
//   ① 读节点存的 anchor 里这个关系这个方向的字段（dataflowup、callers …）拿 id
//   ② POST /anchors 按 id 从新 anchor 表拉回 anchor（和按钮数字同源）
//   ③ 建节点、连边（一条边一种类型），和按钮数字核对
//   ④ 交给布局
// 其余（切树、切关系、pin、收起、会话往前走）改视图状态后调 /screen 整屏重算，
// 后端同样重放这些展开，所以两边给出的节点一致。
// anchor 记录按 id 缓存在 shared.anchorCache：/screen 只发前端还没有的（一个平均 4.7KB）。
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
    var __engine_keep = require('dsh-cdd-lens/engine/keep')
    var savedKeep = __engine_keep.savedKeep
    var keepOf = __engine_keep.keepOf
    var applyKeep = __engine_keep.applyKeep

    var RELATIONS = ['call', 'dataflow', 'inherit', 'dispatch', 'impact']
    var TREES = ['degree1', 'degree2', 'edit']
    // anchor 本来就带的方向；其余方向读补出来的「关系名+up/down」。
    var NATIVE = { 'call:up': 'callers', 'call:down': 'callees', 'inherit:down': 'parent_classes' }

    var shortId = function (id) { return String(id).split('::').pop() }
    var kb = function (bytes) { return (bytes / 1024).toFixed(0) + 'KB' }

    function defaultView() {
      var rels = {}
      RELATIONS.forEach(function (r) { rels[r] = true })
      return { tree: 'degree2', rels: rels, pins: [], opens: [], editKeep: savedKeep('editKeep'), readKeep: savedKeep('readKeep'), openFiles: [] }
    }

    function viewOf() {
      if (shared.view === null || shared.view === undefined) shared.view = defaultView()
      return shared.view
    }

    function cacheOf() {
      if (shared.anchorCache === null || shared.anchorCache === undefined) shared.anchorCache = {}
      return shared.anchorCache
    }

    function activePin(id) {
      return viewOf().pins.filter(function (p) { return p.id === id && (p.until === null || p.until === undefined) })[0]
    }

    function fieldOf(rel, dir) { return NATIVE[rel + ':' + dir] || rel + dir }

    /** 节点存的 anchor 里这个关系这个方向记着的 id：去重、去掉自己。 */
    function idsInField(anchor, rel, dir) {
      var list = Array.isArray(anchor[fieldOf(rel, dir)]) ? anchor[fieldOf(rel, dir)] : []
      var out = []
      list.forEach(function (x) {
        var id = String(x)
        if (id !== anchor.id && out.indexOf(id) < 0) out.push(id)
      })
      return out
    }

    /** POST JSON，返回的 body 上带 __bytes（响应大小，写进 log）。 */
    function postJson(path, query, payload) {
      return fetch(ROUTE + path + '?' + new URLSearchParams(query).toString(), {
        method: 'POST', cache: 'no-store',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
      }).then(function (res) {
        return res.text().then(function (text) {
          if (text === '') throw new Error('HTTP ' + res.status + ' 空响应')
          var body = JSON.parse(text)
          if (!res.ok) throw new Error(body.error || ('HTTP ' + res.status))
          body.__bytes = text.length
          return body
        })
      })
    }

    function setBusy(key, value) {
      shared.busy = shared.busy || {}
      if (value) shared.busy[key] = true
      else delete shared.busy[key]
      publish()
    }

    /** 收下服务端发来的 anchor 记录；索引戳变了先清空缓存。 */
    function remember(anchors, stamp) {
      if (stamp !== undefined && shared.anchorCacheStamp !== stamp) {
        shared.anchorCache = {}
        shared.anchorCacheStamp = stamp
      }
      var cache = cacheOf()
      Object.keys(anchors || {}).forEach(function (id) { cache[id] = anchors[id] })
      return cache
    }

    /** 屏幕 → shared.graph。已画过的位置、类成员展开状态原样带过去（展开时节点不跳）。 */
    function applyScreen(body) {
      var cache = remember(body.anchors, body.stamp)
      var before = shared.graph || emptyGraph()
      var graph = emptyGraph()
      var side = {}
      var missing = 0
      body.side.forEach(function (id) { side[id] = true })
      body.nodes.concat(body.side).forEach(function (id) {
        var anchor = cache[id]
        if (anchor === undefined || anchor === null) { missing += 1; return }
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
      if (missing > 0) note('error', '✗ 屏幕上有 ' + missing + ' 个节点缓存里没有 anchor 记录')
      body.edges.forEach(function (e) { graph.edges.push({ from: e.from, to: e.to, types: [e.type] }) })
      graph.rootId = graph.order.length > 0 ? graph.order[0] : null
      shared.graph = graph
      shared.screen = body
      if (body.stamp !== undefined) shared.graphStamp = body.stamp
    }

    /** 展开拉回来的节点和边，并进当前屏幕（布局只画屏幕上的）。 */
    function mergeIntoScreen(peersIn, edgesIn, buttonsIn) {
      var screen = shared.screen
      if (screen === null || screen === undefined) {
        screen = shared.screen = { nodes: [], side: [], edges: [], buttons: {}, anchors: {}, pinned: [], treeTotals: {} }
      }
      var rels = viewOf().rels
      peersIn.forEach(function (id) {
        var s = screen.side.indexOf(id)
        if (s >= 0) screen.side.splice(s, 1)
        if (screen.nodes.indexOf(id) < 0) screen.nodes.push(id)
        var b = {}
        Object.keys(buttonsIn[id] || {}).forEach(function (k) {
          if (rels[k.replace(/(up|down)$/, '')]) b[k] = buttonsIn[id][k]
        })
        if (screen.buttons[id] === undefined) screen.buttons[id] = b
      })
      edgesIn.forEach(function (e) { screen.edges.push({ from: e.from, to: e.to, type: e.types[0] }) })
      if (shared.graph.rootId === null && shared.graph.order.length > 0) shared.graph.rootId = shared.graph.order[0]
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
        var view = viewOf()
        var t0 = Date.now()
        var known = shared.anchorCacheStamp === undefined ? [] : Object.keys(cacheOf())
        note('screen', '→ /screen 树=' + view.tree + ' 展开=' + view.opens.length + ' pin=' + view.pins.filter(function (p) { return p.until === null || p.until === undefined }).length
          + ' 关系=' + RELATIONS.filter(function (r) { return view.rels[r] }).join(',') + ' · edit 保留 ' + keepOf(view, 'editKeep') + ' 轮 · read 保留 ' + keepOf(view, 'readKeep') + ' 轮 · 已缓存 anchor ' + known.length)
        return postJson('/screen', params(), { state: view, known: known, knownStamp: shared.anchorCacheStamp === undefined ? null : shared.anchorCacheStamp }).then(function (body) {
          if (!Array.isArray(body.nodes)) {
            note('screen', '← 没有仓库：' + (body.reason || 'no-root') + ' · 屏幕不变 · ' + (Date.now() - t0) + 'ms')
            return
          }
          var fresh = Object.keys(body.anchors || {}).length
          applyScreen(body)
          shared.screenError = null
          note('screen', '← 节点 ' + body.nodes.length + ' · 旁边 ' + body.side.length + ' · 边 ' + body.edges.length
            + ' · seed ' + body.seeds + ' · 违例 ' + (body.violations || []).length
            + ' · 响应 ' + kb(body.__bytes) + '（新发 anchor ' + fresh + ' 个）· ' + (Date.now() - t0) + 'ms'
            + (body.timing ? '（读会话 ' + body.timing.log + 'ms · ' + body.timing.source + ' · 计算 ' + body.timing.compute + 'ms）' : '')
            + (body.reason ? ' · ' + body.reason : ''))
          ;(body.expansions || []).forEach(function (x) {
            if (x.skipped) note('screen', '  展开被跳过 ' + shortId(x.id) + ' ' + x.rel + x.dir + '：' + (x.skipped === 'relation-off' ? '这个关系没开' : '节点不在屏幕上'))
          })
          ;(body.violations || []).slice(0, 3).forEach(function (v) { note('error', '违例 ' + v) })
        }).catch(function (error) {
          shared.screenError = String(error && error.message ? error.message : error)
          note('error', '✗ /screen 失败：' + shared.screenError)
        }).then(function () {
          inflight = false
          // 状态在请求途中又变了：再算一次，用最新的状态。回调等最后一次落地才跑。
          if (again) { publish(); return send() }
          waiting.splice(0).forEach(function (fn) { fn() })
          publish()
        })
      }

      /** ①②③④：读字段 → 拉 anchor → 建节点连边 → 交给布局。 */
      var expandDirect = function (id, rel, dir) {
        var t0 = Date.now()
        var key = id + '|' + rel + dir
        var anchor = shared.graph.nodes[id]
        if (anchor === undefined) {
          note('error', '✗ ' + shortId(id) + ' 不在图上，没法展开')
          return Promise.resolve()
        }
        var field = fieldOf(rel, dir)
        var ids = idsInField(anchor, rel, dir)
        var button = ((shared.screen && shared.screen.buttons && shared.screen.buttons[id]) || {})[rel + dir] || 0
        note(ids.length === button ? 'expand' : 'error', '① 读 ' + shortId(id) + '.' + field + ' → ' + ids.length + ' 个 anchor id'
          + (ids.length === button ? '（= 按钮数字）' : '（✗ 按钮数字是 ' + button + '）'))
        setBusy(key, true)
        return postJson('/anchors', params(), { ids: ids }).then(function (body) {
          var got = Object.keys(body.anchors || {})
          var missing = body.missing || []
          remember(body.anchors, body.stamp)
          note('expand', '② /anchors 拉回 ' + got.length + ' 个 anchor，拿不到 ' + missing.length + ' 个'
            + (missing.length > 0 ? '（' + missing.slice(0, 4).map(shortId).join(', ') + (missing.length > 4 ? ' …' : '') + '）' : '')
            + ' · ' + kb(body.__bytes) + ' · ' + (Date.now() - t0) + 'ms')
          var fresh = 0
          var linked = 0
          var added = []
          got.forEach(function (peer) {
            if (shared.graph.nodes[peer] === undefined) { addNode(shared.graph, body.anchors[peer]); fresh += 1 } else linked += 1
            var from = dir === 'down' ? id : peer
            var to = dir === 'down' ? peer : id
            var exists = shared.graph.edges.some(function (e) { return e.from === from && e.to === to && e.types[0] === rel })
            if (!exists) {
              var edge = { from: from, to: to, types: [rel] }
              shared.graph.edges.push(edge)
              added.push(edge)
            }
          })
          mergeIntoScreen(got, added, body.buttons || {})
          note(got.length === button ? 'expand' : 'error', '③ 新建节点 ' + fresh + ' · 连已有 ' + linked + ' · 新建边 ' + added.length
            + (got.length === button ? ' · 和按钮数字一致' : ' · ✗ 按钮说 ' + button + '，实际 ' + got.length))
          lightAround(id)
          setBusy(key, false)
          note('expand', '④ 交给布局：图上 ' + shared.graph.order.length + ' 个节点、' + shared.graph.edges.length + ' 条边 · 共 ' + (Date.now() - t0) + 'ms')
        }).catch(function (error) {
          setBusy(key, false)
          note('error', '✗ 展开 ' + shortId(id) + ' ' + rel + dir + ' 失败：' + String(error && error.message ? error.message : error))
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
          note('btn', '按下 切树 → ' + mode)
          viewOf().tree = mode
          return engine.refresh()
        },

        toggleRelation: function (rel) {
          if (RELATIONS.indexOf(rel) < 0) return Promise.resolve()
          var view = viewOf()
          view.rels[rel] = !view.rels[rel]
          note('btn', '按下 关系 ' + rel + ' → ' + (view.rels[rel] ? '开' : '关'))
          return engine.refresh()
        },

        /** edit / read 保留几轮（见 engine/keep.js）。@param field - 'editKeep' | 'readKeep'。 */
        setKeep: function (field, value) {
          return applyKeep(viewOf(), field, value) ? engine.refresh() : Promise.resolve()
        },

        /** 文件框 + / −：点开看这个文件的全部节点，再点折叠回只留层级高的和 pin 的。@param key - 'tree:文件' 或 'side:文件'。 */
        toggleFile: function (key) {
          var view = viewOf()
          view.openFiles = view.openFiles || []
          var at = view.openFiles.indexOf(key)
          if (at >= 0) view.openFiles.splice(at, 1)
          else view.openFiles.push(key)
          note('btn', '按下 ' + (at >= 0 ? '− 折叠文件框 ' : '+ 展开文件框 ') + String(key).split('/').pop())
          return engine.refresh()
        },

        isOpen: function (id, rel, dir) {
          return viewOf().opens.some(function (o) { return o.id === id && o.rel === rel && o.dir === dir })
        },

        isBusy: function (id, rel, dir) {
          return shared.busy !== undefined && shared.busy !== null && shared.busy[id + '|' + rel + dir] === true
        },

        /** ⬆️ / ⬇️：没开就展开（直线拉 anchor），开着就收起（整屏重算）。 */
        toggleOpen: function (id, rel, dir) {
          var view = viewOf()
          var at = -1
          view.opens.forEach(function (o, i) { if (o.id === id && o.rel === rel && o.dir === dir) at = i })
          shared.selected = id
          requestViewport(id, 'ensure')
          if (at >= 0) {
            view.opens.splice(at, 1)
            note('btn', '按下 收起 ' + (dir === 'up' ? '⬆️' : '⬇️') + rel + ' ' + shortId(id))
            return engine.refresh(function () {
              note('expand', '收起完成：图上 ' + shared.graph.order.length + ' 个节点、' + shared.graph.edges.length + ' 条边')
            })
          }
          view.opens.push({ id: id, rel: rel, dir: dir })
          note('btn', '按下 展开 ' + (dir === 'up' ? '⬆️' : '⬇️') + rel + ' ' + shortId(id))
          return expandDirect(id, rel, dir)
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
          note('btn', '按下 ' + (active === undefined ? 'pin ' : '取消 pin ') + shortId(id) + '（第 ' + turn + ' 轮）')
          return engine.refresh()
        },

        /** 搜索、目录点中一个 anchor：相当于 pin 它——开什么树加进什么树，有什么边连什么边。 */
        focus: function (anchor) {
          if (anchor === null || anchor === undefined) return Promise.resolve()
          note('btn', '选中搜索结果 ' + shortId(anchor.id) + ' → pin')
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
          note('btn', '按下 清空（去掉 ' + view.opens.length + ' 个展开、' + view.pins.length + ' 个 pin）')
          view.opens = []
          view.pins = []
          view.openFiles = []
          shared.lit = null
          return engine.refresh()
        },
      }
    }

    module.exports = { TREES, RELATIONS, screenMethods }
    return module.exports
  },
})
