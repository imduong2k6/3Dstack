---
id: bl.blender_mcp
kind: blender_addon
name: MCP for Blender (legacy socket add-on)
version: "1.8"
checked: 2026-10-27
sources:
  - C:/Users/Admin/AppData/Roaming/Blender Foundation/Blender/5.2/scripts/addons/blender_mcp.py (bl_info, auto-start code)
pipeline_stages: []
routes: []
---

# MCP for Blender 1.8 (legacy)

**What it does:** a single-file add-on (`scripts/addons/blender_mcp.py`) that serves a JSON socket for an older Blender MCP server. On this machine, Claude Desktop's own `blender` connector talks to it.

## Use it for
- Nothing in the pipeline. The pipeline uses the Blender Lab MCP add-on and server (`mcp.blender`).

## How it behaves
- Auto-starts its server on the scene's `blendermcp_port` (9876 by default) shortly after Blender starts and on every file load, unless the user stopped it or the port is already taken (it logs "port 9876 is already in use; auto-start skipped").
- Running in the user's Blender on 2026-10-28 and holding 9876, next to the Lab add-on on 9877.
- Reports add-on protocol 14, while the `mcp-for-blender` 2.2.4 server expects 15. Calls still work. `uvx mcp-for-blender install-addon` updates it if the user wants.

## Gotchas
- **Would clash with `mcp.blender` on port 9876.** Both default to 9876, and the Lab server can't speak this add-on's protocol. The user keeps both: this one stays on 9876 for Claude Desktop, and the Lab add-on runs on 9877 (`BLENDER_MCP_PORT=9877`, see `mcp.blender.md`). The pipeline never disables this add-on.

## Don't use it for
- Pipeline steps. Its tool names differ from the ones the adapters expect.
