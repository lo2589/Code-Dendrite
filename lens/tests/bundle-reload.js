// 热更新契约：bundle 被 harness 重新执行时不许报 duplicate factory registration。
//
// harness 的模块系统（packages/client/modules/src/client/system.ts）：
//   register：同一个 id 登记第二次就抛 "duplicate factory registration"
//   invalidate(id)：只删这一个 id
// 热更新（packages/client/hmr/src/client/index.ts）只 invalidate 入口 id「dsh-cdd-lens」，
// 然后重新执行整个 bundle。以前 bundle 里 41 个部件各自登记，第一个部件就撞车，
// 新代码加载失败、旧代码继续跑——这就是控制台里反复出现的那条报错。
//
//   node lens/scripts/build.js && node lens/tests/bundle-reload.js
'use strict'
const fs = require('fs')
const vm = require('vm')
const path = require('path')
const assert = require('assert')

const BUNDLE = fs.readFileSync(path.join(__dirname, '..', 'lib', 'client.js'), 'utf8')

/** 照 harness 规则写的模块表：重复登记抛错，invalidate 只删一个 id。 */
function hostModules() {
  const factories = new Map()
  const cache = new Map()
  const React = { createElement: () => null, useState: v => [v, () => {}], useEffect: () => {}, useMemo: f => f(), useRef: v => ({ current: v }), useCallback: f => f }
  const require_ = (id) => {
    if (id === 'react') return React
    if (cache.has(id)) return cache.get(id)
    if (!factories.has(id)) throw new Error('client-modules: no registered factory for "' + id + '"')
    const value = factories.get(id)(require_)
    cache.set(id, value)
    return value
  }
  return {
    factories,
    require_,
    load(registration) {
      if (factories.has(registration.id)) {
        throw new Error('client-modules: duplicate factory registration for "' + registration.id + '" (bundle executed twice without invalidate?)')
      }
      factories.set(registration.id, registration.factory)
    },
    invalidate(id) {
      factories.delete(id)
      cache.delete(id)
    },
  }
}

const host = hostModules()
const context = {
  window: {
    __ModuleLoader__: { load: r => host.load(r) },
    localStorage: { getItem: () => '0', setItem() {}, removeItem() {} },
    location: { search: '?cddl-debug=0' }, addEventListener() {}, removeEventListener() {},
  },
  document: { createElement: () => ({ getContext: () => null }), querySelector: () => null, head: { appendChild() {} } },
  console, URLSearchParams, setTimeout, clearTimeout, setInterval, clearInterval,
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
}
vm.createContext(context)

let failed = 0
const check = (name, fn) => {
  try { fn(); console.log('ok   ' + name) } catch (error) { failed += 1; console.log('FAIL ' + name + ' — ' + error.message) }
}

check('第一次执行 bundle 不报错', () => vm.runInContext(BUNDLE, context))
check('入口 dsh-cdd-lens 已登记', () => assert(host.factories.has('dsh-cdd-lens')))
let first = null
check('入口能实例化出插件', () => { first = host.require_('dsh-cdd-lens'); assert.strictEqual(first.name, 'cdd-lens') })

// 热更新：只失效入口 id，再执行一次整个 bundle。
host.invalidate('dsh-cdd-lens')
check('热更新重新执行 bundle 不报 duplicate', () => vm.runInContext(BUNDLE, context))
check('入口重新登记成功', () => assert(host.factories.has('dsh-cdd-lens')))
let second = null
check('新入口实例化出新的插件对象', () => { second = host.require_('dsh-cdd-lens'); assert.strictEqual(second.name, 'cdd-lens'); assert.notStrictEqual(second, first) })

// 再来一次，连续热更新也不许坏。
host.invalidate('dsh-cdd-lens')
check('连续第二次热更新也不报错', () => { vm.runInContext(BUNDLE, context); assert(host.require_('dsh-cdd-lens').name === 'cdd-lens') })

console.log(failed === 0 ? 'ALL PASS' : failed + ' FAILED')
process.exit(failed === 0 ? 0 : 1)
