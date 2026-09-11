// Worker-level accuracy contract:
//  1. the neighbour count on a node IS what expand lists (self-loops excluded)
//  2. call+dataflow to the same peer is ONE neighbour, not two
//  3. verify reports which drawn nodes the index still holds
//  4. chain/neighbors/verify all carry the index stamp they answered from
const fs = require('fs'), os = require('os'), path = require('path')
const { Worker } = require('worker_threads')

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'lens-worker-'))
fs.mkdirSync(path.join(root, '.codedendrite'))
const anchor = (file, symbol, s, e) => ({ file, symbol, line_start: s, line_end: e, symbol_type: 'function' })
fs.writeFileSync(path.join(root, '.codedendrite', 'anchors.json'), JSON.stringify({
  'a.py::f': anchor('a.py', 'f', 1, 9),
  'a.py::g': anchor('a.py', 'g', 10, 19),
  'a.py::h': anchor('a.py', 'h', 20, 29),
}))
fs.writeFileSync(path.join(root, '.codedendrite', 'relations.json'), JSON.stringify({
  edges: [
    { from_id: 'a.py::f', to_id: 'a.py::g', edge_type: 'call' },
    { from_id: 'a.py::f', to_id: 'a.py::g', edge_type: 'dataflow' },
    { from_id: 'a.py::f', to_id: 'a.py::f', edge_type: 'call' },
    { from_id: 'a.py::g', to_id: 'a.py::f', edge_type: 'call' },
    { from_id: 'a.py::h', to_id: 'a.py::f', edge_type: 'call' },
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
const down = await ask('neighbors', { id: 'a.py::f', direction: 'down' })
const up = await ask('neighbors', { id: 'a.py::f', direction: 'up' })
check('self-loop not counted: f.down === 1', anchor_f.anchor.down === 1)
check('self-loop not listed: expand shows 1 peer', down.peers.length === 1)
check('button count === expand count (down)', anchor_f.anchor.down === down.peers.length)
check('button count === expand count (up)', anchor_f.anchor.up === up.peers.length && up.peers.length === 2)
check('call+dataflow to one peer is one neighbour', down.peers[0].id === 'a.py::g' && down.peers[0].types.length === 2)
check('neighbors carries stamp', typeof down.stamp === 'string')

const ver = await ask('verify', { ids: ['a.py::f', 'a.py::gone'] })
check('verify keeps the living', ver.nodes[0].id === 'a.py::f' && ver.nodes[0].missing === undefined)
check('verify reports the gone', ver.nodes[1].missing === true)
check('verify carries stamp', typeof ver.stamp === 'string')

const chain = await ask('chain', { ids: 'a.py::f', hops: 1 })
check('chain carries stamp', typeof chain.stamp === 'string')
check('chain self-loop out of layering: f and g on layers', chain.trees.length === 1)
}

main().then(() => {
worker.terminate()
fs.rmSync(root, { recursive: true, force: true })
console.log(failed === 0 ? 'ALL PASS' : failed + ' FAILED')
process.exit(failed === 0 ? 0 : 1)
})
