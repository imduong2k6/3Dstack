---
id: blx.gscatter
kind: blender_extension
name: Gscatter (Graswald)
version: "0.12.0"
checked: 2026-10-27
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/gscatter/blender_manifest.toml
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/gscatter/README.html
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/gscatter/common/ui.py and asset_manager/ops (panel and operator ids)
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/config/userpref.blend (saved add-on list, read as text)
  - https://blenderartists.org/t/graswald-gscatter-v0-12-1-fixes-for-blender-5-2/1652019
  - https://blenderartists.org/t/having-issues-with-installing-gscatter-0-12-0-python-3-11-on-blender-5-1-python-3-13/1639348.md
  - https://bazaar.blendernation.com/listing/gscatter-by-graswald/
  - toolbox/tools/transfer.blender-unreal.md (bin/blender-bg runs with --factory-startup)
pipeline_stages: [placement-phases, set-dressing]
routes: [blender, blender_unreal]
---

# Gscatter (Graswald)

**What it does:** Graswald's free scattering add-on built on Blender geometry nodes: scatter any object or collection over a surface and tune density, scale, rotation and effect layers, with an asset manager for Graswald's own (partly paid) plant libraries. GPL-3.0-or-later.

## Use it for
- Free alternative to `blx.geo_scatter` for P7 clutter and P9 ground cover, grass and plants on Blender routes, when a simple scatter system is enough.
- Dressing a Blender blockout before the transfer on `blender_unreal`. Instances are modifier-generated, so the layout.json caveat in `blx.geo_scatter` applies.

## How to call it
- UI: 3D View sidebar tab "GScatter" (panels include Info, with a What's new link). Pick a surface, select assets or an object/collection, then Scatter Selected (Ctrl+click scatters each selected object separately).
- Operator ids in the installed source: `gscatter.scatter_selected`, `gscatter.add_to_scene`, `gscatter.install_assets`, `gscatter.download_free_asset`, `gscatter.graswald_asset_library`, `gscatter.refresh_library`. They read the add-on's own library state, and there is no documented scripting API; not tested via `execute_blender_code`.
- Not loaded in `bin/blender-bg` (it runs `--factory-startup`).

## Settings that matter
- Networking follows Blender's Allow Online Access (`bpy.app.online_access`); the Info panel only shows when it is on. The manifest declares network use for "Updates, Downloads, Anonymous Tracking". Blender's Allow Online Access is the switch for this; I did not verify that the add-on honours it for tracking.
- Asset downloads go to the add-on's library folder (set in its preferences); the manifest says it installs, loads and saves Graswald assets, presets and node groups.

## Gotchas
- Version risk on this machine: the installed 0.12.0 bundles Pillow wheels for Python 3.11 only (manifest), while Blender 5.2 runs Python 3.13 (`python313.dll`). Users report the exact install error "This Python version (3.13) isn't compatible with (3.11)" on Blender 5.1, and a Blender 5.2 LTS build (0.12.1) with new Pillow wheels and repaired node-tree connections was posted on Blender Artists by a community member (Dropbox link, not Graswald's site; treat as unofficial).
- Local check: `bl_ext.user_default.gscatter` does not appear in the saved preferences (`userpref.blend`), where the other installed extensions do, and `extensions/.local/lib` has only `python3.11` site-packages. It is not enabled (confirmed in the live Blender on 2026-10-28 (Python 3.13.13)).
- Free tool, but some Graswald assets are sold separately (store.gscatter.com); check each asset's licence.
- Do not commit downloaded Graswald assets to this public repo.

## Don't use it for
- Anything on 5.2 until the Python 3.13 issue is settled (see above); use Geo-Scatter or geometry nodes (`geometry-nodes` skill) meanwhile.
- Route `unreal`: use PCG.

## Version notes
- Installed 0.12.0. 0.12.1 (community post, 3 September 2026) targets Blender 5.2 LTS: new Pillow wheels, repaired NodeTree connections, working Invert for Translate/Rotate/Scale/Grayscale, shared Mixer/Visualizer node groups, and an Extras function to consolidate node groups for systems made in Blender 5.1 or earlier. I found no official changelog from Graswald.
