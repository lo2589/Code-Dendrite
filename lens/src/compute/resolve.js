// dsh-cdd-lens — 计算单元 2b：touch → anchor。
//
//   write        ：该文件全部 anchor
//   read 区间    ：与区间重叠的 anchor；无点号且有成员的符号跳过（成员才是具体答案）
//   read 单行 / edit：包住这一行的最小 anchor；edit 的行号由定位键在当前文件里找（先改后、再改前）
'use strict'

const fs = require('node:fs')
const path = require('node:path')

function fileTable(ctx) {
  if (ctx.fileTable !== undefined) return ctx.fileTable
  const byFile = new Map()
  const members = new Map()
  for (const id of ctx.visible) {
    const a = ctx.anchors[id]
    if (typeof a.file !== 'string' || typeof a.line_start !== 'number' || typeof a.line_end !== 'number') continue
    if (!byFile.has(a.file)) byFile.set(a.file, [])
    const symbol = String(a.symbol || '')
    byFile.get(a.file).push({ id, start: a.line_start, end: a.line_end, symbol })
    const dot = symbol.indexOf('.')
    if (dot > 0) {
      const parent = a.file + '::' + symbol.slice(0, dot)
      members.set(parent, (members.get(parent) || 0) + 1)
    }
  }
  for (const list of byFile.values()) list.sort((l, r) => l.start - r.start || r.end - l.end)
  ctx.fileTable = { byFile, members }
  return ctx.fileTable
}

/** 工具给的路径 → 索引用的仓库相对路径；仓库外返回 null。 */
function workspacePath(root, file) {
  if (typeof file !== 'string' || file === '') return null
  const rel = path.relative(root, path.resolve(root, file)).split(path.sep).join('/')
  return rel === '' || rel.startsWith('..') || path.isAbsolute(rel) ? null : rel
}

function lineOf(root, file, key, texts) {
  if (!texts.has(file)) {
    let lines = null
    try { lines = fs.readFileSync(path.join(root, file), 'utf8').split('\n') } catch { lines = null }
    texts.set(file, lines)
  }
  const lines = texts.get(file)
  if (lines === null) return null
  const at = lines.findIndex(line => line.includes(key))
  return at < 0 ? null : at + 1
}

function resolveTouch(ctx, touch, texts) {
  const file = workspacePath(ctx.root, touch.file)
  if (file === null) return { anchors: [], reason: typeof touch.file === 'string' ? 'outside' : 'no-file', file: touch.file }
  const { byFile, members } = fileTable(ctx)
  const list = byFile.get(file) || []
  if (list.length === 0) return { anchors: [], reason: 'not-indexed', file }
  if (touch.whole === true) return { anchors: list.map(a => a.id), reason: null, file }
  let from = Number.isInteger(touch.from) ? touch.from : null
  for (const key of touch.keys || []) {
    if (from !== null) break
    from = lineOf(ctx.root, file, key, texts)
  }
  if (from === null) return { anchors: [], reason: 'no-line', file }
  const to = touch.to === -1 ? Infinity : touch.to
  if (to === null || to === undefined || to === from) {
    const best = list.filter(a => a.start <= from && from <= a.end).sort((l, r) => (l.end - l.start) - (r.end - r.start))[0]
    return { anchors: best === undefined ? [] : [best.id], reason: best === undefined ? 'no-anchor' : null, file }
  }
  const hits = list
    .filter(a => !(a.start > to || a.end < from))
    .filter(a => a.symbol.includes('.') || !(members.get(a.id) > 0))
    .map(a => a.id)
  return { anchors: hits, reason: hits.length > 0 ? null : 'no-anchor', file }
}

/** touch 列表 → 证据事件 [{ turn, step, name, verb, file, anchors, reason }]。 */
function resolveAll(ctx, touches) {
  const texts = new Map()
  return touches.map((touch) => {
    const hit = resolveTouch(ctx, touch, texts)
    return { turn: touch.turn, step: touch.step, name: touch.name, verb: touch.verb, file: hit.file, anchors: hit.anchors, reason: hit.reason }
  })
}

module.exports = { resolveAll }
