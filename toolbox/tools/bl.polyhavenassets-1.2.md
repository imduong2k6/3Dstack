---
id: bl.polyhavenassets-1.2
kind: blender_addon
name: Poly Haven Assets
version: "1.2.3"
checked: 2026-10-27
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/scripts/addons/polyhavenassets-1.2.3/__init__.py (bl_info)
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/scripts/addons/polyhavenassets-1.2.3/README.md
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/scripts/addons/polyhavenassets-1.2.3/operators (pha.* operator ids)
  - Z:/TextureLibrary/Poly Haven (local library folder)
  - https://docs.polyhaven.com/en/guides/blender-addon
  - https://superhivemarket.com/products/poly-haven-asset-browser
  - https://polyhaven.com/license
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/config/userpref.blend (saved add-on list, read as text)
  - toolbox/tools/transfer.blender-unreal.md (bin/blender-bg runs with --factory-startup)
pipeline_stages: [modular-kit, set-dressing, lighting-passes, texturing-handoff]
routes: [blender, blender_unreal]
---

# Poly Haven Assets

**What it does:** Official Poly Haven add-on that lists every Poly Haven HDRI, material (texture) and 3D model in Blender's Asset Browser and downloads them on demand, with helpers for resolution and LOD switching, real-world texture scale, one-click displacement, and HDRI rotation, brightness and white balance. Installed as a legacy add-on under `scripts/addons`; needs Blender 4.5+.

## Use it for
- Stage 4 library pulls on Blender routes: CC0 props, surface materials and foliage for set dressing (P5 to P9), kit-piece stand-ins, and texture sources for material groups.
- Lighting: HDRIs for sky and reference lighting checks on route `blender` (Cycles) when the lighting brief calls for them.
- Quick placeholders on `blender_unreal` that go through the normal FBX transfer; materials are rebuilt in Unreal from `material_group`, not carried over.

## How to call it
- Setup: in Preferences add an Asset Library named exactly "Poly Haven" (the add-on looks it up by that name; the preferences location moved in Blender 5.2, so find the Asset Libraries list there), open the Asset Browser, pick that library, click Fetch Assets, then drag assets into the scene. Sidebar panels offer the per-asset tools.
- Operators in the install: `pha.pull_from_polyhaven`, `pha.resolution_switch`, `pha.lod_switch`, `pha.tex_scale_fix`, `pha.tex_displacement_setup`, `pha.cancel_download`. They work on assets and context from the Asset Browser UI; not tested via `execute_blender_code`.
- For one-off pulls the Blender MCP server's own `search_assets` and `import_asset` also list Poly Haven (per its server instructions), without the add-on's full library.
- Not loaded in `bin/blender-bg` (it runs `--factory-startup`).

## Settings that matter
- Import method: set to "Append". In Blender 5.0 the default changed to "Pack", which makes assets uneditable and can hide the Poly Haven panel (Superhive notes).
- Resolution: assets import at 1K by default; switch up per asset only when the camera is close. "Fix Texture Scale" sets the real-world mapping multiplier.

## Gotchas
- First sync is large: README says about 3.3 GB, the Superhive page says about 12 GB for the low-resolution set. Plan for the larger number.
- Local check: the add-on is installed but not enabled, and there is no asset library named "Poly Haven" (confirmed in the live Blender on 2026-10-28 (Python 3.13.13)).
- Local check: `Z:/TextureLibrary/Poly Haven` exists (3.4 GB; categorised HDRIs, Models, Textures; no `blender_assets.cats.txt` seen), which looks like a manual download rather than this add-on's library.
- Needs an internet connection for downloads. Poly Haven's terms forbid scraping the site; use the add-on or the published API within its terms.
- Do not commit downloaded assets or textures to this public repo (CC0 would allow it; the repo rule keeps binaries out).

## Don't use it for
- Anything that must match a reference photo exactly: these are generic assets.
- Route `unreal`: import the files with Unreal's importer or the Fab window instead.

## Version notes
- Licence: add-on is GPL, paid ($49 on Superhive, raised from $30 in November 2025; $5/month on Patreon). Assets are CC0, commercial use allowed, no attribution needed.
- 1.2.2 (14 July 2026) fixes Blender 5.2, where asset library preferences moved; 1.2.3 (20 July 2026) fixes an ImportError on in-place updates. 1.2.0 requires Blender 4.5+ and replaced particle grass with Geometry Nodes assets. Installed 1.2.3 is the latest listed.
