// dsh-cdd-lens — The canvas half of the spread-out view.
//
// 这个函数每次 publish 都会跑，所以这里必须便宜：
//   线交给线层（view/wireLayer.js）：SVG 只在排版结果换了时建一次，高亮只改 class。
//   卡片用 MemoNode：卡片自己的签名没变就不重画。
//   缩放放在 shared.zoom，不进卡片 props，否则一缩放所有卡片全部重画。
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/shell/viewCanvas',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __view_outline = require('dsh-cdd-lens/view/outline')
    var Draw = __view_outline.Draw
    var Outline = __view_outline.Outline
    var __view_need_ndex = require('dsh-cdd-lens/view/needIndex')
    var NeedIndex = __view_need_ndex.NeedIndex
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var DebugBar = __runtime_debug.DebugBar
    var __view_node = require('dsh-cdd-lens/view/node')
    var MemoNode = __view_node.MemoNode
    var nodeSig = __view_node.nodeSig
    var __view_wire_layer = require('dsh-cdd-lens/view/wireLayer')
    var WireLayer = __view_wire_layer.WireLayer

    function renderCanvas(props, view) {
      var context = view.context
      var engine = view.engine
      var model = view.model
      var tab = view.tab
      var zoom = view.zoom
      // 卡片拖动时换算指针位移用。
      shared.zoom = zoom[0]

      var canvas
      if (context === undefined) canvas = h('div', { className: 'cddl-empty' }, '连接中…')
      else if (!context.indexed) canvas = h(NeedIndex, { engine: engine })
      else if (tab[0] === 'outline') canvas = h('div', { className: 'cddl-scroll' }, h(Outline, { engine: engine }))
      else if (tab[0] === 'draw') canvas = h(Draw, { engine: engine })
      else if (model.nodes.length === 0) {
        canvas = h('div', { className: 'cddl-empty' },
          '还没有起点。切到「目录」翻一个函数，或者上面搜一个名字。')
      } else {
        canvas = h('div', {
          className: 'cddl-scaler cddl-viewport',
          style: { width: (model.width * zoom[0]) + 'px', height: (model.height * zoom[0]) + 'px' },
        }, h('div', {
          className: 'cddl-canvas'
            // On for one flight window only: the cards fly, the wires re-route
            // at once and meet them there. A settled drawing — gathered or
            // not — must never animate, or a drag rubber-bands behind the
            // pointer.
            + ((shared.gatherAnimUntil || 0) > Date.now() ? ' cddl-gathering' : '')
            // 点亮时其余卡片变暗：一个容器 class 管住，不用逐张卡片改 class。
            + (shared.lit !== null && shared.lit !== undefined ? ' cddl-litmode' : ''),
          style: {
            width: model.width + 'px', height: model.height + 'px',
            transform: 'scale(' + zoom[0] + ')', transformOrigin: '0 0',
          },
        }, [
          // 文件框先画、线后画：线压在框的底色上面，不被框盖住。
          h('div', { key: 'f', className: 'cddl-fileboxes' },
            (model.files || []).map(function (box) {
              return h('div', {
                key: box.file,
                // A flow column guide is not a container: it gets the quiet
                // frame, and the box keeps the loud one for what holds files.
                className: 'cddl-filebox' + (box.frame === 'flow' ? ' cddl-flowbox' : '') + (box.frame === 'side' ? ' cddl-sidebox' : ''),
                'data-file': box.file,
                style: {
                  left: box.x + 'px', top: box.y + 'px',
                  width: box.w + 'px', height: box.h + 'px',
                },
              }, [
                h('strong', { key: 'name', title: box.file }, box.label || box.file),
                h('span', { key: 'count' }, box.count + ' 个节点'),
              ])
            })),
          h(WireLayer, { key: 'w', model: model, engine: engine }),
          h('div', { key: 'r', className: 'cddl-rowlabels' },
            model.rows.map(function (row, i) {
              return h('div', {
                key: i, className: 'cddl-rowlabel' + (row.island ? ' cddl-island-label' : ''),
                // A label belongs over its own tree, not pinned to the left
                // edge — with the trees side by side that put every one of them
                // on top of the first.
                style: { top: (row.y - 16) + 'px', left: (row.x === undefined ? 16 : row.x) + 'px' },
              }, row.label)
            })),
          h('div', { key: 'c', className: 'cddl-chips' },
            model.rows.filter(function (row) { return row.island && row.label }).map(function (row, i) {
              return h('div', {
                key: i, className: 'cddl-chip', style: { top: (row.y - 30) + 'px', right: '24px' },
              }, row.ids.length + ' 个本轮节点 · 不在当前根链')
            })),
          h('div', { key: 'n', className: 'cddl-nodes', style: { width: model.width + 'px', height: model.height + 'px' } },
            model.nodes.map(function (p) {
              return h(MemoNode, { key: p.id, p: p, engine: engine, sig: nodeSig(engine, p) })
            })),
        ]))
      }

      // 调试栏默默放在最底下、跟着内容走（用户：「log默默放最底层就好不要浮在上面占屏幕位置」）。
      // 它不跟着画布缩放；关掉调试时 DebugBar 返回 null，DOM 里什么也不多。
      return h('div', { className: 'cddl-stage-inner' }, [
        h('div', { key: 'cv', className: 'cddl-canvasbody' }, canvas),
        h(DebugBar, { key: 'dbg', build: require('dsh-cdd-lens/runtime/api').BUILD }),
      ])
    }

    module.exports = { renderCanvas }
    return module.exports
  },
})
