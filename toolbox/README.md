# Toolbox

Written by the toolbox scanner (`.claude/skills/toolbox-scan`). One manifest per machine and one instruction file per tool. The next scan only researches tools that are new or have changed version.

| Path | Contents |
| --- | --- |
| `manifest.<machine>.json` | Every tool found on that machine, with a signature that changes when the tool's descriptor changes |
| `tools/<tool-id>.md` | How the pipeline uses the tool, checked against its local and online docs |
| `scans/` | Raw scan output. Not committed |

## Default paths on Windows

| What | Path |
| --- | --- |
| Unreal Engine 5.8 | `C:/Program Files/Epic Games/UE_5.8` |
| Blender 5.2 user config (add-ons, extensions) | `%APPDATA%/Blender Foundation/Blender/5.2` |
| Unreal project plugins | `<project folder>/Plugins` |

Change them in the scan command if your installs live elsewhere.
