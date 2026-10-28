// dsh-cdd-lens — Reaching the Chat tab and opening the dock beside it.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/shell/chatSeat',
  factory: (require) => {
    var module = { exports: {} }
    var __state_store = require('dsh-cdd-lens/state/store')
    var publish = __state_store.publish
    var shared = __state_store.shared

    // ---- the floating panel (shell.overlay) --------------------------------

    function activateChatTab() {
      var candidates = document.querySelectorAll('[role="tab"], button')
      for (var i = 0; i < candidates.length; i += 1) {
        if (String(candidates[i].textContent || '').trim() !== '对话') continue
        candidates[i].click()
        return true
      }
      return false
    }

    function openDockBesideChat(ctx) {
      try {
        var layoutService = ctx.get('layout')
        if (layoutService) layoutService.closeDetails()
      } catch (e) { /* optional host service */ }
      shared.dockOpen = true
      shared.wantGraph = (shared.wantGraph || 0) + 1
      publish()
      window.requestAnimationFrame(activateChatTab)
    }

    /**
     * 跳到逻辑图：只切视图，不动布局。
     *
     * 以前这里直接走 openDockBesideChat——它会关掉宿主的详情面板、强行开 dock、再切
     * 宿主的 tab。人只是想「从轨迹这一行跳到图上那个节点」，结果整页翻了一遍，所有
     * 东西换了位置：要追的那个节点反而更难找了。已经开着就什么都不动，只把视图切到
     * 逻辑图；只有确实没开，才去开。
     */
    function jumpToGraph(ctx) {
      if (shared.dockOpen === true) {
        shared.wantGraph = (shared.wantGraph || 0) + 1
        publish()
        return
      }
      openDockBesideChat(ctx)
    }

    module.exports = { activateChatTab, openDockBesideChat, jumpToGraph }
    return module.exports
  },
})
