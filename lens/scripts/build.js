#!/usr/bin/env node
// Concatenate src/client/*.js into lib/client.js.
//
// The harness fetches ONE bundle URL (package.json `exports["./client"]`) and
// `host.js` greps that same file for the build stamp, so the delivered artifact
// has to stay a single file. The sources are real modules regardless: each one
// registers itself with `window.__ModuleLoader__` under its own id and reaches
// the others through `require`, which the client module system answers from its
// registered-factory table. Concatenation order is therefore dependency order —
// a factory materializes on first require, and a part must already be
// registered when its consumer runs. `parts.json` carries that order; the
// generator refuses to write a cycle, because CJS factory form cannot deliver
// partial exports and the module system throws on one.
const fs = require('fs')
const path = require('path')

const ROOT = path.join(__dirname, '..')
const SRC = path.join(ROOT, 'src', 'client')
const OUT = path.join(ROOT, 'lib', 'client.js')

const manifest = JSON.parse(fs.readFileSync(path.join(SRC, 'parts.json'), 'utf8'))
const build = JSON.parse(fs.readFileSync(path.join(ROOT, 'build.json'), 'utf8')).build

const header = [
  '// dsh-cdd-lens — browser half. GENERATED, DO NOT EDIT.',
  '//',
  '// Built from src/client/ by scripts/build.js. Edit the parts, not this file.',
  '// Written in the shape tsdown emits (`__ModuleLoader__.load` + a CJS body +',
  '// the loader\'s `require`), so a generated bundle drops in on top.',
  '//',
  `// build: ${build}`,
  `// parts: ${manifest.order.length}`,
  '',
].join('\n')

// `__CDD_BUILD__` 是给运行时代码用的占位符：调试栏要显示这次跑的是哪一版，
// 而构建戳的唯一真相是 build.json。写死字面量迟早和 build.json 漂开
// （之前 api.js 里就钉着 V1_20 的旧串），所以在这里统一替换。
const body = manifest.order
  .map(file => fs.readFileSync(path.join(SRC, file), 'utf8')
    .replace(/\s*$/, '\n')
    .replace(/__CDD_BUILD__/g, build))
  .join('\n')

const bundle = header + '\n' + body
if (!bundle.includes(build)) {
  console.error(`build.js: the stamp ${build} is not in the bundle — host /health would report a drift`)
  process.exit(1)
}
fs.writeFileSync(OUT, bundle)
console.log(`lib/client.js  ${bundle.split('\n').length} lines  from ${manifest.order.length} parts  (${build})`)
