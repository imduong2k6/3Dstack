"""Step ledger (house rule 4): one entry per step in plan/steps.json, and a diff at session start.

Library, in the live Blender (the worker's one writer session):

    exec(open(r"<repo>/.claude/skills/blender-adapter/scripts/step_log.py").read())
    path = backup_path(r"<phase folder>", "scene", "P3", "cables")     # .../backups/<file>_P3_<nn>_cables.blend
    log_step(r"<project>/plan/steps.json", who="blender-worker", what="cable runs placed", backup=path, phase="P3", step="cables")
    print(diff_state(r"<project>/plan/steps.json"))                            # at session start

Headless, on a saved file (exit 0 ok, 1 on an error or a missing backup):

    bash bin/blender-bg <file.blend> --python step_log.py -- log --steps plan/steps.json --who NAME --what TEXT --backup PATH [--phase P3] [--step cables]
    bash bin/blender-bg <file.blend> --python step_log.py -- diff --steps plan/steps.json [--out diff.json]

`log` saves the backup copy itself when the path does not exist yet (save_as_mainfile(copy=True)), then checks it is on disk and
not empty, so a step cannot be logged without its backup. `diff` compares the open scene with the last entry and checks that every
backup in the ledger is still on disk. A difference with no step behind it is the user's change or a lost step: report it, never undo it.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime

import bpy


class StepLogError(Exception):
    pass


def _h(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]


def _r(v, n=4):
    return [round(float(x), n) + 0.0 for x in v]


def _cam_light_rows(scene):
    rows = {}
    for o in scene.objects:
        d = o.data
        if o.type == "CAMERA":
            rows[o.name] = [d.type, _r(o.matrix_world.translation), _r(o.matrix_world.to_euler()), round(d.lens, 4), round(d.shift_x, 4),
                            round(d.shift_y, 4), round(d.sensor_width, 3), d.sensor_fit, round(d.ortho_scale, 3)]
        elif o.type == "LIGHT":
            rows[o.name] = [d.type, round(d.energy, 4), _r(d.color), _r(o.matrix_world.translation), _r(o.matrix_world.to_euler()),
                            round(getattr(d, "size", 0.0), 4), round(getattr(d, "spot_size", 0.0), 4), round(getattr(d, "angle", 0.0), 4)]
    return rows


def scene_state(scene=None):
    """Object count, a hash of the object names, and a hash of the cameras and lights (capture.py and lint use the same hashes)."""
    sc = scene or bpy.context.scene
    bpy.context.view_layer.update()  # matrix_world is stale after a script moved something
    names = sorted(o.name for o in sc.objects)
    rows = _cam_light_rows(sc)
    return {"objects": len(names), "name_hash": hashlib.sha1("\n".join(names).encode()).hexdigest()[:12], "cam_light_hash": _h(rows),
            "cameras": sum(1 for o in sc.objects if o.type == "CAMERA"), "lights": sum(1 for o in sc.objects if o.type == "LIGHT"),
            "cam_light": {k: _h(v) for k, v in rows.items()}}


def _read(path):
    if not os.path.exists(path):
        return {"version": 1, "steps": []}
    try:
        data = json.load(open(path))
        assert isinstance(data.get("steps"), list)
        return data
    except (ValueError, AssertionError, AttributeError) as e:
        raise StepLogError(f"{path} is not a step ledger: {e}")


def _write(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def backup_path(phase_dir, base, phase, step):
    """<phase_dir>/backups/<base>_<phase>_<nn>_<step>.blend with the next free nn."""
    folder = os.path.join(phase_dir, "backups")
    n = 1 + sum(1 for f in (os.listdir(folder) if os.path.isdir(folder) else []) if f.startswith(f"{base}_{phase}_") and f.endswith(".blend"))
    return os.path.join(folder, f"{base}_{phase}_{n:02d}_{step}.blend")


def log_step(steps_path, who, what, backup, phase=None, step=None, scene=None):
    """Save the backup copy if it is not on disk yet, then add the ledger entry. Returns the entry."""
    if not (who and what and backup):
        raise StepLogError("who, what and backup are required")
    if not os.path.exists(backup):
        os.makedirs(os.path.dirname(os.path.abspath(backup)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=backup, copy=True)
    size = os.path.getsize(backup) if os.path.exists(backup) else 0
    if size == 0:
        raise StepLogError(f"backup missing or empty: {backup}")
    data = _read(steps_path)
    entry = {"n": len(data["steps"]) + 1, "time": datetime.now().isoformat(timespec="seconds"), "who": who, "what": what,
             "phase": phase, "step": step, "file": bpy.data.filepath, "backup": os.path.abspath(backup), "backup_bytes": size,
             **scene_state(scene)}
    data["steps"].append(entry)
    _write(steps_path, data)
    return entry


def _backup_object_names(path):
    with bpy.data.libraries.load(path) as (src, _):
        return set(src.objects)


def diff_state(steps_path, scene=None):
    """Compare the open scene with the last entry and check every backup in the ledger. `ok` is False when a backup is missing."""
    steps = _read(steps_path)["steps"]
    rep = {"steps": len(steps), "file": bpy.data.filepath, "missing_backups": [], "drift": {}, "ok": True}
    for s in steps:
        b = s.get("backup")
        if not b or not os.path.exists(b) or os.path.getsize(b) == 0:
            rep["missing_backups"].append({"n": s["n"], "what": s.get("what"), "backup": b})
    rep["ok"] = not rep["missing_backups"]
    if not steps:
        rep["note"] = "empty ledger: no step has been logged yet"
        return rep
    last, cur = steps[-1], scene_state(scene)
    rep["last_step"] = {k: last.get(k) for k in ("n", "time", "who", "what", "backup")}
    rep["file_is_last_entry_file"] = os.path.normcase(os.path.abspath(bpy.data.filepath or "")) == os.path.normcase(os.path.abspath(last.get("file") or ""))
    if cur["name_hash"] != last["name_hash"]:
        d = {"logged": last["objects"], "now": cur["objects"]}
        if not any(m["n"] == last["n"] for m in rep["missing_backups"]):
            try:
                then, now = _backup_object_names(last["backup"]), {o.name for o in bpy.data.objects if o.users}
                d.update(added=sorted(now - then), removed=sorted(then - now), method="object names in the last backup against the open file")
            except OSError:
                rep["missing_backups"].append({"n": last["n"], "what": last.get("what"), "backup": last["backup"], "problem": "cannot be opened"})
                rep["ok"] = False
        rep["drift"]["objects"] = d
    if cur["cam_light_hash"] != last["cam_light_hash"]:
        a, b = last.get("cam_light", {}), cur["cam_light"]
        rep["drift"]["cameras_lights"] = {"changed": sorted(k for k in a.keys() & b.keys() if a[k] != b[k]),
                                          "added": sorted(b.keys() - a.keys()), "removed": sorted(a.keys() - b.keys())}
    rep["drifted"] = bool(rep["drift"])
    return rep


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise StepLogError(message)


def main(argv):
    ap = _Parser(prog="step_log.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("log")
    a.add_argument("--steps", required=True)
    a.add_argument("--who", required=True)
    a.add_argument("--what", required=True)
    a.add_argument("--backup", required=True)
    a.add_argument("--phase")
    a.add_argument("--step")
    d = sub.add_parser("diff")
    d.add_argument("--steps", required=True)
    d.add_argument("--out")
    args = ap.parse_args(argv)
    if args.cmd == "log":
        rep = log_step(args.steps, args.who, args.what, args.backup, args.phase, args.step)
        print("STEP", json.dumps({k: rep[k] for k in ("n", "time", "backup", "objects", "name_hash", "cam_light_hash")}))
        return 0
    rep = diff_state(args.steps)
    if args.out:
        json.dump(rep, open(args.out, "w"), indent=1)
    print("DIFF", json.dumps(rep))
    return 0 if rep["ok"] else 1


if any(os.path.basename(a) == "step_log.py" for a in sys.argv) and "--" in sys.argv:
    try:
        code = main(sys.argv[sys.argv.index("--") + 1:])
    except (StepLogError, OSError, RuntimeError) as e:
        print("STEP_LOG ERROR:", e)
        code = 1
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    sys.exit(code)
