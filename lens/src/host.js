// dsh-cdd-lens — host half.
//
// Every route here is reached from a click in the page, never from the agent
// loop. Nothing in this file runs during a turn, listens on `agent/pre-step`,
// or holds the chat thread: the heavy work (9.6MB of index) is on a worker, the
// session fold is a pure pass over already-committed events, and reindexing is a
// detached child process. That is the whole reason the panel can be live while
// the model is streaming.
//
// ## /health first, on day one
//
// Four things have to be the same build before any bug report means anything:
// this file, the browser bundle under lib/, the index worker, and the directory
// dsh actually resolved. The previous attempt at this plugin added that
// handshake at its twenty-fourth version, after twenty versions of not knowing
// which copy was on screen. `build.json` is the single stamp; the host reads it
// from disk and greps lib/client.js for it, so a stale bundle cannot pass for a
// fresh one.
'use strict'

const fs = require('node:fs')
const path = require('node:path')
const childProcess = require('node:child_process')
const { IndexStore } = require('./index_store.js')
const { collect, merge } = require('./session_trace.js')

const PACKAGE_ROOT = path.resolve(__dirname, '..')

/**
 * Where the repository this plugin draws lives.
 *
 * This used to be written down as `'..','..'` from the plugin directory, and
 * every time the plugin moved that pointed somewhere outside the repository —
 * which reads back as a bare "cdd not found" with nothing to explain it. Look
 * for the layout once instead of remembering it: the repository is the first
 * ancestor that has the CLI in it.
 */
function findRepoRoot(start) {
  let dir = start
  for (let i = 0; i < 8; i += 1) {
    if (fs.existsSync(path.join(dir, 'src', 'usage', 'cli', 'cdd'))) return dir
    const parent = path.resolve(dir, '..')
    if (parent === dir) break
    dir = parent
  }
  return path.resolve(start, '..')
}

const REPO_ROOT = findRepoRoot(PACKAGE_ROOT)
// Python 包在 src 下（src/analyzer、src/usage…），import 根是它，不是仓库根。
const SRC_ROOT = path.join(REPO_ROOT, 'src')
const ROUTE = '/plugins/cdd-lens'
const STARTED_AT = new Date().toISOString()

function declaredBuild() {
  try {
    const value = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, 'build.json'), 'utf8')).build
    return typeof value === 'string' && value.length > 0 ? value : '<build.json has no build>'
  } catch (error) {
    return `<build.json unreadable: ${error.message}>`
  }
}

/**
 * Whether the browser bundle on disk carries the declared stamp.
 * A plain substring check: the stamp is a string literal in the bundle, and
 * anything cleverer would parse a file just to ask a question about bytes.
 */
function clientCarriesBuild(build) {
  try {
    return fs.readFileSync(path.join(PACKAGE_ROOT, 'lib', 'client.js'), 'utf8').includes(build)
  } catch {
    return false
  }
}

function hasIndex(root) {
  return typeof root === 'string' && fs.existsSync(path.join(root, '.codedendrite', 'anchors.json'))
}

// No walk up the tree. A session's graph is its OWN project's graph: the index
// is looked for at the session workspace and nowhere else. Borrowing an
// ancestor's `.codedendrite` would silently show one project's code map to a
// conversation about a different project, and the page would look perfectly
// healthy while doing it. A workspace with no index gets an offer to build one
// there, not somebody else's.


/**
 * 1-based line where `text`'s first distinctive line appears in a file.
 *
 * Blank and one-token lines (`}`, `else:`) match everywhere and would anchor an
 * edit to whichever function happened to have one first, so a key shorter than
 * this is treated as no evidence at all rather than as a confident wrong answer.
 */
function findText(root, file, text) {
  let key = null
  for (const line of String(text).split('\n')) {
    const trimmed = line.trim()
    if (trimmed.length >= 12) { key = trimmed; break }
  }
  if (key === null) return null
  try {
    const lines = fs.readFileSync(path.join(root, file), 'utf8').split('\n')
    for (let i = 0; i < lines.length; i += 1) if (lines[i].includes(key)) return i + 1
  } catch {
    return null
  }
  return null
}

/**
 * A tool call's path as the index keys it: workspace-relative, forward slashes.
 *
 * Returns null for anything outside the workspace. Sessions read across
 * projects all the time — another checkout, a file on an external drive — and
 * those are honestly not this project's anchors.
 */
function toWorkspacePath(root, file) {
  if (typeof file !== 'string' || file.length === 0) return null
  const absolute = path.isAbsolute(file) ? file : path.join(root, file)
  const rel = path.relative(root, absolute)
  if (rel.length === 0 || rel.startsWith('..') || path.isAbsolute(rel)) return null
  return rel.split(path.sep).join('/')
}

module.exports = {
  name: 'cdd-lens',
  // Declared, not resolved per call. `apply` runs once at mount; with an empty
  // inject it runs BEFORE the web server exists, `ctx.get('webServer')` returns
  // undefined, and an early return leaves the route permanently unregistered —
  // silently. `sessions` is optional and read per request, because the panel
  // must still draw the repository with no session open at all.
  // `sessionQuery` reads the DURABLE log. The in-memory session store only
  // holds what this process happens to have loaded, so a two-day-old
  // conversation folds to zero touches there and the graph comes up empty over
  // a session that read eight files — successfully, silently, wrongly.
  inject: ['webServer', 'sessionQuery'],

  apply(ctx, config = {}) {
    const server = ctx.get('webServer')
    if (server === undefined || typeof server.register !== 'function') return

    const store = new IndexStore()
    const disposers = []
    /** root → the reindex child currently running for it. */
    const reindexing = new Map()
    /** Roots this process already tried to build unprompted — one attempt each. */
    const autoBuilt = new Set()
    /** root → why its last build could not run or did not finish, for the page to show. */
    const failures = new Map()
    /** root → the `cdd draw` child currently regenerating its browser page. */
    const drawing = new Map()
    const escapeHtml = (text) => String(text).replace(/[&<>"]/g, (ch) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]))
    /**
     * A real browser shell for the short interval before the first format-4
     * index exists. The draw is paged, so its chrome never depends on a file
     * page being ready. Showing the chrome immediately also means there is no
     * client- or server-side loading screen to get stuck on.
     *
     * It watches /draw-status silently and swaps itself for the populated shell
     * when that file lands.
     * @param root - the workspace represented by this shell.
     * @returns a complete document.
     */
    const buildingPage = (root) => [
      '<!doctype html><html><head><meta charset="utf-8"><title>cdd draw</title>',
      '<style>',
      '*{box-sizing:border-box}body{margin:0;height:100vh;display:flex;overflow:hidden;',
      'font:13px Consolas,Menlo,monospace;background:#1e1e1e;color:#d4d4d4}',
      '#sidebar{width:210px;min-width:120px;display:flex;flex-direction:column;',
      'border-right:1px solid #3e3e42;background:#252526}',
      '.hdr{padding:7px 10px;font-size:11px;font-weight:bold;color:#bbb;',
      'letter-spacing:.05em;text-transform:uppercase;border-bottom:1px solid #3e3e42}',
      '.filter{margin:5px 7px;padding:3px 6px;background:#3c3c3c;border:1px solid #555;',
      'color:#d4d4d4;font-size:12px;border-radius:2px}',
      '.root{padding:5px 8px;color:#e2c08d;white-space:nowrap;overflow:hidden;',
      'text-overflow:ellipsis}',
      '#graph{flex:1;display:flex;flex-direction:column;min-width:0}',
      '#bar{height:32px;padding:5px 10px;border-bottom:1px solid #3e3e42;',
      'display:flex;align-items:center;gap:6px;background:#2d2d30}',
      '#title{flex:1;color:#9cdcfe;font-size:12px}',
      '.tag{padding:1px 7px;border-radius:2px;font-size:10px}',
      '.toggle{padding:2px 8px;border:1px solid #007acc;background:#264f78;',
      'color:#9cdcfe;font-size:11px;border-radius:2px}',
      '#canvas{flex:1;display:grid;place-items:center;background:#16161c;color:#3a3a3a}',
      '#detail{width:420px;min-width:200px;border-left:1px solid #3e3e42;',
      'background:#1c1c1c}.empty{padding:28px 14px;color:#3a3a3a;text-align:center}',
      '</style></head><body>',
      '<aside id="sidebar"><div class="hdr">Files</div>',
      '<input class="filter" placeholder="Filter files…" disabled>',
      '<div class="root" title="' + escapeHtml(root) + '">▸ ' +
        escapeHtml(path.basename(root) || root) + '</div></aside>',
      '<main id="graph"><div id="bar"><div id="title">Select a file</div>',
      '<span class="toggle">external</span>',
      '<span class="tag" style="background:#1e1535;color:#c586c0">class</span>',
      '<span class="tag" style="background:#1a4a2a;color:#4ec9b0">method</span>',
      '<span class="tag" style="background:#1a3060;color:#9cdcfe">function</span>',
      '<span class="tag" style="background:#1a2030;color:#3a5a7a">ext</span>',
      '</div><div id="canvas">← select a file</div></main>',
      '<aside id="detail"><div class="hdr">Detail</div>',
      '<div class="empty">Click a node<br>in the graph</div></aside>',
      '<script>',
      'const q=new URLSearchParams(location.search);q.delete("page");',
      'const tick=()=>fetch("draw-status?"+q.toString(),{cache:"no-store"})',
      '.then(r=>r.json()).then(b=>{if(b.ready===true){location.reload();return}',
      'setTimeout(tick,1500)}).catch(()=>setTimeout(tick,3000));tick();',
      '</script></body></html>',
    ].join('')

    // Kept in step with DRAW_FORMAT in visualize/anchor_browser.py.
    const DRAW_FORMAT = 4
    /**
     * Which page format a generated drawing is in, read off its first bytes.
     *
     * @param file - the shell or one page.
     * @returns the format number, or 0 when the file is absent or unstamped
     *   (every drawing generated before the shell/page split is unstamped).
     */
    const drawFormat = (file) => {
      let head = ''
      try {
        const fd = fs.openSync(file, 'r')
        const buffer = Buffer.alloc(64)
        const read = fs.readSync(fd, buffer, 0, 64, 0)
        fs.closeSync(fd)
        head = buffer.slice(0, read).toString('utf8')
      } catch { return 0 }
      const found = /^<!--cdd-draw-format:([0-9]{1,3})-->/.exec(head)
      return found === null ? 0 : Number(found[1])
    }

    const register = (suffix, handler) => {
      disposers.push(server.register({
        kind: 'exact',
        path: ROUTE + suffix,
        handler: (req, res) => {
          Promise.resolve()
            .then(() => handler(req, res, query(req.url)))
            .catch((error) => {
              // A failed query must answer with its reason. A hanging request is
              // a spinner the page can never clear and no log ever explains.
              json(res, 500, { error: String(error && error.message ? error.message : error), code: error?.code ?? 'failed' })
            })
        },
      }))
    }

    const query = raw => Object.fromEntries(new URL(String(raw || '/'), 'http://dsh.local').searchParams.entries())

    const json = (res, status, body) => {
      res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' })
      res.end(JSON.stringify(body))
    }

    /**
     * One session's complete log and current surface, read from persistence.
     *
     * Cached by id and by the log's length, so repeated polls do not re-read a
     * whole session off disk while the page is open.
     */
    const logCache = new Map()
    const readLog = async (id) => {
      if (typeof id !== 'string' || id.length === 0) return null
      const query = ctx.get('sessionQuery')
      if (query === undefined || typeof query.readSession !== 'function') return null
      const cached = logCache.get(id)
      const now = Date.now()
      if (cached !== undefined && now - cached.at < 1500) return cached.value
      try {
        const snapshot = await query.readSession(id)
        let surface = []
        try {
          const face = await query.readSurface(id)
          surface = (face.events ?? []).map(event => event.seq)
        } catch { /* no surface read means nothing fades, not that nothing happened */ }
        const value = { events: snapshot.events ?? [], surface, header: snapshot.session ?? {} }
        logCache.set(id, { at: now, value })
        return value
      } catch {
        return null
      }
    }

    /**
     * Which repository a request is about: the session's own workspace, full stop.
     *
     * An explicit `root` wins (that is the page addressing a specific project).
     * Otherwise it is `session.header.cwd` exactly as recorded — no ancestor
     * search, so a conversation about one project can never be shown another
     * project's code map.
     */
    const rootOf = async (q) => {
      if (typeof q.root === 'string' && q.root.length > 0) return path.resolve(q.root)
      const cwd = (await readLog(q.session))?.header?.cwd
      if (typeof cwd === 'string' && cwd.length > 0) return path.resolve(cwd)
      if (typeof config.root === 'string' && config.root.length > 0) return path.resolve(config.root)
      return process.cwd()
    }

    const ask = async (op, q, extra = {}) => store.ask(op, await rootOf(q), { ...q, ...extra })

    // ---- version handshake ------------------------------------------------

    register('/health', (_req, res) => {
      const build = declaredBuild()
      json(res, 200, {
        plugin: 'dsh-cdd-lens',
        entry: 'cdd-lens',
        packageRoot: PACKAGE_ROOT,
        build,
        clientBundleMatchesBuild: clientCarriesBuild(build),
        startedAt: STARTED_AT,
      })
    })

    // ---- repository ------------------------------------------------------

    /**
     * What the page opens with: which root, whether it is indexed, how big.
     *
     * An unindexed workspace starts building itself right here — nobody types a
     * command for this. `autoBuilt` guards it to one attempt per root per
     * process: a repository that genuinely cannot be indexed must not turn every
     * poll into another spawned build.
     */
    register('/context', async (_req, res, q) => {
      const root = await rootOf(q)
      const indexed = hasIndex(root)
      if (!indexed && !reindexing.has(root) && !autoBuilt.has(root)) {
        autoBuilt.add(root)
        startReindex(root)
      }
      const body = { root, indexed, reindexing: reindexing.has(root), autoBuilding: !indexed }
      if (indexed) {
        try {
          body.stats = await store.ask('stats', root, {})
        } catch (error) {
          body.error = String(error.message)
        }
      }
      json(res, 200, body)
    })

    register('/outline', async (_req, res, q) => json(res, 200, await ask('outline', q)))
    register('/file', async (_req, res, q) => json(res, 200, await ask('file', q)))
    register('/anchor', async (_req, res, q) => json(res, 200, await ask('anchor', q)))
    // One request for the whole local picture: the seeds, everything within
    // `hops` of them in both directions, grouped into the trees they form.
    // Asking hop by hop is what left the client holding a pile of anchors with
    // no idea which layer any of them belonged to.
    register('/chain', async (_req, res, q) => json(res, 200, await ask('chain', q)))
    register('/members', async (_req, res, q) => json(res, 200, await ask('members', q)))
    register('/search', async (_req, res, q) => json(res, 200, await ask('search', q)))
    register('/source', async (_req, res, q) => json(res, 200, await ask('source', q)))
    register('/among', async (_req, res, q) => json(res, 200, await ask('among', q)))

    register('/neighbors', async (_req, res, q) => {
      const direction = q.dir === 'up' ? 'up' : 'down'
      json(res, 200, await ask('neighbors', q, { direction }))
    })

    // Re-validation takes the whole drawn graph, so the id list rides in a POST
    // body — a query string of three hundred anchor ids is a URL some proxy
    // will silently cut in half.
    register('/verify', async (req, res, q) => {
      if (req.method === 'POST') {
        const body = await readJson(req)
        const ids = Array.isArray(body.ids) ? body.ids.slice(0, 2000) : []
        json(res, 200, await ask('verify', q, { ids }))
        return
      }
      json(res, 200, await ask('verify', q))
    })

    // ---- resolving what the client folded ---------------------------------

    /** Read a JSON request body, with a hard cap so a bad request cannot grow unbounded. */
    const readJson = (req, limit = 4 * 1024 * 1024) => new Promise((resolve, reject) => {
      let size = 0
      const chunks = []
      req.on('data', (chunk) => {
        size += chunk.length
        if (size > limit) { reject(new Error('request body too large')); req.destroy(); return }
        chunks.push(chunk)
      })
      req.on('end', () => {
        try {
          resolve(chunks.length === 0 ? {} : JSON.parse(Buffer.concat(chunks).toString('utf8')))
        } catch (error) { reject(error) }
      })
      req.on('error', reject)
    })

    /**
     * Turn a batch of file touches into anchors.
     *
     * The CLIENT folds the session — it already holds every tool call, running
     * or settled, live and paged, through the same conversation-view machinery
     * the Trajectory tab runs on. Re-reading the log here would be a second,
     * slower, staler copy of a thing the page already has. What the page cannot
     * do is look inside the repository, so that is all this does.
     *
     * A touch with `text` and no line is an edit hunk: `edit`/`write` results
     * carry the applied text but no line numbers, so the line is recovered by
     * finding that text in the file as it stands now. Approximate on purpose,
     * and reported as such.
     */
    register('/resolve', async (req, res, q) => {
      if (req.method !== 'POST') { json(res, 405, { error: 'POST only' }); return }
      const body = await readJson(req)
      const root = typeof body.root === 'string' && body.root.length > 0 ? path.resolve(body.root) : await rootOf(q)
      const touches = Array.isArray(body.touches) ? body.touches.slice(0, 500) : []
      const results = []
      for (const touch of touches) {
        const entry = { key: touch.key, file: touch.file, anchors: [], reason: null }
        if (typeof touch.file !== 'string' || touch.file.length === 0) {
          entry.reason = 'no-file'
          results.push(entry)
          continue
        }
        // The page sends the path the tool call carried, which is absolute; the
        // index is keyed by workspace-relative, forward-slashed paths. Passing
        // the absolute one through matches nothing and every anchor comes back
        // "not indexed" — a wrong answer that looks like an honest one.
        const relative = toWorkspacePath(root, touch.file)
        if (relative === null) {
          // Outside this project. Named as such rather than folded in with
          // "not indexed": reading another repository's file is a different
          // fact, and the panel should be able to say which.
          entry.reason = 'outside'
          results.push(entry)
          continue
        }
        entry.file = relative
        let from = Number.isInteger(touch.from) ? touch.from : null
        let approx = false
        if (from === null && typeof touch.text === 'string' && touch.text.length > 0) {
          from = findText(root, entry.file, touch.text)
          approx = true
        }
        if (from === null) {
          entry.reason = 'no-line'
          results.push(entry)
          continue
        }
        try {
          // `to: -1` means the read had no limit — the whole file was opened.
          const hit = await store.ask('locate', root, {
            file: entry.file,
            line: from,
            ...(touch.to === null || touch.to === undefined
              ? {}
              : (Number.isInteger(touch.to) && touch.to !== from ? { to: touch.to } : {})),
            ...(touch.to === -1 ? { to: -1 } : {}),
          })
          const anchors = hit.hits ?? (hit.hit === null ? [] : [hit.hit])
          if (anchors.length === 0) entry.reason = 'not-indexed'
          entry.anchors = anchors
          entry.approx = approx
        } catch (error) {
          entry.reason = error.code === 'no-index' ? 'no-index' : 'error'
        }
        results.push(entry)
      }
      json(res, 200, { root, results })
    })

    // ---- the session's marks on the graph ---------------------------------

    /**
     * Anchors this session touched, with the turn each was first opened on and
     * whether the model still holds the verbatim evidence.
     */
    register('/trace', async (_req, res, q) => {
      const root = await rootOf(q)
      const log = await readLog(q.session)
      if (log === null) {
        json(res, 200, { root, turn: 0, records: [], reason: 'no-session' })
        return
      }
      const { turn, touches, outside } = collect(log.events, log.surface, root)
      const resolved = []
      /** Touched inside the workspace but owning no anchor, keyed by file. */
      const unresolved = new Map()
      const note = (touch, reason) => {
        const current = unresolved.get(touch.file)
        if (current === undefined) {
          unresolved.set(touch.file, { file: touch.file, reason, verb: touch.verb, turns: [touch.turn] })
        } else if (!current.turns.includes(touch.turn)) {
          current.turns.push(touch.turn)
        }
      }
      for (const touch of touches) {
        if (touch.scopeOnly === true) { note(touch, 'scope'); continue }
        if (touch.from === null) { note(touch, 'no-line'); continue }
        try {
          const hit = await store.ask('locate', root, {
            file: touch.file,
            line: touch.from,
            ...(touch.to === null || touch.to === touch.from ? {} : { to: touch.to }),
          })
          const anchors = hit.hits ?? (hit.hit === null ? [] : [hit.hit])
          if (anchors.length === 0) { note(touch, 'not-indexed'); continue }
          for (const anchor of anchors) resolved.push({ ...touch, id: anchor.id, anchor })
        } catch {
          // One unresolvable touch must not lose the rest of the trace.
          note(touch, 'error')
        }
      }
      json(res, 200, {
        root,
        turn,
        records: merge(resolved),
        // Reported, not dropped: an empty graph must be able to say WHY.
        unresolved: [...unresolved.values()],
        outside,
      })
    })

    // ---- cdd draw --------------------------------------------------------

    /**
     * Serve `cdd draw`'s own compound browser for this root.
     *
     * The directory/file/class/function browser CodeDendrite already generates
     * is a real, finished viewer. Replacing it with a plain tree of my own lost
     * a working tool and gained nothing, so it is served verbatim here and shown
     * in a frame. It is self-contained HTML with its data inlined, and it is
     * same-origin, so nothing about it needs a bridge.
     *
     * It is regenerated when the index is newer than the page, so it never shows
     * a picture of a repository that has since changed.
     */
    register('/draw', async (_req, res, q) => {
      const root = await rootOf(q)
      touchDraw(root)
      const shell = path.join(root, '.codedendrite', 'anchor_browser.html')
      const anchors = path.join(root, '.codedendrite', 'anchors.json')
      // One page per file now: the shell holds the tree, each page holds one
      // file, its source and the files one hop away. `page` picks which.
      // A page id is derived from the file's path, not from its position in a
      // sorted list — position made every id depend on which other files
      // existed. Hex, fixed width, and stable for the life of the file.
      const wanted = typeof q.page === 'string' && /^[0-9a-f]{16}$/.test(q.page) ? q.page : null
      const page = wanted === null ? shell
        : path.join(root, '.codedendrite', 'anchor_browser_pages', wanted + '.html')

      // Opening a page is the only moment anyone needs it to be true, and a
      // page is made of one file plus the files one hop away. So that is the
      // work: ask whether any of those moved, and if none did, serve what is
      // already there. Whether they moved is answered by content hash, in the
      // one place that writes the pages — hashing in JavaScript too would be
      // two implementations of "has this changed" waiting to disagree.
      if (wanted !== null) {
        const verdict = await refreshPage(root, wanted)
        // `created` is a file the last full pass had never seen: its page is
        // made here, on the open, rather than deferred to one. `removed` is a
        // file that has left the index, and there is nothing left to draw.
        if (verdict.state === 'removed') {
          json(res, 410, { error: 'file no longer indexed', page: wanted, root })
          return
        }
        if (verdict.state === 'current' || verdict.state === 'rebuilt' || verdict.state === 'created') {
          if (fs.existsSync(page)) {
            res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' })
            fs.createReadStream(page).pipe(res)
            return
          }
        }
        // Nothing left that one page can fix — no drawing at all yet, or the
        // generator would not run. That is the full pass's job.
        const started = startDraw(root)
        json(res, started === 'missing' ? 503 : 202,
          started === 'missing' ? { error: 'cdd not found', root }
            : { building: true, root, page: wanted, state: verdict.state })
        return
      }

      // The shell is the file tree, so what dates it is files appearing and
      // disappearing, not their contents. Two questions, and only one of them
      // is about time: "is the data current?" is the mtime test, "is this even
      // the format this route serves?" is the stamp. A timestamp cannot answer
      // the second — a single-page drawing generated before paging existed is
      // newer than the index it came from, so the mtime test called it fresh
      // for a month while the route piped 296MB into a browser tab.
      const format = drawFormat(page)
      const current = format === DRAW_FORMAT
      let recent = false
      try {
        recent = fs.existsSync(shell) && fs.statSync(shell).mtimeMs >= fs.statSync(anchors).mtimeMs
      } catch { recent = false }
      if (!recent || !current) startDraw(root)
      if (!current) {
        // A page, always — never JSON, and never the old unbounded single page.
        // This route feeds an iframe: 202 with a body of `{"building":true}`
        // put that JSON on screen where the drawing should be, which is worse
        // than the freeze it replaced. Something renderable goes out now and
        // the real drawing arrives behind it.
        res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' })
        res.end(buildingPage(root))
        return
      }
      if (!fs.existsSync(page)) {
        json(res, 404, { error: 'no such page', page: wanted, root })
        return
      }
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' })
      fs.createReadStream(page).pipe(res)
    })

    /**
     * One file's source, read off disk for the drawing to show.
     *
     * The pages used to carry it inlined, which was three quarters of their
     * weight and a snapshot besides — stale as soon as the file was edited, and
     * present for one file per page, so every other anchor answered "source not
     * available". Reading it here costs nothing to store, is never out of date,
     * and makes that answer impossible.
     */
    register('/draw-source', async (_req, res, q) => {
      const root = await rootOf(q)
      const asked = typeof q.file === 'string' ? q.file : ''
      if (asked === '') { json(res, 400, { error: 'no file' }); return }
      // Contained by construction: resolve, then require the result to still be
      // under the workspace. A path is a request from a page, not a permission.
      const full = path.resolve(root, asked)
      const inside = full === root || full.startsWith(root.endsWith(path.sep) ? root : root + path.sep)
      if (!inside) { json(res, 403, { error: 'outside workspace', file: asked }); return }
      let text = null
      try { text = fs.readFileSync(full, 'utf8') } catch (error) {
        json(res, 404, { error: String(error.message), file: asked })
        return
      }
      res.writeHead(200, { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' })
      res.end(text)
    })

    // Carries a stamp so the view can tell a rebuilt drawing from the one it is
    // already showing. Without it the old page stayed on screen for ever: the
    // rebuild finished and nothing asked again.
    register('/draw-status', async (_req, res, q) => {
      const root = await rootOf(q)
      touchDraw(root)
      const shell = path.join(root, '.codedendrite', 'anchor_browser.html')
      const anchors = path.join(root, '.codedendrite', 'anchors.json')
      let stamp = 0
      let indexed = 0
      try { stamp = Math.round(fs.statSync(shell).mtimeMs) } catch { stamp = 0 }
      try { indexed = Math.round(fs.statSync(anchors).mtimeMs) } catch { indexed = 0 }
      const format = drawFormat(shell)
      const current = format === DRAW_FORMAT
      const recent = stamp > 0 && indexed > 0 && stamp >= indexed
      if (!current || !recent) startDraw(root)
      json(res, 200, {
        // `ready` means servable, not "a file exists". It used to mean the
        // latter, so a 296MB drawing in a format this route no longer serves
        // reported ready:true and the view rendered an iframe straight into a
        // refusal. And this is the only thing that polls, so it is the only
        // thing that can start the work: reporting without triggering left the
        // rebuild waiting for a request that would not come until it finished.
        root,
        ready: current && recent,
        building: drawing.has(root) || !(current && recent),
        stamp, indexed, stale: stamp > 0 && indexed > stamp,
        format: format, expectedFormat: DRAW_FORMAT,
      })
    })

    // ---- reindex, without anyone typing a command -------------------------

    /**
     * Run CodeDendrite's update for a root, out of process.
     *
     * `cdd update` builds on a first run and is incremental afterwards, so the
     * same call serves both "this workspace has never been indexed" and "an edit
     * just settled". It is never invoked from inside a turn: the child is
     * detached from the request that started it, and the previous index keeps
     * answering every query until the new one lands.
     *
     * @returns null when it could not be started, else the running record.
     */
    /**
     * Absolute path of the `cdd` entry point, or null when it is not on disk.
     *
     * Two levels up, not three. The plugin used to live at
     * `tools/CodeDendrite/lens`, so the repository root was three hops away;
     * the bucket refactor moved it to `view/lens`, and the old `../../../`
     * silently resolved to `<parent-of-repo>/skills/...` — a path that does
     * not exist, which reads back as "cdd not found" with nothing to explain
     * why.
     */
    const cddBin = () => {
      const candidate = typeof config.cddBin === 'string' && config.cddBin.length > 0
        ? config.cddBin
        : path.join(REPO_ROOT, 'src', 'usage', 'cli', 'cdd')
      return fs.existsSync(candidate) ? candidate : null
    }
    const pythonBin = () => (typeof config.pythonBin === 'string' && config.pythonBin.length > 0
      ? config.pythonBin
      : 'python3')

    // The Python entry points are bucket modules now — `build_file_index.py`
    // opens with `from view.visualize.anchor_browser.dom_sidebar import ...` —
    // so they only import when the repository root is on PYTHONPATH. The
    // children run with `cwd` set to the workspace being drawn, which puts that
    // workspace first on sys.path and never the repository. Without this every
    // spawn dies with "No module named 'view'", which `refreshPage` reports as
    // `spawn-failed` and `startReindex` as an exit code — neither of which
    // points at the path.
    const pythonEnv = () => ({
      ...process.env,
      PYTHONPATH: [SRC_ROOT, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
    })

    // Which workspaces this plugin has actually served a drawing for, and when
    // anyone last asked. A page-at-a-time refresh keeps what you open true; the
    // whole drawing still has to catch up with files that appeared or vanished,
    // and that is a job for a moment when nobody is waiting.
    const drawSeen = new Map()   // root -> { touched, fullAt }
    const IDLE_QUIET = 120_000   // nothing asked for this long counts as idle
    const IDLE_EVERY = 1_800_000 // and a full pass at most this often
    const touchDraw = (root) => {
      const seen = drawSeen.get(root) || { touched: 0, fullAt: 0 }
      seen.touched = Date.now()
      drawSeen.set(root, seen)
    }
    const idleSweep = setInterval(() => {
      const now = Date.now()
      for (const [root, seen] of drawSeen) {
        if (drawing.has(root) || reindexing.has(root)) continue
        if (now - seen.touched < IDLE_QUIET) continue
        if (now - seen.fullAt < IDLE_EVERY) continue
        seen.fullAt = now
        startDraw(root)
      }
    }, 60_000)
    idleSweep.unref?.()

    // The generator, reached directly rather than through `cdd`: the page-level
    // refresh is a flag on it, and `cdd` lives outside this repository in a
    // wheel that has to be rebuilt to gain one.
    //
    // `anchor_browser.py` was split into a package by the bucket refactor; the
    // argparse entry (the one carrying `--page`) is `build_file_index.py`. The
    // old filename does not exist any more, and a missing GENERATOR makes
    // `refreshPage` answer `no-manifest` — an answer that looks like a fact
    // about the page rather than a broken path.
    const GENERATOR = path.resolve(
      REPO_ROOT, 'src', 'view', 'browser', 'build_file_index.py',
    )

    /**
     * Bring one page up to date, if anything it draws has moved.
     *
     * Cheap when nothing changed, which is the common case: the generator reads
     * that page's manifest, hashes the handful of files named in it and stops.
     * It only loads the index when it is actually going to rewrite something.
     * @param root - the workspace the drawing belongs to.
     * @param pageId - the page the browser asked for.
     * @returns the generator's verdict; `state` is one of current, rebuilt,
     *   no-manifest, gone, renumbered, or spawn-failed.
     */
    const refreshPage = (root, pageId) => new Promise((resolve) => {
      if (!fs.existsSync(GENERATOR)) { resolve({ state: 'no-manifest' }); return }
      const child = childProcess.spawn(pythonBin(), [GENERATOR, root, '--page', String(pageId)], {
        cwd: root, env: pythonEnv(), stdio: ['ignore', 'pipe', 'ignore'],
      })
      let out = ''
      child.stdout.on('data', (chunk) => { out += chunk })
      child.on('error', () => resolve({ state: 'spawn-failed' }))
      child.on('close', () => {
        // The generator prints its own progress before the verdict, so the
        // verdict is the last line that parses as JSON.
        for (const line of out.trim().split('\n').reverse()) {
          try { resolve(JSON.parse(line)); return } catch { /* not the verdict */ }
        }
        resolve({ state: 'spawn-failed' })
      })
    })

    /** Regenerate `cdd draw`'s browser page for a root, out of process. */
    const startDraw = (root) => {
      if (drawing.has(root)) return 'running'
      const cdd = cddBin()
      if (cdd === null) return 'missing'
      // No --no-refresh. It was passed because "reindexing is this plugin's own
      // job, on its own schedule" — but that schedule only ever fires for a root
      // with NO index at all, so a root with a stale one was frozen for ever:
      // the drawing was rebuilt from month-old anchors and looked identical.
      // `cdd draw` updates the index itself, incrementally, and that is what
      // makes what comes back actually new. --no-open must still never launch a
      // browser on the machine running the harness.
      const child = childProcess.spawn(pythonBin(), [cdd, 'draw', root, '--no-open'], {
        cwd: root, env: pythonEnv(), stdio: 'ignore',
      })
      drawing.set(root, child)
      child.on('exit', () => { drawing.delete(root) })
      child.on('error', () => { drawing.delete(root) })
      return 'started'
    }

    const startReindex = (root) => {
      if (reindexing.has(root)) return reindexing.get(root)
      const cdd = cddBin()
      if (cdd === null) {
        failures.set(root, 'cdd not found')
        return null
      }
      const child = childProcess.spawn(pythonBin(), [cdd, 'update', root], {
        cwd: root, env: pythonEnv(), stdio: ['ignore', 'pipe', 'pipe'], detached: false,
      })
      let tail = ''
      const keep = chunk => { tail = (tail + chunk).slice(-4000) }
      child.stdout.on('data', keep)
      child.stderr.on('data', keep)
      const record = { child, startedAt: Date.now(), tail: () => tail, code: null }
      reindexing.set(root, record)
      child.on('error', (error) => { failures.set(root, String(error.message)); reindexing.delete(root) })
      child.on('exit', (code) => {
        record.code = code
        if (code !== 0) failures.set(root, `cdd update exited ${code}: ${tail.slice(-300)}`)
        else failures.delete(root)
        // Kept briefly after exit so a polling page reads the outcome rather
        // than seeing the job vanish and having to guess whether it worked.
        setTimeout(() => { if (reindexing.get(root) === record) reindexing.delete(root) }, 10_000).unref?.()
      })
      return record
    }

    register('/reindex', async (_req, res, q) => {
      const root = await rootOf(q)
      // An explicit request retries a root that auto-building already gave up on.
      autoBuilt.add(root)
      failures.delete(root)
      const record = startReindex(root)
      json(res, 200, record === null
        ? { root, started: false, error: failures.get(root) }
        : { root, started: true })
    })

    register('/reindex-status', async (_req, res, q) => {
      const root = await rootOf(q)
      const record = reindexing.get(root)
      const error = failures.get(root)
      json(res, 200, record === undefined
        ? { root, running: false, indexed: hasIndex(root), ...(error === undefined ? {} : { error }) }
        : {
          root, running: record.code === null, code: record.code, indexed: hasIndex(root),
          ms: Date.now() - record.startedAt, tail: record.tail().slice(-400),
          ...(error === undefined ? {} : { error }),
        })
    })

    ctx.effect(() => () => {
      for (const dispose of disposers) if (typeof dispose === 'function') dispose()
      for (const record of reindexing.values()) record.child.kill()
      clearInterval(idleSweep)
      for (const child of drawing.values()) child.kill()
      store.close()
    }, 'cddLens.routes')
  },
}
