// 每个模块都能实例化，每个主组件都能渲染出东西来。
//
// 白屏的成因从来不是数字算错，是某个组件在渲染期抛了——一抛整棵树没了，
// 而布局测试全绿，因为它们只调 layout()，从不渲染。这个文件补的就是那一层：
// 模块能不能起，组件渲不渲得出，以及渲染量有没有上界。
//
//   node lens/scripts/build.js && node lens/tests/render-smoke.js
const fs = require('fs'), vm = require('vm'), assert = require('assert')

const factories = new Map(), cache = new Map()
let states = [], si = 0
const React = {
  createElement: (t, p, ...k) => ({ type: t, props: p || {}, kids: k.flat() }),
  Fragment: 'fragment',
  useState: v => {
    const i = si++
    if (states[i] === undefined) states[i] = typeof v === 'function' ? v() : v
    return [states[i], n => { states[i] = typeof n === 'function' ? n(states[i]) : n }]
  },
  useEffect: () => {}, useMemo: f => f(), useRef: v => ({ current: v }), useCallback: f => f,
}
const require_ = id => {
  if (id === 'react') return React
  if (cache.has(id)) return cache.get(id)
  assert(factories.has(id), 'missing module ' + id)
  const v = factories.get(id)(require_); cache.set(id, v); return v
}
const ctx = {
  window: {
    __ModuleLoader__: { load: r => factories.set(r.id, r.factory) },
    localStorage: { getItem: () => null, setItem: () => {} },
    matchMedia: () => ({ matches: false }),
    requestAnimationFrame: () => 0, cancelAnimationFrame: () => {},
    setInterval: () => 1, clearInterval: () => {},
    addEventListener: () => {}, removeEventListener: () => {},
    location: { origin: 'http://x' }, innerWidth: 1400, innerHeight: 900,
  },
  document: {
    querySelector: () => null, querySelectorAll: () => [],
    createElement: () => ({ style: {}, getContext: () => ({ measureText: () => ({ width: 40 }) }) }),
    head: { appendChild() {} }, body: { appendChild() {} },
    documentElement: { style: { setProperty() {}, removeProperty() {} } },
  },
  navigator: {}, MutationObserver: function () {},
  ResizeObserver: function () { this.observe = () => {}; this.disconnect = () => {} },
  URLSearchParams,
  fetch: () => Promise.resolve({ status: 200, json: () => Promise.resolve({}) }),
  console, JSON, Math, Number, Object, String, Array, isFinite,
  setTimeout, clearTimeout, setInterval, clearInterval,
}
vm.createContext(ctx)
vm.runInContext(fs.readFileSync('lib/client.js', 'utf8'), ctx, { filename: 'built.js' })

let bad = 0
const ids = [...factories.keys()]
const broken = ids.filter(id => { try { require_(id); return false } catch (e) { console.log('✗ ' + id + ' — ' + e.message.split('\n')[0]); return true } })
if (broken.length) bad += broken.length
console.log((broken.length ? '✗ ' : '✓ ') + '模块实例化'.padEnd(10) + (ids.length - broken.length) + '/' + ids.length)

const shared = require_('dsh-cdd-lens/state/store').shared
const model = require_('dsh-cdd-lens/graph/model')
const count = n => (!n || typeof n !== 'object') ? 0 : 1 + (n.kids || []).reduce((s, k) => s + count(k), 0)
const textOf = n => {
  if (n === null || n === undefined) return ''
  if (typeof n === 'string' || typeof n === 'number') return String(n)
  if (typeof n !== 'object') return ''
  return (n.kids || []).map(textOf).join('')
}
const assertUniqueSiblingKeys = (node, path = 'root') => {
  if (!node || typeof node !== 'object') return
  const kids = (node.kids || []).filter(k => k && typeof k === 'object')
  const seen = new Set()
  for (const kid of kids) {
    const key = kid.props && kid.props.key
    if (key !== undefined && key !== null) {
      assert(!seen.has(key), `duplicate sibling key ${String(key)} at ${path}`)
      seen.add(key)
    }
  }
  kids.forEach((kid, index) => assertUniqueSiblingKeys(kid, `${path}/${String(kid.type)}[${index}]`))
}
const engine = { outline: () => {}, fileSymbols: () => {}, focus: () => {}, params: () => ({ root: '/x' }) }

const render = (name, fn, floor) => {
  si = 0; states = []
  try {
    const out = fn()
    const n = count(out)
    const ok = n >= (floor === undefined ? 1 : floor)
    if (!ok) bad += 1
    console.log((ok ? '✓ ' : '✗ ') + name.padEnd(10) + '渲染出 ' + n + ' 个节点')
    return out
  } catch (e) {
    bad += 1
    console.log('✗ ' + name.padEnd(10) + '抛异常: ' + e.message.split('\n')[0])
    return null
  }
}

// 空图：工具栏和空态都要在
shared.graph = model.emptyGraph(); shared.trace = {}; shared.outline = undefined
const lensView = render('LensView', () => require_('dsh-cdd-lens/shell/graphView').LensView({ ctx: { on: () => () => {} } }), 3)
assertUniqueSiblingKeys(lensView)
console.log('✓ ' + 'React keys'.padEnd(10) + '每组同级节点的 key 唯一')
assert(!textOf(lensView).includes('铺满宽度'), '不可用的铺满宽度按钮必须从工具栏移除')
console.log('✓ ' + '工具栏'.padEnd(10) + '不再渲染铺满宽度按钮')

// 目录：真实规模。4566 个目录一次性进 DOM 就是一个卡死的标签页。
const many = []
for (let i = 0; i < 4566; i += 1) {
  many.push({ dir: 'p/pkg' + i, count: 6, files: [{ file: 'p/pkg' + i + '/a.js', count: 3 }] })
}
shared.outline = many
const tree = render('Outline', () => require_('dsh-cdd-lens/view/outline').Outline({ engine }), 5)
assert(count(tree) < 1200, '目录一屏渲染的节点数必须有上界，实际 ' + count(tree))
console.log('✓ ' + '目录上界'.padEnd(10) + '4566 个目录 → ' + count(tree) + ' 个节点')

// 目录读不出来：null 不许把整棵树带走
shared.outline = null
render('目录为 null', () => require_('dsh-cdd-lens/view/outline').Outline({ engine }), 1)

shared.outline = undefined

// 用真的 engine 渲染，不用手捏的。
//
// `cdd draw` 从来没打开过：Draw 调 engine.params()，而 makeEngine 只把 params
// 当参数传给各个方法工厂，从没挂到 engine 上。测试没抓到，是因为测试里的 engine
// 是我按 Draw 的需要捏的——stub 比真货能干，bug 就藏在这个差值里。
;(function realEngineHasWhatTheViewsCall() {
  const { makeEngine } = require_('dsh-cdd-lens/engine/engine')
  const real = makeEngine({ on: () => () => {}, emit: () => {} })
  const needed = ['params', 'outline', 'fileSymbols', 'focus', 'source', 'reindex']
  const missing = needed.filter(k => typeof real[k] !== 'function')
  if (missing.length) bad += 1
  console.log((missing.length ? '✗ ' : '✓ ') + '真 engine'.padEnd(10)
    + (missing.length ? '缺: ' + missing.join(', ') : needed.length + ' 个入口都在'))

  si = 0; states = []
  try {
    const out = require_('dsh-cdd-lens/view/outline').Draw({ engine: real })
    assert.equal(out.type, 'iframe', 'Draw must mount its paged shell on the first render')
    console.log('✓ ' + 'Draw'.padEnd(10) + '用真 engine 渲染出 ' + count(out) + ' 个节点')
  } catch (e) {
    bad += 1
    console.log('✗ ' + 'Draw'.padEnd(10) + '用真 engine 抛: ' + e.message.split('\n')[0])
  }
})()

// A steady draw-status response is not a state change. The poller used to
// compare against the first render captured by its effect, manufacture a new
// object on every 8-second poll, and repaint the toolbar forever.
;(function stableDrawStatusDoesNotRepaint() {
  const { drawStampAfter } = require_('dsh-cdd-lens/view/outline')
  const ready = { stamp: 123 }
  assert.strictEqual(drawStampAfter(ready, { ready: true, stamp: 123, building: false }), ready,
    'unchanged ready response must preserve state identity')
  assert.strictEqual(drawStampAfter(ready, { ready: false, stamp: 124, building: true }), ready,
    'a building response must leave the current shell mounted')
  const rebuilt = drawStampAfter(ready, { ready: true, stamp: 124, building: false })
  assert.notStrictEqual(rebuilt, ready, 'a new drawing stamp must repaint')
  assert.deepEqual(rebuilt, { stamp: 124 })
  console.log('✓ ' + 'Draw 轮询'.padEnd(10) + '稳定响应不再触发重渲染')
})()

// 错误边界：抛出去的东西必须变成看得见的字，而不是一块白。
;(function boundaryShowsTheError() {
  function Component(props) { this.props = props }
  Component.prototype.setState = function (next) { Object.assign(this.state, next) }
  const { makeBoundary } = require_('dsh-cdd-lens/shell/boundary')
  const Boundary = makeBoundary(Object.assign({}, React, { Component: Component }))
  if (Boundary === null) { bad += 1; console.log('✗ 错误边界    没能建立'); return }
  const b = new Boundary({ children: 'x' })
  b.state = Boundary.getDerivedStateFromError(new Error('故意炸一下'))
  const out = b.render()
  const flat = []
  ;(function walk(n) {
    if (n === null || n === undefined) return
    if (typeof n === 'string') { flat.push(n); return }
    if (Array.isArray(n)) { n.forEach(walk); return }
    ;(n.kids || []).forEach(walk)
  })(out)
  const text = flat.join(' ')
  const ok = text.indexOf('故意炸一下') >= 0 && text.indexOf('渲染失败') >= 0
  if (!ok) bad += 1
  console.log((ok ? '✓ ' : '✗ ') + '错误边界'.padEnd(10) + '抛出的话被显示出来：' + text.slice(0, 40) + '…')
})()

console.log(bad === 0 ? '\n✓ 渲染冒烟通过' : '\n' + bad + ' 处渲染问题')
process.exit(bad === 0 ? 0 : 1)
