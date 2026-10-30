"""Headless self-test for the 30 Oct 2026 pipeline patch to validate.py and export_delivery.py (pipeline addition,
not upstream): UCX_ colliders are recognised, and a run that validated or exported nothing exits 1.

    bash bin/blender-bg --python-exit-code 1 --python .claude/skills/blender-image-to-3d/scripts/selftest_pipeline_patch.py -- <out_dir>
"""
import json
import os
import subprocess
import sys

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else os.path.join(HERE, "_selftest_out")
os.makedirs(OUT, exist_ok=True)


def build(path, open_collider=False, text=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    low, col = bpy.data.collections.new("LOW"), bpy.data.collections.new("COLLISION")
    for c in (low, col):
        bpy.context.scene.collection.children.link(c)
    bpy.ops.mesh.primitive_cube_add(size=1)  # a cube carries UVs
    ob = bpy.context.object
    ob.name = "SM_Test"
    ob.data.materials.append(bpy.data.materials.new("M_test"))
    bpy.context.scene.collection.objects.unlink(ob)
    low.objects.link(ob)
    me = bpy.data.meshes.new("UCX_SM_Test_01")  # no UVs, no material, like a real collider
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    if open_collider:
        bmesh.ops.delete(bm, geom=[next(iter(bm.faces))], context="FACES_ONLY")
    bm.to_mesh(me)
    bm.free()
    col.objects.link(bpy.data.objects.new("UCX_SM_Test_01", me))
    if text:  # a live text object with a material and a custom property
        cu = bpy.data.curves.new("TXT_Label", "FONT")
        cu.body = "OPEN"
        cu.materials.append(bpy.data.materials.new("M_label"))
        lab = bpy.data.objects.new("SM_Label", cu)
        lab.location = (2.0, 0.0, 1.0)
        lab["label_id"] = "T01"
        low.objects.link(lab)
    bpy.ops.wm.save_as_mainfile(filepath=path)


def run(script, *args):
    r = subprocess.run([bpy.app.binary_path, "--background", "--factory-startup", "--python", os.path.join(HERE, script), "--", *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


good, bad = os.path.join(OUT, "good.blend"), os.path.join(OUT, "open_collider.blend")
build(good)
build(bad, open_collider=True)
fails = []


def expect(cond, msg):
    if not cond:
        fails.append(msg)


# UCX_ collider, --require-uv: passes, and its triangles stay out of the LOD0 count (a cube is 12 tris)
rc, log = run("validate.py", "--blend", good, "--collections", "LOW,COLLISION", "--require-uv", "--out", os.path.join(OUT, "v_good.json"))
rep = json.load(open(os.path.join(OUT, "v_good.json")))
expect(rc == 0, f"validate good: exit {rc}\n{log[-600:]}")
expect(rep["summary"]["tris_by_lod"] == {"0": 12} or rep["summary"]["tris_by_lod"] == {0: 12}, f"LOD0 tris {rep['summary']['tris_by_lod']}")
expect({o["name"] for o in rep["objects"]} == {"SM_Test", "UCX_SM_Test_01"}, "validate good: UCX_ object not in the report")

# an open UCX_ proxy fails like an open COL_ proxy
rc, log = run("validate.py", "--blend", bad, "--collections", "LOW,COLLISION", "--out", os.path.join(OUT, "v_bad.json"))
rep = json.load(open(os.path.join(OUT, "v_bad.json")))
expect(rc == 1 and any("UCX_SM_Test_01: collision proxy is not closed" in f for f in rep["summary"]["fail"]), f"validate open UCX: exit {rc}")

# a missing collection: nothing validated, exit 1 (it used to be skipped and exit 0)
rc, log = run("validate.py", "--blend", good, "--collections", "NOPE", "--out", os.path.join(OUT, "v_none.json"))
rep = json.load(open(os.path.join(OUT, "v_none.json")))
expect(rc == 1 and any("nothing validated" in f for f in rep["summary"]["fail"]), f"validate missing collection: exit {rc}")
expect(any("collection not found: NOPE" in w for w in rep["summary"]["warn"]), "validate: missing collection not reported")

# an exception (no such file) exits 1, not 0
rc, log = run("validate.py", "--blend", os.path.join(OUT, "no_such.blend"))
expect(rc == 1, f"validate missing file: exit {rc}")

# export: UCX_ goes to the manifest's colliders and stays out of the LOD list
exp = os.path.join(OUT, "export")
rc, log = run("export_delivery.py", "--blend", good, "--out", exp, "--name", "SM_Test", "--collections", "LOW,COLLISION", "--no-animation")
expect(rc == 0, f"export good: exit {rc}\n{log[-800:]}")
if rc == 0:
    man = json.load(open(os.path.join(exp, "asset-manifest.json")))
    expect([c["name"] for c in man["colliders"]] == ["UCX_SM_Test_01"], f"manifest colliders {man['colliders']}")
    expect(man["lods"] == [{"level": 0, "objects": ["SM_Test"], "tris": 12}], f"manifest lods {man['lods']}")

rc, log = run("export_delivery.py", "--blend", good, "--out", os.path.join(OUT, "export_none"), "--name", "SM_Test", "--collections", "NOPE")
expect(rc == 1 and "collection not found: NOPE" in log, f"export missing collection: exit {rc}")

# a text object is converted to a mesh on the export copy (name, transform, material, custom property), and the source keeps live text
txt = os.path.join(OUT, "text.blend")
build(txt, text=True)
for fmt, ext in (("GLB", ".glb"), ("FBX", ".fbx")):
    out = os.path.join(OUT, "export_text_" + fmt)
    rc, log = run("export_delivery.py", "--blend", txt, "--out", out, "--name", "SM_Label", "--format", fmt, "--collections", "LOW,COLLISION", "--no-animation")
    expect(rc == 0, f"export text {fmt}: exit {rc}\n{log[-800:]}")
    if rc != 0:
        continue
    man = json.load(open(os.path.join(out, "asset-manifest.json")))
    expect(man["lods"] and sorted(man["lods"][0]["objects"]) == ["SM_Label", "SM_Test"] and man["lods"][0]["tris"] > 12, f"export text {fmt}: manifest lods {man['lods']}")
    expect(man["materials"] == ["M_label", "M_test"], f"export text {fmt}: materials {man['materials']}")
    blob = open(os.path.join(out, "SM_Label" + ext), "rb").read()
    expect(b"SM_Label" in blob and b"label_id" in blob and b"T01" in blob, f"export text {fmt}: name or custom property missing from the file")
    if fmt == "GLB":
        js = json.loads(blob[20:20 + int.from_bytes(blob[12:16], "little")])
        node = next((n for n in js["nodes"] if n["name"] == "SM_Label"), None)
        expect(node is not None and "mesh" in node, f"export text GLB: node {node}")
bpy.ops.wm.open_mainfile(filepath=txt)
expect(bpy.data.objects["SM_Label"].type == "FONT" and bpy.data.objects["SM_Label"].get("label_id") == "T01", "the source file keeps live text")

print("FAIL:\n" + "\n".join(fails) if fails else "selftest_pipeline_patch: all checks passed")
if fails:
    sys.exit(1)
