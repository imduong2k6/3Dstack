---
id: blx.better_fbx
kind: blender_extension
name: Better FBX Importer & Exporter
version: "6.3.4"
checked: 2026-10-27
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/better_fbx/blender_manifest.toml
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/better_fbx/exporter.py (operator better_export.fbx and its properties)
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/better_fbx/importer.py (operator better_import.fbx)
  - toolbox/tools/transfer.blender-unreal.md
  - https://superhivemarket.com/products/better-fbx-importer--exporter
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/config/userpref.blend (saved add-on list, read as text)
pipeline_stages: [transfer, modular-kit, lod-pipeline]
routes: [blender_unreal]
---

# Better FBX Importer & Exporter

**What it does:** A paid third-party Blender FBX importer and exporter built on the native Autodesk FBX SDK (bundled binaries for Windows, Linux, macOS), with game-engine options: Unreal and Unity axis presets, a game-engine transform clean-up, per-object or per-collection export, LOD export, and material-name styles for Unreal. Also reads .dae, .obj, .dxf and .3ds.

## Use it for
- Stage T on `blender_unreal`: an alternative to Blender's built-in FBX exporter for one FBX per unique mesh (`Separate Files`, or `Separate Collection` with `Move To Origin`).
- Meshes with LODs for meshes that cannot use Nanite (`lod-pipeline`): 6.2.0 added mesh LOD export for Unreal and Unity (Superhive notes). Not used in the tested transfer yet.
- Reading .fbx, .dae, .obj, .dxf and .3ds through one importer (`better_import.fbx`); untested here.

## How to call it
- UI: File > Export or Import > "Better FBX" entries (also a drag-and-drop file handler for .fbx/.dae/.obj/.dxf/.3ds), and Collection Exporters on Blender 4.2+.
- Python, from the installed source (not run): `bpy.ops.better_export.fbx(filepath=..., use_selection=True, my_fbx_axis=..., my_fbx_unit=..., my_scale=..., ...)` and `bpy.ops.better_import.fbx(filepath=...)`. The extension must be enabled in that Blender session.
- Not loaded in `bin/blender-bg` (it runs `--factory-startup`); use the live Blender via MCP, or script around it.

## Settings that matter (export, defaults from source)
- `my_fbx_axis`: MayaZUp (default), OpenGL, Unity, Unreal1 (rotates -90 deg about the vertical axis), Unreal2 (+90 deg). `my_fbx_unit`: cm (default). `my_scale`: 1.0. The tested transfer (Blender built-in FBX, All Local scale, no extra yaw, Y mirrored) maps a 1 m cube to 100 cm and assumes no constant yaw; Unreal1/Unreal2 would add one. Run the arrow and 1 x 2 x 3 m box tests with this exporter before using it, and record the result in `transfer.blender-unreal.md`.
- `use_optimize_for_game_engine` (on) with `use_reset_mesh_origin` (on) and `use_reset_mesh_rotation` (on): resets transforms for the game engine. Check that pivots still match the spec (size within 1 cm, pivot, naming).
- `use_selection` (off by default: turn it on), `use_apply_modifiers` (on; meshes with shape keys are skipped), `use_triangulate` (off), `use_tangents` (off), `use_raw_normals_and_raw_tangents` (off; the description says it avoids an Unreal FBX importer tangent bug at the cost of file size).
- `my_material_style` Blender (default) or Unreal Engine; `use_export_materials` on; `use_embed_media`/`use_copy_texture` off. The pipeline rebuilds materials in Unreal from `material_group`, so export without textures.
- `my_edge_smoothing`: FBXSDK (default), Blender (from hard edges) or None.

## Gotchas
- The tested route uses Blender's built-in exporter. Nothing here is verified for this pipeline until the tests above are run.
- No IK bones, custom bone shapes or multiple bind poses (Superhive). Zbrush round trips need ASCII FBX.
- The command-line utility bundled with the add-on is not GPL; the Python add-on is.
- Restart Blender after upgrading to avoid cached old versions (vendor note).
- Local check: `bl_ext.user_default.better_fbx` is enabled (confirmed in the live Blender on 2026-10-28 (Python 3.13.13)).

## Don't use it for
- Anything the built-in exporter already does in the tested way; extra variables cost review time.
- USD transfer (Blender USD export to Unreal's USD importer is a separate test in `routes.md`).

## Version notes
- Installed 6.3.4 (FBX SDK 2020.3.9, more float precision). Superhive lists 6.3.5 (May 2026) as latest, plus a same-week fix for an exporter "Emissive Color" bug; it is unclear if 6.3.4 has that bug. Listed Blender range 3.6 to 5.2. $25 single seat; studio tiers up to $750.
- UE 5.8 adds an experimental uFBX import path and keeps FBX node visibility as "hidden in game"; re-run the box test if Interchange settings change.
