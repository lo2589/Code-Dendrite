// dsh-cdd-lens — How tall a card is, read off the stylesheet that draws it.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/cardBox',
  factory: (require) => {
    var module = { exports: {} }
    var __styles_graph = require('dsh-cdd-lens/styles/graph')
    var GRAPH_CSS = __styles_graph.GRAPH_CSS

    /** The first `prop:` value inside the rule for `selector`, in pixels. */
    function pxFrom(css, selector, prop) {
      var text = css.join('')
      var at = text.indexOf(selector + '{')
      if (at < 0) return null
      var end = text.indexOf('}', at)
      var body = text.slice(at + selector.length + 1, end < 0 ? undefined : end)
      var hit = new RegExp('(?:^|;)\\s*' + prop + '\\s*:\\s*(-?[0-9.]+)px').exec(body)
      return hit === null ? null : parseFloat(hit[1])
    }

    /**
     * The height of a card, from the rules that draw it.
     *
     * The layout has to reserve exactly what a card takes, and it used to
     * reserve a flat 70 for something that draws 55 — fifteen pixels of slack
     * under every anchor in every box. Writing 55 down instead only moves the
     * problem: two numbers for one thing, in two files, free to drift the next
     * time the card gains a row or loses some padding.
     *
     * So the stylesheet is the single truth and this reads it. A rule that
     * changes shape enough to stop matching falls back to what it measures
     * today, which keeps a drawing on screen rather than collapsing it.
     *
     * @returns { base, membersChrome, memberRow, moreRow, symLine }
     */
    function cardBox() {
      var css = GRAPH_CSS
      var border = pxFrom(css, '.cddl-gnode', 'border')
      var pad = pxFrom(css, '.cddl-gnode', 'padding')
      var symLine = pxFrom(css, '.cddl-gnode .cddl-sym', 'line-height')
      var actionsGap = pxFrom(css, '.cddl-node-actions', 'margin-top')
      var actionsRow = pxFrom(css, '.cddl-node-actions button', 'height')
      var membersTop = pxFrom(css, '.cddl-members', 'margin-top')
      var membersPad = pxFrom(css, '.cddl-members', 'padding-top')
      var memberPad = pxFrom(css, '.cddl-m', 'padding')
      var morePad = pxFrom(css, '.cddl-more', 'padding')

      var or = function (value, fallback) { return value === null ? fallback : value }
      border = or(border, 1)
      pad = or(pad, 7)
      symLine = or(symLine, 16)
      actionsGap = or(actionsGap, 4)
      actionsRow = or(actionsRow, 19)

      return {
        symLine: symLine,
        base: border * 2 + pad * 2 + symLine + actionsGap + actionsRow,
        // A member row is its own padding twice plus one line of text; the
        // divider above the list is a border plus the padding either side.
        membersChrome: or(membersTop, 6) + border + or(membersPad, 5),
        memberRow: or(memberPad, 2) * 2 + symLine + 2,
        moreRow: or(morePad, 5) * 2 + symLine - 4,
      }
    }

    module.exports = { pxFrom, cardBox }
    return module.exports
  },
})
