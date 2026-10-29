---
name: texturing-handoff
description: Write the texturing brief after the hue pass is approved, with one section per material group (value, hue, roughness, real-material references, wear notes and texture set), the texel density, the texture set list and final stats. Use it at Stage 9, before G3 sign-off.
---

# Texturing hand-off

The pipeline stops here. Textures, Post FX and the LUT are the user's.

## `handoff/texturing-brief.md`

What the user gets in Blender: every mesh carries its group's flat L3 colour, in material slots named by group (`M_<group>`), with roughness untouched (outside `full_cg`).

For each material group in `light/palette.json`:

- Value (sRGB and linear) and hue (hex). The user's albedo should average close to these so the approved lighting holds.
- Roughness range, metal or not.
- Real-material references from research and Art Director notes.
- Wear and story notes: every item in `handoff/wear-notes.md` (grime, stains, leaks, rust, cracks and chips, with where and how much), Art Director notes the user marked Later, and items from `backlog.md`.
- Texture set, trim sheet or tiling material, and texel density.
- Which material instances and assets use it.

Also include the full texture set list with resolution and memory at the project texel density, final stats, and route specifics:

- Unreal: material instances on `M_Env_Master`; set `PassMode = 3` (textured) to see the textures under the approved light.
- Blender: material per group, and a UDIM plan from screen coverage at the closest camera, times 2.

## Then

Run `retro`, post G3 with `gate-board`, and tag the commit after sign-off. Exposure stays locked so the textures are judged under the approved light.
