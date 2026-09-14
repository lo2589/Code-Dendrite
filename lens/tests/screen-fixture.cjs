// 测试夹具：把一张手搭的图变成 /screen 的样子，再交给 layout。
//
// 线上的 layout 只画 shared.screen（后端计算单元 src/compute 的结果）。布局测试是手搭
// graph 的，所以在调用 layout 之前按计算单元的形状补一份 screen：
//   图上的节点全部进树（shared.screenSide 里列出的放旁边），一条边一种类型。
'use strict'

/** 一条边带多个类型 → 拆成每种类型一条（和 /screen 给的边一样）。 */
function splitEdges(g) {
  const out = []
  const seen = new Set()
  for (const e of g.edges) {
    const types = Array.isArray(e.types) && e.types.length > 0 ? e.types : ['call']
    for (const type of types) {
      const key = e.from + '\0' + e.to + '\0' + type
      if (seen.has(key)) continue
      seen.add(key)
      out.push({ from: e.from, to: e.to, types: [type] })
    }
  }
  g.edges = out
}

function syncScreen(shared, g, side) {
  splitEdges(g)
  // 和计算单元一致：没给旁边名单时，一条边都不沾的节点连不进树，放旁边。
  const touched = new Set()
  g.edges.forEach(e => { touched.add(e.from); touched.add(e.to) })
  const aside = new Set(side || g.order.filter(id => !touched.has(id)))
  shared.screen = {
    nodes: g.order.filter(id => !aside.has(id)),
    side: g.order.filter(id => aside.has(id)),
    edges: g.edges.map(e => ({ from: e.from, to: e.to, type: e.types[0] })),
    buttons: {}, treeTotals: {}, pinned: [],
  }
}

/** 包一层 layout：每次画之前先按当前图补 screen。 */
function withScreen(layout, shared) {
  return (g, filter, avail) => {
    syncScreen(shared, g, shared.screenSide)
    return layout(g, filter, avail)
  }
}

module.exports = { splitEdges, syncScreen, withScreen }
