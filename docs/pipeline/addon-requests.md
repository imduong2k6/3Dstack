# Blender add-on requests

What the user is building so that modelling runs stop rewriting the same helpers. Written on 31 Oct 2026 after reading the installed add-ons' source and running them headless. Integration (a `toolbox/tools/` file, skill pointers) comes after the current kit test.

## Why these

Three builds of one test prop each wrote their own helpers from scratch: 1,104, 857 and 1,016 lines. All three wrote a loft or strip, a box, a revolve, a rounded outline, a spline tube, text to mesh and a screw. A project's 76 scripts (6,022 lines) repeat the same small functions: 26 of them cast rays, and `cast` and `islands` appear 5 times each, `gap` and `bb` 4 times, `floor_at` and `host_sockets` 3 times.

Those helpers also cost review rounds: 17 floating parts, about 36 kit misfits, a bevel helper that bevelled 0 edges without saying so, and a normals helper that bent window normals.

## Use the installed source, by these rules

1. **Call it as installed** when it works headless and does the job.
2. **Copy the pure function** into our add-on when the source is GPL and the useful part is a plain function. Keep its copyright notice.
3. **Never edit a vendor's folder.** An update wipes the edit, and every update becomes a merge.
4. **Native first.** Native Blender beat several add-ons on the tests below.
5. **No licence stated means call only.** Don't copy it.

Our add-on contains GPL code, so it is GPL too (`SPDX:GPL-3.0-or-later`). That costs nothing while it stays private. Keep its source in its own repo, not this one (`CLAUDE.md`: no third-party files here). This repo gets only the `toolbox/tools/` instruction file.

## How installed add-ons load headless

`bin/blender-bg` runs `--factory-startup`, so no add-on is on. This loaded 11 of the 12 that first failed, in a run that doesn't save preferences:

```python
import addon_utils, gpu
gpu.init()            # only for third-party add-ons that build shaders in register()
addon_utils.enable("bl_ext.user_default.hardops", default_set=True, persistent=False)
```

- `default_set=True` matters: several add-ons read their own entry in the preferences during `register()`.
- `EXEC_DEFAULT` often isn't enough. MESHmachine sets `init`, `hypercursor` and `decalmachine` only in `invoke()`. Setting them on the class reaches the real code without changing its files:

```python
cls = bpy.types.Operator.bl_rna_get_subclass_py("MACHIN3_OT_fuse")
cls.init, cls.hypercursor, cls.decalmachine = True, False, False
bpy.ops.machin3.fuse("EXEC_DEFAULT", segments=4)
```

## What the installed add-ons did

Run on Blender 5.2.3, on small cube and ring fixtures. Faces were counted; nothing was judged by eye and nothing ran on a real asset. Licences are what the files state.

| Add-on | Source | Headless result | Verdict |
| --- | --- | --- | --- |
| Extra Mesh Objects | GPL | `round_cube()` returns plain verts and faces. 0.174 x 0.09 x 0.3 m, radius 3 cm: 150 quads, 0 tris | **Copy** as the shell's corners |
| BoltFactory | GPL | Works, but too dense: a 5.6 mm pan head at 16 divisions is 1,594 tris, a hex nut 1,048 | **Copy** head and drive proportions from `createMesh.py`, not the density |
| MESHmachine 0.20.1 | Its licence file covers only the assets; no code licence stated | Works with the class attributes above. Fuse on a chamfer: all new faces quads. Unchamfer, Unbevel and Unfuse changed the mesh as expected. Refuse finished with no change in counts, not understood | **Call**, for repairs |
| Native Grid Fill | Blender | Round cap: 8 to 4, 12 to 9, 16 to 16, 32 to 64 quads | **Use** for caps |
| Native bridge | Blender | 16-point ring to a square split to 16 points: 16 quads. Unsplit, it gives 20 tris | **Use** for ring patches |
| Multi Grid Fill 1.1.1 | No licence stated | Same counts as native Grid Fill on 12, 16 and 32 | Not needed |
| LoopTools 4.7.7 | GPL | Circle and Relax finish. Shape not checked | Call if needed |
| Bool Tool 2.0 | GPL | One difference worked and left 4 n-gons | Use for the Boolean test (research R7) |
| Perspective Plotter 1.2.7 | GPL | `calc_view` returns at once with no screen. `find_orthocenter` is plain maths. Not run | **Copy** the solver for the fSpy test (research R6) |
| Kushiro Tools 1.18 | GPL | Loads with `gpu.init()`. Safe Inset and Soft Bevel give quads. One tool crashed Blender in a batch and wasn't pinned down | Reserve; run it in its own process |
| EdgeFlow 1.1.2 | GPL | Its poll asks for a 3D view | Copy later if loops on curved shells need it |
| Hard Ops 0.9.88 | GPL | 124,000 lines. Of the tools tried, 25 finished and 59 raised, then `st3_array` crashed Blender | **Skip**: most tools that finished only add native modifiers, and the crash ends the whole run |
| BoxCutter 7.20 | GPL | Loads; not run. Built around shapes drawn with the mouse | Skip |
| Cablerator 1.4.9 | GPL | Loads; not run | Skip: `linear-runs` covers it |
| Quad Filler 1.0.2 | No licence stated | Refused a single open loop: it needs two edge chains | Skip |
| Modifier Tools, Smart Fill, Even Loop | Mixed | Don't load: a removed Blender panel, a dot in the folder name, no `register()` | Skip |

UV add-ons (UVPackmaster, Auto Unwrap, Mio3) load but weren't assessed: UVs come after mesh approval.

## Shared requirements

One extension, `pipeline_tools`, with one module per section below. One version and one `enable()` call suit a run where nothing is on by default. Build the modules in order; each is useful alone.

```
pipeline_tools/
  blender_manifest.toml   LICENSE   __init__.py
  core.py                 # Report, PipelineToolError, topology count
  parts.py  shell.py  rounds.py  finish.py  seat.py  vendors.py  camera.py
  tests/selftest.py
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

| Function | Base features | Start from |
| --- | --- | --- |
| `ring_circle(r, n, phase=0)`, `ring_rounded_rect(w, h, r, seg)` | Point rings, same count at the same index so they loft cleanly | New |
| `strip(bm, rings, closed=True, cap_start=None, cap_end=None, material=0)` | Lofts rings of equal count; raises on a mismatch; caps are `"ngon"`, `"grid"` or None | New |
| `lattice(bm, xs, zs, depth_fn, material=0)` | Quad patch from two lists of cuts and a depth function | New |
| `box(bm, min, max, material=0)`, `prism(bm, outline, y0, y1, material=0)` | Closed solids with correct normals | New |
| `round_box(bm, size, radius, arc_div, lin_div=0, material=0)` | All quads, even `arc_div` | `round_cube()` in `extra_mesh_objects/add_mesh_round_cube.py` |
| `revolve(bm, profile, n, center, axis, material=0)` | Profile round an axis; `n` a multiple of 4; closes on the axis without a fan where it can | New |
| `tube(bm, points, radius, sides, step, material=0)` | Catmull-Rom, no twist along the path, a radius per point, sides a multiple of 4 | New |
| `screw(bm, head, drive, dia, head_h, shank, segments=16, material=0)` | `head`: pan, hex, socket. `drive`: cross, slot, hex, none. **At most 300 tris with a cross recess** | Proportions from BoltFactory `create_pan_head`, `create_hex_head`, `create_phillips_bit`, `create_allen_bit` |
| `hex_nut(bm, flats, h, chamfer=True)`, `thread_rings(bm, r, pitch, count, sides)`, `knurl(bm, r, h, count)` | Game density: rings instead of a helix, sector-based so they can use a radial Array | BoltFactory `add_hex_nut` for proportions |
| `flat_text(bm, text, height, at, width=None, font=None, offset=0.00015, merge=0.00012, material=0)` | Font to flat faces, normals facing out, closed outlines, merged enough to pass the 0.1 mm double check | New |
| `wrapped_text(bm, text, height, radius, angle, axis, ...)` | The same, wrapped on a cylinder, for drums and dials | New |

**Done when:** a test prop's helper block can be replaced by these calls and its triangle count doesn't rise.

## 2. `shell`: a rounded housing with openings planned in the loops

This answers the first feedback on the test prop: random cuts and loops that weren't straight. The later blind build fixed that by hand (85.8 % quads, 2.5 % idle vertices against 77.6 % and 15.4 %), and spent about a dozen functions on it. If its wireframe is approved, lift them from `build_shell`, `lattice`, `patch_xz`, `dome`, `shell_xs`, `shell_zs`, `roll_points` and `wall_point` in that run's `src/build_meter.py`. That code is ours, so there is no licence question.

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

From the feedback's suggestion: find circles, model one sector, array it. Native bridge and Grid Fill already make the quads (see the table), so this module is small.

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

No add-on has this. Use `mathutils.bvhtree.BVHTree` on evaluated meshes.

```python
seat(obj, hosts, direction="-Z", gap=0.0, align="none", sample="corners")     # align: none or normal
seat_many(rows)                                                               # batch; one host tree per host, one report per row
gap(a, b, reach=0.1), world_box(obj), islands(obj), first_hit(origin, direction, hosts)
```

- The report adds `gap_before`, `gap_after`, `hit_object`, `hit_normal`, `tilt_deg`.
- **No hit raises** and names the object and direction. Asking for `align="normal"` on a rough surface reports the spread of normals.

**Done when:** a box 5 cm above a tilted plane lands within 0.1 mm at every corner with `align="normal"`, and a box with nothing below raises.

## 6. `vendors`: installed tools without the setup

For the repair route (generated meshes, research R7), not for new builds, where a live Bevel is better.

```python
use("MESHmachine")                                  # enable() as above, class attributes set, version checked
mm_fuse(obj, faces, segments=4, tension=0.7)        # also mm_unbevel, mm_unchamfer, mm_unfuse, mm_change_width
lt_circle(obj, verts), lt_relax(obj, verts)         # LoopTools
bool_difference(target, cutter)                     # Bool Tool
```

- Each wrapper sets the selection and mode itself, and restores them.
- A tested-version list: an unknown version warns, and the self-test reruns the real tools after any update.
- Run risky tools with `isolated=True`, in their own Blender process, since a crash ends the whole process.

**Done when:** each wrapper's result matches the table above, and a wrong selection raises instead of doing nothing.

## 7. `camera`: a camera from lines in a photo

Test first, as research R6 says, and only after 1 to 5. It would replace the hand-worked parallax in a form read and the separate fSpy install.

```python
solve_camera(image_size, lines={"x": [((x0, y0), (x1, y1)), ...], "z": [...], "y": [...]}, reference=None, sensor=36.0)
```

- Lift the maths from Perspective Plotter's `util.py` (`find_orthocenter`, and the solve inside `calc_view`, which needs no screen once it's out of the operator).
- Returns focal length, principal point, rotation and residual in pixels. Raises when a pair of lines is parallel in the image.

**Done when:** lines projected from a known Blender camera return its focal length within 1 % and its rotation within 0.5°.

## Not on this list

These stay scripts in the repo, and I change them myself:

- **Kit fit test:** a project script (672 lines) to generalise, with no use for a viewport.
- **`validate_mesh.py`:** checks only the root object; false flips on flat decals.
- **`blueprint.py`:** `rectify` can't extend past the given rectangle; `--underlay` stretches.
- **`asset_capture.py`:** fixed close-up direction; glass blocks the view; one comparison box for parts on different planes.
- **Lint, captures, conduit routing:** already scripted.

## Not checked

- No fixture was judged by eye, and none is a real asset. The numbers show that tools run and count faces, not that the shapes are good.
- Licence readings are from the files, not legal advice. Check them before publishing anything.
