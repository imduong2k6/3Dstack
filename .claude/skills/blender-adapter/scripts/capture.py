"""Render the review camera set without touching the user's viewport (tested headless with bpy 5.2.3 using Cycles and Workbench).

    exec(open(r"<repo>/.claude/skills/blender-adapter/scripts/capture.py").read())
    capture_set(r"<project>/reviews/P3-r1", ["CAM_A", "CAM_B", "CAM_TOP"], engine="BLENDER_WORKBENCH", project=r"<project>", repo=r"<repo>")

Headless: bash bin/blender-bg <gate copy> --python capture.py -- --out <dir> --cameras CAM_A,CAM_B --project <project> [--engine CYCLES]
          [--override-lint "reason"]. Exit 0 rendered, 2 refused by lint, 1 any other error.

Lint gate (house rule 9): before any image is written it needs a fresh lint.json for this exact scene state (in out_dir, or next to
it). A missing or stale one is produced here by running scene-lint on the open file (needs `project` and `repo`); a blocker, a crashed
check or no lint at all raises CaptureRefused and nothing is rendered. override_lint="reason" renders anyway and appends one line to
<out_dir>/lint_overrides.log (`YYYY-MM-DD HH:MM who lint override: ...`) for the worker to copy into log.md. lint=False skips the gate (single
assets, tests).

Blank-frame check: right after each PNG is written, frame_check.py (beside this file, or under `repo` when this file is exec'd) reads it. After
every camera has rendered and the settings are restored, a RuntimeError names each blank frame (flat colour, all white, all black, mostly zero
alpha); the PNGs stay on disk for a look. frame_check=False skips it. If frame_check.py cannot be found a warning is printed and the capture goes on.

Per camera it reads res_px, shift, sensor_mm and sensor_fit from light/cameras.json (project or cameras_json) and applies them for that
render only; width and height, when given, override every camera. Every render and output setting it changes is restored afterwards.
"""
import hashlib
import importlib.util
import json
import os
import sys
import time

import bpy


class CaptureRefused(Exception):
    pass


def _r(v, n=4):
    return [round(float(x), n) + 0.0 for x in v]


def _scene_state(scene):
    """Same object-name and camera/light hashes as step_log.scene_state (selftest_adapter.py checks they agree)."""
    h = lambda o: hashlib.sha1(json.dumps(o, sort_keys=True).encode()).hexdigest()[:12]
    bpy.context.view_layer.update()
    rows = {}
    for o in scene.objects:
        d = o.data
        if o.type == "CAMERA":
            rows[o.name] = [d.type, _r(o.matrix_world.translation), _r(o.matrix_world.to_euler()), round(d.lens, 4), round(d.shift_x, 4),
                            round(d.shift_y, 4), round(d.sensor_width, 3), d.sensor_fit, round(d.ortho_scale, 3)]
        elif o.type == "LIGHT":
            rows[o.name] = [d.type, round(d.energy, 4), _r(d.color), _r(o.matrix_world.translation), _r(o.matrix_world.to_euler()),
                            round(getattr(d, "size", 0.0), 4), round(getattr(d, "spot_size", 0.0), 4), round(getattr(d, "angle", 0.0), 4)]
    names = sorted(o.name for o in scene.objects)
    return {"name_hash": hashlib.sha1("\n".join(names).encode()).hexdigest()[:12], "cam_light_hash": h(rows)}


def _load_frame_check(repo):
    """frame_check.py from beside this file, else from <repo>/.claude/skills/blender-adapter/scripts (an exec'd file has no usable __file__).
    Returns the module, or None after a warning: a missing helper must not turn a capture into a confusing crash."""
    here = globals().get("__file__")
    dirs = ([os.path.dirname(os.path.abspath(here))] if here else []) + ([os.path.join(repo, ".claude", "skills", "blender-adapter", "scripts")] if repo else [])
    for d in dirs:
        path = os.path.join(d, "frame_check.py")
        if os.path.isfile(path):
            try:
                spec = importlib.util.spec_from_file_location("frame_check", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
            except Exception as e:
                print(f"capture.py: frame check skipped, {path} did not load ({type(e).__name__}: {e})")
                return None
    print(f"capture.py: frame check skipped, frame_check.py not found in {dirs or 'any known folder (pass repo=)'}")
    return None


def _blank_reason(fc, path):
    """The BlankFrame message for a blank PNG, else None. A PNG the reader cannot parse is warned about, not failed."""
    try:
        fc.assert_not_blank(path)
    except fc.BlankFrame as e:
        return str(e)
    except Exception as e:
        print(f"capture.py: frame check could not read {path} ({type(e).__name__}: {e})")
    return None


def _find_lint(out_dir):
    for d in (out_dir, os.path.dirname(os.path.abspath(out_dir))):
        p = os.path.join(d, "lint.json")
        if os.path.exists(p):
            return p
    return None


def _run_lint(out_dir, project, repo):
    script = os.path.join(repo, ".claude", "skills", "scene-lint", "scripts", "lint_blender.py") if repo else None
    if not script or not os.path.exists(script):
        raise CaptureRefused("no fresh lint.json for this scene and no repo given to run scene-lint: run lint_blender.py first")
    ns = {"__name__": "scene_lint", "__file__": script}
    exec(compile(open(script).read(), script, "exec"), ns)
    return ns["run_lint"](project=project, out_dir=out_dir)


def _lint_gate(out_dir, project, repo, override):
    scene, rep = bpy.context.scene, None
    path = _find_lint(out_dir)
    if path:
        rep = json.load(open(path))
        now = _scene_state(scene)
        if any(rep.get("scene", {}).get(k) != now[k] for k in ("name_hash", "cam_light_hash")):
            rep = None  # lint ran on a different scene state
    if rep is None:
        try:
            rep = _run_lint(out_dir, project, repo)
        except CaptureRefused as e:
            if not override:
                raise
            _log_override(out_dir, f"no lint for this scene state ({e})", override)
            return
    s = rep["summary"]
    if s["blocker"] or s["errors"]:
        what = [f"{b['check']}: {b['object']}" for b in rep.get("blockers", [])][:8]
        msg = f"lint has {s['blocker']} blocker(s) and crashed checks {s['errors']}: {what}"
        if not override:
            raise CaptureRefused(msg + " (fix them, or pass override_lint='reason' to render anyway)")
        _log_override(out_dir, msg, override)


def _log_override(out_dir, msg, reason):
    os.makedirs(out_dir, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%d %H:%M')} capture.py lint override: {msg} | reason: {reason}"
    with open(os.path.join(out_dir, "lint_overrides.log"), "a") as f:
        f.write(line + "\n")
    print(line)


def capture_set(out_dir, cameras, engine="BLENDER_WORKBENCH", width=None, height=None, samples=64, color_type="OBJECT",
                project=None, cameras_json=None, repo=None, lint=True, override_lint=None, frame_check=True):
    """width/height override every camera; else a camera's res_px from cameras.json, else the scene's own resolution, so portrait
    cameras keep their frame. color_type is the Workbench colour source: OBJECT for blockout and placement, MATERIAL for single assets."""
    scene = bpy.context.scene
    rows = {}
    cj = cameras_json or (os.path.join(project, "light", "cameras.json") if project else None)
    if cj and os.path.exists(cj):
        data = json.load(open(cj))
        rows = {r["id"]: r for r in (data.get("cameras", data) if isinstance(data, dict) else data)}
    missing = [n for n in cameras if not bpy.data.objects.get(n) or bpy.data.objects[n].type != "CAMERA"]
    if missing:
        raise RuntimeError(f"missing camera(s) {missing}: nothing rendered")
    if lint:
        _lint_gate(out_dir, project, repo, override_lint)
    fc = _load_frame_check(repo) if frame_check else None
    blanks = []
    r, im = scene.render, scene.render.image_settings
    changes = [(r, "engine", engine), (r, "resolution_percentage", 100),
               # A user's startup compositor (e.g. File Output nodes with empty paths) can blank every capture.
               (r, "use_compositing", False),
               # Multilayer EXR allows no PNG until media_type is IMAGE (Blender 5.x); an output colour-management
               # override would ignore the scene's locked exposure.
               (im, "media_type", "IMAGE"), (im, "file_format", "PNG"), (im, "color_depth", "8"),
               (im, "color_management", "FOLLOW_SCENE")]
    if engine == "CYCLES":
        changes += [(scene.cycles, "samples", samples), (scene.cycles, "use_denoising", True)]
    if engine == "BLENDER_WORKBENCH":
        # Object colours are read without the lighting exposure or white balance, which would blow out or tint them.
        vs = scene.view_settings
        changes += [(scene.display.shading, "color_type", color_type), (vs, "view_transform", "Standard"),
                    (vs, "look", "None"), (vs, "exposure", 0.0), (vs, "use_white_balance", False)]
    saved = [(o, a, getattr(o, a)) for o, a, _ in changes] + [(scene, "camera", scene.camera), (r, "filepath", r.filepath),
                                                                (r, "resolution_x", r.resolution_x), (r, "resolution_y", r.resolution_y)]
    os.makedirs(out_dir, exist_ok=True)
    base_w, base_h = r.resolution_x, r.resolution_y
    try:
        for o, a, v in changes:
            setattr(o, a, v)
        for name in cameras:
            cam, row = bpy.data.objects[name], rows.get(name, {})
            cd = cam.data
            per_cam = [(cd, "shift_x", (row.get("shift") or [cd.shift_x, cd.shift_y])[0]), (cd, "shift_y", (row.get("shift") or [cd.shift_x, cd.shift_y])[1]),
                       (cd, "sensor_width", row.get("sensor_mm") or cd.sensor_width), (cd, "sensor_fit", row.get("sensor_fit") or cd.sensor_fit)]
            w, h = (width or (row.get("res_px") or [base_w])[0]), (height or (row.get("res_px") or [0, base_h])[1])
            prev = [(o, a, getattr(o, a)) for o, a, _ in per_cam]
            try:
                for o, a, v in per_cam:
                    setattr(o, a, v)
                r.resolution_x, r.resolution_y = int(w), int(h)
                scene.camera = cam
                r.filepath = os.path.abspath(os.path.join(out_dir, f"{name}.png"))  # Blender reads a relative path from the drive root
                bpy.ops.render.render(write_still=True)
                reason = _blank_reason(fc, r.filepath) if fc else None
                if reason:
                    blanks.append(reason)
            finally:
                for o, a, v in prev:
                    setattr(o, a, v)
    finally:
        for o, a, v in saved:
            setattr(o, a, v)
    if blanks:
        raise RuntimeError(f"{len(blanks)} blank capture(s), nothing should reach a gate: " + " | ".join(blanks))


def _main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="capture.py")
    ap.error = lambda m: (_ for _ in ()).throw(RuntimeError(m))
    ap.add_argument("--out", required=True)
    ap.add_argument("--cameras", required=True, help="comma-separated camera object names")
    ap.add_argument("--project")
    ap.add_argument("--cameras-json")
    ap.add_argument("--repo")
    ap.add_argument("--engine", default="BLENDER_WORKBENCH")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--color-type", default="OBJECT")
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--override-lint")
    ap.add_argument("--no-lint", action="store_true")
    ap.add_argument("--no-frame-check", action="store_true")
    a = ap.parse_args(argv)
    repo = a.repo or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
    capture_set(a.out, a.cameras.split(","), a.engine, a.width, a.height, a.samples, a.color_type, a.project, a.cameras_json, repo,
                lint=not a.no_lint, override_lint=a.override_lint,
                frame_check=not a.no_frame_check)


if any(os.path.basename(x) == "capture.py" for x in sys.argv) and "--" in sys.argv:
    try:
        _main(sys.argv[sys.argv.index("--") + 1:])
        _code = 0
    except CaptureRefused as e:
        print("CAPTURE REFUSED:", e)
        _code = 2
    except Exception:
        import traceback
        traceback.print_exc()
        _code = 1
    sys.exit(_code)
