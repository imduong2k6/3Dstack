---
id: mcp.blender
kind: mcp_server
name: Blender Lab MCP server (blender_mcp v1.0.3)
version: "1.0.3 (commit 2cea8d566dde, 2026-09-11)"
checked: 2026-10-28
sources:
  - live tools/list and get_objects_summary on the author's PC (claude -p with the repo's .mcp.json, BLENDER_MCP_PORT=9877)
  - https://projects.blender.org/lab/blender_mcp (source read at commit 2cea8d566dde07fbac28a61d698909d69724e853, mcp/blmcp/tools and tools_helpers/connection.py)
  - https://projects.blender.org/lab/blender_mcp/releases/download/v1.0.3/mcp-1.0.3.zip (add-on: blender_manifest.toml, __init__.py)
pipeline_stages: [blockout, modeling, modular-kit, placement-phases, set-dressing, lighting-passes]
routes: [blender, blender_unreal]
---

# Blender Lab MCP server

**What it does:** an MCP server (`uvx ... blender-mcp`, configured as `blender` in `.mcp.json`) that sends Python to the **MCP** add-on (extension id `mcp`, Blender 5.1+) running inside the user's Blender, over a localhost socket (9876 by default, **9877 on the author's PC**).

**Status on the author's PC (2026-10-28): connected.** Add-on 1.0.3 is installed in `extensions/user_default/mcp` and enabled, with auto-start on and its port preference set to 9877. `BLENDER_MCP_PORT=9877` is set user-wide. The older "MCP for Blender" v1.8 add-on (`bl.blender_mcp`) stays enabled on 9876 for Claude Desktop. Both servers run in the same Blender (5.2.3 LTS). `claude -p` with the repo's `.mcp.json` connected, and `get_objects_summary` answered for `SkillTest.blend`: scene `Scene`, workspace `Matchmoving`, an empty `Scene Collection`, no camera.

## Tools (26, live `tools/list`)

| Tool | Read-only | Use |
| --- | --- | --- |
| `execute_blender_code` | no | Run Python with full `bpy` in the live session |
| `*_for_cli` (6): `execute_blender_code_for_cli`, `get_blendfile_summary_{datablocks,missing_files,of_linked_libraries,path_info,usage_guess}_for_cli` | as the live version | Same as the live tool, but on a `blend_file` path in a background Blender (`BLENDER_PATH`). If the live session has that file open with unsaved changes, it works on a temporary saved copy |
| `get_objects_summary` | yes | Collection tree with objects (name, type, parent, data, selection, visibility) |
| `get_object_detail_summary` | yes | One object in detail |
| `get_blendfile_summary_datablocks` | yes | Datablock counts |
| `get_blendfile_summary_missing_files` | yes | Missing external files |
| `get_blendfile_summary_of_linked_libraries` | yes | Linked libraries |
| `get_blendfile_summary_path_info` | yes | File path info |
| `get_blendfile_summary_usage_guess` | yes | What the file seems to be for |
| `get_screenshot_of_area_as_image` | yes | Screenshot of one editor area |
| `get_screenshot_of_window_as_image` | yes | Screenshot of the window |
| `get_screenshot_of_window_as_json` | yes | Window layout as JSON |
| `jump_to_tab_by_name`, `jump_to_tab_by_space_type` | no (UI) | Switch workspace tab |
| `jump_to_view3d_object_by_name`, `jump_to_view3d_object_data_by_name` | no (UI) | Frame an object in the 3D view |
| `render_thumbnail_to_path`, `render_viewport_to_path` | writes a file | Render to an image path |
| `search_api_docs`, `get_python_api_docs`, `search_manual_docs` | yes | Bundled Blender 5.x API and manual search (works without a live Blender) |

## Setup

1. Install and enable the add-on: drag `mcp-1.0.3.zip` into Blender, or `blender.exe --command extension install-file --repo user_default --enable mcp-1.0.3.zip`.
2. Preferences > Add-ons > MCP: Auto Start is on by default (port 9876, host localhost, 1 s delay). It needs **Preferences > System > Allow Online Access** on (it is on here).
3. `BLENDER_PATH` and `BLENDER_BIN` point to `Z:/SteamLibrary/steamapps/common/Blender/blender.exe` on this machine (set with `setx`; open a new terminal).
4. `BLENDER_MCP_HOST` and `BLENDER_MCP_PORT` override the socket for the server; the add-on's port is in its preferences. Change both together. On the author's PC both are 9877.

## Gotchas

- **Port clash with `bl.blender_mcp` (MCP for Blender v1.8).** Both default to 9876. Whichever starts first gets the port: v1.8 auto-starts and skips if the port is busy, and the Lab add-on stores the bind error in its preferences. The Lab server talks newline-delimited JSON `{"code": ..., "strict_json": ...}`, which v1.8 doesn't understand. On the author's PC both stay installed: v1.8 keeps 9876 for Claude Desktop's Blender connector (which reads `BLENDER_PORT`, not `BLENDER_MCP_PORT`), and the Lab add-on's port preference is 9877 with `BLENDER_MCP_PORT=9877` set user-wide. Only one of them should change the scene while a pipeline build runs.
- **The first start can time out.** `uvx` builds the pinned server from git on first use, which took longer than Claude Code's 30 s MCP connect timeout here (the log said `Building blender-mcp ...`, then `CONNECT_TIMEOUT`). Set `MCP_TIMEOUT=240000` for that first run; after that the build is cached.
- A Blender that was open before the add-on was installed won't have it until restarted. If that Blender saves preferences on quit (auto-save prefs is on here), it can write back a preference file without the add-on enabled. Save your work and close Blender before installing.
- `execute_blender_code` runs with the user's rights and no sandbox. Keep it on localhost.

## Don't use it for

- Per-asset headless work: use `bin/blender-bg` (factory settings), so several Modelers can work at once.
