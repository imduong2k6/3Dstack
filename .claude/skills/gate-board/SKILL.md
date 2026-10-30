---
name: gate-board
description: Post a pipeline gate to the Gate Review Board artifact (contact sheet, captures, stats, supervisor verdict, Art Director notes, locked decisions, before/after pairs, a "Please check" list, questions, plan or retro sections) and read back the user's decision. Use it when a gate is awaiting review, and when the user says to continue.
---

# Gate Review Board

Schemas: `docs/pipeline/schemas/gate.schema.json` and `feedback.schema.json`. Data contract: `docs/pipeline/data-and-commits.md`.

Gate order: G0, G1, G2, K, P0 to P9, T, L1, L2, L3, G3. The tier (`scene-pipeline`) decides which of them the user answers; the other reviews are attached to the next user gate as extra captures and a line per review in the summary.

## The board

The board's URL is stored in `brief.yaml › board_url`. If it is empty, publish the board before posting G0: publish `docs/pipeline/pages/gate-review.html` as an Artifact (private by default), store the URL, and use it for every upload and write below. A gate is never posted to a board you haven't recorded.

## Post a gate

1. Write the gate pack locally in `reviews/<gate>-r<n>/`: `contact.png` (`review-pairs/scripts/compose_pairs.py contact --dir <that folder>`), the captures, `stats.json`, `lint.json`, `review.md`, `ad-notes.md`, and the pairs from `review-pairs`. On the Blender routes, a blocker in `lint.json` means fix first: never post it.
2. Upload `contact.png`, the captures and the composed pairs to the board artifact's asset store (Artifact publish with `asset: true` and the board's URL). Use the returned URLs exactly. Captures with reference pixels in frame (photo overlays) are fine on the board, which is private (`house-rules` 3).
3. Write the gate entry with ArtifactData `set` in collection `gates`, id `<slug>-<gate>-r<round>`, status `awaiting_review`. Stamp `createdAt` from the system clock (`date -u +%Y-%m-%dT%H:%M:%SZ`) at the moment of posting, never a typed time. The entry has these parts, in this order:
   - **Summary, stats and verdict.** One line per review attached to this gate. When the manager has started on the default path, the summary says so ("started on the default; undo is ready").
   - **Art Director notes.** Each default shows its cost and size (for example "Do it · ~20 min · 420 x 90 px").
   - **Locked.** A `sections` entry titled "Locked" lists every decision the next stage builds on, with the gate and date it was locked (layout, kit grid, exposure, route, detail level, standing rules). A reversal redoes the work that depends on it, so say what that costs when the user asks for one. Read the entries from `log.md` and `brief.yaml`.
   - **Before and after.** One `captures` entry per pair, the composed `pairs/<id>_pair.png` (before on the left), labelled "Before/after <id>: <what was wrong>", in the order `pairs.json` lists them. (A `sections` entry can't hold images.) Each fixed issue has one pair from `review-pairs`: its own camera, rendered from the previous round's backup and from the new gate copy, captioned with what was wrong. A pair whose note says its objects are out of frame, or that looks unchanged, goes into Please check.
   - **Please check.** A `sections` entry titled "Please check: things I'm not sure work properly": at most 8 items, ranked by risk. Draw them from the agents' not-checked lists, numbers that weren't re-rendered, visible issues, the captures' limits and anything hidden or deferred. Each item says what may be wrong, where to look and why.
   - **Questions.** When the reviewers disagree, the entry carries both renders as captures, with each option's acceptance numbers in the question.
   - G0 carries the plan as `sections` (one per plan heading, as short items), plus `readiness`, `questions`, `requests` and the pre-mortem. G3 carries the retro's top suggestions as a `sections` entry.
4. Tell the user in chat, in one line, with the board link.

## Read the decision

When the user says continue (or on a `/loop` check), read `feedback/<id>`. If it has a decision and `pickedUp` is false:

1. Save it as `reviews/<gate>-r<n>/feedback.json`. A decision given in the thread instead ("approved", "2") is saved there too, with `from: thread` and `submittedAt` from the system clock at the moment you read it, never a typed time, so every gate has its record and its wait time.
2. Set `pickedUp: true` (pin the write to the version you read).
3. `approved` with a supervisor PASS: the gate passes, move on. `approved` with a FIX verdict: take the defaults on the open items and start round n+1; the gate has not passed. `approved_with_notes`: as above, and add the notes as tasks. `changes_requested`: start round n+1 with the notes and the Art Director notes marked Do it.
4. Answers to questions go into `brief.yaml` with `from: board`. A rule the user states for the rest of the project goes into `brief.yaml › standing_rules` as `{date, rule, from}`, in their words.
5. File the Art Director notes by mark: **Later** and **Skip** go to `backlog.md` (one line each: gate, note, mark, date; skipped notes are never suggested again). Any wear item, whatever its mark, goes to `handoff/wear-notes.md` (surface, kind, where, how much) and the surface stays clean (`house-rules` 1).

Without the Artifact tools, write the pack as markdown in `reviews/` and ask in chat.
