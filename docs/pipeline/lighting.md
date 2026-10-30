# Lighting

The order follows the Naughty Dog environment pipeline as this pipeline understands it (block mesh with rough lighting, first pass in gray, value pass, hue pass, Post FX; a pipeline convention, source to confirm: the slides it came from haven't been found), with these changes:

1. The three passes run **once the blockout and modelling are finished**: every asset in P0 to P7 is final (`house-rules` rule 7). Until then the rig is neutral.
2. The pipeline **stops after the hue pass**. Textures, Post FX and the LUT are yours.
3. **Light depth sets how much is measured** (`brief.yaml › light_depth`: `direction | mood | measured`; it follows the mode by default, since 29 Oct 2026). In `blockout` and `camera_match` the default is `mood`: light follows the reference's palette and mood, set by eye, and the passes are L1 plus one colour gate (one flat colour per group, value and hue together, solved hexes kept), roughness untouched, no measuring self-test, implied values or value floors (`lighting-passes`, fast path). Everything below that uses real-world units, EXIF exposure, measured regions, implied values or value floors applies to `full_cg`, where `measured` is the default. The user asked for this after the corridor pilot, where the measured method matched the photo well but took most of the lighting time.

Two rules live in `house-rules` and this page has the detail: rule 7 (the rig stays neutral until the passes; `lighting_focus: deferred`) and rule 8 (exposure).

| Step | When | What happens | Approved at |
| --- | --- | --- | --- |
| L0 part 1: neutral rig brief | Stage 2 | Sky and key direction, time of day, the models that emit, mood references, `lights.json` | G1 |
| Neutral rig, built | Blockout | Sky, key, a light on every emitting model at a plain strength, one manual exposure | G2 (exposure locked) |
| L0 part 2: detailed brief | After blockout and modelling (P0 to P7 final), before L1 | Key and its motivation, key to fill ratio, colour temperatures, focal order, light depth, exposure sweep | L1 |
| L1 Gray pass | After the detailed brief | Every surface sRGB 128; full rig built in order; real exposure set | L1 |
| L2 Value pass | After L1 | One gray per lighting group, 8 to 10 groups, then relight | L2 |
| L3 Hue pass | After L2 | Numbered palette that keeps each value; light colour temperatures | L3 |
| Hand-off | After L3 | Texturing brief and palette | G3 |

Fast path: L2 and L3 are one colour gate, posted as L3.

## L0 Lighting brief

Two parts in `plan/lighting-brief.md`. Part 1 is written at Stage 2 and reviewed at G1; part 2 is written just before L1.

### Part 1: neutral rig (Stage 2)

- **Direction and time of day:** where the sun and sky light come from and when, roughly matching the references and the researched place.
- **Emitting models:** every model that gives off light (bulbs, lamps, signs, screens), from the cyan shapes on the map and `plan/inventory.yaml`. Each gets one light in `lights.json` with a reason (a wall sconce on the map, a street lamp) at a plain, even strength. A light with no reason needs your OK.
- **Mood references**, where AI images are welcome.
- No exposure target, ratio, colour temperature or region grid yet. Reviewers check only that nothing is clipped or black and that each capture's mean stays inside the `light/exposure.json › mean_band`, if one is recorded.

### Part 2: detailed brief (before L1)

Written first thing by `lighting-passes`, once every asset in P0 to P7 is final (earlier only if the interview set an earlier timing). It sets `light_depth`:

| `light_depth` | What the brief sets |
| --- | --- |
| `direction` | Key and sky direction, which practicals are on. No numbers |
| `mood` | Also colour temperatures and the key to fill balance, by eye against the mood references. No numbers |
| `measured` | Outside `full_cg`: one number, the hero camera's mean luminance within 10 % of the reference's; no region grids unless you ask. In `full_cg` (the default there): real-world units, an exposure target, key to fill ratio, a value range per group, region targets |

- **Key light and why:** sun through the far window, a street lamp, a sign.
- **Colour temperatures** of the practicals (`full_cg`: real fixtures from research).
- **Exposure target** (`full_cg`) from a real reference photo's EXIF: `EV100 = log2(N² / t × 100 / ISO)`.
- **Key to fill ratio:** about 4:1 direct sun, 3:1 sunrise or sunset, 2:1 overcast. In stops, the difference is log2 of the ratio (4:1 is 2 stops). A target in `full_cg`, a guide for the eye elsewhere.
- **Focal points** in the order the eye should find them, matched to the player path.
- **Lighting groups** for L2: 8 to 10, each carrying a value, with texturing sub-materials under them. `full_cg`: a value range per group, and value-floor exceptions listed now with a reason.

**Exposure sweep, before anyone works toward a numeric target.** On the saved render from the hero camera, measure each target (`measure.py`) at exposure offsets from -3 to +3 stops in third-stop steps, and re-render at the best offsets (a view transform isn't linear). Put the table in the brief. If one value meets every target, that is the exposure to use. If none does, tell the user before any work starts: which targets conflict, the closest value and its misses, and a relaxed target to approve. On an earlier project a 3 × 3 region grid that no exposure could meet cost a whole light search.

**`lighting_focus: deferred`** (`brief.yaml`, default `active`). When the user says colour, contrast and light wait for their lighting references: the rig and `light/exposure.json` are frozen, part 2 is marked `status: provisional`, reviewers skip the light aspect and give no light or colour notes, and `lighting-passes` doesn't start. When the references arrive, set it back to `active`, rewrite part 2 from them and run the sweep.

## Exposure lifecycle (house rule 8)

One manual exposure from the blockout on, never auto, so captures compare across rounds.

1. **Blockout:** set once by eye on the neutral rig so nothing is clipped or black. Unreal: a Post Process Volume with Min EV100 = Max EV100. Blender: a fixed exposure and view transform in Color Management.
2. **Lock at G2**, once lint shows no face without a material (an empty slot renders wrong, so a value set earlier was judged on the wrong image). Write it to `light/exposure.json`; lint checks that the scene matches the file. Keys: `exposure`, `view_transform`, `look`, `display`, optional `gamma`, `white_balance` and `curves` (Blender, compared by lint); `ev100` (Unreal: Min = Max EV100); `mean_band`, `[low, high]` in sRGB levels for a capture's mean luminance, only when the user gives one at G2; `locked` (the gate) and `date`. The band applies to captures that use the scene's view transform (Material Preview, EEVEE, Cycles), never to Workbench captures, which render at Standard and exposure 0.
3. **G2 to L1:** a change needs a reason in `log.md`, and the file is updated.
4. **L1 sets the real exposure:** run the sweep when the brief has a numeric target and set the value it found; with no target, keep the blockout value unless the gray render clips or crushes. Write it to `light/exposure.json` with the reason in `log.md`.
5. **After L1:** locked through L3 and texturing, so your textures are judged under the approved light.

## Neutral rig at the blockout

- Unreal 5.8: Directional Light, Sky Atmosphere, Sky Light with real-time capture, Exponential Height Fog with volumetric fog, Lumen GI and reflections. `full_cg`: physical units (about 100,000 lx for a sunny midday). Otherwise `lights.json` uses a relative strength from 1 to 5, and the worker picks one engine value per step.
- Post Process Volume with Min EV100 = Max EV100 = the one manual value (lifecycle above). Auto exposure makes a 10 lx scene and a 100,000 lx scene look equally bright, which hides every ratio.
- Interiors: the key comes through openings. A light on every model that emits (bulbs, lamps, signs, screens), at the same plain strength. Changed 30 Oct 2026: this page used to put placeholder lights only on practicals that drive the composition; you now want one on every emitting model.
- Blender scenes: Sun lamp with a physical sky and a fixed exposure in Color Management. On `blender_unreal` the Blender light is judged for direction only.
- The review camera set is created here and reused by every later gate.

## L1 Gray pass

**Setup**

- Pass switch = Gray. Every base colour is 0.216 linear (sRGB 128).
- Exposure: the real value is set here (lifecycle above), then it stays locked.
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
- When the brief sets a ratio: key to fill spot-metered with the HDR (Eye Adaptation) visualisation, within half a stop of it.
- Focal point has the strongest local contrast; shadow shapes lead along the player path.
- Dark areas still readable at the L1 exposure.
- No large clipped areas in the capture histograms. No light leaks at kit seams.
- Light count and shadow casters within budget. If baking, stationary light overlap stays at 4 or fewer.

**Captures:** review cameras in Lit with the gray pass on. The scripted capture can't render Lighting Only (scene captures ignore that viewport setting, tested in UE 5.8.3), and with every surface at one gray the result reads the same way. Exposure is checked in the editor with the HDR (Eye Adaptation) visualisation.

## L2 Value pass

**Setup and rules**

- Every material instance belongs to one material group (`material_group` in the asset spec). Each group gets one gray.
- 8 to 10 lighting groups, planned in part 2 of the L0 brief. A group carries a value at L2; finer differences (a khaki lid on a grey cabinet) are texturing sub-materials under it, not new groups.
- Non-metal values inside about sRGB 60 to 240. Metals keep metallic 1 and are judged by their reflection. Dark non-metals (soot, dark paint, black PVC, around 40 to 55) are allowed as exceptions listed in part 2 of the L0 brief with a reason.
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
- Each colour keeps its group's value. The supervisor desaturates the hue capture by luminance (Rec.709 on linear values, re-encoded; not luma on encoded values) and compares it with L2. Tolerance: 5 sRGB levels per group in `full_cg`; about 8 on the render, or a squint plus the value order, on the fast path (an analytic red read +12.5 levels through the view transform, so 5 can't be met by eye).
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

**Stop.** After you approve L3 the pipeline finalises the texturing brief and stops. Exposure stays locked so your textures are judged under the approved light.

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
