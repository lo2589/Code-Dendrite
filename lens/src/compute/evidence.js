// dsh-cdd-lens — 计算单元 2：会话事件 → touch；解析后的证据 → 每一轮的 seed。
//
//   read ：meta.offset + meta.lines（[{number,text}]）给出行区间
//   write：写的是整个文件 → whole，取该文件全部 anchor（见 resolve.js）
//   edit ：没有行号，带上改后 / 改前文本里第一行 ≥12 字符的内容作为定位键
//   grep、glob、bash 等：不是证据
// 轮次：只有发生了 read/edit/write 的 turn 才算一轮（没有就是状态没变）。
// 计数器（#032）：查看过的节点初始 3，再看一次 +1，过一轮 -1，到 0 不显示；edit 一直留。
'use strict'

const VERBS = { read: 'read', read_image: 'read', edit: 'edit', write: 'edit', str_replace_editor: 'edit' }

function parseArgs(raw) {
  if (typeof raw !== 'string') return {}
  try {
    const value = JSON.parse(raw)
    return value !== null && typeof value === 'object' ? value : {}
  } catch {
    return {}
  }
}

/** 一段文本的定位键：第一行去空白后 ≥12 字符的内容。 */
function keyLine(text) {
  if (typeof text !== 'string') return null
  const key = text.split('\n').map(s => s.trim()).find(s => s.length >= 12)
  return key === undefined ? null : key
}

/** 会话事件（tool/call、tool/result 行）→ 按 seq 排好的调用，带结果。 */
function callsFromEvents(events) {
  const calls = new Map()
  const results = new Map()
  events.forEach((row, index) => {
    if (row === null || typeof row !== 'object') return
    const d = row.data || {}
    const seq = typeof row.seq === 'number' ? row.seq : index
    if (row.type === 'tool/call') {
      calls.set(d.callId, { seq, turn: Number(d.turn), step: Number(d.step), name: d.name, args: parseArgs(d.arguments) })
      return
    }
    if (row.type !== 'tool/result') return
    const msg = d.message || {}
    const first = Array.isArray(msg.content) ? (msg.content[0] || {}) : {}
    const callId = msg.toolCallId || first.toolCallId
    if (callId !== undefined) results.set(callId, { meta: d.meta || {}, failed: first.isError === true || d.error !== undefined })
  })
  return [...calls.entries()]
    .map(([id, call]) => Object.assign(call, { id, result: results.get(id) }))
    .sort((l, r) => l.seq - r.seq)
}

/** 一次已落定的调用 → touch 列表。还没返回结果的调用不算证据。 */
function touchesOf(call) {
  const verb = VERBS[call.name]
  if (verb === undefined || call.result === undefined || call.result.failed) return []
  const meta = call.result.meta
  const base = { turn: call.turn, step: call.step, name: call.name, verb }
  if (verb === 'read') {
    const from = Number.isInteger(meta.offset) ? meta.offset : (Number.isInteger(call.args.offset) ? call.args.offset : 1)
    let to = -1
    if (Array.isArray(meta.lines) && meta.lines.length > 0) {
      const last = meta.lines[meta.lines.length - 1]
      to = Number.isInteger(last.number) ? last.number : from + meta.lines.length - 1
    } else if (Number.isInteger(meta.lines)) {
      to = from + meta.lines - 1
    }
    return [{ ...base, file: meta.path || call.args.file_path, from, to, keys: [] }]
  }
  if (call.name === 'write') return [{ ...base, file: call.args.file_path, from: null, to: null, keys: [], whole: true }]
  const diffs = Array.isArray(meta.diffs) && meta.diffs.length > 0
    ? meta.diffs
    : [{ path: call.args.file_path, newText: call.args.new_string, oldText: call.args.old_string }]
  return diffs.map(d => ({
    ...base, file: d.path || call.args.file_path, from: null, to: null,
    keys: [keyLine(d.newText), keyLine(d.oldText)].filter(k => k !== null),
  }))
}

/** 整个会话 → touch 列表（按调用顺序）。 */
function touchesFromEvents(events) {
  return callsFromEvents(Array.isArray(events) ? events : []).flatMap(touchesOf)
}

/**
 * 截止到 turn 的 seed。
 * @param events - resolve 之后的证据：[{ turn, verb, anchors }]。
 * @returns seeds（edit ∪ 计数器 > 0）、edited、counter、rounds、faded。
 */
function seedsAt(events, turn) {
  const rounds = [...new Set(events.map(e => e.turn))].filter(t => t <= turn).sort((a, b) => a - b)
  const counter = new Map()
  const edited = new Set()
  const faded = new Set()
  rounds.forEach((t, i) => {
    if (i > 0) {
      for (const [id, n] of counter) {
        if (n - 1 <= 0) { counter.delete(id); faded.add(id) } else counter.set(id, n - 1)
      }
    }
    for (const e of events) {
      if (e.turn !== t) continue
      for (const id of e.anchors) {
        if (e.verb === 'edit') { edited.add(id); continue }
        counter.set(id, counter.has(id) ? counter.get(id) + 1 : 3)
        faded.delete(id)
      }
    }
  })
  const seeds = new Set([...edited, ...counter.keys()])
  return { seeds, edited, counter, rounds: rounds.length, faded: [...faded].filter(id => !seeds.has(id)) }
}

module.exports = { keyLine, touchesFromEvents, seedsAt }
