// dsh-cdd-lens — 计算单元 4：状态 → 屏幕。界面上有什么只由这里决定，其他地方不许再过滤。
//
// state  = { turn, tree, rels: {call:bool,…}, searched: [id], opens: [{ id, rel, dir }] }
// screen = {
//   nodes     选中的树（每个选中关系各算一棵，合并）+ 展开拉进来的
//   side      属于 seed、但不在 nodes 里的 → 堆一边
//   edges     只有选中关系的边；一条边一种类型
//   buttons   nodes ∪ side 上每个选中关系：len(字段) > 0 才有
//   anchors   nodes ∪ side 的新 anchor 记录
//   treeTotals 每棵树多少节点、多少关系（避免对不上）
//   violations 不变式违例（必须为空）
// }
'use strict'

const { RELATIONS, peers } = require('./anchors.js')
const { seedsAt } = require('./evidence.js')
const { resolveAll } = require('./resolve.js')
const { TREES, edgeKey, addEdge, treeFor } = require('./trees.js')

function normalizeState(state, events) {
  const turns = [...new Set(events.map(e => e.turn))].sort((a, b) => a - b)
  const rels = {}
  for (const r of RELATIONS) rels[r] = state.rels && typeof state.rels[r] === 'boolean' ? state.rels[r] : true
  const opens = (Array.isArray(state.opens) ? state.opens : []).filter(o => o !== null && typeof o === 'object'
    && typeof o.id === 'string' && RELATIONS.includes(o.rel) && (o.dir === 'up' || o.dir === 'down'))
  return {
    turns,
    turn: Number.isFinite(state.turn) ? state.turn : (turns.length > 0 ? turns[turns.length - 1] : 0),
    tree: TREES.includes(state.tree) ? state.tree : 'degree2',
    rels,
    searched: Array.isArray(state.searched) ? state.searched.map(String) : [],
    opens,
  }
}

/** 一棵树在所有选中关系上的并集。 */
function treeLayer(ctx, mode, rels, seedState, searched) {
  const nodes = new Set()
  const edges = []
  const seen = new Set()
  const perRelation = {}
  for (const rel of rels) {
    const tree = treeFor(ctx, mode, rel, seedState, searched)
    perRelation[rel] = { candidates: tree.candidates, nodes: tree.nodes.length, edges: tree.edges.length, middles: tree.middles.length, badLeaves: tree.badLeaves.length }
    tree.nodes.forEach(id => nodes.add(id))
    tree.edges.forEach(e => addEdge(edges, seen, e.from, e.to, e.type))
  }
  return { nodes, edges, seen, perRelation }
}

/** 按顺序应用展开：显示出来的节点都能展开；邻居已在屏幕上就连，不在就新建。 */
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

/** 每棵树（在当前选中关系下）多少节点、多少关系、旁边堆几个。 */
function treeTotals(ctx, rels, seedState, searched) {
  const totals = {}
  for (const mode of TREES) {
    const layer = treeLayer(ctx, mode, rels, seedState, searched)
    totals[mode] = { nodes: layer.nodes.size, edges: layer.edges.length, side: [...seedState.seeds].filter(id => !layer.nodes.has(id)).length }
  }
  return totals
}

function computeScreen(ctx, events, state) {
  const st = normalizeState(state || {}, events)
  const seedState = seedsAt(events, st.turn)
  const rels = RELATIONS.filter(r => st.rels[r])
  const layer = treeLayer(ctx, st.tree, rels, seedState, st.searched)
  const expansions = applyOpens(ctx, st, layer, seedState.seeds)
  const nodes = [...layer.nodes].sort()
  const side = [...seedState.seeds].sort().filter(id => !layer.nodes.has(id))
  const shown = [...nodes, ...side]
  const screen = {
    turn: st.turn, turns: st.turns, tree: st.tree, rels: st.rels, searched: st.searched,
    seeds: seedState.seeds.size, edited: [...seedState.edited].sort(),
    counter: Object.fromEntries(seedState.counter), faded: seedState.faded.length,
    nodes, side, edges: layer.edges,
    buttons: buttonsFor(ctx, shown, rels),
    anchors: Object.fromEntries(shown.map(id => [id, ctx.anchors[id]])),
    expansions, trees: layer.perRelation,
    treeTotals: treeTotals(ctx, rels, seedState, st.searched),
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
  for (const e of s.edges) {
    if (!nodes.has(e.from) || !nodes.has(e.to)) v.push('边端点不在屏幕: ' + edgeKey(e))
    if (!s.rels[e.type]) v.push('未选关系的边上屏: ' + edgeKey(e))
  }
  for (const id of s.side) {
    if (nodes.has(id)) v.push('side 与节点重叠: ' + id)
    if (!seedState.seeds.has(id)) v.push('side 不是 seed: ' + id)
  }
  for (const [rel, t] of Object.entries(s.trees)) if (t.badLeaves > 0) v.push(`${s.tree}×${rel} 有 ${t.badLeaves} 个非 seed 头/叶`)
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
