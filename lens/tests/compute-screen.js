// 计算单元契约（lens/src/compute）：
//   1 新 anchor 保留原始字段、只补「关系名+up/down」；call 读原生字段并过滤到只剩 anchor
//   2 write 取整个文件；edit 改后文本找不到就找改前文本
//   3 只有 read/edit/write 的 turn 才算一轮；计数器 3、每轮 -1；edit 一直留
//   4 1 度树；2 度树头叶必须是 seed（a-b-c*-d-e* 只留 c*-d-e*）；不在树里的 seed 堆一边
//   5 pin：计数器不减、取消 pin 再减；搜索 pin 进当前树，有什么边连什么边
//   6 按钮数 = 展开数 = 画出的边；展开连已有、连不上建新
//   7 关掉关系 → 该关系的展开、按钮、边都没有；每棵树的节点数和关系数与选中时的屏幕一致
//   8 worker 的 screen 操作与直接计算一致
'use strict'
const fs = require('fs')
const path = require('path')
const { Worker } = require('worker_threads')
const { fromIndex, peers } = require('../src/compute/anchors.js')
const { touchesFromEvents } = require('../src/compute/evidence.js')
const { screenFor } = require('../src/compute/screen.js')

const root = path.join(__dirname, '..', '..', '.cache', 'tests', 'compute-screen-' + process.pid)
fs.mkdirSync(path.join(root, '.codedendrite'), { recursive: true })

const FUNCS = ['f', 'g', 'h', 'k', 'lonely', 'p', 'q', 'x']
const lineText = (name, n) => `# line ${n} of function ${name} here`
const aLines = FUNCS.flatMap((name, i) => [1, 2, 3, 4, 5].map(j => lineText(name, i * 5 + j)))
fs.writeFileSync(path.join(root, 'a.py'), aLines.join('\n') + '\n')
fs.writeFileSync(path.join(root, 'b.py'), Array.from({ length: 10 }, (_, i) => `# b.py line ${i + 1} body`).join('\n') + '\n')

const fn = (file, symbol, start, extra = {}) => ({
  id: `${file}::${symbol}`, file, symbol, line_start: start, line_end: start + 4, symbol_type: 'function', hash: 'h-' + symbol, ...extra,
})
const raw = {}
;[
  fn('a.py', 'f', 1, { callees: ['a.py::g', 'print'] }),
  fn('a.py', 'g', 6, { callers: ['a.py::f'] }),
  fn('a.py', 'h', 11, { callers: ['a.py::q'], callees: ['a.py::x', 'len'] }),
  fn('a.py', 'k', 16, { callers: ['a.py::x'] }),
  fn('a.py', 'lonely', 21),
  fn('a.py', 'p', 26, { callees: ['a.py::q'] }),
  fn('a.py', 'q', 31, { callers: ['a.py::p'], callees: ['a.py::h'] }),
  fn('a.py', 'x', 36, { callers: ['a.py::h'], callees: ['a.py::k'] }),
  fn('b.py', 'w1', 1),
  fn('b.py', 'w2', 6),
].forEach(a => { raw[a.id] = a })
const edge = (from, to, type, extra = {}) => ({ from_id: `a.py::${from}`, to_id: `a.py::${to}`, edge_type: type, ...extra })
const relations = { edges: [
  edge('f', 'g', 'call'), edge('p', 'q', 'call'), edge('q', 'h', 'call'), edge('h', 'x', 'call'), edge('x', 'k', 'call'),
  edge('f', 'g', 'dataflow', { data_in: 'a' }), edge('f', 'g', 'dataflow', { data_in: 'b' }), edge('x', 'k', 'dataflow'),
] }
fs.writeFileSync(path.join(root, '.codedendrite', 'anchors.json'), JSON.stringify(raw))
fs.writeFileSync(path.join(root, '.codedendrite', 'relations.json'), JSON.stringify(relations))

let seq = 0
const rows = []
const call = (turn, step, id, name, args, meta) => {
  rows.push({ type: 'tool/call', seq: ++seq, data: { turn, step, callId: id, name, arguments: JSON.stringify(args) } })
  rows.push({ type: 'tool/result', seq: ++seq, data: { turn, step, message: { role: 'tool', content: [{ type: 'tool-result', toolCallId: id, isError: false }] }, meta } })
}
const abs = file => path.join(root, file)
const readMeta = (file, from, to) => ({ path: abs(file), offset: from, lines: Array.from({ length: to - from + 1 }, (_, i) => ({ number: from + i, text: '' })) })
call(1, 1, 'c1', 'read', { file_path: abs('a.py') }, readMeta('a.py', 1, 10))
call(2, 1, 'c2', 'read', { file_path: abs('a.py') }, readMeta('a.py', 11, 25))
call(3, 1, 'c3', 'write', { file_path: abs('b.py'), content: 'whatever' }, { diffs: [] })
call(3, 2, 'c4', 'edit', { file_path: abs('a.py') }, { diffs: [{ path: abs('a.py'), oldText: lineText('g', 7), newText: 'this replacement text is nowhere in the file' }] })
call(4, 1, 'c5', 'bash', { command: 'ls' }, {})
call(5, 1, 'c6', 'read', { file_path: abs('a.py') }, readMeta('a.py', 11, 15))

let failed = 0
const check = (name, cond) => {
  console.log((cond ? 'ok  ' : 'FAIL') + ' ' + name)
  if (!cond) failed += 1
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b)
const A = id => 'a.py::' + id
const ONLY_CALL = { call: true, dataflow: false, inherit: false, dispatch: false, impact: false }

const ctx = fromIndex(root, raw, relations.edges)
const touches = touchesFromEvents(rows)
const screen = state => screenFor(ctx, touches, state)
const shown = s => new Set([...s.nodes, ...s.side])
const all = []
const keep = s => { all.push(s); return s }

// 1 新 anchor
check('原始字段原样保留', same(Object.keys(raw[A('g')]).map(k => ctx.anchors[A('g')][k]), Object.values(raw[A('g')])))
check('补 dataflowup 且去重', same(ctx.anchors[A('g')].dataflowup, [A('f')]))
check('call 不补字段', ctx.anchors[A('f')].calldown === undefined && ctx.anchors[A('g')].callup === undefined)
check('call 读原生字段并滤掉裸名字', same(peers(ctx, A('f'), 'call', 'down'), [A('g')]))
check('节点上的 callees 不含裸名字：字段长度 = 按钮数字', same(ctx.anchors[A('f')].callees, [A('g')]) && raw[A('f')].callees.includes('print'))

// 2、3 证据与轮次
const s4 = keep(screen({ turn: 4, tree: 'degree1' }))
check('write 取整个文件的 anchor', s4.edited.includes('b.py::w1') && s4.edited.includes('b.py::w2'))
check('edit 改后文本找不到就用改前文本', s4.edited.includes(A('g')))
check('没有 read/edit/write 的 turn 不算一轮（T4 f 还在）', shown(s4).has(A('f')))
const s5 = keep(screen({ turn: 5, tree: 'degree1' }))
check('过 3 轮计数器归零（T5 f 撤下）', !shown(s5).has(A('f')))
check('edit 过的一直留', shown(s5).has(A('g')) && shown(s5).has('b.py::w1'))
check('再看一次续命（T5 h 还在）', shown(s5).has(A('h')) && s5.counter[A('h')] === 2)

// 4 树与旁边
const d1 = keep(screen({ turn: 2, tree: 'degree1' }))
check('1 度树只有 seed 直连', same(d1.nodes, [A('f'), A('g')]))
check('不在树里的 seed 堆一边', same(d1.side, [A('h'), A('k'), A('lonely')]))
check('一条边一种类型（call、dataflow 各一条）', d1.edges.length === 2 && new Set(d1.edges.map(e => e.type)).size === 2)
const d2 = keep(screen({ turn: 2, tree: 'degree2', rels: ONLY_CALL }))
check('2 度树连上 h→x→k', ['h', 'x', 'k'].every(id => d2.nodes.includes(A(id))))
check('2 度树剪掉非 seed 头 p、q', !d2.nodes.includes(A('p')) && !d2.nodes.includes(A('q')))
check('2 度树头叶全是 seed、中间点 1 个', d2.trees.call.badLeaves === 0 && d2.trees.call.middles === 1)
check('2 度树连不上的 seed 在旁边', same(d2.side, [A('lonely')]))

// 5 pin
const frozen = keep(screen({ turn: 5, tree: 'degree1', pins: [{ id: A('f'), at: 1 }] }))
check('pin 期间计数器不减（T5 f 仍是 3）', frozen.counter[A('f')] === 3 && frozen.nodes.includes(A('f')))
const unpinned = keep(screen({ turn: 5, tree: 'degree1', pins: [{ id: A('f'), at: 1, until: 3 }] }))
check('取消 pin 后再开始减（T5 f 剩 1）', unpinned.counter[A('f')] === 1 && shown(unpinned).has(A('f')))
const pinLonely = keep(screen({ turn: 2, tree: 'degree1', pins: [{ id: A('lonely'), at: 2 }] }))
check('pin 的节点进当前树、不在旁边', pinLonely.nodes.includes(A('lonely')) && !pinLonely.side.includes(A('lonely')))
const pinX = keep(screen({ turn: 2, tree: 'degree1', pins: [{ id: A('x'), at: 2 }] }))
check('搜索 pin 一个非 seed：有什么边连什么边', pinX.edges.some(e => e.from === A('h') && e.to === A('x'))
  && pinX.edges.some(e => e.from === A('x') && e.to === A('k')))
check('搜索 pin 连上的旁边 seed 进树', pinX.nodes.includes(A('h')) && pinX.nodes.includes(A('k')) && same(pinX.side, [A('lonely')]))

// 6 展开
const opens = [{ id: A('h'), rel: 'call', dir: 'down' }, { id: A('x'), rel: 'call', dir: 'down' }]
const ex = keep(screen({ turn: 2, tree: 'degree1', opens }))
check('旁边的节点能展开，按钮数 = 展开数', ex.buttons[A('h')].calldown === 1 && ex.expansions[0].count === 1 && ex.expansions[0].fresh === 1)
check('展开出来的节点能继续展开，连已有节点', ex.expansions[1].count === 1 && ex.expansions[1].fresh === 0)
check('被连上的 seed 从旁边进树', ex.nodes.includes(A('k')) && !ex.side.includes(A('k')))
check('画出的边就是展开的边', ex.edges.some(e => e.from === A('h') && e.to === A('x') && e.type === 'call')
  && ex.edges.some(e => e.from === A('x') && e.to === A('k') && e.type === 'call'))

// 7 关系开关、每棵树的数
const off = keep(screen({ turn: 2, tree: 'degree1', rels: { call: false }, opens }))
check('关掉 call：展开不生效', off.expansions.every(x => x.skipped === 'relation-off'))
check('关掉 call：没有 call 边、没有 call 按钮', off.edges.every(e => e.type !== 'call')
  && Object.values(off.buttons).every(b => Object.keys(b).every(k => !k.startsWith('call'))))
check('三棵树都报节点数和关系数', ['degree1', 'degree2', 'edit'].every(m => Number.isInteger(pinX.treeTotals[m].nodes) && Number.isInteger(pinX.treeTotals[m].edges)))
check('当前树的数字 = 屏幕', all.every(s => s.treeTotals[s.tree].nodes === s.nodes.length && s.treeTotals[s.tree].edges === s.edges.length))
check('以上所有屏幕没有违例', all.every(s => s.violations.length === 0))
const partial = screenFor(ctx, touches, { turn: 2, tree: 'degree1' }, [A('f')])
check('前端已有的 anchor 不再重发（节点照样在屏幕上）', partial.anchors[A('f')] === undefined && partial.anchors[A('g')] !== undefined && partial.nodes.includes(A('f')))

// 8 worker
const worker = new Worker(path.join(__dirname, '..', 'src', 'index_worker.js'))
const ask = (op, query) => new Promise((resolve, reject) => {
  worker.once('message', m => (m.ok ? resolve(m.data) : reject(new Error(m.error))))
  worker.postMessage({ seq: 1, op, root, query })
})
ask('screen', { touches, state: { turn: 2, tree: 'degree2', rels: ONLY_CALL } }).then((viaWorker) => {
  check('worker screen 与直接计算一致', same(viaWorker.nodes, d2.nodes) && same(viaWorker.side, d2.side) && typeof viaWorker.stamp === 'string')
}).catch((error) => {
  check('worker screen 可调用: ' + error.message, false)
}).finally(() => {
  worker.terminate()
  fs.rmSync(root, { recursive: true, force: true })
  console.log(failed === 0 ? 'ALL PASS' : failed + ' FAILED')
  process.exit(failed === 0 ? 0 : 1)
})
