---
name: texturing-handoff
description: Start the texturing brief at G2 and finalise it after the hue pass is approved, with one section per material group (value, hue, roughness, real-material references, wear notes), where the user textures, and final stats. In full_cg it also holds the texture set list and the texel density. Start it at G2; finalise it at Stage 9, before G3 sign-off.
---

# Texturing hand-off

The pipeline stops here. Textures, Post FX and the LUT are the user's.

## `handoff/texturing-brief.md`

Start it at G2 and keep adding to it, so Stage 9 only finalises it. At G2 it holds the material groups from the blockout, the wear notes so far (`handoff/wear-notes.md`), the Art Director notes the user marked Later, and the inventory rows (`plan/inventory.yaml`) that each group covers. Every phase adds its wear notes and Later notes. Stage 9 adds the approved values and hues, the stats and the route specifics.

**Where the user textures.** State it in the first lines, from the brief: Blender on `blender_unreal` (the textures travel with the transfer, and the Unreal material instances show them at `PassMode = 3`), Blender on `blender`, Unreal on `unreal`. If `brief.yaml` says otherwise, the brief wins.

What the user gets: every mesh carries its group's flat L3 colour, in material slots named by group (`M_<group>`), with roughness untouched (outside `full_cg`).

For each material group in `light/palette.json`:

- Value (sRGB and linear) and hue (hex). The user's albedo should average close to these so the approved lighting holds.
- Roughness range, metal or not.
- Real-material references from research and Art Director notes.
- Wear and story notes: every item in `handoff/wear-notes.md` (where and how much), Art Director notes the user marked Later, and items from `backlog.md`. Wear is the user's texturing work and is never modelled: `house-rules` rule 1.
- Which material instances and assets use it, and the inventory rows it covers.
- `full_cg` only: the texture set, trim sheet or tiling material, and texel density.

Also include final stats, and route specifics:

- `full_cg` only: the full texture set list with resolution and memory at the project texel density.
- Unreal: material instances on `M_Env_Master`; set `PassMode = 3` (textured) to see the textures under the approved light.
- Blender: material per group. `full_cg` only: a UDIM plan from screen coverage at the closest camera, times 2.

## Then

Run `retro`, post G3 with `gate-board`, and write the save point (`checkpoint`). Exposure stays locked so the textures are judged under the approved light.
