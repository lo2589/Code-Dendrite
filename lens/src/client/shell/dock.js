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
      useEffect(function () {
        engine.context()
        // 索引可能在页面外面被重建（有人跑了 cdd update / rebuild）。不定期问一声，
        // 页面就一直用着上一版 anchor：改过的代码在轨迹里永远显示「没过期」。
        // 放在这个常驻组件里 —— 浮动面板不一定挂载，挂在那儿等于没挂。
        var poll = setInterval(function () { engine.context() }, 10000)
        return function () { clearInterval(poll) }
      }, [])
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
