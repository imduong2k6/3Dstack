# Stats that count hidden cutters and retired objects

**Seen on:** corridor pilot, P8, Oct 2026 · **Modes:** all · **Routes:** blender

**Symptom:** triangle and object counts in `stats.json` included boolean cutters and a retired collection. A supervisor note about it waited 15 hours.
**Cause:** the script walked every object instead of what renders.
**Fix:** `stats.py` walks the evaluated depsgraph and skips objects and collections that are off for render. Tool faults go in the same round's fix list, never in the notes.
**Test:** `selftest_light.py` checks the stats against a known chart.
