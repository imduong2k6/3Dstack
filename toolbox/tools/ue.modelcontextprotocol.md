---
id: ue.modelcontextprotocol
kind: unreal_plugin
name: Unreal MCP
version: "1.0"
checked: 2026-10-29
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Experimental/ModelContextProtocol (plugin descriptor)
  - toolbox/tools/mcp.unreal-mcp.md (tool names, live findings 2026-10-27)
  - Online docs not fetched this run (local descriptors only); verify before relying on version-specific detail.
pipeline_stages: [unreal-adapter, all Unreal stages]
routes: [unreal, blender_unreal]
---

# Unreal MCP

**What it does:** Epic's plugin that hosts the MCP server inside the editor (port 8000 in this setup). Tool names live in mcp.unreal-mcp.

## Use it for
- Every Unreal build step: this is the channel the Unreal worker uses.

## How to call it
- Enable in Project Settings > Plugins and restart; the editor must be open for the server to answer.
- See mcp.unreal-mcp.md for toolsets and call sequences.

## Settings that matter
- Port and auth are in ModelContextProtocolSettings (see mcp.unreal-mcp).

## Gotchas
- 2026-10-29 scan: connection to port 8000 was refused (ECONNREFUSED); editor not running or server not started. Engine query skipped.
- Experimental in 5.8.

## Don't use it for
- Parallel agents on the same editor (one writer per live editor).

## Version notes
- Checked against 1.0 on the author's PC (2026-10-29).
