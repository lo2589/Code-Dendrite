// Contract test for the persistent trajectory sidebar.
const assert = require('assert')
const fs = require('fs')
const vm = require('vm')

const factories = new Map(), cache = new Map()
const React = {
  createElement: (type, props, ...children) => ({ type, props: props || {}, children }),
  Fragment: 'fragment',
  useState: value => [typeof value === 'function' ? value() : value, () => {}],
  useEffect: () => {}, useMemo: fn => fn(), useRef: value => ({ current: value }),
  useCallback: fn => fn,
}
const require_ = id => {
  if (id === 'react') return React
  if (cache.has(id)) return cache.get(id)
  assert(factories.has(id), `missing module ${id}`)
  const value = factories.get(id)(require_)
  cache.set(id, value)
  return value
}
const context = {
  window: {
    __ModuleLoader__: { load: item => factories.set(item.id, item.factory) },
    localStorage: { getItem: () => null, setItem: () => {} },
    matchMedia: () => ({ matches: false }),
    requestAnimationFrame: fn => { fn(); return 1 }, cancelAnimationFrame: () => {},
    setInterval: fn => { fn(); return 1 }, clearInterval: () => {},
    addEventListener: () => {}, removeEventListener: () => {}, location: { origin: 'http://x' },
  },
  document: {}, navigator: {}, MutationObserver: function () {},
  URLSearchParams, fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
  console, JSON, Math, Number, Object, String, Array, isFinite,
  setTimeout, clearTimeout, setInterval, clearInterval,
}
vm.createContext(context)
vm.runInContext(fs.readFileSync('lib/client.js', 'utf8'), context)

const stream = require_('dsh-cdd-lens/view/stream')
const shared = require_('dsh-cdd-lens/state/store').shared

shared.trace = {
  'src/a.py::a': { events: [
    { turn: 2, step: 3, verb: 'read', tool: 'read', onSurface: false },
    { turn: 2, step: 3, verb: 'edit', tool: 'edit', onSurface: false },
  ] },
  'src/b.py::b': { events: [
    { turn: 4, step: 1, verb: 'read', tool: 'read', onSurface: true },
  ] },
}
shared.unresolved = [{ file: 'src/missing.py', reason: 'no-line', steps: [{ turn: 2, step: 4, verb: 'read' }] }]

const rows = stream.stepsOf()
assert.equal(rows.length, 3, 'compacted rows remain in the persistent trajectory')
assert.equal(rows[0].verb, 'edit', 'one step keeps its strongest edit state')
assert.deepEqual(stream.groupRows(rows).map(turn => [turn.turn, turn.steps.length]), [[2, 2], [4, 1]])

let clicked = false
const nativeButton = { getAttribute: () => '跳转到第 4 轮', click: () => { clicked = true } }
context.document.querySelectorAll = selector => selector === 'button[aria-label]' ? [nativeButton] : []
assert.equal(stream.jumpToChatTurn(4), true)
assert.equal(clicked, true, 'sidebar delegates turn paging to Chat native navigation')

shared.graph = { nodes: { 'src/a.py::a': {} } }
let revealed = null
stream.locateInGraph({ get: () => undefined }, {
  reveal: id => { revealed = id; return Promise.resolve() },
}, 'src/a.py::a')
assert.equal(shared.dockOpen, true, 'locate opens the graph dock')
assert.equal(revealed, 'src/a.py::a', 'locate reveals an existing graph node')

const row2 = { dataset: { chatTurn: '2' }, getBoundingClientRect: () => ({ top: 10 }) }
const row4 = { dataset: { chatTurn: '4' }, getBoundingClientRect: () => ({ top: 240 }) }
const scroller = {
  scrollHeight: 1000, scrollTop: 100, clientHeight: 500,
  querySelectorAll: () => [row2, row4],
  getBoundingClientRect: () => ({ top: 0, width: 500 }), contains: () => true,
}
context.document.elementsFromPoint = () => []
assert.equal(stream.turnAtReadingLine(scroller), 2)

const bundle = fs.readFileSync('lib/client.js', 'utf8')
const overlayStart = bundle.indexOf('function LensOverlay')
const overlayEnd = bundle.indexOf('module.exports', overlayStart)
const overlayBody = bundle.slice(overlayStart, overlayEnd)
assert(bundle.includes('data-cdd-trajectory'))
// The rail overlays the margin beside the conversation; it does NOT push the
// page aside. Reserving room squeezed the graph — the thing the panel exists to
// show — and on any tab where the rail did not paint, the reserved band was
// left behind as an empty white strip. dsh-lifecycle's rail reserves nothing
// either. This asserts the reservation stays gone.
assert(!bundle.includes('body:has(.cddl-trajectory) #root'),
  'the trajectory rail must not reserve room in #root')
assert(bundle.includes('cddl-trajectory.is-collapsed'))
assert(bundle.includes('.cddl-trajectory-toggle{display:block}'))
// The shut width is one named token, not the same number written out wherever
// something has to agree with it.
assert(bundle.includes('--cddl-rail-shut'))
assert(bundle.includes('width:var(--cddl-rail-shut)!important'))
// One placement, one layout: the layered sugiyama pass decides where every node
// goes. No skins, so there is no "which placement" branch left to disagree with.
assert(bundle.includes('function sugiyama'))
assert(bundle.includes("p.flowDir = 'ltr'"))
// 出入口是左右各一个小圈：入在左、出在右，不同口。线两头停在这个圈心上。
assert(bundle.includes("className: 'cddl-port cddl-port-in'"))
assert(bundle.includes("className: 'cddl-port cddl-port-out'"))
assert(bundle.includes('.cddl-port-in{left:-6px'))
assert(bundle.includes('.cddl-port-out{right:-6px'))
assert(bundle.includes('width:11px;height:11px'))
assert(bundle.includes('var PORT_OFFSET = 0.5'))
// Two or three boxes across; the box stays the width of its widest name and
// the width the row does not need goes into the gutters.
assert(bundle.includes('WIDEST_ROW'))
assert(bundle.includes('COL_STRIDE'))
// Every grid size is a multiple of the one measured quantity, so the whole
// drawing follows the type size instead of a dozen loose pixel constants.
assert(bundle.includes('var em = function (k)'))
// A card's height is read off the stylesheet that draws it, not written down
// beside it: the layout has to reserve exactly what the card takes, and two
// numbers for one thing in two files drift.
assert(bundle.includes('function cardBox'))
assert(bundle.includes("pxFrom(css, '.cddl-gnode', 'padding')"))
assert(!bundle.includes('70 + wrapped'), 'card height must not be a literal')
assert(!/var (PAD|BOX_PAD|BOX_HEAD|BOX_GAP_X|BOX_GAP_Y|INNER_GAP_X|INNER_GAP_Y|PORT_CLEAR|PORT_STUB|ARROW_EVERY) = \d/.test(bundle),
  'grid sizes must be derived from CHAR_W, not written as pixels')
// Shelf packing of variable-width blocks is gone with it: rows of equal boxes
// need no area heuristic to decide how wide the drawing should be.
assert(!bundle.includes('Math.sqrt(area'))
assert(bundle.includes('overflow-wrap:anywhere;white-space:normal'))
assert(bundle.includes("'aria-label': collapsed ? '展开代码轨迹' : '收起代码轨迹'"))
assert(bundle.includes("'data-locate-anchor-id': row.id"))
assert(bundle.includes('.cddl-view-docked .cddl-toolbar{flex-wrap:nowrap'))
assert(bundle.includes('.cddl-view-docked>.cddl-legend{display:none}'))
assert(!bundle.includes('.cddl-trajectory-toggle{display:none}'))
assert(bundle.includes("window.matchMedia('(max-width:720px)')"))
assert(bundle.includes('Expanded rows survive reloads'))
assert(bundle.includes("--cddl-trajectory-top', top + 'px"))
assert(bundle.includes('header:has([role="tablist"])'))
assert(bundle.includes("tabs.closest('header')"))
assert(bundle.includes('z-index:var(--cddl-trajectory-layer,18)'))
assert(bundle.includes('z-index:var(--cddl-header-layer,19)'))
assert(bundle.includes('z-index:var(--cddl-dock-layer,18)'))
assert(!bundle.includes('cddl-trajectory{position:fixed;right:0;top:var(--cddl-trajectory-top,0);bottom:0;z-index:500'))
assert(!bundle.includes('top:var(--cddl-trajectory-top,76px)'))
assert(!/cddl-trace-anchor[^\n]*cddl-faded/.test(bundle), 'trajectory anchors never receive the graph fade class')
assert(overlayBody.includes('h(LensRuntime'), 'headless runtime stays mounted to ingest the live trace')
assert(!overlayBody.includes('h(LensPanel'), 'retired floating panel is not mounted')

console.log('✓ persistent sidebar keeps compacted history, groups turns, follows Chat, and uses native turn jumps')
