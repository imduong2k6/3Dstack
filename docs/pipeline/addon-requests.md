# Blender add-on requests

What the user is building so that modelling runs stop rewriting the same helpers. Integration (a `toolbox/tools/` file, skill pointers) comes after the current kit test.

## The rule: from scratch, native Blender only

Decided by the user on 31 Oct 2026: these add-ons are written from scratch and rely on no third-party add-on, because another user may not own those plugins.

- **Native Blender and Python only.** That means `bpy`, `bmesh`, `mathutils`, modifiers, Geometry Nodes and Cycles.
- **No calling, wrapping or copying third-party add-ons,** free ones included. Reading one to learn a technique is fine, but the code is our own.
- **The source lives in this repo,** at `addons/pipeline_tools/`, so a new user gets it with the pipeline. It contains no third-party code, so this doesn't break the rule in `CLAUDE.md`. Add install steps to `docs/setup-windows.md`.
- **Licence `SPDX:GPL-3.0-or-later`,** the usual choice for Blender add-ons. It only matters if the add-on is shared.

## Why these

Three builds of one test prop each wrote their own helpers from scratch: 1,104, 857 and 1,016 lines. All three wrote a loft or strip, a box, a revolve, a rounded outline, a spline tube, text to mesh and a screw. A project's 76 scripts (6,022 lines) repeat the same small functions: 26 of them cast rays, and `cast` and `islands` appear 5 times each, `gap` and `bb` 4 times, `floor_at` and `host_sockets` 3 times.

Those helpers also cost review rounds: 17 floating parts, about 36 kit misfits, 9 cables through solids and then 132 found by lint, a bevel helper that bevelled 0 edges without saying so, and a normals helper that bent window normals.

## What native Blender did in tests

Run on Blender 5.2.3 on small fixtures. Faces were counted; nothing was judged by eye.

| Native tool | Result |
| --- | --- |
| Grid Fill on a round cap | 8 points to 4 quads, 12 to 9, 16 to 16, 32 to 64 |
| Bridge, 16-point ring to a square split to 16 points | 16 quads. Unsplit, it gives 20 tris |

Not tested yet: QuadriFlow remesh, native UV packing and the Cycles bake, all headless. Test them before building modules 8 and 9.

For size targets, a 5.6 mm pan-head screw in one free add-on came to 1,594 tris at 16 divisions and a hex nut to 1,048. That is too dense for a game prop, which is why `screw` has a limit below.

## Shared requirements

One extension, `pipeline_tools`, with one module per section below. One version and one `enable()` call suit a run where nothing is on by default. Build the modules in order; each is useful alone.

```
addons/pipeline_tools/
  blender_manifest.toml   LICENSE   __init__.py
  core.py                 # Report, PipelineToolError, topology count
  parts.py  shell.py  rounds.py  finish.py  seat.py  cables.py  ...
  tests/selftest.py
```

`bin/blender-bg` runs `--factory-startup`, so no add-on is on. Scripts enable this one first:

```python
import addon_utils
addon_utils.enable("bl_ext.user_default.pipeline_tools", default_set=True, persistent=False)
```

Every module:

1. **Runs under `blender --background --factory-startup`.** No window, `context.area`, `space_data`, modal or `gpu`.
2. **Plain Python API first.** Functions take objects or a bmesh, and read neither the selection nor the active object. Panels and operators are thin wrappers, and come last: they are for you, not for me.
3. **Metres and real names.** Front is -Y, the wall side is Y = 0, Z is up. Objects use `SM_`, material slots use `M_` by group.
4. **Same input, same mesh,** vertex order included. No random without a seed.
5. **Every call returns a report:** `{tool, version, object, verts, faces, quads, tris, ngons, changed, warnings}`, plus each tool's own numbers below.
6. **Errors are raised.** A call that changes nothing raises `PipelineToolError` with the reason. A silent no-op is a bug.
7. **Modifiers stay live** until the delivery copy.
8. **Topology follows `modeling/references/hard-surface-topology.md`:** mostly quads, n-gons only when flat, round segments a multiple of 4 and of any repeat, even bevels.
9. **Never saves the file, writes preferences or uses the network.**
10. **`VERSION`, and a self-test** that exits 0 or 1. Each module's output passes `validate_mesh.py --stage mesh` with no topology warnings.

## 1. `parts`: the shapes every build rewrites

The largest saving, and the simplest to build.

| Function | Base features |
| --- | --- |
| `ring_circle(r, n, phase=0)`, `ring_rounded_rect(w, h, r, seg)` | Point rings, same count at the same index so they loft cleanly |
| `strip(bm, rings, closed=True, cap_start=None, cap_end=None, material=0)` | Lofts rings of equal count; raises on a mismatch; caps are `"ngon"`, `"grid"` or None |
| `lattice(bm, xs, zs, depth_fn, material=0)` | Quad patch from two lists of cuts and a depth function |
| `box(bm, min, max, material=0)`, `prism(bm, outline, y0, y1, material=0)` | Closed solids with correct normals |
| `round_box(bm, size, radius, arc_div, lin_div=0, material=0)` | All quads, even `arc_div` |
| `revolve(bm, profile, n, center, axis, material=0)` | Profile round an axis; `n` a multiple of 4; closes on the axis without a fan where it can |
| `tube(bm, points, radius, sides, step, material=0)` | Catmull-Rom, no twist along the path, a radius per point, sides a multiple of 4 |
| `screw(bm, head, drive, dia, head_h, shank, segments=16, material=0)` | `head`: pan, hex, socket. `drive`: cross, slot, hex, none. **At most 300 tris with a cross recess** |
| `hex_nut(bm, flats, h, chamfer=True)`, `thread_rings(bm, r, pitch, count, sides)`, `knurl(bm, r, h, count)` | Game density: rings instead of a helix, sector-based so they can use a radial Array |
| `flat_text(bm, text, height, at, width=None, font=None, offset=0.00015, merge=0.00012, material=0)` | Font curve to flat faces, normals facing out, closed outlines, merged enough to pass the 0.1 mm double check. The default font is Blender's own, so it works on any machine |
| `wrapped_text(bm, text, height, radius, angle, axis, ...)` | The same, wrapped on a cylinder, for drums and dials |

**Done when:** a test prop's helper block can be replaced by these calls and its triangle count doesn't rise.

## 2. `shell`: a rounded housing with openings planned in the loops

This answers the first feedback on the test prop: random cuts and loops that weren't straight. The later blind build fixed that by hand (85.8 % quads, 2.5 % idle vertices against 77.6 % and 15.4 %), and spent about a dozen functions on it. If its wireframe is approved, use them as a guide: `build_shell`, `lattice`, `patch_xz`, `dome`, `shell_xs`, `shell_zs`, `roll_points` and `wall_point` in that run's `src/build_meter.py`. That code is ours.

```python
shell(name, width, height, depth, corner_radius, dome=0.0, draft=0.0, arc_div=8, max_cell=0.02,
      openings=[{"kind": "rect", "center": (x, z), "size": (w, h), "corner_radius": r},
                {"kind": "round", "center": (x, z), "diameter": d, "segments": 16}],
      cuts=[{"axis": "z", "at": z}], mirror_x=True, material=0)
```

- Loops land on every opening's edges and run straight to the border. **No Boolean, no bisect, no normal transfer.**
- Half the shape with a live Mirror. Refuse an opening set that isn't symmetric when `mirror_x` is on, and name the opening.
- Corners from a square-to-disc mapping. The back stays flat at Y = 0.
- `region(shell, box) -> faces`, for a cover plate that shares the shell's grid so its edge follows the dome.
- The report adds each opening's edge loop, `corner_error_m`, `idle_share`, `max_valence`.

**Done when:** on a 0.174 x 0.095 x 0.3 m test with one window and one cover: quad share at least 0.8, idle vertices at most 5 %, no edge over 3° off its axis on the flat of the front, each opening corner within 0.1 mm of its request, and `form` reports the mirror within 1 mm.

## 3. `rounds`: round details on square grids

From the feedback's suggestion: find circles, model one sector, array it. Native bridge and Grid Fill already make the quads (see the table above), so this module is small.

```python
ring_patch(bm, face, center, radius, segments=16, loops=1, cap="grid")   # cap: "grid", "open" (a hole) or "boss"
ring_patch_on_surface(bm, faces, center, radius, segments, depth_fn)     # same, following a curved shell
sector_array(obj, count, axis="Y", center=(0, 0, 0))                     # one sector, Array round a helper empty
segments_for(diameter, repeat=1)                                         # steps 8/16/32/64 by size, multiple of 4 and of repeat
```

- Split the square's sides until the point count matches the ring, then bridge. Raise when the counts can't match.
- `sector_array` raises if `segments` isn't a multiple of `count`, keeps the Array live, and reports the empty it added. Files will have this one helper empty, and it needs a non-identity local position.

**Done when:** a 16-point hole in one flat face gives 100 % quads and no pole above valence 5, and a 6-sector hex body joins with no gap at any seam.

## 4. `finish`: bevels, normals, delivery copy

```python
mirror(obj, axis="X", clip=True), array(obj, count, offset)                    # keeps the order: Mirror, Array, Bevel, Weighted Normal
bevel(obj, width, segments=2, angle=30, only="convex")                         # only: convex, all, marked
harden(obj, keep_sharp=True, face_strength=False)                              # Weighted Normal
delivery_copy(root, name=None, merge=0.0001, triangulate=True)                 # a new object; the source is untouched
export_fbx(obj, path)                                                          # the settings blender-adapter's export uses
```

- `bevel` measures the evaluated mesh and **raises if no edge changed**. An odd `segments` raises unless `allow_odd=True`. The report adds `edges_bevelled`, `width_m`, `clamped_edges`.
- `harden` reports `normals_off_deg` against the face normals on flat faces, so a bent window shows up as a number.
- `delivery_copy` joins root and children with modifiers evaluated, keeps custom normals and material slots, and reports triangles per child. `validate_mesh.py` then checks the whole asset, not just the root.

**Done when:** `bevel` on a mesh with no qualifying edges raises, 2 segments on a cube adds faces and reports 12 edges, and the delivery copy of a mirrored, arrayed parent and child has the same evaluated triangle count as the source.

## 5. `seat`: place things on real surfaces

Use `mathutils.bvhtree.BVHTree` on evaluated meshes.

```python
seat(obj, hosts, direction="-Z", gap=0.0, align="none", sample="corners")     # align: none or normal
seat_many(rows)                                                               # batch; one host tree per host, one report per row
gap(a, b, reach=0.1), world_box(obj), islands(obj), first_hit(origin, direction, hosts)
```

- The report adds `gap_before`, `gap_after`, `hit_object`, `hit_normal`, `tilt_deg`.
- **No hit raises** and names the object and direction. Asking for `align="normal"` on a rough surface reports the spread of normals.

**Done when:** a box 5 cm above a tilted plane lands within 0.1 mm at every corner with `align="normal"`, and a box with nothing below raises.

## 6. `cables`: hanging cables and bundles

`linear-runs` already routes runs along walls. This adds what it doesn't have.

```python
hang(start, end, sag, radius, sides=8, hosts=None, material=0)                # catenary between two anchors
bundle(start, end, count, spread, sag, radius, seed=0, ties=0, hosts=None)    # varied cables, never parallel copies
clips(path, spacing, kind="saddle", hosts=None)                               # fixings seated on the host
```

- With `hosts` given, a path through a solid raises and names the host and the point.
- Both ends must sit at their anchors. The report adds `length_m`, `min_bend_radius_m`, `clearance_m`.

**Done when:** a bundle of 5 between two points has no two cables with the same sag, and a path through a test wall raises.

## Later modules

Outlines only, for now. Each still needs a spec before it is built.

| # | Module | Base features | Native base |
| --- | --- | --- | --- |
| 7 | `bake` | Low and high from one mesh, normal and AO bake, cage, check for bad bake areas. Wait for the SubD comparison | Cycles bake |
| 7b | `fit` | Proposed from the SubD tests, not asked for yet. Takes a cage and a target surface (a dense copy), moves each cage vertex along the normal by its gap under SubD, about 12 passes, and reports normal error before and after. Scale rings by 1 / factor first. Tested only against an exact target | `bmesh`, BVH tree |
| 8 | `repair` | Clean, symmetrise, remesh to a target face count, fix scale and pivot, report how far the shape moved | QuadriFlow, voxel remesh, Decimate |
| 9 | `uv` | Trim or box projection, texel density, pack, report | Smart UV Project, Pack Islands |
| 10 | `instancing` | Find identical meshes, swap them for instances, report the saving | Linked mesh data |
| 11 | `facade` | Bays on a grid, row and floor repeats, controlled variation | Geometry Nodes |
| 12 | `signage` | Panels, raised letters, lightboxes, brackets that seat on the wall | `parts`, `seat` |
| 13 | `scatter` | Scatter by zone and density, keep walk paths clear, always instanced | Geometry Nodes |
| 14 | `collision_lod` | UCX proxies, LOD chain, naming | Convex hull, Decimate |
| 15 | `camera` | Camera from lines in a photo; focal length, rotation and pixel error. Test first (research R6). Done when lines from a known camera return its focal length within 1 % and rotation within 0.5° | `mathutils`, vanishing-point maths written fresh |

Modules 8 and 9 will probably be weaker than paid tools at first: native remeshing and packing don't match dedicated products. Judge them against the checks in `validate_mesh.py` and `uv_check.py`.

## Not on this list

These stay scripts in the repo, and I change them myself:

- **Kit fit test:** a project script (672 lines) to generalise, with no use for a viewport.
- **`validate_mesh.py`:** checks only the root object; false flips on flat decals.
- **`blueprint.py`:** `rectify` can't extend past the given rectangle; `--underlay` stretches.
- **`asset_capture.py`:** fixed close-up direction; glass blocks the view; one comparison box for parts on different planes.
- **Lint, captures, conduit routing:** already scripted.
