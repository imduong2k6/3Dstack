---
name: blockout
description: Build the pipeline scene's blockout from the approved layout at real scale on the kit grid, with player or camera checks, the neutral light rig and the review camera set that every later gate reuses. scene-lint must be green before any capture. Use it in Stage 3 on any route.
---

# Blockout and neutral rig

Run by the route's worker (see `docs/pipeline/routes.md`), through its adapter skill.

## Steps

0. **Read the plan.** `plan/inventory.yaml` and `plan/services.yaml` (from `detail-inventory`, when `detail` is not `massing`), `layout.json` and `plan/metrics.yaml`. When the blockout is split into parallel lanes, follow `lane-integration`: each lane brief quotes its rows of the inventory and the services plan, the `metrics.yaml` values it uses and the project's standing rules, and joining runs headless on a copy that the worker reopens (`house-rules` rule 2). Each lane builds `parts/<lane>/<lane>.blend` with `manifest.json`, tags its objects with `lane` and `inv_id`, and keeps its names inside its owned ID prefix (`lane-integration/templates/lane-brief.md`).
1. **Proxies.** One proxy per shape in `layout.json`, kit-sized and on the grid, named with the shape ID (`BLK_W01`; in a lane, inside the lane's ID prefix, `lane-integration`) and put in `COL_Blockout` (Unreal: the `Blockout` outliner folder). Set `map_id` and `phase` on each (Unreal tags `map:W01`, `phase:P1`); `scene-lint` reads the names and tags. Coloured by legend so captures read like the map.
2. **Checks.** Games: a 1.8 m capsule or mannequin walks the path, with door, stair and ceiling clearances; on a walkable scene read `level-design` (core workflow 1 to 3 and 7, readability). CG: look through each hero camera and confirm the frame matches the brief. When `brief.yaml › detail` is not `massing` (mode table in `scene-pipeline`), the `placement-phases` rules for the services blueprint, conduit, cables, wall-mounted items and what a player can see apply from here on.
3. **Neutral rig** from `lights.json` (`house-rules` rule 7): sky and key roughly matching the references' direction and time of day, fog if the references show it, and a light on every model that emits (bulbs, lamps, signs, screens) at its plain relative strength, in `COL_Lights`. No light targets, ratios or colour grading yet. Exposure is one manual value, never auto, following the lifecycle in `house-rules` rule 8 and `docs/pipeline/lighting.md`: set it by eye so nothing is clipped or black, lock it at G2 once lint shows no face without a material, and write it to `light/exposure.json`.
4. **Review cameras.** Create the camera set from `layout.json › cameras`, plus one top view, in `COL_Cameras` as `CAM_<id>` (Unreal: the `Cameras` folder), and save it to `light/cameras.json`. Every later gate reuses these exact cameras. On the Blender routes also write `walk.json` (walkable scenes: the walk paths as eye-height points) and `visible_set.json` (what those points and the cameras see). Unreal route: neither is built; the supervisor judges scope by eye.
5. **Lint, then capture.**
   - **5a, lint.** Run `scene-lint` on the gate copy of the file, not on a backup. It must be green, with no blocker, before any capture: `capture_set` refuses to render on a blocker. Write `plan/walk.json` from `layout.json › path` first, then `bash bin/blender-bg <gate copy> --python .claude/skills/scene-lint/scripts/visible_set.py -- --project projects/<slug>` and `... lint_blender.py -- --project projects/<slug> --out projects/<slug>/reviews/<gate>-r<n> --expect-file <gate copy>`. Exit 2 means blockers: fix and rerun. Rerun `visible_set.py` when a path, a camera or the layout changes. Unreal route: lint is not built yet, so the supervisor checks these by eye.
   - **5b, capture and stats** with the adapter, then hand over to the supervisor and the Art Director.

Change the scale only when the layout or the metrics change; never fix a capture by moving the camera.

## Exit

Before G2 is posted: `lint.json` is green (Unreal route: lint not built, the supervisor checks by eye), `walk.json` and `visible_set.json` exist (Blender routes), the cameras in the scene match `light/cameras.json`, `light/exposure.json` is written, and `handoff/texturing-brief.md` is started (`texturing-handoff`). With lanes, every join's `<out>_join.json` has `"ok": true` and `live_patches.py` has been replayed. Then G2: the user approves scale, composition and light direction.
