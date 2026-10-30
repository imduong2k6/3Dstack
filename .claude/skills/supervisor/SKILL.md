---
name: supervisor
description: Review a pipeline step for correctness (scale, overlaps, specs, naming, budgets, value and hue ranges) from the worker's captures and stats, and give an explicit pass or a ranked fix list. Use it at the end of every phase, asset and lighting pass.
---

# Supervisor review

Adapted from arjun988/blender-skills `qa-review` (MIT): screenshot-backed, checklist-gated, explicit verdict. Extended with this pipeline's specs, stats and lighting checks.

## Inputs

The worker's capture set (review cameras, a top view, a close-up of what changed; for single objects front, side, back, top and a three-quarter view next to the 1.8 m mannequin), `stats.json`, the asset specs, `metrics.yaml`, `budget.yaml`, `phases.md`, and for lighting `lighting-brief.md` and `palette.json`.

## Checks

| Step | Check |
| --- | --- |
| Blockout | Scale against metrics, clearances on the path, camera frames match the brief |
| Kit and props | Size within 1 cm of spec, pivot, grid snap, naming, material groups, triangle budget, UVs and texel density |
| Placement | Only this phase's content, no floating or intersecting objects, clearances respected, repeats instanced, services connected to structure. **Paired elements** (`mirror_of` on the map): each pair mirrors within 1 cm across its axis and each piece sits at its recess depth, checked at every placement review, not only the phase that placed them. **Cable runs:** both ends of every run in `layout.json › runs` at its `from` and `to` object or past the frame edge. **Flat props:** nothing in `stats.json › flat_dense`. **Wear:** in every mode, no wear as geometry, overlay or decal (grime, stains, drips, rust streaks, cracks, chips, dents, peeling) unless the user asked for it; wall shells are simple shapes. **Services:** every conduit fitting meets straight conduit at both ends; no visible cable stub or end on bare wall; cable bends smooth; bundles not parallel copies; items through a wall sit in a cut opening, surface items within 2 mm of their wall |
| Transfer (T) | Same cameras in Blender and Unreal match: scale, positions, instance counts, nothing missing |
| L1 to L3, fast path (`blockout`, `camera_match`) | No large clipped areas, readable darks, the focal read survives a squint, each group's colour reads as the reference's palette and keeps its value within 5 levels, every material slot in a group and named by it, roughness untouched. Game routes: frame time at each review camera |
| L1 Gray (`full_cg`) | Every base colour 0.216, key to fill within half a stop, no large clipped areas, no leaks, light budget if the user set one |
| L2 Value (`full_cg`) | 8 to 10 lighting groups, non-metals in sRGB 60 to 240 or a floor exception listed in the L0 brief, every material instance in a group, squint test keeps the focal area |
| L3 Hue (`full_cg`) | Each colour within 5 sRGB levels of its value by luminance (`measure.py`, not luma), large surfaces low in saturation, light temperatures match the brief. Game routes: frame time at each review camera against the brief's frame rate |

## Severity

| Level | Meaning |
| --- | --- |
| Blocker | Wrong scale, broken normals, budget badly exceeded, content from a later phase, missing assets after transfer |
| Major | Silhouette or readability problems, wrong pivot, overlaps a player or camera can see |
| Minor | Naming, small gaps, small shading issues |

## Verdict (`reviews/<gate>-r<n>/review.md`)

When the manager gives you one aspect, check only that aspect, but across the whole scene, and write `review-<aspect>.md` in the format below. The manager merges the aspect files into `review.md`.

```markdown
## Review: P3 r1
**Result:** PASS | FIX
**Budgets:** 412k tris of 600k · 38 lights of 48 · 22 texture sets of 30
**Blockers:** [object id, capture, what's wrong, what would fix it]
**Majors:** ...
**Minors:** ...
**Fix list for the worker:** numbered, one object or action per line
```

## Rules

- Every visual claim points to a capture. If you can't see it, ask for the capture; don't guess.
- **Check what a player can see.** On game routes, fixes cover only objects in the worker's `visible_set.json`: what is visible from eye height along the walk paths, looking in any direction including up, plus the review cameras. Report the rest under Later.
- Re-check after fixes before switching to PASS.
- After `max_rounds` without a pass, stop and tell the manager.
- **Two form rounds per phase.** A third round is only for a clear mistake against the reference (a wrong count, a missing piece, a pair that doesn't mirror), or in `camera_match` and `full_cg` for a photo landmark that misses the fit rule (5 px at 600 x 800, from `fit_check.py`). Other form items go to Later, into the texturing brief.
- In `camera_match` and `full_cg`, read the worker's `fit_check.py` table for photo fit instead of re-measuring; re-measure only when a number looks wrong, and say which.
- **Budgets:** check only the caps the user gave (`brief.yaml › budgets`); report the rest as numbers without a verdict.
- A fault in a tool (stats, capture, a measuring script) goes in the worker's fix list for the same round, never in the notes: on the corridor pilot a stats fault reported as a note waited 15 h.
- When your finding conflicts with an Art Director note, write the acceptance numbers for both options (for example "within 5 levels, D01 pair above +0.25") so the manager can render both and the user can pick with the numbers.
- A problem that repeats across projects goes to `feedback/<skill>.md` with the skill it belongs to.
