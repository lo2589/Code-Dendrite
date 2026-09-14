// dsh-cdd-lens — The toolbar of the spread-out view.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/shell/viewToolbar',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var emptyGraph = __graph_model.emptyGraph
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var shared = __state_store.shared

    var SKIN_KEY = 'cdd-lens.skin.v1'
    // Restored once, before anything draws, so the first frame is already the
    // drawing this browser last asked for rather than a flash of the other one.
    var __state_persist = require('dsh-cdd-lens/state/persist')
    var clearNodePositions = __state_persist.clearNodePositions
    var __view_panels = require('dsh-cdd-lens/view/panels')
    var Search = __view_panels.Search
    var __shell_chat_eat = require('dsh-cdd-lens/shell/chatSeat')
    var openDockBesideChat = __shell_chat_eat.openDockBesideChat

    /**
     * The control strip above the canvas.
     */
    function renderToolbar(props, view) {
      var context = view.context
      var ctx = view.ctx
      var engine = view.engine
      var fit = view.fit
      var layoutRevision = view.layoutRevision
      var model = view.model
      var relations = view.relations
      var setZoom = view.setZoom
      var tab = view.tab
      var toggleRelation = view.toggleRelation
      var zoom = view.zoom

      // Kept per browser: which drawing someone prefers is a reading habit, not
      // a property of the repository.

      return h('div', { className: 'cddl-toolbar', key: 't' }, [
          h('div', { key: 'seg', className: 'cddl-seg' }, [
            h('button', { key: 'g', className: tab[0] === 'graph' ? 'on' : '', onClick: function () { tab[1]('graph') } }, '逻辑图'),
            h('button', { key: 'o', className: tab[0] === 'outline' ? 'on' : '', onClick: function () { tab[1]('outline') } }, '目录'),
            h('button', { key: 'd', className: tab[0] === 'draw' ? 'on' : '', onClick: function () { tab[1]('draw') } }, 'cdd draw'),
          ]),
          // 树选择器。规则文档 §1.3 定义了四棵树；这里就是选它看哪一棵。
          //   直接树 = 1 度树：seed 之间直接有边，中间不插点
          //   anchor 树：单个 anchor 周围直接相连的邻居，也不插点
          //   2 度树：允许一个中间点把两个 seed 接起来
          //   edit 树：只管 edit 过的那批 anchor
          // 「全部」不套任何树，把图里现有的都画出来。
          tab[0] !== 'graph' ? null
            : h('div', { key: 'tree', className: 'cddl-seg cddl-tree', 'aria-label': '看哪棵树' },
              [['all', '全部'], ['anchor', 'anchor 树'], ['degree1', '1 度树'], ['degree2', '2 度树'], ['edit', 'edit 树']]
                .map(function (pair) {
                  var value = pair[0]
                  return h('button', {
                    key: value,
                    className: (shared.treeMode || 'all') === value ? 'on' : '',
                    'aria-pressed': (shared.treeMode || 'all') === value ? 'true' : 'false',
                    title: value === 'degree1' ? 'seed 之间直接有边的那些，中间不插点'
                      : value === 'degree2' ? '允许一个中间点把两个 seed 接起来'
                      : value === 'edit' ? '只看这次会话 edit 过的 anchor'
                      : value === 'anchor' ? '当前选中 anchor 周围直接相连的邻居'
                      : '图里现有的全部画出来',
                    onClick: function () {
                      shared.treeMode = value
                      publish()
                    },
                  }, pair[1])
                })),
          h(Search, { key: 'q', engine: engine }),
          h('div', { key: 'rel', className: 'cddl-seg cddl-relations', 'aria-label': '关系筛选' },
            ['call', 'dataflow', 'inherit', 'impact', 'dispatch'].map(function (name) {
              return h('button', {
                key: name,
                className: relations[0][name] ? 'on' : '',
                'aria-pressed': relations[0][name] ? 'true' : 'false',
                onClick: function () { toggleRelation(name) },
              }, name)
            })),
          h('span', { key: 'm', className: 'cddl-meta', title: context ? context.root : '' },
            context && context.stats ? (context.stats.anchors + ' anchor · ' + context.stats.edges + ' 边 · ' + context.stats.files + ' 文件') : ''),
          h('span', { key: 's', className: 'cddl-spacer' }),
          h('div', { key: 'layout-mode', className: 'cddl-seg cddl-layout-mode', 'aria-label': '布局状态' }, [
            h('button', {
              key: 'user', className: shared.edgeFocus ? '' : 'on',
              onClick: function () { engine.blurEdge() },
            }, '用户布局'),
            h('button', {
              key: 'focus', className: shared.edgeFocus ? 'on' : '',
              title: shared.edgeFocus
                ? (shared.edgeFocus.type === 'dataflow' ? '完整数据流链路；再次点线或按 Esc 返回' : '依赖前后各 3 跳；再次点线或按 Esc 返回')
                : '点击任意连线进入链路聚焦',
              onClick: function () { if (shared.edgeFocus) engine.blurEdge() },
            }, shared.edgeFocus
              ? (shared.edgeFocus.type === 'dataflow' ? '完整数据链' : '依赖 ±3 跳')
              : '链路聚焦'),
          ]),
          h('div', { key: 'z', className: 'cddl-zoom', 'aria-label': '缩放控制' }, [
            h('button', { key: 'o', className: 'cddl-btn', onClick: function () { setZoom(zoom[0] - .1) } }, '−'),
            h('button', { key: 'n', className: 'cddl-btn', onClick: function () { setZoom(1) } }, Math.round(zoom[0] * 100) + '%'),
            h('button', { key: 'i', className: 'cddl-btn', onClick: function () { setZoom(zoom[0] + .1) } }, '＋'),
          ]),
          h('button', {
            key: 'l', className: 'cddl-btn',
            onClick: function () {
              clearNodePositions()
              shared.edgeFocus = null
              layoutRevision[1](function (n) { return n + 1 })
              publish()
            },
          }, '恢复自动布局'),
          h('button', {
            key: 'a', className: 'cddl-btn', title: '缩小到能看见全图（会看不清字）',
            onClick: function () { fit(shared.selected || shared.graph.rootId, .35) },
          }, '适配'),
          // No "收进浮窗" any more. The floating panel it fed is gone, so the
          // button did nothing a user could see — and a graph that can pop
          // itself out over the page is the mess this view is supposed to
          // replace. Beside Chat is the only place it goes.
          props.docked ? null : h('button', {
            key: 'float', className: 'cddl-btn',
            onClick: function () { openDockBesideChat(ctx) },
          }, '并排 Chat ⤢'),
          h('button', {
            key: 'r', className: 'cddl-btn',
            onClick: function () { engine.reindex() },
          }, shared.reindexing ? '建索引…' : '↻ 重建索引'),
          h('button', {
            key: 'wire-mode', className: 'cddl-btn' + (shared.wireMode === 'all' ? ' on' : ''),
            title: shared.wireStats
              ? (shared.wireMode === 'all'
                ? '正在画全部 ' + shared.wireStats.total + ' 条关系'
                : '只画主干；另有 ' + shared.wireStats.hidden + ' 条关系按节点上的 ↑↓ 展开')
              : '',
            onClick: function () {
              shared.wireMode = shared.wireMode === 'all' ? 'tree' : 'all'
              publish()
            },
          }, shared.wireMode === 'all'
            ? ('全部关系 ' + (shared.wireStats ? shared.wireStats.total : ''))
            : ('主干 ' + (shared.wireStats ? shared.wireStats.drawn + '/' + shared.wireStats.total : ''))),
          h('button', {
            key: 'f', className: 'cddl-btn',
            onClick: function () { shared.graph = emptyGraph(); publish() },
          }, '清空'),
        ])
    }

    module.exports = { renderToolbar }
    return module.exports
  },
})
