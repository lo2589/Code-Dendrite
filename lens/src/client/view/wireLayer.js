// dsh-cdd-lens — 线层：SVG 只在排版结果换了时建一次（照 visual_map/js/graph-render.js）。
//
// 以前每次 publish（选中、高亮、拖动的每一帧）都用 React 重新生成全部线：
// 532 根线 + 532 根点击线 + 1557 个箭头，React 逐个比对。现在：
//   排版结果换了 → 清空重建一次：每根线一条线、一条合并的箭头路径（2 或 3 个三角）、一条点击线
//   高亮 / 聚焦变了 → 只改 class，且只改真的变了的那几根
//   拖动 → 只改被拖节点自己那几根线的 d，不经过 React、不重排
//   点线 → svg 上一个监听器，按 data-from / data-to / data-type 认线
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/wireLayer',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __routing_emit = require('dsh-cdd-lens/routing/emit')
    var pathFrom = __routing_emit.pathFrom
    var arrowPoints = __routing_emit.arrowPoints
    var triangleAt = __routing_emit.triangleAt
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note
    var NS = 'http://www.w3.org/2000/svg'

    // 当前画着的线。拖动时 node.js 通过 dragNode 直接改这里的元素。
    var live = { entries: [], byNode: {}, every: 0, painted: null }

    function wireKey(wire) {
      return wire.from + '→' + wire.to + ':' + wire.type
    }

    /** 高亮、聚焦给一根线加的 class（线和它的箭头共用同一套）。 */
    function stateClass(wire) {
      var out = ''
      var lit = shared.lit
      if (lit !== null && lit !== undefined) {
        out += lit.wires[wire.id] === true || lit.wires[wireKey(wire)] === true ? ' cddl-lit' : ' cddl-unlit'
      }
      if (shared.edgeFocus) out += ' cddl-hot'
      var focused = shared.focused
      if (focused !== null && focused !== undefined) {
        out += wire.from === focused || wire.to === focused ? ' cddl-hot' : ' cddl-cold'
      }
      return out
    }

    function wireClass(wire) {
      return 'cddl-wire cddl-' + wire.type + (wire.faded ? ' cddl-faded' : '') + stateClass(wire)
    }

    function arrowClass(wire) {
      return 'cddl-arrowhead cddl-' + wire.type + (wire.faded ? ' cddl-faded' : '') + stateClass(wire)
    }

    /** 决定线的 class 的全部输入；没变就不用逐根重算。 */
    function paintKey() {
      var lit = shared.lit
      return (lit === null || lit === undefined ? '' : lit.key) + '|' + (shared.edgeFocus ? 1 : 0) + '|' + (shared.focused || '')
    }

    function el(tag, attrs) {
      var node = document.createElementNS(NS, tag)
      Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]) })
      return node
    }

    function arrowD(heads) {
      return heads.map(triangleAt).join(' ')
    }

    function remember(byNode, id, entry) {
      if (byNode[id] === undefined) byNode[id] = []
      if (byNode[id].indexOf(entry) < 0) byNode[id].push(entry)
    }

    /** 排版结果 → SVG 元素。只在排版结果换了时调用。@returns 建了多少根线、多少条箭头路径 */
    function build(svg, model) {
      var t0 = Date.now()
      while (svg.firstChild) svg.removeChild(svg.firstChild)
      var heads = {}
      ;(model.arrows || []).forEach(function (a) {
        var k = a.wireId || a.id
        if (heads[k] === undefined) heads[k] = []
        heads[k].push(a)
      })
      var lines = el('g', {})
      var hits = el('g', {})
      var arrows = el('g', {})
      var dots = el('g', {})
      var entries = []
      var byNode = {}
      model.wires.forEach(function (wire) {
        var entry = { wire: wire, pts: wire.pts || [], cls: wireClass(wire), acls: arrowClass(wire), arrow: null }
        entry.line = el('path', { d: wire.d, class: entry.cls, 'data-edge-id': wire.id })
        entry.hit = el('path', {
          d: wire.d, class: 'cddl-wire-hit', 'data-edge-focus': wireKey(wire),
          'data-from': wire.from, 'data-to': wire.to, 'data-type': wire.type,
        })
        lines.appendChild(entry.line)
        hits.appendChild(entry.hit)
        if (heads[wire.id] !== undefined) {
          entry.arrow = el('path', { d: arrowD(heads[wire.id]), class: entry.acls })
          arrows.appendChild(entry.arrow)
        }
        entries.push(entry)
        remember(byNode, wire.from, entry)
        remember(byNode, wire.to, entry)
      })
      ;(model.junctions || []).forEach(function (dot) {
        dots.appendChild(el('circle', { class: 'cddl-junction', cx: dot.x, cy: dot.y, r: 3.4 }))
      })
      svg.appendChild(lines)
      svg.appendChild(hits)
      svg.appendChild(arrows)
      svg.appendChild(dots)
      var arrowPaths = entries.filter(function (e) { return e.arrow !== null }).length
      live = { entries: entries, byNode: byNode, every: model.arrowEvery || 0, painted: paintKey() }
      note('render', '线层重建：线 ' + entries.length + ' · 箭头路径 ' + arrowPaths + '（' + (model.arrows || []).length
        + ' 个箭头）· 元素 ' + (entries.length * 2 + arrowPaths) + ' · ' + (Date.now() - t0) + 'ms')
      return { wires: entries.length, arrowPaths: arrowPaths }
    }

    /** 高亮 / 聚焦变了：只改变了的 class。@returns 改了几根线 */
    function paint() {
      var key = paintKey()
      if (key === live.painted) return 0
      live.painted = key
      var changed = 0
      live.entries.forEach(function (e) {
        var cls = wireClass(e.wire)
        if (cls !== e.cls) { e.cls = cls; e.line.setAttribute('class', cls); changed += 1 }
        if (e.arrow === null) return
        var acls = arrowClass(e.wire)
        if (acls !== e.acls) { e.acls = acls; e.arrow.setAttribute('class', acls) }
      })
      return changed
    }

    /**
     * 拖动中的一帧：被拖节点那一头的端点跟着挪，线和箭头重新算，其它线一根不碰。
     * @returns 改了几根线
     */
    function dragNode(id, dx, dy) {
      var list = live.byNode[id] || []
      list.forEach(function (e) {
        if (e.pts.length < 2) return
        var pts = e.pts.map(function (pt) { return { x: pt.x, y: pt.y } })
        if (e.wire.from === id) { pts[0].x += dx; pts[0].y += dy }
        if (e.wire.to === id) { pts[pts.length - 1].x += dx; pts[pts.length - 1].y += dy }
        var d = pathFrom(pts)
        e.line.setAttribute('d', d)
        e.hit.setAttribute('d', d)
        if (e.arrow !== null && live.every > 0) e.arrow.setAttribute('d', arrowD(arrowPoints(pts, live.every)))
      })
      return list.length
    }

    function isHit(target) {
      return target !== null && target !== undefined && typeof target.getAttribute === 'function'
        && target.getAttribute('class') === 'cddl-wire-hit'
    }

    /** 点线：高亮这根线前后两个节点，并把起点带进视野。@returns 是不是点在线上 */
    function clickWire(target, engine) {
      if (!isHit(target)) return false
      var from = target.getAttribute('data-from')
      var to = target.getAttribute('data-to')
      var type = target.getAttribute('data-type')
      engine.lightEdge(from, to, type)
      engine.focusEdge(from, to, type)
      return true
    }

    function WireLayer(props) {
      var ref = React.useRef(null)
      var engineRef = React.useRef(props.engine)
      engineRef.current = props.engine
      var model = props.model

      React.useEffect(function () {
        var svg = ref.current
        if (svg === null) return undefined
        // 点在线上不能开始平移画布。
        var down = function (event) { if (isHit(event.target)) event.stopPropagation() }
        var click = function (event) {
          if (!clickWire(event.target, engineRef.current)) return
          event.preventDefault()
          event.stopPropagation()
        }
        svg.addEventListener('pointerdown', down)
        svg.addEventListener('click', click)
        return function () {
          svg.removeEventListener('pointerdown', down)
          svg.removeEventListener('click', click)
        }
      }, [])
      React.useEffect(function () { if (ref.current !== null) build(ref.current, model) }, [model])
      React.useEffect(function () { paint() })

      return h('svg', {
        ref: ref, className: 'cddl-wires',
        width: model.width, height: model.height,
        viewBox: '0 0 ' + model.width + ' ' + model.height,
      })
    }

    module.exports = { WireLayer, build, paint, dragNode, clickWire, wireClass, arrowClass }
    return module.exports
  },
})
