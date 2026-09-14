// dsh-cdd-lens — 调试 log：默认开。
//
// 每个按钮按下、之后每一步做了什么（读哪个字段、发什么请求、拿回多少、建了几个节点
// 几条边、画出多少）都记一条带毫秒时间的 log：显示在图面板顶部的窄栏里，同时打到浏览器
// 控制台（`[cdd 时间] [类别]` 前缀）。点了没反应时，看最后一条 log 就知道断在哪一步。
//
// 关闭：`?cddl-debug=0`，或 localStorage 里 `cdd-lens.debug.v1=0`。
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/runtime/debug',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement

    var KEY = 'cdd-lens.debug.v1'
    var MAX = 200
    var SHOWN = 12

    /** 开关：默认开；只有明确写了 0 才关。 */
    function debugEnabled() {
      try {
        if (typeof window !== 'undefined' && window.location) {
          var q = new URLSearchParams(window.location.search)
          if (q.get('cddl-debug') === '0') return false
          if (q.get('cddl-debug') === '1') return true
        }
        if (window.localStorage.getItem(KEY) === '0') return false
      } catch (e) { /* 读不到开关就按默认开 */ }
      return true
    }

    var on = debugEnabled()
    var events = []
    var facts = {}

    function clock() {
      var d = new Date()
      var pad = function (n, w) { return String(n).padStart(w, '0') }
      return pad(d.getHours(), 2) + ':' + pad(d.getMinutes(), 2) + ':' + pad(d.getSeconds(), 2) + '.' + pad(d.getMilliseconds(), 3)
    }

    function snapshot() {
      return { enabled: on, facts: facts, events: events.slice() }
    }

    /**
     * 记一条 log。
     * @param kind - 'btn' | 'expand' | 'screen' | 'req' | 'res' | 'graph' | 'layout' | 'error' …
     * @param text - 一行描述。
     */
    function note(kind, text) {
      if (!on) return
      var entry = { at: clock(), kind: kind, text: String(text).slice(0, 300) }
      events.push(entry)
      if (events.length > MAX) events.splice(0, events.length - MAX)
      try { console.log('[cdd ' + entry.at + '] [' + kind + '] ' + entry.text) } catch (e) { /* 没有控制台就只进窄栏 */ }
      try {
        window.__cddLens = window.__cddLens || {}
        window.__cddLens.debug = snapshot
      } catch (e) { /* 没有 window 就算了 */ }
    }

    /** 覆盖式的事实：节点数、边数这些「当前值」。 */
    function fact(name, value) {
      if (!on) return
      facts[name] = value
    }

    /** 调试窄栏：最近 SHOWN 条 log。 */
    function DebugBar(props) {
      if (!on) return null
      var lines = []
      Object.keys(facts).forEach(function (k) { lines.push(k + '=' + facts[k]) })
      var shown = events.slice(-SHOWN)
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
          'CDD log ' + (props.build || '') + '  ' + lines.join('  ') + '  （关闭：?cddl-debug=0）'),
        h('div', { key: 'e' }, shown.map(function (e, i) {
          return h('div', { key: i, style: e.kind === 'error' ? { color: 'var(--dsw-alias-label-danger, #d33)' } : null },
            e.at + ' [' + e.kind + '] ' + e.text)
        })),
      ])
    }

    module.exports = { debugEnabled, note, fact, snapshot, DebugBar, isOn: function () { return on } }
    return module.exports
  },
})
