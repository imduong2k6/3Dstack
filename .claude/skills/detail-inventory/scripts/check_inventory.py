"""Check plan/inventory.yaml and plan/services.yaml, and count a Blender file's tagged objects against the inventory.

    python check_inventory.py plan/inventory.yaml [--services plan/services.yaml] [--metrics plan/metrics.yaml]
        [--refs refs/index.yaml] [--work-dir <work_dir>] [--layout-out plan/services_layout.json] [--out report.json]
        [--blend scene.blend | open | --tags tags.json] [--upto P3] [--fail-on blocker|major]
    bash bin/blender-bg <scene.blend> --python check_inventory.py -- plan/inventory.yaml --blend open    # count the open file

Schema errors and a broken services network are blockers. A row that is due (its phase is at or before --upto) and has
fewer or more tagged objects than its count is a major; a tag with no row is a minor. Objects carry the row ID in the custom
property `inv_id`. Exit 1 on a blocker (or a major with --fail-on major). YAML: PyYAML when installed, else a built-in reader
for the subset the templates use (block maps and lists, flow lists and maps, quoted strings, no anchors or block scalars).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

try:
    import bpy
except ImportError:
    bpy = None

PHASES = ["G2"] + [f"P{i}" for i in range(10)]
MOUNTS = {"wall", "ceiling", "floor", "free", "inset", "hung", "surface", "pole"}
CLASSES = {"fixture", "surface", "dressing"}
CONF = {"seen", "inferred", "assumed"}
KINDS = {"electric", "cable", "water", "drain", "gas", "ac", "data", "other"}
NODES = {"supply", "service_head", "meter", "board", "riser", "junction", "fixture", "tray", "bracket", "other"}
BY = {"conduit", "tray", "cable", "pipe", "duct"}


# ---------- YAML subset ----------

def _strip(line):
    q, out = None, []
    for i, ch in enumerate(line):
        if q:
            q = None if ch == q else q
        elif ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _split_kv(s):
    q, depth = None, 0
    for i, ch in enumerate(s):
        if q:
            q = None if ch == q else q
        elif ch in "\"'":
            q = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == ":" and depth == 0 and (i + 1 == len(s) or s[i + 1] == " "):
            return s[:i].strip().strip("\"'"), s[i + 1:].strip()
    return None


def _scalar(s):
    s = s.strip()
    if s in ("", "~", "null"):
        return None
    if s[0] in "\"'" and len(s) > 1 and s[-1] == s[0]:
        return s[1:-1]
    if s[0] in "[{":
        return _flow(s)
    if s in ("true", "false"):
        return s == "true"
    for t in (int, float):
        try:
            return t(s)
        except ValueError:
            pass
    return s


def _flow(s):
    pos = 0

    def ws():
        nonlocal pos
        while pos < len(s) and s[pos] in " \t":
            pos += 1

    def token(stops):
        nonlocal pos
        start, q = pos, None
        while pos < len(s):
            ch = s[pos]
            if q:
                q = None if ch == q else q
            elif ch in "\"'":
                q = ch
            elif ch in stops:
                break
            pos += 1
        return s[start:pos].strip()

    def value():
        nonlocal pos
        ws()
        if s[pos] == "[":
            pos += 1
            out = []
            while True:
                ws()
                if s[pos] == "]":
                    pos += 1
                    return out
                out.append(value())
                ws()
                pos += s[pos] == ","
        if s[pos] == "{":
            pos += 1
            out = {}
            while True:
                ws()
                if s[pos] == "}":
                    pos += 1
                    return out
                key = token(":").strip("\"'")
                pos += 1
                out[key] = value()
                ws()
                pos += s[pos] == ","
        return _scalar(token(",]}"))
    return value()


def mini_yaml(text):
    # shortcut: the subset the templates use (no anchors, block scalars, multi-line flow); use PyYAML for anything wider, it is preferred when installed
    lines = []
    for raw in text.splitlines():
        t = _strip(raw)
        if t.strip() and t.strip() != "---":
            if t.strip()[-1] in "|>" and _split_kv(t.strip()) and _split_kv(t.strip())[1] in ("|", ">"):
                raise ValueError("block scalars are not supported; use a quoted string")
            lines.append((len(t) - len(t.lstrip(" ")), t.strip()))
    pos = 0

    def is_item(l):
        return l == "-" or l.startswith("- ")

    def block(indent):
        return seq(indent) if is_item(lines[pos][1]) else mapping(indent)

    def seq(indent):
        nonlocal pos
        out = []
        while pos < len(lines) and lines[pos][0] == indent and is_item(lines[pos][1]):
            l = lines[pos][1]
            rest = l[1:].strip()
            if not rest:
                pos += 1
                out.append(block(lines[pos][0]))
            elif rest[0] not in "[{\"'" and _split_kv(rest):
                lines[pos] = (indent + l.index(rest), rest)  # `- key: v` opens a map at the key's column
                out.append(mapping(indent + l.index(rest)))
            else:
                pos += 1
                out.append(_scalar(rest))
        return out

    def mapping(indent):
        nonlocal pos
        out = {}
        while pos < len(lines) and lines[pos][0] == indent and not is_item(lines[pos][1]):
            kv = _split_kv(lines[pos][1])
            if kv is None:
                raise ValueError("cannot read line: " + lines[pos][1])
            pos += 1
            key, val = kv
            if val == "":
                nxt = lines[pos] if pos < len(lines) else (-1, "")
                out[key] = block(nxt[0]) if nxt[0] > indent or (nxt[0] == indent and is_item(nxt[1])) else None
            else:
                out[key] = _scalar(val)
        return out
    return block(lines[0][0]) if lines else None


def load(path):
    text = open(path, encoding="utf-8").read()
    if path.lower().endswith(".json"):
        return json.loads(text)
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        return mini_yaml(text)


# ---------- checks ----------

class Report:
    def __init__(self):
        self.blockers, self.majors, self.minors = [], [], []

    def __call__(self, level, msg):
        getattr(self, level + "s").append(msg)


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def xyz(x, n=3):
    return isinstance(x, list) and len(x) == n and all(num(v) for v in x)


def ref_ids(idx):
    ids = set(idx) if isinstance(idx, dict) else set()
    for r in idx.values() if isinstance(idx, dict) else idx or []:
        for k in ("id", "name", "file"):
            if isinstance(r, dict) and r.get(k):
                v = os.path.basename(str(r[k]))
                ids |= {str(r[k]), v, os.path.splitext(v)[0]}
    return ids


def check_inventory(inv, rep, refs=None, work_dir=None):
    rows, zones = {}, {}
    if not isinstance(inv, dict) or not isinstance(inv.get("zones"), list) or not inv["zones"]:
        rep("blocker", "inventory: needs a `zones` list")
        return rows, zones
    zids = set()
    for z in inv["zones"]:
        zid = z.get("id") if isinstance(z, dict) else None
        if not zid or zid in zids:
            rep("blocker", f"zone id missing or duplicated: {zid}")
            continue
        zids.add(zid)
        zones[zid] = {"area_m2": z.get("area_m2"), "fixture": 0, "dressing": 0, "surface": 0}
        if not z.get("name"):
            rep("minor", f"{zid}: no name")
        items = list(z.get("items") or [])
        for w in z.get("walls") or []:
            if not isinstance(w, dict) or not w.get("id"):
                rep("blocker", f"{zid}: a wall needs an id")
                continue
            items += w.get("items") or []
        for it in items:
            iid = it.get("id") if isinstance(it, dict) else None
            where = f"{zid}/{iid}"
            if not iid or iid in rows:
                rep("blocker", f"{zid}: item id missing or duplicated: {iid}")
                continue
            if not iid.startswith(zid + "."):
                rep("blocker", f"{where}: id must start with the zone id and a dot")
            rows[iid] = it
            if not it.get("feature"):
                rep("blocker", f"{where}: no feature")
            c = it.get("count")
            if not ((isinstance(c, int) and not isinstance(c, bool) and c >= 0) or (isinstance(c, list) and len(c) == 2 and all(isinstance(v, int) for v in c) and 0 <= c[0] <= c[1])):
                rep("blocker", f"{where}: count must be a whole number or [min, max]")
            sz = it.get("size_m")
            if not ((isinstance(sz, list) and 1 <= len(sz) <= 3 and all(num(v) and v > 0 for v in sz)) or (num(it.get("dia_m")) and it["dia_m"] > 0)):
                rep("blocker", f"{where}: needs size_m [W, D, H] in metres (or dia_m)")
            if it.get("mount") not in MOUNTS:
                rep("blocker", f"{where}: mount must be one of {sorted(MOUNTS)}")
            h = it.get("height_m")
            if h is not None and not (num(h) or (isinstance(h, list) and len(h) == 2 and all(num(v) for v in h))):
                rep("blocker", f"{where}: height_m must be a number or [low, high]")
            r = it.get("ref")
            if not isinstance(r, dict) or not (r.get("image") or r.get("crop")):
                rep("blocker", f"{where}: ref needs an image (and a crop)")
            else:
                if not r.get("crop"):
                    rep("minor", f"{where}: no reference crop saved")
                elif work_dir and not os.path.exists(os.path.join(work_dir, r["crop"])):
                    rep("minor", f"{where}: crop not found in the work folder: {r['crop']}")
                if refs is not None and r.get("image") and str(r["image"]) not in refs:
                    rep("minor", f"{where}: image {r['image']} is not in refs/index.yaml")
            if not it.get("source"):
                rep("blocker", f"{where}: source is empty (a reference ID, a metrics key or a link)")
            if it.get("confidence") not in (None,) + tuple(CONF):
                rep("blocker", f"{where}: confidence must be one of {sorted(CONF)}")
            if it.get("confidence") == "assumed" and not it.get("note"):
                rep("blocker", f"{where}: an assumed row needs a note")
            if it.get("class", "fixture") not in CLASSES:
                rep("blocker", f"{where}: class must be one of {sorted(CLASSES)}")
            if it.get("phase") is not None and it["phase"] not in PHASES:
                rep("blocker", f"{where}: phase must be one of {PHASES}")
            hi = c if isinstance(c, int) else c[1] if isinstance(c, list) and len(c) == 2 and isinstance(c[1], int) else 0
            if it.get("class", "fixture") in CLASSES:
                zones[zid][it.get("class", "fixture")] += hi
    for z in zones.values():
        z["dressing_per_m2"] = round(z["dressing"] / z["area_m2"], 3) if num(z["area_m2"]) and z["area_m2"] > 0 else None
    return rows, zones


def check_services(svc, rep, rows=None, metrics=None):
    summary = {}
    if not isinstance(svc, dict) or not isinstance(svc.get("networks"), list) or not svc["networks"]:
        rep("blocker", "services: needs a `networks` list")
        return summary, [], []
    seen, shapes, runs_out = set(), [], []
    for net in svc["networks"]:
        nid = net.get("id", "?")
        if net.get("kind") not in KINDS:
            rep("blocker", f"{nid}: kind must be one of {sorted(KINDS)}")
        nodes = {}
        for n in net.get("nodes") or []:
            i = n.get("id")
            if not i or i in seen:
                rep("blocker", f"{nid}: node id missing or used twice: {i}")
                continue
            seen.add(i)
            nodes[i] = n
            if n.get("type") not in NODES:
                rep("blocker", f"{nid}/{i}: type must be one of {sorted(NODES)}")
            if not xyz(n.get("at_m")):
                rep("blocker", f"{nid}/{i}: at_m needs [x, y, z] with the height")
            else:
                shapes.append({"id": i, "legend": "purple", "point_m": n["at_m"][:2], "z_m": n["at_m"][2], "note": n.get("type")})
            if n.get("inv") and rows is not None and n["inv"] not in rows:
                rep("blocker", f"{nid}/{i}: inv {n['inv']} is not a row in inventory.yaml")
        if net.get("supply") not in nodes:
            rep("blocker", f"{nid}: supply must name a node")
        adj = {i: set() for i in nodes}
        fit = {}
        for r in net.get("runs") or []:
            i = r.get("id")
            if not i or i in seen:
                rep("blocker", f"{nid}: run id missing or used twice: {i}")
                continue
            seen.add(i)
            a, b = r.get("from"), r.get("to")
            if a not in nodes or b not in nodes:
                rep("blocker", f"{nid}/{i}: from/to must be nodes of this network (no run without two real ends): {a} -> {b}")
                continue
            adj[a].add(b)
            adj[b].add(a)
            if r.get("by") not in BY:
                rep("blocker", f"{nid}/{i}: by must be one of {sorted(BY)}")
            if r.get("metric"):
                if metrics is not None and r["metric"] not in metrics:
                    rep("blocker", f"{nid}/{i}: metric {r['metric']} has no row in metrics.yaml")
            elif not (num(r.get("dia_mm")) and r.get("source")):
                rep("blocker", f"{nid}/{i}: size needs `metric: <key>` or `dia_mm` with a `source` (a kit size is never read off an AI image)")
            p = r.get("path_m")
            if p is not None:
                if not (isinstance(p, list) and len(p) >= 2 and all(xyz(q) for q in p)):
                    rep("blocker", f"{nid}/{i}: path_m must be a list of [x, y, z] anchors, at least two")
                elif xyz(nodes[a].get("at_m")) and xyz(nodes[b].get("at_m")):
                    for q, n in ((p[0], nodes[a]), (p[-1], nodes[b])):
                        if sum((u - v) ** 2 for u, v in zip(q, n["at_m"])) ** 0.5 > 0.15:
                            rep("blocker", f"{nid}/{i}: path does not start and end on its nodes' anchors")
                            break
            runs_out.append({"id": i, "from": a, "to": b, "count": r.get("count", 1)})
            for f in r.get("fittings") or []:
                fi = f.get("id")
                if not fi or fi in seen or not f.get("type") or not xyz(f.get("at_m")):
                    rep("blocker", f"{nid}/{i}: fitting needs a unique id, a type and at_m [x, y, z]: {fi}")
                    continue
                seen.add(fi)
                fit[f["type"]] = fit.get(f["type"], 0) + 1
                shapes.append({"id": fi, "legend": "purple", "point_m": f["at_m"][:2], "z_m": f["at_m"][2], "note": f["type"]})
        reached, todo = set(), [net.get("supply")] if net.get("supply") in nodes else []
        while todo:
            n = todo.pop()
            if n not in reached:
                reached.add(n)
                todo += adj[n]
        lost = sorted(set(nodes) - reached)
        if lost:
            rep("blocker", f"{nid}: not connected to the supply: {lost}")
        summary[nid] = {"nodes": len(nodes), "runs": len(net.get("runs") or []), "fittings": fit, "unreached": lost}
    return summary, shapes, runs_out


def count_tags():
    """Tagged objects that render, by inv_id. Needs Blender."""
    off = set()

    def walk(c, hidden):
        hidden = hidden or c.hide_render
        if hidden:
            off.add(c.name)
        for ch in c.children:
            walk(ch, hidden)
    walk(bpy.context.scene.collection, False)
    out = {}
    for o in bpy.data.objects:
        t = o.get("inv_id")
        if t and not o.hide_render and not all(c.name in off for c in o.users_collection) and o.users_collection:
            out[str(t)] = out.get(str(t), 0) + 1
    return out


def compare(rows, tags, upto, rep):
    out, limit = {}, PHASES.index(upto) if upto else len(PHASES)
    for i, it in rows.items():
        c = it.get("count")
        lo, hi = (c, c) if isinstance(c, int) else (c[0], c[1]) if isinstance(c, list) and len(c) == 2 else (0, 0)
        due = it.get("phase") is None or it["phase"] not in PHASES or PHASES.index(it["phase"]) <= limit
        n = tags.get(i, 0)
        st = "not_due" if not due else "short" if n < lo else "over" if n > hi else "ok"
        out[i] = {"expected": c, "found": n, "status": st, "phase": it.get("phase")}
        if st in ("short", "over"):
            rep("major", f"{i}: {n} tagged, expected {c} ({st})")
    for t in sorted(set(tags) - set(rows)):
        rep("minor", f"tag {t} ({tags[t]} objects) has no row in inventory.yaml")
        out[t] = {"expected": None, "found": tags[t], "status": "no_row"}
    return out


def find_blender():
    for v in ("BLENDER_BIN", "BLENDER_PATH"):
        if os.environ.get(v):
            return os.environ[v]
    return shutil.which("blender") or r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("inventory", nargs="?")
    ap.add_argument("--services")
    ap.add_argument("--metrics", help="plan/metrics.yaml: a run's `metric` key must exist there")
    ap.add_argument("--refs", help="refs/index.yaml")
    ap.add_argument("--work-dir", help="folder the crop paths are relative to")
    ap.add_argument("--layout-out", help="write the services as layout.json shapes and runs (purple), to merge into layout.json")
    ap.add_argument("--blend", help="a .blend to count tagged objects in, or `open` for the file open in Blender")
    ap.add_argument("--tags", help="JSON {inv_id: count} instead of a .blend")
    ap.add_argument("--dump-tags", help=argparse.SUPPRESS)
    ap.add_argument("--upto", choices=PHASES, help="only rows due at this phase or earlier are compared")
    ap.add_argument("--fail-on", choices=["blocker", "major"], default="blocker")
    ap.add_argument("--out", help="JSON report")
    a = ap.parse_args(argv)
    if a.dump_tags:
        json.dump(count_tags(), open(a.dump_tags, "w"))
        return
    assert a.inventory, "give plan/inventory.yaml"
    rep = Report()
    refs = ref_ids(load(a.refs)) if a.refs else None
    rows, zones = check_inventory(load(a.inventory), rep, refs, a.work_dir)
    result = {"zones": zones, "rows": len(rows)}
    if a.services:
        metrics = load(a.metrics) if a.metrics else None
        result["services"], shapes, runs = check_services(load(a.services), rep, rows, metrics)
        if a.layout_out:
            json.dump({"shapes": shapes, "runs": runs}, open(a.layout_out, "w"), indent=1)
    tags = None
    if a.tags:
        tags = json.load(open(a.tags))
    elif a.blend == "open":
        tags = count_tags()
    elif a.blend:
        tmp = os.path.join(tempfile.mkdtemp(), "tags.json")
        r = subprocess.run([find_blender(), "--background", "--factory-startup", a.blend, "--python", os.path.abspath(__file__), "--", "--dump-tags", tmp],
                           capture_output=True, text=True)
        if r.returncode or not os.path.exists(tmp):
            rep("blocker", "could not count tags in " + a.blend + ": " + r.stderr[-300:])
        else:
            tags = json.load(open(tmp))
    if tags is not None and not rep.blockers:
        result["counts"] = compare(rows, tags, a.upto, rep)
    result.update(blockers=rep.blockers, majors=rep.majors, minors=rep.minors)
    if a.out:
        json.dump(result, open(a.out, "w"), indent=1)
    for lvl, msgs in (("BLOCKER", rep.blockers), ("MAJOR", rep.majors), ("MINOR", rep.minors)):
        for m in msgs:
            print(lvl, m)
    print(f"inventory: {len(rows)} rows, {len(zones)} zones; {len(rep.blockers)} blockers, {len(rep.majors)} majors, {len(rep.minors)} minors")
    if rep.blockers or (a.fail_on == "major" and rep.majors):
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as e:  # under --python an exception would exit 0
        import traceback
        traceback.print_exc()
        print("check_inventory error:", repr(e))
        sys.exit(1)
