---
name: blender-adapter
description: Blender 5.2 specifics for the scene pipeline, covering the MCP tools, session rules, collection structure, naming, save paths, captures from review cameras, validation and stats scripts, the palette script for the lighting passes, and the export to Unreal. The Modeler and the Blender worker load it before any Blender step.
---

# Blender adapter (Blender 5.2)

## Tools

- **Live session: the Blender Lab MCP server**, configured as `blender` in the repo's `.mcp.json` (release v1.0.3, pinned by commit). It needs the MCP add-on running in Blender 5.1 or newer, on port 9876 by default (`BLENDER_MCP_PORT` sets another; on some PCs it is 9877, next to the older community add-on on 9876). Tools: `execute_blender_code`, `get_objects_summary`, `get_object_detail_summary`, `get_blendfile_summary_datablocks`, `get_blendfile_summary_missing_files`, `get_blendfile_summary_of_linked_libraries`, `get_blendfile_summary_path_info`, `get_blendfile_summary_usage_guess`, `get_screenshot_of_area_as_image`, `get_screenshot_of_window_as_image`, `get_screenshot_of_window_as_json`, `jump_to_tab_by_name`, `jump_to_tab_by_space_type`, `jump_to_view3d_object_by_name`, `jump_to_view3d_object_data_by_name`, `render_thumbnail_to_path`, `render_viewport_to_path`, `search_api_docs`, `search_manual_docs`, `get_python_api_docs`. The toolbox scanner records the list it finds in `toolbox/tools/mcp.blender.md`; if the two differ, the scan wins.
- **Look things up before guessing:** `search_api_docs`, `get_python_api_docs` and `search_manual_docs` search the Blender 5.x API and manual bundled with the server. The Modeler and the Asset Tech can use them even though they never touch the live session.
- **Headless runs:** `bash bin/blender-bg <file.blend> --python <script.py> -- <args>` runs Blender in the background on one file, with factory settings. It reads `BLENDER_BIN`, then `BLENDER_PATH`. Use it for per-asset work, validation, exports and the `blender-image-to-3d` scripts.
- Scripts in `scripts/` were tested headless against Blender 5.2's Python module (bpy 5.2.3). Captures were tested with Cycles only; check Workbench and EEVEE captures in your Blender on the first project.

## Session rules

- **One writer per live session.** Only the route's Blender worker drives the open Blender. The Modeler and the Asset Tech work headless on their own asset files with `bin/blender-bg`, so several can run at once. Never open a second Blender window.
- One asset per `.blend` in the work folder, `<work_dir>/assets/<asset_id>/<asset_id>.blend`. `work_dir` is recorded in `log.md` at G0 (default: a `PipelineWork/<slug>` folder next to the Unreal project) and stays out of git, like every `.blend`. The scene file links or appends finished assets from there. Captures and reports for each asset go to `projects/<slug>/assets/<asset_id>/` in the repo.
- Never delete the user's data; hide it. Never change the user's viewport shading or view. Capture through cameras and renders.
- Make scripts idempotent and run each once. Before re-running a builder, check for manual edits (vertex count and hash stored as custom properties on the object) and switch to incremental edits if the user changed it.
- Save after each major step to the project's `.blend` path from `log.md`. The `.blend` lives on the user's work drive, not in git unless LFS rules exist.

## Collections

Adapted from arjun988/blender-skills `scene-assembly` (MIT).

```text
COL_Blockout
COL_Kit            source meshes for kit pieces and props; excluded from the view layer
COL_P0_Site … COL_P9_Life   one per placement phase
COL_Lights
COL_Cameras        CAM_<id> from light/cameras.json
COL_Collision      UCX_ meshes
COL_Ref            references, generated sources; hidden
```

- Repeats are collection instances or linked duplicates (Alt+D) of a `COL_Kit` mesh, never copies.
- Names match Unreal names for anything that goes to Unreal: `SM_`, `UCX_SM_<Name>_01`, `SOCKET_`.
- Custom properties carry the pipeline data: `map_id`, `phase`, `cluster`, `src`, and `material_group` on materials.

## Captures

`scripts/capture.py` renders each review camera to `reviews/<gate>-r<n>/` at the scene's resolution (or a `width` and `height` you pass) without touching the viewport. During the capture it turns compositing off (a user's startup compositor with empty File Output nodes blanks every render), writes 8-bit PNG that follows the scene's colour management (an output override would ignore the locked exposure), and renders Workbench with the Standard view at exposure 0 and white balance off so object colours don't blow out or tint. It restores every setting afterwards; `scripts/check_capture.py` tests this headless. Workbench (colour by object, or `color_type="MATERIAL"` for single assets) for blockout and placement, EEVEE for quick lit checks, and Cycles with denoising for the lighting passes on the CG route. Turntables for single assets come from a temporary camera on a circle.

## Validation and stats

- `scripts/validate_mesh.py`: transforms applied, non-manifold edges, duplicate vertices, n-gons on objects with a Subdivision modifier, inconsistent normals, triangle count against budget, and UVs. Output pasted into the asset spec.
- `scripts/stats.py`: objects by phase and source, unique meshes, evaluated triangles, materials by group, lights by type, counting only what renders (objects or collections off for render, such as cutters and guides, are left out). Written as `stats.json`. Its `flat_dense` lists thin meshes (under 3 cm deep) above 20,000 triangles per square metre: paper, posters and decals that should be planes with alpha.
- `scripts/fit_check.py`: in `camera_match` and `full_cg`, prints each landmark's pixel error at the review camera from the spec's `landmarks.json`, and draws the photo and model points on the photo. Run it before posting a placement or kit step; `scripts/check_fit.py` is its self-check.

## Lighting passes (route `blender`)

- Gray: View Layer › Material Override with one Principled BSDF at base colour 0.216.
- Value and hue: `scripts/palette.py` sets each material's Base Color from its `material_group` in `palette.json` (plus optional roughness, `full_cg` only, and an optional ramp in world Z for a grime gradient, only when the user asks for one: `value_bottom_srgb` in value mode, `hue_bottom_hex` in hue mode) and stores the originals in custom properties, so `restore()` undoes it. Group changes go through `split_group`, `rename_group` and `assign` (whole objects or mesh faces), recorded so `unassign(target)` undoes one and `restore(groups=True)` puts all the original groups back. Move groups by object link; `assign` refuses face slots on a mesh with more than one user, because that changes every instance and the kit source. `solve_hex(hex, value)` scales a picked colour to the group's value by luminance, as a starting point. `scripts/check_palette.py` is its headless self-check.
- Measuring: `scripts/measure.py` holds the one method for every value and hue check (decode, Rec.709 luminance on linear values, region masks, flare ellipses, erosion). Render against photo: decode both from display. Render against render: compare EXRs.
- In `full_cg`, before L1, run `scripts/selftest_light.py` on the project file (headless, never saved). It renders a chart through the locked view transform and checks the measuring tools, the flare mask and the stats; given `palette.json` at L3, it also solves each hex through the view transform (`solved_hex` in `selftest.json`). On the corridor pilot it reproduced the approved H3 palette within 1 level.
- Exposure and view transform are fixed in Color Management at G1 (outside `full_cg`, at the blockout, by eye) and never changed.

## Export to Unreal

- Meshes: FBX per unique asset (or the Send to Unreal add-on if the toolbox lists it). Tested settings (28 Oct 2026, Blender 5.2.3 to UE 5.8.3): selected objects, scale applied on the object, Apply Scalings **All Local**, Apply Unit on, Forward -Z, Up Y, smoothing Face, custom normals kept. A 1 m cube imports as 100 units. Never use "FBX All" or "FBX Units Scale": both import 100 times too small. Y comes in mirrored with no extra rotation, which `import_layout.py` already matches. The exact call is in `toolbox/tools/transfer.blender-unreal.md`; add custom normals, `UCX_` collision and LODs there once the first kit piece is tested.
- Layout (route `blender_unreal`): `scripts/export_layout.py` writes `transfer/layout.json` with one row per placed instance.
