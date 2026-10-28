// 位置三态的契约：ok / stale / unknown，一路到界面。
//
// `staleOf` 一直是三态，但界面曾经写成 `expired ? 'stale' : 'ok'`——「判不了」被
// 渲染成「没过期」。那是编：抓的时候没抓住 hash，和「这份代码没变过」是两件事。
//
// 还有一处同源的错：判过期要「现在的 hash」，而它以前只从图上和缓存里找。轨迹里
// 绝大多数行的 anchor 并不在图上，于是「现在的」恒为空串，位置一律显示没过期——
// 不是没过期，是没去问。engine.ensureAnchors 负责去问。
//
//   node lens/scripts/build.js && node lens/tests/position-state.js
'use strict'
const fs = require('fs')
const vm = require('vm')
const path = require('path')
const assert = require('assert')

const ROOT = path.join(__dirname, '..')
const BUNDLE = fs.readFileSync(path.join(ROOT, 'lib', 'client.js'), 'utf8')

/** 能装下 bundle 的最小宿主：React 打桩，其余按需登记。 */
function loadParts() {
  const factories = new Map()
  const cache = new Map()
  const React = {
    createElement: (type, props, ...kids) => ({ type, props: props || {}, kids: kids.flat() }),
    Fragment: 'fragment',
    useState: v => [typeof v === 'function' ? v() : v, () => {}],
    useEffect: () => {}, useMemo: f => f(), useRef: v => ({ current: v }), useCallback: f => f,
  }
  const require_ = (id) => {
    if (id === 'react') return React
    if (cache.has(id)) return cache.get(id)
    if (!factories.has(id)) throw new Error('no registered factory for "' + id + '"')
    const value = factories.get(id)(require_)
    cache.set(id, value)
    return value
  }
  const context = {
    window: {
      __ModuleLoader__: { load: r => factories.set(r.id, r.factory) },
      // 位置 hash 的账本要存盘，桩必须真的能读能写，否则"冻住"测了个寂寞。
      localStorage: (() => {
        const mem = {}
        return {
          getItem: k => (k in mem ? mem[k] : null),
          setItem: (k, v) => { mem[k] = String(v) },
          removeItem: (k) => { delete mem[k] },
        }
      })(),
      matchMedia: () => ({ matches: false }),
      addEventListener: () => {}, removeEventListener: () => {},
      location: { origin: 'http://x' },
    },
    document: {
      querySelector: () => null, querySelectorAll: () => [],
      createElement: () => ({ style: {} }),
      head: { appendChild() {} }, body: { appendChild() {} },
      documentElement: { style: { setProperty() {}, removeProperty() {} } },
    },
    console, URLSearchParams, setTimeout, clearTimeout, setInterval, clearInterval,
  }
  vm.createContext(context)
  vm.runInContext(BUNDLE, context)
  return require_
}

const require_ = loadParts()
const record = require_('dsh-cdd-lens/view/record')
const store = require_('dsh-cdd-lens/state/store')
const fetchPart = require_('dsh-cdd-lens/engine/fetch')

const sourceOf = rel => fs.readFileSync(path.join(ROOT, 'src', rel), 'utf8')

let failed = 0
const check = (name, fn) => {
  try { fn(); console.log('ok   ' + name) } catch (error) { failed += 1; console.log('FAIL ' + name + ' — ' + error.message) }
}

/** 图上有这个 anchor，它现在的 hash 是 `hash`。 */
const onGraph = (id, hash) => {
  store.shared.graph = { nodes: { [id]: { id, hash } }, edges: [] }
  store.shared.anchorCache = {}
}

const ID = 'src/a.py::f'

// ---- 1. 三态 ---------------------------------------------------------------

check('hash 一样 → ok', () => {
  onGraph(ID, 'aaaa1111')
  assert.strictEqual(record.positionStateOf({ id: ID, hash: 'aaaa1111' }), 'ok')
})

check('hash 不一样 → stale', () => {
  onGraph(ID, 'bbbb2222')
  assert.strictEqual(record.positionStateOf({ id: ID, hash: 'aaaa1111' }), 'stale')
})

check('抓的时候没抓住（空串）→ unknown，不是 ok', () => {
  onGraph(ID, 'aaaa1111')
  assert.strictEqual(record.positionStateOf({ id: ID, hash: '' }), 'unknown')
})

check('anchor 现在查不到（不在图上也不在缓存里）→ unknown，不是 ok', () => {
  store.shared.graph = { nodes: {}, edges: [] }
  store.shared.anchorCache = {}
  assert.strictEqual(record.positionStateOf({ id: ID, hash: 'aaaa1111' }), 'unknown')
})

check('缓存里有也算数（轨迹补回来的那一批）', () => {
  store.shared.graph = { nodes: {}, edges: [] }
  store.shared.anchorCache = { [ID]: { id: ID, hash: 'aaaa1111' } }
  assert.strictEqual(record.positionStateOf({ id: ID, hash: 'aaaa1111' }), 'ok')
  assert.strictEqual(record.positionStateOf({ id: ID, hash: 'cccc3333' }), 'stale')
})

check('没有这一行 → unknown', () => {
  assert.strictEqual(record.positionStateOf(null), 'unknown')
  assert.strictEqual(record.positionStateOf(undefined, ID), 'unknown')
})

check('expiredOf 只认 stale：unknown 不算过期', () => {
  onGraph(ID, 'aaaa1111')
  assert.strictEqual(record.expiredOf({ id: ID, hash: '' }), false)
  store.shared.graph = { nodes: { [ID]: { id: ID, hash: 'bbbb2222' } }, edges: [] }
  assert.strictEqual(record.expiredOf({ id: ID, hash: 'aaaa1111' }), true)
})

// ---- 2. 抓到的 hash 要冻住 ---------------------------------------------------

const P = require_('dsh-cdd-lens/session/position')

check('第一次抓到就冻住，之后再算也不改写', () => {
  P.forgetFrozen()
  const pid = 's1|3|2|a.py::f'
  assert.strictEqual(P.freezeHash(pid, 'aaaa1111'), 'aaaa1111')
  // 索引重建后这里会拿到新 hash；位置记的是"那一刻"，必须还给旧的，
  // 否则它永远等于当前值，过期标不出来。
  assert.strictEqual(P.freezeHash(pid, 'bbbb2222'), 'aaaa1111')
})

check('没抓住（空串）不记账，后来抓住了才记', () => {
  P.forgetFrozen()
  const pid = 's1|4|1|a.py::g'
  assert.strictEqual(P.freezeHash(pid, ''), '')
  assert.strictEqual(P.freezeHash(pid, 'cccc3333'), 'cccc3333')
  assert.strictEqual(P.freezeHash(pid, 'dddd4444'), 'cccc3333')
})

check('不同位置各记各的', () => {
  P.forgetFrozen()
  assert.strictEqual(P.freezeHash('s|1|1|x::a', 'h1'), 'h1')
  assert.strictEqual(P.freezeHash('s|2|1|x::a', 'h2'), 'h2')
  assert.strictEqual(P.freezeHash('s|1|1|x::a', 'h9'), 'h1')
})

check('ingest 把位置 hash 交给账本，而不是每次现算', () => {
  const text = sourceOf('client/engine/ingest.js')
  assert.ok(/hash: freezeHash\(pid, currentHash\(call, anchor\)\)/.test(text),
    '不冻住就会被当前索引的 hash 盖掉，位置永远"没过期"')
})

// ---- 3. 图上的节点：过期就变灰 -----------------------------------------------

check('节点按最近一次看的那个位置判过期', () => {
  const store2 = require_('dsh-cdd-lens/state/store')
  store2.shared.graph = { nodes: { [ID]: { id: ID, hash: 'new9999' } }, edges: [] }
  store2.shared.anchorCache = {}
  // 早先看过一次（那版已经变了），最近又看了一次、对得上 → 不该变灰。
  store2.shared.trace = { [ID]: { id: ID, events: [{ hash: 'old1111' }, { hash: 'new9999' }] } }
  assert.strictEqual(record.recordStateOf(ID), 'ok')
  // 最近一次看的那版之后被改过 → 过期。
  store2.shared.trace = { [ID]: { id: ID, events: [{ hash: 'new9999' }, { hash: 'old1111' }] } }
  assert.strictEqual(record.recordStateOf(ID), 'stale')
  // 没有记录 / 没有事件 → 判不了，不是没过期。
  store2.shared.trace = {}
  assert.strictEqual(record.recordStateOf(ID), 'unknown')
})

check('只有 stale 变灰，判不了不许拿灰色冒充', () => {
  const text = sourceOf('client/view/node.js')
  assert.ok(/position === 'stale' \? ' cddl-stale' : ''/.test(text), '节点没有按过期加灰色类')
  assert.ok(/'data-cdd-node-stale': position/.test(text), '节点没把三态写进 data 属性')
  assert.ok(/recordStateOf\(id\)\]\.join\('\|'\)/.test(text), '过期状态没进重绘签名，卡片会停在旧样子')
  const css = sourceOf('client/styles/graph.js')
  assert.ok(/cddl-stale \.cddl-gnode\{filter:grayscale/.test(css), '没有灰调样式')
  // 透明度是「已被压缩」的通道，过期不许抢；hover 变色会在人眼前晃两下，是丢焦点。
  assert.ok(!/cddl-stale[^']*opacity/.test(css), '过期不许动透明度，那是 faded 的通道')
  assert.ok(!/cddl-stale:hover/.test(css), '过期不许做 hover 变色')
})

// ---- 4. 界面不许把三态压成两态 ----------------------------------------------

check('轨迹栏与「经历」面板都不再写 `? \'stale\' : \'ok\'`', () => {
  ;['client/view/stream.js', 'client/view/panels.js'].forEach((rel) => {
    const text = sourceOf(rel)
    assert.ok(!/\?\s*'stale'\s*:\s*'ok'/.test(text), rel + ' 又把三态压成了两态')
    assert.ok(/data-cdd-position-stale': position/.test(text), rel + ' 没把三态写进 data-cdd-position-stale')
    assert.ok(/未知/.test(text), rel + ' 没有「未知」标签')
  })
})

// ---- 3. 去问「现在的 hash」 --------------------------------------------------

check('问过的不再问；索引换一版就要重新问', () => {
  const ledger = fetchPart.askLedger()
  const ids = ['a::1', 'b::2']
  assert.deepStrictEqual(ledger.pick(ids, {}, {}, 'stamp-1'), ids, '第一次应该全问')
  assert.deepStrictEqual(ledger.pick(ids, {}, {}, 'stamp-1'), [], '同一版索引不该再问')
  // 索引重建：缓存被清空，上一版的"问过了"必须作废，否则轨迹永远停在「未知」。
  assert.deepStrictEqual(ledger.pick(ids, {}, {}, 'stamp-2'), ids, '换版后应该重新问')
})

check('图上或缓存里已有的就不问', () => {
  const ledger = fetchPart.askLedger()
  assert.deepStrictEqual(ledger.pick(['a::1', 'b::2'], { 'a::1': {} }, { 'b::2': {} }, 's'), [])
  assert.deepStrictEqual(ledger.pick([null, '', undefined, 7], {}, {}, 's'), [], '脏 id 一律不问')
})

check('落不到 anchor 的行不打「未知」标签', () => {
  const text = sourceOf('client/view/stream.js')
  assert.ok(/position === 'unknown' && row\.id !== null/.test(text),
    '没有 anchor 的行不是「位置」，不该挂一个永远为真的未知标签')
})

check('索引换版要重算，且不以「图上有节点」为前提', () => {
  const text = sourceOf('client/engine/fetch.js')
  assert.ok(/shared\.graphStamp !== stamp\)/.test(text), '换版检测没了')
  assert.ok(!/shared\.graphStamp !== stamp && shared\.graph\.order\.length > 0/.test(text),
    '图是空的时候也要重算：否则位置拿上一版 hash 比，永远说没过期')
})

check('常驻组件定期问 /context，好发现外面重建的索引', () => {
  // 必须挂在 LensRuntime（always-on）里：浮动面板不一定挂载，挂在那儿等于没挂。
  const text = sourceOf('client/shell/dock.js')
  assert.ok(/setInterval\(function \(\) \{ engine\.context\(\) \}, 10000\)/.test(text), '常驻组件里没有空闲轮询')
  assert.ok(/clearInterval\(poll\)/.test(text), '轮询没清理')
})

check('补 anchor 的 effect 依赖里带索引戳', () => {
  const text = sourceOf('client/view/stream.js')
  assert.ok(/engine\.ensureAnchors[\s\S]{0,200}shared\.anchorCacheStamp\]/.test(text),
    '只看行 id：索引重建后 id 没变，effect 不再跑，缓存空着，过期永远标不出来')
})

check('「在逻辑图中定位」只切视图，不翻页', () => {
  const text = sourceOf('client/view/stream.js')
  assert.ok(/jumpToGraph\(ctx\)/.test(text), '定位应该只切到逻辑图')
  assert.ok(!/openDockBesideChat\(ctx\)/.test(text),
    '不能再强开 dock：关详情面板 + 切宿主 tab = 整页翻一遍，要追的节点反而丢了')
  const seat = sourceOf('client/shell/chatSeat.js')
  assert.ok(/if \(shared\.dockOpen === true\)/.test(seat), '已经开着时必须什么都不动')
})

check('焦点锁：按内容坐标补偿，且挂在了画布上', () => {
  const lock = sourceOf('client/view/focusLock.js')
  // 内容坐标（offsetLeft/offsetTop）不随用户滚动变，所以这把锁不会跟用户滚动打架。
  assert.ok(/el\.offsetLeft, y: el\.offsetTop/.test(lock), '必须用内容坐标，不是屏幕坐标')
  assert.ok(/scroller\.scrollTop \+= now\.y - was\.y/.test(lock), '没有按位移补偿滚动')
  assert.ok(/was\.id === id/.test(lock), '换了焦点的那一次不该补偿')
  assert.ok(/useFocusLock\(canvasRef\)/.test(sourceOf('client/shell/graphView.js')), '焦点锁没挂到画布上')
})

check('engine 有 ensureAnchors', () => {
  const methods = fetchPart.fetchMethods({}, {}, () => 'session-x', () => ({}))
  assert.strictEqual(typeof methods.ensureAnchors, 'function')
})

check('图上已有的 id 不再去问（不发请求，直接完成）', () => {
  onGraph(ID, 'aaaa1111')
  const methods = fetchPart.fetchMethods({}, {}, () => 'session-x', () => ({}))
  return methods.ensureAnchors([ID, null, '', undefined]).then(() => {})
})

process.exitCode = failed === 0 ? 0 : 1
console.log(failed === 0 ? '\n全部通过' : '\n' + failed + ' 项失败')
