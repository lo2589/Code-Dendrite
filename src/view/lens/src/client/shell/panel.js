// dsh-cdd-lens — The floating panel in shell.overlay.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/shell/panel',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __runtime_api = require('dsh-cdd-lens/runtime/api')
    var BUILD = __runtime_api.BUILD
    var api = __runtime_api.api
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var useRightInset = __state_store.useRightInset
    var useShared = __state_store.useShared
    var __state_persist = require('dsh-cdd-lens/state/persist')
    var usePlacement = __state_persist.usePlacement
    var __engine_engine = require('dsh-cdd-lens/engine/engine')
    var makeEngine = __engine_engine.makeEngine
    var __session_trace = require('dsh-cdd-lens/session/trace')
    var useConversationTrace = __session_trace.useConversationTrace
    var __view_record = require('dsh-cdd-lens/view/record')
    var degenerate = __view_record.degenerate
    var __view_stream = require('dsh-cdd-lens/view/stream')
    var Stream = __view_stream.Stream
    var __view_tree = require('dsh-cdd-lens/view/tree')
    var Tree = __view_tree.Tree
    var __view_outline = require('dsh-cdd-lens/view/outline')
    var Draw = __view_outline.Draw
    var Outline = __view_outline.Outline
    var __view_panels = require('dsh-cdd-lens/view/panels')
    var History = __view_panels.History
    var Legend = __view_panels.Legend
    var Search = __view_panels.Search
    var Source = __view_panels.Source
    var Unresolved = __view_panels.Unresolved
    var __view_need_ndex = require('dsh-cdd-lens/view/needIndex')
    var NeedIndex = __view_need_ndex.NeedIndex
    var __shell_chat_eat = require('dsh-cdd-lens/shell/chatSeat')
    var openDockBesideChat = __shell_chat_eat.openDockBesideChat

    function LensPanel(props) {
      var ctx = props.ctx
      useShared()
      var engine = useMemo(function () { return makeEngine(ctx) }, [])
      var open = useState(true)
      var tab = useState('graph')
      var health = useState(null)
      var rootRef = useRef(null)
      var rightInset = useRightInset(rootRef)
      var placement = usePlacement()

      // focus() bumps this; following it puts the graph on screen the moment a
      // function is picked in the directory.
      var wanted = shared.wantGraph || 0
      var seenWant = useRef(wanted)
      useEffect(function () {
        if (wanted !== seenWant.current) { seenWant.current = wanted; tab[1]('graph') }
      }, [wanted])
      var wantedFloat = shared.wantFloat || 0
      var seenFloat = useRef(wantedFloat)
      useEffect(function () {
        if (wantedFloat !== seenFloat.current) {
          seenFloat.current = wantedFloat
          open[1](true)
          tab[1]('graph')
        }
      }, [wantedFloat])

      useEffect(function () {
        engine.context()
        api('/health', {}).then(function (body) { health[1]({ ok: true, body: body }) })
          .catch(function (e) { health[1]({ ok: false, error: String(e.message) }) })
      }, [])
      useConversationTrace(ctx, engine)

      if (!open[0]) {
        return h('div', { className: 'cddl-root', ref: rootRef, style: { right: rightInset + 'px' } },
          h('button', { className: 'cddl-pill', onClick: function () { open[1](true) } },
            ['CDD Lens', shared.turn > 0 ? h('span', { key: 't', className: 'cddl-pilln' }, Object.keys(shared.trace).length) : null]))
      }

      var context = shared.context
      var body
      if (context === undefined) body = h('div', { className: 'cddl-empty' }, '连接中…')
      else if (!context.indexed) body = h(NeedIndex, { engine: engine })
      else if (tab[0] === 'outline') body = h(Outline, { engine: engine })
      else if (tab[0] === 'draw') body = h(Draw, { engine: engine })
      // The rail belongs beside the conversation, not inside the spread-out tab:
      // watching the anchors arrive is something you do WHILE the agent runs,
      // and that tab replaces the chat it is meant to accompany.
      else if (tab[0] === 'steps') body = h(Stream, { engine: engine })
      else body = h(Tree, { engine: engine })

      var stamp = health[0]
      var mismatch = stamp !== null && stamp.ok && (stamp.body.build !== BUILD || !stamp.body.clientBundleMatchesBuild)

      return h('div', {
        className: 'cddl-root', ref: rootRef,
        style: {
          right: (rightInset + placement.place.dx) + 'px',
          bottom: (16 + placement.place.dy) + 'px',
        },
      },
        h('div', { className: 'cddl-card', style: { width: placement.place.w + 'px' } }, [
          h('div', {
            className: 'cddl-grip', key: 'g', title: '拖这里改宽度',
            onPointerDown: placement.onResizeDown,
          }),
          h('div', {
            className: 'cddl-head', key: 'h',
            title: '按住标题拖动面板；双击回到右下角',
            onPointerDown: placement.onMoveDown,
            onDoubleClick: placement.reset,
          }, [
            h('span', { className: 'cddl-title', key: 't' }, 'CDD Lens'),
            h('span', { className: 'cddl-meta', key: 'm', title: context ? context.root : '' },
              context && context.stats
                ? (context.stats.anchors + ' anchor · ' + context.stats.files + ' 文件')
                : (stamp === null ? '…' : (stamp.ok ? '' : stamp.error))),
            degenerate(context)
              ? h('span', {
                key: 'q', className: 'cddl-bad',
                title: '这个工程的索引里 ' + context.stats.anchors + ' 个 anchor 只派生出 '
                  + context.stats.edges + ' 条边。多半是扫进了 node_modules / .venv 之类，'
                  + '调用图画不出来。给这个目录加 .codedendrite_ignore 再重建。',
              }, '索引可疑')
              : null,
            mismatch ? h('span', { key: 'w', className: 'cddl-bad', title: '构建戳对不上：' + stamp.body.build + ' vs ' + BUILD }, '版本不符') : null,
            h('span', { className: 'cddl-spacer', key: 's' }),
            h('button', {
              key: 'dock', className: 'cddl-btn', title: '把逻辑图放到 Chat 右侧',
              onPointerDown: function (e) { e.stopPropagation() },
              onClick: function () { openDockBesideChat(ctx) },
            }, '并排 ⤢'),
            h('button', {
              key: 'r', className: 'cddl-btn', title: '重建索引（增量）',
              onPointerDown: function (e) { e.stopPropagation() },
              onClick: function () { engine.reindex() },
            }, shared.reindexing ? '建索引…' : '↻'),
            h('button', {
              key: 'x', className: 'cddl-btn',
              onPointerDown: function (e) { e.stopPropagation() },
              onClick: function () { open[1](false) },
            }, '—'),
          ]),
          h('div', { className: 'cddl-tabs', key: 'tb' }, [
            h('button', {
              key: 'g', className: tab[0] === 'graph' ? 'on' : '',
              onClick: function () { tab[1]('graph') },
            }, '逻辑图'),
            h('button', {
              key: 'o', className: tab[0] === 'outline' ? 'on' : '',
              onClick: function () { tab[1]('outline') },
            }, '目录'),
            h('button', {
              key: 'd', className: tab[0] === 'draw' ? 'on' : '',
              onClick: function () { tab[1]('draw') },
            }, 'cdd draw'),
            h('button', {
              key: 's', className: tab[0] === 'steps' ? 'on' : '',
              title: '按顺序看这次会话碰过什么',
              onClick: function () { tab[1]('steps') },
            }, '进度'),
          ]),
          h(Search, { key: 'q', engine: engine }),
          h('div', { key: 'b', className: 'cddl-body' }, [body, h(Unresolved, { key: 'u' })]),
          h(Legend, { key: 'l' }),
          h(Source, { key: 's' }),
          h(History, { key: 'y' }),
        ]))
    }

    module.exports = { LensPanel }
    return module.exports
  },
})
