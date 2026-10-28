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
    var useState = React.useState
    var useEffect = React.useEffect
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
      // Only what is genuinely lying on top of this view, measured against the
      // view's own box, is reserved on the right.
      var viewRef = useRef(null)
      var reserve = useOverlapInset(viewRef)

      // The source panel belongs to this view; the trajectory rail has to be
      // told when this view is actually on screen.
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

      var selectedNow = shared.selected
      useEffect(function () {
        if (selectedNow === null || selectedNow === undefined) engine.releaseGather()
      }, [selectedNow])

      // Re-measured on every resize.
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

      // 画什么只由 shared.screen 决定（后端计算单元）；这里只排版。
      var model = useMemo(function () {
        return layout(shared.graph, undefined, availWidth[0])
      }, [shared.revision, layoutRevision[0], availWidth[0]])

      // 量浏览器里真画出来的卡片高度：和排版用的高度差 1px 以上就记下来、重排一次（只在真的变了时，不会来回跳）。
      // 按 CSS 估的高度估小了（按钮换行、名字折行），卡片会撑出文件框、压到下一个框。
      useEffect(function () {
        var el = canvasRef.current
        if (el === null || typeof el.querySelectorAll !== 'function') return
        var byId = {}
        model.nodes.forEach(function (p) { byId[p.id] = p })
        shared.cardHeights = shared.cardHeights || {}
        var changed = 0
        el.querySelectorAll('.cddl-node-shell[data-node-id]').forEach(function (shell) {
          var p = byId[shell.getAttribute('data-node-id')]
          var h = shell.offsetHeight
          if (p === undefined || !(h > 0) || Math.abs(h - p.h) <= 1) return
          var known = shared.cardHeights[p.id]
          if (known && known.h === h && Math.abs(known.w - p.w) < 1) return
          shared.cardHeights[p.id] = { w: p.w, h: h }
          changed += 1
        })
        if (changed === 0) return
        require('dsh-cdd-lens/runtime/debug').note('layout', '量到 ' + changed + ' 张卡片实际高度和估的不一样，按实际高度重排文件框')
        shared.cardHeightsRev = (shared.cardHeightsRev || 0) + 1
        publish()
      }, [model])

      var setZoom = function (value) {
        zoom[1](Math.max(.35, Math.min(1.8, Math.round(value * 100) / 100)))
      }
      /**
       * 这个节点现在看得见吗：只在看不见时才动视口。
       *
       * **露出一部分就算看得见。** 以前要求整张卡片完整落在视口里、四周还留 12px：卡片露出
       * 一半——用户正点着它的展开按钮——也被当成"看不见"，视口居中过去，整张图一跳。
       * 用户正在看、正在点的东西，视口一像素都不该动。完全不在视野里，才把它带过来。
       */
      var onScreen = function (el, id, m, scale) {
        if (el === null) return true
        var target = m.nodes.filter(function (p) { return p.id === id })[0]
        if (target === undefined) return false
        var left = target.x * scale, top = target.y * scale
        var right = (target.x + target.w) * scale, bottom = (target.y + target.h) * scale
        return right > el.scrollLeft && left < el.scrollLeft + el.clientWidth
          && bottom > el.scrollTop && top < el.scrollTop + el.clientHeight
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

      var viewportRequest = shared.viewportRequest || {
        id: shared.selected || shared.graph.rootId,
        mode: 'fit',
        seq: 0,
      }
      // 视口只在真的有人请求时才动：同一个 seq 只消费一次，重画多少次视口都不动。
      var lastSeq = useRef(-1)
      useEffect(function () {
        if (tab[0] !== 'graph' || model.nodes.length === 0) return
        if (viewportRequest.seq === lastSeq.current) return
        lastSeq.current = viewportRequest.seq
        var frame = window.requestAnimationFrame(function () {
          if (viewportRequest.mode === 'fit') {
            var readable = Math.max(zoom[0], 1)
            if (zoom[0] !== readable) setZoom(readable)
            window.requestAnimationFrame(function () {
              // 没选中任何节点：停在左上角，第一个文件框就在眼前；选中了才居中到它。
              var el = canvasRef.current
              if ((shared.selected === null || shared.selected === undefined) && el !== null) { el.scrollLeft = 0; el.scrollTop = 0 }
              else centerOn(viewportRequest.id, readable)
            })
          } else if (viewportRequest.mode === 'ensure') {
            if (!onScreen(canvasRef.current, viewportRequest.id, model, zoom[0])) centerOn(viewportRequest.id, zoom[0])
          } else centerOn(viewportRequest.id, zoom[0])
        })
        return function () { window.cancelAnimationFrame(frame) }
      }, [tab[0], viewportRequest.seq])

      return { ctx: ctx, engine: engine, tab: tab, zoom: zoom, layoutRevision: layoutRevision, canvasRef: canvasRef, context: context, viewRef: viewRef, reserve: reserve, model: model, setZoom: setZoom, centerOn: centerOn, fit: fit }
    }

    module.exports = { useViewState }
    return module.exports
  },
})
