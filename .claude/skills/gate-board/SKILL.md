---
name: gate-board
description: Post a pipeline gate to the Gate Review Board artifact (contact sheet, captures, stats, supervisor verdict, Art Director notes, questions, plan or retro sections) and read back the user's decision. Use it at every gate and phase, and when the user says to continue.
---

# Gate Review Board

Schemas: `docs/pipeline/schemas/gate.schema.json` and `feedback.schema.json`. Data contract: `docs/pipeline/data-and-commits.md`.

Gate order: G0, G1, G2, P0 to P9, T, L1, L2, L3, G3. The tier (`scene-pipeline`) decides which of them the user answers; the other reviews are attached to the next user gate as extra captures and a line per review in the summary.

## Post a gate

1. Write the gate pack locally in `reviews/<gate>-r<n>/`: `contact.png`, the captures, `stats.json`, `review.md`, `ad-notes.md`.
2. Upload `contact.png` and the captures to the board artifact's asset store (Artifact publish with `asset: true` and the board's URL). Use the returned URLs exactly.
3. Write the gate entry with ArtifactData `set` in collection `gates`, id `<slug>-<gate>-r<round>`, status `awaiting_review`. Stamp `createdAt` from the system clock (`date -u +%Y-%m-%dT%H:%M:%SZ`) at the moment of posting, never a typed time: on the corridor pilot typed times drifted up to 147 min and broke the retro's wait times.
   - Each Art Director note's default shows its cost and size (for example "Do it · ~20 min · 420 x 90 px").
   - When the reviewers disagree, the entry carries both renders as captures, with each option's acceptance numbers in the question.
   - When the manager has started on the default path, the summary says so ("started on the default; undo is ready").
   - G0 carries the plan as `sections` (one per plan heading, as short items), plus `readiness`, `questions` and `requests`.
   - G3 carries the retro's top suggestions as a `sections` entry.
4. Tell the user in chat, in one line, with the board link.

## Read the decision

When the user says continue (or on a `/loop` check), read `feedback/<id>`. If it has a decision and `pickedUp` is false:

1. Save it as `reviews/<gate>-r<n>/feedback.json`. A decision given in the thread instead ("approved", "2") is saved there too, with `from: thread`, so every gate has its record.
2. Set `pickedUp: true` (pin the write to the version you read).
3. `approved`: move on. `approved_with_notes`: move on and add the notes as tasks. `changes_requested`: start round n+1 with the notes and the Art Director notes marked Do it.
4. Answers to questions go into `brief.yaml` with `from: board`.

Without the Artifact tools, write the pack as markdown in `reviews/` and ask in chat.
