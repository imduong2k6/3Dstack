---
name: house-rules
description: The pipeline's standing rules in one place (wear, one writer per live editor, projects stay local, backups and the step ledger, visibility states, detail over cost, lighting before the light passes, exposure, review scope, briefs, generation). Every pipeline agent preloads it; the manager reads it at the start of every session. Skills point here instead of keeping their own copy.
---

# House rules

These apply to every project, route and mode. A skill that needs one of them points here; it doesn't restate it. Per-project rules from the user go in `brief.yaml › standing_rules` (dated, in the user's words), and the manager quotes them into every lane brief and reviewer prompt.

"Enforced by" says what catches a break: `lint` (scene-lint blocks captures), `reviewer` (the supervisor checks it), or `none` (only this text).

1. **Wear is the user's texturing work.** In every mode, never model grime, stains, drips, leaks, rust streaks, cracks, chips, dents or peeling paint: no meshes, overlays, decals or stain bands, even when an Art Director note asks for wear. Write each wear item to `handoff/wear-notes.md` (surface, kind, where, how much) and leave the surface clean. Repairs (a patched panel, a replaced part) are objects and may be built. Damage that changes the silhouette (a missing panel, a broken pane) is modelled only when the user asks. *Enforced by: lint (wear names and tags), reviewer.*

2. **One writer per live editor.** Only the route's worker changes the open Unreal editor or the open Blender. Everyone else works headless on their own files. Joining lanes runs headless on a copy, and the worker reopens the result (`lane-integration`). *Enforced by: none.*

3. **Projects stay local.** Nothing under `projects/` or the work folder is ever committed, pushed or put in a PR. Commit and push only pipeline files: skills, docs, `knowledge/`, `feedback/`, `toolbox/` (`checkpoint`). A lesson from a project reaches `feedback/` only with the user's OK, with private names and places taken out. Paths such as `plan/`, `kit/`, `light/` and `reviews/` are inside `projects/<slug>/`; a command run from the repo root spells out `projects/<slug>/`. The Gate Review Board is private and may show project captures. *Enforced by: `.gitignore` and `checkpoint`.*

4. **Back up every step.** After every step of every phase, the worker saves a copy of the live file (`save_as_mainfile(copy=True)` in Blender) to `<phase folder>/backups/<file>_<phase>_<nn>_<step>.blend`, and records it in `plan/steps.json` with `step_log.py` (`blender-adapter`). Backups are never deleted. *Enforced by: lint (every step in the ledger has its backup on disk).*

5. **Visibility has three states; never delete to hide.** `parked`: excluded from the view layer. `review-only`: hidden in render and viewport, shown only for a review capture. `live`: visible. Objects leave the scene only when the user asks. *Enforced by: lint.*

6. **Detail over cost.** Match the references closely. Never pick a default, a piece count or a method because it is cheaper; budgets come only from the user (`brief.yaml › budgets`, no cap by default). `brief.fidelity: faithful` means hero pieces and variants, not the fewest pieces. *Enforced by: reviewer.*

7. **Light stays neutral until blockout and modelling are done.** Until every asset in P0 to P7 is final, the rig is neutral: sky and key roughly matching the references' direction and time of day, and a light on every model that emits (bulbs, lamps, signs, screens) at a plain, even strength. No light targets, ratios or colour grading are reviewed before the light passes; reviewers only check that nothing is clipped or black and that each capture's mean stays inside the `light/exposure.json › mean_band`, if one is recorded. Detailed lighting is `lighting-passes` (L1 to L3) and starts after that. When `lighting_focus: deferred`, colour, contrast and light stay frozen until the user sends lighting references. *Enforced by: reviewer.*

8. **Exposure is fixed, never auto.** One manual exposure from the blockout on, so captures compare across rounds. It is locked at G2 once lint shows no face without a material, written to `light/exposure.json`, and changed before L1 only with a reason logged in `log.md`. L1 sets the real exposure (`lighting-passes`). *Enforced by: lint (scene exposure matches the file).*

9. **Reviews.** Check only what the walk paths and review cameras see (`visible_set.json`), unless `review_scope: whole_scene` (then lint runs with `--visible none`). Scripts count, reviewers judge: lint runs first. The aspect split and the round rules live in `supervisor`. The user's notes always enter the fix list; reviewers' minors never block a gate on their own. *Enforced by: reviewer.*

10. **Briefs ask for results.** A brief to an agent asks for results, evidence files and the step ledger, nothing else. The record of what was done is `plan/steps.json` plus `log.md`, which `retro` reads. *Enforced by: none.*

11. **Generation and credits.** No credits are spent before the user answers the credit question at G0. Concept images default to Flux.2 with the user's references. Pre-approvals (browser with Tripo signed in, GLB downloads into the work folder, headless Blender) are asked once at G0, not per batch. An AI image never sets a real dimension; scale comes from a sourced `metrics.yaml` row. *Enforced by: none; `check_spec.py` for `dims_source`.*

12. **One log line format.** `log.md` lines read `YYYY-MM-DD HH:MM <who> <what>`, so `retro` can measure time. *Enforced by: none.*

13. **Models and effort** are set per agent in `.claude/agents/*.md`; the table is in `docs/pipeline/agents.md`. *Enforced by: none.*
