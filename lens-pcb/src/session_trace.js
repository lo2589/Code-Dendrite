// dsh-cdd-lens-pcb — session → anchor activity.
//
// Turns a live session's committed events into "which anchor did the agent
// touch, on which turn, doing what, and does the model still remember it".
//
// ## Where the line numbers come from, and where they don't
//
// `read` settles with `meta = { path, offset, lines, totalLines }`, so a read is
// an exact line window and resolves to exactly the anchors it overlapped.
//
// `edit` and `write` settle with `meta = { diffs: [{ path, oldText, newText }] }`
// — the applied hunks, and **no line numbers at all**. So an edit is located by
// searching the file on disk for the first substantial line of its `newText`.
// That is a best effort by construction: it reads the file as it is now, so a
// hunk that was later edited again can land on the wrong anchor or nowhere. The
// result carries `approx: true` and the view says so, because an edit silently
// attributed to the wrong function is worse than one honestly marked uncertain.
//
// `bash` is not parsed for redirections. A `sed -i` cannot be attributed to a
// tool call from its command string with any honesty, so it is left out rather
// than guessed at; a reindex still shows the changed anchors, just without a
// turn to pin them to.
//
// ## Why the fade is exact
//
// Compaction does not delete events. It appends a replacement carrying
// `surfaceOp: { op: 'replace', start, end }`, which shadows the original seqs
// on the model-visible surface while the human transcript keeps them. So
// "does the model still hold the verbatim evidence for this anchor" is not a
// heuristic: it is whether the settling event's seq is still on the surface.
//
// ## Read from the log, never from memory
//
// This takes an already-read event array, not a live `Session`. The in-memory
// store only holds sessions the process has loaded; a conversation from two
// days ago has an empty `events` there, and folding it produces zero touches
// while looking perfectly successful — an empty graph over a session that read
// eight files. The caller reads the durable log through `sessionQuery` instead,
// so the answer is the same whether the session is live, cold, or the harness
// restarted a minute ago.
'use strict'

const fs = require('node:fs')
const path = require('node:path')

/** Tool name → what the agent was doing to the code. */
const VERBS = new Map([
  ['read', 'read'], ['read_image', 'read'],
  ['edit', 'edit'], ['write', 'edit'], ['str_replace_editor', 'edit'],
  ['grep', 'search'], ['glob', 'search'],
])

/** Parse a tool/call's raw `arguments`, which is the model's unvalidated JSON string. */
function parseArgs(raw) {
  if (typeof raw !== 'string') return {}
  try {
    const value = JSON.parse(raw)
    return value !== null && typeof value === 'object' ? value : {}
  } catch {
    // A malformed argument string is the model's problem, not a reason to throw
    // out the whole trace.
    return {}
  }
}

/** The text blocks of a tool result, joined — used only to notice an error. */
function blockText(message) {
  const blocks = Array.isArray(message?.content) ? message.content : []
  let text = ''
  for (const block of blocks) {
    const inner = Array.isArray(block?.content) ? block.content : []
    for (const part of inner) if (typeof part?.text === 'string') text += part.text
    if (typeof block?.text === 'string') text += block.text
  }
  return text
}

/**
 * The first line of a hunk worth searching for.
 *
 * Blank lines and one-token lines like `}` or `else:` match everywhere and would
 * anchor an edit to whichever function happened to have one first, so the search
 * key must be long enough to be distinctive or the edit stays file-level.
 */
function searchKey(newText) {
  if (typeof newText !== 'string') return null
  for (const line of newText.split('\n')) {
    const trimmed = line.trim()
    if (trimmed.length >= 12) return trimmed
  }
  return null
}

/** 1-based line of the first occurrence of `key` in `file`, or null. */
function findLine(root, file, key) {
  if (key === null) return null
  try {
    const lines = fs.readFileSync(path.join(root, file), 'utf8').split('\n')
    for (let i = 0; i < lines.length; i += 1) {
      if (lines[i].includes(key)) return i + 1
    }
  } catch {
    return null
  }
  return null
}

/** Workspace-relative, forward-slashed — the form anchor ids are keyed by. */
function relative(root, file) {
  if (typeof file !== 'string' || file.length === 0) return null
  const absolute = path.isAbsolute(file) ? file : path.join(root, file)
  const rel = path.relative(root, absolute)
  // Outside the indexed root: not ours to attribute.
  if (rel.startsWith('..') || path.isAbsolute(rel)) return null
  return rel.split(path.sep).join('/')
}

/**
 * Fold one session's events into the touches the graph paints with.
 *
 * @param events - the complete raw log, read from persistence.
 * @param surfaceSeqs - seqs still on the model-visible surface; a settling seq
 *   missing from this set was shadowed by compaction, which is the fade.
 * @param root - absolute workspace root the anchors are keyed against.
 * @returns touches in event order, plus the last turn seen.
 */
function collect(events, surfaceSeqs, root) {
  const surface = new Set(surfaceSeqs ?? [])

  /** callId → the pending call, so a result can be joined back to its arguments. */
  const open = new Map()
  /** Touches this workspace cannot own, keyed to dedupe repeated reads of one path. */
  const settledOutside = new Map()
  const touches = []
  let turn = 0

  const seqOf = (event, index) => (typeof event?.seq === 'number' ? event.seq : index)

  for (let index = 0; index < events.length; index += 1) {
    const event = events[index]
    if (event === undefined || event === null) continue
    const data = event.data ?? {}
    if (typeof data.turn === 'number') turn = Math.max(turn, data.turn)

    if (event.type === 'tool/call') {
      const verb = VERBS.get(data.name)
      if (verb === undefined) continue
      open.set(data.callId, { turn: data.turn ?? turn, step: data.step ?? 0, name: data.name, verb, args: parseArgs(data.arguments), seq: seqOf(event, index) })
      continue
    }
    if (event.type !== 'tool/result') continue

    // A tool/result carries no callId of its own on `data`; the loop records
    // results under the model's call id inside the message.
    const callId = data.message?.toolCallId
      ?? (Array.isArray(data.message?.content) ? data.message.content[0]?.toolCallId : undefined)
    const call = callId === undefined ? undefined : open.get(callId)
    if (call === undefined) continue
    open.delete(callId)

    const seq = seqOf(event, index)
    const onSurface = surface.size === 0 ? true : surface.has(seq)
    const failed = data.error !== undefined
    const meta = data.meta ?? {}
    const base = { turn: call.turn, step: call.step, tool: call.name, verb: call.verb, seq, onSurface, failed }

    if (failed) continue

    if (call.verb === 'read') {
      const raw = meta.path ?? call.args.file_path
      const file = relative(root, raw)
      if (file === null) {
        if (typeof raw === 'string') {
          settledOutside.set(`${call.turn}:${raw}`, { turn: call.turn, tool: call.name, verb: call.verb, path: raw, reason: 'outside' })
        }
        continue
      }
      const from = Number.isInteger(meta.offset) ? meta.offset : (Number.isInteger(call.args.offset) ? call.args.offset : 1)
      const span = Number.isInteger(meta.lines) ? meta.lines : (Number.isInteger(call.args.limit) ? call.args.limit : null)
      touches.push({ ...base, file, from, to: span === null ? null : from + span - 1, approx: false })
      continue
    }

    if (call.verb === 'edit') {
      const diffs = Array.isArray(meta.diffs) ? meta.diffs : []
      if (diffs.length === 0) {
        const file = relative(root, call.args.file_path)
        if (file !== null) touches.push({ ...base, file, from: null, to: null, approx: true })
        continue
      }
      for (const diff of diffs) {
        const file = relative(root, diff.path ?? call.args.file_path)
        if (file === null) continue
        const line = findLine(root, file, searchKey(diff.newText ?? diff.oldText))
        touches.push({ ...base, file, from: line, to: line, approx: true })
      }
      continue
    }

    // search: the path argument scopes it, but a grep is not evidence that any
    // particular function was read, so it contributes a file scope and no anchor.
    const file = relative(root, call.args.path ?? call.args.file_path)
    if (file !== null) touches.push({ ...base, file, from: null, to: null, approx: true, scopeOnly: true })
  }

  // Everything the agent opened that this workspace's index cannot own. Kept
  // rather than dropped: a session that read twenty files and shows an empty
  // panel reads as a broken plugin, when the truth is usually that the files
  // were outside the project or were not code. Saying which is the difference
  // between an honest empty graph and a silent one.
  const outside = []
  for (const [, call] of settledOutside) outside.push(call)

  // Calls still open never settled: that is the agent working right now.
  const working = []
  for (const call of open.values()) {
    const file = relative(root, call.args.file_path ?? call.args.path)
    if (file === null) continue
    working.push({
      turn: call.turn, step: call.step, tool: call.name, verb: call.verb, seq: call.seq,
      onSurface: true, failed: false, file,
      from: Number.isInteger(call.args.offset) ? call.args.offset : null,
      to: null, approx: true, working: true,
    })
  }

  return { turn, touches: [...touches, ...working], outside }
}

/**
 * Reduce resolved touches into one record per anchor.
 *
 * The first turn that ever reached an anchor is kept forever — collapsing a
 * branch in the view must not lose it — and `state` is the strongest thing that
 * happened: working beats edited beats viewed.
 */
function merge(entries) {
  const byAnchor = new Map()
  for (const entry of entries) {
    const current = byAnchor.get(entry.id)
    const event = {
      turn: entry.turn, verb: entry.verb, tool: entry.tool,
      approx: entry.approx === true, onSurface: entry.onSurface !== false,
      working: entry.working === true,
    }
    if (current === undefined) {
      byAnchor.set(entry.id, {
        id: entry.id, anchor: entry.anchor,
        firstTurn: entry.turn, lastTurn: entry.turn,
        events: [event],
      })
      continue
    }
    current.firstTurn = Math.min(current.firstTurn, entry.turn)
    current.lastTurn = Math.max(current.lastTurn, entry.turn)
    current.events.push(event)
  }
  for (const record of byAnchor.values()) {
    record.events.sort((l, r) => l.turn - r.turn)
    const working = record.events.some(e => e.working)
    const edited = record.events.some(e => e.verb === 'edit')
    record.state = working ? 'working' : edited ? 'edited' : 'viewed'
    // Faded when NOTHING that put this anchor on the graph is still verbatim on
    // the model's surface. One surviving read is enough to say it still knows.
    record.remembered = record.events.some(e => e.onSurface)
    record.approx = record.events.every(e => e.approx)
  }
  return [...byAnchor.values()]
}

module.exports = { collect, merge }
