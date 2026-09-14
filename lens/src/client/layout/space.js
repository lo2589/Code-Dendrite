// dsh-cdd-lens — Where things end up: fitting the drawing, and unpicking overlaps.
//
// Two halves of one job. A placement is proposed, and then it has to be made
// true: nothing off the top or left edge, nothing sitting on top of anything
// else, no anchor stranded outside the frame that owns it. Both halves read
// and write the same placed boxes, and splitting them across two files only
// made the order they run in harder to see.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/layout/space',
  factory: (require) => {
    var module = { exports: {} }
    /**
     * The canvas has to hold everything that was drawn, not just the nodes.
     *
     * A wire leaves its node — into a channel, out along a bus lane, over a
     * hop — and a curve's control points reach further still. None of that is
     * inside any node's box, so sizing the canvas from node positions leaves
     * geometry at negative coordinates, and scrollLeft stops at zero: those
     * pixels cannot be brought into view by any amount of panning. They are
     * drawn and they are gone. So the size comes from the drawing.
     * @param place - the positioned nodes and file boxes.
     * @param drawn - wires, labels, junctions and arrows as emitted.
     * @param metrics - box metrics; its PAD is the margin kept around it all.
     * @returns the real bounds, and the shift that would clear the top left.
     */
    function fitExtent(place, drawn, metrics) {
      var PAD = metrics.PAD
      var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      var see = function (x, y) {
        if (typeof x !== 'number' || typeof y !== 'number') return
        if (!isFinite(x) || !isFinite(y)) return
        if (x < minX) minX = x
        if (x > maxX) maxX = x
        if (y < minY) minY = y
        if (y > maxY) maxY = y
      }
      var box = function (b) { see(b.x, b.y); see(b.x + b.w, b.y + b.h) }
      place.placed.forEach(box)
      ;(place.fileBoxes || []).forEach(box)
      ;(drawn.junctions || []).forEach(function (j) { see(j.x, j.y) })
      ;(drawn.labels || []).forEach(function (l) { see(l.x, l.y) })
      ;(drawn.arrows || []).forEach(function (a) { see(a.x, a.y) })
      ;(drawn.wires || []).forEach(function (wire) {
        if (wire.bounds) {
          see(wire.bounds.minX, wire.bounds.minY)
          see(wire.bounds.maxX, wire.bounds.maxY)
        } else {
          ;(wire.pts || []).forEach(function (p) { see(p.x,p.y) })
        }
      })
      if (minX === Infinity) return { dx: 0, dy: 0, minX: 0, minY: 0, maxX: 0, maxY: 0 }
      return {
        dx: Math.max(0, PAD - minX), dy: Math.max(0, PAD - minY),
        minX: minX, minY: minY, maxX: maxX, maxY: maxY,
      }
    }

    /**
     * Move everything the placement owns, so nothing sits left of or above
     * the origin.
     *
     * A node keeps the coordinate it was SAVED at in `baseX`/`baseY`. Dragging
     * writes that one back, so the margin the wires happened to need this time
     * never folds into a stored position and never accumulates across renders.
     *
     * Row labels travel with the rows they name. `rowBands` is deliberately
     * left where it is: `buildChannels` has already read it by the time
     * anything can need shifting, and nothing reads it afterwards.
     * @param place - nodes, file boxes and row labels, moved in place.
     * @param dx - how far right to move everything.
     * @param dy - how far down to move everything.
     */
    function shiftPlacement(place, dx, dy) {
      if (dx === 0 && dy === 0) return
      place.placed.forEach(function (p) {
        if (p.baseX === undefined) { p.baseX = p.x; p.baseY = p.y }
        p.x += dx
        p.y += dy
      })
      ;(place.fileBoxes || []).forEach(function (b) { b.x += dx; b.y += dy })
      ;(place.rows || []).forEach(function (row) { row.x += dx; row.y += dy })
    }

    /**
     * Move the placement together with the polylines routed through it.
     *
     * Only the orthogonal router keeps polylines of its own. The layered one
     * reads each wire off the two boxes it joins, so for that path moving the
     * boxes and asking again is the same translation — see `layout`.
     * @param place - nodes, file boxes and row labels, moved in place.
     * @param route - the routed polylines, moved in place.
     * @param dx - how far right to move everything.
     * @param dy - how far down to move everything.
     */
    function shiftDrawing(place, route, dx, dy) {
      if (dx === 0 && dy === 0) return
      shiftPlacement(place, dx, dy)
      route.polylines.forEach(function (line) {
        line.pts.forEach(function (pt) { pt.x += dx; pt.y += dy })
      })
    }

    /**
     * No box may sit on top of another.
     *
     * Automatic placement never overlaps, but a coordinate the user dragged is
     * written in verbatim, and two anchors dropped near each other simply
     * covered one another — the one underneath unreadable and unclickable, with
     * wires then routed straight through both. Overlap is never what was meant
     * by dropping a box somewhere, so the boxes are separated afterwards.
     *
     * Pairs are pushed apart along whichever axis they overlap least, which
     * moves each box the shortest distance that resolves it. A box the user
     * placed by hand yields less than one the layout placed, so the drag is
     * still respected; when both were placed by hand they share the push.
     *
     * @param place - placed boxes, moved in place.
     * @param metrics - box metrics; only the gap sizes are read.
     * @returns how many boxes ended up moving.
     */
    function separateOverlaps(place, metrics) {
      // Anchors inside a frame are laid out again by restackBoxes immediately
      // after this, so pushing them apart here is work that is then thrown
      // away — and it is the expensive kind: every pair, twelve times over.
      // At a thousand anchors that was six million comparisons per layout, on
      // a layout that reruns on zoom, selection and a width poll.
      // Anchors a frame will lay out again are still skipped — that pass throws
      // this work away, and it is the expensive kind: every pair, twelve times
      // over. But an anchor the user placed is NOT laid out again any more, so
      // it has to be in here or two dragged cards simply cover each other.
      var boxes = place.placed.filter(function (p) {
        return p.boxKey === undefined || p.manual === true || p.pinned === true
      })
      if (boxes.length < 2) return 0
      var MARGIN = Math.max(4, Math.round(metrics.INNER_GAP_X / 4))
      var PASSES = 12
      var moved = {}

      for (var pass = 0; pass < PASSES; pass += 1) {
        var touched = false
        for (var i = 0; i < boxes.length; i += 1) {
          for (var j = i + 1; j < boxes.length; j += 1) {
            var a = boxes[i]
            var b = boxes[j]
            var ix = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) + MARGIN
            var iy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) + MARGIN
            if (ix <= 0 || iy <= 0) continue

            // Whichever direction needs the least travel.
            var horizontal = ix < iy
            var push = horizontal ? ix : iy
            // A hand-placed box is the one that was meant to be where it is.
            var aHeld = a.manual === true || a.pinned === true
            var bHeld = b.manual === true || b.pinned === true
            var aShare = aHeld === bHeld ? .5 : (aHeld ? .25 : .75)
            var bShare = 1 - aShare

            if (horizontal) {
              var dir = (a.x + a.w / 2) <= (b.x + b.w / 2) ? -1 : 1
              a.x += dir * push * aShare
              b.x -= dir * push * bShare
            } else {
              var dirY = (a.y + a.h / 2) <= (b.y + b.h / 2) ? -1 : 1
              a.y += dirY * push * aShare
              b.y -= dirY * push * bShare
            }
            moved[a.id] = true
            moved[b.id] = true
            touched = true
          }
        }
        if (!touched) break
      }
      return Object.keys(moved).length
    }

    /**
     * A saved coordinate may not strand its box outside the drawing.
     *
     * A position the user dragged wins across refresh, expansion and reindex —
     * which is right, until the layout itself changes shape underneath it. A
     * point that made sense when layers were rows can sit two thousand pixels
     * from anything once they are columns, and the anchor is then off alone in
     * an empty quarter of the canvas with no way back except dragging it.
     *
     * The drag is kept as a direction: the box is pulled back only as far as
     * the edge of where everything else actually is.
     *
     * @param place - placed boxes, moved in place.
     * @param metrics - box metrics; only the gaps are read.
     * @returns how many boxes were pulled back.
     */
    function reclaimStrays(place, metrics, avail) {
      var boxes = place.placed
      var anchored = boxes.filter(function (p) { return p.manual !== true })
      if (anchored.length === 0 || anchored.length === boxes.length) return 0
      var GAP = metrics.BOX_GAP_X
      var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      anchored.forEach(function (p) {
        if (p.x < minX) minX = p.x
        if (p.y < minY) minY = p.y
        if (p.x + p.w > maxX) maxX = p.x + p.w
        if (p.y + p.h > maxY) maxY = p.y + p.h
      })
      // Room to actually put something somewhere. Clamping to the automatic
      // bounds plus one gap meant the drawing never grew for a drag: a node
      // pulled below everything else was pushed straight back up beside the
      // last row, so the canvas could only ever be the size the layout wanted.
      //
      // The bound that matters is the canvas, not the drawing. A pointer can
      // only drop something where it can reach, and that is the visible area;
      // a drawing 250 tall inside a 1200 canvas has to accept a drag 400 down.
      // What this exists to catch is the other case — a coordinate saved when
      // the graph was ten times this size, stranding one card in an empty
      // quarter — and that is still far outside a canvas away. canvasWidth is
      // measured from the real viewport, so nothing here is a pixel count.
      // Distance from the automatic bounds cannot tell these two apart, and
      // every version of that guess was wrong in one direction or the other: a
      // tight clamp meant the drawing never grew for a drag at all — a node
      // pulled below everything went straight back beside the last row — and a
      // loose one let a coordinate saved under a three-times-larger layout
      // strand one card in an empty quarter. The viewport is no help either;
      // the canvas scrolls, so off-screen is somewhere a pointer can reach.
      //
      // What actually separates them is company. A drag lands in the drawing
      // the user is looking at, so something is beside it. A coordinate left
      // over from a layout that no longer exists has nothing near it for
      // further than the whole drawing is wide. So that is the test, and it is
      // measured against the drawing itself rather than any pixel count.
      var span = Math.max(maxX - minX, maxY - minY, GAP)
      var pulled = 0
      boxes.forEach(function (p) {
        if (p.manual !== true) return
        var nearest = Infinity
        for (var i = 0; i < anchored.length; i += 1) {
          var q = anchored[i]
          var gapX = Math.max(0, q.x - (p.x + p.w), p.x - (q.x + q.w))
          var gapY = Math.max(0, q.y - (p.y + p.h), p.y - (q.y + q.h))
          var away = Math.max(gapX, gapY)
          if (away < nearest) nearest = away
        }
        if (nearest <= span) return
        var x = Math.min(Math.max(p.x, minX - GAP), maxX + GAP - p.w)
        var y = Math.min(Math.max(p.y, minY - GAP), maxY + GAP - p.h)
        if (x !== p.x || y !== p.y) { p.x = x; p.y = y; pulled += 1 }
      })
      return pulled
    }

    /**
     * Inside a frame, one column — around whatever the user put there.
     *
     * A drag used to decide the ORDER and nothing else: members were read top
     * to bottom as they sat and then laid out again down the frame, which
     * overwrote the coordinate the pointer had just produced. Every node in
     * every skin carries a boxKey — a file on the board, a layer in the tiers,
     * a column in the flow — so that made the whole drawing immovable: a node
     * dragged 380 across and 260 down landed back on the pixel it started on.
     *
     * A coordinate the user chose now survives. Automatic members still form
     * one column, and they step over the vertical bands a held anchor covers
     * rather than stacking underneath it. The frame keeps its grid slot and
     * its size — growing it to swallow a dragged anchor is what put frames on
     * top of each other — so an anchor dragged clear of its frame simply sits
     * outside it, held inside the drawing as a whole by reclaimStrays.
     *
     * @param place - boxes and placed anchors; anchors are moved in place.
     * @param metrics - box metrics; padding, header and inner gap are read.
     * @returns how many anchors were laid out again.
     */
    function restackBoxes(place, metrics) {
      var boxes = place.fileBoxes
      if (boxes === undefined || boxes.length === 0) return 0
      var BOX_PAD = metrics.BOX_PAD
      var BOX_HEAD = metrics.BOX_HEAD
      var INNER_GAP_Y = metrics.INNER_GAP_Y
      var members = {}
      place.placed.forEach(function (p) {
        if (p.boxKey === undefined) return
        ;(members[p.boxKey] = members[p.boxKey] || []).push(p)
      })
      var moved = 0
      boxes.forEach(function (box) {
        var mine = members[box.key]
        if (mine === undefined || mine.length === 0) return
        var left = box.x + BOX_PAD
        var inner = box.w - BOX_PAD * 2
        var free = []
        mine.forEach(function (p) {
          if (p.manual !== true && p.pinned !== true) free.push(p)
        })
        free.sort(function (l, r) { return l.y - r.y || l.x - r.x })
        // Every held anchor over this column is in the way of it, not only the
        // ones that belong to this frame: a card dragged across from the next
        // file is sitting in this column whatever its boxKey says. One dragged
        // off to the side blocks nothing.
        var bands = place.placed
          .filter(function (p) { return p.manual === true || p.pinned === true })
          .filter(function (p) { return p.x < left + inner && p.x + p.w > left })
          .map(function (p) { return [p.y, p.y + p.h] })
          .sort(function (a, b) { return a[0] - b[0] })
        var y = box.y + BOX_HEAD + BOX_PAD
        free.forEach(function (p) {
          // Bands are sorted, so walking them once is enough: clearing one can
          // only push this row into a later band, never an earlier one.
          for (var i = 0; i < bands.length; i += 1) {
            if (y < bands[i][1] && y + p.h > bands[i][0]) y = bands[i][1] + INNER_GAP_Y
          }
          if (p.x !== left || p.y !== y || p.w !== inner) moved += 1
          p.x = left
          p.y = y
          p.w = inner
          y += p.h + INNER_GAP_Y
        })
      })
      return moved
    }

    module.exports = { fitExtent, shiftPlacement, shiftDrawing, separateOverlaps, reclaimStrays, restackBoxes }
    return module.exports
  },
})
