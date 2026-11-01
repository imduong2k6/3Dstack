# Blender 5.x API traps for scripted game-asset and scene work

Read this before writing a bpy script that touches mesh data, bmesh, UVs, render output or names. Every row with
`verified` is a claim that `scripts/check_api_notes.py` builds and tests on the running Blender (written on 5.2.3):
`bash bin/blender-bg --python .claude/skills/blender-adapter/scripts/check_api_notes.py` exits 1 when one stops holding,
so rerun it after a Blender update and fix this file. The `id` column is the claim's name in that script.

Already covered, not repeated here: Geometry Nodes inputs, layered actions, `use_nodes`, the EEVEE engine id, vertex group
names, looking nodes up by type, negative CLI values (`../../blender-image-to-3d/references/blender-5-notes.md`, section 1).
Not covered anywhere on purpose: characters, hair, sculpting, animation.

## Removed or renamed

| id | Old code (tutorials, older scripts) | On 5.2 | Status |
| --- | --- | --- | --- |
| removed-edge-props | `edge.bevel_weight`, `edge.crease`, `bm.edges.layers.bevel_weight`, `mesh.use_auto_smooth`, `calc_normals_split()` | all gone: `AttributeError` | verified |
| bevel-weight-attribute | set `edge.bevel_weight = 1` | write the `bevel_weight_edge` FLOAT attribute on the EDGE domain; the Bevel modifier's Weight limit reads it | verified |
| bmesh-float-layer | `bm.edges.layers.bevel_weight.verify()` | `bm.edges.layers.float.new("bevel_weight_edge")`, then `e[layer] = 1.0` | verified |
| sharp-edge-lazy | read `mesh.attributes["sharp_edge"]` | the attribute only exists once an edge is sharp; use `edge.use_edge_sharp`, which creates it | verified |
| sharp-face-inverse | read `polygon.use_smooth` as a stored flag | stored as the `sharp_face` attribute, inverted; `use_smooth` still reads and writes it. `sharp_face` exists on a fresh mesh | verified |
| corner-normals | `mesh.calc_normals_split()`, then `loop.normal` | `mesh.corner_normals` (one per loop, always current) | verified |
| custom-normals-no-autosmooth | enable Auto Smooth before `normals_split_custom_set` | not needed; `normals_split_custom_set(list_per_loop)` sets `has_custom_normals` on its own | verified |
| smooth-by-angle-operator | `mesh.use_auto_smooth` plus `auto_smooth_angle` | `bpy.ops.object.shade_smooth_by_angle(angle=rad)` (works headless on the active object) | verified |
| pack-islands-operator | packing after `mesh.select_all` alone | props are `margin`, `margin_method`, `rotate`, `rotate_method`, `shape_method`, `scale`, `merge_overlap`, `pin`; it packs only the selected UVs of the Edit Mode mesh (unselected ones did not move), so `mesh.select_all` and `uv.select_all` first, and pass `rotate=False` for trim-aligned pieces | verified |
| vertex-colors-alias | `mesh.sculpt_vertex_colors` | gone; `mesh.vertex_colors` still exists, but create colour with `mesh.color_attributes.new(name, 'BYTE_COLOR', 'CORNER')` | verified |
| principled-socket-names | `"Specular"`, `"Emission"`, `"Clearcoat"`, `"Transmission"`, `"Subsurface"` | `"Specular IOR Level"`, `"Emission Color"` (+ `"Emission Strength"`), `"Coat Weight"`, `"Transmission Weight"`, `"Subsurface Weight"` | verified |
| boolean-solver-enum | Boolean `solver = 'FAST'` | `'EXACT'`, `'FLOAT'`, `'MANIFOLD'` | verified |
| obj-fbx-operators | `import_scene.obj`, `export_scene.obj` | `wm.obj_import`, `wm.obj_export`; `import_scene.fbx`, `export_scene.fbx` and `gltf` stay. `hasattr(bpy.ops.x, name)` is always True, so check `dir(bpy.ops.x)` | verified |
| light-shadow-prop | `light.cycles.cast_shadow` | `light.use_shadow` | verified |
| media-type-before-format | `image_settings.file_format = 'PNG'` after a multilayer EXR | rejected until `image_settings.media_type = 'IMAGE'` is set first | verified |
| operator-context-dict | `bpy.ops.object.mode_set(ctx_dict, mode=..)` | `ValueError`; use `with bpy.context.temp_override(object=ob, active_object=ob):` | verified |

## Behaviour that silently gives the wrong result

| id | Trap | Do instead | Status |
| --- | --- | --- | --- |
| bevel-material-slot0 | `bmesh.ops.bevel(..)` without `material=` puts every new face (edge strips and corner patches) in slot 0, whatever the neighbours use (our benchmark: bevelled trim lost its material) | pass `material=<slot>` for a fixed slot, or `material=-1` to copy the adjacent face's slot | verified |
| bevel-material-minus-one | `material=-1` looks like a missing value | it means "take the neighbouring face's slot"; all new faces matched a cube whose faces were all slot 2 | verified |
| rename-while-iterating | `for o in bpy.data.objects: o.name = "z" + o.name` re-sorts the collection while it walks: visits repeat or skip | iterate `bpy.data.objects[:]` whenever the loop renames, links, unlinks or removes | verified |
| name-not-requested | `objects.new("Wall")` when `Wall` exists returns `Wall.001`; `bpy.data.objects["Wall"]` is the older one | keep the returned object, read `.name` if you need it | verified |
| stale-bmesh-after-mode-set | a `bmesh.from_edit_mesh` handle kept across `mode_set(mode='OBJECT')` | `is_valid` turns False and any access raises `ReferenceError`; re-fetch it after each mode change, or build with `bmesh.new()` + `from_mesh()` and `free()` it | verified |
| update-from-editmode | reading `mesh.vertices[i].co` while the object is in Edit Mode | edits made through bmesh are not in the mesh yet: call `obj.update_from_editmode()` first (it changed z by the edit in the test) | verified |
| matrix-world-stale | reading `matrix_world` right after moving a parent or adding a constraint | stale until `bpy.context.view_layer.update()` (child read x = 0.0, then 5.0) | verified |
| name-cap-and-undo | names cap at 255 bytes; undo invalidates every stored reference | store names or indices across steps; no undo in `-b` runs | not verified (cannot undo headless; names not tested) |
| ops-in-loops | `bpy.ops` calls in a loop cost about 7 ms each in a 600-object scene against 0.015 ms for `objects.new` | use the data API for bulk work | not verified here (upstream measurement, 5.2.1) |
