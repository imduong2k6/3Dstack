---
name: blender-adapter
description: Blender 5.2 specifics for the scene pipeline, covering the MCP tools, session rules, visibility states, backups and the step ledger, collection structure, naming, captures from review cameras, validation and stats scripts, the palette script for the lighting passes, CG camera and light facts, and the export to Unreal. The Modeler and the Blender worker load it before any Blender step.
---

# Blender adapter (Blender 5.2)

## Tools

- **Live session: the Blender Lab MCP server**, configured as `blender` in the repo's `.mcp.json` (release v1.0.3, pinned by commit). It needs the MCP add-on running in Blender 5.1 or newer, on port 9876 by default (`BLENDER_MCP_PORT` sets another; on some PCs it is 9877, next to the older community add-on on 9876). Tools: `execute_blender_code`, `get_objects_summary`, `get_object_detail_summary`, `get_blendfile_summary_datablocks`, `get_blendfile_summary_missing_files`, `get_blendfile_summary_of_linked_libraries`, `get_blendfile_summary_path_info`, `get_blendfile_summary_usage_guess`, `get_screenshot_of_area_as_image`, `get_screenshot_of_window_as_image`, `get_screenshot_of_window_as_json`, `jump_to_tab_by_name`, `jump_to_tab_by_space_type`, `jump_to_view3d_object_by_name`, `jump_to_view3d_object_data_by_name`, `render_thumbnail_to_path`, `render_viewport_to_path`, `search_api_docs`, `search_manual_docs`, `get_python_api_docs`. The toolbox scanner records the list it finds in `toolbox/tools/mcp.blender.md`; if the two differ, the scan wins.
- **Look things up before guessing:** `search_api_docs`, `get_python_api_docs` and `search_manual_docs` search the Blender 5.x API and manual bundled with the server. The Modeler and the Asset Tech can use them even though they never touch the live session.
- **Headless runs:** `bash bin/blender-bg <file.blend> --python <script.py> -- <args>` runs Blender in the background on one file, with factory settings. It reads `BLENDER_BIN`, then `BLENDER_PATH`. Use it for per-asset work, validation, exports and the `blender-image-to-3d` scripts.
- **Exit codes:** Blender itself exits 0 when a `--python` script raises, so every script in `scripts/` catches its errors and exits non-zero. Check the exit code of every headless run; exit 0 with no output file is a failure.
- Scripts in `scripts/` were tested headless against Blender 5.2's Python module (bpy 5.2.3). Captures were tested with Cycles and Workbench; check EEVEE captures in your Blender on the first project.
- **Scripted bpy work:** read [references/blender-5-api.md](references/blender-5-api.md) first. Its traps are checked on 5.2.3; rerun `scripts/check_api_notes.py` after a Blender update.

## Session rules

- **One writer per live session** (`house-rules` rule 2). Only the route's Blender worker drives the open Blender. The Modeler and the Asset Tech never touch it: they work headless on their own asset files with `bin/blender-bg`, launching their own background Blender per file, so several can run at once. Never open a second Blender window.
- One asset per `.blend` in the work folder, `<work_dir>/assets/<asset_id>/<asset_id>.blend`. `work_dir` is recorded in `log.md` at G0 (default: a `PipelineWork/<slug>` folder next to the Unreal project) and stays out of git, like every `.blend`. The scene file links or appends finished assets from there. Captures and reports for each asset go to `projects/<slug>/assets/<asset_id>/`, which stays local too (`house-rules` rule 3).
- Never delete the user's data; park or hide it (see Visibility). Never change the user's viewport shading or view; capture through cameras and renders. In the live session, model in Solid shading.
- Make scripts idempotent (check before you create) and run each once. Before re-running a builder, check for manual edits (vertex count and hash stored as custom properties on the object) and switch to incremental edits if the user changed it.
- Read the user's own base mesh directly instead of guessing its shape. Check which way an object faces before you mirror it. SubD: work at viewport level 1 and check at level 2.

## Visibility, backups and the step ledger

**Visibility has three states, and nothing is deleted to hide it** (`house-rules` rule 5). "Hidden" alone is not a state: on an earlier project a review-only object stayed visible in the viewport because only its render flag was off.

| State | Meaning | How |
| --- | --- | --- |
| parked | Out of the scene for now | The object sits in a collection excluded from the view layer (`COL_Kit`, or `COL_Parked`) |
| review-only | Not rendered and not in the viewport; shown only for a review capture | `hide_render` and `hide_viewport` both on (`hide_set()` alone is not enough); turned on for the shot and off again after |
| live | Part of the scene | Visible in render and viewport |

Stats count what renders, so parked and review-only objects are left out. Objects leave the scene only when the user asks.

**Back up every step, and write it in the ledger** (`house-rules` rule 4). After each step of each phase the worker:

1. saves the live file to its path in `log.md`;
2. saves a copy with `bpy.ops.wm.save_as_mainfile(copy=True, filepath=...)` to `<phase folder>/backups/<file>_<phase>_<nn>_<step>.blend`; backups are never deleted;
3. runs `scripts/step_log.py log`, which adds an entry to `plan/steps.json`: the backup path, the object count and a hash of the object names, and a hash of the cameras and of the lights. In the live session call `log_step(steps, who=, what=, backup=, phase=, step=)` (it saves the backup if it isn't on disk yet; `backup_path(phase_dir, base, phase, step)` gives the next numbered name). Headless: `... step_log.py -- log --steps projects/<slug>/plan/steps.json --who NAME --what TEXT --backup PATH [--phase P3] [--step cables]`.

At the start of every session, and for every fresh live worker, run `scripts/step_log.py -- diff --steps projects/<slug>/plan/steps.json` (exit 1 on a missing or empty backup). It compares the open file with the last entry. A difference with no logged step behind it (a prop deleted by hand, a moved camera) is the user's change or a lost step: report it to the manager, don't undo it and don't count it as a worker mistake. Lint checks that every logged step has its backup on disk. The `.blend` and its backups live on the user's work drive, never in git.

## Collections

Adapted from arjun988/blender-skills `scene-assembly` (MIT).

```text
COL_Blockout
COL_Kit            source meshes for kit pieces and props; parked (excluded from the view layer)
COL_P0_Site … COL_P9_Life   one per placement phase
COL_Lights
COL_Cameras        CAM_<id> from light/cameras.json
COL_Collision      UCX_ meshes
COL_Parked         anything else that is parked; excluded from the view layer
COL_Ref            references, generated sources; parked
```

- Repeats are collection instances or linked duplicates (Alt+D) of a `COL_Kit` mesh, never copies.
- Names match Unreal names for anything that goes to Unreal: `SM_`, `UCX_SM_<Name>_01`, `SOCKET_`.
- Custom properties carry the pipeline data: `map_id`, `phase`, `cluster`, `src`, and `material_group` on materials.

## Captures

`scripts/capture.py` (`capture_set(out_dir, cameras, project=<project>, repo=<repo>)`) needs a fresh `lint.json` for the open scene, runs `scene-lint` when there is none, and refuses to render on a blocker: it raises `CaptureRefused` (headless exit 2) and writes no image. `override_lint="reason"` renders anyway and appends to `lint_overrides.log` next to the images; copy that line into `log.md`. `lint=False` is for single assets, tests and `review-pairs` only. Otherwise it renders each review camera to `reviews/<gate>-r<n>/` without touching the viewport, and writes `lint.json` next to the images. For every camera it reads the resolution, the lens shift and the sensor fit from that camera's `cameras.json` entry and camera data, so a portrait camera with lens shift keeps its frame; a `width` and `height` you pass override all cameras. During the capture it turns compositing off (a user's startup compositor with empty File Output nodes blanks every render), writes 8-bit PNG that follows the scene's colour management (an output override would ignore the locked exposure), and renders Workbench with the Standard view at exposure 0 and white balance off so object colours don't blow out or tint. It restores every setting afterwards; `scripts/check_capture.py` tests this headless. Workbench (colour by object, or `color_type="MATERIAL"` for single assets) for blockout and placement, EEVEE for quick lit checks, and Cycles with denoising for the lighting passes on the CG route. Use Cycles on the GPU (OptiX, or CUDA if OptiX is unavailable); headless runs use factory settings, so set the compute device in the script. Turntables for single assets come from a temporary camera on a circle. For small details, capture a close-up instead of judging them from a wide shot. A blank frame (flat, all white, all black or mostly zero alpha) raises an error through `scripts/frame_check.py`, with the PNGs left on disk; `frame_check=False` skips it.

**Single assets:** `scripts/asset_capture.py` renders one asset file headless and never saves it. It adds temporary cameras and lights, and writes six axis views, two three-quarters and a 1.8 m mannequin scale shot per mode: `solid`, `matcap` (smears, edge highlights), `culling` (holes, inside-out faces) and `wire` (final mesh edges) by default; `reflect` (stripes: kinks on curved faces, same camera only) and `cycles` when asked. `--close name:x,y,z[:dist]` adds close-ups. With a flat `--photo` (`--photo-kind rectified|ortho`; a perspective photo is refused) and `--photo-box` it writes a side-by-side, a blend and an edge overlay, and measures the width-to-height ratio and each `--feature name:x0,y0,x1,y1` against the part named like it (an object, else a material). `--photo-mask` adds silhouette IoU. It writes `capture_report.json` and exits 1 on any failure. `scripts/check_asset_capture.py` is its self-check.

```
bash bin/blender-bg <asset>.blend --python .claude/skills/blender-adapter/scripts/asset_capture.py -- --object <SM_Name> --out <dir> [--modes solid,matcap,reflect,culling,wire] [--close name:x,y,z] [--photo <rectified img> --photo-kind rectified|ortho --photo-box x0 y0 x1 y1 [--feature name:x0,y0,x1,y1] [--photo-mask <img>]]
```

## Validation and stats

- `scripts/validate_mesh.py`: transforms applied, non-manifold edges, duplicate vertices, n-gons on objects with a Subdivision modifier, inconsistent normals, triangle count against budget, and UVs. Output pasted into the asset spec. With `--spec kit/<asset>.md` (live Blender: `spec=` and `repo=`) it also checks `dims_m` (1 cm, or the `done_when` size tolerance), the `pivot` word and the material slots against `material_group`. Headless: `bash bin/blender-bg <asset>.blend --python .claude/skills/blender-adapter/scripts/validate_mesh.py -- <asset> --spec kit/<asset>.md --out validation.json`. Its `parts` block checks the connected parts: coplanar overlapping faces (z-fighting, which makes `pass` false), and as warnings back-to-back faces, parts inside another closed part and floating fragments. `topology` warns on flow problems and odd Bevel segments. A spec's `form` fails a mirror off by over `tol_mm`. `--stage mesh` skips the UV check before approval. `pass` is also false when most faces have no UV area.
- `scripts/uv_check.py` measures px/m, density spread, flipped and zero-area UV faces, overlap, island gap, coverage and hard edges not on seams. It fails on density more than 10 % from the spec's `texel_density_px_m`, on flipped or zero-area faces and, with the `unique` profile, on overlap. The rest are warnings, because the user textures later. Profile `trim` allows overlap and UVs outside 0-1 and skips coverage and gap; density still counts. `bash bin/blender-bg <asset>.blend --python .claude/skills/blender-adapter/scripts/uv_check.py -- <asset> --spec kit/<asset>.md --tex-size 2048 --profile unique|trim`. `selftest_uv_check.py` tests it.
- `scripts/stats.py`: objects by phase and source, unique meshes, evaluated triangles, materials by group, lights by type, counting only what renders (objects or collections off for render, such as cutters and guides, are left out). It also reports faces without a material (by object and in total) and checks the open file's path against the gate copy it is given, failing when they differ, so stats are never taken from a backup. Written as `stats.json`; `write_stats(path, expect_file=<gate copy>)` then raises `StatsError` on either fault (headless `-- --out stats.json --expect-file <gate copy>`, exit 1). Its `flat_dense` lists thin meshes (under 3 cm deep, over 100 triangles, any size) above 20,000 triangles per square metre: paper, posters and decals that should be planes with alpha.
- `scripts/fit_check.py`: in `camera_match` and `full_cg`, prints each landmark's pixel error at the review camera from the spec's `landmarks.json`, and draws the photo and model points on the photo. Run it before posting a placement or kit step; `scripts/check_fit.py` is its self-check.

## Lighting passes (route `blender`)

- Gray: View Layer › Material Override with one Principled BSDF at base colour 0.216.
- Value and hue: `scripts/palette.py` sets each material's Base Color from its `material_group` in `palette.json` (plus optional roughness, `full_cg` only, and an optional ramp in world Z, only when the user asks for one: `value_bottom_srgb` in value mode, `hue_bottom_hex` in hue mode) and stores the originals in custom properties, so `restore()` undoes it. Group changes go through `split_group`, `rename_group` and `assign` (whole objects or mesh faces), recorded so `unassign(target)` undoes one and `restore(groups=True)` puts all the original groups back. Move groups by object link; `assign` refuses face slots on a mesh with more than one user, because that changes every instance and the kit source. `solve_hex(hex, value)` scales a picked colour to the group's value by luminance, as a starting point. `scripts/check_palette.py` is its headless self-check.
- Measuring: `scripts/measure.py` holds the one method for every value and hue check (decode, region masks, flare ellipses, erosion). `luminance_level` is the one luma metric in the pipeline: Rec.709 on linear values, re-encoded. Scripts, reviewers and the board all quote it; nothing uses Rec.601 luma on encoded values. `grid_stats` splits a capture into a grid and returns each cell's luminance statistics; use it only when the user asks for grid rules (`measure.py -- <png> --grid 3x3`). Render against photo: decode both from display. Render against render: compare EXRs.
- In `full_cg`, before L1, run `scripts/selftest_light.py` on the project file (headless, never saved). It renders a chart through the locked view transform and checks the measuring tools, the flare mask and the stats; given `palette.json` at L3, it also solves each hex through the view transform (`solved_hex` in `selftest.json`). On the corridor pilot it reproduced the approved H3 palette within 1 level.
- Exposure is one manual value from the blockout on, locked at G2 and written to `light/exposure.json` (`house-rules` rule 8); L1 sets the real exposure. The view transform is set once and never changed.

## CG route (route `blender`): cameras and light

Adapted from arjun988/blender-skills `archviz` (MIT), retired here. Lenses and positions come from `light/cameras.json`, approved at G2; these facts help propose them and never justify moving an approved review camera.

- **Interior lenses:** 24 to 35 mm is the usual range; avoid an extreme wide lens unless the reference shows one. Eye height 1.5 to 1.7 m unless the shot is dramatic.
- **Vertical correction:** keep the camera level and correct converging verticals with lens shift (`shift_y`), not by tilting. This matters most on exteriors, where the camera looks up at a facade. With a reference photo, take the lens from its focal length.
- **HDRI:** an HDRI or Sky Texture for exteriors and for light that comes through windows. Practical lamps are emissive meshes or lights placed on the model. Keep white balance accurate to the reference and GI soft; use a single hard key only when the reference shows one.
- Keep glass IOR plausible.

## Export to Unreal

- Meshes: FBX per unique asset (or the Send to Unreal add-on if the toolbox lists it). Tested settings (28 Oct 2026, Blender 5.2.3 to UE 5.8.3): selected objects, scale applied on the object, Apply Scalings **All Local**, Apply Unit on, Forward -Z, Up Y, smoothing Face, custom normals kept. `SOCKET_` empties travel with the mesh: `object_types` is MESH and EMPTY, and the sockets must be selected and not hidden (with MESH alone, or hidden, they are dropped without a word). A 1 m cube imports as 100 units. Never use "FBX All" or "FBX Units Scale": both import 100 times too small. Y comes in mirrored with no extra rotation, which `import_layout.py` already matches. The exact call is in `toolbox/tools/transfer.blender-unreal.md`; add custom normals, `UCX_` collision and LODs there once the first kit piece is tested.
- Layout (route `blender_unreal`): `scripts/export_layout.py` writes `transfer/layout.json` with one row per placed instance. A text object (FONT) is one row named after the object, with the text data name as its asset. The FBX for it is the mesh converted on an export copy; the source file keeps live text.
