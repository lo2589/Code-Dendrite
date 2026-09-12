// dsh-cdd-lens — Corridors between the boxes.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/channels',
  factory: (require) => {
    var module = { exports: {} }

    /**
     * The gaps between box rows and columns, which is where wires travel.
     */
    function buildChannels(place, metrics) {
      var rowBands = place.rowBands
      var PAD = metrics.PAD
      var BOX_GAP_X = metrics.BOX_GAP_X
      var BOX_GAP_Y = metrics.BOX_GAP_Y
      var BOX_W = metrics.BOX_W
      var BOX_COLS = metrics.BOX_COLS

      // ---- channels --------------------------------------------------------
      //
      // A wire that cuts through a file box reads as if it connects to that
      // box's anchors. Measured on this graph, 57 of 123 segments crossed a box
      // they had nothing to do with — 46% of the drawing was lying about what
      // is related to what, and no amount of colour fixes that because the line
      // is genuinely on top of those nodes.
      //
      // So cross-box wires are confined to the gaps: a horizontal channel is the
      // space between two box rows, a vertical channel the space between two box
      // columns. A wire leaves its own box, travels only in channels, and enters
      // the target box. Inside a box you then see only that box's own wires.
      var hChannels = []
      for (var band = 0; band <= rowBands.length; band += 1) {
        if (band === 0) hChannels.push(rowBands.length === 0 ? PAD : rowBands[0].top - BOX_GAP_Y / 2)
        else hChannels.push(rowBands[band - 1].bottom + BOX_GAP_Y / 2)
      }
      var vChannels = []
      for (var col = 0; col <= BOX_COLS; col += 1) {
        vChannels.push(PAD + col * (BOX_W + BOX_GAP_X) - BOX_GAP_X / 2)
      }
      var nearest = function (list, value) {
        var best = list[0]
        for (var i = 1; i < list.length; i += 1) {
          if (Math.abs(list[i] - value) < Math.abs(best - value)) best = list[i]
        }
        return best
      }
      /**
       * Where a wire leaves a node sideways, and the node-free lane it lands in.
       *
       * The box's interior is two node columns with a gap between them and a
       * padding margin on each side; none of those three strips contains a
       * node, so a vertical run inside one of them cannot pass beneath an
       * anchor. The side is chosen by which way the wire is heading.
       */
      var innerLane = function (p, box, towards) {
        var leftward = towards < p.x + p.w / 2
        var port = leftward ? p.x : p.x + p.w
        var lane = leftward
          ? Math.max(box.x + 7, p.x - 10)
          : Math.min(box.x + box.w - 7, p.x + p.w + 10)
        return { port: port, lane: lane }
      }

      /** The channel just outside a box on the side facing `towards`. */
      var exitChannel = function (box, towards) {
        var below = towards > box.y + box.h / 2
        return nearest(hChannels, below ? box.y + box.h + BOX_GAP_Y / 2 : box.y - BOX_GAP_Y / 2)
      }

      return { hChannels: hChannels, vChannels: vChannels, nearest: nearest,
        innerLane: innerLane, exitChannel: exitChannel }
    }

    module.exports = { buildChannels }
    return module.exports
  },
})
