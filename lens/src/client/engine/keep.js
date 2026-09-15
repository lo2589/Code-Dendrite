// dsh-cdd-lens — 工具栏上两个保留轮数的数字框。
//   editKeep：每个节点自己的计时器，edit 一次加 N 轮，过一轮减 1（默认 7）
//   readKeep：看过的节点第一次留 N 轮，再看 +1，过一轮减 1（默认 3）
//   用户：「算了搞个可以设置的数字吧」「edit和read都可以设置嘛」
// 默认值和 compute/evidence.js 同一个；设过的数存在浏览器里，下次打开还是它。
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/engine/keep',
  factory: (require) => {
    var module = { exports: {} }
    var __runtime_debug = require('dsh-cdd-lens/runtime/debug')
    var note = __runtime_debug.note

    var KEEPS = {
      editKeep: { key: 'cdd-lens.edit-keep.v1', fallback: 7, label: 'edit 保留' },
      readKeep: { key: 'cdd-lens.read-keep.v1', fallback: 3, label: 'read 保留' },
    }

    /** 上次在工具栏设过的数，没设过就是默认。@param field - 'editKeep' | 'readKeep' */
    function savedKeep(field) {
      try {
        var n = Number(window.localStorage.getItem(KEEPS[field].key))
        if (Number.isInteger(n) && n >= 1 && n <= 99) return n
      } catch (e) { /* 浏览器存储可选 */ }
      return KEEPS[field].fallback
    }

    /** 视图里这一项现在是几轮。 */
    function keepOf(view, field) {
      return view[field] || KEEPS[field].fallback
    }

    /**
     * 改一项保留轮数：不在 1–99 记 log 不改；改了存进浏览器。
     * @returns 真的改了返回 true（调用方据此重算屏幕）。
     */
    function applyKeep(view, field, value) {
      var spec = KEEPS[field]
      if (spec === undefined) return false
      var n = Math.round(Number(value))
      if (!(n >= 1 && n <= 99)) { note('btn', '✗ ' + spec.label + '轮数要在 1–99：' + value); return false }
      if (view[field] === n) return false
      note('btn', '设置 ' + spec.label + ' ' + keepOf(view, field) + ' → ' + n + ' 轮')
      view[field] = n
      try { window.localStorage.setItem(spec.key, String(n)) } catch (e) { /* 浏览器存储可选 */ }
      return true
    }

    module.exports = { KEEPS, savedKeep, keepOf, applyKeep }
    return module.exports
  },
})
