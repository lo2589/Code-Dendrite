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
