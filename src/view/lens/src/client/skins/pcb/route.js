// dsh-cdd-lens — The board skin: traces, buses and the hops where they cross.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/skins/pcb/route',
  factory: (require) => {
    var module = { exports: {} }
    var __routing_ortho = require('dsh-cdd-lens/routing/ortho')
    var routeOrtho = __routing_ortho.routeOrtho
    var __routing_bus = require('dsh-cdd-lens/routing/bus')
    var mergeBuses = __routing_bus.mergeBuses
    var __routing_lanes = require('dsh-cdd-lens/routing/lanes')
    var spreadLanes = __routing_lanes.spreadLanes
    var __routing_hops = require('dsh-cdd-lens/routing/hops')
    var markHops = __routing_hops.markHops
    var __routing_emit = require('dsh-cdd-lens/routing/emit')
    var emitWires = __routing_emit.emitWires
    var __routing_avoid = require('dsh-cdd-lens/routing/avoid')
    var repairCrossings = __routing_avoid.repairCrossings

    /**
     * The whole board pipeline, in one place instead of spelled out by the
     * orchestrator: route in the channels, merge what shares a run into a bus,
     * give each its own lane, mark the crossings as hops rather than joins,
     * and re-route whatever still cuts through a box.
     *
     * The polylines are handed back as well: a shift of the drawing translates
     * them and re-emits, without routing again.
     */
    function routeBoard(edges, orient, relationFilter, metrics, channels) {
      var route = routeOrtho(edges, orient, relationFilter, channels, metrics)
      mergeBuses(route)
      spreadLanes(route, metrics, orient)
      repairCrossings(route, orient, metrics)
      var hops = markHops(route)
      var drawn = emitWires(route, hops)
      return { route: route, drawn: drawn }
    }

    /** Same traces at a new origin: the polylines have already been moved. */
    function reemitBoard(route, orient, metrics) {
      var drawn = emitWires(route, markHops(route))
      return drawn
    }

    module.exports = { routeBoard, reemitBoard }
    return module.exports
  },
})
