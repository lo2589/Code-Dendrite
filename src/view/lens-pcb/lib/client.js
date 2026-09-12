// dsh-cdd-lens-pcb — browser half.
//
// Two views over one store:
//
//   * a floating panel in `shell.overlay` — a frame-wide layer above every
//     column, click-through by default so the conversation underneath stays
//     fully usable. Not covering the chat is structural here, not a thing this
//     code is careful about.
//   * a full-width graph in `conversation.view`, the tab row beside Chat and
//     Trajectory, for when you actually want to spread it out.
//
// The graph's skeleton is CodeDendrite's real relations. The session only ever
// paints on it: an anchor is blue because a `read` settled on it, orange
// because an `edit` did, dimmed because compaction took the verbatim evidence
// back off the model's surface. Two anchors the agent touched in sequence are
// NOT joined unless the code actually joins them — an unconnected jump renders
// as an island, because that disconnection is information.
//
// Written by hand in the shape tsdown emits (`__ModuleLoader__.load` + a CJS
// body + the loader's `require`), so the generated bundle drops in on top.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens-pcb',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef

    // Inlined from build.json. The host greps this file for the stamp it read
    // from disk, so a drift shows up in /health as clientBundleMatchesBuild:false
    // rather than as mysterious behaviour.
    var BUILD = 'V1_18_NO_SOURCE_PANE_006'
    var ROUTE = '/plugins/cdd-lens-pcb'

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

    // ---- shared session store --------------------------------------------
    //
    // One hook drives both views, so switching between the floating panel and
    // the spread-out tab keeps the same exploration instead of resetting it.

    var shared = {
      graph: emptyGraph(),
      trace: {},
      turn: 0,
      selected: null,
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
     * How much of THIS element's right edge something else is sitting on.
     *
     * `useRightInset` answers a different question: how much of the WINDOW's
     * right edge is spoken for. That is right for anything `position: fixed`,
     * which is placed against the window. It is wrong for a view living inside
     * the frame's middle column — the grid has already subtracted the details
     * track, so paying for it again padded the view by a few hundred pixels of
     * nothing. That dead white strip is what this exists to stop.
     *
     * Nothing overlapping means zero: when a neighbour closes, the width comes
     * straight back with no separate teardown.
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
          var overlay = document.querySelector('[data-shell-overlay]')
          if (overlay !== null) {
            var kids = overlay.querySelectorAll('*')
            for (var i = 0; i < kids.length; i += 1) {
              var node = kids[i]
              if (node === mine || mine.contains(node) || node.contains(mine)) continue
              var style = window.getComputedStyle(node)
              if (style.position !== 'fixed' && style.position !== 'absolute') continue
              if (style.visibility === 'hidden' || style.display === 'none') continue
              var r = node.getBoundingClientRect()
              if (r.width < 80 || r.height < 240) continue
              if (r.left >= rect.right || r.right <= rect.left) continue
              if (r.top >= rect.bottom || r.bottom <= rect.top) continue
              if (r.right < rect.right - 8) continue
              var bite = rect.right - Math.max(rect.left, r.left)
              if (bite > covered) covered = bite
            }
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
    var PLACE_KEY = 'cdd-lens-pcb.placement'

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

    /**
     * The panel may fill the window but never leave it. Every placement passes
     * through here, measured against the live window and the panel's own size:
     * a stale offset from localStorage or a drag past the edge clamps back on
     * screen instead of sinking half the panel below it — a restart used to
     * bring the half-buried panel straight back, because the position outlived
     * the process.
     */
    function clampPlacement(place, rightInset, panelH) {
      var W = window.innerWidth
      var H = window.innerHeight
      var minDx = 8 - rightInset
      var maxDx = Math.max(minDx, W - rightInset - place.w - 8)
      var minDy = -8
      var maxDy = panelH > 0 ? Math.max(minDy, H - 24 - panelH) : Math.max(minDy, place.dy)
      return {
        dx: Math.min(Math.max(place.dx, minDx), maxDx),
        dy: Math.min(Math.max(place.dy, minDy), maxDy),
        w: place.w, h: place.h,
      }
    }

    function usePlacement(rootRef, rightInset) {
      var state = useState(loadPlacement)
      var place = state[0]
      var set = state[1]
      var drag = useRef(null)

      var panelH = function () {
        var el = rootRef === undefined || rootRef === null ? null : rootRef.current
        return el === null || el === undefined ? 0 : el.offsetHeight
      }

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
              set(clampPlacement({
                dx: d.dx - (e.clientX - d.x), dy: d.dy - (e.clientY - d.y), w: d.w, h: d.h,
              }, rightInset, panelH()))
            } else {
              var w = Math.max(300, Math.min(900, d.w - (e.clientX - d.x)))
              set(clampPlacement({ dx: d.dx, dy: d.dy, w: w, h: d.h }, rightInset, panelH()))
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

    /** The current session id, read from the sessions list (root-scoped views get no sessionId prop). */
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

    // ---- engine: fetching that both views share ---------------------------

    function makeEngine(ctx) {
      var session = function () { return currentSession(ctx) }
      var params = function (extra) {
        var base = {}
        var id = session()
        if (id !== undefined && id !== null) base.session = String(id)
        if (shared.root !== undefined) base.root = shared.root
        return Object.assign(base, extra || {})
      }

      var engine = {
        params: params,

        context: function () {
          return api('/context', params()).then(function (body) {
            shared.context = body
            shared.root = body.root
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

        /**
         * Make an anchor the exploration root, replacing whatever was there.
         *
         * Also asks both views to show the graph: picking a function in the
         * directory is a request to SEE it, and leaving the panel on the
         * directory tab builds the graph where nobody can see it.
         */
        focus: function (anchor) {
          shared.wantGraph = (shared.wantGraph || 0) + 1
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
                    turn: call.turn, verb: touch.verb, tool: touch.tool,
                    approx: touch.approx === true || hit.approx === true,
                    onSurface: call.remembered !== false, working: call.running === true,
                  }
                  if (record === undefined) {
                    byAnchor[anchor.id] = {
                      id: anchor.id, anchor: anchor,
                      firstTurn: call.turn, lastTurn: call.turn, events: [event],
                    }
                  } else {
                    record.firstTurn = Math.min(record.firstTurn, call.turn)
                    record.lastTurn = Math.max(record.lastTurn, call.turn)
                    record.events.push(event)
                  }
                })
              })
            })
            Object.keys(byAnchor).forEach(function (id) {
              var record = byAnchor[id]
              record.events.sort(function (l, r) { return l.turn - r.turn })
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
            if (window.__cddLensPcb !== undefined) {
              var reasons = {}
              shared.unresolved.forEach(function (u) { reasons[u.reason] = (reasons[u.reason] || 0) + 1 })
              window.__cddLensPcb.resolve = {
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
            if (fresh.length === 0) return
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
            })
          }

          if (window.__cddLensPcb !== undefined) window.__cddLensPcb.pending = pending.length
          if (pending.length === 0) { after(); return Promise.resolve() }
          return fetch(ROUTE + '/resolve?' + new URLSearchParams(params()).toString(), {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ root: shared.root, touches: pending }),
          }).then(function (res) { return res.json() }).then(function (body) {
            body.results.forEach(function (entry) { shared.resolved[entry.key] = entry })
            after()
          }).catch(function (error) {
            if (window.__cddLensPcb !== undefined) window.__cddLensPcb.resolveError = String(error && error.message ? error.message : error)
            after()
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
      return engine
    }


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

    // ---- presentation helpers ---------------------------------------------

    /** The state class for an anchor: what the session did to it, if anything. */
    function stateOf(id) {
      var record = shared.trace[id]
      if (record === undefined) return null
      return record
    }

    function dotClass(record) {
      if (record === undefined || record === null) return 'cddlp-dot'
      if (record.state === 'working') return 'cddlp-dot cddlp-w'
      if (record.state === 'edited') return 'cddlp-dot cddlp-e'
      return 'cddlp-dot cddlp-v'
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

    function turnLabel(record) {
      if (record === undefined || record === null) return null
      var verb = record.state === 'working' ? '正在改' : record.state === 'edited' ? '改' : '看'
      var tone = record.state === 'working' ? 'cddlp-w' : record.state === 'edited' ? 'cddlp-e' : 'cddlp-v'
      return h('span', { className: 'cddlp-turn ' + tone, title: '第 ' + record.firstTurn + ' 轮第一次打开' + (record.approx ? '（行号为近似）' : '') },
        'T' + record.firstTurn + ' ' + verb + (record.approx ? '~' : ''))
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
        return h('div', { className: 'cddlp-gap' }, [
          h('i', { key: 'l' }), '碰过但代码里没有边 · 不连', h('i', { key: 'r' }),
        ])
      }
      var anchor = row.member ? row.anchor : row.node.anchor
      var record = stateOf(row.id)
      var faded = record !== null && record !== undefined && !record.remembered
      var selected = shared.selected === row.id
      var cls = 'cddlp-node'
        + (selected ? ' cddlp-sel' : '')
        + (faded ? ' cddlp-faded' : '')
        + (row.node !== undefined && row.node.bridge === true ? ' cddlp-bridge' : '')
        + (row.islandRow ? ' cddlp-island' : '')

      var kids = [
        h('span', { key: 'i', className: 'cddlp-ind', style: { width: (row.depth * 17) + 'px' } }),
      ]
      if (!row.member && (anchor.members > 0)) {
        kids.push(h('button', {
          key: 't', className: 'cddlp-twist', title: anchor.members + ' 个成员',
          onClick: function (e) { e.stopPropagation(); engine.members(row.id) },
        }, row.node.members ? '▾' : '▸'))
      } else {
        kids.push(h('span', { key: 't', className: 'cddlp-twist' }, row.member ? '·' : ''))
      }
      var rank = orderOf(row.id)
      kids.push(rank === null
        ? h('span', { key: 'r', className: 'cddlp-rank cddlp-rank-none' }, '')
        : h('span', { key: 'r', className: 'cddlp-rank', title: '第 ' + rank + ' 个被碰到' }, rank))
      kids.push(h('span', { key: 'd', className: dotClass(record) }))
      kids.push(h('span', { key: 's', className: 'cddlp-sym', title: anchor.id }, anchor.symbol))
      if (!row.member && anchor.members > 0) {
        kids.push(h('span', { key: 'k', className: 'cddlp-kind' }, '类 ' + anchor.members))
      }
      if (row.node !== undefined && row.node.bridge === true) {
        kids.push(h('span', {
          key: 'br', className: 'cddlp-kind cddlp-bridgetag',
          title: 'agent 没打开过它。它出现在这里，是因为代码里它把上下两个碰过的 anchor 连起来了。',
        }, '桥'))
      }
      var badge = turnLabel(record)
      if (badge !== null) kids.push(React.cloneElement(badge, { key: 'b' }))
      if (faded) kids.push(h('span', { key: 'f', className: 'cddlp-kind' }, '压缩'))
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
            + (count === 0 ? ' cddlp-off' : ''),
          onClick: function (e) {
            e.stopPropagation()
            if (count === 0) return
            var direction = dir === 'u' ? 'up' : 'down'
            if (row.node && row.node[direction]) engine.collapse(row.id, direction)
            else engine.expand(row.id, direction)
          },
        }, label + count)
      }
      kids.push(h('span', { key: 'h', className: 'cddlp-hop' }, [
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
        return h('div', { className: 'cddlp-empty' },
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
            key: 'f' + i, className: 'cddlp-filehdr',
            style: { paddingLeft: (row.depth * 17 + 2) + 'px' }, title: anchor.file,
          }, short(anchor.file)))
        }
        out.push(h(TreeRow, { key: row.id + ':' + i, row: row, engine: engine }))
      })
      return h('div', { className: 'cddlp-tree' }, out)
    }

    // ---- the directory view (the `cdd draw` shape: for finding things) -----

    function Outline(props) {
      var engine = props.engine
      var openDir = useState({})
      var dirs = shared.outline
      useEffect(function () { if (dirs === undefined) engine.outline() }, [dirs === undefined])
      if (dirs === undefined) return h('div', { className: 'cddlp-empty' }, '读目录…')
      var out = []
      dirs.forEach(function (entry) {
        var isOpen = openDir[0][entry.dir] === true
        out.push(h('div', {
          key: 'd' + entry.dir, className: 'cddlp-dir',
          onClick: function () {
            var next = Object.assign({}, openDir[0])
            next[entry.dir] = !isOpen
            openDir[1](next)
          },
        }, [
          h('span', { key: 't', className: 'cddlp-twist' }, isOpen ? '▾' : '▸'),
          h('span', { key: 'n' }, entry.dir === '.' ? '(根目录)' : entry.dir + '/'),
          h('span', { key: 'c', className: 'cddlp-count' }, entry.count),
        ]))
        if (!isOpen) return
        entry.files.forEach(function (file) {
          var fileOpen = openDir[0]['f:' + file.file] === true
          out.push(h('div', {
            key: 'f' + file.file, className: 'cddlp-fileitem',
            onClick: function () {
              var next = Object.assign({}, openDir[0])
              next['f:' + file.file] = !fileOpen
              openDir[1](next)
              if (!fileOpen) engine.fileSymbols(file.file)
            },
          }, [
            h('span', { key: 't', className: 'cddlp-twist' }, fileOpen ? '▾' : '▸'),
            h('span', { key: 'n' }, file.file.split('/').pop()),
            h('span', { key: 'c', className: 'cddlp-count' }, file.count),
          ]))
          if (!fileOpen) return
          var symbols = (shared.fileCache || {})[file.file]
          if (symbols === undefined) { out.push(h('div', { key: 'l' + file.file, className: 'cddlp-sub' }, '…')); return }
          symbols.forEach(function (anchor) {
            var record = stateOf(anchor.id)
            out.push(h('div', {
              key: 's' + anchor.id, className: 'cddlp-symitem',
              title: '点开 → 成为逻辑图的起点',
              onClick: function () { engine.focus(anchor) },
            }, [
              h('span', { key: 'd', className: dotClass(record) }),
              h('span', { key: 'n', className: 'cddlp-sym' }, anchor.symbol),
              anchor.members > 0 ? h('span', { key: 'm', className: 'cddlp-kind' }, '类 ' + anchor.members) : null,
              h('span', { key: 'l', className: 'cddlp-lines' }, anchor.start + '–' + anchor.end),
            ]))
          })
        })
      })
      return h('div', { className: 'cddlp-tree' }, out)
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
        return h('div', { className: 'cddlp-empty' }, '正在生成 cdd draw 全图…')
      }
      if (state[0].status === 'error') {
        return h('div', { className: 'cddlp-empty' }, ['cdd draw 生成失败：', state[0].error])
      }
      if (state[0].status === 'loading') return h('div', { className: 'cddlp-empty' }, '载入中…')
      return h('iframe', { className: 'cddlp-frame', src: src, title: 'cdd draw' })
    }

    // ---- source ------------------------------------------------------------

    function Source(props) {
      var id = shared.selected
      if (id === null || id === undefined) return null
      var source = (shared.sourceCache || {})[id]
      var node = shared.graph.nodes[id]
      var anchor = node !== undefined ? node.anchor : null
      if (source === undefined) {
        return h('div', { className: 'cddlp-src' }, h('div', { className: 'cddlp-srch' }, '读源码…'))
      }
      var lines = source.lines.map(function (text, i) {
        var no = source.from + i
        var inside = no >= source.start && no <= source.end
        return h('div', { key: no, className: inside ? 'cddlp-hl' : '' }, [
          h('span', { key: 'n', className: 'cddlp-ln' }, no),
          h('span', { key: 't', className: 'cddlp-code' }, text === '' ? ' ' : text),
        ])
      })
      return h('div', { className: 'cddlp-src' }, [
        h('div', { className: 'cddlp-srch', key: 'h' },
          source.file + ' · ' + (anchor ? anchor.symbol : '') + ' · ' + source.start + '–' + source.end),
        h('pre', { key: 'p' }, lines),
      ])
    }

    /** Every turn that reached this anchor — collapsing a branch never erases it. */
    function History(props) {
      var record = stateOf(shared.selected)
      if (record === undefined || record === null) return null
      return h('div', { className: 'cddlp-hist' }, [
        h('h4', { key: 'h' }, '这个 anchor 的经历'),
      ].concat(record.events.map(function (event, i) {
        return h('div', { key: i, className: 'cddlp-hrow' + (event.onSurface ? '' : ' cddlp-faded') }, [
          h('span', { key: 't', className: 'cddlp-t' }, 'T' + event.turn),
          h('span', { key: 'd', className: dotClass({ state: event.working ? 'working' : event.verb === 'edit' ? 'edited' : 'viewed' }) }),
          h('span', { key: 'x' }, event.tool
            + (event.working ? ' · 正在执行' : '')
            + (event.approx ? ' · 行号近似' : '')
            + (event.onSurface ? '' : ' · 已被压缩')),
          event.agent ? h('span', { key: 'a', className: 'cddlp-agent' }, event.agent) : null,
          event.reason ? h('span', { key: 'r', className: 'cddlp-reason' }, event.reason) : null,
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
      return h('div', { className: 'cddlp-search' }, [
        h('input', {
          key: 'i', className: 'cddlp-q', placeholder: '搜 anchor…',
          value: q[0], onChange: onChange,
          onClick: function (e) { e.stopPropagation() },
        }),
        shared.hits === null || shared.hits === undefined || q[0].trim().length === 0 ? null
          : h('div', { key: 'r', className: 'cddlp-hits' }, shared.hits.length === 0
            ? [h('div', { key: 'n', className: 'cddlp-empty' }, '没找到')]
            : shared.hits.map(function (anchor) {
              return h('div', {
                key: anchor.id, className: 'cddlp-hit',
                onClick: function () { q[1](''); shared.hits = null; engine.focus(anchor) },
              }, [
                h('span', { key: 's', className: 'cddlp-sym' }, anchor.symbol),
                h('span', { key: 'f', className: 'cddlp-hitfile' }, short(anchor.file)),
              ])
            })),
      ])
    }

    // ---- legend ------------------------------------------------------------

    function Legend() {
      return h('div', { className: 'cddlp-legend' }, [
        h('b', { key: 'v' }, [h('i', { key: 'd', className: 'cddlp-dot cddlp-v' }), '看过']),
        h('b', { key: 'e' }, [h('i', { key: 'd', className: 'cddlp-dot cddlp-e' }), '改过']),
        h('b', { key: 'w' }, [h('i', { key: 'd', className: 'cddlp-dot cddlp-w' }), '正在改']),
        h('b', { key: 'call' }, [h('i', { key: 'd', className: 'cddlp-swatch cddlp-call' }), 'call']),
        h('b', { key: 'data' }, [h('i', { key: 'd', className: 'cddlp-swatch cddlp-dataflow' }), 'dataflow']),
        h('b', { key: 'inherit' }, [h('i', { key: 'd', className: 'cddlp-swatch cddlp-inherit' }), 'inherit']),
        h('b', { key: 'impact' }, [h('i', { key: 'd', className: 'cddlp-swatch cddlp-impact' }), 'impact']),
        h('b', { key: 'dispatch' }, [h('i', { key: 'd', className: 'cddlp-swatch cddlp-dispatch' }), 'dispatch']),
        h('b', { key: 'plus', className: 'cddlp-action-help cddlp-action-help-plus' }, '＋N 显示 N 个下游'),
        h('b', { key: 'minus', className: 'cddlp-action-help cddlp-action-help-minus' }, '−N 隐藏 N 个下游'),
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
      return h('div', { className: 'cddlp-unres' }, [
        h('h4', { key: 'h' }, [
          h('span', { key: 't' }, '碰过，但没落到 anchor'),
          h('span', { key: 'n', className: 'cddlp-count' }, list.length),
        ]),
      ].concat(list.slice(0, 12).map(function (entry, i) {
        return h('div', { key: i, className: 'cddlp-unrow', title: entry.file }, [
          h('span', { key: 't', className: 'cddlp-t' }, 'T' + entry.turns.join(',')),
          h('span', { key: 'f', className: 'cddlp-sym' }, short(entry.file)),
          h('span', { key: 'w', className: 'cddlp-kind' }, why[entry.reason] || entry.reason),
        ])
      })))
    }

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
      return h('div', { className: 'cddlp-empty' }, [
        h('div', { key: 'a' }, failed ? '建索引失败：' : '这个工程还没索引，正在建（后台跑，不占聊天）：'),
        h('div', { key: 'b', className: 'cddlp-path' }, context ? context.root : ''),
        failed ? h('div', { key: 'e', className: 'cddlp-bad' }, shared.reindexError) : null,
        failed
          ? h('button', { key: 'c', className: 'cddlp-primary', onClick: function () { engine.reindex() } }, '重试')
          : h('div', { key: 'c', className: 'cddlp-progress' },
            shared.reindexing === false && context && !context.indexed ? '启动中…' : '正在建索引…'),
        shared.reindexTail ? h('pre', { key: 'd', className: 'cddlp-tail' }, shared.reindexTail) : null,
      ])
    }

    /**
     * Subscribe to this session's conversation-view target.
     *
     * The shell owns the subscription and the paging; this only forwards each
     * snapshot into the graph. There is no interval over session data, so
     * nothing here competes with a streaming turn.
     */
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
          window.__cddLensPcb = diag
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

    // ---- the floating panel (shell.overlay) --------------------------------

    function LensPanel(props) {
      var ctx = props.ctx
      useShared()
      var engine = useMemo(function () { return makeEngine(ctx) }, [])
      var open = useState(true)
      var tab = useState('graph')
      var health = useState(null)
      var rootRef = useRef(null)
      var rightInset = useRightInset(rootRef)
      var placement = usePlacement(rootRef, rightInset)

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
        return h('div', { className: 'cddlp-root', ref: rootRef, style: { right: rightInset + 'px' } },
          h('button', { className: 'cddlp-pill', onClick: function () { open[1](true) } },
            ['CDD Lens PCB', shared.turn > 0 ? h('span', { key: 't', className: 'cddlp-pilln' }, Object.keys(shared.trace).length) : null]))
      }

      var context = shared.context
      var body
      if (context === undefined) body = h('div', { className: 'cddlp-empty' }, '连接中…')
      else if (!context.indexed) body = h(NeedIndex, { engine: engine })
      else if (tab[0] === 'outline') body = h(Outline, { engine: engine })
      else if (tab[0] === 'draw') body = h(Draw, { engine: engine })
      else body = h(Tree, { engine: engine })

      var stamp = health[0]
      var mismatch = stamp !== null && stamp.ok && (stamp.body.build !== BUILD || !stamp.body.clientBundleMatchesBuild)

      // Display clamps even where the stored value does not: a position saved
      // on a taller window must not put the panel halfway off a shorter one.
      var shownPlace = clampPlacement(placement.place, rightInset,
        rootRef.current === null || rootRef.current === undefined ? 0 : rootRef.current.offsetHeight)

      return h('div', {
        className: 'cddlp-root', ref: rootRef,
        style: {
          right: (rightInset + shownPlace.dx) + 'px',
          bottom: (16 + shownPlace.dy) + 'px',
        },
      },
        h('div', { className: 'cddlp-card', style: { width: placement.place.w + 'px' } }, [
          h('div', {
            className: 'cddlp-grip', key: 'g', title: '拖这里改宽度',
            onPointerDown: placement.onResizeDown,
          }),
          h('div', {
            className: 'cddlp-head', key: 'h',
            title: '按住标题拖动面板；双击回到右下角',
            onPointerDown: placement.onMoveDown,
            onDoubleClick: placement.reset,
          }, [
            h('span', { className: 'cddlp-title', key: 't' }, 'CDD Lens PCB'),
            h('span', { className: 'cddlp-meta', key: 'm', title: context ? context.root : '' },
              context && context.stats
                ? (context.stats.anchors + ' anchor · ' + context.stats.files + ' 文件')
                : (stamp === null ? '…' : (stamp.ok ? '' : stamp.error))),
            degenerate(context)
              ? h('span', {
                key: 'q', className: 'cddlp-bad',
                title: '这个工程的索引里 ' + context.stats.anchors + ' 个 anchor 只派生出 '
                  + context.stats.edges + ' 条边。多半是扫进了 node_modules / .venv 之类，'
                  + '调用图画不出来。给这个目录加 .codedendrite_ignore 再重建。',
              }, '索引可疑')
              : null,
            mismatch ? h('span', { key: 'w', className: 'cddlp-bad', title: '构建戳对不上：' + stamp.body.build + ' vs ' + BUILD }, '版本不符') : null,
            h('span', { className: 'cddlp-spacer', key: 's' }),
            h('button', {
              key: 'r', className: 'cddlp-btn', title: '重建索引（增量）',
              onPointerDown: function (e) { e.stopPropagation() },
              onClick: function () { engine.reindex() },
            }, shared.reindexing ? '建索引…' : '↻'),
            h('button', {
              key: 'x', className: 'cddlp-btn',
              onPointerDown: function (e) { e.stopPropagation() },
              onClick: function () { open[1](false) },
            }, '—'),
          ]),
          h('div', { className: 'cddlp-tabs', key: 'tb' }, [
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
          h('div', { key: 'b', className: 'cddlp-body' }, [body, h(Unresolved, { key: 'u' })]),
          h(Legend, { key: 'l' }),
          h(Source, { key: 's' }),
          h(History, { key: 'y' }),
        ]))
    }

    // ---- the spread-out graph (conversation.view) ---------------------------
    //
    // A layered layout: callers above the selection, callees below, one row per
    // hop, orthogonal wires. Positions are computed from measured text rather
    // than a physics simulation — a node must not drift when a sibling expands.

    var CHAR = 6.9
    var ROW = 126
    var GAPX = 26
    var MAX_PER_ROW = 4

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
    function layout(graph, relationFilter, avail, placements) {
      var shown = visible(graph)
      if (graph.rootId === null) return { nodes: [], wires: [], labels: [], junctions: [], arrows: [], ports: [], rows: [], files: [], width: 0, height: 0 }

      var sizeOf = function (id) {
        var node = graph.nodes[id]
        return {
          w: NODE_W,
          h: node.members && node.memberList !== undefined
            ? 54 + node.memberList.length * 22 + 16
            : 48,
        }
      }

      // A file is the first visual unit. Session-touched anchors are always
      // present; manual +/- exploration may add more anchors and therefore a
      // new file box, while bridge-only implementation details stay hidden.
      var included = graph.order.filter(function (id) {
        var node = graph.nodes[id]
        return shown[id] && node !== undefined
          && (node.session || node.explored || node.pinned || id === shared.selected || id === graph.rootId)
      })
      if (included.length === 0 && graph.nodes[graph.rootId]) included.push(graph.rootId)
      var byFile = {}
      var fileOrder = []
      included.forEach(function (id) {
        var file = graph.nodes[id].anchor.file
        if (byFile[file] === undefined) { byFile[file] = []; fileOrder.push(file) }
        byFile[file].push(id)
      })
      // Order the boxes so callers sit above callees. Then an arrow pointing up
      // reads "who uses this" and one pointing down reads "what this uses" —
      // the direction carries the meaning, with no row labels needed. Files with
      // no call relation keep their arrival order.
      var fileEdges = []
      graph.edges.forEach(function (e) {
        var from = graph.nodes[e.from]
        var to = graph.nodes[e.to]
        if (from === undefined || to === undefined) return
        if (from.anchor.file === to.anchor.file) return
        fileEdges.push([from.anchor.file, to.anchor.file])
      })
      var depth = {}
      fileOrder.forEach(function (file) { depth[file] = 0 })
      // Longest-path layering, bounded: a cycle between files is normal in real
      // code and must not spin here.
      for (var pass = 0; pass < 8; pass += 1) {
        var moved = false
        fileEdges.forEach(function (pair) {
          if (depth[pair[0]] === undefined || depth[pair[1]] === undefined) return
          if (depth[pair[1]] < depth[pair[0]] + 1) { depth[pair[1]] = depth[pair[0]] + 1; moved = true }
        })
        if (!moved) break
      }
      var arrival = {}
      fileOrder.forEach(function (file, i) { arrival[file] = i })
      fileOrder.sort(function (l, r) { return depth[l] - depth[r] || arrival[l] - arrival[r] })

      fileOrder.forEach(function (file) {
        byFile[file].sort(function (l, r) {
          var la = graph.nodes[l].anchor
          var ra = graph.nodes[r].anchor
          var lm = la.symbol.split('.').pop() === 'main' ? 0 : 1
          var rm = ra.symbol.split('.').pop() === 'main' ? 0 : 1
          return lm - rm || (la.start || 0) - (ra.start || 0) || la.symbol.localeCompare(ra.symbol)
        })
      })

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

      var byId = {}
      placed.forEach(function (p) { byId[p.id] = p })
      var boxOf = {}
      fileBoxes.forEach(function (box) { boxOf[box.file] = box })

      // Drag is an override layer ON TOP of the solved layout: positions are
      // computed above, a drag only nudges the nodes someone actually moved,
      // and 重排 throws the overrides away. Applied before routing, so every
      // wire is re-routed from where the node really is.
      if (placements !== undefined && placements !== null) {
        placed.forEach(function (p) {
          var at = placements[p.id]
          if (at !== undefined && typeof at.x === 'number' && typeof at.y === 'number') {
            p.x = at.x
            p.y = at.y
          }
        })
        // A file box re-wraps wherever its members ended up, so the frame
        // keeps naming what is inside it instead of where they used to be.
        fileBoxes.forEach(function (box) {
          var members = placed.filter(function (p) { return p.file === box.file })
          if (members.length === 0) return
          var left = Math.min.apply(Math, members.map(function (p) { return p.x }))
          var top = Math.min.apply(Math, members.map(function (p) { return p.y }))
          var right = Math.max.apply(Math, members.map(function (p) { return p.x + p.w }))
          var bottom = Math.max.apply(Math, members.map(function (p) { return p.y + p.h }))
          box.x = left - BOX_PAD
          box.y = top - BOX_HEAD - BOX_PAD
          box.w = right - left + BOX_PAD * 2
          box.h = bottom - top + BOX_HEAD + BOX_PAD * 2
        })
        boxOf = {}
        fileBoxes.forEach(function (box) { boxOf[box.file] = box })
      }

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
          && (e.always || graph.nodes[e.from].down || graph.nodes[e.to].up)
      })
      var chosen = drawable
      var hiddenCount = 0
      if (shared.wireMode !== 'all') {
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
          var stubbed = false
          if (a.file === b.file && a.innerRow === b.innerRow) {
            // Neighbours on one row inside one box: a short dogleg, all of it
            // inside the box it belongs to. Sideways flow: out the right, in
            // the left.
            var forward = a.x <= b.x
            var sx = forward ? a.x + a.w : a.x
            var sy = a.y + a.h / 2
            var tx = forward ? b.x : b.x + b.w
            var ty = b.y + b.h / 2
            var midX = sx + (tx - sx) / 2
            pts = [{ x: sx, y: sy }, { x: midX, y: sy }, { x: midX, y: ty }, { x: tx, y: ty }]
          } else if (a.file === b.file && boxOf[a.file] !== undefined) {
            // Same file, different rows. One anchor per row means every node in
            // a box shares one column, so the port rule can be the schematic
            // one: OUT through the bottom edge, IN through the top (reversed
            // for a call that goes up). Adjacent rows take a straight drop;
            // anything longer leaves through a 7px stub into the box's side
            // lane, which holds no anchors, and returns to the target's port.
            var boxS = boxOf[a.file]
            var down = a.y < b.y
            var acx = a.x + a.w / 2
            var bcx = b.x + b.w / 2
            var adjacent = down ? a.innerRow + 1 === b.innerRow : b.innerRow + 1 === a.innerRow
            if (adjacent) {
              pts = down
                ? [{ x: acx, y: a.y + a.h }, { x: bcx, y: b.y }]
                : [{ x: acx, y: a.y }, { x: bcx, y: b.y + b.h }]
            } else {
              var sideL = boxS.x + 8
              var sideR = boxS.x + boxS.w - 8
              // Prefer the side with more room from the node edges.
              var useLeft = (a.x - boxS.x) <= (boxS.x + boxS.w - (a.x + a.w))
              var lane = useLeft ? sideL : sideR
              stubbed = true
              pts = down
                ? [
                  { x: acx, y: a.y + a.h }, { x: acx, y: a.y + a.h + 7 },
                  { x: lane, y: a.y + a.h + 7 }, { x: lane, y: b.y - 7 },
                  { x: bcx, y: b.y - 7 }, { x: bcx, y: b.y },
                ]
                : [
                  { x: acx, y: a.y }, { x: acx, y: a.y - 7 },
                  { x: lane, y: a.y - 7 }, { x: lane, y: b.y + b.h + 7 },
                  { x: bcx, y: b.y + b.h + 7 }, { x: bcx, y: b.y + b.h },
                ]
            }
          } else {
            var boxA = boxOf[a.file]
            var boxB = boxOf[b.file]
            var downward = a.y < b.y
            // Ports carry the direction: every wire leaves its source through
            // the bottom edge and enters its target through the top (upward
            // calls mirror). A node reads in one sweep: top = who uses me,
            // bottom = what I use.
            var x1 = a.x + a.w / 2
            var y1 = downward ? a.y + a.h : a.y
            var x2 = b.x + b.w / 2
            var y2 = downward ? b.y : b.y + b.h
            if (boxA === undefined || boxB === undefined) {
              var mid = y1 + (y2 - y1) / 2
              pts = [{ x: x1, y: y1 }, { x: x1, y: mid }, { x: x2, y: mid }, { x: x2, y: y2 }]
            } else {
              // A straight drop from the port would run through whichever
              // sibling sits below in the same box, so the wire takes a 7px
              // stub into the row gap — where no node sits — and only then
              // turns into the side lane. The stubs are part of the node's
              // silhouette and must not be lane-nudged off it.
              var sideA = innerLane(a, boxA, b.x)
              var sideB = innerLane(b, boxB, a.x)
              var yOut = exitChannel(boxA, b.y)
              var yIn = exitChannel(boxB, a.y)
              var stubA = downward ? a.y + a.h + 7 : a.y - 7
              var stubB = downward ? b.y - 7 : b.y + b.h + 7
              stubbed = true
              if (Math.abs(yOut - yIn) < 1) {
                pts = [
                  { x: x1, y: y1 }, { x: x1, y: stubA },
                  { x: sideA.lane, y: stubA }, { x: sideA.lane, y: yOut },
                  { x: sideB.lane, y: yOut }, { x: sideB.lane, y: stubB },
                  { x: x2, y: stubB }, { x: x2, y: y2 },
                ]
              } else {
                var lane = nearest(vChannels, (sideA.lane + sideB.lane) / 2)
                pts = [
                  { x: x1, y: y1 }, { x: x1, y: stubA },
                  { x: sideA.lane, y: stubA }, { x: sideA.lane, y: yOut },
                  { x: lane, y: yOut }, { x: lane, y: yIn },
                  { x: sideB.lane, y: yIn }, { x: sideB.lane, y: stubB },
                  { x: x2, y: stubB }, { x: x2, y: y2 },
                ]
              }
            }
          }
          polylines.push({
            id: e.from + '→' + e.to + ':' + type,
            type: type, pts: pts, fromFile: a.file, toFile: b.file,
            from: e.from, to: e.to,
            stubbed: stubbed,
            faded: stateOf(e.to) !== null && stateOf(e.to) !== undefined && !stateOf(e.to).remembered,
          })
        })
      })

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
        // Only the stub-and-lane shapes (port, stub, lane, channel, …) can
        // share a trunk; the straight in-box drops have nothing to pool.
        var key = line.from + '|' + (line.pts[2].y > line.pts[0].y ? 'down' : 'up')
        ;(busGroups[key] = busGroups[key] || []).push(line)
      })
      Object.keys(busGroups).forEach(function (key) {
        var members = busGroups[key]
        if (members.length < 2) return
        // Every member already leaves through the same port and stub; the
        // trunk is the side lane at pts[2], run to the farthest branch.
        var laneX = members[0].pts[2].x
        var stubY = members[0].pts[1].y
        var branches = members.map(function (line) {
          return { line: line, y: line.pts[3].y }
        }).sort(function (l, r) {
          return Math.abs(l.y - stubY) - Math.abs(r.y - stubY)
        })
        branches.forEach(function (branch) {
          var line = branch.line
          // Redraw as: port, stub onto the trunk, ride the trunk to my own
          // branch point, then leave.
          var tail = line.pts.slice(4)
          line.pts = [
            line.pts[0],
            line.pts[1],
            { x: laneX, y: stubY },
            { x: laneX, y: branch.y },
          ].concat(tail)
          // Remember WHERE in the polyline the branch is, not the coordinates
          // it had at this moment. Lane assignment runs after this and nudges
          // the points; a captured pair of numbers then marks the spot the wire
          // used to be, which is how four of these dots ended up floating in
          // empty canvas.
          line.branchIndex = 3
        })
      })

      // ---- lanes: co-routed segments get their own track -------------------
      var hGroups = {}
      var vGroups = {}
      polylines.forEach(function (line) {
        for (var i = 1; i < line.pts.length; i += 1) {
          var p = line.pts[i - 1]
          var q = line.pts[i]
          // Only interior segments may move; the first and last touch a node.
          if (i - 1 === 0 || i === line.pts.length - 1) continue
          // The stubs tie a port to its lane through the row gap. Nudging one
          // into a track of its own moves it off the gap and under a sibling.
          if (line.stubbed === true && (i === 2 || i === line.pts.length - 2)) continue
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

      // A filled dot means a three-way: one wire arrives, two leave. That is
      // the only thing it can mean if it is to stay distinguishable from a hop,
      // so it is measured off the final geometry rather than remembered from
      // the routing pass. Counting branch markers was wrong twice over — the
      // farthest branch on a trunk is where the trunk ENDS, a plain corner with
      // nothing continuing past it, and a corner marked with a dot claims a
      // convergence that is not there.
      //
      // Degree at a point = how many distinct directions wire leaves it in. A
      // corner is 2, a straight run is 2, an endpoint is 1; only a genuine
      // T or cross reaches 3. Segments are counted whether the point is their
      // vertex or somewhere along their middle, because a trunk running PAST a
      // branch has no vertex there and is exactly what makes it a three-way.
      var DOT_TOL = 1
      var segAll = []
      polylines.forEach(function (line) {
        for (var i = 1; i < line.pts.length; i += 1) {
          var p = line.pts[i - 1]
          var q = line.pts[i]
          if (Math.abs(p.x - q.x) < 0.5 && Math.abs(p.y - q.y) < 0.5) continue
          segAll.push({ line: line, p: p, q: q })
        }
      })
      // Candidates are vertices only: a point where no wire bends or ends is
      // two independent wires crossing, and a crossing is drawn as a hop.
      var cand = {}
      polylines.forEach(function (line) {
        line.pts.forEach(function (pt) {
          cand[Math.round(pt.x) + ':' + Math.round(pt.y)] = { x: pt.x, y: pt.y }
        })
      })
      var dirOf = function (from, to) {
        if (Math.abs(to.x - from.x) > Math.abs(to.y - from.y)) return to.x > from.x ? 'R' : 'L'
        return to.y > from.y ? 'D' : 'U'
      }
      Object.keys(cand).forEach(function (key) {
        var c = cand[key]
        var dirs = {}
        var lines = {}
        for (var k = 0; k < segAll.length; k += 1) {
          var seg = segAll[k]
          var p = seg.p
          var q = seg.q
          var lo = { x: Math.min(p.x, q.x), y: Math.min(p.y, q.y) }
          var hi = { x: Math.max(p.x, q.x), y: Math.max(p.y, q.y) }
          if (c.x < lo.x - DOT_TOL || c.x > hi.x + DOT_TOL) continue
          if (c.y < lo.y - DOT_TOL || c.y > hi.y + DOT_TOL) continue
          var atP = Math.abs(c.x - p.x) <= DOT_TOL && Math.abs(c.y - p.y) <= DOT_TOL
          var atQ = Math.abs(c.x - q.x) <= DOT_TOL && Math.abs(c.y - q.y) <= DOT_TOL
          if (!atP) dirs[dirOf(c, p)] = true
          if (!atQ) dirs[dirOf(c, q)] = true
          lines[seg.line.id] = true
        }
        if (Object.keys(dirs).length < 3) return
        junctions.push({ id: key, x: c.x, y: c.y, count: Object.keys(lines).length })
      })

      // Port markers: one dot where a wire leaves its node, one where it
      // arrives. With every port on the top or bottom edge, the dots make a
      // passing channel wire and an attached wire impossible to confuse.
      var ports = []
      polylines.forEach(function (line) {
        var s = line.pts[0]
        var t = line.pts[line.pts.length - 1]
        ports.push({ id: line.id + ':s', x: s.x, y: s.y, type: line.type, faded: line.faded, from: line.from, to: line.to })
        ports.push({ id: line.id + ':t', x: t.x, y: t.y, type: line.type, faded: line.faded, from: line.from, to: line.to })
      })

      var farX = canvasWidth
      var farY = Math.max(360, canvasY - BOX_GAP_Y + PAD)
      placed.forEach(function (p) {
        if (p.x + p.w + PAD > farX) farX = p.x + p.w + PAD
        if (p.y + p.h + PAD > farY) farY = p.y + p.h + PAD
      })

      return {
        nodes: placed, wires: wires, labels: labels, junctions: junctions, arrows: arrows,
        ports: ports,
        rows: [], files: fileBoxes,
        width: farX, height: farY,
      }
    }

    function GraphNode(props) {
      var engine = props.engine
      var p = props.p
      var anchor = p.node.anchor
      var record = stateOf(p.id)
      var faded = record !== null && record !== undefined && !record.remembered
      var selected = shared.selected === p.id
      var isClass = anchor.kind === 'class' || anchor.members > 0
      // Dragging moves the node, clicking selects it: under a few pixels of
      // travel the press was a click, past them it was a drag — and the click
      // that fires on release after a drag must be swallowed.
      var drag = useRef(null)
      var suppressClick = useRef(false)

      var head = h('div', { className: 'cddlp-gtop' + (isClass ? ' cddlp-class-header' : ''), key: 'top' }, [
        h('span', { key: 'd', className: dotClass(record) }),
        h('span', { key: 's', className: 'cddlp-sym', title: anchor.id }, anchor.symbol),
        turnLabel(record) === null ? null : React.cloneElement(turnLabel(record), { key: 'b' }),
        isClass ? h('button', {
          key: 'c', className: 'cddlp-count',
          title: anchor.members + ' 个成员',
          onClick: function (e) { e.stopPropagation(); engine.members(p.id) },
        }, (p.node.members ? '▾ ' : '▸ ') + anchor.members)
          : h('span', { key: 'l', className: 'cddlp-lines' }, anchor.start + '–' + anchor.end),
        isClass ? h('span', { key: 'k', className: 'cddlp-kind' }, '类') : null,
      ])

      var members = null
      if (p.node.members && p.node.memberList !== undefined) {
        members = h('div', { className: 'cddlp-members', key: 'm' },
          p.node.memberList.map(function (member) {
            var mrec = stateOf(member.id)
            return h('div', {
              key: member.id,
              className: 'cddlp-m' + (shared.selected === member.id ? ' cddlp-sel' : ''),
              title: member.id,
              'data-anchor-id': member.id,
              onClick: function (e) { e.stopPropagation(); engine.select(member.id) },
            }, [
              h('span', { key: 'd', className: dotClass(mrec) }),
              h('span', { key: 's', className: 'cddlp-sym' }, member.symbol.split('.').pop()),
              turnLabel(mrec) === null ? null : React.cloneElement(turnLabel(mrec), { key: 'b' }),
              h('span', { key: 'l', className: 'cddlp-lines' }, member.start + '–' + member.end),
            ])
          }).concat([h('div', { key: 'more', className: 'cddlp-more' }, '共 ' + p.node.memberList.length + ' 个方法')]))
      }

      var upOpen = p.node.up === true
      var downOpen = p.node.down === true
      return h('div', {
        className: 'cddlp-node-shell' + (p.island ? ' cddlp-shell-island' : '')
          + (drag.current !== null && drag.current.moved ? ' cddlp-dragging' : ''),
        style: { left: p.x + 'px', top: p.y + 'px', width: p.w + 'px' },
        'data-node-id': p.id,
        onPointerDown: function (e) {
          if (props.onDrag === undefined) return
          if (e.button !== undefined && e.button !== 0) return
          if (e.target.closest('button') !== null) return
          drag.current = { pointer: e.pointerId, x: e.clientX, y: e.clientY, at: { x: p.x, y: p.y }, moved: false }
          e.currentTarget.setPointerCapture(e.pointerId)
        },
        onPointerMove: function (e) {
          var d = drag.current
          if (d === null || e.pointerId !== d.pointer) return
          var scale = props.zoom || 1
          var dx = (e.clientX - d.x) / scale
          var dy = (e.clientY - d.y) / scale
          if (!d.moved && Math.abs(dx) + Math.abs(dy) <= 4) return
          d.moved = true
          suppressClick.current = true
          e.preventDefault()
          props.onDrag(p.id, { x: Math.max(4, d.at.x + dx), y: Math.max(4, d.at.y + dy) })
        },
        onPointerUp: function (e) {
          if (drag.current === null || e.pointerId !== drag.current.pointer) return
          drag.current = null
        },
      }, [
        h('div', { key: 'h', className: 'cddlp-node-actions' }, [
          h('button', {
            key: 'u',
            title: anchor.up === 0
              ? '索引里没有谁用它'
              : (upOpen ? '收起：谁在用它（' + anchor.up + '）' : '展开：谁在用它（' + anchor.up + '）'),
            disabled: anchor.up === 0,
            className: 'cddlp-action-up' + (upOpen ? ' on' : ''),
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
            className: 'cddlp-action-down' + (downOpen ? ' on' : ''),
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
            className: 'cddlp-action-pin' + (p.node.pinned ? ' on' : (stickyByRecency(p.id) ? ' auto' : '')),
            'data-action': 'pin-anchor',
            onClick: function (e) { e.stopPropagation(); engine.pin(p.id) },
          }, 'pin'),
        ]),
        h('div', {
          key: 'n',
          className: 'cddlp-gnode'
            + (selected ? ' cddlp-sel' : '')
            + (faded ? ' cddlp-faded' : '')
            + (p.node.island ? ' cddlp-island' : '')
            + (isClass ? ' cddlp-cls cddlp-class' : ''),
          title: anchor.id,
          'data-anchor-id': anchor.id,
          onClick: function () {
            if (suppressClick.current) { suppressClick.current = false; return }
            engine.select(p.id)
          },
        }, [
          // No path line here: the box header already names the file, and
          // repeating it inside every node was what squeezed the symbol into an
          // ellipsis. Hover still shows the fully qualified id.

          head,
          members,
          record && record.state === 'working'
            ? h('div', { key: 'w', className: 'cddlp-working' },
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

      return h('div', { className: 'cddlp-hscroll', onPointerDown: onDown, title: '横向滚动' },
        h('div', {
          className: 'cddlp-hscroll-thumb',
          style: {
            width: Math.max(8, st.ratio * 100) + '%',
            left: (st.left * (100 - Math.max(8, st.ratio * 100))) + '%',
          },
        }))
    }

    function LensView(props) {
      var ctx = props.ctx
      useShared()
      var engine = useMemo(function () { return makeEngine(ctx) }, [])
      var tab = useState('graph')
      var relations = useState({ call: true, dataflow: false, inherit: false, impact: false, dispatch: true })
      var zoom = useState(1)
      var layoutRevision = useState(0)
      var placements = useState({})
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
      // Only what genuinely lies on top of this view, measured against the
      // view's own box. Reserving the window's right edge here double-counted
      // the frame's details track and left a dead white strip.
      var reserve = useOverlapInset(viewRef)

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
        return layout(shared.graph, relations[0], availWidth[0], placements[0])
      }, [shared.revision, relations[0], layoutRevision[0], availWidth[0], placements[0]])

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

      var canvas
      if (context === undefined) canvas = h('div', { className: 'cddlp-empty' }, '连接中…')
      else if (!context.indexed) canvas = h(NeedIndex, { engine: engine })
      else if (tab[0] === 'outline') canvas = h('div', { className: 'cddlp-scroll' }, h(Outline, { engine: engine }))
      else if (tab[0] === 'draw') canvas = h(Draw, { engine: engine })
      else if (model.nodes.length === 0) {
        canvas = h('div', { className: 'cddlp-empty' },
          '还没有起点。切到「目录」翻一个函数，或者上面搜一个名字。')
      } else {
        canvas = h('div', {
          className: 'cddlp-scaler cddlp-viewport',
          style: { width: (model.width * zoom[0]) + 'px', height: (model.height * zoom[0]) + 'px' },
        }, h('div', {
          className: 'cddlp-canvas',
          style: {
            width: model.width + 'px', height: model.height + 'px',
            transform: 'scale(' + zoom[0] + ')', transformOrigin: '0 0',
          },
        }, [
          h('svg', {
              key: 'w', className: 'cddlp-wires',
              width: model.width, height: model.height,
              viewBox: '0 0 ' + model.width + ' ' + model.height,
            }, [
              h('defs', { key: 'd' }, [
                h('marker', {
                  key: 'a', id: 'cddlp-arrow', markerWidth: 8, markerHeight: 8, refX: 6.5, refY: 3, orient: 'auto',
                }, h('path', { d: 'M0,0 L6,3 L0,6 z' })),
                h('marker', {
                  key: 'f', id: 'cddlp-arrow-faded', markerWidth: 8, markerHeight: 8, refX: 6.5, refY: 3, orient: 'auto',
                }, h('path', { d: 'M0,0 L6,3 L0,6 z' })),
              ]),
            ].concat(model.wires.map(function (wire) {
              return h('path', {
                key: wire.id, d: wire.d,
                'data-edge-id': wire.id,
                className: 'cddlp-wire cddlp-' + wire.type
                  + (wire.faded ? ' cddlp-faded' : '')
                  + (shared.focused === null || shared.focused === undefined ? ''
                    : (wire.from === shared.focused || wire.to === shared.focused ? ' cddlp-hot' : ' cddlp-cold')),
                'data-from-file': wire.fromFile,
                'data-to-file': wire.toFile,
              })
            })).concat((model.ports || []).map(function (port) {
              return h('circle', {
                key: 'p' + port.id,
                className: 'cddlp-port cddlp-' + port.type
                  + (port.faded ? ' cddlp-faded' : '')
                  + (shared.focused === null || shared.focused === undefined ? ''
                    : (port.from === shared.focused || port.to === shared.focused ? ' cddlp-hot' : ' cddlp-cold')),
                cx: port.x, cy: port.y, r: 2.8,
              })
            })).concat(model.arrows.map(function (arrow) {
              // Repeated along the run: on a wire with four bends a single
              // arrowhead at the far end says nothing about the middle.
              return h('path', {
                key: 'a' + arrow.id,
                className: 'cddlp-arrowhead cddlp-' + arrow.type
                  + (arrow.faded ? ' cddlp-faded' : '')
                  + (shared.focused === null || shared.focused === undefined ? ''
                    : (arrow.from === shared.focused || arrow.to === shared.focused ? ' cddlp-hot' : ' cddlp-cold')),
                d: 'M-4.5,-3.2 L4.5,0 L-4.5,3.2 Z',
                transform: 'translate(' + arrow.x + ',' + arrow.y + ') rotate(' + arrow.angle + ')',
              })
            })).concat(model.junctions.map(function (dot) {
              // Filled dot = these wires actually meet. A hop = they only cross.
              return h('circle', {
                key: 'j' + dot.id, className: 'cddlp-junction',
                cx: dot.x, cy: dot.y, r: 3.4,
              })
            }))),
          h('div', { key: 'f', className: 'cddlp-fileboxes' },
            (model.files || []).map(function (box) {
              return h('div', {
                key: box.file,
                className: 'cddlp-filebox',
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
          h('div', { key: 'r', className: 'cddlp-rowlabels' },
            model.rows.map(function (row, i) {
              return h('div', {
                key: i, className: 'cddlp-rowlabel' + (row.island ? ' cddlp-island-label' : ''),
                style: { top: (row.y - 24) + 'px' },
              }, row.label)
            })),
          h('div', { key: 'c', className: 'cddlp-chips' },
            model.rows.filter(function (row) { return row.island && row.label }).map(function (row, i) {
              return h('div', {
                key: i, className: 'cddlp-chip', style: { top: (row.y - 30) + 'px', right: '24px' },
              }, row.ids.length + ' 个本轮节点 · 不在当前根链')
            })),
          h('div', { key: 'n', className: 'cddlp-nodes', style: { width: model.width + 'px', height: model.height + 'px' } },
            model.nodes.map(function (p) {
              return h(GraphNode, {
                key: p.id, p: p, engine: engine, zoom: zoom[0],
                onDrag: function (id, at) {
                  placements[1](function (before) {
                    var next = Object.assign({}, before)
                    next[id] = at
                    return next
                  })
                },
              })
            })),
        ]))
      }

      return h('div', {
        className: 'cddlp-view',
        ref: viewRef,
        style: { paddingRight: reserve + 'px' },
        'data-conversation-composer-overlay': '',
      }, [
        h('div', { className: 'cddlp-toolbar', key: 't' }, [
          h('div', { key: 'seg', className: 'cddlp-seg' }, [
            h('button', { key: 'g', className: tab[0] === 'graph' ? 'on' : '', onClick: function () { tab[1]('graph') } }, '逻辑图'),
            h('button', { key: 'o', className: tab[0] === 'outline' ? 'on' : '', onClick: function () { tab[1]('outline') } }, '目录'),
            h('button', { key: 'd', className: tab[0] === 'draw' ? 'on' : '', onClick: function () { tab[1]('draw') } }, 'cdd draw'),
          ]),
          h(Search, { key: 'q', engine: engine }),
          h('div', { key: 'rel', className: 'cddlp-seg cddlp-relations', 'aria-label': '关系筛选' },
            ['call', 'dataflow', 'inherit', 'impact', 'dispatch'].map(function (name) {
              return h('button', {
                key: name,
                className: relations[0][name] ? 'on' : '',
                'aria-pressed': relations[0][name] ? 'true' : 'false',
                onClick: function () { toggleRelation(name) },
              }, name)
            })),
          h('span', { key: 'm', className: 'cddlp-meta', title: context ? context.root : '' },
            context && context.stats ? (context.stats.anchors + ' anchor · ' + context.stats.edges + ' 边 · ' + context.stats.files + ' 文件') : ''),
          h('span', { key: 's', className: 'cddlp-spacer' }),
          h('div', { key: 'z', className: 'cddlp-zoom', 'aria-label': '缩放控制' }, [
            h('button', { key: 'o', className: 'cddlp-btn', onClick: function () { setZoom(zoom[0] - .1) } }, '−'),
            h('button', { key: 'n', className: 'cddlp-btn', onClick: function () { setZoom(1) } }, Math.round(zoom[0] * 100) + '%'),
            h('button', { key: 'i', className: 'cddlp-btn', onClick: function () { setZoom(zoom[0] + .1) } }, '＋'),
          ]),
          h('button', {
            key: 'l', className: 'cddlp-btn',
            title: '回到计算布局（放弃所有手动拖动）',
            onClick: function () {
              placements[1]({})
              layoutRevision[1](function (n) { return n + 1 })
            },
          }, '重排'),
          h('button', {
            key: 'a', className: 'cddlp-btn', title: '缩小到能看见全图（会看不清字）',
            onClick: function () { fit(shared.selected || shared.graph.rootId, .35) },
          }, '适配'),
          h('button', {
            key: 'w', className: 'cddlp-btn', title: '按宽度铺满，纵向滚动',
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
            key: 'r', className: 'cddlp-btn',
            onClick: function () { engine.reindex() },
          }, shared.reindexing ? '建索引…' : '↻ 重建索引'),
          h('button', {
            key: 'w', className: 'cddlp-btn' + (shared.wireMode === 'all' ? ' on' : ''),
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
            key: 'f', className: 'cddlp-btn',
            onClick: function () { shared.graph = emptyGraph(); publish() },
          }, '清空'),
        ]),
        h('div', { key: 'st', className: 'cddlp-stage' }, [
          h('div', {
            key: 'c', className: 'cddlp-canvaswrap', ref: canvasRef,
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
                && e.target.closest('.cddlp-gnode, .cddlp-node-actions, .cddlp-filebox') !== null
              if (onNode) return
              var startX = e.clientX
              var startY = e.clientY
              var fromLeft = el.scrollLeft
              var fromTop = el.scrollTop
              var move = function (ev) {
                el.scrollLeft = fromLeft - (ev.clientX - startX)
                el.scrollTop = fromTop - (ev.clientY - startY)
              }
              var up = function () {
                window.removeEventListener('pointermove', move)
                window.removeEventListener('pointerup', up)
                el.style.cursor = ''
              }
              el.style.cursor = 'grabbing'
              window.addEventListener('pointermove', move)
              window.addEventListener('pointerup', up)
            },
          }, canvas),
          h(HScroll, { key: 'hs', canvasRef: canvasRef, width: model.width, zoom: zoom[0] }),
          h('div', { key: 'p', className: 'cddlp-sidepanel' }, [
            h(Source, { key: 's' }),
            h(History, { key: 'h' }),
          ]),

        ]),
        h(Legend, { key: 'l' }),
      ])
    }

    // ---- styles ------------------------------------------------------------
    //
    // Every colour is a dsw alias token. A hardcoded one would look right in
    // whichever theme it was written in and wrong in the other; the tokens
    // follow the viewer's theme with no work here.

    var CSS = [
      // The overlay layer is click-through; pointer events are opted back into
      // per element, and deliberately only on the card — never on a wrapper —
      // so the rest of the frame stays clickable.
      '.cddlp-root{position:absolute;right:16px;bottom:16px;pointer-events:none;',
      'display:flex;flex-direction:column;align-items:flex-end;gap:8px;z-index:400}',
      'body:has(.cddlp-view) .cddlp-root{display:none}',
      '.cddlp-card{pointer-events:auto;position:relative;max-height:min(78vh,760px);display:flex;flex-direction:column;',
      'background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l2);border-radius:11px;',
      'box-shadow:var(--dsw-elevation-panel,0 12px 34px rgba(0,0,0,.5));overflow:hidden;',
      'color:var(--dsw-alias-label-primary);font-family:var(--dsw-font-family,inherit);font-size:12px;line-height:1.6}',
      '.cddlp-pill{pointer-events:auto;cursor:pointer;padding:6px 12px;border-radius:999px;display:flex;gap:6px;align-items:center;',
      'background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l2);',
      'box-shadow:var(--dsw-elevation-panel,0 6px 18px rgba(0,0,0,.4));color:var(--dsw-alias-label-secondary);',
      'font-family:var(--dsw-font-family,inherit);font-size:12px}',
      '.cddlp-pill:hover{color:var(--dsw-alias-label-primary)}',
      '.cddlp-pilln{background:var(--dsw-alias-bg-layer-3);border-radius:9px;padding:0 6px;font-size:10px}',

      '.cddlp-grip{position:absolute;left:0;top:0;bottom:0;width:6px;cursor:ew-resize;z-index:2}',
      '.cddlp-grip:hover{background:var(--dsw-alias-border-l3)}',
      '.cddlp-head{cursor:grab;user-select:none;display:flex;align-items:center;gap:8px;padding:9px 12px;',
      'border-bottom:1px solid var(--dsw-alias-border-l1);flex:none}',
      '.cddlp-title{font-size:12.5px;font-weight:600}',
      '.cddlp-meta{font-family:var(--ds-font-family-code,monospace);font-size:10.5px;',
      'color:var(--dsw-alias-label-caption);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddlp-spacer{flex:1}',
      '.cddlp-bad{color:var(--dsw-alias-state-error-primary);font-size:10.5px}',
      '.cddlp-btn{border:1px solid var(--dsw-alias-border-l2);background:transparent;',
      'color:var(--dsw-alias-label-tertiary);border-radius:5px;font-size:11px;padding:2px 7px;',
      'cursor:pointer;font-family:inherit;white-space:nowrap}',
      '.cddlp-btn:hover{background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}',
      '.cddlp-primary{border:1px solid var(--dsw-alias-border-l3);background:var(--dsw-alias-bg-layer-3);',
      'color:var(--dsw-alias-label-primary);border-radius:6px;font-size:11.5px;padding:4px 12px;',
      'cursor:pointer;font-family:inherit;margin-top:8px}',
      '.cddlp-primary:disabled{opacity:.5;cursor:default}',

      '.cddlp-tabs{display:flex;gap:2px;padding:6px 12px 0;border-bottom:1px solid var(--dsw-alias-border-l1);flex:none}',
      '.cddlp-tabs button{background:transparent;border:0;border-bottom:2px solid transparent;cursor:pointer;',
      'padding:4px 10px;font-size:11.5px;color:var(--dsw-alias-label-caption);font-family:inherit}',
      '.cddlp-tabs button.on{color:var(--dsw-alias-label-primary);border-bottom-color:var(--dsw-alias-state-business-primary)}',

      '.cddlp-search{position:relative;padding:8px 12px 0;flex:none}',
      '.cddlp-q{width:100%;box-sizing:border-box;background:var(--dsw-alias-bg-layer-1);',
      'border:1px solid var(--dsw-alias-border-l2);border-radius:6px;padding:4px 9px;',
      'font-size:11.5px;color:var(--dsw-alias-label-primary);font-family:inherit;outline:none}',
      '.cddlp-q::placeholder{color:var(--dsw-alias-label-dimmed)}',
      '.cddlp-hits{position:absolute;left:12px;right:12px;top:100%;z-index:3;max-height:280px;overflow:auto;',
      'background:var(--dsw-alias-bg-layer-3);border:1px solid var(--dsw-alias-border-l2);border-radius:7px;',
      'box-shadow:0 8px 22px rgba(0,0,0,.45);padding:4px}',
      '.cddlp-hit{display:flex;align-items:baseline;gap:8px;padding:4px 7px;border-radius:5px;cursor:pointer}',
      '.cddlp-hit:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddlp-hitfile{margin-left:auto;font-family:var(--ds-font-family-code,monospace);font-size:10px;',
      'color:var(--dsw-alias-label-caption)}',

      '.cddlp-body{flex:1;min-height:120px;overflow:auto}',
      '.cddlp-tree{padding:8px 10px 10px}',
      '.cddlp-filehdr{font-family:var(--ds-font-family-code,monospace);font-size:10px;',
      'color:var(--dsw-alias-label-caption);margin:8px 0 3px}',
      '.cddlp-node{display:flex;align-items:center;gap:6px;padding:3px 6px;border-radius:6px;cursor:pointer}',
      '.cddlp-node:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddlp-sel{background:var(--dsw-alias-interactive-bg-active)}',
      '.cddlp-ind{flex:none}',
      '.cddlp-twist{width:14px;flex:none;color:var(--dsw-alias-label-dimmed);font-size:9px;text-align:center;',
      'background:transparent;border:0;cursor:pointer;padding:0;font-family:inherit}',
      '.cddlp-twist:hover{color:var(--dsw-alias-label-primary)}',
      '.cddlp-dot{width:7px;height:7px;border-radius:50%;flex:none;background:var(--dsw-alias-label-dimmed);display:inline-block}',
      '.cddlp-dot.cddlp-v{background:var(--dsw-alias-state-business-primary)}',
      '.cddlp-dot.cddlp-e{background:var(--dsw-alias-state-warn-primary)}',
      '.cddlp-dot.cddlp-w{background:var(--dsw-alias-state-error-primary);box-shadow:0 0 0 3px rgba(242,90,90,.2)}',
      '.cddlp-sym{font-family:var(--ds-font-family-code,monospace);font-size:11.5px;',
      'color:var(--dsw-alias-label-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddlp-sel .cddlp-sym{color:var(--dsw-alias-label-primary)}',
      '.cddlp-kind{font-size:9.5px;color:var(--dsw-alias-label-caption);flex:none;',
      'border:1px solid var(--dsw-alias-border-l2);border-radius:3px;padding:0 3px;white-space:nowrap}',
      '.cddlp-turn{font-family:var(--ds-font-family-code,monospace);font-size:9.5px;flex:none;',
      'padding:0 5px;border-radius:9px;border:1px solid transparent;white-space:nowrap}',
      '.cddlp-turn.cddlp-v{color:var(--dsw-alias-state-business-primary);border-color:var(--dsw-alias-state-business-tertiary)}',
      '.cddlp-turn.cddlp-e{color:var(--dsw-alias-state-warn-primary);border-color:var(--dsw-alias-state-warn-tertiary)}',
      '.cddlp-turn.cddlp-w{color:var(--dsw-alias-state-error-primary);border-color:var(--dsw-alias-state-error-secondary)}',
      '.cddlp-lines{font-family:var(--ds-font-family-code,monospace);font-size:9.5px;',
      'color:var(--dsw-alias-label-dimmed);margin-left:auto;flex:none;padding-left:6px;white-space:nowrap}',
      '.cddlp-hop{margin-left:auto;display:flex;gap:2px;flex:none;opacity:.55}',
      '.cddlp-node:hover .cddlp-hop,.cddlp-sel .cddlp-hop{opacity:1}',
      '.cddlp-hop button{font-size:10px;font-family:var(--ds-font-family-code,monospace);cursor:pointer;',
      'color:var(--dsw-alias-label-caption);background:transparent;',
      'border:1px solid var(--dsw-alias-border-l2);border-radius:4px;padding:0 4px}',
      '.cddlp-hop button:hover{color:var(--dsw-alias-label-primary);background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddlp-hop button.on{color:var(--dsw-alias-label-primary);border-color:var(--dsw-alias-border-l4)}',
      // Compaction took the verbatim evidence back: pale, not gone.
      '.cddlp-faded{opacity:.4}',
      '.cddlp-faded .cddlp-sym{font-style:italic}',
      '.cddlp-island{border-left:2px dashed var(--dsw-alias-border-l3)}',
      '.cddlp-bridge .cddlp-sym{color:var(--dsw-alias-label-caption)}',
      '.cddlp-bridgetag{border-style:dashed;opacity:.8}',
      '.cddlp-gap{display:flex;align-items:center;gap:7px;padding:6px 4px;',
      'color:var(--dsw-alias-label-caption);font-size:10px}',
      '.cddlp-gap i{flex:1;height:1px;background:repeating-linear-gradient(90deg,',
      'var(--dsw-alias-label-dimmed) 0 3px,transparent 3px 7px)}',

      '.cddlp-dir,.cddlp-fileitem,.cddlp-symitem{display:flex;align-items:center;gap:6px;',
      'padding:3px 6px;border-radius:6px;cursor:pointer;font-size:11.5px}',
      '.cddlp-dir{color:var(--dsw-alias-label-secondary);font-family:var(--ds-font-family-code,monospace)}',
      '.cddlp-fileitem{padding-left:20px;color:var(--dsw-alias-label-caption);font-family:var(--ds-font-family-code,monospace)}',
      '.cddlp-symitem{padding-left:38px}',
      '.cddlp-dir:hover,.cddlp-fileitem:hover,.cddlp-symitem:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddlp-count{margin-left:auto;font-family:var(--ds-font-family-code,monospace);font-size:10px;',
      'color:var(--dsw-alias-label-dimmed);flex:none}',
      '.cddlp-sub{padding-left:38px;color:var(--dsw-alias-label-dimmed);font-size:11px}',

      '.cddlp-empty{padding:18px 14px;color:var(--dsw-alias-label-tertiary);font-size:11.5px;line-height:1.8}',
      '.cddlp-path{font-family:var(--ds-font-family-code,monospace);font-size:10.5px;',
      'color:var(--dsw-alias-label-caption);word-break:break-all;margin:4px 0}',
      '.cddlp-progress{color:var(--dsw-alias-label-caption);font-size:11px;margin-top:6px}',
      '.cddlp-tail{font-family:var(--ds-font-family-code,monospace);font-size:10px;',
      'color:var(--dsw-alias-label-dimmed);max-height:90px;overflow:auto;margin-top:8px;white-space:pre-wrap}',

      '.cddlp-legend{display:flex;flex-wrap:wrap;gap:12px;padding:8px 12px;flex:none;',
      'border-top:1px solid var(--dsw-alias-border-l1);font-size:10.5px;color:var(--dsw-alias-label-caption)}',
      '.cddlp-legend b{font-weight:400;display:flex;align-items:center;gap:5px}',
      '.cddlp-swatch{display:inline-block;width:18px;height:0;border-top:1.5px solid var(--dsw-alias-border-l4)}',
      '.cddlp-swatch.cddlp-dataflow{border-top-style:dashed}',
      '.cddlp-swatch.cddlp-inherit{border-top-style:dotted}',
      '.cddlp-swatch.cddlp-impact{border-top:2px dotted var(--dsw-alias-border-l3)}',
      '.cddlp-swatch.cddlp-dispatch{border-top:2px dashed var(--dsw-alias-border-l4)}',

      '.cddlp-src{border-top:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);flex:none}',
      '.cddlp-srch{font-family:var(--ds-font-family-code,monospace);font-size:10px;padding:8px 12px 4px;',
      'color:var(--dsw-alias-label-caption);word-break:break-all}',
      '.cddlp-src pre{margin:0;padding:0 12px 10px;font-family:var(--ds-font-family-code,monospace);',
      'font-size:10.5px;line-height:1.65;color:var(--dsw-alias-label-tertiary);max-height:180px;overflow:auto}',
      '.cddlp-hl{background:var(--dsw-alias-state-warn-tertiary);display:block;margin:0 -12px;padding:0 12px;',
      'border-left:2px solid var(--dsw-alias-state-warn-primary)}',
      '.cddlp-ln{color:var(--dsw-alias-label-dimmed);user-select:none;display:inline-block;width:34px}',
      '.cddlp-code{white-space:pre}',
      '.cddlp-hist{border-top:1px solid var(--dsw-alias-border-l1);padding:8px 12px;flex:none}',
      '.cddlp-hist h4{margin:0 0 5px;font-size:10.5px;color:var(--dsw-alias-label-caption);font-weight:500}',
      '.cddlp-unres{margin:10px 10px 4px;padding:8px 10px;border-radius:8px;',
      'border:1px dashed var(--dsw-alias-border-l3);background:var(--dsw-alias-bg-layer-1)}',
      '.cddlp-unres h4{display:flex;align-items:center;gap:6px}',
      '.cddlp-rank{font-family:var(--ds-font-family-code,monospace);font-size:9px;flex:none;',
      'width:15px;text-align:right;color:var(--dsw-alias-label-dimmed)}',
      '.cddlp-rank-none{color:transparent}',
      '.cddlp-hop button.cddlp-off{opacity:.3;cursor:default}',
      '.cddlp-hop button.cddlp-off:hover{background:transparent;color:var(--dsw-alias-label-caption)}',
      '.cddlp-unres h4{margin:0 0 5px;font-size:10.5px;color:var(--dsw-alias-label-caption);font-weight:500}',
      '.cddlp-unrow{display:flex;align-items:center;gap:7px;padding:1px 0;opacity:.75}',
      '.cddlp-hrow{display:flex;align-items:center;gap:7px;font-size:11px;',
      'color:var(--dsw-alias-label-tertiary);padding:1px 0}',
      '.cddlp-agent{font-family:var(--ds-font-family-code,monospace);color:var(--dsw-alias-state-business-primary)}',
      '.cddlp-reason{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--dsw-alias-label-secondary)}',
      '.cddlp-t{font-family:var(--ds-font-family-code,monospace);font-size:10px;',
      'color:var(--dsw-alias-label-caption);width:26px;flex:none}',

      // ---- the spread-out view ----
      '.cddlp-view{--cddlp-bottom-clearance:calc(var(--dsh-composer-height,152px) + 16px);',
      'display:flex;flex-direction:column;height:100%;min-height:0;width:100%;box-sizing:border-box;',
      'padding-bottom:var(--cddlp-bottom-clearance);overflow:hidden;',
      'background:var(--dsw-alias-bg-layer-1);color:var(--dsw-alias-label-primary);',
      'font-family:var(--dsw-font-family,inherit);font-size:12px}',
      '.cddlp-toolbar{display:flex;align-items:center;gap:8px;padding:8px 16px;flex:none;flex-wrap:wrap;',
      'border-bottom:1px solid var(--dsw-alias-border-l1)}',
      '.cddlp-toolbar .cddlp-search{padding:0;width:240px;flex:none}',
      '.cddlp-seg{display:flex;border:1px solid var(--dsw-alias-border-l2);border-radius:6px;overflow:hidden;flex:none}',
      '.cddlp-seg button{padding:3px 11px;font-size:11.5px;background:transparent;border:0;cursor:pointer;',
      'color:var(--dsw-alias-label-caption);border-right:1px solid var(--dsw-alias-border-l2);font-family:inherit}',
      '.cddlp-seg button:last-child{border-right:0}',
      '.cddlp-seg button.on{background:var(--dsw-alias-bg-layer-3);color:var(--dsw-alias-label-primary)}',
      '.cddlp-relations button{font-family:var(--ds-font-family-code,monospace);font-size:10.5px;padding:3px 8px}',
      '.cddlp-relations button.on{box-shadow:inset 0 -2px 0 var(--dsw-alias-state-business-primary)}',
      '.cddlp-zoom{display:flex;gap:2px;align-items:center}',
      '.cddlp-zoom .cddlp-btn:nth-child(2){min-width:46px;font-family:var(--ds-font-family-code,monospace)}',
      '.cddlp-stage{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,var(--cddlp-src, 26%));grid-template-rows:minmax(0,1fr) auto}',
      '.cddlp-canvaswrap{grid-column:1;grid-row:1;position:relative;overflow:auto;',
      'scrollbar-gutter:stable;',
      'background:radial-gradient(circle at 1px 1px, var(--dsw-alias-border-l1) 1px, transparent 0) 0 0/22px 22px,',
      'var(--dsw-alias-bg-base)}',
      '.cddlp-canvaswrap::-webkit-scrollbar{width:12px;height:12px}',
      '.cddlp-hscroll{grid-column:1;grid-row:2;align-self:end;position:relative;height:12px;margin:0 2px 2px;',
      'border-radius:6px;background:var(--dsw-alias-scrollbar-bg-l2,rgba(127,127,127,.10));cursor:pointer;z-index:3}',
      '.cddlp-hscroll-thumb{position:absolute;top:2px;bottom:2px;border-radius:5px;',
      'background:var(--dsw-alias-border-l4);pointer-events:none}',
      '.cddlp-hscroll:hover .cddlp-hscroll-thumb{background:var(--dsw-alias-label-caption)}',
      '.cddlp-canvaswrap::-webkit-scrollbar-track{background:var(--dsw-alias-scrollbar-bg-l2,rgba(127,127,127,.08))}',
      '.cddlp-canvaswrap::-webkit-scrollbar-thumb{background:var(--dsw-alias-border-l4);border-radius:7px;',
      'border:3px solid transparent;background-clip:content-box}',
      '.cddlp-canvaswrap::-webkit-scrollbar-thumb:hover{background:var(--dsw-alias-scrollbar-hover-l2,var(--dsw-alias-label-caption));',
      'background-clip:content-box}',
      '.cddlp-canvaswrap::-webkit-scrollbar-corner{background:transparent}',
      '.cddlp-scaler{position:relative;min-width:100%;min-height:100%}',
      '.cddlp-canvas{position:relative;transition:transform .14s ease}',
      '.cddlp-scroll{overflow:auto;height:100%}',
      '.cddlp-frame{width:100%;height:100%;min-height:320px;border:0;background:#fff;display:block}',
      '.cddlp-wires{position:absolute;left:0;top:0;pointer-events:none}',
      '.cddlp-wire{fill:none;stroke:var(--dsw-alias-state-business-primary);stroke-width:1.8}',
      '.cddlp-wire.cddlp-dataflow{stroke:var(--dsw-alias-state-warn-primary);stroke-dasharray:4 3}',
      '.cddlp-wire.cddlp-inherit{stroke:var(--dsw-alias-label-tertiary);stroke-dasharray:1 3}',
      '.cddlp-wire.cddlp-dispatch{stroke-dasharray:7 3}',
      '.cddlp-wire.cddlp-impact{stroke-dasharray:2 4}',
      '.cddlp-wire.cddlp-faded{stroke:var(--dsw-alias-border-l1)}',
      '#cddlp-arrow path{fill:var(--dsw-alias-state-business-primary)}',
      '#cddlp-arrow-faded path{fill:var(--dsw-alias-border-l1)}',
      '.cddlp-edge-label{font-family:var(--ds-font-family-code,monospace);font-size:9px;',
      'fill:var(--dsw-alias-label-dimmed);paint-order:stroke;stroke:var(--dsw-alias-bg-base);stroke-width:3px}',
      '.cddlp-rowlabels{position:absolute;inset:0;pointer-events:none}',
      '.cddlp-rowlabel{position:absolute;left:16px;font-size:9.5px;letter-spacing:.06em;text-transform:uppercase;',
      'color:var(--dsw-alias-label-dimmed);font-family:var(--ds-font-family-code,monospace)}',
      '.cddlp-rowlabel.cddlp-island-label{padding-top:8px;border-top:1px dashed var(--dsw-alias-border-l2);right:16px}',
      '.cddlp-chips{position:absolute;inset:0;pointer-events:none}',
      '.cddlp-chip{position:absolute;padding:2px 8px;border-radius:999px;border:1px dashed var(--dsw-alias-border-l3);',
      'background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-caption);font-size:9.5px;',
      'font-family:var(--ds-font-family-code,monospace)}',
      '.cddlp-fileboxes{position:absolute;inset:0;pointer-events:none}',
      '.cddlp-arrowhead{fill:var(--dsw-alias-state-business-primary);stroke:none}',
      '.cddlp-arrowhead.cddlp-dataflow{fill:var(--dsw-alias-state-warn-primary)}',
      '.cddlp-arrowhead.cddlp-dispatch{fill:var(--dsw-alias-state-success-primary)}',
      '.cddlp-arrowhead.cddlp-faded{fill:var(--dsw-alias-border-l3)}',
      '.cddlp-action-pin{font-family:var(--dsw-font-family,inherit);letter-spacing:.02em}',
      '.cddlp-action-pin.on{color:var(--dsw-alias-state-warn-primary);border-color:var(--dsw-alias-state-warn-primary)}',
      '.cddlp-action-pin.auto{color:var(--dsw-alias-state-business-primary);border-style:dashed}',
      '.cddlp-junction{fill:var(--dsw-alias-label-primary);stroke:var(--dsw-alias-bg-base);stroke-width:1.2}',
      '.cddlp-port{fill:var(--dsw-alias-state-business-primary);stroke:var(--dsw-alias-bg-base);stroke-width:.8}',
      '.cddlp-port.cddlp-dataflow{fill:var(--dsw-alias-state-warn-primary)}',
      '.cddlp-port.cddlp-inherit{fill:var(--dsw-alias-label-tertiary)}',
      '.cddlp-port.cddlp-faded{fill:var(--dsw-alias-border-l1)}',
      '.cddlp-port.cddlp-cold{opacity:.22}',
      '.cddlp-wire.cddlp-hot{stroke-width:2.6;opacity:1}',
      '.cddlp-wire.cddlp-cold{opacity:.22}',
      '.cddlp-arrowhead.cddlp-hot{opacity:1}',
      '.cddlp-arrowhead.cddlp-cold{opacity:.22}',
      '.cddlp-filebox{position:absolute;box-sizing:border-box;border:2px dashed var(--dsw-alias-border-l4);',
      'border-radius:14px;background:color-mix(in srgb,var(--dsw-alias-bg-layer-2) 34%,transparent)}',
      '.cddlp-filebox strong{position:absolute;left:14px;top:10px;max-width:390px;overflow:hidden;',
      'text-overflow:ellipsis;white-space:nowrap;font:700 12px var(--ds-font-family-code,monospace);',
      'color:var(--dsw-alias-label-primary)}',
      '.cddlp-filebox span{position:absolute;right:14px;top:10px;font:10px var(--ds-font-family-code,monospace);',
      'color:var(--dsw-alias-label-caption)}',
      '.cddlp-nodes{position:relative}',
      '.cddlp-node-shell{position:absolute;cursor:grab}',
      '.cddlp-node-shell.cddlp-dragging{cursor:grabbing;z-index:5}',
      '.cddlp-node-shell.cddlp-dragging *{pointer-events:none}',
      '.cddlp-node-actions{position:absolute;right:0;top:-29px;display:flex;gap:4px;z-index:2;opacity:1}',
      '.cddlp-node-shell:hover .cddlp-node-actions,.cddlp-node-shell:focus-within .cddlp-node-actions{opacity:1}',
      '.cddlp-node-actions button{min-width:31px;height:24px;padding:0 6px;border-radius:6px;cursor:pointer;',
      'font:700 11px var(--ds-font-family-code,monospace);color:var(--dsw-alias-state-business-primary);',
      'background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-state-business-tertiary)}',
      '.cddlp-node-actions .cddlp-action-collapse:not(:disabled){color:var(--dsw-alias-state-warn-primary);',
      'border-color:var(--dsw-alias-state-warn-tertiary)}',
      '.cddlp-node-actions button:hover:not(:disabled),.cddlp-node-actions button.on{color:var(--dsw-alias-label-primary);',
      'border-color:var(--dsw-alias-border-l4);background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddlp-node-actions button:disabled{opacity:.34;cursor:default}',
      '.cddlp-action-help{font-family:var(--ds-font-family-code,monospace);font-weight:600!important}',
      '.cddlp-action-help-plus{color:var(--dsw-alias-state-business-primary)!important}',
      '.cddlp-action-help-minus{color:var(--dsw-alias-state-warn-primary)!important}',
      '.cddlp-gnode{position:relative;box-sizing:border-box;width:100%;background:var(--dsw-alias-bg-layer-2);',
      'border:1px solid var(--dsw-alias-border-l2);border-radius:8px;padding:7px 10px;cursor:pointer;',
      'box-shadow:0 2px 10px rgba(0,0,0,.3)}',
      '.cddlp-gnode:hover{border-color:var(--dsw-alias-border-l4)}',
      '.cddlp-gnode.cddlp-sel{border-color:var(--dsw-alias-state-warn-primary);',
      'box-shadow:0 0 0 1px var(--dsw-alias-state-warn-tertiary),0 6px 18px rgba(0,0,0,.45)}',
      '.cddlp-gnode.cddlp-island{border-style:dashed}',
      '.cddlp-gnode.cddlp-cls{background:var(--dsw-alias-bg-layer-1);border-width:1.5px}',
      '.cddlp-gnode.cddlp-cls .cddlp-gtop{padding-bottom:2px}',
      '.cddlp-gnode .cddlp-sym{overflow:visible;text-overflow:clip;white-space:nowrap;font-size:13.5px;font-weight:500}',
      '.cddlp-gfile{font-family:var(--ds-font-family-code,monospace);font-size:9.5px;',
      'color:var(--dsw-alias-label-caption);margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddlp-gtop{display:flex;align-items:center;gap:6px;flex-wrap:nowrap}',
      '.cddlp-gnode .cddlp-count{background:var(--dsw-alias-bg-layer-3);border:1px solid var(--dsw-alias-border-l2);',
      'border-radius:9px;padding:0 6px;cursor:pointer;color:var(--dsw-alias-label-tertiary);font-size:10px}',
      '.cddlp-members{margin-top:6px;border-top:1px solid var(--dsw-alias-border-l1);padding-top:5px}',
      '.cddlp-m{display:flex;align-items:center;gap:6px;padding:2px 4px;border-radius:5px}',
      '.cddlp-m:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddlp-more{font-size:10px;color:var(--dsw-alias-label-caption);padding:5px 4px 0;text-align:right}',
      '.cddlp-working{margin-top:6px;padding:4px 6px;border-radius:5px;font-size:10px;',
      'color:var(--dsw-alias-state-error-primary);background:var(--dsw-alias-state-error-tertiary);',
      'white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddlp-ghop{display:flex;gap:3px;margin-top:2px;line-height:1.25}',
      '.cddlp-ghop button{font-size:10px;font-family:var(--ds-font-family-code,monospace);cursor:pointer;',
      'color:var(--dsw-alias-label-caption);background:transparent;',
      'border:1px solid var(--dsw-alias-border-l2);border-radius:4px;padding:0 5px}',
      '.cddlp-ghop button:hover{color:var(--dsw-alias-label-primary);background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddlp-ghop button.on{color:var(--dsw-alias-label-primary);border-color:var(--dsw-alias-border-l4)}',
      '.cddlp-sidepanel{grid-column:1;grid-row:3;max-height:38vh;overflow:auto;',
      'border-top:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1)}',
      '.cddlp-sidepanel .cddlp-src pre{max-height:none}',
      '@media (max-width:900px){.cddlp-sidepanel{max-height:46vh}',
      '.cddlp-toolbar .cddlp-search{width:190px}.cddlp-meta{max-width:180px}}',
    ].join('')

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
        style.dataset.plugin = 'dsh-cdd-lens-pcb'
        style.dataset.pluginCss = 'dsh-cdd-lens-pcb/lens.module.css'
        style.textContent = CSS
        document.head.appendChild(style)
        return function () { document.head.removeChild(style) }
      })

      // A slot exists only while the entry that declared it is mounted, and
      // registering into an undeclared slot throws. `inject` runs the
      // registration when the declaration is (or becomes) live, and re-runs it
      // if the owner remounts.
      // No `shell.overlay` registration any more. That slot is not per-tab, so
      // the floating panel painted over whatever the user was actually looking
      // at — including the other lens's tab and the composer underneath it. The
      // view in the conversation tab already owns an engine and the trace
      // subscription, so dropping the panel also drops a second copy of both.

      slots.inject('conversation.view', function () {
        return slots.register({ name: 'conversation.view', id: 'cdd-lens-pcb', order: 20, label: 'CDD Lens PCB' },
          function () { return h(LensView, { ctx: ctx }) })
      })
    }

    // The two halves must answer to the same name, and the name is the ENTRY id
    // from cordis.patch.yml (`cdd-lens-pcb`), not the package name (`dsh-cdd-lens-pcb`).
    // A mismatch loads this module, pairs it to nothing, and never calls apply:
    // no error anywhere, and no panel.
    module.exports = { name: 'cdd-lens-pcb', inject: ['slots', 'sessions', 'uiConversation'], apply: apply }
    return module.exports
  },
})
