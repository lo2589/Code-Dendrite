// dsh-cdd-lens — 计算单元 3：树 × 关系（每种关系各算一棵，一条边只有一种类型）。
//
//   degree1（= 直接树）：seed 之间的直接边，没有中间点
//   degree2：没连上的 seed 沿关系上下游各展开 2 度 → 和 1 度树 merge →
//            反复删掉「不是 seed 的头节点（入度 0）和叶子节点（出度 0）」，直到头和叶全是 seed
//   edit   ：同 degree2，端点只认 edit 过的 seed
//   anchor ：搜索得到的 anchor（可以为空）
// 不在树里的 seed 由 screen.js 堆到一边。
'use strict'

const { peers } = require('./anchors.js')

const TREES = ['degree1', 'degree2', 'edit', 'anchor']

function edgeKey(e) {
  return e.from + '\0' + e.to + '\0' + e.type
}

function addEdge(list, seen, from, to, type) {
  const e = { from, to, type }
  if (seen.has(edgeKey(e))) return false
  seen.add(edgeKey(e))
  list.push(e)
  return true
}

/** ids 内部某关系的边（up、down 两个方向的字段都读）。 */
function edgesAmong(ctx, ids, rel) {
  const set = new Set(ids)
  const seen = new Set()
  const out = []
  for (const id of [...set].sort()) {
    for (const p of peers(ctx, id, rel, 'down')) if (set.has(p)) addEdge(out, seen, id, p, rel)
    for (const p of peers(ctx, id, rel, 'up')) if (set.has(p)) addEdge(out, seen, p, id, rel)
  }
  return out
}

function touchedNodes(edges) {
  const nodes = new Set()
  edges.forEach(e => { nodes.add(e.from); nodes.add(e.to) })
  return nodes
}

function direct(ctx, terminals, rel) {
  const edges = edgesAmong(ctx, terminals, rel)
  return { nodes: [...touchedNodes(edges)].sort(), edges, middles: [], candidates: terminals.length }
}

/** 从 start 沿 rel 往 dir 走 hops 步，边和节点并进 graph。 */
function spread(ctx, start, rel, dir, hops, graph) {
  const visited = new Set([start])
  let frontier = [start]
  for (let h = 0; h < hops; h += 1) {
    const next = []
    for (const id of frontier) {
      for (const p of peers(ctx, id, rel, dir)) {
        if (dir === 'down') addEdge(graph.edges, graph.seen, id, p, rel)
        else addEdge(graph.edges, graph.seen, p, id, rel)
        graph.nodes.add(p)
        if (!visited.has(p)) { visited.add(p); next.push(p) }
      }
    }
    frontier = next
  }
}

function degrees(edges) {
  const indeg = new Map()
  const outdeg = new Map()
  edges.forEach((e) => {
    outdeg.set(e.from, (outdeg.get(e.from) || 0) + 1)
    indeg.set(e.to, (indeg.get(e.to) || 0) + 1)
  })
  return { indeg, outdeg }
}

/** 反复删非 seed 的头（入度 0）和叶（出度 0）。 */
function prune(graph, terminals) {
  const term = new Set(terminals)
  for (;;) {
    const { indeg, outdeg } = degrees(graph.edges)
    const drop = [...graph.nodes].filter(id => !term.has(id) && (!indeg.get(id) || !outdeg.get(id)))
    if (drop.length === 0) return
    const gone = new Set(drop)
    drop.forEach(id => graph.nodes.delete(id))
    graph.edges = graph.edges.filter(e => !gone.has(e.from) && !gone.has(e.to))
  }
}

function degree2(ctx, terminals, rel) {
  const base = direct(ctx, terminals, rel)
  const graph = { nodes: new Set(base.nodes), edges: base.edges.slice(), seen: new Set(base.edges.map(edgeKey)) }
  for (const s of terminals.filter(id => !graph.nodes.has(id))) {
    graph.nodes.add(s)
    spread(ctx, s, rel, 'down', 2, graph)
    spread(ctx, s, rel, 'up', 2, graph)
  }
  const candidates = graph.nodes.size
  prune(graph, terminals)
  const seen = new Set(graph.edges.map(edgeKey))
  edgesAmong(ctx, [...graph.nodes], rel).forEach(e => addEdge(graph.edges, seen, e.from, e.to, e.type))
  const term = new Set(terminals)
  const nodes = [...touchedNodes(graph.edges)].sort()
  return { nodes, edges: graph.edges, middles: nodes.filter(id => !term.has(id)), candidates }
}

function anchorTree(ctx, searched, rel) {
  const nodes = [...new Set(searched.filter(id => ctx.anchors[id] !== undefined))].sort()
  return { nodes, edges: edgesAmong(ctx, nodes, rel), middles: [], candidates: nodes.length }
}

/** 树自检：非端点节点不许是头（入度 0）或叶（出度 0）。 */
function leafCheck(tree, terminals) {
  const term = new Set(terminals)
  const { indeg, outdeg } = degrees(tree.edges)
  return tree.nodes.filter(id => !term.has(id) && (!indeg.get(id) || !outdeg.get(id)))
}

/** 一棵树、一种关系。按 (模式, 关系, seed/edit 集合或搜索集合) 缓存。 */
function treeFor(ctx, mode, rel, seedState, searched) {
  const seeds = [...seedState.seeds].sort()
  const edits = [...seedState.edited].sort()
  const key = [mode, rel, mode === 'anchor' ? searched.join(',') : seeds.join(',') + '|' + edits.join(',')].join('#')
  if (ctx.treeCache.has(key)) return ctx.treeCache.get(key)
  if (ctx.treeCache.size > 500) ctx.treeCache.clear()
  let tree
  let terminals = seeds
  if (mode === 'degree1') tree = direct(ctx, seeds, rel)
  else if (mode === 'degree2') tree = degree2(ctx, seeds, rel)
  else if (mode === 'edit') { terminals = edits; tree = degree2(ctx, edits, rel) }
  else if (mode === 'anchor') { terminals = searched; tree = anchorTree(ctx, searched, rel) }
  else throw new Error('unknown tree ' + mode)
  tree.badLeaves = mode === 'anchor' ? [] : leafCheck(tree, terminals)
  ctx.treeCache.set(key, tree)
  return tree
}

module.exports = { TREES, edgeKey, addEdge, treeFor }
