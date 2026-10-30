# Windows setup

What the repo already holds, so you don't set it up by hand:

| File | What it does |
| --- | --- |
| `.mcp.json` | Two MCP servers: `unreal-mcp` (Epic's plugin, HTTP on port 8000) and `blender` (Blender Lab MCP server v1.0.3, started with `uvx`) |
| `.claude/settings.json` | Enables Epic's Claude Code plugin `unreal-engine-skills-for-claude-code` and pre-approves the two servers once you trust the folder |
| `.claude/skills/` | The pipeline skills plus the installed third-party skills (see `.claude/skills/CREDITS.md`) |
| `bin/blender-bg` | Runs Blender headless on one asset file, so several Modelers can work at once |

The steps below are the machine side. Do them once per PC. Remote Control can do all of them for you.

## 1. Tools

| Tool | Why | Install |
| --- | --- | --- |
| Git for Windows | Git, plus the bash that Epic's plugin hook and `bin/blender-bg` use | `winget install --id Git.Git -e` |
| uv | Starts the Blender MCP server | `winget install --id astral-sh.uv -e` |
| Claude Code | Runs the pipeline | Already installed if Remote Control works |
| Unreal Engine 5.8 | Epic's MCP plugin ships with 5.8 under `Engine/Plugins/Experimental/ModelContextProtocol` | Epic Games Launcher |
| Blender 5.2 | The MCP add-on needs 5.1 or newer | blender.org |

## 2. Clone the repo

```powershell
git clone https://github.com/imduong2k6/3Dstack.git
cd 3Dstack
```

## 3. Unreal project

1. Back up the `.uproject` file.
2. In its `Plugins` array, enable these four (add any that are missing, flip `false` to `true`):

   ```json
   { "Name": "ModelContextProtocol", "Enabled": true },
   { "Name": "AllToolsets", "Enabled": true },
   { "Name": "PythonScriptPlugin", "Enabled": true },
   { "Name": "EditorScriptingUtilities", "Enabled": true }
   ```

   `ModelContextProtocol` is the server, `AllToolsets` gives it its tools, and the other two run the adapter's Python scripts.
3. Start the server with the editor. Add this to `<Project>\Saved\Config\WindowsEditor\EditorPerProjectUserSettings.ini` (create the file if it doesn't exist):

   ```ini
   [/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]
   bAutoStartServer=True
   ```

4. Open the project. The Output Log should show the MCP server starting on port 8000. If another program holds the port, set `ServerPortNumber` in the same section and set `UE_MCP_PORT` to the same number for Claude Code.

## 4. Blender

1. Install the MCP add-on v1.0.3. Either drag `mcp-1.0.3.zip` from the [release page](https://projects.blender.org/lab/blender_mcp/releases) into Blender twice (first adds the Blender Lab repository, second installs), or from a terminal:

   ```powershell
   & "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --command extension install-file --repo user_default --enable mcp-1.0.3.zip
   ```

2. In the add-on's preferences, turn on auto-start. The default port is 9876. If another Blender MCP add-on already uses 9876 (for example the community "MCP for Blender" behind Claude Desktop's Blender connector), keep it and set this add-on to 9877, then run `setx BLENDER_MCP_PORT 9877` so the repo's `.mcp.json` connects to the right one. Only one of them should change the scene while a pipeline build runs.
3. Tell the pipeline where Blender is, for the MCP server and for headless runs:

   ```powershell
   setx BLENDER_BIN  "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
   setx BLENDER_PATH "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
   ```

   Open a new terminal afterwards so the variables are visible.

## 5. Claude Code

1. Start `claude` in the repo folder and trust it. Accept the prompt to install `unreal-engine-skills-for-claude-code`. If no prompt appears, run `/plugin install unreal-engine-skills-for-claude-code@claude-plugins-official`, and if the marketplace is missing, `/plugin marketplace add anthropics/claude-plugins-official` first.
2. With Unreal and Blender open, run `/mcp`. Both `unreal-mcp` and `blender` should show as connected. The first start of `blender` builds the server from git with `uvx`, which can take longer than Claude Code's 30-second start limit; if it shows as failed, start Claude Code once with `MCP_TIMEOUT=240000` set (tested on 28 Oct 2026). After that the build is cached. Open a new terminal or restart the app after any `setx`, since only programs started afterwards see the new value.
3. Check each with a read-only call: Unreal `list_toolsets`, Blender `get_objects_summary`.
4. When the first Modeler or Asset Tech runs `bash bin/blender-bg`, approve it for the session. Background agents send their permission prompts to your main session, and a session-wide approval covers all of them.

## 6. First run

Done on the pilot PC on 27 and 28 Oct 2026. The results are in `toolbox/`, and the fixes are in the adapters. Repeat these steps on a new machine.

1. Run the toolbox scanner. It records the real tool and toolset names in `toolbox/tools/mcp.unreal-mcp.md` and `toolbox/tools/mcp.blender.md`.
2. Test the adapter scripts on the pilot project and fix them in the repo: `capture.py`, `stats.py`, `import_layout.py` in Unreal, and a 1 m cube FBX round trip that must import as 100 units.

## Use it from any Claude Code session

The repo is the package: skills, agents, `.mcp.json` and the plugin setting all load when Claude Code starts in the repo folder. No separate install is needed for another account.

| Where you start Claude Code | What works |
| --- | --- |
| On your PC, terminal or desktop app, in the repo folder | Everything: skills, agents, both MCP servers, Epic's plugin, parallel agents, commits |
| Code on the web or your phone (claude.ai/code), connected to your PC through Remote Control | Everything, because the session runs on your PC. On the PC, run `claude remote-control` in the repo folder (or turn on Remote Control in the desktop app's settings), then pick that session in Code |
| A cloud session in Code, with the repo cloned into Anthropic's cloud | Planning only: intake, interview, research, layout, specs, the retro, and reviews of captures you upload. The cloud can't reach Unreal or Blender on your PC, so `/mcp` shows both servers as failed |
| Another Claude account | The same three options. Sign in with that account and open the repo. To push commits, connect a GitHub account with write access to this repo. If that account has a Tripo connector or workflow, add `tripo` to `generation_services` in the brief |

To run the pipeline from another folder, copy `.claude/`, `.mcp.json`, `bin/` and `docs/` into it. A plugin package is possible too, but the agents' tool guards would need the plugin's server names (`mcp__plugin_<plugin>_<server>`), so the plain repo is the safer route.

## Safety

- Both servers run code from the model with your user's rights: Epic's `execute_tool_script` runs Python in the editor, and the Blender server runs Python in Blender with no sandbox. Keep them on localhost and don't run Claude Code with `--dangerously-skip-permissions` on a project you care about.
- Save and commit the Unreal project before a long session, so you can roll back.
