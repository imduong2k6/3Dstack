# Fix lane brief: {{lane_id}}

Fill every field. Replace `{{...}}`. Send the filled brief to one `modeler` agent. It works headless on copies (`bash bin/blender-bg`), never in the open Blender (`house-rules` rule 2).

## Job

Write and test the fixes below as patches. You don't change the gate or the live file: the live worker replays your patches after the merge test.

- Gate copy to start from: `{{gate copy}}` (read-only; copy it, never save over it)
- Patch file: `{{parts}}/{{lane_id}}/patches.py`
- Test file: `{{parts}}/{{lane_id}}/test.blend`
- Round's lint: `{{projects/<slug>/reviews/<gate>-r<n>/lint.json}}`
- Fix cameras: `{{projects/<slug>/reviews/<gate>-r<n+1>/fix_cams.json}}`

## Your items

Keep each item's ID. Fix only these. Anything else you notice goes in the report.

| ID | What's wrong (from the fix list, word for word) | Objects you own |
| --- | --- | --- |
| `{{F03}}` | `{{...}}` | `{{names, or a bounding box [[x0,y0,z0],[x1,y1,z1]]}}` |

## Seams

| Object or place | Other lane | Owner | Rule for the other lane |
| --- | --- | --- | --- |
| `{{...}}` | `{{...}}` | `{{...}}` | `{{doesn't touch it; names it as a reference only}}` |

An object that isn't yours stays as it is. If your fix needs it changed, say so in the report. The merge test refuses an object two lanes both changed.

## Patches

One `@patch` per fix (`{{F03}}`, then `{{F03_2}}` when an item needs more than one). Example:

```python
@patch("F03", lane="{{lane_id}}", note="vent 2 sits 4 cm higher than the first, as in the reference")
def _(bpy):
    bpy.data.objects["NO_Vent_02"].location.z = 2.14
```

- Find objects with `bpy.data.objects["name"]`, so a wrong name fails instead of doing nothing.
- **Set** values. Never add to one (`location.x += 0.1`, or moving vertices by an offset): each patch runs twice and a second run that changes anything fails.
- A new object is get-or-create by name, with the names and tags in the naming rules, and every face has a material. Anything a patch creates every time it runs (a mesh, a curve) leaves `.001` data, which fails too.
- Use only materials that are already in the gate file. Never touch kit masters, the palette, cameras, lights or exposure: those items aren't in a fix lane. Editing a mesh that several objects share changes all of them, so it fails as an overlap or as somebody else's object.
- No wear as geometry (`house-rules` rule 1). No colour, contrast or light changes while lighting is frozen (rule 7).

## Test before you report

Start from a fresh copy of the gate each time:

```
cp "{{gate copy}}" "{{parts}}/{{lane_id}}/in.blend"
bash bin/blender-bg "{{parts}}/{{lane_id}}/in.blend" --python .claude/skills/lane-integration/scripts/integrate_parts.py -- replay --parts "{{parts}}" --lanes {{lane_id}} --out "{{parts}}/{{lane_id}}/test.blend"
bash bin/blender-bg "{{parts}}/{{lane_id}}/test.blend" --python .claude/skills/scene-lint/scripts/lint_blender.py -- --project projects/{{slug}} --out "{{parts}}/{{lane_id}}/lint" --baseline "{{round's lint.json}}"
```

- It must print `REPLAY OK` with no `NOOP`. A `NOOP` means the patch changed nothing the test reads (transforms, materials, visibility, mesh or curve points, parent, collections, custom properties, the modifier list): fix it, or say in the report why it's right.
- The `NEW` line must show no blocker or major from your objects.
- Look at each item with its camera from the fix cameras, in Workbench (one GPU renders one thing at a time well, so keep Cycles out of the lane).

## Standing rules

From `brief.yaml › standing_rules`, word for word:

- `{{date}}`: "{{the user's words}}" (from: {{chat | board}})

And the `house-rules` skill.

## Report

Write `{{parts}}/{{lane_id}}/report.json` and stop. Results and evidence files only (`house-rules` rule 10).

```json
{"lane": "{{lane_id}}", "patches": "...patches.py", "replay_report": "...test_replay.json", "lint": "...lint/lint.json",
 "fixed": {"<id>": {"objects": ["..."], "render": "path", "note": ""}},
 "not_fixed": {"<id>": "why"}, "noticed": ["..."], "questions": ["..."]}
```
