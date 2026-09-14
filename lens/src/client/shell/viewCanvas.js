// dsh-cdd-lens — The canvas half of the spread-out view.
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
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
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
    var GraphNode = __view_node.GraphNode

    /**
     * The drawing itself, or whatever stands in for it.
     */
    /**
     * Whether this wire or node is part of what was last lit, and if not,
     * whether anything is lit at all.
     *
     * Dimming the rest is what makes a highlight readable: a brighter line
     * among forty identical ones is not brighter enough to find.
     * @param key - the wire id, or an anchor id.
     * @returns the class to append, possibly empty.
     */
    function litClass(key) {
      var lit = shared.lit
      if (lit === null || lit === undefined) return ''
      if (lit.wires[key] === true || lit.nodes[key] === true) return ' cddl-lit'
      return ' cddl-unlit'
    }

    function renderCanvas(props, view) {
      var context = view.context
      var engine = view.engine
      var model = view.model
      var tab = view.tab
      var zoom = view.zoom

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
            + ((shared.gatherAnimUntil || 0) > Date.now() ? ' cddl-gathering' : ''),
          style: {
            width: model.width + 'px', height: model.height + 'px',
            transform: 'scale(' + zoom[0] + ')', transformOrigin: '0 0',
          },
        }, [
          h('svg', {
              key: 'w', className: 'cddl-wires',
              width: model.width, height: model.height,
              viewBox: '0 0 ' + model.width + ' ' + model.height,
            }, [
              h('defs', { key: 'd' }, [
                h('marker', {
                  key: 'a', id: 'cddl-arrow', markerWidth: 11, markerHeight: 11, refX: 8, refY: 3.4, orient: 'auto',
                }, h('path', { d: 'M0,0 L7,3.4 L0,6.8 z' })),
                h('marker', {
                  key: 'f', id: 'cddl-arrow-faded', markerWidth: 11, markerHeight: 11, refX: 8, refY: 3.4, orient: 'auto',
                }, h('path', { d: 'M0,0 L7,3.4 L0,6.8 z' })),
              ]),
            ].concat(model.wires.map(function (wire) {
              return h('path', {
                key: wire.id, d: wire.d,
                'data-edge-id': wire.id,
                className: 'cddl-wire cddl-' + wire.type
                  + (wire.faded ? ' cddl-faded' : '')
                  + litClass(wire.id)
                  + (shared.edgeFocus ? ' cddl-hot' : '')
                  + (shared.focused === null || shared.focused === undefined ? ''
                    : (wire.from === shared.focused || wire.to === shared.focused ? ' cddl-hot' : ' cddl-cold')),
                'data-from-file': wire.fromFile,
                'data-to-file': wire.toFile,
              })
            })).concat(model.wires.map(function (wire) {
              return h('path', {
                key: 'hit:' + wire.id,
                d: wire.d,
                className: 'cddl-wire-hit',
                'data-edge-focus': wire.from + '→' + wire.to + ':' + wire.type,
                onPointerDown: function (event) { event.stopPropagation() },
                onClick: function (event) {
                  event.preventDefault()
                  event.stopPropagation()
                  engine.lightEdge(wire.from, wire.to, wire.type)
                  engine.focusEdge(wire.from, wire.to, wire.type)
                },
              })
            })).concat(model.arrows.map(function (arrow) {
              // Repeated along the run: on a wire with four bends a single
              // arrowhead at the far end says nothing about the middle.
              return h('path', {
                key: 'a' + arrow.id,
                className: 'cddl-arrowhead cddl-' + arrow.type
                  + (arrow.faded ? ' cddl-faded' : '')
                  + litClass(arrow.wireId || arrow.id)
                  + (shared.edgeFocus ? ' cddl-hot' : '')
                  + (shared.focused === null || shared.focused === undefined ? ''
                    : (arrow.from === shared.focused || arrow.to === shared.focused ? ' cddl-hot' : ' cddl-cold')),
                d: 'M-4.5,-3.2 L4.5,0 L-4.5,3.2 Z',
                transform: 'translate(' + arrow.x + ',' + arrow.y + ') rotate(' + arrow.angle + ')',
              })
            })).concat(model.junctions.map(function (dot) {
              // Filled dot = these wires actually meet. A hop = they only cross.
              return h('circle', {
                key: 'j' + dot.id, className: 'cddl-junction',
                cx: dot.x, cy: dot.y, r: 3.4,
              })
            }))),
          h('div', { key: 'f', className: 'cddl-fileboxes' },
            (model.files || []).map(function (box) {
              return h('div', {
                key: box.file,
                // A flow column guide is not a container: it gets the quiet
                // frame, and the box keeps the loud one for what holds files.
                className: 'cddl-filebox' + (box.frame === 'flow' ? ' cddl-flowbox' : ''),
                'data-file': box.file,
                style: {
                  left: box.x + 'px', top: box.y + 'px',
                  width: box.w + 'px', height: box.h + 'px',
                },
              }, [
                h('strong', { key: 'name', title: box.file }, box.file),
                h('span', { key: 'count' }, box.count + ' anchors'),
              ])
            })),
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
              return h(GraphNode, { key: p.id, p: p, engine: engine, zoom: zoom[0] })
            })),
        ]))
      }

      // 调试栏挂在画布外面、上面：它是个诊断窄栏，不该跟着画布缩放平移。
      // 关掉调试时 DebugBar 返回 null，DOM 里什么也不多。
      return h('div', { className: 'cddl-stage-inner' }, [
        h(DebugBar, { key: 'dbg', build: require('dsh-cdd-lens/runtime/api').BUILD }),
        h('div', { key: 'cv', className: 'cddl-canvasbody' }, canvas),
      ])
    }

    module.exports = { renderCanvas }
    return module.exports
  },
})
