---
id: ue.movierenderpipeline
kind: unreal_plugin
name: Movie Render Queue (Movie Render Pipeline)
version: "1.3"
checked: 2026-10-27
sources:
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/MovieScene/MovieRenderPipeline/MovieRenderPipeline.uplugin
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/MovieScene/MovieRenderPipeline/Source/MovieRenderPipelineCore/Private/MovieRenderPipelineCommandLine.cpp
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/MovieScene/MovieRenderPipeline/Content/Python (MoviePipelineEditorExample.py, MovieGraphCreateConfigExample.py, MovieGraphQuickRenderExample.py, MoviePipelineExampleRuntimeExecutor.py)
  - Z:/Unreal Engine/UE_5.8/Engine/Plugins/MovieScene/MovieRenderPipeline/Config/DefaultMovieRenderPipeline.ini
  - .claude/skills/ue5-mcp/SKILL.md (sections 5.15, 5.17, 10.1)
  - https://dev.epicgames.com/documentation/unreal-engine/movie-render-pipeline-in-unreal-engine?lang=en-US
  - https://dev.epicgames.com/documentation/unreal-engine/transitioning-to-the-movie-render-graph-from-movie-render-queue-in-unreal-engine
  - https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes
  - https://forums.unrealengine.com/t/unreal-engine-5-8-released/2729274
pipeline_stages: [blockout, lighting-passes, texturing-handoff]
routes: [unreal, blender_unreal]
---

# Movie Render Queue (Movie Render Pipeline)

**What it does:** Epic's offline renderer for stills and sequences from Sequencer: temporal and spatial anti-aliasing, tiled and multi-pass output, EXR and image sequences. It has two front ends, the Queue (job and config presets) and the node-based Movie Render Graph. Plugin 1.3, `EnabledByDefault: false`, not listed in SkillTest.uproject.

## Use it for
- Review captures that every gate reuses: render each camera in `light/cameras.json` the same way for the G2 blockout, L1-L3 lighting passes and the Stage T comparison.
- Final stills and turntables on the game routes; the CG route renders in Blender Cycles instead.
- Hand-off renders for `texturing-handoff` (the same cameras with the Textured pass switch).

## How to call it
- Enable: Edit > Plugins > Rendering > Movie Render Queue, restart. Open: Window > Cinematics > Movie Render Queue, or the dropdown beside Render Movie in Sequencer. Quick Render gives a one-click real-time render.
- Graph: in the Queue set the Settings column to Movie Render Graph, create a graph asset, then edit it.
- Python in the editor: `subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)`, `queue = subsystem.get_queue()`, `queue.allocate_new_job(unreal.MoviePipelineExecutorJob)`, then `subsystem.render_queue_with_executor_instance(unreal.MoviePipelinePIEExecutor())` with `on_executor_finished_delegate.add_callable_unique(fn)`. Keep executor, queue and callbacks in module globals or they are garbage-collected and the callback silently never fires (engine example). Rendering is asynchronous.
- Graph creation from Python: `graph.create_node_by_class(unreal.MovieGraphGlobalOutputSettingNode)`, `...MovieGraphDeferredRenderPassNode`, `...MovieGraphRenderLayerNode`, `...MovieGraphImageSequenceOutputNode_PNG`. Select nodes are not exposed to Python.
- Command line (from the engine source): `UnrealEditor-Cmd.exe <uproject> <map> -game -LevelSequence="/Game/X.X" -MoviePipelineConfig="/Game/Presets/P.P" -windowed -resx=1920 -resy=1080 -log -notexturestreaming`. `-MoviePipelineLocalExecutorClass=` plus `-ExecutorPythonClass=` runs a custom Python executor.
- Engine examples to copy: the folder `Content/Python` above, presets `Content/Editor/Stills/Presets/Still_Draft` and `Still_Ultra`, and `DefaultRenderGraph` / `BasicConfigTemplateGraph`.

## Settings that matter
- Graph: temporal samples are global (Sampling Method node); spatial samples, anti-aliasing and tone curve live in the Renderer node. The Deferred Rendering entry must stay in the job or nothing renders. Game Overrides node is on by default; if deleted it stops applying.
- Alpha Output (Project Settings > Rendering > Default Settings) and Support Primitive Alpha Holdout (Deferred) for holdouts.
- Remote render needs saved assets; local render runs through Play in Editor.

## Gotchas
- Pipeline-learned (ue5-mcp): MRQ stops at the end of the active camera cut section regardless of the playback range, and its PIE executor re-reads the level sequence from disk, so save the sequence package before rendering.
- Transition page lists unsupported in the graph: High Resolution tiles, Apple ProRes, Final Cut XML, Prestreaming Recorder, 32-bit post-process materials (nDisplay now has graph integration per 5.8 notes). Quick Render settings override the graph.
- The engine's Python example still uses `MovieGraphPathTracedRenderPassNode`; 5.8 renamed it to `MovieGraphPathTracerRenderPassNode` (core redirect in the plugin config).

## Don't use it for
- Route `blender` renders (Cycles). Quick viewport checks: a viewport capture is cheaper.

## Version notes
- 5.8: Movie Render Graph is Production Ready (the 5.7 doc still calls it Beta). The repo's ue5-mcp section 10.1 says the graph is 5.8-only; the 5.7 doc (labelled Beta) and the 5.8 notes ("enters Production Ready status") imply it existed earlier, so only the status is new. New: Light Modifier, Accumulation DOF, Basic Config queue window, audio submix choice.
- Hotfixes: 5.8.1 Accumulation DOF with motion blur; 5.8.2 -NullRHI render crash; 5.8.3 (installed) Naming Tokens not resolving and wrong alpha with Accumulation DOF plus Spectral Lateral Chromatic Aberration.
