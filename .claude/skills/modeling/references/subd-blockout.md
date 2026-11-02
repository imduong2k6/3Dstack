# SubD from a blockout

The route for flat and prismatic SubD parts: plates, brackets, housings with straight walls. Block the part out from simple shapes, Boolean or union them, clean the new edges, then add SubD. This is the user's own order. It has run on one drawn plate of 11 shapes, by script, and twice on one bracket from a photo. The second bracket passed the validator only at a 0.015 mm merge distance and with 33 folded edges, so this route hasn't yet given a finished part. Take the numbers as a start and measure yours.

A cut into a curved face stays on the loop flow or a replaced patch ([subd-recipes.md](subd-recipes.md) section 8). One part can use both.

Keep everything in one script, with each shape as a row of data, so a change re-runs the whole part. Nothing in the clean-up may use a vertex index.

## Counts

- **Every sharp edge gets a bevel of 2 or 4 segments, chosen from the reference.** Use 2 on a tight edge and on a hidden face, and 4 where the reference shows a visible radius. In a tight spot use 0.45 of the room across, because exactly half lands the rows from facing rims on one line, with a floor of 0.1 mm. Report each edge that took less than its class's width instead of dropping its bevel, and look at the ones on the floor: on the bracket about 65 edges didn't fit and seven sat on the floor, and those read worst. The only edges left out are on sharp details that have their own Shade Flat object with no SubD.
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
- **Check before building.** A cutter's floor ring is its wall ring moved in by the floor fillet, so every corner radius must beat that fillet by a margin. Filleted cutters must not overlap or meet at a floor: draw them as one cutter. Print the shortest edge of every ring of every cutter and stop under about 0.2 mm, the margin that held on the 180 mm bracket. Its first Boolean broke these checks and gave 73 n-gons, 3 tris and a 0.024 mm edge. Fixed, the shortest edge was 0.207 mm.
- **Closed cutters, and no faces lying on each other.** Run a cutter 5 mm past every surface it crosses, and start a boss or pad inside the plate. Manifold returned the target unchanged, with no error, for an open cutter, so check that each operation changed the face count.
- **Carry a source attribute.** Give each shape's faces an INT face attribute holding the shape's id. The Exact solver keeps it through the Boolean, so every later step knows which shape a face came from.
- **Order: Difference, Union, Difference, each group's shapes in one collection, on the Exact solver.** Cut what lives in the base, union what stands in those cuts, then cut what passes through the raised parts and trim the back. Union first would cut a boss or tab that stands in a pocket. With nothing raised in a cut, Union then Difference is enough. Take the result with `bpy.data.meshes.new_from_object` from the evaluated object. The plate took 0.05 s and the bracket's 23 objects 0.43 s.
- Keep the shapes and cutters in the file, hidden.

**Stop here, without autopilot.** Capture solid and wire and show the user the Boolean shape. A wrong shape is one number here. After the clean-up it also means checking every line again.

## 3. Find the new edges, clean, round, even, push

1. **Find.** An edge whose two faces have different source ids is a new edge. On the bracket that was simpler than the two other ways, and it also gives each edge its class in step 5. The Mesh Boolean node in Geometry Nodes has an `Intersecting Edges` output, which you can store as an edge attribute. A surface test also works: an edge whose ends and midpoint lie on both shapes, within 2e-6 m. On a 32-segment hole through a plate both found 64 of 64 edges, on Exact and on Manifold.
2. **Clean.** `bmesh.ops.dissolve_limit(bm, angle_limit=radians(0.05), use_dissolve_boundaries=False, verts=list(bm.verts), edges=list(bm.edges), delimit={"NORMAL"})` removes stray edges and joins flat faces back into one. It doesn't remove the solver's bridge edges, which tie a hole to an outer rim across a flat. When those stay, delete every flat face with its inner edges and the T vertices left on straight runs. Cut the walls and then rebuild each level's flats by walking the planar graph of its rims and planned lines, and check that the rebuilt areas add up to what came off, so a rim left unjoined stops the run. Expect n-gons of 70 sides or more before the split; the bracket's back had 134. They all fail [subd-recipes.md](subd-recipes.md) section 5 until they're split.
3. **Split along planned lines.** Draw these on the blueprint before the Boolean, and keep them in the script as named pairs of positions. Don't let a script pick the shortest chords: on the plate that passed every number and still gave stars of long thin spokes, the random cuts the user rejected on the first benchmark. Count the rings and narrow walls when you plan: the bracket needed 209 lines against 104 first planned. These rules come from that one run:
   - Lines run straight and end on a feature's tangent point or on the outline.
   - **On a ring, lines run radially, from the ring's own points.** Between concentric rings, such as a counterbore and its hole or a boss and its bore, each ring point gets a radial line to the next ring. Lines along a ring's tangent gave folding wedges at the boss.
   - **A narrow wall gets a quad on each side,** with a line across it and a new rim point at each end. A thin flat beside a far n-gon centre folds in plane, and the centre test in step 7 misses that.
   - **No long wedges.** Two long sides closing on a short end fold, or leave slivers once the bevels move the rims.
   - A vertex takes more than one line when a ring or a narrow wall needs it. The bracket's largest valence was 6.
   - A line that ends in the middle of a rim cuts on down the wall below it in a column, so the wall stays quads.
4. **Round.** Bevel every sharp edge, as in Counts. Where 2 and 4 segments meet, run the 4 first.
   - **One width:** `bmesh.ops.bevel(bm, geom=edges, offset=w, offset_type="OFFSET", segments=2, profile=1.0, affect="EDGES", clamp_overlap=False, loop_slide=False, harden_normals=False)`. Width is six times the cut you want along each face.
   - **A width per edge:** `bmesh.ops.bevel` has one width, so use the Bevel modifier with `limit_method="WEIGHT"`, `edge_weight="bevel_weight_edge"` and `width` at the largest width, set each edge's weight to its width over that, and take the result back with `new_from_object`. Unequal widths at a nearly straight joint throw a spike, so ease them along the rim. Add the float layer before you hold edges in a dict: added later, it silently loses the values.
   - **A 4-segment round is a custom profile with the rows inside it,** 4 faces across, against 6 with profile 0.5 and a support row on each flat. On the modifier: `profile_type="CUSTOM"`, points (1, a), (m, m), (a, 1) with VECTOR handles, `use_sample_straight_edges` and `use_sample_even_lengths` off, then `initialize(4)`. With s the round's share of the width (0.7 on the bracket), a = 1 - s and m = 1 - 0.189 s, which puts the middle point where SubD lands it on the radius. It ran on 111 edges of one part.
   - A 2-segment chain that ends on a rim leaves a fan of two tris round its middle point. `bmesh.ops.join_triangles` makes the quad.
5. **Know which edges are sharp.** They come from a list, built from the source ids of each edge's two faces and its level, never from an angle. The pushed middle of a 2-step arc turns 64 degrees on a 90-degree fillet and 82 on a 120-degree one, so soft edges overlap sharp ones in angle, and a limit of 35 turned 6-sided screw holes into rounded hexagons.
6. **Rows on flat n-gons.** After the bevel, bevel the edges of each top or floor n-gon whose other face leaves its plane, at half that edge's bevel width. Leave walls out: a wall's 5-gon would put hard edges on a round.
7. **Check the n-gons again.** Stop splitting when each flat n-gon's centre sees every edge, and run that check again after every bevel step, because the bevels move the rims: 28 n-gons that passed at the split went blind later. Change a planned line and re-run the script instead of patching the mesh.
8. **Even.** Measure the softening along each rim against w / 3 x sin(turn / 2), with w the distance to the row on each face and turn the angle between the two faces. That's the limit of the three rows, and at 90 degrees it's w x 1.41 / 6. On the plate the median was right, 0.143 against 0.141 mm, but it ran 0.057 to 0.184 at p5 and p95, and 0.016 to 0.293 at the extremes. The bracket's 629 edges ran 0.417 to 1.493 times the target at p5 and p95, with a median of 0.843. This isn't solved or traced, so look at those places and report them. One try at evening edge lengths, by splitting long rim edges, gave 84 folds. It wasn't traced and may have been the script.
9. **Push.** Section 2 does most of this. Read each round after SubD, and if it's off, move its points along the radius.

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

## What the bracket measured

The second run, by a new agent on this file's rules and with the first run's reading of the part, compared with the first:

| | First | Second |
| --- | --- | --- |
| Failed n-gons | 68 of 159 | 0 of 70 |
| Folded edges | 9 | 33, 20 of them where a hold ends at an L in a wall |
| Cage faces | 2,589 | 2,414 |
| Tris in the cage | 0 | 24 |
| Softening over target, p5 to p95 | 0.42 to 1.51 | 0.39 to 1.71 |
| Boss radius against 15.145 mm | 15.13 to 15.16 | 15.13 to 15.49 |
| Minutes | 77 | 71, with the part already read |

These rows were read at level 4 by a separate script, except the minutes. Inside the first run's failed n-gons the surface normal turned 13 degrees at the median, against 0.03 in the passing ones, so the n-gon rule stands. A hold ending at an L in a wall has no recipe yet: six tries gave 51 to 471 folds.

The first run: one agent, one front photo, at the rules before this file's Boolean order, split lines and bevel recipes. Every depth was guessed from shading and the 180 mm height was assumed. It took about 77 minutes: 29 up to the Boolean shape, nearly all of it reading the part and planning lines, and 48 on the clean-up, mostly folds falling 193, 67, 34, 21, 9.

| Step | Faces | N-gons | Shortest edge |
| --- | --- | --- | --- |
| After the Boolean | 577 | 67, up to 134 sides | 0.207 mm |
| Split | 812 | 116, up to 17 sides | 0.189 mm |
| Round, 4 segments | 1,261 | 129 | 0.046 mm |
| Hold, 2 segments | 2,352 | 145 | 0.040 mm |
| Rows on floors | 2,589 | 159 | 0.040 mm |

- **Fails the validator:** 68 of 159 n-gons, with 9 folded edges where the tab meets the plate. A bevel's chain end puts a T on the next face, so a quad becomes a 5-gon that touches an off-plane point: 55 failed on that alone.
- **Sizes held:** at level 4, 132.57 x 14 x 179.98 mm against 132.79 x 14 x 180, holes 2.82 to 2.832 against 2.825, bore 10.093 to 10.099 against 10.095.
- **Bevelling every sharp edge costs the most faces:** the 2-segment holds on 518 edges added 1,091 of the 2,589.

## Not tested

A live Bevel on a Boolean result, a raised pad on the outline, and a re-run after a depth change. The split-line rules above come from one part. Stopping before section 4 should give a mid-poly game mesh from the same source, with Bevel and weighted normals, but that hasn't run either.
