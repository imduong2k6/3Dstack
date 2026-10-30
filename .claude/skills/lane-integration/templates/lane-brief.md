# Lane brief: {{lane_id}}

Fill every field. Replace `{{...}}`. Send the filled brief to one agent. The agent works headless on its own part file (`bash bin/blender-bg`), never in the open Blender or Unreal (`house-rules` rule 2).

## Job

{{one paragraph: what this lane builds, for which zones and walls, to which detail level (`brief.yaml › detail`)}}

- Part file: `{{parts}}/{{lane_id}}/{{lane_id}}.blend`, collection `{{lane_collection}}`
- Manifest: `{{parts}}/{{lane_id}}/manifest.json` (instances only; see `templates/manifest.json`)
- Owned ID prefix: `{{PFX}}_`. Every object you make starts with it. Nothing outside your lane may.
- Bounding box you may build in (world, m): `{{[[x0,y0,z0],[x1,y1,z1]]}}`
- Freeze: `{{date and time}}`. Stop at that time, run your preflight, report. A change after the freeze is a new freeze.

## World frame

- Units metres, Z up, Y along `{{main axis}}`, origin at `{{what}}`. Object origins are placed as `{{rule, e.g. bottom centre of the footprint}}`; transforms applied.
- Floor datums (Z, m): `{{zone: z, ...}}`. Ceiling or soffit datums: `{{...}}`.

## Metrics (cite, don't re-derive)

Values from `plan/metrics.yaml`, by key:

| Key | Value | Used for |
| --- | --- | --- |
| `{{door_leaf_height_m}}` | `{{2.04}}` | `{{...}}` |

If you need a size that is not here, stop and ask. Do not take a size from an AI image.

## Materials

Use only these exact names; they exist in the gate file. Never create, rename or recolour one. A new material is a request to the manager.

`{{M_Name, M_Name, ...}}`

Every face has a material (no empty slot, no mesh without one). Guides and cutters are hidden from render.

## Naming and tags

- Names: `{{PFX}}_<Thing>_<nn>`. Instances: `{{PFX}}_<Master>_<nn>` (in the manifest).
- Custom properties on every object: `lane = "{{lane_id}}"`, `map_id` (layout shape ID), `phase`, `src`, and `inv_id` (the inventory row it fulfils).
- Visibility: `live` unless the brief says otherwise (`house-rules` rule 5). Never delete to hide.

## Seams

| Seam | Between | Where | Owner | Rule for the other lane |
| --- | --- | --- | --- | --- |
| `{{S01}}` | `{{lane_a}}` / `{{lane_b}}` | `{{wall W03, x 4.0 to 6.5}}` | `{{lane_a}}` | `{{stops 0 mm short, references the owner's piece, builds no copy}}` |

You build the seams you own. For the others, build up to the line and stop.

## What to build (quoted rows)

From `plan/inventory.yaml` (your zones and walls):

```yaml
{{rows}}
```

From `plan/services.yaml` (your runs, nodes and fittings, with anchors and heights):

```yaml
{{rows}}
```

Counts are the target. Report any row you could not match, with its cause.

## Standing rules

From `brief.yaml › standing_rules`, word for word:

- `{{date}}`: "{{the user's words}}" (from: {{chat | board}})

And the `house-rules` skill. In particular: no wear geometry (rule 1), detail over cost (rule 6), neutral light (rule 7).

## Report

Write `{{parts}}/{{lane_id}}/report.json` and stop. Results and evidence files only (`house-rules` rule 10).

```json
{"lane": "{{lane_id}}", "part": "...blend", "objects": 0, "instances": 0,
 "inventory": {"<inv_id>": {"expected": 0, "built": 0, "note": ""}},
 "materials_used": ["..."], "preflight_report": "path to the join report from your scratch copy",
 "captures": ["paths"], "not_done": ["..."], "questions": ["..."]}
```

Preflight: run `integrate_parts.py` on a scratch copy of the gate file with your lane. It must print `JOIN OK` before you report.
