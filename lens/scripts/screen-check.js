#!/usr/bin/env node
// 用真实会话在 shell 里跑计算单元（src/compute），不经过浏览器。
//   S1 往下滑 turn   S2 切树   S3 切关系   S4 全开关系、随机选显示出来的节点切上下行（含旁边、中间点、链式）
//   S5 展开后关关系、展开后往下滑
// 用法：node lens/scripts/screen-check.js [session-id] [repo-root]
// 输出：每一步的节点 / 旁边 / 边 / 违例；最后一行是违例合计，非 0 退出码 1。
'use strict'
const fs = require('fs')
const path = require('path')
const cp = require('child_process')
const { RELATIONS, fromIndex, peers, asymmetry, extraFields } = require('../src/compute/anchors.js')
const { touchesFromEvents } = require('../src/compute/evidence.js')
const { screenFor } = require('../src/compute/screen.js')

const ROOT = path.resolve(process.argv[3] || path.join(__dirname, '..', '..'))
const SESSION = process.argv[2] || 'session-3e4f812f-7b1e-4a48-9ba3-7a7fc9f9f094'
const SESSION_DIR = path.join(process.env.HOME, '.dsh', 'sessions', '-' + ROOT.split(path.sep).join('-') + '--', SESSION)
const ZSTDCAT = process.env.ZSTDCAT || '/opt/homebrew/bin/zstdcat'
const ALL = Object.fromEntries(RELATIONS.map(r => [r, true]))
const TREES = ['degree1', 'degree2', 'edit']
const short = id => String(id || '').split('/').pop()
let violations = 0
let failures = 0

function load() {
  const dir = path.join(ROOT, '.codedendrite')
  const raw = JSON.parse(fs.readFileSync(path.join(dir, 'anchors.json'), 'utf8'))
  const rel = JSON.parse(fs.readFileSync(path.join(dir, 'relations.json'), 'utf8'))
  const text = cp.execFileSync(ZSTDCAT, [path.join(SESSION_DIR, 'session.jsonl.zstd')], { encoding: 'utf8', maxBuffer: 512 * 1024 * 1024 })
  const rows = text.split('\n').filter(Boolean).map((line) => { try { return JSON.parse(line) } catch { return null } }).filter(Boolean)
  return { ctx: fromIndex(ROOT, raw, rel.edges || []), touches: touchesFromEvents(rows) }
}

function rng(seed) {
  let x = seed
  return () => { x = (x * 1103515245 + 12345) % 2147483648; return x / 2147483648 }
}

function run(env, state) {
  const s = screenFor(env.ctx, env.touches, state)
  violations += s.violations.length
  return s
}

function line(s) {
  const types = {}
  s.edges.forEach(e => { types[e.type] = (types[e.type] || 0) + 1 })
  const totals = TREES.map(m => `${m}:${s.treeTotals[m].nodes}n/${s.treeTotals[m].edges}e`).join(' ')
  return `seed=${s.seeds}(edit ${s.edited.length},过期 ${s.faded}) 节点=${s.nodes.length} 旁边=${s.side.length} 边=${s.edges.length} ${JSON.stringify(types)} 违例=${s.violations.length} | 各树 ${totals}`
}

function sameScreen(a, b) {
  return a.nodes.join() === b.nodes.join() && a.side.join() === b.side.join() && a.edges.length === b.edges.length
}

function s0(env) {
  const first = run(env, {})
  console.log(`== S0 root=${ROOT} session=${SESSION}`)
  console.log(`  可见 anchor ${env.ctx.visible.size} 可见边 ${env.ctx.edgeCount} touch ${first.evidence.touches} 解不出 ${JSON.stringify(first.evidence.unresolved)}`)
  console.log('  补字段', JSON.stringify(extraFields(env.ctx)))
  console.log('  不对称', JSON.stringify(asymmetry(env.ctx)))
  return first.turns
}

function s1(env, turns, pinned) {
  console.log('\n== S1 往下滑 turn（全部关系）')
  for (const turn of turns) {
    for (const tree of TREES) console.log(`  T${turn} ${tree.padEnd(7)} ${line(run(env, { turn, tree, rels: ALL, pinned }))}`)
  }
}

function s2s3(env, turn, pinned) {
  console.log(`\n== S2 T${turn} 切树`)
  for (const tree of TREES) {
    const s = run(env, { turn, tree, rels: ALL, pinned })
    console.log(`  ${tree.padEnd(7)} ${line(s)}`)
    s.violations.slice(0, 5).forEach(v => console.log('     违例', v))
  }
  console.log(`\n== S3 T${turn} 切关系`)
  for (const tree of ['degree1', 'degree2', 'edit']) {
    for (const combo of [['call'], ['dataflow'], ['inherit'], ['call', 'dataflow'], RELATIONS]) {
      const rels = Object.fromEntries(RELATIONS.map(r => [r, combo.includes(r)]))
      console.log(`  ${tree.padEnd(7)} [${combo.join('+')}] ${line(run(env, { turn, tree, rels, pinned }))}`)
    }
  }
}

function s4(env, turn, pinned) {
  console.log(`\n== S4 T${turn} degree2 全部关系：随机选显示出来的节点切上下行`)
  const base = { turn, tree: 'degree2', rels: ALL, pinned, opens: [] }
  const first = run(env, base)
  const seeds = new Set([...first.nodes.filter(id => first.edited.includes(id) || first.counter[id]), ...first.side])
  const hasButtons = id => Object.keys(first.buttons[id]).length > 0
  const pool = [...first.nodes, ...first.side].filter(hasButtons)
  const picked = [first.side.find(hasButtons), first.nodes.find(id => !seeds.has(id) && hasButtons(id))].filter(Boolean)
  const rand = rng(20260914)
  while (picked.length < Math.min(6, pool.length)) {
    const id = pool[Math.floor(rand() * pool.length)]
    if (!picked.includes(id)) picked.push(id)
  }
  for (const id of picked) {
    for (const [key, n] of Object.entries(first.buttons[id])) {
      const rel = key.replace(/(up|down)$/, '')
      const dir = key.endsWith('up') ? 'up' : 'down'
      const opened = run(env, { ...base, opens: [{ id, rel, dir }] })
      const closed = run(env, base)
      const x = opened.expansions[0]
      const ok = opened.violations.length === 0 && sameScreen(closed, first) && x.count === n
      if (!ok) failures += 1
      const where = first.side.includes(id) ? '(旁边)' : (seeds.has(id) ? '' : '(中间点)')
      console.log(`  ${short(id)}${where} ${key}=${n} → 展开${x.count} 连已有${x.count - x.fresh} 新建${x.fresh} 节点${first.nodes.length}→${opened.nodes.length} 边${first.edges.length}→${opened.edges.length} 收起复原=${sameScreen(closed, first)} ${ok ? 'OK' : 'FAIL'}`)
    }
  }
  for (const rel of ['call', 'dataflow']) {
    let at = [...first.nodes, ...first.side].find(id => (first.buttons[id][rel + 'down'] || 0) > 0)
    const opens = []
    const trail = [short(at)]
    for (let depth = 0; depth < 4 && at; depth += 1) {
      opens.push({ id: at, rel, dir: 'down' })
      const s = run(env, { ...base, opens })
      const x = s.expansions[s.expansions.length - 1]
      trail.push(`[${rel}down=${x.count} 新建${x.fresh} 违例${s.violations.length}]`)
      at = x.peers.find(p => !opens.some(o => o.id === p) && peers(env.ctx, p, rel, 'down').length > 0)
      if (at) trail.push(short(at))
    }
    console.log(`  链式 ${rel}: ${trail.join(' → ')}`)
  }
}

function s5(env, turns, pinned) {
  console.log('\n== S5 展开 × 关系开关 × 往下滑')
  const turn = turns[turns.length - 1]
  const base = { turn, tree: 'degree2', rels: ALL, pinned }
  const first = run(env, base)
  const id = [...first.nodes, ...first.side].find(x => (first.buttons[x].dataflowup || 0) > 1)
  if (id) {
    const opens = [{ id, rel: 'dataflow', dir: 'up' }]
    const noDataflow = { ...ALL, dataflow: false }
    const off = run(env, { ...base, rels: noDataflow, opens })
    const offBase = run(env, { ...base, rels: noDataflow })
    const same = sameScreen(off, offBase)
    if (!same) failures += 1
    console.log(`  ${short(id)} dataflowup=${first.buttons[id].dataflowup} 展开后关 dataflow：${off.expansions[0].skipped} 与"没展开+关 dataflow"相同=${same}`)
  }
  for (const t of turns.slice(Math.floor(turns.length / 2))) {
    const s = run(env, { turn: t, tree: 'degree2', rels: ALL, pinned })
    const target = [...s.nodes, ...s.side].find(x => (s.buttons[x].calldown || 0) > 0)
    if (!target) continue
    for (const later of turns.filter(x => x >= t)) {
      const moved = run(env, { turn: later, tree: 'degree2', rels: ALL, pinned, opens: [{ id: target, rel: 'call', dir: 'down' }] })
      const x = moved.expansions[0]
      console.log(`  T${t} 展开 ${short(target)} calldown → 滑到 T${later}: ${x.skipped || '展开' + x.count + ' 新建' + x.fresh}`)
    }
    return
  }
}

function main() {
  const env = load()
  const turns = s0(env)
  if (turns.length === 0) { console.log('这个会话没有 read/edit/write'); return }
  const last = turns[turns.length - 1]
  const pinned = [...env.ctx.visible].filter(id => id.endsWith('::factory.exploreMethods') || id.endsWith('::relPeers')).slice(0, 2)
  s1(env, turns, pinned)
  s2s3(env, last, pinned)
  s4(env, last, pinned)
  s5(env, turns, pinned)
  console.log(`\n违例合计 ${violations}，按钮检查失败 ${failures}`)
  process.exit(violations === 0 && failures === 0 ? 0 : 1)
}

main()
