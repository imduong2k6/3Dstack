---
name: input-review
description: Judge a scene brief and its references before planning. It tags every reference by role, builds a coverage matrix, checks scale anchors, conflicts and AI images, rates readiness per area, and writes a question list for the Stage 0 interview. Use it in Stage 0 of the scene pipeline.
---

# Input review

Run by the input reviewer agent (Opus). The output feeds the manager's interview, so every question must be answerable by picking an option.

## Steps

0. **Prepare the images before viewing any.** Run `scripts/prep_refs.py <refs folder>/<group>` once per PureRef group folder (`uv run --no-project --with pillow python -I ...`), plus once for any files outside a group, so each group gets its own labelled contact sheets of 9 in its `_view/`. It rejects files that won't decode, which the API refuses with "Could not process image", and writes clean copies with a 1568 px long edge. Look at each group's sheet first and open single copies only for detail. Report rejected files to the manager; don't retry them.
1. **Tag each reference** in `refs/index.yaml`, group first. Record the PureRef group as `group:`, give the group a first set of roles from its name and its sheet, then refine per image. Roles: `target` (the finished look the scene must reach), `hero` (the photo to match), `measure` (usable for sizes), `form`, `material`, `mood`, `composition`, `placement`, or `unused` with a note for an image you won't use. Mark AI images `ai: true`; they are never `measure`. Mark photos for projection `photo_proj` when the route is `blender`.
   - **Precedence.** For form and composition, `hero` beats `target`, and `target` beats the rest. For a size, only `measure` counts. Two references of the same role that disagree become a question.
   - **Exit rule.** Don't finish while any reference has `roles: []`. Read the file back and count.
2. **Coverage matrix.** For each major element (room, facade, hero prop, ground, ceiling), list which views exist: front, side, top, detail, context. Note the gaps.
3. **Scale anchors.** For each space, find a known size such as a door, a person, a step, a brick course or a car. No anchor means the area is `usable with assumptions` at best.
4. **Conflicts.** References that disagree on a size, material or layout. Propose the middle value or the most reliable source, and say which.
5. **Readiness per area:** `ready`, `usable with assumptions` (list the assumptions), or `blocked` (say what would unblock it).
6. **Image requests.** Specific shots only, such as "a photo of the corridor end wall, straight on, with a door in frame".
7. **Questions.** Everything unclear in the brief or references becomes a question. Most important first.
8. **Hand over.** The tagged `refs/index.yaml` and the group sheets go to `detail-inventory` (Stage 1), which breaks the `hero` and `target` references into zones and features.

## Question list format

```yaml
# plan/questions.yaml
- id: q1
  area: corridor_end
  blocking: true                  # blocking questions must be answered before the plan
  question: What is at the far end of the corridor?
  why: Sets the focal point and the key light.
  options:                        # 2 to 4 options, the default first
    - Window to the street (default)
    - Fire exit door with a push bar
    - Elevator lobby
  default: 0
  from: refs                      # refs | brief | research
```

Write questions about intent (what should the viewer feel, what matters most), scope (what's in and out, what's hero), route and deliverables, lighting (time, weather, key light), fidelity, and budget or time. Don't ask anything the references or brief already answer; cite them instead.

## Output

`plan/input-review.md` (coverage matrix, anchors, conflicts, readiness table, image requests), `plan/questions.yaml`, and `refs/index.yaml` with every reference tagged.
