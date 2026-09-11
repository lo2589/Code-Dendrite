// dsh-cdd-lens — The engine both views drive.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/engine/engine',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __engine_fetch = require('dsh-cdd-lens/engine/fetch')
    var fetchMethods = __engine_fetch.fetchMethods
    var __engine_explore = require('dsh-cdd-lens/engine/explore')
    var exploreMethods = __engine_explore.exploreMethods
    var __engine_selection = require('dsh-cdd-lens/engine/selection')
    var selectionMethods = __engine_selection.selectionMethods
    var __engine_ingest = require('dsh-cdd-lens/engine/ingest')
    var ingestMethods = __engine_ingest.ingestMethods
    var __engine_gather = require('dsh-cdd-lens/engine/gather')
    var gatherMethods = __engine_gather.gatherMethods

    function currentSession(ctx) {
      try {
        var sessions = ctx.get('sessions')
        if (sessions === undefined || sessions.list === undefined) return undefined
        var snap = sessions.list.getSnapshot()
        return snap === undefined ? undefined : snap.current
      } catch (e) {
        return undefined
      }
    }

    /**
     * Assemble one engine for a view.
     *
     * The parts are installed onto the same object, so a method reaching
     * `engine.source` finds the one this call built and not another view's.
     * @param ctx - the client context the view was mounted with.
     * @returns the engine both views drive.
     */
    function makeEngine(ctx) {
      var session = function () { return currentSession(ctx) }
      var params = function (extra) {
        var base = {}
        var id = session()
        if (id !== undefined && id !== null) base.session = String(id)
        if (shared.root !== undefined) base.root = shared.root
        return Object.assign(base, extra || {})
      }
      var engine = {}
      Object.assign(engine, fetchMethods(ctx, engine, session, params))
      Object.assign(engine, exploreMethods(ctx, engine, session, params))
      Object.assign(engine, selectionMethods(ctx, engine, session, params))
      Object.assign(engine, ingestMethods(ctx, engine, session, params))
      Object.assign(engine, gatherMethods(ctx, engine, session, params))
      // Also on the engine, not only handed to the method factories. `Draw`
      // builds its own URL and asks for these, and finding `engine.params`
      // undefined threw on every render of that tab — which is why `cdd draw`
      // had never once opened.
      engine.params = params
      engine.session = session
      return engine
    }

    module.exports = { currentSession, makeEngine }
    return module.exports
  },
})
