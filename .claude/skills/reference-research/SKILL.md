---
name: reference-research
description: Research the real-world facts a scene needs (place, era, construction, materials, real object dimensions, fixtures, colour temperatures, time of day and weather) and write sourced notes and a metrics file. Use it in Stage 1 of the scene pipeline, or whenever a worker needs a real dimension.
---

# Reference research

Research only as deep as the input needs. On the corridor pilot most dimensions came from research text and were later overridden by the photo.

## Order: stop at the first step that answers

1. **Solved before?** Read `knowledge/` in the repo, then the private folder (`brief.yaml › knowledge_local`).
2. **Eyeball from the reference.** Measure each object against one anchor in the same image (a door leaf about 2.0 m, a step about 0.17 m, a standard brick course, a person) and write `source: eyeballed, <ref id>, anchor <what>`.
3. **Real data** (manufacturer data, standards) only for objects the references hide, crop or show too small to judge.
4. **Deep research** (place, era, construction) only for an area with no reference at all.

Tier S stops after step 2 unless an object is hidden: the manager does it, with no researcher agents. Tiers M and L run researcher agents (Sonnet) in parallel, one topic each, for what steps 1 and 2 left open.

## Topics (only what the references don't answer)

| Topic | Find |
| --- | --- |
| Place and era | Building type, construction method, storey heights, typical materials and finishes, what changed over time |
| Objects | Real dimensions of every object type in `plan/assets.yaml`, with a source per number |
| Fixtures and light | Real fixtures of the era, their lamp type and colour temperature, mounting heights |
| Time and weather | Sun angle for the place and time, sky and fog references |
| Wear and story | How this kind of place ages, gets used and gets repaired |

## Rules

- Every number in `plan/metrics.yaml` has `source:` (a link, a book, a knowledge note, or a reference image with its anchor) or `assumed: true` with the reasoning.
- Prefer manufacturer data, standards and building codes, architectural references (Architects' Data and similar), and measured photos with a scale anchor.
- Images found online go into `refs/index.yaml` with their link and a proposed role tag. Never use AI images for measurements.
- If two sources disagree, record both and pick one with a reason.

```yaml
# plan/metrics.yaml
door_leaf_height_m: {value: 2.04, source: "https://…", note: "US residential standard, 6'8\"", role: anchor}
letterbox_width_m: {value: 0.30, source: "eyeballed, corridor-01, anchor door_leaf_height_m"}
corridor_width_m:  {value: 1.83, assumed: true, note: "between hotel corridor norms; no anchor in refs"}
```

## Output

`plan/research.md` with links, `plan/metrics.yaml`, and new entries in `refs/index.yaml`.
