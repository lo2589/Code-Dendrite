// dsh-cdd-lens — Box and canvas measurements.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/metrics',
  factory: (require) => {
    var module = { exports: {} }
    var __layout_cardBox = require('dsh-cdd-lens/layout/cardBox')
    var cardBox = __layout_cardBox.cardBox
    var __graph_model = require('dsh-cdd-lens/graph/model')
    var uiOf = __graph_model.uiOf

    var SYMBOL_FONT = '11.5px ui-monospace, SFMono-Regular, Menlo, monospace'
    var measurer = null
    var measured = {}

    /**
     * How wide a string actually is in a given font.
     *
     * @param text - the string that will be drawn.
     * @param font - a CSS font shorthand, the same one the element uses.
     * @returns the width in CSS pixels; 0 if the browser will not measure.
     */
    function textWidth(text, font) {
      var key = font + '\u0000' + text
      if (measured[key] !== undefined) return measured[key]
      if (measurer === null) {
        try { measurer = document.createElement('canvas').getContext('2d') }
        catch (e) { measurer = false }
      }
      if (measurer === false || measurer === null) return text.length * 7
      measurer.font = font
      measured[key] = measurer.measureText(text).width
      return measured[key]
    }

    /**
     * The name a person would say out loud.
     *
     * `factory@1668.Draw.useEffect@1756.poll.then@1759` is a path to a closure,
     * not something anyone calls a thing. The last segment is what is meant.
     * @param symbol - the anchor's full symbol path.
     * @returns the last segment.
     */
    function shortSymbol(symbol) {
      var parts = String(symbol).split('.')
      return parts[parts.length - 1] || String(symbol)
    }

    /**
     * What to write on each node, given everything else on screen.
     *
     * The last segment is what a person says, so that is the default. But two
     * anchors can share it — `_get_line_content` exists in json_file.py and in
     * jsonl_file.py — and two identical boxes side by side are worse than two
     * long ones. A name only pays for the extra width when it actually collides.
     * @param graph - the graph being drawn.
     * @param included - the ids that will be drawn.
     * @returns id to the label that node should carry.
     */
    function labelsFor(graph, included) {
      var byShort = {}
      included.forEach(function (id) {
        var node = graph.nodes[id]
        if (node === undefined) return
        var name = shortSymbol(node.symbol)
        if (byShort[name] === undefined) byShort[name] = []
        byShort[name].push(id)
      })
      var out = {}
      Object.keys(byShort).forEach(function (name) {
        var group = byShort[name]
        group.forEach(function (id) {
          out[id] = group.length === 1 ? name : graph.nodes[id].symbol
        })
      })
      return out
    }

    /**
     * Box and canvas measurements, driven by the longest name on screen.
     */
    function boxMetrics(graph, scope, avail) {
      var included = scope.included
      var fileOrder = scope.fileOrder

      // Node width follows the longest symbol actually on screen, not a fixed
      // number. A truncated name is the one thing a code graph cannot afford:
      // `_get_line_co…` and `_get_line_count` are different functions and the
      // picture stops answering the question it exists to answer.
      //
      // One width for every node rather than per-node widths: a grid of equal
      // cells keeps the channels straight, and channels are what stop wires
      // running under the boxes.
      // One measured quantity, and everything else expressed against it. The
      // grid used to be a dozen independent pixel constants, so changing the
      // type size moved the text and left every gap, pad and clearance where it
      // was. CHAR_W is the width of one character in the monospace face the
      // cards are set in; the ratios below reproduce the sizes the drawing has
      // today, and now they follow the type instead of standing beside it.
      var CHAR_W = 7.4
      var em = function (k) { return Math.round(CHAR_W * k) }
      var PAD = em(2.43)
      var BOX_GAP_X = em(5.41)
      var BADGES = em(17.3)
      var longest = 0
      included.forEach(function (id) {
        var node = graph.nodes[id]
        var chars = node.symbol.length
        if (chars > longest) longest = chars
        var ui = uiOf(graph, id)
        if (ui !== null && ui.memberList !== undefined) {
          ui.memberList.forEach(function (m) {
            var own = m.symbol.split('.').pop().length + 2
            if (own > longest) longest = own
          })
        }
      })
      // Wide enough for the longest name on screen, but never wider than the
      // space actually available: a single box must always fit without
      // horizontal scrolling, whatever it is called.
      var roomForBox = Math.max(em(32.4), (avail || em(86.5)) - PAD * 2)
      var NODE_W = Math.max(em(27.03), Math.min(roomForBox - em(2.97), Math.ceil(longest * CHAR_W + BADGES)))
      var BOX_W = NODE_W + em(1.49) * 2
      var BOX_GAP_Y = em(5.41)
      var BOX_PAD = em(1.49)
      var BOX_HEAD = em(4.32)
      var INNER_GAP_X = em(2.70)
      var INNER_GAP_Y = em(1.89)
      // A wire leaves and enters through a port, and runs straight for this
      // much before it is allowed to turn — otherwise the head that says
      // which way it is going has nowhere to sit.
      // The gap between two layers has to hold the exit badge of one column,
      // the entry badge of the next, and the wire that joins them. A port sits
      // 29px clear of its box and is 24 wide, so two of them alone need 58 —
      // the 40 that BOX_GAP_X allows was set when layers were rows and the
      // badges were above and below, and it left them overlapping with the
      // wire hidden underneath.
      var PORT_CLEAR = em(3.92)
      var LAYER_GAP_X = PORT_CLEAR * 2 + 38
      var PORT_STUB = em(1.22)
      // How often a head is repeated along a run. One head at the far end
      // says nothing about the middle of a wire with four bends.
      var ARROW_EVERY = em(11.35)
      // The wire-routing sizes. Every skin routes with the same ones — a hop
      // that changed radius with the drawing would be a different diagram, not
      // a different view of it. WIRE_HOP is a radius, so it keeps its half
      // pixel: the arc is drawn with it twice (before and after the crossing),
      // and an integer here would move both.
      var LANE_STEP = em(1.62)          // 12 — one lane's worth of corridor
      var WIRE_HOP = em(1.22) / 2       // 4.5 — hop arc radius
      var WIRE_CORNER = em(1.35)        // 10 — rounded bend radius
      var CORRIDOR_MIN = em(1.08)       // 8 — narrowest usable corridor or side lane
      var SUBLANE_STEP = em(0.54)       // 4 — wires sharing one node gap fan out by this
      var HIT_PAD = em(0.41)            // 3 — a run this close to a box is through it
      // Two or three boxes across, and the boxes share out whatever width that
      // leaves. Deriving the count from a fixed box width instead put four and
      // five narrow boxes on a wide screen: every name wrapped, every box was
      // mostly padding, and the eye had no column to follow. The count leads
      // and the width follows.
      var usable = Math.max(320, (avail || 0) - PAD * 2)
      var WIDEST_ROW = 3
      var BOX_COLS = usable >= (BOX_W + BOX_GAP_X) * 2 ? WIDEST_ROW : 1
      if (BOX_COLS === WIDEST_ROW && usable < (BOX_W + BOX_GAP_X) * WIDEST_ROW) BOX_COLS = 2
      if (fileOrder.length === 1) BOX_COLS = 1
      if (fileOrder.length < BOX_COLS) BOX_COLS = fileOrder.length
      // The box stays the width of the longest name plus its padding — it is
      // not stretched to fill the row. Stretching gave 360px cards holding a
      // twelve-character symbol, mostly empty. The width a row does not need
      // goes into the gutters between the columns, which is where the traces
      // run anyway.
      var COL_STRIDE = BOX_COLS > 1
        ? Math.max(BOX_W + BOX_GAP_X, Math.floor((usable - BOX_W) / (BOX_COLS - 1)))
        : BOX_W + BOX_GAP_X
      // No floor. A hardcoded minimum of 920 held the canvas wider than the
      // boxes it contains, so narrowing the window correctly dropped to one
      // column and then overflowed anyway — the drawing insisted on a width
      // nothing asked for.
      var canvasWidth = PAD * 2 + BOX_COLS * BOX_W + Math.max(0, BOX_COLS - 1) * BOX_GAP_X
      // Measured, not guessed. A pixels-per-character constant was wrong for
      // every font it was not tuned on, and there were two different ones in
      // this codebase for the same face — which is the tell that neither was
      // ever measured. One offscreen canvas answers exactly.
      // Read off the stylesheet that draws the card, not copied out of it: two
      // numbers for one thing in two files drift the next time the card gains a
      // row. See layout/cardBox.js.
      var CARD = cardBox()
      var CARD_BASE = CARD.base
      var MEMBERS_CHROME = CARD.membersChrome
      var MEMBER_ROW = CARD.memberRow
      var MORE_ROW = CARD.moreRow

      var label = labelsFor(graph, included)
      var sizeOf = function (id, widthLimit) {
        var node = graph.nodes[id]
        var ui = uiOf(graph, id) || {}
        var text = label[id] === undefined ? shortSymbol(node.symbol) : label[id]
        var badge = 46
        var chrome = 22 + 14 + 16
        // Keep one small readability gutter between the symbol and its badges;
        // exact text width left `dispatch_command` wrapping at the underscore.
        var own = Math.ceil(textWidth(text, SYMBOL_FONT)) + badge + chrome + 72
        var width = Math.max(150, Math.min(NODE_W, widthLimit || NODE_W, own))
        // Colliding names intentionally keep their fully-qualified symbol.
        // On a narrow vertical canvas the name wraps inside the card instead
        // of silently making the whole graph horizontally scrollable.
        var reserved = node.kind === 'class' || node.members > 0 ? 142 : 96
        var textRoom = Math.max(72, width - reserved)
        var lines = Math.max(1, Math.ceil(textWidth(text, SYMBOL_FONT) / textRoom))
        var wrapped = (lines - 1) * CARD.symLine
        return {
          // Never wider than the space there is, never so narrow the buttons
          // underneath do not fit.
          w: width,
          // Added up from the card's own CSS rather than guessed. The width
          // above is measured — the comment above it says so — while the height
          // was a flat 70 for a plain card that actually draws 55. Every row in
          // every box carried fifteen pixels of slack that nothing was in, and
          // the boxes were that much taller than their contents.
          h: ui.members && ui.memberList !== undefined
            ? CARD_BASE + MEMBERS_CHROME + ui.memberList.length * MEMBER_ROW + MORE_ROW + wrapped
            : CARD_BASE + wrapped,
        }
      }
      return { PAD: PAD, BOX_GAP_X: BOX_GAP_X, BOX_GAP_Y: BOX_GAP_Y, BOX_PAD: BOX_PAD,
        BOX_HEAD: BOX_HEAD, BOX_W: BOX_W, BOX_COLS: BOX_COLS, NODE_W: NODE_W,
        INNER_GAP_X: INNER_GAP_X, INNER_GAP_Y: INNER_GAP_Y,
        PORT_STUB: PORT_STUB, ARROW_EVERY: ARROW_EVERY,
        PORT_CLEAR: PORT_CLEAR, LAYER_GAP_X: LAYER_GAP_X, COL_STRIDE: COL_STRIDE,
        LANE_STEP: LANE_STEP, WIRE_HOP: WIRE_HOP, WIRE_CORNER: WIRE_CORNER, CORRIDOR_MIN: CORRIDOR_MIN,
        SUBLANE_STEP: SUBLANE_STEP, HIT_PAD: HIT_PAD,
        canvasWidth: canvasWidth, sizeOf: sizeOf, label: label }
    }

    module.exports = { boxMetrics, textWidth, shortSymbol, labelsFor }
    return module.exports
  },
})
