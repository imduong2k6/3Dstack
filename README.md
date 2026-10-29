# 3Dstack

A Claude Code pipeline that builds 3D scenes in Unreal Engine 5.8 and Blender 5.2 from photos and concept art. You describe the scene in chat. The pipeline interviews you, plans the work, lays out a floor plan and builds a detailed, accurate blockout. It then lights it and hands it over with a flat colour on every material group, ready for you to texture. A team of agents does the work: a manager, Blender and Unreal workers, Modelers, a supervisor, an Art Director and researchers.

## Use it

1. Set up the PC once: [docs/setup-windows.md](docs/setup-windows.md) (Unreal and Blender MCP servers, uv, Git for Windows).
2. Clone this repo and open Claude Code in it. The skills and agents in `.claude/` load on their own.
3. Describe the scene, with images attached or a folder path, for example:

   > A 1970s hotel corridor, abandoned, golden hour, for my UE game. Refs in D:\Refs\hotel. Tier S, autopilot.

The `scene-pipeline` skill takes it from there.

To use it from another Claude account, give that account's GitHub user access to this private repo (Settings › Collaborators), then clone it the same way. A cloud session on claude.ai/code can plan, research and review captures, but building needs the MCP servers on your PC, so use a local session or Remote Control.

## What you choose in the prompt

| Choice | Options | Default |
| --- | --- | --- |
| Mode | `blockout`: logical, detailed placement, with light and colour following the reference's mood. `camera_match`: also matched to a photo's camera. `full_cg`: a finished CG scene with measured light, real-world values and generated detailed props | `blockout` |
| Tier | S (one photo, one room), M (a few references, several rooms), L (many references, a hero scene). It sets research depth, reviews and which gates wait for you | Asked at G0 |
| Route | `unreal`, `blender_unreal` (built in Blender, lit in Unreal), `blender` (CG in Cycles) | Asked at G0 |
| Budgets | Hours, tokens, Tripo and Magnific credits, triangles, lights | No cap unless you give one |
| Autopilot | Gates are posted for the record and the defaults taken without waiting. It still stops for credits, deletions and scope changes | Off |

## What's inside

- Skills: [.claude/skills](.claude/skills) (start with `scene-pipeline`). Third-party skills keep their licences; see [.claude/skills/CREDITS.md](.claude/skills/CREDITS.md).
- Agents: [.claude/agents](.claude/agents)
- Design, schemas, research and the review board and brief form pages: [docs/pipeline](docs/pipeline/README.md)
- Solved problems, read before any research: [knowledge](knowledge/README.md)
- Tool instruction files written by the toolbox scanner: [toolbox](toolbox/README.md)
- Skill changes and the evidence behind them: [feedback/CHANGELOG.md](feedback/CHANGELOG.md)

Your projects go in `projects/<slug>/`. The `.blend`, FBX and reference photos stay in a work folder outside git.
