// dsh-cdd-lens — The directory view and the draw trigger.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/outline',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __runtime_api = require('dsh-cdd-lens/runtime/api')
    var ROUTE = __runtime_api.ROUTE
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __view_record = require('dsh-cdd-lens/view/record')
    var dotClass = __view_record.dotClass
    var stateOf = __view_record.stateOf

    // ---- the directory view (the `cdd draw` shape: for finding things) -----

    // How many directory rows go into the page at once. This repository's
    // outline is 4,566 directories over 27,003 files; putting all of them in
    // the DOM is not a long list, it is a frozen tab. A screenful at a time,
    // with the filter applied over the whole set, shows the same index and
    // stays usable however large the repository is.
    var DIR_PAGE = 120

    function Outline(props) {
      var engine = props.engine
      var openDir = useState({})
      var filter = useState('')
      var shown = useState(DIR_PAGE)
      var dirs = shared.outline
      useEffect(function () { if (dirs === undefined) engine.outline() }, [dirs === undefined])
      if (dirs === undefined) return h('div', { className: 'cddl-empty' }, '读目录…')
      // `undefined` was the only empty checked for, and the trace clears this
      // to `undefined` — but a failed read leaves it null, and null.forEach is
      // a blank view with an exception behind it.
      if (dirs === null || typeof dirs.slice !== 'function') {
        return h('div', { className: 'cddl-empty' }, '目录读不出来。')
      }
      var needle = filter[0].trim().toLowerCase()
      var matched = needle === '' ? dirs : dirs.filter(function (entry) {
        return String(entry.dir).toLowerCase().indexOf(needle) >= 0
      })
      var page = matched.slice(0, shown[0])
      var out = []
      out.push(h('input', {
        key: 'filter', className: 'cddl-outline-filter', value: filter[0],
        placeholder: '筛目录（共 ' + dirs.length + ' 个）',
        onChange: function (e) { shown[1](DIR_PAGE); filter[1](e.target.value) },
      }))
      page.forEach(function (entry) {
        var isOpen = openDir[0][entry.dir] === true
        out.push(h('div', {
          key: 'd' + entry.dir, className: 'cddl-dir',
          onClick: function () {
            var next = Object.assign({}, openDir[0])
            next[entry.dir] = !isOpen
            openDir[1](next)
          },
        }, [
          h('span', { key: 't', className: 'cddl-twist' }, isOpen ? '▾' : '▸'),
          h('span', { key: 'n' }, entry.dir === '.' ? '(根目录)' : entry.dir + '/'),
          h('span', { key: 'c', className: 'cddl-count' }, entry.count),
        ]))
        if (!isOpen) return
        entry.files.forEach(function (file) {
          var fileOpen = openDir[0]['f:' + file.file] === true
          out.push(h('div', {
            key: 'f' + file.file, className: 'cddl-fileitem',
            onClick: function () {
              var next = Object.assign({}, openDir[0])
              next['f:' + file.file] = !fileOpen
              openDir[1](next)
              if (!fileOpen) engine.fileSymbols(file.file)
            },
          }, [
            h('span', { key: 't', className: 'cddl-twist' }, fileOpen ? '▾' : '▸'),
            h('span', { key: 'n' }, file.file.split('/').pop()),
            h('span', { key: 'c', className: 'cddl-count' }, file.count),
          ]))
          if (!fileOpen) return
          var symbols = (shared.fileCache || {})[file.file]
          if (symbols === undefined) { out.push(h('div', { key: 'l' + file.file, className: 'cddl-sub' }, '…')); return }
          symbols.forEach(function (anchor) {
            var record = stateOf(anchor.id)
            out.push(h('div', {
              key: 's' + anchor.id, className: 'cddl-symitem',
              title: '点开 → 成为逻辑图的起点',
              onClick: function () { engine.focus(anchor) },
            }, [
              h('span', { key: 'd', className: dotClass(record) }),
              h('span', { key: 'n', className: 'cddl-sym' }, anchor.symbol),
              anchor.members > 0 ? h('span', { key: 'm', className: 'cddl-kind' }, '类 ' + anchor.members) : null,
              h('span', { key: 'l', className: 'cddl-lines' }, anchor.start + '–' + anchor.end),
            ]))
          })
        })
      })
      if (matched.length > page.length) {
        out.push(h('div', {
          key: 'more', className: 'cddl-outline-more',
          onClick: function () { shown[1](shown[0] + DIR_PAGE) },
        }, '还有 ' + (matched.length - page.length) + ' 个目录 · 点这里再看 ' + DIR_PAGE + ' 个'))
      }
      if (matched.length === 0) {
        out.push(h('div', { key: 'none', className: 'cddl-empty' }, '没有目录匹配「' + filter[0] + '」'))
      }
      return h('div', { className: 'cddl-tree' }, out)
    }

    /**
     * `cdd draw`'s own compound browser, served verbatim in a frame.
     *
     * CodeDendrite already generates a finished directory/file/class/function
     * browser with its data inlined. Replacing it with a tree of my own lost a
     * working tool, so it is shown as itself. Same-origin, so it needs no bridge.
     */
    function drawStampAfter(before, body) {
      if (body.ready !== true || !body.stamp || body.stamp === before.stamp) return before
      return { stamp: body.stamp }
    }

    function Draw(props) {
      var engine = props.engine
      // The iframe goes up on the first render. `/draw` always answers with a
      // page: the paged browser shell when it exists, or the server-owned build
      // shell while it is being regenerated. Client-side loading/error cards
      // only hid that real shell and could get stuck in front of it.
      var state = useState({ stamp: 0 })
      var query = new URLSearchParams(engine.params()).toString()
      var src = ROUTE + '/draw?' + query
        + (state[0].stamp ? '&v=' + state[0].stamp : '')
      useEffect(function () {
        var stop = false
        var timer = null
        var ask = function () {
          fetch(ROUTE + '/draw-status?' + query, { cache: 'no-store' })
            .then(function (res) { return res.json() })
            .then(function (body) {
              if (stop) return
              state[1](function (before) { return drawStampAfter(before, body) })
              timer = setTimeout(ask, body.building === true || body.ready !== true ? 1500 : 8000)
            })
            .catch(function () {
              if (stop) return
              // The iframe remains mounted with its last real page. A transient
              // status failure only delays the next stamp check.
              timer = setTimeout(ask, 1500)
            })
        }
        ask()
        return function () { stop = true; if (timer !== null) clearTimeout(timer) }
      }, [query])
      return h('iframe', {
        // Keyed on the stamp: a new drawing is a new frame, not a frame asked
        // nicely to reload.
        key: 'draw' + state[0].stamp,
        className: 'cddl-frame', src: src, title: 'cdd draw',
      })
    }

    module.exports = { Outline, Draw, drawStampAfter }
    return module.exports
  },
})
