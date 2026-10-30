---
name: supervisor
description: Review a pipeline step with scene-lint first and judgement after, one aspect at a time (scale and walkability; construction logic; light and values; names, stats and budgets), and give an explicit pass or a ranked fix list. Use it at the end of every phase, asset and lighting pass.
---

# Supervisor review

Adapted from arjun988/blender-skills `qa-review` (MIT): screenshot-backed, checklist-gated, explicit verdict. Extended with this pipeline's specs, stats and lighting checks.

## Inputs

The worker's capture set (review cameras, a top view, a close-up of what changed; for single objects front, side, back, top and a three-quarter view next to the 1.8 m mannequin), `stats.json`, `lint.json`, `visible_set.json`, the asset specs, `metrics.yaml`, `budget.yaml`, `phases.md`, and for lighting `lighting-brief.md` and `palette.json`. Also `brief.yaml › standing_rules`, the previous round's fix list, and the user's notes on the gate.

## Order of work

1. **Read the worker's `lint.json`** (`reviews/<gate>-r<n>/`). Rerun `scene-lint` only when it is older than the gate copy, and then with `--out` in your own folder, never over the shared file. Scripts count, reviewers judge (`house-rules` rule 9), so don't recount what lint counts. Every lint blocker and major goes into the fix list as lint reports it. In `lint.json`, `summary.skipped`, `no_subjects` and `errors` are never a pass, and a check with `checked: 0` looked at nothing. Cable and conduit items marked `unresolved` (minor) are checked by eye on the cameras listed in `seen_by`.
2. **Then add judgement:** what only a person sees in the captures and the references. Use `stats.json` and `measure.py` for numbers.
3. **No per-round probe scripts.** A count you need and lint lacks is a lint gap: report it to the manager and judge by eye until it is added.
4. **Scope is what the walk paths and review cameras see** (unless `brief.yaml › review_scope` is `whole_scene`) (`visible_set.json`: eye height along the walk paths, looking in any direction including up; on the CG route the cameras only). Report the rest under Later.

## Aspects

The manager gives each supervisor one aspect, all read-only on the same captures. Check only your aspect, across the whole scene, and write `review-<aspect>.md` in the format below; the manager merges them into `review.md`. With no aspect given, check all four. Other files point here for these lists.

**1. Scale and walkability**
- Scale against `metrics.yaml`: doors, ceiling and rail heights, stair risers and treads.
- Clearances on the path: door and passage widths, headroom, nothing in the way. Camera frames match `cameras.json` and the brief.
- Transfer (T): the same cameras in Blender and Unreal match in scale, positions and instance counts, and nothing is missing.

**2. Construction logic**
- Overlaps a player or camera can see, and floating objects. Every piece rests on or hangs from something real (supports, brackets).
- **Paired elements** (`mirror_of` on the map): each pair mirrors within 1 cm across its axis and each piece sits at its recess depth, at every placement review, not only the phase that placed them.
- **Where pipes and cables go:** both ends of every run in `layout.json › runs` at its `from` and `to` object or past the frame edge; every conduit fitting meets straight conduit at both ends; no visible cable stub or end on bare wall; bends smooth; bundles not parallel copies; items through a wall sit in a cut opening; surface items within 2 mm of their wall; services connected to structure.
- Only this phase's content, repeats instanced, nothing in `stats.json › flat_dense`, wall shells simple shapes.
- Wear as geometry, overlay or decal is a blocker: see `house-rules` rule 1.

**3. Light and values**
- **Before the light passes** (neutral rig, `house-rules` rule 7) the check is only this: the mean luminance of each review capture (Rec.709, `measure.py`) is inside the band recorded for the scene (`light/exposure.json › mean_band`; with no band, or on a Workbench capture, report the number and give no verdict), at most 0.5 % of pixels are clipped, and there are no black areas. Region-grid rules (`grid_stats`) apply only when the user asks. With `lighting_focus: deferred`, skip colour, contrast and light.
- After that, by pass:

| Pass | Check |
| --- | --- |
| L1 to L3, fast path (`blockout`, `camera_match`) | No large clipped areas, readable darks, the focal read survives a squint, each group's colour reads as the reference's palette and keeps its value within 5 levels, every material slot in a group and named by it, roughness untouched. Game routes: frame time is the user's measurement at L3 unless `unreal-adapter` lists a tool for it |
| L1 Gray (`full_cg`) | Every base colour 0.216, key to fill within half a stop, no large clipped areas, no leaks, light budget if the user set one |
| L2 Value (`full_cg`) | 8 to 10 lighting groups, non-metals in sRGB 60 to 240 or a floor exception listed in the L0 brief, every material instance in a group, squint test keeps the focal area |
| L3 Hue (`full_cg`) | Each colour within 5 sRGB levels of its value by luminance (`measure.py`, not luma), large surfaces low in saturation, light temperatures match the brief |

**4. Names, stats and budgets**
- Kit and props: size within 1 cm of spec, pivot, grid snap, naming, material groups, UVs and texel density, no face without a material (`stats.json`), counts against the inventory by zone.
- **Budgets:** check only the caps the user gave (`brief.yaml › budgets`); report the rest as numbers without a verdict.

## Severity

Same classes as `scene-lint`.

| Level | Meaning |
| --- | --- |
| Blocker | Wrong scale, broken normals, budget badly exceeded, content from a later phase, missing assets after transfer, wear built as geometry, any lint blocker |
| Major | Silhouette or readability problems, wrong pivot, overlaps a player or camera can see |
| Minor | Naming, small gaps, small shading issues. **Minors never block** |

## Verdict (`reviews/<gate>-r<n>/review-<aspect>.md`)

No blocker or major means PASS, with the minors listed as notes.

```markdown
## Review: P3 r1 · aspect: construction logic
**Result:** PASS | FIX
**Lint:** rerun at 14:20, 0 blockers, 2 majors (ids)
**Budgets:** 412k tris of 600k · 38 lights of 48 · 22 texture sets of 30
**Blockers:** [object id, capture, what's wrong, what would fix it]
**Majors:** ...
**Notes (minors):** ...
**Fix list for the worker:** numbered, one object or action per line
```

Every item carries its file, its number in that file and its location (object id, capture, position in frame), for example `review-construction.md #3 · L_204 · CAM_B.png, left third · cable ends 12 cm short of the box · extend it to the box`. The merge keeps all three, so the worker opens only the file an item names.

## Rounds

- **Round 1 reviews the aspect in full. Round n+1 reviews only the fix list, regressions from those fixes, and new lint blockers.** A finding outside those says why it wasn't visible before (a new camera, a moved object, a lint rule that didn't exist); without a reason it goes to Notes.
- **Two form rounds per phase.** A third round is only for a clear mistake against the reference (a wrong count, a missing piece, a pair that doesn't mirror), or in `camera_match` and `full_cg` for a photo landmark that misses the fit rule (5 px at 600 x 800, from `fit_check.py`). Other form items go to Later, into the texturing brief.
- After `max_rounds` without a pass, stop and tell the manager.

## Rules

- Every visual claim points to a capture. If you can't see it, ask for the capture; don't guess.
- **Check a number before you hand it over.** Before a fix item asks a worker to meet a numeric target (an exposure, a ratio, a level, a count, a clearance), check that it can be met, all targets at once: sweep the saved render or do the arithmetic. If no value meets them all, tell the manager before the item goes out; the target is the fault, not the worker (an earlier project had a grid rule no exposure could meet).
- **The user's notes always enter the fix list**, as they wrote them, numbered with the rest. If you disagree, write the numbers beside the item; don't drop it.
- In `camera_match` and `full_cg`, read the worker's `fit_check.py` table for photo fit instead of re-measuring; re-measure only when a number looks wrong, and say which.
- A fault in a tool (stats, capture, a measuring script) goes in the worker's fix list for the same round, never in the notes: on the corridor pilot a stats fault reported as a note waited 15 h.
- When your finding conflicts with an Art Director note, write the acceptance numbers for both options (for example "within 5 levels, D01 pair above +0.25") so the manager can render both and the user can pick with the numbers.
- A problem that repeats across projects goes to the manager for `feedback/<skill>.md` (promoted with the user's OK, `retro`).
