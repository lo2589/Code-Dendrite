// dsh-cdd-lens — Source, history, search, legend, unresolved.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/panels',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useState = React.useState
    var useEffect = React.useEffect
    var useCallback = React.useCallback
    var useMemo = React.useMemo
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var __view_record = require('dsh-cdd-lens/view/record')
    var dotClass = __view_record.dotClass
    var short = __view_record.short
    var stateOf = __view_record.stateOf
    var positionStateOf = __view_record.positionStateOf
    var partialOf = __view_record.partialOf

    // ---- source ------------------------------------------------------------

    function sourceLineCount(source) {
      if (source === null || source === undefined) return 0
      if (Number.isFinite(source.lineCount)) return source.lineCount
      return Math.max(0, Number(source.end) - Number(source.start) + 1)
    }

    function SourceMissing(props) {
      return h('div', { className: 'cddl-src' }, [
        h('div', { key: 'h', className: 'cddl-srch' }, [
          h('span', { key: 't' }, props.id + ' · 源码范围读不出来'),
          h('button', {
            key: 'x', className: 'cddl-src-close', title: '关闭源码详情',
            onClick: function () { props.engine.blur() },
          }, '×'),
        ]),
      ])
    }

    function Source(props) {
      var id = shared.selected
      if (id === null || id === undefined) return null
      var source = (shared.sourceCache || {})[id]
      var node = shared.graph.nodes[id]
      var record = stateOf(id)
      var anchor = node !== undefined ? node : (record && record.anchor ? record.anchor : null)
      if (source === undefined) {
        return h('div', { className: 'cddl-src' }, h('div', { className: 'cddl-srch' }, '读源码…'))
      }
      if (source === null || source.lines === undefined) return h(SourceMissing, { id: id, engine: props.engine })
      var count = sourceLineCount(source)
      var lines = source.lines.map(function (text, i) {
        var no = source.from + i
        var inside = no >= source.start && no <= source.end
        return h('div', { key: no, className: inside ? 'cddl-hl' : '' }, [
          h('span', { key: 'n', className: 'cddl-ln' }, no),
          h('span', { key: 't', className: 'cddl-code' }, text === '' ? ' ' : text),
        ])
      })
      return h('div', { className: 'cddl-src' }, [
        h('div', { className: 'cddl-srch', key: 'h' }, [
          h('span', { key: 't' }, source.file + ' · ' + (anchor ? anchor.symbol : '') + ' · ' + source.start + '–' + source.end + ' · ' + count + ' 行'),
          h('button', {
            key: 'x', className: 'cddl-src-close', title: '关闭源码详情',
            onClick: function () { props.engine.blur() },
          }, '×'),
        ]),
        h('pre', {
          key: 'p',
          'data-cdd-source-id': source.id || id,
          'data-cdd-source-start': source.start,
          'data-cdd-source-end': source.end,
          'data-cdd-source-lines': count,
        }, lines),
      ])
    }

    /** Every turn that reached this anchor — collapsing a branch never erases it. */
    function History(props) {
      var record = stateOf(shared.selected)
      if (record === undefined || record === null) return null
      return h('div', { className: 'cddl-hist' }, [
        h('h4', { key: 'h' }, '这个 anchor 的经历'),
      ].concat(record.events.map(function (event, i) {
        // 每一条经历就是一个位置，三态：对不上是过期，拿不到 hash 是判不了（未知）。
        var position = positionStateOf(event, shared.selected)
        var expired = position === 'stale'
        var unknown = position === 'unknown'
        var partial = partialOf(event)
        return h('div', {
          key: i,
          className: 'cddl-hrow' + (event.onSurface ? '' : ' cddl-faded') + (expired ? ' cddl-expired' : ''),
          'data-cdd-position-id': event.pid || '',
          'data-cdd-position-stale': position,
        }, [
          h('span', { key: 't', className: 'cddl-t' }, 'T' + event.turn),
          h('span', { key: 'd', className: dotClass({ state: event.working ? 'working' : event.verb === 'edit' ? 'edited' : 'viewed' }) }),
          h('span', { key: 'x' }, event.tool
            + (event.working ? ' · 正在执行' : '')
            + (event.approx ? ' · 行号近似' : '')
            + (event.onSurface ? '' : ' · 已被压缩')),
          expired ? h('span', { key: 's', className: 'cddl-hist-tag' }, '过期') : null,
          unknown ? h('span', { key: 'u', className: 'cddl-hist-tag cddl-hist-part', title: '判不了过期：抓的时候没抓住 hash，或者这个 anchor 现在查不到' }, '未知') : null,
          partial ? h('span', { key: 'p', className: 'cddl-hist-tag cddl-hist-part' }, '部分') : null,
          event.agent ? h('span', { key: 'a', className: 'cddl-agent' }, event.agent) : null,
          event.reason ? h('span', { key: 'r', className: 'cddl-reason' }, event.reason) : null,
        ])
      })))
    }

    // ---- search ------------------------------------------------------------

    function Search(props) {
      var engine = props.engine
      var q = useState('')
      var timer = useRef(null)
      var onChange = function (e) {
        var value = e.target.value
        q[1](value)
        if (timer.current !== null) clearTimeout(timer.current)
        timer.current = setTimeout(function () { engine.search(value.trim()) }, 180)
      }
      return h('div', { className: 'cddl-search' }, [
        h('input', {
          key: 'i', className: 'cddl-q', placeholder: '搜 anchor…',
          value: q[0], onChange: onChange,
          onClick: function (e) { e.stopPropagation() },
        }),
        shared.hits === null || shared.hits === undefined || q[0].trim().length === 0 ? null
          : h('div', { key: 'r', className: 'cddl-hits' }, shared.hits.length === 0
            ? [h('div', { key: 'n', className: 'cddl-empty' }, '没找到')]
            : shared.hits.map(function (anchor) {
              return h('div', {
                key: anchor.id, className: 'cddl-hit',
                onClick: function () { q[1](''); shared.hits = null; engine.focus(anchor) },
              }, [
                h('span', { key: 's', className: 'cddl-sym' }, anchor.symbol),
                h('span', { key: 'f', className: 'cddl-hitfile' }, short(anchor.file)),
              ])
            })),
      ])
    }

    // ---- legend ------------------------------------------------------------

    function Legend() {
      return h('div', { className: 'cddl-legend' }, [
        h('b', { key: 'v' }, [h('i', { key: 'd', className: 'cddl-dot cddl-v' }), '看过']),
        h('b', { key: 'e' }, [h('i', { key: 'd', className: 'cddl-dot cddl-e' }), '改过']),
        h('b', { key: 'w' }, [h('i', { key: 'd', className: 'cddl-dot cddl-w' }), '正在改']),
        h('b', { key: 'f', style: { opacity: .45 } }, '变淡 = 被 compaction 压缩，模型记不清了'),
      ])
    }

    /**
     * Files the agent opened that this project's index cannot own.
     *
     * Shown, never dropped. A session that opened twenty files over an empty
     * graph reads as a broken plugin; naming the file and the reason is the
     * difference between an honest empty graph and a silent one.
     */
    function Unresolved() {
      var list = shared.unresolved
      if (list === undefined || list.length === 0) return null
      var why = {
        'not-indexed': '不在索引里',
        'no-line': '没有行号',
        'scope': '只是搜索范围',
        'no-index': '该工程没索引',
        'outside': '在本工程之外',
        'no-file': '没有路径',
        'error': '解析失败',
      }
      return h('div', { className: 'cddl-unres' }, [
        h('h4', { key: 'h' }, [
          h('span', { key: 't' }, '碰过，但没落到 anchor'),
          h('span', { key: 'n', className: 'cddl-count' }, list.length),
        ]),
      ].concat(list.slice(0, 12).map(function (entry, i) {
        return h('div', { key: i, className: 'cddl-unrow', title: entry.file }, [
          h('span', { key: 't', className: 'cddl-t' }, 'T' + entry.turns.join(',')),
          h('span', { key: 'f', className: 'cddl-sym' }, short(entry.file)),
          h('span', { key: 'w', className: 'cddl-kind' }, why[entry.reason] || entry.reason),
        ])
      })))
    }

    module.exports = { Source, History, Search, Legend, Unresolved }
    return module.exports
  },
})
