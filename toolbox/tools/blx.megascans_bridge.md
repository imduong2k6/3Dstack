---
id: blx.megascans_bridge
kind: blender_extension
name: Megascans Bridge
version: "2.1.0"
checked: 2026-10-27
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/megascans_bridge/blender_manifest.toml
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/megascans_bridge/README.md
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/megascans_bridge/CHANGELOG.md
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/megascans_bridge/source/utils/prefs.py (preferences)
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/megascans_bridge/source/ops (operator ids)
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/config/userpref.blend (saved add-on preferences, read as text)
  - D:/Resources/Textures/quixel/Downloaded/assetsData.json (library index)
  - Z:/TextureLibrary/Quixel (second local Quixel folder)
  - https://b3dhub.github.io/addons/megascans-bridge
  - https://superhivemarket.com/products/megascans-bridge
  - https://forums.unrealengine.com/t/quixel-to-fab-transition-faqs/2033839
  - toolbox/tools/transfer.blender-unreal.md (bin/blender-bg runs with --factory-startup)
pipeline_stages: [modular-kit, set-dressing, texturing-handoff]
routes: [blender, blender_unreal]
---

# Megascans Bridge

**What it does:** A third-party (B3dHub, not Epic) Blender add-on that lists and imports Megascans assets you have already downloaded with Quixel Bridge: 3D assets and plants (with LODs and LOD groups), surfaces as materials or node groups, decals, brushes, atlases. It does not download anything.

## Use it for
- Stage 4 library pulls on the Blender routes: surfaces for material groups, scanned rocks, plants and props for set dressing (P5 to P9), imported at real scale for the camera distance.
- Texture sources for the hand-off brief; on `blender_unreal` materials are rebuilt in Unreal from `material_group`, not carried over from here.

## How to call it
- UI only. Sidebar (N panel) tab "M-Bridge" in the 3D View, with a grid, search and pagination; click Import. Surfaces import as a material (Shift adds it to the material list); there are also Shader Editor and Texture Paint (brushes) entry points.
- Operators exist (`mbridge.asset_add`, `mbridge.surface_add`, `mbridge.plant_add`, `mbridge.decal_group_add` and others) but are marked INTERNAL and read the panel's asset list from `scene.mbridge`. They are not designed for scripts; I did not test them through `execute_blender_code`.
- Not available in `bin/blender-bg` runs, which use `--factory-startup` (extensions are not loaded).

## Settings that matter
- Preferences > Library > Path: must contain `assetsData.json`. Add-on default `~/Documents/Megascans Library/Downloaded/`; on this machine it is set to the D: path under Gotchas. Without that file the panel shows a "download some assets" message.
- Size (default 4K; 1K, 2K, 4K, 8K), Model > Format (FBX default, or ABC), Import all LODs (off by default), LODs (default LOD0, LOD2, LOD4, LOD6). Pick the lowest LOD and size the camera distance needs.

## Gotchas
- Local check: the saved Library path in Blender's user preferences is `D:\Resources\Textures\quixel\Downloaded\` (read from `userpref.blend`). It exists, holds `assetsData.json` (327 assets: 198 3d, 94 surface, 29 atlas, 6 3dplant) and about 33 GB in folders `3d`, `3dplant`, `DHI`, `atlas`, `brush`, `surface`. The default `~/Documents/Megascans Library` does not exist. A second, unrelated Quixel folder sits at `Z:/TextureLibrary/Quixel` (382 asset folders, no `assetsData.json`); the add-on does not read it.
- Source of content: Quixel Bridge is still available but "will eventually be sunset"; assets acquired there keep their original licence and get no updates. Fab has no one-click export to Blender, so Fab-only downloads do not land in this add-on's library.
- Content licence: legacy Quixel terms for old claims; Fab Standard License for free promotion claims (usable in any tool or engine). The add-on itself is GPL-2.0-or-later and sold on Superhive (price not read).
- Python wheel: Pillow (cp313 wheels listed in the manifest).
- Megascans files are third-party content: do not commit them (public repo rule).

## Don't use it for
- Getting new Megascans: download via Fab or Bridge first.
- Route `unreal`: use the Fab window (`ue.fab`).

## Version notes
- 2.1.0: adds `abc` model support and a Gamma node; EXR is tried before JPG when both exist (local CHANGELOG, "Changed: EXR format prioritization"). Blender minimum 4.2.0; no 5.2-specific note found.
