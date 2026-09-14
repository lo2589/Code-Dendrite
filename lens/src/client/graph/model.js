// dsh-cdd-lens — The accumulating node/edge store: pure graph operations.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/graph/model',
  factory: (require) => {
    var module = { exports: {} }

    // ---- graph store ------------------------------------------------------
    //
    // A node IS an anchor. `graph.nodes[id]` holds the record that came out of
    // `.codedendrite/anchors.json` — `symbol`, `file`, `line_start`, `callers`,
    // `mro`, `own_methods`, the lot — and nothing else. There is no wrapper and
    // no `node.anchor` hop: everything that wants to know about the code reads
    // the anchor, and anything the drawing needs about a node is either derived
    // from that record or kept in one of the side tables below.
    //
    // Two side tables, both keyed by anchor id, both outside the record:
    //
    //   graph.ui     —按钮和交互状态（谁按开了 up、谁在 loading、谁被 pin）。
    //                  这些是「你看它的方式」，不是「它是什么」，所以不写进
    //                  anchor，重画一次不会污染索引来的数据。
    //   graph.layout — 布局算出来的坐标和端口。布局产物，同样不写回 anchor。
    //
    // Anything typed into .codedendrite stays there; anything we invent lives
    // beside it and can be thrown away and recomputed.

    function emptyGraph() {
      return { nodes: {}, ui: {}, layout: {}, order: [], edges: [], rootId: null }
    }

    /** 每个 anchor 的交互状态。节点进图时建一次，之后只改字段。 */
    function emptyUI() {
      return {
        // 展开状态按「方向:关系」存：一个 anchor 有几个关系就挂几个按钮，各开各的。
        //   ui.open['down:call']     点开了 call 的下游
        //   ui.open['up:inherit']    点开了 inherit 的上游
        //   auto 前缀的是 gather 自动拉进来的，不算用户按过
        open: {},
        members: false, memberList: undefined,
        pinned: false, loading: null, error: null,
        explored: false, island: false, session: false,
        bridge: false, synthetic: false,
        // 这个节点最近一次被查看是哪一轮。看过的节点按轮次变旧、过期撤下；
        // edit 过的节点不看它，一直留着（判据在 graph/visible.fadedOut）。
        viewedAt: undefined,
        // 构图时就明确知道它被 edit 过（trace 还没到时用）。
        edited: false,
      }
    }

    /** anchor 记录的第一次出现，补上 id（索引里本来就带，防外部传裸记录）。 */
    function anchorRecord(anchor) {
      return anchor
    }

    function addNode(graph, anchor) {
      if (anchor === undefined || anchor === null || anchor.id === undefined) return false
      if (graph.nodes[anchor.id] !== undefined) {
        // 重新索引会换掉记录：整条替换，不留旧字段。
        graph.nodes[anchor.id] = anchorRecord(anchor)
        return false
      }
      graph.nodes[anchor.id] = anchorRecord(anchor)
      graph.ui[anchor.id] = emptyUI()
      graph.order.push(anchor.id)
      return true
    }

    /** 交互状态的读写口。没有这条 node 时返回 null，调用方不必自己判空。 */
    function uiOf(graph, id) {
      var entry = graph.ui[id]
      return entry === undefined ? null : entry
    }

    /** 布局产物（x/y/w/h/layer/ports）。算子只读它，不改 anchor。 */
    function placeOf(graph, id) {
      var entry = graph.layout[id]
      return entry === undefined ? null : entry
    }

    function setPlace(graph, id, place) {
      graph.layout[id] = place
      return place
    }

    /** 图上现有的 anchor id，按进入顺序。 */
    function nodeIds(graph) {
      return graph.order
    }

    function addEdge(graph, from, to, types) {
      for (var i = 0; i < graph.edges.length; i++) {
        if (graph.edges[i].from === from && graph.edges[i].to === to) {
          var found = graph.edges[i]
          ;(types || ['call']).forEach(function (type) {
            if (found.types.indexOf(type) < 0) found.types.push(type)
          })
          return found
        }
      }
      var edge = { from: from, to: to, types: types || ['call'] }
      graph.edges.push(edge)
      return edge
    }

    /**
     * Drop a node and every edge touching it. Revalidation is the only caller:
     * an anchor the rebuilt index no longer holds is not a node that went
     * invisible, it is a node that does not exist, and hiding it would keep
     * answering questions about code that is gone.
     */
    function removeNode(graph, id) {
      if (graph.nodes[id] === undefined) return false
      delete graph.nodes[id]
      delete graph.ui[id]
      delete graph.layout[id]
      graph.order = graph.order.filter(function (x) { return x !== id })
      graph.edges = graph.edges.filter(function (e) { return e.from !== id && e.to !== id })
      if (graph.rootId === id) graph.rootId = graph.order.length > 0 ? graph.order[0] : null
      return true
    }

    /** Ids reachable from the roots along currently expanded edges. */
    /**
     * How long an anchor the agent touched holds itself on the graph.
     *
     * Three turns after it was last mentioned. `node.session` alone kept every
     * anchor a session ever opened as a permanent root, so a long conversation
     * only ever accumulated — collapsing a branch freed nothing. Three turns is
     * long enough that the thing just being worked on never vanishes, and an
     * explicit pin overrides it and never expires.
     */

    module.exports = {
      emptyGraph, emptyUI, addNode, addEdge, removeNode,
      uiOf, placeOf, setPlace, nodeIds,
    }
    return module.exports
  },
})
