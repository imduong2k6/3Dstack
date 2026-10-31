---
name: placement-phases
description: Place the scene in ten phases that follow real-world construction order, from P0 site to P9 life and nature, with one save point, capture, review and board entry per phase. After a detailed blockout it starts at the first phase with open items. Use it in Stage 5 on any route.
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
| P8 | Wear and time: repairs (patched panels, replaced parts), and silhouette damage only when the user asks for it. Wear itself is `house-rules` rule 1 | Ageing | Not on the map |
| P9 | Life and nature: foliage, animated assets, people | Living in it | Green, Red |

## After a detailed blockout

When `brief.yaml › detail` is `detailed` or `final` (mode table in `scene-pipeline`), the blockout already holds most of the scene. Don't place it again phase by phase.

- **Phase tags at creation.** Every object gets its `phase` (and `map_id`) when the blockout makes it, so any object can be audited by phase (`blockout`, step 1).
- **Start at the first phase with open items**: objects still proxies, assets still missing, rules still failing. That is usually P5.
- **The phases before it are audits.** P0 to P4 get `scene-lint` and a review of their tagged objects against the rules below, not new placement. Fix what fails; leave what passes.

## Rules

- Services follow the structure they hang from. Fixtures only go where services reach: a light needs a conduit, a sink needs a pipe. Clutter only goes inside a cluster that explains it.
- Respect `clearance_m` in the specs: no prop inside a door swing or a walkway.
- Repeats are instances, never copies: collection instances in Blender, instanced static meshes or PCG in Unreal.
- Unreal: PCG and splines for cables, pipes and railings. Blender: geometry nodes, curves with bevel objects, and arrays.
- **Services plan first.** The plan lives at `plan/services.yaml`, written in Stage 1 by `detail-inventory` and drawn on the map by `layout-2d` in Stage 2: supply, meters, distribution, a run to each unit, then the fixtures, each with an id, position, mount, what it connects to and whether it reuses, moves or is new. Build from it before P3 and before any services in a detailed blockout. Not in lint yet: the supervisor checks that every electrical, conduit or cable object's id is in the plan.
- **Build runs from their rows.** On the Blender routes, conduit, cable, pipe, downpipe and duct runs are built by `linear-runs` from their `plan/services.yaml` rows: routed along the walls, checked against every solid, with bends, saddles and clips. Never type path points. A run it refuses gets a `path_m` or `via_z` on its row.
- **Conduit is one system.** Runs are orthogonal and end at a box, a meter, a fixture or a wall entry.
  - Every fitting meets straight conduit at each open end. Lint: `conduit_open_ends`.
  - Saddle clips about every 0.9 m (not in lint yet; the supervisor checks).
- **Cables** follow `layout.json › runs`.
  - Every run starts and ends at a real object or past the frame edge; a cable enters a wall only through a box, gland or conduit; a visible run under about 0.6 m needs a reason (a drip loop, a box-to-box jumper); no cable passes through a conduit, pipe, box or board. Lint: `cable_ends`, `cable_in_rigid`.
  - Smooth curves: at least 12 segments per bend, no facet over about 8°, shaded smooth (not in lint yet; lint's `cable_sag` covers sag only).
  - **Bundles vary:** mixed strand thickness (wire-sized, about 0.8 to 2 cm in a dense urban scene), and a different sag, spread and seed per run. Never parallel offset copies of one strand. Reviewer.
  - **Building them.** `brief.yaml › cables: rig` builds them with the user's cable generator from the toolbox, one rig per run (`geometry-nodes`, `toolbox/tools/bl.cable_generator.md`). Use the rig for every hanging bundle and every span between two anchors; a single wire along a wall may be a tube. Realize the rig before saving. `guides` leaves one curve per run with its two end points marked, for the user's own cable tool.
  - **In Unreal,** the end points become spline points on the same objects.
- **Wall-mounted items sit on or in the wall.** Items that pass through a wall (vents, louvres, extract fans, AC units) get a real opening in the host wall, as an applied boolean, with their frame flush on the wall face: cut through wherever the far side can be seen, otherwise a blind pocket at least 0.15 m deep. Lint: `through_wall_openings` (it cannot tell whether the far side is seen; the reviewer checks that). Surface-mounted items touch the wall within 2 mm. Lint: `floating`.
- **Paper, posters, stickers and signs** are planes with an alpha cut-out for torn edges, subdivided only where they bend (`knowledge/paper-alpha-planes.md`).
- **Wall shells stay simple shapes.** Wear: see `house-rules` rule 1.
- **Paired elements** (`mirror_of` on the map) are placed once and mirrored across their axis, each set into its recess in the shell.
- CG route: place only what a hero camera sees, plus what casts shadows or reflections into the frame.
- Game routes: checks and polish cover what a player can see from eye height anywhere along the walk paths, looking in any direction including up, plus the review cameras. `visible_set.py` (part of `scene-lint`) writes that set once to `visible_set.json`, from rays cast at points every 0.5 m along the paths. Lint scopes its geometric checks to it. Problems outside it are Later.

## Per phase

1. Place, following `phases.md` and the map IDs. A model that emits (bulb, lamp, sign, screen) gets its `lights.json` row (`lighting-brief` shape) and a plain-strength light in `COL_Lights` when it is placed, and keeps it when a final replaces its proxy (`house-rules` rule 7).
2. Run `scene-lint` (overlaps, floating objects, naming, instancing, and the services and cable fields above) and fix what it finds.
3. Save and back up the step (`house-rules` rule 4), run the stats script, and capture the camera set plus a close-up of what changed.
4. Supervisor and Art Director review; post the board entry; save point with `checkpoint` (a log line, the backup and a ledger entry; projects stay local).
5. Fix rounds up to `max_rounds` (default 3), but at most two rounds of form polish: a third is only for a clear mistake against the reference, or in `camera_match` and `full_cg` a photo landmark that misses the fit rule (5 px at 600 x 800). Other form notes go to Later, into the texturing brief.
6. Wear items (and each Art Director wear note) go to `handoff/wear-notes.md` (`house-rules` rule 1).

Steps 1 to 3 run after every phase. Step 4 runs per review group of the tier: S reviews P0 to P4 and P5 to P9 as two groups, M uses three (P0 to P4, P5 to P7, P8 to P9), L reviews every phase.

In `camera_match` and `full_cg`, run `fit_check.py` (Blender) for the pieces placed in the phase in step 2, and attach its table and overlay to the capture set.
