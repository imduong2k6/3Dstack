# SubD with quads

Used for CG close-ups and hero products. Web sources are noted.

## Mesh rules

- **Low poly first.** Keep the cage as light as the form allows. Smoothness comes from the Subdivision Surface modifier, never from a dense cage.
- **Quads under SubD.** A face with five or more corners shrinks and puckers when subdivided. Delete vertices that no longer shape anything so the faces go back to quads.
- **Few cuts at bends.** Only enough loops to define a bend. Don't cut densely to force smoothness.
- **Sharp details are separate objects.** Crimps, knurling, teeth and serrations go on their own Shade Flat object without SubD. The smooth body stays Shade Smooth with SubD.
- **Levels:** work at viewport 1, check at 2, render at 2. Higher levels hide cage problems instead of fixing them.

## Holding edges

Catmull-Clark subdivision smooths every corner, so anything that should stay sharp needs support.

| Method | When |
| --- | --- |
| **Holding (support) loop**, the default | Add a loop 0.3 to 1 mm from the sharp edge, on both sides if the edge sits between two faces. The closer the loop, the sharper the edge |
| Local bevel (Ctrl+B) | Only when asked, or when a loop would run somewhere it damages the form |
| Bevel modifier, crease | Not used in the SubD route. The game route uses bevel plus weighted normals instead (see game-models.md) |

- **Support only the edges that are sharp in the reference:** base edge, lip, a ring edge, both edges of a groove, a foot. Rounded areas such as a bottle shoulder or a rounded cap edge stay soft.
- **Inner faces need support too.** Anything with thickness (cap, cup, bowl) needs holding loops at the inner corners as well, or the inside bows.
- **Round objects: avoid extra vertical cuts.** Uneven point spacing on a circle makes the subdivided edge kink. If a cut is unavoidable, re-space the ring and make it round again (LoopTools Space and Circle). In scripts, space smooth rings evenly by angle, cluster points only on ribbed rings, and blend between the two over a few rings.

## Hard surface without Boolean

The course's preferred hard-surface method.

- The rules shared with the game route (quads lead, openings from the loop flow, parts split like the real product) are in [hard-surface-topology.md](hard-surface-topology.md).
- **No Boolean cuts.** Booleans leave n-gons, triangles and broken flow. SubD then warps and the surface around the hole ripples.
- **Shells are single-layer surfaces** with the edge folded inward: a holding loop just under the lip, the wall, then a short fold inward. Use Solidify only when the thickness itself is visible.
- **Rounded corners:** don't put the core grid's corner on the outline. Inset the grid by 0.3R or more (R = corner radius) and let concentric rings wrap the corner, or the corner face flattens to nearly 180°. Keep face angles between about 35° and 145°.
- **Matching a source shape** (a scan, the user's base mesh, a higher-resolution model):
  - Take the top edge from the source surface after subdivision.
  - Take wall loops from the real intersection of a section plane with the source, not from an outline. An outline misses undercuts such as a U-shaped wall bottom.
  - Place anchor vertices at the corners first and connect each top-edge anchor to its matching bottom-edge point.
  - **Compensate for SubD shrinkage iteratively.** Move each vertex along one fixed direction per region (vertical for top faces, along the normal for walls) so loops don't slide across each other.
  - Measure against the source subdivided at level 4, surface to surface, not to vertices. Reference result from the course: mean deviation about 0.06 to 0.09 mm, with 95% of points under 0.3 mm.
  - Don't snap each vertex to its nearest point on the source. Loops near the edge cross and the flow tangles.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Bevel uneven or skewed | Apply Scale first, or scale in Edit Mode |
| Bevel goes one way only | There are duplicate vertices or edges. Run Merge by Distance |
| SubD surface wobbles near a hole | There is a Boolean or an n-gon there. Rebuild the hole from the loop flow |
| Rim kinks after SubD | Uneven spacing on a round loop. Re-space with LoopTools |
| Inside of a cup bows | No holding loops on the inner corners |
| Shape shrinks under SubD | Compensate as described above, or add a loop closer to the extremes |

## Web sources

- [SubD support loops 101 (3dft)](https://3dft.notion.site/SubD-Support-Loops-101-3cf944ec377642c6a3e7653029eea281)
- [Matt Murch: leveraging multiple workflows](https://mattmurch.artstation.com/blog/Oba9/leveraging-multiple-workflows)
