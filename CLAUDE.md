# 3D Technical Director pipeline

Claude Code pipeline that builds 3D scenes in Unreal Engine 5.8 and Blender 5.2 from photos and concept art. Start with `docs/pipeline/README.md`; the manager's skill is `.claude/skills/scene-pipeline/`. Machine setup is in `docs/setup-windows.md`.

## Working rules

- **Check every change request first.** When the user asks for a change, compare it with the research in `docs/pipeline/` (`studio-workflows.md`, `lighting.md`, `improvements.md`) and with the earlier decisions it touches. Say plainly if it conflicts with something, or if the research points to a better option, and recommend one. Then make the change unless it changes the goal, in which case ask first.
- **One writer per live editor.** Only the Unreal worker changes the Unreal editor, and only the route's Blender worker drives the open Blender. Parallel agents work headless on their own asset files.
- **Keep the repo free of third-party files.** Don't commit third-party reference photos, `.blend`, `.uasset` or `.fbx` files. Reference photos stay in the work folder; `refs/index.yaml` keeps the source link for each one.
- **Third-party skills** keep their `LICENSE` (and `NOTICE`) files. Note every change to them in the skill's "Pipeline notes" and in `.claude/skills/CREDITS.md`.
- **Where the session runs.** Building needs the Unreal and Blender MCP servers on the user's PC. A cloud session (claude.ai/code without Remote Control) can't reach them: say so and stick to planning, research, specs and reviews of uploaded captures.
- Pipeline changes (skills, docs, `knowledge/`, `feedback/`, `toolbox/`) are committed and pushed to the working branch when they change, as `checkpoint` describes. Projects stay local and are never committed (`house-rules` rule 3).
