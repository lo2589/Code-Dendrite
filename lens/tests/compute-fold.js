// 文件框折叠（src/compute/fold.js）：超过 5 个折叠，只留调用链上游的和 pin / 展开的；点开全画；被折叠的边不画。
const assert = require('assert')
const { foldBoxes, callLevels, FOLD_LIMIT } = require('../src/compute/fold.js')

// x.py 的调用链：A → A.m1 → A.m2 → A.m3，A → B → B.n1 → B.n1.deep；C.c1 没人调用
const calls = {
  'x.py::A': ['x.py::A.m1', 'x.py::B'],
  'x.py::A.m1': ['x.py::A.m2'],
  'x.py::A.m2': ['x.py::A.m3'],
  'x.py::B': ['x.py::B.n1'],
  'x.py::B.n1': ['x.py::B.n1.deep'],
}
const ids = ['x.py::A', 'x.py::A.m1', 'x.py::A.m2', 'x.py::A.m3', 'x.py::B', 'x.py::B.n1', 'x.py::B.n1.deep', 'x.py::C.c1', 'y.py::Z',
  's.py::s1', 's.py::s2', 's.py::s3', 's.py::s4', 's.py::s5', 's.py::s6']
const anchors = {}
ids.forEach((id, i) => {
  const callers = Object.keys(calls).filter(c => calls[c].includes(id))
  anchors[id] = { id, file: id.split('::')[0], symbol: id.split('::')[1], line_start: i + 1, callees: calls[id] || [], callers }
})
const ctx = { anchors, visible: new Set(ids) }
const tree = ids.slice(0, 9)
const side = ids.slice(9)
// 屏幕上的边：A.m2、A.m3 有边（连线多），A.m1 一条边都没有——要证明按调用链上游排，不是按边多排
const edges = [
  { from: 'x.py::A', to: 'x.py::B', type: 'call' },
  { from: 'x.py::A.m2', to: 'y.py::Z', type: 'dataflow' },
  { from: 'x.py::A.m3', to: 'y.py::Z', type: 'dataflow' },
  { from: 'x.py::B.n1.deep', to: 'y.py::Z', type: 'call' },
]
const forced = new Set(['x.py::B.n1.deep', 'x.py::C.c1'])
const layerOf = () => ({ nodes: new Set(tree), edges: edges.map(e => ({ ...e })) })

const level = callLevels(ctx, [...tree, ...side])
assert.deepStrictEqual(['x.py::A', 'x.py::A.m1', 'x.py::B', 'x.py::A.m2', 'x.py::B.n1', 'x.py::A.m3'].map(id => level.get(id)), [0, 1, 1, 2, 2, 3],
  '调用链层级：A 是入口 0 层，A.m1 / B 第 1 层，A.m2 / B.n1 第 2 层，A.m3 第 3 层')

const shut = layerOf()
const out = foldBoxes(ctx, shut, side, forced, [])
assert.strictEqual(FOLD_LIMIT, 5)
assert.deepStrictEqual(out.folds['tree:x.py'], { total: 8, shown: 5, hidden: 3, open: false }, 'x.py 8 个 → 留 5 个、藏 3 个')
assert(shut.nodes.has('x.py::B.n1.deep') && shut.nodes.has('x.py::C.c1'), 'pin / 展开拉出的必留，哪怕在调用链下游')
assert(shut.nodes.has('x.py::A') && shut.nodes.has('x.py::B') && shut.nodes.has('x.py::A.m1'), '调用链上游的 A（0 层）、B 和 A.m1（1 层）留下')
assert(!shut.nodes.has('x.py::A.m2') && !shut.nodes.has('x.py::A.m3'), 'A.m2、A.m3 有边但在下游（2、3 层），折叠——按上游排，不按边多排')
assert(shut.edges.every(e => shut.nodes.has(e.from) && shut.nodes.has(e.to)), '被折叠节点的边一条不画')
assert(shut.nodes.has('y.py::Z') && out.folds['tree:y.py'] === undefined, '不超过 5 个的框不折叠、不出按钮')
assert.deepStrictEqual(out.folds['side:s.py'], { total: 6, shown: 5, hidden: 1, open: false }, '旁边的框单独算：6 个留 5 个')

const opened = layerOf()
const out2 = foldBoxes(ctx, opened, side, forced, ['tree:x.py'])
assert.deepStrictEqual(out2.folds['tree:x.py'], { total: 8, shown: 8, hidden: 0, open: true }, '点开：全画，按钮变 −')
assert.strictEqual(opened.nodes.size, tree.length, '点开后节点一个不少')
assert.strictEqual(opened.edges.length, edges.length, '点开后边一条不少')
console.log('✓ 文件框折叠：超过 5 个留 5 个（pin/展开必留、调用链上游优先、有边的下游照样折叠）、被折叠的边不画、旁边单独算、点开全画')
