---
id: transfer.blender-unreal
kind: transfer               # not a scanned tool: the tested Blender -> Unreal settings the adapters read
name: Blender to Unreal FBX and layout transfer
version: "Blender 5.2.3 -> UE 5.8.3 (Interchange)"
checked: 2026-10-27
sources:
  - test on the author's PC: bin/blender-bg export, StaticMeshTools.import_file + get_bounds over unreal-mcp, PipelineTools.place_layout
pipeline_stages: [modeling, modular-kit, placement-phases, set-dressing]
routes: [blender_unreal]
---

# Blender to Unreal transfer

**What it does:** the FBX export settings and layout mapping that were tested to land a Blender mesh in Unreal at the right size and orientation.

## FBX export (Blender 5.2, tested)

```python
bpy.ops.export_scene.fbx(
    filepath=path, use_selection=True, object_types={"MESH", "EMPTY"},   # EMPTY carries the SOCKET_ sockets; MESH alone drops them
    apply_scale_options="FBX_SCALE_NONE",   # "All Local", Blender's default
    apply_unit_scale=True,                  # "Apply Unit" on
    axis_forward="-Z", axis_up="Y",         # Blender defaults
    bake_space_transform=False,
    mesh_smooth_type="FACE", use_custom_props=False)
```

Scene units: Metric, Unit Scale 1.0. Apply object scale (`transform_apply(scale=True)`) before export. Select what ships (`use_selection=True`): the piece's root object and `root.children_recursive`, which are its `UCX_` meshes and its `SOCKET_` empties.

**Don't use Apply Scalings "FBX All" or "FBX Units Scale".** Both imported 100 times too small (a 1 m cube came in as 1 cm).

| Apply Scalings | Apply Unit | 1 x 2 x 3 m box in UE (cm) |
| --- | --- | --- |
| FBX All (`FBX_SCALE_ALL`) | on | 1 x 2 x 3 (wrong) |
| FBX All | off | 1 x 2 x 3 (wrong) |
| FBX Units Scale (`FBX_SCALE_UNITS`) | on | 1 x 2 x 3 (wrong) |
| All Local (`FBX_SCALE_NONE`) | on | **100 x 200 x 300** |
| FBX Custom Scale (1.0) | on | 100 x 200 x 300 |

## Sockets (`SOCKET_` empties)

A socket is an empty named `SOCKET_<role>`, parented to the piece's root object like its `UCX_` meshes. It goes through the same export call as the mesh with **`EMPTY` in `object_types`**. The call used to list `{"MESH"}` only, which dropped every socket without a word (checked 2026-10-31).

- **Axes:** the mesh's: forward -Z, up Y, no extra rotation for Unreal. Blender 5.2.3 round trip (export, then import into a blank file; the `blender-adapter` self-test runs the call above): position off by 0.0003 mm, rotation off by 0.0 degrees, name and parent kept. In Unreal the socket should sit at the same spot of the imported mesh with the same Y mirror the mesh gets (see Layout transfer). Not tested in Unreal: the editor was down. Check it on the first piece with a socket, and note whether Interchange makes a mesh socket from a `SOCKET_` null.
- **A hidden socket is lost.** A hidden object (`hide_set(True)` or `hide_viewport`) can't be selected, so it is dropped without a word, for example the sockets of a parked variant. Unhide it in the headless run that exports (the run saves nothing), then select it.
- Display type and size are not exported (they come back as plain axes, size 1). Custom properties are off (`use_custom_props=False`), so what a socket carries is its name and transform.

## Unreal import (UE 5.8.3, tested)

`editor_toolset.toolsets.static_mesh.StaticMeshTools.import_file` with `folder_path`, `asset_name`, `source_file` (absolute), defaults otherwise (Interchange FBX pipeline, `combine_meshes` true, no materials). Results on 2026-10-27:

- `SM_TestCube` (1 m cube, centred): bounds -50..50 on every axis, **100 x 100 x 100 units**, 12 triangles, 1 LOD.
- `SM_AxisProbe` (1 x 2 x 3 m, corner at the origin, extending +X +Y +Z in Blender): X 0..100, **Y -200..0**, Z 0..300. Axes map straight across with Y mirrored, no extra 90° yaw.
- Nanite comes in off and there's one material slot (`WorldGridMaterial` with no materials imported). Turn Nanite on for opaque static meshes with `StaticMeshTools.set_nanite_enabled` and assign `MI_` instances after import.
- Not tested yet in Unreal: custom normals, `UCX_` collision, LOD groups, sockets. Check them on the first real kit piece and add the result here.

## Layout transfer (tested)

`import_layout.py` (`PipelineTools.place_layout`) maps Blender `loc_m` (x, y, z) to UE (x, -y, z) x 100 and the quaternion (w, x, y, z) to (w, -x, y, -z). It matches the mesh import above: the Y mirror is the same, and there's no constant yaw to add.

Two-row test (`/Engine/BasicShapes/Cube`): Blender (1, 2, 0) m became UE (100, -200, 0). Blender (3, -1, 0.5) m, rotated +90° about Z, scale (2, 1, 0.5), became UE (300, 100, 50), yaw -90, scale (2, 1, 0.5). The tags were `phase:P3`, `map:W01`, `src:transfer`, the folder was `Transfer/P3`, and a second run replaced the two actors instead of adding two more.

## Gotchas

- `bin/blender-bg` runs with `--factory-startup`, so these settings must be passed in the script; user presets don't apply.
- Test assets from this check are in SkillTest under `/Game/PipelineTest/Meshes` (`Final/` holds the good pair; `Variants/` holds the failed scale options).
