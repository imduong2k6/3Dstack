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
| CG close-up, product or hero prop | SubD with quads and holding loops, a Boolean only on a prepared base | [quad-subd.md](references/quad-subd.md), [volume-methods.md](references/volume-methods.md), and [subd-recipes.md](references/subd-recipes.md) when a count changes or a circle sits in a plate |
| Game hero or mid-distance prop | Mid-poly: bevelled silhouette with weighted or custom normals. Low poly plus a high-poly bake only when it needs sculpted detail | [game-models.md](references/game-models.md) |
| Game modular kit piece | Grid-snapped, trim sheet, custom normals, Nanite or LODs by rule | [game-models.md](references/game-models.md), `modular-kit` skill |
| Far or background, any route | Ultra low poly with hard edges, cards or impostors | [game-models.md](references/game-models.md) |
| CG background building, set extension, vista | Fast CG: simple geometry, photo projection, build only what the camera sees | [fast-cg.md](references/fast-cg.md) |
| Tripo stand-in (placeholder prop) | No Modeler build. `tripo_cleanup.py` fits it to the spec; fix only what its check or the supervisor flags | `tripo-props` skill |
| Hero repair (Magnific mesh, or a Tripo mesh in a hero position) | Repair, then retopologise or bake as the tier needs | [mesh-repair.md](references/mesh-repair.md), `generated-asset` skill |

The Modeler works headless on its own asset file (`bash bin/blender-bg`); the session rules and save paths are in `blender-adapter`. On the game routes the Asset Tech then adds collision (`collision-proxy`) and, only where Nanite can't be used, LODs (`lod-pipeline`).

**Full path: the spec has reference views (front, side, top).** Load `blender-image-to-3d` with the Skill tool and use its gate protocol and scripts: a calibration file with the references at real scale, renders from the reference camera, and measured silhouette checks. Kit pieces and fixed props use its environment asset path.

**Lite path: the spec has no orthographic view (only a turnaround, a 3/4 shot or one photo).** Don't load `blender-image-to-3d`. Build to `dims_m` and the blueprint (step 2), not from the picture. Render the views and the comparison with `asset_capture.py` (`blender-adapter`) against the rectified image, giving the object's box and each `--feature` box in its pixels by hand, never from brightness. Read the width-to-height ratio and the feature errors from `capture_report.json` as your two or three measured ratios, comparing only the proportions the image really shows. List every side the picture doesn't show as inferred in the spec. Then run the validation below.

```
bash bin/blender-bg <asset>.blend --python .claude/skills/blender-adapter/scripts/asset_capture.py -- --object <asset> --out <dir> --photo <rectified> --photo-kind rectified --photo-box x0 y0 x1 y1 --feature <part>:x0,y0,x1,y1
```

Write the choice into the spec before you build:

```yaml
method: subd_quad | game_midpoly | game_bake | game_lowpoly | fast_cg | repair
why: "hero cap, seen at 30 cm in shot 2"
expected_tris: 12000          # at render or LOD0
classification: single_axial  # see volume-methods.md
```

## 2. Read the form, before any mesh

A photo shows the object through a camera. Model the object. Skip this step only for `fast_cg` (a projection seen from that one camera) and `repair`.

1. **Flatten the reference.** A perspective photo gives silhouette and detail, never proportions. Rectify it from a rectangle on the object whose real size you know, and measure from the result. It is true only on that plane, so size anything standing off it from `dims_m` or a second view.

   ```
   python .claude/skills/modeling/scripts/blueprint.py rectify <photo> --corners x0,y0 x1,y1 x2,y2 x3,y3 --size-m W H --out ref/<asset>_rect.png
   ```

   With no rectangle of known size, use two pairs of edges parallel on the object and points round one true circle, all on one plane. It gives true proportions and no scale, so size it from `dims_m`. In simulation it read 1.3 to 2 % at every lens, tilt and crop at 1 px of pick error; it hasn't been tried on a real image, so check `circle_spread_pct` in its report. Don't use a rectangle and a guessed focal length instead: 5 to 16 % on an off-centre crop, and a panel cut from a bigger picture is one. A circle alone is fine from about 135 mm up, and 10 to 25 % wrong at wide lenses.

   ```
   python .claude/skills/modeling/scripts/blueprint.py rectify-pairs <photo> --pair-a x,y x,y x,y x,y --pair-b x,y x,y x,y x,y --circle x,y x,y x,y x,y x,y ... --out ref/<asset>_rect.png
   ```

2. **Split a complex object into sections**: parts that are built and that mirror differently (body, cover, window, gland). Classify each one as axial, symmetric or asymmetric ([volume-methods.md](references/volume-methods.md)). Getting this right first is what keeps the mesh simple.
3. **Write the `form` block in the spec** (template in `modular-kit`), one row per section:
   - Mirror planes. Assume the object was made symmetric until the real object shows otherwise: a taper, a lean or one wider side that perspective explains is not asymmetry.
   - True asymmetries, each with its evidence and box: a seal, a cable, one lug.
   - Every circular detail, full or half, with centre, axis, diameter and segments, and `photo_px` to mark it on the reference.
   - Repeats, with counts: `repeat` for equal sectors round a centre, `repeats` for a row.
4. **Draw the blueprint** and load it as your reference plane. On a pilot or hero without autopilot, show the user the blueprint and the marked reference before you model: a wrong read costs a line here and a rebuild later.

   ```
   python .claude/skills/modeling/scripts/blueprint.py draw kit/<asset>.md --out kit/<asset>_blueprint.png --underlay ref/<asset>_rect.png --mark <photo> --mark-out kit/<asset>_marked.png
   ```

## 3. Build

Read [hard-surface-topology.md](references/hard-surface-topology.md) first. Build one half or one sector with live Mirror and Array modifiers, in `<asset>.blend`. Apply them only on the delivery copy. Work in three levels, and capture and check at the end of each before you start the next, because a big-form fix after small detail is a rebuild:

- **Big: the masses at real scale.** Use the dimensions from the blueprint, the spec and metrics (`dims_source` says where they come from; an AI image or a generated mesh never sets a size, `house-rules` rule 11). Only the points needed to describe the form. Capture front, side and top against the blueprint.
- **Medium: openings, panels and separate parts.** Plan the loops round each opening, using the chosen method. Add loops only where the form bends or a detail sits. Add bevels as live modifiers, with even segments ([game-models.md](references/game-models.md)). Check `--modes wire,matcap`, and add `reflect` on curved faces.
- **Small: screws, labels raised off the surface, ribs and fittings.** Model one and Array it. Check close-ups (`--close`) in `solid` and `wire`.

The rest of the build, at the level each belongs to:

1. **Contact and placement.** Nothing floats and nothing intersects by accident (`validate_mesh.py` lists both under `parts`). For CG, leave a tiny gap so the contact shadow reads. For games, snap kit pieces exactly and sink organic objects such as rocks slightly into the ground.
2. **Pivot and parent.** The pivot goes at the bottom centre, or at the kit grid origin for kit pieces. For a multi-part product, parent all parts to an empty at the bottom centre so the whole thing can be snapped onto a surface. Cameras and lights are never parented to it.
3. **Tubes and round parts** (conduit, pipes, poles, cylindrical fittings): scale uniformly to the measured diameter, never per axis to a box that includes clips or lips. The straight section stays round within 2 mm (width against depth).
4. **No wear.** See `house-rules` rule 1. List wear in `handoff/wear-notes.md` and keep the surface clean.
5. **Details.** Check which way the object faces before you mirror it. Check SubD at viewport level 2 and work at level 1. Capture close-ups to read small details instead of judging them from a wide shot.

## 4. Validate the mesh (scripted, every asset)

Run `blender-adapter/scripts/validate_mesh.py` with the spec. Besides the mesh checks it compares dimensions, pivot and material group against the spec, measures each mirror in `form`, and reports topology. Paste the result into the spec's `validation`.

```
bash bin/blender-bg <asset>.blend --python .claude/skills/blender-adapter/scripts/validate_mesh.py -- <asset> --spec kit/<asset>.md --stage mesh [--tol-mm 1] --out validation.json
```

For a multi-part product, name the empty the parts are parented to: it validates each part, then all of them together, because a part's own run can't see another object. The size tolerance is 1 cm unless a `done_when` line on the size says otherwise (`--tol-mm 1` for products). Exit 1 means a check failed.

- [ ] Every mirror in `form` within `tol_mm`, or the difference listed as an asymmetry with its evidence
- [ ] `topology` warnings read and either fixed or explained in the report, with the `wire` captures looked at from every side
- [ ] Transforms applied, scale 1, and dimensions within tolerance: 1 cm for kit and props, 1 mm for products
- [ ] Tubes and round parts: uniform scale, roundness within 2 mm
- [ ] Pivot matches the spec's `pivot` and `mount`
- [ ] Normals face outward, with no non-manifold edges unless intended
- [ ] No duplicate vertices (Merge by Distance), no stray loose parts
- [ ] Quads under SubD, except a flat n-gon with a support row all round and a centre that sees every edge ([subd-recipes.md](references/subd-recipes.md)). `validate_mesh.py` fails the rest
- [ ] Triangle count at LOD0 or render level within budget
- [ ] Names follow the convention (`SM_`, `UCX_`, `SOCKET_`, and so on) and the material slots match `material_group`
- [ ] Captures: `asset_capture.py` writes front, side, back, top, three-quarter and the 1.8 m mannequin shot, saved for the supervisor. Look at `culling/` for holes and inside-out faces, `matcap/` for smears and lumps, `reflect/` for kinks on curved faces and `wire/` for the flow, close up on every opening (`--close`)

## 5. Mesh approval, then UVs

Without autopilot, stop here and report. No UVs, baking or texturing until the user has approved the final mesh, because each of those is thrown away when the form changes. With autopilot, post the same views for the record and carry on.

- **What the user sees:** solid and wire from the front, a side and a three-quarter, close-ups of each opening, the blueprint, the `topology` numbers and anything you are unsure of. Hand over the `.blend`.
- **How it is grouped:** pilots and heroes one at a time; the rest of a batch as one contact sheet per batch, so one approval covers it (the manager posts it, `scene-pipeline`).

After approval:

- [ ] UVs present, and `uv_check.py` (`blender-adapter`) passes with `--profile trim` for tiling and trim-sheet pieces, `unique` otherwise. For games, texel density is within 10% of the project value, and a second UV channel exists only if lighting is baked
- [ ] `validate_mesh.py` passes again without `--stage mesh`
- [ ] A form change after approval goes back to the user: it voids the approval for that asset

## Lessons loop

Write down each lesson after each model, then promote the lessons that hold up into rules:

1. After each supervisor or Art Director review of a model, add one line to the project's `log.md`: what went wrong, the rule that would have prevented it, and the asset.
2. `retro` proposes the lessons that hold up for `feedback/modeling.md`. They go there only with the user's OK and with project names taken out (`house-rules` rule 3).
3. When the same lesson shows up on two projects, move it into the matching reference file and log the change in `feedback/CHANGELOG.md`.

## Sources

- Web sources are listed at the end of each reference file.
