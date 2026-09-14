// dsh-cdd-lens — 计算单元 5：文件框折叠。
//
// 用户：「超过5个的折叠，只保留层级高的，和pin 的，点加号展开，加号变减号，再点减号折叠，折叠的线和节点就不用画」
//       「（层级高）指的是调用链上游」
//   一个文件框（树里 / 旁边分开算）超过 FOLD_LIMIT 个 anchor、又没被点开时，只留：
//     必留：pin 的、点过展开的节点、展开拉出来的节点（展开 ⬆️N 必须正好出 N 个）
//     再按调用链上游补到 FOLD_LIMIT 个：屏幕上没人调用它的是入口（第 0 层），被调用的 = 调用它的最深一层 + 1；
//     同一层先留屏幕上边多的，再按行号
//   其余节点不画，连着它们的边也不画。点开（openFiles 里有这个框）就全画。
'use strict'

const { peers } = require('./anchors.js')

const FOLD_LIMIT = 5

/** 文件框的键：树里和旁边是两个框。 */
function boxKey(side, file) {
  return (side ? 'side:' : 'tree:') + file
}

/**
 * 调用链层级：只看屏幕上这些节点之间的 call。没人调用的是第 0 层，被调用的 = 调用它的最深一层 + 1。
 * 成环的节点排在已经排好的调用方后面（和 cdd draw 同一个做法）。
 * @returns Map<id, 层级>
 */
function callLevels(ctx, ids) {
  const set = new Set(ids)
  const callees = new Map()
  const indeg = new Map()
  ids.forEach((id) => { callees.set(id, []); indeg.set(id, 0) })
  ids.forEach((id) => {
    for (const to of peers(ctx, id, 'call', 'down')) {
      if (!set.has(to) || to === id) continue
      callees.get(id).push(to)
      indeg.set(to, indeg.get(to) + 1)
    }
  })
  const level = new Map(ids.map(id => [id, 0]))
  const queue = ids.filter(id => indeg.get(id) === 0).sort()
  const done = new Set()
  while (queue.length > 0) {
    const id = queue.shift()
    done.add(id)
    for (const to of callees.get(id)) {
      level.set(to, Math.max(level.get(to), level.get(id) + 1))
      indeg.set(to, indeg.get(to) - 1)
      if (indeg.get(to) === 0) queue.push(to)
    }
  }
  for (const id of ids) {
    if (done.has(id)) continue
    let deepest = -1
    ids.forEach((from) => { if (done.has(from) && callees.get(from).includes(id)) deepest = Math.max(deepest, level.get(from)) })
    level.set(id, deepest + 1)
  }
  return level
}

/**
 * @param ctx - 计算上下文（读 anchors、call 关系）。
 * @param layer - { nodes: Set, edges: [] }：屏幕上的树，被折叠的节点和边会被原地删掉。
 * @param side - 旁边的 seed id。
 * @param forced - 必留的 id（pin、展开的、展开拉出来的）。
 * @param openFiles - 点开的框的键（boxKey）。
 * @returns { side, folds, hidden }：folds[键] = { total, shown, hidden, open }，只列超过 FOLD_LIMIT 的框。
 */
function foldBoxes(ctx, layer, side, forced, openFiles) {
  const open = new Set(openFiles || [])
  const sideSet = new Set(side)
  const all = [...layer.nodes, ...side]
  const level = callLevels(ctx, all)
  const degree = new Map()
  layer.edges.forEach((e) => {
    degree.set(e.from, (degree.get(e.from) || 0) + 1)
    degree.set(e.to, (degree.get(e.to) || 0) + 1)
  })
  const boxes = new Map()
  for (const id of all) {
    const a = ctx.anchors[id]
    if (a === undefined) continue
    const key = boxKey(sideSet.has(id), a.file)
    if (!boxes.has(key)) boxes.set(key, [])
    boxes.get(key).push(id)
  }
  const hidden = new Set()
  const folds = {}
  for (const [key, ids] of boxes) {
    if (ids.length <= FOLD_LIMIT) continue
    if (open.has(key)) {
      folds[key] = { total: ids.length, shown: ids.length, hidden: 0, open: true }
      continue
    }
    const must = ids.filter(id => forced.has(id))
    const rest = ids.filter(id => !forced.has(id)).sort((x, y) => (level.get(x) || 0) - (level.get(y) || 0)
      || (degree.get(y) || 0) - (degree.get(x) || 0)
      || (ctx.anchors[x].line_start || 0) - (ctx.anchors[y].line_start || 0) || (x < y ? -1 : 1))
    const keep = rest.slice(0, Math.max(0, FOLD_LIMIT - must.length))
    rest.slice(keep.length).forEach(id => hidden.add(id))
    folds[key] = { total: ids.length, shown: must.length + keep.length, hidden: rest.length - keep.length, open: false }
  }
  hidden.forEach(id => layer.nodes.delete(id))
  layer.edges = layer.edges.filter(e => !hidden.has(e.from) && !hidden.has(e.to))
  return { side: side.filter(id => !hidden.has(id)), folds, hidden }
}

module.exports = { FOLD_LIMIT, boxKey, callLevels, foldBoxes }
