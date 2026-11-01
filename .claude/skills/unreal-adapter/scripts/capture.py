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

After the export each PNG goes through blender-adapter/scripts/frame_check.py (stdlib only): an all white, all black or flat frame
raises RuntimeError, like a missing file does, with the PNGs left on disk. Alpha is ignored here. The file is found in the sibling skill
(<skills>/blender-adapter/scripts) or under repo=; if it is not there a warning is logged and the capture goes on unchecked.
check_blank=False skips the check. Not yet run in the editor (UE 5.8 was not up when it was added); frame_check itself is tested by
blender-adapter/scripts/selftest_frame_check.py.
"""
import importlib.util
import os

import unreal


def _load_frame_check(repo):
    """frame_check.py from ../../blender-adapter/scripts, else <repo>/.claude/skills/blender-adapter/scripts. None (after a warning) when it
    is missing or will not load, so the capture itself never fails for that reason."""
    here = globals().get("__file__")  # an exec'd copy may have none
    dirs = []
    if here:
        dirs.append(os.path.join(os.path.dirname(os.path.abspath(here)), "..", "..", "blender-adapter", "scripts"))
    if repo:
        dirs.append(os.path.join(repo, ".claude", "skills", "blender-adapter", "scripts"))
    for d in dirs:
        path = os.path.normpath(os.path.join(d, "frame_check.py"))
        if os.path.isfile(path):
            try:
                spec = importlib.util.spec_from_file_location("frame_check", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
            except Exception as e:
                unreal.log_warning(f"capture.py: blank-frame check skipped, {path} did not load ({type(e).__name__}: {e})")
                return None
    unreal.log_warning("capture.py: blank-frame check skipped, frame_check.py not found (looked in "
                       f"{[os.path.normpath(d) for d in dirs] or 'no known folder; pass repo='})")
    return None


def find_camera(label):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for a in actors:
        if isinstance(a, unreal.CameraActor) and a.get_actor_label() == label:
            return a
    raise LookupError(f"camera {label} not found")


def capture_set(out_dir, labels, width=1920, height=1080, view_modes=("lit",), repo=None, check_blank=True):
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
    fc = _load_frame_check(repo) if check_blank else None
    blanks = []
    for n in written if fc else []:
        try:
            # a SceneCapture2D's exported alpha holds no coverage, so only colour can show a blank frame
            fc.assert_not_blank(os.path.join(out_dir, n), {"alpha_zero_fraction": 1.1})
        except fc.BlankFrame as e:
            blanks.append(str(e))
        except Exception as e:  # a PNG the reader cannot parse is not a reason to fail the capture
            unreal.log_warning(f"capture.py: blank-frame check could not read {n} ({type(e).__name__}: {e})")
    if blanks:
        raise RuntimeError(f"{len(blanks)} blank capture(s), nothing should reach a gate: " + " | ".join(blanks))
    msg = f"captured {len(written)} images to {out_dir}: {', '.join(written)}"
    unreal.log(msg)
    return msg
