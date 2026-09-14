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
    // v2：换成文件框网格后，分层排版时代存下的拖动坐标（x 可能到 3000+）不能再用，会把节点甩出文件框、压到别的框上。
    var NODE_POSITIONS_KEY = 'cdd-lens.node-positions.v2'

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
