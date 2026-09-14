// 文件框一行填哪几列（layout/fileGrid.js::eligibleColumns）：
// 用户：「比最短边高1/2平均文件框的，就不填，尽量让一行的文件框底边一致」
// 底边 − 最短底边 > 平均框高 ÷ 2 → 这一行不填。
const fs = require('fs'), vm = require('vm'), path = require('path')
const assert = require('assert')

const factories = new Map()
const ctx = { window: { __ModuleLoader__: { load: r => factories.set(r.id, r.factory) } } }
vm.createContext(ctx)
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'src', 'client', 'layout', 'fileGrid.js'), 'utf8'), ctx)
const stub = id => (id === 'dsh-cdd-lens/graph/model' ? { placeOf: () => null } : { shared: {} })
const { eligibleColumns } = factories.get('dsh-cdd-lens/layout/fileGrid')(stub)

const cases = [
  [[45, 30, 30, 25], 30, [1, 2, 3], '平均框高 30：门槛 25+15=40，45 高出 20 不填'],
  [[45, 30, 30, 25], 20, [1, 2, 3], '平均框高 20：门槛 25+10=35，45 高出 20 不填'],
  [[45, 30, 30, 25], 50, [0, 1, 2, 3], '平均框高 50：门槛 25+25=50，45 高出 20 照填'],
  [[30, 30, 30, 30], 30, [0, 1, 2, 3], '各列一样高：全填'],
  [[100, 30, 30, 30], 60, [1, 2, 3], '平均框高 60：门槛 30+30=60，100 高出 70 不填'],
]
for (const [bottoms, avgBox, want, why] of cases) {
  const got = [...eligibleColumns(bottoms, avgBox)]
  const shortest = Math.min(...bottoms)
  console.log(`底边 [${bottoms.join(', ')}] · 平均框高 ${avgBox} · 最短 ${shortest} · 门槛 ${shortest + avgBox / 2} → 填第 ${got.map(c => c + 1).join('、')} 列（${why}）`)
  assert.deepStrictEqual(got, want, why)
}
console.log('✓ 一行填哪几列：比最短底边高出平均框高一半的不填，5 组全对')
