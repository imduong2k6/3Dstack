# Plan: <title>

Brief: `brief.yaml` · Interview: `plan/interview.md` · Input review: `plan/input-review.md`

## Goal
One or two sentences: what this is, who sees it, and what they should feel.

## Deliverables
- Route: unreal | blender_unreal | blender
- Mode: blockout | camera_match | full_cg, detail: massing | detailed | final, and tier: S | M | L, with the gates the tier gives
- Starting point: from scratch, or the named file and the parts allowed
- Autopilot: on only if the prompt asked for it
- What you get at the end: an Unreal level at the hue pass, stills at 3840 × 2160, a turntable, and so on
- Deadline, if given

## Scope
| In | Out |
| --- | --- |
| Corridor, two rooms seen through open doors | Rooms behind closed doors |

Hero area and focal point:

## References
Readiness per area (from the input review) and the open image requests.

## Assumptions
Each assumption with its default and where it came from. Anything the user overrode in the interview is marked.

## Working rules
The process answers from round 2 (gate pacing, backups, review scope, light depth and timing, concept model, generation pre-approvals) and every entry in `brief.yaml › standing_rules`, each with its date and who said it. The manager quotes this list into every lane brief and reviewer prompt.

## Locked vs open
Locked: what the user has decided and the work will build on (route, detail level, starting point, scope), with the date. Open: what can still change without redoing work, and the default each will take. A change to a locked item is priced before it is made.

## Stages and gates
The stages this route runs, with the gates the user reviews and anything skipped (for example no lighting passes).

## Budgets
Only the caps the user gave at G0 (hours, tokens, credits per service, triangles, lights, texture sets); "no cap" is written as such. Render resolution and shot list for CG.

## Parallel work
Modelers at once (default 3, up to 4), Asset Techs (default 1), generation services in order (default Magnific), and `work_dir`, the folder outside git for `.blend`, FBX and reference photos. See `docs/pipeline/parallel.md`.

## Research topics for Stage 1
Reference topics, and the workflow questions to research (how professionals build this kind of scene on this route).

## Risks
The pre-mortem ("this project went badly; why?", seeded from `feedback/projects.md`): the three to five things most likely to cause rework, and what Stage 0 did about each one.

## Open questions
Anything still not answered, with the default that will be used.
