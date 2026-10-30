---
name: retro
description: At the end of a scene pipeline project (G3), or after a phase that took too many rounds, measure where time and rounds went from log.md and the step ledger, look up better ways to do the slowest steps, and send the user ranked suggestions to make the next phase or project faster. Use it at hand-off, or when the user asks how to speed the pipeline up.
---

# Retro and improvement suggestions

Run by the manager, with a researcher (Sonnet) for the research step. Projects stay local, so the retro reads files, never git history, and opens no commit, push or PR for the project (`house-rules` 3).

## Measure

Read `log.md` first (lines are `YYYY-MM-DD HH:MM <who> <what>`, `house-rules` 12), then `plan/steps.json`, `reviews/*/review.md`, `feedback.json`, `backlog.md` and `feedback/*.md`:

| Number | Why |
| --- | --- |
| Rounds per gate and phase | Where the work bounced |
| Wall time and active time per stage (from the log lines) | Where the time went |
| Build minutes against integration minutes (joining lanes, fixing seams) | Whether the lanes paid off |
| Top 5 supervisor issue types | Repeat mistakes become skill rules |
| The user's corrections after G0, each with the earliest stage that could have asked | Questions the interview should have had |
| Obsolete-work minutes (work thrown away by a reversal) | The price of a late decision |
| Spend before G0 (credits, time) | Cost nobody approved yet |
| Art Director notes marked Skip | Notes the user doesn't value |
| Tripo and Magnific credits used | Cost per asset |

**Too many rounds** means 3 rounds on one gate, 2 changes-requested on it, or over 2 hours of active time on it. Run the retro early for that gate.

## Research

Look up how professionals do the steps that took the most rounds or time. Rate each finding by fit and effort and mark it adopt now, test first or later, as in `workflow-research`. Every problem solved during the project already has a `knowledge/` note; add any that is missing.

## Suggest

Write `handoff/improvements.md`: at most 10 suggestions, ranked by expected gain.

```markdown
### 1. Pre-build a trim sheet before kit pieces (next project)
Evidence: P1 and P2 took 3 rounds each; 9 of 14 supervisor issues were texel density on trims.
Change: add a trim sheet step to `modular-kit`, before modelling.
Gain: about 2 rounds saved per structure phase. Effort: low.
Source: 80.lv 70s office breakdown (link)
```

Each suggestion says whether it's for the next phase (this project) or the next project, which skill, agent or doc changes, the evidence, and the expected gain and effort.

## Deliver

- Attach to the G3 board entry and summarise the top three in chat.
- Suggestions the user accepts become skill edits, committed as `[pipeline] retro: <summary>` (`checkpoint`) and logged in `feedback/CHANGELOG.md`.
- With the user's OK, promote each lesson from the project to `feedback/<skill>.md`, with private names and places taken out, so it reaches the skills and the next project. A lesson that shows up on two projects becomes a rule in the skill.
- Add the project's line to `feedback/projects.md` (rounds, time and credits per stage), so trends across projects show up. Write it without private names; `scene-interview` reads this file for its pre-mortem.
