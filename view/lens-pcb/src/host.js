// dsh-cdd-lens-pcb — host half.
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
const ROUTE = '/plugins/cdd-lens-pcb'
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
  name: 'cdd-lens-pcb',
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
        plugin: 'dsh-cdd-lens-pcb',
        entry: 'cdd-lens-pcb',
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
    register('/members', async (_req, res, q) => json(res, 200, await ask('members', q)))
    register('/search', async (_req, res, q) => json(res, 200, await ask('search', q)))
    register('/source', async (_req, res, q) => json(res, 200, await ask('source', q)))
    register('/among', async (_req, res, q) => json(res, 200, await ask('among', q)))

    register('/neighbors', async (_req, res, q) => {
      const direction = q.dir === 'up' ? 'up' : 'down'
      json(res, 200, await ask('neighbors', q, { direction }))
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
      const page = path.join(root, '.codedendrite', 'anchor_browser.html')
      const anchors = path.join(root, '.codedendrite', 'anchors.json')
      let fresh = false
      try {
        fresh = fs.existsSync(page) && fs.statSync(page).mtimeMs >= fs.statSync(anchors).mtimeMs
      } catch { fresh = false }
      if (!fresh) {
        const started = startDraw(root)
        if (started === 'missing') {
          json(res, 503, { error: 'cdd not found', root })
          return
        }
        if (!fs.existsSync(page)) {
          // Still building and nothing to show yet: say so rather than serving
          // a blank frame the page cannot tell apart from a broken one.
          json(res, 202, { building: true, root })
          return
        }
      }
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' })
      fs.createReadStream(page).pipe(res)
    })

    register('/draw-status', async (_req, res, q) => {
      const root = await rootOf(q)
      const page = path.join(root, '.codedendrite', 'anchor_browser.html')
      json(res, 200, { root, ready: fs.existsSync(page), building: drawing.has(root) })
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
    /** Absolute path of the `cdd` entry point, or null when it is not on disk. */
    const cddBin = () => {
      const candidate = typeof config.cddBin === 'string' && config.cddBin.length > 0
        ? config.cddBin
        : path.resolve(PACKAGE_ROOT, '..', '..', '..', 'skills', 'codedendrite', 'cdd')
      return fs.existsSync(candidate) ? candidate : null
    }
    const pythonBin = () => (typeof config.pythonBin === 'string' && config.pythonBin.length > 0
      ? config.pythonBin
      : 'python3')

    /** Regenerate `cdd draw`'s browser page for a root, out of process. */
    const startDraw = (root) => {
      if (drawing.has(root)) return 'running'
      const cdd = cddBin()
      if (cdd === null) return 'missing'
      // --no-refresh: reindexing is this plugin's own job and is already
      // happening on its own schedule; --no-open must never launch a browser on
      // the machine running the harness.
      const child = childProcess.spawn(pythonBin(), [cdd, 'draw', root, '--no-refresh', '--no-open'], {
        cwd: root, stdio: 'ignore',
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
        cwd: root, stdio: ['ignore', 'pipe', 'pipe'], detached: false,
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
      for (const child of drawing.values()) child.kill()
      store.close()
    }, 'cddLensPcb.routes')
  },
}
