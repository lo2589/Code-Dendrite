// dsh-cdd-lens — 位置：一次查看的坐标，以及它和现在这份代码的关系。
//
// 轨迹栏按「位置」记，不按 anchor 记：谁在第几轮第几步碰到了哪个 anchor。同一个
// anchor 被看两次就是两条位置 —— 它们各有各的时刻，各记各的 hash。
//
//   位置 id = <session>|<turn>|<step>|<anchorId>
//
// 分隔符用 `|`：session 是 UUID（十六进制 + `-`），turn / step 是整数，这三段里
// 不可能出现 `|`。anchorId 放最后一段，它自带 `/`、`:`、`.` 都不参与切分 —— 解析
// 时只切前三个 `|`，剩下整段就是 anchorId。
//
// 每个位置存一个 hash：抓的那一刻这个 anchor 的代码哈希，之后永不改写。任何时候
// 拿它跟现在的对，就知道这个位置过期没有。抓的时候就没抓住的（行对不上、隔了太
// 久才补算）hash 是空串，判不了 —— 空串不是"没过期"，是"不知道"。
//
// ## 读窗口
//
// harness 的 read 结果 `meta.lines` 是 `ReadFileLine[]`（`{ number, text }`），
// **不是行数**（packages/core/tools/src/presentation.ts::ReadResultView）。以前两处
// 用 `Number.isInteger(meta.lines)` 判断，数组恒为 false，于是窗口整个算错：一类
// 退化成"只有第一行"，一类退化成"整个文件"。readWindow 是那两处唯一的算法。
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/session/position',
  factory: (require) => {
    var module = { exports: {} }

    var SEP = '|'

    /** `<session>|<turn>|<step>|<anchorId>`。anchorId 放最后，它自带的 `|` 不影响解析。 */
    function positionId(session, turn, step, anchorId) {
      return [
        session === undefined || session === null ? '' : String(session),
        String(turn),
        String(step),
        String(anchorId),
      ].join(SEP)
    }

    function parsePositionId(pid) {
      var parts = String(pid).split(SEP)
      if (parts.length < 4) return null
      return {
        session: parts[0],
        turn: Number(parts[1]),
        step: Number(parts[2]),
        anchorId: parts.slice(3).join(SEP),
      }
    }

    /** 读回来的那几行原文。不是数组就是没有（老记录、非 read、非 meta 事件）。 */
    function windowLines(meta) {
      var lines = meta === null || meta === undefined ? undefined : meta.lines
      return Array.isArray(lines) ? lines : null
    }

    /**
     * 一次 read 的 `[from, to]`。
     *
     * 正常一定走 `meta.lines` 这条：取最后一行的 `number` 当终点。没有数组时才退回
     * `limit` / 整文件 —— `-1` 是"读到文件尾"在线上各处的写法。
     */
    function readWindow(meta, args) {
      var m = meta || {}
      var a = args || {}
      var from = Number.isInteger(m.offset) ? m.offset : (Number.isInteger(a.offset) ? a.offset : 1)
      var lines = windowLines(m)
      if (lines !== null && lines.length > 0) {
        var last = lines[lines.length - 1]
        var to = Number.isInteger(last.number) ? last.number : from + lines.length - 1
        return { from: from, to: to }
      }
      if (Number.isInteger(m.lines)) return { from: from, to: from + m.lines - 1 }
      if (Number.isInteger(a.limit)) return { from: from, to: from + a.limit - 1 }
      return { from: from, to: -1 }
    }

    /**
     * 位置过期没有。
     *
     * `unknown` 不是"没过期"，是判不了：抓的时候 hash 就没抓住。
     */
    function staleOf(stored, current) {
      if (typeof stored !== 'string' || stored === '') return 'unknown'
      if (typeof current !== 'string' || current === '') return 'unknown'
      return stored === current ? 'ok' : 'stale'
    }

    function intOrNull(value) {
      return Number.isInteger(value) ? value : null
    }

    /**
     * 这次查看读到了这个 anchor 的多少。
     *
     * 读窗口和 anchor 是两个区间，读到的部分就是**它们的交集**：`[max(start,from),
     * min(end,to)]`。实测 535 次 read 里只有 28% 是整文件读，其余首尾至少有一端切
     * 在函数中间，所以"完整落在窗口里"是少数。
     *
     * 不完整**不是**"没碰到" —— 它照样是一条位置，照样记。这里只是把"只扫到尾巴
     * 11 行"和"整只读过"分开，好让界面上不是同一件事。
     *
     * @returns null 表示算不出来（anchor 没有行号，或窗口本身没有行号）。
     */
    function coverageOf(anchor, from, to) {
      var a = anchor || {}
      var start = intOrNull(a.start !== undefined ? a.start : a.line_start)
      var end = intOrNull(a.end !== undefined ? a.end : a.line_end)
      var lo = intOrNull(from)
      // `-1` 是"读到文件尾"在线上各处的写法。
      var hi = to === -1 ? Infinity : intOrNull(to)
      if (start === null || end === null || lo === null || hi === null) return null
      var readFrom = Math.max(start, lo)
      var readTo = Math.min(end, hi)
      if (readTo < readFrom) return null
      return {
        readFrom: readFrom, readTo: readTo,
        span: readTo - readFrom + 1, total: end - start + 1,
        complete: start >= lo && end <= hi,
      }
    }

    // ---- 位置 hash 的账本：抓到一次，之后永不改写 ---------------------------
    //
    // 「存抓那一刻的 hash」以前只是句注释：轨迹每重算一次，hash 就按**当前**索引重新
    // 算一遍，于是它永远等于当前值 —— 自己跟自己比，过期这件事根本不可能发生。真正
    // 要做的是把第一次抓到的值记下来，后面只读不写。
    var HASH_KEY = 'cdd-lens.position-hash.v1'
    var LIMIT = 4000
    var frozen = null

    function loadFrozen() {
      if (frozen !== null) return frozen
      frozen = {}
      try {
        var raw = window.localStorage.getItem(HASH_KEY)
        if (raw) frozen = JSON.parse(raw) || {}
      } catch (e) { frozen = {} }
      return frozen
    }

    function saveFrozen(all) {
      var keys = Object.keys(all)
      if (keys.length > LIMIT) {
        // 超了就丢最早的一批：位置是只增不减的流水，旧的让位给新的。
        keys.slice(0, keys.length - LIMIT).forEach(function (key) { delete all[key] })
      }
      try { window.localStorage.setItem(HASH_KEY, JSON.stringify(all)) } catch (e) { /* 存不下不致命 */ }
    }

    /**
     * 这个位置该用哪个 hash：第一次抓到的那个。
     *
     * @param pid - 位置 id（session|轮次|step|anchor）。
     * @param captured - 这一次算出来的 hash；空串表示没抓住，不记。
     * @returns 账本里的那个值；从没抓住过就返回空串（判不了，不是没过期）。
     */
    function freezeHash(pid, captured) {
      if (typeof pid !== 'string' || pid === '') return typeof captured === 'string' ? captured : ''
      var all = loadFrozen()
      if (typeof all[pid] === 'string' && all[pid] !== '') return all[pid]
      if (typeof captured !== 'string' || captured === '') return ''
      all[pid] = captured
      saveFrozen(all)
      return captured
    }

    /** 测试用：把账本清空，不碰别的状态。 */
    function forgetFrozen() {
      frozen = {}
      try { window.localStorage.removeItem(HASH_KEY) } catch (e) { /* optional */ }
    }

    module.exports = { SEP, positionId, parsePositionId, readWindow, windowLines, staleOf, coverageOf, freezeHash, forgetFrozen }
    return module.exports
  },
})
