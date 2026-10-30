---
name: lighting-passes
description: Run the detailed lighting after blockout and modelling are finished (every asset in P0 to P7 final), starting with the detailed lighting brief. Then the gray (L1), value (L2) and hue (L3) passes, using one pass switch on the material groups, and stop for texturing. Use it in Stages 6 to 8 on the route's lighting engine, Unreal or Blender Cycles.
---

# Lighting passes L1 to L3

Method, thresholds and examples: `docs/pipeline/lighting.md`.

## Start

Start only when blockout and modelling are finished: every asset in P0 to P7 is final (`house-rules` rule 7). Until then the rig stays the neutral one from the blockout. If `brief.yaml › lighting_focus` is `deferred`, don't start: the rig and the exposure stay frozen until the user sends lighting references (`lighting-brief`).

The first step is the detailed lighting brief: write part 2 with `lighting-brief` (`light_depth`, key and its motivation, colour temperatures, ratio, focal order, lighting groups, the exposure sweep) and post it with L1. No light is added or changed before it exists.

Exposure is one manual value, set for real at L1 and locked in every pass after it. The steps are in `house-rules` rule 8 and `docs/pipeline/lighting.md`.

## Fast path: `blockout` and `camera_match`

L1 plus one colour gate, instead of L2 and L3. The result is a flat colour per material group on every mesh, lit for the reference's mood, for the user to texture. Colour only:

- **L1 gray:** one capture set. Check clipping, readable darks and the focal read; push existing lights before adding more.
- **Colour gate, posted as L3:** one flat colour per group from the reference's palette, value and hue together in one `palette.json`. Pick values by eye against the reference. Measure with `measure.py` only when two groups look alike.
- **Keep solved hexes.** Run `selftest_light.py` once with `palette.json` and use its `solved_hex`, not `solve_hex`'s analytic scaling: an analytic red read +12.5 levels off through AgX.
- **Tolerance:** about 8 sRGB levels on the render when desaturated by luminance, or "squint plus value order" (a blurred capture still separates the groups in the same light-to-dark order). Don't chase a tighter number by eye.
- **Leave roughness, metalness and normals alone:** no `roughness` in `palette.json`. Material slots are named by group (`M_<group>`), so the slot name says what to texture.
- **Skip** the rest of the measuring self-test, implied values and value floors; they are `full_cg` steps.

The sections below are the full path, for `full_cg`; the fast path uses only the pass switch and the Stop rule.

## Pass switch

| Route | Gray | Value and hue |
| --- | --- | --- |
| `unreal`, `blender_unreal` | `MPC_LookDev.PassMode = 0` on `M_Env_Master` | `PassMode = 1` or `2`; `apply_palette.py` sets `GroupValue` and `GroupHue` per material instance. Not built yet: `lookdev.py` and `apply_palette.py` don't exist (`unreal-adapter`) |
| `blender` | The adapter's `gray_on()`: View Layer › Material Override with one Principled BSDF at 0.216 | The adapter's palette script sets each material's Base Color from its group and stores the original in a custom property so it can be undone |

`gray_off()` and `restore()` put back exactly what they changed (overrides, slots, original colours and links), so a pass can be switched off and on without drift. `palette.apply` reports what it skipped (emissive and glass surfaces, `photo_proj` surfaces, a group with no material), so a silent skip can't pass as done.

In the value and hue passes, emissive surfaces keep their colour, glass and water keep transmission, and `photo_proj` surfaces stay out. In the gray pass the override grays emissive meshes too, so each emitter's light in `COL_Lights` carries its light (`house-rules` rule 7).

## Before L1: test the measuring tools (full_cg)

Blender route: run `blender-adapter/scripts/selftest_light.py` on the project file and fix any failure before the first L1 capture. Every check in the passes uses `measure.py`, so the method is the one the self-test proved. On the corridor pilot eight measuring faults (luma for luminance, an EXR against a display-decoded photo, a flare inside a region box, hidden objects in the stats) each surfaced in a review and cost part of a round. Unreal routes: render the same chart (0.216 gray, a gray at each value, a colour beside it) through the locked post-process volume and check it the same way.

## L1 Gray

Build broad to fine: key, sky and fill, practicals (with IES profiles where the real fixture is known), accents and rims with a reason, light functions and gobos, then atmosphere. Push existing lights before adding more. Set the exposure (lifecycle in `house-rules` rule 8 and `docs/pipeline/lighting.md`). Check the focal contrast, readable darks, no clipping or leaks, and the light budget; when the brief sets a ratio, the key to fill ratio within half a stop. Capture Lit and the exposure visualisation. Lighting Only is a manual editor capture: scripted capture can't render it (`unreal-adapter`).

## L2 Value

One gray per lighting group, using the groups and floor exceptions planned in part 2 of the lighting brief, non-metals between about sRGB 60 and 240. On a photo-matched scene, measure each group's implied value (photo divided by the gray render in region boxes) first, and search for fill lights only for a brightness-order miss the implied values don't explain. Values come from real materials (the Art Director brings references). Relight afterwards: darker surfaces return less bounce. Write `light/palette.json` with the values. Check that the focal hierarchy survives, run a squint (blurred) capture, and post a per-group table and histogram.

## L3 Hue

A numbered palette, one colour per group, each keeping its group's value within 5 sRGB levels when desaturated by luminance (not luma). Start each colour from the group's implied hue, with the light's colour divided out, never from the photo as seen; solve each hex to its value through the view transform (`selftest_light.py` with `palette.json` gives `solved_hex`). Big surfaces low in saturation, saturated colour for small accents. Light temperatures at real values in `full_cg`. Update `palette.json` with `hue_hex`.

## Stop

After L3 is approved, hand over to `texturing-handoff` to finalise its brief. Don't start textures, Post FX or a LUT; those are the user's.
