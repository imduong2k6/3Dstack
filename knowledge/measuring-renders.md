# Value and hue checks that disagree with what the eye sees

**Seen on:** corridor pilot, L1 to L3, Oct 2026 · **Modes:** full_cg · **Routes:** blender

**Symptom:** eight measuring faults across the lighting passes: luma used for luminance, an EXR compared with a display-decoded photo, a light's flare inside a region box, hidden objects in the stats. A solved colour read 12.5 levels off through AgX.
**Cause:** each check had its own ad hoc method.
**Fix:** one method in `blender-adapter/scripts/measure.py`: decode both from display for render against photo, compare EXRs for render against render, use Rec.709 luminance on linear values, mask flare ellipses, erode regions. Solve hexes through the view transform with `selftest_light.py`.
**Test:** `selftest_light.py` before L1 in full_cg.
