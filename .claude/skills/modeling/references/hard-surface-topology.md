# Hard-surface topology, every route

Applies to every modelled hard-surface asset, SubD or game. Not to Tripo stand-ins, a generated mesh under repair, or photo-projected fast CG.

## The mesh

- **Mostly quads in the source.** Triangulate at export, on the delivery copy, never in the source. A triangle on a flat or hidden face is fine for a game asset. A triangulated source can't be edited or reviewed.
- **N-gons only where they lie flat** and carry no SubD. An n-gon on a curve shades however the engine splits it.
- **Every edge has a job.** It describes a curve, supports a bevel or leads to a detail. If removing it changes neither shape nor shading, remove it. Flat faces carry no grid, except the rows with a job: the two rows beside a curve keep poles off it, and flat rows keep a rim regular.
- **Loops run straight along the form.** A loop that kinks on a flat face or a straight run means something was traced from the photo. Fix the source of it, not the loop.
- **Spend loops where the form bends and where the eye lands**, not evenly over the whole object.

## Openings and details

- **Quads lead.** Every hole, slot and button comes from the loop flow. Leave the loops in place, delete the faces inside the hole, and put the poles (3- or 5-edge vertices) at the hole corners so they turn the flow. On a curved face, keep a pole two clear rows off the curve where the form allows ([subd-recipes.md](subd-recipes.md)).
- **Plan the opening before the shell has detail.** Route loops round it. Never cut a plane or a Boolean across a finished grid.
- **An opening in a curved wall** (Frank Polygon's method; our own test hasn't been run):
  - Raise the wall's segment count until its edges line up with the hole's. On a perpendicular cylinder, match only out to 45 degrees either side of the centre line, and cut the rest as loops across the wall.
  - Use the wall's own edges as the support loops. Loops added beside them pinch.
  - A rectangle lands between two wall edges, with a gap left to run out a fillet.
  - Finish the surface first, then cut.
  - If the counts can't match, keep the error in the support loop, small and out of the way, or spread it wide.
- **Split parts like the real product.** A separate part on the real object is a separate part in the mesh: glass, inner plate, screws, gland, cover. A seam is a real gap between two pieces, not a groove carved into one mesh.

## Round details

- **Segments are a multiple of 4 and of the repeat count,** so vertices land on the mirror planes and every sector matches. An 8-bolt flange has 8, 16 or 24. `check_spec.py` refuses anything else.
- A larger circle needs more. Step up 8, 16, 32 for the small, the medium and the large at the same distance. Changing the count along one form is in [subd-recipes.md](subd-recipes.md).
- **A circle in a flat face:** make a ring of quads round it that ends on a square, so the surrounding grid meets four straight sides.
- **Repeating round a centre:** model one sector, Array it round an empty, and merge. Half circles are a full circle's segment count cut on a mirror plane, so a vertex sits on the plane.

## By script

A script makes the same mistakes faster. Build each part as a parametric patch from the blueprint's dimensions (a grid, a ring lattice, a swept profile) with its loops already where the openings and curves need them. Avoid:

- mapping photo pixels to vertices
- `bmesh.ops.bisect_plane` across a finished surface
- triangulating to fill a hole, unless the hole is flat and the face is then dissolved back to an n-gon or quads
- bevels with default options: the operator, `bmesh.ops.bevel` and the modifier default differently, so set every one
- edit-mode operators with other objects still selected: they change every selected object, so deselect first and check the vertex counts after

## Check it

`validate_mesh.py` reports the numbers under `topology`, as warnings. `asset_capture.py --modes wire` shows the edges, and `--modes reflect` shows kinks on curved faces that matcap misses. Compare two meshes in stripes only from the same camera. Look at the wire from every side, close up on each opening, before you report a mesh as done: the numbers find a problem, the wire shows it. The supervisor reads the same views.
