# SubD recipes: counts, reductions, circles, loops

Read this when a ring or row changes its count, a circle sits in a plate, a support loop goes in, or a SubD surface kinks.

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
- **Not on a concave rim.** T2 has no edge going out, so the arc rule in section 5 rules it out on the first ring round a hole in a plate. It hasn't been tested on a plate at all.
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

- **Order of fixes:** scale the rings, then a taller row, then fit if there is a target.

## 3. Spacing and shear on a curve

- **Normal error is about the difference in edge length / (3 x radius), in radians.** Neighbours differ by less than radius / 20 for under 1 degree. It only counts in the direction the surface bends. It runs 3 to 13 % low on big differences. `validate_mesh.py` warns above 5 degrees as `uneven_on_curves`.
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

## 5. Circles in a plate

- **Arc rule.** On the plate side a rim is concave, so every arc vertex needs an edge or its quad folds (202 degrees). On a floor it is convex, so every other vertex is enough.
- **8 segments in a 2 x 2 grid:** a diagonal from the rim to each grid corner. **16:** a six-face 4 to 2 per quarter, because the arc rule needs an edge at every arc vertex.
- **A round hole in a square box, 16 segments, no reduction.** Put 16 points on a square inset from the outline, at the same angles as the rim vertices, so its corners land on the 45 degree ones. Run rows straight from the rim to that square. Between the square and the outline run one band of quads, with one quad at each corner. Each box corner is then a 3-pole with three quads, and each inset corner a 5-pole. Two independent builds came to this same 224-quad cage: hole spread 0.006 %, flat dip under 0.001 on a 2 x 2 x 0.2 plate.
- **N-gons on a flat face** are allowed under SubD, on two conditions. `validate_mesh.py` fails one that breaks either.
  - **Every face touching it lies in its plane,** so it needs a support row all round. A 16-gon cap on a cylinder with a row dips 0.0001 and reads 0.13 degrees; with none it dips 0.052 and reads 11.19. On a plate with no rows the rim reads 12 to 20 % spread near its edge, against 0.80 % with them.
  - **Its centre must see every edge.** SubD puts a vertex at the average of the corners, so a half ring wrapped round a hole has that vertex inside the hole and folds across the opening, leaving about 0.44 of surface across an opening of 0.64, on each side. Cut it into quarter rings or smaller: four 8-gons and eight 5-gons had no fold.
  - Four 8-gons with rows use 160 faces against 224 for the all-quad cage, with the same hole spread (0.006 %), softening (0.01) and near-rim spread (0.80 %). The flat reads a little worse beside the rows: 2.39 degrees against 1.69, dip 0.0017 against 0.0008.
- **Caps.** 8: one centre vertex with four edges. 16: a 4 x 4 grid with its corners on the 45 degree rim vertices. Respace a flat cap grid after a support row goes in (23 degree corners became 35.9).
- **Two circles close together:** a new centre vertex between them with a cross of edges. Four 6-poles on the flat plate were fine. Two parallel diagonals were worse on the centre hole and can't be mirrored.
- **Border corners.** A diagonal into a border corner gives it three edges, so it pulls in by L x 1.41 / 6 under SubD. Fix: three quads round one new vertex, which leaves a 3-pole on the plate. If the diagonal stops past the line between the two side vertices, that folds; use vertex crease 1.0.
- **Next edge out.** An unsupported rim rounds with the length of the next edge, not its valence: 21 % spread on a rim of valence 4. Support loops take every rim to the limit of its own curve: 0.12 % at 8 segments, 0.01 % at 16.

## 6. Support loops

- **Insert with Bevel: 2 segments, profile 1.0, Loop Slide off.** It keeps the surface and the rim. With Loop Slide on, the row slides sideways on oblique edges: edges of 0.0026 and 16 concave faces, against 0.0311 and none with it off.
- **A corner held at width w loses w / 6 each way, on any scale.** So set the width to six times the cut you want. Measured with equal loops on both sides.
- **Width only sets softness.** Having the loops at all sets roundness, and neither brings back the radius (section 4).
- **Limit.** Keep the width under the next edge and about 0.4 R on a rounded corner. That's one shape: 0.42 R is clean, 0.52 R starts to go wrong, 0.83 R folds.
- **Topology first, loops last.** A live Bevel modifier keeps the cage simple and the width adjustable. In a tight spot leave that edge out of the modifier, or let the loops overlap and Merge by Distance (Frank Polygon, not measured here).
- A support loop beside a reduction: see the table in section 2.
- Not tested: unequal widths.

## 7. Native tools

LoopTools isn't part of Blender 5.2, and the pipeline doesn't call add-ons (`docs/pipeline/addon-requests.md`). These ran headless on 5.2.3.

| Job | Call | Watch for |
| --- | --- | --- |
| Even a ring | `bmesh.ops.space_edge_loops_evenly(bm, geom=edges, interpolation="LINEAR", factor=1.0)`, or `mesh.space_edge_loops_evenly` | It keeps to the old polygon, so the radius drops a little. Round it afterwards |
| Round a ring | `bmesh.ops.circularize(bm, geom=verts + edges, factor=1.0, flatten=1.0)`, or `mesh.circularize` | A wire ring with no faces is left unchanged, with no error. It fits its own radius, so scale to the size you need and check the result |
| Select a whole loop | `mesh.select_edge_loop_multi()`, in Edit Mode with one edge selected | It stops at any pole. `mesh.loop_multi_select` doesn't exist in 5.2 |
| Relax | `mesh.vertices_smooth_laplacian`, `bmesh.ops.smooth_laplacian_vert` | There is no Relax operator |
| Bevel by script | `bmesh.ops.bevel(bm, geom=edges, offset=w, segments=2, profile=1.0, affect="EDGES", clamp_overlap=False, loop_slide=False)` | The bmesh default is `affect="VERTICES"`. The modifier defaults to Loop Slide and Clamp Overlap on; the operator has Loop Slide on and Clamp off. Set every option |
