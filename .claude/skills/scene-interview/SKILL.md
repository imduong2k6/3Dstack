---
name: scene-interview
description: Interview the user at Stage 0 of the scene pipeline with short multiple-choice rounds until nothing important is unclear, then turn the answers, brief and references into plan.md for approval at gate G0. Use it after the input review and before any research or building.
---

# Stage 0 interview and plan

Run by the manager, because only the main session can ask the user questions (subagents cannot use AskUserQuestion).

## Interview

Use AskUserQuestion with up to four questions per call. Each question has two to four options with the default first; the user can always type their own answer.

| Round | Covers | Source |
| --- | --- | --- |
| 1 Goal | What it is for, the deliverables, the route, the mode and tier if the prompt didn't set them, the budgets, the deadline if the prompt didn't give one | Gaps in `brief.yaml` |
| 2 Blockers | Every `blocking: true` question from `plan/questions.yaml` | Input review |
| 3 Look | Hero area and focal point, fidelity, lighting (time, weather, key light), must-haves and must-avoids | Brief and questions |
| 4 Follow-ups | Only where an answer opened a new question, or two answers conflict | Earlier rounds |

Rules:

- **Budgets: ask, never assume.** One question per kind of cap that applies (hours, tokens, generation credits, triangles, lights), with "No cap" as the default option. Generation credits are always asked when generation is on.
- **Tier:** propose one from the references (one photo and one room is S) as the default option, with what it changes in one line.
- Ask about anything unclear. Don't fill gaps silently; an assumption the user never saw is a later rework.
- Don't ask what the references or brief already answer. Say what you took from them instead ("From corridor_03.jpg: wainscot at 1 m").
- One line of "why it matters" per question, in the question text.
- Image requests go in the same round as the questions they relate to. The user can add images to the chat or a form section.
- Stop when no area is `blocked` and every blocking question has an answer or an accepted default. Usually 2 to 4 rounds.
- If the session can't ask interactively (for example a background run), post the questions on the G0 board entry instead and wait.

After each round, write the answers into `brief.yaml` with `from: interview`, and append them to `plan/interview.md`.

## Plan

Write `plan/plan.md` from [plan-template.md](plan-template.md). It is short: one screen per section at most. Then post G0 with `gate-board`, including the plan, the readiness table and the assumptions list. The user approves, approves with notes, or requests changes. Nothing in Stage 1 starts before G0 is approved.
