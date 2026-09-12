// dsh-cdd-lens-pcb — index worker.
//
// Runs on a worker thread and never on the harness's. CodeDendrite's index for
// this repository alone is 6.7MB of anchors.json plus 2.9MB of relations.json;
// `JSON.parse` on that is hundreds of milliseconds of straight-line CPU, and on
// the main thread that is hundreds of milliseconds during which the chat cannot
// stream a token. So the parse, the index build, and every query happen here,
// and the main thread only ever posts a message and awaits a reply.
//
// One worker holds every root it has been asked about, keyed by absolute path,
// each with the mtimes it was built from. A query names its root; a changed
// mtime rebuilds that root and leaves the others alone.
'use strict'

const fs = require('node:fs')
const path = require('node:path')
const { parentPort } = require('node:worker_threads')

/**
 * Built indexes by absolute root path, most-recently-used last.
 *
 * Bounded on purpose. One 250k-anchor index costs roughly 350MB resident, and
 * without a bound a user who moves between three large projects in one session
 * pins about a gigabyte in this thread forever. Rebuilding is cheap by
 * comparison — measured at 0.5–0.9s for indexes of that size — so the trade is
 * plainly worth making, and the query itself never touches the evicted ones.
 */
const repos = new Map()

/** How many roots stay resident. Two, so switching back and forth is still warm. */
const MAX_RESIDENT = 2

/** Mark a root as most recently used, evicting the coldest beyond the bound. */
function touchRepo(root, repo) {
  repos.delete(root)
  repos.set(root, repo)
  while (repos.size > MAX_RESIDENT) {
    // Map iterates in insertion order, so the first key is the coldest.
    const coldest = repos.keys().next().value
    if (coldest === undefined || coldest === root) break
    repos.delete(coldest)
  }
  return repo
}

/**
 * Everything a root's queries read, derived once per build.
 *
 * `byFile` is sorted by `line_start` so a line lookup is a binary search rather
 * than a scan of every anchor in the file, and `enclosing` returns the SMALLEST
 * containing range: a method inside a class inside a module all contain line
 * 210, and the method is the honest answer.
 */
class Repo {
  constructor(root) {
    this.root = root
    this.anchors = new Map()
    this.byFile = new Map()
    this.out = new Map()
    this.in = new Map()
    this.members = new Map()
    this.stamp = null
  }
}

function indexPaths(root) {
  const dir = path.join(root, '.codedendrite')
  return { anchors: path.join(dir, 'anchors.json'), relations: path.join(dir, 'relations.json') }
}

/** mtime+size of both index files: the cheapest thing that changes when cdd rewrites them. */
function stampOf(root) {
  const { anchors, relations } = indexPaths(root)
  try {
    const a = fs.statSync(anchors)
    const r = fs.statSync(relations)
    return `${a.mtimeMs}:${a.size}:${r.mtimeMs}:${r.size}`
  } catch {
    return null
  }
}

function push(map, key, value) {
  const list = map.get(key)
  if (list === undefined) map.set(key, [value])
  else list.push(value)
}

/**
 * Parse one root's index into the query shapes.
 *
 * Anchor ids are `file::symbol`; a method reads `file::Class.method`, which is
 * how `members` is derived without a second pass over the source — the id
 * already carries the containment CodeDendrite recorded.
 */
function build(root) {
  const stamp = stampOf(root)
  if (stamp === null) return null
  const { anchors: anchorsPath, relations: relationsPath } = indexPaths(root)
  const repo = new Repo(root)
  repo.stamp = stamp

  const raw = JSON.parse(fs.readFileSync(anchorsPath, 'utf8'))
  for (const [id, a] of Object.entries(raw)) {
    const node = {
      id,
      file: a.file ?? id.split('::')[0],
      symbol: a.symbol ?? id.split('::')[1] ?? id,
      start: typeof a.line_start === 'number' ? a.line_start : null,
      end: typeof a.line_end === 'number' ? a.line_end : null,
      kind: a.symbol_type ?? null,
    }
    repo.anchors.set(id, node)
    push(repo.byFile, node.file, node)
    // `Class.method` — the dot is inside the symbol half, after `::`.
    const dot = node.symbol.indexOf('.')
    if (dot > 0) push(repo.members, `${node.file}::${node.symbol.slice(0, dot)}`, id)
  }
  for (const list of repo.byFile.values()) {
    list.sort((l, r) => (l.start ?? 0) - (r.start ?? 0) || (r.end ?? 0) - (l.end ?? 0))
  }

  const rel = JSON.parse(fs.readFileSync(relationsPath, 'utf8'))
  for (const e of rel.edges ?? []) {
    // Edges reaching outside the index (builtins like `print`, third-party
    // calls) are dropped rather than drawn as phantom nodes: the graph shows
    // this repository, and a node with no anchor has no source to open.
    if (!repo.anchors.has(e.from_id) || !repo.anchors.has(e.to_id)) continue
    const edge = { from: e.from_id, to: e.to_id, type: e.edge_type }
    push(repo.out, e.from_id, edge)
    push(repo.in, e.to_id, edge)
  }
  return repo
}

/** The built index for `root`, rebuilt when the files on disk moved under it. */
function repoFor(root) {
  const current = repos.get(root)
  const stamp = stampOf(root)
  if (stamp === null) return null
  if (current !== undefined && current.stamp === stamp) return touchRepo(root, current)
  const built = build(root)
  if (built !== null) touchRepo(root, built)
  return built
}

/** Distinct edges to `id`'s neighbours in one direction, deduped by target. */
function hop(repo, id, direction) {
  const edges = (direction === 'up' ? repo.in : repo.out).get(id) ?? []
  const byPeer = new Map()
  for (const e of edges) {
    const peer = direction === 'up' ? e.from : e.to
    if (peer === id) continue
    const seen = byPeer.get(peer)
    // A pair can carry several relation kinds — `update_anchors_for_files` reaches
    // `_generate_anchors_for_paths` as both `call` and `dataflow`. Both are true,
    // so both are reported and the view draws one line per kind.
    if (seen === undefined) byPeer.set(peer, { id: peer, types: [e.type] })
    else if (!seen.types.includes(e.type)) seen.types.push(e.type)
  }
  return [...byPeer.values()].map(entry => ({
    ...entry,
    ...describe(repo, entry.id),
  }))
}

/** The wire shape of one anchor, plus the counts a collapsed node has to show. */
function describe(repo, id) {
  const a = repo.anchors.get(id)
  if (a === undefined) return { id, missing: true }
  return {
    id,
    file: a.file,
    symbol: a.symbol,
    start: a.start,
    end: a.end,
    kind: a.kind,
    members: (repo.members.get(id) ?? []).length,
    up: new Set((repo.in.get(id) ?? []).map(e => e.from)).size,
    down: new Set((repo.out.get(id) ?? []).map(e => e.to)).size,
  }
}

/** The directory/file/symbol outline — the `cdd draw` shape, for finding things. */
function outline(repo) {
  const files = [...repo.byFile.entries()]
    .map(([file, list]) => ({ file, count: list.length }))
    .sort((l, r) => (l.file < r.file ? -1 : l.file > r.file ? 1 : 0))
  const dirs = new Map()
  for (const entry of files) {
    const slash = entry.file.lastIndexOf('/')
    const dir = slash < 0 ? '.' : entry.file.slice(0, slash)
    push(dirs, dir, entry)
  }
  return [...dirs.entries()]
    .map(([dir, entries]) => ({
      dir,
      count: entries.reduce((total, entry) => total + entry.count, 0),
      files: entries,
    }))
    .sort((l, r) => r.count - l.count)
}

/** Top-level symbols of one file, in source order, with their member counts. */
function fileSymbols(repo, file) {
  return (repo.byFile.get(file) ?? [])
    // A method is reported inside its class, not again at the file's top level.
    .filter(a => !a.symbol.includes('.'))
    .map(a => describe(repo, a.id))
}

function search(repo, query, limit) {
  const needle = query.toLowerCase()
  const exact = []
  const partial = []
  for (const a of repo.anchors.values()) {
    const symbol = a.symbol.toLowerCase()
    if (symbol === needle) exact.push(a.id)
    else if (symbol.includes(needle) || a.file.toLowerCase().includes(needle)) partial.push(a.id)
    if (exact.length + partial.length > limit * 6) break
  }
  return [...exact, ...partial].slice(0, limit).map(id => describe(repo, id))
}

/**
 * The smallest anchor whose range contains `line` in `file`.
 *
 * This is how a Read at `foo.py:210` becomes a function rather than a file. The
 * smallest containing range wins, so a line inside a method attributes to the
 * method and not to the class or module that also span it.
 */
function enclosing(repo, file, line) {
  const list = repo.byFile.get(file) ?? []
  let best = null
  for (const a of list) {
    if (a.start === null || a.end === null) continue
    if (a.start > line) break
    if (line > a.end) continue
    if (best === null || (a.end - a.start) < (best.end - best.start)) best = a
  }
  return best === null ? null : describe(repo, best.id)
}

/**
 * Anchors overlapping a line window — a Read with an offset and a length.
 *
 * `to === Infinity` is a read with no limit, which is most reads: the agent
 * opened the whole file. Attributing that to whatever anchor happens to contain
 * line 1 finds nothing at all in the common case (line 1 is imports), which is
 * how a session that read eight files produced an empty graph. A whole-file
 * read touched every anchor in the file, so that is what it reports.
 *
 * A class is skipped when its own methods are in the window: the methods are
 * the specific answer, and listing the class too would double-count the file.
 */
function overlapping(repo, file, from, to) {
  const hits = []
  for (const a of repo.byFile.get(file) ?? []) {
    if (a.start === null || a.end === null) continue
    if (a.start > to) break
    if (a.end < from) continue
    if (!a.symbol.includes('.') && (repo.members.get(a.id) ?? []).length > 0) continue
    hits.push(describe(repo, a.id))
  }
  return hits
}

function sourceOf(repo, id, pad) {
  const a = repo.anchors.get(id)
  if (a === undefined || a.start === null) return null
  const file = path.join(repo.root, a.file)
  let text
  try {
    text = fs.readFileSync(file, 'utf8')
  } catch {
    return null
  }
  const lines = text.split('\n')
  const from = Math.max(1, a.start - pad)
  const to = Math.min(lines.length, a.end + pad)
  return { file: a.file, from, to, start: a.start, end: a.end, lines: lines.slice(from - 1, to) }
}

/**
 * The real edges AMONG a given set of anchors — no new nodes.
 *
 * This is what lets the session's own touches assemble into a graph on their
 * own: the anchors are known (the agent read them), and the only question is
 * which of them the code actually joins. Answering it in one pass beats a
 * neighbour request per anchor, and adding no nodes is the point — a touched
 * set must not silently grow into the whole repository.
 */
function among(repo, ids, bridge) {
  const want = new Set(ids.filter(id => repo.anchors.has(id)))
  const edges = []
  const seen = new Set()
  const add = (e) => {
    const key = `${e.from}\u0000${e.to}\u0000${e.type}`
    if (seen.has(key)) return
    seen.add(key)
    edges.push({ from: e.from, to: e.to, type: e.type })
  }

  for (const id of want) {
    for (const e of repo.out.get(id) ?? []) {
      if (want.has(e.to)) add(e)
    }
  }
  if (bridge !== true) return { edges, bridges: [] }

  // Direct edges alone leave most sessions with none at all: an agent reads a
  // type and the function that uses it, but not the file in between, so both
  // ends of every real relation are rarely both in the touched set. One
  // intermediate hop is admitted — A -> X -> B where A and B were touched —
  // and X comes back marked as a bridge. Nothing further: two hops would pull
  // in the repository.
  const bridges = new Map()
  for (const from of want) {
    for (const first of repo.out.get(from) ?? []) {
      const mid = first.to
      if (want.has(mid)) continue
      for (const second of repo.out.get(mid) ?? []) {
        if (!want.has(second.to) || second.to === from) continue
        if (!bridges.has(mid)) bridges.set(mid, describe(repo, mid))
        add(first)
        add(second)
      }
    }
  }
  // A shared caller is a relation too: two touched anchors both called by one
  // function are related through it, and that caller is often the thing the
  // session was actually working on.
  for (const to of want) {
    for (const first of repo.in.get(to) ?? []) {
      const mid = first.from
      if (want.has(mid)) continue
      for (const second of repo.out.get(mid) ?? []) {
        if (!want.has(second.to) || second.to === to) continue
        if (!bridges.has(mid)) bridges.set(mid, describe(repo, mid))
        add(first)
        add(second)
      }
    }
  }
  return { edges, bridges: [...bridges.values()] }
}

const handlers = {
  stats: (repo) => ({
    root: repo.root,
    anchors: repo.anchors.size,
    files: repo.byFile.size,
    edges: [...repo.out.values()].reduce((total, list) => total + list.length, 0),
    stamp: repo.stamp,
  }),
  outline: repo => ({ dirs: outline(repo) }),
  file: (repo, q) => ({ file: q.file, symbols: fileSymbols(repo, q.file) }),
  anchor: (repo, q) => ({ anchor: describe(repo, q.id) }),
  neighbors: (repo, q) => ({ id: q.id, direction: q.direction, peers: hop(repo, q.id, q.direction) }),
  members: (repo, q) => ({ id: q.id, members: (repo.members.get(q.id) ?? []).map(m => describe(repo, m)) }),
  search: (repo, q) => ({ hits: search(repo, q.q ?? '', Number(q.limit) || 30) }),
  locate: (repo, q) => {
    const from = Number(q.line)
    if (q.to === undefined || q.to === null) {
      return { hit: enclosing(repo, repo === null ? '' : q.file, from), hits: null }
    }
    // -1 is the wire form of "to the end of the file": a read with no limit.
    const to = Number(q.to) < 0 ? Infinity : Number(q.to)
    return { hit: null, hits: overlapping(repo, q.file, from, to) }
  },
  source: (repo, q) => ({ source: sourceOf(repo, q.id, Number(q.pad) || 0) }),
  among: (repo, q) => {
    const ids = typeof q.ids === 'string' ? q.ids.split(',').filter(Boolean) : (q.ids ?? [])
    const result = among(repo, ids, q.bridge === '1' || q.bridge === true)
    return { edges: result.edges, bridges: result.bridges, known: ids.filter(id => repo.anchors.has(id)) }
  },
}

parentPort.on('message', (message) => {
  const { seq, op, root, query } = message
  try {
    const handler = handlers[op]
    if (handler === undefined) throw new Error(`unknown op ${op}`)
    const repo = repoFor(root)
    if (repo === null) {
      // Not an exception: a root with no index is the ordinary state of a fresh
      // checkout, and the page renders "no index here, run cdd" for it.
      parentPort.postMessage({ seq, ok: false, code: 'no-index', error: `${root} has no .codedendrite index` })
      return
    }
    parentPort.postMessage({ seq, ok: true, data: handler(repo, query ?? {}) })
  } catch (error) {
    parentPort.postMessage({ seq, ok: false, code: 'failed', error: String(error && error.message ? error.message : error) })
  }
})
