---
id: ue.mcpclienttoolset
kind: unreal_plugin
name: MCP Client Toolset
version: "1.0"
checked: 2026-10-29
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/Experimental/Toolsets/MCPClientToolset (plugin descriptor)
  - toolbox/tools/mcp.unreal-mcp.md
  - Online docs not fetched this run (local descriptors only); verify before relying on version-specific detail.
pipeline_stages: [unreal-adapter]
routes: [unreal, blender_unreal]
---

# MCP Client Toolset

**What it does:** Toolset plugin that lets the Unreal editor act as an MCP client of other servers. Companion to ue.modelcontextprotocol.

## Use it for
- Only if an in-editor agent must call external MCP servers; the pipeline normally drives Unreal from outside.

## How to call it
- Enable alongside ue.modelcontextprotocol; configure servers in the toolset settings (the scanner changes nothing).

## Settings that matter
- Leave default unless an in-editor agent is wanted.

## Gotchas
- Experimental; not exercised by the pipeline yet. Not verified live (MCP down).

## Don't use it for
- The normal route (external Claude to Unreal MCP server).

## Version notes
- Checked against 1.0 on the author's PC (2026-10-29).
