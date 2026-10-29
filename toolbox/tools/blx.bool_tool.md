---
id: blx.bool_tool
kind: blender_extension
name: Bool Tool
version: "2.0.0"
checked: 2026-10-29
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/blender_org/bool_tool/blender_manifest.toml
  - https://github.com/nickberckley/bool_tool (manifest website)
  - Online docs not fetched this run (local descriptors only); verify before relying on version-specific detail.
pipeline_stages: [modeling, modular-kit]
routes: [blender, blender_unreal]
---

# Bool Tool

**What it does:** Quick boolean cut, slice and union tools for hard-surface modelling.

## Use it for
- Window and door openings in kit pieces, panel cuts.

## How to call it
- Object or Edit mode shortcuts and the add-on panel; see its keymap in Preferences.

## Settings that matter
- Keep cutters as modifiers until the piece is approved, then apply before export.

## Gotchas
- Booleans leave n-gons and non-manifold edges: run the blender-adapter validation before FBX export.
- Applying booleans breaks custom normals; redo the bevel and normal step.

## Don't use it for
- Organic shapes.

## Version notes
- Checked against 2.0.0 on the author's PC (2026-10-29).
