# Construction by shape class

Classify first, then build.

## Classify

| Class | Test | Example |
| --- | --- | --- |
| Single volume, axial | Every horizontal section is a circle around one axis | Bottle, vase, column, lamp base |
| Single volume, symmetric | Mirrors across one, two or three planes | Tube end, shell, box with rounded corners |
| Single volume, asymmetric | No usable axis or mirror | Mouse shell, sculpted cap |
| Multi volume | Several simple volumes joined into one connected mass | Cream jar with a square base and a round neck |

## Axial objects

| Method | How | Best for |
| --- | --- | --- |
| 1. Cylinder, loop cuts, scale | Cylinder, add rings, scale each ring | Simple profiles with few changes |
| 2. Profile and Spin 360° | Draw half the profile, spin around the axis, then Merge by Distance. The Screw modifier keeps the profile editable | Complex profiles. Most accurate and fastest |
| 3. Extrude from a circle | Circle, extrude and scale ring by ring | Quick tests |

- **Thickness:** draw a closed profile covering the outside, the lip and the inside, using real wall values. Example: a 20 cm bottle with a 2 mm wall, 2.5 mm lip and 3 mm base.
- **Grooves:** a four-point notch in the profile, with holding loops on both edges.
- **Tilted objects:** build upright on the axis, parent to an empty, and rotate the empty. To estimate the tilt from a photo, measure the ellipse of a circular rim: minor ÷ major = cos(tilt).
- **Threads:** simplify to parallel rings unless the thread is seen in close-up.
- **Profile from an image:** scan the silhouette row by row, keep only the inflection points, then overlay the result on the image to verify it.

## Symmetric objects

- Mirror on three axes and build 1/8; two axes, build 1/4; one axis, build 1/2.
- Vertices on a mirror plane sit exactly at 0, with Clipping and Merge on.
- A photo taken from one side still shows a symmetric object. A taper, a lean or one wider side that perspective explains is not asymmetry.
- Keep the Mirror live in the source. Apply it only on the delivery copy. A real asymmetry (a seal, a cable, one lug) goes on top as its own part, listed in the spec's `form`.
- **Repeats round a centre:** one sector, Array round an empty, merge. See [hard-surface-topology.md](hard-surface-topology.md).
- Simple cases: scale from a primitive.
- **Crimped ends** (a tube tail): build the body up to the transition loop, duplicate that loop (Shift+D), separate it (P), and grow the crimp as its own flat-shaded object. Space the crimp points with `space_edge_loops_evenly`, leaving out the end points. Two crimp types are common: herringbone and raised rib.

## Asymmetric objects

The hardest class: no axis, no mirror. The job is to redraw the mesh so it hugs the reference.

1. Block the rough mass in low poly, with only the big shape right.
2. Add loop cuts where detail sits, and use SubD for smoothness.

- **One view differs a lot:** one reference plane on that axis, and push vertices to match it.
- **Several views differ:** a reference per view, and balance vertices until every view matches.
- **The rough mass is close to a primitive:** build a core primitive and Shrinkwrap the cage onto it, so vertices stay on the core surface while you move them.
  - Final shape still close to the core: keep the modifier and use its vertex group. Vertices in the group stick to the core; the rest move freely.
  - Final shape far from the core: apply the Shrinkwrap once the points are placed, then continue.
- Example stack for a curved shell: Subdivision, Shrinkwrap, Subdivision, Solidify, Bevel. Measure clearances after the last SubD, because it shrinks the shape.

## Multi-volume objects

- The result is one connected mass, not parts stuck together.
- **Rule 1, simple to complex:** start from the volume that is an unmodified primitive and grow the others from it.
- **Rule 2, few edges to many:** start from the volume with the fewest edges (a cube) and step up to the one with the most (a cylinder).
- Step up with loop cuts. Avoid Subdivide and Knife, which spread unwanted points. Avoid Inset; extrude, then round the ring with `circularize` or To Sphere.
- **Changing edge counts:** to halve a ring, a three-quad 4 to 2 in every unit. For a small local change, a mirrored pair of 2 to 1s set apart, then a 4 to 2, then a 3 to 1. All mix with 1-to-1 rows. Recipes and row heights are in [subd-recipes.md](subd-recipes.md).
- **Square base to round neck:** extrude the top face of the cube, round the new ring with `circularize`, and add holding loops at the shoulder.
- **Separate caps** sit as their own objects with a 0.2 to 0.6 mm gap. Interleave ribs with the body's flow instead of fighting it.

## Repeating tiers: Array and Extrude Individual

For tiered or ribbed objects such as a stacked lamp or a ribbed vase:

1. Build one tier as an open tube.
2. Add an Array with a constant offset and Merge on, then apply it.
3. Extrude the base and top from the boundary loops instead of joining separate parts.
4. Smooth by Angle at 30°.
5. For alternating ribs, select every other face ring and use Extrude Individual Faces (`bmesh.ops.extrude_discrete_faces` in scripts).

## Reading references

- Cross-check plan views against elevations before trusting either.
- When two images disagree, take the middle value and report it in the spec.
- Where volumes meet, they meet. No interpenetration.
