// dsh-cdd-lens — Build stamp, plugin route, and the one fetch wrapper.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/runtime/api',
  factory: (require) => {
    var module = { exports: {} }

    // Inlined from build.json. The host greps this file for the stamp it read
    // from disk, so a drift shows up in /health as clientBundleMatchesBuild:false
    // rather than as mysterious behaviour.
    var BUILD = 'V1_20_COMPACT_TOPOLOGY_GRAPH_015'
    var ROUTE = '/plugins/cdd-lens'

    // ---- wire -------------------------------------------------------------

    function api(path, params) {
      var url = ROUTE + path + '?' + new URLSearchParams(params || {}).toString()
      return fetch(url, { cache: 'no-store' }).then(function (res) {
        if (!res.ok) return res.json().catch(function () { return {} }).then(function (body) {
          throw new Error(body.error || ('HTTP ' + res.status))
        })
        return res.json()
      })
    }

    /** Same wrapper with a JSON body, for payloads too long for a query string. */
    function apiPost(path, params, payload) {
      var url = ROUTE + path + '?' + new URLSearchParams(params || {}).toString()
      return fetch(url, {
        method: 'POST', cache: 'no-store',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload || {}),
      }).then(function (res) {
        if (!res.ok) return res.json().catch(function () { return {} }).then(function (body) {
          throw new Error(body.error || ('HTTP ' + res.status))
        })
        return res.json()
      })
    }

    module.exports = { BUILD, ROUTE, api, apiPost }
    return module.exports
  },
})
