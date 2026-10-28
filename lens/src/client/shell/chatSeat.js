// dsh-cdd-lens — 切到会话里的某个页（Chat / CDD Lens）。
//
// 这里只做一件事：把宿主会话区的某个页切出来。不开悬浮窗、不关宿主的详情面板、
// 不动任何布局 —— 逻辑图已经不悬浮了，它就是会话里的一页。
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

    var LENS_TAB = 'CDD Lens'

    /** 点开会话区里名字叫 name 的那一页；没找到就什么都不做。 */
    function activateTab(name) {
      var candidates = document.querySelectorAll('[role="tab"], button')
      for (var i = 0; i < candidates.length; i += 1) {
        if (String(candidates[i].textContent || '').trim() !== name) continue
        candidates[i].click()
        return true
      }
      return false
    }

    function activateChatTab() {
      return activateTab('对话')
    }

    /**
     * 跳到逻辑图：切到「CDD Lens」这一页，并把页内视图切成逻辑图。
     *
     * 只切页，不动布局。以前这里会关掉宿主的详情面板、强行开一个悬浮的 dock、再切
     * 宿主 tab——人只是想从轨迹这一行跳到图上那个节点，结果整页翻一遍，要追的节点
     * 反而更难找。
     */
    function jumpToGraph() {
      shared.wantGraph = (shared.wantGraph || 0) + 1
      publish()
      activateTab(LENS_TAB)
    }

    module.exports = { LENS_TAB, activateTab, activateChatTab, jumpToGraph }
    return module.exports
  },
})
