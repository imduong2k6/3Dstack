---
name: layout-2d
description: Draw the scene's layout as a floor plan (metre grid, key, zones with heights, numbered callouts, scale bar, notes) in the pipeline's colour legend, with an ID on every shape, the player path or review cameras, focal points, cable runs, the asset list and the phase plan. Use it in Stage 2 of the scene pipeline, before the blockout, or as a rough sketch in Stage 0.
---

# 2D layout map

## Inputs

`brief.yaml`, `plan/plan.md`, `plan/metrics.yaml`, `plan/research.md`, `plan/workflow-notes.md`, `plan/inventory.yaml` and `plan/services.yaml` (`detail-inventory`), and the plan views among the references.

The map reads like an architect's floor plan: a metre grid with axes, a key, zones with their floor heights, numbered red callouts, a scale bar and handwritten notes. The colour legend below is the key's set of zone categories, so the IDs still match the asset list.

## Colour legend (never change it)

| Colour | Meaning |
| --- | --- |
| White | Modular architecture: walls, floors, roofs, columns |
| Red | Animated or interactive: doors, fans, screens, vehicles |
| Grey | Terrain and ground |
| Yellow | Hero or focal asset |
| Orange | Set-dressing cluster |
| Purple | Procedural or repetitive: cables, pipes, fences, railings |
| Green | Foliage and organic |
| Blue | Water and glass |
| Cyan | Light sources |
| Black | Blocked, no-go, collision only |

Every shape also carries a short ID label, because colour alone fails for colour-blind readers and is hard to read back from a PNG. Generated assets get a dashed outline.

## Sketch mode (Stage 0)

When the interview needs a picture to choose from, draw from `brief.yaml` and the references only. No research, metrics or services exist yet, so claim no sizes: title it "SKETCH".

- At most 2 options per round. Fold a third into one of the two instead of drawing it.
- Stable IDs: a shape keeps its ID in every round and every option, and a dropped ID is never reused. The chosen sketch becomes the Stage 2 `layout.json` by editing, not redrawing.
- Render with the same script. Skip the checker and the asset list until Stage 2.

## `layout.json` is the source

Change `layout.json` first, then regenerate the PNG and the lists from it. Never record a layout change only as prose (a review note, a markdown file of changes): the checker, the blockout and lint read the JSON, so a prose-only change leaves them stale.

## Steps

1. **Grid and bounds** at real scale from the metrics. On the game routes, when the scene is walkable, read the `level-design` skill for player metrics, the critical path and readability. Use the kit grid from `modular-kit` (for example 0.5 m).
2. **Circulation.** Games: the player path, with door and corridor widths checked against the player height and camera (`check_layout.py`, step 11). CG: the hero shot cameras first (position, lens, aim), then only what they see. The cameras sit where they frame the scene logically; matching a photo's camera is only for `mode: camera_match` or `full_cg` (`brief.yaml`).
3. **Shapes** in the legend, each with an ID that becomes the asset or cluster ID later, and `z_m` for zones whose floor height differs (a step, a raised bay, a soffit as `[bottom, top]`).
4. **Focal points** numbered in the order the eye should find them, as red `callouts` with one line of text each. Add callouts for anything the blockout must get right that the shapes don't show, such as "left door set into its recess, mirrors D02".
5. **Paired elements.** Where the reference shows a symmetric pair (doors, frames, windows), give both shapes a `mirror_of` and say which axis they mirror across.
6. **Cable runs** in `runs`: each with an ID, `from` and `to` (a shape ID, or `frame_edge`), and a cable count. No run without two real ends.
   **Services network** from `plan/services.yaml` (supply, service head, meters, risers, runs, fittings): merge the `shapes` and `runs` that `check_inventory.py --layout-out` writes into `layout.json` (purple points for the nodes, purple strips for the runs), keeping the IDs from the file, so one ID names the same thing on the map, in the blockout and in lint.
7. **Notes** in `notes` for what a person would scribble on a plan: ceiling heights, "wires sag", "open to stair".

8. **Asset list** `plan/assets.yaml`: one row per unique asset with `source: model | library | generate | unreal_modeling`, legend colour, phase, budget tier, and the camera distance tier (hero, mid, far).
9. **Phase plan** `phases.md`: what goes in each of P0 to P9 for this scene (see `placement-phases`).
10. **Budgets** `budget.yaml`: only the caps the user gave at G0 (`brief.yaml › budgets`); write "no cap" for the rest. Texel density for games; render resolution and shot list for CG.
11. **Check** with `scripts/check_layout.py` on `plan/layout.json` before rendering: door and passage widths, risers and treads, headroom, and path clearance against the player metrics. Set `kind` (door, passage, stair, soffit) on those shapes, with `width_m`, `steps`, `riser_m`, `tread_m`, `clear_height_m` or `blocks` where the polygon can't show it: a kind guessed from the label only warns. Limits come from `plan/lint_rules.yaml` (flat keys or under `layout:`). Exit 1 is a blocker. Fix `layout.json` and rerun until it passes; render only then.
12. **Render** `plan/layout.png` from `plan/layout.json` with `scripts/render_layout.py` (headless Blender: `bash bin/blender-bg --python .claude/skills/layout-2d/scripts/render_layout.py -- projects/<slug>/plan/layout.json projects/<slug>/plan/layout.png`), so the map can be regenerated after edits.

```json
{"title": "Hotel corridor, level 3", "grid_m": 0.5, "shapes": [
  {"id": "F01", "legend": "white", "poly_m": [[0,0],[12,0],[12,2],[0,2]], "z_m": 0.0, "phase": 1},
  {"id": "W01", "legend": "white", "poly_m": [[0,2],[12,2],[12,2.15],[0,2.15]], "phase": 1},
  {"id": "D01", "legend": "red", "poly_m": [[3,1.9],[3.9,1.9],[3.9,2.0],[3,2.0]], "mirror_of": "D02", "phase": 2},
  {"id": "L03", "legend": "cyan",  "point_m": [6,1.2], "fixture": "sconce_1970s", "phase": 4}
], "runs": [{"id": "CB01", "from": "MT01", "to": "frame_edge", "count": 6}],
 "callouts": [{"n": 1, "at_m": [6,1.0], "text": "Sconce pool on the end wall, focal point 1"}],
 "notes": [{"at_m": [0.5,0.4], "text": "ceiling 2.6 m"}],
 "path": [[1,1],[11,1]], "cameras": [{"id": "CAM_A", "pos_m": [0.5,1,1.6], "aim_m": [12,1,1.4], "lens_mm": 24}]}
```

## Output

`plan/layout.json`, `plan/layout.png`, `plan/assets.yaml`, `phases.md`, `budget.yaml`. Reviewed with the lighting brief at G1; the checker has passed before the render.
