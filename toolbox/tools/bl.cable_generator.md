---
id: bl.cable_generator
kind: blender_asset_file
name: GG Cable Generator (the user's own rig)
version: "1.1"
checked: 2026-10-29
sources:
  - E:/Resources/3D Assets/.blend/GG_Cable_Gen_v1-1.blend
pipeline_stages: [placement-phases]
routes: [blender, blender_unreal]
---

# GG Cable Generator

**What it does:** a geometry-nodes rig that makes a bundle of hanging cables between two objects. The user made it; the `.blend` stays on the user's machine and is never committed. Append from it, never save into it.

## What's in the file
- Collection `Cablez` holds the object `Cables`: a 2-vertex edge with the vertex group `Pin`. Its modifiers, in order:
  1. `Guideline` (node group `Guide.Curve`): Resolution, Start Object, End Object. It subdivides the edge between the two objects.
  2. `Cloth`: pinned by `Pin`, quality 15, mass 0.05, cache frames 1 to 2000. The sag comes from this simulation, so it shows only after frames are simulated.
  3. `Cable Gen` (node group `GG.Cables`): Seed, Cables (count), Messiness, Spread, End Spread, Thickness, Speed, Beams, Tint, and Curve (use a curve as the control instead of the cloth guide).
- Collection `Move Me` holds `Start` and `End`: small meshes with a `Wireframe` geometry-nodes display. Put them on the run's two end points.
- Material `GG.Cablez`.

## Use it for
`brief.yaml › cables: rig`, one rig per run in `layout.json › runs`. Each run starts and ends at a real object (a meter, a box, a conduit, a fixture) or past the frame edge.

## How to call it
1. Append `Cablez`, `Move Me` and the material once (`bpy.ops.wm.append` or `bpy.data.libraries.load`).
2. Per run: duplicate the rig, rename it `CBL_<run id>` with `CBL_<run id>_Start` and `_End`, and move Start and End onto the end points. Set Seed (different per run), Cables (the run's count), Messiness, Spread and Thickness.
3. **Curve mode is the default** (corridor pilot, FIX-r1): one guide curve object per run with the rig's `GG.Cables` modifier, Curve on, Beams off. The sag is in the curve and the ends sit exactly where you put them, with nothing frame-dependent. Use the cloth only when the scene has colliders set up and you can bake every run's cache; without colliders the cables hang through furniture. Never leave a scene that depends on an unbaked simulation.
4. The rig is built at metre scale. For wire-sized cables, scale each run object (0.25 gave 1–2 cm wires), then offset the guide curve to cancel the drift the rig adds up and sideways. Embed each end about 1.5 cm into its anchor so no gap shows.
5. Render with the pipeline's own cable material in an object-linked slot. `GG.Cablez` has subsurface 1.0 at a 0.5 m scale and a texture-driven roughness, so it read as pink, translucent wire at real scale. Give whichever material renders a `material_group` (for example `cables`) so the palette passes reach it.
6. Check every end against its anchor (the pilot checked 90 ends) and that the cables touch nothing else.

## Gotchas
- In Blender 5.2, `modifier.keys()` on a geometry-nodes modifier raised a TypeError. Read and set inputs through `modifier.node_group.interface.items_tree` and the socket identifiers.
- The `Cable Gen` group reads the scene time (`Speed`), so the cables can move between frames. Render a fixed frame.
- On `blender_unreal`, realize the cables (apply the modifiers) before Stage T, or rebuild them in Unreal with the Cable Component or splines (`ue.cablecomponent`).
