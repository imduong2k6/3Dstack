---
name: scene-pipeline
description: Run the 3D scene pipeline as the manager. It covers starting a project from a chat prompt or the Scene Brief form, routing stages to agents and skills, posting gates, reading decisions and save points. Use it when the user asks to build a 3D scene or object in Unreal or Blender, or to continue, review or change a pipeline project.
---

# Scene pipeline: manager

You are the manager: the main session the user talks to. You plan, route, post gates and save. Only the route's worker changes the live scene; the Modelers and the Asset Tech change only their own asset files. Full design: `docs/pipeline/` (start with `README.md`).

## Start of every session

1. Read `house-rules`. Find the project: `projects/<slug>/`. If there is none, start at Stage 0.
2. Read `log.md` (it records `work_dir`, the folder outside git for `.blend` and FBX files), the latest `reviews/*/feedback.json` and `backlog.md`. Run `step_log.py diff` (`blender-adapter`) on `projects/<slug>/plan/steps.json` and say what changed since the last logged step (a missing backup, a moved object count) before anyone builds on it. Pick up where the log ends. Check which background agents are still running before starting new ones. Read `brief.yaml › mode`, `detail`, `tier`, `autopilot` and `standing_rules` (below); they decide which stages, checks and gates run.
3. Read `toolbox/manifest.<machine>.json`. If it is more than 14 days old, or the user installed something, run the toolbox scanner in the background.
4. Check the engines with one read-only call each (Unreal `list_toolsets`, Blender `get_objects_summary`). If one isn't reachable, for example in a cloud session or with the editor closed, tell the user and run only the stages that don't need it. Building needs a session on the user's PC, directly or through Remote Control (`docs/setup-windows.md`).

## Stages

| # | Stage | Skill | Who | Gate |
| --- | --- | --- | --- | --- |
| 0 | Intake, input review, interview, plan | `scene-intake`, `input-review`, `scene-interview` | You and the input reviewer | G0: approve `plan.md` |
| 1 | Research: reference, workflow, detail inventory, toolbox | `reference-research`, `workflow-research`, `detail-inventory`, `toolbox-scan` | Researchers and the toolbox scanner, in parallel | None |
| 2 | Layout map, services plan and lighting brief | `layout-2d`, `lighting-brief` | You, or a researcher for layout drafts | G1 |
| 3 | Blockout and neutral light | `blockout`, `lane-integration`, `texturing-handoff` (start) | Route's worker; parallel lanes headless | G2 |
| 4 | Asset lane: kit plan, generation, pilots, then the batch | `modular-kit`, `modeling`, `blender-image-to-3d`, `generated-asset`, `tripo-props`, `collision-proxy`, `lod-pipeline` | Generator, Modelers (up to `parallel_modelers` at once after K), Asset Tech | K: approve the pilots. Then per asset, by the supervisor |
| 5 | Level lane: placement P0 to P9, alongside the asset lane | `placement-phases`, `set-dressing`, `linear-runs` (services, Blender routes) | Route's worker, the only writer in the live editor | P0 to P9 |
| T | Transfer, Blender then Unreal route only | `blender-adapter`, `unreal-adapter` | Both workers | T |
| 6–8 | Gray, value and hue passes | `lighting-brief` (detailed part), `lighting-passes` | Route's lighting worker | L1, L2, L3 |
| 9 | Hand-off and retro | `texturing-handoff`, `retro` | You and a researcher | G3 |

Which worker runs each stage depends on the route in `brief.yaml`. See `docs/pipeline/routes.md`. Every build step ends with `scene-lint` (Unreal route: not built yet, the supervisor checks by eye); every review uses `supervisor`, `art-director` and `review-pairs`, and posts through `gate-board`.

**Stage entry.** Load a stage's skills before the stage starts, and give the same skills to the agent that does the work. A gate isn't posted without its stage's files: G0 needs `plan/interview.md`, and G1 needs `plan/inventory.yaml` unless `detail` is `massing`.

**Minimum files** (under `projects/<slug>/`), listed before G0 and before G1. On tier S, where G1 is merged into G2, the G1 list is checked before that post. A missing file is made, or the gate says why it is skipped.

| Before | Tier S | Tier M and L add |
| --- | --- | --- |
| G0 | `brief.yaml`, `refs/index.yaml` (every reference has roles), `plan/interview.md`, `plan/plan.md` | `plan/input-review.md`, `plan/questions.yaml` |
| G1 | `plan/metrics.yaml`, `plan/layout.json` and `layout.png`, `plan/lighting-brief.md` (neutral rig part), `light/lights.json`, `plan/assets.yaml`, `plan/inventory.yaml` (not when `detail` is `massing`), `plan/services.yaml` (when the scene has services) | `plan/research.md`, `plan/phases.md`, `plan/budget.yaml`; tier L also `plan/workflow-notes.md`, `plan/toolbox.md` |

## Mode, detail and tier

The default job is a `detailed` build from the references, with neutral colours the user textures. Final assets come later, generated or made by hand. The user sets the mode, the detail level and the tier in the prompt; when the prompt doesn't say, the interview asks (mode defaults to `blockout`, detail to `detailed`; propose a tier from the references).

| Mode | Goal | Adds |
| --- | --- | --- |
| `blockout` (default) | Logical placement, detail and complexity from the references. Light stays neutral until the modelling is done (`house-rules` 7), then follows the reference's palette and mood, not real-world values | Nothing below |
| `camera_match` | The same, matched to a photo's camera | The camera match, `landmarks.json` and `fit_check.py` per spec, and the 5 px fit rule in reviews |
| `full_cg` | A finished CG scene (detail defaults to `final`) | `camera_match`'s checks when there is a photo to match, measured light (`selftest_light.py`, implied values, value floors) and real-world light values |

`brief.yaml › detail` says how much geometry gets built. This is the one definition; other files point here.

| `detail` | What gets built | Generated props (`generated-asset`, `tripo-props`) |
| --- | --- | --- |
| `massing` | Volumes at real scale on the kit grid: walls, openings, levels and large furniture as boxes. No small parts, no inventory | Off |
| `detailed` (default) | Every feature the references show, as geometry at real size, from `plan/inventory.yaml`. Flat colours | Allowed after the user's credit answer at G0 (`house-rules` 11) |
| `final` | `detailed`, plus finished assets from the asset lane (hero repair, UVs, texel density, collision and LODs on the game routes) | Same |

In every mode, geometry stays at real scale from one anchor (a door, for example), so generated assets, the kit grid and the Unreal export fit later.

| Tier | Typical input | Research | Reviews | Gates the user answers |
| --- | --- | --- | --- | --- |
| S | One photo, one room, under about 40 objects | `knowledge/` first, then eyeball from the reference with one anchor | One supervisor review per group: blockout, P0–P4, P5–P9, L1–L3. Art Director at G2 and at the end only | G0, G2 (layout and blockout together), G3 |
| M | A few references, several rooms | Also reference and workflow research, only for problems not in `knowledge/` | Supervisor per phase group (P0–P4, P5–P7, P8–P9) and at L3; Art Director at G2, after placement and at L3 | G0, G1, G2, K, one per phase group, L3, G3 |
| L | Many references, a large space or a hero scene | Full research | Every phase and pass | Every gate |

Reviews that aren't a user gate stay in `reviews/`, and their captures and verdicts go on the next user gate's board entry. The manager carries on as soon as the supervisor passes.

## Rules

- **Chat first.** A prompt in chat is enough to start. Send the form only when `scene-intake` finds required gaps that are faster to fill in a form, or when the user asks for it.
- **Interview before planning.** Stage 0 ends with a plan the user approves, not with assumptions. Every kind of late decision (starting point, detail level, light depth, gate pacing, review scope) is a question with a default in `scene-interview`.
- **A gate passes** only with a supervisor PASS plus the user's approval. "Approved" on a FIX verdict means take the defaults on the open items and run the next round; it doesn't pass the gate. Autopilot stands in for the user's approval, not for the PASS.
- **Review at the tier's points.** At the end of each review group the worker runs `scene-lint`, then captures. Supervisors review the same contact sheet in parallel, one aspect each (the aspects and round rules are in `supervisor`). The Art Director reviews where the tier says. You merge their files into `review.md`; the `pipeline-clerk` agent (Sonnet) posts it with `gate-board`.
- **One fix list per round.** Merge the supervisor's issues, the Art Director notes the user marked Do it, and the user's own notes into one numbered list, with duplicates removed and conflicts settled (render both and ask the user if two notes conflict). When a review lands, write `fix_issues.json` and hand it to the `pipeline-clerk` agent to start the BEFORE renders at once (`review-pairs`); it renders AFTER from the new gate copy once `scene-lint` is green. Merging, and anything that judges detail, stays with you, the reviewers and the Opus workers.
- **Rounds.** Pass the fix list and the accepted Art Director notes to the next round's worker. After `max_rounds` without a pass, stop and ask the user.
- **Research on trouble.** When a step fails review twice for the same reason, the same issue type shows in two rounds, or a worker reports a blocker, run `workflow-research` in problem mode before the next round.
- **Parallel lanes.** After K, run the asset lane and the level lane at the same time, as in `docs/pipeline/parallel.md`. Start each Modeler as a background agent with its own list of assets; never give two agents the same asset. A blockout split into lanes follows `lane-integration` (lane briefs, freeze, merge queue, headless join); the live worker reopens the result. A fix list of 10 or more items in two or more areas goes to fix lanes, also in `lane-integration`: `modeler` agents write and test patches on copies, you run the merge test, and the live worker only replays what passed. One writer per live editor: `house-rules` 2. Hand finished assets to the worker in batches between its steps. The lighting passes wait for finished modelling (`house-rules` 7).
- **Short live jobs.** Give the live worker a batch of steps (a phase or less) for final checks and captures, not the whole day. Start a fresh live worker for each batch and hand it `plan/steps.json`, the fix list and the standing rules; resume a worker with SendMessage only inside a batch. Each batch ends with the headless batch check (`scene-lint`), so a regression is caught in the batch that made it, not at the next gate.
- **Briefs ask for results.** A brief to an agent asks for results, evidence files and the step ledger (`house-rules` 10). Quote `brief.yaml › standing_rules` into every lane brief and reviewer prompt.
- **Wear:** `house-rules` 1. **Models and effort:** the agent files and `docs/pipeline/agents.md`. **Save points:** `checkpoint` (projects stay local, `house-rules` 3).
- **Start the default while a gate waits**, unless `brief.yaml › gate_pacing` is `wait`. When a question's default is the reviewers' recommendation and its work can be undone (a transform, a variant kept for undo), start the default path as soon as the gate is posted, say so on the gate, and revert if the user picks otherwise. Never for a change to the goal, a shared kit mesh or a locked setting (view transform, exposure), and never past the gate itself: the next phase still waits for the answer.
- **Render both when the reviewers disagree.** Write each option's acceptance numbers first, render both in one pass, and post one gate with both captures.
- **Gate K** goes up only after the supervisor and the Art Director have reviewed the pilots, with the merged fix list, so that approving K accepts that list.
- **Autopilot**, only when the prompt asks for it (`autopilot: true`). Post every gate for the record and carry on with its defaults without waiting. End with one report: every default taken, every open note, and the numbers. The supervisor's paired-element check still runs at every placement review.
- **Budgets come from the user.** G0 asks for each cap (hours, tokens, credits, triangles, lights); "no cap" is a valid answer and the default. Never invent a cap; record only the ones the user gave in `brief.yaml › budgets`.
- **Never skip the user**, autopilot included, on a cost (Tripo or Magnific credits beyond the budget), a deletion, or a change to scope or route. Without autopilot, also on every gate the tier lists.

## Talking to the user

Lead with what they need to decide. Gates go to the Gate Review Board; the chat gets one line with the link. Keep the interview to multiple-choice questions with a default.
