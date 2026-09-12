// Golden test: the drawing must not change when the code moves.
//
// `client.golden.js` is a bundle that was looked at and accepted. This runs it
// and the current build side by side in the same stubbed browser, asks each for
// a drawing of the same synthetic repository, and compares the two field by
// field.
//
// It exists because moving code between files is exactly the change that looks
// safe and is not: three values inside layout() were REBOUND rather than
// mutated, and the rebinding stopped crossing a phase boundary the moment the
// phases became separate functions. Every one of those was caught here.
//
// It does not cover React rendering — a crash in a component is invisible to
// it. Two such crashes were caught only in a real browser, so a passing run
// here is a licence to open the page, not a substitute for it:
//
//   node lens/scripts/build.js && node lens/tests/layout-golden.js
//   node lens/tests/extent.js
//   lens/scripts/install.sh          # then look at the page
//
// Update the golden ONLY when the drawing is meant to change:
//
//   cp lens/lib/client.js lens/tests/client.golden.js
//
// and say in the commit what changed and why. It was last updated when the
// canvas started being sized from what was drawn rather than from where the
// nodes ended up — before that, wires bent out to negative coordinates and no
// amount of panning could reach them.
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

function load(file) {
  const env = stubEnv()
  vm.runInContext(fs.readFileSync(file, 'utf8'), env.ctx, { filename: file })
  return {
    surface: env.require_('dsh-cdd-lens'),
    layout: env.require_('dsh-cdd-lens/layout/layout').layout,
    shared: env.require_('dsh-cdd-lens/state/store').shared,
    emptyGraph: env.require_('dsh-cdd-lens/graph/model').emptyGraph,
    addNode: env.require_('dsh-cdd-lens/graph/model').addNode,
    addEdge: env.require_('dsh-cdd-lens/graph/model').addEdge,
  }
}

const oldSide = load('tests/client.golden.js')
const newSide = load('lib/client.js')
const surface = newSide.surface
console.log('plugin surface :', JSON.stringify({ name: surface.name, inject: surface.inject, apply: typeof surface.apply }))

// One synthetic repository: three files, a class with members, a call chain,
// a dataflow edge, and one island that nothing connects to.
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
    side.addNode(g, { id, symbol, file, kind, members, start: i * 10 + 1, end: i * 10 + 9 })
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
  Object.keys(g.nodes).forEach(id => { Object.assign(g.nodes[id], { session: true, down: true, up: true }) })
  g.nodes['c/util.js::orphan'].session = false
  const trace = {}
  anchors.forEach(([id], i) => { trace[id] = { lastTurn: 4, firstTurn: 1, kind: i % 3 === 0 ? 'edit' : 'read', remembered: i !== 6 } })
  Object.assign(side.shared, { trace: trace, turn: 4 })
  Object.assign(side.shared, seed)
  return g
}

const CASES = [
  ['默认', {}, undefined, 900],
  ['选中一个节点', { selected: 'a/main.js::wire' }, undefined, 900],
  ['窄画布', {}, undefined, 420],
  ['打开 dataflow', {}, { call: true, dataflow: true, inherit: true, impact: true, dispatch: true }, 1200],
  ['线路镜头', { edgeFocus: { from: 'a/main.js::boot', to: 'a/main.js::wire', type: 'call' } }, undefined, 900],
  ['无起点', { noRoot: true }, undefined, 900],
  ['人工坐标', { nodePositions: { 'b/panel.js::render': { x: 640, y: 300 } } }, undefined, 900],
]

let failed = 0
for (const [label, seed, filter, avail] of CASES) {
  const base = { selected: null, edgeFocus: null, nodePositions: {}, pins: {}, turn: 4 }
  const ga = build(oldSide, Object.assign({}, base, seed))
  const gb = build(newSide, Object.assign({}, base, seed))
  let ra, rb
  try { ra = oldSide.layout(ga, filter, avail) } catch (e) { ra = { threw: String(e) } }
  try { rb = newSide.layout(gb, filter, avail) } catch (e) { rb = { threw: String(e) } }
  const sa = JSON.stringify(ra), sb = JSON.stringify(rb)
  const same = sa === sb
  if (!same) failed += 1
  const shape = ra.nodes
    ? `${ra.nodes.length} 节点 / ${ra.wires.length} 线 / ${ra.files.length} 文件盒 / ${ra.arrows.length} 箭头`
    : ra.threw
  console.log(`${same ? '一致  ' : '不一致'}  ${label.padEnd(14)} ${shape}`)
  if (!same) {
    for (const k of ['nodes', 'wires', 'labels', 'junctions', 'arrows', 'files', 'width', 'height']) {
      if (JSON.stringify(ra[k]) !== JSON.stringify(rb[k])) console.log('        差异字段:', k)
    }
  }
}
console.log(failed === 0 ? '\n全部一致' : `\n${failed} 个用例不一致`)
process.exit(failed === 0 ? 0 : 1)
