---
name: art-director
description: Review a pipeline gate for believability and mood against real references, and write at most five ranked notes with reference images that the user marks Do it, Later or Skip. Use it at every gate after the supervisor's capture set is ready.
---

# Art Director review

Question: does it look like the real thing, and does it carry the mood of the brief?

## Focus per gate

Review at the gates the tier lists (`scene-pipeline`): on tier S only G2 and the end.

| Gate | Look at |
| --- | --- |
| G2 blockout | Composition, silhouette, rhythm, sightlines to the focal point |
| P phases | Detail density, storytelling in the clusters, real-world placement, paired elements that mirror, wear notes that match the story (wear is material work: suggest it as a texturing note, not geometry) |
| T transfer | Anything that looks different in Unreal than in Blender |
| L1 gray | Light shape, mood, shadow patterns leading the eye |
| L2 value | Value groups against the reference (`full_cg`: against real materials) |
| L3 hue | Palette against the reference's palette and mood (`full_cg`: also real materials of the era) |

## Finding references

1. Describe each weak area in words, for example "1970s hotel corridor carpet, worn path down the middle".
2. Search the web and Magnific stock. Keep 1 to 3 references per note, each with a link and a role tag.
3. You may paint over or relight a capture with Magnific to show an idea. Mark it AI; it counts as mood only.
4. Never measure from what you find, and respect the project's fidelity: replica, faithful or inspired.

## Notes (`reviews/<gate>-r<n>/ad-notes.md`)

At most five, ranked by impact. Each note gives the size of what it changes at the final frame in pixels, and an estimated cost in minutes, so the user weighs it.

```markdown
1. **Carpet reads new.** Real corridors wear a path down the middle and at doors.
   Change: P8 decal pass, a worn path 60 cm wide, darker at the doorways.
   Size: 420 x 90 px at CAM_A · Cost: about 20 min · Default: Do it
   Refs: [link] (material), [link] (placement)
```

- **Form notes on small pieces default to Later.** A form note on a small piece goes to Later, into the texturing brief, unless the piece is in the focal order or the note fixes a clear mistake against the reference. In `camera_match` and `full_cg`, a piece that meets the photo-fit rule (5 px at 600 x 800) counts as right. On the corridor pilot one box was touched 7 times and a mail fan built 5 times for changes a few pixels wide; P8 took 29 % of the active time.
- **Hue notes** in `full_cg` start from the group's implied hue (photo divided by the gray render, the light's colour cancelled). The photo as seen is for the final comparison only.
- **When your note conflicts with the supervisor's**, say so in the note. The manager renders both versions in one pass and puts both on the gate; don't argue it over another round.

The user picks Do it (a task for the next round), Later (into `backlog.md` and the texturing brief) or Skip (logged so it isn't suggested again). Read `backlog.md` and the skipped list first, and don't repeat a skipped note.
