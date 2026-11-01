---
id: transfer.blender-unreal
kind: transfer               # not a scanned tool: the tested Blender -> Unreal settings the adapters read
name: Blender to Unreal FBX and layout transfer
version: "Blender 5.2.3 -> UE 5.8.3 (Interchange)"
checked: 2026-11-01
sources:
  - test on the author's PC: bin/blender-bg export, StaticMeshTools.import_file + get_bounds over unreal-mcp, PipelineTools.place_layout
  - 2026-11-01 check transfer of a 7,474-object scene with probe pieces, over a plain HTTP client
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

`editor_toolset.toolsets.static_mesh.StaticMeshTools.import_file` with `folder_path`, `asset_name`, `source_file` (absolute), defaults otherwise (`combine_meshes` true, no materials). The log shows it runs the legacy importer, `FactoryCreateFile: StaticMesh with FbxFactory`, and the asset keeps a `FbxStaticMeshImportData`, even with the `Interchange.FeatureFlags.Import.FBX` cvar on (checked 2026-11-01). The settings it reads back: `normalImportMethod` `FBXNIM_ImportNormals`, `bAutoGenerateCollision` true, `bOneConvexHullPerUCX` true, `bBuildNanite` false, `bGenerateLightmapUVs` true, `bReorderMaterialToFbxOrder` true. Results on 2026-10-27:

- `SM_TestCube` (1 m cube, centred): bounds -50..50 on every axis, **100 x 100 x 100 units**, 12 triangles, 1 LOD.
- `SM_AxisProbe` (1 x 2 x 3 m, corner at the origin, extending +X +Y +Z in Blender): X 0..100, **Y -200..0**, Z 0..300. Axes map straight across with Y mirrored, no extra 90° yaw.
- Nanite comes in off and there's one material slot (`WorldGridMaterial` with no materials imported). Turn Nanite on for opaque static meshes with `StaticMeshTools.set_nanite_enabled` and assign `MI_` instances after import.
- Not tested yet in Unreal: LOD groups.

Tested 2026-11-01 with the same import call (UE 5.8, Blender 5.2.3):

- **Custom normals survive.** LOD0 vertex count before Nanite against Blender's unique (vertex, corner normal, UV) count: 160/160, 494/494, 1952/1948, 24/24 on four pieces with custom normals.
- **`UCX_` works.** A child mesh `UCX_<mesh>_00` exported with the piece becomes one convex element with the UCX's 8 vertices, and adds no visible triangles. `SceneTools.trace_world` hits the render mesh, so it can't prove simple collision; read `<mesh>:BodySetup_0 › aggGeom`, or use `find_actors` with `bounds` and `collision_channels`.
- **No `UCX_` means a generated hull.** `bAutoGenerateCollision` gives each mesh one coarse convex hull (`aggGeom.convexElems`). `import_file` has no argument to turn it off. A long or L-shaped mesh gets one hull over its whole extent, so read it as a stand-in, not as collision.
- **A mesh name containing `UCX` is dropped.** A root mesh named `SM_ProbeUCX` imported with "produced no assets"; renamed `SM_ProbeCol`, the same file imported. Avoid `UCX` in any visible mesh's name. The importer's source is said to treat `UBX`, `USP`, `UCP` and `MCDCX` the same way (not tested).
- **Sockets come through, with a catch.** `SOCKET_top` becomes the mesh socket `top`. Location is right with the Y mirror (Blender 0.5, 1, 3 m gave 50, -100, 300 cm). Rotation and scale carry the FBX conversion: Blender +45 about Z read yaw -45 plus roll -90, and relative scale 100. Correct those before anything attaches to a socket. `Sockets` isn't readable as a mesh property; read the subobject `<mesh>.<mesh>:StaticMeshSocket_0`.
- **Material slots.** Slots take the FBX material names, in FBX order, all on `WorldGridMaterial` until assigned. `StaticMeshTools.set_material` by slot name works. An actor override goes on `<actor>.StaticMeshComponent0` with `ObjectTools.set_properties`, values `{"overrideMaterials": [null or "<object path>", ...]}`, one entry per slot in order.
- **Nanite.** `set_nanite_enabled` works per mesh. After it, `get_triangle_count` and `get_vertex_count` report the fallback mesh (2008 source triangles read 552), so take source counts from Blender.
- **Mirrored actors.** Scale -1 on an actor renders the right way out and the bounds are right; a chiral probe landed mirrored as expected. `matrix_world.decompose()` hands a mirrored object back as all three scales negative with an adjusted rotation, which the mapping below carries unchanged.
- **Names ignore case.** Windows files and Unreal assets are case-insensitive: two meshes `Cable_A` and `cable_a` overwrite one FBX silently. Check names case-insensitively before export.
- **Pace.** 1,088 small FBX files imported with materials and Nanite in about 7 minutes, in batches through `execute_tool_script` capped at about 150,000 triangles or 40 files, saving after each.
- **Count the files after an import.** Assets imported in a test stay in memory until `save_assets` names them, and a saved level that uses them still reports clean. Compare the `.uasset` files in the Content folder with the export list before calling an import done.
- **Fast export.** A scratch scene holding one temporary object per mesh exports about 40 FBX a second, even from a file with 9,000 objects (`use_selection` otherwise walks the whole scene).

## Layout transfer (tested)

`import_layout.py` (`PipelineTools.place_layout`) maps Blender `loc_m` (x, y, z) to UE (x, -y, z) x 100 and the quaternion (w, x, y, z) to (w, -x, y, -z). It matches the mesh import above: the Y mirror is the same, and there's no constant yaw to add.

Two-row test (`/Engine/BasicShapes/Cube`): Blender (1, 2, 0) m became UE (100, -200, 0). Blender (3, -1, 0.5) m, rotated +90° about Z, scale (2, 1, 0.5), became UE (300, 100, 50), yaw -90, scale (2, 1, 0.5). The tags were `phase:P3`, `map:W01`, `src:transfer`, the folder was `Transfer/P3`, and a second run replaced the two actors instead of adding two more.

## Gotchas

- `bin/blender-bg` runs with `--factory-startup`, so these settings must be passed in the script; user presets don't apply.
- Test assets from this check are in SkillTest under `/Game/PipelineTest/Meshes` (`Final/` holds the good pair; `Variants/` holds the failed scale options).
