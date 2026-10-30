---
name: detail-inventory
description: "Turn the tagged references into plan/inventory.yaml (per zone and wall: feature, count, size, mount, reference crop, source) and plan/services.yaml (the connected network of supply, service head, meters, risers, runs and fittings, with anchors and heights). Lane briefs quote their rows, set-dressing density comes from the counts, and check_inventory.py counts tagged objects against them. Use it in Stage 1, before the layout and the blockout, unless brief.yaml detail is massing."
---

# Detail inventory

On an earlier project the detail research and the electrical blueprint arrived after the first blockout review: 32 missing items, 13 contradictions with the renders, 149 service components. The blockout was built twice, and a conduit kit was sized from an AI image (45 mm; real conduit runs 20 to 32 mm). Studios break the concept into components before they build. This skill does that once, up front, and keeps the result as the file everything else counts against.

Runs unless `brief.yaml › detail` is `massing` (`scene-pipeline` has the table). Inputs: `refs/index.yaml` with roles (`hero`, `target`, `measure`, `form`), the coverage matrix in `plan/input-review.md`, `plan/metrics.yaml` and `plan/research.md` (`reference-research`).

## Inventory

1. **Zones and walls.** From the coverage matrix, give every area and every wall or surface an ID (`Z1`, `Z1.W_left`). `layout-2d` keeps these IDs as shape IDs, so one ID names the same place in the inventory, on the map, in the blockout and in lint.
2. **Walk each reference** (hero and target first, then the others) and list every feature it shows, zone by zone and wall by wall: fixtures, openings, signs, vents, units, brackets, loose items. One row per feature type per wall or zone, with `id` (`<zone>.<wall>.<slug>`), `feature`, `class` (`fixture`, `surface` or `dressing`), `count`, `size_m`, `mount`, `height_m`, `ref`, `source`, `phase` and `confidence` (`templates/inventory.yaml`).
3. **Count what you can see.** When the frame cuts a row off, write a range (`[4, 6]`), mark it `inferred` or `assumed`, and say why in `note`. Counting is the point: "a few vents" is not a row.
4. **Size from an anchor.** Measure against something of known size in the same image (a door leaf, a step) and write that in `source`. A size that sets a kit family's scale (repeated 10 or more times, such as conduit, pipe, door leaf) needs a `plan/metrics.yaml` row with `role: kit_scale` and a real source before any spec uses it (`reference-research`). An AI image never sizes anything (`house-rules` rule 11).
5. **Crop it.** Save the reference crop for each row to `<work_dir>/refs/crops/<row id>.png` and set `ref.crop` and `ref.image`. Crops stay in the work folder; `refs/index.yaml` keeps the source link (`CLAUDE.md`: no third-party photos in the repo).
6. **Contradictions.** Where a render or concept disagrees with a real photo, the photo wins; log the pair in `plan/inventory-notes.md` so the user can overrule it at G1.
7. **Wear is not a row.** Grime, stains, rust and the like go to `handoff/wear-notes.md` (`house-rules` rule 1).

## Services

Build `plan/services.yaml` for everything that is connected: electric, cable and data, water and drain, AC. One network per kind (`templates/services.yaml`).

- Chain: **supply → service head → meters → risers → distribution → runs → fixtures**, in that order, with fittings (elbows, tees, boxes, brackets) on the runs. Arrange it the way the references do (meter boards grouped at stair entries, conduit vertical and horizontal, bundles sagging between brackets).
- Every node has an anchor `at_m: [x, y, z]` with its height. Every run has two real ends, a `by` (conduit, tray, cable, pipe, duct), a count, and a size that is a `metric:` key from `metrics.yaml` or a `dia_mm` with a `source`. A fixture a network doesn't reach is an error: a lamp needs a conduit, a sink a pipe.
- A node that fulfils an inventory row names it in `inv`.
- Stage 2: `layout-2d` draws the network as purple shapes with these IDs (`check_inventory.py --layout-out` writes the shapes and runs to merge into `layout.json`).

## Check

```
P=projects/<slug>
python .claude/skills/detail-inventory/scripts/check_inventory.py $P/plan/inventory.yaml --services $P/plan/services.yaml \
  --metrics $P/plan/metrics.yaml --refs $P/refs/index.yaml --work-dir <work_dir> --out $P/plan/inventory-check.json
```

Blockers (schema, an unconnected node, a run size with no source) must be fixed before G1. The summary prints each zone's counts and `dressing_per_m2`. `scripts/selftest_inventory.py` tests it (plain Python, and counting under `bin/blender-bg`).

## Who uses it

- **Lane briefs** (`lane-integration`) quote their zones' rows and runs, and the lane tags every object it builds with the row ID in the custom property `inv_id` (instances carry it in the manifest `props`).
- **Set-dressing** takes its density from the `dressing` counts per zone and `dressing_per_m2`, not from a feeling for how busy the mood is.
- **The worker**, right after `scene-lint`, counts tagged objects against the rows due at the current phase (scene-lint doesn't count them): `check_inventory.py $P/plan/inventory.yaml --blend <gate copy.blend> --upto P3 --fail-on major --out $P/reviews/<gate>-r<n>/inventory-count.json` (headless, on a copy). A due row with the wrong count is a major, a tag with no row a minor; the supervisor reads the file like `lint.json`.
- **G1** shows the user the counts per zone and the contradiction notes. Later findings add rows (with a `log.md` line); a row is never deleted because it was built.
