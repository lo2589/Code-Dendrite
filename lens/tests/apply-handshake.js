// apply 握手：客户端 apply 真跑了，/health 才说 applied:true，而且报的是哪一版。
//
// 两半都真跑，不读源码猜：
//   浏览器半：在 vm 里执行 lib/client.js，实例化入口、调 apply，看它打出去的请求。
//   host 半：用假的 webServer 挂上 src/host.js，直接调 /applied 和 /health 的 handler。
//
//   node lens/scripts/build.js && node lens/tests/apply-handshake.js
'use strict'
const fs = require('fs')
const vm = require('vm')
const path = require('path')
const assert = require('assert')

const ROOT = path.join(__dirname, '..')
const BUILD = JSON.parse(fs.readFileSync(path.join(ROOT, 'build.json'), 'utf8')).build

let failed = 0
const check = async (name, fn) => {
  try { await fn(); console.log('ok   ' + name) } catch (error) { failed += 1; console.log('FAIL ' + name + ' — ' + error.message) }
}

/** 在 vm 里跑 bundle，返回入口插件和它打出去的每个 URL。 */
function loadClient() {
  const factories = new Map()
  const cache = new Map()
  const React = { createElement: () => null, useState: v => [v, () => {}], useEffect: () => {}, useMemo: f => f(), useRef: v => ({ current: v }), useCallback: f => f }
  const require_ = (id) => {
    if (id === 'react') return React
    if (!cache.has(id)) cache.set(id, factories.get(id)(require_))
    return cache.get(id)
  }
  const urls = []
  const context = {
    window: {
      __ModuleLoader__: { load: r => { if (!factories.has(r.id)) factories.set(r.id, r.factory) } },
      localStorage: { getItem: () => '0', setItem() {}, removeItem() {} },
      location: { search: '?cddl-debug=0' }, addEventListener() {}, removeEventListener() {},
    },
    document: { createElement: () => ({ getContext: () => null }), querySelector: () => null, head: { appendChild() {} } },
    console, URLSearchParams, setTimeout, clearTimeout, setInterval, clearInterval,
    fetch: (url) => { urls.push(url); return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) }) },
  }
  vm.createContext(context)
  vm.runInContext(fs.readFileSync(path.join(ROOT, 'lib', 'client.js'), 'utf8'), context)
  return { plugin: require_('dsh-cdd-lens'), urls }
}

/** 挂上 host 半，返回「按路径调 handler 拿 JSON」的函数和卸载函数。 */
function mountHost() {
  const routes = new Map()
  const effects = []
  const services = { webServer: { register: (r) => { routes.set(r.path, r.handler); return () => {} } } }
  const ctx = { get: name => services[name], effect: (fn) => { effects.push(fn()) } }
  require('../src/host.js').apply(ctx, {})
  const call = (url) => new Promise((resolve) => {
    const handler = routes.get(url.split('?')[0])
    assert.ok(handler, 'host 没注册 ' + url)
    let status = 0
    handler({ url }, { writeHead: (s) => { status = s }, end: (body) => resolve({ status, body: JSON.parse(body) }) })
  })
  return { call, unmount: () => effects.forEach(dispose => typeof dispose === 'function' && dispose()) }
}

async function main() {
  await check('浏览器半：apply 第一件事就打 /applied，带的是这一版的戳', () => {
    const { plugin, urls } = loadClient()
    plugin.apply({ get: () => undefined, effect() {} }) // 没有 slots：面板挂不上，但回报照样要发
    const hit = urls.find(u => u.startsWith('/plugins/cdd-lens/applied?'))
    assert.ok(hit, '没打 /applied，打出去的是：' + JSON.stringify(urls))
    assert.strictEqual(new URLSearchParams(hit.split('?')[1]).get('build'), BUILD)
  })

  const host = mountHost()
  try {
    await check('host 半：没有页面 apply 过，/health 说 applied:false', async () => {
      const { body } = await host.call('/plugins/cdd-lens/health')
      assert.strictEqual(body.build, BUILD)
      assert.deepStrictEqual(body.client, { applied: false, count: 0, lastAt: null, lastBuild: null, matchesBuild: false })
    })
    await check('host 半：apply 回报一次旧版，matchesBuild:false', async () => {
      await host.call('/plugins/cdd-lens/applied?build=V0_OLD')
      const { body } = await host.call('/plugins/cdd-lens/health')
      assert.strictEqual(body.client.applied, true)
      assert.strictEqual(body.client.lastBuild, 'V0_OLD')
      assert.strictEqual(body.client.matchesBuild, false)
    })
    await check('host 半：再回报这一版，count=2、matchesBuild:true', async () => {
      await host.call('/plugins/cdd-lens/applied?build=' + BUILD)
      const { body } = await host.call('/plugins/cdd-lens/health')
      assert.strictEqual(body.client.count, 2)
      assert.strictEqual(body.client.matchesBuild, true)
      assert.ok(!Number.isNaN(Date.parse(body.client.lastAt)))
    })
  } finally {
    host.unmount()
  }

  process.exitCode = failed === 0 ? 0 : 1
  console.log(failed === 0 ? '\nALL PASS' : '\n' + failed + ' 项失败')
}

main()
