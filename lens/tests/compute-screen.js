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
  edge('f', 'g', 'dataflow', { data_in: 'a', evidence: 'strict-dataflow:relay' }), edge('f', 'g', 'dataflow', { data_in: 'b', evidence: 'strict-dataflow:relay+return' }),
  edge('x', 'k', 'dataflow', { evidence: 'strict-dataflow:return' }),
  // 反例：dataflow 只算 return / relay。arg 就是 call，state（self.x 写 → 读）只是两个定义，没有证据的是生成器兜底——都不算。
  edge('p', 'q', 'dataflow', { evidence: 'strict-dataflow:arg' }), edge('q', 'h', 'dataflow', { evidence: 'strict-dataflow:state' }),
  edge('h', 'x', 'dataflow', { evidence: 'strict-dataflow:arg+state' }), edge('lonely', 'x', 'dataflow', { data_out: 'str, int' }),
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
check('dataflow 不算 arg / state / arg+state / 无证据：不补字段', ['p', 'q', 'h', 'lonely'].every(id => ctx.anchors[A(id)].dataflowdown === undefined)
  && ['q', 'h'].every(id => ctx.anchors[A(id)].dataflowup === undefined) && same(ctx.anchors[A('x')].dataflowdown, [A('k')]) && ctx.anchors[A('x')].dataflowup === undefined)
check('dataflow 不算的边不出按钮', peers(ctx, A('q'), 'dataflow', 'up').length === 0 && peers(ctx, A('x'), 'dataflow', 'up').length === 0)
{
  const { countsAsRelation } = require(path.join(__dirname, '..', 'src', 'compute', 'anchors.js'))
  check('老索引没有 evidence：data_out 是 kind 名照认、是类型名不认；其它关系原样算',
    countsAsRelation({ edge_type: 'dataflow', data_out: 'relay+return' }) && !countsAsRelation({ edge_type: 'dataflow', data_out: 'arg' })
    && !countsAsRelation({ edge_type: 'dataflow', data_out: 'str, int' }) && countsAsRelation({ edge_type: 'call' }) && countsAsRelation({ edge_type: 'inherit' }))
}
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
check('edit 过的在计时内（T5 g、b.py::w1 还在）', shown(s5).has(A('g')) && shown(s5).has('b.py::w1'))
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

// 5b edit 计时器：每个节点自己管自己，edit 一次 +editKeep 轮（默认 7，可设），过一轮 -1，到 0 不再算 edit；pin 不减
{
  const { seedsAt, normalizeEditKeep } = require(path.join(__dirname, '..', 'src', 'compute', 'evidence.js'))
  const rounds = (n, extra) => Array.from({ length: n }, (_, i) => ({ turn: i + 1, verb: 'read', anchors: ['z.py::tick'] })).concat(extra)
  const ev = rounds(12, [{ turn: 1, verb: 'edit', anchors: ['e.py::a'] }])
  check('edit 默认留 7 轮：T7 剩 1、T8 不再算 edit', seedsAt(ev, 7).editTimer.get('e.py::a') === 1 && !seedsAt(ev, 8).edited.has('e.py::a'))
  const again = rounds(12, [{ turn: 1, verb: 'edit', anchors: ['e.py::a'] }, { turn: 3, verb: 'edit', anchors: ['e.py::a'] }])
  check('轮数内再 edit：剩下的 +7（T3 = 5 + 7 = 12）', seedsAt(again, 3).editTimer.get('e.py::a') === 12 && seedsAt(again, 12).edited.has('e.py::a'))
  check('可以设：editKeep=2 → T2 还算、T3 不算', seedsAt(ev, 2, [], { editKeep: 2 }).edited.has('e.py::a') && !seedsAt(ev, 3, [], { editKeep: 2 }).edited.has('e.py::a'))
  check('pin 住 edit 计时器不减', seedsAt(ev, 12, [{ id: 'e.py::a', at: 1, until: null }]).editTimer.get('e.py::a') === 7)
  const both = rounds(12, [{ turn: 1, verb: 'edit', anchors: ['e.py::a'] }, { turn: 6, verb: 'read', anchors: ['e.py::a'] }])
  check('两个计数自己管自己：edit 到 0 时看过的还在 → 仍是 seed', !seedsAt(both, 8).edited.has('e.py::a') && seedsAt(both, 8).seeds.has('e.py::a'))
  check('设置不合法回到 7', normalizeEditKeep(0) === 7 && normalizeEditKeep(100) === 7 && normalizeEditKeep('x') === 7 && normalizeEditKeep(3) === 3)
  const withKeep = screen({ turn: 5, tree: 'edit', editKeep: 2 })
  check('屏幕带 editKeep 和每个节点的 edit 计时', withKeep.editKeep === 2 && withKeep.editTimer !== null && typeof withKeep.editTimer === 'object')
}

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
