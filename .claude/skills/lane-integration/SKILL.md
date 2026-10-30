---
name: lane-integration
description: Split a blockout (or any big placement batch) into parallel lanes and join them back into one gate file without the usual defects (instances at the origin, lanes re-appended wholesale, an old material re-applied, empty material slots). It covers the lane brief, seam owners, the freeze rule, the merge queue and the headless join script. Use it whenever two or more agents build parts of the same scene at once.
---

# Lane integration

On an earlier project six lanes built their parts in 37 minutes and one worker then spent 116 minutes joining them. The defects were all join defects: 37 instances landed at the world origin after an append, three lanes were appended again wholesale, a builder re-applied an old red material, and slot 0 was empty on 10 walls (749 m²), which broke the exposure lock. Parallel lanes only pay when joining is cheap and repeatable. A lane gets a contract (owned IDs, seam owners, a frozen file) and a script rebuilds it from scratch, headless, one lane at a time.

Lanes work headless on their own part file. The live editor still has one writer (`house-rules` rule 2): the join runs on a copy, and the live worker reopens the result.

## Split

- Cut by area or zone, never by trade, so a lane can be built and looked at alone. Shared things (kit masters, the palette, the camera set, exposure) belong to the manager and are frozen before any lane starts. A lane never edits them.
- Each lane owns: one collection (`COL_Lane_<id>`, under `COL_Blockout` or the phase's collection, unless the brief names another), one ID prefix (`<PFX>_`, unique across lanes), and a bounding box. The join refuses a name outside the prefix, and a name with the prefix outside the lane.
- **Seams.** Every place two lanes meet (a shared wall, a stair landing, a cable crossing the border) is a row in the seam table with an **owner**. The owner builds the shared piece; the other lane builds up to it and stops, and names it as a reference only. Unowned seams are how pieces get built twice or not at all.
- Repeated objects (props, fittings) are **instances** of a master in the kit, listed in the lane's `manifest.json`, never pasted copies.

## Lane brief

Write one per lane from `templates/lane-brief.md`. It holds the world frame, metrics (cite `plan/metrics.yaml` by key), the exact material names, naming and tags, the owned ID prefix, the seam rows, the lane's rows from `plan/inventory.yaml` and `plan/services.yaml` (`detail-inventory`), the freeze time, the report format and the `brief.yaml › standing_rules`, quoted word for word. Ask for results and evidence files only (`house-rules` rule 10).

## Freeze

1. The lane builds in `<work_dir>/parts/<lane>/<lane>.blend` and writes `manifest.json` (`templates/manifest.json`).
2. Before the freeze it runs the join on its own scratch copy of the gate file. A red report goes back to the builder, not the manager.
3. At the freeze time it stops and the manager runs `python .claude/skills/lane-integration/scripts/integrate_parts.py freeze --parts <parts> --lanes <ids>` (plain Python, no Blender). That stores the part file's SHA-256 in the manifest. The join refuses a part whose hash differs, so an edit after the freeze is a new freeze and a new place in the queue.

## Merge queue

The manager orders the lanes: structure first, then what hangs on it, then cables and services. One lane at a time:

```
bash bin/blender-bg <gate_copy.blend> --python .claude/skills/lane-integration/scripts/integrate_parts.py -- \
  --parts <parts> --lanes <id> --out <next_copy.blend> --patches <parts>/live_patches.py \
  --backup-dir <phase>/backups --phase <phase> --step join_<id>
```

`--out` becomes the next lane's input. Several lanes in one run (`--lanes a,b,c`) is the same thing in order. The run does, per lane:

1. Check the freeze hash.
2. Remove the lane's collection by name, and every object carrying `lane == <id>`, with the data nothing else uses.
3. Load the collection by name from the part file (`--mode append`, the default, or `link`).
4. Point every material slot at the **gate file's** material of the same name, never by slot index. A part's own stale copy of a material loses; a changed colour is listed under `drift`.
5. Place the instances from the manifest.
6. Assert: names inside the prefix and no foreign use of it, no `.001` names, no empty or missing slot, only allowed materials (the gate's own, plus the manifest's `new_materials`; or its `materials` list when it gives one), every listed instance present, sharing its master's data and at its manifest position, **none at the origin** unless the manifest says `at_origin`.
7. Replay `live_patches.py`, then assert again.
8. Save `--out`, plus a backup copy in `--backup-dir` (`house-rules` rule 4), and write `<out>_join.json`.

Any failed assert prints `FAIL`, exits 1 and saves nothing. The manager sends the failure list to the lane's builder; the queue moves on to the next lane. A passed join goes to the live worker with the report: reopen `--out`, log the step with `step_log.py` (`blender-adapter`), run `scene-lint`, capture.

`append` is the default because the gate's materials, exposure and palette passes need local data. Use `link` only for a rigid lane that never changes material; patches cannot persist on a linked lane and are refused.

## Live-only fixes

Anything the live worker changes in a lane after a join is also added to `parts/live_patches.py` (`templates/live_patches.py`): one `@patch(id, lane=...)` function per fix, finding objects by name and **setting** values, never adding to them. The join replays the file after every rebuild and runs each patch twice; a patch that changes the scene on the second run fails. A fix that belongs in the lane's own file goes to the builder at the next freeze, and its patch is then deleted.

## Don't

- Don't append a lane's objects wholesale into the live file, or place instances by hand there.
- Don't let a lane create materials. A new one is named in the lane brief by the manager, and the manifest declares it under `new_materials`.
- Don't edit a part after its freeze, or a master after the lanes start.
- Don't fix a seam in the lane that doesn't own it.
