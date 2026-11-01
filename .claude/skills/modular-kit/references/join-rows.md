# Join rows

`kit_library.py join-rows` joins a finished batch of lane placements into a scene file. `sync` cannot: it swaps a piece's mesh by datablock and never reads where a lane put anything. Run it headless on a **copy** of the live file; the live worker reopens the result (`house-rules` rule 2, `lane-integration`).

## The rows file

The project's own tool reads its lane maps (every lane keeps its own format) and writes one json, so this script never knows a project:

```
{"rows": [{"lane", "gate", "master", "loc": [x,y,z], "rot": [deg x,y,z], "scale": n | [x,y,z], "placed": true,
           "why": "when placed is false", "slots": {"1": "M_Name"} | ["M_A", "M_B"] | "M_Name", "at_origin": false, "object": "name to give it"}],
 "gate_hidden": {"<gate object>": ["<lane>", ...]},
 "gate_not_found": {"<name>": ["<lane>"]},
 "swapped": {"<built asset>": n} | ["<built asset>", ...],
 "host_cuts": [{"object", "faces": {"axis": "y", "at": -1.0, "tol": 0.001, "between": {"x": [0, 2]}}, "only_if": "object_shown", "why"}]}
```

`master` is a piece name in the library. Rows a lane has parked or superseded, or that belong to an option the user has not chosen, are `placed: false` (or left out of the file). `slots` are per-row material overrides, kept as per-object slots so objects keep sharing one mesh.

## Steps

1. Run `build` on a copy of the library (`--scene` the live copy) to add pieces that are not in it yet; `build --refresh --dry-run` first lists what it would add, replace and keep. Plain `build` never replaces a piece. `--refresh` replaces a stale piece (an asset saved after the build, or a piece the dry run flags as "the scene's own mesh and an asset file of that name exists") with a fresh copy of the asset, in place, backup first, and only if the library piece is as the manifest says: edited pieces are kept and listed as `kept_user_edit`. The manifest then holds the refreshed hash, so `sync` reads it as unchanged and swaps nothing into scene meshes; this join places and swaps from the library. `build` never adds a new variant of an asset it already has: a row naming one is skipped as "not in the library" until that piece is added by hand.
2. Dry run: `bash bin/blender-bg <live copy> --python .claude/skills/modular-kit/scripts/kit_library.py -- join-rows --library <lib> --manifest <manifest> --rows <rows.json> --report <dry.json>`. It changes and saves nothing. The report lists every row (add, move, keep or skip with the reason), every gate object (hide or skip with the reason), the gate meshes it would swap, host cuts, warnings (a piece with no UV map, an asset file newer than the library, a slot override that cannot be applied), flags (a `gate_not_found` name that is neither `new:...` nor a row's own id), orphans (objects of an earlier run whose row is gone: left alone) and the object and triangle counts.
3. Real run: the same with `--apply --backup <new path> --save-as <next copy> [--parent <collection>] [--phase <tag>]`. It refuses without `--backup`, checks the result (placed count equals the rows', every row at its transform, none at the origin, no empty slot, no `.001` material, cameras, lights, render and view settings and collection exclusion unchanged) and exits 1 without saving if one fails. `--skip-lanes A,B` leaves lanes out together with the gate objects only they replace; `--skip-no-uv` leaves out pieces that have no UV map; `--no-swap` keeps the gate meshes as they are.
4. Rerun on the result: every row is `keep`, nothing is hidden or swapped.
5. `scene-lint`, then the live worker saves, backs up and logs the step.

## What it does

- Rows are matched to objects by `lane|gate|master|count` (property `kit_row`), so a regenerated rows file moves what changed and adds nothing twice.
- A gate object a row replaces gets `hide_render` and `hide_viewport` on (the review-only state, property `kit_join_hidden`), is never deleted, and stays hidden for as long as one lane that names it is not left out. Hiding it back is flipping the two flags.
- A gate mesh named like a built asset takes the library mesh when the rows file lists the asset under `swapped` (the project knows which assets are new; an older asset must not overwrite a mesh the scene has moved on from) and a shown object uses the mesh; a mesh only hidden objects use is left alone, so a restored gate object looks as it did. Without `swapped` nothing is swapped.
- A host cut removes faces from a gate mesh, so it runs only when its object is shown, on a copy of the mesh; the old mesh stays as `<name>.pre_cut`.
- Library edits count: pieces are joined the way `sync` joins them. An edited piece updates the mesh every placed object shares.

## Limits

- Object and triangle counts read mesh data and leave modifiers out.
- Placed objects named `<master>.<lane>.<nnnn>` are `duplicate suffix` minors in `scene-lint`.
- The library and manifest are only read; the join writes nothing but the backup, the report and `--save-as`.
