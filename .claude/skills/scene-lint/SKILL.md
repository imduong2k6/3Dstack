---
name: scene-lint
description: Count every countable defect in the Blender scene with one script (missing materials, wrong file, cameras, lights and exposure off their JSON, names and tags, objects at the origin, floating or crossing objects, cable ends, conduit ends, openings, doors, stairs, path clearance, wear geometry, visibility states, missing backups) and write lint.json next to the captures. Use it before every capture set and at every review, so reviewers only judge. The Unreal version is not built yet.
---

# Scene lint

Scripts count, reviewers judge (`house-rules` rule 9). Run it on the gate copy of the file (never a backup) before `capture_set`, and again at the start of every review round. A reviewer reruns it and reads `lint.json`; no per-round probe scripts.

## Classes

| Class | Meaning | Effect |
| --- | --- | --- |
| blocker | A capture would lie or a house rule is broken (faces without material, wrong file, a camera or the exposure off its JSON, a review-only object visible, an object at the origin, wear as geometry) | `capture_set` refuses to render; the gate cannot post |
| major | A defect a player or camera can see (floating or crossing objects, a cable or conduit end in the air, a vent with no opening, a narrow door or passage, a high riser, a missing backup, naming and tags) | Goes into the worker's fix list this round |
| minor | Small or unreadable (a cable sags a lot, an end that could not be read, a duplicate name suffix) | Noted; never blocks a gate |

## Run

```text
bash bin/blender-bg <gate copy> --python .claude/skills/scene-lint/scripts/visible_set.py -- --project projects/<slug>
bash bin/blender-bg <gate copy> --python .claude/skills/scene-lint/scripts/lint_blender.py -- --project projects/<slug> --out projects/<slug>/reviews/<gate>-r<n> --expect-file <gate copy>
```

Exit 0: no blocker. Exit 2: a blocker (`lint.json` is still written). Exit 1: the script failed or a check crashed. About 25 s and 12 s on a 1,400-object, 4-million-triangle scene.

`visible_set.py` writes `plan/visible_set.json`: eyes along `plan/walk.json` (`{"paths": {"main": [[x, y], ...]}}`, copied from `layout.json › path`; start on the lowest floor or give the first point a z) and every camera in `light/cameras.json`, by ray casting, plus a probe of each unseen object so thin cables are not lost. Rerun it when a path, a camera or the layout changes. Geometric checks look only at that set; objects added since count as in it. Data checks (materials, file, cameras, names, origin, visibility, wear, backups) cover the whole file.

## Reading `lint.json`

`summary` has the counts, `blockers`, and three lists that are never a pass: `skipped` (an input file was missing), `no_subjects` (the check found nothing to check, for example no object is named or tagged a cable) and `errors` (a check crashed). Each check has `status`, `checked` (how many things it looked at), `count`, `counts` by class, and `items` (the first 100; `count` is exact). A zero with `checked: 0` means nothing was looked at. It is not a clean result.

| Check (field) | Class | Finds |
| --- | --- | --- |
| `file_path` | blocker | open file is not `--expect-file` |
| `faces_no_material` | blocker | faces on empty or missing slots, rendered meshes |
| `cameras_match` | blocker | position, rotation, lens, shift, sensor, type differ from `light/cameras.json`; missing or unlisted cameras (minor) |
| `lights_match` | major | type, position, power differ from `light/lights.json`; emissive rows name their `object` |
| `exposure_match` | blocker | exposure, view transform, look, display, white balance differ from `light/exposure.json` |
| `names_tags` | major | default or spaced names, `CAM_` and `UCX_SM_<Name>_NN` rules, no `phase` tag (property or `COL_P<n>`), blockout object without `map_id`; duplicate suffix and material without `material_group` are minor |
| `origin_objects` | blocker | a small object or instance sitting at the world origin (the join defect); `origin_ok` clears one |
| `visibility_states` | blocker | review-only object visible in render or viewport; parked object still in the view layer (major); renders but hidden in the viewport (major) |
| `wear_geometry` | blocker | an object or collection named or tagged grime, stain, drip, leak, rust, crack, chip, dent, peel or decal; `wear_ok` clears a repair |
| `step_backup` | major | a step in `plan/steps.json` whose backup is not on disk, or an unreadable ledger |
| `floating` | major | no chain of touching objects (within 2 cm) reaches the ground |
| `interpenetration` | major | two solids cross deeper than 2 cm (depth from the crossing triangles) |
| `cable_ends`, `cable_sag` | major, minor | every cable end classed attached, terminated (enters a surface head-on, or buried) or dead end (a tail along a surface, or in the air); sag over 20 % of span |
| `conduit_open_ends` | major | a conduit or fitting end that meets no conduit, fitting, box, meter, fixture or wall |
| `through_wall_openings` | major | a vent, louvre, fan or AC unit inside a wall slab with no opening cut |
| `door_sizes`, `stair_risers` | major | door width or height under the thresholds; risers over, treads under (uneven risers are minor) |
| `path_clearance` | major | along `walk.json`: no floor, something in the 1.8 m capsule or at knee height, clear width or headroom under the thresholds |

How a check knows what an object is: the custom property `kind` (`cable`, `conduit`, `door`, `stair`, `wall`, `through_wall`, `anchor`) if set, else words in the object's or its collection's name (`Cable_Hook`, `SM_Door_Frame`). Wrong guess? Set `kind`. Other overrides: `origin_ok`, `float_ok`, `overlap_ok`, `ends_ok` (a cable that leaves the frame), `wear_ok`, `clear_width_m`, `stair_id`.

Cable ends come from the mesh structure (end caps, open loops, spline ends, wire ends), never from vertex extremes, and a joint to another cable counts only when that cable is itself anchored. A hooked run whose corners sat on anchors while its real end hung in the air once reported "0 floating" and 13 floated; `selftest_lint.py` plants that case. A mesh whose ends cannot be read (generated or merged fittings; more than 4 ends on a conduit piece) is a minor `unresolved`, never a pass. Keep one cable or conduit piece per object where you can.

## Per-project rules

`plan/lint_rules.yaml` is optional and holds only what differs from the defaults in `lintlib.py › DEFAULT_RULES`:

```yaml
door_min_width_m: 0.8
riser_max_m: 0.18
cable_sag_max_ratio: 0.3
severity:
  names_tags: minor        # change a check's class
disable: [interpenetration]
tokens:
  conduit: [conduit, elbow, pipe]    # name words per kind
overlap_allow:             # token pairs whose objects may cross
  - [clip, pipe]
```

## Unreal

Not built yet. `lint_unreal.py` will iterate the level's actors for the same checks (outliner names and tags, floating and crossing actors, cable and spline ends, parked actors) and run Data Validation on the assets; it needs the editor, so it belongs to the Unreal worker. Until then the Unreal route has no lint gate and the supervisor checks those items by eye.

## Self-tests

```text
bash bin/blender-bg --python-exit-code 1 --python .claude/skills/scene-lint/scripts/selftest_lint.py -- <out_dir>
```

It builds a small scene with one planted defect per check and a clean control beside each, and checks `lint.json`, the visible set and the exit codes.
