---
name: scene-interview
description: Interview the user at Stage 0 of the scene pipeline with short multiple-choice rounds until nothing important is unclear, including a fixed round on process and starting point, then read the job back, and turn the answers, brief and references into plan.md for approval at gate G0. Use it after the input review and before any research or building.
---

# Stage 0 interview and plan

Run by the manager, because only the main session can ask the user questions (subagents cannot use AskUserQuestion). Load this skill before the interview starts; G0 is not posted without `plan/interview.md`.

## Interview

Use AskUserQuestion with up to four questions per call. Each question has two to four options with the default first; the user can always type their own answer.

| Round | Covers | Source |
| --- | --- | --- |
| 1 Goal | What it is for, the deliverables, the route, the mode and tier if the prompt didn't set them, the budgets, the deadline if the prompt didn't give one | Gaps in `brief.yaml` |
| 2 Process and starting point (fixed) | The questions in the table below, always asked (the last two only when they apply), in up to three calls | The table below |
| 3 Blockers | Every `blocking: true` question from `plan/questions.yaml`. For a walkable scene, also the walk time, footprint, junctions and levels still missing from `brief.yaml › walk` | Input review |
| 4 Look | Hero area and focal point, fidelity (`faithful` or `inspired`), the time of day and weather the references show, must-haves and must-avoids | Brief and questions |
| 5 Follow-ups | Only where an answer opened a new question, or two answers conflict | Earlier rounds |

**Round 2: process and starting point.** Every question has a default, so "all defaults" is one answer. The answers go into `brief.yaml`; a rule the user states goes into `standing_rules` (below).

| Question | Options (default first) | Brief key |
| --- | --- | --- |
| Starting point | From scratch · Reuse a named file, with the parts allowed (kit, layout, props) | `starting_point` |
| Detail level (`scene-pipeline` defines it) | `detailed` · `massing` · `final` | `detail` |
| Light depth | Mood, matched to the references by eye (default; `measured` in `full_cg`) · Direction and time of day only · Measured, one number to hit | `light_depth` |
| Light timing | Neutral light until the modelling is done, then detailed light (`house-rules` 7) · Frozen until you send lighting references · Detailed light earlier, from the stage you name | `lighting_focus` (`deferred` when frozen), or `standing_rules` for an earlier start |
| Gate pacing | Start the default while a gate waits, never past the gate · Wait for each answer before starting anything · Autopilot | `gate_pacing`, `autopilot` |
| Backups | A copy after every step (`house-rules` 4) · Per phase only | `standing_rules` if changed |
| Review scope | What the walk paths and review cameras see (`house-rules` 9) · The whole scene | `review_scope` |
| Concept model (only when image generation is on) | Flux.2 with your references · Another model, named | `concept_model` |
| Generation pre-approvals (only when generation is on) | Approve now: the browser with Tripo signed in, GLB downloads into the work folder, headless Blender · Approve some · Ask me each time | `generation_preapproved` |

Credits are a separate question (below). Nothing is spent, and no concept image is made, before it is answered (`house-rules` 11).

Rules:

- **Budgets: ask, never assume.** One question per kind of cap that applies (hours, tokens, generation credits, triangles, lights), with "No cap" as the default option. Generation credits are always asked when generation is on.
- **Tier:** propose one from the references (one photo and one room is S) as the default option, with what it changes in one line.
- Ask about anything unclear. Don't fill gaps silently; an assumption the user never saw is a later rework.
- Don't ask what the references or brief already answer. Say what you took from them instead ("From corridor_03.jpg: wainscot at 1 m").
- One line of "why it matters" per question, in the question text.
- Image requests go in the same round as the questions they relate to. The user can add images to the chat or a form section.
- Stop when no area is `blocked` and every blocking question has an answer or an accepted default. Usually 3 to 5 rounds.
- **Standing rules.** Anything the user says should hold for the whole project ("never model grime", "wait for me before Stage 4") goes into `brief.yaml › standing_rules` as `{date, rule, from: interview}`, in their words, and into the plan's Working rules. The manager quotes the list into every lane brief and reviewer prompt.
- **No multiple-choice tool** (a client without AskUserQuestion), or a background run: ask the same questions as a numbered list in chat, each with its options and the default marked, and take "ok" as all defaults. With nobody to answer, post the questions on the G0 board entry and wait. Either way, write `plan/interview.md`.

After each round, write the answers into `brief.yaml` with `from: interview`, and append them to `plan/interview.md`.

## Read-back

When the rounds are done, and before writing the plan, send the user a short brief in chat, at most 10 lines: the goal, the scope and size, the starting point, the detail level, the route and mode, the standing rules, and what gets built first. Ask whether that is the job. Write the plan only after a yes; a no or a correction goes back into a follow-up round. The read-back stays in chat; it is not a gate.

## Plan

Write `plan/plan.md` from [plan-template.md](plan-template.md). It is short: one screen per section at most. Before posting, take three minutes for a pre-mortem: "this project went badly; why?". Read `feedback/projects.md` and the `feedback/<skill>.md` files for what went wrong on earlier projects, and write the three to five most likely reasons under Risks, each with what Stage 0 does about it now (a question asked, a standing rule, a check). Then post G0 with `gate-board`, including the plan, the readiness table, the assumptions list and the pre-mortem. The user approves, approves with notes, or requests changes. Nothing in Stage 1 starts before G0 is approved.
