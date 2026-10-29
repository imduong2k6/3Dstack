# Build routes

`brief.yaml › route` picks one. You can change the route at G0 or G1; after G2 a change costs a re-blockout.

| Stage | `unreal` (game, default) | `blender_unreal` (game) | `blender` (CG) |
| --- | --- | --- | --- |
| 0 Intake and plan | Manager | Manager | Manager |
| 1 Toolbox scan | Unreal and Blender | Unreal and Blender, plus a transfer test | Blender only |
| 2 Layout | Player metrics, path, hero cameras | Same | Camera first: hero shots and lens, then the layout that serves them |
| 3 Blockout and rough light | Unreal worker | Blender worker. Rough light is judged for direction only, because the final light is in Unreal | Blender worker |
| 4 Asset lane | Modelers headless in Blender, in parallel after K; Asset Tech exports FBX; imported into Unreal by the Unreal worker | Modelers headless in Blender; the Blender worker links the finished assets into the scene | Modelers; SubD or fast CG chosen per shot distance; no Asset Tech (no collision, LODs or FBX) |
| 5 Placement | Unreal worker, with PCG and splines | Blender worker, with geometry nodes and arrays | Blender worker, building only what the cameras see |
| T Transfer | None | Blender worker exports, Unreal worker imports, supervisor checks | None |
| 6–8 Lighting passes | Unreal, Lumen | Unreal, after the transfer | Blender, Cycles |
| 9 Hand-off | Material instances per group | Same | Blender materials per group and a UDIM plan |
| Budgets | Game budgets, Nanite or LODs, collision | Same | Screen coverage per shot, no LODs or collision |

## Transfer (route `blender_unreal`)

1. **Assets:** each unique mesh is exported once as FBX (or through the Send to Unreal add-on, if `toolbox/` lists it) into `/Game/<Slug>/Meshes`.
2. **Layout:** the Blender worker writes `transfer/layout.json` with one row per placed instance: asset id, Blender transform, collection and phase. The Unreal worker spawns actors (or instanced static meshes for repeats) from it, so instancing survives and a re-transfer replaces placements without duplicating them.
3. **Coordinate conversion:** Blender is Z-up, right-handed, in metres; Unreal is Z-up, left-handed, in centimetres. Use the conversion in the adapters (`.claude/skills/unreal-adapter/scripts/import_layout.py`) and verify it on the first project with an asymmetric test object (an arrow pointing +X with a notch on +Y). Record the result in `toolbox/tools/transfer.blender-unreal.md`.
4. **Materials:** rebuilt in Unreal on `M_Env_Master` from `material_group`, not carried over.
5. **Gate T:** the supervisor compares the Blender and Unreal captures from the same cameras: scale, positions, instance counts and missing assets.
6. **USD:** Blender's USD export into Unreal's USD importer is the alternative to test once. If it keeps instancing and transforms cleanly in 5.8, the scanner notes it and step 2 can switch to USD.

## CG specifics (route `blender`)

- Deliverables come from the brief: stills, turntables or shots at the render resolution.
- Review cameras are the hero shots, plus one wider shot per shot for context.
- Lighting passes use View Layer › Material Override for gray, and the palette script for value and hue (see [lighting.md](lighting.md)).
- Exposure: one fixed exposure and view transform per project, set at G1 and locked.
