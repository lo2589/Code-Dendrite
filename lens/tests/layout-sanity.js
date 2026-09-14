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


const B = stubEnv(); B.ctx.window.location.search = '?cddl-debug=1'; vm.runInContext(fs.readFileSync('lib/client.js', 'utf8'), B.ctx, { filename: 'built.js' })
const side = {
  layout: B.require_('dsh-cdd-lens/layout/layout').layout,
  shared: B.require_('dsh-cdd-lens/state/store').shared,
  emptyGraph: B.require_('dsh-cdd-lens/graph/model').emptyGraph,
  addNode: B.require_('dsh-cdd-lens/graph/model').addNode,
  addEdge: B.require_('dsh-cdd-lens/graph/model').addEdge,
  uiOf: B.require_('dsh-cdd-lens/graph/model').uiOf,
  placeOf: B.require_('dsh-cdd-lens/graph/model').placeOf,
  setPlace: B.require_('dsh-cdd-lens/graph/model').setPlace,
  require_: B.require_,
}
// 交互状态进 graph.ui，坐标进 graph.layout —— 都不写回 anchor 记录。
function mark(side, g, id, patch) {
  var ui = side.require_('dsh-cdd-lens/graph/model').uiOf(g, id)
  Object.assign(ui, patch)
}
side.setUI = mark
function seat(side, g, id, patch) {
  side.setPlace(g, id, Object.assign(side.placeOf(g, id) || {}, patch))
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
  Object.keys(g.nodes).forEach(id => { mark(side, g, id, { session: true, down: true, up: true }) })
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
      seat(side, g, id, { layer: seats[id][0], tree: seats[id][1] })
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
function endpointLocks(m) {
  const byId = new Map(m.nodes.map(n => [n.id, n]))
  const loose = []
  ;(m.wires || []).forEach(w => {
    const from = byId.get(w.from)
    const to = byId.get(w.to)
    if (!from || !to) { loose.push(w.id + ' 缺节点'); return }
    if (!w.pts || w.pts[0] !== from.ports.out) loose.push(w.id + ' 起点没共享 from.out')
    if (!w.pts || w.pts[w.pts.length - 1] !== to.ports.in) loose.push(w.id + ' 终点没共享 to.in')
    if (!w.sourcePort || w.sourcePort.point !== from.ports.out) loose.push(w.id + ' sourcePort 没共享 from.out')
    if (!w.targetPort || w.targetPort.point !== to.ports.in) loose.push(w.id + ' targetPort 没共享 to.in')
  })
  return loose
}
const {segments:segs,hits:segHitsRect}=require('./svg-geometry.cjs')

// What fetch.js actually does with islands: every one of them is seated in a
// single trailing tree at layer 0. A pile of them is the shape that pushed the
// rest of the drawing away, so it belongs in the fixture.
function withIslands(side, g, count) {
  var trees = Object.keys(g.nodes).map(function (id) { return (side.placeOf(g, id) || {}).tree })
    .filter(function (t) { return typeof t === 'number' })
  var last = trees.length === 0 ? 0 : Math.max.apply(Math, trees)
  for (var i = 0; i < count; i += 1) {
    var id = 'z/lone' + i + '.js::lone' + i
    side.addNode(g, { id: id, symbol: 'lone' + i, file: 'z/lone' + i + '.js', kind: 'function', members: 0, line_start: 1, line_end: 9 })
    mark(side, g, id, { session: true, down: true, up: true })
    seat(side, g, id, { layer: 0, tree: last + 1 })
  }
  return g
}

// Trees of wildly different size, which is what a real chain looks like: one
// deep spine, a few short branches, and a pile of unconnected anchors.
function withTrees(side, g, shapes) {
  var used = Object.keys(g.nodes).map(function (id) { return (side.placeOf(g, id) || {}).tree })
    .filter(function (t) { return typeof t === 'number' })
  var next = used.length === 0 ? 1 : Math.max.apply(Math, used) + 1
  shapes.forEach(function (layers, t) {
    var tree = next + t
    var prev = null
    layers.forEach(function (count, layer) {
      for (var i = 0; i < count; i += 1) {
        var id = 't' + tree + '/l' + layer + '_' + i + '.js::fn' + i
        side.addNode(g, { id: id, symbol: 'fn' + layer + '_' + i, file: 't' + tree + '/l' + layer + '_' + i + '.js',
          kind: 'function', members: 0, line_start: 1, line_end: 9 })
        mark(side, g, id, { session: true, down: true, up: true })
        seat(side, g, id, { layer: layer, tree: tree })
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
        kind: 'function', members: 0, line_start: i * 10 + 1, line_end: i * 10 + 9 })
      mark(side, g, id, { session: true, down: true, up: true })
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

  // Anything the user dragged is exempt from the spacing rules: boxes on top of
  // each other are the honest drawing of where they put them.
  const handPlaced = Object.keys(seed.nodePositions || {}).length > 0

  // 2. 遮挡
  const hits = []
  if (!handPlaced) {
    for (let i = 0; i < rs.length; i += 1) for (let j = i + 1; j < rs.length; j += 1) {
      const a = overlap(rs[i], rs[j]); if (a > 0) hits.push(rs[i].id + ' × ' + rs[j].id + ' = ' + a + 'px²')
    }
  }

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

  // 4. 文件盒已随皮肤一起退场：现在只有一种布局——按关系分层，层定 x、层内定 y。
  //    文件盒是「按文件分组」那套皮肤的东西，和分层是两套互斥的分组方式，
  //    两个都画只会互相打架。所以这里不再有盒子可重叠。
  const boxHits = []

  // 5. 线穿节点（端点所属的两个节点不算）
  // 收拢时上下游被拉到焦点两侧，线必须从焦点旁边过；那是覆盖层故意画成那样的。
  const gathered = side.shared.gather !== null && side.shared.gather !== undefined
  let through = 0, sample = null
  if (!handPlaced && !gathered) {
    ;(m.wires || []).forEach(w => {
      segs(w.d).forEach(([p, q]) => {
        rs.forEach(r => {
                  if (segHitsRect(p, q, r)) { through += 1; if (sample === null) sample = w.id + ' 穿过 ' + r.id }
        })
      })
    })
  }

  // 6. 单排对齐：同一层的节点必须左边对齐、宽度一致，才是一竖列。逐个按自己的
  //    文字定宽会排出七个不同的右沿，跟在右沿后面的「出」角标就连成锯齿线。
  //    手动拖过的节点不算——用户把它拖出这一列，本来就是要它不在列里。
  const ragged = []
  {
    const byLayer = {}
    m.nodes.forEach(n => {
      if (n.manual === true || n.pinned === true) return
      ;(byLayer[n.layer] = byLayer[n.layer] || []).push(n)
    })
    Object.keys(byLayer).forEach(k => {
      const xs = new Set(byLayer[k].map(n => Math.round(n.x)))
      const ws = new Set(byLayer[k].map(n => Math.round(n.w)))
      if (xs.size > 1) ragged.push('层 ' + k + ' 左沿不齐 ' + [...xs].join('/'))
      if (ws.size > 1) ragged.push('层 ' + k + ' 宽度不一 ' + [...ws].join('/'))
    })
  }
  const looseEndpoints = endpointLocks(m)

  // A case that quietly drew nothing must not report a pass.
  // placement.js only boxes a file with three or more anchors present —
  // otherwise the drawing becomes a wall of almost-empty frames.
  const ok = far.length === 0 && hits.length === 0 && through === 0 && cramped.length === 0
    && boxHits.length === 0 && ragged.length === 0 && looseEndpoints.length === 0
  if (!ok) bad += 1
  console.log((ok ? '✓ ' : '✗ ') + label.padEnd(14)
    + ' 跑远 ' + far.length + ' · 遮挡 ' + hits.length + ' · 角标打架 ' + cramped.length
    + ' · 线穿节点 ' + through + ' · 文件盒重叠 ' + boxHits.length
    + ' · 端点脱锁 ' + looseEndpoints.length
    + ' · 层 ' + (m.layers || 0) + ' · 交叉 ' + (m.crossings || 0))
  if (ragged.length) console.log('    不齐: ' + ragged.slice(0, 3).join(' | '))
  if (looseEndpoints.length) console.log('    端点脱锁: ' + looseEndpoints.slice(0, 3).join(' | '))
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
;(function onlyOneLayout() {
  // 皮肤已删。现在只有一种布局：按关系分层——层定 x、层内定 y。
  // 同一个图跑两次必须给出同样的层数、节点数和交叉数（确定性）。
  const base = { selected: null, edgeFocus: null, nodePositions: {}, pins: {}, turn: 4, gather: null, wireMode: 'trunk' }
  const shot = () => {
    const g = build(side, Object.assign({}, base, { tiered: true }))
    const m = side.layout(g, undefined, 900)
    return { nodes: m.nodes.length, layers: m.layers, crossings: m.crossings, wires: (m.wires || []).length }
  }
  const a = shot()
  const b = shot()
  const same = JSON.stringify(a) === JSON.stringify(b)
  const ok = a.nodes > 0 && a.layers > 0 && a.wires > 0 && same
  console.log((ok ? '✓ ' : '✗ ') + '唯一布局'.padEnd(12)
    + ' 节点 ' + a.nodes + ' · 层 ' + a.layers + ' · 交叉 ' + a.crossings + ' · 线 ' + a.wires
    + (same ? ' · 两次一致' : ' · 两次不一致'))
  if (!ok) bad += 1
})()

// 展开链路每一步都要有记录：按下 -> 请求 -> 返回 -> 建节点 -> 连边 -> 高亮。
//
// 这条是为「按钮点了没反应」写的。没有 log 的时候，四种坏法在屏幕上长得一模一样
// （请求没发出去 / 返回空 / 建不出节点 / 渲染抛错），只能靠猜。开着 debug 之后
// 每一层都留下痕迹，一眼看得出断在哪。
function expandIsFullyLogged() {
  const base = { selected: null, edgeFocus: null, nodePositions: {}, pins: {}, turn: 1, gather: null, wireMode: 'all' }
  const g = side.emptyGraph()
  side.addNode(g, { id: 'a/m.js::f', symbol: 'f', file: 'a/m.js', kind: 'function', members: 0,
    line_start: 1, line_end: 9, peerCounts: { call: { up: 0, down: 2 } } })
  g.rootId = 'a/m.js::f'
  mark(side, g, 'a/m.js::f', { session: true })
  Object.assign(side.shared, base, { graph: g, trace: {}, selected: 'a/m.js::f' })

  // 桩：/expand 返回两个下游
  const peers = [
    { id: 'a/m.js::g', symbol: 'g', file: 'a/m.js', kind: 'function', members: 0, line_start: 11, line_end: 19, peerCounts: { call: { up: 1, down: 0 } } },
    { id: 'a/m.js::h', symbol: 'h', file: 'a/m.js', kind: 'function', members: 0, line_start: 21, line_end: 29, peerCounts: { call: { up: 1, down: 0 } } },
  ]
  B.ctx.fetch = (url) => {
    const u = String(url)
    if (u.indexOf('/expand') >= 0) {
      const dir = u.indexOf('dir=up') >= 0 ? 'up' : 'down'
      const rel = (u.match(/rel=([a-z]+)/) || [])[1] || 'call'
      const hit = dir === 'down' ? peers : []
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ peers: hit, count: hit.length, stamp: 's' }) })
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
  }

  const dbg = side.require_('dsh-cdd-lens/runtime/debug')

  const engine = B.require_('dsh-cdd-lens/engine/engine').makeEngine({ get: () => undefined, on: () => () => {}, emit: () => {} })
  return engine.expand('a/m.js::f', 'down', null, 'call').then(() => {
    const snap = dbg.snapshot()
    const kinds = snap.events.map(e => e.kind)
    const has = (kind, needle) => snap.events.some(e => e.kind === kind && e.text.indexOf(needle) >= 0)
    const traced = has('expand', 'start') && has('req', '/expand') && has('res', '/expand')
      && has('expand', '完成') && has('layout', 'placed=')
    const wired = g.edges.length === 2 && Object.keys(g.nodes).length === 3
    const highlighted = snap.events.some(e => e.kind === 'expand' && e.text.indexOf('高亮') >= 0)
    const ok = traced && wired && highlighted
    console.log((ok ? '✓ ' : '✗ ') + '展开全链路log'.padEnd(12)
      + ' 事件=' + kinds.length + ' 种=' + [...new Set(kinds)].join('/')
      + ' 节点=' + Object.keys(g.nodes).length + ' 边=' + g.edges.length
      + (highlighted ? ' 高亮已记' : ' 高亮缺失'))
    if (!ok) bad += 1
  })
}

// 看过的节点会过期撤下，edit 过的一直留着。
//
// 语义：一个节点被查看之后，只在最近 STICKY_TURNS(3) 轮里还算新鲜；会话往前走
// 一轮它就更旧一点，走够 3 轮就撤下来。**edit 过的例外——一直留着。**
// 没有这条的话图只进不出，翻过去的东西全赖在屏幕上。
;(function viewedFadesEditedStays() {
  const base = { selected: null, edgeFocus: null, nodePositions: {}, pins: {}, turn: 1, gather: null }
  const g = side.emptyGraph()
  const mk = (id, sym) => {
    side.addNode(g, { id, symbol: sym, file: 'a/m.js', kind: 'function', members: 0, line_start: 1, line_end: 9 })
    mark(side, g, id, { session: true })
  }
  mk('a/m.js::edited', 'edited')
  mk('a/m.js::viewed', 'viewed')
  mk('a/m.js::pinned', 'pinned')
  mark(side, g, 'a/m.js::pinned', { pinned: true })
  g.rootId = 'a/m.js::edited'
  side.addEdge(g, 'a/m.js::edited', 'a/m.js::viewed', ['call'])
  Object.assign(side.shared, base, {
    graph: g,
    trace: {
      'a/m.js::edited': { id: 'a/m.js::edited', firstTurn: 1, lastTurn: 1, state: 'edited', events: [{ turn: 1, verb: 'edit', onSurface: true }] },
      'a/m.js::viewed': { id: 'a/m.js::viewed', firstTurn: 1, lastTurn: 1, state: 'viewed', events: [{ turn: 1, verb: 'read', onSurface: true }] },
    },
  })
  const visible = side.require_('dsh-cdd-lens/graph/visible').visible
  const show = () => Object.keys(visible(side.shared.graph)).map(k => k.split('::')[1]).sort().join(',')
  const at1 = show()
  side.shared.turn = 4
  const at4 = show()

  const ok = at1 === 'edited,pinned,viewed'
    && at4 === 'edited,pinned'
  console.log((ok ? '✓ ' : '✗ ') + '过期与edit'.padEnd(12)
    + ' 第1轮[' + at1 + '] → 第4轮[' + at4 + '] · edit 一直在 · 看过的撤下 · pinned 一直在')
  if (!ok) bad += 1
})()

// 用户按钮比默认信息高：edit tree 里点展开，展开出来的节点不许再被树/过期过滤。
;(function editTreeKeepsExpandedPeers() {
  const g = side.emptyGraph()
  side.addNode(g, { id: 'a/edit.js::root', symbol: 'root', file: 'a/edit.js', kind: 'function',
    members: 0, line_start: 1, line_end: 9 })
  side.addNode(g, { id: 'a/edit.js::peer', symbol: 'peer', file: 'a/edit.js', kind: 'function',
    members: 0, line_start: 11, line_end: 19 })
  side.addEdge(g, 'a/edit.js::root', 'a/edit.js::peer', ['call'])
  g.rootId = 'a/edit.js::root'
  mark(side, g, 'a/edit.js::root', { session: true, open: { 'down:call': true } })
  mark(side, g, 'a/edit.js::peer', { explored: true })
  Object.assign(side.shared, {
    graph: g,
    trace: {
      'a/edit.js::root': { id: 'a/edit.js::root', firstTurn: 1, lastTurn: 1, state: 'edited',
        events: [{ turn: 1, verb: 'edit', onSurface: true }] },
      'a/edit.js::peer': { id: 'a/edit.js::peer', firstTurn: 1, lastTurn: 1, state: 'viewed',
        events: [{ turn: 1, verb: 'read', onSurface: true }] },
    },
    turn: 8,
    selected: null,
    edgeFocus: null,
    nodePositions: {},
    pins: {},
    gather: null,
    skin: 'auto',
    wireMode: 'all',
    treeMode: 'edit',
  })
  const visible = side.require_('dsh-cdd-lens/graph/visible').visible
  const show = () => Object.keys(visible(side.shared.graph)).map(k => k.split('::')[1]).sort().join(',')
  const editShown = show()
  const editDrawn = side.layout(g, undefined, 900)
  side.uiOf(g, 'a/edit.js::root').open['down:call'] = false
  const closedShown = show()
  const closedDrawn = side.layout(g, undefined, 900)
  const ok = editShown === 'peer,root'
    && editDrawn.nodes.length === 2 && (editDrawn.wires || []).length === 1
    && closedShown === 'root'
    && closedDrawn.nodes.length === 1 && (closedDrawn.wires || []).length === 0
  console.log((ok ? '✓ ' : '✗ ') + '按钮优先'.padEnd(12)
    + ' edit[' + editShown + '] 线 ' + (editDrawn.wires || []).length
    + ' · 折叠[' + closedShown + '] 线 ' + (closedDrawn.wires || []).length
    + ' · 展开不被默认过滤')
  if (!ok) bad += 1
  side.shared.treeMode = 'all'
})()

// 展开不许跳变：点开上/下展开时，已经画在屏幕上的节点一个像素都不许动。
//
// 这条以前是坏的：每层都按自己的高度垂直居中，新节点一进来就把老层整体推走，
// 实测点一次 ↓ 父节点下移 81px。现在位置冻结——画过的照旧，新的接在下面。
;(function expandDoesNotJump() {
  const base = { selected: null, edgeFocus: null, nodePositions: {}, pins: {}, turn: 4, gather: null, wireMode: 'all' }
  const g = build(side, Object.assign({}, base))
  // 先画一次：f 是根，g 在第二层。这一遍给出它们的初始位置。
  const first = side.layout(g, undefined, 900)
  const before = {}
  first.nodes.forEach(n => { before[n.id] = { x: n.x, y: n.y, w: n.w } })

  // 点开 g 的向下展开 call：往里塞三个新节点，名字故意长一点。
  mark(side, g, 'a/main.js::boot', { open: { 'down:call': true } })
  const fresh = [
    ['z/new.js::a_very_long_neighbour_name_alpha', 'a_very_long_neighbour_name_alpha'],
    ['z/new.js::b_very_long_neighbour_name_beta', 'b_very_long_neighbour_name_beta'],
    ['z/new.js::c_very_long_neighbour_name_gamma', 'c_very_long_neighbour_name_gamma'],
  ]
  fresh.forEach(([id, sym]) => {
    side.addNode(g, { id, symbol: sym, file: 'z/new.js', kind: 'function', members: 0, line_start: 1, line_end: 9 })
    mark(side, g, id, { session: true })
    side.addEdge(g, 'a/main.js::boot', id, ['call'])
  })

  const second = side.layout(g, undefined, 900)
  let jump = 0, widthMoved = 0, missing = 0
  second.nodes.forEach(n => {
    const was = before[n.id]
    if (was === undefined) return
    const d = Math.abs(n.x - was.x) + Math.abs(n.y - was.y)
    if (d > jump) jump = d
    if (Math.round(n.w) !== Math.round(was.w)) widthMoved += 1
  })
  fresh.forEach(([id]) => { if (second.nodes.filter(n => n.id === id).length === 0) missing += 1 })
  const gotWires = (second.wires || []).length
  const ok = jump === 0 && widthMoved === 0 && missing === 0 && gotWires > (first.wires || []).length
  console.log((ok ? '✓ ' : '✗ ') + '展开不跳变'.padEnd(12)
    + ' 老节点位移 ' + jump + 'px · 宽度被改 ' + widthMoved + ' · 新节点到齐 ' + (missing === 0 ? '✓' : '缺 ' + missing)
    + ' · 线 ' + (first.wires || []).length + '→' + gotWires)
  if (!ok) bad += 1
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
    side.addNode(g, { id, symbol: s, file: 'x/cross.js', kind: 'function', members: 0, line_start: 1, line_end: 9 })
    // 不在主链上：pin 住才在 visible 里有根，否则整列被 scope 丢掉，用例空转。
    mark(side, g, id, { session: true, down: true, up: true, pinned: true })
    seat(side, g, id, { layer: 4, tree: 9 })
  })
  ;['v1', 'v2', 'v3'].forEach((s, i) => {
    const id = 'x/cross.js::' + s
    side.addNode(g, { id, symbol: s, file: 'x/cross.js', kind: 'function', members: 0, line_start: 1, line_end: 9 })
    mark(side, g, id, { session: true, down: true, up: true, pinned: true })
    seat(side, g, id, { layer: 5, tree: 9 })
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
  let expandCalls = 0
  B.ctx.fetch = url => {
    const u = String(url)
    if (u.indexOf('/expand') >= 0) {
      expandCalls += 1
      const peers = u.indexOf('dir=up') >= 0 ? [] : [
        { id: 'a/m.js::g', symbol: 'g', file: 'a/m.js', kind: 'function', members: 0,
          line_start: 11, line_end: 19,
          peerCounts: { call: { up: 1, down: 0 } }, types: ['call'] },
      ]
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ peers: peers, count: peers.length, stamp: 'x' }) })
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
  }
  const engine = B.require_('dsh-cdd-lens/engine/engine').makeEngine({ get: () => undefined })
  Object.assign(side.shared, { trace: {}, turn: 4, selected: null, edgeFocus: null,
    nodePositions: {}, pins: {}, gather: null, skin: 'auto' })
  engine.focus({ id: 'a/m.js::f', symbol: 'f', file: 'a/m.js', kind: 'function', members: 0, start: 1, end: 9 })
    .then(() => {
      const g = side.shared.graph
      // /chain 已删：层由布局自己算，不再是服务端送下来的。
      // focus 现在只做一件事——按 call 关系把上下两层拉进图。
      const m = side.layout(g, undefined, 900)
      const ok = expandCalls === 2 && m.nodes.length === 2
      console.log((ok ? '✓ ' : '✗ ') + 'focus 建图'.padEnd(12)
        + ' expand 调用 ' + expandCalls + ' · 节点 ' + m.nodes.length + '/2')
      if (!ok) bad += 1
      return expandIsFullyLogged().then(nodeExpansionContract).then(finish)
    })
    .catch(error => {
      console.log('✗ focus 盖层    抛错: ' + String(error && error.message || error))
      bad += 1
      finish()
    })

  function nodeExpansionContract() {
    const calls = []
    B.ctx.fetch = url => {
      const u = String(url)
      calls.push(u)
      // 真实 worker 按 rel 过滤后返回（relPeers）；桩也照做，否则测的不是代码。
      const PARSE = { id: 'pkg/core.js::parse', symbol: 'parse', file: 'pkg/core.js', kind: 'function', members: 0,
        line_start: 30, line_end: 44, peerCounts: { call: { up: 1, down: 0 } } }
      const LOAD = { id: 'pkg/io.js::load', symbol: 'load', file: 'pkg/io.js', kind: 'function', members: 0,
        line_start: 10, line_end: 28, peerCounts: { dataflow: { up: 1, down: 0 } } }
      const HANDLE = { id: 'pkg/api.js::handle', symbol: 'handle', file: 'pkg/api.js', kind: 'function', members: 0,
        line_start: 8, line_end: 18, peerCounts: { call: { up: 0, down: 1 } } }
      const MAIN = { id: 'pkg/cli.js::main', symbol: 'main', file: 'pkg/cli.js', kind: 'function', members: 0,
        line_start: 50, line_end: 68, peerCounts: { dispatch: { up: 0, down: 1 } } }
      if (u.indexOf('/expand') >= 0) {
        const dir = u.indexOf('dir=up') >= 0 ? 'up' : 'down'
        const rel = (u.match(/rel=([a-z]+)/) || [])[1] || 'call'
        const table = {
          'down:call': [PARSE], 'down:dataflow': [LOAD],
          'up:call': [HANDLE], 'up:dispatch': [MAIN],
        }
        const peers = table[dir + ':' + rel] || []
        return Promise.resolve({ ok: true, json: () => Promise.resolve({
          id: 'pkg/core.js::root', direction: dir, relation: rel, peers: peers,
          count: peers.length, stamp: 'expand-contract',
        }) })
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    }

    const g = side.emptyGraph()
    side.addNode(g, {
      id: 'pkg/core.js::root', symbol: 'root', file: 'pkg/core.js', kind: 'function',
      members: 0, line_start: 1, line_end: 20,
      peerCounts: { call: { up: 2, down: 2 }, dataflow: { up: 0, down: 1 }, dispatch: { up: 1, down: 0 } },
    })
    g.rootId = 'pkg/core.js::root'
    Object.assign(side.shared, {
      graph: g, trace: {}, turn: 1, selected: null, edgeFocus: null,
      nodePositions: {}, pins: {}, gather: null, skin: 'auto', graphStamp: 'expand-contract',
    })
    const engine2 = B.require_('dsh-cdd-lens/engine/engine').makeEngine({ get: () => undefined })
    // 「有几个关系挂几个」：call 的上下、dataflow 的下、dispatch 的上，各按一次。
    return engine2.expand('pkg/core.js::root', 'down', null, 'call')
      .then(() => engine2.expand('pkg/core.js::root', 'up', null, 'call'))
      .then(() => engine2.expand('pkg/core.js::root', 'down', null, 'dataflow'))
      .then(() => engine2.expand('pkg/core.js::root', 'up', null, 'dispatch'))
      .then(() => {
        const ids = Object.keys(side.shared.graph.nodes)
        const edgeKey = e => e.from + '->' + e.to + ':' + (e.types || []).join(',')
        const edges = side.shared.graph.edges.map(edgeKey).sort()
        // 一次展开只走一个关系，所以每条边就是那一条关系自己的类型。
        // 四个按钮各按一次 → 四个节点、四条边，一根不多一根不少。
        const expectedEdges = [
          'pkg/api.js::handle->pkg/core.js::root:call',
          'pkg/cli.js::main->pkg/core.js::root:dispatch',
          'pkg/core.js::root->pkg/core.js::parse:call',
          'pkg/core.js::root->pkg/io.js::load:dataflow',
        ].sort()
        const expectedIds = [
          'pkg/api.js::handle',
          'pkg/cli.js::main',
          'pkg/core.js::parse',
          'pkg/core.js::root',
          'pkg/io.js::load',
        ].sort()
        const root = side.shared.graph.nodes['pkg/core.js::root']
        const rootUI = side.require_('dsh-cdd-lens/graph/model').uiOf(side.shared.graph, 'pkg/core.js::root')
        side.shared.wireMode = 'tree'
        side.shared.selected = null
        const drawn = side.layout(side.shared.graph, { call: true, dataflow: true, dispatch: true }, 900)
        const ok = calls.filter(u => u.indexOf('/expand') >= 0).length === 4
          && root.peerCounts.call.up === 2 && root.peerCounts.call.down === 2
          && ids.sort().join('|') === expectedIds.join('|')
          && edges.join('|') === expectedEdges.join('|')
          && rootUI.open['up:call'] === true && rootUI.open['down:call'] === true
          && drawn.wires.length === 4
        console.log((ok ? '✓ ' : '✗ ') + '节点展开'.padEnd(12)
          + ' 上游 2/2 · 下游 2/2 · 边方向 ' + (edges.join('|') === expectedEdges.join('|') ? '✓' : '✗')
          + ' · 画线 ' + drawn.wires.length + '/4')
        if (!ok) bad += 1
        return nodeExpansionRefreshesShortDirection()
      })
  }

  function nodeExpansionRefreshesShortDirection() {
    const calls = []
    B.ctx.fetch = url => {
      const u = String(url)
      calls.push(u)
      if (u.indexOf('/expand') >= 0 && u.indexOf('dir=down') >= 0) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({
          anchor: { id: 'pkg/core.js::root', symbol: 'root', file: 'pkg/core.js', kind: 'function', members: 0, line_start: 1, line_end: 20, up: 1, down: 2 },
          peers: [
            { id: 'pkg/core.js::parse', symbol: 'parse', file: 'pkg/core.js', kind: 'function', members: 0, line_start: 30, line_end: 44, peerCounts: { call: { up: 1, down: 0 } }, types: ['call'] },
            { id: 'pkg/io.js::load', symbol: 'load', file: 'pkg/io.js', kind: 'function', members: 0, line_start: 10, line_end: 28, peerCounts: { dataflow: { up: 1, down: 0 } }, types: ['dataflow'] },
          ],
          stamp: 'expand-contract',
        }) })
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    }

    const g = side.emptyGraph()
    side.addNode(g, {
      id: 'pkg/core.js::root', symbol: 'root', file: 'pkg/core.js', kind: 'function',
      members: 0, line_start: 1, line_end: 20, peerCounts: { call: { up: 1, down: 2 } },
    })
    side.addNode(g, {
      id: 'pkg/api.js::handle', symbol: 'handle', file: 'pkg/api.js', kind: 'function',
      members: 0, line_start: 8, line_end: 18, peerCounts: { call: { up: 0, down: 1 } },
    })
    side.addEdge(g, 'pkg/api.js::handle', 'pkg/core.js::root', ['call'])
    g.rootId = 'pkg/core.js::root'
    side.require_('dsh-cdd-lens/graph/model').uiOf(g, 'pkg/core.js::root').open['down:call'] = true
    Object.assign(side.shared, {
      graph: g, trace: {}, turn: 1, selected: null, edgeFocus: null,
      nodePositions: {}, pins: {}, gather: null, skin: 'auto', graphStamp: 'expand-contract',
    })
    const engine3 = B.require_('dsh-cdd-lens/engine/engine').makeEngine({ get: () => undefined })
    return engine3.expand('pkg/core.js::root', 'down').then(() => {
      const fetched = calls.filter(u => u.indexOf('/expand') >= 0 && u.indexOf('dir=down') >= 0).length
      const edges = side.shared.graph.edges
      const hasDown = edges.some(e => e.from === 'pkg/core.js::root' && e.to === 'pkg/core.js::parse')
        && edges.some(e => e.from === 'pkg/core.js::root' && e.to === 'pkg/io.js::load')
      const ok = fetched === 0 && !hasDown
      console.log((ok ? '✓ ' : '✗ ') + '展开补齐'.padEnd(12)
        + ' 已展开不再请求 · 反向边不冒充下游 · 请求 ' + fetched + ' · 假下游 ' + (hasDown ? '有' : '无'))
      if (!ok) bad += 1
    })
  }
})()
