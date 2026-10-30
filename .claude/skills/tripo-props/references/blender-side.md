# Blender side: import, clean-up, replace, check, atlas

From an earlier project, where 19 props went through these steps. The scripts' docstrings have the exact behaviour.

## What an import looks like
- It arrives in the active collection, rotation 0, scale 1, with its largest side normalised to about 1.0 m. The front was on −Y for every prop but one (a window air conditioner came in with its room side on −Y).
- Its name is the Export File Name if that applied, else Tripo's own title. The root can be an Empty with children rather than a mesh; `cleanup()` skips anything that isn't a mesh.
- Material `tripo_mat_<hash>`: Principled BSDF, a Normal Map and four image nodes, with images `<name>_basecolor|metallic|normal|roughness` packed as JPEG.

## Front check
`qa_views.py`, or the Blender MCP `look` with `target` as a list. When the pictures are ambiguous, count the vertices in the front and back 20 % of the depth: the detail sits on the front (a meter had 59 against 32).

## `cleanup()` arguments
- `props[name] = (dims_m, mount, collide[, opts])`: `dims_m` is the spec's `[W, D, H]` in metres, pasted as one triple. X = W, Y = D, Z = H. Before 30 Oct 2026 the call took `(W, H, D, mount, collide)`, which swapped depth and height; that form now raises.
- Scale is **uniform** by default (one factor from the governing axis). If the axes would need factors more than 8 % apart, `cleanup()` raises before it changes anything; `scale="per_axis"` is the old stretch. In `opts`, `{"kind": "tube", "diameter_m": 0.045}` scales a round part uniformly to its diameter and raises unless it is round within 2 mm. `materials="palette"` (with `{"material_group": "<group>"}` in `opts`) replaces the Tripo materials and images with one flat `M_<group>`: no textures, no atlas.
- `pivot_min[name]`: where the bounding box's min corner goes when the pivot isn't the mount's default, for example an air conditioner set into a wall 0.36 m behind its face.
- `rot_x` / `rot_z`: one-time turns in degrees, applied only before the `tripo_prop` tag exists, so reruns don't turn again. A prop already tagged needs the turn applied by hand once (`me.transform(Rz @ Rx)`) before `cleanup()`.
- `collide=False` when something else covers it, such as a load riding on a cart whose UCX covers both.

## Replacing a master with a regenerated one
Send the new model as `SM_<Name>_v2`, then in one live call: remove the old object and its `UCX_` children, then its mesh, materials and images once their user count is 0 (skip a shared mesh); rename `_v2` to `SM_<Name>` (object and mesh); run `cleanup()`; print any leftover `.0xx` or `_v2` names (expect none). The same name and pivot keep placement scripts working. If the old master was on the atlas, run `build()` again.

## Measuring
- `obj.dimensions` and `bound_box` are stale for objects in an excluded collection and right after a mesh edit: measure `mesh.vertices`, or call `view_layer.update()` first.
- `mesh.materials.clear()` sets every polygon's `material_index` to 0, which matters if you touch slots.

## Workbench renders in Blender 5.2
When the scene's output is a multilayer EXR and a compositor grade is on, Workbench stills come out washed. Save and restore in `try/finally`: `image_settings.media_type = "IMAGE"` before `file_format = "PNG"`, `render.use_compositing = False`; restore `media_type` first. `qa_views.py` avoids this by rendering in its own new scene.

## Atlas
Not used with `materials="palette"`.
- Why: on an earlier project the export cap was 40 materials; 15 Tripo materials took the scene to 52, and the atlas brought it to 38.
- Layout: 4 columns of 1024 px cells (1008 px content resampled with Lanczos 3, 8 px edge extension, so a 16 px gutter), `uv_atlas = uv_tripo * scale + cell offset`, no rotation, so tangent-space normals stay valid. The layout and source paths are in `textures/props_atlas/props_atlas_layout.json`; originals in `textures/tripo_src/<base>/`.
- A new prop: append its base to `BASES` (the order is the cell order; never reorder), keep its own `M_<base>` from `cleanup()`, run `build()`. The sheet grows and old cells keep their pixels.
- `RETOUCH` holds per-prop look fixes applied to cells; `retouch()` applies them again.
