# Skill changelog

Every skill change, with the evidence and the user's approval.

## 2026-10-29: revision after the corridor pilot (v6)

Asked by pika on 29 Oct 2026 after reviewing the corridor pilot, with answers to 17 questions at 03:50Z. The pipeline's default job is now a detailed, accurate blockout with flat colours for the user to texture; effort scales with the input.

| # | Change | Skills and files |
| --- | --- | --- |
| 1 | `mode` in the brief: `blockout` (default), `camera_match`, `full_cg`. The five photo-matching edits of the previous entry (landmark fit and `fit_check.py`, the measuring self-test, implied values, value floors, solved hexes) now run only in `camera_match` or `full_cg` | `scene-pipeline`, `modular-kit`, `placement-phases`, `supervisor`, `art-director`, `lighting-brief`, `lighting-passes`, `blender-adapter`, `docs/pipeline/lighting.md`, `brief.schema.json` |
| 2 | `tier` S, M or L, set by the user (asked at G0 if missing): research depth, review groups and the gates the user answers. Tier S answers G0, G2 and G3 only; other reviews are attached to the next gate | `scene-pipeline`, `placement-phases`, `gate-board`, `art-director`, `docs/pipeline/stages.md` |
| 3 | Budgets are asked at G0, never assumed; "no cap" is the default answer | `scene-interview`, `plan-template.md`, `layout-2d`, `supervisor`, `brief.schema.json` |
| 4 | Research in order: `knowledge/`, eyeballed from the reference against one anchor, real data for hidden objects, deep research only without references. New `knowledge/` folder (seven notes from the pilot) and a private folder outside git | `reference-research`, `workflow-research`, `knowledge/` |
| 5 | The layout map is a floor plan: metre grid with axes, key, zones with Z heights, numbered red callouts, scale bar, handwritten notes; plus `mirror_of` pairs and cable `runs` | `layout-2d` and `render_layout.py` |
| 6 | Outside `full_cg`, light follows the reference's palette and mood, set by eye; real-world values only in `full_cg` | `lighting-brief`, `lighting-passes`, `docs/pipeline/lighting.md` |
| 7 | L1 to L3 kept, but colour only in the blockout modes: no roughness changes, fewer checks, one review at L3 on tier S | `lighting-passes`, `supervisor`, `texturing-handoff` |
| 8 | Wear (grime, stains, leaks, rust, cracks, chips) is a texturing note in `handoff/wear-notes.md`, not geometry; wall shells stay simple; paper and posters are planes with alpha; `stats.py` reports `flat_dense` | `placement-phases`, `set-dressing`, `modular-kit`, `texturing-handoff`, `supervisor`, `modeling/references/fast-cg.md`, `blender-adapter` |
| 9 | Cables: every run ends at a real object or past the frame edge; `cables: rig` uses the user's GG cable generator (`toolbox/tools/bl.cable_generator.md`), `guides` leaves curves for the user's tool | `placement-phases`, `geometry-nodes` (pipeline notes), `supervisor`, `layout-2d` |
| 10 | Paired elements mirror and sit in their recesses, checked at every placement review (the left door missed every later gate on the pilot) | `supervisor`, `placement-phases`, `layout-2d` |
| 11 | New `tripo-props` skill from the user's own Tripo workflow: recrop, Studio settings, Send to Blender, `tripo_cleanup.py` (props from the spec, not a table in the script), `qa_views.py`, `props_atlas.py`. Generation runs only in `full_cg` or a detailed blockout | `tripo-props`, `generated-asset`, `modeling`, `brief.schema.json`, `CREDITS.md` |
| 12 | Autopilot when the prompt asks for it: gates posted for the record, defaults taken, stops only for credits, deletions and scope | `scene-intake`, `scene-pipeline` |
| 13 | Subagents stay; Agent Teams to revisit when it leaves experimental | `scene-pipeline`, `docs/pipeline/parallel.md` |

Checked against the research: `studio-workflows.md` lists physically based light for CG lighting; that now applies to `full_cg`, and the blockout modes follow the user's call for mood-first light. It also describes two or three structured review rounds (blockout, first pass, polish), which tier S matches more closely than the old per-phase gates. Nothing else conflicts. Changes apply to every route (answer 13).

Tests: `check_palette.py`, `check_fit.py` unchanged; new `tripo-props/scripts/tests/check_tripo_cleanup.py` passes, and the ported `test_props_atlas.py` passes (57 s) with Blender 5.2.3. `render_layout.py` rendered the corridor's layout as a floor plan. `stats.py` on the pilot's final file lists the dense cards (45,000 to 780,000 triangles per square metre) and the rust decals in `flat_dense`.

## 2026-10-29: retro of corridor-pilot, all ten suggestions

Approved by pika at G3 ("2": now, all ten), 29 Oct 2026 00:50Z. Evidence: `projects/corridor-pilot/handoff/improvements.md` and `retro-numbers.md`. All ten rest on one project's evidence; `feedback/README.md` normally waits for a second project, and the user chose to adopt them now. Check them on the next run.

| # | Change | Skills and files |
| --- | --- | --- |
| 1 | Art Director notes carry size in pixels and cost in minutes; form notes on pieces that meet the 5 px fit rule default to Later unless in the focal order; two form rounds per phase, a third only for a landmark miss | `art-director`, `supervisor`, `placement-phases`, `gate-board` |
| 2 | Specs from the photo crop with labelled landmarks first; `landmarks.json` per spec; new `fit_check.py` prints landmark errors and an overlay, with `check_fit.py` | `modular-kit`, `blender-adapter`, `placement-phases`, `supervisor` |
| 3 | The manager starts a reversible default path while a gate waits, and says so on the gate; never for goal changes, shared kit meshes or locked settings, never past the gate | `scene-pipeline`, `gate-board` |
| 4 | New `measure.py` (one measuring method) and `selftest_light.py` (chart through the locked view transform; checks colour drift by luminance, the flare mask, erosion and stats) run before L1 | `blender-adapter`, `lighting-passes`, `lighting-brief` |
| 5 | Photo-matched scenes measure implied values before any fill-light search; wall-order and shadow checks are L2 checks | `lighting-passes`, `lighting-brief`, `docs/pipeline/lighting.md` |
| 6 | `palette.assign` refuses face slots on a mesh with more than one user; a case added to `check_palette.py` | `blender-adapter` |
| 7 | The L0 brief plans 8 to 10 lighting groups, texturing sub-materials and listed value-floor exceptions | `lighting-brief`, `lighting-passes`, `supervisor`, `docs/pipeline/lighting.md`, `docs/pipeline/agents.md` |
| 8 | Hues start from the implied (light-removed) hue; the 5-level check uses luminance; `palette.solve_hex` as a start and `selftest_light.py` `solved_hex` through the view transform | `art-director`, `lighting-passes`, `supervisor`, `blender-adapter`, `docs/pipeline/lighting.md` |
| 9 | Render both versions when the reviewers disagree, with each option's acceptance numbers | `scene-pipeline`, `supervisor`, `art-director`, `gate-board` |
| 10 | `createdAt` from the system clock; `feedback.json` saved for decisions given in the thread; gate K only after both reviews; tool faults go in the same round's fix list | `gate-board`, `scene-pipeline`, `modular-kit`, `supervisor` |

Also: `docs/pipeline/lighting.md` marks the Naughty Dog three-pass wording as a pipeline convention whose source is still to confirm (the retro researcher couldn't find the slides).

Tests: `check_palette.py`, `check_fit.py` and `selftest_light.py` pass headless with Blender 5.2.3. On the corridor pilot's file, `selftest_light.py` with the approved H3 `palette.json` put all 12 groups within 1 level of their grays (letterbox_paint -0.1, matching the +0.1 measured at L3). Its test red, solved by albedo luminance alone, read +12.5 levels through AgX, which is why `solved_hex` comes from the render.

## 2026-10-30: corridor-pilot evidence moved out of `scene-pipeline`

The skill kept these numbers inside its rules. The rules stay in the skill; the evidence lives here.

- Tier: the corridor pilot was tier S work run at tier L and took 9 h 48 min of active time.
- Start the default while a gate waits: the user took the default 19 times out of 19, and about an hour went to idle waits.
- Render both when the reviewers disagree: 3 to 5 minutes on the pilot, against 25 to 90 for a review round.
- Autopilot: with every gate approved at its default (a test of autopilot), the left door's misplacement got through every later gate, so the supervisor's paired-element check runs at every placement review.
- `gate-board`: typed `createdAt` times on the pilot drifted up to 147 min and broke the retro's wait times, hence the system clock.

## 2026-10-30: skill audit (v7)

Approved by pika on the Skill Audit page, 30 Oct 2026: 49 items, with notes on seven. Evidence: the audit of an earlier project's blockout rounds (repeated defects, lane joins, wear meshes, refused briefs).

| # | Change | Skills and files |
| --- | --- | --- |
| 1 | New `house-rules`: 13 standing rules in one place, each with what enforces it; every agent preloads it and other skills point to it | `house-rules`, all agents, most skills |
| 2 | Projects stay local: nothing under `projects/` is committed or pushed; a project save point is a backup, a `plan/steps.json` entry and a `log.md` line; pipeline commits are `[pipeline] <what>` (user's notes on checkpoint, retro, scene-intake) | `checkpoint`, `retro`, `scene-intake`, `data-and-commits.md`, `.gitignore`, `CLAUDE.md` |
| 3 | Light stays neutral until blockout and modelling are done, with a light on every model that emits; detailed lighting after that (user's notes on lighting-brief and lighting-passes) | `house-rules` 7, `lighting-brief` (two parts), `lighting-passes`, `blockout`, `placement-phases`, `lighting.md` |
| 4 | The interview reads the job back in at most 10 lines before plan.md (user's note) | `scene-interview` |
| 5 | Briefs ask for results and evidence files only; the wording that was refused is gone (user's note on S1) | `house-rules` 10, `lane-integration` |
| 6 | Checks as code: `scene-lint` (19 checks, `lint.json`, capture refuses on a blocker), `step_log.py`, `check_layout.py`, `check_spec.py`, `kit_joint_test.py`, `measure.py --grid`, `stats.py --expect-file`; palette `gray_on()`/`gray_off()` and a skip report | `scene-lint`, `blender-adapter`, `layout-2d`, `modular-kit` |
| 7 | New `lane-integration`, `detail-inventory` and `review-pairs` | those skills, `scene-pipeline`, `blockout`, `gate-board` |
| 8 | Retired `model-picker` and `archviz` (its camera and light facts moved to `blender-adapter`) | `CREDITS.md` |

Checked against the research: making projects local for every project changes the old commit rule (now in `data-and-commits.md`); project text files have no off-machine copy unless the user backs up the work folder. The neutral-light rule widens `lighting.md`'s "placeholder lights only for practicals that drive the composition" to every emitting model. Two read-only reviews (approved items landed; cross-skill consistency) found 28 gaps, all fixed. Not built: the Unreal lint, lookdev and capture fixes (the Unreal MCP was unreachable).

Tests: `selftest_lint.py`, `selftest_adapter.py`, `selftest_validate_mesh.py`, `check_palette.py`, `selftest_check_layout.py`, `check_spec` and `kit_joint_test` self-tests, `selftest_integrate.py`, `selftest_inventory.py`, `selftest_pairs.py`, `check_tripo_cleanup.py` and `selftest_pipeline_patch.py` pass with Blender 5.2.3.

## 2026-10-30: scene-lint reads conduit fittings and vent pockets

Found on an earlier project's G2 r3 lint: 154 conduits reported as unreadable, and 4 vents as solid wall. `conduit_open_ends` read every flat face of a screw, nut or saddle tab as a tube end, missed the caps of fittings shorter than they are wide, and counted boxes and saddles as conduit pieces because their names held "Conduit". `through_wall_openings` always probed from one side, so a vent in a blind pocket read as solid wall. A check with only minors also reported `fail`, so 154 minors read as majors.

| Change | Files |
| --- | --- |
| Strict end reading for conduit: hardware islands ignored, open loops of 6 or more vertices, round caps at any length, up to 16 ends (merged runs) | `lint_blender.py` |
| Boxes, saddles, clips, straps, clamps, brackets, meters and boards are anchors, never conduit subjects; kind exclusions read the object's own name only | `lintlib.py` |
| Vents probed from the face they sit on; a blind pocket of at least `vent_pocket_min_m` (0.05 m) is a minor note | `lint_blender.py`, `lintlib.py` |
| `status: warn` for a check with only minors | `lint_blender.py`, `scene-lint` |

On the same gate copy: unreadable conduits 154 to 18 (generated elbows), the 4 vents become minor notes (pockets 0.17 to 0.20 m deep), and 3 merged runs that were unreadable now show 7 real open ends, 2.5 to 9 cm short of the wall or roof. Majors 199 to 198, minors 200 to 68; nothing else changed. `selftest_lint.py` gains a short coupling with screw heads, saddle and box names, and a vent in a blind pocket.
