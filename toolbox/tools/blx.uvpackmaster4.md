---
id: blx.uvpackmaster4
kind: blender_extension
name: UVPackmaster 4
version: "4.1.0"
checked: 2026-10-27
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/uvpackmaster4/blender_manifest.toml
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/uvpackmaster4/__init__.py (bl_info)
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/uvpackmaster4/spipeline/operators (operator ids)
  - C:/Program Files/UVPackmaster/engine4 (installed engine, release-4.1.0.uvpmi)
  - https://uvpackmaster.com/
  - https://uvpackmaster.com/doc4/blender/latest/
  - https://uvpackmaster.com/for-blender/release-notes-v4/
  - https://superhivemarket.com/products/uvpackmaster/
  - https://www.cgchannel.com/2026/01/uvpackmaster-4-for-blender-is-out/
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/config/userpref.blend (saved add-on list, read as text)
  - toolbox/tools/transfer.blender-unreal.md (bin/blender-bg runs with --factory-startup)
pipeline_stages: [modeling, modular-kit, texturing-handoff]
routes: [blender, blender_unreal]
---

# UVPackmaster 4

**What it does:** A UV island packer for Blender with a separate native packing engine (CPU, plus a GPU variant using Cuda and Vulkan). Packs one or many objects into one or more UV tiles with texel-density control, grouping, stacking of similar islands, and a UV-editor panel ("UV Editor > N panel > UVPackmaster4").

## Use it for
- Stage 4 kit pieces (`modular-kit`) and props (`modeling`): pack UVs to a consistent texel density across a kit so trim sheets and material groups line up.
- Packing many pieces into shared atlas tiles, or each material group into its own tile (modes Groups To Tiles, Groups Together, Groups Independently).
- Texel-density targets for the texturing brief (`texturing-handoff`): the texel density units setting defaults to px/m (px/cm, px/in, px/ft available). Apply TD (Packing), which sets density without packing, needs 4.1.1 or later; the installed 4.1.0 doesn't have it.

## How to call it
- UI: select the object in Edit Mode, select islands in the UV Editor, open the UVPackmaster4 tab, choose a Pack Mode and options, press Pack.
- Operator ids from the installed source: `uvpackmaster4.pack`, `uvpackmaster4.overlap_check`, `uvpackmaster4.measure_area`, `uvpackmaster4.select_similar`, `uvpackmaster4.align_similar`, `uvpackmaster4.group_by_similarity`, `uvpackmaster4.split_overlapping`, `uvpackmaster4.orient_to_3d_space`. They expect UV Editor context and run the engine as a separate process, so calling them from `execute_blender_code` needs a context override. Not tested here.
- Scripting hooks exist: scripts stored in the Text Editor can run before or after an operation (docs "Scripting" and "Running From A Script"), and 4.1 added an optional local AI assistant. Read those pages before automating.
- Not loaded in `bin/blender-bg` (factory startup); the engine also has to be reachable.

## Settings that matter
- Pixel Margin (set per texture size), Island Rotation Step, Normalize Scale, Heuristic Search (4.0.4: Advanced Heuristic Automatic is the default), Dynamic Tiles (4.0, the packer chooses how many tiles), Lock Overlapping, Stack Groups, Custom Target Box, Non-Square Packing.
- Keep one pixel-margin rule for the whole kit (decide it in the kit plan), so edge bleed is the same on every piece.

## Gotchas
- Local check: the add-on (4.1.0) and the engine (`C:/Program Files/UVPackmaster/engine4`, registry value `HKLM\Software\UVPackmaster\Engine4InstallPath`, release 4.1.0, `win/uvpm.exe` and a `vulkan` folder) are both installed and the versions match. Licence activation state was not checked and I did not run the engine.
- The add-on is GPL; the engine is under a separate vendor EULA (`EULA.rtf` in the engine folder). Paid: Superhive listed $55 single seat and $199 and $349 studio tiers; CG Channel (January 2026) reported $53 and $199. Prices may have moved.
- `bl_ext.user_default.uvpackmaster4` is enabled (confirmed in the live Blender on 2026-10-28 (Python 3.13.13)).
- UVPackmaster 3 data can be moved with Transfer V3 Options and Transfer V3 Object Data (4.0.3).
- Heavy UV maps and inconsistent islands have their own doc pages (Heavy UV Maps Handling, Inconsistent Islands Error Handling).

## Don't use it for
- Unwrapping (seams, projection): it only packs and aligns existing islands.
- Single simple meshes where Blender's built-in Pack Islands is good enough for the budget.

## Version notes
- Installed 4.1.0 adds a local AI assistant (off by default, no cloud) and non-ASCII names. 4.1.1 adds Apply TD (Packing), parametrised AI prompts and Auto Repacking for Pack To Others; 4.1.2 fixes UV selection detection for Auto Repacking on Blender 5.x. The installed version is behind both; whether 5.2 has other issues was not found.
- 4.0.0 (January 2026) introduced Dynamic Tiles, per-island texel density and the group layout mode for atlases.
