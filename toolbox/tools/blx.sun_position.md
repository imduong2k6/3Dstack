---
id: blx.sun_position
kind: blender_extension
name: Sun Position
version: "4.0.2"
checked: 2026-10-29
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/blender_org/sun_position/blender_manifest.toml and README.md
  - https://docs.blender.org/manual/en/latest/addons/lighting/sun_position.html
  - Online docs not fetched this run (local descriptors only); verify before relying on version-specific detail.
pipeline_stages: [lighting-brief, lighting-passes]
routes: [blender]
---

# Sun Position

**What it does:** Positions a Sun light or Sky texture from latitude, longitude, date and time.

## Use it for
- Blender Cycles route: set the key light direction from the researched place and time of day.

## How to call it
- World properties or the 3D viewport sidebar > Sun Position; Sun + Sky or HDRI mode; enter location and time.

## Settings that matter
- Set the north offset to match the layout; keep the fixed exposure (`house-rules` 8).

## Gotchas
- Not for Unreal (use Sky Atmosphere and Directional Light per the lighting brief).
- Check timezone and scene units before trusting the angle.

## Don't use it for
- Interior scenes lit only by practicals.

## Version notes
- Checked against 4.0.2 on the author's PC (2026-10-29).
