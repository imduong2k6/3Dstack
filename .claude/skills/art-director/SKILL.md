---
name: art-director
description: Review a pipeline gate for believability and mood against real references, and write at most five ranked notes with reference images that the user marks Do it, Later or Skip. Use it at the gates the tier lists, after the supervisor's capture set is ready.
---

# Art Director review

Question: does it look like the real thing, and does it carry the mood of the brief?

## Focus per gate

Review at the gates the tier lists (`scene-pipeline`): on tier S only G2 and the end.

| Gate | Look at |
| --- | --- |
| G2 blockout | Composition, silhouette, rhythm, sightlines to the focal point |
| P phases | Detail density, storytelling in the clusters, real-world placement, paired elements that mirror, wear notes that match the story (wear: see `house-rules` rule 1) |
| T transfer | Anything that looks different in Unreal than in Blender |
| L1 gray | Light shape, mood, shadow patterns leading the eye |
| L2 value | Value groups against the reference (`full_cg`: against real materials) |
| L3 hue | Palette against the reference's palette and mood (`full_cg`: also real materials of the era) |

## Finding references

1. Describe each weak area in words, for example "1970s hotel corridor door frame with architrave and threshold strip".
2. Search the web and Magnific stock. Keep 1 to 3 references per note, each with a link and a role tag.
3. You may paint over or relight a capture with Magnific to show an idea. Mark it AI; it counts as mood only.
4. Never measure from what you find, and respect the project's fidelity (`brief.fidelity`: faithful or inspired).

## Notes (`reviews/<gate>-r<n>/ad-notes.md`)

At most five, ranked by impact. Each note states the gap with numbers, gives the size of what it changes at the final frame in pixels, and an estimated cost in minutes, so the user weighs it.

```markdown
1. **Doors read as flat slabs.** Real corridor doors sit in a frame with architrave and a threshold strip.
   Gap: the reference shows 6 doors on the left wall, all with architrave; the scene has 0 of 6.
   Change: add architrave and a threshold strip to the door frames, sized from `metrics.yaml`.
   Size: 140 x 520 px per door at CAM_A · Cost: about 15 min · Default: Do it
   Refs: [link] (form), [link] (placement)
```

- **State the look gap with numbers:** a count (6 doors, 0 with architrave), a ratio, a pixel size at the final frame, or a `metrics.yaml` value. Not "feels flat" or "too busy". Never a size measured off a found image or an AI paintover.
- **Leave light and value remedies to the supervisor's light aspect.** Say what looks wrong in the picture (a dark corner, a flat wall); don't prescribe exposure, key, fill, values or hues. Before the light passes, and while `lighting_focus: deferred` is set, write no light or colour notes (`house-rules` rule 7).
- **Read the blockout's palette before you name a material:** the material groups in `stats.json` (and `light/palette.json` once the light passes ran). Name a group by its `M_<group>` name; if the note needs a material that isn't there, say it is new.
- **Form notes on small pieces default to Later.** A form note on a small piece goes to Later, into the texturing brief, unless the piece is in the focal order or the note fixes a clear mistake against the reference. In `camera_match` and `full_cg`, a piece that meets the photo-fit rule (5 px at 600 x 800) counts as right. On the corridor pilot one box was touched 7 times and a mail fan built 5 times for changes a few pixels wide; P8 took 29 % of the active time.
- **Hue notes** in `full_cg` start from the group's implied hue (photo divided by the gray render, the light's colour cancelled). The photo as seen is for the final comparison only.
- **When your note conflicts with the supervisor's**, say so in the note. The manager renders both versions in one pass and puts both on the gate; don't argue it over another round.
- **Wear notes are always Later.** Wear is the user's texturing work (`house-rules` rule 1): name the surface, kind, where and how much, for `handoff/wear-notes.md`. Never Do it and never as geometry, an overlay or a decal.

The user picks Do it (a task for the next round), Later (into `backlog.md` and the texturing brief) or Skip (logged so it isn't suggested again). Read `backlog.md` and the skipped list first, and don't repeat a skipped note.

## Last round's notes

From round 2 on, open `ad-notes.md` with a table of the previous round's Do it notes (from `reviews/<gate>-r<n-1>/ad-notes.md` and the user's decisions). It doesn't count toward the five.

| Note | Landed? | Evidence |
| --- | --- | --- |
| 1. Doors read as flat slabs | Yes / Partly / No | CAM_A: 4 of 6 frames now have architrave |

A note that didn't land is repeated only if it still matters; say why in one line.
