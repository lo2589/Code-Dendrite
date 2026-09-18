// dsh-cdd-lens — Per-anchor presentation helpers.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/record',
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
    var __session_position = require('dsh-cdd-lens/session/position')
    var staleOf = __session_position.staleOf

    // ---- presentation helpers ---------------------------------------------

    /** The state class for an anchor: what the session did to it, if anything. */
    function stateOf(id) {
      var record = shared.trace[id]
      if (record === undefined) return null
      return record
    }

    function dotClass(record) {
      if (record === undefined || record === null) return 'cddl-dot'
      if (record.state === 'working') return 'cddl-dot cddl-w'
      if (record.state === 'edited') return 'cddl-dot cddl-e'
      return 'cddl-dot cddl-v'
    }

    /**
     * The order the agent reached this anchor, 1-based.
     *
     * The turn number alone is not an order: a session that did all its reading
     * in one turn stamps every node T13 and the sequence — the thing being
     * reported — disappears. This is the rank of the first call that touched it.
     */
    function orderOf(id) {
      var seq = shared.order
      if (seq === undefined) return null
      var i = seq[id]
      return i === undefined ? null : i
    }

    /**
     * When this anchor was first opened, to the step.
     *
     * A turn number alone is not enough to find the moment again: a turn is
     * twenty tool calls, and "somewhere in turn 15" is not a place. `t15s3` is
     * the third call of turn 15, which is a place — it lines up with what the
     * trajectory shows and with what anyone says out loud.
     * @param record - the anchor's session record, or nothing.
     * @returns the badge element, or null when the session never touched it.
     */
    function turnLabel(record) {
      if (record === undefined || record === null) return null
      var verb = record.state === 'working' ? '正在改' : record.state === 'edited' ? '改' : '看'
      var tone = record.state === 'working' ? 'cddl-w' : record.state === 'edited' ? 'cddl-e' : 'cddl-v'
      var at = 't' + record.firstTurn + (record.firstStep === undefined ? '' : 's' + record.firstStep)
      var last = 't' + record.lastTurn + (record.lastStep === undefined ? '' : 's' + record.lastStep)
      var title = '第 ' + record.firstTurn + ' 轮第 ' + (record.firstStep || 1) + ' 步第一次打开'
        + (last === at ? '' : '，最后一次是 ' + last)
        + (record.approx ? '（行号为近似）' : '')
      return h('span', { className: 'cddl-turn ' + tone, title: title },
        at + ' ' + verb + (record.approx ? '~' : ''))
    }

    /**
     * Whether a project's index is too edge-poor to draw a call graph from.
     *
     * An unfiltered scan of a repository with `node_modules` in it produces
     * hundreds of thousands of anchors and almost no relations — every symbol
     * found, nothing connected. The panel would then draw a correct, useless
     * empty graph, and the honest thing is to say the index is the problem.
     */
    function degenerate(context) {
      if (context === undefined || context === null || context.stats === undefined) return false
      var stats = context.stats
      return stats.anchors > 5000 && stats.edges < stats.anchors / 20
    }

    function short(file) {
      var parts = String(file || '').split('/')
      return parts.length <= 2 ? file : '…/' + parts.slice(-2).join('/')
    }

    // ---- 位置：这一刻的 anchor 和现在的关系 ----------------------------------

    /**
     * 这个 anchor **现在**的 hash。
     *
     * 图上节点的记录就是当前索引里的记录（`/screen` 发的），anchor 缓存同理 ——
     * 两边描述的都是"现在的代码"。都没有就返回空串：那一位判不了过期。
     */
    function currentHashOf(id) {
      var nodes = shared.graph === undefined || shared.graph === null ? undefined : shared.graph.nodes
      var node = nodes === undefined || nodes === null ? undefined : nodes[id]
      if (node !== undefined && node !== null && typeof node.hash === 'string') return node.hash
      var cached = (shared.anchorCache || {})[id]
      if (cached !== undefined && cached !== null && typeof cached.hash === 'string') return cached.hash
      return ''
    }

    /**
     * 这个位置过期没有：存下来的 hash 和现在的对不上，就是这份代码在那之后改过。
     *
     * @param row - 一条位置（轨迹栏的行，或 anchor 记录里的一条经历）。
     * @param id - 它属于哪个 anchor。轨迹栏的行自己带 `id`；「经历」面板的一条经历不带
     *   （它挂在 anchor 记录下面），所以调用方要把 anchor id 传进来。
     *
     * 空 hash 是**判不了**，不是没过期 —— 抓的时候就没抓住（回放旧会话、anchor 本来
     * 就没有 hash），这种情况不打过期标记，因为打了就是编。
     */
    function expiredOf(row, id) {
      if (row === undefined || row === null) return false
      var anchorId = id === undefined ? row.id : id
      return staleOf(row.hash, currentHashOf(anchorId)) === 'stale'
    }

    /** 只读到一部分：窗口切在函数中间。不完整不是"没碰到"，仍然是一条位置。 */
    function partialOf(row) {
      var cover = row === undefined || row === null ? undefined : row.coverage
      return cover !== undefined && cover !== null && cover.complete === false
    }

    module.exports = { stateOf, dotClass, orderOf, turnLabel, degenerate, short, currentHashOf, expiredOf, partialOf }
    return module.exports
  },
})
