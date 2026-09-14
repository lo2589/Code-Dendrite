// 文件框最后收一遍（layout/settle.js）：框被撑高、压住下面的框时，整体往下推开，框永远不叠。
const fs = require('fs'), vm = require('vm'), path = require('path')
const assert = require('assert')

const factories = new Map()
const ctx = { window: { __ModuleLoader__: { load: r => factories.set(r.id, r.factory) } } }
vm.createContext(ctx)
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'src', 'client', 'layout', 'settle.js'), 'utf8'), ctx)
const { settleBoxes } = factories.get('dsh-cdd-lens/layout/settle')(() => {})

const metrics = { BOX_PAD: 11, BOX_HEAD: 32, BOX_GAP_X: 40, BOX_GAP_Y: 40 }
const node = (id, file, x, y, h, extra = {}) => ({ id, file, x, y, w: 260, h, ...extra })
// A 在左上，B 在它正下方（隔 40），C 在右上；旁边一段 S。a2 实际比排版估的高，把 A 撑到压住 B。
const laid = {
  boxes: [
    { file: 'a.js', frame: 'tree', x: 18, y: 18, w: 282, h: 200 },
    { file: 'b.js', frame: 'tree', x: 18, y: 258, w: 282, h: 120 },
    { file: 'c.js', frame: 'tree', x: 340, y: 18, w: 282, h: 150 },
    { file: 's.js', frame: 'side', x: 18, y: 440, w: 282, h: 100 },
  ],
  rows: [{ x: 18, y: 424, label: '旁边' }],
}
const placed = [
  node('a1', 'a.js', 29, 50, 60), node('a2', 'a.js', 29, 124, 260),
  node('b1', 'b.js', 29, 290, 60),
  node('c1', 'c.js', 351, 50, 60),
  node('s1', 's.js', 29, 472, 60, { side: true }),
  node('m', 'b.js', 40, 40, 60, { manual: true }),
]
const before = Object.fromEntries(placed.map(p => [p.id, { x: p.x, y: p.y }]))
const out = settleBoxes({ placed }, laid, metrics)
const by = Object.fromEntries(placed.map(p => [p.id, p]))
const box = f => out.boxes.find(b => b.file === f)
const inter = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
const inside = (p, b) => p.x >= b.x && p.y >= b.y && p.x + p.w <= b.x + b.w && p.y + p.h <= b.y + b.h

let pairs = 0
for (let i = 0; i < out.boxes.length; i += 1) for (let j = i + 1; j < out.boxes.length; j += 1) if (inter(out.boxes[i], out.boxes[j])) pairs += 1
assert.strictEqual(pairs, 0, '收过之后框两两不叠')
assert(inside(by.a1, box('a.js')) && inside(by.a2, box('a.js')), 'A 长到装下被撑高的 a2')
const dy = by.b1.y - before.b1.y
assert(dy > 0 && box('b.js').y - laid.boxes[1].y === dy, 'B 连同 b1 整体往下推，推的距离一样')
assert(box('b.js').y >= box('a.js').y + box('a.js').h + 40, 'B 和 A 之间留着框间距')
assert.deepStrictEqual({ x: by.c1.x, y: by.c1.y }, before.c1, '没被压的 C 不动')
assert.deepStrictEqual({ x: by.m.x, y: by.m.y }, before.m, '手工拖过的节点留在原处，不算进框')
assert(out.rows[0].y >= box('b.js').y + box('b.js').h + 36, '「旁边」标题跟到树的框下面')
assert(box('s.js').y >= out.rows[0].y + 8 && inside(by.s1, box('s.js')), '旁边的框从标题下面开始，节点跟着框走')
console.log('✓ 文件框收一遍：撑高的框长大、压住的框连同节点往下推、C 不动、拖过的节点不动、旁边跟到树下面')
