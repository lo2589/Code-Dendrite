// dsh-cdd-lens — Bezier wires for dataflow and dependency edges.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/routing/curve',
  factory: (require) => {
    var module = { exports: {} }
    var __view_record = require('dsh-cdd-lens/view/record')
    var stateOf = __view_record.stateOf

    /**
     * Soft curves for the relations the orthogonal router does not carry.
     */
    function emitCurves(edges, orient, relationFilter, drawn) {
      var chosen = edges.chosen
      var byId = orient.byId
      var wires = drawn.wires
      var arrows = drawn.arrows

      var cubicPoint = function (p0, p1, p2, p3, t) {
        var u = 1 - t
        return {
          x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
          y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y,
        }
      }
      var cubicAngle = function (p0, p1, p2, p3, t) {
        var u = 1 - t
        var dx = 3 * u * u * (p1.x - p0.x) + 6 * u * t * (p2.x - p1.x) + 3 * t * t * (p3.x - p2.x)
        var dy = 3 * u * u * (p1.y - p0.y) + 6 * u * t * (p2.y - p1.y) + 3 * t * t * (p3.y - p2.y)
        return Math.atan2(dy, dx) * 180 / Math.PI
      }
      chosen.forEach(function (edge) {
        var from = byId[edge.from]
        var to = byId[edge.to]
        ;(edge.types || ['call']).filter(function (type) {
          return relationFilter === undefined || relationFilter[type] !== false
        }).forEach(function (type) {
          var isData = type === 'dataflow'
          var yOffset = isData ? 6 : -6
          var fromRight = from.flowDir !== 'rtl'
          var toEntryRight = to.flowDir === 'rtl'
          var p0 = { x: fromRight ? from.x + from.w : from.x, y: from.y + from.h / 2 + yOffset }
          var p3 = { x: toEntryRight ? to.x + to.w : to.x, y: to.y + to.h / 2 + yOffset }
          var bend = Math.max(52, Math.abs(p3.y - p0.y) * .20, Math.abs(p3.x - p0.x) * .22)
          var p1 = { x: p0.x + (fromRight ? bend : -bend), y: p0.y }
          var p2 = { x: p3.x + (toEntryRight ? bend : -bend), y: p3.y }
          var id = edge.from + '→' + edge.to + ':' + type
          var faded = stateOf(edge.to) !== null && stateOf(edge.to) !== undefined && !stateOf(edge.to).remembered
          wires.push({
            id: id,
            d: 'M' + p0.x + ',' + p0.y + ' C' + p1.x + ',' + p1.y + ' ' + p2.x + ',' + p2.y + ' ' + p3.x + ',' + p3.y,
            type: type, faded: faded,
            fromFile: from.file, toFile: to.file,
            from: edge.from, to: edge.to,
          })
          var at = cubicPoint(p0, p1, p2, p3, .78)
          arrows.push({
            id: id + ':arrow', wireId: id, from: edge.from, to: edge.to,
            x: at.x, y: at.y, angle: cubicAngle(p0, p1, p2, p3, .78),
            type: type, faded: faded,
          })
        })
      })

    }

    module.exports = { emitCurves }
    return module.exports
  },
})
