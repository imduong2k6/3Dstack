---
name: scene-pipeline
description: Run the 3D scene pipeline as the manager. It covers starting a project from a chat prompt or the Scene Brief form, routing stages to agents and skills, posting gates, reading decisions and committing. Use it when the user asks to build a 3D scene or object in Unreal or Blender, or to continue, review or change a pipeline project.
---

# Scene pipeline: manager

You are the manager: the main session the user talks to. You plan, route, post gates and commit. Only the route's worker changes the live scene; the Modelers and the Asset Tech change only their own asset files. Full design: `docs/pipeline/` (start with `README.md`).

## Start of every session

1. Find the project: `projects/<slug>/`. If there is none, start at Stage 0.
2. Read `log.md` (it records `work_dir`, the folder outside git for `.blend` and FBX files), the latest `reviews/*/feedback.json`, and `backlog.md`, and pick up where the log ends. Check which background agents are still running before starting new ones. Read `brief.yaml › mode`, `tier` and `autopilot` (below); they decide which stages, checks and gates run.
3. Read `toolbox/manifest.<machine>.json`. If it is more than 14 days old, or the user installed something, run the toolbox scanner in the background.
4. Check the engines with one read-only call each (Unreal `list_toolsets`, Blender `get_objects_summary`). If one isn't reachable, for example in a cloud session or with the editor closed, tell the user and run only the stages that don't need it. Building needs a session on the user's PC, directly or through Remote Control (`docs/setup-windows.md`).

## Stages

| # | Stage | Skill | Who | Gate |
| --- | --- | --- | --- | --- |
| 0 | Intake, input review, interview, plan | `scene-intake`, `input-review`, `scene-interview` | You and the input reviewer | G0: approve `plan.md` |
| 1 | Research: reference, workflow, toolbox | `reference-research`, `workflow-research`, `toolbox-scan` | Researchers and the toolbox scanner, in parallel | None |
| 2 | Layout map and lighting brief | `layout-2d`, `lighting-brief` | You, or a researcher for layout drafts | G1 |
| 3 | Blockout and rough light | `blockout` | Route's worker | G2 |
| 4 | Asset lane: kit plan, generation, pilots, then the batch | `modular-kit`, `modeling`, `blender-image-to-3d`, `generated-asset`, `tripo-props`, `collision-proxy`, `lod-pipeline` | Generator, Modelers (up to `parallel.modelers` at once after K), Asset Tech | K: approve the pilots. Then per asset, by the supervisor |
| 5 | Level lane: placement P0 to P9, alongside the asset lane | `placement-phases`, `set-dressing` | Route's worker, the only writer in the live editor | P0 to P9 |
| T | Transfer, Blender then Unreal route only | `blender-adapter`, `unreal-adapter` | Both workers | T |
| 6–8 | Gray, value and hue passes | `lighting-passes` | Route's lighting worker | L1, L2, L3 |
| 9 | Hand-off and retro | `texturing-handoff`, `retro` | You and a researcher | G3 |

Which worker runs each stage depends on the route in `brief.yaml`. See [routes.md](routes.md).

## Mode and tier

The default job is a detailed, accurate blockout from the references, with neutral colours the user textures. Final assets come later, generated or made by hand. The user sets the mode and the tier in the prompt; when the prompt doesn't say, ask at G0 (mode defaults to `blockout`; propose a tier from the references).

| Mode | Goal | Adds |
| --- | --- | --- |
| `blockout` (default) | Logical placement, detail and complexity from the references. Light and colour follow the reference's palette and mood, not real-world values | Nothing below |
| `camera_match` | The same, matched to a photo's camera | The camera match, `landmarks.json` and `fit_check.py` per spec, and the 5 px fit rule in reviews |
| `full_cg` | A finished CG scene | `camera_match`'s checks when there is a photo to match, measured light (`selftest_light.py`, implied values, value floors, solved hexes), real-world light values, and generated detailed props (`tripo-props`, `generated-asset`) |

In every mode, geometry stays at real scale from one anchor (a door, for example), so generated assets, the kit grid and the Unreal export fit later.

| Tier | Typical input | Research | Reviews | Gates the user answers |
| --- | --- | --- | --- | --- |
| S | One photo, one room, under about 40 objects | `knowledge/` first, then eyeball from the reference with one anchor | One supervisor review per group: blockout, P0–P4, P5–P9, L1–L3. Art Director at G2 and at the end only | G0, G2 (layout and blockout together), G3 |
| M | A few references, several rooms | Also reference and workflow research, only for problems not in `knowledge/` | Supervisor per phase group (P0–P4, P5–P7, P8–P9) and at L3; Art Director at G2, after placement and at L3 | G0, G1, G2, K, one per phase group, L3, G3 |
| L | Many references, a large space or a hero scene | Full research | Every phase and pass | Every gate |

Reviews that aren't a user gate stay in `reviews/`, and their captures and verdicts go on the next user gate's board entry. The manager carries on as soon as the supervisor passes. The corridor pilot was tier S work run at tier L and took 9 h 48 min of active time.

## Rules

- **Chat first.** A prompt in chat is enough to start. Send the form only when `scene-intake` finds required gaps that are faster to fill in a form, or when the user asks for it.
- **Interview before planning.** Stage 0 ends with a plan the user approves, not with assumptions.
- **Review at the tier's points.** At the end of each review group the worker captures; the supervisor (and the Art Director where the tier says) review the same contact sheet; then you post it with `gate-board`.
- **One fix list per round.** Merge the supervisor's issues, the Art Director notes the user marked Do it, and the user's own notes into one numbered list, with duplicates removed and conflicts settled (render both and ask the user if two notes conflict).
- **Rounds.** Resume the same worker with SendMessage, passing the fix list and the Art Director notes the user accepted. After `max_rounds` without a pass, stop and ask the user.
- **Research on trouble.** When a step fails review twice for the same reason, or a worker reports a blocker, run `workflow-research` in problem mode before the next round.
- **Parallel lanes.** After K, run the asset lane and the level lane at the same time, as in `docs/pipeline/parallel.md`. Start each Modeler as a background agent with its own list of assets; never give two agents the same asset. Only the route's worker touches the live Unreal editor or the open Blender; everyone else works headless on their own files. Hand finished assets to the worker in batches between its steps. Start the lighting passes only when every asset in P0 to P7 is final.
- **Models.** Workers and the Modeler always run on Opus. The Asset Tech and the Generator start on Sonnet. Other agents follow `model-picker` when `model_routing` is on.
- **Commit** at every save point with `checkpoint`.
- **Start the default while a gate waits.** When a question's default is the reviewers' recommendation and its work can be undone (a transform, a variant kept for undo), start the default path as soon as the gate is posted, say so on the gate, and revert if the user picks otherwise. Never for a change to the goal, a shared kit mesh or a locked setting (view transform, exposure), and never past the gate itself: the next phase still waits for the answer. On the corridor pilot the user took the default 19 times out of 19, and about an hour went to idle waits.
- **Render both when the reviewers disagree.** Write each option's acceptance numbers first, render both in one pass, and post one gate with both captures. It took 3 to 5 minutes on the corridor pilot, against 25 to 90 for a review round.
- **Gate K** goes up only after the supervisor and the Art Director have reviewed the pilots, with the merged fix list, so that approving K accepts that list.
- **Autopilot**, only when the prompt asks for it (`autopilot: true`). Post every gate for the record and carry on with its defaults without waiting. End with one report: every default taken, every open note, and the numbers. On the corridor pilot (every gate approved at its default, to test this) the left door's misplacement got through every later gate, so the supervisor's paired-element check runs at every placement review.
- **Budgets come from the user.** G0 asks for each cap (hours, tokens, credits, triangles, lights); "no cap" is a valid answer and the default. Never invent a cap; record only the ones the user gave in `brief.yaml › budgets`.
- **Subagents, not Agent Teams.** Every agent is a subagent that reports to you. Agent Teams stays off until the feature leaves experimental; then revisit it for the Modeler batch and for the supervisor and Art Director settling disagreements directly.
- **Never skip the user**, autopilot included, on a cost (Tripo or Magnific credits beyond the budget), a deletion, or a change to scope or route. Without autopilot, also on every gate the tier lists.

## Talking to the user

Lead with what they need to decide. Gates go to the Gate Review Board; the chat gets one line with the link. Keep the interview to multiple-choice questions with a default.
