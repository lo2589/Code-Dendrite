// Worker-level accuracy contract:
//  1. the neighbour count on a node IS what expand lists (self-loops excluded)
//  2. call+dataflow to the same peer is ONE neighbour, not two
//  3. verify reports which drawn nodes the index still holds
//  4. chain/neighbors/verify all carry the index stamp they answered from
const fs = require('fs'), os = require('os'), path = require('path')
const { Worker } = require('worker_threads')

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'lens-worker-'))
fs.mkdirSync(path.join(root, '.codedendrite'))
const anchor = (file, symbol, s, e, extra = {}) => ({ file, symbol, line_start: s, line_end: e, symbol_type: 'function', ...extra })
fs.writeFileSync(path.join(root, '.codedendrite', 'anchors.json'), JSON.stringify({
  // `callers` / `callees` 是 anchors.json 那一半，必须和边表说的一致：
  // 上下游现在是"边表 ∩ 记录字段"，夹具里两者打架的话，测的就不是代码了。
  'a.py::f': anchor('a.py', 'f', 1, 9, {
    hash: 'hash-of-f', qualified_name: 'f', imports: ['os'],
    callers: ['a.py::g', 'a.py::h'], callees: ['a.py::g'],
    mro: ['a.py::f'], own_methods: ['a.py::f'],
  }),
  'a.py::g': anchor('a.py', 'g', 10, 19, {
    hash: 'hash-of-g', qualified_name: 'g', imports: ['sys'],
    callers: ['a.py::f'], callees: ['a.py::f'],
  }),
  'a.py::h': anchor('a.py', 'h', 20, 29),
  'a.py::main': anchor('a.py', 'main', 30, 39),
  'a.py::main#if': anchor('a.py', 'main#if', 34, 37, {
    symbol_type: 'virtual_block',
    is_virtual: true,
    virtual_kind: 'condition',
    parent_anchor: 'a.py::main',
  }),
  'a.py::child': anchor('a.py', 'child', 40, 49),
  'frontend/src/app.ts::boot': anchor('frontend/src/app.ts', 'boot', 1, 9),
  'frontend/src/app.ts::renderThing': anchor('frontend/src/app.ts', 'renderThing', 10, 19),
  'node_modules/pkg/index.ts::vendored': anchor('node_modules/pkg/index.ts', 'vendored', 1, 9),
  'tests/stats.py::stats': anchor('tests/stats.py', 'stats', 1, 9),
}))
fs.writeFileSync(path.join(root, '.codedendrite', 'relations.json'), JSON.stringify({
  edges: [
    { from_id: 'a.py::f', to_id: 'a.py::g', edge_type: 'call' },
    { from_id: 'a.py::f', to_id: 'a.py::g', edge_type: 'dataflow' },
    { from_id: 'a.py::f', to_id: 'a.py::f', edge_type: 'call' },
    { from_id: 'a.py::g', to_id: 'a.py::f', edge_type: 'call' },
    { from_id: 'a.py::h', to_id: 'a.py::f', edge_type: 'call' },
    { from_id: 'a.py::main', to_id: 'a.py::main#if', edge_type: 'call' },
    { from_id: 'a.py::main#if', to_id: 'a.py::child', edge_type: 'call' },
  ],
}))

const worker = new Worker(path.join(__dirname, '..', 'src', 'index_worker.js'))
let seq = 0
const pending = new Map()
worker.on('message', (m) => {
  const p = pending.get(m.seq)
  if (p === undefined) return
  pending.delete(m.seq)
  m.ok ? p.resolve(m.data) : p.reject(new Error(m.error))
})
const ask = (op, query) => new Promise((resolve, reject) => {
  seq += 1
  pending.set(seq, { resolve, reject })
  worker.postMessage({ seq, op, root, query })
})

let failed = 0
const check = (name, cond) => {
  console.log((cond ? 'ok  ' : 'FAIL') + ' ' + name)
  if (!cond) failed += 1
}

async function main() {
const anchor_f = await ask('anchor', { id: 'a.py::f' })
const down = await ask('expand', { id: 'a.py::f', direction: 'down', rel: 'call' })
const up = await ask('expand', { id: 'a.py::f', direction: 'up', rel: 'call' })
check('self-loop not counted: f call down === 1', anchor_f.anchor.peerCounts.call.down === 1)
check('self-loop not listed: expand shows 1 peer', down.peers.length === 1)
check('expand returns same-snapshot source anchor', down.from.id === 'a.py::f' && down.count === down.peers.length)
// A DOM node IS an anchor: what CodeDendrite stored has to reach the browser,
// both for the node that is drawn and for every node an expand creates. A
// node carrying a stripped stub cannot draw itself or expand honestly.
const RECORD = ['hash', 'qualified_name', 'imports', 'callers', 'mro', 'own_methods', 'symbol_type']
const carried = (subject, stored) => RECORD
  .filter(f => stored[f] !== undefined)
  .every(f => JSON.stringify(subject[f]) === JSON.stringify(stored[f]))
check('a drawn node carries its whole stored anchor',
  carried(anchor_f.anchor, { hash: 'hash-of-f', qualified_name: 'f', imports: ['os'], callers: ['a.py::g', 'a.py::h'], callees: ['a.py::g'], mro: ['a.py::f'], own_methods: ['a.py::f'], symbol_type: 'function' }))
check('a node born from an expand carries its whole stored anchor',
  carried(down.peers[0], { hash: 'hash-of-g', qualified_name: 'g', imports: ['sys'], callers: ['a.py::f'], symbol_type: 'function' }))
check('the anchor beside an expand result is the same record',
  carried(up.from, { hash: 'hash-of-f', qualified_name: 'f', callers: ['a.py::g', 'a.py::h'] }))
check('button count === expand count (down)', anchor_f.anchor.peerCounts.call.down === down.peers.length)
check('button count === expand count (up)', anchor_f.anchor.peerCounts.call.up === up.peers.length && up.peers.length === 2)
// 邻居只由 call 决定，线也只画那条 call 边：出和入不许共用一条边，types 不许多挂。
check('a peer reached by call is one neighbour, wired as call',
  down.peers[0].id === 'a.py::g' && down.peers[0].types.length === 1 && down.peers[0].types[0] === 'call')
check('expand carries stamp', typeof down.stamp === 'string')

const ver = await ask('verify', { ids: ['a.py::f', 'a.py::gone'] })
check('verify keeps the living', ver.nodes[0].id === 'a.py::f' && ver.nodes[0].missing === undefined)
check('verify reports the gone', ver.nodes[1].missing === true)
check('verify carries stamp', typeof ver.stamp === 'string')

// /chain 已删：分层现在由布局自己算（client/layout/sugiyama）。
// 链式展开走 /walk：一次请求拿到 a → b → c 整条链。
const walked = await ask('walk', { id: 'a.py::f', direction: 'down', rel: 'call', depth: 4 })
check('walk carries stamp', typeof walked.stamp === 'string')
check('walk follows the chain f -> g (g calls back to f, already seen)',
  walked.nodes.length === 2 && walked.edges.length >= 1)
const walkedUp = await ask('walk', { id: 'a.py::g', direction: 'up', rel: 'call', depth: 4 })
check('walk upstream of g reaches f then its callers',
  walkedUp.nodes.map(n => n.id).sort().join(',') === 'a.py::f,a.py::g,a.py::h')

const stats = await ask('stats', {})
check('stats hides virtual anchors', stats.anchors === 9)
const mainAnchor = await ask('anchor', { id: 'a.py::main' })
const mainDown = await ask('expand', { id: 'a.py::main', direction: 'down', rel: 'call' })
check('virtual block folded out of neighbour count', mainAnchor.anchor.peerCounts.call.down === 1)
check('expand skips virtual block and reaches real child',
  mainDown.peers.length === 1 && mainDown.peers[0].id === 'a.py::child')
const virtualBlock = await ask('anchor', { id: 'a.py::main#if' })
check('virtual block stays hidden if addressed directly', virtualBlock.anchor.hidden === true)
const virtualSearch = await ask('search', { q: 'main#if', limit: 8 })
check('search hides virtual blocks', virtualSearch.hits.length === 0)
// 虚块折叠现在靠 /walk：从 main 往下走，穿虚拟块摸到真节点 child。
const foldedChain = { trees: [{ nodes: (await ask('walk', { id: 'a.py::main', direction: 'down', rel: 'call', depth: 4 })).nodes.map(n => ({ id: n.id })) }] }
const foldedIds = foldedChain.trees.flatMap(tree => tree.nodes.map(node => node.id))
check('chain folds virtual blocks out',
  foldedIds.includes('a.py::child') && !foldedIds.includes('a.py::main#if'))

const ts = await ask('search', { q: 'ts', limit: 8 })
check('short ts search means TypeScript, not tests/stats noise',
  ts.hits.length >= 2
  && ts.hits[0].file === 'frontend/src/app.ts'
  && ts.hits.every(hit => hit.file !== 'tests/stats.py'))
const dotTs = await ask('search', { q: '.ts', limit: 8 })
check('.ts extension search only returns TypeScript files',
  dotTs.hits.length >= 2 && dotTs.hits.every(hit => hit.file.endsWith('.ts')))
check('extension search keeps vendored files behind project files',
  dotTs.hits[0].file === 'frontend/src/app.ts')
}

main().then(() => {
worker.terminate()
fs.rmSync(root, { recursive: true, force: true })
console.log(failed === 0 ? 'ALL PASS' : failed + ' FAILED')
process.exit(failed === 0 ? 0 : 1)
})
