// 焦点不能丢：图变了（展开、切开关、新一轮），上次画过的卡片原地不动，新来的只往空地放。
//
// 以前节点数一变，整张图从零重新装箱，所有卡片换位置——用户正盯着的那张跑了，就是丢焦点。
// 整体重排只在用户自己要求时做：「恢复自动布局」、改画布宽度。
//
//   node lens/scripts/build.js && node lens/tests/layout-hold.js
'use strict'
const fs = require('fs')
const vm = require('vm')
const path = require('path')
const assert = require('assert')

const BUNDLE = fs.readFileSync(path.join(__dirname, '..', 'lib', 'client.js'), 'utf8')

function loadParts() {
  const factories = new Map()
  const cache = new Map()
  const require_ = (id) => {
    if (id === 'react') return { createElement: () => null, useState: v => [v, () => {}], useEffect: () => {}, useMemo: f => f(), useRef: v => ({ current: v }), useCallback: f => f }
    if (cache.has(id)) return cache.get(id)
    if (!factories.has(id)) throw new Error('no registered factory for "' + id + '"')
    const value = factories.get(id)(require_)
    cache.set(id, value)
    return value
  }
  const context = {
    window: { __ModuleLoader__: { load: r => factories.set(r.id, r.factory) }, localStorage: { getItem: () => null, setItem: () => {} } },
    document: { querySelector: () => null, querySelectorAll: () => [], createElement: () => ({ style: {} }), head: { appendChild() {} } },
    console, setTimeout, clearTimeout,
  }
  vm.createContext(context)
  vm.runInContext(BUNDLE, context)
  return require_
}

const S = loadParts()('dsh-cdd-lens/layout/stable')

let failed = 0
const check = (name, fn) => {
  try { fn(); console.log('ok   ' + name) } catch (error) { failed += 1; console.log('FAIL ' + name + ' — ' + error.message) }
}

const G = { cols: 2, cellW: 240, cardW: 220, pad: 10, gapX: 20, anchorGap: 40, head: 24, innerY: 8, left: 16 }
const H = 60
const GAP = 20
const AVAIL = 600
const tools = {
  portsFor: (x, y, w, h) => ({ in: { x, y: y + h / 2 }, out: { x: x + w, y: y + h / 2 } }),
  polylinesFor: () => [],
}

/** 一张卡片：col 列、第 row 张，按 G 的网格算坐标（和 fileGrid 一样的排法）。 */
const card = (id, file, col, top, row) => ({
  id, file, side: false, boxKey: file, w: G.cardW, h: H,
  x: G.left + col * (G.cellW + G.gapX) + G.pad, y: top + G.head + row * (H + G.innerY),
})
const box = (file) => ({ file, label: file, frame: 'tree' })
const laidOf = (placed, files) => ({ placed, boxes: files.map(box), rows: [], grid: G, canvasY: 400 })
const by = (laid, id) => laid.placed.find(p => p.id === id)
const overlap = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h

// 上一张：a.js 在第 0 列（两张），b.js 在第 1 列（一张）。
const before = [card('a1', 'a.js', 0, 16, 0), card('a2', 'a.js', 0, 16, 1), card('b1', 'b.js', 1, 16, 0)]

check('老卡片坐标一个像素都不变；新卡片接在自己文件框底下', () => {
  S.forget()
  S.hold(before, G.cols)
  // 这次整体装箱把所有东西都排到了别处——保位必须不认这个结果。
  const fresh = [card('a1', 'a.js', 1, 300, 0), card('a2', 'a.js', 1, 300, 1), card('a3', 'a.js', 1, 300, 2), card('b1', 'b.js', 0, 300, 0)]
  const out = S.holdLayout({}, laidOf(fresh, ['a.js', 'b.js']), GAP, tools)
  before.forEach(p => {
    const q = by(out, p.id)
    assert.deepStrictEqual([q.x, q.y], [p.x, p.y], p.id + ' 动了')
  })
  const a3 = by(out, 'a3')
  assert.strictEqual(a3.x, before[0].x, 'a3 应该在 a.js 那一列')
  assert.strictEqual(a3.y, before[1].y + H + G.innerY, 'a3 应该接在 a2 底下')
  assert.strictEqual(a3.boxKey, 'a.js')
  assert.strictEqual(out.held.kept, 3)
  assert.strictEqual(out.held.fresh, 1)
})

check('老框底下被别的框挡住：新卡片到下面另开续框，老卡片照样不动', () => {
  S.forget()
  // c.js 紧贴在 a.js 下面，a.js 往下长就会压到它。
  const cTop = before[1].y + H + G.pad + 10
  const prev = before.concat([card('c1', 'c.js', 0, cTop, 0)])
  S.hold(prev, G.cols)
  const fresh = prev.map(p => Object.assign({}, p)).concat([card('a3', 'a.js', 0, 0, 0)])
  const out = S.holdLayout({}, laidOf(fresh, ['a.js', 'b.js', 'c.js']), GAP, tools)
  prev.forEach(p => {
    const q = by(out, p.id)
    assert.deepStrictEqual([q.x, q.y], [p.x, p.y], p.id + ' 动了')
  })
  const a3 = by(out, 'a3')
  assert.strictEqual(a3.boxKey, 'a.js#续', '应该进续框')
  const cont = out.boxes.find(b => b.boxKey === 'a.js#续')
  assert.ok(cont, '应该有一个续框')
  assert.ok(/（续）$/.test(cont.label), '续框要标出来是续')
  out.boxes.filter(b => b !== cont).forEach(b => assert.ok(!overlap(cont, b), '续框压到了 ' + b.file))
})

check('有卡片被移除：剩下的原地不动', () => {
  S.forget()
  S.hold(before, G.cols)
  const fresh = [card('a1', 'a.js', 0, 0, 0), card('b1', 'b.js', 0, 0, 1)]
  const out = S.holdLayout({}, laidOf(fresh, ['a.js', 'b.js']), GAP, tools)
  ;['a1', 'b1'].forEach(id => {
    const p = before.find(x => x.id === id)
    const q = by(out, id)
    assert.deepStrictEqual([q.x, q.y], [p.x, p.y], id + ' 动了')
  })
})

check('卡片在「树」和「旁边」之间换区：位置不变', () => {
  S.forget()
  S.hold(before, G.cols)
  // 关掉一种关系后，b1 不在树里了，掉进「旁边」区；整体装箱把它排到了很远的地方。
  const fresh = before.map(p => Object.assign({}, p))
  fresh[2] = Object.assign({}, fresh[2], { side: true, x: 9999, y: 9999 })
  const laid = laidOf(fresh, ['a.js', 'b.js'])
  laid.boxes.push({ file: 'b.js', label: 'b.js', frame: 'side' })
  const out = S.holdLayout({}, laid, GAP, tools)
  const b1 = by(out, 'b1')
  assert.deepStrictEqual([b1.x, b1.y], [before[2].x, before[2].y], 'b1 换了区就跑了')
  assert.strictEqual(b1.side, true, '换区本身要保留')
})

check('关掉一种关系卡片消失，再打开它回来：回到原位，不放到最下面', () => {
  S.forget()
  S.hold(before, G.cols)
  // 关掉：b1 不在图上了
  const off = S.holdLayout({}, laidOf(before.filter(p => p.id !== 'b1').map(p => Object.assign({}, p)), ['a.js']), GAP, tools)
  S.hold(off.placed, G.cols)
  // 打开：b1 回来，整体装箱把它排到了很远的地方
  const back = before.map(p => Object.assign({}, p))
  back[2] = Object.assign({}, back[2], { x: 9999, y: 9999 })
  const on = S.holdLayout({}, laidOf(back, ['a.js', 'b.js']), GAP, tools)
  const b1 = by(on, 'b1')
  assert.deepStrictEqual([b1.x, b1.y], [before[2].x, before[2].y], 'b1 回来没回原位')
})

check('回来的卡片旁边紧挨着同文件「旁边」区的框：照样回原位', () => {
  S.forget()
  // a.js 在树区两张；同一个文件在「旁边」区还有一张，框紧贴在树区框下面。
  const s1 = Object.assign(card('s1', 'a.js', 0, before[1].y + H + G.pad + 4, 0), { side: true })
  const prev = before.concat([s1])
  S.hold(prev, G.cols)
  const offPlaced = prev.filter(p => p.id !== 'a2').map(p => Object.assign({}, p))
  const offLaid = laidOf(offPlaced, ['a.js', 'b.js'])
  offLaid.boxes.push({ file: 'a.js', label: 'a.js', frame: 'side' })
  const off = S.holdLayout({}, offLaid, GAP, tools)
  S.hold(off.placed, G.cols)
  const backLaid = laidOf(prev.map(p => Object.assign({}, p, p.id === 'a2' ? { x: 9999, y: 9999 } : {})), ['a.js', 'b.js'])
  backLaid.boxes.push({ file: 'a.js', label: 'a.js', frame: 'side' })
  const out = S.holdLayout({}, backLaid, GAP, tools)
  const a2 = by(out, 'a2')
  assert.deepStrictEqual([a2.x, a2.y], [before[1].x, before[1].y], 'a2 被同文件的旁边区框挡住，没回原位')
})

check('回来的卡片原位已经被占：当新卡片放空地，不压别人', () => {
  S.forget()
  S.hold(before, G.cols)
  const off = S.holdLayout({}, laidOf(before.filter(p => p.id !== 'a2').map(p => Object.assign({}, p)), ['a.js', 'b.js']), GAP, tools)
  S.hold(off.placed, G.cols)
  // a2 不在的时候，a3 接在 a1 底下，正好占了 a2 原来的位置
  const withA3 = off.placed.map(p => Object.assign({}, p)).concat([card('a3', 'a.js', 0, 0, 0)])
  const mid = S.holdLayout({}, laidOf(withA3, ['a.js', 'b.js']), GAP, tools)
  S.hold(mid.placed, G.cols)
  const back = mid.placed.map(p => Object.assign({}, p)).concat([card('a2', 'a.js', 0, 0, 0)])
  const out = S.holdLayout({}, laidOf(back, ['a.js', 'b.js']), GAP, tools)
  const a2 = by(out, 'a2')
  out.placed.filter(p => p.id !== 'a2').forEach(p => assert.ok(!overlap(a2, p), 'a2 压在了 ' + p.id + ' 上'))
})

check('卡片长高压到同框下一张：只把下一张往下让，不往上拉', () => {
  S.forget()
  S.hold(before, G.cols)
  const fresh = before.map(p => Object.assign({}, p))
  fresh[0].h = H + 30
  const out = S.holdLayout({}, laidOf(fresh, ['a.js', 'b.js']), GAP, tools)
  assert.strictEqual(by(out, 'a1').y, before[0].y, 'a1 不该动')
  assert.strictEqual(by(out, 'a2').y, before[0].y + H + 30 + G.innerY, 'a2 应该刚好让开')
  assert.strictEqual(by(out, 'b1').y, before[2].y, '别的框不该动')
})

check('用户要求重排（恢复自动布局）：原样交回整体装箱的结果', () => {
  S.hold(before, G.cols)
  S.forget()
  const laid = laidOf([card('a1', 'a.js', 1, 300, 0)], ['a.js'])
  assert.strictEqual(S.holdLayout({}, laid, GAP, tools), laid)
})

check('冒出滚动条、宽度少十几像素（列数没变）：照样保位', () => {
  S.forget()
  S.hold(before, G.cols)
  // 列数一样：只是滚动条占了点宽度，不是用户改宽度。
  const fresh = before.map(p => Object.assign({}, p, { x: p.x + 500, y: p.y + 500 }))
  const out = S.holdLayout({}, laidOf(fresh, ['a.js', 'b.js']), GAP, tools)
  before.forEach(p => {
    const q = by(out, p.id)
    assert.deepStrictEqual([q.x, q.y], [p.x, p.y], p.id + ' 被滚动条挤走了')
  })
})

check('列数真的变了（用户改了宽度）：整体重排', () => {
  S.forget()
  S.hold(before, G.cols)
  const laid = laidOf([card('a1', 'a.js', 1, 300, 0)], ['a.js'])
  laid.grid = Object.assign({}, G, { cols: G.cols + 1 })
  assert.strictEqual(S.holdLayout({}, laid, GAP, tools), laid)
})

check('一张老卡片都对不上（换会话）：整体重排', () => {
  S.forget()
  S.hold(before, G.cols)
  const laid = laidOf([card('z1', 'z.js', 0, 16, 0)], ['z.js'])
  assert.strictEqual(S.holdLayout({}, laid, GAP, tools), laid)
})

check('保位时收框不把「旁边」区推到树区底下', () => {
  const settle = loadParts()('dsh-cdd-lens/layout/settle')
  const metrics = { BOX_PAD: G.pad, BOX_HEAD: G.head, BOX_GAP_X: 20, BOX_GAP_Y: 20 }
  // 旁边区一个框在上面 y=100；树区新长出来的一个框在下面 y=600。
  const s1 = Object.assign(card('s1', 's.js', 1, 100, 0), { side: true })
  const t1 = card('t1', 't.js', 0, 600, 0)
  const boxes = [
    { file: 't.js', frame: 'tree', x: t1.x - G.pad, y: 600, w: G.cellW, h: 100 },
    { file: 's.js', frame: 'side', x: s1.x - G.pad, y: 100, w: G.cellW, h: 100 },
  ]
  const rows = [{ x: 16, y: 84, label: '旁边' }]
  const place = { placed: [Object.assign({}, s1), Object.assign({}, t1)] }
  settle.settleBoxes(place, { boxes, rows, held: { kept: 2 } }, metrics)
  assert.strictEqual(place.placed[0].y, s1.y, '旁边区的老卡片被推走了')
  assert.strictEqual(place.placed[1].y, t1.y, '树区的卡片不该动')
  // 不保位（第一次画）时规矩照旧：旁边整段在树下面。
  const fresh = { placed: [Object.assign({}, s1), Object.assign({}, t1)] }
  settle.settleBoxes(fresh, { boxes: boxes.map(b => Object.assign({}, b)), rows: rows.map(r => Object.assign({}, r)) }, metrics)
  assert.ok(fresh.placed[0].y > t1.y, '不保位时旁边区应该在树的下面')
})

check('点卡片 / 定位：看得见就不动视口（ensure，不是 center）', () => {
  const text = fs.readFileSync(path.join(__dirname, '..', 'src', 'client', 'engine', 'selection.js'), 'utf8')
  const reveal = text.slice(text.indexOf('reveal: function'), text.indexOf('select: function'))
  assert.ok(/requestViewport\(id, 'ensure'\)/.test(reveal), 'reveal 还在 center：点一下正看着的卡片，整张图滑一下')
})

check('「看得见」= 露出一部分就算，不要求整张卡片完整在视口里', () => {
  const text = fs.readFileSync(path.join(__dirname, '..', 'src', 'client', 'shell', 'viewState.js'), 'utf8')
  const on = text.slice(text.indexOf('var onScreen'), text.indexOf('var centerOn'))
  assert.ok(/right > el\.scrollLeft && left < el\.scrollLeft \+ el\.clientWidth/.test(on), '还在要求整张卡片落在视口里')
  assert.ok(!/pad = 12/.test(on), '不该再留 12px 余量把半露的卡片判成看不见')
})

check('横向滚动条那一行永远占着：出现/消失不挤矮画布', () => {
  const text = fs.readFileSync(path.join(__dirname, '..', 'src', 'client', 'view', 'hscroll.js'), 'utf8')
  assert.ok(!/if \(st\.overflow <= 2\) return null/.test(text), '没溢出时还是不渲染：一溢出画布就被挤矮 15px')
  assert.ok(/cddl-hscroll-idle/.test(text), '没溢出时要放一个看不见的占位')
})

check('收框按框标识认成员：续框和主框各认各的', () => {
  const text = fs.readFileSync(path.join(__dirname, '..', 'src', 'client', 'layout', 'settle.js'), 'utf8')
  assert.ok(/p\.boxKey !== undefined \? p\.boxKey : p\.file/.test(text), '收框还在按文件名认成员')
})

process.exitCode = failed === 0 ? 0 : 1
console.log(failed === 0 ? '\n全部通过' : '\n' + failed + ' 项失败')
