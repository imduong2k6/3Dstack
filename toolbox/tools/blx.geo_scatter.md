---
id: blx.geo_scatter
kind: blender_extension
name: Geo-Scatter
version: "5.6.4"
checked: 2026-10-27
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/geo_scatter/blender_manifest.toml
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default/geo_scatter/gpl_script (operator ids, tab_name preference)
  - https://www.geoscatter.com/documentation
  - https://www.geoscatter.com/docs-installation.html
  - https://www.geoscatter.com/docs-scattering.html
  - https://www.geoscatter.com/docs-changelogs.html
  - https://superhivemarket.com/products/scatter
  - docs/pipeline/routes.md
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/config/userpref.blend (saved add-on list, read as text)
  - toolbox/tools/transfer.blender-unreal.md (bin/blender-bg runs with --factory-startup)
pipeline_stages: [placement-phases, set-dressing]
routes: [blender, blender_unreal]
---

# Geo-Scatter

**What it does:** A paid Blender scattering system built on Geometry Nodes: scatter instances over surfaces by density, preset or biome, paint them by hand (Manual), drop them with physics, and drive density, scale and rotation with masks, slope, altitude, proximity and wind. Each scatter system is an object with a geometry-node modifier ("GEO-SCATTER ENGINE").

## Use it for
- P9 life and nature and P7 clutter on route `blender` (CG): grass, rocks, debris, ground cover, forests, building only what the cameras see.
- Dressing a Blender-side blockout before the transfer on `blender_unreal`, when instance counts are modest (see Gotchas).

## How to call it
- UI: after enabling, a sidebar tab in the 3D View (name is a preference, default from the plugin name, "Geo-Scatter") with Create and Tweak panels. Create operators: Add (random, 0.2/m2), Density Scatter (per m2, cm2, ha, km2), Preset Scatter, Biome Scatter (library of .scatpack biomes), Manual Scatter (brush mode), Quick Scatter (pie menu, Shift+Ctrl+Alt+W), Physics mode.
- Operator ids in the installed source: `scatter5.add_psy_simple`, `add_psy_density`, `add_psy_preset`, `add_psy_manual`, `add_psy_physics`, `add_biome`. They depend on the add-on's own context (emitter, surfaces); there is no published scripting API in what I read, so drive it from the UI and use Blender MCP screenshots to check results. I did not call these through `execute_blender_code`.
- Not loaded in `bin/blender-bg` (factory startup); use the live Blender.
- Biomes install from `.scatpack` files via the plugin manager ("Install a Scatter Package"); biomes without a .blend need their asset folder under Preferences > Filepaths > Asset libraries.

## Settings that matter
- Surface(s) in Tweak > Surface; Material ID culling (5.6) restricts scattering to chosen material faces.
- Density in real units; for big terrains start low. Optimization panel: FOV and distance culling, viewport placeholders.
- Remove a system with the minus icon in the system list, not by deleting objects or collections in the Outliner.

## Gotchas
- Large surfaces freeze the viewport at high density; abiotic curvature and vertex-group painting are slow on high-poly surfaces.
- Route `blender_unreal`: `transfer/layout.json` needs one row per placed instance (routes.md). Scatter output is modifier-generated, and how to export per-instance transforms is not covered in the docs I read. Either keep scatter for Blender-only renders, or rebuild it in Unreal with PCG (`ue.pcg`) from the same density rules.
- Licence is paid: Individual $99 (1 user), Team $299 (2 to 6), Studio $899 on Superhive; the manifest says code is GPL and the node assets are under the vendor EULA (geoscatter.com/legal). The installed manifest says "Individual License": check that it covers the intended use.
- Local check: `bl_ext.user_default.geo_scatter` is enabled (confirmed in the live Blender on 2026-10-28 (Python 3.13.13)). Its manifest wheels are Python 3.13 builds (pybullet cp313), matching Blender 5.2.
- Install docs conflict on the panel location ("T" panel versus Scatter N panel): check the tab in your build.
- Scatter assets used for stills are third-party; do not commit .blend or asset files (public repo).

## Don't use it for
- Route `unreal`: use PCG. Hero props placed by hand. Tiny scenes where a Geometry Nodes scatter in the `geometry-nodes` skill is enough.

## Version notes
- 5.6.4 (17 July 2026) targets Blender 5.2 LTS: fixes serious geometry-node API breakages from Blender 5.2, supports 5.2's compact tab; accepts systems made with 5.0 to 5.6. This is the installed version.
- 5.6.0 changes that alter old results: material culling now culls surface polygons rather than points; instance-by-probability uses a count not a percentage; the `ins_col` collections are no longer used. 5.6 added Physics mode and a rebuilt instancing engine.
