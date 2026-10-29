# A face-slot colour change spreads to every instance

**Seen on:** corridor pilot, L3, Oct 2026 · **Modes:** all · **Routes:** blender

**Symptom:** recolouring a few faces of one letterbox recoloured every letterbox and the kit source.
**Cause:** the faces belonged to a mesh shared by several objects.
**Fix:** move material groups by object link; `palette.assign` refuses face slots on a mesh with more than one user.
**Test:** `blender-adapter/scripts/check_palette.py`.
