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
