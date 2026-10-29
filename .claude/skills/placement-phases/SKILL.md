---
name: placement-phases
description: Place the scene in ten phases that follow real-world construction order, from P0 site to P9 life and nature, with one save, capture, review, board entry and commit per phase. Use it in Stage 5 on any route.
---

# Placement phases P0 to P9

Run by the route's worker. Each phase places only what physically exists by then.

| Phase | What goes in | Real-world step | Map colour |
| --- | --- | --- | --- |
| P0 | Site and ground: terrain, roads, kerbs, paths, water level | Site prep | Grey |
| P1 | Structure: floors, walls, columns, stairs, roof | Structural frame | White |
| P2 | Envelope and openings: facades, windows, doors | Enclosure | White, Blue, Red |
| P3 | Services: pipes, ducts, cable trays, conduits, overhead wires | Rough-in | Purple |
| P4 | Fixed fit-out: light fittings, cabinetry, signage, railings | Trim-out | Cyan |
| P5 | Anchor props and the hero piece | Furniture move-in | Yellow |
| P6 | Story clusters of 3 to 7 props | Occupancy | Orange |
| P7 | Small clutter, inside clusters | Daily use | Orange |
| P8 | Wear and time: damage that changes the silhouette, and repairs. Grime, stains, leaks, rust, cracks and chips are texturing notes, not meshes (in `full_cg`, decals are allowed) | Ageing | Not on the map |
| P9 | Life and nature: foliage, animated assets, people | Living in it | Green, Red |

## Rules

- Services follow the structure they hang from. Fixtures only go where services reach: a light needs a conduit, a sink needs a pipe. Clutter only goes inside a cluster that explains it.
- Respect `clearance_m` in the specs: no prop inside a door swing or a walkway.
- Repeats are instances, never copies: collection instances in Blender, instanced static meshes or PCG in Unreal.
- Unreal: PCG and splines for cables, pipes and railings. Blender: geometry nodes, curves with bevel objects, and arrays.
- **Cables** follow `layout.json › runs`: every run starts and ends at a real object (a meter, a box, a conduit, a fixture) or past the frame edge. `brief.yaml › cables: rig` builds them with the cable generator from the toolbox, one rig per run (`geometry-nodes`); `guides` leaves one curve per run with its two end points marked, for the user's own cable tool. In Unreal, the end points become spline points on the same objects.
- **Paper, posters, stickers and signs** are planes with an alpha cut-out for torn edges, subdivided only where they bend (`knowledge/paper-alpha-planes.md`).
- **Wall shells stay simple shapes.** Chips and cracks are texturing notes; detailed damage is generated (`tripo-props`) only in `full_cg` or when the user asks for a detailed blockout.
- **Paired elements** (`mirror_of` on the map) are placed once and mirrored across their axis, each set into its recess in the shell.
- CG route: place only what a hero camera sees, plus what casts shadows or reflections into the frame.

## Per phase

1. Place, following `phases.md` and the map IDs.
2. Run the adapter's validation (overlaps, floating objects, naming, instancing) and fix what it finds.
3. Save, run the stats script, and capture the camera set plus a close-up of what changed.
4. Supervisor and Art Director review; post the board entry; commit with `checkpoint`.
5. Fix rounds up to `max_rounds`, but at most two rounds of form polish: a third is only for a clear mistake against the reference, or in `camera_match` and `full_cg` a photo landmark that misses the fit rule (5 px at 600 x 800). Other form notes go to Later, into the texturing brief.
6. Write each wear item you didn't model (and each Art Director wear note) into `handoff/wear-notes.md`: the surface, the kind of wear, where and how much.

Steps 1 to 3 run after every phase. Step 4 runs per review group of the tier: S reviews P0 to P4 and P5 to P9 as two groups, M uses three (P0 to P4, P5 to P7, P8 to P9), L reviews every phase.

In `camera_match` and `full_cg`, run `fit_check.py` (Blender) for the pieces placed in the phase in step 2, and attach its table and overlay to the capture set.
