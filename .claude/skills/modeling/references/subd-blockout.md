# SubD from a blockout

The route for flat and prismatic SubD parts: plates, brackets, housings with straight walls. Block the part out from simple shapes, Boolean or union them, clean the new edges, then add SubD. This is the user's own order. It has run once, by script, on one drawn plate of 11 shapes, so take the numbers as a start and measure yours.

A cut into a curved face stays on the loop flow or a replaced patch ([subd-recipes.md](subd-recipes.md) section 8). One part can use both.

Keep everything in one script, with each shape as a row of data, so a change re-runs the whole part. Nothing in the clean-up may use a vertex index.

## Counts

- **Every sharp edge gets a bevel of 2 or 4 segments, chosen from the reference.** Use 2 on a tight edge and on a hidden face, and 4 where the reference shows a visible radius. In a tight spot use half the width. If that doesn't fit, report the edge instead of dropping its bevel. The only edges left out are on sharp details that have their own Shade Flat object with no SubD.
- **Fillets and rounded corners on the base are 2 or 4 segments too.** The base stays simple and SubD does the smoothing. Before this rule the plate's Boolean had 678 faces. With it, 223.
- **Circles are a multiple of 4 in most cases, and always even.** Use 6 only on a small hole where that section can't be retopologised, with `why_6` in the spec. Grid Fill needs an even ring: 6 gives 2 quads, 8 gives 4, 12 gives 9, 16 gives 16, and 7 gives nothing, with no error.

## 1. Blockout, big to small

- Build from the blueprint at real scale, biggest shape first, one object per shape.
- An outline that isn't a primitive is a row of lines and arcs read off the blueprint, never a trace of pixels.
- Give each feature one operation before you model it:

| Feature | Operation |
| --- | --- |
| Hole through a flat | Difference |
| Pocket with rounded corners and floor | Difference, with the cutter already filleted |
| Open slot | Difference, with the cutter running past the outline |
| Boss or raised pad | Union, or a separate part if it's separate on the real product |
| Screw or raised label | Separate object, no Boolean |
| Fine printed or engraved text | Left for the texture, and listed in the report |
| Cut into a curved face | Not this route |

## 2. Shape each piece, then Boolean or union

- **Bevel, extrude and inset each shape first,** so each cutter brings its own rounded corners and the operation has less to repair.
- **Draw rounds so SubD lands on the size.** SubD pulls a ring in by (4 + 2 cos(360 / n)) / 6: 8 sides .9024, 12 .9553, 16 .9746. Draw the ring at r / factor. In a fillet the tangent points stay on the lines. With 2 steps the middle point goes at r x (6 - 2 cos t) / 4, where t is the turn per step. With 4 steps the inner points go at r x 6 / (4 + 2 cos t).
- **Closed cutters, and no faces lying on each other.** Run a cutter 5 mm past every surface it crosses, and start a boss or pad inside the plate. Manifold returned the target unchanged, with no error, for an open cutter, so check that each operation changed the face count.
- **Union first, then Difference with all the cutters in one collection, on the Exact solver.** Take the result with `bpy.data.meshes.new_from_object` from the evaluated object. The plate took 0.05 s.
- Keep the shapes and cutters in the file, hidden.

**Stop here, without autopilot.** Capture solid and wire and show the user the Boolean shape. A wrong shape is one number here. After the clean-up it also means checking every line again.

## 3. Find the new edges, clean, round, even, push

1. **Find.** The Mesh Boolean node in Geometry Nodes has an `Intersecting Edges` output: store it as an edge attribute. A surface test also works: an edge whose ends and midpoint lie on both shapes, within 2e-6 m. On a 32-segment hole through a plate both found 64 of 64 edges, on Exact and on Manifold.
2. **Clean.** `bmesh.ops.dissolve_limit(bm, angle_limit=radians(0.05), use_dissolve_boundaries=False, verts=list(bm.verts), edges=list(bm.edges), delimit={"NORMAL"})` removes stray edges and joins flat faces back into one. Expect n-gons of 70 sides or more. They all fail [subd-recipes.md](subd-recipes.md) section 5 until they're split.
3. **Split along planned lines.** Draw these on the blueprint before the Boolean, and keep them in the script as named pairs of positions. Lines run straight, continue a feature's own edge where they can, and give no vertex more than one added line. They end on a feature's tangent point or on the outline. Stop splitting when each flat n-gon's centre sees every edge. Don't let a script pick the shortest chords: on the plate that passed every number and still gave stars of long thin spokes, the random cuts the user rejected on the first benchmark. Planned lines haven't been run yet.
4. **Round.** Bevel every sharp edge, as in Counts: `bmesh.ops.bevel(bm, geom=edges, offset=w, offset_type="OFFSET", segments=2, profile=1.0, affect="EDGES", clamp_overlap=False, loop_slide=False, harden_normals=False)`. Width is six times the cut you want along each face. A 4-segment round is profile 0.5 with a support row on each flat ([subd-recipes.md](subd-recipes.md) section 6). It hasn't been run on a rim.
5. **Know which edges are sharp.** List them from the shapes when you can. An angle test needs a limit of about 70 degrees: at these counts a 2-segment fillet turns 45 degrees a step and a 6-sided hole 60, and a limit of 35 turned the screw holes into rounded hexagons. On the plate 70 found all 244 sharp edges, but with almost no margin: the largest soft edge was 69.6 and the smallest sharp one 71.4. So use the list, and the angle as a check.
6. **Rows on flat n-gons.** After the bevel, bevel the edges of each top or floor n-gon whose other face leaves its plane, at half the width. Leave walls out: a wall's 5-gon would put hard edges on a round.
7. **Even.** Measure the softening along each rim against w x 1.41 / 6. On the plate the median was right, 0.143 against 0.141 mm, but it ran 0.057 to 0.184 at p5 and p95, and 0.016 to 0.293 at the extremes. This isn't solved or traced, so look at those places and report them. One try at evening edge lengths, by splitting long rim edges, gave 84 folds. It wasn't traced and may have been the script.
8. **Push.** Step 2 does most of this. Read each round after SubD, and if it's off, move its points along the radius.

## 4. SubD conversion

- Add the Subdivision modifier last. Work at level 1 and check at level 2.
- Run `validate_mesh.py` and read `topology.folded_edges` and the failed n-gons. Then look at the wire from every side, because numbers pass on poor flow.
- To measure a part with no scan, run the same script at high counts, such as 16 segments per fillet and 64-sided circles, and use that as the target at level 4. The plate's target had 2,390 faces.

## What the plate measured

Outer corners 4 segments, pocket and slot corners and floors 2, hole and boss 12 sides, screw holes 8, all pushed, with script-picked split lines.

| Stage | Faces | N-gons | Shortest edge |
| --- | --- | --- | --- |
| Blockout | 233 | | |
| After the Boolean | 223 | 22, up to 77 sides | 0.35 mm |
| After the clean-up | 303 | 36, up to 14 sides | 0.35 mm |
| Final cage | 876 | 36, of which 8 fail the validator | 0.30 mm |

- **Folds at level 2: 0.** A denser version sent straight to Bevel and SubD with no clean-up gave 766 folded edges and a 5.8 mm flap, so the clean-up isn't optional.
- **Sizes:** the hole of r 6 read 5.989 to 6.086 and the screw holes of r 2.5 read 2.487 to 2.553.
- **Against the target:** away from edges, 0.223 mm at p95 and 0.417 mm at worst, on a pocket wall.
- The 8 failed n-gons were all 5-gons touching an off-plane face, and none was blind.

## Not tested

Planned split lines, a 4-segment round on a rim, a live Bevel on a Boolean result, a raised pad, a real reference, and how long the route takes on a real part. Stopping before step 4 should give a mid-poly game mesh from the same source, with Bevel and weighted normals, but that hasn't run either.
