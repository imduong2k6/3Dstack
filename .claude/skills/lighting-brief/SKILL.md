---
name: lighting-brief
description: Write the L0 lighting brief for a pipeline scene, covering the key light and its motivation, practicals from the map, exposure target, key to fill ratio, colour temperatures, focal order and mood references, plus lights.json. Use it in Stage 2, before the blockout's rough light.
---

# L0 lighting brief

Full method and numbers: `docs/pipeline/lighting.md`.

## By mode (`brief.yaml › mode`)

- **`blockout` and `camera_match`:** light for the reference's palette and mood. Every light still has a reason, but intensity, colour temperature and exposure are set by eye against the reference, not from real-world values; creative choices are fine when they serve the mood. Pick the exposure once at the blockout and lock it. The key to fill ratios below are a starting guide. Skip the items marked *full_cg*.
- **`full_cg`:** everything below, in real-world units.

## Write `plan/lighting-brief.md`

- **Key light and why.** Every light in `light/lights.json` carries a reason, such as the sun through the west window. A light with no reason needs the user's OK.
- **Practicals** come from the cyan shapes on the map, with fixture type and the colour the reference shows (*full_cg:* lamp and real colour temperature from research).
- *full_cg:* **Exposure target** from a real reference photo's EXIF: `EV100 = log2(N² / t × 100 / ISO)`. Exposure stays locked from the blockout to the hue pass.
- **Key to fill ratio:** about 4:1 for direct sun, 3:1 at sunrise or sunset, 2:1 overcast. In stops it is log2 of the ratio.
- **Focal points** in the order the eye should find them, matching the map.
- **Mood references**, where AI images are welcome, tagged `mood`.
- **Lighting groups.** The draft groups for L2, split into lighting groups (8 to 10, each carries a value) and texturing sub-materials (stay under a lighting group). On the corridor pilot the groups grew from 10 to 12, each new one costing a question. *full_cg:* a value range per group, and any value-floor exceptions listed now with a reason, such as soot, dark paint or black PVC around 50.
- *full_cg:* **Decode path**, written once: render against photo, both decoded from display; render against render, EXRs; values and hues by luminance (`blender-adapter/scripts/measure.py`).
- *full_cg with a photo to match:* wall-order and shadow-shape checks against the photo are L2 checks from the start, because they depend on the values.
- **Route notes.** `unreal`: Lumen, physical units, a Post Process Volume with Min EV100 = Max EV100. `blender`: the Cycles light paths, view transform and fixed exposure. `blender_unreal`: the rough light in Blender is for direction only; final values are set in Unreal after the transfer.

## `light/lights.json`

```json
[{"id": "L_KEY", "type": "directional", "reason": "sun through W windows", "intensity_lux": 100000,
  "temperature_k": 5500, "rotation_deg": [0, -25, 250]},
 {"id": "L03", "type": "point", "reason": "1970s wall sconce, map L03", "temperature_k": 2700,
  "intensity_lm": 450, "ies": null}]
```

Reviewed with the layout at G1.
