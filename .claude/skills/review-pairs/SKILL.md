---
name: review-pairs
description: Turn a review's fix list (review.md, the Art Director notes and the user's notes) into one camera per issue (fix_cams.json), render BEFORE from the previous backup as soon as the review lands and AFTER from the new gate copy with identical cameras and exposure, and compose captioned side-by-side pairs for the board's before/after section. Use it every round that has a fix list, from the review to the gate post.
---

# Review pairs

The user's rule: every fixed issue gets a before/after close-up pair, so they judge the fix without hunting for it (`gate-board`, before/after). An earlier project built this step by hand twice (20 pairs in about 8 minutes, with the BEFORE frames re-rendered). This is the same step as scripts, so the BEFORE side can start the minute the review lands, while the workers fix.

The manager writes `fix_issues.json` with the merged fix list (step 1). The `pipeline-clerk` agent (Sonnet) runs steps 2 to 7, which are scripts, and reports anything it can't frame or that looks unchanged; it decides nothing about the fixes. Everything runs headless on copies (`bash bin/blender-bg`, `house-rules` rule 2); the open Blender is never touched. Files go in `reviews/<gate>-r<n+1>/`, the round the fixes land in.

## Steps

1. **Issues.** When `review.md`, the Art Director's `ad-notes.md` and the user's notes are in, write `fix_issues.json` (`templates/fix_issues.json`): one row per fix-list item, keeping its ID so the board pair names the same item.
   - `caption`: what was wrong, in one or two sentences, with the object names and numbers from the review. The pair's left side shows it.
   - `targets`: the exact object names (the fix's own objects, including ones it adds), or `boxes` for a place. `engine`: `WORKBENCH` for form, position, scale and construction; `CYCLES` for look, colour and light, which are the Art Director's notes. `fill` (0.5 to 0.9) is how much of the frame the targets fill.
   - A note about a whole view uses `kind: review_cam` with that review camera (it renders at the camera's own frame). A layout change uses `kind: plan`, a top view cut at `cut_z`.
   - `from_camera` picks the side to look from; `loc_m` (and `lens_mm`) pins a camera when the auto placement warns. `show` lists review-only objects to draw for that frame.
   - No pair for wear (`house-rules` rule 1; it goes to `wear-notes.md`), and none for colour, contrast or light while lighting is frozen (`house-rules` rule 7).
2. **Before copy.** Copy the previous round's latest backup to `reviews/<gate>-r<n+1>/before.blend`.
3. **Cameras.** Run `fix_cams.py` on it (add `--after <new gate copy>` once that exists, so objects the fix adds or moves are framed in both files). It writes `fix_cams.json`. A `WARN` (`visible_fraction` under 0.5) means no side shows the targets together: split the issue or set `loc_m`. For a long list, render at `--scale 0.25` and run `compose_pairs.py contact` for one framing look before the full render.
4. **BEFORE.** `render_pairs.py --side before` on `before.blend`, as soon as the cameras exist. It writes `pairs/before/<id>.png` and `_meta.json` (exposure and view transform).
5. **AFTER.** When the new gate copy is saved and `scene-lint` is green: `render_pairs.py --side after --match pairs/before/_meta.json` on it. `--match` gives the after render the before side's exposure and view transform (both sides also use the same samples and seed), so a pair compares the scene and not the grading (`house-rules` rule 8 locks exposure; if the new file's own differs, the pair says so). The cameras are identical because both sides read `fix_cams.json` and nothing else.
6. **Compose.** `compose_pairs.py pairs --cams fix_cams.json --dir pairs --before-label "<round>" --after-label "<round>"` writes `pairs/<id>_pair.png` (before left, after right, caption and a note line below) and `pairs/pairs.json`.
7. **Board.** `gate-board` uploads the pair images and adds them to the gate entry's captures as "Before/after <id>" in fix-list order. A pair that looks unchanged, or whose note says the objects are outside the frame, goes into "Please check" instead of being hidden.

Commands (repo root; `<R>` is `projects/<slug>/reviews/<gate>-r<n+1>`):

```
bash bin/blender-bg <R>/before.blend --python .claude/skills/review-pairs/scripts/fix_cams.py -- --issues <R>/fix_issues.json --out <R>/fix_cams.json [--cameras projects/<slug>/light/cameras.json] [--after <R>/gate.blend]
bash bin/blender-bg <R>/before.blend --python .claude/skills/review-pairs/scripts/render_pairs.py -- --cams <R>/fix_cams.json --out <R>/pairs/before --side before
bash bin/blender-bg <R>/gate.blend   --python .claude/skills/review-pairs/scripts/render_pairs.py -- --cams <R>/fix_cams.json --out <R>/pairs/after --side after --match <R>/pairs/before/_meta.json
bash bin/blender-bg --python .claude/skills/review-pairs/scripts/compose_pairs.py -- pairs --cams <R>/fix_cams.json --dir <R>/pairs --before-label r2 --after-label r3
```

## Notes

- Cycles frames use 64 samples (`--spp`) and the GPU when there is one, for this run only; Workbench frames render in material colour.
- A camera that itself changed in the fix (a new lens or clip) gets `before: {lens_mm, rot_deg, clip_m, note}` on its issue, and the before side renders with it. A `review_cam` keeps the review camera's clip, and an orthographic one (`type: ortho` in `cameras.json`) its `ortho_scale`. It reads the camera from `cameras.json` on every run, so a fix that changes a review camera updates `cameras.json` together with the scene (`scene-lint` `cameras_match` checks both); rerun `fix_cams.py` after that and before the AFTER side. An issue's own `res_px` overrides the camera's.
- Scripts: `fix_cams.py` (cameras), `render_pairs.py` (one side), `compose_pairs.py` (pairs and framing sheet; Pillow is not in Blender's Python, so it uses `imbuf` and `blf`), `selftest_pairs.py` (synthetic scene, end to end).
