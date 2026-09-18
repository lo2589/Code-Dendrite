// dsh-cdd-lens — 会话快照 → 轨迹标记（看过 / 改过 / 第几轮）。
//
// 只给轨迹栏和卡片上的标记用：shared.trace / shared.unresolved / shared.order。
// 图上有哪些节点、哪些边一概不在这里定——折完一份快照就叫 /screen 重算屏幕
// （后端自己读会话日志，见 src/compute）。
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/engine/ingest',
  factory: (require) => {
    var module = { exports: {} }
    var __runtime_api = require('dsh-cdd-lens/runtime/api')
    var ROUTE = __runtime_api.ROUTE
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note
    var fact = __runtime_debug.fact
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var requestViewport = __state_store.requestViewport
    var shared = __state_store.shared
    var __session_position = require('dsh-cdd-lens/session/position')
    var positionId = __session_position.positionId
    var windowLines = __session_position.windowLines
    var coverageOf = __session_position.coverageOf

    /** 每次调用是它那一轮的第几步：t15s3 的那个 3，每轮从 1 开始数。 */
    function stepsOf(snap) {
      var stepOf = {}
      var stepped = {}
      snap.calls.forEach(function (call) {
        stepped[call.turn] = (stepped[call.turn] || 0) + 1
        stepOf[call.key] = stepped[call.turn]
      })
      return stepOf
    }

    function noteUnresolved(unresolved, call, touch, hit, at) {
      var f = hit.file || touch.path
      if (unresolved[f] === undefined) unresolved[f] = { file: f, reason: hit.reason, verb: touch.verb, turns: [], steps: [] }
      if (unresolved[f].turns.indexOf(call.turn) < 0) unresolved[f].turns.push(call.turn)
      var seenAt = unresolved[f].steps.some(function (x) { return x.turn === at.turn && x.step === at.step })
      if (!seenAt) unresolved[f].steps.push(at)
    }

    function noteAnchor(byAnchor, call, anchor, event) {
      var record = byAnchor[anchor.id]
      if (record === undefined) {
        byAnchor[anchor.id] = {
          id: anchor.id, anchor: anchor, firstTurn: call.turn, lastTurn: call.turn,
          firstStep: event.step, lastStep: event.step, events: [event],
        }
        return
      }
      if (call.turn < record.firstTurn || (call.turn === record.firstTurn && event.step < record.firstStep)) {
        record.firstTurn = call.turn
        record.firstStep = event.step
      }
      if (call.turn > record.lastTurn || (call.turn === record.lastTurn && event.step > record.lastStep)) {
        record.lastTurn = call.turn
        record.lastStep = event.step
      }
      record.events.push(event)
    }

    /** 这个 anchor 现在记录在索引里的 hash（拿不到就是空串）。 */
    function currentHash(call, anchor) {
      var hash = typeof anchor.hash === 'string' ? anchor.hash : ''
      if (hash === '') return ''
      // 位置要记的是"抓的那一刻这个 anchor 的代码"。只有这一步发生在 lens 真的在看
      // 这个会话之后，索引里的那份才等于那一刻的代码。回放旧会话时索引描述的是今天
      // 的文件，拿今天的 hash 冒充当时的，这个位置就会假装"没过期"—— 那是假话，
      // 所以这种位置存空串：判不了，不是没过期。
      var since = shared.watchSince
      if (!Number.isFinite(since)) return ''
      var at = call.time
      // 还在跑的调用没有落地时刻，它就是此刻。
      if (!Number.isFinite(at)) return hash
      return at >= since ? hash : ''
    }

    /** 解析结果 → 每个 anchor 一条轨迹记录；落不到 anchor 的文件照实列出，不丢。 */
    function foldTrace(snap, sessionId) {
      var stepOf = stepsOf(snap)
      var byAnchor = {}
      var unresolved = {}
      snap.calls.forEach(function (call) {
        call.touches.forEach(function (touch, i) {
          var hit = shared.resolved[call.key + '#' + i]
          if (hit === undefined) return
          var at = { turn: call.turn, step: stepOf[call.key] || 1, verb: touch.verb }
          if (hit.anchors.length === 0) { noteUnresolved(unresolved, call, touch, hit, at); return }
          // 这个 step 抓下来的那几行原文。轨迹栏展开看的就是它，不是今天的文件 ——
          // 位置记的是"那一刻看到的代码"，现在文件什么样是另一件事（看过期标记）。
          var lines = windowLines(touch)
          hit.anchors.forEach(function (anchor) {
            noteAnchor(byAnchor, call, anchor, {
              turn: call.turn, step: at.step, verb: touch.verb, tool: touch.tool,
              approx: touch.approx === true || hit.approx === true,
              onSurface: call.remembered !== false, working: call.running === true,
              // 位置 id：这次查看的坐标。同一 anchor 被看多次 → 多条位置，各有各的 hash。
              pid: positionId(sessionId, call.turn, at.step, anchor.id),
              // 抓的那一刻这个 anchor 的 hash，之后永不改写。空串 = 没抓住。
              hash: currentHash(call, anchor),
              lines: lines,
              coverage: coverageOf(anchor, touch.from, touch.to),
            })
          })
        })
      })
      Object.keys(byAnchor).forEach(function (id) {
        var record = byAnchor[id]
        record.events.sort(function (l, r) { return l.turn - r.turn || l.step - r.step })
        var working = record.events.some(function (e) { return e.working })
        var edited = record.events.some(function (e) { return e.verb === 'edit' })
        record.state = working ? 'working' : edited ? 'edited' : 'viewed'
        // One surviving verbatim read is enough to say the model still knows it.
        record.remembered = record.events.some(function (e) { return e.onSurface })
        record.approx = record.events.every(function (e) { return e.approx })
      })
      return { byAnchor: byAnchor, unresolved: Object.keys(unresolved).map(function (k) { return unresolved[k] }) }
    }

    /** 每个 anchor 第一次被碰到的先后名次（按调用 seq），也就是 agent 实际走的顺序。 */
    function rankOf(snap) {
      var firstSeq = {}
      snap.calls.forEach(function (call) {
        call.touches.forEach(function (touch, i) {
          var hit = shared.resolved[call.key + '#' + i]
          if (hit === undefined) return
          hit.anchors.forEach(function (anchor) {
            if (firstSeq[anchor.id] === undefined || call.seq < firstSeq[anchor.id]) firstSeq[anchor.id] = call.seq
          })
        })
      })
      var order = {}
      Object.keys(firstSeq).sort(function (l, r) { return firstSeq[l] - firstSeq[r] })
        .forEach(function (id, i) { order[id] = i + 1 })
      return order
    }

    function ingestMethods(ctx, engine, session, params) {
      return {
        /**
         * Fold one conversation-view snapshot into the trajectory marks, then
         * ask /screen for the drawing.
         */
        ingest: function (snap) {
          if (snap === undefined || snap === null) return Promise.resolve()
          // Resolving before the root is known would ask the wrong repository.
          if (shared.root === undefined) {
            return engine.context().then(function () {
              // 问过还是没有仓库：停在这里，不再反复问。
              if (shared.root === undefined) return
              return engine.ingest(snap)
            })
          }
          shared.turn = snap.turn
          // 会话快照在 agent 流式输出时一秒变很多次，但证据（read/edit/write 及其状态）没变时，
          // 屏幕不会变：不重折轨迹、不重算 /screen、不重画。
          var signature = snap.calls
            .filter(function (call) { return call.touches.length > 0 })
            .map(function (call) { return call.key + (call.running ? 'r' : 's') + (call.remembered === false ? 'f' : 'k') + call.touches.length })
            .join('|')
          if (signature === shared.evidenceSignature) return Promise.resolve()
          shared.evidenceSignature = signature
          shared.resolved = shared.resolved || {}
          var pending = []
          snap.calls.forEach(function (call) {
            call.touches.forEach(function (touch, i) {
              var key = call.key + '#' + i
              if (shared.resolved[key] !== undefined) return
              if (touch.scopeOnly === true) {
                shared.resolved[key] = { anchors: [], reason: 'scope', file: touch.path }
                return
              }
              pending.push({ key: key, file: touch.path, from: touch.from, to: touch.to, text: touch.text })
            })
          })

          var after = function () {
            var folded = foldTrace(snap, session())
            shared.trace = folded.byAnchor
            shared.unresolved = folded.unresolved
            shared.order = rankOf(snap)
            var ids = Object.keys(folded.byAnchor)
            fact('trace', ids.length)
            fact('unresolved', shared.unresolved.length)
            note('graph', 'ingest anchors=' + ids.length + ' unresolved=' + shared.unresolved.length)
            if (window.__cddLens !== undefined) {
              var reasons = {}
              shared.unresolved.forEach(function (u) { reasons[u.reason] = (reasons[u.reason] || 0) + 1 })
              window.__cddLens.resolve = {
                calls: snap.calls.length, anchors: ids.length, unresolved: shared.unresolved.length,
                reasons: reasons, root: shared.root,
              }
            }
            if (shared.selected === null && ids.length > 0) {
              var newest = ids.map(function (id) { return folded.byAnchor[id] })
                .sort(function (l, r) { return r.lastTurn - l.lastTurn })[0]
              shared.selected = newest.id
              requestViewport(newest.id, 'fit')
              engine.source(newest.id)
            }
            publish()
            return engine.refresh()
          }

          note('graph', 'ingest calls=' + snap.calls.length + ' pending=' + pending.length
            + ' resolved=' + Object.keys(shared.resolved).length)
          if (window.__cddLens !== undefined) window.__cddLens.pending = pending.length
          if (pending.length === 0) return after()
          return fetch(ROUTE + '/resolve?' + new URLSearchParams(params()).toString(), {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ root: shared.root, touches: pending }),
          }).then(function (res) { return res.json() }).then(function (body) {
            body.results.forEach(function (entry) { shared.resolved[entry.key] = entry })
            return after()
          }).catch(function (error) {
            if (window.__cddLens !== undefined) window.__cddLens.resolveError = String(error && error.message ? error.message : error)
            return after()
          })
        },
      }
    }

    module.exports = { ingestMethods }
    return module.exports
  },
})
