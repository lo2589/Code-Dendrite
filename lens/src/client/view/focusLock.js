// dsh-cdd-lens — 焦点锁：重排之后，正在看的那张卡片不许跑。
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/view/focusLock',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var useEffect = React.useEffect
    var useRef = React.useRef
    var __state_store = require('dsh-cdd-lens/state/store')
    var shared = __state_store.shared

    /** 这个节点在**内容坐标**里的位置（和滚到哪儿无关）。 */
    function spotOf(scroller, id) {
      if (scroller === null || scroller === undefined || typeof id !== 'string' || id === '') return null
      var el = null
      var all = scroller.querySelectorAll('[data-node-id]')
      for (var i = 0; i < all.length; i += 1) {
        if (all[i].getAttribute('data-node-id') === id) { el = all[i]; break }
      }
      if (el === null) return null
      return { x: el.offsetLeft, y: el.offsetTop }
    }

    /** 该钉住谁：选中的那张；没有选中就钉视口中间那张。 */
    function pickFocus(scroller) {
      if (typeof shared.selected === 'string' && spotOf(scroller, shared.selected) !== null) return shared.selected
      var mid = scroller.scrollTop + scroller.clientHeight / 2
      var all = scroller.querySelectorAll('[data-node-id]')
      var best = null
      var bestGap = Infinity
      for (var i = 0; i < all.length; i += 1) {
        var gap = Math.abs(all[i].offsetTop + all[i].offsetHeight / 2 - mid)
        if (gap < bestGap) { bestGap = gap; best = all[i].getAttribute('data-node-id') }
      }
      return best
    }

    /**
     * 重排后把焦点卡片钉回原来的屏幕位置，整张画布跟着它挪。
     *
     * 布局重算会让整列卡片平移——实测索引换一版，9 张卡片里 8 张动了，竖直 69px。
     * 人正盯着一张卡片追代码，卡片跑了就是丢焦点。这里不碰布局怎么算，只在它算完
     * 之后，按焦点卡片在内容坐标里的位移，把画布滚动同样多。
     *
     * 为什么用内容坐标而不是屏幕坐标：用户自己滚动只改 scrollTop、不改内容坐标，
     * 所以这把锁不会跟用户的滚动打架；只有布局真的挪了东西，它才出手。
     *
     * 换了焦点（点了别的卡片）的那一次只记位置、不补偿：那次移动是用户自己要的。
     */
    function useFocusLock(scrollerRef) {
      var mark = useRef(null)
      useEffect(function () {
        var scroller = scrollerRef === null || scrollerRef === undefined ? null : scrollerRef.current
        if (scroller === null || scroller === undefined || scroller.querySelectorAll === undefined) return
        var kept = mark.current !== null && spotOf(scroller, mark.current.id) !== null ? mark.current.id : null
        var id = typeof shared.selected === 'string' && spotOf(scroller, shared.selected) !== null
          ? shared.selected
          : (kept !== null ? kept : pickFocus(scroller))
        var now = spotOf(scroller, id)
        if (now === null) { mark.current = null; return }
        var was = mark.current
        if (was !== null && was.id === id && (was.x !== now.x || was.y !== now.y)) {
          scroller.scrollLeft += now.x - was.x
          scroller.scrollTop += now.y - was.y
        }
        mark.current = { id: id, x: now.x, y: now.y }
      })
    }

    module.exports = { spotOf, pickFocus, useFocusLock }
    return module.exports
  },
})
