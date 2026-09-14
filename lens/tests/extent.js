// Nothing may be drawn where it cannot be reached.
//
// The canvas has one size and the viewport scrolls inside it. A coordinate
// below zero, or past width/height, is not "off screen for now" — scrollLeft
// stops at 0, so that pixel can never be brought into view by any amount of
// panning. It is drawn and it is gone.
//
// This asks the layout for a drawing and then checks every coordinate it
// produced: node corners, file boxes, junctions, labels, arrowheads, and every
// number in every wire's path. All of them must fall inside the width and
// height the layout reported for that same drawing.
//
//   node lens/scripts/build.js && node lens/tests/extent.js
//
// It fails today: wires bend outward further than the margin the canvas was
// given, so the canvas has to be sized from what was actually drawn rather
// than from where the nodes ended up.
const fs = require('fs'), vm = require('vm')

function stubEnv() {
  const store = {}
  const React = {
    createElement: (type, props, ...kids) => ({ type, props, kids }),
    useState: v => [v, () => {}], useEffect: () => {}, useCallback: f => f,
    useMemo: f => f(), useRef: () => ({ current: null }),
  }
  const factories = new Map(), cache = new Map()
  const seed = new Map([['react', React]])
  const require_ = spec => {
    if (seed.has(spec)) return seed.get(spec)
    if (cache.has(spec)) return cache.get(spec)
    if (!factories.has(spec)) throw new Error('missing module ' + spec)
    const exports = factories.get(spec)(require_)
    cache.set(spec, exports)
    return exports
  }
  const win = {
    __ModuleLoader__: { load: r => factories.set(r.id, r.factory) },
    localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v) }, removeItem: k => { delete store[k] } },
    requestAnimationFrame: () => 0, cancelAnimationFrame: () => {}, setTimeout, clearTimeout, setInterval, clearInterval,
    addEventListener: () => {}, removeEventListener: () => {}, location: { origin: 'http://x' },
  }
  const ctx = {
    window: win, globalThis: win, React, URLSearchParams, fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
    document: { querySelector: () => null, querySelectorAll: () => [], createElement: () => ({ style: {}, classList: { add() {}, remove() {} }, appendChild() {} }), head: { appendChild() {} }, body: { appendChild() {} }, documentElement: { style: { setProperty() {}, removeProperty() {} } } },
    console, Math, JSON, setTimeout, clearTimeout, setInterval, clearInterval,
  }
  vm.createContext(ctx)
  return { ctx, require_, factories }
}


const B = stubEnv(); vm.runInContext(fs.readFileSync('lib/client.js', 'utf8'), B.ctx, { filename: 'built.js' })
const side = {
  layout: B.require_('dsh-cdd-lens/layout/layout').layout,
  shared: B.require_('dsh-cdd-lens/state/store').shared,
  emptyGraph: B.require_('dsh-cdd-lens/graph/model').emptyGraph,
  addNode: B.require_('dsh-cdd-lens/graph/model').addNode,
  addEdge: B.require_('dsh-cdd-lens/graph/model').addEdge,
  uiOf: B.require_('dsh-cdd-lens/graph/model').uiOf,
  placeOf: B.require_('dsh-cdd-lens/graph/model').placeOf,
  setPlace: B.require_('dsh-cdd-lens/graph/model').setPlace,
}
function build(side, seed) {
  const g = side.emptyGraph()
  const anchors = [
    ['a/main.js::main', 'main', 'a/main.js', 'function', 0],
    ['a/main.js::boot', 'boot', 'a/main.js', 'function', 0],
    ['a/main.js::wire', 'wire', 'a/main.js', 'function', 0],
    ['b/panel.js::Panel', 'Panel', 'b/panel.js', 'class', 4],
    ['b/panel.js::render', 'Panel.render', 'b/panel.js', 'function', 0],
    ['b/panel.js::mount', 'Panel.mount', 'b/panel.js', 'function', 0],
    ['c/util.js::clamp', 'clamp', 'c/util.js', 'function', 0],
    ['c/util.js::orphan', 'orphan', 'c/util.js', 'function', 0],
  ]
  anchors.forEach(([id, symbol, file, kind, members], i) => {
    side.addNode(g, { id, symbol, file, kind, members, line_start: i * 10 + 1, line_end: i * 10 + 9 })
  })
  g.rootId = seed.noRoot === true ? null : 'a/main.js::main'
  const edges = [
    ['a/main.js::main', 'a/main.js::boot', ['call']],
    ['a/main.js::main', 'b/panel.js::Panel', ['call']],
    ['a/main.js::boot', 'a/main.js::wire', ['call']],
    ['a/main.js::wire', 'b/panel.js::mount', ['call', 'dispatch']],
    ['b/panel.js::Panel', 'b/panel.js::render', ['inherit']],
    ['b/panel.js::render', 'c/util.js::clamp', ['call']],
    ['a/main.js::boot', 'c/util.js::clamp', ['dataflow']],
    ['b/panel.js::mount', 'a/main.js::main', ['impact']],
  ]
  edges.forEach(([f, t, types]) => side.addEdge(g, f, t, types))
  g.edges.forEach(e => { e.always = true })
  // What ingest would have marked: these anchors are the session's own, and
  // both directions are expanded so the walk reaches the whole graph.
  // 交互状态住在 graph.ui，不在 anchor 记录上。
  Object.keys(g.nodes).forEach(id => { Object.assign(side.uiOf(g, id), { session: true, down: true, up: true }) })
  side.uiOf(g, 'c/util.js::orphan').session = false
  if (seed.tiered) {
    var seats = {
      'a/main.js::main': [0, 0],
      'a/main.js::boot': [1, 0], 'b/panel.js::Panel': [1, 0],
      'a/main.js::wire': [2, 0], 'b/panel.js::render': [2, 0],
      'b/panel.js::mount': [3, 0], 'c/util.js::clamp': [3, 0],
      'c/util.js::orphan': [0, 1],
    }
    Object.keys(seats).forEach(id => {
      side.setPlace(g, id, Object.assign(side.placeOf(g, id) || {}, {
        layer: seats[id][0], tree: seats[id][1],
      }))
    })
  }
  const trace = {}
  anchors.forEach(([id], i) => { trace[id] = { lastTurn: 4, firstTurn: 1, kind: i % 3 === 0 ? 'edit' : 'read', remembered: i !== 6 } })
  Object.assign(side.shared, { trace: trace, turn: 4 })
  Object.assign(side.shared, seed)
  return g
}


// Every coordinate the drawing puts on the canvas.
function points(m) {
  const out = []
  const push = (x, y, what) => { if (typeof x === 'number' && typeof y === 'number' && isFinite(x) && isFinite(y)) out.push({ x, y, what }) }
  m.nodes.forEach(n => { push(n.x, n.y, 'node ' + n.id); push(n.x + n.w, n.y + n.h, 'node ' + n.id) })
  m.files.forEach(f => { push(f.x, f.y, 'filebox ' + f.file); push(f.x + f.w, f.y + f.h, 'filebox ' + f.file) })
  ;(m.junctions || []).forEach(j => push(j.x, j.y, 'junction'))
  ;(m.labels || []).forEach(l => push(l.x, l.y, 'label ' + (l.text || '')))
  ;(m.arrows || []).forEach(a => push(a.x, a.y, 'arrow'))
  ;(m.wires || []).forEach(w => {
    require('./svg-geometry.cjs').segments(w.d).forEach(([a,b]) => { push(a.x,a.y,'wire '+w.id);push(b.x,b.y,'wire '+w.id) })
  })
  return out
}

const CASES = [
  ['默认', {}, undefined, 900],
  ['选中一个节点', { selected: 'a/main.js::wire' }, undefined, 900],
  ['窄画布 420', {}, undefined, 420],
  ['很窄 320', {}, undefined, 320],
  ['分层拓扑窄屏', { tiered: true }, undefined, 420],
  ['全部关系打开', {}, { call: true, dataflow: true, inherit: true, impact: true, dispatch: true }, 1200],
  ['线路镜头', { edgeFocus: { from: 'a/main.js::boot', to: 'a/main.js::wire', type: 'call' } }, undefined, 900],
  ['人工坐标(远)', { nodePositions: { 'b/panel.js::render': { x: 1400, y: 900 } } }, undefined, 900],
  // A node dragged above or left of the origin is the one thing that makes
  // the layered path shift what it already drew. It used to throw there.
  ['分层·拖到负坐标', { tiered: true, nodePositions: { 'b/panel.js::render': { x: -600, y: -400 } } }, undefined, 900],
]

let bad = 0
for (const [label, seed, filter, avail] of CASES) {
  const base = { selected: null, edgeFocus: null, nodePositions: {}, pins: {}, turn: 4 }
  const g = build(side, Object.assign({}, base, seed))
  const m = side.layout(g, filter, avail)
  const pts = points(m)
  const out = pts.filter(p => p.x < 0 || p.y < 0 || p.x > m.width || p.y > m.height)
  const minX = Math.min(...pts.map(p => p.x)), maxX = Math.max(...pts.map(p => p.x))
  const minY = Math.min(...pts.map(p => p.y)), maxY = Math.max(...pts.map(p => p.y))
  // Every case here has edges, so a drawing with no wires is a drawing that
  // was computed and then thrown away — which looks fine to a bounds check.
  const wires = (m.wires || []).length
  const mark = wires === 0 ? '一条线都没有' : (out.length === 0 ? '全部在内' : `越界 ${out.length}/${pts.length}`)
  console.log(`${out.length || wires === 0 ? '✗' : '✓'} ${label.padEnd(14)} 画布 ${m.width}x${m.height}  内容 x[${minX.toFixed(0)},${maxX.toFixed(0)}] y[${minY.toFixed(0)},${maxY.toFixed(0)}]  ${wires} 线  ${mark}`)
  if (wires === 0) bad += 1
  if (out.length) {
    bad += 1
    const kinds = {}
    out.forEach(p => { const k = p.what.split(' ')[0]; kinds[k] = (kinds[k] || 0) + 1 })
    console.log('   越界的:', JSON.stringify(kinds), ' 最远:',
      JSON.stringify(out.reduce((a, b) => (Math.abs(b.x) + Math.abs(b.y) > Math.abs(a.x) + Math.abs(a.y) ? b : a))))
  }
}
console.log(bad === 0 ? '\n每一根线都在可滚动范围内' : `\n${bad}/${CASES.length} 个用例有东西落在画布外——挪不到、看不见`)

process.exitCode = bad === 0 ? 0 : 1
