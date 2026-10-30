---
id: bl.tripo3d_blender_bridge
kind: blender_addon
name: Tripo Bridge
version: "1.0.34"
checked: 2026-10-29
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/scripts/addons/Tripo3d_Blender_Bridge/__init__.py (bl_info)
  - https://www.tripo3d.ai/blog/tripo-dcc-bridge-for-blender (bl_info doc_url)
  - skill tripo-props
  - Online docs not fetched this run (local descriptors only); verify before relying on version-specific detail.
pipeline_stages: [generated-asset, tripo-props, modeling]
routes: [blender, blender_unreal]
---

# Tripo Bridge

**What it does:** Receives meshes sent from Tripo Studio ('Send to Blender') over the DCC Bridge; sidebar panel View3D > Tripo Bridge. Paid service; the scanner never signs in.

## Use it for
- Detailed placeholder props in `full_cg`, or when `brief.yaml › detail` is not `massing` (assets.yaml source generate).

## How to call it
- View3D sidebar > Tripo Bridge, start the bridge, then 'Send to Blender' in Tripo Studio (browser, driven by the user).
- Follow skill tripo-props for crops, clean-up, scale and pivot.

## Settings that matter
- Imported mesh arrives at arbitrary scale and orientation: fix to spec size and pivot, run an orientation check before the Modeler.

## Gotchas
- Generated meshes are never final; the Modeler repairs to spec.
- Needs a Tripo account and credits; keep keys out of the repo.
- If 'Send to Blender' stalls (the export starts, nothing imports; seen 2026-10-29): in the browser open the top-bar DCC Bridge panel in Tripo Studio, switch Blender on, check it says Connected, then resend. Downloading GLB files is the last resort and needs the user's OK.

## Don't use it for
- Hero assets or measured routes (use blender-image-to-3d).

## Version notes
- Checked against 1.0.34 on the author's PC (2026-10-29).
