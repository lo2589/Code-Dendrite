// dsh-cdd-lens — Folding a session transcript into anchor touches.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/session/trajectory',
  factory: (require) => {
    var module = { exports: {} }
    var __session_position = require('dsh-cdd-lens/session/position')
    var readWindow = __session_position.readWindow
    var windowLines = __session_position.windowLines

    // ---- folding the session, off the Trajectory target --------------------
    //
    // Not a target of our own. A conversation view target only receives nodes
    // that some registered NODE definition contributes to it — the assembler
    // builds per target from `contextsByTarget` — so registering a builder
    // alone gets a live, correctly driven stream of exactly nothing. That is
    // what the first attempt did, and it looked like a working plugin with an
    // empty graph.
    //
    // `trajectory` already has that whole definition set: every tool card,
    // every running call, compaction markers, and a seq to turn index, assembled
    // once and paged by the shell. Reading it is both less code and the only
    // version that cannot disagree with the Trajectory tab beside us.

    var TARGET = 'trajectory'

    /** Tool name to what the agent was doing to the code. */
    var VERBS = {
      read: 'read', read_image: 'read',
      edit: 'edit', write: 'edit', str_replace_editor: 'edit',
      grep: 'search', glob: 'search',
    }

    function parseArgs(raw) {
      if (typeof raw !== 'string') return {}
      try {
        var value = JSON.parse(raw)
        return value !== null && typeof value === 'object' ? value : {}
      } catch (e) { return {} }
    }

    /**
     * Pull the file touches out of one tool card.
     *
     * A running call — seen, no result yet — is the agent working right now, and
     * it is the only source for the red node.
     */
    function touchesOf(block) {
      var settled = block.kind === 'tool-result'
      var name = settled ? (block.call === null || block.call === undefined ? null : block.call.name) : block.name
      var verb = name === null || name === undefined ? undefined : VERBS[name]
      var out = []
      if (verb === undefined) return out
      if (settled && (block.isError === true || block.error !== undefined)) return out

      var argsRaw = settled ? (block.call === null || block.call === undefined ? '' : block.call.argsRaw) : block.argsRaw
      var args = parseArgs(argsRaw)
      var meta = settled ? block.meta : undefined
      var running = !settled

      if (verb === 'read') {
        var file = (meta && meta.path) || args.file_path
        if (typeof file !== 'string') return out
        var window = readWindow(meta, args)
        // The window's own text rides along: it is the only copy of the code as
        // it stood at this step, and the trajectory row shows that copy rather
        // than today's file.
        out.push({
          path: file, from: window.from, to: window.to,
          lines: windowLines(meta),
          text: null, verb: verb, tool: name, running: running, approx: false,
        })
        return out
      }

      if (verb === 'edit') {
        var diffs = meta && Array.isArray(meta.diffs) ? meta.diffs : []
        if (diffs.length === 0) {
          if (typeof args.file_path === 'string') {
            out.push({
              path: args.file_path, from: null, to: null,
              text: args.new_string || args.content || null,
              verb: verb, tool: name, running: running, approx: true,
            })
          }
          return out
        }
        diffs.forEach(function (diff) {
          var p = diff.path || args.file_path
          if (typeof p !== 'string') return
          // A diff hunk carries no line numbers; the applied text is the only
          // handle, and the host finds it in the file as it stands now.
          out.push({
            path: p, from: null, to: null, text: diff.newText || diff.oldText || null,
            verb: verb, tool: name, running: running, approx: true,
          })
        })
        return out
      }

      // A grep scopes a directory; it is not evidence that any particular
      // function was read, so it contributes a file scope and no anchor.
      var scope = args.path || args.file_path
      if (typeof scope === 'string') {
        out.push({
          path: scope, from: null, to: null, text: null,
          verb: verb, tool: name, running: running, approx: true, scopeOnly: true,
        })
      }
      return out
    }

    /** One tool card and every code-dispatch child under it. */
    function walkCalls(block, sink) {
      sink.push(block)
      var kids = block.subCalls || []
      for (var i = 0; i < kids.length; i++) walkCalls(kids[i], sink)
    }

    /**
     * Fold a Trajectory snapshot into the calls the graph paints with.
     *
     * `eventLocations` already places each seq in its turn, so the turn number
     * on a node is read, never inferred. Everything at or before the newest
     * landed compaction is no longer verbatim on the model's surface: that is
     * the fade, taken from the marker the conversation itself renders.
     */
    function foldTrajectory(snap) {
      if (snap === undefined || snap === null) return { calls: [], turn: 0, compactedThrough: -1 }
      var nodes = snap.eventNodes || []
      // Turn table built from the nodes that carry one (assistant, user, …).
      // `eventLocations` also holds it, but only for seqs the location index
      // matched; a tool result whose own seq is absent there silently reads as
      // turn 0, and every badge on the graph then says T0.
      var bounds = []
      nodes.forEach(function (node) {
        if (typeof node.turn === 'number' && typeof node.seq === 'number') {
          bounds.push({ seq: node.seq, turn: node.turn })
        }
      })
      var locations = snap.eventLocations
      if (locations !== undefined && typeof locations.forEach === 'function') {
        locations.forEach(function (at, seq) {
          if (at !== null && at !== undefined && (at.kind === 'turn' || at.kind === 'step')) {
            bounds.push({ seq: seq, turn: at.turn.turn })
          }
        })
      }
      bounds.sort(function (l, r) { return l.seq - r.seq })
      var turnOf = function (seq) {
        var turn = 0
        for (var i = 0; i < bounds.length; i++) {
          if (bounds[i].seq <= seq) turn = bounds[i].turn
          else break
        }
        return turn
      }

      var cut = -1
      var maxTurn = 0
      var calls = []
      var push = function (block, seq, running) {
        var touches = touchesOf(block)
        if (touches.length === 0) return
        var turn = turnOf(seq)
        if (turn > maxTurn) maxTurn = turn
        // `time` 是这一步落地的时刻（epoch ms）。位置记 hash 时要拿它判断这一步是
        // 不是 lens 正在看的时候发生的：回放一份旧会话，那些 step 早于我们开始看，
        // 那时候的代码我们没见过，hash 也就无从抓起。
        calls.push({ key: block.callId, seq: seq, turn: turn, touches: touches, running: running, time: block.time })
      }

      nodes.forEach(function (node) {
        if (node.kind === 'compaction') { if (node.seq > cut) cut = node.seq; return }
        if (node.kind !== 'tool-result') return
        var blocks = []
        walkCalls(node, blocks)
        blocks.forEach(function (block) { push(block, block.seq === undefined ? node.seq : block.seq, false) })
      })
      ;(snap.runningCalls || []).forEach(function (block) {
        var blocks = []
        walkCalls(block, blocks)
        blocks.forEach(function (b) { push(b, Number.MAX_SAFE_INTEGER, true) })
      })

      calls.sort(function (l, r) { return l.seq - r.seq })
      calls.forEach(function (call) { call.remembered = call.seq > cut })
      if (snap.partial !== null && snap.partial !== undefined && snap.partial.turn > maxTurn) maxTurn = snap.partial.turn
      return { calls: calls, turn: maxTurn, compactedThrough: cut }
    }

    module.exports = { TARGET, VERBS, parseArgs, touchesOf, walkCalls, foldTrajectory }
    return module.exports
  },
})
