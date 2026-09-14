// dsh-cdd-lens — browser half. GENERATED, DO NOT EDIT.
//
// Built from src/client/ by scripts/build.js. Edit the parts, not this file.
// Written in the shape tsdown emits (`__ModuleLoader__.load` + a CJS body +
// the loader's `require`), so a generated bundle drops in on top.
//
// build: V1_36_SCREEN_COMPUTE_UNIT_001
// parts: 44

// dsh-cdd-lens — Build stamp, plugin route, and the one fetch wrapper.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/runtime/api',
  factory: (require) => {
    var module = { exports: {} }

    // Inlined from build.json. The host greps this file for the stamp it read
    // from disk, so a drift shows up in /health as clientBundleMatchesBuild:false
    // rather than as mysterious behaviour.
    var BUILD = 'V1_36_SCREEN_COMPUTE_UNIT_001'
    var ROUTE = '/plugins/cdd-lens'
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note

    // ---- wire -------------------------------------------------------------

    function api(path, params) {
      var url = ROUTE + path + '?' + new URLSearchParams(params || {}).toString()
      note('req', path + ' ' + (new URLSearchParams(params || {})).toString())
      return fetch(url, { cache: 'no-store' }).then(function (res) {
        if (!res.ok) {
          note('error', path + ' -> HTTP ' + res.status)
          return res.json().catch(function () { return {} }).then(function (body) {
            throw new Error(body.error || ('HTTP ' + res.status))
          })
        }
        return res.json().then(function (body) {
          note('res', path + ' -> 200 ' + summarize(path, body))
          return body
        })
      })
    }

    /** 一行摘要：这次返回了什么，数量对不对。 */
    function summarize(path, body) {
      if (body === null || body === undefined) return '(空)'
      if (path === '/expand') return 'count=' + body.count + ' peers=' + ((body.peers || []).length)
      if (path === '/walk') return 'nodes=' + ((body.nodes || []).length) + ' edges=' + ((body.edges || []).length)
      if (path === '/resolve') return 'results=' + ((body.results || []).length)
      if (path === '/context') return 'anchors=' + ((body.stats || {}).anchors)
      if (Array.isArray(body.hits)) return 'hits=' + body.hits.length
      var keys = Object.keys(body)
      return keys.slice(0, 4).join(',')
    }

    /** Same wrapper with a JSON body, for payloads too long for a query string. */
    function apiPost(path, params, payload) {
      var url = ROUTE + path + '?' + new URLSearchParams(params || {}).toString()
      note('req', 'POST ' + path + ' ids=' + ((payload && payload.ids) ? payload.ids.length : 0))
      return fetch(url, {
        method: 'POST', cache: 'no-store',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload || {}),
      }).then(function (res) {
        if (!res.ok) return res.json().catch(function () { return {} }).then(function (body) {
          throw new Error(body.error || ('HTTP ' + res.status))
        })
        return res.json()
      })
    }

    module.exports = { BUILD, ROUTE, api, apiPost }
    return module.exports
  },
})

// dsh-cdd-lens — Debug 模式。
//
// 图上点不出来的时候，光看画面分不清是哪一层坏的：请求没发出去、服务端返回空、
// 布局收到 0 个节点、还是渲染时抛错——四种在屏幕上都长成一样（一片空白）。
//
// 这个模块把这三层的事实都记下来，并显示在图面板顶部的一条窄栏里：
//
//   请求   最近几次 /expand /walk /resolve 的路径、HTTP 码、返回数量
//   图的形状  ingest 之后有多少节点、多少边；布局收到多少、画出多少
//   错误   任何一层抛出的原始消息（截断到一行）
//
// 开关：`?cddl-debug=1` 或 localStorage 里的 `cdd-lens.debug=1`。
// 关掉时所有记录都是空操作，不影响正常路径。
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/runtime/debug',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement

    var KEY = 'cdd-lens.debug.v1'
    var MAX = 24

    /** 开关状态：URL 参数优先，其次 localStorage，默认关。 */
    function debugEnabled() {
      try {
        if (typeof window !== 'undefined' && window.location) {
          var q = new URLSearchParams(window.location.search)
          if (q.get('cddl-debug') === '1') return true
          if (q.get('cddl-debug') === '0') return false
        }
        var stored = window.localStorage.getItem(KEY)
        if (stored === '1') return true
        if (stored === '0') return false
      } catch (e) { /* 隐私模式下 localStorage 会抛，按关闭处理 */ }
      return false
    }

    var on = debugEnabled()
    var events = []
    var facts = {}

    /**
     * 记一条事件。任何一层都可以调，关掉时是空操作。
     *
     * @param kind - 'req' | 'res' | 'graph' | 'layout' | 'error'。
     * @param text - 一行描述。
     */
    function note(kind, text) {
      if (!on) return
      events.push({ at: new Date().toLocaleTimeString(), kind: kind, text: String(text).slice(0, 220) })
      if (events.length > MAX) events.splice(0, events.length - MAX)
      // 也挂到 window 上：控制台里 `__cddLens.debug()` 直接能看。
      try {
        window.__cddLens = window.__cddLens || {}
        window.__cddLens.debug = debugSnapshot
      } catch (e) { /* 没有 window 就算了 */ }
    }

    /** 覆盖式的事实：节点数、边数这些「当前值」。 */
    function fact(name, value) {
      if (!on) return
      facts[name] = value
    }

    function snapshot() {
      return { enabled: on, facts: facts, events: events.slice() }
    }

    /** 调试窄栏。关掉调试时不渲染任何东西。 */
    function DebugBar(props) {
      if (!on) return null
      var lines = []
      Object.keys(facts).forEach(function (k) { lines.push(k + '=' + facts[k]) })
      var shown = events.slice(-6)
      return h('div', {
        className: 'cddl-debugbar',
        style: {
          fontSize: '10px', lineHeight: '1.45', padding: '4px 8px',
          borderBottom: '1px solid var(--dsw-alias-border-l2)',
          background: 'var(--dsw-alias-bg-layer-3)',
          color: 'var(--dsw-alias-label-secondary)',
          fontFamily: 'var(--ds-font-family-code,monospace)',
          whiteSpace: 'pre-wrap', maxHeight: '30vh', overflow: 'auto',
        },
      }, [
        h('div', { key: 'f', style: { fontWeight: 700, color: 'var(--dsw-alias-label-primary)' } },
          'CDD debug ' + (props.build || '') + '  ' + lines.join('  ')),
        h('div', { key: 'e' }, shown.map(function (e, i) {
          return h('div', { key: i }, e.at + ' [' + e.kind + '] ' + e.text)
        })),
      ])
    }

    module.exports = { debugEnabled, note, fact, snapshot, DebugBar, isOn: function () { return on } }
    return module.exports
  },
})

// dsh-cdd-lens — The accumulating node/edge store: pure graph operations.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/graph/model',
  factory: (require) => {
    var module = { exports: {} }

    // ---- graph store ------------------------------------------------------
    //
    // A node IS an anchor. `graph.nodes[id]` holds the record that came out of
    // `.codedendrite/anchors.json` — `symbol`, `file`, `line_start`, `callers`,
    // `mro`, `own_methods`, the lot — and nothing else. There is no wrapper and
    // no `node.anchor` hop: everything that wants to know about the code reads
    // the anchor, and anything the drawing needs about a node is either derived
    // from that record or kept in one of the side tables below.
    //
    // Two side tables, both keyed by anchor id, both outside the record:
    //
    //   graph.ui     —按钮和交互状态（谁按开了 up、谁在 loading、谁被 pin）。
    //                  这些是「你看它的方式」，不是「它是什么」，所以不写进
    //                  anchor，重画一次不会污染索引来的数据。
    //   graph.layout — 布局算出来的坐标和端口。布局产物，同样不写回 anchor。
    //
    // Anything typed into .codedendrite stays there; anything we invent lives
    // beside it and can be thrown away and recomputed.

    function emptyGraph() {
      return { nodes: {}, ui: {}, layout: {}, order: [], edges: [], rootId: null }
    }

    /** 每个 anchor 的交互状态。节点进图时建一次，之后只改字段。 */
    function emptyUI() {
      return {
        // 展开状态按「方向:关系」存：一个 anchor 有几个关系就挂几个按钮，各开各的。
        //   ui.open['down:call']     点开了 call 的下游
        //   ui.open['up:inherit']    点开了 inherit 的上游
        //   auto 前缀的是 gather 自动拉进来的，不算用户按过
        open: {},
        members: false, memberList: undefined,
        pinned: false, loading: null, error: null,
        explored: false, island: false, session: false,
        bridge: false, synthetic: false,
        // 这个节点最近一次被查看是哪一轮。看过的节点按轮次变旧、过期撤下；
        // edit 过的节点不看它，一直留着（判据在 graph/visible.fadedOut）。
        viewedAt: undefined,
        // 构图时就明确知道它被 edit 过（trace 还没到时用）。
        edited: false,
      }
    }

    /** anchor 记录的第一次出现，补上 id（索引里本来就带，防外部传裸记录）。 */
    function anchorRecord(anchor) {
      return anchor
    }

    function addNode(graph, anchor) {
      if (anchor === undefined || anchor === null || anchor.id === undefined) return false
      if (graph.nodes[anchor.id] !== undefined) {
        // 重新索引会换掉记录：整条替换，不留旧字段。
        graph.nodes[anchor.id] = anchorRecord(anchor)
        return false
      }
      graph.nodes[anchor.id] = anchorRecord(anchor)
      graph.ui[anchor.id] = emptyUI()
      graph.order.push(anchor.id)
      return true
    }

    /** 交互状态的读写口。没有这条 node 时返回 null，调用方不必自己判空。 */
    function uiOf(graph, id) {
      var entry = graph.ui[id]
      return entry === undefined ? null : entry
    }

    /** 布局产物（x/y/w/h/layer/ports）。算子只读它，不改 anchor。 */
    function placeOf(graph, id) {
      var entry = graph.layout[id]
      return entry === undefined ? null : entry
    }

    function setPlace(graph, id, place) {
      graph.layout[id] = place
      return place
    }

    /** 图上现有的 anchor id，按进入顺序。 */
    function nodeIds(graph) {
      return graph.order
    }

    function addEdge(graph, from, to, types) {
      for (var i = 0; i < graph.edges.length; i++) {
        if (graph.edges[i].from === from && graph.edges[i].to === to) {
          var found = graph.edges[i]
          ;(types || ['call']).forEach(function (type) {
            if (found.types.indexOf(type) < 0) found.types.push(type)
          })
          return found
        }
      }
      var edge = { from: from, to: to, types: types || ['call'] }
      graph.edges.push(edge)
      return edge
    }

    /**
     * Drop a node and every edge touching it. Revalidation is the only caller:
     * an anchor the rebuilt index no longer holds is not a node that went
     * invisible, it is a node that does not exist, and hiding it would keep
     * answering questions about code that is gone.
     */
    function removeNode(graph, id) {
      if (graph.nodes[id] === undefined) return false
      delete graph.nodes[id]
      delete graph.ui[id]
      delete graph.layout[id]
      graph.order = graph.order.filter(function (x) { return x !== id })
      graph.edges = graph.edges.filter(function (e) { return e.from !== id && e.to !== id })
      if (graph.rootId === id) graph.rootId = graph.order.length > 0 ? graph.order[0] : null
      return true
    }

    /** Ids reachable from the roots along currently expanded edges. */
    /**
     * How long an anchor the agent touched holds itself on the graph.
     *
     * Three turns after it was last mentioned. `node.session` alone kept every
     * anchor a session ever opened as a permanent root, so a long conversation
     * only ever accumulated — collapsing a branch freed nothing. Three turns is
     * long enough that the thing just being worked on never vanishes, and an
     * explicit pin overrides it and never expires.
     */

    module.exports = {
      emptyGraph, emptyUI, addNode, addEdge, removeNode,
      uiOf, placeOf, setPlace, nodeIds,
    }
    return module.exports
  },
})

// dsh-cdd-lens — Shared exploration state and the React bindings over it.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/state/store',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var emptyGraph = __graph_model.emptyGraph

    // ---- shared session store --------------------------------------------
    //
    // One hook drives both views, so switching between the floating panel and
    // the spread-out tab keeps the same exploration instead of resetting it.

    var shared = {
      graph: emptyGraph(),
      trace: {},
      turn: 0,
      selected: null,
      focused: null,
      edgeFocus: null,
      // 看哪棵树（规则文档 §1.3）：all 不套树，其余是四棵树之一。
      // 选择器在工具栏；这个值决定布局把哪些节点放上屏幕。
      treeMode: 'all',
      // 画线模式。默认 'all' 画全部关系边——默认走「主干」的话，没选中任何节点时
      // 画面上可能一根线都没有，看起来就是「图坏了」。工具栏上仍可切回主干。
      wireMode: 'all',
      // What a click on a wire lit up: the anchors and the wires that
      // belong to the same run of relations. A highlight, not a layout —
      // nothing moves, so you can see what you clicked in the place you
      // clicked it.
      lit: null,
      nodePositions: {},
      positionRoot: null,
      revision: 0,
      listeners: [],
    }

    var DOCK_OPEN_KEY = 'cdd-lens.dock-open.v1'
    var dockOpenValue = true

    /**
     * Whether the floating panel was open last time, read back on reload.
     *
     * The panel lives only in memory otherwise, and it is this plugin's whole
     * surface: every reload put it back to closed, and the one tab that can
     * reopen it is registered into a session-scoped slot, which is not declared
     * at every moment the page is alive. A reader who closed the panel then had
     * nothing left to click. An unpersisted `false` is indistinguishable from a
     * panel that was never there, so open is the default too.
     */
    function loadDockOpen() {
      try {
        var stored = window.localStorage.getItem(DOCK_OPEN_KEY)
        if (stored === '1') return true
        if (stored === '0') return false
      } catch (e) { /* browser persistence is optional */ }
      return true
    }

    dockOpenValue = loadDockOpen()

    // Every writer assigns `shared.dockOpen` directly, so the persistence lives
    // on the property itself: one accessor covers all of them, and a future
    // writer cannot forget the localStorage call the way a setter helper would.
    Object.defineProperty(shared, 'dockOpen', {
      enumerable: true,
      get: function () { return dockOpenValue },
      set: function (value) {
        dockOpenValue = value === true
        try {
          window.localStorage.setItem(DOCK_OPEN_KEY, dockOpenValue ? '1' : '0')
        } catch (e) { /* browser persistence is optional */ }
      },
    })

    function publish() {
      shared.revision = (shared.revision || 0) + 1
      shared.listeners.forEach(function (fn) { fn() })
    }

    /**
     * 请求把视口移到某个节点上。
     *
     * mode:
     *   'center'  直接居中（用户主动点选、搜索跳转）
     *   'fit'     按可读比例居中（换图、会话 ingest）
     *   'ensure'  **只在它不在视野里时才动**。展开用这个：点一下展开，
     *             节点就在你眼前，视口却跳一下，看着就是「树乱跳」。
     *             已经在视野里就什么都不做，你看到的画面一个像素都不动。
     */
    function requestViewport(id, mode) {
      shared.viewportRequest = {
        id: id,
        mode: mode || 'center',
        seq: ((shared.viewportRequest || {}).seq || 0) + 1,
      }
    }

    function useShared() {
      var tick = useState(0)
      var setTick = tick[1]
      useEffect(function () {
        var fn = function () { setTick(function (n) { return n + 1 }) }
        shared.listeners.push(fn)
        return function () {
          var i = shared.listeners.indexOf(fn)
          if (i >= 0) shared.listeners.splice(i, 1)
        }
      }, [])
      return shared
    }

    /**
     * How far the floating panel must sit from the window's right edge.
     *
     * `shell.overlay` spans the whole frame, so `right: 16px` is the WINDOW's
     * right edge — which is underneath the details column whenever the layout
     * has it open, and the panel silently disappears behind it. AppFrame writes
     * the solved track widths as an inline `grid-template-columns` on the frame
     * ("280px minmax(0, 1fr) 360px"), so the third track is the details width,
     * and reading it is the only thing that stays correct while the column is
     * dragged, auto-shrunk, or closed to zero.
     */
    function useRightInset(ref) {
      var inset = useState(16)
      useEffect(function () {
        var measure = function () {
          // Two different things can own the right edge, and both have to be
          // stepped around or the panel is invisible for reasons nothing on
          // screen explains.
          //
          // 1. The details column: a real grid track on the frame. Computed
          //    style, not inline — AppFrame writes "280px minmax(0, 1fr) 360px"
          //    and only the computed form resolves the middle track to pixels.
          // 2. Another plugin's rail. `shell.overlay` is a LIST slot: anyone may
          //    register into it, and one occupant here paints a `position:fixed`
          //    right rail at z-index 500. Raising our own z-index would be a
          //    fight neither of us can win; measuring past it is not.
          var overlay = document.querySelector('[data-shell-overlay]')
          if (overlay === null) return
          var frame = overlay.parentElement
          var occupied = 0
          if (frame !== null) {
            var tracks = window.getComputedStyle(frame).gridTemplateColumns
            if (tracks) {
              var parts = tracks.trim().split(/\s+/)
              var last = parseFloat(parts[parts.length - 1])
              if (!isNaN(last)) occupied = last
            }
          }

          var mine = ref.current
          var width = window.innerWidth
          var leftmost = width
          var panels = overlay.querySelectorAll('*')
          for (var i = 0; i < panels.length; i++) {
            var node = panels[i]
            if (mine !== null && mine !== undefined && (node === mine || mine.contains(node))) continue
            var style = window.getComputedStyle(node)
            if (style.position !== 'fixed' && style.position !== 'absolute') continue
            var rect = node.getBoundingClientRect()
            // A rail, not a badge: touching the right edge and tall enough that
            // sitting under it would hide the panel rather than clip a corner.
            if (rect.width < 80 || rect.height < 240) continue
            if (rect.right < width - 8) continue
            if (rect.left < leftmost) leftmost = rect.left
          }
          if (leftmost < width) occupied = Math.max(occupied, width - leftmost)

          var next = 16 + occupied
          inset[1](function (current) { return current === next ? current : next })
        }
        measure()
        // Columns are drag-resizable and other plugins' rails open and close, so
        // a one-shot measure is right only until the first change.
        var observer = null
        var overlay = document.querySelector('[data-shell-overlay]')
        if (overlay !== null && typeof ResizeObserver === 'function') {
          observer = new ResizeObserver(measure)
          observer.observe(overlay)
          if (overlay.parentElement !== null) observer.observe(overlay.parentElement)
        }
        window.addEventListener('resize', measure)
        var timer = setInterval(measure, 800)
        return function () {
          if (observer !== null) observer.disconnect()
          window.removeEventListener('resize', measure)
          clearInterval(timer)
        }
      }, [])
      return inset[0]
    }

    /**
     * How much of THIS element's right edge something else is sitting on.
     *
     * `useRightInset` answers a different question: how much of the WINDOW's
     * right edge is spoken for. That is the right question for anything with
     * `position: fixed`, which is placed against the window. It is the wrong
     * question for a view that lives inside the frame's middle column — the
     * grid has already subtracted the details track, so paying for it again
     * padded the view by a few hundred pixels of nothing. That dead white
     * strip is what this exists to stop.
     *
     * Only a rail that genuinely overlaps, and genuinely eats into the right
     * edge, counts. Nothing overlapping means zero: when the neighbour closes,
     * the width comes straight back with no separate teardown.
     */
    function useOverlapInset(ref) {
      var inset = useState(0)
      useEffect(function () {
        var measure = function () {
          var mine = ref.current
          if (mine === null || mine === undefined) return
          var rect = mine.getBoundingClientRect()
          if (rect.width === 0) return
          var covered = 0
          var consider = function (node) {
            if (node === mine || mine.contains(node) || node.contains(mine)) return
            var style = window.getComputedStyle(node)
            if (style.position !== 'fixed' && style.position !== 'absolute') return
            if (style.visibility === 'hidden' || style.display === 'none') return
            var r = node.getBoundingClientRect()
            // A rail, not a badge or a tooltip.
            if (r.width < 80 || r.height < 240) return
            // It has to actually be on top of me, on both axes.
            if (r.left >= rect.right || r.right <= rect.left) return
            if (r.top >= rect.bottom || r.bottom <= rect.top) return
            // And it has to reach my right edge. Something parked over my
            // middle is not something a right-hand margin can step around.
            if (r.right < rect.right - 8) return
            var bite = rect.right - Math.max(rect.left, r.left)
            if (bite > covered) covered = bite
          }
          var overlay = document.querySelector('[data-shell-overlay]')
          if (overlay !== null) {
            var kids = overlay.querySelectorAll('*')
            for (var i = 0; i < kids.length; i += 1) consider(kids[i])
          }
          var next = Math.max(0, Math.round(covered))
          inset[1](function (current) { return current === next ? current : next })
        }
        measure()
        var observer = null
        var overlay = document.querySelector('[data-shell-overlay]')
        if (overlay !== null && typeof ResizeObserver === 'function') {
          observer = new ResizeObserver(measure)
          observer.observe(overlay)
          if (overlay.parentElement !== null) observer.observe(overlay.parentElement)
        }
        window.addEventListener('resize', measure)
        var timer = setInterval(measure, 800)
        return function () {
          if (observer !== null) observer.disconnect()
          window.removeEventListener('resize', measure)
          clearInterval(timer)
        }
      }, [])
      return inset[0]
    }

    /**
     * Drag the panel by its header, resize it by its left edge.
     *
     * Position is kept as an offset from the auto-placed corner rather than as
     * absolute coordinates, so a dragged panel still steps around the details
     * column and other plugins' rails when they open — an absolute position
     * would be correct until the first layout change and wrong after it.
     *
     * Stored per browser under a fixed key: where someone put the panel is a
     * per-viewer convenience, and losing it on reload is the only thing more
     * annoying than not being able to move it.
     */

    module.exports = { shared, publish, requestViewport, useShared, useRightInset, useOverlapInset }
    return module.exports
  },
})

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
    function treeFilter(graph, modeOverride) {
      var mode = modeOverride || shared.treeMode || 'all'
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

    function visibleForMode(graph, modeOverride) {
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
      var treeAllow = treeFilter(graph, modeOverride)
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

    function visible(graph) {
      return visibleForMode(graph)
    }

    module.exports = { STICKY_TURNS, stickyByRecency, editedNode, fadedOut, treeFilter, visible, visibleForMode }
    return module.exports
  },
})

// dsh-cdd-lens — Panel placement and node coordinates in localStorage.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/state/persist',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared

    var PLACE_KEY = 'cdd-lens.placement'

    function loadPlacement() {
      try {
        var raw = window.localStorage.getItem(PLACE_KEY)
        if (raw === null) return { dx: 0, dy: 0, w: 412, h: 0 }
        var value = JSON.parse(raw)
        return {
          dx: typeof value.dx === 'number' ? value.dx : 0,
          dy: typeof value.dy === 'number' ? value.dy : 0,
          w: typeof value.w === 'number' ? value.w : 412,
          h: typeof value.h === 'number' ? value.h : 0,
        }
      } catch (e) {
        // Private windows and blocked site data both throw here; a panel in its
        // default corner is a fine outcome, a crashed plugin is not.
        return { dx: 0, dy: 0, w: 412, h: 0 }
      }
    }

    function savePlacement(place) {
      try { window.localStorage.setItem(PLACE_KEY, JSON.stringify(place)) } catch (e) { /* ignore */ }
    }

    function usePlacement() {
      var state = useState(loadPlacement)
      var place = state[0]
      var set = state[1]
      var drag = useRef(null)

      var onPointerDown = function (mode) {
        return function (event) {
          if (event.button !== undefined && event.button !== 0) return
          event.preventDefault()
          event.stopPropagation()
          drag.current = {
            mode: mode, x: event.clientX, y: event.clientY,
            dx: place.dx, dy: place.dy, w: place.w, h: place.h,
          }
          var move = function (e) {
            var d = drag.current
            if (d === null) return
            if (d.mode === 'move') {
              // Right-anchored and bottom-anchored, so dragging right/down must
              // shrink the offsets.
              set({ dx: d.dx - (e.clientX - d.x), dy: d.dy - (e.clientY - d.y), w: d.w, h: d.h })
            } else {
              var w = Math.max(300, Math.min(900, d.w - (e.clientX - d.x)))
              set({ dx: d.dx, dy: d.dy, w: w, h: d.h })
            }
          }
          var up = function () {
            window.removeEventListener('pointermove', move)
            window.removeEventListener('pointerup', up)
            if (drag.current !== null) { drag.current = null }
            set(function (current) { savePlacement(current); return current })
          }
          window.addEventListener('pointermove', move)
          window.addEventListener('pointerup', up)
        }
      }

      return {
        place: place,
        onMoveDown: onPointerDown('move'),
        onResizeDown: onPointerDown('resize'),
        reset: function () {
          var fresh = { dx: 0, dy: 0, w: 412, h: 0 }
          set(fresh); savePlacement(fresh)
        },
      }
    }

    // User-authored node positions are the durable layout. Automatic focus
    // layout is derived in memory and never writes this table, so leaving a
    // highlighted chain restores the exact picture the user arranged.
    var NODE_POSITIONS_KEY = 'cdd-lens.node-positions.v1'

    function readAllNodePositions() {
      try {
        var raw = window.localStorage.getItem(NODE_POSITIONS_KEY)
        var parsed = raw === null ? {} : JSON.parse(raw)
        return parsed && typeof parsed === 'object' ? parsed : {}
      } catch (e) { return {} }
    }

    function ensureNodePositions(root) {
      var key = String(root || '')
      if (shared.positionRoot === key) return
      var all = readAllNodePositions()
      shared.positionRoot = key
      shared.nodePositions = all[key] && typeof all[key] === 'object' ? all[key] : {}
    }

    function saveNodePosition(id, point) {
      if (shared.positionRoot === null) return
      shared.nodePositions[id] = { x: Math.round(point.x), y: Math.round(point.y) }
      try {
        var all = readAllNodePositions()
        all[shared.positionRoot] = shared.nodePositions
        window.localStorage.setItem(NODE_POSITIONS_KEY, JSON.stringify(all))
      } catch (e) { /* a blocked localStorage keeps the layout session-local */ }
    }

    function clearNodePositions() {
      if (shared.positionRoot === null) return
      shared.nodePositions = {}
      try {
        var all = readAllNodePositions()
        delete all[shared.positionRoot]
        window.localStorage.setItem(NODE_POSITIONS_KEY, JSON.stringify(all))
      } catch (e) { /* ignore */ }
    }

    /** The current session id, read from the sessions list (root-scoped views get no sessionId prop). */

    module.exports = { PLACE_KEY, loadPlacement, savePlacement, usePlacement, NODE_POSITIONS_KEY, readAllNodePositions, ensureNodePositions, saveNodePosition, clearNodePositions }
    return module.exports
  },
})

// dsh-cdd-lens — Folding a session transcript into anchor touches.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/session/trajectory',
  factory: (require) => {
    var module = { exports: {} }

    // ---- folding the session, off the Trajectory target --------------------
    //
    // Not a target of our own. A conversation view target only receives nodes
    // that some registered NODE definition contributes to it — the assembler
    // builds per target from `contextsByTarget` — so registering a builder
    // alone gets a live, correctly driven stream of exactly nothing. That is
    // what the first attempt did, and it looked like a working plugin with an
    // empty graph.
    //
    // `trajectory` already has that whole definition set: every tool card,
    // every running call, compaction markers, and a seq to turn index, assembled
    // once and paged by the shell. Reading it is both less code and the only
    // version that cannot disagree with the Trajectory tab beside us.

    var TARGET = 'trajectory'

    /** Tool name to what the agent was doing to the code. */
    var VERBS = {
      read: 'read', read_image: 'read',
      edit: 'edit', write: 'edit', str_replace_editor: 'edit',
      grep: 'search', glob: 'search',
    }

    function parseArgs(raw) {
      if (typeof raw !== 'string') return {}
      try {
        var value = JSON.parse(raw)
        return value !== null && typeof value === 'object' ? value : {}
      } catch (e) { return {} }
    }

    /**
     * Pull the file touches out of one tool card.
     *
     * A running call — seen, no result yet — is the agent working right now, and
     * it is the only source for the red node.
     */
    function touchesOf(block) {
      var settled = block.kind === 'tool-result'
      var name = settled ? (block.call === null || block.call === undefined ? null : block.call.name) : block.name
      var verb = name === null || name === undefined ? undefined : VERBS[name]
      var out = []
      if (verb === undefined) return out
      if (settled && (block.isError === true || block.error !== undefined)) return out

      var argsRaw = settled ? (block.call === null || block.call === undefined ? '' : block.call.argsRaw) : block.argsRaw
      var args = parseArgs(argsRaw)
      var meta = settled ? block.meta : undefined
      var running = !settled

      if (verb === 'read') {
        var file = (meta && meta.path) || args.file_path
        if (typeof file !== 'string') return out
        var from = (meta && Number.isInteger(meta.offset)) ? meta.offset
          : (Number.isInteger(args.offset) ? args.offset : 1)
        var span = (meta && Number.isInteger(meta.lines)) ? meta.lines
          : (Number.isInteger(args.limit) ? args.limit : null)
        // No limit means the agent opened the whole file, which is most reads.
        // -1 says so on the wire; resolving such a read to whatever anchor
        // contains line 1 finds nothing (line 1 is imports) and was why a
        // session that read eight files drew an empty graph.
        out.push({
          path: file, from: from, to: span === null ? -1 : from + span - 1,
          text: null, verb: verb, tool: name, running: running, approx: false,
        })
        return out
      }

      if (verb === 'edit') {
        var diffs = meta && Array.isArray(meta.diffs) ? meta.diffs : []
        if (diffs.length === 0) {
          if (typeof args.file_path === 'string') {
            out.push({
              path: args.file_path, from: null, to: null,
              text: args.new_string || args.content || null,
              verb: verb, tool: name, running: running, approx: true,
            })
          }
          return out
        }
        diffs.forEach(function (diff) {
          var p = diff.path || args.file_path
          if (typeof p !== 'string') return
          // A diff hunk carries no line numbers; the applied text is the only
          // handle, and the host finds it in the file as it stands now.
          out.push({
            path: p, from: null, to: null, text: diff.newText || diff.oldText || null,
            verb: verb, tool: name, running: running, approx: true,
          })
        })
        return out
      }

      // A grep scopes a directory; it is not evidence that any particular
      // function was read, so it contributes a file scope and no anchor.
      var scope = args.path || args.file_path
      if (typeof scope === 'string') {
        out.push({
          path: scope, from: null, to: null, text: null,
          verb: verb, tool: name, running: running, approx: true, scopeOnly: true,
        })
      }
      return out
    }

    /** One tool card and every code-dispatch child under it. */
    function walkCalls(block, sink) {
      sink.push(block)
      var kids = block.subCalls || []
      for (var i = 0; i < kids.length; i++) walkCalls(kids[i], sink)
    }

    /**
     * Fold a Trajectory snapshot into the calls the graph paints with.
     *
     * `eventLocations` already places each seq in its turn, so the turn number
     * on a node is read, never inferred. Everything at or before the newest
     * landed compaction is no longer verbatim on the model's surface: that is
     * the fade, taken from the marker the conversation itself renders.
     */
    function foldTrajectory(snap) {
      if (snap === undefined || snap === null) return { calls: [], turn: 0, compactedThrough: -1 }
      var nodes = snap.eventNodes || []
      // Turn table built from the nodes that carry one (assistant, user, …).
      // `eventLocations` also holds it, but only for seqs the location index
      // matched; a tool result whose own seq is absent there silently reads as
      // turn 0, and every badge on the graph then says T0.
      var bounds = []
      nodes.forEach(function (node) {
        if (typeof node.turn === 'number' && typeof node.seq === 'number') {
          bounds.push({ seq: node.seq, turn: node.turn })
        }
      })
      var locations = snap.eventLocations
      if (locations !== undefined && typeof locations.forEach === 'function') {
        locations.forEach(function (at, seq) {
          if (at !== null && at !== undefined && (at.kind === 'turn' || at.kind === 'step')) {
            bounds.push({ seq: seq, turn: at.turn.turn })
          }
        })
      }
      bounds.sort(function (l, r) { return l.seq - r.seq })
      var turnOf = function (seq) {
        var turn = 0
        for (var i = 0; i < bounds.length; i++) {
          if (bounds[i].seq <= seq) turn = bounds[i].turn
          else break
        }
        return turn
      }

      var cut = -1
      var maxTurn = 0
      var calls = []
      var push = function (block, seq, running) {
        var touches = touchesOf(block)
        if (touches.length === 0) return
        var turn = turnOf(seq)
        if (turn > maxTurn) maxTurn = turn
        calls.push({ key: block.callId, seq: seq, turn: turn, touches: touches, running: running })
      }

      nodes.forEach(function (node) {
        if (node.kind === 'compaction') { if (node.seq > cut) cut = node.seq; return }
        if (node.kind !== 'tool-result') return
        var blocks = []
        walkCalls(node, blocks)
        blocks.forEach(function (block) { push(block, block.seq === undefined ? node.seq : block.seq, false) })
      })
      ;(snap.runningCalls || []).forEach(function (block) {
        var blocks = []
        walkCalls(block, blocks)
        blocks.forEach(function (b) { push(b, Number.MAX_SAFE_INTEGER, true) })
      })

      calls.sort(function (l, r) { return l.seq - r.seq })
      calls.forEach(function (call) { call.remembered = call.seq > cut })
      if (snap.partial !== null && snap.partial !== undefined && snap.partial.turn > maxTurn) maxTurn = snap.partial.turn
      return { calls: calls, turn: maxTurn, compactedThrough: cut }
    }

    module.exports = { TARGET, VERBS, parseArgs, touchesOf, walkCalls, foldTrajectory }
    return module.exports
  },
})

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
         * Re-check every node on the graph against the index as it stands NOW.
         *
         * Triggered when any answer carries a stamp different from the one the
         * graph was seated against: anchors the rebuild dropped are removed
         * (not hidden — the code they named is gone), survivors get their
         * counts refreshed, and the graph takes the new stamp. Layers are
         * recomputed by the layout itself, so nothing here re-seats anything.
         */
        revalidate: function () {
          if (shared.revalidating === true) return Promise.resolve()
          var ids = shared.graph.order.slice()
          if (ids.length === 0) return Promise.resolve()
          shared.revalidating = true
          return apiPost('/recheck', params({}), { ids: ids }).then(function (body) {
            body.nodes.forEach(function (n) {
              if (n.missing === true) { removeNode(shared.graph, n.id); return }
              var node = shared.graph.nodes[n.id]
              // node 就是 anchor：整条替换，不留旧字段。
              if (node !== undefined) shared.graph.nodes[n.id] = n
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

    module.exports = { fetchMethods }
    return module.exports
  },
})

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
          if (ui.open[slot] === true) {
            note('expand', 'SKIP 这个方向已经开着（' + slot + '）')
            return Promise.resolve()
          }
          if (ui.open[autoSlot] === true) {
            if (!auto) {
              ui.open[slot] = true
              ui.open[autoSlot] = false
              lightNeighbourhood(id)
              publish()
              note('expand', 'PROMOTE 自动展开状态为用户打开（' + slot + '）')
              return Promise.resolve()
            }
            note('expand', 'SKIP 这个方向已经自动开着（' + autoSlot + '）')
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

// dsh-cdd-lens — Engine methods for selection, edge focus and dragging.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/engine/selection',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var requestViewport = __state_store.requestViewport
    var shared = __state_store.shared
    var __state_persist = require('dsh-cdd-lens/state/persist')
    var saveNodePosition = __state_persist.saveNodePosition
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf

    /**
     * What is selected, focused, or being dragged.
     *
     * @param ctx - the client context the views were mounted with.
     * @param engine - the engine being assembled; methods call each other
     *   through it, so it is passed in rather than closed over.
     * @param session - the current session id, or null.
     * @param params - query parameters for one request.
     * @returns the methods this file contributes.
     */
    function selectionMethods(ctx, engine, session, params) {
      return {
        reveal: function (id) {
          shared.selected = id
          shared.focused = id
          shared.edgeFocus = null
          shared.lit = null
          // 记下「这一轮看过它」：看过的节点按轮次变旧、过期撤下；
          // edit 过的不受影响，一直留着（见 graph/visible.fadedOut）。
          var ui = uiOf(shared.graph, id)
          if (ui !== null) ui.viewedAt = shared.turn
          requestViewport(id, 'center')
          publish()
          return engine.source(id)
        },
        select: function (id) {
          // Clicking the already-focused node clears the emphasis, so getting
          // the whole picture back does not require hunting for empty canvas.
          // The gathered neighbours fly home with it.
          if (shared.focused === id) { shared.focused = null; engine.releaseGather(); publish(); return Promise.resolve() }
          // `focused` is set only by a human click. `selected` also moves on its
          // own when a trace loads, and dimming everything else off THAT made
          // 88% of the wires grey the moment the tab opened — an emphasis that
          // is always on is just a washed-out picture.
          return engine.reveal(id)
        },
        blur: function () {
          shared.focused = null
          engine.releaseGather()
          publish()
        },
        /**
         * Light up what a wire belongs to.
         *
         * A dataflow edge is one link in a run: the value came from somewhere
         * and goes on somewhere, and seeing only the two ends of one hop tells
         * you almost nothing. So dataflow lights the whole run it belongs to,
         * following the same relation kind in both directions. A call is not
         * like that — `a` calls `b` and that is the whole fact — so it lights
         * its two ends and stops.
         * @param from - the wire's source anchor id.
         * @param to - the wire's target anchor id.
         * @param type - the relation kind the wire is drawing.
         */
        lightEdge: function (from, to, type) {
          var was = shared.lit
          if (was !== null && was.key === from + '→' + to + ':' + type) {
            shared.lit = null
            publish()
            return
          }
          var nodes = {}
          var wires = {}
          var mark = function (f, t) {
            nodes[f] = true
            nodes[t] = true
            wires[f + '→' + t + ':' + type] = true
          }
          mark(from, to)
          if (type === 'dataflow') {
            // Walk the run, both ways, along this kind only.
            var seen = {}
            var queue = [from, to]
            while (queue.length > 0) {
              var at = queue.shift()
              if (seen[at]) continue
              seen[at] = true
              shared.graph.edges.forEach(function (e) {
                if ((e.types || []).indexOf(type) < 0) return
                if (e.from === at || e.to === at) {
                  mark(e.from, e.to)
                  queue.push(e.from === at ? e.to : e.from)
                }
              })
            }
          }
          shared.lit = { key: from + '→' + to + ':' + type, type: type, nodes: nodes, wires: wires }
          publish()
        },

        /** Light every wire that touches one anchor, so its own are obvious. */
        lightNode: function (id) {
          if (shared.lit !== null && shared.lit.key === id) { shared.lit = null; publish(); return }
          var nodes = {}
          var wires = {}
          nodes[id] = true
          shared.graph.edges.forEach(function (e) {
            if (e.from !== id && e.to !== id) return
            nodes[e.from] = true
            nodes[e.to] = true
            ;(e.types || []).forEach(function (type) {
              wires[e.from + '→' + e.to + ':' + type] = true
            })
          })
          shared.lit = { key: id, type: null, nodes: nodes, wires: wires }
          publish()
        },

        focusEdge: function (from, to, type) {
          var before = shared.edgeFocus
          if (before && before.from === from && before.to === to && before.type === type) {
            shared.edgeFocus = null
          } else {
            shared.edgeFocus = { from: from, to: to, type: type }
            shared.focused = null
            requestViewport(from, 'center')
          }
          publish()
        },
        blurEdge: function () {
          if (shared.edgeFocus === null || shared.edgeFocus === undefined) return
          shared.edgeFocus = null
          shared.lit = null
          publish()
        },
        moveNode: function (id, point, commit) {
          shared.nodePositions[id] = { x: Math.round(point.x), y: Math.round(point.y) }
          // A drag during a gather takes the node out of the gathered column:
          // the overlay re-seats its members on every layout, so without the
          // mark the next pass would put the card straight back and the drag
          // would move nothing — the lock the user reported.
          if (shared.gather !== null && shared.gather !== undefined) {
            if (shared.gather.freed === undefined) shared.gather.freed = {}
            shared.gather.freed[id] = true
          }
          if (commit) saveNodePosition(id, point)
          publish()
        },
      }
    }

    module.exports = { selectionMethods }
    return module.exports
  },
})

// dsh-cdd-lens — Engine method that turns a session snapshot into anchor state.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/engine/ingest',
  factory: (require) => {
    var module = { exports: {} }
    var __runtime_api = require('dsh-cdd-lens/runtime/api')
    var ROUTE = __runtime_api.ROUTE
    var api = __runtime_api.api
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var addEdge = __graph_model.addEdge
    var addNode = __graph_model.addNode
    var uiOf = __graph_model.uiOf
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note
    var fact = __runtime_debug.fact
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var requestViewport = __state_store.requestViewport
    var shared = __state_store.shared

    /**
     * Taking one session snapshot and painting it onto the graph.
     *
     * @param ctx - the client context the views were mounted with.
     * @param engine - the engine being assembled; methods call each other
     *   through it, so it is passed in rather than closed over.
     * @param session - the current session id, or null.
     * @param params - query parameters for one request.
     * @returns the methods this file contributes.
     */
    function ingestMethods(ctx, engine, session, params) {
      return {
        /**
         * Fold one conversation-view snapshot into the graph.
         *
         * The snapshot arrives from the shell, not from a poll: the same source
         * the Trajectory tab runs on, so it is live during streaming, correct
         * after a cold reload, and cannot disagree with the chat beside it.
         *
         * Only the file to anchor step needs the host, and only for calls not
         * seen before. The page cannot look inside the repository, and that is
         * the whole of what it asks for.
         */
        ingest: function (snap) {
          if (snap === undefined || snap === null) return Promise.resolve()
          // Resolving before the root is known would ask the wrong repository.
          if (shared.root === undefined) return engine.context().then(function () { return engine.ingest(snap) })
          shared.turn = snap.turn
          shared.resolved = shared.resolved || {}
          var pending = []
          snap.calls.forEach(function (call) {
            call.touches.forEach(function (touch, i) {
              var key = call.key + '#' + i
              if (shared.resolved[key] !== undefined) return
              if (touch.scopeOnly === true) {
                shared.resolved[key] = { anchors: [], reason: 'scope', file: touch.path }
                return
              }
              pending.push({ key: key, file: touch.path, from: touch.from, to: touch.to, text: touch.text })
            })
          })

          var after = function () {
            var byAnchor = {}
            var unresolved = {}
            // Which step of its turn a call is. `seq` is global and means nothing
            // to a reader; "the third tool call of turn 15" is what someone
            // actually says out loud, so the badge carries t15s3 and the numbering
            // restarts with every turn.
            var stepOf = {}
            var stepped = {}
            snap.calls.forEach(function (call) {
              stepped[call.turn] = (stepped[call.turn] || 0) + 1
              stepOf[call.key] = stepped[call.turn]
            })
            snap.calls.forEach(function (call) {
              call.touches.forEach(function (touch, i) {
                var hit = shared.resolved[call.key + '#' + i]
                if (hit === undefined) return
                if (hit.anchors.length === 0) {
                  // Kept, not dropped. A session that opened twenty files and
                  // shows an empty panel reads as a broken plugin; naming the
                  // file and the reason is the difference between an honest
                  // empty graph and a silent one.
                  var f = hit.file || touch.path
                  if (unresolved[f] === undefined) {
                    unresolved[f] = {
                      file: f, reason: hit.reason, verb: touch.verb, turns: [], steps: [],
                    }
                  }
                  if (unresolved[f].turns.indexOf(call.turn) < 0) unresolved[f].turns.push(call.turn)
                  // Where in the session it happened, same as a resolved touch.
                  // A file that could not be pinned to an anchor still happened
                  // at a moment, and leaving it out of the order would make the
                  // rail quietly skip part of what the agent did.
                  var at = { turn: call.turn, step: stepOf[call.key] || 1, verb: touch.verb }
                  var seenAt = unresolved[f].steps.some(function (x) {
                    return x.turn === at.turn && x.step === at.step
                  })
                  if (!seenAt) unresolved[f].steps.push(at)
                  return
                }
                hit.anchors.forEach(function (anchor) {
                  var record = byAnchor[anchor.id]
                  var event = {
                    turn: call.turn, step: stepOf[call.key] || 1,
                    verb: touch.verb, tool: touch.tool,
                    approx: touch.approx === true || hit.approx === true,
                    onSurface: call.remembered !== false, working: call.running === true,
                  }
                  if (record === undefined) {
                    byAnchor[anchor.id] = {
                      id: anchor.id, anchor: anchor,
                      firstTurn: call.turn, lastTurn: call.turn,
                      firstStep: event.step, lastStep: event.step, events: [event],
                    }
                  } else {
                    if (call.turn < record.firstTurn
                        || (call.turn === record.firstTurn && event.step < record.firstStep)) {
                      record.firstTurn = call.turn
                      record.firstStep = event.step
                    }
                    if (call.turn > record.lastTurn
                        || (call.turn === record.lastTurn && event.step > record.lastStep)) {
                      record.lastTurn = call.turn
                      record.lastStep = event.step
                    }
                    record.events.push(event)
                  }
                })
              })
            })
            Object.keys(byAnchor).forEach(function (id) {
              var record = byAnchor[id]
              record.events.sort(function (l, r) { return l.turn - r.turn || l.step - r.step })
              var working = record.events.some(function (e) { return e.working })
              var edited = record.events.some(function (e) { return e.verb === 'edit' })
              record.state = working ? 'working' : edited ? 'edited' : 'viewed'
              // One surviving verbatim read is enough to say the model still knows it.
              record.remembered = record.events.some(function (e) { return e.onSurface })
              record.approx = record.events.every(function (e) { return e.approx })
              // 把「这次会话改过它」同时写到节点上：edit 的节点一直留在图上，图那一边
              // 不必每次去翻 trace。也记下最近一次被碰是哪一轮——看过的节点按轮次
              // 变旧、过期撤下（见 graph/visible.fadedOut）。
              var ui = uiOf(shared.graph, record.id)
              if (ui !== null) {
                if (edited || working) ui.edited = true
                ui.viewedAt = record.lastTurn
              }
            })
            shared.trace = byAnchor
            shared.unresolved = Object.keys(unresolved).map(function (k) { return unresolved[k] })
            note('graph', 'anchors=' + Object.keys(byAnchor).length
              + ' unresolved=' + shared.unresolved.length + ' graphNodes=' + Object.keys(shared.graph.nodes).length
              + ' graphEdges=' + shared.graph.edges.length)
            fact('trace', Object.keys(byAnchor).length)
            fact('unresolved', shared.unresolved.length)
            // Rank by the seq of the first call that reached each anchor: the
            // order the agent actually walked, which is what the graph is for.
            var firstSeq = {}
            snap.calls.forEach(function (call) {
              call.touches.forEach(function (touch, i) {
                var hit = shared.resolved[call.key + '#' + i]
                if (hit === undefined) return
                hit.anchors.forEach(function (anchor) {
                  if (firstSeq[anchor.id] === undefined || call.seq < firstSeq[anchor.id]) {
                    firstSeq[anchor.id] = call.seq
                  }
                })
              })
            })
            var ranked = Object.keys(firstSeq).sort(function (l, r) { return firstSeq[l] - firstSeq[r] })
            shared.order = {}
            ranked.forEach(function (id, i) { shared.order[id] = i + 1 })
            if (window.__cddLens !== undefined) {
              var reasons = {}
              shared.unresolved.forEach(function (u) { reasons[u.reason] = (reasons[u.reason] || 0) + 1 })
              window.__cddLens.resolve = {
                calls: snap.calls.length,
                anchors: Object.keys(byAnchor).length,
                unresolved: shared.unresolved.length,
                reasons: reasons,
                root: shared.root,
              }
            }

            var ids = Object.keys(byAnchor)
            if (ids.length === 0) { publish(); return }
            var fresh = []
            ids.forEach(function (id) {
              if (shared.graph.nodes[id] === undefined) {
                addNode(shared.graph, byAnchor[id].anchor)
                uiOf(shared.graph, id).island = true
                fresh.push(id)
              }
              uiOf(shared.graph, id).session = true
            })
            if (shared.graph.rootId === null) {
              var newest = ids.map(function (id) { return byAnchor[id] })
                .sort(function (l, r) { return r.lastTurn - l.lastTurn })[0]
              shared.graph.rootId = newest.id
              uiOf(shared.graph, newest.id).island = false
              if (shared.selected === null) {
                shared.selected = newest.id
                requestViewport(newest.id, 'fit')
                engine.source(newest.id)
              }
            }
            publish()
            if (fresh.length === 0) return grow()
            // Only edges the code actually has, between anchors already on
            // screen. Nothing new is pulled in, and two anchors touched in
            // sequence with no edge between them stay apart: that gap is the
            // finding, not a rendering bug to paper over.
            // `bridge=1` because direct edges alone are almost always none: an
            // agent reads a type and a function that uses it, but not the file
            // between them, so both ends of a real relation are rarely both in
            // the touched set. One intermediate hop is admitted and comes back
            // marked, so the connection is visible and it is still obvious which
            // nodes the agent actually opened.
            return api('/among', params({
              ids: Object.keys(shared.graph.nodes).join(','), bridge: '1',
            })).then(function (link) {
              (link.bridges || []).forEach(function (anchor) {
                if (shared.graph.nodes[anchor.id] === undefined) {
                  addNode(shared.graph, anchor)
                  uiOf(shared.graph, anchor.id).bridge = true
                  uiOf(shared.graph, anchor.id).synthetic = true
                }
              })
              link.edges.forEach(function (e) {
                // Mark the EDGE, never the node's expanded flag. Setting
                // `node.down = true` here told the ↓ button that the callees
                // were already on screen when they had never been fetched, so a
                // press ran the collapse branch, hid nothing, and looked dead.
                var edge = addEdge(shared.graph, e.from, e.to, [e.type])
                if (edge !== undefined) edge.always = true
                if (shared.graph.nodes[e.from] !== undefined) {
                  uiOf(shared.graph, e.from).island = false
                }
                if (shared.graph.nodes[e.to] !== undefined) {
                  uiOf(shared.graph, e.to).island = false
                }
              })
              publish()
              return grow()
            })
          }

          // What the picture is about is what was changed. The edits are the
          // seeds; `chain` pushes each of them out and back and reports the
          // 这里以前调 engine.chain(edits, 1) 让服务端把图分层、把树长出来。
          //
          // /chain 已经删了——分层现在由布局自己算（layout/sugiyama 的第 2 步），
          // 子节点由按关系的展开按钮（/expand、/walk）拉进来。这一次会话 ingest
          // 只负责把「碰过的 anchor」放上屏幕并连上它们之间的边，够布局画第一版。
          //
          // 留着这个调用的话，engine.chain 不存在会当场抛错，整张图建不出来——
          // 表现就是「面板说还没有起点」，而画布空白。
          var grow = function () {
            fact('graphNodes', Object.keys(shared.graph.nodes).length)
            fact('graphEdges', shared.graph.edges.length)
            fact('root', shared.graph.rootId === null ? 'null' : String(shared.graph.rootId).split('::').pop())
            note('graph', '图就绪 nodes=' + Object.keys(shared.graph.nodes).length
              + ' edges=' + shared.graph.edges.length + ' root=' + shared.graph.rootId)
            publish()
            return Promise.resolve()
          }

          note('graph', 'ingest calls=' + snap.calls.length + ' pending=' + pending.length
            + ' resolved=' + Object.keys(shared.resolved).length)
          if (window.__cddLens !== undefined) window.__cddLens.pending = pending.length
          if (pending.length === 0) { after(); return Promise.resolve() }
          return fetch(ROUTE + '/resolve?' + new URLSearchParams(params()).toString(), {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ root: shared.root, touches: pending }),
          }).then(function (res) { return res.json() }).then(function (body) {
            body.results.forEach(function (entry) { shared.resolved[entry.key] = entry })
            after()
          }).catch(function (error) {
            if (window.__cddLens !== undefined) window.__cddLens.resolveError = String(error && error.message ? error.message : error)
            after()
          })
        },
      }
    }

    module.exports = { ingestMethods }
    return module.exports
  },
})

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
          var ui = uiOf(shared.graph, id)
          if (node === undefined || ui === null) return Promise.resolve()
          if (shared.gather !== null && shared.gather !== undefined && shared.gather.focus === id) {
            return Promise.resolve()
          }
          // freed: ids the user dragged out of the column while it was up.
          // They stay where they were dropped until the gather itself ends.
          shared.gather = { focus: id, freed: {} }
          stampFlight()
          publish()
          var loads = []
          // node 就是 anchor：`up`/`down` 是索引给的计数，直接读。
          // `auto=true`：拉邻居，但不碰按钮状态。选中一个节点不等于替用户按了
          // 上下键——以前它直接写 node.up/node.down，于是你点中节点时两个按钮
          // 已经是"收起"态，你按的第一下其实是在收起来。
          // 有哪几个关系就自动拉哪几个；只拉 call，避免选中一个节点就把
          // dataflow / inherit 的邻居全倒进来（那是用户按按钮才该发生的事）。
          var counts = node.peerCounts || {}
          var call = counts.call
          if (call !== undefined) {
            if (ui.open['up:call'] !== true && ui.open['autoup:call'] !== true && call.up > 0) {
              loads.push(engine.expand(id, 'up', true, 'call'))
            }
            if (ui.open['down:call'] !== true && ui.open['autodown:call'] !== true && call.down > 0) {
              loads.push(engine.expand(id, 'down', true, 'call'))
            }
          }
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

// dsh-cdd-lens — The engine both views drive.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/engine/engine',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __engine_fetch = require('dsh-cdd-lens/engine/fetch')
    var fetchMethods = __engine_fetch.fetchMethods
    var __engine_explore = require('dsh-cdd-lens/engine/explore')
    var exploreMethods = __engine_explore.exploreMethods
    var __engine_selection = require('dsh-cdd-lens/engine/selection')
    var selectionMethods = __engine_selection.selectionMethods
    var __engine_ingest = require('dsh-cdd-lens/engine/ingest')
    var ingestMethods = __engine_ingest.ingestMethods
    var __engine_gather = require('dsh-cdd-lens/engine/gather')
    var gatherMethods = __engine_gather.gatherMethods

    function currentSession(ctx) {
      try {
        var sessions = ctx.get('sessions')
        if (sessions === undefined || sessions.list === undefined) return undefined
        var snap = sessions.list.getSnapshot()
        return snap === undefined ? undefined : snap.current
      } catch (e) {
        return undefined
      }
    }

    /**
     * Assemble one engine for a view.
     *
     * The parts are installed onto the same object, so a method reaching
     * `engine.source` finds the one this call built and not another view's.
     * @param ctx - the client context the view was mounted with.
     * @returns the engine both views drive.
     */
    function makeEngine(ctx) {
      var session = function () { return currentSession(ctx) }
      var params = function (extra) {
        var base = {}
        var id = session()
        if (id !== undefined && id !== null) base.session = String(id)
        if (shared.root !== undefined) base.root = shared.root
        return Object.assign(base, extra || {})
      }
      var engine = {}
      Object.assign(engine, fetchMethods(ctx, engine, session, params))
      Object.assign(engine, exploreMethods(ctx, engine, session, params))
      Object.assign(engine, selectionMethods(ctx, engine, session, params))
      Object.assign(engine, ingestMethods(ctx, engine, session, params))
      Object.assign(engine, gatherMethods(ctx, engine, session, params))
      // Also on the engine, not only handed to the method factories. `Draw`
      // builds its own URL and asks for these, and finding `engine.params`
      // undefined threw on every render of that tab — which is why `cdd draw`
      // had never once opened.
      engine.params = params
      engine.session = session
      return engine
    }

    module.exports = { currentSession, makeEngine }
    return module.exports
  },
})

// dsh-cdd-lens — Binding a live session to engine.ingest.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/session/trace',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var emptyGraph = __graph_model.emptyGraph
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var shared = __state_store.shared
    var __session_trajectory = require('dsh-cdd-lens/session/trajectory')
    var TARGET = __session_trajectory.TARGET
    var foldTrajectory = __session_trajectory.foldTrajectory

    function useConversationTrace(ctx, engine) {
      useEffect(function () {
        // The floating panel and the full view share one store. Only one of
        // them may own the conversation subscription; two owners race to reset
        // and repaint the same graph, which makes a successful button click
        // appear to undo itself.
        var owner = {}
        if (shared.traceOwner !== undefined && shared.traceOwner !== null) return
        shared.traceOwner = owner
        var conv = ctx.get('uiConversation')
        var sessions = ctx.get('sessions')
        if (conv === undefined || sessions === undefined) {
          shared.traceOwner = null
          return
        }
        var disposed = false
        var unsubscribe = null
        var boundTo = null

        var bind = function () {
          if (disposed) return
          var id
          try { id = sessions.list.getSnapshot().current } catch (e) { id = undefined }
          if (id === boundTo) return
          if (unsubscribe !== null) { unsubscribe(); unsubscribe = null }
          boundTo = id
          // A different conversation is a different project and a different
          // graph; carrying the old exploration across would be a lie.
          //
          // `root` and `context` MUST be cleared with it. `params()` sends the
          // remembered root on every request and it wins over the session on the
          // host, so a stale one silently resolved this conversation's files
          // against the previous conversation's repository — every anchor came
          // back "not indexed" while the panel looked perfectly healthy.
          shared.graph = emptyGraph()
          shared.trace = {}
          shared.resolved = {}
          shared.unresolved = []
          shared.selected = null
          shared.focused = null
          shared.edgeFocus = null
          shared.root = undefined
          shared.context = undefined
          shared.outline = undefined
          shared.fileCache = {}
          shared.sourceCache = {}
          publish()
          if (id === undefined || id === null) return
          // A diagnostic handle, deliberately kept: when the graph is empty the
          // only question that matters is whether the fold saw no tool calls or
          // never got a target at all, and those look identical on screen.
          var diag = { sessionId: id, target: null, error: null, snapshot: null }
          window.__cddLens = diag
          var target
          try {
            target = conv.binding(id).target(TARGET)
          } catch (e) {
            diag.error = String(e && e.message ? e.message : e)
            return
          }
          if (target === undefined || target === null || typeof target.getSnapshot !== 'function') {
            diag.error = 'target missing: ' + Object.prototype.toString.call(target)
            return
          }
          diag.target = 'ok'
          var push = function () {
            var folded = foldTrajectory(target.getSnapshot())
            diag.snapshot = { calls: folded.calls.length, turn: folded.turn, compactedThrough: folded.compactedThrough }
            engine.ingest(folded)
          }
          unsubscribe = target.subscribe(push)
          engine.context().then(push)
        }

        bind()
        // The selected session changes without this component remounting.
        var watch = setInterval(bind, 800)
        return function () {
          disposed = true
          clearInterval(watch)
          if (unsubscribe !== null) unsubscribe()
          if (shared.traceOwner === owner) shared.traceOwner = null
        }
      }, [])
    }

    module.exports = { useConversationTrace }
    return module.exports
  },
})

// dsh-cdd-lens — Per-anchor presentation helpers.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/record',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared

    // ---- presentation helpers ---------------------------------------------

    /** The state class for an anchor: what the session did to it, if anything. */
    function stateOf(id) {
      var record = shared.trace[id]
      if (record === undefined) return null
      return record
    }

    function dotClass(record) {
      if (record === undefined || record === null) return 'cddl-dot'
      if (record.state === 'working') return 'cddl-dot cddl-w'
      if (record.state === 'edited') return 'cddl-dot cddl-e'
      return 'cddl-dot cddl-v'
    }

    /**
     * The order the agent reached this anchor, 1-based.
     *
     * The turn number alone is not an order: a session that did all its reading
     * in one turn stamps every node T13 and the sequence — the thing being
     * reported — disappears. This is the rank of the first call that touched it.
     */
    function orderOf(id) {
      var seq = shared.order
      if (seq === undefined) return null
      var i = seq[id]
      return i === undefined ? null : i
    }

    /**
     * When this anchor was first opened, to the step.
     *
     * A turn number alone is not enough to find the moment again: a turn is
     * twenty tool calls, and "somewhere in turn 15" is not a place. `t15s3` is
     * the third call of turn 15, which is a place — it lines up with what the
     * trajectory shows and with what anyone says out loud.
     * @param record - the anchor's session record, or nothing.
     * @returns the badge element, or null when the session never touched it.
     */
    function turnLabel(record) {
      if (record === undefined || record === null) return null
      var verb = record.state === 'working' ? '正在改' : record.state === 'edited' ? '改' : '看'
      var tone = record.state === 'working' ? 'cddl-w' : record.state === 'edited' ? 'cddl-e' : 'cddl-v'
      var at = 't' + record.firstTurn + (record.firstStep === undefined ? '' : 's' + record.firstStep)
      var last = 't' + record.lastTurn + (record.lastStep === undefined ? '' : 's' + record.lastStep)
      var title = '第 ' + record.firstTurn + ' 轮第 ' + (record.firstStep || 1) + ' 步第一次打开'
        + (last === at ? '' : '，最后一次是 ' + last)
        + (record.approx ? '（行号为近似）' : '')
      return h('span', { className: 'cddl-turn ' + tone, title: title },
        at + ' ' + verb + (record.approx ? '~' : ''))
    }

    /**
     * Whether a project's index is too edge-poor to draw a call graph from.
     *
     * An unfiltered scan of a repository with `node_modules` in it produces
     * hundreds of thousands of anchors and almost no relations — every symbol
     * found, nothing connected. The panel would then draw a correct, useless
     * empty graph, and the honest thing is to say the index is the problem.
     */
    function degenerate(context) {
      if (context === undefined || context === null || context.stats === undefined) return false
      var stats = context.stats
      return stats.anchors > 5000 && stats.edges < stats.anchors / 20
    }

    function short(file) {
      var parts = String(file || '').split('/')
      return parts.length <= 2 ? file : '…/' + parts.slice(-2).join('/')
    }

    module.exports = { stateOf, dotClass, orderOf, turnLabel, degenerate, short }
    return module.exports
  },
})

// dsh-cdd-lens — The vertical tree in the floating panel.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/tree',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __graph_visible = require('dsh-cdd-lens/graph/visible')
    var visible = __graph_visible.visible
    var __view_record = require('dsh-cdd-lens/view/record')
    var dotClass = __view_record.dotClass
    var orderOf = __view_record.orderOf
    var short = __view_record.short
    var stateOf = __view_record.stateOf
    var turnLabel = __view_record.turnLabel
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf

    // ---- the vertical tree (floating panel) --------------------------------

    /**
     * Depth-first walk of the expanded graph, emitting rows with indents.
     *
     * Callers come first (they are "above" in the call direction), then the node
     * itself, then callees. Islands are emitted after a divider that names them
     * as unconnected rather than being folded into the tree.
     */
    function treeRows(graph) {
      var rows = []
      var seen = {}
      var shown = visible(graph)
      // Everything the session touched is shown whether or not an edge reaches
      // it. An anchor with no relations in the index is still an anchor the
      // agent opened, and dropping it would hide the very thing being reported.
      graph.order.forEach(function (id) { shown[id] = true })

      function walk(id, depth, direction) {
        if (seen[id] || !shown[id]) return
        seen[id] = true
        var node = graph.nodes[id]
        var ui = uiOf(graph, id) || {}
        if (node === undefined) return
        // Callers of an expanded node render ABOVE it at the same depth,
        // whichever direction the walk arrived from. Gating this on the arrival
        // direction meant pressing ↑ on anything below the root added the nodes
        // and drew none of them — the button looked dead.
        var openUp = Object.keys(ui.open).some(function (k) {
          return k.indexOf('up:') === 0 && ui.open[k] === true
        })
        if (openUp) {
          graph.edges.forEach(function (e) {
            if (e.to === id) walk(e.from, depth, 'up')
          })
        }
        rows.push({ id: id, depth: depth, node: node })
        if (ui.members && ui.memberList !== undefined) {
          ui.memberList.forEach(function (member) {
            rows.push({ id: member.id, depth: depth + 1, member: true, anchor: member })
          })
        }
        var openDown = Object.keys(ui.open).some(function (k) {
          return k.indexOf('down:') === 0 && ui.open[k] === true
        })
        if (openDown) {
          graph.edges.forEach(function (e) {
            if (e.from === id) walk(e.to, depth + 1, 'down')
          })
        }
      }

      if (graph.rootId !== null) walk(graph.rootId, 0, null)

      // Anchors the session touched that the root's subtree does not reach.
      // Each is walked as its own root, so a pair the code DOES connect nests
      // instead of being listed side by side as two unrelated things — the
      // edges are the whole point, and flattening them here threw them away
      // after the trouble of finding them.
      var roots = graph.order.filter(function (id) {
        if (seen[id] || !shown[id]) return false
        // Only a node nothing else in the graph reaches is a root of its own.
        return !graph.edges.some(function (e) {
          return e.to === id && graph.nodes[e.from] !== undefined && shown[e.from]
        })
      })
      if (roots.length > 0) {
        rows.push({ gap: true })
        roots.forEach(function (id) {
          var before = rows.length
          walk(id, 0, 'down')
          if (rows.length > before) rows[before].islandRow = true
        })
      }
      return rows
    }

    function TreeRow(props) {
      var engine = props.engine
      var row = props.row
      if (row.gap) {
        return h('div', { className: 'cddl-gap' }, [
          h('i', { key: 'l' }), '碰过但代码里没有边 · 不连', h('i', { key: 'r' }),
        ])
      }
      var anchor = row.member ? row.anchor : row.node
      var record = stateOf(row.id)
      var faded = record !== null && record !== undefined && !record.remembered
      var selected = shared.selected === row.id
      var ui = row.node !== undefined ? (uiOf(shared.graph, row.id) || {}) : {}
      var synthetic = row.node !== undefined && (ui.synthetic === true || ui.bridge === true)
      var cls = 'cddl-node'
        + (selected ? ' cddl-sel' : '')
        + (faded ? ' cddl-faded' : '')
        + (row.node !== undefined && ui.bridge === true ? ' cddl-bridge' : '')
        + (row.islandRow ? ' cddl-island' : '')

      var kids = [
        h('span', { key: 'i', className: 'cddl-ind', style: { width: (row.depth * 17) + 'px' } }),
      ]
      if (!row.member && !synthetic && (anchor.members > 0)) {
        kids.push(h('button', {
          key: 't', className: 'cddl-twist', title: anchor.members + ' 个成员',
          onClick: function (e) { e.stopPropagation(); engine.members(row.id) },
        }, ui.members ? '▾' : '▸'))
      } else {
        kids.push(h('span', { key: 't', className: 'cddl-twist' }, row.member ? '·' : ''))
      }
      var rank = orderOf(row.id)
      kids.push(rank === null
        ? h('span', { key: 'r', className: 'cddl-rank cddl-rank-none' }, '')
        : h('span', { key: 'r', className: 'cddl-rank', title: '第 ' + rank + ' 个被碰到' }, rank))
      kids.push(h('span', { key: 'd', className: dotClass(record) }))
      kids.push(h('span', { key: 's', className: 'cddl-sym', title: anchor.id }, anchor.symbol))
      if (!row.member && !synthetic && anchor.members > 0) {
        kids.push(h('span', { key: 'k', className: 'cddl-kind' }, '类 ' + anchor.members))
      }
      if (row.node !== undefined && ui.bridge === true) {
        kids.push(h('span', {
          key: 'br', className: 'cddl-kind cddl-bridgetag',
          title: 'agent 没打开过它。它出现在这里，是因为代码里它把上下两个碰过的 anchor 连起来了。',
        }, '桥'))
      }
      var badge = turnLabel(record)
      if (badge !== null) kids.push(React.cloneElement(badge, { key: 'b' }))
      if (faded) kids.push(h('span', { key: 'f', className: 'cddl-kind' }, '压缩'))
      var REL_ORDER = ['call', 'dataflow', 'inherit', 'dispatch', 'impact']
      var hop = function (direction, rel, count) {
        var slot = direction + ':' + rel
        var open = ui.open[slot] === true
        // 桥接点不许继续展开：它是布局借来的中间点，不是 agent 打开过的 anchor。
        var disabled = synthetic
        return h('button', {
          key: slot,
          disabled: disabled,
          'data-relation': rel,
          'data-count': count,
          title: synthetic
            ? '桥接节点只解释连接，不继续展开'
            : ((open ? '收起' : '展开') + (direction === 'up' ? '：谁在用它（' : '：它在用谁（') + count + '）'
              + ' · ' + rel + '\n按住 Shift 点：一路展开到底'),
          className: 'cddl-rel-' + rel + (open ? ' on' : '') + (disabled ? ' cddl-off' : ''),
          onClick: function (e) {
            e.stopPropagation()
            if (disabled) return
            if (open) { engine.collapse(row.id, direction, rel); return }
            if (e.shiftKey) engine.walk(row.id, direction, rel, 4)
            else engine.expand(row.id, direction, null, rel)
          },
        }, (direction === 'up' ? '↑' : '↓') + count)
      }
      var hopButtons = []
      REL_ORDER.forEach(function (rel) {
        var c = (anchor.peerCounts || {})[rel]
        // 没有数据的关系不出现——不画箭头、不写 0。
        if (c === undefined) return
        if (c.up > 0) hopButtons.push(hop('up', rel, c.up))
        if (c.down > 0) hopButtons.push(hop('down', rel, c.down))
      })
      kids.push(h('span', { key: 'h', className: 'cddl-hop' }, hopButtons.concat([
        h('button', {
          key: 'p', title: '固定',
          className: ui.pinned ? 'on' : '',
          onClick: function (e) { e.stopPropagation(); engine.pin(row.id) },
        }, ui.pinned ? '●' : '○'),
      ])))

      return h('div', {
        className: cls,
        onClick: function () { engine.select(row.id) },
      }, kids)
    }

    function Tree(props) {
      var engine = props.engine
      var rows = treeRows(shared.graph)
      if (rows.length === 0) {
        return h('div', { className: 'cddl-empty' },
          '还没有起点。到「目录」里翻一个函数，或者搜一个名字。')
      }
      var out = []
      var lastFile = null
      rows.forEach(function (row, i) {
        if (row.gap) { out.push(h(TreeRow, { key: 'gap' + i, row: row, engine: engine })); lastFile = null; return }
        var anchor = row.member ? row.anchor : row.node
        if (anchor.file !== lastFile) {
          lastFile = anchor.file
          out.push(h('div', {
            key: 'f' + i, className: 'cddl-filehdr',
            style: { paddingLeft: (row.depth * 17 + 2) + 'px' }, title: anchor.file,
          }, short(anchor.file)))
        }
        out.push(h(TreeRow, { key: row.id + ':' + i, row: row, engine: engine }))
      })
      return h('div', { className: 'cddl-tree' }, out)
    }

    module.exports = { treeRows, TreeRow, Tree }
    return module.exports
  },
})

// dsh-cdd-lens — The directory view and the draw trigger.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/outline',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __runtime_api = require('dsh-cdd-lens/runtime/api')
    var ROUTE = __runtime_api.ROUTE
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __view_record = require('dsh-cdd-lens/view/record')
    var dotClass = __view_record.dotClass
    var stateOf = __view_record.stateOf

    // ---- the directory view (the `cdd draw` shape: for finding things) -----

    // How many directory rows go into the page at once. This repository's
    // outline is 4,566 directories over 27,003 files; putting all of them in
    // the DOM is not a long list, it is a frozen tab. A screenful at a time,
    // with the filter applied over the whole set, shows the same index and
    // stays usable however large the repository is.
    var DIR_PAGE = 120

    function Outline(props) {
      var engine = props.engine
      var openDir = useState({})
      var filter = useState('')
      var shown = useState(DIR_PAGE)
      var dirs = shared.outline
      useEffect(function () { if (dirs === undefined) engine.outline() }, [dirs === undefined])
      if (dirs === undefined) return h('div', { className: 'cddl-empty' }, '读目录…')
      // `undefined` was the only empty checked for, and the trace clears this
      // to `undefined` — but a failed read leaves it null, and null.forEach is
      // a blank view with an exception behind it.
      if (dirs === null || typeof dirs.slice !== 'function') {
        return h('div', { className: 'cddl-empty' }, '目录读不出来。')
      }
      var needle = filter[0].trim().toLowerCase()
      var matched = needle === '' ? dirs : dirs.filter(function (entry) {
        return String(entry.dir).toLowerCase().indexOf(needle) >= 0
      })
      var page = matched.slice(0, shown[0])
      var out = []
      out.push(h('input', {
        key: 'filter', className: 'cddl-outline-filter', value: filter[0],
        placeholder: '筛目录（共 ' + dirs.length + ' 个）',
        onChange: function (e) { shown[1](DIR_PAGE); filter[1](e.target.value) },
      }))
      page.forEach(function (entry) {
        var isOpen = openDir[0][entry.dir] === true
        out.push(h('div', {
          key: 'd' + entry.dir, className: 'cddl-dir',
          onClick: function () {
            var next = Object.assign({}, openDir[0])
            next[entry.dir] = !isOpen
            openDir[1](next)
          },
        }, [
          h('span', { key: 't', className: 'cddl-twist' }, isOpen ? '▾' : '▸'),
          h('span', { key: 'n' }, entry.dir === '.' ? '(根目录)' : entry.dir + '/'),
          h('span', { key: 'c', className: 'cddl-count' }, entry.count),
        ]))
        if (!isOpen) return
        entry.files.forEach(function (file) {
          var fileOpen = openDir[0]['f:' + file.file] === true
          out.push(h('div', {
            key: 'f' + file.file, className: 'cddl-fileitem',
            onClick: function () {
              var next = Object.assign({}, openDir[0])
              next['f:' + file.file] = !fileOpen
              openDir[1](next)
              if (!fileOpen) engine.fileSymbols(file.file)
            },
          }, [
            h('span', { key: 't', className: 'cddl-twist' }, fileOpen ? '▾' : '▸'),
            h('span', { key: 'n' }, file.file.split('/').pop()),
            h('span', { key: 'c', className: 'cddl-count' }, file.count),
          ]))
          if (!fileOpen) return
          var symbols = (shared.fileCache || {})[file.file]
          if (symbols === undefined) { out.push(h('div', { key: 'l' + file.file, className: 'cddl-sub' }, '…')); return }
          symbols.forEach(function (anchor) {
            var record = stateOf(anchor.id)
            out.push(h('div', {
              key: 's' + anchor.id, className: 'cddl-symitem',
              title: '点开 → 成为逻辑图的起点',
              onClick: function () { engine.focus(anchor) },
            }, [
              h('span', { key: 'd', className: dotClass(record) }),
              h('span', { key: 'n', className: 'cddl-sym' }, anchor.symbol),
              anchor.members > 0 ? h('span', { key: 'm', className: 'cddl-kind' }, '类 ' + anchor.members) : null,
              h('span', { key: 'l', className: 'cddl-lines' }, anchor.start + '–' + anchor.end),
            ]))
          })
        })
      })
      if (matched.length > page.length) {
        out.push(h('div', {
          key: 'more', className: 'cddl-outline-more',
          onClick: function () { shown[1](shown[0] + DIR_PAGE) },
        }, '还有 ' + (matched.length - page.length) + ' 个目录 · 点这里再看 ' + DIR_PAGE + ' 个'))
      }
      if (matched.length === 0) {
        out.push(h('div', { key: 'none', className: 'cddl-empty' }, '没有目录匹配「' + filter[0] + '」'))
      }
      return h('div', { className: 'cddl-tree' }, out)
    }

    /**
     * `cdd draw`'s own compound browser, served verbatim in a frame.
     *
     * CodeDendrite already generates a finished directory/file/class/function
     * browser with its data inlined. Replacing it with a tree of my own lost a
     * working tool, so it is shown as itself. Same-origin, so it needs no bridge.
     */
    function drawStampAfter(before, body) {
      var hasMeta = before.ready !== undefined || before.building !== undefined || before.error !== undefined
      if (!hasMeta) {
        if (body.ready !== true || !body.stamp || body.stamp === before.stamp) return before
        return { stamp: body.stamp }
      }
      var next = {
        stamp: before.stamp || 0,
        ready: body.ready === true,
        building: body.building === true,
        error: body.error || null,
      }
      if (body.ready === true && body.stamp && body.stamp !== before.stamp) {
        next.stamp = body.stamp
      }
      if (next.stamp === before.stamp && next.ready === before.ready
          && next.building === before.building && next.error === before.error) return before
      return next
    }

    function Draw(props) {
      var engine = props.engine
      // The iframe goes up on the first render. `/draw` always answers with a
      // page: the paged browser shell when it exists, or the server-owned build
      // shell while it is being regenerated. Client-side loading/error cards
      // only hid that real shell and could get stuck in front of it.
      var state = useState({ stamp: 0, ready: false, building: false, error: null })
      var query = new URLSearchParams(engine.params()).toString()
      var src = ROUTE + '/draw?' + query
        + (state[0].stamp ? '&v=' + state[0].stamp : '')
      useEffect(function () {
        var stop = false
        var timer = null
        var ask = function () {
          fetch(ROUTE + '/draw-status?' + query, { cache: 'no-store' })
            .then(function (res) { return res.json() })
            .then(function (body) {
              if (stop) return
              state[1](function (before) { return drawStampAfter(before, body) })
              timer = setTimeout(ask, body.building === true || body.ready !== true ? 1500 : 8000)
            })
            .catch(function () {
              if (stop) return
              // The iframe remains mounted with its last real page. A transient
              // status failure only delays the next stamp check.
              timer = setTimeout(ask, 1500)
            })
        }
        ask()
        return function () { stop = true; if (timer !== null) clearTimeout(timer) }
      }, [query])
      return h('iframe', {
        // Keyed on the stamp: a new drawing is a new frame, not a frame asked
        // nicely to reload.
        key: 'draw' + state[0].stamp,
        className: 'cddl-frame', src: src, title: 'cdd draw',
      })
    }

    module.exports = { Outline, Draw, drawStampAfter }
    return module.exports
  },
})

// dsh-cdd-lens — Source, history, search, legend, unresolved.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/panels',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __view_record = require('dsh-cdd-lens/view/record')
    var dotClass = __view_record.dotClass
    var short = __view_record.short
    var stateOf = __view_record.stateOf

    // ---- source ------------------------------------------------------------

    function sourceLineCount(source) {
      if (source === null || source === undefined) return 0
      if (Number.isFinite(source.lineCount)) return source.lineCount
      return Math.max(0, Number(source.end) - Number(source.start) + 1)
    }

    function SourceMissing(props) {
      return h('div', { className: 'cddl-src' }, [
        h('div', { key: 'h', className: 'cddl-srch' }, [
          h('span', { key: 't' }, props.id + ' · 源码范围读不出来'),
          h('button', {
            key: 'x', className: 'cddl-src-close', title: '关闭源码详情',
            onClick: function () { props.engine.blur() },
          }, '×'),
        ]),
      ])
    }

    function Source(props) {
      var id = shared.selected
      if (id === null || id === undefined) return null
      var source = (shared.sourceCache || {})[id]
      var node = shared.graph.nodes[id]
      var record = stateOf(id)
      var anchor = node !== undefined ? node : (record && record.anchor ? record.anchor : null)
      if (source === undefined) {
        return h('div', { className: 'cddl-src' }, h('div', { className: 'cddl-srch' }, '读源码…'))
      }
      if (source === null || source.lines === undefined) return h(SourceMissing, { id: id, engine: props.engine })
      var count = sourceLineCount(source)
      var lines = source.lines.map(function (text, i) {
        var no = source.from + i
        var inside = no >= source.start && no <= source.end
        return h('div', { key: no, className: inside ? 'cddl-hl' : '' }, [
          h('span', { key: 'n', className: 'cddl-ln' }, no),
          h('span', { key: 't', className: 'cddl-code' }, text === '' ? ' ' : text),
        ])
      })
      return h('div', { className: 'cddl-src' }, [
        h('div', { className: 'cddl-srch', key: 'h' }, [
          h('span', { key: 't' }, source.file + ' · ' + (anchor ? anchor.symbol : '') + ' · ' + source.start + '–' + source.end + ' · ' + count + ' 行'),
          h('button', {
            key: 'x', className: 'cddl-src-close', title: '关闭源码详情',
            onClick: function () { props.engine.blur() },
          }, '×'),
        ]),
        h('pre', {
          key: 'p',
          'data-cdd-source-id': source.id || id,
          'data-cdd-source-start': source.start,
          'data-cdd-source-end': source.end,
          'data-cdd-source-lines': count,
        }, lines),
      ])
    }

    /** Every turn that reached this anchor — collapsing a branch never erases it. */
    function History(props) {
      var record = stateOf(shared.selected)
      if (record === undefined || record === null) return null
      return h('div', { className: 'cddl-hist' }, [
        h('h4', { key: 'h' }, '这个 anchor 的经历'),
      ].concat(record.events.map(function (event, i) {
        return h('div', { key: i, className: 'cddl-hrow' + (event.onSurface ? '' : ' cddl-faded') }, [
          h('span', { key: 't', className: 'cddl-t' }, 'T' + event.turn),
          h('span', { key: 'd', className: dotClass({ state: event.working ? 'working' : event.verb === 'edit' ? 'edited' : 'viewed' }) }),
          h('span', { key: 'x' }, event.tool
            + (event.working ? ' · 正在执行' : '')
            + (event.approx ? ' · 行号近似' : '')
            + (event.onSurface ? '' : ' · 已被压缩')),
          event.agent ? h('span', { key: 'a', className: 'cddl-agent' }, event.agent) : null,
          event.reason ? h('span', { key: 'r', className: 'cddl-reason' }, event.reason) : null,
        ])
      })))
    }

    // ---- search ------------------------------------------------------------

    function Search(props) {
      var engine = props.engine
      var q = useState('')
      var timer = useRef(null)
      var onChange = function (e) {
        var value = e.target.value
        q[1](value)
        if (timer.current !== null) clearTimeout(timer.current)
        timer.current = setTimeout(function () { engine.search(value.trim()) }, 180)
      }
      return h('div', { className: 'cddl-search' }, [
        h('input', {
          key: 'i', className: 'cddl-q', placeholder: '搜 anchor…',
          value: q[0], onChange: onChange,
          onClick: function (e) { e.stopPropagation() },
        }),
        shared.hits === null || shared.hits === undefined || q[0].trim().length === 0 ? null
          : h('div', { key: 'r', className: 'cddl-hits' }, shared.hits.length === 0
            ? [h('div', { key: 'n', className: 'cddl-empty' }, '没找到')]
            : shared.hits.map(function (anchor) {
              return h('div', {
                key: anchor.id, className: 'cddl-hit',
                onClick: function () { q[1](''); shared.hits = null; engine.focus(anchor) },
              }, [
                h('span', { key: 's', className: 'cddl-sym' }, anchor.symbol),
                h('span', { key: 'f', className: 'cddl-hitfile' }, short(anchor.file)),
              ])
            })),
      ])
    }

    // ---- legend ------------------------------------------------------------

    function Legend() {
      return h('div', { className: 'cddl-legend' }, [
        h('b', { key: 'v' }, [h('i', { key: 'd', className: 'cddl-dot cddl-v' }), '看过']),
        h('b', { key: 'e' }, [h('i', { key: 'd', className: 'cddl-dot cddl-e' }), '改过']),
        h('b', { key: 'w' }, [h('i', { key: 'd', className: 'cddl-dot cddl-w' }), '正在改']),
        h('b', { key: 'f', style: { opacity: .45 } }, '变淡 = 被 compaction 压缩，模型记不清了'),
      ])
    }

    /**
     * Files the agent opened that this project's index cannot own.
     *
     * Shown, never dropped. A session that opened twenty files over an empty
     * graph reads as a broken plugin; naming the file and the reason is the
     * difference between an honest empty graph and a silent one.
     */
    function Unresolved() {
      var list = shared.unresolved
      if (list === undefined || list.length === 0) return null
      var why = {
        'not-indexed': '不在索引里',
        'no-line': '没有行号',
        'scope': '只是搜索范围',
        'no-index': '该工程没索引',
        'outside': '在本工程之外',
        'no-file': '没有路径',
        'error': '解析失败',
      }
      return h('div', { className: 'cddl-unres' }, [
        h('h4', { key: 'h' }, [
          h('span', { key: 't' }, '碰过，但没落到 anchor'),
          h('span', { key: 'n', className: 'cddl-count' }, list.length),
        ]),
      ].concat(list.slice(0, 12).map(function (entry, i) {
        return h('div', { key: i, className: 'cddl-unrow', title: entry.file }, [
          h('span', { key: 't', className: 'cddl-t' }, 'T' + entry.turns.join(',')),
          h('span', { key: 'f', className: 'cddl-sym' }, short(entry.file)),
          h('span', { key: 'w', className: 'cddl-kind' }, why[entry.reason] || entry.reason),
        ])
      })))
    }

    module.exports = { Source, History, Search, Legend, Unresolved }
    return module.exports
  },
})

// dsh-cdd-lens — The no-index-yet placeholder.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/needIndex',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared

    // ---- no index yet ------------------------------------------------------

    /**
     * A workspace with no index yet.
     *
     * The host already started the build when it answered /context — nothing
     * here asks anyone to run a command. This only reports progress, and offers
     * a retry for the one case that needs a decision: a build that failed.
     */
    function NeedIndex(props) {
      var engine = props.engine
      var context = shared.context
      useEffect(function () {
        var timer = setInterval(function () { engine.reindexStatus() }, 1200)
        return function () { clearInterval(timer) }
      }, [])
      var failed = shared.reindexError !== undefined && shared.reindexError !== null
      return h('div', { className: 'cddl-empty' }, [
        h('div', { key: 'a' }, failed ? '建索引失败：' : '这个工程还没索引，正在建（后台跑，不占聊天）：'),
        h('div', { key: 'b', className: 'cddl-path' }, context ? context.root : ''),
        failed ? h('div', { key: 'e', className: 'cddl-bad' }, shared.reindexError) : null,
        failed
          ? h('button', { key: 'c', className: 'cddl-primary', onClick: function () { engine.reindex() } }, '重试')
          : h('div', { key: 'c', className: 'cddl-progress' },
            shared.reindexing === false && context && !context.indexed ? '启动中…' : '正在建索引…'),
        shared.reindexTail ? h('pre', { key: 'd', className: 'cddl-tail' }, shared.reindexTail) : null,
      ])
    }

    /**
     * Subscribe to this session's conversation-view target.
     *
     * The shell owns the subscription and the paging; this only forwards each
     * snapshot into the graph. There is no interval over session data, so
     * nothing here competes with a streaming turn.
     */

    module.exports = { NeedIndex }
    return module.exports
  },
})

// dsh-cdd-lens — One anchor box.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/node',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __graph_visible = require('dsh-cdd-lens/graph/visible')
    var stickyByRecency = __graph_visible.stickyByRecency
    var __view_record = require('dsh-cdd-lens/view/record')
    var dotClass = __view_record.dotClass
    var stateOf = __view_record.stateOf
    var turnLabel = __view_record.turnLabel
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note

    function GraphNode(props) {
      var engine = props.engine
      var p = props.p
      var zoom = props.zoom || 1
      var drag = useRef(null)
      // node 就是 anchor：不用再走 `.anchor` 那一跳。
      var anchor = p.node
      var ui = uiOf(shared.graph, p.id) || {}
      var record = stateOf(p.id)
      var faded = record !== null && record !== undefined && !record.remembered
      var selected = shared.selected === p.id
      var synthetic = ui.synthetic === true || ui.bridge === true || anchor.hidden === true
      var isClass = !synthetic && (anchor.kind === 'class' || anchor.members > 0)
      // A class and a function are two different things, and the card has to say
      // so in colour rather than in a 1.5px border nobody can see. `kind` rides
      // in on the anchor, so this reads the record instead of guessing.
      var isFn = !synthetic && !isClass

      var head = h('div', { className: 'cddl-gtop' + (isClass ? ' cddl-class-header' : ''), key: 'top' }, [
        h('span', { key: 'd', className: dotClass(record) }),
        h('span', { key: 's', className: 'cddl-sym', title: anchor.id },
          p.label || anchor.symbol.split('.').pop() || anchor.symbol),
        turnLabel(record) === null ? null : React.cloneElement(turnLabel(record), { key: 'b' }),
        isClass ? h('button', {
          key: 'c', className: 'cddl-count',
          title: anchor.members + ' 个成员',
          onClick: function (e) { e.stopPropagation(); engine.members(p.id) },
        }, (ui.members ? '▾ ' : '▸ ') + anchor.members)
          : h('span', { key: 'l', className: 'cddl-lines' }, anchor.line_start + '–' + anchor.line_end),
        isClass ? h('span', { key: 'k', className: 'cddl-kind' }, '类') : null,
      ])

      // 展开按钮按关系挂：anchor.peerCounts 是 worker 给的
      //   { call: {up, down}, inherit: {up, down}, … }
      // 只列出**有数据**的关系——某个关系是 0 就不在这里出现，不画箭头也不写数字。
      var REL_LABEL = {
        call: '调用', dataflow: '数据流', inherit: '继承',
        dispatch: '分派', impact: '影响',
      }
      var REL_ORDER = ['call', 'dataflow', 'inherit', 'dispatch', 'impact']
      var counts = anchor.peerCounts || {}

      function hopButton(direction, rel) {
        var n = counts[rel][direction]
        var slot = direction + ':' + rel
        var open = ui.open[slot] === true
        var arrow = direction === 'up' ? '↑' : '↓'
        var verb = direction === 'up' ? '谁在用它' : '它在用谁'
        return h('button', {
          key: slot,
          title: REL_LABEL[rel] + ' · ' + verb + '（' + n + '）'
            + '\n点一下：展开/收起一层'
            + '\n按住 Shift 点：一路展开到底（链式）',
          className: 'cddl-action-' + direction + ' cddl-rel-' + rel + (open ? ' on' : ''),
          'data-action': direction === 'up' ? 'expand-callers' : 'expand-callees',
          'data-relation': rel,
          'data-count': n,
          onClick: function (e) {
            e.stopPropagation()
            note('btn', '按下 ' + (direction === 'up' ? '↑' : '↓') + rel
              + ' count=' + n + (open ? ' [收起]' : '')
              + ' 节点=' + String(p.id).split('::').pop())
            if (open) { engine.collapse(p.id, direction, rel); return }
            if (e.shiftKey) engine.walk(p.id, direction, rel, 4)
            else engine.expand(p.id, direction, null, rel)
          },
        }, [
          h('span', { key: 'a', className: 'cddl-rel-arrow' }, arrow),
          h('span', { key: 'n', className: 'cddl-rel-count' }, n),
          h('span', { key: 'r', className: 'cddl-rel-name' }, rel),
        ])
      }

      var hopButtons = []
      REL_ORDER.forEach(function (rel) {
        var c = counts[rel]
        if (c === undefined) return
        // 上行在左、下行在右，同一关系两个方向挨着，颜色一致。
        if (c.up > 0) hopButtons.push(hopButton('up', rel))
        if (c.down > 0) hopButtons.push(hopButton('down', rel))
      })

      var actions = synthetic
        ? h('div', { key: 'h', className: 'cddl-node-actions cddl-node-actions-bridge' }, [
          h('span', {
            key: 'b', className: 'cddl-kind cddl-bridgetag',
            title: '它只是把两个真实 anchor 连起来的中间点，不参与继续展开。',
          }, '桥'),
        ])
        :
        h('div', { key: 'h', className: 'cddl-node-actions' }, hopButtons.concat([
          h('button', {
            key: 'p',
            title: ui.pinned
              ? '取消固定'
              : (stickyByRecency(p.id)
                ? '最近碰过，自动保留三轮；点一下改为永久固定'
                : '固定：折叠上级时也留在图上'),
            className: 'cddl-action-pin' + (ui.pinned ? ' on' : (stickyByRecency(p.id) ? ' auto' : '')),
            'data-action': 'pin-anchor',
            onClick: function (e) { e.stopPropagation(); engine.pin(p.id) },
          }, 'pin'),
        ]))

      var members = null
      if (!synthetic && ui.members && ui.memberList !== undefined) {
        members = h('div', { className: 'cddl-members', key: 'm' },
          ui.memberList.map(function (member) {
            var mrec = stateOf(member.id)
            return h('div', {
              key: member.id,
              className: 'cddl-m' + (shared.selected === member.id ? ' cddl-sel' : ''),
              title: member.id,
              'data-anchor-id': member.id,
              onClick: function (e) { e.stopPropagation(); engine.select(member.id) },
            }, [
              h('span', { key: 'd', className: dotClass(mrec) }),
              h('span', { key: 's', className: 'cddl-sym' }, member.symbol.split('.').pop()),
              turnLabel(mrec) === null ? null : React.cloneElement(turnLabel(mrec), { key: 'b' }),
              h('span', { key: 'l', className: 'cddl-lines' }, member.start + '–' + member.end),
            ])
          }).concat([h('div', { key: 'more', className: 'cddl-more' }, '共 ' + ui.memberList.length + ' 个方法')]))
      }

      // 同一张卡片用在两处：画布上定位的，和轨迹栏里顺着流排的。只有位置不同，
      // 所以只切这一个标记——另写一个组件迟早会和这个跑偏。
      var flow = props.flow === true
      // 出入口各一个小圈：**入在左、出在右，不同口**。线从左边的小圈进、
      // 从右边的小圈出，两头都停在圈上——线必须明显连到圈上，不许悬空。
      //
      // 以前这里是 24×20 的方块角标，里面写「入」「出」两个字，而且入出可以
      // 落在同一条边（role='both'）上；那样两个方向挤在一个口，看不出谁进谁出。
      var vertical = p.flowAxis === 'vertical'
      var portViews = [
        h('span', {
          key: 'port-in',
          className: 'cddl-port cddl-port-in' + (vertical ? ' cddl-port-vtop' : ''),
          'data-port': 'in',
          title: '关系进入此 Anchor',
        }),
        h('span', {
          key: 'port-out',
          className: 'cddl-port cddl-port-out' + (vertical ? ' cddl-port-vbottom' : ''),
          'data-port': 'out',
          title: '关系离开此 Anchor',
        }),
      ]
      return h('div', {
        className: 'cddl-node-shell' + (p.island ? ' cddl-shell-island' : '')
          + (flow ? ' cddl-node-flow' : ''),
        style: flow
          ? { width: p.w + 'px' }
          : { left: p.x + 'px', top: p.y + 'px', width: p.w + 'px' },
        'data-node-id': p.id,
        // What this node believes about itself, readable from the outside. A
        // button that does not light up after it worked is indistinguishable
        // from one that did nothing, and guessing which was costing more than
        // the attribute does.
        // 有哪些「方向:关系」开着，供外部测试读。以前只报 up/down 两个方向，
        // 现在每个关系各开各的，所以按 key 全列出来。
        'data-open': Object.keys(ui.open).filter(function (k) {
          return ui.open[k] === true && k.indexOf('auto') !== 0
        }).sort().join(' ') || 'none',
      }, [
        portViews,
        h('div', {
          key: 'n',
          className: 'cddl-gnode'
            + (shared.lit === null || shared.lit === undefined ? ''
              : (shared.lit.nodes[p.id] === true ? ' cddl-lit' : ' cddl-unlit'))
            + (selected ? ' cddl-sel' : '')
            + (faded ? ' cddl-faded' : '')
            + (ui.island ? ' cddl-island' : '')
            + (synthetic ? ' cddl-bridge' : '')
            + (isClass ? ' cddl-cls cddl-class' : '')
            + (isFn ? ' cddl-fn' : ''),
          title: anchor.id,
          'data-anchor-id': anchor.id,
          onPointerDown: function (event) {
            if (event.button !== 0) return
            if (event.target.closest && event.target.closest('button')) return
            event.preventDefault()
            event.stopPropagation()
            // Drag in the coordinates a position is SAVED in, not the ones it
            // is drawn at. The drawing may have been moved to make room for
            // wires; folding that margin into the stored position would move
            // the node again on the next render, and again after that.
            var baseX = p.baseX === undefined ? p.x : p.baseX
            var baseY = p.baseY === undefined ? p.y : p.baseY
            var start = { clientX: event.clientX, clientY: event.clientY, x: baseX, y: baseY }
            var latest = { x: baseX, y: baseY }
            var moved = false
            drag.current = start
            var move = function (e) {
              var dx = (e.clientX - start.clientX) / zoom
              var dy = (e.clientY - start.clientY) / zoom
              if (!moved && Math.abs(dx) + Math.abs(dy) < 4) return
              moved = true
              latest = { x: Math.max(4, start.x + dx), y: Math.max(4, start.y + dy) }
              engine.moveNode(p.id, latest, false)
            }
            var up = function () {
              drag.current = null
              window.removeEventListener('pointermove', move)
              window.removeEventListener('pointerup', up)
              if (moved) engine.moveNode(p.id, latest, true)
              else { engine.select(p.id); engine.lightNode(p.id) }
            }
            window.addEventListener('pointermove', move)
            window.addEventListener('pointerup', up)
          },
        }, [
          // No path line here: the box header already names the file, and
          // repeating it inside every node was what squeezed the symbol into an
          // ellipsis. Hover still shows the fully qualified id.

          head,
          // The controls live in the card, on their own line under the name.
          // Floating them above it meant they overlapped whatever sat there,
          // and a node's own buttons reading as another node's is worse than
          // the two pixels of height they cost.
          actions,
          members,
          record && record.state === 'working'
            ? h('div', { key: 'w', className: 'cddl-working' },
              ((record.events[record.events.length - 1] || {}).agent || 'Agent') + ' working · '
                + ((record.events[record.events.length - 1] || {}).reason || '正在处理此 Anchor'))
            : null,
        ]),
      ])
    }

    /**
     * A horizontal scrollbar of our own, pinned to the bottom of the canvas.
     *
     * `scrollbar-gutter` reserves the vertical gutter and has no horizontal
     * counterpart, and this platform's native horizontal bar is an overlay: it
     * occupies no layout space and fades out when idle. So a drawing that
     * genuinely scrolls sideways reads as one that cannot, and the only way to
     * discover otherwise is to try. Drawn explicitly, the axis is simply there.
     */

    module.exports = { GraphNode }
    return module.exports
  },
})

// dsh-cdd-lens — The canvas horizontal scrollbar.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/hscroll',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef

    function HScroll(props) {
      var state = useState({ overflow: 0, ratio: 0, left: 0 })
      var st = state[0]
      var set = state[1]
      var dragging = useRef(null)

      useEffect(function () {
        var read = function () {
          var el = props.canvasRef.current
          if (el === null || el === undefined) return
          var overflow = el.scrollWidth - el.clientWidth
          var next = {
            overflow: overflow,
            ratio: overflow <= 0 ? 0 : el.clientWidth / el.scrollWidth,
            left: overflow <= 0 ? 0 : el.scrollLeft / overflow,
          }
          set(function (before) {
            if (before.overflow === next.overflow
              && Math.abs(before.left - next.left) < .002) return before
            return next
          })
        }
        read()
        var el = props.canvasRef.current
        if (el !== null && el !== undefined) el.addEventListener('scroll', read)
        var timer = setInterval(read, 250)
        return function () {
          clearInterval(timer)
          if (el !== null && el !== undefined) el.removeEventListener('scroll', read)
        }
      }, [props.width, props.zoom])

      if (st.overflow <= 2) return null

      var onDown = function (e) {
        var el = props.canvasRef.current
        if (el === null) return
        var track = e.currentTarget.getBoundingClientRect()
        var jump = function (clientX) {
          var frac = Math.min(1, Math.max(0, (clientX - track.left) / track.width))
          el.scrollLeft = frac * (el.scrollWidth - el.clientWidth)
        }
        jump(e.clientX)
        var move = function (ev) { jump(ev.clientX) }
        var up = function () {
          window.removeEventListener('pointermove', move)
          window.removeEventListener('pointerup', up)
        }
        window.addEventListener('pointermove', move)
        window.addEventListener('pointerup', up)
      }

      return h('div', { className: 'cddl-hscroll', onPointerDown: onDown, title: '横向滚动' },
        h('div', {
          className: 'cddl-hscroll-thumb',
          style: {
            width: Math.max(8, st.ratio * 100) + '%',
            left: (st.left * (100 - Math.max(8, st.ratio * 100))) + '%',
          },
        }))
    }

    module.exports = { HScroll }
    return module.exports
  },
})

// dsh-cdd-lens — Edge kinds, the line-focus camera, and the layout it derives.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/camera',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared

    // ---- the spread-out graph (conversation.view) ---------------------------
    //
    // A layered layout: callers above the selection, callees below, one row per
    // hop, orthogonal wires. Positions are computed from measured text rather
    // than a physics simulation — a node must not drift when a sibling expands.

    var CHAR = 6.9
    var ROW = 126
    var GAPX = 26
    var MAX_PER_ROW = 4

    function edgeHasType(edge, type) {
      return (edge.types || []).indexOf(type) >= 0
    }

    function dependencyEdge(edge) {
      return !edgeHasType(edge, 'dataflow')
        || (edge.types || []).some(function (type) { return type !== 'dataflow' })
    }

    /** Nodes/edges shown by the temporary line-focus camera. */
    function edgeFocusOf(graph) {
      var wanted = shared.edgeFocus
      if (wanted === null || wanted === undefined) return null
      var ids = {}
      var keys = {}
      ids[wanted.from] = true
      ids[wanted.to] = true
      keys[wanted.from + '→' + wanted.to + ':' + wanted.type] = true

      if (wanted.type === 'dataflow') {
        // A data value is followed end to end. Both directions are visited so
        // clicking the middle of a producer/consumer chain still reveals its
        // origin and every eventual consumer.
        var queue = [wanted.from, wanted.to]
        while (queue.length > 0) {
          var current = queue.shift()
          graph.edges.forEach(function (edge) {
            if (!edgeHasType(edge, 'dataflow')) return
            if (edge.from !== current && edge.to !== current) return
            keys[edge.from + '→' + edge.to + ':dataflow'] = true
            ;[edge.from, edge.to].forEach(function (id) {
              if (ids[id]) return
              ids[id] = true
              queue.push(id)
            })
          })
        }
      } else {
        var walk = function (start, direction) {
          var frontier = [start]
          for (var hop = 0; hop < 3; hop += 1) {
            var next = []
            frontier.forEach(function (current) {
              graph.edges.forEach(function (edge) {
                if (!dependencyEdge(edge)) return
                var matches = direction === 'up' ? edge.to === current : edge.from === current
                if (!matches) return
                var id = direction === 'up' ? edge.from : edge.to
                ;(edge.types || ['call']).forEach(function (type) {
                  if (type !== 'dataflow') keys[edge.from + '→' + edge.to + ':' + type] = true
                })
                if (!ids[id]) { ids[id] = true; next.push(id) }
              })
            })
            frontier = next
          }
        }
        walk(wanted.from, 'up')
        walk(wanted.to, 'down')
      }
      return { ids: ids, keys: keys, type: wanted.type }
    }

    /**
     * @param avail - the canvas viewport's real width in CSS pixels. Everything
     *   that decides how wide the drawing gets is derived from it. The previous
     *   version divided a hardcoded 1580 to choose the column count, which is a
     *   viewport that does not exist here: the canvas actually gets about 977
     *   (the window minus dsh's sidebar, minus the space reserved for a
     *   neighbouring plugin's rail, minus this view's own source column). So the
     *   layout produced a drawing wider than the space it had, and no amount of
     *   font or routing work could make that readable.
     */
    /**
     * Temporary camera layout: a top-to-bottom relationship chain.
     *
     * It never writes shared.nodePositions, so leaving the camera restores
     * every user coordinate exactly.
     * @param graph - the graph being drawn.
     * @param scope - what is on screen.
     * @param place - the boxes and nodes already positioned.
     * @param rank - relationship ranking for this graph.
     * @param metrics - box metrics for this canvas.
     */
    function cameraLayout(graph, scope, place, rank, metrics) {
      var activeFocus = scope.activeFocus
      var included = scope.included
      var placed = place.placed
      var indegree = rank.indegree
      var NODE_W = metrics.NODE_W
      var PAD = metrics.PAD

      if (activeFocus === null) {
        // Auto-layout provides first positions only. Once the user moves an
        // anchor, that coordinate wins across refresh, expansion and reindex.
        placed.forEach(function (p) {
          var point = shared.nodePositions[p.id]
          if (point === undefined) return
          p.x = point.x
          p.y = point.y
          // Marked, because everything downstream has to tell a coordinate the
          // user chose from one the layout produced: which box yields when two
          // collide, and which one may be pulled back when it ends up stranded.
          p.manual = true
        })
      } else {
        // Temporary camera layout. It derives a top-to-bottom relationship
        // chain: every caller/callee step flips the node's in/out side.
        // without touching shared.nodePositions, so exit restores every user
        // coordinate exactly.
        var focusedEdges = []
        graph.edges.forEach(function (edge) {
          ;(edge.types || ['call']).forEach(function (type) {
            var key = edge.from + '→' + edge.to + ':' + type
            if (activeFocus.keys[key]) focusedEdges.push({ from: edge.from, to: edge.to, type: type })
          })
        })
        var indegree = {}
        included.forEach(function (id) { indegree[id] = 0 })
        focusedEdges.forEach(function (edge) {
          if (indegree[edge.to] !== undefined && indegree[edge.from] !== undefined) indegree[edge.to] += 1
        })
        var depthById = {}
        var queue = included.filter(function (id) { return indegree[id] === 0 })
        if (queue.length === 0 && shared.edgeFocus) queue.push(shared.edgeFocus.from)
        queue.forEach(function (id) { depthById[id] = 0 })
        while (queue.length > 0) {
          var current = queue.shift()
          focusedEdges.forEach(function (edge) {
            if (edge.from !== current || depthById[edge.to] !== undefined) return
            depthById[edge.to] = depthById[current] + 1
            queue.push(edge.to)
          })
        }
        var nextDepth = 0
        included.forEach(function (id) {
          if (depthById[id] === undefined) depthById[id] = nextDepth++
        })
        var levels = {}
        placed.forEach(function (p) {
          var level = depthById[p.id] || 0
          ;(levels[level] = levels[level] || []).push(p)
        })
        Object.keys(levels).sort(function (l, r) { return Number(l) - Number(r) }).forEach(function (level) {
          levels[level].forEach(function (p, row) {
            p.x = PAD + 46 + row * (NODE_W + 76)
            p.y = PAD + 46 + Number(level) * (Math.max(72, p.h) + 62)
          })
        })
      }

    }

    module.exports = { CHAR, ROW, GAPX, MAX_PER_ROW, edgeHasType, dependencyEdge, edgeFocusOf, cameraLayout }
    return module.exports
  },
})

// dsh-cdd-lens — What gets drawn, in what order, and which way round.
//
// Everything decided before a coordinate exists: which nodes are on screen,
// which file each column belongs to and in what order, and which side of a
// node its wires enter and leave by. Three questions, one answer set, and no
// skin can place anything until all three are settled.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/prep',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __graph_visible = require('dsh-cdd-lens/graph/visible')
    var visibleForMode = __graph_visible.visibleForMode
    var __layout_camera = require('dsh-cdd-lens/layout/camera')
    var edgeFocusOf = __layout_camera.edgeFocusOf
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf

    /**
     * What is on screen at all, and which file each anchor belongs to.
     */
    function layoutScope(graph, modeOverride) {

      var shown = visibleForMode(graph, modeOverride)

      // A file is the first visual unit. Session-touched anchors are always
      // present; manual +/- exploration may add more anchors and therefore a
      // new file box, while bridge-only implementation details stay hidden.
      var included = graph.order.filter(function (id) {
        var node = graph.nodes[id]
        var ui = uiOf(graph, id)
        return shown[id] && node !== undefined && ui !== null
          && (ui.session || ui.explored || ui.pinned || id === shared.selected || id === graph.rootId)
      })
      var mode = modeOverride || shared.treeMode || 'all'
      if (included.length === 0 && mode === 'all' && graph.nodes[graph.rootId]) included.push(graph.rootId)
      var activeFocus = modeOverride === undefined ? edgeFocusOf(graph) : null
      if (activeFocus !== null) {
        included = graph.order.filter(function (id) {
          return activeFocus.ids[id] === true && graph.nodes[id] !== undefined
        })
      }
      var byFile = {}
      var fileOrder = []
      included.forEach(function (id) {
        var file = graph.nodes[id].file
        if (byFile[file] === undefined) { byFile[file] = []; fileOrder.push(file) }
        byFile[file].push(id)
      })
      return { shown: shown, included: included, activeFocus: activeFocus, byFile: byFile, fileOrder: fileOrder }
    }

    /**
     * Relationship order, not source-line order and not row parity.
     */
    function rankFiles(graph, relationFilter, scope) {
      var included = scope.included
      var byFile = scope.byFile
      var fileOrder = scope.fileOrder

      // Relationship order, not source-line order and not row parity. Start at
      // a visible main (when present), then the session root, then every other
      // component. Each real caller -> callee edge advances one relationship
      // step. Cycles are harmless because a node is ranked only once.
      var includedSet = {}
      included.forEach(function (id) { includedSet[id] = true })
      var relationEdges = graph.edges.filter(function (edge) {
        if (!includedSet[edge.from] || !includedSet[edge.to]) return false
        return (edge.types || ['call']).some(function (type) {
          return relationFilter === undefined || relationFilter[type] !== false
        })
      })
      var outgoing = {}
      var indegree = {}
      included.forEach(function (id) { outgoing[id] = []; indegree[id] = 0 })
      relationEdges.forEach(function (edge) {
        outgoing[edge.from].push(edge.to)
        indegree[edge.to] += 1
      })
      var relationRank = {}
      var rankQueue = []
      var nextComponentRank = 0
      var rankFrom = function (seed) {
        if (!includedSet[seed] || relationRank[seed] !== undefined) return
        relationRank[seed] = nextComponentRank
        rankQueue.push(seed)
        while (rankQueue.length > 0) {
          var current = rankQueue.shift()
          outgoing[current].forEach(function (next) {
            if (relationRank[next] !== undefined) return
            relationRank[next] = relationRank[current] + 1
            rankQueue.push(next)
          })
        }
        nextComponentRank = Math.max.apply(Math, Object.keys(relationRank).map(function (id) { return relationRank[id] })) + 2
      }
      included.filter(function (id) {
        return graph.nodes[id].symbol.split && graph.nodes[id].symbol.split('.').pop() === 'main'
      }).forEach(rankFrom)
      rankFrom(graph.rootId)
      included.filter(function (id) { return indegree[id] === 0 }).forEach(rankFrom)
      included.forEach(rankFrom)

      // A file box follows the earliest relationship step of the anchors it
      // contains. The box is a visual boundary only; it no longer invents the
      // semantic order of nodes inside it.
      var depth = {}
      fileOrder.forEach(function (file) {
        depth[file] = Math.min.apply(Math, byFile[file].map(function (id) { return relationRank[id] }))
      })
      var arrival = {}
      fileOrder.forEach(function (file, i) { arrival[file] = i })
      fileOrder.sort(function (l, r) { return depth[l] - depth[r] || arrival[l] - arrival[r] })

      fileOrder.forEach(function (file) {
        byFile[file].sort(function (l, r) {
          var la = graph.nodes[l]
          var ra = graph.nodes[r]
          var lm = la.symbol.split('.').pop() === 'main' ? 0 : 1
          var rm = ra.symbol.split('.').pop() === 'main' ? 0 : 1
          return relationRank[l] - relationRank[r] || lm - rm
            || (la.line_start || 0) - (ra.line_start || 0) || la.symbol.localeCompare(ra.symbol)
        })
      })

      return { indegree: indegree, relationRank: relationRank }
    }

    /**
     * In/out sides propagated by real relations, not by row number.
     */
    function orientFlow(graph, scope, place, metrics, avail) {
      var included = scope.included
      var placed = place.placed
      var fileBoxes = place.fileBoxes
      var canvasY = place.canvasY
      var PAD = metrics.PAD
      var BOX_GAP_Y = metrics.BOX_GAP_Y
      var canvasWidth = metrics.canvasWidth

      var byId = {}
      placed.forEach(function (p) { byId[p.id] = p })

      // The alternating in/out sides this used to compute are gone: every box
      // is laid in the same grid and every port is on a side, so a node that
      // flipped put its entry where its callers leave from. The walk that
      // produced them is gone with them — it re-scanned every edge for every
      // node it reached, which is O(nodes x edges) and was the single most
      // expensive thing in a layout whose result was then overwritten.
      placed.forEach(function (p) { p.flowDir = 'ltr' })
      var boxOf = {}
      fileBoxes.forEach(function (box) { boxOf[box.file] = box })
      canvasWidth = Math.max(avail || 0, PAD * 2 + Math.max.apply(Math, placed.map(function (p) { return p.x + p.w })))
      canvasY = PAD + Math.max.apply(Math, placed.map(function (p) { return p.y + p.h })) + BOX_GAP_Y

      return { byId: byId, boxOf: boxOf, canvasWidth: canvasWidth, canvasY: canvasY }
    }

    module.exports = { layoutScope, rankFiles, orientFlow }
    return module.exports
  },
})

// dsh-cdd-lens — Stylesheet: the drawing itself.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/styles/graph',
  factory: (require) => {
    var module = { exports: {} }

    /** Canvas, nodes, wires, ports and file boxes. */
    var GRAPH_CSS = [
      '.cddl-stage{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:minmax(0,1fr) auto;position:relative}',
      '.cddl-canvaswrap{grid-column:1;grid-row:1;position:relative;overflow:auto;scrollbar-gutter:stable;background:radial-gradient(circle at 1px 1px, var(--dsw-alias-border-l1) 1px, transparent 0) 0 0/22px 22px,var(--dsw-alias-bg-base)}',
      '.cddl-stage-inner{position:relative;min-width:100%;min-height:100%}',
      '.cddl-canvasbody{position:relative;min-width:100%;min-height:100%}',
      '.cddl-canvaswrap::-webkit-scrollbar{width:12px;height:12px}',
      '.cddl-hscroll{grid-column:1;grid-row:2;align-self:end;position:relative;height:12px;margin:0 2px 2px;border-radius:6px;background:var(--dsw-alias-scrollbar-bg-l2,rgba(127,127,127,.10));cursor:pointer;z-index:3}',
      '.cddl-hscroll-thumb{position:absolute;top:2px;bottom:2px;border-radius:5px;background:var(--dsw-alias-border-l4);pointer-events:none}',
      '.cddl-hscroll:hover .cddl-hscroll-thumb{background:var(--dsw-alias-label-caption)}',
      '.cddl-canvaswrap::-webkit-scrollbar-track{background:var(--dsw-alias-scrollbar-bg-l2,rgba(127,127,127,.08))}',
      '.cddl-canvaswrap::-webkit-scrollbar-thumb{background:var(--dsw-alias-border-l4);border-radius:7px;border:3px solid transparent;background-clip:content-box}',
      '.cddl-canvaswrap::-webkit-scrollbar-thumb:hover{background:var(--dsw-alias-scrollbar-hover-l2,var(--dsw-alias-label-caption));background-clip:content-box}',
      '.cddl-canvaswrap::-webkit-scrollbar-corner{background:transparent}',
      '.cddl-scaler{position:relative;min-width:100%;min-height:100%}',
      '.cddl-canvas{position:relative;transition:transform .14s ease}',
      '.cddl-scroll{overflow:auto;height:100%}',
      '.cddl-frame{width:100%;height:100%;min-height:320px;border:0;background:#fff;display:block}',
      '.cddl-wires{position:absolute;left:0;top:0;pointer-events:none}',
      '.cddl-wire{fill:none;stroke:var(--dsw-alias-state-business-primary);stroke-width:1.65;opacity:.78;stroke-linecap:round;stroke-linejoin:round}',
      '.cddl-wire-hit{fill:none;stroke:transparent;stroke-width:18;pointer-events:stroke;cursor:pointer}',
      '.cddl-wire.cddl-dataflow{stroke:var(--dsw-alias-state-warn-primary);stroke-dasharray:4 3}',
      '.cddl-wire.cddl-inherit{stroke:var(--dsw-alias-label-tertiary);stroke-dasharray:1 3}',
      '.cddl-wire.cddl-dispatch{stroke-dasharray:7 3}',
      '.cddl-wire.cddl-impact{stroke-dasharray:2 4}',
      '.cddl-wire.cddl-faded{stroke:var(--dsw-alias-border-l1)}',
      '#cddl-arrow path{fill:var(--dsw-alias-state-business-primary)}',
      '#cddl-arrow-faded path{fill:var(--dsw-alias-border-l1)}',
      '.cddl-edge-label{font-family:var(--ds-font-family-code,monospace);font-size:9px;fill:var(--dsw-alias-label-dimmed);paint-order:stroke;stroke:var(--dsw-alias-bg-base);stroke-width:3px}',
      '.cddl-rowlabels{position:absolute;inset:0;pointer-events:none}',
      '.cddl-rowlabel{position:absolute;left:16px;font-size:9.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--dsw-alias-label-dimmed);font-family:var(--ds-font-family-code,monospace)}',
      '.cddl-rowlabel.cddl-island-label{padding-top:8px;border-top:1px dashed var(--dsw-alias-border-l2);right:16px}',
      '.cddl-chips{position:absolute;inset:0;pointer-events:none}',
      '.cddl-chip{position:absolute;padding:2px 8px;border-radius:999px;border:1px dashed var(--dsw-alias-border-l3);background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-caption);font-size:9.5px;font-family:var(--ds-font-family-code,monospace)}',
      '.cddl-fileboxes{position:absolute;inset:0;pointer-events:none}',
      '.cddl-arrowhead{fill:var(--dsw-alias-state-business-primary);stroke:none}',
      '.cddl-arrowhead.cddl-dataflow{fill:var(--dsw-alias-state-warn-primary)}',
      '.cddl-arrowhead.cddl-dispatch{fill:var(--dsw-alias-state-success-primary)}',
      '.cddl-arrowhead.cddl-faded{fill:var(--dsw-alias-border-l3)}',
      '.cddl-action-pin{font-family:var(--dsw-font-family,inherit);letter-spacing:.02em}',
      '.cddl-action-pin.on{color:var(--dsw-alias-state-warn-primary);border-color:var(--dsw-alias-state-warn-primary)}',
      '.cddl-action-pin.auto{color:var(--dsw-alias-state-business-primary);border-style:dashed}',
      '.cddl-junction{fill:var(--dsw-alias-label-primary);stroke:var(--dsw-alias-bg-base);stroke-width:1.2}',
      '.cddl-wire.cddl-hot{stroke-width:2.9;opacity:1}',
      '.cddl-wire.cddl-cold{opacity:.12}',
      '.cddl-arrowhead.cddl-hot{opacity:1}',
      '.cddl-arrowhead.cddl-cold{opacity:.22}',
      '.cddl-filebox{position:absolute;box-sizing:border-box;border:2px dashed var(--dsw-alias-border-l4);border-radius:14px;background:color-mix(in srgb,var(--dsw-alias-bg-layer-2) 34%,transparent)}',
      '.cddl-filebox strong{position:absolute;left:14px;top:10px;max-width:390px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:700 12px var(--ds-font-family-code,monospace);color:var(--dsw-alias-label-primary)}',
      '.cddl-filebox span{position:absolute;right:14px;top:10px;font:10px var(--ds-font-family-code,monospace);color:var(--dsw-alias-label-caption)}',
      // The flow skin's column guide: a hairline and a quiet label, no fill.
      // A frame that reads as a box is the board skin's claim that these
      // anchors belong together; a column says only how deep the chain is, and
      // drawing it as a box is what made the two skins indistinguishable.
      '.cddl-flowbox{border-width:1px;border-color:var(--dsw-alias-border-l2);border-radius:9px;background:transparent}',
      '.cddl-flowbox strong{font-weight:500;color:var(--dsw-alias-label-caption)}',
      '.cddl-flowbox span{display:none}',
      // The node layer is painted after the wires and spans the whole canvas,
      // so without this it swallowed every click meant for a wire — the hit
      // areas were there and unreachable. Only the cards take the mouse.
      '.cddl-nodes{position:relative;pointer-events:none}',
      '.cddl-node-shell{pointer-events:auto}',
      // DSH owns overlay layer 20. Keep the persistent rail below that layer,
      // while its reserved #root margin keeps it visible beside normal Chat.
      '.cddl-trajectory{position:fixed;right:0;top:var(--cddl-trajectory-top,0);bottom:0;z-index:var(--cddl-trajectory-layer,18);box-sizing:border-box;pointer-events:auto;display:flex;flex-direction:column;min-width:280px;max-width:520px;color:var(--dsw-alias-label-primary);background:var(--dsw-alias-bg-layer-1);border-left:1px solid var(--dsw-alias-border-l3);box-shadow:-8px 0 24px rgba(0,0,0,.16);font-family:var(--dsw-font-family,inherit)}',
      '.cddl-trajectory-resize{position:absolute;left:-6px;top:0;bottom:0;width:12px;cursor:ew-resize;z-index:5}',
      '.cddl-trajectory-resize:hover{background:color-mix(in srgb,var(--dsw-alias-state-business-primary) 24%,transparent)}',
      '.cddl-trajectory-head{height:56px;box-sizing:border-box;display:flex;align-items:center;gap:10px;padding:8px 12px;border-bottom:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-2);flex:none}',
      '.cddl-trajectory-head>div{min-width:0;display:flex;flex:1;flex-direction:column;gap:1px}',
      '.cddl-trajectory-head strong{font-size:14px;line-height:18px}',
      '.cddl-trajectory-head span{font-size:10px;color:var(--dsw-alias-label-caption);white-space:nowrap}',
      '.cddl-trajectory-head button{border:1px solid var(--dsw-alias-border-l3);border-radius:6px;background:var(--dsw-alias-bg-layer-3);color:var(--dsw-alias-label-secondary);font:11px inherit;padding:4px 8px;cursor:pointer}',
      '.cddl-trajectory-head button:hover{color:var(--dsw-alias-label-primary);border-color:var(--dsw-alias-state-business-primary)}',
      '.cddl-trajectory-toggle{display:block}',
      // One name for the shut width instead of the same number repeated at
      // every place that has to agree with it.
      '.cddl-trajectory{--cddl-rail-shut:2.75rem}',
      '.cddl-trajectory.is-collapsed{width:var(--cddl-rail-shut)!important;min-width:var(--cddl-rail-shut);max-width:var(--cddl-rail-shut)}',
      '.cddl-trajectory.is-collapsed .cddl-trajectory-resize,.cddl-trajectory.is-collapsed .cddl-trajectory-body,.cddl-trajectory.is-collapsed .cddl-trajectory-head>div,.cddl-trajectory.is-collapsed .cddl-trajectory-graph{display:none}',
      '.cddl-trajectory.is-collapsed .cddl-trajectory-head{height:100%;padding:12px 5px;align-items:flex-start;justify-content:center}',
      '.cddl-trajectory.is-collapsed .cddl-trajectory-toggle{display:block;align-self:stretch;margin:0;width:calc(var(--cddl-rail-shut) - .5rem);height:100%;padding:10px 4px;writing-mode:vertical-rl;letter-spacing:.15em;background:var(--dsw-alias-bg-layer-3)}',
      '.cddl-trajectory-body{flex:1;min-height:0;overflow:auto;scrollbar-gutter:stable;padding:8px 9px 24px}',
      '.cddl-trajectory-empty{padding:24px 12px;color:var(--dsw-alias-label-tertiary);font-size:12px;line-height:1.7}',
      '.cddl-trace-turn{position:relative;margin-bottom:10px;border:1px solid var(--dsw-alias-border-l2);border-radius:9px;overflow:hidden;background:var(--dsw-alias-bg-layer-2)}',
      '.cddl-trace-turn.is-current{border-color:var(--dsw-alias-state-business-primary);box-shadow:0 0 0 1px color-mix(in srgb,var(--dsw-alias-state-business-primary) 22%,transparent)}',
      '.cddl-trace-turn-head{width:100%;height:31px;display:flex;align-items:center;gap:8px;padding:0 9px;border:0;border-bottom:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-3);cursor:pointer;color:inherit}',
      '.cddl-trace-turn-head b{font:700 10px var(--ds-font-family-code,ui-monospace,monospace);letter-spacing:.06em}',
      '.cddl-trace-turn-head span{font-size:9.5px;color:var(--dsw-alias-label-caption)}',
      '.cddl-trace-turn-head span:last-child{margin-left:auto;opacity:0}',
      '.cddl-trace-turn-head:hover span:last-child,.cddl-trace-turn-head[aria-current="true"] span:last-child{opacity:1}',
      '.cddl-trace-turn-head[aria-current="true"] b{color:var(--dsw-alias-state-business-primary)}',
      '.cddl-trace-steps{padding:6px 7px 8px}',
      '.cddl-trace-turn-empty{padding:9px 8px;color:var(--dsw-alias-label-caption);font-size:10.5px;text-align:center}',
      '.cddl-trace-step{display:grid;grid-template-columns:43px minmax(0,1fr);gap:6px;position:relative}',
      '.cddl-trace-step+.cddl-trace-step{margin-top:5px}',
      '.cddl-trace-step-label{padding-top:8px;text-align:right;font:700 8.5px var(--ds-font-family-code,ui-monospace,monospace);color:var(--dsw-alias-label-dimmed);letter-spacing:.04em}',
      '.cddl-trace-step-rows{display:flex;flex-direction:column;gap:4px;min-width:0}',
      '.cddl-trace-anchor{border:1px solid var(--dsw-alias-border-l2);border-radius:7px;overflow:hidden;background:var(--dsw-alias-bg-layer-1)}',
      '.cddl-trace-anchor.is-open{border-color:var(--dsw-alias-border-l4)}',
      '.cddl-trace-anchor-main{width:100%;min-height:31px;display:grid;grid-template-columns:12px 8px minmax(0,1fr) auto;align-items:center;gap:6px;padding:5px 7px;border:0;background:transparent;color:inherit;cursor:pointer;text-align:left}',
      '.cddl-trace-anchor-main:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-trace-chevron{font-size:10px;color:var(--dsw-alias-label-caption)}',
      '.cddl-trace-dot{width:7px;height:7px;border-radius:50%;background:var(--dsw-alias-state-business-primary)}',
      '.cddl-trace-edited .cddl-trace-dot{background:var(--dsw-alias-state-warn-primary)}',
      '.cddl-trace-working .cddl-trace-dot{background:var(--dsw-alias-state-error-primary);box-shadow:0 0 0 3px color-mix(in srgb,var(--dsw-alias-state-error-primary) 22%,transparent)}',
      '.cddl-trace-label{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:11px var(--ds-font-family-code,ui-monospace,monospace);color:var(--dsw-alias-label-secondary)}',
      '.cddl-trace-state{font-size:9px;color:var(--dsw-alias-label-caption);white-space:nowrap}',
      '.cddl-trace-edited .cddl-trace-state{color:var(--dsw-alias-state-warn-primary)}',
      '.cddl-trace-working .cddl-trace-state{color:var(--dsw-alias-state-error-primary)}',
      '.cddl-trace-detail{border-top:1px solid var(--dsw-alias-border-l1);padding:7px;background:var(--dsw-alias-bg-layer-2)}',
      '.cddl-trace-path{font:9px var(--ds-font-family-code,ui-monospace,monospace);color:var(--dsw-alias-label-caption);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:5px}',
      '.cddl-trace-source pre{max-height:230px;overflow:auto;margin:0;padding:6px;border-radius:5px;background:var(--dsw-alias-bg-base);font:9.5px/1.45 var(--ds-font-family-code,ui-monospace,monospace)}',
      '.cddl-trace-source pre div{display:grid;grid-template-columns:31px minmax(0,1fr);gap:7px}',
      '.cddl-trace-source pre span{text-align:right;color:var(--dsw-alias-label-dimmed);user-select:none}',
      '.cddl-trace-source pre code{white-space:pre;color:var(--dsw-alias-label-secondary)}',
      '.cddl-trace-missing{padding:7px;color:var(--dsw-alias-label-tertiary);font-size:10px}',
      '.cddl-trace-loading{padding:8px;color:var(--dsw-alias-label-caption);font-size:10px}',
      '.cddl-trace-locate,.cddl-trace-unresolved button{margin-top:6px;border:1px solid var(--dsw-alias-border-l3);border-radius:5px;background:transparent;color:var(--dsw-alias-label-secondary);font:10px inherit;padding:3px 7px;cursor:pointer}',
      '.cddl-trace-unresolved{display:flex;align-items:center;gap:8px;font-size:10px;color:var(--dsw-alias-label-caption)}',
      '.cddl-trace-unresolved button{margin:0 0 0 auto}',
      '@media (min-width:721px) and (max-width:900px){.cddl-trajectory{width:min(var(--cddl-trajectory-width,360px),52vw)!important;min-width:220px}.cddl-dock{right:min(var(--cddl-trajectory-width,360px),52vw)}.cddl-trace-step{grid-template-columns:34px minmax(0,1fr)}.cddl-trace-step-label{font-size:8px}}',
      '@media (max-width:720px){.cddl-trajectory:not(.is-collapsed){width:min(var(--cddl-trajectory-width,360px),82vw)!important;min-width:280px}.cddl-trajectory-toggle{display:block}.cddl-trajectory:not(.is-collapsed){box-shadow:-18px 0 42px rgba(0,0,0,.34)}.cddl-dock{right:44px;min-width:0;max-width:calc(100vw - 44px)}.cddl-trace-step{grid-template-columns:34px minmax(0,1fr)}.cddl-trace-step-label{font-size:8px}}',
      '.cddl-rail{display:flex;flex-direction:column;min-height:0;height:100%}',
      '.cddl-rail-head{padding:6px 10px;font-size:10.5px;color:var(--dsw-alias-label-tertiary);border-bottom:1px solid var(--dsw-alias-border-l1);flex:none}',
      '.cddl-rail-body{overflow:auto;padding:6px 4px 14px;display:flex;flex-direction:column;gap:7px;flex:1}',
      '.cddl-rail-empty{padding:14px 12px;font-size:11.5px;color:var(--dsw-alias-label-tertiary)}',
      '.cddl-rail-row{position:relative;padding-left:12px}',
      '.cddl-rail-at{display:flex;align-items:baseline;gap:6px;font-size:9.5px;margin-bottom:2px;font-family:var(--ds-font-family-code,ui-monospace,monospace)}',
      '.cddl-rail-at b{font-weight:500;color:var(--dsw-alias-label-tertiary)}',
      '.cddl-rail-verb{color:var(--dsw-alias-label-quaternary)}',
      '.cddl-rail-verb-e{color:var(--dsw-alias-state-warn-primary)}',
      // Only the edits are threaded. Two reads in a row means they were read in
      // a row and nothing else; drawing that would invent a relation.
      '.cddl-rail-thread::before{content:\'\';position:absolute;left:3px;top:0;bottom:-6px;width:1px;background:var(--dsw-alias-border-l3)}',
      '.cddl-rail-edit::after{content:\'\';position:absolute;left:0;top:14px;width:7px;height:7px;border-radius:50%;background:var(--dsw-alias-state-warn-primary)}',
      '.cddl-rail-on .cddl-gnode{outline:1px solid var(--dsw-alias-state-business-primary)}',
      '.cddl-rail-gone{font-size:11px;color:var(--dsw-alias-label-quaternary);padding:3px 0}',
      '.cddl-rail-file{display:flex;align-items:center;gap:6px;padding:4px 6px;border-radius:7px;border:1px dashed var(--dsw-alias-border-l3);background:var(--dsw-alias-bg-layer-2)}',
      '.cddl-rail-path{font-family:var(--ds-font-family-code,ui-monospace,monospace);font-size:10.5px;color:var(--dsw-alias-label-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;direction:rtl;text-align:left;flex:1;min-width:0}',
      '.cddl-rail-insert{font-size:9.5px;padding:1px 6px;border-radius:5px;flex:none;cursor:pointer;border:1px solid var(--dsw-alias-border-l3);background:transparent;color:var(--dsw-alias-label-tertiary);font-family:inherit}',
      '.cddl-rail-insert:hover{color:var(--dsw-alias-label-primary);border-color:var(--dsw-alias-state-business-primary)}',
      '.cddl-rail-why{font-size:9px;color:var(--dsw-alias-label-quaternary);flex:none}',
      '.cddl-wire.cddl-lit{stroke-width:3;opacity:1;filter:drop-shadow(0 0 3px color-mix(in srgb,var(--dsw-alias-state-business-primary) 58%,transparent))}',
      '.cddl-wire.cddl-unlit{opacity:.05}',
      '.cddl-gnode.cddl-lit{border-color:var(--dsw-alias-state-business-primary)}',
      '.cddl-gnode.cddl-unlit{opacity:.24}',
      '.cddl-arrowhead.cddl-lit{opacity:1}',
      '.cddl-arrowhead.cddl-unlit{opacity:.05}',
      '.cddl-node-shell{position:absolute}',
      // Gather flights only. Scoped to the window so panning or dragging a
      // settled drawing never lags; 260ms matches GATHER_MS in engine/gather.
      // 节点位移**不做过渡**：线是由布局一次算出来的绝对坐标路径，节点却用
      // CSS 慢慢飘过去，两边就永远差一截——看着就是「线没锁死在节点上，节点
      // 挪走了线慢一点」。
      //
      // 想两个都动只有一个稳的办法：在 JS 里逐帧把节点和线一起插值。SVG 的
      // d 属性做 CSS 过渡在不同浏览器上不可靠（命令序列一不一样就跳变），
      // 而重算布局逐帧画在几百个节点上太贵。所以选择两边都**瞬间到位**：
      // 同一帧里节点和线一起落地，端点永远钉在端口小圈上。
      '.cddl-gathering .cddl-node-shell{transition:none}',
      '.cddl-node-flow{position:static;flex:none}',
      '.cddl-node-flow .cddl-port{display:none}',
      // 出入口的小圈：入在左、出在右，各是一个实心小圆，外面一圈底色把它
      // 从卡片边上"抠"出来。线两头就停在这个圈上，所以它必须看得见。
      '.cddl-port{position:absolute;top:50%;z-index:4;width:11px;height:11px;box-sizing:border-box;border-radius:50%;transform:translateY(-50%);box-shadow:0 0 0 2px var(--dsw-alias-bg-layer-2)}',
      '.cddl-port-in{left:-6px;background:var(--dsw-alias-state-business-primary)}',
      '.cddl-port-out{right:-6px;background:var(--dsw-alias-state-warn-primary)}',
      '.cddl-port-vtop{left:50%;top:-6px;transform:translateX(-50%)}',
      '.cddl-port-vbottom{left:50%;top:auto;bottom:-6px;transform:translateX(-50%)}',
      '.cddl-node-actions{display:flex;gap:4px;margin-top:4px;z-index:2}',
      '.cddl-node-actions button{font-size:10px}',
      '.cddl-node-shell:hover .cddl-node-actions,.cddl-node-shell:focus-within .cddl-node-actions{opacity:1}',
      '.cddl-node-actions button{min-width:26px;height:19px;padding:0 5px;border-radius:5px;cursor:pointer;font:700 11px var(--ds-font-family-code,monospace);color:var(--dsw-alias-state-business-primary);background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-state-business-tertiary)}',
      '.cddl-node-actions .cddl-action-collapse:not(:disabled){color:var(--dsw-alias-state-warn-primary);border-color:var(--dsw-alias-state-warn-tertiary)}',
      '.cddl-node-actions button:hover:not(:disabled),.cddl-node-actions button.on{color:var(--dsw-alias-label-primary);border-color:var(--dsw-alias-border-l4);background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-node-actions button:disabled{opacity:.34;cursor:default}',
      // 展开按钮按关系挂：一个关系一种颜色，箭头、数字、线同色。
      // 没有数据的关系不出现，所以这里不需要 :disabled 的灰样式。
      '.cddl-node-actions .cddl-rel-arrow{font-weight:700}',
      '.cddl-node-actions .cddl-rel-count{margin-left:2px;font-weight:700}',
      '.cddl-node-actions .cddl-rel-name{margin-left:3px;font-size:8px;opacity:.6;letter-spacing:.02em}',
      '.cddl-node-actions .cddl-rel-call{color:var(--dsw-alias-state-business-primary);border-color:var(--dsw-alias-state-business-tertiary)}',
      '.cddl-node-actions .cddl-rel-dataflow{color:var(--dsw-alias-state-warn-primary);border-color:color-mix(in srgb,var(--dsw-alias-state-warn-primary) 45%,transparent)}',
      '.cddl-node-actions .cddl-rel-inherit{color:var(--dsw-alias-label-tertiary);border-color:var(--dsw-alias-border-l3)}',
      '.cddl-node-actions .cddl-rel-dispatch{color:var(--dsw-alias-state-success-primary);border-color:color-mix(in srgb,var(--dsw-alias-state-success-primary) 45%,transparent)}',
      '.cddl-node-actions button.cddl-rel-call.on{background:color-mix(in srgb,var(--dsw-alias-state-business-primary) 22%,transparent)}',
      '.cddl-node-actions button.cddl-rel-dataflow.on{background:color-mix(in srgb,var(--dsw-alias-state-warn-primary) 22%,transparent)}',
      '.cddl-node-actions button.cddl-rel-inherit.on{background:color-mix(in srgb,var(--dsw-alias-label-tertiary) 22%,transparent)}',
      '.cddl-node-actions button.cddl-rel-dispatch.on{background:color-mix(in srgb,var(--dsw-alias-state-success-primary) 22%,transparent)}',
      '.cddl-action-help{font-family:var(--ds-font-family-code,monospace);font-weight:600!important}',
      '.cddl-action-help-plus{color:var(--dsw-alias-state-business-primary)!important}',
      '.cddl-action-help-minus{color:var(--dsw-alias-state-warn-primary)!important}',
      '.cddl-gnode{position:relative;box-sizing:border-box;width:100%;background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l2);border-radius:8px;padding:7px 10px;cursor:grab;touch-action:none;box-shadow:0 2px 10px rgba(0,0,0,.3)}',
      '.cddl-gnode:hover{border-color:var(--dsw-alias-border-l4)}',
      '.cddl-gnode.cddl-sel{border-color:var(--dsw-alias-state-warn-primary);box-shadow:0 0 0 1px var(--dsw-alias-state-warn-tertiary),0 6px 18px rgba(0,0,0,.45)}',
      '.cddl-gnode.cddl-island{border-style:dashed}',
      // 类和函数是两种东西，颜色必须一眼分得出：类走 business（蓝），函数走
      // success（绿），左边一条 3px 实色竖条把归属钉死。底色用 color-mix 兑出来，
      // 浏览器不认这条声明就退回基础底色，不会变透明。
      '.cddl-gnode.cddl-cls{background:color-mix(in srgb, var(--dsw-alias-state-business-primary) 16%, var(--dsw-alias-bg-layer-2));border-color:var(--dsw-alias-state-business-tertiary);border-left:3px solid var(--dsw-alias-state-business-primary)}',
      '.cddl-gnode.cddl-fn{background:color-mix(in srgb, var(--dsw-alias-state-success-primary) 12%, var(--dsw-alias-bg-layer-2));border-color:var(--dsw-alias-border-l2);border-left:3px solid var(--dsw-alias-state-success-primary)}',
      '.cddl-gnode.cddl-cls:hover,.cddl-gnode.cddl-fn:hover{border-top-color:var(--dsw-alias-border-l4);border-right-color:var(--dsw-alias-border-l4);border-bottom-color:var(--dsw-alias-border-l4)}',
      '.cddl-gnode.cddl-cls .cddl-gtop{padding-bottom:2px}',
      '.cddl-gnode .cddl-sym{min-width:0;flex:1;overflow-wrap:anywhere;white-space:normal;line-height:16px;font-size:13.5px;font-weight:500}',
      '.cddl-gfile{font-family:var(--ds-font-family-code,monospace);font-size:9.5px;color:var(--dsw-alias-label-caption);margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddl-gtop{display:flex;align-items:center;gap:6px;flex-wrap:nowrap}',
      '.cddl-gnode .cddl-count{background:var(--dsw-alias-bg-layer-3);border:1px solid var(--dsw-alias-border-l2);border-radius:9px;padding:0 6px;cursor:pointer;color:var(--dsw-alias-label-tertiary);font-size:10px}',
      '.cddl-members{margin-top:6px;border-top:1px solid var(--dsw-alias-border-l1);padding-top:5px}',
      '.cddl-m{display:flex;align-items:center;gap:6px;padding:2px 4px;border-radius:5px}',
      '.cddl-m:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-more{font-size:10px;color:var(--dsw-alias-label-caption);padding:5px 4px 0;text-align:right}',
      '.cddl-working{margin-top:6px;padding:4px 6px;border-radius:5px;font-size:10px;color:var(--dsw-alias-state-error-primary);background:var(--dsw-alias-state-error-tertiary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddl-ghop{display:flex;gap:3px;margin-top:2px;line-height:1.25}',
      '.cddl-ghop button{font-size:10px;font-family:var(--ds-font-family-code,monospace);cursor:pointer;color:var(--dsw-alias-label-caption);background:transparent;border:1px solid var(--dsw-alias-border-l2);border-radius:4px;padding:0 5px}',
      '.cddl-ghop button:hover{color:var(--dsw-alias-label-primary);background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-ghop button.on{color:var(--dsw-alias-label-primary);border-color:var(--dsw-alias-border-l4)}',
      '.cddl-sidepanel{position:absolute;z-index:12;right:0;top:0;bottom:0;width:min(440px,55%);border-left:1px solid var(--dsw-alias-border-l2);box-shadow:-10px 0 28px rgba(0,0,0,.14);background:var(--dsw-alias-bg-layer-1);overflow:auto}',
      '.cddl-draw-fallback{display:flex;flex-direction:column;min-height:0;height:100%}',
      '.cddl-draw-note{flex:none;padding:8px 12px;font-size:11px;line-height:1.6;color:var(--dsw-alias-label-tertiary);border-bottom:1px solid var(--dsw-alias-border-l1)}',
      '.cddl-draw-fallback-body{flex:1;min-height:0;overflow:auto}',
      '.cddl-draw-open{margin-left:8px;vertical-align:middle}',
      '.cddl-outline-filter{width:calc(100% - 16px);margin:6px 8px;padding:4px 8px;font-size:11px;border-radius:6px;border:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-primary);outline:none}',
      '.cddl-outline-more{margin:6px 8px;padding:6px 8px;font-size:11px;text-align:center;cursor:pointer;border-radius:6px;border:1px dashed var(--dsw-alias-border-l3);color:var(--dsw-alias-label-tertiary)}',
      '.cddl-outline-more:hover{border-color:var(--dsw-alias-state-business-primary)}',
      '.cddl-boundary{padding:14px 16px;font-size:12px;line-height:1.7;color:var(--dsw-alias-label-primary)}',
      '.cddl-boundary-msg{margin:6px 0;color:var(--dsw-alias-state-warn-primary);word-break:break-word}',
      '.cddl-boundary-stack{margin:6px 0;padding:8px;font-size:10.5px;white-space:pre-wrap;overflow:auto;max-height:40vh;border-radius:6px;background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-tertiary)}',
      '.cddl-boundary-hint{color:var(--dsw-alias-label-caption)}',
      '.cddl-sidepanel .cddl-src pre{max-height:none}',
      '.cddl-trajectory-src{flex:none;max-height:46%;overflow:auto;border-bottom:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-2)}',
      '@media (max-width:900px){.cddl-sidepanel{width:min(420px,72%)}.cddl-toolbar .cddl-search{width:190px}.cddl-meta{max-width:180px}}',
    ]

    module.exports = { GRAPH_CSS }
    return module.exports
  },
})

// dsh-cdd-lens — How tall a card is, read off the stylesheet that draws it.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/cardBox',
  factory: (require) => {
    var module = { exports: {} }
    var __styles_graph = require('dsh-cdd-lens/styles/graph')
    var GRAPH_CSS = __styles_graph.GRAPH_CSS

    /** The first `prop:` value inside the rule for `selector`, in pixels. */
    function pxFrom(css, selector, prop) {
      var text = css.join('')
      var at = text.indexOf(selector + '{')
      if (at < 0) return null
      var end = text.indexOf('}', at)
      var body = text.slice(at + selector.length + 1, end < 0 ? undefined : end)
      var hit = new RegExp('(?:^|;)\\s*' + prop + '\\s*:\\s*(-?[0-9.]+)px').exec(body)
      return hit === null ? null : parseFloat(hit[1])
    }

    /**
     * The height of a card, from the rules that draw it.
     *
     * The layout has to reserve exactly what a card takes, and it used to
     * reserve a flat 70 for something that draws 55 — fifteen pixels of slack
     * under every anchor in every box. Writing 55 down instead only moves the
     * problem: two numbers for one thing, in two files, free to drift the next
     * time the card gains a row or loses some padding.
     *
     * So the stylesheet is the single truth and this reads it. A rule that
     * changes shape enough to stop matching falls back to what it measures
     * today, which keeps a drawing on screen rather than collapsing it.
     *
     * @returns { base, membersChrome, memberRow, moreRow, symLine }
     */
    function cardBox() {
      var css = GRAPH_CSS
      var border = pxFrom(css, '.cddl-gnode', 'border')
      var pad = pxFrom(css, '.cddl-gnode', 'padding')
      var symLine = pxFrom(css, '.cddl-gnode .cddl-sym', 'line-height')
      var actionsGap = pxFrom(css, '.cddl-node-actions', 'margin-top')
      var actionsRow = pxFrom(css, '.cddl-node-actions button', 'height')
      var membersTop = pxFrom(css, '.cddl-members', 'margin-top')
      var membersPad = pxFrom(css, '.cddl-members', 'padding-top')
      var memberPad = pxFrom(css, '.cddl-m', 'padding')
      var morePad = pxFrom(css, '.cddl-more', 'padding')

      var or = function (value, fallback) { return value === null ? fallback : value }
      border = or(border, 1)
      pad = or(pad, 7)
      symLine = or(symLine, 16)
      actionsGap = or(actionsGap, 4)
      actionsRow = or(actionsRow, 19)

      return {
        symLine: symLine,
        base: border * 2 + pad * 2 + symLine + actionsGap + actionsRow,
        // A member row is its own padding twice plus one line of text; the
        // divider above the list is a border plus the padding either side.
        membersChrome: or(membersTop, 6) + border + or(membersPad, 5),
        memberRow: or(memberPad, 2) * 2 + symLine + 2,
        moreRow: or(morePad, 5) * 2 + symLine - 4,
      }
    }

    module.exports = { pxFrom, cardBox }
    return module.exports
  },
})

// dsh-cdd-lens — Box and canvas measurements.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/metrics',
  factory: (require) => {
    var module = { exports: {} }
    var __layout_cardBox = require('dsh-cdd-lens/layout/cardBox')
    var cardBox = __layout_cardBox.cardBox
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf

    var SYMBOL_FONT = '11.5px ui-monospace, SFMono-Regular, Menlo, monospace'
    var measurer = null
    var measured = {}

    /**
     * How wide a string actually is in a given font.
     *
     * @param text - the string that will be drawn.
     * @param font - a CSS font shorthand, the same one the element uses.
     * @returns the width in CSS pixels; 0 if the browser will not measure.
     */
    function textWidth(text, font) {
      var key = font + '\u0000' + text
      if (measured[key] !== undefined) return measured[key]
      if (measurer === null) {
        try { measurer = document.createElement('canvas').getContext('2d') }
        catch (e) { measurer = false }
      }
      if (measurer === false || measurer === null) return text.length * 7
      measurer.font = font
      measured[key] = measurer.measureText(text).width
      return measured[key]
    }

    /**
     * The name a person would say out loud.
     *
     * `factory@1668.Draw.useEffect@1756.poll.then@1759` is a path to a closure,
     * not something anyone calls a thing. The last segment is what is meant.
     * @param symbol - the anchor's full symbol path.
     * @returns the last segment.
     */
    function shortSymbol(symbol) {
      var parts = String(symbol).split('.')
      return parts[parts.length - 1] || String(symbol)
    }

    /**
     * What to write on each node, given everything else on screen.
     *
     * The last segment is what a person says, so that is the default. But two
     * anchors can share it — `_get_line_content` exists in json_file.py and in
     * jsonl_file.py — and two identical boxes side by side are worse than two
     * long ones. A name only pays for the extra width when it actually collides.
     * @param graph - the graph being drawn.
     * @param included - the ids that will be drawn.
     * @returns id to the label that node should carry.
     */
    function labelsFor(graph, included) {
      var byShort = {}
      included.forEach(function (id) {
        var node = graph.nodes[id]
        if (node === undefined) return
        var name = shortSymbol(node.symbol)
        if (byShort[name] === undefined) byShort[name] = []
        byShort[name].push(id)
      })
      var out = {}
      Object.keys(byShort).forEach(function (name) {
        var group = byShort[name]
        group.forEach(function (id) {
          out[id] = group.length === 1 ? name : graph.nodes[id].symbol
        })
      })
      return out
    }

    /**
     * Box and canvas measurements, driven by the longest name on screen.
     */
    function boxMetrics(graph, scope, avail) {
      var included = scope.included
      var fileOrder = scope.fileOrder

      // Node width follows the longest symbol actually on screen, not a fixed
      // number. A truncated name is the one thing a code graph cannot afford:
      // `_get_line_co…` and `_get_line_count` are different functions and the
      // picture stops answering the question it exists to answer.
      //
      // One width for every node rather than per-node widths: a grid of equal
      // cells keeps the channels straight, and channels are what stop wires
      // running under the boxes.
      // One measured quantity, and everything else expressed against it. The
      // grid used to be a dozen independent pixel constants, so changing the
      // type size moved the text and left every gap, pad and clearance where it
      // was. CHAR_W is the width of one character in the monospace face the
      // cards are set in; the ratios below reproduce the sizes the drawing has
      // today, and now they follow the type instead of standing beside it.
      var CHAR_W = 7.4
      var em = function (k) { return Math.round(CHAR_W * k) }
      var PAD = em(2.43)
      var BOX_GAP_X = em(5.41)
      var BADGES = em(17.3)
      var longest = 0
      included.forEach(function (id) {
        var node = graph.nodes[id]
        var chars = node.symbol.length
        if (chars > longest) longest = chars
        var ui = uiOf(graph, id)
        if (ui !== null && ui.memberList !== undefined) {
          ui.memberList.forEach(function (m) {
            var own = m.symbol.split('.').pop().length + 2
            if (own > longest) longest = own
          })
        }
      })
      // Wide enough for the longest name on screen, but never wider than the
      // space actually available: a single box must always fit without
      // horizontal scrolling, whatever it is called.
      var roomForBox = Math.max(em(32.4), (avail || em(86.5)) - PAD * 2)
      var NODE_W = Math.max(em(27.03), Math.min(roomForBox - em(2.97), Math.ceil(longest * CHAR_W + BADGES)))
      var BOX_W = NODE_W + em(1.49) * 2
      var BOX_GAP_Y = em(5.41)
      var BOX_PAD = em(1.49)
      var BOX_HEAD = em(4.32)
      var INNER_GAP_X = em(2.70)
      var INNER_GAP_Y = em(1.89)
      // A wire leaves and enters through a port, and runs straight for this
      // much before it is allowed to turn — otherwise the head that says
      // which way it is going has nowhere to sit.
      // The gap between two layers has to hold the exit badge of one column,
      // the entry badge of the next, and the wire that joins them. A port sits
      // 29px clear of its box and is 24 wide, so two of them alone need 58 —
      // the 40 that BOX_GAP_X allows was set when layers were rows and the
      // badges were above and below, and it left them overlapping with the
      // wire hidden underneath.
      var PORT_CLEAR = em(3.92)
      var LAYER_GAP_X = PORT_CLEAR * 2 + 38
      var PORT_STUB = em(1.22)
      // How often a head is repeated along a run. One head at the far end
      // says nothing about the middle of a wire with four bends.
      var ARROW_EVERY = em(11.35)
      // The wire-routing sizes. Every skin routes with the same ones — a hop
      // that changed radius with the drawing would be a different diagram, not
      // a different view of it. WIRE_HOP is a radius, so it keeps its half
      // pixel: the arc is drawn with it twice (before and after the crossing),
      // and an integer here would move both.
      var LANE_STEP = em(1.62)          // 12 — one lane's worth of corridor
      var WIRE_HOP = em(1.22) / 2       // 4.5 — hop arc radius
      var WIRE_CORNER = em(1.35)        // 10 — rounded bend radius
      var CORRIDOR_MIN = em(1.08)       // 8 — narrowest usable corridor or side lane
      var SUBLANE_STEP = em(0.54)       // 4 — wires sharing one node gap fan out by this
      var HIT_PAD = em(0.41)            // 3 — a run this close to a box is through it
      // Two or three boxes across, and the boxes share out whatever width that
      // leaves. Deriving the count from a fixed box width instead put four and
      // five narrow boxes on a wide screen: every name wrapped, every box was
      // mostly padding, and the eye had no column to follow. The count leads
      // and the width follows.
      var usable = Math.max(320, (avail || 0) - PAD * 2)
      var WIDEST_ROW = 3
      var BOX_COLS = usable >= (BOX_W + BOX_GAP_X) * 2 ? WIDEST_ROW : 1
      if (BOX_COLS === WIDEST_ROW && usable < (BOX_W + BOX_GAP_X) * WIDEST_ROW) BOX_COLS = 2
      if (fileOrder.length === 1) BOX_COLS = 1
      if (fileOrder.length < BOX_COLS) BOX_COLS = fileOrder.length
      // The box stays the width of the longest name plus its padding — it is
      // not stretched to fill the row. Stretching gave 360px cards holding a
      // twelve-character symbol, mostly empty. The width a row does not need
      // goes into the gutters between the columns, which is where the traces
      // run anyway.
      var COL_STRIDE = BOX_COLS > 1
        ? Math.max(BOX_W + BOX_GAP_X, Math.floor((usable - BOX_W) / (BOX_COLS - 1)))
        : BOX_W + BOX_GAP_X
      // No floor. A hardcoded minimum of 920 held the canvas wider than the
      // boxes it contains, so narrowing the window correctly dropped to one
      // column and then overflowed anyway — the drawing insisted on a width
      // nothing asked for.
      var canvasWidth = PAD * 2 + BOX_COLS * BOX_W + Math.max(0, BOX_COLS - 1) * BOX_GAP_X
      // Measured, not guessed. A pixels-per-character constant was wrong for
      // every font it was not tuned on, and there were two different ones in
      // this codebase for the same face — which is the tell that neither was
      // ever measured. One offscreen canvas answers exactly.
      // Read off the stylesheet that draws the card, not copied out of it: two
      // numbers for one thing in two files drift the next time the card gains a
      // row. See layout/cardBox.js.
      var CARD = cardBox()
      var CARD_BASE = CARD.base
      var MEMBERS_CHROME = CARD.membersChrome
      var MEMBER_ROW = CARD.memberRow
      var MORE_ROW = CARD.moreRow

      var label = labelsFor(graph, included)
      var sizeOf = function (id, widthLimit) {
        var node = graph.nodes[id]
        var ui = uiOf(graph, id) || {}
        var text = label[id] === undefined ? shortSymbol(node.symbol) : label[id]
        var badge = 46
        var chrome = 22 + 14 + 16
        // Keep one small readability gutter between the symbol and its badges;
        // exact text width left `dispatch_command` wrapping at the underscore.
        var own = Math.ceil(textWidth(text, SYMBOL_FONT)) + badge + chrome + 72
        var width = Math.max(150, Math.min(NODE_W, widthLimit || NODE_W, own))
        // Colliding names intentionally keep their fully-qualified symbol.
        // On a narrow vertical canvas the name wraps inside the card instead
        // of silently making the whole graph horizontally scrollable.
        var reserved = node.kind === 'class' || node.members > 0 ? 142 : 96
        var textRoom = Math.max(72, width - reserved)
        var lines = Math.max(1, Math.ceil(textWidth(text, SYMBOL_FONT) / textRoom))
        var wrapped = (lines - 1) * CARD.symLine
        return {
          // Never wider than the space there is, never so narrow the buttons
          // underneath do not fit.
          w: width,
          // Added up from the card's own CSS rather than guessed. The width
          // above is measured — the comment above it says so — while the height
          // was a flat 70 for a plain card that actually draws 55. Every row in
          // every box carried fifteen pixels of slack that nothing was in, and
          // the boxes were that much taller than their contents.
          h: ui.members && ui.memberList !== undefined
            ? CARD_BASE + MEMBERS_CHROME + ui.memberList.length * MEMBER_ROW + MORE_ROW + wrapped
            : CARD_BASE + wrapped,
        }
      }
      return { PAD: PAD, BOX_GAP_X: BOX_GAP_X, BOX_GAP_Y: BOX_GAP_Y, BOX_PAD: BOX_PAD,
        BOX_HEAD: BOX_HEAD, BOX_W: BOX_W, BOX_COLS: BOX_COLS, NODE_W: NODE_W,
        INNER_GAP_X: INNER_GAP_X, INNER_GAP_Y: INNER_GAP_Y,
        PORT_STUB: PORT_STUB, ARROW_EVERY: ARROW_EVERY,
        PORT_CLEAR: PORT_CLEAR, LAYER_GAP_X: LAYER_GAP_X, COL_STRIDE: COL_STRIDE,
        LANE_STEP: LANE_STEP, WIRE_HOP: WIRE_HOP, WIRE_CORNER: WIRE_CORNER, CORRIDOR_MIN: CORRIDOR_MIN,
        SUBLANE_STEP: SUBLANE_STEP, HIT_PAD: HIT_PAD,
        canvasWidth: canvasWidth, sizeOf: sizeOf, label: label }
    }

    module.exports = { boxMetrics, textWidth, shortSymbol, labelsFor }
    return module.exports
  },
})

// Shared, structured geometry. SVG is output only, never a routing input.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/geometry',
  factory: (require) => {
    function compact(points) {
      var out = []
      points.forEach(function (p) {
        if (!Number.isFinite(p.x) || !Number.isFinite(p.y)) return
        var q = out[out.length - 1]
        if (q && Math.abs(p.x - q.x) < 1e-7 && Math.abs(p.y - q.y) < 1e-7) return
        while (out.length > 1) {
          var a = out[out.length - 2], b = out[out.length - 1]
          if ((a.x === b.x && b.x === p.x && (b.y - a.y) * (p.y - b.y) >= 0)
            || (a.y === b.y && b.y === p.y && (b.x - a.x) * (p.x - b.x) >= 0)) out.pop()
          else break
        }
        out.push({ x: p.x, y: p.y })
      })
      return out
    }
    function sideOf(node, p) {
      var sides = [['left', Math.abs(p.x - node.x)], ['right', Math.abs(p.x - node.x - node.w)],
        ['top', Math.abs(p.y - node.y)], ['bottom', Math.abs(p.y - node.y - node.h)]]
      sides.sort(function (a, b) { return a[1] - b[1] })
      return sides[0][0]
    }
    function portAt(node, side, stub) {
      var x = node.x + node.w / 2, y = node.y + node.h / 2
      var dx = side === 'left' ? -1 : side === 'right' ? 1 : 0
      var dy = side === 'top' ? -1 : side === 'bottom' ? 1 : 0
      if (dx) x += dx * node.w / 2
      if (dy) y += dy * node.h / 2
      return { side: side, point: { x: x, y: y }, exit: { x: x + dx * stub, y: y + dy * stub } }
    }
    function length(pts) {
      var n = 0
      for (var i = 1; i < pts.length; i++) n += Math.abs(pts[i].x - pts[i-1].x) + Math.abs(pts[i].y - pts[i-1].y)
      return n
    }
    function atDistance(pts, distance) {
      for (var i = 1; i < pts.length; i++) {
        var p = pts[i-1], q = pts[i], dx = q.x-p.x, dy = q.y-p.y, n = Math.abs(dx)+Math.abs(dy)
        if (n > 0 && (distance <= n || i === pts.length-1)) {
          var t = Math.max(0, Math.min(1, distance/n))
          return { x:p.x+dx*t, y:p.y+dy*t, angle:Math.atan2(dy,dx)*180/Math.PI, segment:i }
        }
        distance -= n
      }
      return { x:pts[0].x, y:pts[0].y, angle:0, segment:0 }
    }
    // Ports are attached to the SAME endpoint objects that translate with a route.
    function bindPorts(route, orient) {
      Object.keys(orient.byId).forEach(function (id) { orient.byId[id].routingPorts = [] })
      route.polylines.forEach(function (line) {
        if (line.status === 'blocked' || line.pts.length < 2) return
        ;[['from','sourcePort','out',0],['to','targetPort','in',line.pts.length-1]].forEach(function (spec) {
          var node = orient.byId[line[spec[0]]]
          if (!node) return
          var p = line.pts[spec[3]], side = sideOf(node,p)
          line[spec[1]] = { side:side, point:p }
          var existing = node.routingPorts.filter(function (port) { return port.side === side })[0]
          if (!existing) { existing = { side:side, in:false, out:false }; node.routingPorts.push(existing) }
          existing[spec[2]] = true
        })
      })
    }
    return { compact, sideOf, portAt, length, atDistance, bindPorts }
  },
})

// dsh-cdd-lens — Drawing every relation is what makes the web; this picks.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/select',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf

    /**
     * Which relations get a wire: a trunk by default, the rest on demand.
     */
    function chooseEdges(graph, scope, orient, relationFilter) {
      var activeFocus = scope.activeFocus
      var byId = orient.byId
      var REL_ORDER = ['call', 'dataflow', 'inherit', 'impact', 'dispatch']

      // ---- which edges get drawn ------------------------------------------
      //
      // Drawing every relation is what makes the web, and no amount of clever
      // routing fixes it. Measured on this graph — 103 nodes, 227 call/dispatch
      // edges — the three-segment dogleg router produces 1326 geometric
      // crossings. Giving each edge its own corridor makes it WORSE (5265):
      // separate lanes mean more turns, and the turns are what cross.
      //
      // Only the edge count moves the number. A spanning tree over the same
      // nodes is 63 edges and 55 crossings — a 24x drop with identical node
      // placement. So the trunk is drawn by default and everything else is
      // reachable: selecting a node lights up all of ITS relations (32 edges,
      // 30 crossings), and the per-node up/down counts were always the hidden
      // ones. This is the flyline idea from board layout, where the same
      // problem has the same answer — except a router must connect every net
      // and we may simply not draw one.
      // 一条边算不算「打开」：这条边自己的关系类型对应的那个按钮开没开。
      // 展开状态按「方向:关系」存（ui.open['down:call']），所以必须看边的类型，
      // 不能只看方向——点开 call 的 ↓ 不该把 inherit 的边也点亮。
      var opened = function (ui, prefix, types) {
        if (ui === null || ui === undefined || ui.open === undefined) return false
        return types.some(function (t) {
          return ui.open[prefix + ':' + t] === true
        })
      }
      var relationAllowed = function (types) {
        if (relationFilter === undefined || relationFilter === null) return true
        return types.some(function (t) { return relationFilter[t] !== false })
      }
      var relationStats = function (pool, chosenPool) {
        var stats = {}
        REL_ORDER.forEach(function (type) { stats[type] = { total: 0, drawn: 0 } })
        pool.forEach(function (e) {
          var seen = {}
          ;(e.types || ['call']).forEach(function (type) {
            if (seen[type]) return
            seen[type] = true
            if (stats[type] === undefined) stats[type] = { total: 0, drawn: 0 }
            stats[type].total += 1
          })
        })
        chosenPool.forEach(function (e) {
          var seen = {}
          ;(e.types || ['call']).forEach(function (type) {
            if (relationFilter !== undefined && relationFilter !== null && relationFilter[type] === false) return
            if (seen[type]) return
            seen[type] = true
            if (stats[type] === undefined) stats[type] = { total: 0, drawn: 0 }
            stats[type].drawn += 1
          })
        })
        return stats
      }
      var drawableAll = graph.edges.filter(function (e) {
        var fromUI = uiOf(graph, e.from)
        var toUI = uiOf(graph, e.to)
        if (byId[e.from] === undefined || byId[e.to] === undefined) return false
        if (activeFocus !== null || e.always) return true
        var types = e.types || ['call']
        return opened(fromUI, 'down', types) || opened(toUI, 'up', types)
      })
      var drawable = drawableAll.filter(function (e) { return relationAllowed(e.types || ['call']) })
      var explicitlyOpened = function (e) {
        var types = e.types || ['call']
        return opened(uiOf(graph, e.from), 'down', types) || opened(uiOf(graph, e.to), 'up', types)
      }
      var chosen = drawable
      var hiddenCount = 0
      if (activeFocus !== null) {
        chosen = drawable.filter(function (edge) {
          return (edge.types || ['call']).some(function (type) {
            return activeFocus.keys[edge.from + '→' + edge.to + ':' + type] === true
          })
        })
        hiddenCount = drawable.length - chosen.length
      } else if (shared.wireMode !== 'all') {
        var keep = {}
        var focus = shared.selected
        // A pressed ↑/↓ button is a literal request: show every relation that
        // made that count. The trunk pass below is only for background edges;
        // it may not compress "2" visible neighbours into one line.
        drawable.forEach(function (e) {
          if (explicitlyOpened(e)) keep[e.from + '→' + e.to] = true
        })
        // Every relation of the selected node, in both directions.
        drawable.forEach(function (e) {
          if (e.from === focus || e.to === focus) keep[e.from + '→' + e.to] = true
        })
        // One parent per node — the one the chain data means, not the nearest
        // placed caller. Geometric distance made the trunk a function of the
        // skin: move the nodes and a different edge becomes the parent, so the
        // same graph showed a different skeleton in every drawing. Consistency
        // across skins beats hugging one layout. The layer comes from the
        // index (DFS finish order, longest-path relaxed) and rides in on
        // node.layer, so the caller exactly one layer up is the real parent;
        // otherwise the smallest layer difference wins, with a forward step
        // preferred over a backward one of the same size, and nodes without a
        // layer are decided by the edge's place in graph.edges — stable, and
        // the same in every skin because it never touches a coordinate.
        var best = {}
        drawable.forEach(function (e) {
          var from = graph.nodes[e.from]
          var to = graph.nodes[e.to]
          var la = from === undefined ? undefined : from.layer
          var lb = to === undefined ? undefined : to.layer
          var d = typeof la === 'number' && typeof lb === 'number' ? lb - la : null
          var cost = d === null ? Infinity
            : d === 1 ? 0
            : Math.abs(d) + (d < 1 ? 0.5 : 0)
          // Strictly smaller wins, so a tie keeps the edge that came first —
          // the deterministic tiebreak, with no geometry involved.
          if (best[e.to] === undefined || cost < best[e.to].cost) best[e.to] = { e: e, cost: cost }
        })
        Object.keys(best).forEach(function (to) {
          var e = best[to].e
          keep[e.from + '→' + e.to] = true
        })
        chosen = drawable.filter(function (e) { return keep[e.from + '→' + e.to] === true })
        hiddenCount = drawable.length - chosen.length
      }
      shared.wireStats = {
        drawn: chosen.length,
        hidden: hiddenCount,
        total: drawable.length,
        relations: relationStats(drawableAll, chosen),
      }

      return { chosen: chosen, hiddenCount: hiddenCount, stats: shared.wireStats }
    }

    module.exports = { chooseEdges }
    return module.exports
  },
})

// All skins emit from final geometry. No stage repairs SVG strings afterwards.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/emit',
  factory: (require) => {
    var geometry = require('dsh-cdd-lens/routing/geometry')
    /**
     * 两个端点之间的三次贝塞尔。
     *
     * 控制点沿水平方向外推，所以线离开出端口时是朝右的、进入入端口时是朝左的，
     * 两头都正对着小圈。这就是 jsoncrack 那种观感，也是它比折线好看的原因：
     * 没有硬折角，且起点方向明确告诉你是从哪里出来的。
     */
    function bezierPath(a, b) {
      var dx = Math.max(36, Math.abs(b.x - a.x) * .5)
      return 'M' + a.x + ',' + a.y
        + ' C' + (a.x + dx) + ',' + a.y
        + ' ' + (b.x - dx) + ',' + b.y
        + ' ' + b.x + ',' + b.y
    }

    /** 一条线上的一串点怎么连：两点用贝塞尔，多点用平滑折线。 */
    function pathFrom(pts) {
      if (pts.length < 2) return ''
      if (pts.length === 2) return bezierPath(pts[0], pts[1])
      var d = 'M' + pts[0].x + ',' + pts[0].y
      for (var i = 1; i < pts.length; i += 1) d += ' L' + pts[i].x + ',' + pts[i].y
      return d
    }

    /**
     * 一条线上放几个箭头，放在哪。
     *
     * 箭头是看方向的唯一线索，所以宁可多。短线上至少一个；线一长就按间距铺，
     * 最多 6 个——再多就把线糊成一条毛毛虫了。首尾各留 14px，免得箭头压在
     * 端口小圈或目标卡片上。
     */
    /** 贝塞尔上的一点和切线角（t 在 0..1）。 */
    function bezierAt(a, c1, c2, b, t) {
      var mt = 1 - t
      var x = mt*mt*mt*a.x + 3*mt*mt*t*c1.x + 3*mt*t*t*c2.x + t*t*t*b.x
      var y = mt*mt*mt*a.y + 3*mt*mt*t*c1.y + 3*mt*t*t*c2.y + t*t*t*b.y
      var dx = 3*mt*mt*(c1.x-a.x) + 6*mt*t*(c2.x-c1.x) + 3*t*t*(b.x-c2.x)
      var dy = 3*mt*mt*(c1.y-a.y) + 6*mt*t*(c2.y-c1.y) + 3*t*t*(b.y-c2.y)
      return { x: x, y: y, angle: Math.atan2(dy, dx) * 180 / Math.PI }
    }

    /** 这条线的控制点；多点（跨层）的线不适用，返回 null。 */
    function bezierControls(pts) {
      if (pts.length !== 2) return null
      var a = pts[0], b = pts[1]
      var dx = Math.max(36, Math.abs(b.x - a.x) * .5)
      return { a: a, c1: { x: a.x + dx, y: a.y }, c2: { x: b.x - dx, y: b.y }, b: b }
    }

    function arrowDistances(total, every) {
      if (total <= 0) return []
      if (total < every) return [total * .55]
      var step = Math.max(56, every)
      var count = Math.floor((total - 28) / step)
      if (count < 1) count = 1
      if (count > 6) count = 6
      var out = []
      for (var i = 1; i <= count; i += 1) out.push(total * i / (count + 1))
      return out
    }

    function emitWires(route,hops) {
      var wires=[],labels=[],junctions=[],arrows=[]
      route.polylines.forEach(function (line) {
        var pts=line.pts
        if (line.status==='blocked' || pts.length<2) return
        var minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity
        var see=function (x,y) { minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y) }
        pts.forEach(function (p) { see(p.x,p.y) })
        // 路径：两点走贝塞尔，跨层（有虚节点拐点）走折线。
        var d = pathFrom(pts)
        var arcs = []
        wires.push({ id:line.id,d:d,type:line.type,faded:line.faded,from:line.from,to:line.to,
          fromFile:line.fromFile,toFile:line.toFile,pts:pts,arcs:arcs,
          sourcePort:line.sourcePort,targetPort:line.targetPort,
          bounds:{minX:minX,minY:minY,maxX:maxX,maxY:maxY} })
        var total=geometry.length(pts),distances=arrowDistances(total,route.ARROW_EVERY)
        var curve = bezierControls(pts)
        distances.forEach(function (distance,j) {
          // 两点线走的是贝塞尔，箭头必须落在曲线上，不能按弦估。
          var at = curve !== null
            ? bezierAt(curve.a, curve.c1, curve.c2, curve.b, Math.min(1, Math.max(0, distance / total)))
            : geometry.atDistance(pts,distance)
          if (arcs.some(function (arc) { return Math.abs(at.y-arc.y)<0.5 && at.x>=arc.lo-2 && at.x<=arc.hi+2 })) return
          arrows.push({ id:line.id+':head'+j,wireId:line.id,from:line.from,to:line.to,type:line.type,
            x:at.x,y:at.y,angle:at.angle,faded:line.faded })
        })
        // Position by walked distance, so a two-point route is a valid route.
        var mid=geometry.atDistance(pts,total/2)
        labels.push({id:line.id,x:mid.x,y:mid.y,type:line.type})
      })
      return {wires:wires,labels:labels,junctions:junctions,arrows:arrows,unrouted:route.unrouted || []}
    }
    return {emitWires}
  },
})

// dsh-cdd-lens — The gather overlay: a selected node's neighbours at its side.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/gather',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared

    /** Does a sit on top of b? */
    function overlapping(a, b, margin) {
      return Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) + margin > 0
        && Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) + margin > 0
    }

    /**
     * A node the user dragged out of a running gather is free of both the
     * overlay and its frame.
     *
     * The overlay re-seats its nodes on every layout — which is what made a
     * gathered card undraggable: moveNode wrote the coordinate, the next
     * layout put the card straight back beside the focus, and the wires never
     * saw it move. engine/selection marks the dragged id in gather.freed;
     * here that mark strips the frame membership before restackBoxes can seat
     * the card again, and applyGather below leaves it where it was dropped.
     * Releasing the gather clears the mark, and the next layout seats the
     * node exactly as if none of this had happened.
     *
     * @param place - the positioned nodes, marked in place.
     * @returns how many nodes are freed.
     */
    function freeGatherDragged(place) {
      var gather = shared.gather
      if (gather === null || gather === undefined || gather.freed === undefined) return 0
      var freed = 0
      place.placed.forEach(function (p) {
        if (gather.freed[p.id] !== true) return
        p.boxKey = undefined
        // 用户把它拖出收拢列了：这就是他放的位置，分离重叠不许再推它。
        // 不标 manual 的话，收拢列的分离过程会把它推回旁边一格。
        p.manual = true
        freed += 1
      })
      return freed
    }

    /**
     * Pull the selected node's callers to its left and its callees to its
     * right, as two columns hugging it.
     *
     * An overlay, not a placement: it runs after the skin, the hand-placed
     * coordinates and the restack have all had their say, and it wins over
     * them, because a node whose neighbours sit two screens away answers the
     * one question the drawing exists for — what does this touch — only if
     * you can see them. Nothing is recorded for the trip back. The override
     * is recomputed from scratch on every layout, so releasing it is simply
     * running the same layout without it: wherever the skin and the user say
     * the nodes stand NOW is where they return to, and a drag or an expansion
     * mid-gather can never resurrect a stale coordinate as a ghost.
     *
     * The edge-focus camera is itself an answer to "what is around this
     * relation"; gathering on top of it would rearrange the chain it is
     * showing, so the overlay steps aside while it is active.
     *
     * @param graph - the graph being drawn.
     * @param place - the positioned nodes, moved in place.
     * @param metrics - box metrics; the column gap and spacing come from it.
     * @returns how many nodes were moved.
     */
    function applyGather(graph, place, metrics) {
      var gather = shared.gather
      if (gather === null || gather === undefined) return 0
      if (shared.edgeFocus !== null && shared.edgeFocus !== undefined) return 0
      var byId = {}
      place.placed.forEach(function (p) { byId[p.id] = p })
      var focus = byId[gather.focus]
      if (focus === undefined) return 0

      // A node that is both caller and callee keeps one seat — the upstream
      // one, since that is the side that explains where it came from.
      var seen = {}
      var ups = []
      var downs = []
      graph.edges.forEach(function (e) {
        if (e.to === gather.focus && e.from !== gather.focus
          && byId[e.from] !== undefined && seen[e.from] !== true) {
          seen[e.from] = true
          ups.push(byId[e.from])
        }
        if (e.from === gather.focus && e.to !== gather.focus
          && byId[e.to] !== undefined && seen[e.to] !== true) {
          seen[e.to] = true
          downs.push(byId[e.to])
        }
      })

      var GAP = metrics.LAYER_GAP_X
      var INNER_GAP_Y = metrics.INNER_GAP_Y
      var NEAR = metrics.PORT_STUB
      var freed = gather.freed || {}
      var moved = 0
      var seated = []

      var seatColumn = function (nodes, rightward) {
        if (nodes.length === 0) return
        // In the order they already stand, top to bottom: the gather moves
        // them as little as it can.
        var ordered = nodes.slice().sort(function (l, r) { return l.y - r.y || l.x - r.x })
        var total = ordered.reduce(function (acc, p) { return acc + p.h }, 0)
          + INNER_GAP_Y * (ordered.length - 1)
        var y = focus.y + focus.h / 2 - total / 2
        ordered.forEach(function (p) {
          // Dragged out of the column by the user mid-gather: it stays where
          // it was dropped and takes no seat here.
          if (freed[p.id] === true) return
          var x = rightward ? focus.x + focus.w + GAP : focus.x - GAP - p.w
          var y0 = y
          y += p.h + INNER_GAP_Y
          // Already there, near enough: an animation about nothing is noise.
          if (Math.abs(p.x - x) < NEAR && Math.abs(p.y - y0) < NEAR) return
          p.x = x
          p.y = y0
          p.gathered = true
          // 被收拢的节点也算「用户放好的位置」：分离重叠那一步不许再推它。
          // 以前 gather 之后紧跟 restackBoxes 把它们捡回去，所以不需要这个标记；
          // 现在收拢跑在分离之后，不标的话刚排好的列会被推开。
          p.manual = true
          // Out of its frame: the frame would otherwise restack it straight
          // back into its old slot on this very pass.
          p.boxKey = undefined
          // 重新归层：它现在站的那一列就是它的新层。分层布局按 layer 定 x，
          // 一个还报着旧层的卡片会被排回原来的列，收拢就白做了。
          var targetLayer = typeof focus.layer === 'number'
            ? focus.layer + (rightward ? 1 : -1)
            : undefined
          if (targetLayer !== undefined) {
            p.layer = targetLayer
            p.flowLayer = targetLayer
          }
          seated.push(p)
          moved += 1
        })
      }
      seatColumn(ups, false)
      seatColumn(downs, true)

      // What a gathered node may not land on: the focus, and every node that
      // stays in its frame — read AFTER the seating stripped the movers, or a
      // moved node would collide with the ghost of where it stood. The frames
      // own their columns — restackBoxes puts their members back every layout —
      // so the gathered column gives way vertically instead of asking the
      // frame to move.
      var solid = place.placed.filter(function (p) { return p.boxKey !== undefined })
      // Frames do not move, so where the column lands on one, the column
      // slides down past whatever stands there — the focus stays the anchor
      // horizontally, and the hug stays readable even when the column grows
      // longer than the space beside the focus.
      seated.forEach(function (p) {
        var guard = 0
        var hit = true
        while (hit && guard < 50) {
          hit = false
          guard += 1
          for (var i = 0; i < solid.length; i += 1) {
            if (overlapping(p, solid[i], 1)) {
              p.y = solid[i].y + solid[i].h + INNER_GAP_Y
              hit = true
            }
          }
          for (var k = 0; k < seated.length; k += 1) {
            if (seated[k] !== p && overlapping(p, seated[k], 1)) {
              p.y = seated[k].y + seated[k].h + INNER_GAP_Y
              hit = true
            }
          }
        }
      })
      return moved
    }

    module.exports = { applyGather, freeGatherDragged }
    return module.exports
  },
})

// dsh-cdd-lens — Where things end up: fitting the drawing, and unpicking overlaps.
//
// Two halves of one job. A placement is proposed, and then it has to be made
// true: nothing off the top or left edge, nothing sitting on top of anything
// else, no anchor stranded outside the frame that owns it. Both halves read
// and write the same placed boxes, and splitting them across two files only
// made the order they run in harder to see.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/space',
  factory: (require) => {
    var module = { exports: {} }
    /**
     * The canvas has to hold everything that was drawn, not just the nodes.
     *
     * A wire leaves its node — into a channel, out along a bus lane, over a
     * hop — and a curve's control points reach further still. None of that is
     * inside any node's box, so sizing the canvas from node positions leaves
     * geometry at negative coordinates, and scrollLeft stops at zero: those
     * pixels cannot be brought into view by any amount of panning. They are
     * drawn and they are gone. So the size comes from the drawing.
     * @param place - the positioned nodes and file boxes.
     * @param drawn - wires, labels, junctions and arrows as emitted.
     * @param metrics - box metrics; its PAD is the margin kept around it all.
     * @returns the real bounds, and the shift that would clear the top left.
     */
    function fitExtent(place, drawn, metrics) {
      var PAD = metrics.PAD
      var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      var see = function (x, y) {
        if (typeof x !== 'number' || typeof y !== 'number') return
        if (!isFinite(x) || !isFinite(y)) return
        if (x < minX) minX = x
        if (x > maxX) maxX = x
        if (y < minY) minY = y
        if (y > maxY) maxY = y
      }
      var box = function (b) { see(b.x, b.y); see(b.x + b.w, b.y + b.h) }
      place.placed.forEach(box)
      ;(place.fileBoxes || []).forEach(box)
      ;(drawn.junctions || []).forEach(function (j) { see(j.x, j.y) })
      ;(drawn.labels || []).forEach(function (l) { see(l.x, l.y) })
      ;(drawn.arrows || []).forEach(function (a) { see(a.x, a.y) })
      ;(drawn.wires || []).forEach(function (wire) {
        if (wire.bounds) {
          see(wire.bounds.minX, wire.bounds.minY)
          see(wire.bounds.maxX, wire.bounds.maxY)
        } else {
          ;(wire.pts || []).forEach(function (p) { see(p.x,p.y) })
        }
      })
      if (minX === Infinity) return { dx: 0, dy: 0, minX: 0, minY: 0, maxX: 0, maxY: 0 }
      return {
        dx: Math.max(0, PAD - minX), dy: Math.max(0, PAD - minY),
        minX: minX, minY: minY, maxX: maxX, maxY: maxY,
      }
    }

    /**
     * Move everything the placement owns, so nothing sits left of or above
     * the origin.
     *
     * A node keeps the coordinate it was SAVED at in `baseX`/`baseY`. Dragging
     * writes that one back, so the margin the wires happened to need this time
     * never folds into a stored position and never accumulates across renders.
     *
     * Row labels travel with the rows they name. `rowBands` is deliberately
     * left where it is: `buildChannels` has already read it by the time
     * anything can need shifting, and nothing reads it afterwards.
     * @param place - nodes, file boxes and row labels, moved in place.
     * @param dx - how far right to move everything.
     * @param dy - how far down to move everything.
     */
    function shiftPlacement(place, dx, dy) {
      if (dx === 0 && dy === 0) return
      place.placed.forEach(function (p) {
        if (p.baseX === undefined) { p.baseX = p.x; p.baseY = p.y }
        p.x += dx
        p.y += dy
      })
      ;(place.fileBoxes || []).forEach(function (b) { b.x += dx; b.y += dy })
      ;(place.rows || []).forEach(function (row) { row.x += dx; row.y += dy })
    }

    /**
     * Move the placement together with the polylines routed through it.
     *
     * Only the orthogonal router keeps polylines of its own. The layered one
     * reads each wire off the two boxes it joins, so for that path moving the
     * boxes and asking again is the same translation — see `layout`.
     * @param place - nodes, file boxes and row labels, moved in place.
     * @param route - the routed polylines, moved in place.
     * @param dx - how far right to move everything.
     * @param dy - how far down to move everything.
     */
    function shiftDrawing(place, route, dx, dy) {
      if (dx === 0 && dy === 0) return
      shiftPlacement(place, dx, dy)
      route.polylines.forEach(function (line) {
        line.pts.forEach(function (pt) { pt.x += dx; pt.y += dy })
      })
    }

    /**
     * No box may sit on top of another.
     *
     * Automatic placement never overlaps, but a coordinate the user dragged is
     * written in verbatim, and two anchors dropped near each other simply
     * covered one another — the one underneath unreadable and unclickable, with
     * wires then routed straight through both. Overlap is never what was meant
     * by dropping a box somewhere, so the boxes are separated afterwards.
     *
     * Pairs are pushed apart along whichever axis they overlap least, which
     * moves each box the shortest distance that resolves it. A box the user
     * placed by hand yields less than one the layout placed, so the drag is
     * still respected; when both were placed by hand they share the push.
     *
     * @param place - placed boxes, moved in place.
     * @param metrics - box metrics; only the gap sizes are read.
     * @returns how many boxes ended up moving.
     */
    function separateOverlaps(place, metrics) {
      // Anchors inside a frame are laid out again by restackBoxes immediately
      // after this, so pushing them apart here is work that is then thrown
      // away — and it is the expensive kind: every pair, twelve times over.
      // At a thousand anchors that was six million comparisons per layout, on
      // a layout that reruns on zoom, selection and a width poll.
      // Anchors a frame will lay out again are still skipped — that pass throws
      // this work away, and it is the expensive kind: every pair, twelve times
      // over. But an anchor the user placed is NOT laid out again any more, so
      // it has to be in here or two dragged cards simply cover each other.
      var boxes = place.placed.filter(function (p) {
        return p.boxKey === undefined || p.manual === true || p.pinned === true
      })
      if (boxes.length < 2) return 0
      var MARGIN = Math.max(4, Math.round(metrics.INNER_GAP_X / 4))
      var PASSES = 12
      var moved = {}

      for (var pass = 0; pass < PASSES; pass += 1) {
        var touched = false
        for (var i = 0; i < boxes.length; i += 1) {
          for (var j = i + 1; j < boxes.length; j += 1) {
            var a = boxes[i]
            var b = boxes[j]
            var ix = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) + MARGIN
            var iy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) + MARGIN
            if (ix <= 0 || iy <= 0) continue

            // Whichever direction needs the least travel.
            var horizontal = ix < iy
            var push = horizontal ? ix : iy
            // A hand-placed box is the one that was meant to be where it is.
            var aHeld = a.manual === true || a.pinned === true
            var bHeld = b.manual === true || b.pinned === true
            var aShare = aHeld === bHeld ? .5 : (aHeld ? .25 : .75)
            var bShare = 1 - aShare

            if (horizontal) {
              var dir = (a.x + a.w / 2) <= (b.x + b.w / 2) ? -1 : 1
              a.x += dir * push * aShare
              b.x -= dir * push * bShare
            } else {
              var dirY = (a.y + a.h / 2) <= (b.y + b.h / 2) ? -1 : 1
              a.y += dirY * push * aShare
              b.y -= dirY * push * bShare
            }
            moved[a.id] = true
            moved[b.id] = true
            touched = true
          }
        }
        if (!touched) break
      }
      return Object.keys(moved).length
    }

    /**
     * A saved coordinate may not strand its box outside the drawing.
     *
     * A position the user dragged wins across refresh, expansion and reindex —
     * which is right, until the layout itself changes shape underneath it. A
     * point that made sense when layers were rows can sit two thousand pixels
     * from anything once they are columns, and the anchor is then off alone in
     * an empty quarter of the canvas with no way back except dragging it.
     *
     * The drag is kept as a direction: the box is pulled back only as far as
     * the edge of where everything else actually is.
     *
     * @param place - placed boxes, moved in place.
     * @param metrics - box metrics; only the gaps are read.
     * @returns how many boxes were pulled back.
     */
    function reclaimStrays(place, metrics, avail) {
      var boxes = place.placed
      var anchored = boxes.filter(function (p) { return p.manual !== true })
      if (anchored.length === 0 || anchored.length === boxes.length) return 0
      var GAP = metrics.BOX_GAP_X
      var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      anchored.forEach(function (p) {
        if (p.x < minX) minX = p.x
        if (p.y < minY) minY = p.y
        if (p.x + p.w > maxX) maxX = p.x + p.w
        if (p.y + p.h > maxY) maxY = p.y + p.h
      })
      // Room to actually put something somewhere. Clamping to the automatic
      // bounds plus one gap meant the drawing never grew for a drag: a node
      // pulled below everything else was pushed straight back up beside the
      // last row, so the canvas could only ever be the size the layout wanted.
      //
      // The bound that matters is the canvas, not the drawing. A pointer can
      // only drop something where it can reach, and that is the visible area;
      // a drawing 250 tall inside a 1200 canvas has to accept a drag 400 down.
      // What this exists to catch is the other case — a coordinate saved when
      // the graph was ten times this size, stranding one card in an empty
      // quarter — and that is still far outside a canvas away. canvasWidth is
      // measured from the real viewport, so nothing here is a pixel count.
      // Distance from the automatic bounds cannot tell these two apart, and
      // every version of that guess was wrong in one direction or the other: a
      // tight clamp meant the drawing never grew for a drag at all — a node
      // pulled below everything went straight back beside the last row — and a
      // loose one let a coordinate saved under a three-times-larger layout
      // strand one card in an empty quarter. The viewport is no help either;
      // the canvas scrolls, so off-screen is somewhere a pointer can reach.
      //
      // What actually separates them is company. A drag lands in the drawing
      // the user is looking at, so something is beside it. A coordinate left
      // over from a layout that no longer exists has nothing near it for
      // further than the whole drawing is wide. So that is the test, and it is
      // measured against the drawing itself rather than any pixel count.
      var span = Math.max(maxX - minX, maxY - minY, GAP)
      var pulled = 0
      boxes.forEach(function (p) {
        if (p.manual !== true) return
        var nearest = Infinity
        for (var i = 0; i < anchored.length; i += 1) {
          var q = anchored[i]
          var gapX = Math.max(0, q.x - (p.x + p.w), p.x - (q.x + q.w))
          var gapY = Math.max(0, q.y - (p.y + p.h), p.y - (q.y + q.h))
          var away = Math.max(gapX, gapY)
          if (away < nearest) nearest = away
        }
        if (nearest <= span) return
        var x = Math.min(Math.max(p.x, minX - GAP), maxX + GAP - p.w)
        var y = Math.min(Math.max(p.y, minY - GAP), maxY + GAP - p.h)
        if (x !== p.x || y !== p.y) { p.x = x; p.y = y; pulled += 1 }
      })
      return pulled
    }

    /**
     * Inside a frame, one column — around whatever the user put there.
     *
     * A drag used to decide the ORDER and nothing else: members were read top
     * to bottom as they sat and then laid out again down the frame, which
     * overwrote the coordinate the pointer had just produced. Every node in
     * every skin carries a boxKey — a file on the board, a layer in the tiers,
     * a column in the flow — so that made the whole drawing immovable: a node
     * dragged 380 across and 260 down landed back on the pixel it started on.
     *
     * A coordinate the user chose now survives. Automatic members still form
     * one column, and they step over the vertical bands a held anchor covers
     * rather than stacking underneath it. The frame keeps its grid slot and
     * its size — growing it to swallow a dragged anchor is what put frames on
     * top of each other — so an anchor dragged clear of its frame simply sits
     * outside it, held inside the drawing as a whole by reclaimStrays.
     *
     * @param place - boxes and placed anchors; anchors are moved in place.
     * @param metrics - box metrics; padding, header and inner gap are read.
     * @returns how many anchors were laid out again.
     */
    function restackBoxes(place, metrics) {
      var boxes = place.fileBoxes
      if (boxes === undefined || boxes.length === 0) return 0
      var BOX_PAD = metrics.BOX_PAD
      var BOX_HEAD = metrics.BOX_HEAD
      var INNER_GAP_Y = metrics.INNER_GAP_Y
      var members = {}
      place.placed.forEach(function (p) {
        if (p.boxKey === undefined) return
        ;(members[p.boxKey] = members[p.boxKey] || []).push(p)
      })
      var moved = 0
      boxes.forEach(function (box) {
        var mine = members[box.key]
        if (mine === undefined || mine.length === 0) return
        var left = box.x + BOX_PAD
        var inner = box.w - BOX_PAD * 2
        var free = []
        mine.forEach(function (p) {
          if (p.manual !== true && p.pinned !== true) free.push(p)
        })
        free.sort(function (l, r) { return l.y - r.y || l.x - r.x })
        // Every held anchor over this column is in the way of it, not only the
        // ones that belong to this frame: a card dragged across from the next
        // file is sitting in this column whatever its boxKey says. One dragged
        // off to the side blocks nothing.
        var bands = place.placed
          .filter(function (p) { return p.manual === true || p.pinned === true })
          .filter(function (p) { return p.x < left + inner && p.x + p.w > left })
          .map(function (p) { return [p.y, p.y + p.h] })
          .sort(function (a, b) { return a[0] - b[0] })
        var y = box.y + BOX_HEAD + BOX_PAD
        free.forEach(function (p) {
          // Bands are sorted, so walking them once is enough: clearing one can
          // only push this row into a later band, never an earlier one.
          for (var i = 0; i < bands.length; i += 1) {
            if (y < bands[i][1] && y + p.h > bands[i][0]) y = bands[i][1] + INNER_GAP_Y
          }
          if (p.x !== left || p.y !== y || p.w !== inner) moved += 1
          p.x = left
          p.y = y
          p.w = inner
          y += p.h + INNER_GAP_Y
        })
      })
      return moved
    }

    module.exports = { fitExtent, shiftPlacement, shiftDrawing, separateOverlaps, reclaimStrays, restackBoxes }
    return module.exports
  },
})

// dsh-cdd-lens — 分层布局（自研 Sugiyama）。唯一的布局，没有皮肤。
//
// 端口：从 /Users/a1/Workspace/WORKSPACE/visual_map/js/graph-layout.js 移植，
// 四步与原实现一致，只把 node 的取法换成 CDD 的 anchor 图：
//
//   1. 消环   —— DFS 找回向边，逻辑上反转它们使图变成 DAG
//   2. 分层   —— 最长路径法：layer[v] = max(layer[前驱]) + 1
//   3. 排序   —— 跨层长边拆成虚节点链，虚节点与真实节点一起做重心排序；
//                交叉数 = 每个层边界上「下层序号序列的严格逆序对数」
//   4. 坐标   —— 层定 x、层内序号定 y、各层垂直居中；
//                虚节点坐标输出成边的 bendPoints，直接喂给 routing/emit
//
// 为什么不用 ELK：纯 ELK 在这张图上性能差。自研这套 400 行、零依赖、确定性。
//
// 输入是 CDD 的图：`graph.nodes[id]` 就是 anchor 记录，`graph.ui[id]` 是按钮状态，
// 布局只读前者，一个字段都不写回。
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/sugiyama',
  factory: (require) => {
    var module = { exports: {} }

    var NODE_W = 180
    var NODE_H = 46
    var DUMMY_H = 10
    var GAP_X = 110
    var GAP_Y = 26
    var MARGIN = 40
    var SWEEPS = 12

    // 端口小圈 11px，CSS 写 left/right:-6px，所以圆心落在节点边界外 0.5px。
    // 线的端点就是这个圆心；这里和 layout/layout.js 的 PORT_OFFSET 必须一致。
    var PORT_OFFSET = 0.5

    /** 端点：入在左、出在右，各外探 PORT_OFFSET。 */
    function portsFor(x, y, w, h) {
      return {
        in: { x: x - PORT_OFFSET, y: y + h / 2 },
        out: { x: x + w + PORT_OFFSET, y: y + h / 2 },
      }
    }

    /**
     * 把一个 CDD 图排成分层图。
     *
     * @param graph - { nodes: {id: anchor}, edges: [{from,to,types}] }。
     * @param included - 这一轮要画的 id（layoutScope 决定）。
     * @param metrics - boxMetrics 的结果，提供 sizeOf / label / PAD。
     * @returns { placed, polylines, fileBoxes, canvasY, crossings, layers }。
     */
    function sugiyama(graph, included, metrics, placedAt) {
      var ids = included.filter(function (id) { return graph.nodes[id] !== undefined })
      var idSet = {}
      ids.forEach(function (id) { idSet[id] = true })

      // 只画两端都在屏幕上的边。
      var edges = graph.edges.filter(function (e) {
        return idSet[e.from] === true && idSet[e.to] === true && e.from !== e.to
      })

      if (ids.length === 0) {
        return { placed: [], polylines: [], canvasY: MARGIN, crossings: 0, layers: 0 }
      }

      // ---------- 1. 消环：迭代 DFS，GRAY 邻居即回向边 ----------
      var out = {}
      ids.forEach(function (id) { out[id] = [] })
      edges.forEach(function (e) { out[e.from].push(e.to) })

      var WHITE = 0, GRAY = 1, BLACK = 2
      var color = {}
      ids.forEach(function (id) { color[id] = WHITE })
      var backEdge = {}
      ids.forEach(function (s) {
        if (color[s] !== WHITE) return
        color[s] = GRAY
        var stack = [[s, 0]]
        while (stack.length > 0) {
          var top = stack[stack.length - 1]
          var v = top[0]
          var adj = out[v]
          if (top[1] < adj.length) {
            var w = adj[top[1]]
            top[1] += 1
            if (color[w] === WHITE) { color[w] = GRAY; stack.push([w, 0]) }
            else if (color[w] === GRAY) { backEdge[v + '\u0000' + w] = true }
          } else {
            color[v] = BLACK
            stack.pop()
          }
        }
      })

      // ---------- 2. DAG 化 + 最长路径分层 ----------
      var dagEdges = edges.map(function (e) {
        var reversed = backEdge[e.from + '\u0000' + e.to] === true
        return { edge: e, from: reversed ? e.to : e.from, to: reversed ? e.from : e.to, reversed: reversed }
      })
      var dagOut = {}, dagIn = {}, indeg = {}
      ids.forEach(function (id) { dagOut[id] = []; dagIn[id] = []; indeg[id] = 0 })
      dagEdges.forEach(function (d) {
        dagOut[d.from].push(d.to)
        dagIn[d.to].push(d.from)
        indeg[d.to] += 1
      })
      var layerOf = {}
      var queue = ids.filter(function (id) { return indeg[id] === 0 })
      var left = 0
      while (queue.length > 0) {
        var v = queue.shift()
        left += 1
        var l = 0
        dagIn[v].forEach(function (p) { if (layerOf[p] + 1 > l) l = layerOf[p] + 1 })
        layerOf[v] = l
        dagOut[v].forEach(function (w) {
          indeg[w] -= 1
          if (indeg[w] === 0) queue.push(w)
        })
      }
      // 有环残留时把没排到的塞到最后一层，不让它们消失。
      var layerCount = 1
      ids.forEach(function (id) {
        if (layerOf[id] === undefined) layerOf[id] = 0
        if (layerOf[id] + 1 > layerCount) layerCount = layerOf[id] + 1
      })

      // ---------- 3a. 跨层边拆虚节点 ----------
      var layers = []
      for (var i = 0; i < layerCount; i += 1) layers.push([])
      ids.forEach(function (id) { layers[layerOf[id]].push(id) })

      var unitAdj = {}
      ids.forEach(function (id) { unitAdj[id] = {} })
      var segsByBoundary = []
      for (var b = 0; b < layerCount - 1; b += 1) segsByBoundary.push([])
      var dummyOfEdge = {}
      var reversedDummy = {}
      var dummySeq = 0

      function pushUnit(f, t, l) {
        segsByBoundary[l].push([f, t])
        unitAdj[f][t] = true
        unitAdj[t][f] = true
      }

      dagEdges.forEach(function (d, i) {
        var span = layerOf[d.to] - layerOf[d.from]
        if (span <= 1) { pushUnit(d.from, d.to, layerOf[d.from]); return }
        var chain = []
        for (var k = 1; k < span; k += 1) {
          var did = '\u0000vd' + (dummySeq++)
          chain.push(did)
          layers[layerOf[d.from] + k].push(did)
          unitAdj[did] = {}
        }
        dummyOfEdge[i] = d.reversed ? chain.slice().reverse() : chain
        if (d.reversed) chain.forEach(function (k) { reversedDummy[k] = true })
        var seq = [d.from].concat(chain).concat([d.to])
        for (var s = 0; s + 1 < seq.length; s += 1) pushUnit(seq[s], seq[s + 1], layerOf[d.from] + s)
      })

      // ---------- 3b. 重心排序 + 交叉计数 ----------
      function indexMap(layerNodes) {
        var m = {}
        layerNodes.forEach(function (id, i) { m[id] = i })
        return m
      }
      function sortLayer(layerNodes, neighborIndex) {
        var keys = layerNodes.map(function (id, i) {
          var sum = 0, cnt = 0
          Object.keys(unitAdj[id] || {}).forEach(function (nb) {
            if (neighborIndex[nb] !== undefined) { sum += neighborIndex[nb]; cnt += 1 }
          })
          return { id: id, i: i, key: cnt ? sum / cnt : i }
        })
        keys.sort(function (a, b) { return a.key - b.key || a.i - b.i })
        keys.forEach(function (k, i) { layerNodes[i] = k.id })
      }
      function countInversions(arr) {
        var inv = 0
        var buf = new Array(arr.length)
        function mergeSort(lo, hi) {
          if (hi - lo < 2) return
          var mid = (lo + hi) >> 1
          mergeSort(lo, mid); mergeSort(mid, hi)
          var i = lo, j = mid, k = lo
          while (i < mid && j < hi) {
            if (arr[i] <= arr[j]) buf[k++] = arr[i++]
            else { buf[k++] = arr[j++]; inv += mid - i }
          }
          while (i < mid) buf[k++] = arr[i++]
          while (j < hi) buf[k++] = arr[j++]
          for (var t = lo; t < hi; t += 1) arr[t] = buf[t]
        }
        mergeSort(0, arr.length)
        return inv
      }
      function countCrossings(order) {
        var pos = {}
        order.forEach(function (layer, l) { layer.forEach(function (id, i) { pos[id] = { l: l, i: i } }) })
        var c = 0
        for (var l = 0; l < order.length - 1; l += 1) {
          var bucket = segsByBoundary[l]
          if (bucket.length < 2) continue
          var segs = bucket.map(function (s) { return [pos[s[0]].i, pos[s[1]].i] })
          segs.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1] })
          c += countInversions(segs.map(function (s) { return s[1] }))
        }
        return c
      }

      var order = layers.map(function (l) { return l.slice() })
      var best = countCrossings(order)
      var bestOrder = order.map(function (l) { return l.slice() })
      for (var it = 0; it < SWEEPS; it += 1) {
        for (var l2 = 1; l2 < order.length; l2 += 1) sortLayer(order[l2], indexMap(order[l2 - 1]))
        for (var l3 = order.length - 2; l3 >= 0; l3 -= 1) sortLayer(order[l3], indexMap(order[l3 + 1]))
        var c2 = countCrossings(order)
        if (c2 < best) { best = c2; bestOrder = order.map(function (l) { return l.slice() }) }
      }
      order = bestOrder

      // ---------- 4. 坐标 ----------
      var isDummy = function (id) { return idSet[id] !== true }
      var sizes = {}
      var label = {}
      ids.forEach(function (id) {
        var size = metrics && metrics.sizeOf ? metrics.sizeOf(id, NODE_W * 2) : { w: NODE_W, h: NODE_H }
        sizes[id] = { w: size.w, h: size.h }
        label[id] = metrics && metrics.label ? metrics.label[id] : undefined
      })
      var rowH = function (id) { return isDummy(id) ? DUMMY_H : sizes[id].h }

      // 一列一个宽度：层内左沿对齐是分层图可读性的底线，逐个按文字定宽会排出
      // 七个不同的右沿。取全图最宽的那个名字定列宽，所有节点一样宽。
      var columnW = 0
      ids.forEach(function (id) { if (sizes[id].w > columnW) columnW = sizes[id].w })
      ids.forEach(function (id) { sizes[id].w = columnW })

      var layerHeights = order.map(function (l) {
        var total = 0
        l.forEach(function (id) { total += rowH(id) })
        return total + Math.max(0, l.length - 1) * GAP_Y
      })
      var maxH = 0
      layerHeights.forEach(function (h) { if (h > maxH) maxH = h })

      var placed = []
      var dummyPos = {}
      var placeOfId = {}
      // 反向边（回向边）的虚节点不放在行里：放到整张图下面的一条旁路上。
      // 放在行里的话，它从源节点的右侧端口一路横穿过去，会穿过同层其它盒子。
      var bypassY = MARGIN + maxH + 34
      // 已经画在屏幕上的节点位置冻结：点开上/下展开时，原来的节点不许跳。
      //
      // 以前每层都按自己的高度垂直居中，新节点一进来就把老层整体推走——
      // 实测点一次 ↓，父节点下移 81px。这里改成：有位置的照旧，没位置的往
      // 该层「已有内容的下方」排。整张图第一次画（没有任何位置）时行为不变。
      var frozen = {}
      if (typeof placedAt === 'function') {
        ids.forEach(function (id) {
          var at = placedAt(id)
          if (at === null || at === undefined) return
          if (typeof at.x !== 'number' || typeof at.y !== 'number') return
          frozen[id] = { x: at.x, y: at.y, w: at.w, h: at.h, layer: at.layer }
        })
      }
      var frozenCount = Object.keys(frozen).length
      // 冻结节点的层不动：它已经在那一列了，重算层只会让它在列之间跳。
      var frozenLayers = {}
      Object.keys(frozen).forEach(function (id) { frozenLayers[frozen[id].layer] = true })

      order.forEach(function (layerNodes, l) {
        var colX = MARGIN + l * (columnW + GAP_X)
        var y = MARGIN + (maxH - layerHeights[l]) / 2
        // 这一层里已经站着的节点，按它们的 y 排好，新节点接在下面。
        var standing = []
        if (frozenCount > 0) {
          layerNodes.forEach(function (id) {
            if (frozen[id] !== undefined) standing.push(frozen[id])
          })
          standing.sort(function (a, b) { return a.y - b.y })
          if (standing.length > 0) {
            var bottom = standing[standing.length - 1]
            y = bottom.y + bottom.h + GAP_Y
            colX = standing[0].x
          }
        }
        layerNodes.forEach(function (id) {
          if (isDummy(id)) {
            if (reversedDummy[id] === true) {
              // 底部旁路：只占 x，y 统一在图下方。
              dummyPos[id] = { x: colX + columnW / 2, y: bypassY }
              return
            }
            dummyPos[id] = { x: colX + columnW, y: y + DUMMY_H / 2 }
            y += DUMMY_H + GAP_Y
            return
          }
          if (frozen[id] !== undefined) {
            // 位置照旧，一个像素都不动；只把它记进 placeOfId 供布线用。
            var keep = frozen[id]
            // 宽度也用**它画着时的那一个**：新来一个名字更长的邻居会把全图
            // 列宽推大，跟着走的话老卡片会自己变宽——那也是一种跳变。
            var keepW = typeof keep.w === 'number' ? keep.w : sizes[id].w
            var keepRec = {
              id: id, node: graph.nodes[id], anchor: graph.nodes[id],
              x: keep.x, y: keep.y, w: keepW, h: sizes[id].h,
              file: graph.nodes[id].file,
              layer: keep.layer, tree: 0,
              label: label[id],
              ports: portsFor(keep.x, keep.y, keepW, sizes[id].h),
              flowDir: 'ltr',
              boxKey: graph.nodes[id].file,
              frozen: true,
            }
            placed.push(keepRec)
            placeOfId[id] = keepRec
            return
          }
          var w = sizes[id].w
          var h = sizes[id].h
          var rec = {
            id: id, node: graph.nodes[id], anchor: graph.nodes[id],
            x: colX, y: y, w: w, h: h,
            file: graph.nodes[id].file,
            layer: l, tree: 0,
            label: label[id],
            ports: portsFor(colX, y, w, h),
            flowDir: 'ltr',
            boxKey: graph.nodes[id].file,
          }
          placed.push(rec)
          placeOfId[id] = rec
          y += h + GAP_Y
        })
      })

      // ---------- 边 → polylines（emit 直接吃这个） ----------
      var polylines = []
      dagEdges.forEach(function (d, i) {
        var a = placeOfId[d.edge.from]
        var b = placeOfId[d.edge.to]
        if (a === undefined || b === undefined) return
        var dummies = (dummyOfEdge[i] || []).map(function (k) {
          var p = dummyPos[k]
          return p === undefined ? null : { x: p.x, y: p.y }
        }).filter(Boolean)
        var types = d.edge.types || ['call']
        // 反向边（回向边）走底部旁路。光有旁路点不够：直接从源节点的右侧端口
        // 连到旁路点，会横穿源节点自己那一层的其它盒子。所以拆成三段——
        //   从端口先下降到旁路高度（垂直，贴着端口那一列的右沿，不压任何盒子）
        //   → 沿旁路横走到目标那一列
        //   → 再垂直上升到目标端口
        var pts
        if (d.reversed && dummies.length > 0) {
          var startPort = a.ports.out
          var endPort = b.ports.in
          pts = [{ x: startPort.x, y: startPort.y }]
          pts.push({ x: startPort.x, y: bypassY })
          pts = pts.concat(dummies.slice(0, dummies.length - 1))
          pts.push({ x: endPort.x, y: bypassY })
          pts.push({ x: endPort.x, y: endPort.y })
        } else {
          pts = [a.ports.out].concat(dummies).concat([b.ports.in])
        }
        polylines.push({
          id: d.edge.from + '\u2192' + d.edge.to + ':' + types.join(','),
          from: d.edge.from, to: d.edge.to,
          type: types[0], types: types,
          reversed: d.reversed,
          faded: false,
          fromFile: a.file, toFile: b.file,
          pts: pts,
          sourcePort: { side: 'right', point: a.ports.out },
          targetPort: { side: 'left', point: b.ports.in },
          status: 'ok',
        })
      })

      return {
        placed: placed,
        polylines: polylines,
        canvasY: bypassY + 60,
        crossings: best,
        layers: layerCount,
        width: MARGIN * 2 + layerCount * columnW + Math.max(0, layerCount - 1) * GAP_X,
        height: MARGIN * 2 + maxH,
      }
    }

    module.exports = { sugiyama }
    return module.exports
  },
})

// dsh-cdd-lens — One graph in, one drawing out: the stages in order.
//
// 只有一条路径，没有皮肤。分层由 layout/sugiyama 自己算——不再问服务端要 `/chain`。
//
// 这条管线是照 /Users/a1/Workspace/WORKSPACE/visual_map 重写的：
//   数据(graph) → 分层布局(sugiyama) → 边折线(polylines) → emit 成 SVG 路径
// visual_map 里布局与布线解耦，靠的是 `edge.bendPoints` 这一个契约；这里也一样，
// sugiyama 把跨层边的拐点算好放进 pts，emit 只管照着画。
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/layout',
  factory: (require) => {
    var module = { exports: {} }
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note
    var fact = __runtime_debug.fact
    var placeOf = __graph_model.placeOf
    var setPlace = __graph_model.setPlace
    var __layout_prep = require('dsh-cdd-lens/layout/prep')
    var layoutScope = __layout_prep.layoutScope
    var __layout_metrics = require('dsh-cdd-lens/layout/metrics')
    var boxMetrics = __layout_metrics.boxMetrics
    var __layout_sugiyama = require('dsh-cdd-lens/layout/sugiyama')
    var sugiyama = __layout_sugiyama.sugiyama
    var __layout_space = require('dsh-cdd-lens/layout/space')
    var reclaimStrays = __layout_space.reclaimStrays
    var separateOverlaps = __layout_space.separateOverlaps
    var fitExtent = __layout_space.fitExtent
    var shiftDrawing = __layout_space.shiftDrawing
    var __layout_gather = require('dsh-cdd-lens/layout/gather')
    var applyGather = __layout_gather.applyGather
    var freeGatherDragged = __layout_gather.freeGatherDragged
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __routing_select = require('dsh-cdd-lens/routing/select')
    var chooseEdges = __routing_select.chooseEdges
    var __routing_emit = require('dsh-cdd-lens/routing/emit')
    var emitWires = __routing_emit.emitWires
    var PORT_OFFSET = 0.5

    function portsFor(p) {
      return {
        in: { x: p.x - PORT_OFFSET, y: p.y + p.h / 2 },
        out: { x: p.x + p.w + PORT_OFFSET, y: p.y + p.h / 2 },
      }
    }

    function syncPorts(place) {
      place.placed.forEach(function (p) { p.ports = portsFor(p) })
    }

    function bindPolylineEndpoints(line, byId) {
        var a = byId[line.from]
        var b = byId[line.to]
        if (a === undefined || b === undefined) return line
        var middle = (line.pts || []).slice(1, -1).map(function (pt) { return { x: pt.x, y: pt.y } })
        var pts = [a.ports.out].concat(middle).concat([b.ports.in])
        return Object.assign({}, line, {
          pts: pts,
          sourcePort: { side: 'right', point: a.ports.out },
          targetPort: { side: 'left', point: b.ports.in },
        })
    }

    function bindPolylineSet(polylines, byId) {
      return polylines.map(function (line) { return bindPolylineEndpoints(line, byId) })
    }

    function allowedTypes(types, relationFilter) {
      if (relationFilter === undefined || relationFilter === null) return types
      return types.filter(function (type) { return relationFilter[type] !== false })
    }

    function finalPolylines(lines, picked, byId, relationFilter) {
      return bindPolylineSet(lines.filter(function (line) {
        var types = allowedTypes(line.types || [line.type || 'call'], relationFilter)
        return types.length > 0
          && picked[line.from + '\u0000' + line.to] === true
      }).map(function (line) {
        var types = allowedTypes(line.types || [line.type || 'call'], relationFilter)
        return Object.assign({}, line, {
          id: line.from + '\u2192' + line.to + ':' + types.join(','),
          type: types[0],
          types: types,
        })
      }), byId)
    }

    /**
     * Turn one graph into one drawing.
     *
     * @param graph - nodes and edges to draw。
     * @param relationFilter - relation kinds the viewer left switched on。
     * @param avail - the canvas viewport width in CSS pixels。
     * @returns nodes, wires, labels, junctions, arrows, file boxes and size。
     */
    function layout(graph, relationFilter, avail) {
      if (graph.rootId === null) {
        note('layout', 'rootId=null，没有起点可用（nodes=' + Object.keys(graph.nodes).length + '）')
        return { nodes: [], wires: [], labels: [], junctions: [], arrows: [], rows: [], files: [], width: 0, height: 0 }
      }
      var scope = layoutScope(graph)
      var metrics = boxMetrics(graph, scope, avail)

      // ---- 会话自己的边要画出来，不管有没有人按过按钮 ----
      //
      // 这是删掉 /among 之后必须补上的一件事：那条路由以前给 bridge 边打
      // `always`。没有它，一个刚 ingest 出来的图里每条边两端都没被按过，
      // select.js 就把它们全部滤掉——画面上就是「一堆卡片，一根线都没有」。
      //
      // 判据不是「谁打的标记」，而是这个节点本身有没有被这次会话碰过：
      // 两个 anchor 都是会话自己的，它们之间的关系就是这次会话要看的答案。
      graph.edges.forEach(function (e) {
        if (e.always === true) return
        var fromUI = uiOf(graph, e.from)
        var toUI = uiOf(graph, e.to)
        var fromSession = fromUI !== null && (fromUI.session === true || fromUI.explored === true)
        var toSession = toUI !== null && (toUI.session === true || toUI.explored === true)
        if (fromSession && toSession) e.always = true
      })

      // ---- 分层布局：消环 → 分层 → 排序 → 坐标，一次全出 ----
      var laid = sugiyama(graph, scope.included, metrics, function (id) {
        var known = placeOf(graph, id)
        // 只认已经真正画过的那一次位置。node 上没有位置 = 它还没上过屏幕。
        if (known === null || typeof known.x !== 'number' || typeof known.y !== 'number') return null
        return known
      })
      var place = {
        placed: laid.placed,
        rows: [],
        canvasY: laid.canvasY,
      }

      // 手工拖过的坐标原样生效；跑偏的拉回来，再推开重叠。
      // 注意顺序：先应用保存的位置，再分离重叠——反过来的话保存的位置会被覆盖。
      applySavedPositions(graph, place, shared.nodePositions || {})
      freeGatherDragged(place)
      reclaimStrays(place, metrics, avail)

      var orient = { byId: {} }
      place.placed.forEach(function (p) { orient.byId[p.id] = p })

      // 选中节点的上下游坐到它旁边，收拢之后才推重叠——反过来的话
      // 收拢列里刚排好的卡片会被分离过程推走。
      applyGather(graph, place, metrics)
      separateOverlaps(place, metrics)
      syncPorts(place)

      // ---- 布线：哪条边值得画 ----
      var edges = chooseEdges(graph, scope, orient, relationFilter)
      var picked = {}
      edges.chosen.forEach(function (e) { picked[e.from + '\u0000' + e.to] = true })

      // ---- 出线：sugiyama 的折线按 id 挂上关系类型，再交给 emit ----
      var polylines = finalPolylines(laid.polylines, picked, orient.byId, relationFilter)
      var kept = {}
      polylines.forEach(function (p) { kept[p.from] = true; kept[p.to] = true })
      // 被 select 滤掉的边不画，但线两端的节点仍然要留着。
      var hops = { hSegs: new Map(), segments: [] }
      var drawn = emitWires({ polylines: polylines, hSegs: hops.hSegs, WIRE_CORNER: metrics.WIRE_CORNER, ARROW_EVERY: metrics.ARROW_EVERY }, hops)

      // ---- 尺寸：从画出来的东西反推 ----
      // 手工坐标可能把某个节点放到负坐标（画布原点左边/上边）。那时整张图
      // 往右下挪一屏边距，挪完再重新出线——布线不变，只是原点移了位置。
      var fit = fitExtent(place, drawn, metrics)
      if (fit.dx > 0 || fit.dy > 0) {
        shiftDrawing(place, { polylines: polylines }, fit.dx, fit.dy)
        syncPorts(place)
        orient.byId = {}
        place.placed.forEach(function (p) { orient.byId[p.id] = p })
        polylines = bindPolylineSet(polylines, orient.byId)
        drawn = emitWires({ polylines: polylines, hSegs: hops.hSegs, WIRE_CORNER: metrics.WIRE_CORNER, ARROW_EVERY: metrics.ARROW_EVERY }, hops)
        fit = fitExtent(place, drawn, metrics)
      }
      // 只记录第一次上屏的位置。之后普通布局、选中、高亮、过滤、画布尺寸变化
      // 都不许改它；只有用户拖动走 shared.nodePositions 才能覆盖。
      place.placed.forEach(function (p) {
        if (placeOf(graph, p.id) !== null) return
        setPlace(graph, p.id, {
          x: p.x, y: p.y, w: p.w, h: p.h, layer: p.layer,
          ports: p.ports,
        })
      })

      var maxX = fit.maxX, maxY = fit.maxY

      fact('layout', place.placed.length + 'n/' + drawn.wires.length + 'w/' + (laid.layers || 0) + 'L')
      note('layout', 'in=' + Object.keys(graph.nodes).length + ' edges=' + graph.edges.length
        + ' -> placed=' + place.placed.length + ' wires=' + drawn.wires.length + ' layers=' + laid.layers)
      return {
        nodes: place.placed, wires: drawn.wires, labels: drawn.labels,
        junctions: drawn.junctions, arrows: drawn.arrows, unrouted: drawn.unrouted,
        rows: [], files: [],
        layers: laid.layers,
        crossings: laid.crossings,
        stats: {
          nodes: place.placed.length,
          wires: drawn.wires.length,
          relations: edges.stats.relations,
          wireTotal: edges.stats.total,
        },
        width: Math.max(avail || 0, maxX + metrics.PAD),
        height: Math.max(360, maxY + metrics.PAD),
      }
    }

    /**
     * 手工拖过的坐标原样写上。
     *
     * 分层布局先给出建议位置，用户拖过的那一个覆盖它——不然每次重画都会把用户
     * 摆好的东西弹回去。
     */
    function applySavedPositions(graph, place, positions) {
      if (positions === null || positions === undefined) return
      place.placed.forEach(function (p) {
        var at = positions[p.id]
        if (at === undefined || typeof at.x !== 'number' || typeof at.y !== 'number') return
        p.x = at.x
        p.y = at.y
        p.manual = true
        p.ports = {
          in: { x: p.x, y: p.y + p.h / 2 },
          out: { x: p.x + p.w, y: p.y + p.h / 2 },
        }
      })
    }

    module.exports = { layout }
    return module.exports
  },
})

// dsh-cdd-lens — Persistent trajectory sidebar beside Chat.
//
// The graph explains code relationships. This rail explains the session in
// time, and deliberately owns its own rendering state: compaction may fade a
// graph node, but it must never erase or pale a historical trajectory entry.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/stream',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useEffect = React.useEffect
    var useMemo = React.useMemo
    var useRef = React.useRef
    var useState = React.useState
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var useShared = __state_store.useShared
    var __view_panels = require('dsh-cdd-lens/view/panels')
    var Source = __view_panels.Source
    var History = __view_panels.History
    var __engine_engine = require('dsh-cdd-lens/engine/engine')
    var makeEngine = __engine_engine.makeEngine
    var __shell_chatSeat = require('dsh-cdd-lens/shell/chatSeat')
    var openDockBesideChat = __shell_chatSeat.openDockBesideChat

    var WIDTH_KEY = 'cdd-lens.trajectory-width.v1'
    var EXPANDED_KEY = 'cdd-lens.trajectory-expanded.v1'
    var COLLAPSED_KEY = 'cdd-lens.trajectory-collapsed.v1'

    function stronger(left, right) {
      if (right.working === true) return right
      if (left.working === true) return left
      if (right.verb === 'edit' || right.verb === 'write') return right
      return left
    }

    /** One persistent row per anchor/file per tool step, earliest first. */
    function stepsOf() {
      var trace = shared.trace || {}
      var rows = {}
      Object.keys(trace).forEach(function (id) {
        ;(trace[id].events || []).forEach(function (event) {
          var step = event.step || 1
          var key = event.turn + ':' + step + ':' + id
          var row = {
            key: key, id: id, turn: event.turn, step: step,
            verb: event.verb, tool: event.tool, working: event.working === true,
            agent: event.agent, reason: event.reason,
          }
          rows[key] = rows[key] === undefined ? row : stronger(rows[key], row)
        })
      })
      ;(shared.unresolved || []).forEach(function (entry) {
        ;(entry.steps || []).forEach(function (at) {
          var key = at.turn + ':' + at.step + ':file:' + entry.file
          rows[key] = {
            key: key, id: null, file: entry.file, reason: entry.reason,
            turn: at.turn, step: at.step, verb: at.verb || entry.verb,
            working: false,
          }
        })
      })
      return Object.keys(rows).map(function (key) { return rows[key] }).sort(function (l, r) {
        return l.turn - r.turn || l.step - r.step
          || String(l.id || l.file).localeCompare(String(r.id || r.file))
      })
    }

    /** Turn -> step -> rows, preserving chronological order. */
    function groupRows(rows) {
      var turns = []
      var byTurn = {}
      rows.forEach(function (row) {
        var turn = byTurn[row.turn]
        if (turn === undefined) {
          turn = { turn: row.turn, steps: [], byStep: {} }
          byTurn[row.turn] = turn
          turns.push(turn)
        }
        var step = turn.byStep[row.step]
        if (step === undefined) {
          step = { step: row.step, rows: [] }
          turn.byStep[row.step] = step
          turn.steps.push(step)
        }
        step.rows.push(row)
      })
      turns.forEach(function (turn) { delete turn.byStep })
      return turns
    }

    function verbOf(row) {
      if (row.working === true) return '正在处理'
      if (row.verb === 'edit' || row.verb === 'write') return '已修改'
      if (row.verb === 'search') return '已搜索'
      return '已查看'
    }

    function stateClass(row) {
      if (row.working === true) return ' cddl-trace-working'
      if (row.verb === 'edit' || row.verb === 'write') return ' cddl-trace-edited'
      return ' cddl-trace-viewed'
    }

    function loadWidth() {
      try {
        var value = Number(window.localStorage.getItem(WIDTH_KEY))
        if (isFinite(value) && value >= 280 && value <= 520) return value
      } catch (e) { /* browser persistence is optional */ }
      return 360
    }

    function loadExpanded() {
      try {
        var value = JSON.parse(window.localStorage.getItem(EXPANDED_KEY) || '[]')
        if (Array.isArray(value)) {
          var out = {}
          value.forEach(function (key) { if (typeof key === 'string') out[key] = true })
          return out
        }
      } catch (e) { /* malformed old preference: begin folded */ }
      return {}
    }

    function loadCollapsed() {
      try {
        var stored = window.localStorage.getItem(COLLAPSED_KEY)
        if (stored === '1') return true
        if (stored === '0') return false
      } catch (e) { /* browser persistence is optional */ }
      return window.matchMedia && window.matchMedia('(max-width:720px)').matches
    }

    function saveExpanded(value) {
      try {
        window.localStorage.setItem(EXPANDED_KEY, JSON.stringify(Object.keys(value).filter(function (key) { return value[key] })))
      } catch (e) { /* browser persistence is optional */ }
    }

    function chatScroller() {
      var list = document.querySelector('[data-chat-flow]')
      if (list === null) return null
      return list.closest('[data-conversation-scroll]') || list.parentElement
    }

    /** Chat's current reading Turn, using the same 20%/96px line as ChatView. */
    function turnAtReadingLine(scroller) {
      if (scroller === null) return null
      var rows = scroller.querySelectorAll('[data-chat-turn]:not([hidden])')
      if (rows.length === 0) return null
      if (scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight <= 25) {
        return Number(rows[rows.length - 1].dataset.chatTurn)
      }
      var box = scroller.getBoundingClientRect()
      var line = box.top + Math.min(96, scroller.clientHeight * .2)
      var found = null
      if (typeof document.elementsFromPoint === 'function' && box.width > 0) {
        var hits = document.elementsFromPoint(box.left + box.width / 2, line)
        for (var i = 0; i < hits.length; i++) {
          var owner = hits[i].closest ? hits[i].closest('[data-chat-turn]') : null
          if (owner !== null && scroller.contains(owner)) {
            var exact = Number(owner.dataset.chatTurn)
            if (Number.isSafeInteger(exact)) return exact
          }
        }
      }
      for (var j = 0; j < rows.length; j++) {
        if (rows[j].getBoundingClientRect().top > line) break
        var turn = Number(rows[j].dataset.chatTurn)
        if (Number.isSafeInteger(turn)) found = turn
      }
      return found === null ? Number(rows[0].dataset.chatTurn) : found
    }

    function directScrollToTurn(turn) {
      var rows = document.querySelectorAll('[data-chat-turn]:not([hidden])')
      for (var i = 0; i < rows.length; i++) {
        if (Number(rows[i].dataset.chatTurn) !== Number(turn)) continue
        var scroller = rows[i].closest('[data-conversation-scroll]') || chatScroller()
        if (scroller === null) return false
        var outer = scroller.getBoundingClientRect()
        var target = rows[i].getBoundingClientRect()
        scroller.scrollTop += target.top - outer.top - Math.min(96, scroller.clientHeight * .2)
        return true
      }
      return false
    }

    /** Reuse Chat's native pager, then verify and enforce the visual landing. */
    function jumpToChatTurn(turn) {
      var labels = [
        '跳转到第 ' + turn + ' 轮', '加载并跳转到第 ' + turn + ' 轮',
        'Jump to turn ' + turn, 'Load and jump to turn ' + turn,
      ]
      var buttons = document.querySelectorAll('button[aria-label]')
      for (var i = 0; i < buttons.length; i++) {
        if (labels.indexOf(buttons[i].getAttribute('aria-label')) >= 0) {
          buttons[i].click()
          // Native navigation owns paging. Once its target row is present,
          // this visual landing guard makes the contract observable even when
          // another scroll owner (composer follow, media panel) moved afterward.
          var tries = 0
          var timer = window.setInterval(function () {
            tries += 1
            if (directScrollToTurn(turn) || tries >= 20) window.clearInterval(timer)
          }, 100)
          return true
        }
      }
      return directScrollToTurn(turn)
    }

    /** Follow Chat without coupling the two scroll positions. */
    function useChatTurn(initial) {
      var state = useState(initial || null)
      var setTurn = state[1]
      useEffect(function () {
        var bound = null
        var frame = null
        var sync = function () {
          frame = null
          var next = turnAtReadingLine(bound)
          if (Number.isSafeInteger(next)) setTurn(function (current) { return current === next ? current : next })
        }
        var schedule = function () {
          if (frame !== null) return
          frame = window.requestAnimationFrame(sync)
        }
        var bind = function () {
          var next = chatScroller()
          if (next === bound) return
          if (bound !== null) bound.removeEventListener('scroll', schedule)
          bound = next
          if (bound !== null) {
            bound.addEventListener('scroll', schedule, { passive: true })
            schedule()
          }
        }
        bind()
        var observer = new MutationObserver(bind)
        observer.observe(document.body, { childList: true, subtree: true })
        window.addEventListener('resize', schedule)
        return function () {
          observer.disconnect()
          if (bound !== null) bound.removeEventListener('scroll', schedule)
          if (frame !== null) window.cancelAnimationFrame(frame)
          window.removeEventListener('resize', schedule)
        }
      }, [])
      return state[0]
    }

    function insertPath(path) {
      var box = document.querySelector('[contenteditable="true"]')
      if (box === null) return false
      box.focus()
      try { return document.execCommand('insertText', false, path + ' ') } catch (e) { return false }
    }

    function sourceLineCount(source) {
      if (source === null || source === undefined) return 0
      if (Number.isFinite(source.lineCount)) return source.lineCount
      return Math.max(0, Number(source.end) - Number(source.start) + 1)
    }

    function SourceSnippet(props) {
      var source = (shared.sourceCache || {})[props.id]
      if (source === undefined) return h('div', { className: 'cddl-trace-loading' }, '读取源码…')
      if (source === null || source.lines === undefined) {
        return h('div', {
          className: 'cddl-trace-source cddl-trace-missing',
          'data-cdd-source-id': props.id,
        }, '源码范围读不出来')
      }
      var count = sourceLineCount(source)
      return h('div', { className: 'cddl-trace-source' }, [
        h('div', { key: 'path', className: 'cddl-trace-path', title: source.file },
          source.file + ':' + source.start + '–' + source.end + ' · ' + count + ' 行'),
        h('pre', {
          key: 'code',
          'data-cdd-source-id': source.id || props.id,
          'data-cdd-source-start': source.start,
          'data-cdd-source-end': source.end,
          'data-cdd-source-lines': count,
        }, source.lines.map(function (text, i) {
          return h('div', { key: source.from + i }, [
            h('span', { key: 'n' }, source.from + i),
            h('code', { key: 'c' }, text === '' ? ' ' : text),
          ])
        })),
      ])
    }

    function locateInGraph(ctx, engine, id) {
      // 先把图面板开出来，再定位：面板没开的话，定位完了也没人看得见。
      openDockBesideChat(ctx)
      if (shared.graph.nodes[id] !== undefined) return engine.reveal(id)
      return engine.anchor(id).then(function (anchor) {
        if (anchor === null || anchor === undefined) return false
        return engine.focus(anchor).then(function () { return engine.reveal(id) }).then(function () { return true })
      })
    }

    function AnchorRow(props) {
      var row = props.row
      var node = row.id === null ? undefined : shared.graph.nodes[row.id]
      var anchor = node === undefined ? null : node
      var label = anchor === null ? (row.id === null ? row.file : row.id.split('::').pop()) : anchor.symbol
      return h('article', {
        className: 'cddl-trace-anchor' + stateClass(row) + (props.expanded ? ' is-open' : ''),
        'data-cdd-anchor-id': row.id || '',
      }, [
        h('button', {
          key: 'main', className: 'cddl-trace-anchor-main',
          title: props.expanded ? '折叠 Anchor' : '展开 Anchor',
          onClick: function () { props.onToggle(row) },
        }, [
          h('span', { key: 'chev', className: 'cddl-trace-chevron' }, props.expanded ? '▾' : '▸'),
          h('span', { key: 'dot', className: 'cddl-trace-dot' }),
          h('span', { key: 'label', className: 'cddl-trace-label', title: row.id || row.file }, label),
          h('span', { key: 'state', className: 'cddl-trace-state' }, verbOf(row)),
        ]),
        props.expanded ? h('div', { key: 'detail', className: 'cddl-trace-detail' }, [
          row.id === null
            ? h('div', { key: 'file', className: 'cddl-trace-unresolved' }, [
              h('span', { key: 'why' }, row.reason || '未匹配到 Anchor'),
              h('button', { key: 'insert', onClick: function () { insertPath(row.file) } }, '插入路径'),
            ])
            : h(SourceSnippet, { key: 'source', id: row.id }),
          row.id !== null ? h('button', {
            key: 'locate', className: 'cddl-trace-locate',
            'data-locate-anchor-id': row.id,
            onClick: function () { locateInGraph(props.ctx, props.engine, row.id) },
          }, '在逻辑图中定位') : null,
        ]) : null,
      ])
    }

    /** Fixed right column; history is never filtered by compaction/fade. */
    function TrajectorySidebar(props) {
      useShared()
      var engine = useMemo(function () { return makeEngine(props.ctx) }, [])
      var rows = stepsOf()
      var turns = groupRows(rows)
      var currentTurn = useChatTurn(shared.turn)
      var visibleTurns = turns.slice()
      if (Number.isSafeInteger(currentTurn) && !visibleTurns.some(function (turn) { return turn.turn === currentTurn })) {
        visibleTurns.push({ turn: currentTurn, steps: [], empty: true })
        visibleTurns.sort(function (left, right) { return left.turn - right.turn })
      }
      var expandedState = useState(loadExpanded)
      var expanded = expandedState[0]
      var setExpanded = expandedState[1]
      var widthState = useState(loadWidth)
      var width = widthState[0]
      var setWidth = widthState[1]
      var collapsedState = useState(loadCollapsed)
      var collapsed = collapsedState[0]
      var setCollapsed = collapsedState[1]
      var bodyRef = useRef(null)
      var pointerInside = useRef(false)
      var drag = useRef(null)

      // Expanded rows survive reloads. Their in-memory source cache does not,
      // so restore the data as well as the chevron instead of leaving a
      // permanent empty "读取源码…" panel after refresh.
      useEffect(function () {
        rows.forEach(function (row) {
          if (row.id !== null && expanded[row.key] === true && (shared.sourceCache || {})[row.id] === undefined) {
            engine.source(row.id)
          }
        })
      }, [rows.length, Object.keys(expanded).join('|')])

      useEffect(function () {
        document.documentElement.style.setProperty('--cddl-trajectory-width', width + 'px')
        try { window.localStorage.setItem(WIDTH_KEY, String(width)) } catch (e) { /* optional */ }
        return function () { document.documentElement.style.removeProperty('--cddl-trajectory-width') }
      }, [width])

      // The trajectory is the third content column, not a viewport overlay.
      // Follow Chat's real scroll-area top so DSH's complete session header
      // remains visible even if the host changes its header height.
      useEffect(function () {
        var frame = null
        var syncTop = function () {
          frame = null
          var scroller = chatScroller()
          var tabs = document.querySelector('[role="tablist"]')
          var header = tabs === null ? null : tabs.closest('header')
          // Falling back to 0 put this column over the session header and the
          // tab bar — the one thing it must never cover, because that is how
          // you leave it. The tab strip's own bottom is the floor.
          // Tied to Chat's own scroll area, top and bottom. Anchored to the
          // window instead, it rode over the session header and the tab strip —
          // the one thing it must never cover, since that is how you leave it.
          var tabsBottom = tabs === null ? 0 : Math.round(tabs.getBoundingClientRect().bottom)
          // Only the top is derived, and only far enough to clear the header and
          // the tab strip — the one thing this column must never cover, since
          // that is how you leave it. The bottom is left alone: tying it to
          // Chat's box meant a hidden element's zero rect collapsed the whole
          // column, and the space reserved for it stayed behind as a blank band.
          var boundary = scroller !== null ? scroller.getBoundingClientRect().top
            : header !== null ? header.getBoundingClientRect().bottom : tabsBottom
          var top = Math.max(tabsBottom, Math.round(boundary))
          document.documentElement.style.setProperty('--cddl-trajectory-top', top + 'px')
        }
        var schedule = function () {
          if (frame !== null) return
          frame = window.requestAnimationFrame(syncTop)
        }
        syncTop()
        var observer = new MutationObserver(schedule)
        observer.observe(document.body, { childList: true, subtree: true })
        window.addEventListener('resize', schedule)
        return function () {
          observer.disconnect()
          if (frame !== null) window.cancelAnimationFrame(frame)
          window.removeEventListener('resize', schedule)
          document.documentElement.style.removeProperty('--cddl-trajectory-top')
        }
      }, [])

      var toggleCollapsed = function () {
        var next = !collapsed
        try { window.localStorage.setItem(COLLAPSED_KEY, next ? '1' : '0') } catch (e) { /* optional */ }
        setCollapsed(next)
      }

      useEffect(function () {
        var body = bodyRef.current
        if (body === null || pointerInside.current || !Number.isSafeInteger(currentTurn)) return
        var groups = body.querySelectorAll('[data-cdd-turn]')
        for (var i = 0; i < groups.length; i++) {
          if (Number(groups[i].dataset.cddTurn) !== currentTurn) continue
          var outer = body.getBoundingClientRect()
          var target = groups[i].getBoundingClientRect()
          if (target.top >= outer.top && target.bottom <= outer.bottom) return
          body.scrollTop += target.top - outer.top
          return
        }
      }, [currentTurn, rows.length])

      var toggle = function (row) {
        var next = Object.assign({}, expanded)
        if (next[row.key]) delete next[row.key]
        else {
          next[row.key] = true
          if (row.id !== null) engine.source(row.id)
        }
        saveExpanded(next)
        setExpanded(next)
      }

      var resize = function (event) {
        if (event.button !== undefined && event.button !== 0) return
        event.preventDefault()
        drag.current = { x: event.clientX, width: width }
        var move = function (e) {
          var next = drag.current.width + (drag.current.x - e.clientX)
          setWidth(Math.max(280, Math.min(520, next)))
        }
        var up = function () {
          drag.current = null
          window.removeEventListener('pointermove', move)
          window.removeEventListener('pointerup', up)
        }
        window.addEventListener('pointermove', move)
        window.addEventListener('pointerup', up)
      }

      return h('aside', {
        className: 'cddl-trajectory' + (collapsed ? ' is-collapsed' : ''),
        style: { width: width + 'px' },
        'data-cdd-trajectory': 'persistent',
      }, [
        h('div', { key: 'resize', className: 'cddl-trajectory-resize', title: '拖动改变轨迹栏宽度', onPointerDown: resize }),
        // The source lives here, not over the graph. This edge is one place
        // with several tenants; reading a function should cost the graph
        // nothing, and the graph is the thing you came to look at.
        (shared.focused && shared.viewMounted > 0) ? h('div', { key: 'src', className: 'cddl-trajectory-src' }, [
          h(Source, { key: 's', engine: engine }),
          h(History, { key: 'h' }),
        ]) : null,
        h('header', { key: 'head', className: 'cddl-trajectory-head' }, [
          h('div', { key: 'title' }, [
            h('strong', { key: 'strong' }, '轨迹'),
            h('span', { key: 'count' }, turns.length + ' 轮 · ' + rows.length + ' Anchor 记录'),
          ]),
          h('button', {
            key: 'collapse', className: 'cddl-trajectory-toggle',
            'aria-expanded': collapsed ? 'false' : 'true',
            'aria-label': collapsed ? '展开代码轨迹' : '收起代码轨迹',
            title: collapsed ? '展开轨迹侧栏' : '收起轨迹侧栏', onClick: toggleCollapsed,
          }, collapsed ? '代码轨迹' : '收起'),
        ]),
        h('div', {
          key: 'body', ref: bodyRef, className: 'cddl-trajectory-body',
          onPointerEnter: function () { pointerInside.current = true },
          onPointerLeave: function () { pointerInside.current = false },
        }, visibleTurns.length === 0
          ? h('div', { className: 'cddl-trajectory-empty' }, 'Agent 查看或修改代码后，轨迹会永久保留在这里。')
          : visibleTurns.map(function (turn) {
            var active = turn.turn === currentTurn
            return h('section', {
              key: turn.turn, className: 'cddl-trace-turn' + (active ? ' is-current' : ''),
              'data-cdd-turn': turn.turn,
            }, [
              h('button', {
                key: 'turn', className: 'cddl-trace-turn-head',
                'aria-current': active ? 'true' : undefined,
                onClick: function () { jumpToChatTurn(turn.turn) },
              }, [
                h('b', { key: 't' }, 'TURN ' + turn.turn),
                h('span', { key: 'n' }, turn.steps.length + ' 步'),
                h('span', { key: 'jump' }, '跳到对话'),
              ]),
              h('div', { key: 'steps', className: 'cddl-trace-steps' }, turn.steps.map(function (step) {
                return h('div', { key: step.step, className: 'cddl-trace-step' }, [
                  h('div', { key: 'label', className: 'cddl-trace-step-label' }, 'STEP ' + step.step),
                  h('div', { key: 'rows', className: 'cddl-trace-step-rows' }, step.rows.map(function (row) {
                    return h(AnchorRow, {
                      key: row.key, row: row, engine: engine,
                      ctx: props.ctx,
                      expanded: expanded[row.key] === true, onToggle: toggle,
                    })
                  })),
                ])
              }).concat(turn.empty === true
                ? [h('div', { key: 'empty', className: 'cddl-trace-turn-empty' }, '本轮没有代码轨迹')]
                : [])),
            ])
          })),
      ])
    }

    /** Kept for the old "进度" tab; it now renders the same persistent model. */
    function Stream(props) {
      var rows = stepsOf()
      return h('div', { className: 'cddl-rail' }, rows.length === 0
        ? h('div', { className: 'cddl-rail-empty' }, '还没有动作。')
        : h('div', { className: 'cddl-rail-body' }, groupRows(rows).map(function (turn) {
          return h('div', { key: turn.turn, className: 'cddl-rail-at' },
            'TURN ' + turn.turn + ' · ' + turn.steps.length + ' 步')
        })))
    }

    module.exports = {
      WIDTH_KEY, EXPANDED_KEY, stepsOf, groupRows, turnAtReadingLine,
      directScrollToTurn, jumpToChatTurn, locateInGraph, TrajectorySidebar, Stream,
    }
    return module.exports
  },
})

// dsh-cdd-lens — Reaching the Chat tab and opening the dock beside it.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/shell/chatSeat',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var shared = __state_store.shared

    // ---- the floating panel (shell.overlay) --------------------------------

    function activateChatTab() {
      var candidates = document.querySelectorAll('[role="tab"], button')
      for (var i = 0; i < candidates.length; i += 1) {
        if (String(candidates[i].textContent || '').trim() !== '对话') continue
        candidates[i].click()
        return true
      }
      return false
    }

    function openDockBesideChat(ctx) {
      try {
        var layoutService = ctx.get('layout')
        if (layoutService) layoutService.closeDetails()
      } catch (e) { /* optional host service */ }
      shared.dockOpen = true
      shared.wantGraph = (shared.wantGraph || 0) + 1
      publish()
      window.requestAnimationFrame(activateChatTab)
    }

    module.exports = { activateChatTab, openDockBesideChat }
    return module.exports
  },
})

// dsh-cdd-lens — The floating panel in shell.overlay.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/shell/panel',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __runtime_api = require('dsh-cdd-lens/runtime/api')
    var BUILD = __runtime_api.BUILD
    var api = __runtime_api.api
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var useRightInset = __state_store.useRightInset
    var useShared = __state_store.useShared
    var __state_persist = require('dsh-cdd-lens/state/persist')
    var usePlacement = __state_persist.usePlacement
    var __engine_engine = require('dsh-cdd-lens/engine/engine')
    var makeEngine = __engine_engine.makeEngine
    var __session_trace = require('dsh-cdd-lens/session/trace')
    var useConversationTrace = __session_trace.useConversationTrace
    var __view_record = require('dsh-cdd-lens/view/record')
    var degenerate = __view_record.degenerate
    var __view_stream = require('dsh-cdd-lens/view/stream')
    var Stream = __view_stream.Stream
    var __view_tree = require('dsh-cdd-lens/view/tree')
    var Tree = __view_tree.Tree
    var __view_outline = require('dsh-cdd-lens/view/outline')
    var Draw = __view_outline.Draw
    var Outline = __view_outline.Outline
    var __view_panels = require('dsh-cdd-lens/view/panels')
    var History = __view_panels.History
    var Legend = __view_panels.Legend
    var Search = __view_panels.Search
    var Source = __view_panels.Source
    var Unresolved = __view_panels.Unresolved
    var __view_need_ndex = require('dsh-cdd-lens/view/needIndex')
    var NeedIndex = __view_need_ndex.NeedIndex
    var __shell_chat_eat = require('dsh-cdd-lens/shell/chatSeat')
    var openDockBesideChat = __shell_chat_eat.openDockBesideChat

    function LensPanel(props) {
      var ctx = props.ctx
      useShared()
      var engine = useMemo(function () { return makeEngine(ctx) }, [])
      var open = useState(true)
      var tab = useState('graph')
      var health = useState(null)
      var rootRef = useRef(null)
      var rightInset = useRightInset(rootRef)
      var placement = usePlacement()

      // focus() bumps this; following it puts the graph on screen the moment a
      // function is picked in the directory.
      var wanted = shared.wantGraph || 0
      var seenWant = useRef(wanted)
      useEffect(function () {
        if (wanted !== seenWant.current) { seenWant.current = wanted; tab[1]('graph') }
      }, [wanted])
      var wantedFloat = shared.wantFloat || 0
      var seenFloat = useRef(wantedFloat)
      useEffect(function () {
        if (wantedFloat !== seenFloat.current) {
          seenFloat.current = wantedFloat
          open[1](true)
          tab[1]('graph')
        }
      }, [wantedFloat])

      useEffect(function () {
        engine.context()
        api('/health', {}).then(function (body) { health[1]({ ok: true, body: body }) })
          .catch(function (e) { health[1]({ ok: false, error: String(e.message) }) })
      }, [])
      useConversationTrace(ctx, engine)

      if (!open[0]) {
        return h('div', { className: 'cddl-root', ref: rootRef, style: { right: rightInset + 'px' } },
          h('button', { className: 'cddl-pill', onClick: function () { open[1](true) } },
            ['CDD Lens', shared.turn > 0 ? h('span', { key: 't', className: 'cddl-pilln' }, Object.keys(shared.trace).length) : null]))
      }

      var context = shared.context
      var body
      if (context === undefined) body = h('div', { className: 'cddl-empty' }, '连接中…')
      else if (!context.indexed) body = h(NeedIndex, { engine: engine })
      else if (tab[0] === 'outline') body = h(Outline, { engine: engine })
      else if (tab[0] === 'draw') body = h(Draw, { engine: engine })
      // The rail belongs beside the conversation, not inside the spread-out tab:
      // watching the anchors arrive is something you do WHILE the agent runs,
      // and that tab replaces the chat it is meant to accompany.
      else if (tab[0] === 'steps') body = h(Stream, { engine: engine })
      else body = h(Tree, { engine: engine })

      var stamp = health[0]
      var mismatch = stamp !== null && stamp.ok && (stamp.body.build !== BUILD || !stamp.body.clientBundleMatchesBuild)

      return h('div', {
        className: 'cddl-root', ref: rootRef,
        style: {
          right: (rightInset + placement.place.dx) + 'px',
          bottom: (16 + placement.place.dy) + 'px',
        },
      },
        h('div', { className: 'cddl-card', style: { width: placement.place.w + 'px' } }, [
          h('div', {
            className: 'cddl-grip', key: 'g', title: '拖这里改宽度',
            onPointerDown: placement.onResizeDown,
          }),
          h('div', {
            className: 'cddl-head', key: 'h',
            title: '按住标题拖动面板；双击回到右下角',
            onPointerDown: placement.onMoveDown,
            onDoubleClick: placement.reset,
          }, [
            h('span', { className: 'cddl-title', key: 't' }, 'CDD Lens'),
            h('span', { className: 'cddl-meta', key: 'm', title: context ? context.root : '' },
              context && context.stats
                ? (context.stats.anchors + ' anchor · ' + context.stats.files + ' 文件')
                : (stamp === null ? '…' : (stamp.ok ? '' : stamp.error))),
            degenerate(context)
              ? h('span', {
                key: 'q', className: 'cddl-bad',
                title: '这个工程的索引里 ' + context.stats.anchors + ' 个 anchor 只派生出 '
                  + context.stats.edges + ' 条边。多半是扫进了 node_modules / .venv 之类，'
                  + '调用图画不出来。给这个目录加 .codedendrite_ignore 再重建。',
              }, '索引可疑')
              : null,
            mismatch ? h('span', { key: 'w', className: 'cddl-bad', title: '构建戳对不上：' + stamp.body.build + ' vs ' + BUILD }, '版本不符') : null,
            h('span', { className: 'cddl-spacer', key: 's' }),
            h('button', {
              key: 'dock', className: 'cddl-btn', title: '把逻辑图放到 Chat 右侧',
              onPointerDown: function (e) { e.stopPropagation() },
              onClick: function () { openDockBesideChat(ctx) },
            }, '并排 ⤢'),
            h('button', {
              key: 'r', className: 'cddl-btn', title: '重建索引（增量）',
              onPointerDown: function (e) { e.stopPropagation() },
              onClick: function () { engine.reindex() },
            }, shared.reindexing ? '建索引…' : '↻'),
            h('button', {
              key: 'x', className: 'cddl-btn',
              onPointerDown: function (e) { e.stopPropagation() },
              onClick: function () { open[1](false) },
            }, '—'),
          ]),
          h('div', { className: 'cddl-tabs', key: 'tb' }, [
            h('button', {
              key: 'g', className: tab[0] === 'graph' ? 'on' : '',
              onClick: function () { tab[1]('graph') },
            }, '逻辑图'),
            h('button', {
              key: 'o', className: tab[0] === 'outline' ? 'on' : '',
              onClick: function () { tab[1]('outline') },
            }, '目录'),
            h('button', {
              key: 'd', className: tab[0] === 'draw' ? 'on' : '',
              onClick: function () { tab[1]('draw') },
            }, 'cdd draw'),
            h('button', {
              key: 's', className: tab[0] === 'steps' ? 'on' : '',
              title: '按顺序看这次会话碰过什么',
              onClick: function () { tab[1]('steps') },
            }, '进度'),
          ]),
          h(Search, { key: 'q', engine: engine }),
          h('div', { key: 'b', className: 'cddl-body' }, [body, h(Unresolved, { key: 'u' })]),
          h(Legend, { key: 'l' }),
          h(Source, { key: 's', engine: engine }),
          h(History, { key: 'y' }),
        ]))
    }

    module.exports = { LensPanel }
    return module.exports
  },
})

// dsh-cdd-lens — Hooks and derived state for the spread-out view.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/shell/viewState',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var publish = __state_store.publish
    var useOverlapInset = __state_store.useOverlapInset
    var useShared = __state_store.useShared
    var __engine_engine = require('dsh-cdd-lens/engine/engine')
    var makeEngine = __engine_engine.makeEngine
    var __session_trace = require('dsh-cdd-lens/session/trace')
    var useConversationTrace = __session_trace.useConversationTrace
    var __layout_layout = require('dsh-cdd-lens/layout/layout')
    var layout = __layout_layout.layout

    /**
     * Every hook and derived value the spread-out view runs on.
     */
    function useViewState(props) {

      var ctx = props.ctx
      useShared()
      var engine = useMemo(function () { return makeEngine(ctx) }, [])
      var tab = useState('graph')
      var relations = useState({ call: true, dataflow: false, inherit: false, impact: false, dispatch: true })
      var zoom = useState(1)
      var layoutRevision = useState(0)
      var canvasRef = useRef(null)

      useEffect(function () { engine.context() }, [])
      useConversationTrace(ctx, engine)

      var wanted = shared.wantGraph || 0
      var seenWant = useRef(wanted)
      useEffect(function () {
        if (wanted !== seenWant.current) { seenWant.current = wanted; tab[1]('graph') }
      }, [wanted])

      var context = shared.context
      // The spread-out view sits in the centre column, but another plugin's
      // `position: fixed` rail paints over everything at z-index 500 — including
      // the right end of this toolbar, whose buttons then cannot be clicked at
      // all (the pointer lands on the neighbour). Reserving its measured width
      // is the same fix the floating panel already needed; hit-testing does not
      // care that we are inside a column.
      var viewRef = useRef(null)
      // Only what is genuinely lying on top of this view, measured against the
      // view's own box. Reserving the window's right edge here double-counted
      // the frame's details track — the grid had already taken it out — and
      // left a dead white strip the drawing could never reach.
      var reserve = useOverlapInset(viewRef)

      // The source panel belongs to this view, wherever it is drawn. It rides
      // in the trajectory rail, which outlives any one tab, so the rail has to
      // be told when this view is actually on screen — otherwise the source of
      // an anchor keeps sitting there over Chat, owned by nothing.
      useEffect(function () {
        shared.viewMounted = (shared.viewMounted || 0) + 1
        publish()
        return function () {
          shared.viewMounted = Math.max(0, (shared.viewMounted || 1) - 1)
          publish()
        }
      }, [])

      useEffect(function () {
        var escape = function (event) { if (event.key === 'Escape') engine.blurEdge() }
        window.addEventListener('keydown', escape)
        return function () { window.removeEventListener('keydown', escape) }
      }, [])

      // Selection is a highlight/source action only. Node coordinates are
      // stable after first paint unless the user drags them, so selecting a
      // card must not auto-expand or re-seat its neighbours.
      var selectedNow = shared.selected
      useEffect(function () {
        if (selectedNow === null || selectedNow === undefined) engine.releaseGather()
      }, [selectedNow])

      // Re-measured on every resize: the source column, the neighbour rail and
      // dsh's own sidebar all change this number while the page is open.
      var availWidth = useState(0)
      useEffect(function () {
        var read = function () {
          var el = canvasRef.current
          if (el === null) return
          var w = el.clientWidth
          availWidth[1](function (before) { return Math.abs(before - w) < 8 ? before : w })
        }
        read()
        var timer = setInterval(read, 400)
        window.addEventListener('resize', read)
        return function () { clearInterval(timer); window.removeEventListener('resize', read) }
      }, [])

      var model = useMemo(function () {
        return layout(shared.graph, relations[0], availWidth[0])
      }, [shared.revision, relations[0], layoutRevision[0], availWidth[0]])

      var setZoom = function (value) {
        zoom[1](Math.max(.35, Math.min(1.8, Math.round(value * 100) / 100)))
      }
      /**
       * 这个节点现在**看得见吗**（它的框整个落在可滚动视野内，留一点余量）。
       *
       * 展开只在这里返回 false 时才动视口：你点开一个就在眼前的节点，
       * 画面不该动；点开一个滚出视野的节点，才需要把它带回来。
       */
      var onScreen = function (el, id, m, scale) {
        if (el === null) return true
        var target = m.nodes.filter(function (p) { return p.id === id })[0]
        if (target === undefined) return false
        var pad = 12
        var left = target.x * scale, top = target.y * scale
        var right = (target.x + target.w) * scale, bottom = (target.y + target.h) * scale
        return left >= el.scrollLeft + pad && top >= el.scrollTop + pad
          && right <= el.scrollLeft + el.clientWidth - pad
          && bottom <= el.scrollTop + el.clientHeight - pad
      }
      var centerOn = function (id, scale) {
        var el = canvasRef.current
        if (el === null) return
        var target = model.nodes.filter(function (p) { return p.id === id })[0]
        var x = target === undefined ? model.width / 2 : target.x + target.w / 2
        var y = target === undefined ? model.height / 2 : target.y + target.h / 2
        el.scrollLeft = Math.max(0, x * scale - el.clientWidth / 2)
        el.scrollTop = Math.max(0, y * scale - el.clientHeight / 2)
      }
      var fit = function (id, minimum) {
        var el = canvasRef.current
        if (el === null || model.width === 0 || model.height === 0) return
        var next = Math.max(minimum || .35, Math.min((el.clientWidth - 40) / model.width, (el.clientHeight - 40) / model.height, 1))
        next = Math.round(next * 100) / 100
        setZoom(next)
        window.requestAnimationFrame(function () {
          window.requestAnimationFrame(function () { centerOn(id, next) })
        })
      }
      var toggleRelation = function (name) {
        relations[1](function (before) {
          var next = Object.assign({}, before)
          next[name] = !next[name]
          return next
        })
      }

      var viewportRequest = shared.viewportRequest || {
        id: shared.selected || shared.graph.rootId,
        mode: 'fit',
        seq: 0,
      }
      // 视口只在**真的有人请求**时才动。
      //
      // 以前这个 effect 的依赖里有 model.width / model.height，于是图一长大
      // （展开一层、画布变高）它就重跑，把视口重新居中到选中节点——节点坐标
      // 一个像素没动，整屏却在跳。用户看到的就是「展开之后乱跳」。
      //
      // 现在按请求序号走：同一个 seq 只消费一次，重画多少次视口都不动。
      var lastSeq = useRef(-1)
      useEffect(function () {
        if (tab[0] !== 'graph' || model.nodes.length === 0) return
        if (viewportRequest.seq === lastSeq.current) return
        lastSeq.current = viewportRequest.seq
        var frame = window.requestAnimationFrame(function () {
          // Never auto-shrink. Fitting the whole canvas means dividing by its
          // HEIGHT, and a graph of any size is tall — the solve landed on 68%
          // every single time, which rendered a 13.5px name at nine pixels.
          // A drawing too small to read is not an overview of anything, so the
          // automatic behaviour is: full size, scrolled to the anchor in
          // question. Shrinking to see everything at once stays available, but
          // as a deliberate press of 适配.
          if (viewportRequest.mode === 'fit') {
            var readable = Math.max(zoom[0], 1)
            if (zoom[0] !== readable) setZoom(readable)
            window.requestAnimationFrame(function () { centerOn(viewportRequest.id, readable) })
          } else if (viewportRequest.mode === 'ensure') {
            // 展开用这个：节点已经在视野里就什么都不做。展开一个新节点时视口
            // 跳一下，看着就是「点了展开树乱跳」——真正跳的是视口不是节点。
            if (!onScreen(canvasRef.current, viewportRequest.id, model, zoom[0])) {
              centerOn(viewportRequest.id, zoom[0])
            }
          } else centerOn(viewportRequest.id, zoom[0])
        })
        return function () { window.cancelAnimationFrame(frame) }
      }, [tab[0], viewportRequest.seq])

      return { ctx: ctx, engine: engine, tab: tab, relations: relations, zoom: zoom, layoutRevision: layoutRevision, canvasRef: canvasRef, context: context, viewRef: viewRef, reserve: reserve, model: model, setZoom: setZoom, centerOn: centerOn, fit: fit, toggleRelation: toggleRelation }
    }

    module.exports = { useViewState }
    return module.exports
  },
})

// dsh-cdd-lens — The canvas half of the spread-out view.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/shell/viewCanvas',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __view_outline = require('dsh-cdd-lens/view/outline')
    var Draw = __view_outline.Draw
    var Outline = __view_outline.Outline
    var __view_need_ndex = require('dsh-cdd-lens/view/needIndex')
    var NeedIndex = __view_need_ndex.NeedIndex
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var DebugBar = __runtime_debug.DebugBar
    var __view_node = require('dsh-cdd-lens/view/node')
    var GraphNode = __view_node.GraphNode

    /**
     * The drawing itself, or whatever stands in for it.
     */
    /**
     * Whether this wire or node is part of what was last lit, and if not,
     * whether anything is lit at all.
     *
     * Dimming the rest is what makes a highlight readable: a brighter line
     * among forty identical ones is not brighter enough to find.
     * @param key - the wire id, or an anchor id.
     * @returns the class to append, possibly empty.
     */
    function litClass(key) {
      var lit = shared.lit
      if (lit === null || lit === undefined) return ''
      if (lit.wires[key] === true || lit.nodes[key] === true) return ' cddl-lit'
      return ' cddl-unlit'
    }

    function renderCanvas(props, view) {
      var context = view.context
      var engine = view.engine
      var model = view.model
      var tab = view.tab
      var zoom = view.zoom

      var canvas
      if (context === undefined) canvas = h('div', { className: 'cddl-empty' }, '连接中…')
      else if (!context.indexed) canvas = h(NeedIndex, { engine: engine })
      else if (tab[0] === 'outline') canvas = h('div', { className: 'cddl-scroll' }, h(Outline, { engine: engine }))
      else if (tab[0] === 'draw') canvas = h(Draw, { engine: engine })
      else if (model.nodes.length === 0) {
        canvas = h('div', { className: 'cddl-empty' },
          '还没有起点。切到「目录」翻一个函数，或者上面搜一个名字。')
      } else {
        canvas = h('div', {
          className: 'cddl-scaler cddl-viewport',
          style: { width: (model.width * zoom[0]) + 'px', height: (model.height * zoom[0]) + 'px' },
        }, h('div', {
          className: 'cddl-canvas'
            // On for one flight window only: the cards fly, the wires re-route
            // at once and meet them there. A settled drawing — gathered or
            // not — must never animate, or a drag rubber-bands behind the
            // pointer.
            + ((shared.gatherAnimUntil || 0) > Date.now() ? ' cddl-gathering' : ''),
          style: {
            width: model.width + 'px', height: model.height + 'px',
            transform: 'scale(' + zoom[0] + ')', transformOrigin: '0 0',
          },
        }, [
          h('svg', {
              key: 'w', className: 'cddl-wires',
              width: model.width, height: model.height,
              viewBox: '0 0 ' + model.width + ' ' + model.height,
            }, [
              h('defs', { key: 'd' }, [
                h('marker', {
                  key: 'a', id: 'cddl-arrow', markerWidth: 11, markerHeight: 11, refX: 8, refY: 3.4, orient: 'auto',
                }, h('path', { d: 'M0,0 L7,3.4 L0,6.8 z' })),
                h('marker', {
                  key: 'f', id: 'cddl-arrow-faded', markerWidth: 11, markerHeight: 11, refX: 8, refY: 3.4, orient: 'auto',
                }, h('path', { d: 'M0,0 L7,3.4 L0,6.8 z' })),
              ]),
            ].concat(model.wires.map(function (wire) {
              return h('path', {
                key: wire.id, d: wire.d,
                'data-edge-id': wire.id,
                className: 'cddl-wire cddl-' + wire.type
                  + (wire.faded ? ' cddl-faded' : '')
                  + litClass(wire.id)
                  + (shared.edgeFocus ? ' cddl-hot' : '')
                  + (shared.focused === null || shared.focused === undefined ? ''
                    : (wire.from === shared.focused || wire.to === shared.focused ? ' cddl-hot' : ' cddl-cold')),
                'data-from-file': wire.fromFile,
                'data-to-file': wire.toFile,
              })
            })).concat(model.wires.map(function (wire) {
              return h('path', {
                key: 'hit:' + wire.id,
                d: wire.d,
                className: 'cddl-wire-hit',
                'data-edge-focus': wire.from + '→' + wire.to + ':' + wire.type,
                onPointerDown: function (event) { event.stopPropagation() },
                onClick: function (event) {
                  event.preventDefault()
                  event.stopPropagation()
                  engine.lightEdge(wire.from, wire.to, wire.type)
                  engine.focusEdge(wire.from, wire.to, wire.type)
                },
              })
            })).concat(model.arrows.map(function (arrow) {
              // Repeated along the run: on a wire with four bends a single
              // arrowhead at the far end says nothing about the middle.
              return h('path', {
                key: 'a' + arrow.id,
                className: 'cddl-arrowhead cddl-' + arrow.type
                  + (arrow.faded ? ' cddl-faded' : '')
                  + litClass(arrow.wireId || arrow.id)
                  + (shared.edgeFocus ? ' cddl-hot' : '')
                  + (shared.focused === null || shared.focused === undefined ? ''
                    : (arrow.from === shared.focused || arrow.to === shared.focused ? ' cddl-hot' : ' cddl-cold')),
                d: 'M-4.5,-3.2 L4.5,0 L-4.5,3.2 Z',
                transform: 'translate(' + arrow.x + ',' + arrow.y + ') rotate(' + arrow.angle + ')',
              })
            })).concat(model.junctions.map(function (dot) {
              // Filled dot = these wires actually meet. A hop = they only cross.
              return h('circle', {
                key: 'j' + dot.id, className: 'cddl-junction',
                cx: dot.x, cy: dot.y, r: 3.4,
              })
            }))),
          h('div', { key: 'f', className: 'cddl-fileboxes' },
            (model.files || []).map(function (box) {
              return h('div', {
                key: box.file,
                // A flow column guide is not a container: it gets the quiet
                // frame, and the box keeps the loud one for what holds files.
                className: 'cddl-filebox' + (box.frame === 'flow' ? ' cddl-flowbox' : ''),
                'data-file': box.file,
                style: {
                  left: box.x + 'px', top: box.y + 'px',
                  width: box.w + 'px', height: box.h + 'px',
                },
              }, [
                h('strong', { key: 'name', title: box.file }, box.file),
                h('span', { key: 'count' }, box.count + ' anchors'),
              ])
            })),
          h('div', { key: 'r', className: 'cddl-rowlabels' },
            model.rows.map(function (row, i) {
              return h('div', {
                key: i, className: 'cddl-rowlabel' + (row.island ? ' cddl-island-label' : ''),
                // A label belongs over its own tree, not pinned to the left
                // edge — with the trees side by side that put every one of them
                // on top of the first.
                style: { top: (row.y - 16) + 'px', left: (row.x === undefined ? 16 : row.x) + 'px' },
              }, row.label)
            })),
          h('div', { key: 'c', className: 'cddl-chips' },
            model.rows.filter(function (row) { return row.island && row.label }).map(function (row, i) {
              return h('div', {
                key: i, className: 'cddl-chip', style: { top: (row.y - 30) + 'px', right: '24px' },
              }, row.ids.length + ' 个本轮节点 · 不在当前根链')
            })),
          h('div', { key: 'n', className: 'cddl-nodes', style: { width: model.width + 'px', height: model.height + 'px' } },
            model.nodes.map(function (p) {
              return h(GraphNode, { key: p.id, p: p, engine: engine, zoom: zoom[0] })
            })),
        ]))
      }

      // 调试栏挂在画布外面、上面：它是个诊断窄栏，不该跟着画布缩放平移。
      // 关掉调试时 DebugBar 返回 null，DOM 里什么也不多。
      return h('div', { className: 'cddl-stage-inner' }, [
        h(DebugBar, { key: 'dbg', build: require('dsh-cdd-lens/runtime/api').BUILD }),
        h('div', { key: 'cv', className: 'cddl-canvasbody' }, canvas),
      ])
    }

    module.exports = { renderCanvas }
    return module.exports
  },
})

// dsh-cdd-lens — The toolbar of the spread-out view.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/shell/viewToolbar',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var emptyGraph = __graph_model.emptyGraph
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var shared = __state_store.shared

    var SKIN_KEY = 'cdd-lens.skin.v1'
    // Restored once, before anything draws, so the first frame is already the
    // drawing this browser last asked for rather than a flash of the other one.
    var __state_persist = require('dsh-cdd-lens/state/persist')
    var clearNodePositions = __state_persist.clearNodePositions
    var __view_panels = require('dsh-cdd-lens/view/panels')
    var Search = __view_panels.Search
    var __shell_chat_eat = require('dsh-cdd-lens/shell/chatSeat')
    var openDockBesideChat = __shell_chat_eat.openDockBesideChat

    /**
     * The control strip above the canvas.
     */
    function renderToolbar(props, view) {
      var context = view.context
      var ctx = view.ctx
      var engine = view.engine
      var fit = view.fit
      var layoutRevision = view.layoutRevision
      var model = view.model
      var relations = view.relations
      var setZoom = view.setZoom
      var tab = view.tab
      var toggleRelation = view.toggleRelation
      var zoom = view.zoom

      // Kept per browser: which drawing someone prefers is a reading habit, not
      // a property of the repository.

      return h('div', { className: 'cddl-toolbar', key: 't' }, [
          h('div', { key: 'seg', className: 'cddl-seg' }, [
            h('button', { key: 'g', className: tab[0] === 'graph' ? 'on' : '', onClick: function () { tab[1]('graph') } }, '逻辑图'),
            h('button', { key: 'o', className: tab[0] === 'outline' ? 'on' : '', onClick: function () { tab[1]('outline') } }, '目录'),
            h('button', { key: 'd', className: tab[0] === 'draw' ? 'on' : '', onClick: function () { tab[1]('draw') } }, 'cdd draw'),
          ]),
          // 树选择器。规则文档 §1.3 定义了四棵树；这里就是选它看哪一棵。
          //   直接树 = 1 度树：seed 之间直接有边，中间不插点
          //   anchor 树：单个 anchor 周围直接相连的邻居，也不插点
          //   2 度树：允许一个中间点把两个 seed 接起来
          //   edit 树：只管 edit 过的那批 anchor
          // 「全部」不套任何树，把图里现有的都画出来。
          tab[0] !== 'graph' ? null
            : h('div', { key: 'tree', className: 'cddl-seg cddl-tree', 'aria-label': '看哪棵树' },
              [['all', '全部'], ['anchor', 'anchor 树'], ['degree1', '1 度树'], ['degree2', '2 度树'], ['edit', 'edit 树']]
                .map(function (pair) {
                  var value = pair[0]
                  return h('button', {
                    key: value,
                    className: (shared.treeMode || 'all') === value ? 'on' : '',
                    'aria-pressed': (shared.treeMode || 'all') === value ? 'true' : 'false',
                    title: value === 'degree1' ? 'seed 之间直接有边的那些，中间不插点'
                      : value === 'degree2' ? '允许一个中间点把两个 seed 接起来'
                      : value === 'edit' ? '只看这次会话 edit 过的 anchor'
                      : value === 'anchor' ? '当前选中 anchor 周围直接相连的邻居'
                      : '图里现有的全部画出来',
                    onClick: function () {
                      shared.treeMode = value
                      publish()
                    },
                  }, pair[1])
                })),
          h(Search, { key: 'q', engine: engine }),
          h('div', { key: 'rel', className: 'cddl-seg cddl-relations', 'aria-label': '关系筛选' },
            ['call', 'dataflow', 'inherit', 'impact', 'dispatch'].map(function (name) {
              return h('button', {
                key: name,
                className: relations[0][name] ? 'on' : '',
                'aria-pressed': relations[0][name] ? 'true' : 'false',
                onClick: function () { toggleRelation(name) },
              }, name)
            })),
          h('span', { key: 'm', className: 'cddl-meta', title: context ? context.root : '' },
            context && context.stats ? (context.stats.anchors + ' anchor · ' + context.stats.edges + ' 边 · ' + context.stats.files + ' 文件') : ''),
          h('span', { key: 's', className: 'cddl-spacer' }),
          h('div', { key: 'layout-mode', className: 'cddl-seg cddl-layout-mode', 'aria-label': '布局状态' }, [
            h('button', {
              key: 'user', className: shared.edgeFocus ? '' : 'on',
              onClick: function () { engine.blurEdge() },
            }, '用户布局'),
            h('button', {
              key: 'focus', className: shared.edgeFocus ? 'on' : '',
              title: shared.edgeFocus
                ? (shared.edgeFocus.type === 'dataflow' ? '完整数据流链路；再次点线或按 Esc 返回' : '依赖前后各 3 跳；再次点线或按 Esc 返回')
                : '点击任意连线进入链路聚焦',
              onClick: function () { if (shared.edgeFocus) engine.blurEdge() },
            }, shared.edgeFocus
              ? (shared.edgeFocus.type === 'dataflow' ? '完整数据链' : '依赖 ±3 跳')
              : '链路聚焦'),
          ]),
          h('div', { key: 'z', className: 'cddl-zoom', 'aria-label': '缩放控制' }, [
            h('button', { key: 'o', className: 'cddl-btn', onClick: function () { setZoom(zoom[0] - .1) } }, '−'),
            h('button', { key: 'n', className: 'cddl-btn', onClick: function () { setZoom(1) } }, Math.round(zoom[0] * 100) + '%'),
            h('button', { key: 'i', className: 'cddl-btn', onClick: function () { setZoom(zoom[0] + .1) } }, '＋'),
          ]),
          h('button', {
            key: 'l', className: 'cddl-btn',
            onClick: function () {
              clearNodePositions()
              shared.edgeFocus = null
              layoutRevision[1](function (n) { return n + 1 })
              publish()
            },
          }, '恢复自动布局'),
          h('button', {
            key: 'a', className: 'cddl-btn', title: '缩小到能看见全图（会看不清字）',
            onClick: function () { fit(shared.selected || shared.graph.rootId, .35) },
          }, '适配'),
          // No "收进浮窗" any more. The floating panel it fed is gone, so the
          // button did nothing a user could see — and a graph that can pop
          // itself out over the page is the mess this view is supposed to
          // replace. Beside Chat is the only place it goes.
          props.docked ? null : h('button', {
            key: 'float', className: 'cddl-btn',
            onClick: function () { openDockBesideChat(ctx) },
          }, '并排 Chat ⤢'),
          h('button', {
            key: 'r', className: 'cddl-btn',
            onClick: function () { engine.reindex() },
          }, shared.reindexing ? '建索引…' : '↻ 重建索引'),
          h('button', {
            key: 'wire-mode', className: 'cddl-btn' + (shared.wireMode === 'all' ? ' on' : ''),
            title: shared.wireStats
              ? (shared.wireMode === 'all'
                ? '正在画全部 ' + shared.wireStats.total + ' 条关系'
                : '只画主干；另有 ' + shared.wireStats.hidden + ' 条关系按节点上的 ↑↓ 展开')
              : '',
            onClick: function () {
              shared.wireMode = shared.wireMode === 'all' ? 'tree' : 'all'
              publish()
            },
          }, shared.wireMode === 'all'
            ? ('全部关系 ' + (shared.wireStats ? shared.wireStats.total : ''))
            : ('主干 ' + (shared.wireStats ? shared.wireStats.drawn + '/' + shared.wireStats.total : ''))),
          h('button', {
            key: 'f', className: 'cddl-btn',
            onClick: function () { shared.graph = emptyGraph(); publish() },
          }, '清空'),
        ])
    }

    module.exports = { renderToolbar }
    return module.exports
  },
})

// dsh-cdd-lens — A render that throws must not take the page with it.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/shell/boundary',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement

    /**
     * Show what went wrong instead of showing nothing.
     *
     * A throw anywhere inside a render unmounts the whole subtree, and what is
     * left is a white rectangle that says nothing at all: not which component,
     * not which line, not even that anything failed. Every white screen this
     * plugin has produced was one exception away from being a one-line message,
     * and each of them cost a round trip to find out which one.
     *
     * Written as a class because that is the only thing React will hand an
     * error to. It is also deliberately dumb: no state beyond the error, no
     * retry, nothing that can itself throw.
     */
    function makeBoundary(React) {
      if (typeof React.Component !== 'function') return null
      function Boundary(props) {
        React.Component.call(this, props)
        this.state = { error: null }
      }
      Boundary.prototype = Object.create(React.Component.prototype)
      Boundary.prototype.constructor = Boundary
      Boundary.getDerivedStateFromError = function (error) { return { error: error } }
      Boundary.prototype.componentDidCatch = function (error, info) {
        // Kept where a person can reach it without a debugger attached.
        try {
          window.__cddLensError = {
            message: String(error && error.message),
            stack: String(error && error.stack),
            component: String((info && info.componentStack) || ''),
            at: new Date().toISOString(),
          }
        } catch (e) { /* nothing useful to do here */ }
        try { console.error('[cdd-lens] render failed', error, info) } catch (e) { /* ignore */ }
      }
      Boundary.prototype.render = function () {
        if (this.state.error === null) return this.props.children
        var error = this.state.error
        return h('div', { className: 'cddl-boundary' }, [
          h('strong', { key: 't' }, 'CDD Lens 这一块渲染失败了'),
          h('div', { key: 'm', className: 'cddl-boundary-msg' },
            String(error && error.message ? error.message : error)),
          h('pre', { key: 's', className: 'cddl-boundary-stack' },
            String((error && error.stack) || '').split('\n').slice(0, 6).join('\n')),
          h('div', { key: 'h', className: 'cddl-boundary-hint' },
            '完整信息也放在 window.__cddLensError 里。图没画出来，其余部分不受影响。'),
        ])
      }
      return Boundary
    }

    module.exports = { makeBoundary }
    return module.exports
  },
})

// dsh-cdd-lens — The spread-out graph in conversation.view.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/shell/graphView',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __view_panels = require('dsh-cdd-lens/view/panels')
    var History = __view_panels.History
    var Legend = __view_panels.Legend
    var Source = __view_panels.Source
    var __view_hscroll = require('dsh-cdd-lens/view/hscroll')
    var HScroll = __view_hscroll.HScroll
    var __shell_view_tate = require('dsh-cdd-lens/shell/viewState')
    var useViewState = __shell_view_tate.useViewState
    var __shell_view_anvas = require('dsh-cdd-lens/shell/viewCanvas')
    var renderCanvas = __shell_view_anvas.renderCanvas
    var __shell_view_oolbar = require('dsh-cdd-lens/shell/viewToolbar')
    var renderToolbar = __shell_view_oolbar.renderToolbar

    /**
     * The spread-out graph in conversation.view.
     *
     * State, toolbar and canvas each live in their own file; this is the
     * frame that seats them.
     * @param props - ctx, and whether the view is docked beside Chat.
     * @returns the view element.
     */
    function LensView(props) {
      var view = useViewState(props)
      var engine = view.engine
      var model = view.model
      var zoom = view.zoom
      var setZoom = view.setZoom
      var canvasRef = view.canvasRef
      var viewRef = view.viewRef
      var reserve = view.reserve
      var canvas = renderCanvas(props, view)

      return h('div', {
        className: 'cddl-view' + (props.docked ? ' cddl-view-docked' : ''),
        ref: viewRef,
        style: { paddingRight: reserve + 'px' },
        'data-conversation-composer-overlay': '',
      }, [
        renderToolbar(props, view),
        h('div', { key: 'st', className: 'cddl-stage' + (shared.focused ? ' cddl-stage-detail' : '') }, [
          h('div', {
            key: 'c', className: 'cddl-canvaswrap', ref: canvasRef,
            onWheel: function (e) {
              // Plain wheel scrolls; only a modifier zooms. Shift gives the
              // horizontal axis, which is what a trackpad-less mouse has no
              // other way to reach.
              if (e.shiftKey && !e.ctrlKey && !e.metaKey) {
                var el = canvasRef.current
                if (el !== null) { el.scrollLeft += e.deltaY; e.preventDefault() }
                return
              }
              if (!e.ctrlKey && !e.metaKey) return
              e.preventDefault()
              setZoom(zoom[0] + (e.deltaY < 0 ? .08 : -.08))
            },
            onPointerDown: function (e) {
              // Drag the empty canvas to pan. Finding a scrollbar to reach the
              // far side of a wide drawing is the slow way round.
              if (e.button !== 0) return
              var el = canvasRef.current
              if (el === null) return
              var onNode = e.target.closest !== undefined
                && e.target.closest('.cddl-gnode, .cddl-node-actions, .cddl-filebox') !== null
              if (onNode) return
              var startX = e.clientX
              var startY = e.clientY
              var fromLeft = el.scrollLeft
              var fromTop = el.scrollTop
              var moved = false
              var move = function (ev) {
                if (Math.abs(ev.clientX - startX) + Math.abs(ev.clientY - startY) > 4) moved = true
                el.scrollLeft = fromLeft - (ev.clientX - startX)
                el.scrollTop = fromTop - (ev.clientY - startY)
              }
              var up = function () {
                window.removeEventListener('pointermove', move)
                window.removeEventListener('pointerup', up)
                el.style.cursor = ''
                // A click on empty canvas lets everything go: the edge focus,
                // and the neighbours a selection had gathered.
                if (!moved) { engine.blurEdge(); engine.releaseGather() }
              }
              el.style.cursor = 'grabbing'
              window.addEventListener('pointermove', move)
              window.addEventListener('pointerup', up)
            },
          }, canvas),
          h(HScroll, { key: 'hs', canvasRef: canvasRef, width: model.width, zoom: zoom[0] }),
          // The source moved to the trajectory rail — see view/stream.js.
        ]),
        h(Legend, { key: 'l' }),
      ])
    }

    module.exports = { LensView }
    return module.exports
  },
})

// dsh-cdd-lens — The dock beside Chat and the overlay that seats both views.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/shell/dock',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var shared = __state_store.shared
    var useShared = __state_store.useShared
    var __engine_engine = require('dsh-cdd-lens/engine/engine')
    var makeEngine = __engine_engine.makeEngine
    var __session_trace = require('dsh-cdd-lens/session/trace')
    var useConversationTrace = __session_trace.useConversationTrace
    var __shell_graph_iew = require('dsh-cdd-lens/shell/graphView')
    var LensView = __shell_graph_iew.LensView
    var __view_stream = require('dsh-cdd-lens/view/stream')
    var TrajectorySidebar = __view_stream.TrajectorySidebar

    var DOCK_WIDTH_KEY = 'cdd-lens.dock-width'

    /** Always-on data owner with no visible panel. */
    function LensRuntime(props) {
      var engine = useMemo(function () { return makeEngine(props.ctx) }, [])
      useEffect(function () { engine.context() }, [])
      useConversationTrace(props.ctx, engine)
      return null
    }

    function loadDockWidth() {
      try {
        var value = Number(window.localStorage.getItem(DOCK_WIDTH_KEY))
        if (isFinite(value) && value >= 420) return value
      } catch (e) { /* ignore */ }
      return Math.max(520, Math.min(760, Math.round(window.innerWidth * .48)))
    }

    function LensDock(props) {
      useShared()
      var widthState = useState(loadDockWidth)
      var width = widthState[0]
      var setWidth = widthState[1]
      var drag = useRef(null)

      useEffect(function () {
        document.documentElement.style.setProperty('--cddl-dock-width', width + 'px')
        try { window.localStorage.setItem(DOCK_WIDTH_KEY, String(width)) } catch (e) { /* ignore */ }
        return function () { document.documentElement.style.removeProperty('--cddl-dock-width') }
      }, [width])

      if (!shared.dockOpen) return null

      var resize = function (event) {
        if (event.button !== undefined && event.button !== 0) return
        event.preventDefault()
        event.stopPropagation()
        drag.current = { x: event.clientX, width: width }
        var move = function (e) {
          if (drag.current === null) return
          var next = drag.current.width + (drag.current.x - e.clientX)
          setWidth(Math.max(420, Math.min(window.innerWidth * .78, next)))
        }
        var up = function () {
          drag.current = null
          window.removeEventListener('pointermove', move)
          window.removeEventListener('pointerup', up)
        }
        window.addEventListener('pointermove', move)
        window.addEventListener('pointerup', up)
      }

      return h('section', {
        className: 'cddl-dock cddl-dock-open',
        style: { width: width + 'px' },
        'data-cdd-dock': '',
      }, [
        h('div', { key: 'resize', className: 'cddl-dock-resize', onPointerDown: resize, title: '拖动改变宽度' }),
        h('header', { key: 'head', className: 'cddl-dock-head' }, [
          h('strong', { key: 'title' }, 'CDD Lens'),
          h('span', { key: 'mode', className: 'cddl-meta' }, shared.edgeFocus ? '链路聚焦（临时）' : '用户布局'),
          h('span', { key: 'space', className: 'cddl-spacer' }),
          h('button', {
            key: 'close', className: 'cddl-btn',
            onClick: function () { shared.dockOpen = false; publish() },
          }, '收起'),
        ]),
        h(LensView, { key: 'view', ctx: props.ctx, docked: true }),
      ])
    }

    function LensOverlay(props) {
      return h(React.Fragment, null, [
        h(LensRuntime, { key: 'runtime', ctx: props.ctx }),
        h(LensDock, { key: 'dock', ctx: props.ctx }),
        h(TrajectorySidebar, { key: 'trajectory', ctx: props.ctx }),
      ])
    }

    module.exports = { DOCK_WIDTH_KEY, loadDockWidth, LensRuntime, LensDock, LensOverlay }
    return module.exports
  },
})

// dsh-cdd-lens — Stylesheet: the frame the graph sits in.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/styles/shell',
  factory: (require) => {
    var module = { exports: {} }

    /** Frame, panel, dock, toolbar and tree. */
    var SHELL_CSS = [
      // The overlay layer is click-through; pointer events are opted back into
      // per element, and deliberately only on the card — never on a wrapper —
      // so the rest of the frame stays clickable.
      '.cddl-root{position:absolute;right:16px;bottom:16px;pointer-events:none;display:flex;flex-direction:column;align-items:flex-end;gap:8px;z-index:400}',
      'body:has(.cddl-view) .cddl-root,body:has(.cddl-trajectory) .cddl-root{display:none}',
      // Header stays above the rail, but below DSH's workbench overlay layer.
      'body:has(.cddl-trajectory) header:has([role="tablist"]){position:relative;z-index:var(--cddl-header-layer,19);width:calc(100% + var(--cddl-trajectory-width,360px))}',
      // Nothing reserves room for the trajectory column any more. Pushing
      // #root aside squeezed the graph — the thing you opened this for —
      // and on any tab where the column did not paint, the reserved band
      // stayed behind as an empty white strip. It overlays the margin
      // beside the conversation instead, the way dsh-lifecycle's rail does.
      '.cddl-dock{position:fixed;right:var(--cddl-trajectory-width,0px);top:var(--cddl-trajectory-top,0);bottom:0;z-index:var(--cddl-dock-layer,18);pointer-events:auto;min-width:420px;max-width:78vw;display:flex;flex-direction:column;background:var(--dsw-alias-bg-layer-1);border-left:1px solid var(--dsw-alias-border-l3);box-shadow:-12px 0 32px rgba(0,0,0,.28)}',
      '.cddl-dock-resize{position:absolute;left:-6px;top:0;bottom:0;width:12px;cursor:ew-resize;z-index:6}',
      '.cddl-dock-resize:hover{background:color-mix(in srgb,var(--dsw-alias-state-business-primary) 28%,transparent)}',
      '.cddl-dock-head{height:38px;box-sizing:border-box;padding:0 10px;display:flex;align-items:center;gap:9px;flex:none;border-bottom:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-2)}',
      '.cddl-dock>.cddl-view{flex:1;min-height:0;height:auto;padding-bottom:0}',
      '.cddl-card{pointer-events:auto;position:relative;max-height:min(78vh,760px);display:flex;flex-direction:column;background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l2);border-radius:11px;box-shadow:var(--dsw-elevation-panel,0 12px 34px rgba(0,0,0,.5));overflow:hidden;color:var(--dsw-alias-label-primary);font-family:var(--dsw-font-family,inherit);font-size:12px;line-height:1.6}',
      '.cddl-pill{pointer-events:auto;cursor:pointer;padding:6px 12px;border-radius:999px;display:flex;gap:6px;align-items:center;background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l2);box-shadow:var(--dsw-elevation-panel,0 6px 18px rgba(0,0,0,.4));color:var(--dsw-alias-label-secondary);font-family:var(--dsw-font-family,inherit);font-size:12px}',
      '.cddl-pill:hover{color:var(--dsw-alias-label-primary)}',
      '.cddl-pilln{background:var(--dsw-alias-bg-layer-3);border-radius:9px;padding:0 6px;font-size:10px}',

      '.cddl-grip{position:absolute;left:0;top:0;bottom:0;width:6px;cursor:ew-resize;z-index:2}',
      '.cddl-grip:hover{background:var(--dsw-alias-border-l3)}',
      '.cddl-head{cursor:grab;user-select:none;display:flex;align-items:center;gap:8px;padding:9px 12px;border-bottom:1px solid var(--dsw-alias-border-l1);flex:none}',
      '.cddl-title{font-size:12.5px;font-weight:600}',
      '.cddl-meta{font-family:var(--ds-font-family-code,monospace);font-size:10.5px;color:var(--dsw-alias-label-caption);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddl-spacer{flex:1}',
      '.cddl-bad{color:var(--dsw-alias-state-error-primary);font-size:10.5px}',
      '.cddl-btn{border:1px solid var(--dsw-alias-border-l2);background:transparent;color:var(--dsw-alias-label-tertiary);border-radius:5px;font-size:11px;padding:2px 7px;cursor:pointer;font-family:inherit;white-space:nowrap}',
      '.cddl-btn:hover{background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}',
      '.cddl-primary{border:1px solid var(--dsw-alias-border-l3);background:var(--dsw-alias-bg-layer-3);color:var(--dsw-alias-label-primary);border-radius:6px;font-size:11.5px;padding:4px 12px;cursor:pointer;font-family:inherit;margin-top:8px}',
      '.cddl-primary:disabled{opacity:.5;cursor:default}',

      '.cddl-tabs{display:flex;gap:2px;padding:6px 12px 0;border-bottom:1px solid var(--dsw-alias-border-l1);flex:none}',
      '.cddl-tabs button{background:transparent;border:0;border-bottom:2px solid transparent;cursor:pointer;padding:4px 10px;font-size:11.5px;color:var(--dsw-alias-label-caption);font-family:inherit}',
      '.cddl-tabs button.on{color:var(--dsw-alias-label-primary);border-bottom-color:var(--dsw-alias-state-business-primary)}',

      '.cddl-search{position:relative;padding:8px 12px 0;flex:none}',
      '.cddl-q{width:100%;box-sizing:border-box;background:var(--dsw-alias-bg-layer-1);border:1px solid var(--dsw-alias-border-l2);border-radius:6px;padding:4px 9px;font-size:11.5px;color:var(--dsw-alias-label-primary);font-family:inherit;outline:none}',
      '.cddl-q::placeholder{color:var(--dsw-alias-label-dimmed)}',
      '.cddl-hits{position:absolute;left:12px;right:12px;top:100%;z-index:3;max-height:280px;overflow:auto;background:var(--dsw-alias-bg-layer-3);border:1px solid var(--dsw-alias-border-l2);border-radius:7px;box-shadow:0 8px 22px rgba(0,0,0,.45);padding:4px}',
      '.cddl-hit{display:flex;align-items:baseline;gap:8px;padding:4px 7px;border-radius:5px;cursor:pointer}',
      '.cddl-hit:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-hitfile{margin-left:auto;font-family:var(--ds-font-family-code,monospace);font-size:10px;color:var(--dsw-alias-label-caption)}',

      '.cddl-body{flex:1;min-height:120px;overflow:auto}',
      '.cddl-tree{padding:8px 10px 10px}',
      '.cddl-filehdr{font-family:var(--ds-font-family-code,monospace);font-size:10px;color:var(--dsw-alias-label-caption);margin:8px 0 3px}',
      '.cddl-node{display:flex;align-items:center;gap:6px;padding:3px 6px;border-radius:6px;cursor:pointer}',
      '.cddl-node:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-sel{background:var(--dsw-alias-interactive-bg-active)}',
      '.cddl-ind{flex:none}',
      '.cddl-twist{width:14px;flex:none;color:var(--dsw-alias-label-dimmed);font-size:9px;text-align:center;background:transparent;border:0;cursor:pointer;padding:0;font-family:inherit}',
      '.cddl-twist:hover{color:var(--dsw-alias-label-primary)}',
      '.cddl-dot{width:7px;height:7px;border-radius:50%;flex:none;background:var(--dsw-alias-label-dimmed);display:inline-block}',
      '.cddl-dot.cddl-v{background:var(--dsw-alias-state-business-primary)}',
      '.cddl-dot.cddl-e{background:var(--dsw-alias-state-warn-primary)}',
      '.cddl-dot.cddl-w{background:var(--dsw-alias-state-error-primary);box-shadow:0 0 0 3px rgba(242,90,90,.2)}',
      '.cddl-sym{font-family:var(--ds-font-family-code,monospace);font-size:11.5px;color:var(--dsw-alias-label-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddl-sel .cddl-sym{color:var(--dsw-alias-label-primary)}',
      '.cddl-kind{font-size:9.5px;color:var(--dsw-alias-label-caption);flex:none;border:1px solid var(--dsw-alias-border-l2);border-radius:3px;padding:0 3px;white-space:nowrap}',
      '.cddl-turn{font-family:var(--ds-font-family-code,monospace);font-size:9.5px;flex:none;padding:0 5px;border-radius:9px;border:1px solid transparent;white-space:nowrap}',
      '.cddl-turn.cddl-v{color:var(--dsw-alias-state-business-primary);border-color:var(--dsw-alias-state-business-tertiary)}',
      '.cddl-turn.cddl-e{color:var(--dsw-alias-state-warn-primary);border-color:var(--dsw-alias-state-warn-tertiary)}',
      '.cddl-turn.cddl-w{color:var(--dsw-alias-state-error-primary);border-color:var(--dsw-alias-state-error-secondary)}',
      '.cddl-lines{font-family:var(--ds-font-family-code,monospace);font-size:9.5px;color:var(--dsw-alias-label-dimmed);margin-left:auto;flex:none;padding-left:6px;white-space:nowrap}',
      '.cddl-hop{margin-left:auto;display:flex;gap:2px;flex:none;opacity:.55}',
      '.cddl-node:hover .cddl-hop,.cddl-sel .cddl-hop{opacity:1}',
      '.cddl-hop button{font-size:10px;font-family:var(--ds-font-family-code,monospace);cursor:pointer;color:var(--dsw-alias-label-caption);background:transparent;border:1px solid var(--dsw-alias-border-l2);border-radius:4px;padding:0 4px}',
      '.cddl-hop button:hover{color:var(--dsw-alias-label-primary);background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-hop button.on{color:var(--dsw-alias-label-primary);border-color:var(--dsw-alias-border-l4)}',
      // Compaction took the verbatim evidence back: pale, not gone.
      '.cddl-faded{opacity:.4}',
      '.cddl-faded .cddl-sym{font-style:italic}',
      '.cddl-island{border-left:2px dashed var(--dsw-alias-border-l3)}',
      '.cddl-bridge .cddl-sym{color:var(--dsw-alias-label-caption)}',
      '.cddl-bridgetag{border-style:dashed;opacity:.8}',
      '.cddl-gap{display:flex;align-items:center;gap:7px;padding:6px 4px;color:var(--dsw-alias-label-caption);font-size:10px}',
      '.cddl-gap i{flex:1;height:1px;background:repeating-linear-gradient(90deg,var(--dsw-alias-label-dimmed) 0 3px,transparent 3px 7px)}',

      '.cddl-dir,.cddl-fileitem,.cddl-symitem{display:flex;align-items:center;gap:6px;padding:3px 6px;border-radius:6px;cursor:pointer;font-size:11.5px}',
      '.cddl-dir{color:var(--dsw-alias-label-secondary);font-family:var(--ds-font-family-code,monospace)}',
      '.cddl-fileitem{padding-left:20px;color:var(--dsw-alias-label-caption);font-family:var(--ds-font-family-code,monospace)}',
      '.cddl-symitem{padding-left:38px}',
      '.cddl-dir:hover,.cddl-fileitem:hover,.cddl-symitem:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-count{margin-left:auto;font-family:var(--ds-font-family-code,monospace);font-size:10px;color:var(--dsw-alias-label-dimmed);flex:none}',
      '.cddl-sub{padding-left:38px;color:var(--dsw-alias-label-dimmed);font-size:11px}',

      '.cddl-empty{padding:18px 14px;color:var(--dsw-alias-label-tertiary);font-size:11.5px;line-height:1.8}',
      '.cddl-path{font-family:var(--ds-font-family-code,monospace);font-size:10.5px;color:var(--dsw-alias-label-caption);word-break:break-all;margin:4px 0}',
      '.cddl-progress{color:var(--dsw-alias-label-caption);font-size:11px;margin-top:6px}',
      '.cddl-tail{font-family:var(--ds-font-family-code,monospace);font-size:10px;color:var(--dsw-alias-label-dimmed);max-height:90px;overflow:auto;margin-top:8px;white-space:pre-wrap}',

      '.cddl-legend{display:flex;flex-wrap:wrap;gap:12px;padding:8px 12px;flex:none;border-top:1px solid var(--dsw-alias-border-l1);font-size:10.5px;color:var(--dsw-alias-label-caption)}',
      '.cddl-legend b{font-weight:400;display:flex;align-items:center;gap:5px}',
      '.cddl-swatch{display:inline-block;width:18px;height:0;border-top:1.5px solid var(--dsw-alias-border-l4)}',
      '.cddl-swatch.cddl-dataflow{border-top-style:dashed}',
      '.cddl-swatch.cddl-inherit{border-top-style:dotted}',
      '.cddl-swatch.cddl-impact{border-top:2px dotted var(--dsw-alias-border-l3)}',
      '.cddl-swatch.cddl-dispatch{border-top:2px dashed var(--dsw-alias-border-l4)}',

      '.cddl-src{border-top:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);flex:none}',
      '.cddl-srch{font-family:var(--ds-font-family-code,monospace);font-size:10px;padding:8px 8px 4px 12px;color:var(--dsw-alias-label-caption);word-break:break-all;display:flex;align-items:flex-start;gap:8px}',
      '.cddl-srch>span{min-width:0;flex:1}',
      '.cddl-src-close{flex:none;width:24px;height:24px;border:1px solid var(--dsw-alias-border-l2);border-radius:5px;background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-caption);cursor:pointer;font-size:16px;line-height:18px}',
      '.cddl-src pre{margin:0;padding:0 12px 10px;font-family:var(--ds-font-family-code,monospace);font-size:10.5px;line-height:1.65;color:var(--dsw-alias-label-tertiary);max-height:180px;overflow:auto}',
      '.cddl-hl{background:var(--dsw-alias-state-warn-tertiary);display:block;margin:0 -12px;padding:0 12px;border-left:2px solid var(--dsw-alias-state-warn-primary)}',
      '.cddl-ln{color:var(--dsw-alias-label-dimmed);user-select:none;display:inline-block;width:34px}',
      '.cddl-code{white-space:pre}',
      '.cddl-hist{border-top:1px solid var(--dsw-alias-border-l1);padding:8px 12px;flex:none}',
      '.cddl-hist h4{margin:0 0 5px;font-size:10.5px;color:var(--dsw-alias-label-caption);font-weight:500}',
      '.cddl-unres{margin:10px 10px 4px;padding:8px 10px;border-radius:8px;border:1px dashed var(--dsw-alias-border-l3);background:var(--dsw-alias-bg-layer-1)}',
      '.cddl-unres h4{display:flex;align-items:center;gap:6px}',
      '.cddl-rank{font-family:var(--ds-font-family-code,monospace);font-size:9px;flex:none;width:15px;text-align:right;color:var(--dsw-alias-label-dimmed)}',
      '.cddl-rank-none{color:transparent}',
      '.cddl-hop button.cddl-off{opacity:.3;cursor:default}',
      '.cddl-hop button.cddl-off:hover{background:transparent;color:var(--dsw-alias-label-caption)}',
      '.cddl-unres h4{margin:0 0 5px;font-size:10.5px;color:var(--dsw-alias-label-caption);font-weight:500}',
      '.cddl-unrow{display:flex;align-items:center;gap:7px;padding:1px 0;opacity:.75}',
      '.cddl-hrow{display:flex;align-items:center;gap:7px;font-size:11px;color:var(--dsw-alias-label-tertiary);padding:1px 0}',
      '.cddl-agent{font-family:var(--ds-font-family-code,monospace);color:var(--dsw-alias-state-business-primary)}',
      '.cddl-reason{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--dsw-alias-label-secondary)}',
      '.cddl-t{font-family:var(--ds-font-family-code,monospace);font-size:10px;color:var(--dsw-alias-label-caption);width:26px;flex:none}',

      // ---- the spread-out view ----
      '.cddl-view{--cddl-bottom-clearance:calc(var(--dsh-composer-height,152px) + 16px);display:flex;flex-direction:column;height:100%;min-height:0;width:100%;box-sizing:border-box;padding-bottom:var(--cddl-bottom-clearance);overflow:hidden;background:var(--dsw-alias-bg-layer-1);color:var(--dsw-alias-label-primary);font-family:var(--dsw-font-family,inherit);font-size:12px}',
      '.cddl-view-docked{--cddl-bottom-clearance:0px}',
      '.cddl-toolbar{display:flex;align-items:center;gap:8px;padding:8px 16px;flex:none;flex-wrap:wrap;border-bottom:1px solid var(--dsw-alias-border-l1)}',
      '.cddl-view-docked .cddl-toolbar{flex-wrap:nowrap;overflow-x:auto;overflow-y:hidden;padding:6px 8px}',
      '.cddl-view-docked .cddl-toolbar>*{flex:none}',
      '.cddl-view-docked>.cddl-legend{display:none}',
      '.cddl-toolbar .cddl-search{padding:0;width:240px;flex:none}',
      '.cddl-seg{display:flex;border:1px solid var(--dsw-alias-border-l2);border-radius:6px;overflow:hidden;flex:none}',
      '.cddl-seg button{padding:3px 11px;font-size:11.5px;background:transparent;border:0;cursor:pointer;color:var(--dsw-alias-label-caption);border-right:1px solid var(--dsw-alias-border-l2);font-family:inherit}',
      '.cddl-seg button:last-child{border-right:0}',
      '.cddl-seg button.on{background:var(--dsw-alias-bg-layer-3);color:var(--dsw-alias-label-primary)}',
      '.cddl-relations button{font-family:var(--ds-font-family-code,monospace);font-size:10.5px;padding:3px 8px}',
      '.cddl-relations button.on{box-shadow:inset 0 -2px 0 var(--dsw-alias-state-business-primary)}',
      '.cddl-zoom{display:flex;gap:2px;align-items:center}',
      '.cddl-zoom .cddl-btn:nth-child(2){min-width:46px;font-family:var(--ds-font-family-code,monospace)}',
    ]

    module.exports = { SHELL_CSS }
    return module.exports
  },
})

// dsh-cdd-lens — The plugin surface: slot injection and apply.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __shell_graph_iew = require('dsh-cdd-lens/shell/graphView')
    var LensView = __shell_graph_iew.LensView
    var __shell_boundary = require('dsh-cdd-lens/shell/boundary')
    var makeBoundary = __shell_boundary.makeBoundary
    var Boundary = makeBoundary(React)
    var __shell_dock = require('dsh-cdd-lens/shell/dock')
    var LensOverlay = __shell_dock.LensOverlay
    var __styles_shell = require('dsh-cdd-lens/styles/shell')
    var SHELL_CSS = __styles_shell.SHELL_CSS
    var __styles_graph = require('dsh-cdd-lens/styles/graph')
    var GRAPH_CSS = __styles_graph.GRAPH_CSS

    var CSS = SHELL_CSS.concat(GRAPH_CSS).join('')

    function apply(ctx) {
      var slots = ctx.get('slots')
      if (slots === undefined) return

      // No target of our own is registered: `trajectory` is read as it is.
       // See the fold above for why a target without node definitions receives
       // nothing.

      // ctx.effect's argument is the effect BODY — it runs immediately and its
      // return value is the disposer. Appending outside and passing removeChild
      // in would tear the stylesheet down on the next line.
      ctx.effect(function () {
        var style = document.createElement('style')
        style.dataset.plugin = 'dsh-cdd-lens'
        style.dataset.pluginCss = 'dsh-cdd-lens/lens.module.css'
        style.textContent = CSS
        document.head.appendChild(style)
        return function () { document.head.removeChild(style) }
      })

      // A slot exists only while the entry that declared it is mounted, and
      // registering into an undeclared slot throws. `inject` runs the
      // registration when the declaration is (or becomes) live, and re-runs it
      // if the owner remounts.
      slots.inject('shell.overlay', function () {
        return slots.register({ name: 'shell.overlay', id: 'cdd-lens', order: 50 },
          function () { return h(LensOverlay, { ctx: ctx }) })
      })

      slots.inject('conversation.view', function () {
        return slots.register({ name: 'conversation.view', id: 'cdd-lens', order: 20, label: 'CDD Lens' },
          // Wrapped, because a throw inside the view used to blank the seat and
          // say nothing — and finding out which line did it cost a round trip
          // every time. See shell/boundary.js.
          function () {
            var view = h(LensView, { ctx: ctx })
            return Boundary === null ? view : h(Boundary, null, view)
          })
      })
    }

    module.exports = { name: 'cdd-lens', inject: ['slots', 'sessions', 'uiConversation', 'layout'], apply: apply }
    return module.exports
  },
})
