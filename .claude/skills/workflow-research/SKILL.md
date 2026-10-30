---
name: workflow-research
description: Research how professional environment artists, game studios and VFX teams build a given kind of scene or solve a given problem, then rate each finding by fit and effort and map it to a pipeline stage and skill. It has two modes, Stage 1 project research and problem research when a step keeps failing. Use it to make this and future projects faster.
---

# Workflow research

Run by researcher agents (Sonnet). The goal is speed and quality on this project and the next one, not a reading list.

Read `knowledge/` (repo, then `brief.yaml › knowledge_local`) before going online. A problem with a note there is solved: use the note and only search when it doesn't fit.

## Mode 1: Stage 1 project research

Run it when `brief.yaml` shows any of these: route `blender_unreal`, generation on (`generation_services` not empty), or `detail` other than `massing`. If none holds, skip it and say so in `log.md`. When it runs, it covers only problems this scene raises that `knowledge/` doesn't cover; tier S keeps to the one or two biggest, tier M asks only those questions, tier L runs it in full.

Question: how do professionals build *this kind of scene* on *this route*? For example "abandoned hotel corridor in UE5 with Lumen", or "rainy Hanoi street at night, Blender only, stills".

Look for:

- Breakdowns of similar scenes (80.lv, ArtStation blogs, Polycount, GDC and Unreal Fest talks, befores & afters)
- The kit and trim strategy they used, how many unique pieces, how they handled repetition
- Tools and tricks: PCG graphs, geometry nodes setups, decal workflows, add-ons, scripts
- Lighting setups for the same time of day and mood
- What they said they would do differently

## Mode 2: problem research

Starts automatically when the same issue type appears in two review rounds (the same lint rule or the same fix-list category, in the supervisor's or the user's notes), or when a worker reports a blocker. The manager starts it before the next round. Question: how do professionals handle *this specific problem*? Examples: "kit seams visible under grazing light", "Lumen light leaks at modular wall joins", "Tripo chair legs too thick". Return one to three concrete fixes with sources, and the one you recommend. When the fix works, write it to `knowledge/` (format in `knowledge/README.md`), or to the private folder if it needs reference photos or client details.

End-of-project research is part of `retro`, not a mode here. Every problem solved during the project still gets a `knowledge/` note.

## Rating each finding

```yaml
# plan/workflow-notes.md (one table), or a plan/pro-tips.md entry in problem mode
- finding: Use one 2048 trim sheet for all wall trims, mouldings and door frames
  source: https://80.lv/…
  stage: 4 kit
  skill: modular-kit
  fit: high            # high | medium | low for this project and route
  effort: low          # low | medium | high
  gain: "about 30 fewer unique texture sets; faster texturing hand-off"
  recommend: adopt_now # adopt_now | test_first | later
```

- `adopt_now` items go into the G1 pack for the user's approval; nothing changes a skill without approval.
- `test_first` items get a time-boxed test task in the plan.
- `later` items go to `feedback/ideas.md` for the next project.

Prefer sources by people who shipped the work. Link everything. Say when a finding is one person's opinion.
