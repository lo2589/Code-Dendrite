// dsh-cdd-lens — 悬浮层：常驻的数据主人 + 轨迹栏。
//
// **这个插件里能悬浮的有且只有轨迹栏。** 逻辑图不悬浮，它住在会话里的「CDD Lens」
// 页，和 Chat 并列。悬浮的图盖在页面上，一开一关整页的东西都换位置，正在追的那个
// 节点就丢了 —— 这正是「焦点不能丢」里第一条。
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
    var useEffect = React.useEffect
    var useMemo = React.useMemo
    var __engine_engine = require('dsh-cdd-lens/engine/engine')
    var makeEngine = __engine_engine.makeEngine
    var __session_trace = require('dsh-cdd-lens/session/trace')
    var useConversationTrace = __session_trace.useConversationTrace
    var __view_stream = require('dsh-cdd-lens/view/stream')
    var TrajectorySidebar = __view_stream.TrajectorySidebar

    // 轨迹栏是否已被 dsh-plugin-rightbar 托管。rightbar 是可选的：没装就永远 false，
    // 轨迹栏照旧自己浮着；装了，entry.js 的 inject 把它置 true，浮动的那条就不画。
    var hostedState = { value: false, listeners: new Set() }
    function setTrajectoryHosted(value) {
      hostedState.value = value === true
      hostedState.listeners.forEach(function (fn) { fn() })
    }
    function subscribeHosted(fn) {
      hostedState.listeners.add(fn)
      return function () { hostedState.listeners.delete(fn) }
    }
    function readHosted() { return hostedState.value }

    /** Always-on data owner with no visible panel. */
    function LensRuntime(props) {
      var engine = useMemo(function () { return makeEngine(props.ctx) }, [])
      useEffect(function () {
        engine.context()
        // 索引可能在页面外面被重建（有人跑了 cdd update / rebuild）。不定期问一声，
        // 页面就一直用着上一版 anchor：改过的代码在轨迹里永远显示「没过期」。
        // 放在这个常驻组件里 —— 别的面板不一定挂载，挂在那儿等于没挂。
        var poll = setInterval(function () { engine.context() }, 10000)
        return function () { clearInterval(poll) }
      }, [])
      useConversationTrace(props.ctx, engine)
      return null
    }

    function LensOverlay(props) {
      var hosted = React.useSyncExternalStore(subscribeHosted, readHosted, readHosted)
      return h(React.Fragment, null, [
        h(LensRuntime, { key: 'runtime', ctx: props.ctx }),
        hosted ? null : h(TrajectorySidebar, { key: 'trajectory', ctx: props.ctx }),
      ])
    }

    module.exports = { LensRuntime, LensOverlay, setTrajectoryHosted }
    return module.exports
  },
})
