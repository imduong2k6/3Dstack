---
name: modular-kit
description: Plan and spec the scene's modular kit (grid, piece list, pivots, sockets, trim sheets, material groups, collision and LODs) and write one asset spec per piece for the Modeler. Use it in Stage 4, after the blockout is approved.
---

# Modular kit

The kit plan comes first; the Modeler builds pieces from the specs with the `modeling` skill.

## Plan the kit

1. **Count the repeats** in the blockout. Pieces that repeat become kit pieces; one-offs become props.
2. **Grid:** pick it from the blockout (for example 0.5 m snapping, with 1, 2 and 4 m wall widths). Pivots go on a grid corner.
3. **Trim sheet first.** Design one trim sheet (mouldings, frames, skirting, panel edges) and the tiling materials before modelling, so pieces are UV'd once. Assign each surface a `material_group` from the palette groups.
4. **Piece list:** straight, corner, T-junction, end, door, window, transitions, and floor and ceiling tiles. Add a broken variant only when the user asks for one; dirt, stains, cracks and chips are the user's texturing work, not mesh variants. Recesses for doors and windows are part of the wall piece.
5. **Collision and LOD plan** per piece type (see `modeling/references/game-models.md`).
6. **Batches for the asset lane.** In `plan/assets.yaml`, give each asset a `batch` (pilot, kit, props, generated, hero) so the manager can split the work across Modelers by type. Hero assets get a Modeler to themselves.

For piece roles and counts, grid starting points and storytelling details, read the `environment-artist` skill (its pipeline notes say what to ignore).

## Asset spec (`kit/<asset>.md`)

```yaml
---
id: SM_Office_Wall_Door_A
kit: Office
legend: white
phase: 2
source: build            # build | library | generate | unreal_modeling
dims_m: [4.00, 0.15, 3.00]
pivot: bottom-center
snap_grid_m: 0.5
sockets:
  - {name: hinge_L, pos_m: [-0.45, 0, 0]}
clearance_m:
  door_swing: {radius: 0.9, side: +y}
material_group: [upper_wall, trim, door_frames]
texture_set: TS_Office_Walls
texel_density_px_m: 512
camera_tier: mid         # hero | mid | far
budget_tris: 800
method: null             # the Modeler fills this in
landmarks: kit/SM_Office_Wall_Door_A.landmarks.json   # camera_match and full_cg: read by fit_check.py
done_when:               # measurable acceptance, like an outsourcing brief
  - every landmark in landmarks.json within 5 px at CAM_A, 600 x 800
  - snaps to the 0.5 m grid with no gaps against SM_Office_Wall_Plain_A
  - door leaf opening 0.90 x 2.04 m within 1 cm
  - one material slot per material_group, texel density 512 px/m within 10%
---
The photo crop first, with its landmarks labelled, then notes, reference images and what makes this piece specific.
```

**`camera_match` and `full_cg`: the crop comes before research.** Write each spec from the photo crop of that piece, with its landmarks (corners, lid edges, the cell it sits in) labelled and measured in pixels at the review camera. Research text fills only what the crop can't show, such as depth behind a face. On the corridor pilot, 7 spec items written from research text were overridden by the Modeler at K, and a box hung in front of its pigeonhole for 6 touches before anyone checked the photo showed it inside. The landmarks go in `landmarks.json` (format in `blender-adapter/scripts/fit_check.py`); the worker runs `fit_check()` before posting and attaches its table and overlay, and the supervisor reads that output instead of re-measuring.

## Pilot first

Before the batch, one Modeler builds one representative kit piece and one prop, and the Asset Tech finishes them. The supervisor and the Art Director review them, and you approve them at gate K. Post K only once both reviews are in, with their merged fix list, so that approving K accepts that list (on the corridor pilot K was approved 2 minutes after the build, before the 14-item list existed). Lessons go into the specs before the batch starts, the same way studios start an outsourcing partner with a paid test asset. Only then does the manager run several Modelers at once (see `docs/pipeline/parallel.md`).

## Exit

The supervisor passes each piece against its spec: size within 1 cm, pivot, naming, grid snap, and material groups. Finished pieces go to the level lane in batches and replace their proxies.
