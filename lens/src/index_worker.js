// dsh-cdd-lens — index worker.
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
    this.visible = new Set()
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

function virtualAnchor(anchor) {
  return anchor !== undefined && anchor !== null
    && (anchor.isVirtual === true || anchor.kind === 'virtual_block')
}

function addRelation(repo, from, to, type) {
  const edge = { from, to, type }
  push(repo.out, from, edge)
  push(repo.in, to, edge)
}

function addVisibleRelation(repo, seen, from, to, type) {
  if (from === to) return
  if (!repo.visible.has(from) || !repo.visible.has(to)) return
  const key = `${from}\u0000${to}\u0000${type}`
  if (seen.has(key)) return
  seen.add(key)
  addRelation(repo, from, to, type)
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
      isVirtual: a.is_virtual === true || a.symbol_type === 'virtual_block',
      virtualKind: a.virtual_kind ?? null,
      parentAnchor: a.parent_anchor ?? null,
      // The stored record, whole. A DOM node IS an anchor: what it draws, what
      // it expands into and which relations it shows all come from this, so it
      // has to travel with the node instead of being dropped at build time.
      // `hash`, `qualified_name`, `imports`, `callers`, `parent_classes`,
      // `mro`, `own_methods` and `effective_methods` used to stop here, which
      // left every card and every node born from an expand holding a stub.
      record: a,
    }
    repo.anchors.set(id, node)
    if (virtualAnchor(node)) continue
    repo.visible.add(id)
    push(repo.byFile, node.file, node)
    // `Class.method` — the dot is inside the symbol half, after `::`.
    const dot = node.symbol.indexOf('.')
    if (dot > 0) push(repo.members, `${node.file}::${node.symbol.slice(0, dot)}`, id)
  }
  for (const list of repo.byFile.values()) {
    list.sort((l, r) => (l.start ?? 0) - (r.start ?? 0) || (r.end ?? 0) - (l.end ?? 0))
  }

  const rel = JSON.parse(fs.readFileSync(relationsPath, 'utf8'))
  // 计算单元的上下文（新 anchor = 原始记录 + relation 补边）随索引一起建，不再单独解析一遍。
  repo.compute = require('./compute/anchors.js').fromIndex(root, raw, rel.edges ?? [])
  const rawOut = new Map()
  for (const e of rel.edges ?? []) {
    // Edges reaching outside the index (builtins like `print`, third-party
    // calls) are dropped rather than drawn as phantom nodes: the graph shows
    // this repository, and a node with no anchor has no source to open.
    if (!repo.anchors.has(e.from_id) || !repo.anchors.has(e.to_id)) continue
    push(rawOut, e.from_id, { from: e.from_id, to: e.to_id, type: e.edge_type })
  }

  const seen = new Set()
  const walkVirtual = (from, first, type, visited) => {
    if (visited.has(first)) return
    visited.add(first)
    for (const next of rawOut.get(first) ?? []) {
      const target = repo.anchors.get(next.to)
      if (target === undefined) continue
      if (virtualAnchor(target)) {
        walkVirtual(from, next.to, type, visited)
      } else {
        addVisibleRelation(repo, seen, from, next.to, type)
      }
    }
  }

  for (const from of repo.visible) {
    for (const edge of rawOut.get(from) ?? []) {
      const target = repo.anchors.get(edge.to)
      if (target === undefined) continue
      if (virtualAnchor(target)) walkVirtual(from, edge.to, edge.type, new Set())
      else addVisibleRelation(repo, seen, from, edge.to, edge.type)
    }
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

/**
 * 记录里的 `callers` / `callees` 字段——anchors.json 那一半。
 *
 * 它是**裸调用名单**，不是解析好的邻居表：`callees` 里常常写着 `len`、
 * `bounding_box` 这种短名字，要按 import 上下文才解析得到具体 anchor，而记录
 * 本身不带解析结果。所以这个字段只能用来**对账报警**，不能拿它过滤邻居——实测
 * `visual_computer_operate` 上 ↓ 方向有 89 条真边因为记录里只写了裸名字而被滤掉，
 * 那正是"有的没抓到"。
 *
 * 返回 null 表示"这条记录没算过这个方向"，**不是**"这个方向没人"：没算过的字段
 * 序列化成 null（`_ws_handshake_headers` 的 callers 就是 None，而它确实被
 * make_handler 调用）。
 */
function recordPeers(repo, id, direction) {
  const rec = repo.anchors.get(id)?.record
  const list = direction === 'up' ? rec?.callers : rec?.callees
  if (!Array.isArray(list) || list.length === 0) return null
  const found = new Set()
  for (const raw of list) {
    const key = String(raw)
    if (key === id) continue
    if (!repo.anchors.has(key) || !repo.visible.has(key)) continue
    found.add(key)
  }
  return found
}

/**
 * 上下键的邻居：**只认 call**，而且两端都必须是真实 anchor。
 *
 * 两个文件一起用，分工是这样：relations.json 给出**已经解析好的** call 边（谁
 * 调用谁、那个名字在这段上下文里指哪里），anchors.json 把边两端的 id 变成一条
 * 真实记录——记录取得到，这个 peer 才建得出 node。缺前者就没有方向，缺后者就
 * 没有节点。
 *
 * dataflow 不能算进来。它的箭头指的是**数据**往哪走，不是谁调用谁：`return`
 * 边写成 `被调用方 -> 调用方`，于是同一个调用者在 ↑ 里出现一次、又在 ↓ 里出现
 * 一次——实测 `vco/models.py::GridSpec` 的 ↓60 里有 35 个（58%）正是刚按 ↑ 拉
 * 进来那批，按下去自然"没有新东西"。inherit / impact / dispatch 同理。
 *
 * 这里是上下键的**唯一真相**：按钮上的数字、展开出来的名单、画出来的节点都由
 * 它出，所以三者不可能对不上。
 */
function callPeers(repo, id, direction) {
  return relPeers(repo, id, direction, 'call')
}

/** 有数据的关系类型。 */
const RELATIONS = ['call', 'dataflow', 'inherit', 'dispatch', 'impact']

/**
 * 按关系取邻居：**两端都必须是真实 anchor**。
 *
 * relations.json 给出已经解析好的边（谁指向谁、那个名字在这段上下文里指哪里），
 * anchors.json 把两端的 id 变成一条真实记录——记录取得到，这个 peer 才建得出 node。
 * 缺前者就没有方向，缺后者就没有节点。
 *
 * 不再「只认 call」。上下键现在按关系分开：call 一个按钮、inherit 一个按钮，
 * 各自显示各自的数、各自的颜色（见规则文档 §2.3）。同一条边的 from === id 就是
 * 下行、to === id 就是上行，两个方向永远不会共用同一条边。
 *
 * @param relation - 关系类型；省略表示全部关系。
 */
function relPeers(repo, id, direction, relation) {
  const edges = (direction === 'up' ? repo.in : repo.out).get(id) ?? []
  const found = new Set()
  for (const e of edges) {
    if (relation !== undefined && relation !== null && e.type !== relation) continue
    const peer = direction === 'up' ? e.from : e.to
    if (peer === id) continue
    if (!repo.anchors.has(peer) || !repo.visible.has(peer)) continue
    found.add(peer)
  }
  return [...found].sort()
}

/**
 * 一个 anchor 每个关系、每个方向有几个邻居。
 *
 * **这是按钮数字的唯一来源。** 有几个关系挂几个按钮，某个关系是 0 就不挂那个按钮、
 * 不写数字（见规则文档 §2.3.1、§2.3.2）。按钮上的数字、展开出来的名单、画出来的线
 * 都走 relPeers，所以三者不可能对不上。
 */
function peerCounts(repo, id) {
  const counts = {}
  for (const rel of RELATIONS) {
    const up = relPeers(repo, id, 'up', rel).length
    const down = relPeers(repo, id, 'down', rel).length
    if (up > 0 || down > 0) counts[rel] = { up, down }
  }
  return counts
}

/** 两个来源的差集：只做情报，不参与过滤。onlyInEdges 通常是记录写了裸名字。 */
function crossCheck(repo, id, direction, relation) {
  const fromEdges = new Set(relPeers(repo, id, direction, relation))
  const record = recordPeers(repo, id, direction)
  if (record === null) {
    return { edges: fromEdges.size, record: null, agreed: fromEdges.size, onlyInEdges: [], onlyInRecord: [] }
  }
  const onlyInEdges = [...fromEdges].filter(x => !record.has(x))
  const onlyInRecord = [...record].filter(x => !fromEdges.has(x))
  return {
    edges: fromEdges.size,
    record: record.size,
    agreed: fromEdges.size - onlyInEdges.length,
    onlyInEdges,
    onlyInRecord,
  }
}

/**
 * 这条线的类型。
 *
 * 一次展开只走一个关系（call 一个按钮、inherit 一个按钮），所以画出来的线就是
 * 那条边自己的类型。以前这里把两个节点之间的**所有**关系塞进 types，于是一条
 * 下行线身上可能挂着反向的 dataflow，出和入看着像同一条边。
 */
function peerTypes(relation) {
  return [relation || 'call']
}

/** Distinct edges to `id`'s neighbours in one direction, deduped by target. */
function hop(repo, id, direction, relation) {
  const rel = relation || 'call'
  return relPeers(repo, id, direction, rel).map(peer => ({
    id: peer,
    types: peerTypes(rel),
    ...describe(repo, peer),
  }))
}

/**
 * A class's own methods.
 *
 * The record carries `own_methods`, which is what CodeDendrite decided the
 * class owns — including a method whose symbol does not nest under the class.
 * Splitting the symbol on its dot is only the fallback for an anchor that has
 * no record to speak from. Ids that are not in this index cannot become a
 * card, so they are dropped rather than promised.
 */
function memberIds(repo, id) {
  const own = repo.anchors.get(id)?.record?.own_methods
  if (Array.isArray(own) && own.length > 0) {
    const known = own.filter(m => repo.anchors.has(m) && repo.visible.has(m))
    if (known.length > 0) return known
  }
  return repo.members.get(id) ?? []
}

/**
 * The wire shape of one anchor: the whole stored record, plus the counts a
 * collapsed node has to show.
 *
 * The record goes out first so a node carries its anchor — `hash`,
 * `qualified_name`, `imports`, `callers`, `parent_classes`, `mro`,
 * `own_methods`, `effective_methods`, `symbol_type`. The normalized fields
 * follow and win, because they are what the reader is written against.
 */
function describe(repo, id) {
  const a = repo.anchors.get(id)
  if (a === undefined) return { id, missing: true }
  if (!repo.visible.has(id)) return { id, hidden: true }
  return {
    ...(a.record ?? {}),
    id,
    file: a.file,
    symbol: a.symbol,
    start: a.start,
    end: a.end,
    kind: a.kind,
    members: memberIds(repo, id).length,
    // Self-loops are excluded for one reason: hop() skips them, so a recursive
    // function counting itself here made the button promise one neighbour more
    // than expand can ever list. The number on the button IS the expand count.
    // 按钮上的数字就是展开出来的名单长度——两边都走 relPeers，同一次判断，
    // 不可能出现"说 60 只给出 25 个"。
    //   up / down        ：call 方向的计数，老调用方还在读
    //   peerCounts       ：**每个关系每个方向**的计数，按钮按它挂
    //                      有几个关系挂几个，是 0 的不出现在这里
    up: relPeers(repo, id, 'up', 'call').length,
    down: relPeers(repo, id, 'down', 'call').length,
    peerCounts: peerCounts(repo, id),
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

function fileName(file) {
  const slash = file.lastIndexOf('/')
  return slash < 0 ? file : file.slice(slash + 1)
}

function stem(file) {
  const name = fileName(file)
  const dot = name.lastIndexOf('.')
  return dot < 0 ? name : name.slice(0, dot)
}

function words(text) {
  return text.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean)
}

function vendored(file) {
  return /(^|\/)(node_modules|vendor|dist|build|coverage|__pycache__)(\/|$)/.test(file)
}

function langExtensions(needle) {
  const langs = {
    ts: ['.ts', '.tsx'],
    typescript: ['.ts', '.tsx'],
    js: ['.js', '.jsx', '.mjs', '.cjs'],
    javascript: ['.js', '.jsx', '.mjs', '.cjs'],
    py: ['.py'],
    python: ['.py'],
  }
  return langs[needle] || null
}

function searchMode(raw) {
  const needle = raw.trim().toLowerCase()
  if (needle.length === 0) return { kind: 'empty', needle }
  if (needle.startsWith('path:')) return { kind: 'path', needle: needle.slice(5).trim() }
  if (needle.startsWith('lang:')) {
    const lang = needle.slice(5).trim()
    return { kind: 'extension', needle: lang, extensions: langExtensions(lang) || [lang[0] === '.' ? lang : '.' + lang] }
  }
  if (/^\.[a-z0-9]+$/.test(needle)) return { kind: 'extension', needle, extensions: [needle] }
  return { kind: 'normal', needle, extensions: langExtensions(needle) }
}

function scoreSearchAnchor(a, mode) {
  if (mode.kind === 'empty') return null
  const file = a.file.toLowerCase()
  const name = fileName(file)
  const base = stem(file)
  const symbol = a.symbol.toLowerCase()
  const short = mode.needle.length <= 2
  let score = null

  if (mode.kind === 'path') {
    if (mode.needle.length === 0 || !file.includes(mode.needle)) return null
    score = fileName(file).includes(mode.needle) ? 760 : 620
  } else if (mode.kind === 'extension') {
    if (!mode.extensions.some(ext => file.endsWith(ext))) return null
    score = symbol.includes('.') ? 720 : 780
  } else {
    if (mode.extensions !== null && mode.extensions.some(ext => file.endsWith(ext))) score = 820
    if (symbol === mode.needle) score = Math.max(score || 0, 1000)
    if (symbol.split('.').pop() === mode.needle) score = Math.max(score || 0, 950)
    if (base === mode.needle || name === mode.needle) score = Math.max(score || 0, 900)
    if (words(symbol).indexOf(mode.needle) >= 0) score = Math.max(score || 0, 840)
    if (words(file).indexOf(mode.needle) >= 0) score = Math.max(score || 0, 800)
    if (!short && symbol.startsWith(mode.needle)) score = Math.max(score || 0, 740)
    if (!short && name.startsWith(mode.needle)) score = Math.max(score || 0, 700)
    if (!short && symbol.includes(mode.needle)) score = Math.max(score || 0, 560)
    if (!short && file.includes(mode.needle)) score = Math.max(score || 0, 520)
  }

  if (score === null) return null
  if (vendored(file)) score -= 320
  if (symbol.includes('.')) score -= 8
  return score
}

function search(repo, query, limit) {
  const mode = searchMode(query)
  const ranked = []
  for (const a of repo.anchors.values()) {
    if (!repo.visible.has(a.id)) continue
    const score = scoreSearchAnchor(a, mode)
    if (score === null) continue
    ranked.push({ id: a.id, score, file: a.file, symbol: a.symbol })
  }
  ranked.sort((l, r) => r.score - l.score
    || l.file.localeCompare(r.file)
    || l.symbol.localeCompare(r.symbol)
    || l.id.localeCompare(r.id))
  return ranked.slice(0, limit).map(hit => describe(repo, hit.id))
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
  const want = new Set(ids.filter(id => repo.visible.has(id)))
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
    anchors: repo.visible.size,
    files: repo.byFile.size,
    edges: [...repo.out.values()].reduce((total, list) => total + list.length, 0),
    stamp: repo.stamp,
  }),
  outline: repo => ({ dirs: outline(repo) }),
  file: (repo, q) => ({ file: q.file, symbols: fileSymbols(repo, q.file) }),
  anchor: (repo, q) => ({ anchor: describe(repo, q.id) }),
  /**
   * 按关系展开一层：从 `id` 出发，沿 `rel` 关系往 `direction` 走一跳。
   *
   * 一个新接口替掉旧的 `/neighbors`。区别只有一个但很关键：**不再只认 call**。
   * 前端对每个有数据的关系挂一个按钮，点哪个就带哪个 `rel` 过来，所以：
   *   - 按钮上的数字（`counts[rel][direction]`）
   *   - 这次返回的名单（`peers`）
   * 都出自同一个 `relPeers`，同一次判断——说 N 就一定是 N 个节点。
   */
  expand: (repo, q) => {
    const relation = RELATIONS.includes(q.rel) ? q.rel : 'call'
    const direction = q.direction === 'up' ? 'up' : 'down'
    const peers = hop(repo, q.id, direction, relation)
    return {
      id: q.id,
      direction,
      relation,
      from: describe(repo, q.id),
      peers,
      count: peers.length,
      stamp: repo.stamp,
    }
  },
  /**
   * 链式展开：`a → b → c → d` 一路走。
   *
   * 从 `id` 开始沿 `rel` 往 `direction` 走，每一层的新节点继续走，直到没有新节点
   * 或到 `depth`。**一次请求就是一整条链**，前端不用为每一层再发一次——这就是
   * 「一路往下拉能 a→b→c→d」的数据侧。
   *
   * 用 BFS 记 `parent`，所以每个节点只出现一次，回来的边天然构成一条到根的路径，
   * 不会因为图里有菱形而重复建节点。
   */
  walk: (repo, q) => {
    const relation = RELATIONS.includes(q.rel) ? q.rel : 'call'
    const direction = q.direction === 'up' ? 'up' : 'down'
    const depth = Math.max(1, Math.min(8, Number(q.depth) || 4))
    const start = describe(repo, q.id)
    const nodes = new Map([[start.id, start]])
    const edges = []
    let frontier = [start.id]
    for (let level = 0; level < depth && frontier.length > 0; level += 1) {
      const next = []
      for (const current of frontier) {
        for (const peer of hop(repo, current, direction, relation)) {
          edges.push({ from: peer.id, to: current, types: [relation] })
          if (nodes.has(peer.id)) continue
          nodes.set(peer.id, peer)
          next.push(peer.id)
        }
      }
      frontier = next
    }
    return {
      id: q.id,
      direction,
      relation,
      depth,
      nodes: [...nodes.values()],
      edges,
      count: nodes.size,
      stamp: repo.stamp,
    }
  },
  // Re-validation after the index moved under a drawn graph: which of these
  // nodes still exist, and what are their counts now. describe() reports
  // missing:true for anything the rebuilt index no longer holds.
  verify: (repo, q) => {
    const ids = typeof q.ids === 'string' ? q.ids.split(',').filter(Boolean) : (q.ids ?? [])
    return { stamp: repo.stamp, nodes: ids.map(id => describe(repo, id)) }
  },
  members: (repo, q) => ({ id: q.id, members: memberIds(repo, q.id).map(m => describe(repo, m)) }),
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
  // 计算单元（src/compute）：屏幕上有什么只由它算。repo.compute 在 build() 里随索引一起建。
  screen: (repo, q) => ({
    ...require('./compute/screen.js').screenFor(repo.compute, Array.isArray(q.touches) ? q.touches : [], q.state ?? {}),
    stamp: repo.stamp,
  }),
  // 展开：按 id 从新 anchor 表（anchors.json 原始记录 + relation 补边）里拿 anchor，
  // 顺带给出这些节点的按钮数字——和 /screen 走同一个 peers，数字不会对不上。
  anchors: (repo, q) => {
    const { RELATIONS, peers } = require('./compute/anchors.js')
    const ids = Array.isArray(q.ids) ? [...new Set(q.ids.map(String))] : []
    const anchors = {}
    const buttons = {}
    const missing = []
    for (const id of ids) {
      if (!repo.compute.visible.has(id)) { missing.push(id); continue }
      anchors[id] = repo.compute.anchors[id]
      const b = {}
      for (const rel of RELATIONS) {
        const up = peers(repo.compute, id, rel, 'up').length
        const down = peers(repo.compute, id, rel, 'down').length
        if (up > 0) b[rel + 'up'] = up
        if (down > 0) b[rel + 'down'] = down
      }
      buttons[id] = b
    }
    return { anchors, buttons, missing, stamp: repo.stamp }
  },
  among: (repo, q) => {
    const ids = typeof q.ids === 'string' ? q.ids.split(',').filter(Boolean) : (q.ids ?? [])
    const result = among(repo, ids, q.bridge === '1' || q.bridge === true)
    return { edges: result.edges, bridges: result.bridges, known: ids.filter(id => repo.visible.has(id)) }
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
