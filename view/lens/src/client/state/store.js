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
