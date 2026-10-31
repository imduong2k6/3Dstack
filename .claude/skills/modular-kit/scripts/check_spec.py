"""Check asset specs (`kit/*.md`, YAML front matter) against the template in the modular-kit skill. Plain Python, no Blender.

    python check_spec.py kit/*.md [--metrics plan/metrics.yaml] [--services plan/services.yaml] [--json] [--out report.json]
    python check_spec.py kit/SM_X.md --migrate      # rewrite the mechanical legacy renames in place, then check again

Checks: required keys; enums (type, source, mount, camera_tier, method); dims_m is three positive numbers [W, D, H];
dims_source is present and every `metrics.<row>` it names is a row of metrics.yaml; asset equals the file name; collision is
`UCX_<asset>_NN` or `none` with a reason (`collision_reason: ...`, a value that starts "none: ...", or a comment after it); ports are well formed
(pos_m, unit dir, kind, size_m); slots are {material_group, texture_set, ...} rows; asset_tech is a mapping; service_id is a node, run
or network id in services.yaml; the pivot word is one that validate_mesh.py can check. A spec with `superseded_by` (the piece that
replaces it) needs only `asset` and `type`: nothing is built from it, so the build fields are not required (they are still checked
when present). Legacy keys are errors that name the replacement. --migrate renames `id` to `asset` and
`source: build` to `model`, and `material: X` to `material_group: [X]`; `ends_local` needs a person (ports have a kind and a
section), so it stays an error. --migrate re-reads its own output and writes nothing if the result is not the old data renamed.

Without --metrics/--services the files are taken from `<project>/plan/` when the specs sit in `<project>/kit/`. Exit 1 when any
spec has an error, 2 when nothing could be read. YAML: PyYAML is not installed with the pipeline's Python (and not in Blender),
so this module has its own reader for the subset specs use (block maps and lists, flow lists and maps, quoted strings, block
scalars, no anchors or tags). Other scripts import `load_spec`, `load_yaml_file` and `pivot_anchor` from here.
"""
import argparse
import glob
import json
import math
import os
import re
import sys


class SpecError(Exception):
    pass


# ---- YAML subset reader ----------------------------------------------------

_ESC = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", '"': '"', "/": "/", " ": " "}


def _strip_comment(s):
    q, i = None, 0
    while i < len(s):
        c = s[i]
        if q:
            if c == "\\" and q == '"':
                i += 2
                continue
            if c == q:
                if q == "'" and s[i + 1:i + 2] == "'":
                    i += 2
                    continue
                q = None
        elif c in "\"'" and (i == 0 or s[i - 1] in " \t[{,"):
            q = c
        elif c == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i].rstrip()
        i += 1
    return s.rstrip()


def _quoted(s):
    """Read the quoted scalar at the start of s; return (value, index after the closing quote)."""
    q, i, out = s[0], 1, []
    while i < len(s):
        c = s[i]
        if q == "'":
            if c == "'":
                if s[i + 1:i + 2] == "'":
                    out.append("'")
                    i += 2
                    continue
                return "".join(out), i + 1
            out.append(c)
        elif c == '"':
            return "".join(out), i + 1
        elif c == "\\" and i + 1 < len(s):
            i += 1
            if s[i] == "u" and re.match(r"[0-9a-fA-F]{4}", s[i + 1:i + 5]):
                out.append(chr(int(s[i + 1:i + 5], 16)))
                i += 5
                continue
            out.append(_ESC.get(s[i], "\\" + s[i]))
        else:
            out.append(c)
        i += 1
    raise SpecError("unterminated quoted string: " + s[:30])


def _plain(s):
    s = s.strip()
    if s in ("", "~", "null", "Null", "NULL"):
        return None
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
        return False
    if re.fullmatch(r"[-+]?(0|[1-9]\d*)", s):
        return int(s)
    if re.fullmatch(r"[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?", s) and re.search(r"[.eE]", s):
        return float(s)
    return s


def _flow(s):
    pos = 0

    def ws():
        nonlocal pos
        while pos < len(s) and s[pos] in " \t":
            pos += 1

    def scalar(key):
        nonlocal pos
        ws()
        if pos < len(s) and s[pos] in "\"'":
            v, n = _quoted(s[pos:])
            pos += n
            return v
        start = pos
        while pos < len(s) and s[pos] not in ",]}":
            if key and s[pos] == ":" and (pos + 1 == len(s) or s[pos + 1] in " ,]}"):
                break
            pos += 1
        return _plain(s[start:pos]) if not key else s[start:pos].strip()

    def value():
        nonlocal pos
        ws()
        if pos >= len(s):
            raise SpecError("flow value ends early: " + s)
        if s[pos] in "[{":
            close = "]" if s[pos] == "[" else "}"
            is_map = close == "}"
            pos += 1
            out = {} if is_map else []
            while True:
                ws()
                if pos >= len(s):
                    raise SpecError("unclosed " + ("{" if is_map else "[") + " in: " + s)
                if s[pos] == close:
                    pos += 1
                    return out
                if is_map:
                    k = scalar(True)
                    ws()
                    if pos >= len(s) or s[pos] != ":":
                        raise SpecError(f"flow map key `{k}` has no value in: {s}")
                    pos += 1
                    ws()
                    out[k] = None if pos < len(s) and s[pos] in ",}" else value()
                else:
                    out.append(value())
                ws()
                if pos < len(s) and s[pos] == ",":
                    pos += 1
                elif pos < len(s) and s[pos] != close:
                    raise SpecError(f"expected , or {close} in: {s}")
        return scalar(False)

    v = value()
    ws()
    if pos != len(s):
        raise SpecError("text after a flow value: " + s[pos:])
    return v


def _balanced(s):
    depth, q, i = 0, None, 0
    while i < len(s):
        c = s[i]
        if q:
            if c == "\\" and q == '"':
                i += 1
            elif c == q:
                q = None
        elif c in "\"'" and (i == 0 or s[i - 1] in " \t[{,:"):
            q = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        i += 1
    return depth <= 0 and q is None


def _closed(s):
    try:
        _quoted(s)
        return True
    except SpecError:
        return False


def _value(s):
    s = s.strip()
    if not s:
        return None
    if s[0] in "[{":
        return _flow(s)
    if s[0] in "\"'":
        v, n = _quoted(s)
        if s[n:].strip():
            raise SpecError("text after a quoted string: " + s[n:].strip())
        return v
    return _plain(s)


def _split_kv(s):
    if s[0] in "[{":
        return None
    if s[0] in "\"'":
        try:
            k, n = _quoted(s)
        except SpecError:
            return None
        rest = s[n:].lstrip()
        return (k, rest[1:].strip()) if rest[:1] == ":" and rest[1:2] in ("", " ") else None
    m = re.match(r"(.+?)(?::[ ]+|:$)(.*)$", s)
    return (m.group(1).strip(), m.group(2).strip()) if m else None


def _is_item(b):
    return b == "-" or b.startswith("- ")


def _rows(text):
    raw, rows, i = text.splitlines(), [], 0
    while i < len(raw):
        line = raw[i]
        i += 1
        if "\t" in line[:len(line) - len(line.lstrip())]:
            raise SpecError("tab in indentation: " + line.strip()[:40])
        s = _strip_comment(line)
        body = s.strip()
        if not body or body == "---":
            continue
        indent = len(s) - len(s.lstrip(" "))
        m = re.search(r"(^|:\s+|-\s+)([|>])([+-]?\d?|\d?[+-]?)$", body)
        if m:
            blk = []
            while i < len(raw) and (not raw[i].strip() or len(raw[i]) - len(raw[i].lstrip(" ")) > indent):
                blk.append(raw[i])
                i += 1
            pad = min([len(b) - len(b.lstrip(" ")) for b in blk if b.strip()] or [0])
            lines = [b[pad:] for b in blk]
            while lines and not lines[-1].strip():
                lines.pop()
            text_val = "\n".join(lines) if m.group(2) == "|" else re.sub(r"(?<!\n)\n(?!\n)", " ", "\n".join(lines))
            body = body[:m.start(2)] + json.dumps(text_val + ("" if "-" in m.group(3) else "\n"), ensure_ascii=False)
        rows.append([indent, body])
    return rows


def _more(rows, i, indent, rest):
    """Join the lines a flow collection, a quoted string or a plain scalar continues over."""
    if rest[0] in "[{":
        while not _balanced(rest) and i < len(rows):
            rest += " " + rows[i][1]
            i += 1
    elif rest[0] in "\"'":
        while not _closed(rest) and i < len(rows):
            rest += " " + rows[i][1]
            i += 1
    else:
        while i < len(rows) and rows[i][0] > indent:
            rest += " " + rows[i][1]
            i += 1
    return rest, i


def _block(rows, i, indent):
    body = rows[i][1]
    if _is_item(body):
        return _seq(rows, i, indent)
    if _split_kv(body) is not None:
        return _map(rows, i, indent)
    rest, j = _more(rows, i + 1, indent - 1, body)
    return _value(rest), j


def _seq(rows, i, indent):
    out = []
    while i < len(rows) and rows[i][0] == indent and _is_item(rows[i][1]):
        body = rows[i][1]
        rest = body[1:].lstrip(" ")
        if not rest:
            i += 1
            if i < len(rows) and rows[i][0] > indent:
                v, i = _block(rows, i, rows[i][0])
            else:
                v = None
            out.append(v)
        elif _is_item(rest) or _split_kv(rest) is not None:
            col = indent + len(body) - len(rest)
            rows[i] = [col, rest]
            v, i = _block(rows, i, col)
            out.append(v)
        else:
            rest, i = _more(rows, i + 1, indent, rest)
            out.append(_value(rest))
    return out, i


def _map(rows, i, indent):
    out = {}
    while i < len(rows) and rows[i][0] == indent and not _is_item(rows[i][1]):
        kv = _split_kv(rows[i][1])
        if kv is None:
            raise SpecError("cannot read line: " + rows[i][1])
        key, rest = kv
        if key in out:
            raise SpecError("duplicate key: " + key)
        i += 1
        if rest == "":
            if i < len(rows) and (rows[i][0] > indent or (rows[i][0] == indent and _is_item(rows[i][1]))):
                out[key], i = _block(rows, i, rows[i][0])
            else:
                out[key] = None
        else:
            rest, i = _more(rows, i, indent, rest)
            out[key] = _value(rest)
    if i < len(rows) and rows[i][0] > indent:
        raise SpecError("unexpected indentation at: " + rows[i][1])
    return out, i


def parse_yaml(text):
    rows = _rows(text)
    if not rows:
        return None
    val, i = _block(rows, 0, rows[0][0])
    if i != len(rows):
        raise SpecError("cannot read line: " + rows[i][1])
    return val


# ---- files ------------------------------------------------------------------

def front_matter_span(text):
    """(first, last) line indexes of the front matter body in text.splitlines(keepends=True), or None."""
    lines = text.lstrip("\ufeff").splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None
    for j in range(1, len(lines)):
        if lines[j].strip() in ("---", "..."):
            return 1, j
    return None


def parse_front_matter(text):
    span = front_matter_span(text)
    if not span:
        raise SpecError("no YAML front matter: the file must start with a --- line and close it with another")
    data = parse_yaml("".join(text.lstrip("\ufeff").splitlines(keepends=True)[span[0]:span[1]]))
    if not isinstance(data, dict):
        raise SpecError("the front matter is not a mapping of keys")
    return data


def _read(path):
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise SpecError(f"cannot read {path}: {e}")


def load_spec(path):
    return parse_front_matter(_read(path))


def load_yaml_file(path):
    text = _read(path)
    try:
        return json.loads(text) if path.lower().endswith(".json") else parse_yaml(text)
    except ValueError as e:
        raise SpecError(f"cannot parse {path}: {e}")


def top_level_comments(text):
    """{key: trailing comment} for the `key: value  # comment` lines of the front matter (a collision reason may sit there)."""
    span, out = front_matter_span(text), {}
    for line in (text.lstrip("\ufeff").splitlines()[span[0]:span[1]] if span else []):
        m = re.match(r"([A-Za-z_]\w*)\s*:(.*)$", line)
        if m:
            c = m.group(2)[len(_strip_comment(m.group(2))):].strip().lstrip("#").strip()
            if c:
                out[m.group(1)] = c
    return out


def collect_ids(node, out=None):
    """Every `id` value in a services file, at any depth (networks, nodes, runs, fittings)."""
    out = set() if out is None else out
    if isinstance(node, dict):
        if isinstance(node.get("id"), (str, int)):
            out.add(str(node["id"]))
        for v in node.values():
            collect_ids(v, out)
    elif isinstance(node, list):
        for v in node:
            collect_ids(v, out)
    return out


# ---- pivot words (shared with validate_mesh.py) -----------------------------

_PIVOT_SIDES = {"bottom": ("z", "min"), "top": ("z", "max"), "back": ("y", "max"), "front": ("y", "min"),
                "left": ("x", "min"), "right": ("x", "max")}


def pivot_anchor(pivot):
    """Where the origin sits in the local bounding box: {axis: 'min' | 'max' | 'center'}, or None for words not known.

    bottom/top = z min/max, front/back = y min/max (the front looks along -Y, the wall is behind at +Y), left/right = x min/max,
    center = the middle of every axis not named, corner = the min corner. `bottom-center`, `top-center`, `back-face-centre`,
    `center`, `grid-corner` are all fine. An axis the word does not name is not checked.
    """
    anchor, centre, corner = {}, False, False
    for w in re.split(r"[\s_\-]+", str(pivot).strip().lower()):
        if w in _PIVOT_SIDES:
            ax, side = _PIVOT_SIDES[w]
            if anchor.setdefault(ax, side) != side:
                return None
        elif w in ("center", "centre", "middle"):
            centre = True
        elif w == "corner":
            corner = True
        elif w not in ("face", "of", "the", "grid", "origin"):
            return None
    if not (anchor or centre or corner):
        return None
    for ax in "xyz":
        anchor.setdefault(ax, "min" if corner else "center" if centre else None)
    return {ax: side for ax, side in anchor.items() if side}


# ---- the template -----------------------------------------------------------

TYPES = ("kit", "prop", "hero")
SOURCES = ("model", "library", "generate", "unreal_modeling")
MOUNTS = ("floor", "wall", "hang", "inset")
TIERS = ("hero", "mid", "far")
METHODS = ("subd_quad", "game_midpoly", "game_bake", "game_lowpoly", "fast_cg", "repair")
REQUIRED = ("asset", "type", "phase", "source", "priority", "count_in_scene", "photos", "dims_m", "dims_source", "mount",
            "pivot", "material_group", "camera_tier", "budget_tris", "collision", "done_when")
KIT_REQUIRED = ("kit", "snap_grid_m", "ports")
OPTIONAL = ("sockets", "clearance_m", "texture_set", "texel_density_px_m", "service_id", "landmarks", "generated",
            "collision_reason", "method", "why", "expected_tris", "classification", "file", "validation",
            "slots", "asset_tech", "superseded_by")
# old key -> (new key, whether --migrate can do it alone)
LEGACY_KEYS = {"id": ("asset", True), "material": ("material_group", True), "ends_local": ("ports", False)}
LEGACY_VALUES = {("source", "build"): "model"}
PORT_KEYS = {"name", "pos_m", "dir", "kind", "size_m", "role", "note"}
PORT_ROLES = ("end", "opening", "inset")   # kit_joint_test.py: a joint between pieces; a hole in a face (a bay's door or window); the piece that fills one
SLOT_KEYS = {"material_group", "texture_set", "uv", "strips", "note"}
# what the Asset Tech writes under asset_tech (export result); an unlisted key is a warning, not an error
ASSET_TECH_KEYS = {"fbx", "fbx_open", "fbx_settings", "reimport", "tris", "slots", "ucx_count", "texel_density", "sockets_exported",
                   "lods", "nanite", "unreal_import", "note"}
LEVELS = ("error", "warn")


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _vec(x, n):
    return isinstance(x, list) and len(x) == n and all(_num(v) for v in x)


def _int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _text(x):
    return isinstance(x, str) and bool(x.strip())


def check_spec(data, stem=None, metrics=None, service_ids=None, comments=None):
    """Return the findings for one parsed spec: dicts with level (error | warn), code, key, message. comments: top_level_comments()."""
    out = []

    def add(level, code, key, msg, **kw):
        out.append({"level": level, "code": code, "key": key, "message": msg, **kw})

    def err(code, key, msg, **kw):
        add("error", code, key, msg, **kw)

    def warn(code, key, msg, **kw):
        add("warn", code, key, msg, **kw)

    renamed = set()
    for old, (new, mechanical) in LEGACY_KEYS.items():
        if old in data:
            renamed.add(new)
            if new in data:
                err("legacy_key", old, f"legacy key `{old}` is still there beside `{new}`: delete `{old}`", replacement=new, fixable=False)
            else:
                how = "--migrate renames it" if mechanical else "needs a person: it becomes ports with a kind and a section"
                err("legacy_key", old, f"legacy key `{old}`: use `{new}` ({how})", replacement=new, fixable=mechanical)
    for (key, old), new in LEGACY_VALUES.items():
        if data.get(key) == old:
            err("legacy_value", key, f"`{key}: {old}` is legacy: use `{key}: {new}` (--migrate renames it)", replacement=new, fixable=True)

    kit = data.get("type") == "kit"
    sup = data.get("superseded_by")
    superseded = _text(sup) or (isinstance(sup, list) and bool(sup) and all(_text(x) for x in sup))
    if sup is not None and not superseded:
        err("type", "superseded_by", "superseded_by is the piece or set that replaces this one (a line, or a list of lines), or null")
    for key in ("asset", "type") if superseded else REQUIRED + (KIT_REQUIRED if kit else ()):
        if data.get(key) is None and key not in renamed:
            err("missing_key", key, f"required key `{key}` is missing" + (" (a kit piece needs it)" if key in KIT_REQUIRED else ""))
    known = set(REQUIRED) | set(KIT_REQUIRED) | set(OPTIONAL) | set(LEGACY_KEYS)
    for key in data:
        if key not in known:
            warn("unknown_key", key, f"`{key}` is not in the asset spec template")

    for key, allowed in (("type", TYPES), ("source", SOURCES), ("mount", MOUNTS), ("camera_tier", TIERS), ("method", METHODS)):
        v = data.get(key)
        if v is not None and v not in allowed and not (isinstance(v, str) and (key, v) in LEGACY_VALUES):
            err("enum", key, f"`{key}: {v}` is not one of {' | '.join(allowed)}")

    asset = data.get("asset")
    if asset is not None:
        if not _text(asset):
            err("asset_name", "asset", "asset must be a name")
        elif stem is not None and asset != stem:
            err("asset_name", "asset", f"asset `{asset}` must equal the file name `{stem}`")
        elif not re.match(r"(SM|SK)_\w+$", asset):
            warn("asset_name", "asset", f"`{asset}` does not start with SM_ or SK_")

    if data.get("phase") is not None and not (_int(data["phase"]) and 0 <= data["phase"] <= 9):
        err("type", "phase", "phase is the placement phase number 0 to 9")
    if data.get("priority") is not None and not (_int(data["priority"]) and data["priority"] >= 1):
        err("type", "priority", "priority is a whole number from 1 (built first)")
    c = data.get("count_in_scene")
    if c is not None and not ((_int(c) and c >= 0) or _text(c)):
        err("type", "count_in_scene", "count_in_scene is a number, or a range and how it is set")
    if data.get("budget_tris") is not None and not (_int(data["budget_tris"]) and data["budget_tris"] > 0):
        err("type", "budget_tris", "budget_tris is a positive whole number")
    if data.get("photos") is not None and not isinstance(data["photos"], list):
        err("type", "photos", "photos is a list of reference crops")
    elif data.get("photos") == [] and not superseded:
        warn("type", "photos", "photos is empty: the spec has no reference crop")
    if kit and data.get("snap_grid_m") is not None and not (_num(data["snap_grid_m"]) and data["snap_grid_m"] > 0):
        err("type", "snap_grid_m", "snap_grid_m is a positive number of metres")
    if data.get("texel_density_px_m") is not None and not (_num(data["texel_density_px_m"]) and data["texel_density_px_m"] > 0):
        err("type", "texel_density_px_m", "texel_density_px_m is a positive number")
    if kit and not superseded and data.get("texture_set") is None:
        warn("missing_key", "texture_set", "texture_set is not set")

    d = data.get("dims_m")
    if d is not None and not (_vec(d, 3) and all(x > 0 for x in d)):
        err("dims", "dims_m", "dims_m is three positive numbers [W, D, H] in metres")

    src = data.get("dims_source")
    if src is not None:
        parts = src if isinstance(src, list) else [src]
        if not parts or not all(_text(p) for p in parts):
            err("dims_source", "dims_source", "dims_source is the metrics.<row> or the measured crop the size comes from")
        elif metrics is not None:
            for p in parts:
                for row in re.findall(r"\bmetrics\.([A-Za-z_]\w*)", p):
                    if row not in metrics:
                        err("metrics_row", "dims_source", f"metrics.{row} is not a row of metrics.yaml")

    pv = data.get("pivot")
    if pv is not None:
        if not _text(pv):
            err("type", "pivot", "pivot is a word such as bottom-center")
        elif pivot_anchor(pv) is None:
            warn("pivot", "pivot", f"pivot `{pv}` is not a word validate_mesh.py can check (bottom-center, top-center, back-face-centre, center, corner)")

    mg = data.get("material_group")
    if mg is not None:
        if not (isinstance(mg, list) and mg and all(_text(g) for g in mg)):
            err("type", "material_group", "material_group is a list of palette group names, one per material slot")
        else:
            for g in mg:
                if g.startswith("M_"):
                    warn("material_group", "material_group", f"`{g}` looks like a material name: list the group (without M_)")

    col = data.get("collision")
    if col is not None:
        head = re.match(r"[A-Za-z0-9_]*", str(col).strip()).group(0)
        if head == "none":
            tail = re.sub(r"^none\W*", "", str(col).strip())
            if not (_text(data.get("collision_reason")) or len(tail) >= 3 or len((comments or {}).get("collision", "")) >= 3):
                err("collision", "collision", "collision `none` needs a reason: add `collision_reason: ...` or a comment after it")
        elif isinstance(asset, str) and not re.fullmatch(rf"UCX_{re.escape(asset)}_\d\d", head):
            err("collision", "collision", f"collision must be UCX_{asset}_NN (two digits) or none with a reason, not `{head}`")

    ports = data.get("ports")
    if ports is not None:
        _check_ports(ports, err, warn)
        if kit and ports == [] and not superseded:
            warn("port", "ports", "a kit piece with no ports never joins anything")
    soc = data.get("sockets")
    if soc is not None:
        if not isinstance(soc, list):
            err("socket", "sockets", "sockets is a list of {name, pos_m}")
        else:
            for n, s in enumerate(soc):
                if not (isinstance(s, dict) and _text(s.get("name")) and _vec(s.get("pos_m"), 3)):
                    err("socket", f"sockets[{n}]", "a socket needs a name and pos_m [x, y, z]")

    if data.get("slots") is not None:
        _check_slots(data["slots"], data.get("material_group"), err, warn)
    at = data.get("asset_tech")
    if at is not None:
        if not isinstance(at, dict):
            err("type", "asset_tech", "asset_tech is the Asset Tech's result: a mapping (fbx, reimport, tris, ucx_count, ...)")
        else:
            for k in sorted(set(at) - ASSET_TECH_KEYS):
                warn("unknown_key", f"asset_tech.{k}", f"`{k}` is not an asset_tech key the template lists")
            for k, ok in (("tris", lambda v: _int(v) and v > 0), ("ucx_count", lambda v: _int(v) and v >= 0),
                          ("slots", lambda v: isinstance(v, list)), ("sockets_exported", lambda v: isinstance(v, list))):
                if at.get(k) is not None and not ok(at[k]):
                    err("type", f"asset_tech.{k}", f"asset_tech.{k} is " + {"tris": "a positive whole number", "ucx_count": "a whole number",
                                                                           "slots": "a list of material names", "sockets_exported": "a list of socket names"}[k])

    sid = data.get("service_id")
    if sid is not None:
        if not _text(str(sid)):
            err("service_id", "service_id", "service_id is an id from services.yaml, or null")
        elif service_ids is not None and str(sid) not in service_ids:
            err("service_id", "service_id", f"service_id `{sid}` is not an id in services.yaml")
    if data.get("landmarks") is not None and not _text(data["landmarks"]):
        err("type", "landmarks", "landmarks is the path of the landmarks json")

    if data.get("source") == "generate" and not isinstance(data.get("generated"), dict) and not superseded:
        err("missing_key", "generated", "source `generate` needs the `generated` block (generated-asset skill)")
    dw = data.get("done_when")
    if dw is not None and not (isinstance(dw, list) and dw and all(_text(x) for x in dw)):
        err("type", "done_when", "done_when is a list of measurable acceptance lines")
    et = data.get("expected_tris")
    if et is not None and not (_int(et) and et > 0):
        err("type", "expected_tris", "expected_tris is a positive whole number")
    return out


def _check_slots(slots, groups, err, warn):
    if not isinstance(slots, list):
        err("slot", "slots", "slots is a list of {material_group, texture_set, uv, strips}")
        return
    seen = set()
    for n, sl in enumerate(slots):
        where = f"slots[{n}]"
        if not (isinstance(sl, dict) and _text(sl.get("material_group")) and _text(sl.get("texture_set"))):
            err("slot", where, "a slot is a mapping with a material_group and a texture_set")
            continue
        g = sl["material_group"]
        if g in seen:
            err("slot", where, f"material_group `{g}` has two slots")
        seen.add(g)
        if isinstance(groups, list) and g not in groups:
            warn("slot", where, f"material_group `{g}` is not in the spec's material_group list")
        if sl.get("strips") is not None and not (isinstance(sl["strips"], list) and all(_text(x) for x in sl["strips"])):
            err("slot", where, "strips is a list of trim strips, or null")
        extra = sorted(set(sl) - SLOT_KEYS)
        if extra:
            warn("slot", where, "unknown slot key " + ", ".join(extra))


def _check_ports(ports, err, warn):
    if not isinstance(ports, list):
        err("port", "ports", "ports is a list of {name, pos_m, dir, kind, size_m}")
        return
    seen = set()
    for n, p in enumerate(ports):
        where = f"ports[{n}]"
        if not isinstance(p, dict):
            err("port", where, "a port is a mapping {name, pos_m, dir, kind, size_m}")
            continue
        name = p.get("name")
        if not _text(name):
            err("port", where, "port has no name")
        else:
            where += f" ({name})"
            if name in seen:
                err("port", where, "duplicate port name")
            seen.add(name)
        if not _vec(p.get("pos_m"), 3):
            err("port", where, "pos_m must be three numbers [x, y, z] in metres")
        if not _vec(p.get("dir"), 3):
            err("port", where, "dir must be three numbers, the outward unit normal")
        elif abs(math.sqrt(sum(x * x for x in p["dir"])) - 1) > 1e-3:
            err("port", where, f"dir must have length 1, it has {math.sqrt(sum(x * x for x in p['dir'])):.4f}")
        if not _text(p.get("kind")):
            err("port", where, "kind is missing: two ports mate only when their kinds are equal")
        if p.get("role") is not None and p["role"] not in PORT_ROLES:
            err("port", where, f"role must be one of {' | '.join(PORT_ROLES)}, not `{p['role']}`")
        s = p.get("size_m")
        if not (isinstance(s, list) and len(s) in (1, 2) and all(_num(x) and x > 0 for x in s)):
            err("port", where, "size_m must be [d] for round or [w, h] for rectangular, in positive metres")
        extra = sorted(set(p) - PORT_KEYS)
        if extra:
            warn("port", where, "unknown port key " + ", ".join(extra))


# ---- migrate ----------------------------------------------------------------

def _rename(d, old, new, wrap=False):
    return {(new if k == old else k): ([v] if wrap and k == old else v) for k, v in d.items()}


def migrate_text(text):
    """Apply the mechanical renames to the front matter. Returns (new text, list of notes); refuses a result that is more than the renames."""
    span = front_matter_span(text)
    if not span:
        raise SpecError("no YAML front matter")
    old_data = parse_front_matter(text)
    lines = text.splitlines(keepends=True)
    notes, expected = [], old_data
    for n in range(span[0], span[1]):
        body = lines[n].rstrip("\r\n")
        eol = lines[n][len(body):]
        m = re.match(r"(id|material)(\s*):(.*)$", body)
        if m and m.group(1) == "id" and "asset" not in old_data:
            lines[n] = "asset" + m.group(2) + ":" + m.group(3) + eol
            expected = _rename(expected, "id", "asset")
            notes.append("id -> asset")
        elif m and m.group(1) == "material" and "material_group" not in old_data:
            val = _strip_comment(m.group(3)).strip()
            comment = m.group(3)[len(_strip_comment(m.group(3))):]
            if val and val[0] not in "[|>":
                lines[n] = f"material_group{m.group(2)}: [{val}]{comment}{eol}"
                expected = _rename(expected, "material", "material_group", wrap=True)
                notes.append("material -> material_group (value wrapped in a list)")
            elif not val or val[0] == "[":
                lines[n] = "material_group" + m.group(2) + ":" + m.group(3) + eol
                expected = _rename(expected, "material", "material_group")
                notes.append("material -> material_group")
        elif old_data.get("source") == "build" and re.match(r"source\s*:\s*build\s*(#.*)?$", body):
            lines[n] = re.sub(r"\bbuild\b", "model", body, count=1) + eol
            expected = dict(expected, source="model")
            notes.append("source: build -> model")
    new = "".join(lines)
    if notes and parse_front_matter(new) != expected:
        raise SpecError("migrate would change more than the renames; the file was left as it is")
    return new, notes


# ---- run --------------------------------------------------------------------

def check_file(path, metrics=None, service_ids=None):
    """Findings for one spec file as a report row."""
    row = {"file": path, "asset": None, "errors": [], "warnings": []}
    try:
        text = _read(path)
        data = parse_front_matter(text)
        row["asset"] = data.get("asset") if isinstance(data.get("asset"), str) else None
        found = check_spec(data, os.path.splitext(os.path.basename(path))[0], metrics, service_ids,
                           top_level_comments(text))
    except SpecError as e:
        found = [{"level": "error", "code": "front_matter" if "front matter" in str(e) else "parse", "key": None, "message": str(e)}]
    for f in found:
        row["errors" if f["level"] == "error" else "warnings"].append({k: v for k, v in f.items() if k != "level"})
    return row


def summarize(rows):
    by = {"errors": {}, "warnings": {}}
    for r in rows:
        for kind in by:
            for f in r[kind]:
                by[kind][f["code"]] = by[kind].get(f["code"], 0) + 1
    return {"specs": len(rows), "errors": sum(by["errors"].values()), "warnings": sum(by["warnings"].values()), "by_code": by}


def format_table(rep):
    out = []
    for r in rep["specs"]:
        if not (r["errors"] or r["warnings"]):
            continue
        out.append(f"{os.path.basename(r['file'])}: {len(r['errors'])} error(s), {len(r['warnings'])} warning(s)")
        for kind, tag in (("errors", "ERROR"), ("warnings", "warn ")):
            for f in r[kind]:
                out.append(f"  {tag}  {f['code']:<13} {str(f['key'] or ''):<20} {f['message']}")
    s = rep["summary"]
    out.append(f"{s['specs']} spec(s), {s['errors']} error(s), {s['warnings']} warning(s); metrics: {rep['checked']['metrics'] or 'not checked'}, "
               f"services: {rep['checked']['services'] or 'not checked'}")
    for kind in ("errors", "warnings"):
        if s["by_code"][kind]:
            out.append(f"{kind} by type: " + ", ".join(f"{k} {v}" for k, v in sorted(s["by_code"][kind].items())))
    out.append("PASS" if rep["pass"] else "FAIL")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="check_spec.py", description="Check asset specs (kit/*.md) against the template.")
    ap.add_argument("specs", nargs="+", help="spec files; wildcards are expanded here")
    ap.add_argument("--metrics", help="plan/metrics.yaml (default: <project>/plan/metrics.yaml when it exists)")
    ap.add_argument("--services", help="plan/services.yaml (default: <project>/plan/services.yaml when it exists)")
    ap.add_argument("--json", action="store_true", help="print the JSON report instead of the table")
    ap.add_argument("--out", help="also write the JSON report to this file")
    ap.add_argument("--migrate", action="store_true", help="rewrite id, source: build and material in place, then check")
    a = ap.parse_args(argv)
    paths = sorted({p for s in a.specs for p in (glob.glob(s) if re.search(r"[*?\[]", s) else [s])})
    if not paths:
        print("check_spec: no spec files matched", file=sys.stderr)
        return 2
    plan = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(paths[0]))), "plan")
    metrics_path = a.metrics or next((p for p in [os.path.join(plan, "metrics.yaml")] if os.path.exists(p)), None)
    services_path = a.services or next((p for p in [os.path.join(plan, "services.yaml")] if os.path.exists(p)), None)
    try:
        m = load_yaml_file(metrics_path) if metrics_path else None
        metrics = (m.get("metrics") if isinstance(m, dict) and isinstance(m.get("metrics"), dict) else m) if m is not None else None
        if metrics_path and not isinstance(metrics, dict):
            raise SpecError(f"{metrics_path} is not a mapping of metric rows")
        service_ids = collect_ids(load_yaml_file(services_path)) if services_path else None
    except SpecError as e:
        print("check_spec:", e, file=sys.stderr)
        return 2
    notes = []
    if a.migrate:
        for p in paths:
            try:
                text = _read(p)
                new, done = migrate_text(text)
                if done:
                    with open(p, "w", encoding="utf-8", newline="") as f:
                        f.write(new)
                    notes.append(f"{p}: " + "; ".join(done))
            except SpecError as e:
                notes.append(f"{p}: not migrated: {e}")
    rows = [check_file(p, metrics, service_ids) for p in paths]
    rep = {"pass": not any(r["errors"] for r in rows), "checked": {"metrics": metrics_path, "services": services_path},
           "summary": summarize(rows), "specs": rows}
    if notes:
        rep["migrated"] = notes
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1)
    print(json.dumps(rep, indent=1) if a.json else "\n".join(["MIGRATED " + n for n in notes] + [format_table(rep)]))
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
