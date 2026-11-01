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

- **2 to 1** (T0 T1 T2, B0 B1). Add M, and S on the column from T2 to B1. Faces: T0 T1 M B0, T1 T2 S M, M S B1 B0. One 3-pole (M), one 5-pole (B0). The edge from M to S carries on along the row and must end at a mirrored 2 to 1, so one alone can't close a ring.
- **4 to 2** is that pair touching (T0 to T4, B0 B1 B2, new M0 S M1). Faces: T0 T1 M0 B0, T1 T2 S M0, T2 T3 M1 S, T3 T4 B2 M1, B0 M0 S B1, B1 S M1 B2. 3-poles at M0 and M1. 5-poles at B0 and B2, which become 6-poles where 4 to 2s sit side by side.
- **3 to 1** (T0 to T3, B0 B1). Add M0, M1. Faces: T0 T1 M0 B0, T1 T2 M1 M0, T2 T3 B1 M1, M0 M1 B1 B0. Two 3-poles, two 5-poles.

| Need | Use | 16 to 14, both rings even: normal error, roundness spread |
| --- | --- | --- |
| Small change, room for an extra row | A mirrored pair of 2 to 1s set apart, best when opposite each other | 4.32 degrees, 1.24 % |
| Small change, no room | 4 to 2 | 4.53, 2.18 % |
| Last choice | 3 to 1, the worst on every surface tested | 5.81, 2.78 % |
| Halve a ring | A 4 to 2 in every unit, all in one row | See height, below |

The extra row of a pair stops at its poles, so a support loop can't run along it.

### Rules for any reduction

- **Even both rings straight after it, within one or two rows.** Leaving the wide edge is the worst thing measured: 31.94 degrees and 16 % spread, against 5.81 and 2.78 % on the same mesh with both rings even. A slow blend along the rows doesn't help, because each ring just carries the unevenness. Round the ring is different: stepping a change over three columns is three times better.
- **Give it height.** Make the reduction row and the one row on its coarse side at least as tall as the coarse edge, taller on low counts. The other rows are free.

  | 16 to 8, same 168 faces, coarse edge 2 | Raw | Rings scaled | Fit |
  | --- | --- | --- | --- |
  | Reduction row 0.5, coarse row 1 | 26.06 | 13.47 | not run |
  | Row 1, coarse row 1 | 15.76 | 8.78 | 6.88 |
  | Row 2, coarse row 2 | 8.16 | 4.94 | 4.11 |
  | Row 6, coarse row 2 | 3.93 | 2.96 | 2.85 |

  For a halving all round the ring, tilt = atan(1.5 x step / height), with step = radius x (dense factor - coarse factor). The 1.5 was fitted from these same readings, and it fails on a single local reduction (1.67 predicted, 4.20 measured). Height for 5 degrees, in coarse edges: 1.6 on an 8 ring, 0.8 on a 16 ring (both measured); 2.6 on a 4 ring, 0.4 on a 32 ring (predicted). The 5 is a reference line, not a limit.
- **Don't stage a halving by default.** In the same height, one row beats two stages raw (3.93 against 7.26) and scaled (2.96 against 4.69), and they tie after fit (2.85 against 2.71). Stage it only to lose the 6-poles (24 more faces on 16 to 8) or when the row can't grow and you can fit (4.51 against 6.88). Four stages add nothing over two.
- **6-poles.** Practitioners and Pixar's modelling notes advise against high valence, and use a 5-pole to turn three loops into five. Here 6-poles read no worse on a tube, but none was tested with a support loop beside it. If review objects, two stages remove them.
- **One clear row between two reductions.** More adds nothing, and the poles don't need to line up.
- **Two clear rows from any curve.** Count from the reduction's whole row to the tangent line. One fillet shape, radius 4, coarse edge 1:

  | Clear rows | Added normal error |
  | --- | --- |
  | 2 or more | 0.00 |
  | 1 | 0.06 to 0.08 |
  | 0, touching | 1.24 to 1.91 |
  | Inside the fillet | 4.11 to 5.69 |

- **Order of fixes:** a taller row costs nothing, so first that. Then scale the rings. Then fit, if there is a target. Stages only if it still isn't enough.

## 3. Spacing and shear on a curve

- **Normal error is about the difference in edge length / (3 x radius), in radians.** Neighbours differ by less than radius / 20 for under 1 degree. It only counts in the direction the surface bends. It runs 3 to 13 % low on big differences. `validate_mesh.py` warns above 5 degrees as `uneven_on_curves`.
- **Don't choose between pole types; fix spacing and shear first.** A lone pole adds under 1 degree. Sheared cells cost more: 60/120 degree cells read 2.07 at radius 4, 72/108 read 1.40.
- **Pure quads wobble too.** A dense strip with no pole reads the same as a 3 to 1.

## 4. Size and fit

A ring of radius r ends at r x (4 + 2 cos(360 / n)) / 6, whatever the loops or their width.

| Segments | 4 | 6 | 8 | 10 | 12 | 14 | 16 | 24 | 32 | 64 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Factor | .6667 | .8333 | .9024 | .9363 | .9553 | .9670 | .9746 | .9886 | .9936 | .9984 |

- **To hold a size, scale the ring by 1 / factor.** At a reduction that about halves the tilt but leaves a ridge, 3.5 % of the radius on 16 to 8.
- **Fit** moves each cage vertex along the normal by the gap between its SubD position and a target surface, about 12 times. It cut normal error by 2 to 4 times and ripple by about 4 times, moving the cage 3 to 11 % of an edge. It needs a target; a dense copy is untested.
- Fit alone is the default, because it leaves the rows where they are. On a closed ring, even the rings and then fit. Relax first only on a 3 to 1 where fit leaves too much: it bends the rows, and the stripes wave.

## 5. Circles in a plate

- **Arc rule.** On the plate side a rim is concave, so every arc vertex needs an edge or its quad folds (202 degrees). On a floor it is convex, so every other vertex is enough.
- **8 segments in a 2 x 2 grid:** a diagonal from the rim to each grid corner. **16:** a 4 to 2 per quarter.
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
- Not tested: unequal widths, a support loop beside a reduction.

## 7. Native tools

LoopTools isn't part of Blender 5.2, and the pipeline doesn't call add-ons (`docs/pipeline/addon-requests.md`). These ran headless on 5.2.3.

| Job | Call | Watch for |
| --- | --- | --- |
| Even a ring | `bmesh.ops.space_edge_loops_evenly(bm, geom=edges, interpolation="LINEAR", factor=1.0)`, or `mesh.space_edge_loops_evenly` | It keeps to the old polygon, so the radius drops a little. Round it afterwards |
| Round a ring | `bmesh.ops.circularize(bm, geom=verts + edges, factor=1.0, flatten=1.0)`, or `mesh.circularize` | A wire ring with no faces is left unchanged, with no error. It fits its own radius, so scale to the size you need and check the result |
| Relax | `mesh.vertices_smooth_laplacian`, `bmesh.ops.smooth_laplacian_vert` | There is no Relax operator |
| Bevel by script | `bmesh.ops.bevel(bm, geom=edges, offset=w, segments=2, profile=1.0, affect="EDGES", clamp_overlap=False, loop_slide=False)` | The bmesh default is `affect="VERTICES"`. The modifier defaults to Loop Slide and Clamp Overlap on; the operator has Loop Slide on and Clamp off. Set every option |
