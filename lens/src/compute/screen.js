// dsh-cdd-lens — 计算单元 4：状态 → 屏幕。界面上有什么只由这里决定，其他地方不许再过滤。
//
// state = { turn, tree, rels: {call:bool,…}, pins: [{ id, at, until }], opens: [{ id, rel, dir }] }
//   pins ：人为固定（含搜索），优先级最高。pin 期间计数器不减、取消 pin 后再减（见 evidence.seedsAt）；
//          开什么树加进什么树，和屏幕上的节点有什么边连什么边。兼容 pinned: [id]（从一开始就 pin 着）。
// 顺序（固定）：选中的树 → 加 pin → 展开 → pin 连边 → 旁边（不在树里的 seed，堆到树下面）
// screen = { nodes, side, pinned, edges, buttons, anchors, expansions, trees, treeTotals, violations }
'use strict'

const { RELATIONS, peers } = require('./anchors.js')
const { seedsAt } = require('./evidence.js')
const { resolveAll } = require('./resolve.js')
const { TREES, edgeKey, addEdge, treeFor } = require('./trees.js')

function normalizePins(ctx, state) {
  const pins = (Array.isArray(state.pins) ? state.pins : [])
    .filter(p => p !== null && typeof p === 'object' && typeof p.id === 'string')
    .map(p => ({ id: p.id, at: Number.isFinite(p.at) ? p.at : -Infinity, until: Number.isFinite(p.until) ? p.until : null }))
  const legacy = (Array.isArray(state.pinned) ? state.pinned : []).map(id => ({ id: String(id), at: -Infinity, until: null }))
  return [...pins, ...legacy].filter(p => ctx.visible.has(p.id))
}

function normalizeState(ctx, state, events) {
  const turns = [...new Set(events.map(e => e.turn))].sort((a, b) => a - b)
  const turn = Number.isFinite(state.turn) ? state.turn : (turns.length > 0 ? turns[turns.length - 1] : 0)
  const rels = {}
  for (const r of RELATIONS) rels[r] = state.rels && typeof state.rels[r] === 'boolean' ? state.rels[r] : true
  const opens = (Array.isArray(state.opens) ? state.opens : []).filter(o => o !== null && typeof o === 'object'
    && typeof o.id === 'string' && RELATIONS.includes(o.rel) && (o.dir === 'up' || o.dir === 'down'))
  const pins = normalizePins(ctx, state)
  const pinned = [...new Set(pins.filter(p => p.at <= turn && (p.until === null || turn < p.until)).map(p => p.id))].sort()
  return { turns, turn, tree: TREES.includes(state.tree) ? state.tree : 'degree2', rels, pins, pinned, opens }
}

/** 一棵树在所有选中关系上的并集。 */
function treeLayer(ctx, mode, rels, seedState) {
  const nodes = new Set()
  const edges = []
  const seen = new Set()
  const perRelation = {}
  for (const rel of rels) {
    const tree = treeFor(ctx, mode, rel, seedState)
    perRelation[rel] = { candidates: tree.candidates, nodes: tree.nodes.length, edges: tree.edges.length, middles: tree.middles.length, badLeaves: tree.badLeaves.length }
    tree.nodes.forEach(id => nodes.add(id))
    tree.edges.forEach(e => addEdge(edges, seen, e.from, e.to, e.type))
  }
  return { nodes, edges, seen, perRelation }
}

/** 展开：显示出来的节点（树里的、旁边的）都能展开；邻居在屏幕上就连，不在就新建。 */
function applyOpens(ctx, st, layer, seeds) {
  const expansions = []
  for (const op of st.opens) {
    if (!st.rels[op.rel]) { expansions.push({ ...op, skipped: 'relation-off' }); continue }
    if (!layer.nodes.has(op.id) && !seeds.has(op.id)) { expansions.push({ ...op, skipped: 'not-on-screen' }); continue }
    layer.nodes.add(op.id)
    const list = peers(ctx, op.id, op.rel, op.dir)
    let fresh = 0
    for (const p of list) {
      // 旁边堆着的 seed 已经显示在屏幕上：连上它算「连已有」，不算新建。
      if (!layer.nodes.has(p) && !seeds.has(p)) fresh += 1
      layer.nodes.add(p)
      if (op.dir === 'down') addEdge(layer.edges, layer.seen, op.id, p, op.rel)
      else addEdge(layer.edges, layer.seen, p, op.id, op.rel)
    }
    expansions.push({ ...op, count: list.length, peers: list, fresh })
  }
  return expansions
}

/** pin 连边：和屏幕上的节点（含旁边的 seed）有什么边连什么边；被连到的旁边 seed 进树。 */
function connectPinned(ctx, st, layer, seeds) {
  const onScreen = id => layer.nodes.has(id) || seeds.has(id)
  for (const id of st.pinned) {
    for (const rel of RELATIONS.filter(r => st.rels[r])) {
      for (const p of peers(ctx, id, rel, 'down')) {
        if (!onScreen(p)) continue
        layer.nodes.add(p)
        addEdge(layer.edges, layer.seen, id, p, rel)
      }
      for (const p of peers(ctx, id, rel, 'up')) {
        if (!onScreen(p)) continue
        layer.nodes.add(p)
        addEdge(layer.edges, layer.seen, p, id, rel)
      }
    }
  }
}

/** 某棵树选中时屏幕上的节点和边（固定顺序：树 → pin → 展开 → pin 连边 → 旁边）。 */
function screenLayer(ctx, st, mode, seedState) {
  const rels = RELATIONS.filter(r => st.rels[r])
  const layer = treeLayer(ctx, mode, rels, seedState)
  st.pinned.forEach(id => layer.nodes.add(id))
  const expansions = applyOpens(ctx, st, layer, seedState.seeds)
  connectPinned(ctx, st, layer, seedState.seeds)
  const side = [...seedState.seeds].sort().filter(id => !layer.nodes.has(id))
  return { layer, expansions, side }
}

function buttonsFor(ctx, ids, rels) {
  const buttons = {}
  for (const id of ids) {
    const b = {}
    for (const rel of rels) {
      const up = peers(ctx, id, rel, 'up').length
      const down = peers(ctx, id, rel, 'down').length
      if (up > 0) b[rel + 'up'] = up
      if (down > 0) b[rel + 'down'] = down
    }
    buttons[id] = b
  }
  return buttons
}

function computeScreen(ctx, events, state) {
  const st = normalizeState(ctx, state || {}, events)
  const seedState = seedsAt(events, st.turn, st.pins)
  const rels = RELATIONS.filter(r => st.rels[r])
  const { layer, expansions, side } = screenLayer(ctx, st, st.tree, seedState)
  const nodes = [...layer.nodes].sort()
  const shown = [...nodes, ...side]
  const treeTotals = {}
  for (const mode of TREES) {
    const other = mode === st.tree ? { layer, side } : screenLayer(ctx, st, mode, seedState)
    treeTotals[mode] = { nodes: other.layer.nodes.size, edges: other.layer.edges.length, side: other.side.length }
  }
  const screen = {
    turn: st.turn, turns: st.turns, tree: st.tree, rels: st.rels, pinned: st.pinned,
    seeds: seedState.seeds.size, edited: [...seedState.edited].sort(),
    counter: Object.fromEntries(seedState.counter), faded: seedState.faded.length,
    nodes, side, edges: layer.edges,
    buttons: buttonsFor(ctx, shown, rels),
    anchors: Object.fromEntries(shown.map(id => [id, ctx.anchors[id]])),
    expansions, trees: layer.perRelation, treeTotals,
  }
  screen.violations = check(ctx, screen, seedState)
  return screen
}

/** 不变式。任何一条不成立都记下来。 */
function check(ctx, s, seedState) {
  const v = []
  const nodes = new Set(s.nodes)
  const keys = new Set(s.edges.map(edgeKey))
  for (const id of s.nodes) if (!ctx.visible.has(id)) v.push('节点不在索引: ' + id)
  for (const id of s.pinned) if (!nodes.has(id)) v.push('pin 的节点不在屏幕上: ' + id)
  for (const e of s.edges) {
    if (!nodes.has(e.from) || !nodes.has(e.to)) v.push('边端点不在屏幕: ' + edgeKey(e))
    if (!s.rels[e.type]) v.push('未选关系的边上屏: ' + edgeKey(e))
  }
  for (const id of s.side) {
    if (nodes.has(id)) v.push('旁边与节点重叠: ' + id)
    if (!seedState.seeds.has(id)) v.push('旁边不是 seed: ' + id)
  }
  for (const [rel, t] of Object.entries(s.trees)) if (t.badLeaves > 0) v.push(`${s.tree}×${rel} 有 ${t.badLeaves} 个非 seed 头/叶`)
  const own = s.treeTotals[s.tree]
  if (own.nodes !== s.nodes.length || own.edges !== s.edges.length || own.side !== s.side.length) v.push('当前树的数字和屏幕对不上')
  for (const x of s.expansions) {
    if (x.skipped) continue
    const button = s.buttons[x.id][x.rel + x.dir] || 0
    if (button !== x.count) v.push(`按钮 ${x.rel}${x.dir}=${button} ≠ 展开 ${x.count}: ${x.id}`)
    const drawn = x.peers.filter(p => nodes.has(p) && keys.has(edgeKey(x.dir === 'down'
      ? { from: x.id, to: p, type: x.rel } : { from: p, to: x.id, type: x.rel }))).length
    if (drawn !== x.count) v.push(`展开 ${x.rel}${x.dir} 数字 ${x.count} ≠ 画出的边 ${drawn}: ${x.id}`)
  }
  return v
}

/** touch（来自会话）+ 状态 → 屏幕。worker 和 shell 脚本都走这一个入口。 */
function screenFor(ctx, touches, state) {
  const events = resolveAll(ctx, touches)
  const screen = computeScreen(ctx, events, state)
  const unresolved = {}
  events.filter(e => e.anchors.length === 0).forEach(e => { unresolved[e.reason] = (unresolved[e.reason] || 0) + 1 })
  screen.evidence = { touches: events.length, unresolved }
  return screen
}

module.exports = { computeScreen, screenFor }
