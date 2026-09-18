// 位置与读窗口的契约。
//
// 两件事，都是"以前算错、而且错得不响"的那一类：
//
// 1) read 的窗口。harness 的 read 结果 `meta.lines` 是 `ReadFileLine[]`
//    （packages/core/tools/src/presentation.ts::ReadResultView），**不是行数**。
//    前端 session/trajectory.js 与宿主 session_trace.js 都写成
//    `Number.isInteger(meta.lines)` —— 数组永远过不了这个判断，分支是死代码：
//      前端 → 掉到"没写 limit 就是整文件"，`to: -1`
//      宿主 → 掉到 `to: null`，退化成"只认 from 那一行的单个 anchor"
//    535 条真实会话记录里 179 条（33.5%）窗口算错，两条路各错 152 条，而且是
//    同一个 read 给出两个不同答案。这里第 5 组用真实形状的数据把那段钉死。
//
// 2) 位置。轨迹栏按「位置」记：`session|轮次|step|anchor`。每条位置在抓的那一刻
//    存一个 hash（之后不改），拿它跟这个 anchor 现在的 hash 比 —— 不一样就是过期。
//    空 hash 是**判不了**，不是没过期；把它当过期的反义词就会编。
//
//   node lens/scripts/build.js && node lens/tests/position-window.js
'use strict'
const fs = require('fs')
const vm = require('vm')
const path = require('path')
const assert = require('assert')

const BUNDLE = fs.readFileSync(path.join(__dirname, '..', 'lib', 'client.js'), 'utf8')

/** 能装下 bundle 的最小宿主：只认登记，其余交给调用方。 */
function loadParts() {
  const factories = new Map()
  const cache = new Map()
  const require_ = (id) => {
    if (cache.has(id)) return cache.get(id)
    if (!factories.has(id)) throw new Error('no registered factory for "' + id + '"')
    const value = factories.get(id)(require_)
    cache.set(id, value)
    return value
  }
  const context = {
    window: { __ModuleLoader__: { load: r => factories.set(r.id, r.factory) } },
    console, URLSearchParams, setTimeout, clearTimeout, setInterval, clearInterval,
  }
  vm.createContext(context)
  vm.runInContext(BUNDLE, context)
  return { require_, factories }
}

const parts = loadParts()
const P = parts.require_('dsh-cdd-lens/session/position')

// 模块跑在 vm 上下文里，它返回的对象原型和我们这边不是同一个，
// deepStrictEqual 会拿原型说事。取值重建成这边的普通对象再比。
const win = (meta, args) => {
  const w = P.readWindow(meta, args)
  return { from: w.from, to: w.to }
}

let failed = 0
const check = (name, fn) => {
  try { fn(); console.log('ok   ' + name) } catch (error) { failed += 1; console.log('FAIL ' + name + ' — ' + error.message) }
}

// ---- 1. 位置 id：编得出来，解得回去 --------------------------------------

const SESSION = '97f1864e-58b4-44f4-ba4d-5e6bee396efd'
const ANCHOR = 'lens/src/compute/resolve.js::resolveTouch'

check('位置 id 是 session|轮次|step|anchor', () => {
  assert.strictEqual(P.positionId(SESSION, 3, 7, ANCHOR), SESSION + '|3|7|' + ANCHOR)
})

check('位置 id 解得回四个字段', () => {
  const at = P.parsePositionId(P.positionId(SESSION, 3, 7, ANCHOR))
  assert.strictEqual(at.session, SESSION)
  assert.strictEqual(at.turn, 3)
  assert.strictEqual(at.step, 7)
  assert.strictEqual(at.anchorId, ANCHOR)
})

check('anchorId 自带 | 也不切错（只切前三个）', () => {
  const odd = 'weird|dir/a b.py::f'
  assert.strictEqual(P.parsePositionId(P.positionId('s', 1, 2, odd)).anchorId, odd)
})

check('同一 step 的不同 anchor 是两条位置', () => {
  assert.notStrictEqual(P.positionId('s', 1, 2, 'a.py::f'), P.positionId('s', 1, 2, 'a.py::g'))
})

check('同一 anchor 的不同 step 是两条位置', () => {
  assert.notStrictEqual(P.positionId('s', 1, 2, ANCHOR), P.positionId('s', 1, 3, ANCHOR))
})

check('缺字段的位置 id 解出来是 null', () => {
  assert.strictEqual(P.parsePositionId('s|1|2'), null)
})

// ---- 2. 过期：三种情况，未知不是没事 --------------------------------------

check('hash 一样 → 没过期', () => assert.strictEqual(P.staleOf('dce8168db1dc', 'dce8168db1dc'), 'ok'))
check('hash 不一样 → 过期', () => assert.strictEqual(P.staleOf('dce8168db1dc', '0c6b6b5ce341'), 'stale'))
check('存的是空 → 判不了（不是没过期）', () => assert.strictEqual(P.staleOf('', 'dce8168db1dc'), 'unknown'))
check('现在的拿不到 → 判不了', () => assert.strictEqual(P.staleOf('dce8168db1dc', ''), 'unknown'))
check('两边都空 → 判不了', () => assert.strictEqual(P.staleOf('', ''), 'unknown'))
check('根本没有 hash 字段 → 判不了', () => assert.strictEqual(P.staleOf(undefined, 'x'), 'unknown'))

// ---- 3. 读到多少：读窗口和 anchor 的交集 -----------------------------------

const FULL = { start: 100, end: 120 }
const HEAD = { start: 90, end: 120 }
const TAIL = { start: 100, end: 140 }
const SWALLOW = { start: 80, end: 200 }

check('完整落在窗口里 → complete', () => {
  const c = P.coverageOf(FULL, 90, 130)
  assert.deepStrictEqual([c.readFrom, c.readTo, c.span, c.total, c.complete], [100, 120, 21, 21, true])
})

check('头被切：anchor 起点在窗口上方', () => {
  const c = P.coverageOf(HEAD, 100, 130)
  assert.deepStrictEqual([c.readFrom, c.readTo, c.span, c.total, c.complete], [100, 120, 21, 31, false])
})

check('尾被切：anchor 终点在窗口下方', () => {
  const c = P.coverageOf(TAIL, 90, 130)
  assert.deepStrictEqual([c.readFrom, c.readTo, c.span, c.total, c.complete], [100, 130, 31, 41, false])
})

check('两头都切：窗口只是它的中段', () => {
  const c = P.coverageOf(SWALLOW, 100, 130)
  assert.deepStrictEqual([c.readFrom, c.readTo, c.span, c.total, c.complete], [100, 130, 31, 121, false])
})

check('不完整照样算得出来（不丢，只标部分）', () => {
  assert.notStrictEqual(P.coverageOf(SWALLOW, 100, 130), null)
})

check('to=-1（读到文件尾）按整段算', () => {
  const c = P.coverageOf({ start: 5, end: 9 }, 1, -1)
  assert.deepStrictEqual([c.span, c.complete], [5, true])
})

check('窗口和 anchor 不相交 → null', () => {
  assert.strictEqual(P.coverageOf({ start: 300, end: 320 }, 100, 130), null)
})

check('anchor 没有行号 → null', () => {
  assert.strictEqual(P.coverageOf({ symbol: 'f' }, 100, 130), null)
  assert.strictEqual(P.coverageOf(null, 100, 130), null)
})

check('索引的原始字段名（line_start/line_end）也认', () => {
  const c = P.coverageOf({ line_start: 100, line_end: 120 }, 90, 130)
  assert.strictEqual(c.complete, true)
})

// ---- 4. 读窗口：三种来源，各走各的 ----------------------------------------

check('有 lines 数组 → 用最后一行的 number 当终点', () => {
  const meta = { offset: 40, lines: [{ number: 40, text: 'a' }, { number: 46, text: 'b' }], totalLines: 46 }
  assert.deepStrictEqual(win(meta, {}), { from: 40, to: 46 })
})

check('lines 是空数组 → 退回 limit', () => {
  assert.deepStrictEqual(win({ offset: 10, lines: [] }, { limit: 5 }), { from: 10, to: 14 })
})

check('没有 lines 也没有 limit → 整文件（-1）', () => {
  assert.deepStrictEqual(win({ offset: 1 }, {}), { from: 1, to: -1 })
})

check('from 优先取 meta.offset，其次参数，都没有就 1', () => {
  assert.strictEqual(win({ offset: 3, lines: [{ number: 3, text: '' }] }, { offset: 99 }).from, 3)
  assert.strictEqual(win({ lines: [] }, { offset: 99, limit: 4 }).from, 99)
  assert.strictEqual(win({}, {}).from, 1)
})

check('windowLines 只认数组', () => {
  assert.strictEqual(P.windowLines({ lines: [{ number: 1, text: 'x' }] }).length, 1)
  assert.strictEqual(P.windowLines({ lines: 40 }), null)
  assert.strictEqual(P.windowLines({}), null)
  assert.strictEqual(P.windowLines(null), null)
})

// ---- 5. 回归：真实会话里那些被算错的窗口 -----------------------------------
//
// 形状抄自 .dsh 会话日志里真实的 read 结果。左边是 meta，右边是这段代码**必须**
// 给出的窗口。旧的 `Number.isInteger(meta.lines)` 式在这里全线走错。

const CASES = [
  // 描述,                                  meta,                                             参数,                  应有窗口
  ['整文件读（没写 limit）', { offset: 1, lines: n(1, 46), totalLines: 46 }, { file_path: 'a.py' }, { from: 1, to: 46 }],
  ['从 40 行读到文件尾（没写 limit）', { offset: 40, lines: n(40, 46), totalLines: 46 }, { file_path: 'a.py', offset: 40 }, { from: 40, to: 46 }],
  ['中段 65 行（没写 limit）', { offset: 130, lines: n(130, 194), totalLines: 194 }, { file_path: 'a.py', offset: 130 }, { from: 130, to: 194 }],
  ['写了 limit 且读满', { offset: 10, lines: n(10, 39), totalLines: 900 }, { file_path: 'a.py', offset: 10, limit: 30 }, { from: 10, to: 39 }],
  ['写了 limit 但到文件尾截断', { offset: 880, lines: n(880, 900), totalLines: 900 }, { file_path: 'a.py', offset: 880, limit: 30 }, { from: 880, to: 900 }],
  ['只有一行', { offset: 7, lines: n(7, 7), totalLines: 900 }, { file_path: 'a.py', offset: 7, limit: 1 }, { from: 7, to: 7 }],
]

function n(from, to) {
  const out = []
  for (let i = from; i <= to; i += 1) out.push({ number: i, text: 'line ' + i })
  return out
}

CASES.forEach(([label, meta, args, want]) => {
  check('真实形状 · ' + label, () => assert.deepStrictEqual(win(meta, args), want))
})

check('这些用例里至少有一条是旧写法必错的（没 limit 且 offset>1）', () => {
  const [, meta, args] = CASES[1]
  const old = (() => {
    const from = Number.isInteger(meta.offset) ? meta.offset : 1
    const span = Number.isInteger(meta.lines) ? meta.lines : (Number.isInteger(args.limit) ? args.limit : null)
    return { from, to: span === null ? -1 : from + span - 1 }
  })()
  assert.deepStrictEqual(old, { from: 40, to: -1 }, '旧写法在这里给出整文件，正是这个 bug')
  assert.deepStrictEqual(win(meta, args), { from: 40, to: 46 })
})

console.log(failed === 0 ? 'ALL PASS' : failed + ' FAILED')
process.exit(failed === 0 ? 0 : 1)
