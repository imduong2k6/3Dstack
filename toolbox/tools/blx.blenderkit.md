---
id: blx.blenderkit
kind: blender_extension
name: Blendkit (BlenderKit) Online Asset Library
version: "3.21.2-260917"
checked: 2026-10-27
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/blenderkit/blender_manifest.toml
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/blenderkit/__init__.py (bl_info)
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/blenderkit/client (bundled client binaries)
  - C:/Users/Admin/blenderkit_data (local data folder)
  - https://github.com/BlenderKit/blenderkit
  - https://github.com/BlenderKit/BlenderKit/wiki
  - https://www.blendkit.com/faq-frequently-asked-questions/
  - https://www.blenderkit.com/plans/pricing/
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/config/userpref.blend (saved add-on list, read as text)
  - toolbox/tools/transfer.blender-unreal.md (bin/blender-bg runs with --factory-startup)
pipeline_stages: [modular-kit, set-dressing, texturing-handoff]
routes: [blender, blender_unreal]
---

# Blendkit (BlenderKit) Online Asset Library

**What it does:** Blender add-on for searching, downloading, rating and uploading assets from the community library (models, materials, scenes, HDRIs, brushes) by drag and drop. The project now brands itself Blendkit (blendkit.com, "formerly known as BlenderKit"); the extension id and code still say `blenderkit`.

## Use it for
- Stage 4 library pulls on Blender routes: props, materials and HDRIs for set dressing (P5 to P9) and texture sources for material groups, when Poly Haven (`bl.polyhavenassets-1.2`) or the Megascans library has no match.
- Reference-grade stand-ins during blockout review, replaced by built kit pieces later.

## How to call it
- UI: sidebar (N panel) in the 3D View, tab "Blendkit" (bl_info: "View3D > Properties > Blendkit"). Search, pick an asset, drag it into the scene.
- It starts a background client process (`bk_client-windows-x86_64.exe`, bundled client versions v1.7.0 to v1.12.13 under `client/`) that does the network transfer, and keeps a local data folder (`C:/Users/Admin/blenderkit_data` exists with a `client` and `config` folder).
- I found no documented Python or MCP interface. Drive it from the UI, and import the downloaded files with the normal Blender import path if scripting is needed.
- Not loaded in `bin/blender-bg` (it runs `--factory-startup`).

## Settings that matter
- The manifest declares network access ("Search and download from blendkit.com") and file access ("Import and export assets").
- Asset licence per item: check Royalty Free (RF) versus CC0 before the asset goes into a deliverable.
- Log in only through the user's own session: agents must not sign in. Free accounts can bookmark and rate; the Full plan unlocks the whole library and gives 2 GB of private storage.

## Gotchas
- Plans: Free is free and gives a subset of the library; Full was listed at about $9 per month on the pricing page (snippet, date unverified). The free-plan asset limit was not stated anywhere I could read.
- Licence terms (FAQ): Royalty Free assets can be used commercially, but the assets themselves cannot be sold; materials in your own models can. Attribution and game-engine redistribution rules are on the Licenses pages, which I did not read. Check them for assets that ship in a game.
- Scale is not guaranteed: verify against `plan/metrics.yaml`, and rebuild materials from `material_group` for the Unreal transfer.
- Local check: `bl_ext.user_default.blenderkit` is enabled (confirmed in the live Blender on 2026-10-28 (Python 3.13.13)), and the saved global asset directory is `C:/Users/Admin/blenderkit_data` (both read from `userpref.blend`).
- This repo is public: do not commit downloaded assets.
- The add-on ships its own client executable; if searches or downloads fail, check that a firewall is not blocking it.

## Don't use it for
- Anything that must be built to spec (kit pieces with pivots, sockets, collision).
- Route `unreal`: use the Fab window (`ue.fab`); the FAQ links a separate "Blendkit for Unreal" integration that I did not review.

## Version notes
- Installed 3.21.2 (build 2026-09-17), Blender minimum 3.0.0. I found no published changelog for this build (GitHub Releases is empty).
- Branding is now Blendkit; blenderkit.com redirects (301) to blendkit.com. Wiki and issue tracker remain on GitHub under BlenderKit.
