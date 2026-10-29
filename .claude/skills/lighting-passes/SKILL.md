---
name: lighting-passes
description: Run the gray (L1), value (L2) and hue (L3) lighting passes after the kit and set dressing are in, using one pass switch on the material groups, then stop for texturing. Use it in Stages 6 to 8 on the route's lighting engine, Unreal or Blender Cycles.
---

# Lighting passes L1 to L3

Method, thresholds and examples: `docs/pipeline/lighting.md`. Exposure stays locked to the brief's value in every pass.

## Fast path: `blockout` and `camera_match`

The result is a flat colour per material group on every mesh, lit for the reference's mood, for the user to texture. Colour only:

- **L1 gray:** one capture set. Check clipping, readable darks and the focal read; push existing lights before adding more.
- **L2 value:** one gray per lighting group, picked by eye against the reference. Measure with `measure.py` only when two groups look alike.
- **L3 hue:** one flat colour per group from the reference's palette, keeping its L2 value within 5 levels when desaturated.
- **Leave roughness, metalness and normals alone:** no `roughness` in `palette.json`. Material slots are named by group (`M_<group>`), so the slot name says what to texture.
- **Skip** the measuring self-test, implied values, value floors and solved hexes; they are `full_cg` steps.
- **Reviews by tier:** S runs L1 to L3 back to back with one supervisor review at L3; M reviews L1 and L3; L reviews every pass.

The sections below are the full path for `full_cg`; the fast path uses only the pass switch and the Stop rule.

## Pass switch

| Route | Gray | Value and hue |
| --- | --- | --- |
| `unreal`, `blender_unreal` | `MPC_LookDev.PassMode = 0` on `M_Env_Master` | `PassMode = 1` or `2`; `apply_palette.py` sets `GroupValue` and `GroupHue` per material instance |
| `blender` | View Layer › Material Override with one Principled BSDF at 0.216 | The adapter's palette script sets each material's Base Color from its group and stores the original in a custom property so it can be undone |

Emissive surfaces keep their colour, glass and water keep transmission, and `photo_proj` surfaces stay out of the passes.

## Before L1: test the measuring tools (full_cg)

Blender route: run `blender-adapter/scripts/selftest_light.py` on the project file and fix any failure before the first L1 capture. Every check in the passes uses `measure.py`, so the method is the one the self-test proved. On the corridor pilot eight measuring faults (luma for luminance, an EXR against a display-decoded photo, a flare inside a region box, hidden objects in the stats) each surfaced in a review and cost part of a round. Unreal routes: render the same chart (0.216 gray, a gray at each value, a colour beside it) through the locked post-process volume and check it the same way.

## L1 Gray

Build broad to fine: key, sky and fill, practicals (with IES profiles where the real fixture is known), accents and rims with a reason, light functions and gobos, then atmosphere. Push existing lights before adding more. Check the key to fill ratio within half a stop, the focal contrast, readable darks, no clipping or leaks, and the light budget. Capture Lit, Lighting Only, and the exposure visualisation.

## L2 Value

One gray per lighting group, using the groups and floor exceptions planned in the L0 brief, non-metals between about sRGB 60 and 240. On a photo-matched scene, measure each group's implied value (photo divided by the gray render in region boxes) first, and search for fill lights only for a brightness-order miss the implied values don't explain. Values come from real materials (the Art Director brings references). Relight afterwards: darker surfaces return less bounce. Write `light/palette.json` with the values. Check that the focal hierarchy survives, run a squint (blurred) capture, and post a per-group table and histogram.

## L3 Hue

A numbered palette, one colour per group, each keeping its group's value within 5 sRGB levels when desaturated by luminance (not luma). Start each colour from the group's implied hue, with the light's colour divided out, never from the photo as seen; solve each hex to its value through the view transform (`selftest_light.py` with `palette.json` gives `solved_hex`). Big surfaces low in saturation, saturated colour for small accents. Light temperatures at real values in `full_cg`. Update `palette.json` with `hue_hex`.

## Stop

After L3 is approved, hand over to `texturing-handoff`. Don't start textures, Post FX or a LUT; those are the user's.
