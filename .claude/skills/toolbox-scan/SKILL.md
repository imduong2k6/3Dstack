---
name: toolbox-scan
description: Scan the machine for Unreal plugins, Blender add-ons and extensions, asset libraries, MCP servers and CLIs, then research each new or changed tool's docs (local first, then online) and write an instruction file per tool into toolbox/, so later scans only research what changed. Use it at the start of a project, after installing something, or when the manifest is more than 14 days old.
---

# Toolbox scan

Run by the toolbox scanner agent. Read-only on the engines: list, never install, enable or change settings.

## Files

```text
toolbox/
  manifest.<machine>.json     # every tool found: id, kind, version, path, signature, doc_file, researched, status (no project or open-file names: house-rules 3)
  tools/<tool-id>.md          # one instruction file per tool, shared across machines
  scans/<machine>-<date>.json # raw scan output, not committed (in .gitignore)
```

Tool ids: `ue.<plugin>`, `bl.<addon>`, `blx.<extension>`, `mcp.<server>`, `cli.<name>`, `lib.<library>`.

## Steps

1. **Scan.** Run `scripts/scan_toolbox.py` with the machine's paths (the usual Windows ones are in [references/commands.md](references/commands.md); check `brief.yaml` and `toolbox/README.md` for others).

   The script keeps engine plugins only when they are enabled in the project, come from Fab or the Marketplace, or are on its list of pipeline-relevant plugins (PCG, Geometry Script, Python, Movie Render Queue, USD, Water, Cable Component, Model Context Protocol and similar). Pass `--all-engine` to list everything.

2. **Ask the engines what the files can't tell you.** Through the Unreal and Blender MCP servers (read-only calls), list the enabled plugins and add-ons, the Blender asset libraries in Preferences, and the MCP tool names each server exposes. Record the MCP tool names in `toolbox/tools/mcp.<server>.md`; the adapters read them from there.

3. **Diff.** The scan output has `new`, `changed`, `undocumented`, `unchanged` and `missing`. Only `new`, `changed` and `undocumented` tools get researched. `unchanged` tools are skipped. `missing` tools stay in the manifest marked missing, so their instruction files can be reused if they come back.

4. **Research each tool that needs it.**
   - Local first: the `.uplugin` description and DocsURL, the add-on's `bl_info` or `blender_manifest.toml`, a README or docs folder in the install, and the tool's own help (`--help`).
   - Then online: the official docs page, the Fab or Superhive or extensions.blender.org page, the changelog for this version, and one good tutorial if the docs are thin.
   - Write `toolbox/tools/<tool-id>.md` from [instruction-template.md](instruction-template.md).
   - Mark it in the manifest with `--update-manifest` (once per scan) and `--mark <tool-id> --doc <file>` (commands in [references/commands.md](references/commands.md)).
   - A version change only needs the changelog read and the "Version notes" section updated.
   - Cap the work at 20 tools per run. If there are more, do the ones the current brief is most likely to use first and list the rest as pending.

5. **Project shortlist (optional).** Skip it when the agents can work from `toolbox/tools/` alone. Otherwise write `plan/toolbox.md` for the current project: the tools that matter for this brief and route, grouped by stage, each linking to its instruction file. Add a "Worth installing" section for tools the research or workflow notes suggest that aren't installed. Installing is the user's call.

## Rules

- Never enable, disable, install, update or configure anything.
- Every instruction file names its sources and the date it was checked.
- Paid tools: note the licence, but never buy or sign in.
- **Tool faults go back into the note.** When a worker hits a fault in a tool (a stall, a crash, a wrong default) and finds the fix, write it the same day under `## Gotchas` in `toolbox/tools/<tool-id>.md`, dated, with the fix that worked. Memory or `log.md` alone is not enough: the next project reads the note.
