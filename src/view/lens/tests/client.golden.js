// dsh-cdd-lens — browser half. GENERATED, DO NOT EDIT.
//
// Built from src/client/ by scripts/build.js. Edit the parts, not this file.
// Written in the shape tsdown emits (`__ModuleLoader__.load` + a CJS body +
// the loader's `require`), so a generated bundle drops in on top.
//
// build: V1_19_DOCK_FOCUS_LAYOUT_001
// parts: 47

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
    var BUILD = 'V1_19_DOCK_FOCUS_LAYOUT_001'
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

    module.exports = { BUILD, ROUTE, api }
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

    module.exports = { emptyGraph, addNode, addEdge }
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
      dockOpen: false,
      nodePositions: {},
      positionRoot: null,
      revision: 0,
      listeners: [],
    }
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

    module.exports = { shared, publish, requestViewport, useShared, useRightInset }
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
              // The layer belongs on the node, so whatever draws the graph can
              // ask a node where it goes instead of working it out again.
              var seat = function (id, layer, tree, seed) {
                var node = shared.graph.nodes[id]
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

        context: function () {
          return api('/context', params()).then(function (body) {
            shared.context = body
            shared.root = body.root
            ensureNodePositions(body.root)
            publish()
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
            requestViewport(anchor.id, 'fit')
            publish()
            return engine.source(anchor.id)
          })
        },
        /** Add an anchor beside the current exploration without resetting it. */
        add: function (anchor) {
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
        select: function (id) {
          // Clicking the already-focused node clears the emphasis, so getting
          // the whole picture back does not require hunting for empty canvas.
          if (shared.focused === id) { shared.focused = null; publish(); return Promise.resolve() }
          shared.selected = id
          requestViewport(id, 'center')
          // `focused` is set only by a human click. `selected` also moves on its
          // own when a trace loads, and dimming everything else off THAT made
          // 88% of the wires grey the moment the tab opened — an emphasis that
          // is always on is just a washed-out picture.
          shared.focused = id
          publish()
          return engine.source(id)
        },
        blur: function () {
          shared.focused = null
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
                    unresolved[f] = { file: f, reason: hit.reason, verb: touch.verb, turns: [] }
                  }
                  if (unresolved[f].turns.indexOf(call.turn) < 0) unresolved[f].turns.push(call.turn)
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

    function Outline(props) {
      var engine = props.engine
      var openDir = useState({})
      var dirs = shared.outline
      useEffect(function () { if (dirs === undefined) engine.outline() }, [dirs === undefined])
      if (dirs === undefined) return h('div', { className: 'cddl-empty' }, '读目录…')
      var out = []
      dirs.forEach(function (entry) {
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
      return h('div', { className: 'cddl-tree' }, out)
    }

    /**
     * `cdd draw`'s own compound browser, served verbatim in a frame.
     *
     * CodeDendrite already generates a finished directory/file/class/function
     * browser with its data inlined. Replacing it with a tree of my own lost a
     * working tool, so it is shown as itself. Same-origin, so it needs no bridge.
     */
    function Draw(props) {
      var engine = props.engine
      var state = useState({ status: 'loading' })
      var src = ROUTE + '/draw?' + new URLSearchParams(engine.params()).toString()
      useEffect(function () {
        var stop = false
        var poll = function () {
          fetch(src, { cache: 'no-store' }).then(function (res) {
            if (stop) return
            if (res.status === 200) { state[1]({ status: 'ready' }); return }
            if (res.status === 202) { state[1]({ status: 'building' }); setTimeout(poll, 1500); return }
            return res.json().then(function (body) { state[1]({ status: 'error', error: body.error }) })
          }).catch(function (error) { if (!stop) state[1]({ status: 'error', error: String(error.message) }) })
        }
        poll()
        return function () { stop = true }
      }, [src])
      if (state[0].status === 'building') {
        return h('div', { className: 'cddl-empty' }, '正在生成 cdd draw 全图…')
      }
      if (state[0].status === 'error') {
        return h('div', { className: 'cddl-empty' }, ['cdd draw 生成失败：', state[0].error])
      }
      if (state[0].status === 'loading') return h('div', { className: 'cddl-empty' }, '载入中…')
      return h('iframe', { className: 'cddl-frame', src: src, title: 'cdd draw' })
    }

    module.exports = { Outline, Draw }
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

      var upOpen = p.node.up === true
      var downOpen = p.node.down === true
      // The same card is used twice: positioned on the canvas, and standing in
      // the flow of the stream rail. Only where it sits differs, so only that
      // is switched — a second component would drift from this one.
      var flow = props.flow === true
      return h('div', {
        className: 'cddl-node-shell' + (p.island ? ' cddl-shell-island' : '')
          + (flow ? ' cddl-node-flow' : ''),
        style: flow
          ? { width: p.w + 'px' }
          : { left: p.x + 'px', top: p.y + 'px', width: p.w + 'px' },
        'data-node-id': p.id,
      }, [
        h('span', {
          key: 'port-in',
          className: 'cddl-port cddl-port-in cddl-port-' + (p.flowDir === 'rtl' ? 'right' : 'left'),
          'data-port': 'in',
          title: '关系进入此 Anchor',
        }, '入'),
        h('span', {
          key: 'port-out',
          className: 'cddl-port cddl-port-out cddl-port-' + (p.flowDir === 'rtl' ? 'left' : 'right'),
          'data-port': 'out',
          title: '此 Anchor 调用下一个 Anchor',
        }, '出'),
        h('div', {
          key: 'n',
          className: 'cddl-gnode'
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
              else engine.select(p.id)
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

// dsh-cdd-lens — Which anchors and files this drawing covers.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/scope',
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

    module.exports = { layoutScope }
    return module.exports
  },
})

// dsh-cdd-lens — Ordering files and anchors by relationship depth.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/ranking',
  factory: (require) => {
    var module = { exports: {} }

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

    module.exports = { rankFiles }
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
      var PAD = 18
      var BOX_GAP_X = 40
      var CHAR_W = 7.4
      var BADGES = 128
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
      var roomForBox = Math.max(240, (avail || 640) - PAD * 2)
      var NODE_W = Math.max(200, Math.min(roomForBox - 22, Math.ceil(longest * CHAR_W + BADGES)))
      var BOX_W = NODE_W + 11 * 2
      var BOX_GAP_Y = 40
      var BOX_PAD = 11
      var BOX_HEAD = 32
      var INNER_GAP_X = 20
      var INNER_GAP_Y = 14
      // Narrow boxes mean more of them fit across, which keeps related files
      // near each other and the wires between them short.
      var usable = Math.max(320, (avail || 0) - PAD * 2)
      var BOX_COLS = Math.max(1, Math.floor((usable + BOX_GAP_X) / (BOX_W + BOX_GAP_X)))
      if (fileOrder.length === 1) BOX_COLS = 1
      if (fileOrder.length < BOX_COLS) BOX_COLS = fileOrder.length
      // No floor. A hardcoded minimum of 920 held the canvas wider than the
      // boxes it contains, so narrowing the window correctly dropped to one
      // column and then overflowed anyway — the drawing insisted on a width
      // nothing asked for.
      var canvasWidth = PAD * 2 + BOX_COLS * BOX_W + Math.max(0, BOX_COLS - 1) * BOX_GAP_X
      // Measured, not guessed. A pixels-per-character constant was wrong for
      // every font it was not tuned on, and there were two different ones in
      // this codebase for the same face — which is the tell that neither was
      // ever measured. One offscreen canvas answers exactly.
      var label = labelsFor(graph, included)
      var sizeOf = function (id) {
        var node = graph.nodes[id]
        var text = label[id] === undefined ? shortSymbol(node.anchor.symbol) : label[id]
        var badge = 46
        var chrome = 22 + 14 + 16
        var own = Math.ceil(textWidth(text, SYMBOL_FONT)) + badge + chrome
        return {
          // Never wider than the space there is, never so narrow the buttons
          // underneath do not fit.
          w: Math.max(150, Math.min(NODE_W, own)),
          // The controls sit inside the card now, so a plain node is two rows.
          h: node.members && node.memberList !== undefined
            ? 54 + node.memberList.length * 22 + 16 + 22
            : 70,
        }
      }
      return { PAD: PAD, BOX_GAP_X: BOX_GAP_X, BOX_GAP_Y: BOX_GAP_Y, BOX_PAD: BOX_PAD,
        BOX_HEAD: BOX_HEAD, BOX_W: BOX_W, BOX_COLS: BOX_COLS, NODE_W: NODE_W,
        INNER_GAP_X: INNER_GAP_X, INNER_GAP_Y: INNER_GAP_Y,
        canvasWidth: canvasWidth, sizeOf: sizeOf, label: label }
    }

    module.exports = { boxMetrics, textWidth, shortSymbol, labelsFor }
    return module.exports
  },
})

// dsh-cdd-lens — Where the boxes and the anchors inside them sit.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/placement',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * First positions: file boxes in rows, anchors down each box.
     */
    function placeBoxes(graph, scope, metrics) {
      var byFile = scope.byFile
      var fileOrder = scope.fileOrder
      var PAD = metrics.PAD
      var BOX_GAP_X = metrics.BOX_GAP_X
      var BOX_GAP_Y = metrics.BOX_GAP_Y
      var BOX_PAD = metrics.BOX_PAD
      var BOX_HEAD = metrics.BOX_HEAD
      var BOX_W = metrics.BOX_W
      var BOX_COLS = metrics.BOX_COLS
      var INNER_GAP_X = metrics.INNER_GAP_X
      var INNER_GAP_Y = metrics.INNER_GAP_Y
      var sizeOf = metrics.sizeOf

      var placed = []
      var fileBoxes = []
      // The vertical bands the box rows occupy. The gaps between them are the
      // horizontal channels; the gaps between columns are the vertical ones.
      // They already exist in the layout — nothing used them, so every wire took
      // the shortest line and went straight through whatever box was in the way.
      var rowBands = []
      var canvasY = PAD
      for (var fileStart = 0; fileStart < fileOrder.length; fileStart += BOX_COLS) {
        var filesInRow = fileOrder.slice(fileStart, fileStart + BOX_COLS)
        var rowLayouts = filesInRow.map(function (file, col) {
          var ids = byFile[file]
          var localRows = []
          // One anchor per row. Two columns made every box twice as wide, which
          // pushed the boxes apart, which made every wire longer — the width
          // was spent on emptiness and paid for in travel. Reading a file's
          // anchors top to bottom is also just how a file reads.
          for (var i = 0; i < ids.length; i += 1) localRows.push([ids[i]])
          var contentHeight = 0
          localRows.forEach(function (idsInRow, rowIndex) {
            var height = Math.max.apply(Math, idsInRow.map(function (id) { return sizeOf(id).h }))
            contentHeight += height + (rowIndex === localRows.length - 1 ? 0 : INNER_GAP_Y)
          })
          return {
            file: file, ids: ids, localRows: localRows,
            x: PAD + col * (BOX_W + BOX_GAP_X),
            h: BOX_HEAD + BOX_PAD + contentHeight + BOX_PAD,
          }
        })
        var fileRowHeight = Math.max.apply(Math, rowLayouts.map(function (box) { return box.h }))
        rowLayouts.forEach(function (box, boxIndex) {
          fileBoxes.push({ file: box.file, x: box.x, y: canvasY, w: BOX_W, h: box.h, count: box.ids.length })
          var nodeY = canvasY + BOX_HEAD + BOX_PAD
          box.localRows.forEach(function (idsInRow, localRow) {
            var localHeight = Math.max.apply(Math, idsInRow.map(function (id) { return sizeOf(id).h }))
            idsInRow.forEach(function (id, col) {
              var size = sizeOf(id)
              placed.push({
                id: id, node: graph.nodes[id],
                x: box.x + BOX_PAD + col * (size.w + INNER_GAP_X),
                y: nodeY, w: size.w, h: size.h,
                rowIndex: fileStart + localRow, innerRow: localRow,
                file: box.file, island: false,
              })
            })
            nodeY += localHeight + INNER_GAP_Y
          })
        })
        rowBands.push({ top: canvasY, bottom: canvasY + fileRowHeight })
        canvasY += fileRowHeight + BOX_GAP_Y
      }

      return { placed: placed, fileBoxes: fileBoxes, rowBands: rowBands, canvasY: canvasY }
    }
    /**
     * A file becomes a visual container only at three or more anchors.
     */
    function deriveFileBoxes(place, metrics) {
      var placed = place.placed
      var fileBoxes = place.fileBoxes
      var BOX_PAD = metrics.BOX_PAD
      var BOX_HEAD = metrics.BOX_HEAD

      // A file becomes a visual container only when at least three of its
      // anchors are present. One- and two-anchor files remain loose nodes, so
      // the graph does not turn into a wall of almost-empty boxes.
      var placedByFile = {}
      placed.forEach(function (p) { (placedByFile[p.file] = placedByFile[p.file] || []).push(p) })
      fileBoxes = []
      Object.keys(placedByFile).forEach(function (file) {
        var members = placedByFile[file]
        if (members.length < 3) return
        var left = Math.min.apply(Math, members.map(function (p) { return p.x })) - BOX_PAD
        var top = Math.min.apply(Math, members.map(function (p) { return p.y })) - BOX_HEAD
        var right = Math.max.apply(Math, members.map(function (p) { return p.x + p.w })) + BOX_PAD
        var bottom = Math.max.apply(Math, members.map(function (p) { return p.y + p.h })) + BOX_PAD
        fileBoxes.push({ file: file, x: left, y: top, w: right - left, h: bottom - top, count: members.length })
      })

      return fileBoxes
    }

    module.exports = { placeBoxes, deriveFileBoxes }
    return module.exports
  },
})

// dsh-cdd-lens — Which side of a node a wire enters and leaves by.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/orientation',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared

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

      // In/out sides are propagated by actual relations, not assigned from a
      // visual row number. Starting at the graph root, every connected next
      // node receives on its caller's exit side and exits from the other side.
      // Disconnected components repeat the same rule from their own first node.
      var orientation = {}
      var orientQueue = []
      var seedOrientation = function (id) {
        if (byId[id] === undefined || orientation[id] !== undefined) return
        orientation[id] = 'ltr'
        orientQueue.push(id)
        while (orientQueue.length > 0) {
          var current = orientQueue.shift()
          graph.edges.forEach(function (edge) {
            if (byId[edge.from] === undefined || byId[edge.to] === undefined) return
            var peer = edge.from === current ? edge.to : (edge.to === current ? edge.from : null)
            if (peer === null || orientation[peer] !== undefined) return
            orientation[peer] = orientation[current] === 'ltr' ? 'rtl' : 'ltr'
            orientQueue.push(peer)
          })
        }
      }
      included.filter(function (id) {
        return graph.nodes[id].anchor.symbol.split && graph.nodes[id].anchor.symbol.split('.').pop() === 'main'
      }).forEach(seedOrientation)
      seedOrientation(graph.rootId)
      if (shared.edgeFocus) seedOrientation(shared.edgeFocus.from)
      included.forEach(seedOrientation)
      placed.forEach(function (p) { p.flowDir = orientation[p.id] || 'ltr' })
      var boxOf = {}
      fileBoxes.forEach(function (box) { boxOf[box.file] = box })
      canvasWidth = Math.max(avail || 0, PAD * 2 + Math.max.apply(Math, placed.map(function (p) { return p.x + p.w })))
      canvasY = PAD + Math.max.apply(Math, placed.map(function (p) { return p.y + p.h })) + BOX_GAP_Y

      return { byId: byId, boxOf: boxOf, canvasWidth: canvasWidth, canvasY: canvasY }
    }

    module.exports = { orientFlow }
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
        // One parent per node — the nearest placed caller, so the trunk follows
        // the layout instead of fighting it.
        var best = {}
        drawable.forEach(function (e) {
          var a = byId[e.from]
          var b = byId[e.to]
          var cost = Math.abs(a.x - b.x) + Math.abs(a.y - b.y)
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
    function routeOrtho(edges, orient, relationFilter, channels) {
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
      var LANE_STEP = 12
      var HOP = 4.5
      var ARROW_EVERY = 68

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
            var sideL = boxS.x + 8
            var sideR = boxS.x + boxS.w - 8
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
        var key = line.from + '|' + (line.pts[2].y > line.pts[0].y ? 'down' : 'up')
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
      hSegs.forEach(function (h) {
        var y = h.p.y
        var lo = Math.min(h.p.x, h.q.x)
        var hi = Math.max(h.p.x, h.q.x)
        var xs = []
        vSegs.forEach(function (v) {
          if (v.line === h.line) return
          var x = v.p.x
          var y0 = Math.min(v.p.y, v.q.y)
          var y1 = Math.max(v.p.y, v.q.y)
          if (x > lo + HOP && x < hi - HOP && y > y0 + 0.5 && y < y1 - 0.5) xs.push(x)
        })
        h.hops = xs.sort(function (l, r) { return l - r })
      })

      return { hSegs: hSegs, vSegs: vSegs }
    }

    module.exports = { markHops }
    return module.exports
  },
})

// dsh-cdd-lens — Turning routed polylines into drawable output.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/emit',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * Polylines become SVG paths, arrowheads and labels.
     */
    function emitWires(route, hops) {
      var polylines = route.polylines
      var HOP = route.HOP
      var ARROW_EVERY = route.ARROW_EVERY
      var hSegs = hops.hSegs

      var wires = []
      var labels = []
      var junctions = []
      var arrows = []

      polylines.forEach(function (line) {
        var pts = line.pts
        var d = 'M' + pts[0].x + ',' + pts[0].y
        for (var i = 1; i < pts.length; i += 1) {
          var p = pts[i - 1]
          var q = pts[i]
          var seg = null
          for (var k = 0; k < hSegs.length; k += 1) {
            if (hSegs[k].p === p && hSegs[k].q === q) { seg = hSegs[k]; break }
          }
          if (seg !== null && seg.hops !== undefined && seg.hops.length > 0) {
            var rightward = q.x > p.x
            var order = rightward ? seg.hops : seg.hops.slice().reverse()
            order.forEach(function (cx) {
              var before = rightward ? cx - HOP : cx + HOP
              var after = rightward ? cx + HOP : cx - HOP
              d += ' L' + before + ',' + p.y
              // sweepFlag 0 arcs upward in both travel directions.
              d += ' A' + HOP + ',' + HOP + ' 0 0 ' + (rightward ? 1 : 0) + ' ' + after + ',' + p.y
            })
            d += ' L' + q.x + ',' + q.y
          } else {
            d += ' L' + q.x + ',' + q.y
          }
        }
        wires.push({
          id: line.id, d: d, type: line.type, faded: line.faded,
          fromFile: line.fromFile, toFile: line.toFile,
          from: line.from, to: line.to,
        })

        // Direction markers along the run, not just at the far end.
        var walked = 0
        var next = ARROW_EVERY * 0.55
        for (var j = 1; j < pts.length; j += 1) {
          var s = pts[j - 1]
          var t = pts[j]
          var len = Math.abs(t.x - s.x) + Math.abs(t.y - s.y)
          if (len < 1) continue
          var angle = Math.atan2(t.y - s.y, t.x - s.x) * 180 / Math.PI
          while (walked + len >= next) {
            var into = next - walked
            var ratio = into / len
            arrows.push({
              id: line.id + ':' + arrows.length,
              from: line.from, to: line.to,
              x: s.x + (t.x - s.x) * ratio,
              y: s.y + (t.y - s.y) * ratio,
              angle: angle, type: line.type, faded: line.faded,
            })
            next += ARROW_EVERY
          }
          walked += len
        }

        var mid = pts[Math.max(1, Math.floor(pts.length / 2))]
        labels.push({ id: line.id, x: mid.x + 5, y: mid.y - 4, type: line.type })
      })

      // No inferred junction dots. A dot that claims several static relations
      // meet at one semantic point is information the index does not provide.

      // V1.19: relations are readable fly-lines, not a second layout engine.
      // Every relation flips the next node's direction: if A enters left and
      // exits right, its callee B enters right and exits left. This follows the
      // graph relation rather than a row/column parity rule.
      wires = []
      arrows = []
      labels = []
      junctions = []
      return { wires: wires, labels: labels, junctions: junctions, arrows: arrows }
    }

    module.exports = { emitWires }
    return module.exports
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

// dsh-cdd-lens — How big the canvas has to be for all of it to be reachable.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/extent',
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
        // Every coordinate pair in the path, control points included: a cubic
        // never leaves its own control hull, so bounding the hull bounds the
        // curve, and bounding it slightly wide only ever reserves more room.
        var nums = String(wire.d || '').match(/-?\d+(?:\.\d+)?/g) || []
        for (var i = 0; i + 1 < nums.length; i += 2) see(Number(nums[i]), Number(nums[i + 1]))
      })
      if (minX === Infinity) return { dx: 0, dy: 0, minX: 0, minY: 0, maxX: 0, maxY: 0 }
      return {
        dx: Math.max(0, PAD - minX), dy: Math.max(0, PAD - minY),
        minX: minX, minY: minY, maxX: maxX, maxY: maxY,
      }
    }

    /**
     * Move the whole drawing so nothing sits left of or above the origin.
     *
     * A node keeps the coordinate it was SAVED at in `baseX`/`baseY`. Dragging
     * writes that one back, so the margin the wires happened to need this time
     * never folds into a stored position and never accumulates across renders.
     * @param place - nodes and file boxes, moved in place.
     * @param route - the routed polylines, moved in place.
     * @param dx - how far right to move everything.
     * @param dy - how far down to move everything.
     */
    function shiftDrawing(place, route, dx, dy) {
      if (dx === 0 && dy === 0) return
      place.placed.forEach(function (p) {
        if (p.baseX === undefined) { p.baseX = p.x; p.baseY = p.y }
        p.x += dx
        p.y += dy
      })
      place.fileBoxes.forEach(function (b) { b.x += dx; b.y += dy })
      route.polylines.forEach(function (line) {
        line.pts.forEach(function (pt) { pt.x += dx; pt.y += dy })
      })
    }

    module.exports = { fitExtent, shiftDrawing }
    return module.exports
  },
})

// dsh-cdd-lens — Placing anchors by how far they are from what was edited.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/tiers',
  factory: (require) => {
    var module = { exports: {} }

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
     * One row per layer, trees stacked in the order `/chain` ranked them.
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
      var PAD = metrics.PAD
      var BOX_GAP_X = metrics.BOX_GAP_X
      var BOX_GAP_Y = metrics.BOX_GAP_Y
      var sizeOf = metrics.sizeOf

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

      var placed = []
      var rowBands = []
      var rows = []
      var canvasY = PAD
      var lastTree = null
      order.forEach(function (key) {
        var band = bands[key]
        // A new tree is a new subject; the gap says so without a heading.
        if (lastTree !== null && band.tree !== lastTree) canvasY += BOX_GAP_Y
        lastTree = band.tree
        // Anchors the session touched lead their row: they are why the rest of
        // the row is on screen at all.
        band.ids.sort(function (l, r) {
          var ln = graph.nodes[l], rn = graph.nodes[r]
          return (ln.seed === true ? 0 : 1) - (rn.seed === true ? 0 : 1)
            || ln.anchor.symbol.localeCompare(rn.anchor.symbol)
        })
        var height = 0
        var x = PAD
        band.ids.forEach(function (id) {
          var size = sizeOf(id)
          var node = graph.nodes[id]
          placed.push({
            id: id, node: node, anchor: node.anchor, file: node.anchor.file,
            x: x, y: canvasY, w: size.w, h: size.h,
            layer: band.layer, tree: band.tree, label: metrics.label[id],
          })
          x += size.w + BOX_GAP_X
          if (size.h > height) height = size.h
        })
        rows.push({
          label: 'L' + band.layer + ' · ' + band.ids.length,
          y: canvasY, ids: band.ids.slice(), island: false,
        })
        rowBands.push({ y: canvasY, h: height })
        canvasY += height + BOX_GAP_Y
      })

      return { placed: placed, fileBoxes: [], rowBands: rowBands, rows: rows, canvasY: canvasY }
    }

    module.exports = { tiered, placeTiers }
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
    var __layout_camera = require('dsh-cdd-lens/layout/camera')
    var cameraLayout = __layout_camera.cameraLayout
    var __layout_scope = require('dsh-cdd-lens/layout/scope')
    var layoutScope = __layout_scope.layoutScope
    var __layout_ranking = require('dsh-cdd-lens/layout/ranking')
    var rankFiles = __layout_ranking.rankFiles
    var __layout_metrics = require('dsh-cdd-lens/layout/metrics')
    var boxMetrics = __layout_metrics.boxMetrics
    var __layout_tiers = require('dsh-cdd-lens/layout/tiers')
    var tiered = __layout_tiers.tiered
    var placeTiers = __layout_tiers.placeTiers
    var __layout_placement = require('dsh-cdd-lens/layout/placement')
    var deriveFileBoxes = __layout_placement.deriveFileBoxes
    var placeBoxes = __layout_placement.placeBoxes
    var __layout_orientation = require('dsh-cdd-lens/layout/orientation')
    var orientFlow = __layout_orientation.orientFlow
    var __layout_channels = require('dsh-cdd-lens/layout/channels')
    var buildChannels = __layout_channels.buildChannels
    var __routing_select = require('dsh-cdd-lens/routing/select')
    var chooseEdges = __routing_select.chooseEdges
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
    var __routing_curve = require('dsh-cdd-lens/routing/curve')
    var emitCurves = __routing_curve.emitCurves
    var __layout_extent = require('dsh-cdd-lens/layout/extent')
    var fitExtent = __layout_extent.fitExtent
    var shiftDrawing = __layout_extent.shiftDrawing

    /**
     * Turn one graph into one drawing.
     *
     * Every step is a file of its own: what is on screen, how it ranks, how
     * big the boxes are, where they go, which way each node faces, where the
     * corridors are, which relations earn a wire, and how those wires are
     * routed and emitted. Routing is the last stage and the only one with two
     * implementations, so replacing it replaces nothing else.
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
      // Layers when `/chain` has said where everything goes, file boxes when it
      // has not. The two cannot be mixed: half a drawing laid out by relation
      // and half by directory is harder to read than either done alone.
      var byLayer = tiered(graph, scope.included)
      var place = byLayer ? placeTiers(graph, scope, metrics)
        : placeBoxes(graph, scope, metrics)
      cameraLayout(graph, scope, place, rank, metrics)
      if (!byLayer) place.fileBoxes = deriveFileBoxes(place, metrics)
      var orient = orientFlow(graph, scope, place, metrics, avail)
      metrics.canvasWidth = orient.canvasWidth
      place.canvasY = orient.canvasY
      var channels = buildChannels(place, metrics)
      var edges = chooseEdges(graph, scope, orient)
      var route = routeOrtho(edges, orient, relationFilter, channels)
      mergeBuses(route)
      spreadLanes(route, metrics)
      var hops = markHops(route)
      var drawn = emitWires(route, hops)
      emitCurves(edges, orient, relationFilter, drawn)
      // The size comes from what was drawn. If any of it landed off the top
      // left, move the whole drawing into view and emit it again there —
      // routing does not change, only where its origin sits.
      var fit = fitExtent(place, drawn, metrics)
      if (fit.dx > 0 || fit.dy > 0) {
        shiftDrawing(place, route, fit.dx, fit.dy)
        hops = markHops(route)
        drawn = emitWires(route, hops)
        emitCurves(edges, orient, relationFilter, drawn)
        fit = fitExtent(place, drawn, metrics)
      }
      return {
        nodes: place.placed, wires: drawn.wires, labels: drawn.labels,
        junctions: drawn.junctions, arrows: drawn.arrows,
        rows: place.rows || [], files: place.fileBoxes,
        width: Math.max(avail || 0, fit.maxX + metrics.PAD),
        height: Math.max(360, fit.maxY + metrics.PAD),
      }
    }

    module.exports = { layout }
    return module.exports
  },
})

// dsh-cdd-lens — The rail: every touch in the order it happened.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/stream',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __layout_metrics = require('dsh-cdd-lens/layout/metrics')
    var textWidth = __layout_metrics.textWidth
    var labelsFor = __layout_metrics.labelsFor
    var __view_node = require('dsh-cdd-lens/view/node')
    var GraphNode = __view_node.GraphNode

    /**
     * Every touch the session made, once per anchor per step, in order.
     *
     * The graph answers "what is related to what". It cannot answer "what
     * happened, in what order" — putting time on a spatial layout is exactly
     * what turned the picture into a list before. So the order lives here
     * instead, one row per step, and the graph is left to do its own job.
     * @returns rows of {turn, step, verb, id}, earliest first.
     */
    function stepsOf() {
      var trace = shared.trace || {}
      var rows = []
      Object.keys(trace).forEach(function (id) {
        var seen = {}
        ;(trace[id].events || []).forEach(function (e) {
          var at = e.turn + ':' + (e.step || 1)
          // One row per anchor per step. A read that reports three times in the
          // same call is one thing happening, not three.
          if (seen[at] === true) return
          seen[at] = true
          rows.push({ id: id, turn: e.turn, step: e.step || 1, verb: e.verb })
        })
      })
      rows.sort(function (l, r) {
        return l.turn - r.turn || l.step - r.step || l.id.localeCompare(r.id)
      })
      return rows
    }

    /** The word for what the agent did, in the tense it was doing it. */
    function verbOf(verb) {
      if (verb === 'edit' || verb === 'write') return 'editing'
      return 'reading'
    }

    /**
     * The rail beside the graph.
     *
     * Nothing is joined by a line here except the edits: reading two things in
     * a row says only that they were read in a row, and drawing that would be
     * inventing a relation the code does not have. Edits are different — they
     * are what the session is for, and the thread through them is the story.
     * @param props - the engine, for selecting and redrawing.
     * @returns the rail element.
     */
    function Stream(props) {
      var engine = props.engine
      var rows = stepsOf()
      if (rows.length === 0) {
        return h('div', { className: 'cddl-rail' },
          h('div', { className: 'cddl-rail-empty' }, '还没有动作。读或改一个文件，这里会按顺序长出来。'))
      }
      var ids = rows.map(function (r) { return r.id })
      var label = labelsFor(shared.graph, ids)
      var width = 0
      ids.forEach(function (id) {
        var node = shared.graph.nodes[id]
        if (node === undefined) return
        var text = label[id] || node.anchor.symbol
        var own = Math.ceil(textWidth(text, '11.5px ui-monospace, SFMono-Regular, Menlo, monospace')) + 84
        if (own > width) width = own
      })
      width = Math.max(160, Math.min(260, width))

      var edits = rows.filter(function (r) { return verbOf(r.verb) === 'editing' })
      var firstEdit = edits.length === 0 ? -1 : rows.indexOf(edits[0])
      var lastEdit = edits.length === 0 ? -1 : rows.lastIndexOf(edits[edits.length - 1])

      return h('div', { className: 'cddl-rail' }, [
        h('div', { key: 'h', className: 'cddl-rail-head' },
          rows.length + ' 步 · ' + edits.length + ' 次改动'),
        h('div', { key: 'b', className: 'cddl-rail-body' },
          rows.map(function (row, i) {
            var node = shared.graph.nodes[row.id]
            var editing = verbOf(row.verb) === 'editing'
            // The thread runs only between the first and the last edit, so a
            // long tail of reads does not trail a line behind it.
            var threaded = firstEdit >= 0 && i >= firstEdit && i <= lastEdit
            return h('div', {
              key: row.turn + ':' + row.step + ':' + row.id,
              className: 'cddl-rail-row'
                + (editing ? ' cddl-rail-edit' : '')
                + (threaded ? ' cddl-rail-thread' : '')
                + (shared.selected === row.id ? ' cddl-rail-on' : ''),
            }, [
              h('div', { key: 'a', className: 'cddl-rail-at' }, [
                h('b', { key: 't' }, 't' + row.turn + ':step' + row.step),
                h('span', { key: 'v', className: editing ? 'cddl-rail-verb-e' : 'cddl-rail-verb' },
                  verbOf(row.verb)),
              ]),
              node === undefined
                ? h('div', { key: 'n', className: 'cddl-rail-gone' }, row.id.split('::').pop())
                : h(GraphNode, {
                  key: 'n', flow: true, engine: engine, zoom: 1,
                  p: {
                    id: row.id, node: node, anchor: node.anchor, file: node.anchor.file,
                    x: 0, y: 0, w: width, h: 70, label: label[row.id],
                  },
                }),
            ])
          })),
      ])
    }

    module.exports = { Stream, stepsOf }
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
    var useRightInset = __state_store.useRightInset
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
      var rightInset = useRightInset(viewRef)
      var reserve = props.docked ? 0 : Math.max(0, rightInset - 16)

      useEffect(function () {
        var escape = function (event) { if (event.key === 'Escape') engine.blurEdge() }
        window.addEventListener('keydown', escape)
        return function () { window.removeEventListener('keydown', escape) }
      }, [])

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
          className: 'cddl-canvas',
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
                className: 'cddl-filebox',
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
                style: { top: (row.y - 24) + 'px' },
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
      var canvasRef = view.canvasRef
      var centerOn = view.centerOn
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

      return h('div', { className: 'cddl-toolbar', key: 't' }, [
          h('div', { key: 'seg', className: 'cddl-seg' }, [
            h('button', { key: 'g', className: tab[0] === 'graph' ? 'on' : '', onClick: function () { tab[1]('graph') } }, '逻辑图'),
            h('button', { key: 'o', className: tab[0] === 'outline' ? 'on' : '', onClick: function () { tab[1]('outline') } }, '目录'),
            h('button', { key: 'd', className: tab[0] === 'draw' ? 'on' : '', onClick: function () { tab[1]('draw') } }, 'cdd draw'),
          ]),
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
          h('button', {
            key: 'w', className: 'cddl-btn', title: '按宽度铺满，纵向滚动',
            onClick: function () {
              var el = canvasRef.current
              if (el === null || model.width === 0) return
              var next = Math.round(Math.min(1.4, Math.max(.5, (el.clientWidth - 32) / model.width)) * 100) / 100
              setZoom(next)
              window.requestAnimationFrame(function () {
                window.requestAnimationFrame(function () { centerOn(shared.selected || shared.graph.rootId, next) })
              })
            },
          }, '铺满宽度'),
          h('button', {
            key: 'float', className: 'cddl-btn',
            onClick: function () {
              if (props.docked) {
                shared.dockOpen = false
                shared.wantFloat = (shared.wantFloat || 0) + 1
                publish()
              } else {
                openDockBesideChat(ctx)
              }
            },
          }, props.docked ? '收进浮窗 ⤡' : '并排 Chat ⤢'),
          h('button', {
            key: 'r', className: 'cddl-btn',
            onClick: function () { engine.reindex() },
          }, shared.reindexing ? '建索引…' : '↻ 重建索引'),
          h('button', {
            key: 'w', className: 'cddl-btn' + (shared.wireMode === 'all' ? ' on' : ''),
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
    var __view_stream = require('dsh-cdd-lens/view/stream')
    var Stream = __view_stream.Stream
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
        // The rail carries the order things happened in; the canvas carries what
        // is related to what. They are two different questions and neither answers
        // the other, so they sit side by side rather than one pretending to be both.
        h('div', { key: 'st', className: 'cddl-stage' + (shared.focused ? ' cddl-stage-detail' : '') }, [
          h(Stream, { key: 'rail', engine: engine }),
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
                if (!moved) engine.blurEdge()
              }
              el.style.cursor = 'grabbing'
              window.addEventListener('pointermove', move)
              window.addEventListener('pointerup', up)
            },
          }, canvas),
          h(HScroll, { key: 'hs', canvasRef: canvasRef, width: model.width, zoom: zoom[0] }),
          shared.focused ? h('div', { key: 'p', className: 'cddl-sidepanel' }, [
            h(Source, { key: 's', engine: engine }),
            h(History, { key: 'h' }),
          ]) : null,
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
    var __shell_panel = require('dsh-cdd-lens/shell/panel')
    var LensPanel = __shell_panel.LensPanel
    var __shell_graph_iew = require('dsh-cdd-lens/shell/graphView')
    var LensView = __shell_graph_iew.LensView

    var DOCK_WIDTH_KEY = 'cdd-lens.dock-width'

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
        h(LensPanel, { key: 'panel', ctx: props.ctx }),
        h(LensDock, { key: 'dock', ctx: props.ctx }),
      ])
    }

    module.exports = { DOCK_WIDTH_KEY, loadDockWidth, LensDock, LensOverlay }
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
      '.cddl-root{position:absolute;right:16px;bottom:16px;pointer-events:none;',
      'display:flex;flex-direction:column;align-items:flex-end;gap:8px;z-index:400}',
      'body:has(.cddl-view) .cddl-root{display:none}',
      'body:has(.cddl-dock-open) #root{margin-right:var(--cddl-dock-width,640px);transition:margin-right .16s ease}',
      '.cddl-dock{position:fixed;right:0;top:0;bottom:0;z-index:480;pointer-events:auto;min-width:420px;max-width:78vw;',
      'display:flex;flex-direction:column;background:var(--dsw-alias-bg-layer-1);border-left:1px solid var(--dsw-alias-border-l3);',
      'box-shadow:-12px 0 32px rgba(0,0,0,.28)}',
      '.cddl-dock-resize{position:absolute;left:-6px;top:0;bottom:0;width:12px;cursor:ew-resize;z-index:6}',
      '.cddl-dock-resize:hover{background:color-mix(in srgb,var(--dsw-alias-state-business-primary) 28%,transparent)}',
      '.cddl-dock-head{height:38px;box-sizing:border-box;padding:0 10px;display:flex;align-items:center;gap:9px;flex:none;',
      'border-bottom:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-2)}',
      '.cddl-dock>.cddl-view{flex:1;min-height:0;height:auto;padding-bottom:0}',
      '.cddl-card{pointer-events:auto;position:relative;max-height:min(78vh,760px);display:flex;flex-direction:column;',
      'background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l2);border-radius:11px;',
      'box-shadow:var(--dsw-elevation-panel,0 12px 34px rgba(0,0,0,.5));overflow:hidden;',
      'color:var(--dsw-alias-label-primary);font-family:var(--dsw-font-family,inherit);font-size:12px;line-height:1.6}',
      '.cddl-pill{pointer-events:auto;cursor:pointer;padding:6px 12px;border-radius:999px;display:flex;gap:6px;align-items:center;',
      'background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l2);',
      'box-shadow:var(--dsw-elevation-panel,0 6px 18px rgba(0,0,0,.4));color:var(--dsw-alias-label-secondary);',
      'font-family:var(--dsw-font-family,inherit);font-size:12px}',
      '.cddl-pill:hover{color:var(--dsw-alias-label-primary)}',
      '.cddl-pilln{background:var(--dsw-alias-bg-layer-3);border-radius:9px;padding:0 6px;font-size:10px}',

      '.cddl-grip{position:absolute;left:0;top:0;bottom:0;width:6px;cursor:ew-resize;z-index:2}',
      '.cddl-grip:hover{background:var(--dsw-alias-border-l3)}',
      '.cddl-head{cursor:grab;user-select:none;display:flex;align-items:center;gap:8px;padding:9px 12px;',
      'border-bottom:1px solid var(--dsw-alias-border-l1);flex:none}',
      '.cddl-title{font-size:12.5px;font-weight:600}',
      '.cddl-meta{font-family:var(--ds-font-family-code,monospace);font-size:10.5px;',
      'color:var(--dsw-alias-label-caption);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddl-spacer{flex:1}',
      '.cddl-bad{color:var(--dsw-alias-state-error-primary);font-size:10.5px}',
      '.cddl-btn{border:1px solid var(--dsw-alias-border-l2);background:transparent;',
      'color:var(--dsw-alias-label-tertiary);border-radius:5px;font-size:11px;padding:2px 7px;',
      'cursor:pointer;font-family:inherit;white-space:nowrap}',
      '.cddl-btn:hover{background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}',
      '.cddl-primary{border:1px solid var(--dsw-alias-border-l3);background:var(--dsw-alias-bg-layer-3);',
      'color:var(--dsw-alias-label-primary);border-radius:6px;font-size:11.5px;padding:4px 12px;',
      'cursor:pointer;font-family:inherit;margin-top:8px}',
      '.cddl-primary:disabled{opacity:.5;cursor:default}',

      '.cddl-tabs{display:flex;gap:2px;padding:6px 12px 0;border-bottom:1px solid var(--dsw-alias-border-l1);flex:none}',
      '.cddl-tabs button{background:transparent;border:0;border-bottom:2px solid transparent;cursor:pointer;',
      'padding:4px 10px;font-size:11.5px;color:var(--dsw-alias-label-caption);font-family:inherit}',
      '.cddl-tabs button.on{color:var(--dsw-alias-label-primary);border-bottom-color:var(--dsw-alias-state-business-primary)}',

      '.cddl-search{position:relative;padding:8px 12px 0;flex:none}',
      '.cddl-q{width:100%;box-sizing:border-box;background:var(--dsw-alias-bg-layer-1);',
      'border:1px solid var(--dsw-alias-border-l2);border-radius:6px;padding:4px 9px;',
      'font-size:11.5px;color:var(--dsw-alias-label-primary);font-family:inherit;outline:none}',
      '.cddl-q::placeholder{color:var(--dsw-alias-label-dimmed)}',
      '.cddl-hits{position:absolute;left:12px;right:12px;top:100%;z-index:3;max-height:280px;overflow:auto;',
      'background:var(--dsw-alias-bg-layer-3);border:1px solid var(--dsw-alias-border-l2);border-radius:7px;',
      'box-shadow:0 8px 22px rgba(0,0,0,.45);padding:4px}',
      '.cddl-hit{display:flex;align-items:baseline;gap:8px;padding:4px 7px;border-radius:5px;cursor:pointer}',
      '.cddl-hit:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-hitfile{margin-left:auto;font-family:var(--ds-font-family-code,monospace);font-size:10px;',
      'color:var(--dsw-alias-label-caption)}',

      '.cddl-body{flex:1;min-height:120px;overflow:auto}',
      '.cddl-tree{padding:8px 10px 10px}',
      '.cddl-filehdr{font-family:var(--ds-font-family-code,monospace);font-size:10px;',
      'color:var(--dsw-alias-label-caption);margin:8px 0 3px}',
      '.cddl-node{display:flex;align-items:center;gap:6px;padding:3px 6px;border-radius:6px;cursor:pointer}',
      '.cddl-node:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-sel{background:var(--dsw-alias-interactive-bg-active)}',
      '.cddl-ind{flex:none}',
      '.cddl-twist{width:14px;flex:none;color:var(--dsw-alias-label-dimmed);font-size:9px;text-align:center;',
      'background:transparent;border:0;cursor:pointer;padding:0;font-family:inherit}',
      '.cddl-twist:hover{color:var(--dsw-alias-label-primary)}',
      '.cddl-dot{width:7px;height:7px;border-radius:50%;flex:none;background:var(--dsw-alias-label-dimmed);display:inline-block}',
      '.cddl-dot.cddl-v{background:var(--dsw-alias-state-business-primary)}',
      '.cddl-dot.cddl-e{background:var(--dsw-alias-state-warn-primary)}',
      '.cddl-dot.cddl-w{background:var(--dsw-alias-state-error-primary);box-shadow:0 0 0 3px rgba(242,90,90,.2)}',
      '.cddl-sym{font-family:var(--ds-font-family-code,monospace);font-size:11.5px;',
      'color:var(--dsw-alias-label-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddl-sel .cddl-sym{color:var(--dsw-alias-label-primary)}',
      '.cddl-kind{font-size:9.5px;color:var(--dsw-alias-label-caption);flex:none;',
      'border:1px solid var(--dsw-alias-border-l2);border-radius:3px;padding:0 3px;white-space:nowrap}',
      '.cddl-turn{font-family:var(--ds-font-family-code,monospace);font-size:9.5px;flex:none;',
      'padding:0 5px;border-radius:9px;border:1px solid transparent;white-space:nowrap}',
      '.cddl-turn.cddl-v{color:var(--dsw-alias-state-business-primary);border-color:var(--dsw-alias-state-business-tertiary)}',
      '.cddl-turn.cddl-e{color:var(--dsw-alias-state-warn-primary);border-color:var(--dsw-alias-state-warn-tertiary)}',
      '.cddl-turn.cddl-w{color:var(--dsw-alias-state-error-primary);border-color:var(--dsw-alias-state-error-secondary)}',
      '.cddl-lines{font-family:var(--ds-font-family-code,monospace);font-size:9.5px;',
      'color:var(--dsw-alias-label-dimmed);margin-left:auto;flex:none;padding-left:6px;white-space:nowrap}',
      '.cddl-hop{margin-left:auto;display:flex;gap:2px;flex:none;opacity:.55}',
      '.cddl-node:hover .cddl-hop,.cddl-sel .cddl-hop{opacity:1}',
      '.cddl-hop button{font-size:10px;font-family:var(--ds-font-family-code,monospace);cursor:pointer;',
      'color:var(--dsw-alias-label-caption);background:transparent;',
      'border:1px solid var(--dsw-alias-border-l2);border-radius:4px;padding:0 4px}',
      '.cddl-hop button:hover{color:var(--dsw-alias-label-primary);background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-hop button.on{color:var(--dsw-alias-label-primary);border-color:var(--dsw-alias-border-l4)}',
      // Compaction took the verbatim evidence back: pale, not gone.
      '.cddl-faded{opacity:.4}',
      '.cddl-faded .cddl-sym{font-style:italic}',
      '.cddl-island{border-left:2px dashed var(--dsw-alias-border-l3)}',
      '.cddl-bridge .cddl-sym{color:var(--dsw-alias-label-caption)}',
      '.cddl-bridgetag{border-style:dashed;opacity:.8}',
      '.cddl-gap{display:flex;align-items:center;gap:7px;padding:6px 4px;',
      'color:var(--dsw-alias-label-caption);font-size:10px}',
      '.cddl-gap i{flex:1;height:1px;background:repeating-linear-gradient(90deg,',
      'var(--dsw-alias-label-dimmed) 0 3px,transparent 3px 7px)}',

      '.cddl-dir,.cddl-fileitem,.cddl-symitem{display:flex;align-items:center;gap:6px;',
      'padding:3px 6px;border-radius:6px;cursor:pointer;font-size:11.5px}',
      '.cddl-dir{color:var(--dsw-alias-label-secondary);font-family:var(--ds-font-family-code,monospace)}',
      '.cddl-fileitem{padding-left:20px;color:var(--dsw-alias-label-caption);font-family:var(--ds-font-family-code,monospace)}',
      '.cddl-symitem{padding-left:38px}',
      '.cddl-dir:hover,.cddl-fileitem:hover,.cddl-symitem:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-count{margin-left:auto;font-family:var(--ds-font-family-code,monospace);font-size:10px;',
      'color:var(--dsw-alias-label-dimmed);flex:none}',
      '.cddl-sub{padding-left:38px;color:var(--dsw-alias-label-dimmed);font-size:11px}',

      '.cddl-empty{padding:18px 14px;color:var(--dsw-alias-label-tertiary);font-size:11.5px;line-height:1.8}',
      '.cddl-path{font-family:var(--ds-font-family-code,monospace);font-size:10.5px;',
      'color:var(--dsw-alias-label-caption);word-break:break-all;margin:4px 0}',
      '.cddl-progress{color:var(--dsw-alias-label-caption);font-size:11px;margin-top:6px}',
      '.cddl-tail{font-family:var(--ds-font-family-code,monospace);font-size:10px;',
      'color:var(--dsw-alias-label-dimmed);max-height:90px;overflow:auto;margin-top:8px;white-space:pre-wrap}',

      '.cddl-legend{display:flex;flex-wrap:wrap;gap:12px;padding:8px 12px;flex:none;',
      'border-top:1px solid var(--dsw-alias-border-l1);font-size:10.5px;color:var(--dsw-alias-label-caption)}',
      '.cddl-legend b{font-weight:400;display:flex;align-items:center;gap:5px}',
      '.cddl-swatch{display:inline-block;width:18px;height:0;border-top:1.5px solid var(--dsw-alias-border-l4)}',
      '.cddl-swatch.cddl-dataflow{border-top-style:dashed}',
      '.cddl-swatch.cddl-inherit{border-top-style:dotted}',
      '.cddl-swatch.cddl-impact{border-top:2px dotted var(--dsw-alias-border-l3)}',
      '.cddl-swatch.cddl-dispatch{border-top:2px dashed var(--dsw-alias-border-l4)}',

      '.cddl-src{border-top:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);flex:none}',
      '.cddl-srch{font-family:var(--ds-font-family-code,monospace);font-size:10px;padding:8px 8px 4px 12px;',
      'color:var(--dsw-alias-label-caption);word-break:break-all;display:flex;align-items:flex-start;gap:8px}',
      '.cddl-srch>span{min-width:0;flex:1}',
      '.cddl-src-close{flex:none;width:24px;height:24px;border:1px solid var(--dsw-alias-border-l2);border-radius:5px;',
      'background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-caption);cursor:pointer;font-size:16px;line-height:18px}',
      '.cddl-src pre{margin:0;padding:0 12px 10px;font-family:var(--ds-font-family-code,monospace);',
      'font-size:10.5px;line-height:1.65;color:var(--dsw-alias-label-tertiary);max-height:180px;overflow:auto}',
      '.cddl-hl{background:var(--dsw-alias-state-warn-tertiary);display:block;margin:0 -12px;padding:0 12px;',
      'border-left:2px solid var(--dsw-alias-state-warn-primary)}',
      '.cddl-ln{color:var(--dsw-alias-label-dimmed);user-select:none;display:inline-block;width:34px}',
      '.cddl-code{white-space:pre}',
      '.cddl-hist{border-top:1px solid var(--dsw-alias-border-l1);padding:8px 12px;flex:none}',
      '.cddl-hist h4{margin:0 0 5px;font-size:10.5px;color:var(--dsw-alias-label-caption);font-weight:500}',
      '.cddl-unres{margin:10px 10px 4px;padding:8px 10px;border-radius:8px;',
      'border:1px dashed var(--dsw-alias-border-l3);background:var(--dsw-alias-bg-layer-1)}',
      '.cddl-unres h4{display:flex;align-items:center;gap:6px}',
      '.cddl-rank{font-family:var(--ds-font-family-code,monospace);font-size:9px;flex:none;',
      'width:15px;text-align:right;color:var(--dsw-alias-label-dimmed)}',
      '.cddl-rank-none{color:transparent}',
      '.cddl-hop button.cddl-off{opacity:.3;cursor:default}',
      '.cddl-hop button.cddl-off:hover{background:transparent;color:var(--dsw-alias-label-caption)}',
      '.cddl-unres h4{margin:0 0 5px;font-size:10.5px;color:var(--dsw-alias-label-caption);font-weight:500}',
      '.cddl-unrow{display:flex;align-items:center;gap:7px;padding:1px 0;opacity:.75}',
      '.cddl-hrow{display:flex;align-items:center;gap:7px;font-size:11px;',
      'color:var(--dsw-alias-label-tertiary);padding:1px 0}',
      '.cddl-agent{font-family:var(--ds-font-family-code,monospace);color:var(--dsw-alias-state-business-primary)}',
      '.cddl-reason{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--dsw-alias-label-secondary)}',
      '.cddl-t{font-family:var(--ds-font-family-code,monospace);font-size:10px;',
      'color:var(--dsw-alias-label-caption);width:26px;flex:none}',

      // ---- the spread-out view ----
      '.cddl-view{--cddl-bottom-clearance:calc(var(--dsh-composer-height,152px) + 16px);',
      'display:flex;flex-direction:column;height:100%;min-height:0;width:100%;box-sizing:border-box;',
      'padding-bottom:var(--cddl-bottom-clearance);overflow:hidden;',
      'background:var(--dsw-alias-bg-layer-1);color:var(--dsw-alias-label-primary);',
      'font-family:var(--dsw-font-family,inherit);font-size:12px}',
      '.cddl-view-docked{--cddl-bottom-clearance:0px}',
      '.cddl-toolbar{display:flex;align-items:center;gap:8px;padding:8px 16px;flex:none;flex-wrap:wrap;',
      'border-bottom:1px solid var(--dsw-alias-border-l1)}',
      '.cddl-toolbar .cddl-search{padding:0;width:240px;flex:none}',
      '.cddl-seg{display:flex;border:1px solid var(--dsw-alias-border-l2);border-radius:6px;overflow:hidden;flex:none}',
      '.cddl-seg button{padding:3px 11px;font-size:11.5px;background:transparent;border:0;cursor:pointer;',
      'color:var(--dsw-alias-label-caption);border-right:1px solid var(--dsw-alias-border-l2);font-family:inherit}',
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
      '.cddl-canvaswrap{grid-column:1;grid-row:1;position:relative;overflow:auto;',
      'scrollbar-gutter:stable;',
      'background:radial-gradient(circle at 1px 1px, var(--dsw-alias-border-l1) 1px, transparent 0) 0 0/22px 22px,',
      'var(--dsw-alias-bg-base)}',
      '.cddl-canvaswrap::-webkit-scrollbar{width:12px;height:12px}',
      '.cddl-hscroll{grid-column:1;grid-row:2;align-self:end;position:relative;height:12px;margin:0 2px 2px;',
      'border-radius:6px;background:var(--dsw-alias-scrollbar-bg-l2,rgba(127,127,127,.10));cursor:pointer;z-index:3}',
      '.cddl-hscroll-thumb{position:absolute;top:2px;bottom:2px;border-radius:5px;',
      'background:var(--dsw-alias-border-l4);pointer-events:none}',
      '.cddl-hscroll:hover .cddl-hscroll-thumb{background:var(--dsw-alias-label-caption)}',
      '.cddl-canvaswrap::-webkit-scrollbar-track{background:var(--dsw-alias-scrollbar-bg-l2,rgba(127,127,127,.08))}',
      '.cddl-canvaswrap::-webkit-scrollbar-thumb{background:var(--dsw-alias-border-l4);border-radius:7px;',
      'border:3px solid transparent;background-clip:content-box}',
      '.cddl-canvaswrap::-webkit-scrollbar-thumb:hover{background:var(--dsw-alias-scrollbar-hover-l2,var(--dsw-alias-label-caption));',
      'background-clip:content-box}',
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
      '.cddl-edge-label{font-family:var(--ds-font-family-code,monospace);font-size:9px;',
      'fill:var(--dsw-alias-label-dimmed);paint-order:stroke;stroke:var(--dsw-alias-bg-base);stroke-width:3px}',
      '.cddl-rowlabels{position:absolute;inset:0;pointer-events:none}',
      '.cddl-rowlabel{position:absolute;left:16px;font-size:9.5px;letter-spacing:.06em;text-transform:uppercase;',
      'color:var(--dsw-alias-label-dimmed);font-family:var(--ds-font-family-code,monospace)}',
      '.cddl-rowlabel.cddl-island-label{padding-top:8px;border-top:1px dashed var(--dsw-alias-border-l2);right:16px}',
      '.cddl-chips{position:absolute;inset:0;pointer-events:none}',
      '.cddl-chip{position:absolute;padding:2px 8px;border-radius:999px;border:1px dashed var(--dsw-alias-border-l3);',
      'background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-caption);font-size:9.5px;',
      'font-family:var(--ds-font-family-code,monospace)}',
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
      '.cddl-filebox{position:absolute;box-sizing:border-box;border:2px dashed var(--dsw-alias-border-l4);',
      'border-radius:14px;background:color-mix(in srgb,var(--dsw-alias-bg-layer-2) 34%,transparent)}',
      '.cddl-filebox strong{position:absolute;left:14px;top:10px;max-width:390px;overflow:hidden;',
      'text-overflow:ellipsis;white-space:nowrap;font:700 12px var(--ds-font-family-code,monospace);',
      'color:var(--dsw-alias-label-primary)}',
      '.cddl-filebox span{position:absolute;right:14px;top:10px;font:10px var(--ds-font-family-code,monospace);',
      'color:var(--dsw-alias-label-caption)}',
      '.cddl-nodes{position:relative}',
      '.cddl-rail{width:var(--cddl-rail-w,300px);flex:none;display:flex;flex-direction:column;',
      'border-right:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-1);min-height:0}',
      '.cddl-rail-head{padding:6px 10px;font-size:10.5px;color:var(--dsw-alias-label-tertiary);',
      'border-bottom:1px solid var(--dsw-alias-border-l1);flex:none}',
      '.cddl-rail-body{overflow:auto;padding:6px 10px 14px;display:flex;flex-direction:column;gap:6px}',
      '.cddl-rail-empty{padding:14px 12px;font-size:11.5px;color:var(--dsw-alias-label-tertiary)}',
      '.cddl-rail-row{position:relative;padding-left:12px}',
      '.cddl-rail-at{display:flex;align-items:baseline;gap:6px;font-size:9.5px;margin-bottom:2px;',
      'font-family:var(--ds-font-family-code,ui-monospace,monospace)}',
      '.cddl-rail-at b{font-weight:500;color:var(--dsw-alias-label-tertiary)}',
      '.cddl-rail-verb{color:var(--dsw-alias-label-quaternary)}',
      '.cddl-rail-verb-e{color:var(--dsw-alias-state-warn-primary)}',
      // Only the edits are threaded. Two reads in a row means they were read in
      // a row and nothing else; drawing that would invent a relation.
      '.cddl-rail-thread::before{content:\'\';position:absolute;left:3px;top:0;bottom:-6px;',
      'width:1px;background:var(--dsw-alias-border-l3)}',
      '.cddl-rail-edit::after{content:\'\';position:absolute;left:0;top:14px;width:7px;height:7px;',
      'border-radius:50%;background:var(--dsw-alias-state-warn-primary)}',
      '.cddl-rail-on .cddl-gnode{outline:1px solid var(--dsw-alias-state-business-primary)}',
      '.cddl-rail-gone{font-size:11px;color:var(--dsw-alias-label-quaternary);padding:3px 0}',
      '.cddl-node-shell{position:absolute}',
      '.cddl-node-flow{position:static;flex:none}',
      '.cddl-node-flow .cddl-port{display:none}',
      '.cddl-port{position:absolute;top:50%;z-index:4;width:24px;height:20px;box-sizing:border-box;',
      'display:flex;align-items:center;justify-content:center;transform:translateY(-50%);border-radius:4px;',
      'font:800 10px var(--ds-font-family-code,monospace);background:var(--dsw-alias-bg-layer-3);',
      'box-shadow:0 0 0 2px var(--dsw-alias-bg-base)}',
      '.cddl-port-left{left:-29px}.cddl-port-right{right:-29px}',
      '.cddl-port-in{color:var(--dsw-alias-state-business-primary);border:1px solid var(--dsw-alias-state-business-primary)}',
      '.cddl-port-out{color:var(--dsw-alias-state-warn-primary);border:1px solid var(--dsw-alias-state-warn-primary)}',
      '.cddl-node-actions{display:flex;gap:4px;margin-top:4px;z-index:2}',
      '.cddl-node-actions button{font-size:10px}',
      '.cddl-node-shell:hover .cddl-node-actions,.cddl-node-shell:focus-within .cddl-node-actions{opacity:1}',
      '.cddl-node-actions button{min-width:26px;height:19px;padding:0 5px;border-radius:5px;cursor:pointer;',
      'font:700 11px var(--ds-font-family-code,monospace);color:var(--dsw-alias-state-business-primary);',
      'background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-state-business-tertiary)}',
      '.cddl-node-actions .cddl-action-collapse:not(:disabled){color:var(--dsw-alias-state-warn-primary);',
      'border-color:var(--dsw-alias-state-warn-tertiary)}',
      '.cddl-node-actions button:hover:not(:disabled),.cddl-node-actions button.on{color:var(--dsw-alias-label-primary);',
      'border-color:var(--dsw-alias-border-l4);background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-node-actions button:disabled{opacity:.34;cursor:default}',
      '.cddl-action-help{font-family:var(--ds-font-family-code,monospace);font-weight:600!important}',
      '.cddl-action-help-plus{color:var(--dsw-alias-state-business-primary)!important}',
      '.cddl-action-help-minus{color:var(--dsw-alias-state-warn-primary)!important}',
      '.cddl-gnode{position:relative;box-sizing:border-box;width:100%;background:var(--dsw-alias-bg-layer-2);',
      'border:1px solid var(--dsw-alias-border-l2);border-radius:8px;padding:7px 10px;cursor:grab;touch-action:none;',
      'box-shadow:0 2px 10px rgba(0,0,0,.3)}',
      '.cddl-gnode:hover{border-color:var(--dsw-alias-border-l4)}',
      '.cddl-gnode.cddl-sel{border-color:var(--dsw-alias-state-warn-primary);',
      'box-shadow:0 0 0 1px var(--dsw-alias-state-warn-tertiary),0 6px 18px rgba(0,0,0,.45)}',
      '.cddl-gnode.cddl-island{border-style:dashed}',
      '.cddl-gnode.cddl-cls{background:var(--dsw-alias-bg-layer-1);border-width:1.5px}',
      '.cddl-gnode.cddl-cls .cddl-gtop{padding-bottom:2px}',
      '.cddl-gnode .cddl-sym{overflow:visible;text-overflow:clip;white-space:nowrap;font-size:13.5px;font-weight:500}',
      '.cddl-gfile{font-family:var(--ds-font-family-code,monospace);font-size:9.5px;',
      'color:var(--dsw-alias-label-caption);margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddl-gtop{display:flex;align-items:center;gap:6px;flex-wrap:nowrap}',
      '.cddl-gnode .cddl-count{background:var(--dsw-alias-bg-layer-3);border:1px solid var(--dsw-alias-border-l2);',
      'border-radius:9px;padding:0 6px;cursor:pointer;color:var(--dsw-alias-label-tertiary);font-size:10px}',
      '.cddl-members{margin-top:6px;border-top:1px solid var(--dsw-alias-border-l1);padding-top:5px}',
      '.cddl-m{display:flex;align-items:center;gap:6px;padding:2px 4px;border-radius:5px}',
      '.cddl-m:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-more{font-size:10px;color:var(--dsw-alias-label-caption);padding:5px 4px 0;text-align:right}',
      '.cddl-working{margin-top:6px;padding:4px 6px;border-radius:5px;font-size:10px;',
      'color:var(--dsw-alias-state-error-primary);background:var(--dsw-alias-state-error-tertiary);',
      'white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddl-ghop{display:flex;gap:3px;margin-top:2px;line-height:1.25}',
      '.cddl-ghop button{font-size:10px;font-family:var(--ds-font-family-code,monospace);cursor:pointer;',
      'color:var(--dsw-alias-label-caption);background:transparent;',
      'border:1px solid var(--dsw-alias-border-l2);border-radius:4px;padding:0 5px}',
      '.cddl-ghop button:hover{color:var(--dsw-alias-label-primary);background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-ghop button.on{color:var(--dsw-alias-label-primary);border-color:var(--dsw-alias-border-l4)}',
      '.cddl-sidepanel{position:absolute;z-index:12;right:0;top:0;bottom:0;width:min(440px,55%);',
      'border-left:1px solid var(--dsw-alias-border-l2);box-shadow:-10px 0 28px rgba(0,0,0,.14);',
      'background:var(--dsw-alias-bg-layer-1);overflow:auto}',
      '.cddl-sidepanel .cddl-src pre{max-height:none}',
      '@media (max-width:900px){.cddl-sidepanel{width:min(420px,72%)}',
      '.cddl-toolbar .cddl-search{width:190px}.cddl-meta{max-width:180px}}',
    ]

    module.exports = { GRAPH_CSS }
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
          function () { return h(LensView, { ctx: ctx }) })
      })
    }

    module.exports = { name: 'cdd-lens', inject: ['slots', 'sessions', 'uiConversation', 'layout'], apply: apply }
    return module.exports
  },
})
