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
    var setTrajectoryHosted = __shell_dock.setTrajectoryHosted
    var __view_stream = require('dsh-cdd-lens/view/stream')
    var TrajectorySidebar = __view_stream.TrajectorySidebar
    var __styles_shell = require('dsh-cdd-lens/styles/shell')
    var SHELL_CSS = __styles_shell.SHELL_CSS
    var __styles_graph = require('dsh-cdd-lens/styles/graph')
    var GRAPH_CSS = __styles_graph.GRAPH_CSS
    var __runtime_api = require('dsh-cdd-lens/runtime/api')
    var api = __runtime_api.api
    var BUILD = __runtime_api.BUILD

    var CSS = SHELL_CSS.concat(GRAPH_CSS).join('')

    function apply(ctx) {
      // 第一件事：告诉 host「apply 真的跑了，跑的是这一版」。/health 的 client 块靠它，
      // 面板不出现时一眼分得清是没 apply，还是 apply 了但画不出来。回报失败不挡面板。
      api('/applied', { build: BUILD }).catch(function () {})
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

      // 可选：装了 dsh-plugin-rightbar 就把轨迹栏挂成它的「轨迹」标签。没装时 rightbar.tab
      // 永远不会被声明，这个 inject 永远不触发，轨迹栏照旧自己浮着；rightbar 卸载时
      // disposer 把托管标记放回去，浮动的轨迹栏自动回来。不是安装依赖。
      slots.inject('rightbar.tab', function () {
        var dispose = slots.register({ name: 'rightbar.tab', id: 'cdd-trajectory', order: 10, label: '轨迹' },
          function () {
            var rail = h(TrajectorySidebar, { ctx: ctx, hosted: true })
            return Boundary === null ? rail : h(Boundary, null, rail)
          })
        setTrajectoryHosted(true)
        return function () { dispose(); setTrajectoryHosted(false) }
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
