# Lighting

The order follows the Naughty Dog environment pipeline as this pipeline understands it (block mesh with rough lighting, first pass in gray, value pass, hue pass, Post FX; a pipeline convention, source to confirm: the slides it came from haven't been found), with two changes:

1. The three passes run **after the modular kit and set dressing are in** (after P9).
2. The pipeline **stops after the hue pass**. Textures, Post FX and the LUT are yours.
3. **The mode sets how much is measured** (`brief.yaml › mode`, since 29 Oct 2026). In `blockout` and `camera_match`, light follows the reference's palette and mood, set by eye, and the passes are colour only: one gray, one value and one flat colour per group, roughness untouched, no measuring self-test, implied values, value floors or solved hexes (`lighting-passes`, fast path). Everything below that uses real-world units, EXIF exposure, measured regions or solved colours applies to `full_cg`. The user asked for this after the corridor pilot, where the measured method matched the photo well but took most of the lighting time.

| Step | When | What happens | Approved at |
| --- | --- | --- | --- |
| L0 Lighting brief | Planning | Key light and its motivation, practicals from the map, exposure target, key to fill ratio, colour temperatures, mood references | G1 |
| Rough rig | Blockout | Key at physical units, sky, fog, exposure locked | G2 |
| L1 Gray pass | After kit and dressing | Every surface sRGB 128; full rig built in order and measured | L1 |
| L2 Value pass | After L1 | One gray per lighting group, 8 to 10 groups, then relight | L2 |
| L3 Hue pass | After L2 | Numbered palette that keeps each value; light colour temperatures | L3 |
| Hand-off | After L3 | Texturing brief and palette | G3 |

## L0 Lighting brief

- **Key light and why:** sun through the far window, a street lamp, a sign. Every light in `lights.json` carries a reason. A light with no reason needs your OK.
- **Practicals** come from the cyan shapes on the map, with fixture type and real colour temperature from research.
- **Exposure target** from a real reference photo's EXIF: `EV100 = log2(N² / t × 100 / ISO)`.
- **Key to fill ratio:** about 4:1 direct sun, 3:1 sunrise or sunset, 2:1 overcast. In stops, the difference is log2 of the ratio (4:1 is 2 stops).
- **Focal points** in the order the eye should find them, matched to the player path.
- **Mood references**, where AI images are welcome.

## Rough rig at the blockout

- Unreal 5.8: Directional Light in lux (about 100,000 lx for a sunny midday), Sky Atmosphere, Sky Light with real-time capture, Exponential Height Fog with volumetric fog, Lumen GI and reflections.
- Post Process Volume with Min EV100 = Max EV100 = the brief's target. Auto exposure makes a 10 lx scene and a 100,000 lx scene look equally bright, which hides every ratio.
- Interiors: the key comes through openings. Placeholder lights only for practicals that drive the composition.
- Blender scenes: Sun lamp with a physical sky and a fixed exposure in Color Management.
- The review camera set is created here and reused by every later gate.

## L1 Gray pass

**Setup**

- Pass switch = Gray. Every base colour is 0.216 linear (sRGB 128).
- Roughness stays at each group's default. Emissive surfaces keep their colour because they are light sources. Glass and water keep their transmission.

**Build order, broad to fine**

1. Key light and dominant direction
2. Sky and fill, with bounce from Lumen
3. Practicals, with IES profiles where the real fixture is known
4. Accents and rims that separate the focal point, each with a reason
5. Light functions and gobos: window frames, blinds, foliage
6. Atmosphere: height fog, local fog volumes, volumetric scattering

**Checks**

- Push a few lights further before adding more.
- Key to fill ratio spot-metered with the HDR (Eye Adaptation) visualisation, within half a stop of the brief.
- Focal point has the strongest local contrast; shadow shapes lead along the player path.
- Dark areas still readable at the locked exposure.
- No large clipped areas in the capture histograms. No light leaks at kit seams.
- Light count and shadow casters within budget. If baking, stationary light overlap stays at 4 or fewer.

**Captures:** review cameras in Lit with the gray pass on. The scripted capture can't render Lighting Only (scene captures ignore that viewport setting, tested in UE 5.8.3), and with every surface at one gray the result reads the same way. Exposure is checked in the editor with the HDR (Eye Adaptation) visualisation.

## L2 Value pass

**Setup and rules**

- Every material instance belongs to one material group (`material_group` in the asset spec). Each group gets one gray.
- 8 to 10 lighting groups, planned in the L0 brief. A group carries a value at L2; finer differences (a khaki lid on a grey cabinet) are texturing sub-materials under it, not new groups.
- Non-metal values inside about sRGB 60 to 240. Metals keep metallic 1 and are judged by their reflection. Dark non-metals (soot, dark paint, black PVC, around 40 to 55) are allowed as exceptions listed in the L0 brief with a reason.
- On a photo-matched scene, measure each group's implied value (photo divided by the gray render in region boxes) right after the L1 baseline, before searching for fill lights: on the corridor pilot two fill lights were built and rejected for a wall-order miss that the values fixed.
- Values come from real materials; the Art Director brings references.
- Large surfaces in the middle of the range; extremes for small accents and the focal area.
- Relight afterwards: darker surfaces return less bounce.

**Checks:** focal hierarchy survives against L1; squint (blurred) capture still separates big shapes; neighbouring groups that must read apart are far enough apart; luminance histogram and a per-group table on the board.

**Example, hotel corridor**

| # | Group | sRGB | Linear |
| --- | --- | --- | --- |
| 1 | Ceiling | 200 | 0.578 |
| 2 | Trim | 215 | 0.680 |
| 3 | Upper wall | 170 | 0.402 |
| 4 | Door frames | 150 | 0.305 |
| 5 | Wainscot | 120 | 0.188 |
| 6 | Furniture | 105 | 0.141 |
| 7 | Doors | 90 | 0.102 |
| 8 | Metal fixtures | 140 | 0.262 |
| 9 | Carpet | 64 | 0.051 |

## L3 Hue pass

**Setup and rules**

- Pass switch = Hue. A numbered palette, one colour per group, about 10 entries.
- Each colour keeps its group's value. The supervisor desaturates the hue capture by luminance (Rec.709 on linear values, re-encoded; not luma on encoded values) and compares it with L2. Starting tolerance: 5 sRGB levels per group.
- Start each colour from the group's implied (light-removed) hue: the photo divided by the gray render at the same pixels, so the light's colour cancels. The photo as seen is only for the final comparison; picking from it counts the light's warmth twice. Solve each hex to its value through the view transform (Blender: `selftest_light.py`'s `solved_hex`).
- Big surfaces stay low in saturation; saturated colour is for small accents and the focal point.
- Light colour is set here: warm against cool between key and fill, practicals at their real temperature (`Use Temperature` on Unreal lights).
- The Art Director checks the palette against real materials of the era and the mood references.

| Source | About |
| --- | --- |
| Candle, fire | 1,900 K |
| Household tungsten bulb | 2,700 K |
| Halogen | 3,000 K |
| Cool white fluorescent | 4,000 K |
| Midday sun | 5,500 K |
| Overcast sky | 6,500 K |
| Blue sky, in shade | 10,000 K and up |

Common approximations; real fixtures found in research override them.

**Stop.** After you approve L3 the pipeline writes the texturing brief and stops. Exposure stays locked so your textures are judged under the approved light.

## One switch for all passes

```text
MPC_LookDev        scalar PassMode   0 gray · 1 value · 2 hue · 3 textured
M_Env_Master       BaseColor = PassMode 0 → 0.216 (sRGB 128)
                               PassMode 1 → GroupValue   (scalar, linear)
                               PassMode 2 → GroupHue     (vector, linear)
                               PassMode 3 → your BaseColor texture × tint
                   Roughness = GroupRoughness until PassMode 3, then your texture
                   static switch LookDev: off at ship, so the branch compiles out
MI_<Group>         one parent instance per material group, child instances per asset
```

```python
# apply_palette.py, run through the Unreal MCP's Python tool (sketch)
mel = unreal.MaterialEditingLibrary
for g in palette["groups"]:
    mi = unreal.load_asset(g["instance"])
    mel.set_material_instance_scalar_parameter_value(mi, "GroupValue", srgb_to_linear(g["value_srgb"]))
    if "hue_hex" in g:
        mel.set_material_instance_vector_parameter_value(mi, "GroupHue", hex_to_linear_color(g["hue_hex"]))
    mel.update_material_instance(mi)
```

Blender: the gray pass is View Layer › Override › Material with one Principled BSDF at 0.216. Value and hue passes use a script that sets each material's Base Color from its group and keeps the original in a custom property, so the swap can be undone.

## Sources

- Naughty Dog environment pipeline slides: First Pass, Value Pass, Hue Pass (not found; the GDC 2014 talk page and an 80.lv interview don't describe the three passes)
- [GDC 2014: In-Game and Cinematic Lighting of The Last of Us](https://gdcvault.com/play/1020475/In-Game-and-Cinematic-Lighting)
- [Magnopus: Lighting in Unreal with photography principles](https://www.magnopus.com/blog/lighting-in-unreal-with-photography-principles)
- [80.lv: Working on lighting for video games](https://80.lv/articles/working-on-lighting-for-video-games)
- [Shinsoj: PBR colour space conversion and albedo chart](https://shinsoj.artstation.com/blog/Q9j6/pbr-color-space-conversion-and-albedo-chart)
