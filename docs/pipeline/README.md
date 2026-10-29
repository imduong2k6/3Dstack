# 3D Scene Pipeline, v6

A Claude Code pipeline that builds a 3D scene or object from real-life photos and concept art with the Unreal Engine 5.8 and Blender 5.2 MCP servers. It starts from a chat prompt, interviews you, plans, builds and lights the scene up to an approved hue pass, then hands off to you for texturing.

- Setup on your PC, and using it from any Claude Code session: [../setup-windows.md](../setup-windows.md)
- Parallel agents: [parallel.md](parallel.md)
- Input form (optional): [pages/scene-brief.html](pages/scene-brief.html)
- Review board: [pages/gate-review.html](pages/gate-review.html)
- Agents: [`.claude/agents/`](../../.claude/agents) · Skills: [`.claude/skills/`](../../.claude/skills)
- What changed and what to try next: [improvements.md](improvements.md)

The HTML pages are the sources of the published Claude artifacts. The form and board store data through the artifact runtime, so they only work fully when opened as artifacts.

## Stack

| Choice | Effect |
| --- | --- |
| Unreal Engine 5.8, about 80% of work | Epic's ModelContextProtocol plugin (`unreal-mcp` in `.mcp.json`) and Epic's Claude Code plugin. Final assembly, PCG, lighting passes and captures on the game routes |
| Blender 5.2, about 20% | Blender Lab MCP server v1.0.3 (`blender` in `.mcp.json`) for the live session, headless Blender for per-asset work. All modelling; the whole scene on the Blender routes |
| Tripo and Magnific, only for detailed work | Generated props in `full_cg` or a detailed blockout (`tripo-props`, `generated-asset`), then repaired to spec by the Modeler. Magnific also does images and stock reference search |
| Windows | Paths and the toolbox scan default to Windows installs |

## Mode and tier

The default job is a detailed, accurate **blockout** from the references, with a flat colour per material group for you to texture. Final assets come later, generated or made by hand. You set two things in the prompt (or at G0):

- **Mode:** `blockout` (default; light and colour follow the reference's mood), `camera_match` (also matched to a photo's camera), or `full_cg` (a finished CG scene with measured light and real-world values).
- **Tier:** S, M or L. It sets research depth, how often reviews run and which gates wait for you. One photo of one room is S.

Add "autopilot" to the prompt to have the gates posted for the record while the pipeline carries on with their defaults. Solved problems live in [`knowledge/`](../../knowledge) and are read before any research. Details: `.claude/skills/scene-pipeline/SKILL.md`.

## Routes

| Route | Built in | Lit in | Use for |
| --- | --- | --- | --- |
| `unreal` | Unreal, with models from Blender | Unreal | Game scenes, the default |
| `blender_unreal` | Blender, then transferred | Unreal | Game scenes you'd rather assemble in Blender |
| `blender` | Blender | Blender Cycles | CG stills, turntables and shots |

Details: [routes.md](routes.md).

## Flow

```mermaid
flowchart TD
  C[Your prompt in chat, images welcome] --> S0[Intake and input review]
  F[Scene Brief form, only if needed] -.-> S0
  S0 --> I[Interview: multiple-choice rounds]
  I --> PL[plan.md]
  PL --> G0{G0 approve the plan}
  G0 --> S1[Research: reference, pro workflows, toolbox scan]
  S1 --> S2[2D layout map and lighting brief]
  S2 --> G1{G1 approve layout, light and workflow picks}
  G1 --> S3[Blockout and rough light]
  S3 --> G2{G2 approve blockout}
  G2 --> S4[Kit plan, generation, pilot assets]
  S4 --> K{K approve the pilots}
  K --> AL[Asset lane: Modelers in parallel, Asset Tech]
  G2 --> S5[Level lane: placement P0 to P9 with proxies]
  AL -- finished assets in batches --> S5
  S5 --> P{Review after each phase}
  P --> R{Route}
  R -- blender_unreal --> T[Transfer to Unreal, gate T]
  R -- unreal or blender --> L1
  T --> L1[L1 Gray pass]
  L1 --> L2[L2 Value pass]
  L2 --> L3[L3 Hue pass]
  L3 --> S9[Texturing brief and retro]
  S9 --> G3{G3 sign-off and suggestions for next time}
  G3 --> STOP([Pipeline stops. Textures, Post FX and LUT are yours])
```

After G2 two lanes run at once: the asset lane builds kit pieces and props headless, several Modelers at a time, while the route's worker places phases with proxies and swaps finished assets in. Every gate posts to the Gate Review Board and waits for your decision. The supervisor and the Art Director review every build and lighting step from the same camera set, and the manager merges their notes and yours into one fix list. The pipeline commits and pushes at every save point.

## Documents

| File | Contents |
| --- | --- |
| [stages.md](stages.md) | Each stage's inputs, work, outputs, agents and exit rule |
| [routes.md](routes.md) | The three build routes and the Blender to Unreal transfer |
| [lighting.md](lighting.md) | Lighting brief, rough rig, the gray, value and hue passes, the pass switch |
| [agents.md](agents.md) | Agents, models, the interview, the Modeler, the Asset Tech and Generator, the toolbox scanner, researchers and the retro |
| [parallel.md](parallel.md) | What runs at the same time, what stays single, and the settings |
| [studio-workflows.md](studio-workflows.md) | How game and VFX studios staff and run environment work, and what v4 took from it |
| [data-and-commits.md](data-and-commits.md) | Project folder layout, data contracts for the form and board, auto-commit |
| [improvements.md](improvements.md) | What changed in v5 and v4, suggestions, and what still needs a test |
| [schemas/](schemas/) | JSON Schemas for the brief, gate entries, feedback, the palette and the toolbox manifest |
| [examples/](examples/) | The hotel corridor example used on the board |

## Status

The skills and agents are written. The toolbox scan script is tested. The Blender scripts are tested headless against Blender 5.2's Python module; the Unreal scripts are sketches to verify on the first project. See [improvements.md](improvements.md#test-on-the-first-project).
