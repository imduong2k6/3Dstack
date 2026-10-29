---
id: blx.kritskiy_cablerator
kind: blender_extension
name: Cablerator
version: "1.4.9"
checked: 2026-10-29
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/kritskiy_cablerator/blender_manifest.toml
  - https://cablerator.readthedocs.io/en/latest/ (manifest website)
  - Online docs not fetched this run (local descriptors only); verify before relying on version-specific detail.
pipeline_stages: [geometry-nodes, placement-phases (P3 services), set-dressing]
routes: [blender, blender_unreal]
---

# Cablerator

**What it does:** Creates cables between two faces or along edges and curves, with connectors and a geometry-nodes cable mode.

## Use it for
- P3 service cables on the Blender route; hanging cables between buildings.

## How to call it
- Add > Create Cable, or Shift+Alt+C menu. Modes: draw, from edge, from selected, split and recable.

## Settings that matter
- Prefer the geometry-nodes or curve cable so it stays editable and light; apply and instance only for export.

## Gotchas
- On the Unreal route cables use PCG and splines or ue.cablecomponent instead.
- Large cable counts: low bevel resolution, then check the tri budget.

## Don't use it for
- Unreal-side cables.
- Rope physics.

## Version notes
- Checked against 1.4.9 on the author's PC (2026-10-29).
