---
id: ue.pcg                      # same id as the manifest
kind: unreal_plugin             # unreal_plugin | blender_addon | blender_extension | mcp_server | cli | asset_library
name: Procedural Content Generation Framework
version: "1.0"                  # the version this file was checked against
checked: 2026-10-28
sources:
  - https://dev.epicgames.com/documentation/...
pipeline_stages: [placement-phases, set-dressing]
routes: [unreal, blender_unreal]
---

# <Name>

**What it does:** one or two sentences.

## Use it for
- Pipeline uses, by stage. Example: P3 services, cable and pipe runs along splines.

## How to call it
- Editor path, Python API, console command, CLI flags, or MCP tool names, with one short example each.

## Settings that matter
- Defaults to change for this pipeline, and why.

## Gotchas
- Known bugs, performance traps, version differences. Add a dated line, with the fix that worked, the same day a tool fault is hit (`toolbox-scan` Rules).

## Don't use it for
- Cases where another tool or a manual step is better.

## Version notes
- What changed in this version that matters to the pipeline.
