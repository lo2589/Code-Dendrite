// 文件框折叠（src/compute/fold.js）：超过 5 个折叠，只留层级高的和 pin / 展开的；点开全画；被折叠的边不画。
const assert = require('assert')
const { foldBoxes, FOLD_LIMIT } = require('../src/compute/fold.js')

const a = (id, line) => ({ id, file: id.split('::')[0], symbol: id.split('::')[1], line_start: line })
const anchors = Object.fromEntries([
  a('x.py::A', 1), a('x.py::A.m1', 2), a('x.py::A.m2', 3), a('x.py::A.m3', 4),
  a('x.py::B', 10), a('x.py::B.n1', 11), a('x.py::B.n1.deep', 12), a('x.py::C.c1', 20),
  a('y.py::Z', 1),
  a('s.py::s1', 1), a('s.py::s2', 2), a('s.py::s3', 3), a('s.py::s4', 4), a('s.py::s5', 5), a('s.py::s6', 6),
].map(x => [x.id, x]))
const ctx = { anchors }
const tree = ['x.py::A', 'x.py::A.m1', 'x.py::A.m2', 'x.py::A.m3', 'x.py::B', 'x.py::B.n1', 'x.py::B.n1.deep', 'x.py::C.c1', 'y.py::Z']
const side = ['s.py::s1', 's.py::s2', 's.py::s3', 's.py::s4', 's.py::s5', 's.py::s6']
const edges = [
  { from: 'x.py::A', to: 'x.py::B', type: 'call' },
  { from: 'x.py::A.m2', to: 'y.py::Z', type: 'call' },
  { from: 'x.py::B.n1.deep', to: 'y.py::Z', type: 'call' },
  { from: 'x.py::A.m3', to: 'x.py::B.n1', type: 'dataflow' },
]
const forced = new Set(['x.py::B.n1.deep', 'x.py::C.c1'])
const layerOf = () => ({ nodes: new Set(tree), edges: edges.map(e => ({ ...e })) })

// 折叠
const shut = layerOf()
const out = foldBoxes(ctx, shut, side, forced, [])
const shownX = [...shut.nodes].filter(id => id.startsWith('x.py::')).sort()
assert.strictEqual(FOLD_LIMIT, 5)
assert.deepStrictEqual(out.folds['tree:x.py'], { total: 8, shown: 5, hidden: 3, open: false }, 'x.py 8 个 → 留 5 个、藏 3 个')
assert(forced.has('x.py::B.n1.deep') && shut.nodes.has('x.py::B.n1.deep') && shut.nodes.has('x.py::C.c1'), 'pin / 展开拉出的必留，哪怕层级低')
assert(shut.nodes.has('x.py::A') && shut.nodes.has('x.py::B'), '层级最高的 A、B 留下')
assert(shut.nodes.has('x.py::A.m2') && !shut.nodes.has('x.py::A.m1'), '同层级先留屏幕上有边的（A.m2 有边，A.m1 没边）')
assert.strictEqual(shownX.length, 5, 'x.py 正好画 5 个')
assert(shut.edges.every(e => shut.nodes.has(e.from) && shut.nodes.has(e.to)), '被折叠节点的边一条不画')
assert(shut.nodes.has('y.py::Z') && out.folds['tree:y.py'] === undefined, '不超过 5 个的框不折叠、不出按钮')
assert.deepStrictEqual(out.folds['side:s.py'], { total: 6, shown: 5, hidden: 1, open: false }, '旁边的框单独算：6 个留 5 个')
assert.deepStrictEqual(out.side, side.slice(0, 5), '旁边按层级同、行号先后留前 5 个')

// 点开
const opened = layerOf()
const out2 = foldBoxes(ctx, opened, side, forced, ['tree:x.py'])
assert.deepStrictEqual(out2.folds['tree:x.py'], { total: 8, shown: 8, hidden: 0, open: true }, '点开：全画，按钮变 −')
assert.strictEqual(opened.nodes.size, tree.length, '点开后节点一个不少')
assert.strictEqual(opened.edges.length, edges.length, '点开后边一条不少')
console.log('✓ 文件框折叠：超过 5 个留 5 个（pin/展开必留、层级高优先、同层有边优先）、被折叠的边不画、旁边单独算、点开全画')
