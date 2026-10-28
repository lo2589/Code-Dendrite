// 宿主契约：lens 依赖的 harness 接口，在 harness 源码里还是不是那个样子。
//
// harness 处在 developer preview，README 明写会有破坏兼容的改动；一个月几千个提交。
// lens 是纯 JS，用不上 harness 的 .d.ts，接口一变只会在页面里静默坏掉
// （meta.lines 被当整数判断、恒 false，就是这么坏了好几版没人知道）。
// 这个测试直接读 harness 源码，把 lens 用到的每一处对一遍：
//   1. slot：注册的 slot 名在 slot-catalog 里，传的选项都是 catalog 认的
//   2. 服务：inject / ctx.get 的每个服务都有 `declare module` 声明
//   3. sessionQuery：host 调的 readSession / readSurface 还在
//   4. read 结果：ReadFileLine 还是 { number, text }，ReadResultView 还有 offset / lines
//   5. 模块表：重复登记仍然抛错（bundle-reload.js 的模拟宿主才算数），boot 行 id == 包名
//
//   DSH_REPO=/path/to/deepseek-harness node lens/tests/host-contract.js
//
// 找不到 harness 就整个跳过并大声说出来，不假装通过。
'use strict'
const fs = require('fs')
const path = require('path')
const assert = require('assert')

const LENS = path.join(__dirname, '..')
// 跟 scripts/install.sh 同一个默认：lens 所在仓库的同级目录 deepseek-harness。
const DSH = process.env.DSH_REPO || path.join(LENS, '..', '..', 'deepseek-harness')

const read = (rel) => fs.readFileSync(path.join(DSH, rel), 'utf8')

// 不是宿主的 slot，而是可选插件自己声明的 slot（lens 软接入，不是安装依赖）。
// 这类 slot 不查宿主 slot-catalog，改查声明它的那个插件的源码里确实还声明着。
const OPTIONAL_SLOTS = {
  'rightbar.tab': path.join(LENS, '..', '..', 'dsh-plugin-rightbar', 'src', 'client.js'),
}
const lensSource = (rel) => fs.readFileSync(path.join(LENS, rel), 'utf8')

let failed = 0
const check = (name, fn) => {
  try { fn(); console.log('ok   ' + name) } catch (error) { failed += 1; console.log('FAIL ' + name + ' — ' + error.message) }
}

/** lens 源码里所有 .js 文件（src/ 下，不含生成的 lib/）。 */
function lensFiles(dir = path.join(LENS, 'src')) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    const full = path.join(dir, d.name)
    if (d.isDirectory()) return lensFiles(full)
    return d.name.endsWith('.js') ? [full] : []
  })
}

/** harness 的非测试、非产物 TS 源码。 */
function harnessSources(dir = path.join(DSH, 'packages')) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    if (['node_modules', 'lib', 'tests', 'dist'].includes(d.name)) return []
    const full = path.join(dir, d.name)
    if (d.isDirectory()) return harnessSources(full)
    return /\.tsx?$/.test(d.name) && !/\.spec\.tsx?$/.test(d.name) ? [full] : []
  })
}

/** slot-catalog 里一个 key 的条目：kind 和它认的 register 选项名。 */
function catalogEntry(catalog, key) {
  const start = catalog.indexOf(`key: '${key}',`)
  if (start < 0) return null
  const next = catalog.indexOf('    key: \'', start + 1)
  const body = catalog.slice(start, next < 0 ? undefined : next)
  const kind = (body.match(/kind: '([^']+)'/) || [])[1]
  const options = [...body.matchAll(/name: '([^']+)',\s*\n\s*requirement: '([^']+)'/g)]
    .map(m => ({ name: m[1], requirement: m[2] }))
  return { kind, options }
}

/** lens 里每一处 slots.register({ name: 'x', ... }) 的 slot 名和它传的选项名。 */
function lensRegistrations() {
  return lensFiles().flatMap((file) => {
    const text = fs.readFileSync(file, 'utf8')
    return [...text.matchAll(/slots\.register\(\{([^}]*)\}/g)].map((m) => {
      const keys = [...m[1].matchAll(/(\w+):/g)].map(k => k[1])
      return { file: path.relative(LENS, file), slot: (m[1].match(/name: '([^']+)'/) || [])[1], options: keys.filter(k => k !== 'name') }
    })
  })
}

/** lens 用到的所有 cordis 服务：ctx.get('x') 加上入口的 inject 列表。 */
function lensServices() {
  const names = new Set()
  for (const file of lensFiles()) {
    for (const m of fs.readFileSync(file, 'utf8').matchAll(/ctx\.get\('([^']+)'\)/g)) names.add(m[1])
  }
  const inject = lensSource('src/client/entry.js').match(/inject: \[([^\]]*)\]/)
  for (const m of inject[1].matchAll(/'([^']+)'/g)) names.add(m[1])
  return [...names].sort()
}

/** 一个 TS interface 的字段名（只认顶层 `name: type` / `name?: type`）。 */
function interfaceFields(text, name) {
  const start = text.search(new RegExp(`export interface ${name}\\b[^{]*\\{`))
  if (start < 0) return null
  const open = text.indexOf('{', start)
  let depth = 0
  let end = open
  for (; end < text.length; end += 1) {
    if (text[end] === '{') depth += 1
    if (text[end] === '}') { depth -= 1; if (depth === 0) break }
  }
  const body = text.slice(open + 1, end).replace(/\/\*[\s\S]*?\*\//g, '')
  const fields = {}
  for (const m of body.matchAll(/^\s{2}(\w+)\??:\s*([^\n]+)$/gm)) fields[m[1]] = m[2].trim()
  return fields
}

if (!fs.existsSync(path.join(DSH, 'packages'))) {
  console.log(`SKIP 找不到 harness 源码：${DSH}（设 DSH_REPO 指过去）。宿主契约没有被检查。`)
  process.exit(0)
}
console.log('harness: ' + DSH)

check('1. lens 注册的每个 slot 都在 slot-catalog 里，选项都被认', () => {
  const catalog = read('packages/extensions/cordis-client-runner/src/client/slot-catalog.ts')
  const regs = lensRegistrations()
  assert.ok(regs.length > 0, 'lens 里一处 slots.register 都没找到，测试自己坏了')
  for (const reg of regs) {
    if (OPTIONAL_SLOTS[reg.slot] !== undefined) {
      const owner = OPTIONAL_SLOTS[reg.slot]
      if (!fs.existsSync(owner)) { console.log(`     （${reg.slot} 的声明方不在 ${owner}，跳过）`); continue }
      assert.ok(fs.readFileSync(owner, 'utf8').includes(`children: { '${reg.slot}': { kind: 'list'`), `${reg.file}: ${owner} 不再声明 list 型 '${reg.slot}'`)
      continue
    }
    const entry = catalogEntry(catalog, reg.slot)
    assert.ok(entry !== null, `${reg.file}: slot '${reg.slot}' 已不在 harness 的 slot-catalog 里`)
    const known = entry.options.map(o => o.name)
    for (const opt of reg.options) assert.ok(known.includes(opt), `${reg.file}: slot '${reg.slot}' 不再认选项 '${opt}'（现在认 ${known.join(', ')}）`)
    for (const o of entry.options) {
      if (o.requirement === 'required') assert.ok(reg.options.includes(o.name), `${reg.file}: slot '${reg.slot}' 现在要求必传 '${o.name}'`)
    }
  }
})

check('2. lens 用到的每个服务都有 declare module 声明', () => {
  const services = lensServices()
  const declared = new Set()
  for (const file of harnessSources()) {
    const text = fs.readFileSync(file, 'utf8')
    if (!/interface Context\b/.test(text)) continue
    for (const name of services) if (new RegExp(`^\\s+${name}\\??:\\s`, 'm').test(text)) declared.add(name)
  }
  const missing = services.filter(name => !declared.has(name))
  assert.deepStrictEqual(missing, [], `这些服务在 harness 里找不到声明：${missing.join(', ')}（lens 用了 ${services.join(', ')}）`)
})

check('3. sessionQuery 还有 readSession / readSurface', () => {
  const engine = read('packages/session-query/session-query/src/index.ts')
  for (const method of ['readSession', 'readSurface']) {
    assert.ok(new RegExp(`^\\s+async ${method}\\(`, 'm').test(engine), `SessionQueryEngine.${method} 不见了，host.js 读会话会静默返回空`)
  }
})

check('4. read 结果：ReadFileLine = { number, text }，ReadResultView 有 offset / lines', () => {
  const presentation = read('packages/core/tools/src/presentation.ts')
  const line = interfaceFields(presentation, 'ReadFileLine')
  assert.deepStrictEqual(line, { number: 'number', text: 'string' }, 'ReadFileLine 的形状变了，compute/window.js 与 client/session/position.js 要跟着改')
  assert.ok(/^\s+offset: number$/m.test(presentation), 'ReadResultView.offset 不再是 number')
  assert.ok(/^\s+lines: ReadFileLine\[\]$/m.test(presentation), 'ReadResultView.lines 不再是 ReadFileLine[]')
  const { readWindow } = require('../src/compute/window.js')
  const sample = { offset: 10, lines: [{ number: 10, text: 'a' }, { number: 12, text: 'b' }] }
  assert.deepStrictEqual(readWindow(sample, {}), { from: 10, to: 12 }, 'readWindow 没按 ReadFileLine[] 读')
})

check('5. 模块表：重复登记仍抛错，boot 行 id 就是包名', () => {
  const system = read('packages/client/modules/src/client/system.ts')
  assert.ok(/duplicate factory registration/.test(system), '模块表不再拒绝重复登记——bundle-reload.js 的模拟宿主要跟着改')
  const manifest = read('packages/client/modules/src/client/manifest.ts')
  assert.ok(/Entry name == package name/.test(manifest), 'WebBootEntry.id 不再等于包名，入口配对规则变了')
  const pkg = JSON.parse(lensSource('package.json')).name
  assert.ok(lensSource('src/client/entry.js').includes(`id: '${pkg}',`), `客户端入口登记的 id 不是包名 ${pkg}，宿主配不上，面板静默不出现`)
})

process.exitCode = failed === 0 ? 0 : 1
console.log(failed === 0 ? '\nALL PASS' : '\n' + failed + ' 项失败')
