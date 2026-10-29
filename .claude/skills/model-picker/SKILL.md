---
name: model-picker
description: Pick the Claude model tier for each scene pipeline task from a rules table, escalate after repeated review failures, and log every choice in routing.yaml. Use it when the brief has model_routing on.
---

# Model picker

Only when `model_routing: true` in the brief. When it is off, every agent uses its own file's model: Opus for workers, the Modeler and reviewers, and Sonnet for researchers, the scanner, the Asset Tech and the Generator.

## Fixed

Workers (Unreal, Blender), the Modeler, the supervisor, the Art Director and the input reviewer stay on **Opus**. The picker never moves them down.

The Asset Tech and the Generator start on **Sonnet**: their work is scripted and checked by numbers. The picker moves either one to Opus for an asset whose output fails review twice.

## Picked per task

| Tier | Tasks |
| --- | --- |
| Haiku | Indexing references, renaming, export batches, running stats scripts, commits, board updates |
| Sonnet | Reference and workflow research, toolbox instruction files, layout drafts, the texturing brief |
| Opus | Conflicting references, the lighting brief, anything a Sonnet task failed twice |

## Escalation

A task whose output fails review twice moves up one tier for its next try. Log it.

```yaml
# routing.yaml
- task: research.fixtures
  tier: sonnet
  reason: default
- task: layout.draft
  tier: opus
  reason: failed G1 review twice on circulation
```
