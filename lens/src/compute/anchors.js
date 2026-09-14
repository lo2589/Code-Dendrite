// dsh-cdd-lens — 计算单元 1：新 anchor。
//
// 新 anchor = anchors.json 原始记录（一个字段不改）+ relations.json 里 anchor 没有的边。
//   原来没有的方向：字段名 = 关系名 + up/down（dataflowup、dispatchdown …）
//   call、inherit↓ 本来就有（callers / callees / parent_classes）：读原生字段，过滤到只剩 anchor
//   len(字段) 就是按钮上的数字；peers() 是唯一取数口。
// dataflow 只算 return 和 relay（见 countsAsRelation）：arg 就是 call，self.x 写 → 读只是两个定义。
'use strict'

const RELATIONS = ['call', 'dataflow', 'inherit', 'dispatch', 'impact']

/** anchor 本来就带的方向。没列在这里的方向一律补「关系名+up/down」。 */
const NATIVE = { 'call:up': 'callers', 'call:down': 'callees', 'inherit:down': 'parent_classes' }

const DATAFLOW_KINDS = new Set(['arg', 'return', 'relay', 'state'])

/**
 * 一条 dataflow 边的 kind 集合（arg / return / relay / state）。
 *
 * 口径同生成器 generate_relations.py::_edge_kinds：evidence 以 "strict-dataflow:" 开头，冒号后按 + 拆。
 * 老索引没有 evidence 时，data_out 本身就是 kind 名（如 "relay+return"）才照认；
 * 生成器兜底的「调用即数据流」data_out 是类型名，拆不出 kind，是空集。
 */
function dataflowKinds(edge) {
  const evidence = String((edge && edge.evidence) || '')
  if (evidence.startsWith('strict-dataflow:')) {
    return new Set(evidence.slice('strict-dataflow:'.length).split('+').filter(Boolean))
  }
  if (evidence.length > 0) return new Set()
  const parts = String((edge && edge.data_out) || '').split('+').map(s => s.trim()).filter(Boolean)
  return parts.length > 0 && parts.every(p => DATAFLOW_KINDS.has(p)) ? new Set(parts) : new Set()
}

/**
 * 这条边算不算关系。读 relations.json 的入口（fromIndex、index_worker.build）都先过这里。
 *
 * dataflow 只算 return（B 的返回值被 A 拿去当输入）和 relay（产出方 → 接收方）。
 * arg（就是 call）、state（self.x 写 → 读，两个 anchor 只是定义）、没有 kind 的都不算。
 * 其它关系类型原样算。
 */
function countsAsRelation(edge) {
  if (edge === null || typeof edge !== 'object' || edge.edge_type !== 'dataflow') return true
  const kinds = dataflowKinds(edge)
  return kinds.has('return') || kinds.has('relay')
}

function isVirtual(a) {
  return a !== null && typeof a === 'object' && (a.is_virtual === true || a.symbol_type === 'virtual_block')
}

/** relations.json → 两端都是可见 anchor 的边；穿过虚拟 anchor；同 (from,to,type) 去重。 */
function visibleEdges(raw, visible, relationEdges) {
  const out = new Map()
  for (const e of relationEdges) {
    if (!Object.hasOwn(raw, e.from_id) || !Object.hasOwn(raw, e.to_id)) continue
    if (!out.has(e.from_id)) out.set(e.from_id, [])
    out.get(e.from_id).push(e)
  }
  const seen = new Set()
  const result = []
  const add = (from, to, type) => {
    if (from === to || !visible.has(from) || !visible.has(to)) return
    const key = from + '\0' + to + '\0' + type
    if (seen.has(key)) return
    seen.add(key)
    result.push({ from, to, type })
  }
  const walk = (from, mid, type, visited) => {
    if (visited.has(mid)) return
    visited.add(mid)
    for (const e of out.get(mid) || []) {
      if (visible.has(e.to_id)) add(from, e.to_id, type)
      else walk(from, e.to_id, type, visited)
    }
  }
  for (const from of visible) {
    for (const e of out.get(from) || []) {
      if (visible.has(e.to_id)) add(from, e.to_id, e.edge_type)
      else walk(from, e.to_id, e.edge_type, new Set())
    }
  }
  return result
}

function pushUnique(obj, key, value) {
  if (obj[key] === undefined) obj[key] = []
  if (!obj[key].includes(value)) obj[key].push(value)
}

/**
 * 一份索引 → 计算上下文。每次索引重建做一次。
 * @param root - 仓库根（绝对路径）。
 * @param raw - anchors.json 解析结果。
 * @param relationEdges - relations.json 的 edges（不算关系的 dataflow 在这里先滤掉）。
 */
function fromIndex(root, raw, relationEdges) {
  const visible = new Set(Object.keys(raw).filter(id => !isVirtual(raw[id])))
  const edges = visibleEdges(raw, visible, (relationEdges || []).filter(countsAsRelation))
  const extra = {}
  for (const id of visible) extra[id] = {}
  for (const e of edges) {
    if (NATIVE[e.type + ':down'] === undefined) pushUnique(extra[e.from], e.type + 'down', e.to)
    if (NATIVE[e.type + ':up'] === undefined) pushUnique(extra[e.to], e.type + 'up', e.from)
  }
  const anchors = {}
  for (const id of visible) {
    const anchor = Object.assign({ id }, raw[id], extra[id])
    // 原生的 callers / callees / parent_classes 里混着裸名字（print、len、Promise.resolve 的 resolve…）
    // 和不在索引里的 id（external::TestCase）。裸名字不是 anchor，不参与计数：节点上的这三个字段
    // 只留真实 anchor id——字段长度就是按钮数字，也就是展开能拉回的个数。
    for (const field of Object.values(NATIVE)) {
      if (!Array.isArray(anchor[field])) continue
      anchor[field] = [...new Set(anchor[field].map(String))].filter(x => x !== id && visible.has(x))
    }
    anchors[id] = anchor
  }
  return { root, raw, visible, anchors, edgeCount: edges.length, treeCache: new Map() }
}

/** 某个 anchor 某关系某方向的邻居：读字段，过滤到只剩可见 anchor，去重，排序。 */
function peers(ctx, id, rel, dir) {
  const a = ctx.anchors[id]
  if (a === undefined) return []
  const field = NATIVE[rel + ':' + dir] || rel + dir
  const list = Array.isArray(a[field]) ? a[field] : []
  return [...new Set(list.filter(x => x !== id && ctx.visible.has(x)))].sort()
}

/** 自检：a 的 down 里有 b，b 的 up 里却没有 a。 */
function asymmetry(ctx) {
  const report = {}
  for (const rel of RELATIONS) {
    let bad = 0
    for (const id of ctx.visible) {
      for (const p of peers(ctx, id, rel, 'down')) if (!peers(ctx, p, rel, 'up').includes(id)) bad += 1
    }
    report[rel] = bad
  }
  return report
}

/** 补出来的字段：每个字段多少 anchor 带、共多少条。 */
function extraFields(ctx) {
  const stats = {}
  for (const id of ctx.visible) {
    for (const key of Object.keys(ctx.anchors[id])) {
      if (key === 'id' || Object.hasOwn(ctx.raw[id], key)) continue
      stats[key] = stats[key] || { anchors: 0, entries: 0 }
      stats[key].anchors += 1
      stats[key].entries += ctx.anchors[id][key].length
    }
  }
  return stats
}

module.exports = { RELATIONS, NATIVE, dataflowKinds, countsAsRelation, fromIndex, peers, asymmetry, extraFields }
