---
name: checkpoint
description: Commit and push the pipeline project at a save point (end of each phase, lighting pass, or user decision), tag approved gates, and record the engine project's revision. Use it whenever the scene pipeline reaches a save point and auto_commit is on.
---

# Checkpoint

Only when `auto_commit: true` in the brief (the default).

1. **Branch:** `scene/<slug>`, one per project. Create it from the default branch on the first save.
2. **Stage** the project folder, skill feedback files, and compressed captures (PNG or JPEG). Never stage engine binaries unless Git LFS rules exist for them (see `docs/pipeline/data-and-commits.md`).
3. **Message:** `[<slug>] <gate> r<round> <decision or status>: <short what>`, for example `[hotel-corridor] L2 r1 changes_requested: value pass`.
4. **Engine revision:** record the Unreal project's commit or changelist and the `.blend` path and save time in `log.md`.
5. **Push** after every commit. Never force-push. If a push fails, keep the commit, retry with backoff, and if it still fails show it on the board and in chat.
6. **Tag** approved gates: `<slug>/<gate>`, for example `hotel-corridor/G2`.
