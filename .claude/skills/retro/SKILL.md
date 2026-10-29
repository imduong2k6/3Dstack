---
name: retro
description: At the end of a scene pipeline project (G3), or after a phase that took too many rounds, measure where time and rounds went, combine it with research findings, and send the user ranked suggestions to make the next phase or project faster. Use it at hand-off, or when the user asks how to speed the pipeline up.
---

# Retro and improvement suggestions

Run by the manager, with a researcher for mode 3 of `workflow-research`.

## Measure

From `log.md`, `git log` timestamps, `reviews/*/review.md`, `feedback.json`, `routing.yaml`, `backlog.md` and `feedback/*.md`:

| Number | Why |
| --- | --- |
| Rounds per gate and phase | Where the work bounced |
| Wall time per stage (commit to commit) | Where the time went |
| Top 5 supervisor issue types | Repeat mistakes become skill rules |
| Art Director notes marked Skip | Notes the user doesn't value |
| Model escalations | Tasks that need a stronger default |
| Tripo and Magnific credits used | Cost per asset |
| User edits after a gate | What the agents missed |

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
- Suggestions the user accepts become skill edits in one commit, `[pipeline] retro <slug>: <summary>`, logged in `feedback/CHANGELOG.md`.
- Add the project's line to `feedback/projects.md` (rounds, time and credits per stage), so trends across projects show up.
