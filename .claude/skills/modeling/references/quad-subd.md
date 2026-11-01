# SubD with quads

Used for CG close-ups and hero products. Web sources are noted. Counts, reductions, circles in a plate and loop widths, with measured numbers, are in [subd-recipes.md](subd-recipes.md).

## Mesh rules

- **Low poly first.** Keep the cage as light as the form allows. Smoothness comes from the Subdivision Surface modifier, never from a dense cage.
- **Quads under SubD.** A face with five or more corners shrinks and puckers when subdivided. Delete vertices that no longer shape anything so the faces go back to quads. The one exception is a flat n-gon with a support row all round and a centre that sees every edge ([subd-recipes.md](subd-recipes.md), section 5).
- **Few cuts at bends.** Only enough loops to define a bend. Don't cut densely to force smoothness.
- **Sharp details are separate objects.** Crimps, knurling, teeth and serrations go on their own Shade Flat object without SubD. The smooth body stays Shade Smooth with SubD.
- **Levels:** work at viewport 1, check at 2, render at 2. Higher levels hide cage problems instead of fixing them.

## Holding edges

Catmull-Clark subdivision smooths every corner, so anything that should stay sharp needs support.

| Method | When |
| --- | --- |
| **Holding (support) loop**, the default | Add a loop beside the sharp edge, on both sides if the edge sits between two faces. A loop at width w softens the corner by w / 6 each way, on any scale, so set the width to six times the cut you want |
| Bevel as a loop inserter | 2 segments, profile 1.0, Loop Slide off. It keeps the surface and the rim. A live modifier keeps the cage simple and the width adjustable; set every option, because the defaults differ |
| Crease | Vertex crease 1.0 only on a border corner that can't take the three-quad fix. No edge crease: it may not survive export and it still needs support nearby. The game route uses bevel plus weighted normals instead (see game-models.md) |

- **Support only the edges that are sharp in the reference:** base edge, lip, a ring edge, both edges of a groove, a foot. Rounded areas such as a bottle shoulder or a rounded cap edge stay soft.
- **Every sharp edge gets a bevel of 2 or 4 segments, chosen from the reference.** Use 2 on a tight edge and on a hidden face, and 4 where the reference shows a visible radius. In a tight spot use half the width, and if that doesn't fit, report the edge.
- **Inner faces need support too.** Anything with thickness (cap, cup, bowl) needs holding loops at the inner corners as well, or the inside bows.
- **Round objects: avoid extra vertical cuts.** Uneven point spacing on a circle makes the subdivided edge kink. If a cut is unavoidable, re-space the ring straight after it and make it round again (`space_edge_loops_evenly`, `circularize`). In scripts, space smooth rings evenly by angle, cluster points only on ribbed rings, and blend between the two over one or two rings.

## Hard surface

- The rules shared with the game route (quads lead, openings from the loop flow, parts split like the real product) are in [hard-surface-topology.md](hard-surface-topology.md).
- **A flat or prismatic part starts from a blockout and Booleans:** [subd-blockout.md](subd-blockout.md).
- **On a curved part, build from the loop flow first; a Boolean is a tool, not the plan.** On an unprepared grid it leaves n-gons, triangles and broken flow, and SubD then warps the surface around the hole. All three solvers left n-gons on a simple cut in Blender 5.2, and Manifold returned the target untouched, with no error, for an open cutter. It can work on a prepared base (Frank Polygon's tutorials): base edges matched to the cutter, Merge by Distance and Limited Dissolve after, no stray edges, and room left for the loops. Anything curved must still come out in quads. On an unprepared curved wall, replace the patch round the cut rather than repair it: see [subd-recipes.md](subd-recipes.md) section 8. A repair that keeps the solver's rim is still untested.
- **Shells are single-layer surfaces** with the edge folded inward: a holding loop just under the lip, the wall, then a short fold inward. Use Solidify only when the thickness itself is visible.
- **Rounded corners:** don't put the core grid's corner on the outline. Inset the grid by 0.3R or more (R = corner radius) and let concentric rings wrap the corner, or the corner face flattens to nearly 180°. Keep face angles between about 35° and 145° on curved faces. Flat plates read 29° to 158° in tests and their rims still held.
- **Matching a source shape** (a scan, the user's base mesh, a higher-resolution model):
  - Take the top edge from the source surface after subdivision.
  - Take wall loops from the real intersection of a section plane with the source, not from an outline. An outline misses undercuts such as a U-shaped wall bottom.
  - Place anchor vertices at the corners first and connect each top-edge anchor to its matching bottom-edge point.
  - **Compensate for SubD shrinkage iteratively.** Move each vertex along one fixed direction per region (vertical for top faces, along the normal for walls) so loops don't slide across each other. Measured as "fit" in [subd-recipes.md](subd-recipes.md): about 12 passes against a target surface, or one solve on an exact height field.
  - Measure against the source subdivided at level 4, surface to surface, not to vertices. Reference result from the course: mean deviation about 0.06 to 0.09 mm, with 95% of points under 0.3 mm.
  - Don't snap each vertex to its nearest point on the source. Loops near the edge cross and the flow tangles.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Bevel uneven or skewed | Apply Scale first, or scale in Edit Mode |
| Bevel goes one way only | There are duplicate vertices or edges. Run Merge by Distance |
| SubD surface wobbles near a hole | A Boolean, an n-gon, a pole on the curve or uneven spacing: pure quads wobble too. Rebuild the hole from the loop flow, or on a flat part re-plan its lines ([subd-blockout.md](subd-blockout.md)). Keep poles two rows off the curve, even the spacing |
| Rim kinks after SubD | Uneven spacing on a round loop. Re-space with `space_edge_loops_evenly` |
| Dent or ridge where a ring changes count | A wide edge left below the reduction, or a row too short. Even both rings, make the row taller, then fit ([subd-recipes.md](subd-recipes.md)) |
| Inside of a cup bows | No holding loops on the inner corners |
| Shape shrinks under SubD | Scale each ring by 1 / factor ([subd-recipes.md](subd-recipes.md)), and compensate as described above. A closer loop doesn't bring a ring's radius back |
| Bevel row collapses on oblique edges | Loop Slide is on. Turn it off |

## Web sources

- [SubD support loops 101 (3dft)](https://3dft.notion.site/SubD-Support-Loops-101-3cf944ec377642c6a3e7653029eea281)
- [Matt Murch: leveraging multiple workflows](https://mattmurch.artstation.com/blog/Oba9/leveraging-multiple-workflows)
- [Frank Polygon: Boolean and Sub-D, 123 blocks](https://frankpolygon.artstation.com/blog/oebM/boolean-sub-d-hard-surface-modeling-123-blocks-exercise-tutorial)
- [OpenSubdiv: modeling tips](https://graphics.pixar.com/opensubdiv/docs/mod_notes.html)
