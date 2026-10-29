# Dense meshes for paper cards and posters

**Seen on:** corridor pilot, P7 and P8, Oct 2026 · **Modes:** all · **Routes:** all

**Symptom:** small cards such as SM_CARD_A4_Torn_D02_Patch had about 2,600 triangles each, 45,000 to 780,000 per square metre, with the torn edge modelled. The topology was unusable.
**Cause:** the torn outline was cut into the mesh instead of the material.
**Fix:** paper, posters, stickers and signs are planes: one quad when flat, subdivided only where they bend. The torn edge is an alpha cut-out in the material (a noise mask on the UV edge, or a shared mask image).
**Test:** `stats.py › flat_dense` lists any thin mesh above 20,000 triangles per square metre (a 20 x 20 subdivided A4 card is about 12,800).
