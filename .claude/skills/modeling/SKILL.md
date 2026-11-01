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
| Tripo stand-in (placeholder prop) | No Modeler build. `tripo_cleanup.py` fits it to the spec; fix only what its check or the supervisor flags | `tripo-props` skill |
| Hero repair (Magnific mesh, or a Tripo mesh in a hero position) | Repair, then retopologise or bake as the tier needs | [mesh-repair.md](references/mesh-repair.md), `generated-asset` skill |

The Modeler works headless on its own asset file (`bash bin/blender-bg`); the session rules and save paths are in `blender-adapter`. On the game routes the Asset Tech then adds collision (`collision-proxy`) and, only where Nanite can't be used, LODs (`lod-pipeline`).

**Full path: the spec has reference views (front, side, top).** Load `blender-image-to-3d` with the Skill tool and use its gate protocol and scripts: a calibration file with the references at real scale, renders from the reference camera, and measured silhouette checks. Kit pieces and fixed props use its environment asset path.

**Lite path: the spec has no orthographic view (only a turnaround, a 3/4 shot or one photo).** Don't load `blender-image-to-3d`. Build to `dims_m` from the spec, not from the picture. Render the views and the comparison with `asset_capture.py` (`blender-adapter`), giving the object's box and each `--feature` box in photo pixels by hand, never from brightness. Read the width-to-height ratio and the feature errors from `capture_report.json` as your two or three measured ratios, comparing only the proportions the picture really shows. List every side the picture doesn't show as inferred in the spec. Then run the validation below.

```
bash bin/blender-bg <asset>.blend --python .claude/skills/blender-adapter/scripts/asset_capture.py -- --object <asset> --out <dir> --photo <photo> --photo-box x0 y0 x1 y1 --feature <part>:x0,y0,x1,y1
```

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

1. **Blockout at real scale.** Use the dimensions from the spec and metrics (`dims_source` says where they come from; an AI image or a generated mesh never sets a size, `house-rules` rule 11). Set up reference planes or a camera match per view. Capture front, side and top with the reference overlaid and compare before you add any detail.
2. **Go from low poly to high poly.** Only the points needed to describe the form. Add loops only where the form bends or a detail sits.
3. **Build the detail with the chosen method.**
4. **Contact and placement.** Nothing floats and nothing intersects by accident. For CG, leave a tiny gap so the contact shadow reads. For games, snap kit pieces exactly and sink organic objects such as rocks slightly into the ground.
5. **Pivot and parent.** The pivot goes at the bottom centre, or at the kit grid origin for kit pieces. For a multi-part product, parent all parts to an empty at the bottom centre so the whole thing can be snapped onto a surface. Cameras and lights are never parented to it.
6. **Tubes and round parts** (conduit, pipes, poles, cylindrical fittings): scale uniformly to the measured diameter, never per axis to a box that includes clips or lips. The straight section stays round within 2 mm (width against depth).
7. **No wear.** See `house-rules` rule 1. List wear in `handoff/wear-notes.md` and keep the surface clean.
8. **Details.** Check which way the object faces before you mirror it. Check SubD at viewport level 2 and work at level 1. Capture close-ups to read small details instead of judging them from a wide shot.

## 4. Validate (scripted, every asset)

Run `blender-adapter/scripts/validate_mesh.py` with the spec. Besides the mesh checks it compares dimensions, pivot and material group against the spec. Paste the result into the spec's `validation`.

```
bash bin/blender-bg <asset>.blend --python .claude/skills/blender-adapter/scripts/validate_mesh.py -- <asset> --spec kit/<asset>.md [--tol-mm 1] --out validation.json
```

The size tolerance is 1 cm unless a `done_when` line on the size says otherwise (`--tol-mm 1` for products). Exit 1 means a check failed.

- [ ] Transforms applied, scale 1, and dimensions within tolerance: 1 cm for kit and props, 1 mm for products
- [ ] Tubes and round parts: uniform scale, roundness within 2 mm
- [ ] Pivot matches the spec's `pivot` and `mount`
- [ ] Normals face outward, with no non-manifold edges unless intended
- [ ] No duplicate vertices (Merge by Distance), no stray loose parts
- [ ] Only quads under SubD; n-gons are allowed only on flat, non-subdivided faces
- [ ] Triangle count at LOD0 or render level within budget
- [ ] UVs present, and `uv_check.py` (`blender-adapter`) passes with `--profile trim` for tiling and trim-sheet pieces, `unique` otherwise. For games, texel density is within 10% of the project value, and a second UV channel exists only if lighting is baked
- [ ] Names follow the convention (`SM_`, `UCX_`, `SOCKET_`, and so on) and the material slots match `material_group`
- [ ] Captures: `asset_capture.py` writes front, side, back, top, three-quarter and the 1.8 m mannequin shot, saved for the supervisor. Look at `culling/` for holes and inside-out faces and `matcap/` for smears and lumps, close up on every cut (`--close`)

## Lessons loop

Write down each lesson after each model, then promote the lessons that hold up into rules:

1. After each supervisor or Art Director review of a model, add one line to the project's `log.md`: what went wrong, the rule that would have prevented it, and the asset.
2. `retro` proposes the lessons that hold up for `feedback/modeling.md`. They go there only with the user's OK and with project names taken out (`house-rules` rule 3).
3. When the same lesson shows up on two projects, move it into the matching reference file and log the change in `feedback/CHANGELOG.md`.

## Sources

- Web sources are listed at the end of each reference file.
