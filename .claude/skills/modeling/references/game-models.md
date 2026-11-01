# Game models

For Unreal targets, whether built in Blender or in Unreal's modelling tools. The numbers are starting defaults; `plan/budget.yaml` and the brief override them.

## Pick by camera distance

Matt Murch's three workflows. One scene, and even one asset, can mix them.

| Workflow | Use for | How |
| --- | --- | --- |
| Ultra low poly, hard edges | Far props, background buildings, filler | Silhouette only. Hard edges where faces meet at sharp angles, UV seams on the hard edges, tiling or trim textures |
| Mid-poly with custom normals | Close to mid distance, most hero props and kit pieces | Bevel the silhouette edges (see Bevels below, Harden Normals) and add a Weighted Normal modifier (Face Area, Keep Sharp). No baked normal map needed, so tiling materials and trim sheets work. Inset panels may need their normals edited by hand |
| Low poly with high-poly bake | Assets with sculpted or fine detail (carvings, cloth folds, damage) | High poly by sculpt or SubD. Low poly follows the silhouette: a separate mesh, or the SubD cage with its support loops or modifier stack stripped, which is one way among several ([hard-surface-workflows.md](../../../../docs/pipeline/hard-surface-workflows.md)). Bake normals and AO with a tight cage, split UVs at every hard edge, keep one tangent basis (MikkTSpace), and name pairs `_low` and `_high` |

## Bevels

- **Even segments, always:** 2 or 4 most of the time. The larger the curve, the more it needs, so go above 4 only for a big radius that shows. An odd count, 1 included, gets a warning from `validate_mesh.py`.
- Take the width from the real radius on the rectified reference.
- Keep the bevel a live modifier until the mesh is approved, so the topology under it stays simple to change.
- The SubD route keeps its holding loops instead ([quad-subd.md](quad-subd.md)).

## Openings in a curved shell

Plan a window or seam in a domed or rolled shell into the shell's loops from the start, as [hard-surface-topology.md](hard-surface-topology.md) describes. Don't slice a finished shell with `bmesh.ops.bisect_plane` or a Boolean: that gave the random cuts on the first benchmark meter.

If a shell is already cut and the shading has pulled out of shape around the hole, normal transfer is the repair, not the method:

1. Rebuild the shell without the opening as the source.
2. Give the cut shell's outer faces the source's normals: Data Transfer (custom normals, nearest face interpolated) after Weighted Normal, limited by distance so that cut walls keep their own hard shading. Or write the sampled normals with `normals_split_custom_set`. Apply it, then check the result.
3. A plate cut from the shell takes the normals of its own surface. If it should read as flat, make it flat instead of inheriting the shell's curve.

Judge the shell in the shiny matcap and `reflect` stripe views (`blender-adapter`, `asset_capture.py`), close up on every opening. Smears and lumps that don't show in a neutral render show there, and kinks that matcap misses show in the stripes. `validate_mesh.py` can't see most of them.

## Nanite or LODs (Unreal 5.8)

- Opaque static meshes default to **Nanite**. Polycount matters much less, but disk size and memory still matter, so don't import a raw multi-million-triangle sculpt when a mid-poly mesh reads the same.
- Many tiny disconnected pieces, such as leaves or chain links, make poor Nanite meshes; check them against the current Nanite docs first.
- Skeletal meshes, translucent materials and anything Nanite does not support keep **classic LODs**: LOD0 at 100%, then about 50%, 25% and 12.5%, switched by screen size.
- With Nanite on, keep a sensible fallback mesh for platforms or features that don't support it.

## Modular kits

- Build to the project grid (for example 50 cm, 1 m, 2 m, or 4 m wall widths). Pivots sit on a grid corner, and pieces snap edge to edge with no gaps.
- Use **trim sheets** and tiling materials so dozens of pieces share a few texture sets. A full kit is often more than 50 pieces, mostly repetitive work.
- Vertex density stays even across matching edges so lighting and vertex paint blend across seams.
- **Vistas and backdrops:** cards or simple volumes with no backfaces, never full geometry.

## UVs and texel density

- One texel density per project, set at G1. Common starting points are 512 px/m for third person and 1024 px/m for first person. Allow 10% either way.
- Kit pieces map onto trim sheets. Unique hero props get their own UV set.
- Add a second UV channel for lightmaps only when lighting is baked. Lumen needs none.

## Collision

- Simple convex shapes named `UCX_<MeshName>_01`, `_02`, and so on, exported with the mesh.
- Walls and floors get boxes. Stairs get a ramp so the player moves smoothly.
- Props the player can't reach get no collision. Use complex-as-simple only for meshes that really need it.

## Triangle budgets (starting defaults)

| Asset | Triangles |
| --- | --- |
| Modular wall, 2 m | 200 to 800 |
| Floor tile | 100 to 400 |
| Hero building section | 5,000 to 20,000 |
| Hero prop | 15,000 to 50,000 |
| Standard prop | 5,000 to 15,000 |
| Background prop | 500 to 5,000 |
| Small clutter | 100 to 500 |

With Nanite on, treat these as guides for disk size and authoring time rather than hard limits.

## Naming

`SM_` static mesh, `SK_` skeletal mesh, `UCX_SM_<Name>_01` collision, `SOCKET_<Name>` socket empty, `M_` material, `MI_` material instance, `T_<Name>_BC/_N/_ORM` textures. `material_group` from the asset spec decides the material instance.

## Normals on export

In Blender 5.x, auto smooth is replaced by the Smooth by Angle modifier, and Weighted Normal works without it. Export normals with the FBX (smoothing: Face, or Normals Only) and import them in Unreal with Import Normals rather than Compute, or the custom normals are lost.

## Sources

- [Matt Murch: leveraging multiple workflows](https://mattmurch.artstation.com/blog/Oba9/leveraging-multiple-workflows)
- [80.lv: the mid-poly workflow in UE5](https://80.lv/articles/creating-assets-within-the-mid-poly-workflow-in-ue5/)
- [Marmoset: baking a hard-surface weapon](https://marmoset.co/posts/baking-a-hard-surface-weapon-in-toolbag/)
- [80.lv: the stages of environment art in gamedev](https://80.lv/articles/the-stages-of-environment-art-in-gamedev)
- [80.lv: a guide on Nanite by the Unreal Engine team](https://80.lv/articles/a-guide-on-nanite-by-the-unreal-engine-team/)
- [Unreal Engine: Nanite, the end of polycounts](https://www.unrealengine.com/en-US/blog/nanite-in-ue5-the-end-of-polycounts)
- [80.lv: 70s office modular environment in UE5](https://80.lv/articles/setting-up-a-70s-office-modular-environment-with-unreal-engine-5)
- [Ian London: modular level kit geometry](https://ianlondon.github.io/posts/modular-level-kit-geometry)
- [arjun988/blender-skills](https://github.com/arjun988/blender-skills): polycount budgets and Unreal naming (MIT)
