# SubD recipes: counts, reductions, circles, loops

Read this when a ring or row changes its count, a circle sits in a plate, a support loop goes in, a round runs out, a branch or a Boolean meets a curved wall, a SubD surface kinks or folds, or you plan a whole plate, dome, dish, seam or set of ribs.

The numbers were measured on Blender 5.2 on test plates and tubes, against an exact surface. None has been judged on a real asset under real light, so use the degrees to compare options, not as limits. The web evidence is in `docs/pipeline/hard-surface-workflows.md`.

## 1. Check the count first

| Rule | What it means |
| --- | --- |
| A mesh of only quads has an even border | An odd border can't be all quads. Add or remove one border vertex |
| Odd-sided faces and border edges are both odd or both even | Tris and pentagons go away in pairs, unless the border changes |
| A closed ring that cuts the mesh in two has an even border on each side | A tube's ring can't change between odd and even: 16 to 14 works, 16 to 15 can't |
| A grid cap needs an even ring | Choose even counts unless the tube stays open |
| Inner vertices add up (4 - edges), border vertices (3 - edges), and the total is 4 x (vertices - edges + faces) | Poles can move or pair up, never disappear. A tube totals 0: 3-poles and 5-poles balance, and a 6-pole counts as two 5-poles |

`validate_mesh.py` reports an odd border as `odd_border_islands`.

## 2. Reductions

T is the dense row and B the coarse row. M and S are new vertices in the row between.

- **Three-quad 4 to 2** (T0 to T4, B0 B1 B2, no new vertex). Faces: B0 B1 T1 T0, B1 T3 T2 T1, B1 B2 T4 T3. T2 is a 3-pole on the dense ring and B1 a 5-pole on the coarse ring. No 6-poles, even side by side.
- **Six-face 4 to 2** (T0 to T4, B0 B1 B2, new M0 S M1). Faces: T0 T1 M0 B0, T1 T2 S M0, T2 T3 M1 S, T3 T4 B2 M1, B0 M0 S B1, B1 S M1 B2. 3-poles at M0 and M1. 5-poles at B0 and B2, which become 6-poles where these cells sit side by side.
- **2 to 1** (T0 T1 T2, B0 B1). Add M, and S on the column from T2 to B1. Faces: T0 T1 M B0, T1 T2 S M, M S B1 B0. One 3-pole (M), one 5-pole (B0). The edge from M to S carries on along the row and must end at a mirrored 2 to 1, so one alone can't close a ring. Two touching make the six-face cell.
- **3 to 1** (T0 to T3, B0 B1). Add M0, M1. Faces: T0 T1 M0 B0, T1 T2 M1 M0, T2 T3 B1 M1, M0 M1 B1 B0. Two 3-poles, two 5-poles.

| Need | Use | Why |
| --- | --- | --- |
| Halve a ring on a smooth surface | A three-quad cell in every unit, all in one row | Half the raw error of the six-face cell, 2 to 5 times less with the rings scaled |
| Halve a ring with a hard edge or a whole loop needed on the dense ring | First move the three-quad row two rows away from that ring. With no room, a six-face cell in every unit | Its dense ring stays one whole loop (limits, below) |
| Small local change, room for an extra row | A mirrored pair of 2 to 1s set apart, best when opposite each other | 16 to 14: 4.32 degrees, 1.24 % spread |
| Small local change, no room | Either 4 to 2 | Six-face 4.53, 2.18 %. Three-quad 4.75, 1.98 %. After fit, 1.96 and 2.43 |
| Last choice | 3 to 1, the worst on every surface tested | 5.81, 2.78 % |

The extra row of a pair stops at its poles, so a support loop can't run along it.

Three-quad against six-face on 16 to 8 tubes with every ring even. Normal error in degrees: raw, rings scaled, fit.

| Row height, coarse edge 2 | Three-quad, 156 faces | Six-face, 168 faces |
| --- | --- | --- |
| Row 0.5, coarse row 1 | 13.69, 2.80, not run | 26.06, 13.47, not run |
| Row 1, coarse row 1 | 8.44, 1.66, 1.79 | 15.76, 8.78, 6.88 |
| Row 2, coarse row 2 | 4.52, 1.30, 1.42 | 8.16, 4.94, 4.11 |
| Row 6, coarse row 2 | 1.94, 1.25, 1.27 | 3.93, 2.96, 2.85 |

The same holds at other counts. 32 to 16 at row 1 reads 2.23, 0.49, 0.56 against 4.22, 2.33, 1.88. 24 to 12 at row 3.4 reads 1.48, 0.67, 0.72 against 2.97, 1.99, 1.82. A whole run 32 to 16 to 8 reads 4.52, 1.30, 1.42 at 308 faces against 8.16, 4.94, 4.10 at 344.

Other surfaces, on a patch four cells wide with the row as tall as the coarse edge, radius 8, raw, three-quad then six-face: flat 0.00 and 0.00 (both exactly flat), saddle 0.80 and 1.94, bend along the row 1.50 and 2.71, sphere 4.35 and 4.16, bend across the row 2.97 and 2.44. It wins where the surface bends along the rings and loses slightly where it bends across them. No flipped faces on any.

Limits of the three-quad cell:

- **Edge loop selection stops at T2.** `select_edge_loop_multi` picks 4 of 16 edges on its dense ring, against all 16 on a six-face dense ring. Both stop at the coarse ring's poles.
- **Not on a concave rim.** T2 has no edge going out, so the arc rule in section 5 rules it out on the first ring round a hole in a plate. It hasn't been tested on a plate at all. Set back one ring from a joint on a curved wall it worked (section 8).
- **Support loops near it.** Normal error round the ring and spread at that ring, 16 to 8, row 2, Bevel width 0.2. Every Bevel gave only quads. Keep a loop two rows clear on the dense side.

  | Loop on | Three-quad | Six-face |
  | --- | --- | --- |
  | The dense ring | 4.89, 3.10 % | 0.89, 0.63 % |
  | One row clear, dense side | 0.36, 0.20 % | 0.03, 0.01 % |
  | Two rows clear, dense side | 0.03, 0.01 % | 0.03, 0.01 % |
  | The coarse ring | 1.10, 0.74 % | 2.40, 1.83 % |
  | One row clear, coarse side | 0.30, 0.14 % | 0.42, 0.20 % |

### Rules for any reduction

- **Even both rings straight after it, within one or two rows.** Leaving the wide edge is the worst thing measured: 31.94 degrees and 16 % spread, against 5.81 and 2.78 % on the same mesh with both rings even. A slow blend along the rows doesn't help, because each ring just carries the unevenness. Round the ring is different: stepping a change over three columns is three times better.
- **Scale each ring by its factor** (section 4). That's the biggest single gain on a halving.
- **Give it height.** Make the reduction row and the one row on its coarse side at least as tall as the coarse edge, taller on low counts. The other rows are free.
- **Don't stage a halving.** The three-quad cell has no 6-poles to lose. With the six-face cell, one row beat two stages in the same height, raw (3.93 against 7.26) and scaled (2.96 against 4.69), and they tied after fit (2.85 against 2.71).
- **One clear row between two reductions.** More adds nothing, and the poles don't need to line up. Measured on the six-face cell.
- **Two clear rows from any curve.** Count from the reduction's whole row to the tangent line. One fillet shape, radius 4, coarse edge 1, six-face cell:

  | Clear rows | Added normal error |
  | --- | --- |
  | 2 or more | 0.00 |
  | 1 | 0.06 to 0.08 |
  | 0, touching | 1.24 to 1.91 |
  | Inside the fillet | 4.11 to 5.69 |

  This is a cell beside a fillet. A three-quad cell that changes the count along a round and is fitted to it added nothing (section 6).

- **Order of fixes:** scale the rings, then a taller row, then fit if there is a target.

## 3. Spacing and shear on a curve

- **Normal error is about the difference in edge length / (3 x radius), in radians.** Neighbours differ by less than radius / 20 for under 1 degree. It only counts in the direction the surface bends. It runs 3 to 13 % low on big differences. `validate_mesh.py` warns above 5 degrees as `uneven_on_curves`. Beside a hard edge uneven edges are the point, so it counts those apart as `support_row_verts`: a narrow edge under a quarter of the wide one, a turn of 60 degrees or more at the vertex or within three vertices on the narrow side, or a border there. All 454 flags on the ring faults of tests 04 and 05 stay, all 15 on tests 07 and 08 clear, and one whole part fell from 1,351 to 418. Read what's left as a place to check in `--modes reflect`, not a fault: of the four worst spots on that part, two kink in the stripes and two don't. A tight row on a smooth curve counts as a support row, so check those in the wire.
- **Don't choose between pole types; fix spacing and shear first.** A lone pole adds under 1 degree. Sheared cells cost more: 60/120 degree cells read 2.07 at radius 4, 72/108 read 1.40.
- **Pure quads wobble too.** A dense strip with no pole reads the same as a 3 to 1.

## 4. Size and fit

A ring of radius r ends at r x (4 + 2 cos(360 / n)) / 6, whatever the loops or their width.

| Segments | 4 | 6 | 8 | 10 | 12 | 14 | 16 | 24 | 32 | 64 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Factor | .6667 | .8333 | .9024 | .9363 | .9553 | .9670 | .9746 | .9886 | .9936 | .9984 |

- **To hold a size, scale the ring by 1 / factor.** On a 16 to 8 three-quad cell that cuts the error 1.5 to 5 times and leaves a ridge of 0.5 % of the radius. On a six-face cell it about halves the error and leaves 3.5 %.
- **Fit** moves each cage vertex along the normal by the gap between its SubD position and a target surface, about 12 times. It cut normal error by 2 to 4 times and ripple by about 4 times, moving the cage 3 to 11 % of an edge. It needs a target; a dense copy is untested. On a three-quad halving it doesn't beat scaled rings on normal error (1.79 against 1.66 at row 1), but it brings the ridge from 0.5 % towards 0. A run with an exact fit read 0.73 degrees on 24 to 12.
- Fit alone is the default, because it leaves the rows where they are. On a closed ring, even the rings and then fit. Relax first only on a 3 to 1 where fit leaves too much: it bends the rows, and the stripes wave.
- **One solve instead of passes, on an exact height field.** SubD is linear in the cage, so one least-squares solve in z over the subdivided surface replaces the passes and leaves xy where it is. Two agents reached this separately: a grid went from 2237 faces to 509 at the same tolerance, and a rim fit from 2.57 to 0.71 degrees on the same points. The price: a solved cage sits off the surface, up to 1.43 mm on one part, so it can't be edited by hand and a form change means solving again. It needs an exact target, which a part from an image doesn't have.
- **A held edge's line moves with its neighbour during a fit.** One agent: held still, it read 0.0797 mm; moved on every pass, 0.0405.

## 5. Circles in a plate

- **Arc rule.** On the plate side a rim is concave, so every arc vertex needs an edge or its quad folds (202 degrees). On a floor it is convex, so every other vertex is enough.
- **8 segments in a 2 x 2 grid:** a diagonal from the rim to each grid corner. **16:** a six-face 4 to 2 per quarter, because the arc rule needs an edge at every arc vertex.
- **A round hole in a square box, 16 segments, no reduction.** Put 16 points on a square inset from the outline, at the same angles as the rim vertices, so its corners land on the 45 degree ones. Run rows straight from the rim to that square. Between the square and the outline run one band of quads, with one quad at each corner. Each box corner is then a 3-pole with three quads, and each inset corner a 5-pole. Two independent builds came to this same 224-quad cage: hole spread 0.006 %, flat dip under 0.001 on a 2 x 2 x 0.2 plate.
- **N-gons on a flat face** are allowed under SubD, on two conditions. `validate_mesh.py` fails one that breaks either.
  - **Every face touching it lies in its plane,** so it needs a support row all round. A 16-gon cap on a cylinder with a row dips 0.0001 and reads 0.13 degrees; with none it dips 0.052 and reads 11.19. On a plate with no rows the rim reads 12 to 20 % spread near its edge, against 0.80 % with them.
  - **Its centre must see every edge.** SubD puts a vertex at the average of the corners, so a half ring wrapped round a hole has that vertex inside the hole and folds across the opening, leaving about 0.44 of surface across an opening of 0.64, on each side. Cut it into quarter rings or smaller: four 8-gons and eight 5-gons had no fold.
  - Four 8-gons with rows use 160 faces against 224 for the all-quad cage, with the same hole spread (0.006 %), softening (0.01) and near-rim spread (0.80 %). The flat reads a little worse beside the rows: 2.39 degrees against 1.69, dip 0.0017 against 0.0008.
  - **Passing both doesn't make it safe.** A flat 8-gon 5.8 x 43 mm closing the gap between two ribs passes both and folds, 168 edges at level 2; three quads in that gap read 0. 111 isolated n-gons of the same proportions never fold, so its surroundings cause it, not its size, and no size rule catches it. Read the fold count (section 9).
- **Caps.** 8: one centre vertex with four edges. 16: a 4 x 4 grid with its corners on the 45 degree rim vertices, on a flat or circular cap; on a dome over a non-circular seam it read 2.08 degrees against 0.79 for a pole (section 10). Respace a flat cap grid after a support row goes in (23 degree corners became 35.9).
- **Two circles close together:** a new centre vertex between them with a cross of edges. Four 6-poles on the flat plate were fine. Two parallel diagonals were worse on the centre hole and can't be mirrored.
- **Border corners.** A diagonal into a border corner gives it three edges, so it pulls in by L x 1.41 / 6 under SubD. Fix: three quads round one new vertex, which leaves a 3-pole on the plate. If the diagonal stops past the line between the two side vertices, that folds; use vertex crease 1.0.
- **Plan corners of a box.** Long outline edges round a corner in plan, however well the top edge is held. Give every vertical corner a guard vertex each side, with one quad at the corner. Two agents found this separately: 12.7 mm and 84 degrees off, 2.86 mm and 79.8 degrees off, the second with a p95 of 0.06 degrees (section 9).
- **Next edge out.** An unsupported rim rounds with the length of the next edge, not its valence: 21 % spread on a rim of valence 4. Support loops take every rim to the limit of its own curve: 0.12 % at 8 segments, 0.01 % at 16.

## 6. Support loops

- **Insert with Bevel: 2 segments, profile 1.0, Loop Slide off.** It keeps the surface and the rim. With Loop Slide on, the row slides sideways on oblique edges: edges of 0.0026 and 16 concave faces, against 0.0311 and none with it off.
- **A corner held at width w loses w / 6 along each face, on any scale.** At a right angle that is a straight gap of w x 1.41 / 6 from the sharp edge. So set the width to six times the cut you want, and say which number a spec means: width 0.12 cuts 0.02 along each face and leaves a gap of 0.028. Measured with equal loops on both sides.
- **Where three loops meet at a box corner,** it pulls in w / 4 along each axis: 0.045 at width 0.18, 0.015 at 0.06.
- **The face goes flat past the loop,** at (5w + L) / 6 from the edge, where L is the next edge in. On a 2 x 2 x 2 box at width 0.18 that is 0.4233: it dips 0.0018 at 0.2 from the edge, 0.0001 at 0.3 and nothing at 0.4. To end the soft band sooner, add a row to shorten L.
- **Width only sets softness.** Having the loops at all sets roundness, and neither brings back the radius (section 4).
- **Limit.** Keep the width under the next edge and about 0.4 R on a rounded corner. That's one shape: 0.42 R is clean, 0.52 R starts to go wrong, 0.83 R folds.
- **Topology first, loops last.** A live Bevel modifier keeps the cage simple and the width adjustable. In a tight spot leave that edge out of the modifier, or set w to half the width. Letting the loops overlap and then Merge by Distance gains nothing: on a rib 1 mm wide it loses 0.083 to 0.089 mm at the top centre against 0.083 for half the width, and it only comes clean when the merge is wider than the crossing and under w. Otherwise one flipped face stays.
- **Merge distance goes under the shortest edge.** Below it a merge touches nothing: 0.9 w was clean at seven widths from 2 to 0.02 mm. At w it starts to take the rows, and at 1.5 w a 54-face box falls to 13 to 17 faces with non-manifold edges. A 2-segment Bevel's shortest edge is w, but on a small ring it's the ring edge, about 2 pi r / n: radius 1 mm at 64 segments loses 209 of 384 vertices at the default 0.1 mm, while radius 2 mm or more up to 64 segments loses none. `validate_mesh.py --merge-dist` has the same limit, so lower it on a part with edges at or under 0.1 mm, or it reports real rows as duplicates. Not tested: a merge on curved or sheared ribs, or a live Bevel's own merge.
- A support loop beside a reduction: see the table in section 2.
- Not tested: unequal widths.

### Round edges

One agent, one 4 x 2 x 1 box each, not judged on a real asset.

- **A 2-segment round needs a support row on each flat.** With rows, radius 0.2 stays within 0.85 % of the true round. The agent read 3.5 % without them; I didn't check that. Even so, a 2-segment section reads 3 to 4 degrees of normal error.
- **A count change along a round:** a three-quad 4 to 2 across the round, here over 0.6 of its length, with its rings fitted to the circle. 2 segments to 4 at radius 0.2 kept the section at 0.0581 to 0.0586 against 0.0586, and read 3.1 degrees at the cell against 3.88 and 2.64 away from it.
- **A round running out to sharp:** keep one ring count along the whole edge, so there is no reduction: 2 segments across the round and a support row on each flat, with the three corner points sliding between the round and the loops. Rings at even pitch, 0.25 here, with the widths set ahead so the run-out comes out smooth after SubD. Radius 0.15 to softening 0.01 over a length of 1 read 0.0439 (the target), 0.0269 halfway and 0.0101 (target 0.0100), steady in between, with both flats at 0.07 degrees or less.

## 7. Native tools

LoopTools isn't part of Blender 5.2, and the pipeline doesn't call add-ons (`docs/pipeline/addon-requests.md`). These ran headless on 5.2.3.

| Job | Call | Watch for |
| --- | --- | --- |
| Even a ring | `bmesh.ops.space_edge_loops_evenly(bm, geom=edges, interpolation="LINEAR", factor=1.0)`, or `mesh.space_edge_loops_evenly` | It keeps to the old polygon, so the radius drops a little. Round it afterwards |
| Round a ring | `bmesh.ops.circularize(bm, geom=verts + edges, factor=1.0, flatten=1.0)`, or `mesh.circularize` | A wire ring with no faces is left unchanged, with no error. It fits its own radius, so scale to the size you need and check the result |
| Select a whole loop | `mesh.select_edge_loop_multi()`, in Edit Mode with one edge selected | It stops at any pole. `mesh.loop_multi_select` doesn't exist in 5.2 |
| Relax | `mesh.vertices_smooth_laplacian`, `bmesh.ops.smooth_laplacian_vert` | There is no Relax operator |
| Bevel by script | `bmesh.ops.bevel(bm, geom=edges, offset=w, segments=2, profile=1.0, affect="EDGES", clamp_overlap=False, loop_slide=False)` | The bmesh default is `affect="VERTICES"`. The modifier defaults to Loop Slide and Clamp Overlap on; the operator has Loop Slide on and Clamp off. Set every option |

## 8. Openings in a curved wall

Each recipe below is one agent on one shape, so take it as a working start and measure yours.

### A small branch into a large wall

Open pipe radius 3 and 32 segments, branch radius 1 and 8 segments, sharp joint with a width of 0.12.

- **Drop the wall's count over the joint.** 32 round at the ends, three-quad 4 to 2 cells over a row 1.2 tall, 16 round in the middle.
- **Set the branch in a 4 x 4 block of wall cells.** A 2 x 2 block with an 8 ring read 1.16 % and 4.5 degrees by the agent's reading.
- **Grow the ring away from the joint:** joint, a support ring each side, one more ring, then four three-quad cells going 8 to 16 with their poles on the block's diagonals.
- **Fit along the normal.** The target at the joint is the corner pulled in w / 6 along each face. The agent reported exact fit as unstable here; I didn't reproduce that. It also scaled the hole rings sideways by 1.108 and 1.06, by trial.
- **Result:** 340 quads, 16 3-poles, 20 5-poles. Main within 0.24 %, branch 0.12 %. Normal 1.31 degrees by the joint, 0.56 away from it, 0.26 on the branch. Joint gap 0.023 to 0.028.
- **Not checked:** Frank Polygon's rule of matching wall segments to the opening out to 45 degrees. This branch spans about 20 degrees either side, so it doesn't test that.

### Booleans under SubD

- **On a flat plate an Exact Boolean leaves n-gons that fold.** A 16-segment cylinder through a 2 x 2 x 0.2 plate left two half-ring 12-gons on the top face, with their centres over the hole. Don't keep them (section 5): cut them into quarter rings and add rows, or rebuild.
- **On a curved wall, replace the patch round the cut.** What the solver leaves is badly placed for SubD, so delete it inside a patch and build new quads, keeping the patch's outline. For a pocket of radius 0.8 in a wall of radius 3 and 32 segments, the patch was 4 x 4 cells with 16 outline vertices.
- **Inside the patch, from the rim out:** a rim ring, an outer support ring, then a band to the outline. Going in: a support ring under the rim, the pocket wall, a support ring above the floor, then a support row and a flat 16-gon on the floor.
- **Hold the size and fit.** Scale the 16 rings by 1 / .9746 and the whole wall by 1 / .9936. Then fit the outer support ring, about 10 passes, by the average radius error of the wall round it. Leave pocket wall points out of that sample, because they aren't on the wall. That mistake cost one attempt.
- **Result:** 336 quads, the floor 16-gon and two end caps, all 242 far wall vertices kept. Wall within 0.20 %, normal 1.47 degrees, or 0.97 well away from the pocket. Pocket 0.7995 to 0.8003. Floor within 0.0009.
- **Width 0.10 gave a floor edge gap of 0.023 but a rim gap of 0.015.** I didn't trace why. The fit moves the outer ring, which is the likely cause, so measure the rim after fit.
- **Not tested:** a true repair that keeps the solver's rim, a prepared base with matched segments, and subdividing and shrinkwrapping onto an uncut copy.

## 9. Folds, and reading the numbers

- **A fold can pass every other check.** Four files with up to 528 folded edges at level 4 passed `validate_mesh.py` and every p95. A fold in a flat face reads 0 mm off the target, and it didn't show in a reflection close-up. Only the wire shows it, as a dense strip. `topology.folded_edges` now counts edges of the level 2 surface that turn back past 100 degrees and names the places. All four flagged, and 30 clean models read 0.
- **It can flag real form.** A slab about 10 % thick or less with no support rows flags, because its rim really is that sharp at level 2. One whole part reads 38 that haven't been sorted. So it's a warning: look at each place in the wire.
- **Reductions on a flat can fold,** so "flat 0.00" in section 2 says nothing about folds. A three-quad 8 to 4 and a 3 to 1 both folded on a flat plate, up to 0.69 mm2 per patch. The same 8 to 4 didn't fold on a round dish, and did on an oval with a 0.3 mm row beside it. Read the fold count after any reduction.
- **Read max beside p95.** p95 read 0.06 degrees over a 79.8 degree corner, and clean over points at 180 degrees. A pass on p95 alone says nothing about a local fault.
- **1 degree at p95 isn't a clean-reflection target.** A flat at 0.40 degrees shows faint waves out to about 10 mm past a dish's rim; one at 0.06 is clean. Whether that matters depends on the material, so judge it in `--modes reflect`.

## 10. Whole shapes

From measured tests with one exact target per shape, aim 0.05 to 0.1 mm and 1 degree at p95, one agent per shape, re-measured at level 4. Most counts below rest on a solve (section 4), so use them to rank layouts, not as budgets. A cage you place by hand needs more.

### A plate with a T-junction

Three arms, crowned top of about 337 mm radius, nearly flat.

- **Count rim vertices first.** Five rows per rim vertex (top support, three wall rows, bottom support) are 73 to 80 % of the faces, and the lattice inside only 7 to 13 %. Study the rim before any cage: a straight wall depends only on the rim polygon.
- **Let few lattice lines reach the rim.** One grid, 379 faces. A core of three quads round a 3-pole at the T, so the arms stop there, 366. That core with fans to each fillet and a sparser lattice, 326, with a worst point of 3.05 degrees at the junction.
- **Guards on an inner fillet.** A guard vertex just past each tangent, linked to the existing lattice line, took five even arc points from 1.53 to 0.71 degrees.
- **Don't read this as licence on a tight curve.** Poles on the fillet cost nothing here and the arc rule's fold didn't show, but this top is nearly flat, so keep two clear rows and the arc rule.
- **Long rim spans sag along the top edge.** The agent read softening up to 0.81 mm where 0.33 was asked. No check sampled it, and fitting the rim's height is untested.

### A dome on a non-circular seam

- **Rings to a pole.** A superellipse seam at 12 segments, rings at 0.8, 0.5 and 0.2 of the seam, closing on one centre vertex: 147 faces. 24 segments on a 6 x 6 grid cap: 213. 16 to 8 with a reduction and a 2 x 2 cap, which is the same mesh as a pole: 169. Reductions didn't pay at these counts. 8 segments, 125 faces, missed by 0.02 degrees.
- **Seam spacing.** Space seam vertices by the root of curvature, with vertices on the axes and diagonals. By the agent's look, reflection stripes stay calmer than on a grid cap, where they kink towards its corners.

### A soft dish in a plate

- **A placed grid pays for shrink everywhere.** Its error is cell squared / 6 x the Laplacian: 0.0477 mm by that sum at a 3.09 mm cell and 30 per metre, 0.0473 measured. That cell then covers the whole plate.
- **Rings let rows bunch where the form turns.** Placed on the surface with no solve, 32 columns and 14 rings pass at 705 faces, against 2237 for the grid. 16 columns read 0.135 mm, and 8 columns 1.16 mm, so keep 8, 16, 32 for a placed cage.
- **With an exact target and a solve,** 8 columns and 5 rings pass at 117 faces. Ring spacing at the rim counted more than column count, and too wide a cap sets the centre's error: a 22 mm cap read 0.1145 mm against 0.0268 at 16 mm.
- **Keep the flat regular for about 10 mm past the rim** if it will reflect. Cutting the perimeter to 95 faces passes, but brings waves there, a two-fold swirl in the wire and two 6-poles, so take the 117.

### A stepped seam across a dish

Two parts with a 0.5 mm gap, the seam running along lattice lines. One shape, and only one of four layouts passes, at 418 faces against 117 with no seam.

- **Leave the next rows alone.** At the same 412 faces, stepping them read 1.34 degrees far from the seam and leaving them 0.72, because stepping pulls a round ring off its circle.
- **Run one local row beside the support row,** following the seam and the step, ended on the flat by a mirrored 2 to 1 pair. Keep (5w + L) / 6 inside the seam's band (section 6): with w 1.2 mm, L 2.8 mm passed and 3.5 mm didn't.
- **A vertex on the step's mirror line and even columns** gave the biggest gain, from 0.0700 mm and 1.86 degrees beside the seam to 0.0513 and 1.01.
- **Flat n-gons on straight walls** passed, with wall rows only at corners, about 16 % fewer faces by sum. The passing layout has 14.
- **Reflex corners:** a support vertex each side with an inward edge. A corner quad there makes an arrowhead.

### Ribs on a block

Five ribs, flat and curved tops.

- **One mesh when the foot must soften, separate parts when a hard crease is right.** Separate parts are cheapest, 14 % under the best one-mesh on flat and 17 % on curved, and they have a hard crease at the foot that nothing here scored. That's a look decision, not a cost one.
- **Close a gap between ribs with three quads,** not one long n-gon (section 5).
- **All quads against n-gons is 10 faces,** 386 against 376, once the folds are gone. Choose by what's easiest to edit.
- **On a flat, layout hardly changes the shape.** A full grid spends 594 faces to improve a number that already passed at 324. On a curve the grid is most accurate and isn't needed: 349 faces pass with 43 % fewer than 616, with the least margin at 0.87 degrees.
