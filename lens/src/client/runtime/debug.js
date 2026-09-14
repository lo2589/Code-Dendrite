// dsh-cdd-lens — Debug 模式。
//
// 图上点不出来的时候，光看画面分不清是哪一层坏的：请求没发出去、服务端返回空、
// 布局收到 0 个节点、还是渲染时抛错——四种在屏幕上都长成一样（一片空白）。
//
// 这个模块把这三层的事实都记下来，并显示在图面板顶部的一条窄栏里：
//
//   请求   最近几次 /expand /walk /resolve 的路径、HTTP 码、返回数量
//   图的形状  ingest 之后有多少节点、多少边；布局收到多少、画出多少
//   错误   任何一层抛出的原始消息（截断到一行）
//
// 开关：`?cddl-debug=1` 或 localStorage 里的 `cdd-lens.debug=1`。
// 关掉时所有记录都是空操作，不影响正常路径。
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/runtime/debug',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement

    var KEY = 'cdd-lens.debug.v1'
    var MAX = 24

    /** 开关状态：URL 参数优先，其次 localStorage，默认关。 */
    function debugEnabled() {
      try {
        if (typeof window !== 'undefined' && window.location) {
          var q = new URLSearchParams(window.location.search)
          if (q.get('cddl-debug') === '1') return true
          if (q.get('cddl-debug') === '0') return false
        }
        var stored = window.localStorage.getItem(KEY)
        if (stored === '1') return true
        if (stored === '0') return false
      } catch (e) { /* 隐私模式下 localStorage 会抛，按关闭处理 */ }
      return false
    }

    var on = debugEnabled()
    var events = []
    var facts = {}

    /**
     * 记一条事件。任何一层都可以调，关掉时是空操作。
     *
     * @param kind - 'req' | 'res' | 'graph' | 'layout' | 'error'。
     * @param text - 一行描述。
     */
    function note(kind, text) {
      if (!on) return
      events.push({ at: new Date().toLocaleTimeString(), kind: kind, text: String(text).slice(0, 220) })
      if (events.length > MAX) events.splice(0, events.length - MAX)
      // 也挂到 window 上：控制台里 `__cddLens.debug()` 直接能看。
      try {
        window.__cddLens = window.__cddLens || {}
        window.__cddLens.debug = debugSnapshot
      } catch (e) { /* 没有 window 就算了 */ }
    }

    /** 覆盖式的事实：节点数、边数这些「当前值」。 */
    function fact(name, value) {
      if (!on) return
      facts[name] = value
    }

    function snapshot() {
      return { enabled: on, facts: facts, events: events.slice() }
    }

    /** 调试窄栏。关掉调试时不渲染任何东西。 */
    function DebugBar(props) {
      if (!on) return null
      var lines = []
      Object.keys(facts).forEach(function (k) { lines.push(k + '=' + facts[k]) })
      var shown = events.slice(-6)
      return h('div', {
        className: 'cddl-debugbar',
        style: {
          fontSize: '10px', lineHeight: '1.45', padding: '4px 8px',
          borderBottom: '1px solid var(--dsw-alias-border-l2)',
          background: 'var(--dsw-alias-bg-layer-3)',
          color: 'var(--dsw-alias-label-secondary)',
          fontFamily: 'var(--ds-font-family-code,monospace)',
          whiteSpace: 'pre-wrap', maxHeight: '30vh', overflow: 'auto',
        },
      }, [
        h('div', { key: 'f', style: { fontWeight: 700, color: 'var(--dsw-alias-label-primary)' } },
          'CDD debug ' + (props.build || '') + '  ' + lines.join('  ')),
        h('div', { key: 'e' }, shown.map(function (e, i) {
          return h('div', { key: i }, e.at + ' [' + e.kind + '] ' + e.text)
        })),
      ])
    }

    module.exports = { debugEnabled, note, fact, snapshot, DebugBar, isOn: function () { return on } }
    return module.exports
  },
})
