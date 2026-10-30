"""Check plan/layout.json against building-code-style limits before it is rendered: door and passage widths, stair
risers and treads, headroom and path clearance. Prints a table, writes JSON, exits 1 on a blocker (2 on a bad input).

    python .claude/skills/layout-2d/scripts/check_layout.py plan/layout.json [--rules plan/lint_rules.yaml]
        [--out plan/layout_check.json] [--allow-empty]
    (also runs under Blender: bash bin/blender-bg --python <this file> -- plan/layout.json)

Reads these optional fields on a shape (all metres; shapes without them are not measured):
  kind            "door" | "passage" | "stair" | "soffit". Without it the kind is guessed from the id and label
                  (door, gate, hatch; stair, steps; passage, corridor, alley, lane, walkway; soffit). A guessed kind
                  only warns; an explicit one blocks. A misspelt kind is an error.
  width_m         overrides the width taken from the polygon: a door's longer side, a passage's or stair's shorter side
                  of the smallest rectangle around it. Set it for L-shaped or wide-and-short shapes.
  z_m, steps      stair: z_m [bottom, top] and the number of risers (or riser_m, tread_m). Riser = rise / steps; tread =
                  the polygon's longer side / steps (a conservative reading: set tread_m if the top landing is inside).
                  A "8 steps" in the label is read as steps when the kind is guessed.
  clear_height_m  headroom under a lintel, soffit or stair; checked on any shape that has it.
  floor_m, z_m    soffit: headroom = z_m[0] - floor_m (floor_m defaults to 0).
  blocks          true, or legend "black", marks a shape the player path must keep clear of.
Path: top-level "path" is the player's centre line; its clear width is twice the distance to the nearest blocking shape.

Limits (metres) are IBC/IRC-style values; plan/lint_rules.yaml (or --rules) overrides them, either as flat
`key: value` lines or under a `layout:` heading; an unknown key under `layout:` is an error.
Self-test: scripts/selftest_check_layout.py.
"""
import argparse
import json
import math
import os
import re
import sys

RULES = {
    "door_min_width_m": 0.91,      # 36 in leaf as drawn (the code asks 32 in clear)
    "passage_min_width_m": 0.91,   # 36 in corridor
    "stair_min_width_m": 0.91,     # 36 in
    "riser_max_m": 0.178,          # 7 in
    "riser_min_m": 0.102,          # 4 in
    "tread_min_m": 0.279,          # 11 in
    "min_headroom_m": 2.03,        # 80 in
    "path_min_width_m": 0.91,      # clear width along the player path; set to the player width plus a margin for games
}
KINDS = ("door", "passage", "stair", "soffit")
GUESS = (("stair", r"\b(?:stair|steps?\b)"), ("door", r"\b(?:door|gate|hatch)"), ("soffit", r"\bsoffit"),
         ("passage", r"\b(?:passage|corridor|alley|lane|walkway)"))
EPS = 1e-6


# GEOMETRY (plan view, metres)

def rect_dims(poly):
    """Sides (long, short) of the smallest rectangle around a polygon, tried along each edge."""
    best = None
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        n = math.hypot(x1 - x0, y1 - y0)
        if n < 1e-9:
            continue
        ux, uy = (x1 - x0) / n, (y1 - y0) / n
        us = [(x - x0) * ux + (y - y0) * uy for x, y in poly]
        vs = [-(x - x0) * uy + (y - y0) * ux for x, y in poly]
        w, h = max(us) - min(us), max(vs) - min(vs)
        if best is None or w * h < best[0]:
            best = (w * h, max(w, h), min(w, h))
    if best is None:
        raise ValueError("a polygon with no edge length")
    return best[1], best[2]


def _pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _cross(a, b, c, d):
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0


def _inside(p, poly):
    hit = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > p[1]) != (y1 > p[1]) and p[0] < (x1 - x0) * (p[1] - y0) / (y1 - y0) + x0:
            hit = not hit
    return hit


def seg_poly_dist(a, b, poly):
    """Distance from segment a-b to a polygon; 0 when they touch or the segment starts inside."""
    edges = list(zip(poly, poly[1:] + poly[:1]))
    if _inside(a, poly) or _inside(b, poly) or any(_cross(a, b, c, d) for c, d in edges):
        return 0.0
    return min(min(_pt_seg(a, c, d), _pt_seg(b, c, d), _pt_seg(c, a, b), _pt_seg(d, a, b)) for c, d in edges)


# RULES FILE

def read_rules(path):
    """A flat or one-level `key: number` file; unknown keys under `layout:` raise, other top-level keys are not ours."""
    section, flat, lay = None, {}, {}
    for line in open(path, encoding="utf-8").read().splitlines():
        text = line.split("#")[0].rstrip()
        if not text.strip():
            continue
        key, _, val = text.strip().partition(":")
        val = val.strip()
        if text[0] not in " \t":
            section = key if not val else None
            if val and key in RULES:
                flat[key] = val
        elif section == "layout":
            lay[key] = val
    unknown = sorted(set(lay) - set(RULES))
    if unknown:
        raise ValueError(f"{path}: unknown keys under layout: {unknown}; known {sorted(RULES)}")
    try:
        return {k: float(v) for k, v in {**flat, **lay}.items()}
    except ValueError as e:
        raise ValueError(f"{path}: a limit is not a number ({e})") from None


# CHECKS

def guess_kind(s):
    text = (s["id"] + " " + s.get("label", "")).lower()
    return next((k for k, pat in GUESS if re.search(pat, text)), None)


def check(layout, rules):
    rows, skipped = [], []

    def judge(s, kind, what, value, lo=None, hi=None, inferred=False, note=""):
        bad = (lo is not None and value < lo - EPS) or (hi is not None and value > hi + EPS)
        rows.append({"id": s["id"], "kind": kind, "check": what, "value": round(value, 4), "min": lo, "max": hi,
                     "status": ("warn" if inferred else "blocker") if bad else "ok", "inferred": inferred, "note": note})

    for s in layout.get("shapes", []):
        poly = s.get("poly_m")
        kind, inferred = s.get("kind"), False
        if kind is None and poly and len(poly) >= 3:
            kind, inferred = guess_kind(s), True
        if kind is not None and kind not in KINDS:
            raise ValueError(f"{s['id']}: kind {kind!r} is not one of {KINDS}")
        if "clear_height_m" in s:
            judge(s, kind or "-", "headroom", s["clear_height_m"], lo=rules["min_headroom_m"], inferred=inferred and kind is not None)
        if kind is None:
            continue
        if not poly or len(poly) < 3:
            skipped.append(f"{s['id']}: {kind} has no poly_m")
            continue
        long_, short = rect_dims(poly)
        z = s.get("z_m")
        if kind == "door":
            judge(s, kind, "width", s.get("width_m", long_), lo=rules["door_min_width_m"], inferred=inferred)
        elif kind == "passage":
            judge(s, kind, "width", s.get("width_m", short), lo=rules["passage_min_width_m"], inferred=inferred)
        elif kind == "soffit":
            if isinstance(z, list) and len(z) == 2:
                judge(s, kind, "headroom", z[0] - s.get("floor_m", 0.0), lo=rules["min_headroom_m"], inferred=inferred)
            else:
                skipped.append(f"{s['id']}: soffit needs z_m [bottom, top]")
        else:
            judge(s, kind, "width", s.get("width_m", short), lo=rules["stair_min_width_m"], inferred=inferred)
            steps = s.get("steps")
            if not steps and inferred:
                m = re.search(r"(\d+)\s*steps?\b", s.get("label", "").lower())
                steps = int(m.group(1)) if m else None
            riser = s.get("riser_m") or (abs(z[1] - z[0]) / steps if steps and isinstance(z, list) and len(z) == 2 else None)
            tread = s.get("tread_m") or (long_ / steps if steps else None)
            if riser is None:
                skipped.append(f"{s['id']}: stair needs steps and z_m [bottom, top], or riser_m")
            else:
                judge(s, kind, "riser", riser, lo=rules["riser_min_m"], hi=rules["riser_max_m"], inferred=inferred)
            if tread is None:
                skipped.append(f"{s['id']}: stair needs steps or tread_m for the tread")
            else:
                judge(s, kind, "tread", tread, lo=rules["tread_min_m"], inferred=inferred)

    path = layout.get("path", [])
    blockers = [s for s in layout.get("shapes", []) if (s.get("blocks") or s.get("legend") == "black") and len(s.get("poly_m", [])) >= 3]
    if len(path) >= 2 and not blockers:
        skipped.append("path: no blocking shape (legend black or blocks: true) to measure against")
    for k, (a, b) in enumerate(zip(path, path[1:])):
        if blockers:
            d, nearest = min((seg_poly_dist(a, b, s["poly_m"]), s["id"]) for s in blockers)
            judge({"id": f"path[{k}]"}, "path", "clear width", 2 * d, lo=rules["path_min_width_m"], note="nearest " + nearest)
    return rows, skipped


# MAIN

def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("layout")
    p.add_argument("--rules", default=None, help="default: lint_rules.yaml next to the layout, when it exists")
    p.add_argument("--out", default=None, help="default: layout_check.json next to the layout")
    p.add_argument("--allow-empty", action="store_true", help="a layout with nothing to measure is not a failure (Stage 0 sketches)")
    a = p.parse_args(argv)
    here = os.path.dirname(os.path.abspath(a.layout))
    rules_path = a.rules or (os.path.join(here, "lint_rules.yaml") if os.path.exists(os.path.join(here, "lint_rules.yaml")) else None)
    rules = {**RULES, **(read_rules(rules_path) if rules_path else {})}
    rows, skipped = check(json.load(open(a.layout, encoding="utf-8")), rules)

    n = {s: sum(r["status"] == s for r in rows) for s in ("ok", "blocker", "warn")}
    print(f"{'ID':<14}{'KIND':<9}{'CHECK':<12}{'VALUE':>8}  {'LIMIT':<15}STATUS")
    for r in rows:
        lo, hi = r["min"], r["max"]
        limit = f"{lo:g} to {hi:g}" if None not in (lo, hi) else (f">= {lo:g}" if hi is None else f"<= {hi:g}")
        status = "ok" if r["status"] == "ok" else r["status"].upper() + (" (guessed kind)" if r["inferred"] else "") + ("  " + r["note"] if r["note"] else "")
        print(f"{r['id']:<14}{r['kind']:<9}{r['check']:<12}{r['value']:>8.3f}  {limit:<15}{status}")
    for s in skipped:
        print("skipped:", s)
    empty = not rows
    print(f"checked {len(rows)}: {n['ok']} ok, {n['blocker']} blockers, {n['warn']} warnings; {len(skipped)} skipped"
          + (f"; limits from {rules_path}" if rules_path else "; default limits"))
    if empty:
        print("nothing checked: no door, passage, stair, soffit, clear_height_m or path with a blocker in this layout")
    out = a.out or os.path.join(here, "layout_check.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"layout": os.path.abspath(a.layout), "rules_file": rules_path, "rules": rules, "counts": {**n, "checked": len(rows), "skipped": len(skipped)},
                   "rows": rows, "skipped": skipped}, f, indent=2)
    print("report", out)
    return 1 if n["blocker"] or (empty and not a.allow_empty) else 0


if __name__ == "__main__":
    try:
        code = main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    except (OSError, ValueError, KeyError) as e:   # a bad layout or rules file is an error, not a pass
        print("check_layout: error:", e, file=sys.stderr)
        code = 2
    sys.exit(code)
