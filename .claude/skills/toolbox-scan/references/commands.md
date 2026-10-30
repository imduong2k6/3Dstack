# Toolbox scan commands

Run from the repo root. Paths are the usual Windows ones; use the machine's own.

## Scan

```bash
python "${CLAUDE_SKILL_DIR}/scripts/scan_toolbox.py" --machine "$COMPUTERNAME"   --ue-root "C:/Program Files/Epic Games/UE_5.8"   --uproject "<project>.uproject"   --blender-config "$APPDATA/Blender Foundation/Blender/5.2"   --asset-lib "<each Blender asset library and Fab or Megascans folder>"   --manifest "toolbox/manifest.$COMPUTERNAME.json" --out "toolbox/scans/$COMPUTERNAME-$(date +%F).json"
```

## Mark the manifest

```bash
python "${CLAUDE_SKILL_DIR}/scripts/scan_toolbox.py" --machine "$COMPUTERNAME"   --manifest "toolbox/manifest.$COMPUTERNAME.json" --update-manifest "<scan json>"   # once per scan
python "${CLAUDE_SKILL_DIR}/scripts/scan_toolbox.py" --machine "$COMPUTERNAME"   --manifest "toolbox/manifest.$COMPUTERNAME.json" --mark ue.pcg --doc toolbox/tools/ue.pcg.md
```
