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
  if (seed.tiered) {
    var seats = {
      'a/main.js::main': [0, 0],
      'a/main.js::boot': [1, 0], 'b/panel.js::Panel': [1, 0],
      'a/main.js::wire': [2, 0], 'b/panel.js::render': [2, 0],
      'b/panel.js::mount': [3, 0], 'c/util.js::clamp': [3, 0],
      'c/util.js::orphan': [0, 1],
    }
    Object.keys(seats).forEach(id => {
      g.nodes[id].layer = seats[id][0]
      g.nodes[id].tree = seats[id][1]
    })
  }
  const trace = {}
  anchors.forEach(([id], i) => { trace[id] = { lastTurn: 4, firstTurn: 1, kind: i % 3 === 0 ? 'edit' : 'read', remembered: i !== 6 } })
  Object.assign(side.shared, { trace: trace, turn: 4 })
  Object.assign(side.shared, seed)
  return g
}

// 三条硬规矩，来自实际使用：节点不许跑远、节点不许互相遮挡、线不许穿过节点。
function rects(m) { return m.nodes.map(n => ({ id: n.id, x: n.x, y: n.y, w: n.w, h: n.h })) }
function overlap(a, b) {
  var ix = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)
  var iy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y)
  return ix > 1 && iy > 1 ? Math.round(ix * iy) : 0
}
const {segments:segs,hits:segHitsRect}=require('./svg-geometry.cjs')

// What fetch.js actually does with islands: every one of them is seated in a
// single trailing tree at layer 0. A pile of them is the shape that pushed the
// rest of the drawing away, so it belongs in the fixture.
function withIslands(side, g, count) {
  var trees = Object.keys(g.nodes).map(function (id) { return g.nodes[id].tree })
    .filter(function (t) { return typeof t === 'number' })
  var last = trees.length === 0 ? 0 : Math.max.apply(Math, trees)
  for (var i = 0; i < count; i += 1) {
    var id = 'z/lone' + i + '.js::lone' + i
    side.addNode(g, { id: id, symbol: 'lone' + i, file: 'z/lone' + i + '.js', kind: 'function', members: 0, start: 1, end: 9 })
    Object.assign(g.nodes[id], { session: true, down: true, up: true, layer: 0, tree: last + 1 })
  }
  return g
}

// Trees of wildly different size, which is what a real chain looks like: one
// deep spine, a few short branches, and a pile of unconnected anchors.
function withTrees(side, g, shapes) {
  var used = Object.keys(g.nodes).map(function (id) { return g.nodes[id].tree })
    .filter(function (t) { return typeof t === 'number' })
  var next = used.length === 0 ? 1 : Math.max.apply(Math, used) + 1
  shapes.forEach(function (layers, t) {
    var tree = next + t
    var prev = null
    layers.forEach(function (count, layer) {
      for (var i = 0; i < count; i += 1) {
        var id = 't' + tree + '/l' + layer + '_' + i + '.js::fn' + i
        side.addNode(g, { id: id, symbol: 'fn' + layer + '_' + i, file: 't' + tree + '/l' + layer + '_' + i + '.js',
          kind: 'function', members: 0, start: 1, end: 9 })
        Object.assign(g.nodes[id], { session: true, down: true, up: true, layer: layer, tree: tree })
        if (prev !== null && i === 0) { side.addEdge(g, prev, id, ['call']); g.edges[g.edges.length - 1].always = true }
      }
      prev = 't' + tree + '/l' + layer + '_0.js::fn0'
    })
  })
  return g
}

// The board skin derives one box per file from the bounding box of that file's
// anchors. Two files whose anchors end up interleaved therefore produce two
// boxes on top of each other, and an anchor inside the overlap belongs to
// neither as far as the eye can tell.
function withFiles(side, g, files, perFile) {
  for (var f = 0; f < files; f += 1) {
    for (var i = 0; i < perFile; i += 1) {
      var id = 'm/mod' + f + '.js::fn' + i
      side.addNode(g, { id: id, symbol: 'fn' + f + '_' + i, file: 'm/mod' + f + '.js',
        kind: 'function', members: 0, start: i * 10 + 1, end: i * 10 + 9 })
      Object.assign(g.nodes[id], { session: true, down: true, up: true })
      // Reachable from the root, or layoutScope drops it and the case tests
      // nothing while still reporting a pass.
      var parent = i > 0 ? 'm/mod' + f + '.js::fn' + (i - 1) : g.rootId
      side.addEdge(g, parent, id, ['call'])
      g.edges[g.edges.length - 1].always = true
    }
  }
  return g
}

const CASES = [
  ['分层 · 900',   { tiered: true }, undefined, 900],
  ['分层 · 窄 420', { tiered: true }, undefined, 420],
  ['分层 · 全关系', { tiered: true, wireMode:'all' }, { call:1, dataflow:1, inherit:1, impact:1, dispatch:1 }, 900],
  ['文件盒 · 900',  {}, undefined, 900],
  ['文件盒 · 全关系',{wireMode:'all'}, { call:1, dataflow:1, inherit:1, impact:1, dispatch:1 }, 900],
  ['分层 · 20 个孤岛', { tiered: true, islands: 20 }, undefined, 900],
  ['分层 · 60 个孤岛', { tiered: true, islands: 60 }, undefined, 1400],
  ['分层 · 手工坐标',  { tiered: true, nodePositions: { 'b/panel.js::render': { x: 300, y: 120 }, 'c/util.js::clamp': { x: 320, y: 140 } } }, undefined, 900],
  ['分层 · 大小悬殊的树', { tiered: true, trees: [[1,1,1,1,1,1,1,1], [3], [1,2], [6,6], [1]] }, undefined, 1200],
  ['分层 · 树 + 孤岛',   { tiered: true, trees: [[1,1,1,1,1,1], [4], [1,1]], islands: 25 }, undefined, 1200],
  // A coordinate the user dragged is kept across relayouts. When the layout
  // itself changes shape, that saved point can be nowhere near anything.
  ['分层 · 旧坐标遗留',  { tiered: true, trees: [[1,1,1,1]],
    nodePositions: { 'c/util.js::clamp': { x: 2600, y: 1800 } } }, undefined, 1200],
  ['PCB · 12 个文件',  { skin: 'pcb', files: [12, 3] }, undefined, 1200],
  ['PCB · 窄屏多文件',  { skin: 'pcb', files: [16, 3] }, undefined, 520],
  // Two files' anchors dragged into each other: the boxes derived from them
  // must still not be laid on top of one another.
  // Hand-dragged: boxes may overlap here, so only the other four rules apply.
  ['PCB · 文件被拖散(允许叠)', { skin: 'pcb', files: [4, 3],
    nodePositions: { 'm/mod0.js::fn2': { x: 640, y: 300 }, 'm/mod1.js::fn0': { x: 660, y: 320 } } }, undefined, 1200],
  // 流向皮肤：列号来自 node.layer（/chain 下发的最长路径层），层间走廊留给走线；
  // 跨层边沿走廊逐层下楼梯、穿过中间列的节点间隙，逆向边镜像走左侧。没有层级
  // 数据的图进尾随列，不放弃整个布局。
  ['流向 · 900',   { skin: 'flow', tiered: true }, undefined, 900],
  ['流向 · 窄 420', { skin: 'flow', tiered: true }, undefined, 420],
  ['流向 · 全关系', { skin: 'flow', tiered: true, wireMode:'all' }, { call:1, dataflow:1, inherit:1, impact:1, dispatch:1 }, 900],
  ['流向 · 无层级数据', { skin: 'flow' }, undefined, 900],
  ['流向 · 大小悬殊的树', { skin: 'flow', trees: [[1,1,1,1,1,1,1,1], [3], [1,2], [6,6], [1]] }, undefined, 1200],
  ['流向 · 树 + 孤岛',   { skin: 'flow', trees: [[1,1,1,1,1,1], [4], [1,1]], islands: 25 }, undefined, 1200],
  ['流向 · 手工坐标',  { skin: 'flow', tiered: true,
    nodePositions: { 'b/panel.js::render': { x: 300, y: 120 }, 'c/util.js::clamp': { x: 320, y: 140 } } }, undefined, 900],
  // 收拢是覆盖层：焦点不动，上下游贴到两侧，松开后各皮肤布局原样回来。
  ['收拢 · 流向',   { skin: 'flow', tiered: true, gather: { focus: 'a/main.js::wire' } }, undefined, 900],
  ['收拢 · 分层',   { tiered: true, gather: { focus: 'a/main.js::wire' } }, undefined, 900],
  ['收拢 · 文件盒', { skin: 'pcb', gather: { focus: 'a/main.js::wire' } }, undefined, 900],
]

let bad = 0
for (const [label, seed, filter, avail] of CASES) {
  const base = { selected: null, edgeFocus: null, nodePositions: {}, pins: {}, turn: 4, gather: null, wireMode: 'trunk' }
  side.shared.skin = seed.skin || 'auto'
  let g = build(side, Object.assign({}, base, seed))
  if (seed.files) g = withFiles(side, g, seed.files[0], seed.files[1])
  if (seed.trees) g = withTrees(side, g, seed.trees)
  if (seed.islands) g = withIslands(side, g, seed.islands)
  const m = side.layout(g, filter, avail)
  const rs = rects(m)

  // 1. 跑远：沿一个轴排好序，相邻两个之间空出一大片，后面的就是被甩出去了。
  //    看重心距离量不到这种——一堆节点连成两团时重心正好落在中间的空处。
  const medW = rs.map(r => r.w).sort((a, b) => a - b)[Math.floor(rs.length / 2)] || 180
  const medH = rs.map(r => r.h).sort((a, b) => a - b)[Math.floor(rs.length / 2)] || 60
  const gapsOn = (get, limit) => {
    const sorted = rs.slice().sort((a, b) => get(a) - get(b))
    const out = []
    for (let i = 1; i < sorted.length; i += 1) {
      const gap = get(sorted[i]) - get(sorted[i - 1])
      if (gap > limit) out.push(sorted[i].id + ' 前面空了 ' + Math.round(gap) + 'px')
    }
    return out
  }
  const far = gapsOn(r => r.x + r.w / 2, medW * 3).concat(gapsOn(r => r.y + r.h / 2, medH * 6))
    .map(t => ({ id: t }))

  // 2. 遮挡
  const hits = []
  for (let i = 0; i < rs.length; i += 1) for (let j = i + 1; j < rs.length; j += 1) {
    const a = overlap(rs[i], rs[j]); if (a > 0) hits.push(rs[i].id + ' × ' + rs[j].id + ' = ' + a + 'px²')
  }

  // Anything the user dragged is exempt from the spacing rules below: boxes and
  // badges on top of each other are the honest drawing of where they put them.
  const handPlaced = Object.keys(seed.nodePositions || {}).length > 0

  // 3. 角标打架：一个「出」占右侧 29px 净空，对面的「入」也要 29px。两个横向
  //    相邻、纵向有重叠的节点之间不够 58px，两个角标就会叠在一起，把它们中间
  //    那根线整个盖住——看着就是一堆没有连线的卡片。
  const PORT_CLEAR = 29
  const cramped = []
  for (let i = 0; i < rs.length; i += 1) for (let j = 0; j < rs.length; j += 1) {
    if (i === j) continue
    const a = rs[i], b = rs[j]
    if (b.x < a.x + a.w) continue
    if (Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) <= 1) continue
    const gap = b.x - (a.x + a.w)
    if (gap < PORT_CLEAR * 2 && !handPlaced) {
      cramped.push(a.id + ' → ' + b.id + ' 只有 ' + Math.round(gap) + 'px')
    }
  }

  // 4. 文件盒重叠：盒子是「这些 anchor 同属一个文件」的唯一视觉说明，两个盒子
  //    压在一起，里面的 anchor 就不知道算谁的了。
  const fbs = (m.files || []).map(f => ({ id: f.file, x: f.x, y: f.y, w: f.w, h: f.h }))
  const boxHits = []
  {
    for (let i = 0; i < fbs.length; i += 1) for (let j = i + 1; j < fbs.length; j += 1) {
      const area = overlap(fbs[i], fbs[j])
      if (area > 0) boxHits.push(fbs[i].id + ' × ' + fbs[j].id + ' = ' + area + 'px²')
    }
  }

  // 5. 线穿节点（端点所属的两个节点不算）
  let through = 0, sample = null
  ;(m.wires || []).forEach(w => {
    segs(w.d).forEach(([p, q]) => {
      rs.forEach(r => {
                if (segHitsRect(p, q, r)) { through += 1; if (sample === null) sample = w.id + ' 穿过 ' + r.id }
      })
    })
  })

  // 6. 单排对齐：一个框里的 anchor 必须左边对齐、宽度一致，才是一竖列。逐个
  //    按自己的文字定宽会排出七个不同的右沿，跟在右沿后面的「出」角标就连成
  //    一条锯齿线，而不是一竖列。
  // 手动放的节点不算：用户把一个 anchor 拖出这一列，本来就是要它不在列里。
  // 「拖动不能破坏这两条规矩」曾经成立，代价是拖动根本不生效——每个皮肤的
  // 每个节点都带 boxKey，于是整张图挪不动。自动排的成员仍然必须成一列。
  const ragged = []
  {
    const byBox = {}
    m.nodes.forEach(n => {
      if (n.boxKey === undefined || n.manual === true || n.pinned === true) return
      ;(byBox[n.boxKey] = byBox[n.boxKey] || []).push(n)
    })
    Object.keys(byBox).forEach(k => {
      const xs = new Set(byBox[k].map(n => Math.round(n.x)))
      const ws = new Set(byBox[k].map(n => Math.round(n.w)))
      if (xs.size > 1) ragged.push(k + ' 左沿不齐 ' + [...xs].join('/'))
      if (ws.size > 1) ragged.push(k + ' 宽度不一 ' + [...ws].join('/'))
    })
    // 列对齐：同一列的框 x 必须相同，列与列之间不许有交叠。
    const cols = {}
    fbs.forEach(f => { const k = Math.round(f.x); (cols[k] = cols[k] || []).push(f) })
    const lefts = Object.keys(cols).map(Number).sort((a, b) => a - b)
    const widestBox = Math.max.apply(null, fbs.map(f => f.w))
    lefts.slice(1).forEach((x, i) => {
      const prevRight = Math.max.apply(null, cols[lefts[i]].map(f => f.x + f.w))
      if (x < prevRight) ragged.push('列相交 ' + Math.round(prevRight) + ' > ' + x)
      // Spreading the columns across the canvas left two boxes at opposite
      // edges with a screen of nothing between them. A gutter wider than a box
      // is not spacing, it is distance.
      if (x - prevRight > widestBox) {
        ragged.push('列距过远 ' + Math.round(x - prevRight) + ' > 框宽 ' + Math.round(widestBox))
      }
    })
  }

  // A case that quietly drew nothing must not report a pass.
  // placement.js only boxes a file with three or more anchors present —
  // otherwise the drawing becomes a wall of almost-empty frames.
  const wantBoxes = seed.files && seed.files[1] >= 3 ? seed.files[0] : 0
  const missing = wantBoxes > 0 && fbs.length < wantBoxes
  const ok = far.length === 0 && hits.length === 0 && through === 0 && cramped.length === 0
    && boxHits.length === 0 && !missing && ragged.length === 0
  if (!ok) bad += 1
  console.log((ok ? '✓ ' : '✗ ') + label.padEnd(14)
    + ' 跑远 ' + far.length + ' · 遮挡 ' + hits.length + ' · 角标打架 ' + cramped.length
    + ' · 线穿节点 ' + through + ' · 文件盒重叠 ' + boxHits.length
    + (wantBoxes ? ' · 盒子 ' + fbs.length + '/' + wantBoxes : ''))
  if (ragged.length) console.log('    不齐: ' + ragged.slice(0, 3).join(' | '))
  if (boxHits.length) console.log('    文件盒重叠: ' + boxHits.slice(0, 3).join(' | '))
  if (cramped.length) console.log('    角标打架: ' + cramped.slice(0, 3).join(' | '))
  if (far.length) console.log('    跑远: ' + far.slice(0, 4).map(r => r.id).join(' | '))
  if (hits.length) console.log('    遮挡: ' + hits.slice(0, 3).join(' | '))
  if (sample) console.log('    例: ' + sample)
}
// Layout reruns on zoom, on selection, and on a width poll every 400ms, so its
// cost is felt continuously rather than once. Two passes were quadratic — every
// wire segment against every box, every horizontal run against every vertical —
// and a thousand anchors took a second each time, which is what freezing is.
;(function costOfSize() {
  const build1000 = () => {
    const g = side.emptyGraph()
    let prev = null
    for (let f = 0; f < 100; f += 1) {
      for (let i = 0; i < 10; i += 1) {
        const id = 'perf/mod' + f + '.js::fn' + i
        side.addNode(g, { id, symbol: 'fn' + f + '_' + i, file: 'perf/mod' + f + '.js',
          kind: 'function', members: 0, start: i * 10 + 1, end: i * 10 + 9 })
        Object.assign(g.nodes[id], { session: true, down: true, up: true, layer: i, tree: f })
        if (g.rootId === null) g.rootId = id
        if (prev !== null) { side.addEdge(g, prev, id, ['call']); g.edges[g.edges.length - 1].always = true }
        prev = id
      }
    }
    Object.assign(side.shared, { trace: {}, turn: 4, selected: null, edgeFocus: null, nodePositions: {}, pins: {} })
    return g
  }
  const BUDGET = 400
  const worst = []
  ;['pcb', 'tiers'].forEach(skin => {
    side.shared.skin = skin
    const g = build1000()
    const t0 = Date.now()
    side.layout(g, undefined, 1400)
    worst.push([skin, Date.now() - t0])
  })
  side.shared.skin = 'auto'
  const over = worst.filter(([, ms]) => ms > BUDGET)
  console.log((over.length ? '✗ ' : '✓ ') + '1000 节点耗时'.padEnd(11)
    + worst.map(([k, ms]) => k + ' ' + ms + 'ms').join(' · ') + '   预算 ' + BUDGET + 'ms')
  if (over.length) bad += 1
})()

// The skin has to actually change the drawing. A control that reads as chosen
// while nothing moves is worse than no control.
;(function skinSwitches() {
  const base = { selected: null, edgeFocus: null, nodePositions: {}, pins: {}, turn: 4, gather: null, wireMode: 'trunk' }
  const shot = want => {
    side.shared.skin = want
    const g = build(side, Object.assign({}, base, { tiered: true }))
    const m = side.layout(g, undefined, 900)
    return { files: (m.files || []).length, wires: (m.wires || []).length,
      labels: (m.files || []).map(f => String(f.file)) }
  }
  const tiers = shot('tiers')
  const pcb = shot('pcb')
  const flow = shot('flow')
  side.shared.skin = 'auto'
  // Both draw the same grid now; what differs is what a box holds. A layer box
  // is titled by its tree and layer, a file box by its path. Flow names its
  // frames after the layer column they wrap.
  const byLayer = tiers.labels.every(t => /^T\d+ · L\d+ · \d+$/.test(t))
  const byFile = pcb.labels.every(t => t.indexOf('/') >= 0)
  const byFlow = flow.labels.every(t => /^L\d+ · \d+$/.test(t))
  const ok = tiers.files > 0 && pcb.files > 0 && flow.files > 0 && byLayer && byFile && byFlow
    && tiers.wires > 0 && pcb.wires > 0 && flow.wires > 0
  console.log((ok ? '✓ ' : '✗ ') + '皮肤切换'.padEnd(12)
    + ' 分层[盒 ' + tiers.files + ' 按层 ' + (byLayer ? '✓' : '✗') + ' · 线 ' + tiers.wires + ']'
    + '  PCB[盒 ' + pcb.files + ' 按文件 ' + (byFile ? '✓' : '✗') + ' · 线 ' + pcb.wires + ']'
    + '  流向[盒 ' + flow.files + ' 按方向列 ' + (byFlow ? '✓' : '✗') + ' · 线 ' + flow.wires + ']')
  if (!ok) bad += 1
})()

// 收拢：选中即把上下游拉到身边；取消后原样恢复。恢复不靠存坐标——覆盖层每次
// 布局重算，撤销它就是再跑一次没有它的布局，所以中途拖动/展开都不会留下鬼影。
;(function gatherFocus() {
  const base = { selected: null, edgeFocus: null, nodePositions: {}, pins: {}, turn: 4, tiered: true, gather: null }
  const at = (m, id) => m.nodes.filter(n => n.id === id)[0]
  side.shared.skin = 'flow'
  side.shared.wireMode = 'all'
  const before = side.layout(build(side, Object.assign({}, base)), undefined, 900)
  // 焦点 clamp：上游 render（贴邻 L2）和 boot（L1，隔一层）——boot 的收拢是真
  // 位移，贴左列、归新层、边走短路径才有得可断。gather 在 build 之后设置：
  // build 会把 seed 里的 gather:null 写回 shared。
  const gd = build(side, Object.assign({}, base))
  side.shared.gather = { focus: 'c/util.js::clamp' }
  const during = side.layout(gd, undefined, 900)
  side.shared.gather = null
  const after = side.layout(build(side, Object.assign({}, base)), undefined, 900)
  side.shared.wireMode = undefined

  const f = at(during, 'c/util.js::clamp')
  const fBefore = at(before, 'c/util.js::clamp')
  const boot = at(during, 'a/main.js::boot')      // clamp 的 dataflow 上游，原本隔一层
  const render = at(during, 'b/panel.js::render') // clamp 的 call 上游，本就贴邻
  const wire = at(during, 'a/main.js::wire')      // 与 clamp 无直接边
  const GAP = 96  // LAYER_GAP_X = PORT_CLEAR*2 + 38
  const wBoot = during.wires.filter(w => w.from === 'a/main.js::boot' && w.to === 'c/util.js::clamp')[0]
  // 只数 M/L 的坐标对，跳过 hop 弧的参数
  const spanOf = d => {
    const pts = []
    const re = /[ML](-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/g
    let mm
    while ((mm = re.exec(d)) !== null) pts.push([+mm[1], +mm[2]])
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1])
    return { x: Math.max.apply(null, xs) - Math.min.apply(null, xs),
      y: Math.max.apply(null, ys) - Math.min.apply(null, ys) }
  }
  const span = wBoot ? spanOf(wBoot.d) : { x: 9999, y: 9999 }
  const checks = [
    ['焦点不动', Math.abs(f.x - fBefore.x) < 1 && Math.abs(f.y - fBefore.y) < 1],
    ['隔层上游贴到左列', Math.abs(boot.x + boot.w - (f.x - GAP)) < 2],
    ['贴邻上游贴到左列', Math.abs(render.x + render.w - (f.x - GAP)) < 2],
    ['收拢节点按新位置归层', boot.flowLayer === f.flowLayer - 1 && render.flowLayer === f.flowLayer - 1],
    ['收拢后的边走短路径', span.x < 500 && span.y < 400],
    ['无关节点不动', Math.abs(wire.x - at(before, 'a/main.js::wire').x) < 1
      && Math.abs(wire.y - at(before, 'a/main.js::wire').y) < 1],
    ['松开后恢复', JSON.stringify(after.nodes.map(n => [n.id, n.x, n.y]))
      === JSON.stringify(before.nodes.map(n => [n.id, n.x, n.y]))],
  ]
  // Bug 1 回归：收拢中拖动的节点脱离收拢列，停在用户放下的位置，不被拉回。
  const gf = build(side, Object.assign({}, base,
    { nodePositions: { 'a/main.js::boot': { x: 500, y: 500 } } }))
  side.shared.gather = { focus: 'c/util.js::clamp', freed: { 'a/main.js::boot': true } }
  const freedM = side.layout(gf, undefined, 900)
  side.shared.gather = null
  const bootF = at(freedM, 'a/main.js::boot')
  const fF = at(freedM, 'c/util.js::clamp')
  checks.push(['收拢中拖动不被拉回', Math.abs(bootF.x - 500) < 80
    && Math.abs(bootF.x + bootF.w - (fF.x - GAP)) > 100])
  const failed = checks.filter(([, ok]) => !ok).map(([name]) => name)
  console.log((failed.length === 0 ? '✓ ' : '✗ ') + '收拢/放回'.padEnd(12)
    + (failed.length === 0 ? '焦点不动 · 上下游贴列 · 归层短路径 · 拖动自由 · 恢复一致' : '失败: ' + failed.join('、')))
  if (failed.length) bad += 1
})()

// Barycenter：列内顺序由布线参与决定。夹具是两列各三个节点、三条边全交错——
// 旧的 tree+符号序排出 3 个逆序对，扫描后应当归零；几何上的线交叉也要归零。
;(function barycenterSweep() {
  const base = { selected: null, edgeFocus: null, nodePositions: {}, pins: {}, turn: 4, tiered: true, gather: null }
  side.shared.skin = 'flow'
  side.shared.wireMode = 'all'
  const g = build(side, Object.assign({}, base))
  const pairs = [['u1', 'v3'], ['u2', 'v2'], ['u3', 'v1']]
  ;['u1', 'u2', 'u3'].forEach((s, i) => {
    const id = 'x/cross.js::' + s
    side.addNode(g, { id, symbol: s, file: 'x/cross.js', kind: 'function', members: 0, start: 1, end: 9 })
    // 不在主链上：pin 住才在 visible 里有根，否则整列被 scope 丢掉，用例空转。
    Object.assign(g.nodes[id], { session: true, down: true, up: true, pinned: true, layer: 4, tree: 9 })
  })
  ;['v1', 'v2', 'v3'].forEach((s, i) => {
    const id = 'x/cross.js::' + s
    side.addNode(g, { id, symbol: s, file: 'x/cross.js', kind: 'function', members: 0, start: 1, end: 9 })
    Object.assign(g.nodes[id], { session: true, down: true, up: true, pinned: true, layer: 5, tree: 9 })
  })
  pairs.forEach(([u, v]) => {
    side.addEdge(g, 'x/cross.js::' + u, 'x/cross.js::' + v, ['call'])
    g.edges[g.edges.length - 1].always = true
  })
  const m = side.layout(g, undefined, 1400)
  side.shared.skin = 'auto'
  side.shared.wireMode = undefined

  const at = id => m.nodes.filter(n => n.id === id)[0]
  const yOrder = ids => ids.slice().sort((a, b) => at(a).y - at(b).y)
  const inversions = (leftIds, rightIds, edges) => {
    const li = {}, ri = {}
    leftIds.forEach((id, i) => { li[id] = i })
    rightIds.forEach((id, i) => { ri[id] = i })
    let n = 0
    for (let i = 0; i < edges.length; i += 1) for (let j = i + 1; j < edges.length; j += 1) {
      const a = [li[edges[i][0]], ri[edges[i][1]]]
      const b = [li[edges[j][0]], ri[edges[j][1]]]
      if ((a[0] - b[0]) * (a[1] - b[1]) < 0) n += 1
    }
    return n
  }
  const U = ['x/cross.js::u1', 'x/cross.js::u2', 'x/cross.js::u3']
  const V = ['x/cross.js::v1', 'x/cross.js::v2', 'x/cross.js::v3']
  const E = pairs.map(([u, v]) => ['x/cross.js::' + u, 'x/cross.js::' + v])
  // 重排前 = 旧规则（tree 再符号）给出的顺序：u1,u2,u3 对 v1,v2,v3。
  const beforeN = inversions(U, V, E)
  const afterN = inversions(yOrder(U), yOrder(V), E)

  // 几何交叉：三根线两两做线段相交测试（hop 弧的参数先剥掉）。
  const ptsOf = d => {
    const pts = []
    const re = /[ML](-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/g
    let mm
    while ((mm = re.exec(d)) !== null) pts.push([+mm[1], +mm[2]])
    return pts
  }
  const cross = (p1, p2, p3, p4) => {
    const d = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    const d1 = d(p3, p4, p1), d2 = d(p3, p4, p2), d3 = d(p1, p2, p3), d4 = d(p1, p2, p4)
    return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))
  }
  const fan = m.wires.filter(w => w.from.indexOf('x/cross.js::') === 0)
  let geo = 0
  fan.forEach((a, i) => fan.slice(i + 1).forEach(b => {
    const pa = ptsOf(a.d), pb = ptsOf(b.d)
    for (let s = 1; s < pa.length; s += 1) for (let t = 1; t < pb.length; t += 1) {
      if (cross(pa[s - 1], pa[s], pb[t - 1], pb[t])) geo += 1
    }
  }))
  const ok = beforeN === 3 && afterN < beforeN && afterN === 0 && geo === 0
  console.log((ok ? '✓ ' : '✗ ') + '重心重排'.padEnd(12)
    + ' 交叉: 符号序 ' + beforeN + ' → 重排后 ' + afterN + ' · 线交叉 ' + geo)
  if (!ok) bad += 1
})()

// focus 建图（搜索/目录入口）过去从不开口要 /chain，图全部无层，flow 只能堆
// 进尾列。这里用桩 fetch 模拟 /neighbors 与 /chain，验证 focus 之后节点带层、
// flow 皮肤没有「未入链」列。这个用例是异步的，所以总结等它。
;(function focusSeatsLayers() {
  const finish = () => {
    process.exitCode = bad === 0 ? 0 : 1
    console.log(bad === 0 ? '\n三条都过' : '\n' + bad + '/' + CASES.length + ' 个用例违规')
  }
  let chainCalls = 0
  B.ctx.fetch = url => {
    const u = String(url)
    if (u.indexOf('/chain') >= 0) {
      chainCalls += 1
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        seeds: 1, hops: 1,
        trees: [{ size: 2, seeds: 1, layers: [['a/m.js::f'], ['a/m.js::g']],
          nodes: [{ id: 'a/m.js::f', layer: 0, seed: true }, { id: 'a/m.js::g', layer: 1, seed: false }],
          edges: [{ from: 'a/m.js::f', to: 'a/m.js::g', types: ['call'] }] }],
        islands: [],
      }) })
    }
    if (u.indexOf('/neighbors') >= 0) {
      const peers = u.indexOf('dir=up') >= 0 ? [] : [
        { id: 'a/m.js::g', symbol: 'g', file: 'a/m.js', kind: 'function', members: 0, start: 11, end: 19, types: ['call'] },
      ]
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ peers: peers }) })
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
  }
  const engine = B.require_('dsh-cdd-lens/engine/engine').makeEngine({ get: () => undefined })
  Object.assign(side.shared, { trace: {}, turn: 4, selected: null, edgeFocus: null,
    nodePositions: {}, pins: {}, gather: null, skin: 'auto' })
  engine.focus({ id: 'a/m.js::f', symbol: 'f', file: 'a/m.js', kind: 'function', members: 0, start: 1, end: 9 })
    .then(() => {
      const g = side.shared.graph
      const seated = g.nodes['a/m.js::f'].layer === 0 && g.nodes['a/m.js::g'].layer === 1
        && typeof g.nodes['a/m.js::f'].tree === 'number'
      side.shared.skin = 'flow'
      const m = side.layout(g, undefined, 900)
      side.shared.skin = 'auto'
      const rest = (m.files || []).filter(fb => String(fb.file).indexOf('未入链') === 0)
      const ok = chainCalls === 1 && seated && rest.length === 0 && m.nodes.length === 2
      console.log((ok ? '✓ ' : '✗ ') + 'focus 盖层'.padEnd(12)
        + ' chain 调用 ' + chainCalls + ' · 带层 ' + (seated ? '✓' : '✗')
        + ' · 尾列 ' + rest.length + ' · 节点 ' + m.nodes.length + '/2')
      if (!ok) bad += 1
      finish()
    })
    .catch(error => {
      console.log('✗ focus 盖层    抛错: ' + String(error && error.message || error))
      bad += 1
      finish()
    })
})()
