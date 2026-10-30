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
- **Services blueprint first.** Before P3, and before any services in a detailed blockout, draw the services as one connected system over the map. A typical chain runs from the supply entry to the meter boards, then to the distribution boxes, then a run to each unit, then the fixtures (lamps, switches, sockets, intercoms, signs, AC). Give each component an id, its position and mount, what it connects to and by what (conduit, tray or cable), and whether it reuses, moves or is a new asset. Arrange it the way the references do: meter boards grouped near stair entries, conduit vertical and horizontal, bundles sagging between brackets. Build from the blueprint; nothing electrical goes in that isn't on it.
- **Conduit is one system.** Every fitting (elbow, tee, coupling) meets straight conduit at each open end. Runs are orthogonal, saddle-clipped to the wall about every 0.9 m, and end at a box, a meter, a fixture or a wall entry. A fitting with an open end is a fault.
- **Cables** follow `layout.json › runs`:
  - **Ends.** Every run starts and ends at a real object (a meter, a box, a conduit, a fixture) or past the frame edge. A cable enters a wall only through a box, gland or conduit, never bare plaster. A visible run under about 0.6 m needs a reason (a drip loop, a box-to-box jumper); otherwise extend it or remove it.
  - **Smooth curves:** at least 12 segments per bend, no facet over about 8°, shaded smooth.
  - **Bundles vary:** mixed strand thickness (wire-sized, about 0.8 to 2 cm in a dense urban scene), and a different sag, spread and seed per run. Never parallel offset copies of one strand.
  - **Building them.** `brief.yaml › cables: rig` builds them with the user's cable generator from the toolbox, one rig per run (`geometry-nodes`, `toolbox/tools/bl.cable_generator.md`). Use the rig for every hanging bundle and every span between two anchors; a single wire along a wall may be a tube. Realize the rig before saving. `guides` leaves one curve per run with its two end points marked, for the user's own cable tool.
  - **In Unreal,** the end points become spline points on the same objects.
- **Wall-mounted items sit on or in the wall.** Items that pass through a wall (vents, louvres, extract fans, AC units) get a real opening cut in the host wall, as an applied boolean, and sit with their frame flush on the wall face. Surface-mounted items touch the wall within 2 mm.
- **Paper, posters, stickers and signs** are planes with an alpha cut-out for torn edges, subdivided only where they bend (`knowledge/paper-alpha-planes.md`).
- **Wall shells stay simple shapes.** Chips and cracks are texturing notes; detailed damage is generated (`tripo-props`) only in `full_cg` or when the user asks for a detailed blockout.
- **Paired elements** (`mirror_of` on the map) are placed once and mirrored across their axis, each set into its recess in the shell.
- CG route: place only what a hero camera sees, plus what casts shadows or reflections into the frame.
- Game routes: checks and polish cover what a player can see from eye height anywhere along the walk paths, looking in any direction including up, plus the review cameras. The worker writes that set once (`visible_set.json`, from rays cast at points every 0.5 m along the paths). Problems outside it are Later, not fixes.

## Per phase

1. Place, following `phases.md` and the map IDs.
2. Run the adapter's validation (overlaps, floating objects, naming, instancing) and fix what it finds.
3. Save, run the stats script, and capture the camera set plus a close-up of what changed.
4. Supervisor and Art Director review; post the board entry; commit with `checkpoint`.
5. Fix rounds up to `max_rounds`, but at most two rounds of form polish: a third is only for a clear mistake against the reference, or in `camera_match` and `full_cg` a photo landmark that misses the fit rule (5 px at 600 x 800). Other form notes go to Later, into the texturing brief.
6. Write each wear item you didn't model (and each Art Director wear note) into `handoff/wear-notes.md`: the surface, the kind of wear, where and how much.

Steps 1 to 3 run after every phase. Step 4 runs per review group of the tier: S reviews P0 to P4 and P5 to P9 as two groups, M uses three (P0 to P4, P5 to P7, P8 to P9), L reviews every phase.

In `camera_match` and `full_cg`, run `fit_check.py` (Blender) for the pieces placed in the phase in step 2, and attach its table and overlay to the capture set.
