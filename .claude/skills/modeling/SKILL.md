---
name: modeling
description: Build or repair a 3D model in Blender for the scene pipeline, such as a kit piece, prop, hero asset, or a Tripo or Magnific mesh that needs cleaning. It picks a method per asset (SubD quads, game low or mid-poly, custom-normal bevels, or fast photo-projected CG) from the route, camera distance and budget. Use it for any modelling task in the pipeline.
---

# Modeling

The Modeler agent runs this skill. It turns one asset spec (`kit/<asset>.md`) into a mesh that matches the reference, has real-world scale, and fits the route and budget.

## 1. Pick the method before touching the mesh

Read the spec, the `measure` and `form` references, `plan/metrics.yaml`, and the camera distance tier from `light/cameras.json` or the layout. Then pick one row. One asset can mix methods, for example a SubD body with low-poly screws.

| Situation | Method | Read |
| --- | --- | --- |
| CG close-up, product or hero prop | SubD with quads and holding loops, no Boolean | [quad-subd.md](references/quad-subd.md), [volume-methods.md](references/volume-methods.md) |
| Game hero or mid-distance prop | Mid-poly: bevelled silhouette with weighted or custom normals. Low poly plus a high-poly bake only when it needs sculpted detail | [game-models.md](references/game-models.md) |
| Game modular kit piece | Grid-snapped, trim sheet, custom normals, Nanite or LODs by rule | [game-models.md](references/game-models.md), `modular-kit` skill |
| Far or background, any route | Ultra low poly with hard edges, cards or impostors | [game-models.md](references/game-models.md) |
| CG background building, set extension, vista | Fast CG: simple geometry, photo projection, build only what the camera sees | [fast-cg.md](references/fast-cg.md) |
| Generated output (Tripo or Magnific) | Repair, then retopologise or bake as the tier needs | [mesh-repair.md](references/mesh-repair.md), `generated-asset` skill |

For every single asset, use the gate protocol and scripts from `blender-image-to-3d`: a calibration file with the references at real scale, renders from the reference camera, and measured silhouette checks. On the game routes the Asset Tech then adds collision (`collision-proxy`) and, only where Nanite can't be used, LODs (`lod-pipeline`).

Write the choice into the spec before you build:

```yaml
method: subd_quad | game_midpoly | game_bake | game_lowpoly | fast_cg | repair
why: "hero cap, seen at 30 cm in shot 2"
expected_tris: 12000          # at render or LOD0
classification: single_axial  # see volume-methods.md
```

## 2. Classify the shape

Single volume or several volumes joined into one mass. A single volume is axial (a lathe shape), symmetric, or asymmetric. Each class has its own construction method in [volume-methods.md](references/volume-methods.md). Getting this right first is what keeps the mesh simple.

## 3. Build

1. **Blockout at real scale.** Use the dimensions from the spec and metrics. Set up reference planes or a camera match per view. Capture front, side and top with the reference overlaid and compare before you add any detail.
2. **Go from low poly to high poly.** Only the points needed to describe the form. Add loops only where the form bends or a detail sits.
3. **Build the detail with the chosen method.**
4. **Contact and placement.** Nothing floats and nothing intersects by accident. For CG, leave a tiny gap so the contact shadow reads. For games, snap kit pieces exactly and sink organic objects such as rocks slightly into the ground.
5. **Pivot and parent.** The pivot goes at the bottom centre, or at the kit grid origin for kit pieces. For a multi-part product, parent all parts to an empty at the bottom centre so the whole thing can be snapped onto a surface. Cameras and lights are never parented to it.

## 4. Validate (scripted, every asset)

Run the checks through the Blender adapter's validation script and paste the result into the spec.

- [ ] Transforms applied, scale 1, and dimensions within tolerance: 1 cm for kit and props, 1 mm for products
- [ ] Normals face outward, with no non-manifold edges unless intended
- [ ] No duplicate vertices (Merge by Distance), no stray loose parts
- [ ] Only quads under SubD; n-gons are allowed only on flat, non-subdivided faces
- [ ] Triangle count at LOD0 or render level within budget
- [ ] UVs present. For games, texel density is within 10% of the project value, and a second UV channel exists only if lighting is baked
- [ ] Names follow the convention (`SM_`, `UCX_`, `SOCKET_`, and so on) and the material slots match `material_group`
- [ ] Captures: front, side, back, top, and a three-quarter view next to the 1.8 m mannequin, saved for the supervisor

## Blender session rules

They apply whenever the agent drives the user's Blender through MCP.

- Work in the Blender instance that is already open. Never launch a new one.
- Never delete the user's data. Hide it instead, for example the default cube.
- Save after each major step to the project path given by the `blender-adapter` skill. Outside the pipeline, ask for the folder and file name first.
- Make scripts idempotent (check before you create) and run each one once, so a re-run doesn't duplicate geometry.
- Before you re-run a rebuild script, check whether the user edited the mesh by hand. Compare the stored vertex count and hash with the current mesh. If they changed, write small incremental scripts that build on the edit instead of rebuilding.
- Read the user's own base mesh directly instead of guessing its shape.
- Never change the viewport shading or view while the user may be inspecting it. Captures go through review cameras and offscreen renders.
- Capture close-ups to read small details instead of judging them from a wide shot.
- Check which way the object faces before you mirror it.
- Model in Solid shading. Check SubD at viewport level 2; work at level 1.
- For CG renders, use Cycles on the GPU (OptiX, or CUDA if OptiX is unavailable).

## Lessons loop

Write down each lesson after each model, then promote the lessons that hold up into rules:

1. After each supervisor or Art Director review of a model, add one line to `feedback/modeling.md`: what went wrong, the rule that would have prevented it, and the asset.
2. When the same lesson shows up on two projects, move it into the matching reference file and log the change in `feedback/CHANGELOG.md`.

## Sources

- Web sources are listed at the end of each reference file.
