---
name: checkpoint
description: Save points for the pipeline. A change to pipeline files (skills, docs, knowledge, feedback, toolbox) is committed and pushed as `[pipeline] <what>`. A project save point (end of each phase, lighting pass or user decision) is a log.md line, the step backup and a plan/steps.json entry, with no git, because projects stay local. Use it whenever the scene pipeline reaches a save point or a pipeline file changes.
---

# Checkpoint

Projects stay local: nothing under `projects/` or the work folder is ever committed, pushed or put in a PR (`house-rules` 3). The two kinds of save point below are never mixed.

## Project save point

At the end of each phase, each lighting pass and each decision the user sends. No git.

1. **Backup.** A copy of the live file in the phase folder's `backups/` (`house-rules` 4), unless the save point is a decision with no new work.
2. **Ledger.** One entry in `plan/steps.json` with `step_log.py log` (`blender-adapter`).
3. **Log line** in `log.md`, always, even when there is nothing to back up: `YYYY-MM-DD HH:MM <who> <gate> r<round> <decision or status>: <what>`, with the backup path. Add the engine revision: the Unreal project's commit or changelist, and the `.blend` path and save time.

## Pipeline commit

When a skill, a doc, a `knowledge/` note, a `feedback/` file or a `toolbox/` file changes.

1. **Stage by path:** `.claude/`, `docs/`, `knowledge/`, `feedback/`, `toolbox/` (not raw scans), `CLAUDE.md`, `README.md`. Never stage `projects/`, captures, engine binaries or the work folder; `git status` shows nothing from them. A lesson from a project reaches `feedback/` only with the user's OK, with private names and places taken out.
2. **Lint** when a skill or agent file changed: `python .claude/skills/checkpoint/scripts/check_skills.py`. Fix its errors (a broken description hides a skill from the list). Warnings are for review.
3. **Message:** `[pipeline] <what changed>`, on the working branch.
4. **Push** after every commit. Never force-push. If a push fails, keep the commit, retry with backoff, and if it still fails tell the user in chat.
