// dsh-cdd-lens — browser half. GENERATED, DO NOT EDIT.
//
// Built from src/client/ by scripts/build.js. Edit the parts, not this file.
// Written in the shape tsdown emits (`__ModuleLoader__.load` + a CJS body +
// the loader's `require`), so a generated bundle drops in on top.
//
// build: V1_24_DOCK_OPEN_PERSIST_007
// parts: 57

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
    var BUILD = 'V1_20_COMPACT_TOPOLOGY_GRAPH_015'
    var ROUTE = '/plugins/cdd-lens'

    // ---- wire -------------------------------------------------------------

    function api(path, params) {
      var url = ROUTE + path + '?' + new URLSearchParams(params || {}).toString()
      return fetch(url, { cache: 'no-store' }).then(function (res) {
        if (!res.ok) return res.json().catch(function () { return {} }).then(function (body) {
          throw new Error(body.error || ('HTTP ' + res.status))
        })
        return res.json()
      })
    }

    /** Same wrapper with a JSON body, for payloads too long for a query string. */
    function apiPost(path, params, payload) {
      var url = ROUTE + path + '?' + new URLSearchParams(params || {}).toString()
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
    // Nodes and edges accumulate as you walk. Nothing is ever silently dropped:
    // collapsing hides descendants that no other branch and no pin is holding,
    // and the anchor's turn record survives regardless — a collapse must not
    // erase that the agent was there on turn 3.

    function emptyGraph() {
      return { nodes: {}, order: [], edges: [], rootId: null }
    }

    function addNode(graph, anchor) {
      if (graph.nodes[anchor.id] !== undefined) {
        // Refresh the counts; a reindex can change them under us.
        graph.nodes[anchor.id].anchor = anchor
        return false
      }
      graph.nodes[anchor.id] = {
        anchor: anchor, down: false, up: false, members: false, pinned: false,
      }
      graph.order.push(anchor.id)
      return true
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

    module.exports = { emptyGraph, addNode, addEdge, removeNode }
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

    var STICKY_TURNS = 3

    function stickyByRecency(id) {
      var record = shared.trace[id]
      if (record === undefined) return false
      return shared.turn - record.lastTurn < STICKY_TURNS
    }

    function visible(graph) {
      var roots = []
      if (graph.rootId !== null && graph.nodes[graph.rootId] !== undefined) roots.push(graph.rootId)
      graph.order.forEach(function (id) {
        var node = graph.nodes[id]
        if (node.pinned || node.island || stickyByRecency(id)) roots.push(id)
      })
      var seen = {}
      var stack = roots.slice()
      while (stack.length > 0) {
        var id = stack.pop()
        if (seen[id]) continue
        seen[id] = true
        var node = graph.nodes[id]
        if (node === undefined) continue
        graph.edges.forEach(function (e) {
          // `always` edges join the session's own anchors; they show whether or
          // not anyone pressed expand.
          if (e.from === id && (node.down || e.always)) stack.push(e.to)
          if (e.to === id && (node.up || e.always)) stack.push(e.from)
        })
      }
      return seen
    }

    module.exports = { STICKY_TURNS, stickyByRecency, visible }
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
        expand: function (id, direction) {
          var node = shared.graph.nodes[id]
          if (node === undefined) return Promise.resolve()
          shared.selected = id
          requestViewport(id, 'center')
          node['manual' + direction] = false
          if (node[direction]) return Promise.resolve()
          node.loading = direction
          publish()
          return api('/neighbors', params({ id: id, dir: direction })).then(function (body) {
            body.peers.forEach(function (peer) {
              addNode(shared.graph, peer)
              shared.graph.nodes[peer.id].explored = true
              if (direction === 'down') addEdge(shared.graph, id, peer.id, peer.types)
              else addEdge(shared.graph, peer.id, id, peer.types)
            })
            node[direction] = true
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
          }
          publish()
        },
        blurEdge: function () {
          if (shared.edgeFocus === null || shared.edgeFocus === undefined) return
          shared.edgeFocus = null
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
            })
            shared.trace = byAnchor
            shared.unresolved = Object.keys(unresolved).map(function (k) { return unresolved[k] })
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
                shared.graph.nodes[id].island = true
                fresh.push(id)
              }
              shared.graph.nodes[id].session = true
            })
            if (shared.graph.rootId === null) {
              var newest = ids.map(function (id) { return byAnchor[id] })
                .sort(function (l, r) { return r.lastTurn - l.lastTurn })[0]
              shared.graph.rootId = newest.id
              shared.graph.nodes[newest.id].island = false
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
                  shared.graph.nodes[anchor.id].bridge = true
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
                  shared.graph.nodes[e.from].island = false
                }
                if (shared.graph.nodes[e.to] !== undefined) {
                  shared.graph.nodes[e.to].island = false
                }
              })
              publish()
              return grow()
            })
          }

          // What the picture is about is what was changed. The edits are the
          // seeds; `chain` pushes each of them out and back and reports the
          // trees they land in, so a node arrives already knowing its layer
          // instead of the view having to invent one from file names.
          var grow = function () {
            var edits = Object.keys(shared.trace || {}).filter(function (id) {
              var record = shared.trace[id]
              return record.state === 'edited' || record.state === 'working'
            })
            // Nothing was edited yet — a session that has only read so far still
            // deserves a picture, so the reads stand in as seeds.
            if (edits.length === 0) edits = Object.keys(shared.trace || {})
            return engine.chain(edits, 1)
          }

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
          if (node === undefined) return Promise.resolve()
          if (shared.gather !== null && shared.gather !== undefined && shared.gather.focus === id) {
            return Promise.resolve()
          }
          // freed: ids the user dragged out of the column while it was up.
          // They stay where they were dropped until the gather itself ends.
          shared.gather = { focus: id, freed: {} }
          stampFlight()
          publish()
          var loads = []
          if (node.up !== true) loads.push(engine.expand(id, 'up'))
          if (node.down !== true) loads.push(engine.expand(id, 'down'))
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
        if (node === undefined) return
        // Callers of an expanded node render ABOVE it at the same depth,
        // whichever direction the walk arrived from. Gating this on the arrival
        // direction meant pressing ↑ on anything below the root added the nodes
        // and drew none of them — the button looked dead.
        if (node.up) {
          graph.edges.forEach(function (e) {
            if (e.to === id) walk(e.from, depth, 'up')
          })
        }
        rows.push({ id: id, depth: depth, node: node })
        if (node.members && node.memberList !== undefined) {
          node.memberList.forEach(function (member) {
            rows.push({ id: member.id, depth: depth + 1, member: true, anchor: member })
          })
        }
        if (node.down) {
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
      var anchor = row.member ? row.anchor : row.node.anchor
      var record = stateOf(row.id)
      var faded = record !== null && record !== undefined && !record.remembered
      var selected = shared.selected === row.id
      var cls = 'cddl-node'
        + (selected ? ' cddl-sel' : '')
        + (faded ? ' cddl-faded' : '')
        + (row.node !== undefined && row.node.bridge === true ? ' cddl-bridge' : '')
        + (row.islandRow ? ' cddl-island' : '')

      var kids = [
        h('span', { key: 'i', className: 'cddl-ind', style: { width: (row.depth * 17) + 'px' } }),
      ]
      if (!row.member && (anchor.members > 0)) {
        kids.push(h('button', {
          key: 't', className: 'cddl-twist', title: anchor.members + ' 个成员',
          onClick: function (e) { e.stopPropagation(); engine.members(row.id) },
        }, row.node.members ? '▾' : '▸'))
      } else {
        kids.push(h('span', { key: 't', className: 'cddl-twist' }, row.member ? '·' : ''))
      }
      var rank = orderOf(row.id)
      kids.push(rank === null
        ? h('span', { key: 'r', className: 'cddl-rank cddl-rank-none' }, '')
        : h('span', { key: 'r', className: 'cddl-rank', title: '第 ' + rank + ' 个被碰到' }, rank))
      kids.push(h('span', { key: 'd', className: dotClass(record) }))
      kids.push(h('span', { key: 's', className: 'cddl-sym', title: anchor.id }, anchor.symbol))
      if (!row.member && anchor.members > 0) {
        kids.push(h('span', { key: 'k', className: 'cddl-kind' }, '类 ' + anchor.members))
      }
      if (row.node !== undefined && row.node.bridge === true) {
        kids.push(h('span', {
          key: 'br', className: 'cddl-kind cddl-bridgetag',
          title: 'agent 没打开过它。它出现在这里，是因为代码里它把上下两个碰过的 anchor 连起来了。',
        }, '桥'))
      }
      var badge = turnLabel(record)
      if (badge !== null) kids.push(React.cloneElement(badge, { key: 'b' }))
      if (faded) kids.push(h('span', { key: 'f', className: 'cddl-kind' }, '压缩'))
      var hop = function (dir, count, label) {
        // A zero count is a fact about the index, not a button. Leaving it
        // clickable makes every press look broken; disabling it says the index
        // has no such edge, which is the actual answer.
        return h('button', {
          key: dir,
          disabled: count === 0,
          title: count === 0
            ? (dir === 'u' ? '索引里没有谁用它' : '索引里它没用任何东西')
            : ((row.node && row.node[dir === 'u' ? 'up' : 'down'] ? '收起' : '展开')
              + (dir === 'u' ? '：谁在用它（' : '：它在用谁（') + count + '）'),
          className: (row.node && row.node[dir === 'u' ? 'up' : 'down'] ? 'on' : '')
            + (count === 0 ? ' cddl-off' : ''),
          onClick: function (e) {
            e.stopPropagation()
            if (count === 0) return
            var direction = dir === 'u' ? 'up' : 'down'
            if (row.node && row.node[direction]) engine.collapse(row.id, direction)
            else engine.expand(row.id, direction)
          },
        }, label + count)
      }
      kids.push(h('span', { key: 'h', className: 'cddl-hop' }, [
        hop('u', anchor.up, '↑'),
        hop('d', anchor.down, '↓'),
        h('button', {
          key: 'p', title: '固定',
          className: row.node && row.node.pinned ? 'on' : '',
          onClick: function (e) { e.stopPropagation(); engine.pin(row.id) },
        }, row.node && row.node.pinned ? '●' : '○'),
      ]))

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
        var anchor = row.member ? row.anchor : row.node.anchor
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
      if (body.ready !== true || !body.stamp || body.stamp === before.stamp) return before
      return { stamp: body.stamp }
    }

    function Draw(props) {
      var engine = props.engine
      // The iframe goes up on the first render. `/draw` always answers with a
      // page: the paged browser shell when it exists, or the server-owned build
      // shell while it is being regenerated. Client-side loading/error cards
      // only hid that real shell and could get stuck in front of it.
      var state = useState({ stamp: 0 })
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

    function Source(props) {
      var id = shared.selected
      if (id === null || id === undefined) return null
      var source = (shared.sourceCache || {})[id]
      var node = shared.graph.nodes[id]
      var anchor = node !== undefined ? node.anchor : null
      if (source === undefined) {
        return h('div', { className: 'cddl-src' }, h('div', { className: 'cddl-srch' }, '读源码…'))
      }
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
          h('span', { key: 't' }, source.file + ' · ' + (anchor ? anchor.symbol : '') + ' · ' + source.start + '–' + source.end),
          h('button', {
            key: 'x', className: 'cddl-src-close', title: '关闭源码详情',
            onClick: function () { props.engine.blur() },
          }, '×'),
        ]),
        h('pre', { key: 'p' }, lines),
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
        h('b', { key: 'call' }, [h('i', { key: 'd', className: 'cddl-swatch cddl-call' }), 'call']),
        h('b', { key: 'data' }, [h('i', { key: 'd', className: 'cddl-swatch cddl-dataflow' }), 'dataflow']),
        h('b', { key: 'inherit' }, [h('i', { key: 'd', className: 'cddl-swatch cddl-inherit' }), 'inherit']),
        h('b', { key: 'impact' }, [h('i', { key: 'd', className: 'cddl-swatch cddl-impact' }), 'impact']),
        h('b', { key: 'dispatch' }, [h('i', { key: 'd', className: 'cddl-swatch cddl-dispatch' }), 'dispatch']),
        h('b', { key: 'plus', className: 'cddl-action-help cddl-action-help-plus' }, '＋N 显示 N 个下游'),
        h('b', { key: 'minus', className: 'cddl-action-help cddl-action-help-minus' }, '−N 隐藏 N 个下游'),
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

    function GraphNode(props) {
      var engine = props.engine
      var p = props.p
      var zoom = props.zoom || 1
      var drag = useRef(null)
      var anchor = p.node.anchor
      var record = stateOf(p.id)
      var faded = record !== null && record !== undefined && !record.remembered
      var selected = shared.selected === p.id
      var isClass = anchor.kind === 'class' || anchor.members > 0

      var head = h('div', { className: 'cddl-gtop' + (isClass ? ' cddl-class-header' : ''), key: 'top' }, [
        h('span', { key: 'd', className: dotClass(record) }),
        h('span', { key: 's', className: 'cddl-sym', title: anchor.id },
          p.label || anchor.symbol.split('.').pop() || anchor.symbol),
        turnLabel(record) === null ? null : React.cloneElement(turnLabel(record), { key: 'b' }),
        isClass ? h('button', {
          key: 'c', className: 'cddl-count',
          title: anchor.members + ' 个成员',
          onClick: function (e) { e.stopPropagation(); engine.members(p.id) },
        }, (p.node.members ? '▾ ' : '▸ ') + anchor.members)
          : h('span', { key: 'l', className: 'cddl-lines' }, anchor.start + '–' + anchor.end),
        isClass ? h('span', { key: 'k', className: 'cddl-kind' }, '类') : null,
      ])

      // Read before the buttons are built, not after. `var` hoisting made
      // these undefined inside the action row when it moved into the card,
      // so the button never lit up and its tooltip said the wrong thing
      // while the expansion itself worked fine.
      var upOpen = p.node.up === true
      var downOpen = p.node.down === true

      var actions =
        h('div', { key: 'h', className: 'cddl-node-actions' }, [
          h('button', {
            key: 'u',
            title: anchor.up === 0
              ? '索引里没有谁用它'
              : (upOpen ? '收起：谁在用它（' + anchor.up + '）' : '展开：谁在用它（' + anchor.up + '）'),
            disabled: anchor.up === 0,
            className: 'cddl-action-up' + (upOpen ? ' on' : ''),
            'data-action': 'expand-callers',
            onClick: function (e) {
              e.stopPropagation()
              if (upOpen) engine.collapse(p.id, 'up')
              else engine.expand(p.id, 'up')
            },
          }, '↑' + anchor.up),
          h('button', {
            key: 'd',
            title: anchor.down === 0
              ? '索引里它没用任何东西'
              : (downOpen ? '收起：它在用谁（' + anchor.down + '）' : '展开：它在用谁（' + anchor.down + '）'),
            disabled: anchor.down === 0,
            className: 'cddl-action-down' + (downOpen ? ' on' : ''),
            'data-action': 'expand-callees',
            onClick: function (e) {
              e.stopPropagation()
              if (downOpen) engine.collapse(p.id, 'down')
              else engine.expand(p.id, 'down')
            },
          }, '↓' + anchor.down),
          h('button', {
            key: 'p',
            title: p.node.pinned
              ? '取消固定'
              : (stickyByRecency(p.id)
                ? '最近碰过，自动保留三轮；点一下改为永久固定'
                : '固定：折叠上级时也留在图上'),
            className: 'cddl-action-pin' + (p.node.pinned ? ' on' : (stickyByRecency(p.id) ? ' auto' : '')),
            'data-action': 'pin-anchor',
            onClick: function (e) { e.stopPropagation(); engine.pin(p.id) },
          }, 'pin'),
        ])

      var members = null
      if (p.node.members && p.node.memberList !== undefined) {
        members = h('div', { className: 'cddl-members', key: 'm' },
          p.node.memberList.map(function (member) {
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
          }).concat([h('div', { key: 'more', className: 'cddl-more' }, '共 ' + p.node.memberList.length + ' 个方法')]))
      }

      // The same card is used twice: positioned on the canvas, and standing in
      // the flow of the stream rail. Only where it sits differs, so only that
      // is switched — a second component would drift from this one.
      var flow = props.flow === true
      var vertical = p.flowAxis === 'vertical'
      var ports = p.routingPorts
      if (!ports || !ports.length) ports = [
        {side:vertical?'top':'left',in:true,out:false},
        {side:vertical?'bottom':'right',in:false,out:true},
      ]
      var portViews = ports.map(function (port) {
        var role=port.in && port.out?'both':port.in?'in':'out'
        return h('span', {key:'port-'+port.side,
          className:'cddl-port cddl-port-'+role+' cddl-port-'+port.side,
          'data-port':role, 'data-port-side':port.side,
          title:role==='both'?'此处有进入和离开此 Anchor 的关系':port.in?'关系进入此 Anchor':'关系离开此 Anchor',
        }, role==='both'?'入出':port.in?'入':'出')
      })
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
        'data-open': (upOpen ? 'up' : '') + (downOpen ? 'down' : '') || 'none',
      }, [
        portViews,
        h('div', {
          key: 'n',
          className: 'cddl-gnode'
            + (shared.lit === null || shared.lit === undefined ? ''
              : (shared.lit.nodes[p.id] === true ? ' cddl-lit' : ' cddl-unlit'))
            + (selected ? ' cddl-sel' : '')
            + (faded ? ' cddl-faded' : '')
            + (p.node.island ? ' cddl-island' : '')
            + (isClass ? ' cddl-cls cddl-class' : ''),
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
    var visible = __graph_visible.visible
    var __layout_camera = require('dsh-cdd-lens/layout/camera')
    var edgeFocusOf = __layout_camera.edgeFocusOf

    /**
     * What is on screen at all, and which file each anchor belongs to.
     */
    function layoutScope(graph) {

      var shown = visible(graph)

      // A file is the first visual unit. Session-touched anchors are always
      // present; manual +/- exploration may add more anchors and therefore a
      // new file box, while bridge-only implementation details stay hidden.
      var included = graph.order.filter(function (id) {
        var node = graph.nodes[id]
        return shown[id] && node !== undefined
          && (node.session || node.explored || node.pinned || id === shared.selected || id === graph.rootId)
      })
      if (included.length === 0 && graph.nodes[graph.rootId]) included.push(graph.rootId)
      var activeFocus = edgeFocusOf(graph)
      if (activeFocus !== null) {
        included = graph.order.filter(function (id) {
          return activeFocus.ids[id] === true && graph.nodes[id] !== undefined
        })
      }
      var byFile = {}
      var fileOrder = []
      included.forEach(function (id) {
        var file = graph.nodes[id].anchor.file
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
        return graph.nodes[id].anchor.symbol.split && graph.nodes[id].anchor.symbol.split('.').pop() === 'main'
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
          var la = graph.nodes[l].anchor
          var ra = graph.nodes[r].anchor
          var lm = la.symbol.split('.').pop() === 'main' ? 0 : 1
          var rm = ra.symbol.split('.').pop() === 'main' ? 0 : 1
          return relationRank[l] - relationRank[r] || lm - rm
            || (la.start || 0) - (ra.start || 0) || la.symbol.localeCompare(ra.symbol)
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
      '.cddl-wire{fill:none;stroke:var(--dsw-alias-state-business-primary);stroke-width:1.8}',
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
      '.cddl-wire.cddl-hot{stroke-width:2.6;opacity:1}',
      '.cddl-wire.cddl-cold{opacity:.22}',
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
      '.cddl-wire.cddl-lit{stroke-width:2.2;opacity:1}',
      '.cddl-wire.cddl-unlit{opacity:.13}',
      '.cddl-gnode.cddl-lit{border-color:var(--dsw-alias-state-business-primary)}',
      '.cddl-gnode.cddl-unlit{opacity:.3}',
      '.cddl-arrowhead.cddl-unlit{opacity:.13}',
      '.cddl-node-shell{position:absolute}',
      // Gather flights only. Scoped to the window so panning or dragging a
      // settled drawing never lags; 260ms matches GATHER_MS in engine/gather.
      '.cddl-gathering .cddl-node-shell{transition:left .26s ease,top .26s ease}',
      '.cddl-node-flow{position:static;flex:none}',
      '.cddl-node-flow .cddl-port{display:none}',
      '.cddl-port{position:absolute;top:50%;z-index:4;width:24px;height:20px;box-sizing:border-box;display:flex;align-items:center;justify-content:center;transform:translateY(-50%);border-radius:4px;font:800 10px var(--ds-font-family-code,monospace);background:var(--dsw-alias-bg-layer-3);box-shadow:0 0 0 2px var(--dsw-alias-bg-base)}',
      '.cddl-port-left{left:-29px}',
      '.cddl-port-right{right:-29px}',
      '.cddl-port-top{left:50%;top:-25px;transform:translateX(-50%)}',
      '.cddl-port-bottom{left:50%;top:auto;bottom:-25px;transform:translateX(-50%)}',
      '.cddl-port-in{color:var(--dsw-alias-state-business-primary);border:1px solid var(--dsw-alias-state-business-primary)}',
      '.cddl-port-both{color:var(--dsw-alias-label-primary);border:1px solid var(--dsw-alias-border-l3)}',
      '.cddl-port-out{color:var(--dsw-alias-state-warn-primary);border:1px solid var(--dsw-alias-state-warn-primary)}',
      '.cddl-node-actions{display:flex;gap:4px;margin-top:4px;z-index:2}',
      '.cddl-node-actions button{font-size:10px}',
      '.cddl-node-shell:hover .cddl-node-actions,.cddl-node-shell:focus-within .cddl-node-actions{opacity:1}',
      '.cddl-node-actions button{min-width:26px;height:19px;padding:0 5px;border-radius:5px;cursor:pointer;font:700 11px var(--ds-font-family-code,monospace);color:var(--dsw-alias-state-business-primary);background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-state-business-tertiary)}',
      '.cddl-node-actions .cddl-action-collapse:not(:disabled){color:var(--dsw-alias-state-warn-primary);border-color:var(--dsw-alias-state-warn-tertiary)}',
      '.cddl-node-actions button:hover:not(:disabled),.cddl-node-actions button.on{color:var(--dsw-alias-label-primary);border-color:var(--dsw-alias-border-l4);background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-node-actions button:disabled{opacity:.34;cursor:default}',
      '.cddl-action-help{font-family:var(--ds-font-family-code,monospace);font-weight:600!important}',
      '.cddl-action-help-plus{color:var(--dsw-alias-state-business-primary)!important}',
      '.cddl-action-help-minus{color:var(--dsw-alias-state-warn-primary)!important}',
      '.cddl-gnode{position:relative;box-sizing:border-box;width:100%;background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l2);border-radius:8px;padding:7px 10px;cursor:grab;touch-action:none;box-shadow:0 2px 10px rgba(0,0,0,.3)}',
      '.cddl-gnode:hover{border-color:var(--dsw-alias-border-l4)}',
      '.cddl-gnode.cddl-sel{border-color:var(--dsw-alias-state-warn-primary);box-shadow:0 0 0 1px var(--dsw-alias-state-warn-tertiary),0 6px 18px rgba(0,0,0,.45)}',
      '.cddl-gnode.cddl-island{border-style:dashed}',
      '.cddl-gnode.cddl-cls{background:var(--dsw-alias-bg-layer-1);border-width:1.5px}',
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
        var name = shortSymbol(node.anchor.symbol)
        if (byShort[name] === undefined) byShort[name] = []
        byShort[name].push(id)
      })
      var out = {}
      Object.keys(byShort).forEach(function (name) {
        var group = byShort[name]
        group.forEach(function (id) {
          out[id] = group.length === 1 ? name : graph.nodes[id].anchor.symbol
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
        var anchor = graph.nodes[id].anchor
        var chars = anchor.symbol.length
        if (chars > longest) longest = chars
        if (graph.nodes[id].memberList !== undefined) {
          graph.nodes[id].memberList.forEach(function (m) {
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
        var text = label[id] === undefined ? shortSymbol(node.anchor.symbol) : label[id]
        var badge = 46
        var chrome = 22 + 14 + 16
        // Keep one small readability gutter between the symbol and its badges;
        // exact text width left `dispatch_command` wrapping at the underscore.
        var own = Math.ceil(textWidth(text, SYMBOL_FONT)) + badge + chrome + 72
        var width = Math.max(150, Math.min(NODE_W, widthLimit || NODE_W, own))
        // Colliding names intentionally keep their fully-qualified symbol.
        // On a narrow vertical canvas the name wraps inside the card instead
        // of silently making the whole graph horizontally scrollable.
        var reserved = node.anchor.kind === 'class' || node.anchor.members > 0 ? 142 : 96
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
          h: node.members && node.memberList !== undefined
            ? CARD_BASE + MEMBERS_CHROME + node.memberList.length * MEMBER_ROW + MORE_ROW + wrapped
            : CARD_BASE + wrapped,
        }
      }
      return { PAD: PAD, BOX_GAP_X: BOX_GAP_X, BOX_GAP_Y: BOX_GAP_Y, BOX_PAD: BOX_PAD,
        BOX_HEAD: BOX_HEAD, BOX_W: BOX_W, BOX_COLS: BOX_COLS, NODE_W: NODE_W,
        INNER_GAP_X: INNER_GAP_X, INNER_GAP_Y: INNER_GAP_Y,
        PORT_STUB: PORT_STUB, ARROW_EVERY: ARROW_EVERY,
        PORT_CLEAR: PORT_CLEAR, LAYER_GAP_X: LAYER_GAP_X, COL_STRIDE: COL_STRIDE,
        LANE_STEP: LANE_STEP, WIRE_HOP: WIRE_HOP, CORRIDOR_MIN: CORRIDOR_MIN,
        SUBLANE_STEP: SUBLANE_STEP, HIT_PAD: HIT_PAD,
        canvasWidth: canvasWidth, sizeOf: sizeOf, label: label }
    }

    module.exports = { boxMetrics, textWidth, shortSymbol, labelsFor }
    return module.exports
  },
})

// dsh-cdd-lens — One grid of boxes, whatever the boxes are grouped by.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/grid',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * Boxes in rows, anchors down each box.
     *
     * The board drawing had this and the layered one did not: equal-width
     * boxes, as many across as the canvas allows, each row as tall as its
     * tallest box, a gutter between them for the traces. The layered drawing
     * packed its own way instead — blocks of varying width shelved left to
     * right — and the result was a field of cards at irregular spacing that
     * read as clutter no matter how well the wires were routed.
     *
     * So both now come through here. What differs between them is only what a
     * box means: one file, or one layer of one tree.
     *
     * @param graph - source of the node records.
     * @param groups - ordered [{ key, label, ids }]; one box each.
     * @param metrics - box metrics.
     * @returns placed anchors, the boxes around them, the row bands the
     *   gutters sit between, and how far down the drawing reaches.
     */
    function placeGroups(graph, groups, metrics) {
      var PAD = metrics.PAD
      var BOX_GAP_X = metrics.BOX_GAP_X
      var BOX_GAP_Y = metrics.BOX_GAP_Y
      var BOX_PAD = metrics.BOX_PAD
      var BOX_HEAD = metrics.BOX_HEAD
      var BOX_W = metrics.BOX_W
      var BOX_COLS = metrics.BOX_COLS
      var INNER_GAP_Y = metrics.INNER_GAP_Y
      var sizeOf = metrics.sizeOf

      var placed = []
      var boxes = []
      var rowBands = []
      var canvasY = PAD

      // Each box is as wide as the longest name it holds, and every anchor in
      // it is drawn to that width. Sized one by one they came out ragged: seven
      // different right edges in one box, and the exit badges that follow those
      // edges strung out in a zigzag instead of a column. Sized from the longest
      // name on the whole screen — which is what the board plugin does — a box
      // of short names is padded out to match some other box's longest.
      var innerOf = {}
      groups.forEach(function (group) {
        innerOf[group.key] = Math.max.apply(Math, group.ids.map(function (id) {
          return sizeOf(id).w
        }))
      })
      // Spaced by the widest box, so no box can reach into the next column
      // however long its own names are — and by that alone. Spreading the
      // columns to the full width of the canvas left two boxes marooned at
      // opposite edges with a screen of nothing between them; the gutter only
      // has to hold the exit badge of one column, the entry badge of the next,
      // and the wire that joins them, which is what LAYER_GAP_X measures.
      var widest = Math.max.apply(Math, groups.map(function (group) {
        return innerOf[group.key] + BOX_PAD * 2
      }))
      var stride = widest + metrics.LAYER_GAP_X

      for (var start = 0; start < groups.length; start += BOX_COLS) {
        var inRow = groups.slice(start, start + BOX_COLS)
        var layouts = inRow.map(function (group, col) {
          var inner = innerOf[group.key]
          // One anchor per row. Two columns made every box twice as wide, which
          // pushed the boxes apart, which made every wire longer — the width
          // was spent on emptiness and paid for in travel.
          var height = 0
          group.ids.forEach(function (id, i) {
            height += sizeOf(id, inner).h + (i === group.ids.length - 1 ? 0 : INNER_GAP_Y)
          })
          return {
            group: group, inner: inner,
            x: PAD + col * stride,
            w: inner + BOX_PAD * 2,
            h: BOX_HEAD + BOX_PAD + height + BOX_PAD,
          }
        })
        var rowHeight = Math.max.apply(Math, layouts.map(function (box) { return box.h }))
        layouts.forEach(function (box) {
          boxes.push({
            file: box.group.label, key: box.group.key,
            x: box.x, y: canvasY, w: box.w, h: box.h, count: box.group.ids.length,
          })
          var nodeY = canvasY + BOX_HEAD + BOX_PAD
          box.group.ids.forEach(function (id, localRow) {
            var size = sizeOf(id, box.inner)
            var node = graph.nodes[id]
            placed.push({
              id: id, node: node, anchor: node.anchor,
              x: box.x + BOX_PAD, y: nodeY, w: box.inner, h: size.h,
              rowIndex: start + localRow, innerRow: localRow,
              file: node.anchor.file, island: false,
              // Which frame this anchor belongs to, so the frame can follow it.
              boxKey: box.group.key,
              layer: node.layer, tree: node.tree,
              label: metrics.label[id],
            })
            nodeY += size.h + INNER_GAP_Y
          })
        })
        rowBands.push({ top: canvasY, bottom: canvasY + rowHeight })
        canvasY += rowHeight + BOX_GAP_Y
      }

      return { placed: placed, boxes: boxes, rowBands: rowBands, canvasY: canvasY }
    }

    module.exports = { placeGroups }
    return module.exports
  },
})

// dsh-cdd-lens — The board skin: what belongs in a box.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/skins/pcb/group',
  factory: (require) => {
    var module = { exports: {} }
    var __layout_grid = require('dsh-cdd-lens/layout/grid')
    var placeGroups = __layout_grid.placeGroups

    /**
     * One box per file, in the order the ranking put the files.
     *
     * The grid is shared with the layered skin; only this — what a box holds —
     * is the board skin's own. A file is the unit here because a trace between
     * two files is the thing worth seeing on a board.
     */
    function placeBoxes(graph, scope, metrics) {
      var byFile = scope.byFile
      var groups = scope.fileOrder.map(function (file) {
        return { key: file, label: file, ids: byFile[file] }
      })
      var laid = placeGroups(graph, groups, metrics)
      return {
        placed: laid.placed, fileBoxes: laid.boxes,
        rowBands: laid.rowBands, canvasY: laid.canvasY,
      }
    }

    module.exports = { placeBoxes }
    return module.exports
  },
})

// dsh-cdd-lens — The layered skin: what belongs in a box.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/skins/tiers/group',
  factory: (require) => {
    var module = { exports: {} }
    var __layout_grid = require('dsh-cdd-lens/layout/grid')
    var placeGroups = __layout_grid.placeGroups

    /**
     * Whether this drawing can be laid out by layer at all.
     *
     * `/chain` puts a layer on every node it reached. If it has not answered
     * yet, or answered for a different exploration than the one on screen, the
     * old file-box placement still has to be able to take over — a half-layered
     * picture would be worse than either.
     * @param graph - the graph being drawn.
     * @param included - the ids that will be drawn.
     * @returns true when every included node knows its layer.
     */
    function tiered(graph, included) {
      if (included.length === 0) return false
      return included.every(function (id) {
        var node = graph.nodes[id]
        return node !== undefined && typeof node.layer === 'number'
      })
    }

    /**
     * One vertical band per layer, trees stacked in the order `/chain` ranked
     * them.
     *
     * No file boxes. Grouping by file is what turned this view into the
     * directory listing next to it: a file is where an anchor is stored, not
     * what it has to do with anything else. The row an anchor sits in is its
     * distance from the thing that was edited, which is the question the
     * picture exists to answer.
     * @param graph - the graph being drawn.
     * @param scope - what is on screen.
     * @param metrics - box metrics for this canvas.
     * @returns placed nodes, the row bands wires travel between, the labelled
     *   rows, and how far down the drawing reaches.
     */
    function placeTiers(graph, scope, metrics) {
      var included = scope.included

      // One box per layer of one tree — the same grid the board drawing uses,
      // grouped by a different thing. Packing blocks of varying width onto
      // shelves instead gave irregular spacing that read as clutter however
      // well the wires were routed, so there is now one placement and two ways
      // of deciding what belongs in a box.
      var bands = {}
      var order = []
      included.forEach(function (id) {
        var node = graph.nodes[id]
        var tree = typeof node.tree === 'number' ? node.tree : 0
        var key = tree + ':' + node.layer
        if (bands[key] === undefined) {
          bands[key] = { tree: tree, layer: node.layer, ids: [] }
          order.push(key)
        }
        bands[key].ids.push(id)
      })
      order.sort(function (l, r) {
        return bands[l].tree - bands[r].tree || bands[l].layer - bands[r].layer
      })

      var groups = order.map(function (key) {
        var band = bands[key]
        // Anchors the session touched lead their box: they are why the rest of
        // it is on screen at all.
        band.ids.sort(function (l, r) {
          var ln = graph.nodes[l], rn = graph.nodes[r]
          return (ln.seed === true ? 0 : 1) - (rn.seed === true ? 0 : 1)
            || ln.anchor.symbol.localeCompare(rn.anchor.symbol)
        })
        return {
          key: key,
          label: 'T' + (band.tree + 1) + ' · L' + band.layer + ' · ' + band.ids.length,
          ids: band.ids,
        }
      })

      var laid = placeGroups(graph, groups, metrics)
      return {
        placed: laid.placed, fileBoxes: laid.boxes, rowBands: laid.rowBands,
        // The box header carries the layer's name, so there is no separate
        // row label to draw beside it any more.
        rows: [], canvasY: laid.canvasY,
      }
    }

    module.exports = { tiered, placeTiers }
    return module.exports
  },
})

// dsh-cdd-lens — The flow skin: one column per layer the index assigned.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/skins/flow/group',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * One column per layer, callers left of callees, with the corridor
     * between two columns reserved for the wires at placement time.
     *
     * The layer is not computed here. The host side derives it from the edge
     * tables — DFS finish order, then longest-path relaxation — and sends it
     * down on every node as `node.layer` (engine/fetch seats it there), which
     * is also what the tiers skin reads. Recomputing it client-side from the
     * edges that happen to be visible answered a different question: how the
     * drawing is wired, not how deep into the data a node sits.
     *
     * A node without a layer — or with no edge on screen at all, which is the
     * shape an island arrives in — shares one trailing column rather than
     * forcing the whole drawing to fall back. The corridor between two columns
     * is metrics.LAYER_GAP_X wide, reserved at placement time the way elk's
     * layered layout reserves it: room for an exit badge, an entry badge, and
     * the lanes between them. skins/flow/route is written against that
     * reservation.
     *
     * @param graph - the graph being drawn.
     * @param scope - what is on screen.
     * @param metrics - box metrics for this canvas.
     * @returns placed nodes, one labelled frame per column, and how far down
     *   the drawing reaches — the same shape the other two skins return.
     */
    function placeFlow(graph, scope, metrics) {
      var included = scope.included
      var PAD = metrics.PAD
      var NODE_W = metrics.NODE_W
      var LAYER_GAP_X = metrics.LAYER_GAP_X
      var BOX_PAD = metrics.BOX_PAD
      var BOX_HEAD = metrics.BOX_HEAD
      var INNER_GAP_Y = metrics.INNER_GAP_Y
      var sizeOf = metrics.sizeOf
      // A shallow margin above the columns so a wire crossing a column over
      // its first node has room that belongs to no node.
      var TOP_BAND = BOX_HEAD

      // Which nodes carry a layer at all — the same typeof check the layered
      // skin's `tiered` makes — and which of those the visible edges actually
      // touch. A node with neither goes to the trailing column.
      var includedSet = {}
      included.forEach(function (id) { includedSet[id] = true })
      var linked = {}
      graph.edges.forEach(function (edge) {
        if (includedSet[edge.from]) linked[edge.from] = true
        if (includedSet[edge.to]) linked[edge.to] = true
      })
      var seated = {}
      var maxLayer = -1
      included.forEach(function (id) {
        var node = graph.nodes[id]
        if (typeof node.layer !== 'number' || linked[id] !== true) return
        seated[id] = true
        if (node.layer > maxLayer) maxLayer = node.layer
      })
      var restLayer = maxLayer + 1
      var flowLayerOf = function (id) {
        return seated[id] === true ? graph.nodes[id].layer : restLayer
      }

      var byLayer = {}
      var columns = []
      included.forEach(function (id) {
        var L = flowLayerOf(id)
        if (byLayer[L] === undefined) { byLayer[L] = []; columns.push(L) }
        byLayer[L].push(id)
      })
      columns.sort(function (l, r) { return l - r })
      var colIndex = {}
      columns.forEach(function (L, i) { colIndex[L] = i })

      // One chain's nodes keep together: tree first, then the name. The
      // trailing column holds whatever the layering did not seat, in plain
      // symbol order — and stays in it; nothing routes to it, so ordering it
      // by wires would be noise.
      columns.forEach(function (L) {
        byLayer[L].sort(function (l, r) {
          var ln = graph.nodes[l]
          var rn = graph.nodes[r]
          var lt = L === restLayer ? 0 : (typeof ln.tree === 'number' ? ln.tree : 0)
          var rt = L === restLayer ? 0 : (typeof rn.tree === 'number' ? rn.tree : 0)
          return lt - rt || ln.anchor.symbol.localeCompare(rn.anchor.symbol)
        })
      })

      var size = {}
      included.forEach(function (id) { size[id] = sizeOf(id) })

      // ---- barycenter sweep -------------------------------------------------
      //
      // The order inside a column decides how often the wires cross: the
      // corridor router gives every wire its own lane, but a lane change still
      // costs a bend, and a fan of inverted pairs crosses however it is laned.
      // Which is to say the wiring has to participate in the placement — the
      // thing dagre and elk's layered layout both do and this column order did
      // not. So after the data order above, each column is re-sorted by where
      // its neighbours in the adjacent columns actually stand: a node sinks or
      // rises to the mean height of the anchors its edges lead to and come
      // from. A node with no edge into a neighbouring column, and any tie,
      // keeps the seat it had — the sweep may settle the picture, never
      // shuffle it.
      var adj = {}
      included.forEach(function (id) { adj[id] = [] })
      graph.edges.forEach(function (edge) {
        if (!includedSet[edge.from] || !includedSet[edge.to]) return
        if (Math.abs(colIndex[flowLayerOf(edge.from)] - colIndex[flowLayerOf(edge.to)]) !== 1) return
        adj[edge.from].push(edge.to)
        adj[edge.to].push(edge.from)
      })
      var yOf = {}
      var layColumn = function (ids) {
        var y = PAD + TOP_BAND
        ids.forEach(function (id) {
          yOf[id] = y
          y += size[id].h + INNER_GAP_Y
        })
      }
      columns.forEach(function (L) { layColumn(byLayer[L]) })
      var sweepColumn = function (L) {
        if (L === restLayer) return
        var keyed = byLayer[L].map(function (id, at) {
          var ns = adj[id]
          var key = yOf[id] + size[id].h / 2
          if (ns.length > 0) {
            var sum = 0
            ns.forEach(function (n) { sum += yOf[n] + size[n].h / 2 })
            key = sum / ns.length
          }
          return { id: id, key: key, at: at }
        })
        keyed.sort(function (l, r) { return l.key - r.key || l.at - r.at })
        byLayer[L] = keyed.map(function (k) { return k.id })
        layColumn(byLayer[L])
      }
      // One direction at a time, each column seated before the next is read.
      // Sweeping every column from one shared snapshot settles nothing: both
      // sides of a crossed fan flip together and the crossings survive the
      // flip. Left to right and back is one round; two rounds settle the fans
      // this drawing actually grows.
      var SWEEPS = 2
      for (var sweep = 0; sweep < SWEEPS; sweep += 1) {
        columns.forEach(sweepColumn)
        columns.slice().reverse().forEach(sweepColumn)
      }

      var placed = []
      var boxes = []
      var canvasY = PAD
      columns.forEach(function (L) {
        var ids = byLayer[L]
        var col = colIndex[L]
        var x = PAD + col * (NODE_W + LAYER_GAP_X)
        var y = PAD + TOP_BAND
        ids.forEach(function (id, row) {
          var node = graph.nodes[id]
          placed.push({
            id: id, node: node, anchor: node.anchor,
            // One width for every node, whatever its name measures at: equal
            // cells are what keep the corridors between the columns straight,
            // and the corridors are what the router promises are empty.
            x: x, y: y, w: NODE_W, h: size[id].h,
            rowIndex: row, innerRow: row,
            file: node.anchor.file, island: L === restLayer,
            // Which frame this anchor belongs to, so the frame can follow it.
            boxKey: 'L' + L,
            layer: node.layer, tree: node.tree,
            // The column this skin put it in. The router reads this rather
            // than the x coordinate, which a dragged node no longer agrees
            // with.
            flowLayer: L,
            label: metrics.label[id],
          })
          y += size[id].h + INNER_GAP_Y
        })
        boxes.push({
          file: L === restLayer ? '未入链 · ' + ids.length : 'L' + L + ' · ' + ids.length,
          key: 'L' + L,
          // Marked, so the canvas can draw a column guide rather than a box:
          // the flow frame is a reading aid, not a container.
          frame: 'flow',
          x: x - BOX_PAD, y: PAD + TOP_BAND - BOX_HEAD,
          w: NODE_W + BOX_PAD * 2,
          h: (y - INNER_GAP_Y) - (PAD + TOP_BAND) + BOX_HEAD + BOX_PAD,
          count: ids.length,
        })
        var bottom = y - INNER_GAP_Y + BOX_PAD
        if (bottom > canvasY) canvasY = bottom
      })

      // No rowBands: the channels this skin routes through run between the
      // columns, and layout/channels derives horizontal bands from rows this
      // drawing does not have.
      return { placed: placed, fileBoxes: boxes, rowBands: [], rows: [], canvasY: canvasY }
    }

    module.exports = { placeFlow }
    return module.exports
  },
})

// dsh-cdd-lens — Corridors between the boxes.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/channels',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * The gaps between box rows and columns, which is where wires travel.
     */
    function buildChannels(place, metrics) {
      var rowBands = place.rowBands
      var PAD = metrics.PAD
      var BOX_GAP_X = metrics.BOX_GAP_X
      var BOX_GAP_Y = metrics.BOX_GAP_Y
      var BOX_W = metrics.BOX_W
      var BOX_COLS = metrics.BOX_COLS

      // ---- channels --------------------------------------------------------
      //
      // A wire that cuts through a file box reads as if it connects to that
      // box's anchors. Measured on this graph, 57 of 123 segments crossed a box
      // they had nothing to do with — 46% of the drawing was lying about what
      // is related to what, and no amount of colour fixes that because the line
      // is genuinely on top of those nodes.
      //
      // So cross-box wires are confined to the gaps: a horizontal channel is the
      // space between two box rows, a vertical channel the space between two box
      // columns. A wire leaves its own box, travels only in channels, and enters
      // the target box. Inside a box you then see only that box's own wires.
      var hChannels = []
      for (var band = 0; band <= rowBands.length; band += 1) {
        if (band === 0) hChannels.push(rowBands.length === 0 ? PAD : rowBands[0].top - BOX_GAP_Y / 2)
        else hChannels.push(rowBands[band - 1].bottom + BOX_GAP_Y / 2)
      }
      var vChannels = []
      for (var col = 0; col <= BOX_COLS; col += 1) {
        vChannels.push(PAD + col * (BOX_W + BOX_GAP_X) - BOX_GAP_X / 2)
      }
      var nearest = function (list, value) {
        var best = list[0]
        for (var i = 1; i < list.length; i += 1) {
          if (Math.abs(list[i] - value) < Math.abs(best - value)) best = list[i]
        }
        return best
      }
      /**
       * Where a wire leaves a node sideways, and the node-free lane it lands in.
       *
       * The box's interior is two node columns with a gap between them and a
       * padding margin on each side; none of those three strips contains a
       * node, so a vertical run inside one of them cannot pass beneath an
       * anchor. The side is chosen by which way the wire is heading.
       */
      var innerLane = function (p, box, towards) {
        var leftward = towards < p.x + p.w / 2
        var port = leftward ? p.x : p.x + p.w
        var lane = leftward
          ? Math.max(box.x + 7, p.x - 10)
          : Math.min(box.x + box.w - 7, p.x + p.w + 10)
        return { port: port, lane: lane }
      }

      /** The channel just outside a box on the side facing `towards`. */
      var exitChannel = function (box, towards) {
        var below = towards > box.y + box.h / 2
        return nearest(hChannels, below ? box.y + box.h + BOX_GAP_Y / 2 : box.y - BOX_GAP_Y / 2)
      }

      return { hChannels: hChannels, vChannels: vChannels, nearest: nearest,
        innerLane: innerLane, exitChannel: exitChannel }
    }

    module.exports = { buildChannels }
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

    /**
     * Which relations get a wire: a trunk by default, the rest on demand.
     */
    function chooseEdges(graph, scope, orient) {
      var activeFocus = scope.activeFocus
      var byId = orient.byId

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
      var drawable = graph.edges.filter(function (e) {
        return byId[e.from] !== undefined && byId[e.to] !== undefined
          && (activeFocus !== null || e.always || graph.nodes[e.from].down || graph.nodes[e.to].up)
      })
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
      shared.wireStats = { drawn: chosen.length, hidden: hiddenCount, total: drawable.length }

      return { chosen: chosen, hiddenCount: hiddenCount }
    }

    module.exports = { chooseEdges }
    return module.exports
  },
})

// dsh-cdd-lens — Orthogonal routing through the channels.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/ortho',
  factory: (require) => {
    var module = { exports: {} }
    var __view_record = require('dsh-cdd-lens/view/record')
    var stateOf = __view_record.stateOf

    /**
     * Wires as a schematic: out of a box, along channels, into the target.
     */
    function routeOrtho(edges, orient, relationFilter, channels, metrics) {
      var chosen = edges.chosen
      var byId = orient.byId
      var boxOf = orient.boxOf
      var vChannels = channels.vChannels
      var nearest = channels.nearest
      var innerLane = channels.innerLane
      var exitChannel = channels.exitChannel

      // ---- wires, drawn the way a schematic is -----------------------------
      //
      // Five rules, all of them things a circuit diagram settled long ago:
      //
      //   * a wire never runs under a module — it uses the channels between
      //     boxes, so a line inside a box always belongs to that box;
      //   * two wires travelling the same corridor get their own lane, because
      //     drawn on top of each other they read as one wire;
      //   * a crossing is drawn as a hop, so "crosses" and "joins" stop looking
      //     the same;
      //   * a real junction gets a filled dot, for the same reason;
      //   * direction markers repeat along the path, because on a long wire with
      //     four bends a single arrowhead at the far end tells you nothing about
      //     the middle.
      //
      // Points are shared objects between neighbouring segments, so nudging a
      // segment into its lane simply lengthens or shortens the two segments it
      // joins — the polyline stays connected with no extra bookkeeping.
      //
      // One spacing for every skin: these used to be written here as pixels,
      // and the flow skin carried its own copy, so a type-size change would
      // have had to find them all. They live in layout/metrics now.
      var LANE_STEP = metrics.LANE_STEP
      var HOP = metrics.WIRE_HOP
      var CORRIDOR_MIN = metrics.CORRIDOR_MIN
      // One spacing for both skins. This module carried its own 68 while the
      // layered one used 84, so the same wire got a different arrow density
      // depending on which drawing you were looking at.
      var ARROW_EVERY = metrics.ARROW_EVERY

      var polylines = []
      chosen.forEach(function (e) {
        var a = byId[e.from]
        var b = byId[e.to]
        var types = e.types.filter(function (type) {
          return relationFilter === undefined || relationFilter[type] !== false
        })
        types.forEach(function (type) {
          var pts
          if (a.file === b.file && a.innerRow === b.innerRow) {
            // Neighbours on one row inside one box: a short dogleg, all of it
            // inside the box it belongs to.
            var forward = a.x <= b.x
            var sx = forward ? a.x + a.w : a.x
            var sy = a.y + a.h / 2
            var tx = forward ? b.x : b.x + b.w
            var ty = b.y + b.h / 2
            var midX = sx + (tx - sx) / 2
            pts = [{ x: sx, y: sy }, { x: midX, y: sy }, { x: midX, y: ty }, { x: tx, y: ty }]
          } else if (a.file === b.file && boxOf[a.file] !== undefined) {
            // Same file, different rows. With one anchor per row this is now the
            // common case, and routing it through the channels OUTSIDE the box
            // would send a wire out the bottom and back in the top of the very
            // box it never leaves. It travels in the box's own side lane, which
            // holds no anchors.
            var boxS = boxOf[a.file]
            var down = a.y < b.y
            var sideL = boxS.x + CORRIDOR_MIN
            var sideR = boxS.x + boxS.w - CORRIDOR_MIN
            // Prefer the side with more room from the node edges.
            var useLeft = (a.x - boxS.x) <= (boxS.x + boxS.w - (a.x + a.w))
            var lane = useLeft ? sideL : sideR
            var portA = useLeft ? a.x : a.x + a.w
            var portB = useLeft ? b.x : b.x + b.w
            pts = [
              { x: portA, y: a.y + a.h / 2 },
              { x: lane, y: a.y + a.h / 2 },
              { x: lane, y: b.y + b.h / 2 },
              { x: portB, y: b.y + b.h / 2 },
            ]
          } else {
            var boxA = boxOf[a.file]
            var boxB = boxOf[b.file]
            var downward = a.y < b.y
            var x1 = a.x + a.w / 2
            var y1 = downward ? a.y + a.h : a.y
            var x2 = b.x + b.w / 2
            var y2 = downward ? b.y : b.y + b.h
            if (boxA === undefined || boxB === undefined) {
              var mid = y1 + (y2 - y1) / 2
              pts = [{ x: x1, y: y1 }, { x: x1, y: mid }, { x: x2, y: mid }, { x: x2, y: y2 }]
            } else {
              // Leaving straight down from a node runs the wire through
              // whichever sibling sits below it in the same box — and the node
              // is painted on top, so the wire simply disappears under it. So a
              // wire leaves SIDEWAYS first, into the gap beside its column,
              // and only then travels vertically. Those inner gaps hold no
              // nodes, which is what makes them safe.
              var sideA = innerLane(a, boxA, b.x)
              var sideB = innerLane(b, boxB, a.x)
              var yOut = exitChannel(boxA, b.y)
              var yIn = exitChannel(boxB, a.y)
              var ayEdge = a.y + a.h / 2
              var byEdge = b.y + b.h / 2
              if (Math.abs(yOut - yIn) < 1) {
                pts = [
                  { x: sideA.port, y: ayEdge }, { x: sideA.lane, y: ayEdge },
                  { x: sideA.lane, y: yOut }, { x: sideB.lane, y: yOut },
                  { x: sideB.lane, y: byEdge }, { x: sideB.port, y: byEdge },
                ]
              } else {
                var lane = nearest(vChannels, (sideA.lane + sideB.lane) / 2)
                pts = [
                  { x: sideA.port, y: ayEdge }, { x: sideA.lane, y: ayEdge },
                  { x: sideA.lane, y: yOut }, { x: lane, y: yOut },
                  { x: lane, y: yIn }, { x: sideB.lane, y: yIn },
                  { x: sideB.lane, y: byEdge }, { x: sideB.port, y: byEdge },
                ]
              }
            }
          }
          polylines.push({
            id: e.from + '→' + e.to + ':' + type,
            type: type, pts: pts, fromFile: a.file, toFile: b.file,
            from: e.from, to: e.to,
            faded: stateOf(e.to) !== null && stateOf(e.to) !== undefined && !stateOf(e.to).remembered,
          })
        })
      })

      return { polylines: polylines, LANE_STEP: LANE_STEP, HOP: HOP, ARROW_EVERY: ARROW_EVERY }
    }

    module.exports = { routeOrtho }
    return module.exports
  },
})

// dsh-cdd-lens — Collapsing parallel departures into a trunk.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/bus',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * One trunk out of a node, branches off it.
     */
    function mergeBuses(route) {
      var polylines = route.polylines

      // ---- buses: one trunk out of a node, branches off it ------------------
      //
      // Forty-one wires each taking their own path put dozens of parallel lines
      // in the same narrow channel. Crossings were low — parallel lines do not
      // cross — and the picture was still unreadable, which is what made
      // crossing count the wrong measure: side by side and indistinguishable is
      // worse than crossing and traceable.
      //
      // A schematic answers this with a bus. Everything leaving one node in one
      // direction shares a single trunk, and each destination leaves it at its
      // own branch point, marked with a filled dot. N lines in a corridor become
      // one line plus N short stubs, and the dot says "this is where that one
      // goes" — a crossing, drawn as a hop, never means that.
      var busGroups = {}
      polylines.forEach(function (line) {
        if (line.pts.length < 5) return
        // Only the cross-box shape (port, lane, channel, …) can share a trunk;
        // the short in-box routes have nothing to pool.
        var key = [line.from,line.type,line.pts[0].x,line.pts[0].y,line.pts[1].x,
          line.pts[2].y > line.pts[0].y ? 'down' : 'up'].join('|')
        ;(busGroups[key] = busGroups[key] || []).push(line)
      })
      Object.keys(busGroups).forEach(function (key) {
        var members = busGroups[key]
        if (members.length < 2) return
        // Every member already leaves through the same port and side lane; the
        // trunk is that lane, run to the farthest branch.
        var laneX = members[0].pts[1].x
        var startY = members[0].pts[0].y
        var branches = members.map(function (line) {
          return { line: line, y: line.pts[2].y }
        }).sort(function (l, r) {
          return Math.abs(l.y - startY) - Math.abs(r.y - startY)
        })
        branches.forEach(function (branch) {
          var line = branch.line
          // Redraw as: stay on the trunk to my own branch point, then leave.
          var tail = line.pts.slice(3)
          line.pts = [
            { x: line.pts[0].x, y: startY },
            { x: laneX, y: startY },
            { x: laneX, y: branch.y },
          ].concat(tail)
          // Remember WHERE in the polyline the branch is, not the coordinates
          // it had at this moment. Lane assignment runs after this and nudges
          // the points; a captured pair of numbers then marks the spot the wire
          // used to be, which is how four of these dots ended up floating in
          // empty canvas.
          line.branchIndex = 2
          line.busKey = key
        })
      })

    }

    module.exports = { mergeBuses }
    return module.exports
  },
})

// dsh-cdd-lens — Separating segments that would otherwise overlap.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/lanes',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * Co-routed segments get their own track.
     */
    function spreadLanes(route, metrics) {
      var polylines = route.polylines
      var LANE_STEP = route.LANE_STEP
      var BOX_GAP_X = metrics.BOX_GAP_X
      var BOX_GAP_Y = metrics.BOX_GAP_Y

      // ---- lanes: co-routed segments get their own track -------------------
      var hGroups = {}
      var vGroups = {}
      polylines.forEach(function (line) {
        for (var i = 1; i < line.pts.length; i += 1) {
          var p = line.pts[i - 1]
          var q = line.pts[i]
          // Only interior segments may move; the first and last touch a node.
          if (i - 1 === 0 || i === line.pts.length - 1) continue
          // The run down a shared trunk is the ONE segment that must stay
          // exactly where its siblings are. Laning treats those overlapping
          // runs as co-routed wires and pushes each into its own track, which
          // is how a bus of four became four parallel lines a few pixels
          // apart, and how every branch point stopped being a place where
          // anything actually met.
          if (line.branchIndex !== undefined && i === line.branchIndex) continue
          // A zero-length segment satisfies BOTH tests. Classified as
          // horizontal it gets nudged into a lane, which drags a point off the
          // line and collapses the dogleg — two identical points and a wire
          // that no longer meets its own node.
          if (Math.abs(p.x - q.x) < 0.5 && Math.abs(p.y - q.y) < 0.5) continue
          if (Math.abs(p.y - q.y) < 0.5) {
            var hk = String(Math.round(p.y))
            ;(hGroups[hk] = hGroups[hk] || []).push({ p: p, q: q })
          } else if (Math.abs(p.x - q.x) < 0.5) {
            var vk = String(Math.round(p.x))
            ;(vGroups[vk] = vGroups[vk] || []).push({ p: p, q: q })
          }
        }
      })
      var spread = function (groups, axis, budget) {
        Object.keys(groups).forEach(function (key) {
          var list = groups[key]
          if (list.length < 2) return
          // Order by where each segment starts so neighbouring lanes belong to
          // wires heading the same way; interleaving them would add crossings.
          list.sort(function (l, r) {
            return (axis === 'y' ? Math.min(l.p.x, l.q.x) - Math.min(r.p.x, r.q.x)
              : Math.min(l.p.y, l.q.y) - Math.min(r.p.y, r.q.y))
          })
          var step = Math.min(LANE_STEP, budget / Math.max(1, list.length - 1))
          list.forEach(function (seg, i) {
            var off = (i - (list.length - 1) / 2) * step
            seg.p[axis] += off
            seg.q[axis] += off
          })
        })
      }
      spread(hGroups, 'y', Math.max(10, BOX_GAP_Y - 14))
      spread(vGroups, 'x', Math.max(10, BOX_GAP_X - 14))

    }

    module.exports = { spreadLanes }
    return module.exports
  },
})

// dsh-cdd-lens — Where one wire crosses another.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/hops',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * A crossing is not a join.
     */
    function markHops(route) {
      var polylines = route.polylines
      var HOP = route.HOP

      // ---- hops: a crossing is not a join ----------------------------------
      var hSegs = []
      var vSegs = []
      polylines.forEach(function (line) {
        if (line.status === 'blocked') return
        for (var i = 1; i < line.pts.length; i += 1) {
          var p = line.pts[i - 1]
          var q = line.pts[i]
          if (Math.abs(p.x - q.x) < 0.5 && Math.abs(p.y - q.y) < 0.5) continue
          if (Math.abs(p.y - q.y) < 0.5) hSegs.push({ line: line, p: p, q: q })
          else if (Math.abs(p.x - q.x) < 0.5) vSegs.push({ line: line, p: p, q: q })
        }
      })
      // Horizontal wires hop over vertical ones — one convention, applied
      // everywhere, so a hop always means the same thing.
      //
      // Only the verticals whose x falls inside this run are candidates, so the
      // verticals are sorted by x once and each run walks the slice it spans.
      // Comparing every horizontal against every vertical is the same count of
      // comparisons as wires squared, which at a thousand anchors was almost
      // half a second — on a layout that reruns on zoom and selection.
      var sorted = vSegs.slice().sort(function (l, r) { return l.p.x - r.p.x })
      var startAt = function (x) {
        var lo = 0
        var hi = sorted.length
        while (lo < hi) {
          var mid = (lo + hi) >> 1
          if (sorted[mid].p.x < x) lo = mid + 1
          else hi = mid
        }
        return lo
      }
      hSegs.forEach(function (h) {
        var y = h.p.y
        var lo = Math.min(h.p.x, h.q.x)
        var hi = Math.max(h.p.x, h.q.x)
        var xs = []
        for (var i = startAt(lo + HOP); i < sorted.length; i += 1) {
          var v = sorted[i]
          var x = v.p.x
          if (x >= hi - HOP) break
          if (v.line === h.line || (h.line.busKey && h.line.busKey === v.line.busKey)) continue
          var y0 = Math.min(v.p.y, v.q.y)
          var y1 = Math.max(v.p.y, v.q.y)
          if (y > y0 + 0.5 && y < y1 - 0.5) xs.push(x)
        }
        // Merge overlapping hop intervals, including repeated crossings at x.
        var spans = []
        xs.forEach(function (x) {
          var last = spans[spans.length - 1]
          if (last && x - HOP <= last.hi) last.hi = Math.max(last.hi, x + HOP)
          else spans.push({ lo:x-HOP, hi:x+HOP, y:y, radius:HOP })
        })
        spans.forEach(function (span) {
          var obstacles = route.obstacles || []
          var collides = function (up) {
            var top = up ? y-HOP : y, bottom = up ? y : y+HOP
            return obstacles.some(function (b) {
              return b.x < span.hi && b.x+b.w > span.lo && b.y < bottom && b.y+b.h > top
            })
          }
          span.up = !collides(true)
          span.gap = !span.up && collides(false)
        })
        h.hops = spans
      })

      return { hSegs: hSegs, vSegs: vSegs }
    }

    module.exports = { markHops }
    return module.exports
  },
})

// All skins emit from final geometry. No stage repairs SVG strings afterwards.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/emit',
  factory: (require) => {
    var geometry = require('dsh-cdd-lens/routing/geometry')
    function emitWires(route,hops) {
      var wires=[],labels=[],junctions=[],arrows=[],segments=new Map()
      hops.hSegs.forEach(function (s) { segments.set(s.p,s) })
      route.polylines.forEach(function (line) {
        var pts=line.pts
        if (line.status==='blocked' || pts.length<2) return
        var minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity
        var see=function (x,y) { minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y) }
        pts.forEach(function (p) { see(p.x,p.y) })
        var d='M'+pts[0].x+','+pts[0].y,arcs=[]
        for (var i=1;i<pts.length;i++) {
          var p=pts[i-1],q=pts[i],seg=segments.get(p)
          if (seg && seg.q===q && seg.hops.length) {
            var forward=q.x>p.x,order=forward?seg.hops:seg.hops.slice().reverse()
            order.forEach(function (span) {
              var before=forward?span.lo:span.hi,after=forward?span.hi:span.lo
              d+=' L'+before+','+p.y
              if (span.gap) d+=' M'+after+','+p.y
              else {
                var rx=(span.hi-span.lo)/2,ry=span.radius
                d+=' A'+rx+','+ry+' 0 0 '+((forward===span.up)?1:0)+' '+after+','+p.y
                see(span.lo,p.y+(span.up?-ry:ry));see(span.hi,p.y)
              }
              arcs.push(span)
            })
          }
          d+=' L'+q.x+','+q.y
        }
        wires.push({ id:line.id,d:d,type:line.type,faded:line.faded,from:line.from,to:line.to,
          fromFile:line.fromFile,toFile:line.toFile,pts:pts,arcs:arcs,
          sourcePort:line.sourcePort,targetPort:line.targetPort,
          bounds:{minX:minX,minY:minY,maxX:maxX,maxY:maxY} })
        var total=geometry.length(pts),every=route.ARROW_EVERY,distances=[]
        // Keep the final head off the port badge, and always give short wires a head.
        for (var t=every*0.55;t<total;t+=every) distances.push(t)
        if (!distances.length) distances.push(total/2)
        distances.forEach(function (distance,j) {
          var at=geometry.atDistance(pts,distance)
          if (arcs.some(function (arc) { return Math.abs(at.y-arc.y)<0.5 && at.x>=arc.lo-2 && at.x<=arc.hi+2 })) return
          arrows.push({ id:line.id+':head'+j,from:line.from,to:line.to,type:line.type,
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

// dsh-cdd-lens — Bezier wires for dataflow and dependency edges.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/curve',
  factory: (require) => {
    var module = { exports: {} }
    var __view_record = require('dsh-cdd-lens/view/record')
    var stateOf = __view_record.stateOf

    /**
     * Soft curves for the relations the orthogonal router does not carry.
     */
    function emitCurves(edges, orient, relationFilter, drawn) {
      var chosen = edges.chosen
      var byId = orient.byId
      var wires = drawn.wires
      var arrows = drawn.arrows

      var cubicPoint = function (p0, p1, p2, p3, t) {
        var u = 1 - t
        return {
          x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
          y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y,
        }
      }
      var cubicAngle = function (p0, p1, p2, p3, t) {
        var u = 1 - t
        var dx = 3 * u * u * (p1.x - p0.x) + 6 * u * t * (p2.x - p1.x) + 3 * t * t * (p3.x - p2.x)
        var dy = 3 * u * u * (p1.y - p0.y) + 6 * u * t * (p2.y - p1.y) + 3 * t * t * (p3.y - p2.y)
        return Math.atan2(dy, dx) * 180 / Math.PI
      }
      chosen.forEach(function (edge) {
        var from = byId[edge.from]
        var to = byId[edge.to]
        ;(edge.types || ['call']).filter(function (type) {
          return relationFilter === undefined || relationFilter[type] !== false
        }).forEach(function (type) {
          var isData = type === 'dataflow'
          var yOffset = isData ? 6 : -6
          var fromRight = from.flowDir !== 'rtl'
          var toEntryRight = to.flowDir === 'rtl'
          var p0 = { x: fromRight ? from.x + from.w : from.x, y: from.y + from.h / 2 + yOffset }
          var p3 = { x: toEntryRight ? to.x + to.w : to.x, y: to.y + to.h / 2 + yOffset }
          var bend = Math.max(52, Math.abs(p3.y - p0.y) * .20, Math.abs(p3.x - p0.x) * .22)
          var p1 = { x: p0.x + (fromRight ? bend : -bend), y: p0.y }
          var p2 = { x: p3.x + (toEntryRight ? bend : -bend), y: p3.y }
          var id = edge.from + '→' + edge.to + ':' + type
          var faded = stateOf(edge.to) !== null && stateOf(edge.to) !== undefined && !stateOf(edge.to).remembered
          wires.push({
            id: id,
            d: 'M' + p0.x + ',' + p0.y + ' C' + p1.x + ',' + p1.y + ' ' + p2.x + ',' + p2.y + ' ' + p3.x + ',' + p3.y,
            type: type, faded: faded,
            fromFile: from.file, toFile: to.file,
            from: edge.from, to: edge.to,
          })
          var at = cubicPoint(p0, p1, p2, p3, .78)
          arrows.push({
            id: id + ':arrow', from: edge.from, to: edge.to,
            x: at.x, y: at.y, angle: cubicAngle(p0, p1, p2, p3, .78),
            type: type, faded: faded,
          })
        })
      })

    }

    module.exports = { emitCurves }
    return module.exports
  },
})

// dsh-cdd-lens — Rerouting the runs that cut through a box.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/avoid',
  factory: (require) => {
    var geometry = require('dsh-cdd-lens/routing/geometry')

    // Boundary contact is allowed; entering ANY card interior is not.
    // Endpoints lie on the boundary and need no whole-node exemption.
    var TOUCH_SLACK = 0

    /** Every drawn box, so a run can be tested against all of them. */
    function boxesOf(orient) {
      var byId = orient.byId
      return Object.keys(byId).map(function (id) { return byId[id] })
    }

    /**
     * Boxes bucketed by position, so a segment asks about its own neighbourhood.
     *
     * Testing every segment against every box is fine at forty anchors and half
     * a second at a thousand: the count of comparisons is segments times boxes,
     * and both grow with the graph. A run only ever passes near a handful of
     * boxes, and the grid layout means those are easy to find.
     */
    function boxIndex(boxes) {
      var CELL = 256
      var cells = {}
      var key = function (cx, cy) { return cx + ':' + cy }
      boxes.forEach(function (r) {
        var x0 = Math.floor(r.x / CELL), x1 = Math.floor((r.x + r.w) / CELL)
        var y0 = Math.floor(r.y / CELL), y1 = Math.floor((r.y + r.h) / CELL)
        for (var cx = x0; cx <= x1; cx += 1) {
          for (var cy = y0; cy <= y1; cy += 1) {
            var k = key(cx, cy)
            if (cells[k] === undefined) cells[k] = []
            cells[k].push(r)
          }
        }
      })
      return {
        near: function (p, q, out) {
          out.length = 0
          var seen = {}
          var x0 = Math.floor(Math.min(p.x, q.x) / CELL), x1 = Math.floor(Math.max(p.x, q.x) / CELL)
          var y0 = Math.floor(Math.min(p.y, q.y) / CELL), y1 = Math.floor(Math.max(p.y, q.y) / CELL)
          for (var cx = x0; cx <= x1; cx += 1) {
            for (var cy = y0; cy <= y1; cy += 1) {
              var list = cells[key(cx, cy)]
              if (list === undefined) continue
              for (var i = 0; i < list.length; i += 1) {
                var r = list[i]
                if (seen[r.id] === true) continue
                seen[r.id] = true
                out.push(r)
              }
            }
          }
          return out
        },
      }
    }

    /** Test every segment, including internal runs through its own endpoints. */
    function blockedBy(pts, boxes, fromId, toId, index) {
      var scratch = []
      for (var i = 1; i < pts.length; i += 1) {
        var p = pts[i - 1]
        var q = pts[i]
        var near = index === undefined ? boxes : index.near(p, q, scratch)
        for (var k = 0; k < near.length; k += 1) {
          var r = near[k]
          var x1 = r.x + TOUCH_SLACK, y1 = r.y + TOUCH_SLACK
          var x2 = r.x + r.w - TOUCH_SLACK, y2 = r.y + r.h - TOUCH_SLACK
          if (x2 <= x1 || y2 <= y1) continue
          if ((p.x > x1 && p.x < x2 && p.y > y1 && p.y < y2)
            || (q.x > x1 && q.x < x2 && q.y > y1 && q.y < y2)) return true
          if (Math.abs(p.y - q.y) < .5) {
            if (p.y > y1 && p.y < y2
              && Math.max(p.x, q.x) > x1 && Math.min(p.x, q.x) < x2) return true
          } else if (Math.abs(p.x - q.x) < .5) {
            if (p.x > x1 && p.x < x2
              && Math.max(p.y, q.y) > y1 && Math.min(p.y, q.y) < y2) return true
          }
        }
      }
      return false
    }

    // A* over a coordinate-compressed orthogonal visibility grid. The queue is
    // lazy: only reached grid points and their four neighbours are evaluated.
    function searchPath(starts, ends, boxes, stub, index, preferred) {
      var clearance = stub / 2
      var xs = [], ys = []
      starts.concat(ends).forEach(function (p) { xs.push(p.exit.x); ys.push(p.exit.y) })
      boxes.forEach(function (b) { xs.push(b.x-clearance,b.x+b.w+clearance); ys.push(b.y-clearance,b.y+b.h+clearance) })
      xs = Array.from(new Set(xs)).sort(function (a,b) { return a-b })
      ys = Array.from(new Set(ys)).sort(function (a,b) { return a-b })
      var nx = xs.length, xids = new Map(), yids = new Map()
      xs.forEach(function (x,i) { xids.set(x,i) }); ys.forEach(function (y,i) { yids.set(y,i) })
      var idOf = function (p) { return yids.get(p.y)*nx+xids.get(p.x) }
      var pointOf = function (id) { return { x:xs[id%nx],y:ys[Math.floor(id/nx)] } }
      var targets = new Map()
      ends.forEach(function (p) { targets.set(idOf(p.exit),p) })
      var heap = [], best = new Map(), previous = new Map(), origins = new Map(), links = new Map()
      var push = function (item) {
        heap.push(item)
        var i = heap.length-1
        while (i>0) { var j=(i-1)>>1; if (heap[j].f<=item.f) break; heap[i]=heap[j]; i=j }
        heap[i]=item
      }
      var pop = function () {
        var first=heap[0],last=heap.pop()
        if (heap.length) {
          var i=0
          while (i*2+1<heap.length) {
            var c=i*2+1
            if (c+1<heap.length && heap[c+1].f<heap[c].f) c++
            if (heap[c].f>=last.f) break
            heap[i]=heap[c];i=c
          }
          heap[i]=last
        }
        return first
      }
      var estimate = function (p) {
        var result=Infinity
        ends.forEach(function (t) { result=Math.min(result,Math.abs(t.exit.x-p.x)+Math.abs(t.exit.y-p.y)) })
        return result
      }
      starts.forEach(function (p) {
        var id=idOf(p.exit),dir=p.side==='left'||p.side==='right'?1:2,key=id*3+dir
        var g=stub+(preferred && p.side!==preferred[0]?stub:0)
        if (best.has(key) && best.get(key)<=g) return
        best.set(key,g);origins.set(key,p);push({key:key,id:id,dir:dir,g:g,f:g+estimate(p.exit)})
      })
      var winner=null,winCost=Infinity
      while (heap.length) {
        var state=pop()
        if (state.f>=winCost) break
        if (best.get(state.key)!==state.g) continue
        var p=pointOf(state.id),target=targets.get(state.id)
        if (target) {
          var endDir=target.side==='left'||target.side==='right'?1:2
          var total=state.g+stub+(endDir!==state.dir?stub:0)+(preferred && target.side!==preferred[1]?stub:0)
          if (total<winCost) { winCost=total;winner={state:state,target:target} }
        }
        var xi=state.id%nx,yi=Math.floor(state.id/nx)
        ;[[xi-1,yi,1],[xi+1,yi,1],[xi,yi-1,2],[xi,yi+1,2]].forEach(function (next) {
          if (next[0]<0 || next[0]>=nx || next[1]<0 || next[1]>=ys.length) return
          var id=next[1]*nx+next[0],q=pointOf(id)
          var link=Math.min(id,state.id)+':'+Math.max(id,state.id)
          if (!links.has(link)) links.set(link,!blockedBy([p,q],boxes,null,null,index))
          if (!links.get(link)) return
          var g=state.g+Math.abs(q.x-p.x)+Math.abs(q.y-p.y)+(state.dir!==next[2]?stub:0)
          var key=id*3+next[2]
          if (best.has(key) && best.get(key)<=g) return
          best.set(key,g);previous.set(key,state.key);origins.set(key,origins.get(state.key))
          push({key:key,id:id,dir:next[2],g:g,f:g+estimate(q)})
        })
      }
      if (!winner) return null
      var key=winner.state.key,reverse=[]
      var origin=origins.get(key)
      while (key!==undefined) { reverse.push(pointOf(Math.floor(key/3)));key=previous.get(key) }
      return geometry.compact([origin.point].concat(reverse.reverse(),[winner.target.point]))
    }

    /** Search local obstacles first; expand only if the local route is blocked. */
    function clearPath(a,b,boxes,stub,fromId,toId,index,preferred) {
      index=index || boxIndex(boxes)
      var sides=['right','left','bottom','top']
      var ports=function (node) {
        return sides.map(function (side) { return geometry.portAt(node,side,stub) })
          .filter(function (p) { return !blockedBy([p.point,p.exit],boxes,null,null,index) })
      }
      var starts=ports(a),ends=ports(b)
      if (!starts.length || !ends.length) return null
      // All simple doglegs compete by length and turns before searching a grid.
      var best=null,cost=Infinity
      starts.forEach(function (s) { ends.forEach(function (t) {
        ;[[s.exit,{x:t.exit.x,y:s.exit.y},t.exit],
          [s.exit,{x:s.exit.x,y:t.exit.y},t.exit]].forEach(function (middle) {
          var candidate=geometry.compact([s.point].concat(middle,[t.point]))
          var n=geometry.length(candidate)+stub*Math.max(0,candidate.length-2)
            +(preferred && s.side!==preferred[0]?stub:0)+(preferred && t.side!==preferred[1]?stub:0)
          if (n<cost && !blockedBy(candidate,boxes,fromId,toId,index)) { cost=n;best=candidate }
        })
      }) })
      if (best) return best
      var margin=stub*4
      for (;;) {
        var local=boxes.filter(function (r) {
          return r.x+r.w>=Math.min(a.x,b.x)-margin && r.x<=Math.max(a.x+a.w,b.x+b.w)+margin
            && r.y+r.h>=Math.min(a.y,b.y)-margin && r.y<=Math.max(a.y+a.h,b.y+b.h)+margin
        })
        var result=searchPath(starts,ends,local,stub,boxIndex(local),preferred)
        if (result && !blockedBy(result,boxes,fromId,toId,index)) return result
        if (local.length===boxes.length) return null
        margin*=2
      }
    }

    /** Repair the source of truth BEFORE hops, decorations and SVG emission. */
    function repairCrossings(route,orient,metrics) {
      var boxes=boxesOf(orient),index=boxIndex(boxes),fixed=0
      route.obstacles=boxes
      route.unrouted=[]
      var reuse=new Map()
      route.polylines.forEach(function (line) {
        line.pts=geometry.compact(line.pts)
        var a=orient.byId[line.from],b=orient.byId[line.to]
        if (!a || !b) { line.status='blocked';route.unrouted.push(line);return }
        if (line.pts.length>=2 && !blockedBy(line.pts,boxes,line.from,line.to,index)) { line.status='routed';return }
        var key=line.from+'→'+line.to
        var preferred=line.pts.length ? [geometry.sideOf(a,line.pts[0]),geometry.sideOf(b,line.pts[line.pts.length-1])] : ['right','left']
        if (!reuse.has(key)) reuse.set(key,clearPath(a,b,boxes,metrics.PORT_STUB,line.from,line.to,index,preferred))
        var found=reuse.get(key)
        if (!found) { line.status='blocked';line.pts=[];route.unrouted.push(line);return }
        line.pts=found.map(function (p) { return {x:p.x,y:p.y} })
        line.status='routed';delete line.branchIndex;delete line.busKey;fixed++
      })
      geometry.bindPorts(route,orient)
      return fixed
    }
    return { boxesOf,boxIndex,blockedBy,searchPath,clearPath,repairCrossings }
  },
})

// dsh-cdd-lens — The board skin: traces, buses and the hops where they cross.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/skins/pcb/route',
  factory: (require) => {
    var module = { exports: {} }
    var __routing_ortho = require('dsh-cdd-lens/routing/ortho')
    var routeOrtho = __routing_ortho.routeOrtho
    var __routing_bus = require('dsh-cdd-lens/routing/bus')
    var mergeBuses = __routing_bus.mergeBuses
    var __routing_lanes = require('dsh-cdd-lens/routing/lanes')
    var spreadLanes = __routing_lanes.spreadLanes
    var __routing_hops = require('dsh-cdd-lens/routing/hops')
    var markHops = __routing_hops.markHops
    var __routing_emit = require('dsh-cdd-lens/routing/emit')
    var emitWires = __routing_emit.emitWires
    var __routing_avoid = require('dsh-cdd-lens/routing/avoid')
    var repairCrossings = __routing_avoid.repairCrossings

    /**
     * The whole board pipeline, in one place instead of spelled out by the
     * orchestrator: route in the channels, merge what shares a run into a bus,
     * give each its own lane, mark the crossings as hops rather than joins,
     * and re-route whatever still cuts through a box.
     *
     * The polylines are handed back as well: a shift of the drawing translates
     * them and re-emits, without routing again.
     */
    function routeBoard(edges, orient, relationFilter, metrics, channels) {
      var route = routeOrtho(edges, orient, relationFilter, channels, metrics)
      mergeBuses(route)
      spreadLanes(route, metrics, orient)
      repairCrossings(route, orient, metrics)
      var hops = markHops(route)
      var drawn = emitWires(route, hops)
      return { route: route, drawn: drawn }
    }

    /** Same traces at a new origin: the polylines have already been moved. */
    function reemitBoard(route, orient, metrics) {
      var drawn = emitWires(route, markHops(route))
      return drawn
    }

    module.exports = { routeBoard, reemitBoard }
    return module.exports
  },
})

// dsh-cdd-lens — The layered skin: how a wire gets from box to box.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/skins/tiers/route',
  factory: (require) => {
    var module = { exports: {} }
    var repairCrossings = require('dsh-cdd-lens/routing/avoid').repairCrossings
    var emitWires = require('dsh-cdd-lens/routing/emit').emitWires
    var markHops = require('dsh-cdd-lens/routing/hops').markHops

    /**
     * Route the chosen relations through the gaps between layers.
     *
     * A curve drawn straight from one node's edge to another's crosses whatever
     * stands between them, which on a layered drawing is every node in every
     * layer it spans. A wire here leaves the bottom of its source, drops into
     * the gap below that layer, runs sideways there, and comes down into the top
     * of its target — so the only place a wire is ever horizontal is a gap where
     * nothing is standing.
     *
     * Wires sharing a gap get their own height in it, ordered by where they are
     * going, so parallel departures do not lie on top of each other.
     * @param edges - the relations to draw, from routing/select.
     * @param orient - byId, the placed node for every id.
     * @param relationFilter - relation kinds the viewer left switched on.
     * @param metrics - box metrics; its BOX_GAP_Y is the room between layers.
     * @returns wires, arrowheads and labels, ready to draw.
     */
    function routeTiers(edges, orient, relationFilter, metrics) {
      var byId = orient.byId
      var live = []
      edges.chosen.forEach(function (edge) {
        var a = byId[edge.from]
        var b = byId[edge.to]
        if (a === undefined || b === undefined) return
        var types = (edge.types || []).filter(function (type) {
          return relationFilter === undefined || relationFilter[type] !== false
        })
        types.forEach(function (type) {
          live.push({ edge: edge, type: type, a: a, b: b })
        })
      })

      // Calls read left to right: a wire leaves the caller's right edge and
      // arrives at the callee's left edge. The only place it may travel
      // vertically is the corridor between two layers, so it never runs
      // through a column it has no business in.
      //
      // Everything crossing the same corridor shares it, so each wire gets its
      // own vertical line inside it rather than all of them stacking on the
      // middle.
      var lanes = {}
      live.forEach(function (w) {
        var key = Math.round(w.a.x + w.a.w) + ':' + Math.round(w.b.x)
        if (lanes[key] === undefined) lanes[key] = []
        lanes[key].push(w)
      })
      Object.keys(lanes).forEach(function (key) {
        var list = lanes[key]
        list.sort(function (l, r) { return (l.b.y + l.b.h / 2) - (r.b.y + r.b.h / 2) })
        var left = Number(key.split(':')[0])
        var right = Number(key.split(':')[1])
        var room = Math.max(metrics.LANE_STEP, right - left - metrics.CORRIDOR_MIN)
        var step = room / (list.length + 1)
        list.forEach(function (w, i) { w.mid = left + step * (i + 1) })
      })

      var STUB = metrics.PORT_STUB
      var polylines = []
      live.forEach(function (w) {
        var a = w.a
        var b = w.b
        var forward = b.x > a.x + a.w
        var pts
        if (forward) {
          var y1 = a.y + a.h / 2
          var y2 = b.y + b.h / 2
          var x1 = a.x + a.w
          var x2 = b.x
          // Straight out of the exit port, straight into the entry port, and
          // only the corridor between the two columns in between.
          var mid = w.mid === undefined ? x1 + (x2 - x1) / 2 : w.mid
          mid = Math.min(Math.max(mid, x1 + STUB), x2 - STUB)
          pts = [
            { x: x1, y: y1 }, { x: mid, y: y1 },
            { x: mid, y: y2 }, { x: x2, y: y2 },
          ]
        } else {
          // Backwards or sideways: down out of the source, along under both, up
          // into the target. It never crosses a column because it never enters
          // one.
          var below = Math.max(a.y + a.h, b.y + b.h) + STUB * 2
          var ax = a.x + a.w / 2
          var bx = b.x + b.w / 2
          pts = [
            { x: ax, y: a.y + a.h }, { x: ax, y: below },
            { x: bx, y: below }, { x: bx, y: b.y + b.h },
          ]
        }
        polylines.push({id:w.edge.from+'→'+w.edge.to+':'+w.type,
          from:w.edge.from,to:w.edge.to,type:w.type,pts:pts,
          fromFile:a.file,toFile:b.file,faded:w.edge.faded===true})
      })
      var route = {polylines:polylines,LANE_STEP:metrics.LANE_STEP,HOP:metrics.WIRE_HOP,ARROW_EVERY:metrics.ARROW_EVERY}
      repairCrossings(route,orient,metrics)
      var drawn = emitWires(route,markHops(route))
      drawn.route = route
      return drawn
    }

    module.exports = { routeTiers }
    return module.exports
  },
})

// dsh-cdd-lens — The flow skin: wires that live in the corridors the columns reserved.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/skins/flow/route',
  factory: (require) => {
    var module = { exports: {} }
    var __routing_hops = require('dsh-cdd-lens/routing/hops')
    var markHops = __routing_hops.markHops
    var __routing_emit = require('dsh-cdd-lens/routing/emit')
    var emitWires = __routing_emit.emitWires
    var __routing_avoid = require('dsh-cdd-lens/routing/avoid')
    var repairCrossings = __routing_avoid.repairCrossings
    var __view_record = require('dsh-cdd-lens/view/record')
    var stateOf = __view_record.stateOf

    /**
     * The column geometry the placement produced, rebuilt from the placed
     * nodes. Columns are keyed by the flowLayer the placement stamped on each
     * node, not by x coordinate: a node the user dragged keeps its layer even
     * where its position no longer agrees with it.
     */
    function columnsOf(orient) {
      var byId = orient.byId
      var byLayer = {}
      var order = []
      Object.keys(byId).forEach(function (id) {
        var p = byId[id]
        var L = typeof p.flowLayer === 'number' ? p.flowLayer : 0
        if (byLayer[L] === undefined) { byLayer[L] = []; order.push(L) }
        byLayer[L].push(p)
      })
      order.sort(function (l, r) { return l - r })
      var index = {}
      var left = []
      var right = []
      var members = []
      order.forEach(function (L, i) {
        index[L] = i
        left[i] = Math.min.apply(Math, byLayer[L].map(function (p) { return p.x }))
        right[i] = Math.max.apply(Math, byLayer[L].map(function (p) { return p.x + p.w }))
        members[i] = byLayer[L].slice().sort(function (l, r) { return l.y - r.y })
      })
      return { index: index, left: left, right: right, members: members, count: order.length }
    }

    /**
     * The heights at which a wire may cross a column without touching a node:
     * the middle of every gap between two stacked nodes, plus the small
     * margins above the first and below the last.
     *
     * This is the other half of the reservation the placement made: the
     * corridor between two columns is where a wire runs vertically, and these
     * gaps are where it may slip horizontally through a column on its way to
     * the next corridor — the staircase an elk-style layered layout builds
     * with dummy nodes, read off the nodes that are already there.
     */
    function gapLanesOf(members, gapY) {
      var lanes = []
      for (var i = 0; i <= members.length; i += 1) {
        if (i === 0) lanes.push(members[0].y - gapY / 2)
        else if (i === members.length) lanes.push(members[i - 1].y + members[i - 1].h + gapY / 2)
        else lanes.push((members[i - 1].y + members[i - 1].h + members[i].y) / 2)
      }
      return lanes
    }

    /**
     * Route the chosen relations through the reserved corridors.
     *
     * A wire only ever runs horizontally where no node stands: inside the
     * corridor between two columns, or through a gap between two nodes of the
     * column it crosses. Four shapes cover every relation:
     *
     *   near — one layer forward: out of the caller's right edge, down the
     *     corridor between the two columns, into the callee's left edge;
     *   same — both ends in one column: out of the right edge, down the
     *     corridor to the right, back into the right edge;
     *   far — several layers forward: a staircase. Down the corridor past the
     *     source to the height of a gap in the next column, across the column
     *     through that gap, down the next corridor, and so on until the
     *     corridor before the target, then in through its left edge;
     *   back — against the direction: the same staircase mirrored, out of the
     *     left edge and into the target's right edge.
     *
     * Earlier the long wires went round the whole drawing instead — up into a
     * band above everything, across the full canvas, and down — and the
     * picture grew a ladder of wires over and under it that said nothing. The
     * staircase keeps a long edge inside the columns it actually crosses.
     *
     * Every vertical run shares its corridor with the other wires that need
     * it, so each gets its own lane inside it, ordered by where it is going.
     * Crossings that remain are marked as hops, and whatever still cuts
     * through a box — possible once the user has dragged nodes out of their
     * columns — is re-routed by the same repair the board skin ends with,
     * whose detours are the only wires that still leave the drawing.
     *
     * @param edges - the relations to draw, from routing/select.
     * @param orient - byId, the placed node for every id.
     * @param relationFilter - relation kinds the viewer left switched on.
     * @param metrics - box metrics; PORT_STUB is the straight run out of a
     *   port, LAYER_GAP_X the corridor the placement reserved.
     * @returns the route (polylines, so a shift can move them) and the drawn
     *   wires, arrowheads and labels.
     */
    function routeFlow(edges, orient, relationFilter, metrics) {
      var byId = orient.byId
      var STUB = metrics.PORT_STUB
      var GAP = metrics.LAYER_GAP_X
      var CORRIDOR_MIN = metrics.CORRIDOR_MIN
      var SUBLANE_STEP = metrics.SUBLANE_STEP
      var cols = columnsOf(orient)

      // The x range a corridor owns. A corridor is named after the column it
      // follows; -1 is the margin left of the first column, which a backward
      // wire out of the first column leaves through. Outside the first and
      // last column the corridor is as wide as the placement promised.
      function corridor(c) {
        var lo = c < 0 ? cols.left[0] - GAP + STUB : cols.right[c] + STUB
        var hi = c < 0 || c >= cols.count - 1
          ? lo + GAP - STUB * 2
          : cols.left[c + 1] - STUB
        // Dragged nodes can pull two columns over each other; a corridor that
        // narrow still answers, and repairCrossings cleans up after it.
        return { lo: lo, hi: Math.max(hi, lo + CORRIDOR_MIN) }
      }

      // Lane requests per corridor, assigned once every wire has asked, so the
      // lanes can be ordered by where each run is headed instead of by which
      // wire asked first.
      var requests = {}
      function ask(c, sort) {
        var r = { sort: sort, x: null }
        ;(requests[c] = requests[c] || []).push(r)
        return r
      }

      var live = []
      edges.chosen.forEach(function (edge) {
        var a = byId[edge.from]
        var b = byId[edge.to]
        if (a === undefined || b === undefined || a === b) return
        ;(edge.types || ['call']).filter(function (type) {
          return relationFilter === undefined || relationFilter[type] !== false
        }).forEach(function (type) {
          live.push({ edge: edge, type: type, a: a, b: b })
        })
      })

      var columnOf = function (p) {
        return cols.index[typeof p.flowLayer === 'number' ? p.flowLayer : 0]
      }
      // Which columns each long wire has to cross, so every crossed column can
      // hand out its gap lanes once all of them are known.
      var crossings = {}
      live.forEach(function (w) {
        var ca = columnOf(w.a)
        var cb = columnOf(w.b)
        var ay = w.a.y + w.a.h / 2
        var by = w.b.y + w.b.h / 2
        w.lanes = {}
        w.crossY = {}
        if (cb === ca + 1) {
          w.kind = 'near'
          w.lanes[ca] = ask(ca, by)
        } else if (cb === ca) {
          w.kind = 'same'
          w.lanes[ca] = ask(ca, (ay + by) / 2)
        } else if (cb > ca + 1) {
          w.kind = 'far'
          for (var c = ca; c <= cb - 1; c += 1) w.lanes[c] = ask(c, by)
          for (var x = ca + 1; x <= cb - 1; x += 1) {
            ;(crossings[x] = crossings[x] || []).push(w)
          }
        } else {
          w.kind = 'back'
          for (var k = cb; k <= ca - 1; k += 1) w.lanes[k] = ask(k, by)
          for (var z = cb + 1; z <= ca - 1; z += 1) {
            ;(crossings[z] = crossings[z] || []).push(w)
          }
        }
      })

      Object.keys(requests).forEach(function (key) {
        var list = requests[key]
        list.sort(function (l, r) { return l.sort - r.sort })
        var corr = corridor(Number(key))
        list.forEach(function (r, i) {
          r.x = corr.lo + (i + 1) * (corr.hi - corr.lo) / (list.length + 1)
        })
      })

      // The gap each wire crosses a column through: the one nearest to where
      // it is going. Wires that share a gap fan out inside it, a few pixels
      // apart — the gap between two nodes is narrow, and a bundle that reads
      // as one strand is better than a wire through a node.
      Object.keys(crossings).forEach(function (key) {
        var c = Number(key)
        var lanes = gapLanesOf(cols.members[c], metrics.INNER_GAP_Y)
        var wires = crossings[key]
        var byGap = {}
        wires.forEach(function (w) {
          var by = w.b.y + w.b.h / 2
          var best = 0
          // A tie goes to the later gap: the margins above the first node and
          // below the last are for when the target really is up against the
          // column's edge, not for a target that has a gap between nodes
          // exactly as near.
          for (var i = 1; i < lanes.length; i += 1) {
            if (Math.abs(lanes[i] - by) <= Math.abs(lanes[best] - by)) best = i
          }
          ;(byGap[best] = byGap[best] || []).push(w)
          w.crossY[c] = best
        })
        Object.keys(byGap).forEach(function (gapKey) {
          var group = byGap[gapKey]
          var mid = lanes[Number(gapKey)]
          group.sort(function (l, r) {
            return (l.b.y + l.b.h / 2) - (r.b.y + r.b.h / 2)
          })
          var step = Math.min(SUBLANE_STEP, (metrics.INNER_GAP_Y - SUBLANE_STEP) / Math.max(1, group.length))
          group.forEach(function (w, i) {
            w.crossY[c] = mid + (i - (group.length - 1) / 2) * step
          })
        })
      })

      var polylines = []
      live.forEach(function (w) {
        var a = w.a
        var b = w.b
        var ay = a.y + a.h / 2
        var by = b.y + b.h / 2
        var pts
        var c
        if (w.kind === 'near') {
          pts = [
            { x: a.x + a.w, y: ay }, { x: w.lanes[columnOf(a)].x, y: ay },
            { x: w.lanes[columnOf(a)].x, y: by }, { x: b.x, y: by },
          ]
        } else if (w.kind === 'same') {
          pts = [
            { x: a.x + a.w, y: ay }, { x: w.lanes[columnOf(a)].x, y: ay },
            { x: w.lanes[columnOf(a)].x, y: by }, { x: b.x + b.w, y: by },
          ]
        } else if (w.kind === 'far') {
          // Right out of the source, then the staircase: vertical in one
          // corridor, across the next column through its gap, repeat.
          pts = [{ x: a.x + a.w, y: ay }, { x: w.lanes[columnOf(a)].x, y: ay }]
          for (c = columnOf(a) + 1; c <= columnOf(b) - 1; c += 1) {
            pts.push({ x: w.lanes[c - 1].x, y: w.crossY[c] })
            pts.push({ x: w.lanes[c].x, y: w.crossY[c] })
          }
          pts.push({ x: w.lanes[columnOf(b) - 1].x, y: by })
          pts.push({ x: b.x, y: by })
        } else {
          // Left out of the source, the mirrored staircase, into the target's
          // right edge.
          pts = [{ x: a.x, y: ay }, { x: w.lanes[columnOf(a) - 1].x, y: ay }]
          for (c = columnOf(a) - 1; c >= columnOf(b) + 1; c -= 1) {
            pts.push({ x: w.lanes[c].x, y: w.crossY[c] })
            pts.push({ x: w.lanes[c - 1].x, y: w.crossY[c] })
          }
          pts.push({ x: w.lanes[columnOf(b)].x, y: by })
          pts.push({ x: b.x + b.w, y: by })
        }
        polylines.push({
          id: w.edge.from + '→' + w.edge.to + ':' + w.type,
          type: w.type, pts: pts, fromFile: a.file, toFile: b.file,
          from: w.edge.from, to: w.edge.to,
          faded: stateOf(w.edge.to) !== null && stateOf(w.edge.to) !== undefined
            && !stateOf(w.edge.to).remembered,
        })
      })

      var route = { polylines: polylines, LANE_STEP: metrics.LANE_STEP, HOP: metrics.WIRE_HOP, ARROW_EVERY: metrics.ARROW_EVERY }
      repairCrossings(route, orient, metrics)
      var drawn = emitWires(route, markHops(route))
      return { route: route, drawn: drawn }
    }

    /** Same wires at a new origin: the polylines have already been moved. */
    function reemitFlow(route, orient, metrics) {
      var drawn = emitWires(route, markHops(route))
      return drawn
    }

    module.exports = { routeFlow, reemitFlow }
    return module.exports
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
          // Out of its frame: the frame would otherwise restack it straight
          // back into its old slot on this very pass.
          p.boxKey = undefined
          // Re-stamped with the column it now stands in. The flow router
          // reads its corridors off flowLayer, and a card beside the focus
          // that still claims its old layer would be routed to through the
          // corridors of a column it no longer occupies — the long way round
          // that this overlay exists to abolish.
          if (typeof focus.flowLayer === 'number') {
            p.flowLayer = focus.flowLayer + (rightward ? 1 : -1)
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

// dsh-cdd-lens — Which of the three drawings the graph is rendered as.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/skin',
  factory: (require) => {
    var module = { exports: {} }
    var __skins_tiers_group = require('dsh-cdd-lens/skins/tiers/group')
    var tiered = __skins_tiers_group.tiered

    var SKINS = ['auto', 'tiers', 'pcb', 'flow']

    /**
     * Layers, file boxes, or direction columns — and who decides.
     *
     * All three drawings already exist. Layers read as a call chain: a column
     * per step, wires straight across. File boxes read as a board: anchors
     * grouped by the file that holds them, traces merged into buses and hopped
     * over each other where they cross. Flow reads as direction: a column per
     * BFS step of the call graph with the wire corridors reserved between the
     * columns. Which one is right depends on the question being asked.
     *
     * `auto` keeps the old rule — layers when `/chain` has assigned every node
     * a layer, file boxes when it has not. `tiers` asks for layers and falls
     * back to the board when no layer was assigned, because drawing half of
     * each is worse than either alone. `pcb` and `flow` need nothing the graph
     * does not always have, so they are honoured as asked.
     *
     * @param graph - the graph about to be drawn.
     * @param included - the ids on screen.
     * @param wanted - 'auto' | 'tiers' | 'pcb' | 'flow'.
     * @returns the skin to lay out with: 'tiers' | 'pcb' | 'flow'.
     */
    function skinFor(graph, included, wanted) {
      if (wanted === 'pcb') return 'pcb'
      if (wanted === 'flow') return 'flow'
      var canLayer = tiered(graph, included)
      if (wanted === 'tiers') return canLayer ? 'tiers' : 'pcb'
      return canLayer ? 'tiers' : 'pcb'
    }

    /** The question older callers still ask: layers, or file boxes. */
    function byLayerFor(graph, included, wanted) {
      return skinFor(graph, included, wanted) === 'tiers'
    }

    module.exports = { SKINS, skinFor, byLayerFor }
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
      place.fileBoxes.forEach(box)
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
      place.fileBoxes.forEach(function (b) { b.x += dx; b.y += dy })
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

// dsh-cdd-lens — One graph in, one drawing out: the stages in order.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/layout',
  factory: (require) => {
    var module = { exports: {} }
    var __layout_prep = require('dsh-cdd-lens/layout/prep')
    var layoutScope = __layout_prep.layoutScope
    var rankFiles = __layout_prep.rankFiles
    var orientFlow = __layout_prep.orientFlow
    var __layout_space = require('dsh-cdd-lens/layout/space')
    var fitExtent = __layout_space.fitExtent
    var shiftPlacement = __layout_space.shiftPlacement
    var shiftDrawing = __layout_space.shiftDrawing
    var separateOverlaps = __layout_space.separateOverlaps
    var reclaimStrays = __layout_space.reclaimStrays
    var restackBoxes = __layout_space.restackBoxes
    var __layout_camera = require('dsh-cdd-lens/layout/camera')
    var cameraLayout = __layout_camera.cameraLayout
    var __layout_metrics = require('dsh-cdd-lens/layout/metrics')
    var boxMetrics = __layout_metrics.boxMetrics
    var __skins_tiers_route = require('dsh-cdd-lens/skins/tiers/route')
    var routeTiers = __skins_tiers_route.routeTiers
    var __layout_skin = require('dsh-cdd-lens/layout/skin')
    var skinFor = __layout_skin.skinFor
    var __state_store_skin = require('dsh-cdd-lens/state/store')
    var sharedSkin = __state_store_skin.shared
    var __skins_tiers_group = require('dsh-cdd-lens/skins/tiers/group')
    var placeTiers = __skins_tiers_group.placeTiers
    var __skins_pcb_group = require('dsh-cdd-lens/skins/pcb/group')
    var placeBoxes = __skins_pcb_group.placeBoxes
    var __skins_pcb_route = require('dsh-cdd-lens/skins/pcb/route')
    var routeBoard = __skins_pcb_route.routeBoard
    var reemitBoard = __skins_pcb_route.reemitBoard
    var __skins_flow_group = require('dsh-cdd-lens/skins/flow/group')
    var placeFlow = __skins_flow_group.placeFlow
    var __skins_flow_route = require('dsh-cdd-lens/skins/flow/route')
    var routeFlow = __skins_flow_route.routeFlow
    var reemitFlow = __skins_flow_route.reemitFlow
    var __layout_channels = require('dsh-cdd-lens/layout/channels')
    var buildChannels = __layout_channels.buildChannels
    var __routing_select = require('dsh-cdd-lens/routing/select')
    var chooseEdges = __routing_select.chooseEdges
    var __layout_gather = require('dsh-cdd-lens/layout/gather')
    var applyGather = __layout_gather.applyGather
    var freeGatherDragged = __layout_gather.freeGatherDragged

    /**
     * Turn one graph into one drawing.
     *
     * Every step is a file of its own: what is on screen, how it ranks, how
     * big the boxes are, where they go, which way each node faces, where the
     * corridors are, which relations earn a wire, and how those wires are
     * routed and emitted. Routing is the last stage and the only one the skin
     * decides, so replacing it replaces nothing else.
     * @param graph - nodes and edges to draw.
     * @param relationFilter - relation kinds the viewer left switched on.
     * @param avail - the canvas viewport width in CSS pixels.
     * @returns nodes, wires, labels, junctions, arrows, file boxes and size.
     */
    function layout(graph, relationFilter, avail) {
      if (graph.rootId === null) return { nodes: [], wires: [], labels: [], junctions: [], arrows: [], rows: [], files: [], width: 0, height: 0 }
      var scope = layoutScope(graph)
      var rank = rankFiles(graph, relationFilter, scope)
      var metrics = boxMetrics(graph, scope, avail)
      // Layers when `/chain` has said where everything goes, file boxes or
      // direction columns when it has not — or whichever of the three the
      // viewer asked for. They cannot be mixed: half a drawing laid out by
      // relation and half by directory is harder to read than either alone.
      var skin = skinFor(graph, scope.included, sharedSkin.skin || 'auto')
      var place = skin === 'tiers' ? placeTiers(graph, scope, metrics)
        : skin === 'flow' ? placeFlow(graph, scope, metrics)
        : placeBoxes(graph, scope, metrics)
      cameraLayout(graph, scope, place, rank, metrics)
      // A node dragged out of a running gather is out of its frame too —
      // before the restack, which would seat it again.
      freeGatherDragged(place)
      // Hand-placed coordinates are written in verbatim above, so this is the
      // first point at which a box can be on top of another, or off on its own
      // in an empty quarter because the layout changed shape under a saved
      // point. Pull the strays in first, then push apart what now collides.
      reclaimStrays(place, metrics, avail)
      separateOverlaps(place, metrics)
      // Frames stay in their grid slots; a drag reorders what is inside one.
      restackBoxes(place, metrics)
      // The gather overlay seats the selected node's callers and callees
      // beside it — after the restack, so a frame cannot take a gathered node
      // back, and before orientation and routing read the positions. With no
      // selection gathered it moves nothing and every skin draws as before.
      applyGather(graph, place, metrics)
      // The grid placed these boxes; deriving them again from where the
      // anchors ended up threw that away — and it ran after the separation
      // pass, so two files whose anchors had drifted together produced two
      // boxes on top of each other.
      var orient = orientFlow(graph, scope, place, metrics, avail)
      metrics.canvasWidth = orient.canvasWidth
      place.canvasY = orient.canvasY
      var channels = buildChannels(place, metrics)
      var edges = chooseEdges(graph, scope, orient)
      // Declared for both paths on purpose. These used to be `var`s inside the
      // else, which hoists them: the layered path then reached a `route` that
      // was always `undefined`, and the shift below threw on it — blanking the
      // whole view for any drawing that happened to need moving.
      var route = null
      var drawn
      if (skin === 'tiers') {
        // Layered drawings get a router that knows about layers: the gap under
        // a row is the only place a wire may run sideways, so a wire never
        // crosses a node it has nothing to do with.
        drawn = routeTiers(edges, orient, relationFilter, metrics)
        route = drawn.route
      } else if (skin === 'flow') {
        // Flow drawings get a router that knows about the corridors the
        // placement reserved between the columns: the only places a wire may
        // run at all.
        var flow = routeFlow(edges, orient, relationFilter, metrics)
        route = flow.route
        drawn = flow.drawn
      } else {
        var board = routeBoard(edges, orient, relationFilter, metrics, channels)
        route = board.route
        drawn = board.drawn
      }
      // The size comes from what was drawn. If any of it landed off the top
      // left, move the whole drawing into view and emit it again there —
      // routing does not change, only where its origin sits.
      var fit = fitExtent(place, drawn, metrics)
      if (fit.dx > 0 || fit.dy > 0) {
        shiftDrawing(place, route, fit.dx, fit.dy)
        drawn = reemitBoard(route, orient, metrics)
        fit = fitExtent(place, drawn, metrics)
      }
      return {
        nodes: place.placed, wires: drawn.wires, labels: drawn.labels,
        junctions: drawn.junctions, arrows: drawn.arrows, unrouted: drawn.unrouted,
        rows: place.rows || [], files: place.fileBoxes,
        width: Math.max(avail || 0, fit.maxX + metrics.PAD),
        height: Math.max(360, fit.maxY + metrics.PAD),
      }
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
    var __shell_chat_eat = require('dsh-cdd-lens/shell/chatSeat')
    var openDockBesideChat = __shell_chat_eat.openDockBesideChat

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

    function SourceSnippet(props) {
      var source = (shared.sourceCache || {})[props.id]
      if (source === undefined) return h('div', { className: 'cddl-trace-loading' }, '读取源码…')
      return h('div', { className: 'cddl-trace-source' }, [
        h('div', { key: 'path', className: 'cddl-trace-path', title: source.file },
          source.file + ':' + source.start + '–' + source.end),
        h('pre', { key: 'code' }, source.lines.map(function (text, i) {
          return h('div', { key: source.from + i }, [
            h('span', { key: 'n' }, source.from + i),
            h('code', { key: 'c' }, text === '' ? ' ' : text),
          ])
        })),
      ])
    }

    function locateInGraph(ctx, engine, id) {
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
      var anchor = node === undefined ? null : node.anchor
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
          h('button', {
            key: 'graph', className: 'cddl-trajectory-graph',
            onClick: function () { openDockBesideChat(props.ctx) },
          }, '逻辑图'),
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
          h(Source, { key: 's' }),
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

      // Selection IS the gather switch: a node that becomes selected pulls its
      // callers and callees to its side; losing the selection puts them back.
      // Watching the value catches every path that selects — click, search,
      // directory, a trace landing — without each of them having to know.
      var selectedNow = shared.selected
      useEffect(function () {
        if (selectedNow === null || selectedNow === undefined) engine.releaseGather()
        else engine.gather(selectedNow)
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
      useEffect(function () {
        if (tab[0] !== 'graph' || model.nodes.length === 0) return
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
          } else centerOn(viewportRequest.id, zoom[0])
        })
        return function () { window.cancelAnimationFrame(frame) }
      }, [tab[0], viewportRequest.seq, model.width, model.height])

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
                  key: 'a', id: 'cddl-arrow', markerWidth: 8, markerHeight: 8, refX: 6.5, refY: 3, orient: 'auto',
                }, h('path', { d: 'M0,0 L6,3 L0,6 z' })),
                h('marker', {
                  key: 'f', id: 'cddl-arrow-faded', markerWidth: 8, markerHeight: 8, refX: 6.5, refY: 3, orient: 'auto',
                }, h('path', { d: 'M0,0 L6,3 L0,6 z' })),
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
                },
              })
            })).concat(model.arrows.map(function (arrow) {
              // Repeated along the run: on a wire with four bends a single
              // arrowhead at the far end says nothing about the middle.
              return h('path', {
                key: 'a' + arrow.id,
                className: 'cddl-arrowhead cddl-' + arrow.type
                  + (arrow.faded ? ' cddl-faded' : '')
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

      return canvas
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
    if (shared.skin === undefined) {
      try {
        var savedSkin = window.localStorage.getItem(SKIN_KEY)
        shared.skin = savedSkin === 'tiers' || savedSkin === 'pcb' || savedSkin === 'flow' ? savedSkin : 'auto'
      } catch (e) { shared.skin = 'auto' }
    }
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
      var setSkin = function (value) {
        shared.skin = value
        try { window.localStorage.setItem(SKIN_KEY, value) } catch (e) { /* optional */ }
        publish()
      }

      return h('div', { className: 'cddl-toolbar', key: 't' }, [
          h('div', { key: 'seg', className: 'cddl-seg' }, [
            h('button', { key: 'g', className: tab[0] === 'graph' ? 'on' : '', onClick: function () { tab[1]('graph') } }, '逻辑图'),
            h('button', { key: 'o', className: tab[0] === 'outline' ? 'on' : '', onClick: function () { tab[1]('outline') } }, '目录'),
            h('button', { key: 'd', className: tab[0] === 'draw' ? 'on' : '', onClick: function () { tab[1]('draw') } }, 'cdd draw'),
          ]),
          // All three drawings have always existed as data; only the chooser
          // used to decide between two of them. Layers read as a call chain,
          // file boxes read as a board, flow reads as direction — which one
          // answers your question is not something the data knows.
          tab[0] !== 'graph' ? null
            : h('div', { key: 'skin', className: 'cddl-seg cddl-skin', 'aria-label': '图的形态' },
              [['auto', '自动'], ['tiers', '分层'], ['pcb', 'PCB'], ['flow', '流向']].map(function (pair) {
                var value = pair[0]
                return h('button', {
                  key: value,
                  className: (shared.skin || 'auto') === value ? 'on' : '',
                  'aria-pressed': (shared.skin || 'auto') === value ? 'true' : 'false',
                  title: value === 'tiers' ? '按调用层级排成列'
                    : value === 'pcb' ? '按文件分盒子，走线像电路板'
                    : value === 'flow' ? '按调用方向分列，线走层间预留的通道'
                    : '有层级信息就分层，没有就用文件盒',
                  onClick: function () { setSkin(value) },
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
