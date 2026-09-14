#!/usr/bin/env node
// Concatenate src/client/*.js into lib/client.js.
//
// The harness fetches ONE bundle URL (package.json `exports["./client"]`) and
// `host.js` greps that same file for the build stamp, so the delivered artifact
// has to stay a single file. The sources are real modules regardless: each one
// registers under its own id and reaches the others through `require`.
// Concatenation order is dependency order — `parts.json` carries it.
//
// 热更新：部件先登记到 bundle 自己的表里，宿主模块表只靠入口「dsh-cdd-lens」取插件。
//   harness 热更新（packages/client/hmr）只 invalidate 入口 id，然后重跑整个 bundle；
//   模块表（packages/client/modules/src/client/system.ts）对已登记的 id 再登记会抛
//   "duplicate factory registration"。以前 41 个部件各自往宿主表登记，第一个部件就撞车，
//   新代码加载失败、旧代码继续跑。现在入口的工厂在 bundle 自己的表里解析部件，
//   重跑一次拿到的就是这次执行出来的新部件。
//   部件 id 仍往宿主表登记一份（测试和按部件 id 取模块的调用方要用）；热更新时宿主已有
//   这些 id、会拒绝登记，这是预期的，吞掉即可——入口不经过宿主表取部件。
const fs = require('fs')
const path = require('path')

const ROOT = path.join(__dirname, '..')
const SRC = path.join(ROOT, 'src', 'client')
const OUT = path.join(ROOT, 'lib', 'client.js')
const ENTRY = 'dsh-cdd-lens'
const HOST_LOAD = 'window.__ModuleLoader__.load('
const LOCAL_LOAD = '__cddLocal.load('

const manifest = JSON.parse(fs.readFileSync(path.join(SRC, 'parts.json'), 'utf8'))
const build = JSON.parse(fs.readFileSync(path.join(ROOT, 'build.json'), 'utf8')).build

const header = [
  '// dsh-cdd-lens — browser half. GENERATED, DO NOT EDIT.',
  '//',
  '// Built from src/client/ by scripts/build.js. Edit the parts, not this file.',
  '// Parts register into the bundle\'s own table; the host module table only',
  '// receives the entry "' + ENTRY + '" (hot reload re-executes the bundle safely).',
  '//',
  `// build: ${build}`,
  `// parts: ${manifest.order.length}`,
  '',
].join('\n')

const prelude = [
  ';(function () {',
  'var __cddHost = window.__ModuleLoader__',
  'var __cddParts = {}',
  'var __cddLocal = { load: function (registration) { __cddParts[registration.id] = registration.factory } }',
  '',
].join('\n')

const epilogue = [
  '',
  '// 入口的工厂：部件从本次执行的表里取，其余（react 等）交给宿主。',
  'function __cddMount(hostRequire) {',
  '  var made = {}',
  '  var req = function (id) {',
  '    if (!Object.prototype.hasOwnProperty.call(__cddParts, id)) return hostRequire(id)',
  '    if (!Object.prototype.hasOwnProperty.call(made, id)) made[id] = __cddParts[id](req)',
  '    return made[id]',
  '  }',
  '  return req',
  '}',
  'Object.keys(__cddParts).forEach(function (id) {',
  `  if (id === '${ENTRY}') return`,
  '  try { __cddHost.load({ id: id, factory: __cddParts[id] }) } catch (e) { /* 热更新重跑：宿主已有这个部件 id，入口不经过宿主表 */ }',
  '})',
  `__cddHost.load({ id: '${ENTRY}', factory: function (hostRequire) { return __cddMount(hostRequire)('${ENTRY}') } })`,
  '})()',
  '',
].join('\n')

// `__CDD_BUILD__` 是给运行时代码用的占位符：构建戳的唯一真相是 build.json。
const parts = manifest.order.map((file) => {
  const text = fs.readFileSync(path.join(SRC, file), 'utf8')
  const count = text.split(HOST_LOAD).length - 1
  if (count !== 1) {
    console.error(`build.js: ${file} 里的 ${HOST_LOAD} 出现 ${count} 次，必须正好 1 次`)
    process.exit(1)
  }
  return text.replace(HOST_LOAD, LOCAL_LOAD).replace(/\s*$/, '\n').replace(/__CDD_BUILD__/g, build)
})

const bundle = header + '\n' + prelude + parts.join('\n') + epilogue
if (!bundle.includes(build)) {
  console.error(`build.js: the stamp ${build} is not in the bundle — host /health would report a drift`)
  process.exit(1)
}
if (!parts.some(text => text.includes(`id: '${ENTRY}',`))) {
  console.error(`build.js: 没有部件登记入口 id "${ENTRY}"`)
  process.exit(1)
}
fs.writeFileSync(OUT, bundle)
console.log(`lib/client.js  ${bundle.split('\n').length} lines  from ${manifest.order.length} parts  (${build})`)
