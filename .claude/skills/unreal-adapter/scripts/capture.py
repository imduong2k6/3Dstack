"""Capture the review camera set in Unreal (tested in UE 5.8.3 through PipelineTools.capture_set).

Over MCP: PipelineTools.capture_set(out_dir=r"<project>/reviews/P3-r1",
    labels=["CAM_A", "CAM_B", "CAM_TOP"], view_modes=["lit"]).
In the editor's Python console:
    exec(open(r"<repo>/.claude/skills/unreal-adapter/scripts/capture.py").read())
    capture_set(r"<project>/reviews/P3-r1", ["CAM_A", "CAM_B", "CAM_TOP"])

Each camera renders through a temporary SceneCapture2D into a render target that is
exported as PNG, so the files exist when the call returns and the editor can be in the
background. HighResShot wrote nothing while the editor was unfocused. The capture copies
the camera's FOV and post-process settings; lock exposure with the level's Post Process
Volume (Min EV100 = Max EV100).

Only "lit" is supported. Lighting Only is applied by the viewport client, not by scene
captures (UE 5.8 GameViewportClient sets DiffuseOverrideParameter), so a lighting_only
capture came out identical to lit. For the L1 lighting read, set MPC_LookDev.PassMode = 0
(every base colour sRGB 128) and capture "lit".
"""
import os

import unreal


def find_camera(label):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for a in actors:
        if isinstance(a, unreal.CameraActor) and a.get_actor_label() == label:
            return a
    raise LookupError(f"camera {label} not found")


def capture_set(out_dir, labels, width=1920, height=1080, view_modes=("lit",)):
    if any(m != "lit" for m in view_modes):
        raise ValueError(f"view modes {list(view_modes)}: only 'lit' is supported; for the L1 lighting "
                         "read set MPC_LookDev.PassMode = 0 (gray) and capture 'lit'")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    os.makedirs(out_dir, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(
        world, width, height, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    written = []
    for label in labels:
        cam = find_camera(label)
        view = cam.get_editor_property("camera_component")
        fov = view.get_horizontal_field_of_view() if isinstance(view, unreal.CineCameraComponent) else view.field_of_view
        cap = eas.spawn_actor_from_class(unreal.SceneCapture2D, cam.get_actor_location(), cam.get_actor_rotation())
        try:
            comp = cap.get_editor_property("capture_component2d")
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
            comp.set_editor_property("capture_every_frame", False)
            comp.set_editor_property("fov_angle", fov)
            comp.set_editor_property("post_process_settings", view.get_editor_property("post_process_settings"))
            comp.capture_scene()
            name = f"{label}_lit.png"
            unreal.RenderingLibrary.export_render_target(world, rt, out_dir, name)
            written.append(name)
        finally:
            eas.destroy_actor(cap)
    missing = [n for n in written if not os.path.isfile(os.path.join(out_dir, n))]
    if missing:
        raise RuntimeError(f"export failed for {missing}")
    msg = f"captured {len(written)} images to {out_dir}: {', '.join(written)}"
    unreal.log(msg)
    return msg
