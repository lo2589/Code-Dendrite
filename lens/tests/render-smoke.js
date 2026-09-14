// 每个模块都能实例化，每个主组件都能渲染出东西来。
//
// 白屏的成因从来不是数字算错，是某个组件在渲染期抛了——一抛整棵树没了，
// 而布局测试全绿，因为它们只调 layout()，从不渲染。这个文件补的就是那一层：
// 模块能不能起，组件渲不渲得出，以及渲染量有没有上界。
//
//   node lens/scripts/build.js && node lens/tests/render-smoke.js
const fs = require('fs'), vm = require('vm'), assert = require('assert')

const factories = new Map(), cache = new Map()
let states = [], si = 0
const React = {
  createElement: (t, p, ...k) => ({ type: t, props: p || {}, kids: k.flat() }),
  Fragment: 'fragment',
  useState: v => {
    const i = si++
    if (states[i] === undefined) states[i] = typeof v === 'function' ? v() : v
    return [states[i], n => { states[i] = typeof n === 'function' ? n(states[i]) : n }]
  },
  useEffect: () => {}, useMemo: f => f(), useRef: v => ({ current: v }), useCallback: f => f,
}
const require_ = id => {
  if (id === 'react') return React
  if (cache.has(id)) return cache.get(id)
  assert(factories.has(id), 'missing module ' + id)
  const v = factories.get(id)(require_); cache.set(id, v); return v
}
const ctx = {
  window: {
    __ModuleLoader__: { load: r => factories.set(r.id, r.factory) },
    localStorage: { getItem: () => null, setItem: () => {} },
    matchMedia: () => ({ matches: false }),
    requestAnimationFrame: () => 0, cancelAnimationFrame: () => {},
    setInterval: () => 1, clearInterval: () => {},
    addEventListener: () => {}, removeEventListener: () => {},
    location: { origin: 'http://x' }, innerWidth: 1400, innerHeight: 900,
  },
  document: {
    querySelector: () => null, querySelectorAll: () => [],
    createElement: () => ({ style: {}, getContext: () => ({ measureText: () => ({ width: 40 }) }) }),
    head: { appendChild() {} }, body: { appendChild() {} },
    documentElement: { style: { setProperty() {}, removeProperty() {} } },
  },
  navigator: {}, MutationObserver: function () {},
  ResizeObserver: function () { this.observe = () => {}; this.disconnect = () => {} },
  URLSearchParams,
  fetch: () => Promise.resolve({ status: 200, json: () => Promise.resolve({}) }),
  console, JSON, Math, Number, Object, String, Array, isFinite,
  setTimeout, clearTimeout, setInterval, clearInterval,
}
vm.createContext(ctx)
vm.runInContext(fs.readFileSync('lib/client.js', 'utf8'), ctx, { filename: 'built.js' })

let bad = 0
const ids = [...factories.keys()]
const broken = ids.filter(id => { try { require_(id); return false } catch (e) { console.log('✗ ' + id + ' — ' + e.message.split('\n')[0]); return true } })
if (broken.length) bad += broken.length
console.log((broken.length ? '✗ ' : '✓ ') + '模块实例化'.padEnd(10) + (ids.length - broken.length) + '/' + ids.length)

const shared = require_('dsh-cdd-lens/state/store').shared
const model = require_('dsh-cdd-lens/graph/model')
const count = n => (!n || typeof n !== 'object') ? 0 : 1 + (n.kids || []).reduce((s, k) => s + count(k), 0)
const textOf = n => {
  if (n === null || n === undefined) return ''
  if (typeof n === 'string' || typeof n === 'number') return String(n)
  if (typeof n !== 'object') return ''
  return (n.kids || []).map(textOf).join('')
}
const findAll = (node, pred, out = []) => {
  if (node && typeof node === 'object') {
    if (pred(node)) out.push(node)
    ;(node.kids || []).forEach(k => findAll(k, pred, out))
  }
  return out
}
const assertUniqueSiblingKeys = (node, path = 'root') => {
  if (!node || typeof node !== 'object') return
  const kids = (node.kids || []).filter(k => k && typeof k === 'object')
  const seen = new Set()
  for (const kid of kids) {
    const key = kid.props && kid.props.key
    if (key !== undefined && key !== null) {
      assert(!seen.has(key), `duplicate sibling key ${String(key)} at ${path}`)
      seen.add(key)
    }
  }
  kids.forEach((kid, index) => assertUniqueSiblingKeys(kid, `${path}/${String(kid.type)}[${index}]`))
}
const engine = { outline: () => {}, fileSymbols: () => {}, focus: () => {}, params: () => ({ root: '/x' }) }

const render = (name, fn, floor) => {
  si = 0; states = []
  try {
    const out = fn()
    const n = count(out)
    const ok = n >= (floor === undefined ? 1 : floor)
    if (!ok) bad += 1
    console.log((ok ? '✓ ' : '✗ ') + name.padEnd(10) + '渲染出 ' + n + ' 个节点')
    return out
  } catch (e) {
    bad += 1
    console.log('✗ ' + name.padEnd(10) + '抛异常: ' + e.message.split('\n')[0])
    return null
  }
}

// 空图：工具栏和空态都要在
shared.graph = model.emptyGraph(); shared.trace = {}; shared.outline = undefined
const lensView = render('LensView', () => require_('dsh-cdd-lens/shell/graphView').LensView({ ctx: { on: () => () => {} } }), 3)
assertUniqueSiblingKeys(lensView)
console.log('✓ ' + 'React keys'.padEnd(10) + '每组同级节点的 key 唯一')
assert(!textOf(lensView).includes('铺满宽度'), '不可用的铺满宽度按钮必须从工具栏移除')
console.log('✓ ' + '工具栏'.padEnd(10) + '不再渲染铺满宽度按钮')
const wraps = findAll(lensView, n => n.props && String(n.props.className || '').split(/\s+/).includes('cddl-canvaswrap'))
assert.strictEqual(wraps.length, 1, 'LensView must have exactly one scroll-owning canvaswrap')
console.log('✓ ' + '画布 DOM'.padEnd(10) + '只有一层 cddl-canvaswrap')

// 目录：真实规模。4566 个目录一次性进 DOM 就是一个卡死的标签页。
const many = []
for (let i = 0; i < 4566; i += 1) {
  many.push({ dir: 'p/pkg' + i, count: 6, files: [{ file: 'p/pkg' + i + '/a.js', count: 3 }] })
}
shared.outline = many
const tree = render('Outline', () => require_('dsh-cdd-lens/view/outline').Outline({ engine }), 5)
assert(count(tree) < 1200, '目录一屏渲染的节点数必须有上界，实际 ' + count(tree))
console.log('✓ ' + '目录上界'.padEnd(10) + '4566 个目录 → ' + count(tree) + ' 个节点')

// 目录读不出来：null 不许把整棵树带走
shared.outline = null
render('目录为 null', () => require_('dsh-cdd-lens/view/outline').Outline({ engine }), 1)

shared.outline = undefined

// A visible wire click must enter line focus, not only paint a weak highlight.
// The old handler called lightEdge alone, so the toolbar promised "链路聚焦"
// while the graph stayed in the crowded PCB view.
;(function wireClickFocusesAndArrowFollowsHighlight() {
  const renderCanvas = require_('dsh-cdd-lens/shell/viewCanvas').renderCanvas
  const layer = require_('dsh-cdd-lens/view/wireLayer')
  const calls = []
  shared.lit = { key: 'a→b:call', type: 'call', nodes: {}, wires: { 'a→b:call': true } }
  shared.edgeFocus = null
  shared.focused = null
  const stubEngine = {
    lightEdge: (from, to, type) => { calls.push(['lightEdge', from, to, type]) },
    focusEdge: (from, to, type) => { calls.push(['focusEdge', from, to, type]) },
    isPinned: () => false, isOpen: () => false, isBusy: () => false,
  }
  const out = renderCanvas({}, {
    context: { indexed: true },
    tab: ['graph'],
    zoom: [1],
    engine: stubEngine,
    model: {
      width: 200, height: 120, files: [], rows: [], junctions: [],
      nodes: [
        {
          id: 'a', x: 10, y: 30, w: 70, h: 45,
          node: { id: 'a', symbol: 'a', file: 'a.js', kind: 'function', line_start: 1, line_end: 4, up: 0, down: 1 },
        },
        {
          id: 'b', x: 120, y: 30, w: 70, h: 45,
          node: { id: 'b', symbol: 'b', file: 'b.js', kind: 'function', line_start: 5, line_end: 8, up: 1, down: 0 },
        },
      ],
      wires: [{ id: 'a→b:call', d: 'M10,10 L120,10', type: 'call', from: 'a', to: 'b' }],
      arrows: [{ id: 'a→b:call:head0', wireId: 'a→b:call', type: 'call', from: 'a', to: 'b', x: 80, y: 10, angle: 0 }],
    },
  })
  // 线由线层自己建 SVG（不经过 React）：画布里有线层，线层拿到的就是这份排版结果。
  let wireLayer = null
  ;(function walk(n) {
    if (!n || typeof n !== 'object') return
    if (n.type === layer.WireLayer) wireLayer = n
    ;(n.kids || []).forEach(walk)
  })(out)
  assert(wireLayer !== null, 'canvas must mount the wire layer')
  assert.strictEqual(wireLayer.props.model.wires.length, 1, 'wire layer draws the model it was given')
  // 点击走 svg 上的一个监听器：按 data-from / data-to / data-type 认线。
  const attrs = { class: 'cddl-wire-hit', 'data-from': 'a', 'data-to': 'b', 'data-type': 'call' }
  assert(layer.clickWire({ getAttribute: k => attrs[k] }, stubEngine), 'click on a hit path is a wire click')
  assert(!layer.clickWire({ getAttribute: () => 'cddl-wire' }, stubEngine), 'click elsewhere is not')
  assert.deepEqual(calls, [['lightEdge', 'a', 'b', 'call'], ['focusEdge', 'a', 'b', 'call']])
  const wire = { id: 'a→b:call', type: 'call', from: 'a', to: 'b' }
  assert(layer.arrowClass(wire).includes('cddl-lit'), 'arrowhead must follow the lit wire')
  assert(layer.wireClass({ id: 'x→y:call', type: 'call', from: 'x', to: 'y' }).includes('cddl-unlit'), 'other wires dim')
  shared.lit = null
  console.log('✓ ' + '线点击'.padEnd(10) + '进入链路聚焦，箭头跟随高亮')
})()

// 「有几个关系挂几个」：按钮只读 /screen 给的 screen.buttons（就是 len(关系+up/down)），
// 没有数据的关系一个都不出现——不画箭头、不写 0。卡片和树面板的数字必须一样。
;(function buttonsComeFromScreen() {
  const { GraphNode } = require_('dsh-cdd-lens/view/node')
  const { TreeRow } = require_('dsh-cdd-lens/view/tree')
  const { makeEngine } = require_('dsh-cdd-lens/engine/engine')
  const real = makeEngine({ get: () => undefined })
  const anchor = { id: 'a.py::f', symbol: 'f', file: 'a.py', symbol_type: 'function', line_start: 1, line_end: 9 }
  shared.graph = model.emptyGraph()
  model.addNode(shared.graph, anchor)
  shared.graph.rootId = anchor.id
  shared.view = null
  shared.screen = {
    nodes: [anchor.id], side: [], edges: [], pinned: [], treeTotals: {},
    buttons: { [anchor.id]: { callup: 8, calldown: 2, inheritup: 3, inheritdown: 1 } },
  }
  shared.selected = null
  shared.trace = {}
  shared.turn = 1

  const collect = (root) => {
    const out = []
    const walk = n => {
      if (!n || typeof n !== 'object') return
      if (n.type === 'button' && n.props && n.props['data-relation']) {
        out.push({ rel: n.props['data-relation'], count: Number(n.props['data-count']), cls: String(n.props.className || '') })
      }
      ;(n.kids || []).forEach(walk)
    }
    walk(root)
    return out
  }
  const buttons = collect(GraphNode({
    engine: real, zoom: 1,
    p: { id: anchor.id, x: 0, y: 0, w: 180, h: 80, node: shared.graph.nodes[anchor.id] },
  }))
  const treeButtons = collect(TreeRow({ engine: real, row: { id: anchor.id, depth: 0, node: shared.graph.nodes[anchor.id] } }))

  const rels = buttons.map(b => b.rel)
  const counts = buttons.map(b => b.count).sort((a, b) => a - b)
  assert.strictEqual(buttons.length, 4, 'one button per relation per direction, absent ones omitted')
  assert(!rels.includes('dataflow') && !rels.includes('dispatch') && !rels.includes('impact'),
    'a relation with no data renders no button and no zero')
  assert.deepEqual(counts, [1, 2, 3, 8], 'each button carries its own count from screen.buttons')
  assert(buttons.filter(b => b.rel === 'call').every(b => b.cls.includes('cddl-rel-call')), 'call buttons carry the call colour class')
  assert(buttons.filter(b => b.rel === 'inherit').every(b => b.cls.includes('cddl-rel-inherit')), 'inherit buttons carry the inherit colour class')
  assert.deepEqual(treeButtons.map(b => b.count).sort((a, b) => a - b), counts, 'tree panel shows the same numbers as the card')
  console.log('✓ ' + '按钮来自屏幕'.padEnd(10) + 'call ↑8↓2 · inherit ↑3↓1 · 其余不出现 · 树面板同数')
})()

// 按钮只改视图状态（shared.view），节点和边不在前端增删；pin 记下第几轮 pin、第几轮取消。
;(function buttonsOnlyChangeViewState() {
  const { makeEngine } = require_('dsh-cdd-lens/engine/engine')
  const real = makeEngine({ get: () => undefined })
  shared.view = null
  shared.turn = 3
  const before = Object.keys(shared.graph.nodes).length
  real.toggleOpen('a.py::f', 'dataflow', 'up')
  assert(real.isOpen('a.py::f', 'dataflow', 'up'), 'first press records the open')
  real.toggleOpen('a.py::f', 'dataflow', 'up')
  assert(!real.isOpen('a.py::f', 'dataflow', 'up'), 'second press collapses')
  real.pin('a.py::f')
  assert(real.isPinned('a.py::f') && shared.view.pins[0].at === 3, 'pin records the turn it started')
  shared.turn = 5
  real.pin('a.py::f')
  assert(!real.isPinned('a.py::f') && shared.view.pins[0].until === 5, 'unpin records the turn it stopped')
  assert.strictEqual(Object.keys(shared.graph.nodes).length, before, 'buttons never add or remove nodes on the client')
  console.log('✓ ' + '按钮只改状态'.padEnd(10) + '展开/收起/pin/取消 pin 都只写 shared.view')
})()

// 用真的 engine 渲染，不用手捏的。
//
// `cdd draw` 从来没打开过：Draw 调 engine.params()，而 makeEngine 只把 params
// 当参数传给各个方法工厂，从没挂到 engine 上。测试没抓到，是因为测试里的 engine
// 是我按 Draw 的需要捏的——stub 比真货能干，bug 就藏在这个差值里。
;(function realEngineHasWhatTheViewsCall() {
  const { makeEngine } = require_('dsh-cdd-lens/engine/engine')
  const real = makeEngine({ on: () => () => {}, emit: () => {} })
  const needed = ['params', 'outline', 'fileSymbols', 'focus', 'source', 'reindex']
  const missing = needed.filter(k => typeof real[k] !== 'function')
  if (missing.length) bad += 1
  console.log((missing.length ? '✗ ' : '✓ ') + '真 engine'.padEnd(10)
    + (missing.length ? '缺: ' + missing.join(', ') : needed.length + ' 个入口都在'))

  si = 0; states = []
  try {
    const out = require_('dsh-cdd-lens/view/outline').Draw({ engine: real })
    assert.equal(out.type, 'iframe', 'Draw must mount its paged shell on the first render')
    console.log('✓ ' + 'Draw'.padEnd(10) + '用真 engine 渲染出 ' + count(out) + ' 个节点')
  } catch (e) {
    bad += 1
    console.log('✗ ' + 'Draw'.padEnd(10) + '用真 engine 抛: ' + e.message.split('\n')[0])
  }
})()

// A steady draw-status response is not a state change. The poller used to
// compare against the first render captured by its effect, manufacture a new
// object on every 8-second poll, and repaint the toolbar forever.
;(function stableDrawStatusDoesNotRepaint() {
  const { drawStampAfter } = require_('dsh-cdd-lens/view/outline')
  const ready = { stamp: 123 }
  assert.strictEqual(drawStampAfter(ready, { ready: true, stamp: 123, building: false }), ready,
    'unchanged ready response must preserve state identity')
  assert.strictEqual(drawStampAfter(ready, { ready: false, stamp: 124, building: true }), ready,
    'a building response must leave the current shell mounted')
  const rebuilt = drawStampAfter(ready, { ready: true, stamp: 124, building: false })
  assert.notStrictEqual(rebuilt, ready, 'a new drawing stamp must repaint')
  assert.deepEqual(rebuilt, { stamp: 124 })
  console.log('✓ ' + 'Draw 轮询'.padEnd(10) + '稳定响应不再触发重渲染')
})()

// 错误边界：抛出去的东西必须变成看得见的字，而不是一块白。
;(function boundaryShowsTheError() {
  function Component(props) { this.props = props }
  Component.prototype.setState = function (next) { Object.assign(this.state, next) }
  const { makeBoundary } = require_('dsh-cdd-lens/shell/boundary')
  const Boundary = makeBoundary(Object.assign({}, React, { Component: Component }))
  if (Boundary === null) { bad += 1; console.log('✗ 错误边界    没能建立'); return }
  const b = new Boundary({ children: 'x' })
  b.state = Boundary.getDerivedStateFromError(new Error('故意炸一下'))
  const out = b.render()
  const flat = []
  ;(function walk(n) {
    if (n === null || n === undefined) return
    if (typeof n === 'string') { flat.push(n); return }
    if (Array.isArray(n)) { n.forEach(walk); return }
    ;(n.kids || []).forEach(walk)
  })(out)
  const text = flat.join(' ')
  const ok = text.indexOf('故意炸一下') >= 0 && text.indexOf('渲染失败') >= 0
  if (!ok) bad += 1
  console.log((ok ? '✓ ' : '✗ ') + '错误边界'.padEnd(10) + '抛出的话被显示出来：' + text.slice(0, 40) + '…')
})()

console.log(bad === 0 ? '\n✓ 渲染冒烟通过' : '\n' + bad + ' 处渲染问题')
process.exit(bad === 0 ? 0 : 1)
