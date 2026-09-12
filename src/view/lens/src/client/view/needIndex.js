// dsh-cdd-lens — The no-index-yet placeholder.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/needIndex',
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

    // ---- no index yet ------------------------------------------------------

    /**
     * A workspace with no index yet.
     *
     * The host already started the build when it answered /context — nothing
     * here asks anyone to run a command. This only reports progress, and offers
     * a retry for the one case that needs a decision: a build that failed.
     */
    function NeedIndex(props) {
      var engine = props.engine
      var context = shared.context
      useEffect(function () {
        var timer = setInterval(function () { engine.reindexStatus() }, 1200)
        return function () { clearInterval(timer) }
      }, [])
      var failed = shared.reindexError !== undefined && shared.reindexError !== null
      return h('div', { className: 'cddl-empty' }, [
        h('div', { key: 'a' }, failed ? '建索引失败：' : '这个工程还没索引，正在建（后台跑，不占聊天）：'),
        h('div', { key: 'b', className: 'cddl-path' }, context ? context.root : ''),
        failed ? h('div', { key: 'e', className: 'cddl-bad' }, shared.reindexError) : null,
        failed
          ? h('button', { key: 'c', className: 'cddl-primary', onClick: function () { engine.reindex() } }, '重试')
          : h('div', { key: 'c', className: 'cddl-progress' },
            shared.reindexing === false && context && !context.indexed ? '启动中…' : '正在建索引…'),
        shared.reindexTail ? h('pre', { key: 'd', className: 'cddl-tail' }, shared.reindexTail) : null,
      ])
    }

    /**
     * Subscribe to this session's conversation-view target.
     *
     * The shell owns the subscription and the paging; this only forwards each
     * snapshot into the graph. There is no interval over session data, so
     * nothing here competes with a streaming turn.
     */

    module.exports = { NeedIndex }
    return module.exports
  },
})
