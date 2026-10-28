// dsh-cdd-lens — apply 握手：浏览器那一半真的跑起来了没有。
//
// harness 配不上入口、缺一个 inject 的服务、bundle 抛在工厂里，结果都是同一个：
// apply 从没被调用，面板不出现，哪里都不报错（Cordis 把缺依赖的插件挂在 PENDING，
// 静默）。/health 原来只能证明「磁盘上的 bundle 是新的」，证明不了「页面上跑的是它」。
//
// 客户端 apply 一开始就打一次 /applied?build=...，这里记下来；/health 原样报出。
// host 启动之后还没有页面 apply 过，就是 applied:false —— 那是要去查的信号，不是常态。
'use strict'

/**
 * 一张只增不减的回报表。
 *
 * @param declaredBuild - 读 build.json 当前戳的函数（每次现读，跟 /health 同源）。
 */
function makeHandshake(declaredBuild) {
  let count = 0
  let lastAt = null
  let lastBuild = null

  /** 客户端 apply 回报一次。build 缺失记成 null，不猜。 */
  function applied(build) {
    count += 1
    lastAt = new Date().toISOString()
    lastBuild = typeof build === 'string' && build.length > 0 ? build : null
  }

  /** 给 /health 的那一块。matchesBuild：最后一次 apply 的 bundle 是不是磁盘上这一版。 */
  function report() {
    return {
      applied: count > 0,
      count,
      lastAt,
      lastBuild,
      matchesBuild: count > 0 && lastBuild === declaredBuild(),
    }
  }

  return { applied, report }
}

module.exports = { makeHandshake }
