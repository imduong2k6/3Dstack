---
name: lighting-brief
description: Write the lighting brief for a pipeline scene in two parts. At Stage 2, the neutral rig (sky and key direction, time of day, a light on every model that emits, mood references, lights.json). Just before the gray pass, the detailed part (key and its motivation, colour temperatures, key to fill ratio, focal order, light depth, the exposure sweep). Use it in Stage 2, and again before L1.
---

# Lighting brief

Method and numbers: `docs/pipeline/lighting.md`. Rules: `house-rules` rule 7 (the rig stays neutral until blockout and modelling are done) and rule 8 (exposure lifecycle).

## Part 1: neutral rig (Stage 2, reviewed at G1)

Write the "Neutral rig" section of `plan/lighting-brief.md` and `light/lights.json`:

- **Direction and time of day.** Where the sun and sky light come from and when, roughly matching the references (and the researched place).
- **Emitting models.** One light for every model that gives off light (bulbs, lamps, signs, screens), listed from the cyan shapes on the map and `plan/inventory.yaml`, each with the fixture type and a reason, such as "wall sconce, map L03". A light with no reason needs the user's OK.
- **Mood references**, where AI images are welcome, tagged `mood`.
- Nothing else. No exposure target, key to fill ratio, colour temperature or region grid is set or reviewed yet; reviewers check only that nothing is clipped or black and that each capture's mean stays inside the `light/exposure.json › mean_band`, if one is recorded.

**Route notes.** `unreal`: Lumen and a Post Process Volume with Min EV100 = Max EV100 (one manual value, see the exposure lifecycle). `blender`: the Cycles light paths, view transform and fixed exposure. `blender_unreal`: the light in Blender is for direction only; final values are set in Unreal after the transfer.

## `light/lights.json`

`id` is the light object's name. `strength` is a relative number from 1 to 5, never lux or lumens: give every emitting model the same plain strength unless the reference clearly shows one brighter or dimmer. `fixture` names the model it sits in. When the worker places a light it adds `pos_m` and `energy_w` (Blender watts), which lint compares with the scene. A row with `object` instead says an emissive mesh stands in for the light.

```json
[{"id": "L_KEY", "type": "sun", "reason": "sun through W windows", "strength": 3, "rotation_deg": [0, -25, 250]},
 {"id": "L_L03", "type": "point", "reason": "1970s wall sconce, map L03", "fixture": "SM_Sconce_L03", "strength": 2,
  "pos_m": [6.0, 1.2, 2.1], "energy_w": 25}]
```

Real units (`intensity_lux`, `intensity_lm`, `temperature_k`, `ies`) come with Part 2, before L1, in every mode.

## Part 2: detailed brief (just before L1)

Written as the first step of `lighting-passes`, once every asset in P0 to P7 is final (earlier only if the interview set an earlier timing). Add the "Detailed" section to `plan/lighting-brief.md`. Set `brief.yaml › light_depth` (asked in the interview; default `mood`, and `measured` in `full_cg`):

- **`direction`:** key and sky direction and which practicals are on. No numbers.
- **`mood`:** also colour temperatures and the key to fill balance, set by eye against the mood references. No numbers.
- **`measured`:** outside `full_cg`, one number: the hero camera's mean luminance within 10 % of the reference's, and no region grids unless the user asks. In `full_cg`, everything below in real-world units; it is the default there.

Contents:

- **Key light and why.** Every light in `light/lights.json` carries a reason, such as the sun through the west window.
- **Colour temperatures** of the practicals, from the colour the reference shows (*full_cg:* lamp and real temperature from research).
- *full_cg:* **Exposure target** from a real reference photo's EXIF: `EV100 = log2(N² / t × 100 / ISO)`.
- **Key to fill ratio:** about 4:1 for direct sun, 3:1 at sunrise or sunset, 2:1 overcast. In stops it is log2 of the ratio. A target in `full_cg`, a guide for the eye elsewhere.
- **Focal points** in the order the eye should find them, matching the map.
- **Lighting groups.** The draft groups for L2, split into lighting groups (8 to 10, each carries a value) and texturing sub-materials (stay under a lighting group). On the corridor pilot the groups grew from 10 to 12, each new one costing a question. *full_cg:* a value range per group, and any value-floor exceptions listed now with a reason, such as soot, dark paint or black PVC around 50.
- *full_cg:* **Decode path**, written once: render against photo, both decoded from display; render against render, EXRs; values and hues by luminance (`blender-adapter/scripts/measure.py`).
- *full_cg, with a photo to match:* wall-order and shadow-shape checks against the photo are L2 checks from the start, because they depend on the values.

## Exposure sweep (before anyone works toward a numeric target)

Any number in the brief (the hero mean luminance in `measured`, or the `full_cg` targets) must be reachable before a worker chases it.

1. On the saved render from the hero camera, measure each target at exposure offsets from -3 to +3 stops in third-stop steps (`measure.py`), and re-render at the best offsets, because a view transform isn't linear.
2. Put the table in the brief.
3. One value meets every target: that is the exposure to try. None does: stop and tell the user, with the targets that conflict, the closest value and its misses, and a relaxed target to approve. Nobody works toward the original target.

## `lighting_focus: deferred`

`brief.yaml › lighting_focus` is `active` by default. When the user says colour, contrast and light wait for their lighting references, set it to `deferred` and log it:

- The rig and `light/exposure.json` are frozen. Nothing is added, moved or re-exposed.
- `plan/lighting-brief.md` is marked `status: provisional`.
- Reviewers skip the light aspect and give no light or colour notes. `lighting-passes` doesn't start.

When the references arrive, set it back to `active`, rewrite the detailed part from them and run the sweep.

## Exposure

One manual exposure from the blockout on, locked at G2 after lint shows no face without a material, written to `light/exposure.json`, and set for real at L1. The steps are in `house-rules` rule 8 and `docs/pipeline/lighting.md`; this skill doesn't repeat them.
