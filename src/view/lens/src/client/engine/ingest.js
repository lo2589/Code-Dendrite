// dsh-cdd-lens — Engine method that turns a session snapshot into anchor state.
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
    var api = __runtime_api.api
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var addEdge = __graph_model.addEdge
    var addNode = __graph_model.addNode
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var requestViewport = __state_store.requestViewport
    var shared = __state_store.shared

    /**
     * Taking one session snapshot and painting it onto the graph.
     *
     * @param ctx - the client context the views were mounted with.
     * @param engine - the engine being assembled; methods call each other
     *   through it, so it is passed in rather than closed over.
     * @param session - the current session id, or null.
     * @param params - query parameters for one request.
     * @returns the methods this file contributes.
     */
    function ingestMethods(ctx, engine, session, params) {
      return {
        /**
         * Fold one conversation-view snapshot into the graph.
         *
         * The snapshot arrives from the shell, not from a poll: the same source
         * the Trajectory tab runs on, so it is live during streaming, correct
         * after a cold reload, and cannot disagree with the chat beside it.
         *
         * Only the file to anchor step needs the host, and only for calls not
         * seen before. The page cannot look inside the repository, and that is
         * the whole of what it asks for.
         */
        ingest: function (snap) {
          if (snap === undefined || snap === null) return Promise.resolve()
          // Resolving before the root is known would ask the wrong repository.
          if (shared.root === undefined) return engine.context().then(function () { return engine.ingest(snap) })
          shared.turn = snap.turn
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
            var byAnchor = {}
            var unresolved = {}
            // Which step of its turn a call is. `seq` is global and means nothing
            // to a reader; "the third tool call of turn 15" is what someone
            // actually says out loud, so the badge carries t15s3 and the numbering
            // restarts with every turn.
            var stepOf = {}
            var stepped = {}
            snap.calls.forEach(function (call) {
              stepped[call.turn] = (stepped[call.turn] || 0) + 1
              stepOf[call.key] = stepped[call.turn]
            })
            snap.calls.forEach(function (call) {
              call.touches.forEach(function (touch, i) {
                var hit = shared.resolved[call.key + '#' + i]
                if (hit === undefined) return
                if (hit.anchors.length === 0) {
                  // Kept, not dropped. A session that opened twenty files and
                  // shows an empty panel reads as a broken plugin; naming the
                  // file and the reason is the difference between an honest
                  // empty graph and a silent one.
                  var f = hit.file || touch.path
                  if (unresolved[f] === undefined) {
                    unresolved[f] = {
                      file: f, reason: hit.reason, verb: touch.verb, turns: [], steps: [],
                    }
                  }
                  if (unresolved[f].turns.indexOf(call.turn) < 0) unresolved[f].turns.push(call.turn)
                  // Where in the session it happened, same as a resolved touch.
                  // A file that could not be pinned to an anchor still happened
                  // at a moment, and leaving it out of the order would make the
                  // rail quietly skip part of what the agent did.
                  var at = { turn: call.turn, step: stepOf[call.key] || 1, verb: touch.verb }
                  var seenAt = unresolved[f].steps.some(function (x) {
                    return x.turn === at.turn && x.step === at.step
                  })
                  if (!seenAt) unresolved[f].steps.push(at)
                  return
                }
                hit.anchors.forEach(function (anchor) {
                  var record = byAnchor[anchor.id]
                  var event = {
                    turn: call.turn, step: stepOf[call.key] || 1,
                    verb: touch.verb, tool: touch.tool,
                    approx: touch.approx === true || hit.approx === true,
                    onSurface: call.remembered !== false, working: call.running === true,
                  }
                  if (record === undefined) {
                    byAnchor[anchor.id] = {
                      id: anchor.id, anchor: anchor,
                      firstTurn: call.turn, lastTurn: call.turn,
                      firstStep: event.step, lastStep: event.step, events: [event],
                    }
                  } else {
                    if (call.turn < record.firstTurn
                        || (call.turn === record.firstTurn && event.step < record.firstStep)) {
                      record.firstTurn = call.turn
                      record.firstStep = event.step
                    }
                    if (call.turn > record.lastTurn
                        || (call.turn === record.lastTurn && event.step > record.lastStep)) {
                      record.lastTurn = call.turn
                      record.lastStep = event.step
                    }
                    record.events.push(event)
                  }
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
            shared.trace = byAnchor
            shared.unresolved = Object.keys(unresolved).map(function (k) { return unresolved[k] })
            // Rank by the seq of the first call that reached each anchor: the
            // order the agent actually walked, which is what the graph is for.
            var firstSeq = {}
            snap.calls.forEach(function (call) {
              call.touches.forEach(function (touch, i) {
                var hit = shared.resolved[call.key + '#' + i]
                if (hit === undefined) return
                hit.anchors.forEach(function (anchor) {
                  if (firstSeq[anchor.id] === undefined || call.seq < firstSeq[anchor.id]) {
                    firstSeq[anchor.id] = call.seq
                  }
                })
              })
            })
            var ranked = Object.keys(firstSeq).sort(function (l, r) { return firstSeq[l] - firstSeq[r] })
            shared.order = {}
            ranked.forEach(function (id, i) { shared.order[id] = i + 1 })
            if (window.__cddLens !== undefined) {
              var reasons = {}
              shared.unresolved.forEach(function (u) { reasons[u.reason] = (reasons[u.reason] || 0) + 1 })
              window.__cddLens.resolve = {
                calls: snap.calls.length,
                anchors: Object.keys(byAnchor).length,
                unresolved: shared.unresolved.length,
                reasons: reasons,
                root: shared.root,
              }
            }

            var ids = Object.keys(byAnchor)
            if (ids.length === 0) { publish(); return }
            var fresh = []
            ids.forEach(function (id) {
              if (shared.graph.nodes[id] === undefined) {
                addNode(shared.graph, byAnchor[id].anchor)
                shared.graph.nodes[id].island = true
                fresh.push(id)
              }
              shared.graph.nodes[id].session = true
            })
            if (shared.graph.rootId === null) {
              var newest = ids.map(function (id) { return byAnchor[id] })
                .sort(function (l, r) { return r.lastTurn - l.lastTurn })[0]
              shared.graph.rootId = newest.id
              shared.graph.nodes[newest.id].island = false
              if (shared.selected === null) {
                shared.selected = newest.id
                requestViewport(newest.id, 'fit')
                engine.source(newest.id)
              }
            }
            publish()
            if (fresh.length === 0) return grow()
            // Only edges the code actually has, between anchors already on
            // screen. Nothing new is pulled in, and two anchors touched in
            // sequence with no edge between them stay apart: that gap is the
            // finding, not a rendering bug to paper over.
            // `bridge=1` because direct edges alone are almost always none: an
            // agent reads a type and a function that uses it, but not the file
            // between them, so both ends of a real relation are rarely both in
            // the touched set. One intermediate hop is admitted and comes back
            // marked, so the connection is visible and it is still obvious which
            // nodes the agent actually opened.
            return api('/among', params({
              ids: Object.keys(shared.graph.nodes).join(','), bridge: '1',
            })).then(function (link) {
              (link.bridges || []).forEach(function (anchor) {
                if (shared.graph.nodes[anchor.id] === undefined) {
                  addNode(shared.graph, anchor)
                  shared.graph.nodes[anchor.id].bridge = true
                }
              })
              link.edges.forEach(function (e) {
                // Mark the EDGE, never the node's expanded flag. Setting
                // `node.down = true` here told the ↓ button that the callees
                // were already on screen when they had never been fetched, so a
                // press ran the collapse branch, hid nothing, and looked dead.
                var edge = addEdge(shared.graph, e.from, e.to, [e.type])
                if (edge !== undefined) edge.always = true
                if (shared.graph.nodes[e.from] !== undefined) {
                  shared.graph.nodes[e.from].island = false
                }
                if (shared.graph.nodes[e.to] !== undefined) {
                  shared.graph.nodes[e.to].island = false
                }
              })
              publish()
              return grow()
            })
          }

          // What the picture is about is what was changed. The edits are the
          // seeds; `chain` pushes each of them out and back and reports the
          // trees they land in, so a node arrives already knowing its layer
          // instead of the view having to invent one from file names.
          var grow = function () {
            var edits = Object.keys(shared.trace || {}).filter(function (id) {
              var record = shared.trace[id]
              return record.state === 'edited' || record.state === 'working'
            })
            // Nothing was edited yet — a session that has only read so far still
            // deserves a picture, so the reads stand in as seeds.
            if (edits.length === 0) edits = Object.keys(shared.trace || {})
            return engine.chain(edits, 1)
          }

          if (window.__cddLens !== undefined) window.__cddLens.pending = pending.length
          if (pending.length === 0) { after(); return Promise.resolve() }
          return fetch(ROUTE + '/resolve?' + new URLSearchParams(params()).toString(), {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ root: shared.root, touches: pending }),
          }).then(function (res) { return res.json() }).then(function (body) {
            body.results.forEach(function (entry) { shared.resolved[entry.key] = entry })
            after()
          }).catch(function (error) {
            if (window.__cddLens !== undefined) window.__cddLens.resolveError = String(error && error.message ? error.message : error)
            after()
          })
        },
      }
    }

    module.exports = { ingestMethods }
    return module.exports
  },
})
