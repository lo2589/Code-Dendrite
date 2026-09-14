// dsh-cdd-lens — The toolbar of the spread-out view.
//
// 树开关、关系开关只改视图状态（engine/screen.js），屏幕由 /screen 重算；
// 每棵树按钮上直接写「N节点/M关系」，数字就是选中这棵树时屏幕上的数。
// 每个按钮点下去都记一条 log（runtime/debug）。
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
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var shared = __state_store.shared
    var __state_persist = require('dsh-cdd-lens/state/persist')
    var clearNodePositions = __state_persist.clearNodePositions
    var __view_panels = require('dsh-cdd-lens/view/panels')
    var Search = __view_panels.Search
    var __shell_chat_eat = require('dsh-cdd-lens/shell/chatSeat')
    var openDockBesideChat = __shell_chat_eat.openDockBesideChat
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note

    var TREE_BUTTONS = [
      ['degree1', '1 度树', 'seed 之间直接有边，中间不插点'],
      ['degree2', '2 度树', '没连上的 seed 上下游各展开 2 度，剪到头和叶都是 seed'],
      ['edit', 'edit 树', '同 2 度树，但头和叶只认 edit 过的 seed'],
    ]
    var RELATIONS = ['call', 'dataflow', 'inherit', 'impact', 'dispatch']

    /** 按钮点击：先记 log，再做事。 */
    function clicked(label, fn) {
      return function (event) {
        note('btn', '按下 ' + label)
        return fn(event)
      }
    }

    function treeSelector(engine) {
      var view = engine.view()
      var totals = (shared.screen && shared.screen.treeTotals) || {}
      return h('div', { key: 'tree', className: 'cddl-seg cddl-tree', 'aria-label': '看哪棵树' },
        TREE_BUTTONS.map(function (t) {
          var n = totals[t[0]]
          var on = view.tree === t[0]
          return h('button', {
            key: t[0],
            className: on ? 'on' : '',
            'aria-pressed': on ? 'true' : 'false',
            'data-tree': t[0],
            'data-nodes': n ? n.nodes : '',
            'data-edges': n ? n.edges : '',
            title: t[2] + (n ? '\n旁边另有 ' + n.side + ' 个 seed' : ''),
            onClick: function () { engine.setTree(t[0]) },
          }, t[1] + (n ? ' ' + n.nodes + '节点/' + n.edges + '关系' : ''))
        }))
    }

    /** edit 保留几轮：每个节点自己的计时器，edit 一次加 N 轮，每过一轮减 1，到 0 不再算 edit 过。 */
    function editKeepInput(engine) {
      var keep = engine.view().editKeep || 7
      return h('label', { key: 'keep', className: 'cddl-meta cddl-editkeep', title: '每个节点自己的计时器：edit 一次加 N 轮，每过一轮减 1，到 0 就不再算 edit 过的节点' }, [
        'edit 保留 ',
        h('input', {
          key: 'n', type: 'number', min: 1, max: 99, step: 1, value: keep, 'data-edit-keep': keep, style: { width: '44px' },
          onChange: function (event) { engine.setEditKeep(event.target.value) },
        }),
        ' 轮',
      ])
    }

    function relationSelector(engine) {
      var rels = engine.view().rels
      return h('div', { key: 'rel', className: 'cddl-seg cddl-relations', 'aria-label': '关系开关' },
        RELATIONS.map(function (name) {
          return h('button', {
            key: name,
            className: rels[name] ? 'on' : '',
            'aria-pressed': rels[name] ? 'true' : 'false',
            onClick: function () { engine.toggleRelation(name) },
          }, name)
        }))
    }

    /**
     * The control strip above the canvas.
     */
    function renderToolbar(props, view) {
      var context = view.context
      var ctx = view.ctx
      var engine = view.engine
      var fit = view.fit
      var layoutRevision = view.layoutRevision
      var setZoom = view.setZoom
      var tab = view.tab
      var zoom = view.zoom

      return h('div', { className: 'cddl-toolbar', key: 't' }, [
        h('div', { key: 'seg', className: 'cddl-seg' }, [
          h('button', { key: 'g', className: tab[0] === 'graph' ? 'on' : '', onClick: clicked('逻辑图', function () { tab[1]('graph') }) }, '逻辑图'),
          h('button', { key: 'o', className: tab[0] === 'outline' ? 'on' : '', onClick: clicked('目录', function () { tab[1]('outline') }) }, '目录'),
          h('button', { key: 'd', className: tab[0] === 'draw' ? 'on' : '', onClick: clicked('cdd draw', function () { tab[1]('draw') }) }, 'cdd draw'),
        ]),
        tab[0] !== 'graph' ? null : treeSelector(engine),
        tab[0] !== 'graph' ? null : editKeepInput(engine),
        h(Search, { key: 'q', engine: engine }),
        relationSelector(engine),
        h('span', { key: 'm', className: 'cddl-meta', title: context ? context.root : '' },
          context && context.stats ? (context.stats.anchors + ' anchor · ' + context.stats.edges + ' 边 · ' + context.stats.files + ' 文件') : ''),
        shared.screenError ? h('span', { key: 'err', className: 'cddl-meta cddl-error', title: shared.screenError }, '屏幕计算失败') : null,
        h('span', { key: 's', className: 'cddl-spacer' }),
        h('div', { key: 'z', className: 'cddl-zoom', 'aria-label': '缩放控制' }, [
          h('button', { key: 'o', className: 'cddl-btn', onClick: clicked('缩小', function () { setZoom(zoom[0] - .1) }) }, '−'),
          h('button', { key: 'n', className: 'cddl-btn', onClick: clicked('缩放 100%', function () { setZoom(1) }) }, Math.round(zoom[0] * 100) + '%'),
          h('button', { key: 'i', className: 'cddl-btn', onClick: clicked('放大', function () { setZoom(zoom[0] + .1) }) }, '＋'),
        ]),
        h('button', {
          key: 'l', className: 'cddl-btn',
          onClick: clicked('恢复自动布局', function () {
            clearNodePositions()
            // 框的先后也按交流重新算一遍。
            shared.boxOrder = null
            layoutRevision[1](function (n) { return n + 1 })
            publish()
          }),
        }, '恢复自动布局'),
        h('button', {
          key: 'a', className: 'cddl-btn', title: '缩小到能看见全图（会看不清字）',
          onClick: clicked('适配', function () { fit(shared.selected || shared.graph.rootId, .35) }),
        }, '适配'),
        props.docked ? null : h('button', {
          key: 'float', className: 'cddl-btn',
          onClick: clicked('并排 Chat', function () { openDockBesideChat(ctx) }),
        }, '并排 Chat ⤢'),
        h('button', {
          key: 'r', className: 'cddl-btn',
          onClick: function () { engine.reindex() },
        }, shared.reindexing ? '建索引…' : '↻ 重建索引'),
        h('button', {
          key: 'f', className: 'cddl-btn', title: '去掉所有展开和 pin',
          onClick: function () { engine.resetView() },
        }, '清空'),
      ])
    }

    module.exports = { renderToolbar }
    return module.exports
  },
})
