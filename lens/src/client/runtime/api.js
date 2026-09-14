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
    var BUILD = '__CDD_BUILD__'
    var ROUTE = '/plugins/cdd-lens'
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note

    // ---- wire -------------------------------------------------------------

    function api(path, params) {
      var url = ROUTE + path + '?' + new URLSearchParams(params || {}).toString()
      note('req', path + ' ' + (new URLSearchParams(params || {})).toString())
      return fetch(url, { cache: 'no-store' }).then(function (res) {
        if (!res.ok) {
          note('error', path + ' -> HTTP ' + res.status)
          return res.json().catch(function () { return {} }).then(function (body) {
            throw new Error(body.error || ('HTTP ' + res.status))
          })
        }
        return res.json().then(function (body) {
          note('res', path + ' -> 200 ' + summarize(path, body))
          return body
        })
      })
    }

    /** 一行摘要：这次返回了什么，数量对不对。 */
    function summarize(path, body) {
      if (body === null || body === undefined) return '(空)'
      if (path === '/expand') return 'count=' + body.count + ' peers=' + ((body.peers || []).length)
      if (path === '/walk') return 'nodes=' + ((body.nodes || []).length) + ' edges=' + ((body.edges || []).length)
      if (path === '/resolve') return 'results=' + ((body.results || []).length)
      if (path === '/context') return 'anchors=' + ((body.stats || {}).anchors)
      if (Array.isArray(body.hits)) return 'hits=' + body.hits.length
      var keys = Object.keys(body)
      return keys.slice(0, 4).join(',')
    }

    /** Same wrapper with a JSON body, for payloads too long for a query string. */
    function apiPost(path, params, payload) {
      var url = ROUTE + path + '?' + new URLSearchParams(params || {}).toString()
      note('req', 'POST ' + path + ' ids=' + ((payload && payload.ids) ? payload.ids.length : 0))
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
