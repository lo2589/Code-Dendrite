// dsh-cdd-lens — Persistent trajectory sidebar beside Chat.
//
// The graph explains code relationships. This rail explains the session in
// time, and deliberately owns its own rendering state: compaction may fade a
// graph node, but it must never erase or pale a historical trajectory entry.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/stream',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement
    var useEffect = React.useEffect
    var useMemo = React.useMemo
    var useRef = React.useRef
    var useState = React.useState
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared
    var useShared = __state_store.useShared
    var __view_panels = require('dsh-cdd-lens/view/panels')
    var Source = __view_panels.Source
    var History = __view_panels.History
    var __engine_engine = require('dsh-cdd-lens/engine/engine')
    var makeEngine = __engine_engine.makeEngine
    var __shell_chatSeat = require('dsh-cdd-lens/shell/chatSeat')
    var openDockBesideChat = __shell_chatSeat.openDockBesideChat

    var WIDTH_KEY = 'cdd-lens.trajectory-width.v1'
    var EXPANDED_KEY = 'cdd-lens.trajectory-expanded.v1'
    var COLLAPSED_KEY = 'cdd-lens.trajectory-collapsed.v1'

    function stronger(left, right) {
      if (right.working === true) return right
      if (left.working === true) return left
      if (right.verb === 'edit' || right.verb === 'write') return right
      return left
    }

    /** One persistent row per anchor/file per tool step, earliest first. */
    function stepsOf() {
      var trace = shared.trace || {}
      var rows = {}
      Object.keys(trace).forEach(function (id) {
        ;(trace[id].events || []).forEach(function (event) {
          var step = event.step || 1
          var key = event.turn + ':' + step + ':' + id
          var row = {
            key: key, id: id, turn: event.turn, step: step,
            verb: event.verb, tool: event.tool, working: event.working === true,
            agent: event.agent, reason: event.reason,
          }
          rows[key] = rows[key] === undefined ? row : stronger(rows[key], row)
        })
      })
      ;(shared.unresolved || []).forEach(function (entry) {
        ;(entry.steps || []).forEach(function (at) {
          var key = at.turn + ':' + at.step + ':file:' + entry.file
          rows[key] = {
            key: key, id: null, file: entry.file, reason: entry.reason,
            turn: at.turn, step: at.step, verb: at.verb || entry.verb,
            working: false,
          }
        })
      })
      return Object.keys(rows).map(function (key) { return rows[key] }).sort(function (l, r) {
        return l.turn - r.turn || l.step - r.step
          || String(l.id || l.file).localeCompare(String(r.id || r.file))
      })
    }

    /** Turn -> step -> rows, preserving chronological order. */
    function groupRows(rows) {
      var turns = []
      var byTurn = {}
      rows.forEach(function (row) {
        var turn = byTurn[row.turn]
        if (turn === undefined) {
          turn = { turn: row.turn, steps: [], byStep: {} }
          byTurn[row.turn] = turn
          turns.push(turn)
        }
        var step = turn.byStep[row.step]
        if (step === undefined) {
          step = { step: row.step, rows: [] }
          turn.byStep[row.step] = step
          turn.steps.push(step)
        }
        step.rows.push(row)
      })
      turns.forEach(function (turn) { delete turn.byStep })
      return turns
    }

    function verbOf(row) {
      if (row.working === true) return '正在处理'
      if (row.verb === 'edit' || row.verb === 'write') return '已修改'
      if (row.verb === 'search') return '已搜索'
      return '已查看'
    }

    function stateClass(row) {
      if (row.working === true) return ' cddl-trace-working'
      if (row.verb === 'edit' || row.verb === 'write') return ' cddl-trace-edited'
      return ' cddl-trace-viewed'
    }

    function loadWidth() {
      try {
        var value = Number(window.localStorage.getItem(WIDTH_KEY))
        if (isFinite(value) && value >= 280 && value <= 520) return value
      } catch (e) { /* browser persistence is optional */ }
      return 360
    }

    function loadExpanded() {
      try {
        var value = JSON.parse(window.localStorage.getItem(EXPANDED_KEY) || '[]')
        if (Array.isArray(value)) {
          var out = {}
          value.forEach(function (key) { if (typeof key === 'string') out[key] = true })
          return out
        }
      } catch (e) { /* malformed old preference: begin folded */ }
      return {}
    }

    function loadCollapsed() {
      try {
        var stored = window.localStorage.getItem(COLLAPSED_KEY)
        if (stored === '1') return true
        if (stored === '0') return false
      } catch (e) { /* browser persistence is optional */ }
      return window.matchMedia && window.matchMedia('(max-width:720px)').matches
    }

    function saveExpanded(value) {
      try {
        window.localStorage.setItem(EXPANDED_KEY, JSON.stringify(Object.keys(value).filter(function (key) { return value[key] })))
      } catch (e) { /* browser persistence is optional */ }
    }

    function chatScroller() {
      var list = document.querySelector('[data-chat-flow]')
      if (list === null) return null
      return list.closest('[data-conversation-scroll]') || list.parentElement
    }

    /** Chat's current reading Turn, using the same 20%/96px line as ChatView. */
    function turnAtReadingLine(scroller) {
      if (scroller === null) return null
      var rows = scroller.querySelectorAll('[data-chat-turn]:not([hidden])')
      if (rows.length === 0) return null
      if (scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight <= 25) {
        return Number(rows[rows.length - 1].dataset.chatTurn)
      }
      var box = scroller.getBoundingClientRect()
      var line = box.top + Math.min(96, scroller.clientHeight * .2)
      var found = null
      if (typeof document.elementsFromPoint === 'function' && box.width > 0) {
        var hits = document.elementsFromPoint(box.left + box.width / 2, line)
        for (var i = 0; i < hits.length; i++) {
          var owner = hits[i].closest ? hits[i].closest('[data-chat-turn]') : null
          if (owner !== null && scroller.contains(owner)) {
            var exact = Number(owner.dataset.chatTurn)
            if (Number.isSafeInteger(exact)) return exact
          }
        }
      }
      for (var j = 0; j < rows.length; j++) {
        if (rows[j].getBoundingClientRect().top > line) break
        var turn = Number(rows[j].dataset.chatTurn)
        if (Number.isSafeInteger(turn)) found = turn
      }
      return found === null ? Number(rows[0].dataset.chatTurn) : found
    }

    function directScrollToTurn(turn) {
      var rows = document.querySelectorAll('[data-chat-turn]:not([hidden])')
      for (var i = 0; i < rows.length; i++) {
        if (Number(rows[i].dataset.chatTurn) !== Number(turn)) continue
        var scroller = rows[i].closest('[data-conversation-scroll]') || chatScroller()
        if (scroller === null) return false
        var outer = scroller.getBoundingClientRect()
        var target = rows[i].getBoundingClientRect()
        scroller.scrollTop += target.top - outer.top - Math.min(96, scroller.clientHeight * .2)
        return true
      }
      return false
    }

    /** Reuse Chat's native pager, then verify and enforce the visual landing. */
    function jumpToChatTurn(turn) {
      var labels = [
        '跳转到第 ' + turn + ' 轮', '加载并跳转到第 ' + turn + ' 轮',
        'Jump to turn ' + turn, 'Load and jump to turn ' + turn,
      ]
      var buttons = document.querySelectorAll('button[aria-label]')
      for (var i = 0; i < buttons.length; i++) {
        if (labels.indexOf(buttons[i].getAttribute('aria-label')) >= 0) {
          buttons[i].click()
          // Native navigation owns paging. Once its target row is present,
          // this visual landing guard makes the contract observable even when
          // another scroll owner (composer follow, media panel) moved afterward.
          var tries = 0
          var timer = window.setInterval(function () {
            tries += 1
            if (directScrollToTurn(turn) || tries >= 20) window.clearInterval(timer)
          }, 100)
          return true
        }
      }
      return directScrollToTurn(turn)
    }

    /** Follow Chat without coupling the two scroll positions. */
    function useChatTurn(initial) {
      var state = useState(initial || null)
      var setTurn = state[1]
      useEffect(function () {
        var bound = null
        var frame = null
        var sync = function () {
          frame = null
          var next = turnAtReadingLine(bound)
          if (Number.isSafeInteger(next)) setTurn(function (current) { return current === next ? current : next })
        }
        var schedule = function () {
          if (frame !== null) return
          frame = window.requestAnimationFrame(sync)
        }
        var bind = function () {
          var next = chatScroller()
          if (next === bound) return
          if (bound !== null) bound.removeEventListener('scroll', schedule)
          bound = next
          if (bound !== null) {
            bound.addEventListener('scroll', schedule, { passive: true })
            schedule()
          }
        }
        bind()
        var observer = new MutationObserver(bind)
        observer.observe(document.body, { childList: true, subtree: true })
        window.addEventListener('resize', schedule)
        return function () {
          observer.disconnect()
          if (bound !== null) bound.removeEventListener('scroll', schedule)
          if (frame !== null) window.cancelAnimationFrame(frame)
          window.removeEventListener('resize', schedule)
        }
      }, [])
      return state[0]
    }

    function insertPath(path) {
      var box = document.querySelector('[contenteditable="true"]')
      if (box === null) return false
      box.focus()
      try { return document.execCommand('insertText', false, path + ' ') } catch (e) { return false }
    }

    function sourceLineCount(source) {
      if (source === null || source === undefined) return 0
      if (Number.isFinite(source.lineCount)) return source.lineCount
      return Math.max(0, Number(source.end) - Number(source.start) + 1)
    }

    function SourceSnippet(props) {
      var source = (shared.sourceCache || {})[props.id]
      if (source === undefined) return h('div', { className: 'cddl-trace-loading' }, '读取源码…')
      if (source === null || source.lines === undefined) {
        return h('div', {
          className: 'cddl-trace-source cddl-trace-missing',
          'data-cdd-source-id': props.id,
        }, '源码范围读不出来')
      }
      var count = sourceLineCount(source)
      return h('div', { className: 'cddl-trace-source' }, [
        h('div', { key: 'path', className: 'cddl-trace-path', title: source.file },
          source.file + ':' + source.start + '–' + source.end + ' · ' + count + ' 行'),
        h('pre', {
          key: 'code',
          'data-cdd-source-id': source.id || props.id,
          'data-cdd-source-start': source.start,
          'data-cdd-source-end': source.end,
          'data-cdd-source-lines': count,
        }, source.lines.map(function (text, i) {
          return h('div', { key: source.from + i }, [
            h('span', { key: 'n' }, source.from + i),
            h('code', { key: 'c' }, text === '' ? ' ' : text),
          ])
        })),
      ])
    }

    function locateInGraph(ctx, engine, id) {
      // 先把图面板开出来，再定位：面板没开的话，定位完了也没人看得见。
      openDockBesideChat(ctx)
      if (shared.graph.nodes[id] !== undefined) return engine.reveal(id)
      return engine.anchor(id).then(function (anchor) {
        if (anchor === null || anchor === undefined) return false
        return engine.focus(anchor).then(function () { return engine.reveal(id) }).then(function () { return true })
      })
    }

    function AnchorRow(props) {
      var row = props.row
      var node = row.id === null ? undefined : shared.graph.nodes[row.id]
      var anchor = node === undefined ? null : node
      var label = anchor === null ? (row.id === null ? row.file : row.id.split('::').pop()) : anchor.symbol
      return h('article', {
        className: 'cddl-trace-anchor' + stateClass(row) + (props.expanded ? ' is-open' : ''),
        'data-cdd-anchor-id': row.id || '',
      }, [
        h('button', {
          key: 'main', className: 'cddl-trace-anchor-main',
          title: props.expanded ? '折叠 Anchor' : '展开 Anchor',
          onClick: function () { props.onToggle(row) },
        }, [
          h('span', { key: 'chev', className: 'cddl-trace-chevron' }, props.expanded ? '▾' : '▸'),
          h('span', { key: 'dot', className: 'cddl-trace-dot' }),
          h('span', { key: 'label', className: 'cddl-trace-label', title: row.id || row.file }, label),
          h('span', { key: 'state', className: 'cddl-trace-state' }, verbOf(row)),
        ]),
        props.expanded ? h('div', { key: 'detail', className: 'cddl-trace-detail' }, [
          row.id === null
            ? h('div', { key: 'file', className: 'cddl-trace-unresolved' }, [
              h('span', { key: 'why' }, row.reason || '未匹配到 Anchor'),
              h('button', { key: 'insert', onClick: function () { insertPath(row.file) } }, '插入路径'),
            ])
            : h(SourceSnippet, { key: 'source', id: row.id }),
          row.id !== null ? h('button', {
            key: 'locate', className: 'cddl-trace-locate',
            'data-locate-anchor-id': row.id,
            onClick: function () { locateInGraph(props.ctx, props.engine, row.id) },
          }, '在逻辑图中定位') : null,
        ]) : null,
      ])
    }

    /** Fixed right column; history is never filtered by compaction/fade. */
    function TrajectorySidebar(props) {
      useShared()
      var engine = useMemo(function () { return makeEngine(props.ctx) }, [])
      var rows = stepsOf()
      var turns = groupRows(rows)
      var currentTurn = useChatTurn(shared.turn)
      var visibleTurns = turns.slice()
      if (Number.isSafeInteger(currentTurn) && !visibleTurns.some(function (turn) { return turn.turn === currentTurn })) {
        visibleTurns.push({ turn: currentTurn, steps: [], empty: true })
        visibleTurns.sort(function (left, right) { return left.turn - right.turn })
      }
      var expandedState = useState(loadExpanded)
      var expanded = expandedState[0]
      var setExpanded = expandedState[1]
      var widthState = useState(loadWidth)
      var width = widthState[0]
      var setWidth = widthState[1]
      var collapsedState = useState(loadCollapsed)
      var collapsed = collapsedState[0]
      var setCollapsed = collapsedState[1]
      var bodyRef = useRef(null)
      var pointerInside = useRef(false)
      var drag = useRef(null)

      // Expanded rows survive reloads. Their in-memory source cache does not,
      // so restore the data as well as the chevron instead of leaving a
      // permanent empty "读取源码…" panel after refresh.
      useEffect(function () {
        rows.forEach(function (row) {
          if (row.id !== null && expanded[row.key] === true && (shared.sourceCache || {})[row.id] === undefined) {
            engine.source(row.id)
          }
        })
      }, [rows.length, Object.keys(expanded).join('|')])

      useEffect(function () {
        document.documentElement.style.setProperty('--cddl-trajectory-width', width + 'px')
        try { window.localStorage.setItem(WIDTH_KEY, String(width)) } catch (e) { /* optional */ }
        return function () { document.documentElement.style.removeProperty('--cddl-trajectory-width') }
      }, [width])

      // The trajectory is the third content column, not a viewport overlay.
      // Follow Chat's real scroll-area top so DSH's complete session header
      // remains visible even if the host changes its header height.
      useEffect(function () {
        var frame = null
        var syncTop = function () {
          frame = null
          var scroller = chatScroller()
          var tabs = document.querySelector('[role="tablist"]')
          var header = tabs === null ? null : tabs.closest('header')
          // Falling back to 0 put this column over the session header and the
          // tab bar — the one thing it must never cover, because that is how
          // you leave it. The tab strip's own bottom is the floor.
          // Tied to Chat's own scroll area, top and bottom. Anchored to the
          // window instead, it rode over the session header and the tab strip —
          // the one thing it must never cover, since that is how you leave it.
          var tabsBottom = tabs === null ? 0 : Math.round(tabs.getBoundingClientRect().bottom)
          // Only the top is derived, and only far enough to clear the header and
          // the tab strip — the one thing this column must never cover, since
          // that is how you leave it. The bottom is left alone: tying it to
          // Chat's box meant a hidden element's zero rect collapsed the whole
          // column, and the space reserved for it stayed behind as a blank band.
          var boundary = scroller !== null ? scroller.getBoundingClientRect().top
            : header !== null ? header.getBoundingClientRect().bottom : tabsBottom
          var top = Math.max(tabsBottom, Math.round(boundary))
          document.documentElement.style.setProperty('--cddl-trajectory-top', top + 'px')
        }
        var schedule = function () {
          if (frame !== null) return
          frame = window.requestAnimationFrame(syncTop)
        }
        syncTop()
        var observer = new MutationObserver(schedule)
        observer.observe(document.body, { childList: true, subtree: true })
        window.addEventListener('resize', schedule)
        return function () {
          observer.disconnect()
          if (frame !== null) window.cancelAnimationFrame(frame)
          window.removeEventListener('resize', schedule)
          document.documentElement.style.removeProperty('--cddl-trajectory-top')
        }
      }, [])

      var toggleCollapsed = function () {
        var next = !collapsed
        try { window.localStorage.setItem(COLLAPSED_KEY, next ? '1' : '0') } catch (e) { /* optional */ }
        setCollapsed(next)
      }

      useEffect(function () {
        var body = bodyRef.current
        if (body === null || pointerInside.current || !Number.isSafeInteger(currentTurn)) return
        var groups = body.querySelectorAll('[data-cdd-turn]')
        for (var i = 0; i < groups.length; i++) {
          if (Number(groups[i].dataset.cddTurn) !== currentTurn) continue
          var outer = body.getBoundingClientRect()
          var target = groups[i].getBoundingClientRect()
          if (target.top >= outer.top && target.bottom <= outer.bottom) return
          body.scrollTop += target.top - outer.top
          return
        }
      }, [currentTurn, rows.length])

      var toggle = function (row) {
        var next = Object.assign({}, expanded)
        if (next[row.key]) delete next[row.key]
        else {
          next[row.key] = true
          if (row.id !== null) engine.source(row.id)
        }
        saveExpanded(next)
        setExpanded(next)
      }

      var resize = function (event) {
        if (event.button !== undefined && event.button !== 0) return
        event.preventDefault()
        drag.current = { x: event.clientX, width: width }
        var move = function (e) {
          var next = drag.current.width + (drag.current.x - e.clientX)
          setWidth(Math.max(280, Math.min(520, next)))
        }
        var up = function () {
          drag.current = null
          window.removeEventListener('pointermove', move)
          window.removeEventListener('pointerup', up)
        }
        window.addEventListener('pointermove', move)
        window.addEventListener('pointerup', up)
      }

      return h('aside', {
        className: 'cddl-trajectory' + (collapsed ? ' is-collapsed' : ''),
        style: { width: width + 'px' },
        'data-cdd-trajectory': 'persistent',
      }, [
        h('div', { key: 'resize', className: 'cddl-trajectory-resize', title: '拖动改变轨迹栏宽度', onPointerDown: resize }),
        // The source lives here, not over the graph. This edge is one place
        // with several tenants; reading a function should cost the graph
        // nothing, and the graph is the thing you came to look at.
        (shared.focused && shared.viewMounted > 0) ? h('div', { key: 'src', className: 'cddl-trajectory-src' }, [
          h(Source, { key: 's', engine: engine }),
          h(History, { key: 'h' }),
        ]) : null,
        h('header', { key: 'head', className: 'cddl-trajectory-head' }, [
          h('div', { key: 'title' }, [
            h('strong', { key: 'strong' }, '轨迹'),
            h('span', { key: 'count' }, turns.length + ' 轮 · ' + rows.length + ' Anchor 记录'),
          ]),
          h('button', {
            key: 'collapse', className: 'cddl-trajectory-toggle',
            'aria-expanded': collapsed ? 'false' : 'true',
            'aria-label': collapsed ? '展开代码轨迹' : '收起代码轨迹',
            title: collapsed ? '展开轨迹侧栏' : '收起轨迹侧栏', onClick: toggleCollapsed,
          }, collapsed ? '代码轨迹' : '收起'),
        ]),
        h('div', {
          key: 'body', ref: bodyRef, className: 'cddl-trajectory-body',
          onPointerEnter: function () { pointerInside.current = true },
          onPointerLeave: function () { pointerInside.current = false },
        }, visibleTurns.length === 0
          ? h('div', { className: 'cddl-trajectory-empty' }, 'Agent 查看或修改代码后，轨迹会永久保留在这里。')
          : visibleTurns.map(function (turn) {
            var active = turn.turn === currentTurn
            return h('section', {
              key: turn.turn, className: 'cddl-trace-turn' + (active ? ' is-current' : ''),
              'data-cdd-turn': turn.turn,
            }, [
              h('button', {
                key: 'turn', className: 'cddl-trace-turn-head',
                'aria-current': active ? 'true' : undefined,
                onClick: function () { jumpToChatTurn(turn.turn) },
              }, [
                h('b', { key: 't' }, 'TURN ' + turn.turn),
                h('span', { key: 'n' }, turn.steps.length + ' 步'),
                h('span', { key: 'jump' }, '跳到对话'),
              ]),
              h('div', { key: 'steps', className: 'cddl-trace-steps' }, turn.steps.map(function (step) {
                return h('div', { key: step.step, className: 'cddl-trace-step' }, [
                  h('div', { key: 'label', className: 'cddl-trace-step-label' }, 'STEP ' + step.step),
                  h('div', { key: 'rows', className: 'cddl-trace-step-rows' }, step.rows.map(function (row) {
                    return h(AnchorRow, {
                      key: row.key, row: row, engine: engine,
                      ctx: props.ctx,
                      expanded: expanded[row.key] === true, onToggle: toggle,
                    })
                  })),
                ])
              }).concat(turn.empty === true
                ? [h('div', { key: 'empty', className: 'cddl-trace-turn-empty' }, '本轮没有代码轨迹')]
                : [])),
            ])
          })),
      ])
    }

    /** Kept for the old "进度" tab; it now renders the same persistent model. */
    function Stream(props) {
      var rows = stepsOf()
      return h('div', { className: 'cddl-rail' }, rows.length === 0
        ? h('div', { className: 'cddl-rail-empty' }, '还没有动作。')
        : h('div', { className: 'cddl-rail-body' }, groupRows(rows).map(function (turn) {
          return h('div', { key: turn.turn, className: 'cddl-rail-at' },
            'TURN ' + turn.turn + ' · ' + turn.steps.length + ' 步')
        })))
    }

    module.exports = {
      WIDTH_KEY, EXPANDED_KEY, stepsOf, groupRows, turnAtReadingLine,
      directScrollToTurn, jumpToChatTurn, locateInGraph, TrajectorySidebar, Stream,
    }
    return module.exports
  },
})
