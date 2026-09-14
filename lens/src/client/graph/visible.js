// dsh-cdd-lens — Which anchors stay on screen: pins and recency.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/graph/visible',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf

    var STICKY_TURNS = 3

    function stickyByRecency(id) {
      var record = shared.trace[id]
      if (record === undefined) return false
      return shared.turn - record.lastTurn < STICKY_TURNS
    }

    /**
     * 这个节点是 edit 过的吗——edit 的一直留着，永远不消失。
     *
     * 两条判据，任一条成立就算：trace 记录说这次会话动过它的代码（state 是
     * edited / working，或有过 verb='edit' 的事件），或者构图时打过 edited 标记。
     */
    function editedNode(graph, id) {
      var record = shared.trace[id]
      if (record !== undefined) {
        if (record.state === 'edited' || record.state === 'working') return true
        if (Array.isArray(record.events)) {
          for (var i = 0; i < record.events.length; i += 1) {
            if (record.events[i].verb === 'edit') return true
          }
        }
      }
      var ui = graph.ui[id]
      return ui !== undefined && ui.edited === true
    }

    /**
     * 看过的节点什么时候撤下。
     *
     * 一个节点被查看之后，只在最近 STICKY_TURNS 轮里还算新鲜；会话往前走一轮它
     * 就更旧一点，走够 STICKY_TURNS 轮就撤下来。**edit 过的例外——一直留着。**
     *
     * 没有这个的话图只进不出：翻过去的东西全赖在屏幕上，越看越满。
     */
    function fadedOut(graph, id) {
      if (editedNode(graph, id)) return false
      var ui = uiOf(graph, id)
      if (ui === null) return true
      if (ui.pinned === true) return false
      if (hasUserOpen(ui)) return false
      if (id === shared.selected) return false
      // 只有**被查看过**的节点才谈得上变旧。刚展开出来的、会话碰过的、
      // 布局借来的桥，都还没有「看过多久」这回事，不许被滤掉——否则一展开
      // 新节点就当场消失。
      var record = shared.trace[id]
      if (record !== undefined) return shared.turn - record.lastTurn >= STICKY_TURNS
      if (typeof ui.viewedAt === 'number') return shared.turn - ui.viewedAt >= STICKY_TURNS
      return false
    }

    function hasUserOpen(ui) {
      var keys = Object.keys(ui.open || {})
      for (var i = 0; i < keys.length; i += 1) {
        if (keys[i].indexOf('auto') === 0) continue
        if (ui.open[keys[i]] === true) return true
      }
      return false
    }

    function userExplicit(graph, id) {
      var ui = uiOf(graph, id)
      if (ui === null) return false
      return ui.pinned === true || hasUserOpen(ui) || id === shared.selected
    }


    /**
     * 当前选的是哪棵树，它只要哪些节点（规则文档 §1.3）。
     *
     *   all      不套树，图里现有的全画
     *   anchor   单个 anchor 周围**直接相连**的邻居，中间不插点
     *   degree1  1 度树 = 直接树：seed 之间直接有边，中间不插点
     *   degree2  2 度树：允许一个中间点把两个 seed 接起来
     *   edit     edit 树：只管这次会话 edit 过的那批 anchor
     *
     * @returns 允许上屏的 id 集合；treeMode 为 all 时返回 null（表示不限制）。
     */
    function treeFilter(graph) {
      var mode = shared.treeMode || 'all'
      if (mode === 'all') return null
      var allow = {}
      var edgeTouches = function (id, keep) {
        allow[id] = true
        graph.edges.forEach(function (e) {
          if (e.from !== id && e.to !== id) return
          allow[e.from] = true
          allow[e.to] = true
          if (keep !== undefined) keep[e.from] = true
        })
      }
      if (mode === 'edit') {
        graph.order.forEach(function (id) {
          if (editedNode(graph, id)) allow[id] = true
        })
        return allow
      }
      if (mode === 'anchor') {
        var focus = shared.focused || shared.selected || graph.rootId
        if (focus !== null && graph.nodes[focus] !== undefined) edgeTouches(focus)
        return allow
      }
      // degree1 / degree2：先把会话碰过的 anchor 当 seed，再按「中间点」放宽。
      //   1 度树：seed 之间的直接边，中间不许插点 —— 所以只有 seed 和直接相连的 seed。
      //   2 度树：再多允许一个中间点（非 seed）把两个 seed 接起来。
      var seed = {}
      graph.order.forEach(function (id) {
        var ui = uiOf(graph, id)
        if (ui === null) return
        if (ui.session || ui.explored || editedNode(graph, id)) seed[id] = true
      })
      Object.keys(seed).forEach(function (id) { allow[id] = true })
      graph.edges.forEach(function (e) {
        var a = seed[e.from] === true, b = seed[e.to] === true
        if (a && b) { allow[e.from] = true; allow[e.to] = true; return }
        if (mode !== 'degree2') return
        // 中间点：一端是 seed，另一端也通向另一个 seed。
        if (a || b) {
          allow[e.from] = true
          allow[e.to] = true
        }
      })
      return allow
    }

    function visible(graph) {
      var roots = []
      var root = function (id, force) {
        roots.push({ id: id, force: force === true })
      }
      if (graph.rootId !== null && graph.nodes[graph.rootId] !== undefined) root(graph.rootId, userExplicit(graph, graph.rootId))
      graph.order.forEach(function (id) {
        var ui = uiOf(graph, id)
        if (ui === null) return
        // 会话碰过的 anchor 是根：agent 读过/改过它，它就该在图上，不需要谁先按
        // 一下展开才出现。以前这一步只认 pin / island / 最近碰过，于是刚 ingest
        // 出来的图只剩一个根节点，连线自然一根都没有。
        if (ui.session || ui.island || stickyByRecency(id) || editedNode(graph, id)) root(id, false)
        if (userExplicit(graph, id)) root(id, true)
      })
      var treeAllow = treeFilter(graph)
      var seen = {}
      var stack = roots.slice()
      while (stack.length > 0) {
        var item = stack.pop()
        var id = item.id
        var force = item.force === true
        if (seen[id]) continue
        if (!force && fadedOut(graph, id)) continue
        if (treeAllow !== null && treeAllow[id] !== true && !force && !userExplicit(graph, id)) continue
        seen[id] = true
        if (graph.nodes[id] === undefined) continue
        var ui = uiOf(graph, id)
        if (ui === null) continue
        graph.edges.forEach(function (e) {
          // 一条边算不算「打开」：这条边的关系类型对应的那个按钮开没开。
          // 展开状态按「方向:关系」存，所以这里要看边自己的类型，不能只看方向——
          // 点开 call 的 ↓ 不该把 inherit 的 ↓ 也点亮。
          //
          // `always` 边连的是会话自己的 anchor，不管有没有人按过都要显示。
          // `auto` 前缀是 gather 选中时自动拉进来的：要画，但不是按钮的状态。
          var types = e.types || ['call']
          if (e.from === id) {
            if (e.always) { stack.push({ id: e.to, force: false }); return }
            var userDown = types.some(function (t) { return ui.open['down:' + t] === true })
            var autoDown = types.some(function (t) { return ui.open['autodown:' + t] === true })
            if (userDown || autoDown) stack.push({ id: e.to, force: force || userDown })
          }
          if (e.to === id) {
            if (e.always) { stack.push({ id: e.from, force: false }); return }
            var userUp = types.some(function (t) { return ui.open['up:' + t] === true })
            var autoUp = types.some(function (t) { return ui.open['autoup:' + t] === true })
            if (userUp || autoUp) stack.push({ id: e.from, force: force || userUp })
          }
        })
      }
      return seen
    }

    module.exports = { STICKY_TURNS, stickyByRecency, editedNode, fadedOut, treeFilter, visible }
    return module.exports
  },
})
