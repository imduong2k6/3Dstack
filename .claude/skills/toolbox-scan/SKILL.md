---
name: toolbox-scan
description: Scan the machine for Unreal plugins, Blender add-ons and extensions, asset libraries, MCP servers and CLIs, then research each new or changed tool's docs (local first, then online) and write an instruction file per tool into toolbox/, so later scans only research what changed. Use it at the start of a project, after installing something, or when the manifest is more than 14 days old.
---

# Toolbox scan

Run by the toolbox scanner agent. Read-only on the engines: list, never install, enable or change settings.

## Files

```text
toolbox/
  manifest.<machine>.json     # every tool found: id, kind, version, path, signature, doc_file, researched, status
  tools/<tool-id>.md          # one instruction file per tool, shared across machines
  scans/<machine>-<date>.json # raw scan output, not committed (in .gitignore)
```

Tool ids: `ue.<plugin>`, `bl.<addon>`, `blx.<extension>`, `mcp.<server>`, `cli.<name>`, `lib.<library>`.

## Steps

1. **Scan.** Run the script with the machine's paths. On Windows the usual paths are shown; check `brief.yaml` and `toolbox/README.md` for others.

   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/scan_toolbox.py" --machine "$COMPUTERNAME" \
     --ue-root "C:/Program Files/Epic Games/UE_5.8" \
     --uproject "<project>.uproject" \
     --blender-config "$APPDATA/Blender Foundation/Blender/5.2" \
     --asset-lib "<each Blender asset library and Fab or Megascans folder>" \
     --manifest "toolbox/manifest.$COMPUTERNAME.json" --out "toolbox/scans/$COMPUTERNAME-$(date +%F).json"
   ```

   The script keeps engine plugins only when they are enabled in the project, come from Fab or the Marketplace, or are on its list of pipeline-relevant plugins (PCG, Geometry Script, Python, Movie Render Queue, USD, Water, Cable Component, Model Context Protocol and similar). Pass `--all-engine` to list everything.

2. **Ask the engines what the files can't tell you.** Through the Unreal and Blender MCP servers (read-only calls), list the enabled plugins and add-ons, the Blender asset libraries in Preferences, and the MCP tool names each server exposes. Record the MCP tool names in `toolbox/tools/mcp.<server>.md`; the adapters read them from there.

3. **Diff.** The scan output has `new`, `changed`, `undocumented`, `unchanged` and `missing`. Only `new`, `changed` and `undocumented` tools get researched. `unchanged` tools are skipped. `missing` tools stay in the manifest marked missing, so their instruction files can be reused if they come back.

4. **Research each tool that needs it.**
   - Local first: the `.uplugin` description and DocsURL, the add-on's `bl_info` or `blender_manifest.toml`, a README or docs folder in the install, and the tool's own help (`--help`).
   - Then online: the official docs page, the Fab or Superhive or extensions.blender.org page, the changelog for this version, and one good tutorial if the docs are thin.
   - Write `toolbox/tools/<tool-id>.md` from [instruction-template.md](instruction-template.md).
   - Mark it in the manifest:

     ```bash
     python "${CLAUDE_SKILL_DIR}/scripts/scan_toolbox.py" --machine "$COMPUTERNAME" \
       --manifest "toolbox/manifest.$COMPUTERNAME.json" --update-manifest "<scan json>"   # once per scan
     python "${CLAUDE_SKILL_DIR}/scripts/scan_toolbox.py" --machine "$COMPUTERNAME" \
       --manifest "toolbox/manifest.$COMPUTERNAME.json" --mark ue.pcg --doc toolbox/tools/ue.pcg.md
     ```

   - A version change only needs the changelog read and the "Version notes" section updated.
   - Cap the work at 20 tools per run. If there are more, do the ones the current brief is most likely to use first and list the rest as pending.

5. **Project shortlist.** Write `plan/toolbox.md` for the current project: the tools that matter for this brief and route, grouped by stage, each linking to its instruction file. Add a "Worth installing" section for tools the research or workflow notes suggest that aren't installed. Installing is the user's call.

## Rules

- Never enable, disable, install, update or configure anything.
- Every instruction file names its sources and the date it was checked.
- Paid tools: note the licence, but never buy or sign in.
