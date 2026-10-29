# Repairing generated and scanned meshes

For Tripo and Magnific 3D outputs, scans, and any mesh from outside. Generated meshes are usually dense triangles, have lighting baked into the colour, merge parts that should be separate, and come in at an arbitrary scale.

## Always

1. **Keep the source.** Duplicate the import as `<Name>_Source` in a hidden `COL_Ref` collection before you change anything.
2. **Scale to the spec.** Scale the bounding box to the dimensions in `kit/<asset>.md`, then apply scale. Check one real dimension, such as a seat height or a door width.
3. **Orient and pivot.** Front faces -Y in Blender. Put the pivot at the bottom centre or the spec's origin.
4. **Clean up.** Merge by Distance, delete loose parts and floating noise, recalculate normals outward, and fix non-manifold edges and holes (Grid Fill or a patch).
5. **Strip baked light.** Colour from a generated mesh is reference only. The value and hue passes need clean material groups, so remove the colour or use it only as a guide.

## Then pick a path by tier

| Tier | Path |
| --- | --- |
| Far or clutter | Decimate to budget (Planar first, then Collapse) and keep the silhouette. Auto UV or a simple box map is enough |
| Mid, game | Quad remesh (Magnific `models3d_remesh`, or Blender's Remesh or QuadriFlow) to budget. UV unwrap (Magnific `models3d_uv_unwrap`, or by hand). Bake the normal map from the source |
| Hero, game | Retopologise by hand over the source (Shrinkwrap plus snapping), with a quad flow that follows the form. Bake normals and AO from the source. Split moving or separate parts |
| Hero, CG | Rebuild as SubD over the source (see quad-subd.md). Use the source only as a shape guide |

- **Split parts like the real object.** Lids, handles and cushions become separate objects. Magnific `models3d_segment` can propose the split.
- **Bevel or holding loops** where the real object is sharp; generated meshes are usually soft everywhere.
- Never place a raw generated mesh in a hero position. The supervisor rejects it.

## Checks before hand-off

- [ ] Within budget for its tier
- [ ] Dimensions within 1 cm of the spec
- [ ] No baked-light colour left in the material
- [ ] Parts split where the real object splits
- [ ] UVs and texel density meet the project value
- [ ] Spec records the source (`tripo`, `magnific`, `scan`), the prompt or image used, and the credits spent

## Sources

- [arjun988/blender-skills, realistic-style scan clean-up reference](https://github.com/arjun988/blender-skills) (MIT)
- Repair imported meshes before modelling on top of them
