---
name: scene-intake
description: Turn the user's chat prompt, attached images or a submitted Scene Brief form into a draft brief.yaml and a reference index for the scene pipeline, and decide whether the form is needed. Use it at the start of a new pipeline project.
---

# Scene intake

Chat first. Most projects start with a message such as "a 1970s hotel corridor, abandoned, golden hour, for my UE game, refs in D:\Refs\hotel". Only send the form when it saves the user time.

## Steps

1. **Collect the inputs.** The chat text, any images in the chat, paths the user named, and, if the user submitted a brief on the form, that brief. The form lives at the Scene Brief Intake artifact; read it with `ArtifactData list briefs`, newest `submitted` first.
2. **Extract into `brief.yaml`** using the field names in `docs/pipeline/schemas/brief.schema.json` (schema 2). For each field, record where the value came from:

   ```yaml
   route: {value: blender_unreal, from: chat}        # chat | form | image | default | assumed
   time_of_day: {value: golden, from: default}
   ```

3. **Images.** Copy chat images and form uploads into `refs/inbox/`. Form uploads are artifact assets: fetch each id with `Artifact read` (`path` = the asset id). Record them in `refs/index.yaml` with `from: chat | form`, and leave role tags for the input reviewer.
4. **Required fields:** subject, target, route, context (or a context prompt or images), and at least one reference source. The deadline, if any, comes from the prompt text.
5. **Mode, tier, autopilot and budgets from the prompt.** "Full CG" or "finished scene" sets `mode: full_cg`; "match the camera" or "match the photo" sets `camera_match`; otherwise `blockout`, from `default`. "Tier S/M/L" (or "small", "medium", "large" job) sets `tier`; leave it empty for G0 if the prompt doesn't say. "Autopilot" or "don't wait for me" sets `autopilot: true`. Any cap the prompt names goes into `budgets`; never fill one in.
6. **Form or interview?**
   - Send the form link only when three or more required fields are missing, or the user prefers forms. Tell them which sections to fill, and that each section can be a prompt with images.
   - Otherwise go straight to the input review and the interview, which fills the gaps with multiple-choice questions.
7. **Project folder.** Create `projects/<slug>/` from the folder layout in `docs/pipeline/data-and-commits.md`. The slug comes from the user's project name if they gave one, otherwise from the brief title. Never ask for a project name just to make a slug.

## Output

`brief.yaml` (draft), `refs/index.yaml` (untagged), and one line in `log.md`: what came from where and what is missing.
