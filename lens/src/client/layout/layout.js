// dsh-cdd-lens — One graph in, one drawing out: the stages in order.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/layout',
  factory: (require) => {
    var module = { exports: {} }
    var __layout_prep = require('dsh-cdd-lens/layout/prep')
    var layoutScope = __layout_prep.layoutScope
    var rankFiles = __layout_prep.rankFiles
    var orientFlow = __layout_prep.orientFlow
    var __layout_space = require('dsh-cdd-lens/layout/space')
    var fitExtent = __layout_space.fitExtent
    var shiftPlacement = __layout_space.shiftPlacement
    var shiftDrawing = __layout_space.shiftDrawing
    var separateOverlaps = __layout_space.separateOverlaps
    var reclaimStrays = __layout_space.reclaimStrays
    var restackBoxes = __layout_space.restackBoxes
    var __layout_camera = require('dsh-cdd-lens/layout/camera')
    var cameraLayout = __layout_camera.cameraLayout
    var __layout_metrics = require('dsh-cdd-lens/layout/metrics')
    var boxMetrics = __layout_metrics.boxMetrics
    var __skins_tiers_route = require('dsh-cdd-lens/skins/tiers/route')
    var routeTiers = __skins_tiers_route.routeTiers
    var __layout_skin = require('dsh-cdd-lens/layout/skin')
    var skinFor = __layout_skin.skinFor
    var __state_store_skin = require('dsh-cdd-lens/state/store')
    var sharedSkin = __state_store_skin.shared
    var __skins_tiers_group = require('dsh-cdd-lens/skins/tiers/group')
    var placeTiers = __skins_tiers_group.placeTiers
    var __skins_pcb_group = require('dsh-cdd-lens/skins/pcb/group')
    var placeBoxes = __skins_pcb_group.placeBoxes
    var __skins_pcb_route = require('dsh-cdd-lens/skins/pcb/route')
    var routeBoard = __skins_pcb_route.routeBoard
    var reemitBoard = __skins_pcb_route.reemitBoard
    var __skins_flow_group = require('dsh-cdd-lens/skins/flow/group')
    var placeFlow = __skins_flow_group.placeFlow
    var __skins_flow_route = require('dsh-cdd-lens/skins/flow/route')
    var routeFlow = __skins_flow_route.routeFlow
    var reemitFlow = __skins_flow_route.reemitFlow
    var __layout_channels = require('dsh-cdd-lens/layout/channels')
    var buildChannels = __layout_channels.buildChannels
    var __routing_select = require('dsh-cdd-lens/routing/select')
    var chooseEdges = __routing_select.chooseEdges
    var __layout_gather = require('dsh-cdd-lens/layout/gather')
    var applyGather = __layout_gather.applyGather
    var freeGatherDragged = __layout_gather.freeGatherDragged

    /**
     * Turn one graph into one drawing.
     *
     * Every step is a file of its own: what is on screen, how it ranks, how
     * big the boxes are, where they go, which way each node faces, where the
     * corridors are, which relations earn a wire, and how those wires are
     * routed and emitted. Routing is the last stage and the only one the skin
     * decides, so replacing it replaces nothing else.
     * @param graph - nodes and edges to draw.
     * @param relationFilter - relation kinds the viewer left switched on.
     * @param avail - the canvas viewport width in CSS pixels.
     * @returns nodes, wires, labels, junctions, arrows, file boxes and size.
     */
    function layout(graph, relationFilter, avail) {
      if (graph.rootId === null) return { nodes: [], wires: [], labels: [], junctions: [], arrows: [], rows: [], files: [], width: 0, height: 0 }
      var scope = layoutScope(graph)
      var rank = rankFiles(graph, relationFilter, scope)
      var metrics = boxMetrics(graph, scope, avail)
      // Layers when `/chain` has said where everything goes, file boxes or
      // direction columns when it has not — or whichever of the three the
      // viewer asked for. They cannot be mixed: half a drawing laid out by
      // relation and half by directory is harder to read than either alone.
      var skin = skinFor(graph, scope.included, sharedSkin.skin || 'auto')
      var place = skin === 'tiers' ? placeTiers(graph, scope, metrics)
        : skin === 'flow' ? placeFlow(graph, scope, metrics)
        : placeBoxes(graph, scope, metrics)
      cameraLayout(graph, scope, place, rank, metrics)
      // A node dragged out of a running gather is out of its frame too —
      // before the restack, which would seat it again.
      freeGatherDragged(place)
      // Hand-placed coordinates are written in verbatim above, so this is the
      // first point at which a box can be on top of another, or off on its own
      // in an empty quarter because the layout changed shape under a saved
      // point. Pull the strays in first, then push apart what now collides.
      reclaimStrays(place, metrics, avail)
      separateOverlaps(place, metrics)
      // Frames stay in their grid slots; a drag reorders what is inside one.
      restackBoxes(place, metrics)
      // The gather overlay seats the selected node's callers and callees
      // beside it — after the restack, so a frame cannot take a gathered node
      // back, and before orientation and routing read the positions. With no
      // selection gathered it moves nothing and every skin draws as before.
      applyGather(graph, place, metrics)
      // The grid placed these boxes; deriving them again from where the
      // anchors ended up threw that away — and it ran after the separation
      // pass, so two files whose anchors had drifted together produced two
      // boxes on top of each other.
      var orient = orientFlow(graph, scope, place, metrics, avail)
      metrics.canvasWidth = orient.canvasWidth
      place.canvasY = orient.canvasY
      var channels = buildChannels(place, metrics)
      var edges = chooseEdges(graph, scope, orient)
      // Declared for both paths on purpose. These used to be `var`s inside the
      // else, which hoists them: the layered path then reached a `route` that
      // was always `undefined`, and the shift below threw on it — blanking the
      // whole view for any drawing that happened to need moving.
      var route = null
      var drawn
      if (skin === 'tiers') {
        // Layered drawings get a router that knows about layers: the gap under
        // a row is the only place a wire may run sideways, so a wire never
        // crosses a node it has nothing to do with.
        drawn = routeTiers(edges, orient, relationFilter, metrics)
        route = drawn.route
      } else if (skin === 'flow') {
        // Flow drawings get a router that knows about the corridors the
        // placement reserved between the columns: the only places a wire may
        // run at all.
        var flow = routeFlow(edges, orient, relationFilter, metrics)
        route = flow.route
        drawn = flow.drawn
      } else {
        var board = routeBoard(edges, orient, relationFilter, metrics, channels)
        route = board.route
        drawn = board.drawn
      }
      // The size comes from what was drawn. If any of it landed off the top
      // left, move the whole drawing into view and emit it again there —
      // routing does not change, only where its origin sits.
      var fit = fitExtent(place, drawn, metrics)
      if (fit.dx > 0 || fit.dy > 0) {
        shiftDrawing(place, route, fit.dx, fit.dy)
        drawn = reemitBoard(route, orient, metrics)
        fit = fitExtent(place, drawn, metrics)
      }
      return {
        nodes: place.placed, wires: drawn.wires, labels: drawn.labels,
        junctions: drawn.junctions, arrows: drawn.arrows, unrouted: drawn.unrouted,
        rows: place.rows || [], files: place.fileBoxes,
        width: Math.max(avail || 0, fit.maxX + metrics.PAD),
        height: Math.max(360, fit.maxY + metrics.PAD),
      }
    }

    module.exports = { layout }
    return module.exports
  },
})
