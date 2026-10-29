#!/usr/bin/env python3
"""Scan Unreal plugins, Blender add-ons and extensions, MCP servers and CLIs.

Prints (or writes) JSON with one row per tool and a diff against the machine's
manifest, so the toolbox scanner only researches new or changed tools.

Standard library only. Python 3.11+ (tomllib).

Examples (Windows, Git Bash or PowerShell):
  python scan_toolbox.py --machine studio-pc \
      --ue-root "C:/Program Files/Epic Games/UE_5.8" \
      --uproject "D:/Projects/Hotel/Hotel.uproject" \
      --blender-config "$APPDATA/Blender Foundation/Blender/5.2" \
      --manifest toolbox/manifest.studio-pc.json --out scan.json
  python scan_toolbox.py --machine studio-pc --manifest toolbox/manifest.studio-pc.json \
      --update-manifest scan.json
  python scan_toolbox.py --machine studio-pc --manifest toolbox/manifest.studio-pc.json \
      --mark ue.pcg --doc toolbox/tools/ue.pcg.md
"""
import argparse
import ast
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

# Engine plugins worth an instruction file even when the project doesn't enable them.
RELEVANT_ENGINE = {
    "pcg", "pcggeometryscriptinterop", "geometryscripting", "modelingtoolseditormode",
    "pythonscriptplugin", "editorscriptingutilities", "movierenderpipeline", "usdimporter",
    "cablecomponent", "water", "landmass", "proceduralmeshcomponent", "modelcontextprotocol",
    "datasmithimporter", "fracture", "scriptabletoolsframework",
}
DEFAULT_CLIS = ["git", "git-lfs", "blender", "ffmpeg", "magick", "oiiotool", "tripo", "claude"]


def sig(data: bytes, extra: str = "") -> str:
    return hashlib.sha1(data + extra.encode()).hexdigest()[:16]


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def read_json_loose(path: Path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(re.sub(r",(\s*[}\]])", r"\1", text))  # trailing commas


def scan_unreal(ue_roots, uproject, all_engine):
    tools, enabled = [], {}
    proj_plugins_dir = None
    if uproject:
        up = Path(uproject)
        try:
            data = read_json_loose(up)
            enabled = {p["Name"].lower(): p.get("Enabled", True) for p in data.get("Plugins", [])}
        except (OSError, ValueError, KeyError) as e:
            print(f"warning: cannot read {up}: {e}", file=sys.stderr)
        proj_plugins_dir = up.parent / "Plugins"
    roots = [(proj_plugins_dir, "project")] if proj_plugins_dir and proj_plugins_dir.is_dir() else []
    roots += [(Path(r) / "Engine" / "Plugins", "engine") for r in ue_roots]
    for root, origin in roots:
        if not root.is_dir():
            print(f"warning: not found: {root}", file=sys.stderr)
            continue
        for f in root.rglob("*.uplugin"):
            stem = f.stem.lower()
            where = origin
            parts = {p.lower() for p in f.parts}
            if origin == "engine" and ("marketplace" in parts or "fab" in parts):
                where = "marketplace"
            keep = (where != "engine" or all_engine or stem in RELEVANT_ENGINE
                    or enabled.get(stem) is True)
            if not keep:
                continue
            raw = f.read_bytes()
            try:
                d = read_json_loose(f)
            except ValueError:
                d = {}
            tools.append({
                "id": f"ue.{stem}",
                "kind": "unreal_plugin",
                "name": d.get("FriendlyName") or f.stem,
                "version": str(d.get("VersionName") or d.get("Version") or ""),
                "origin": where,
                "enabled_in_project": enabled.get(stem),
                "path": str(f.parent),
                "description": d.get("Description", ""),
                "docs": d.get("DocsURL") or d.get("MarketplaceURL") or "",
                "by": d.get("CreatedBy", ""),
                "signature": sig(raw),
            })
    return tools


def parse_bl_info(init_py: Path):
    try:
        tree = ast.parse(init_py.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "bl_info" for t in node.targets):
            try:
                return ast.literal_eval(node.value)
            except ValueError:
                return None
    return None


def scan_blender(config_dirs):
    tools = []
    for cfg in map(Path, config_dirs):
        addons = cfg / "scripts" / "addons"
        if addons.is_dir():
            for entry in sorted(addons.iterdir()):
                init = entry / "__init__.py" if entry.is_dir() else entry
                if entry.name.startswith(("_", ".")) or not init.is_file() or init.suffix != ".py":
                    continue
                info = parse_bl_info(init) or {}
                ver = ".".join(map(str, info.get("version", ()))) if info else ""
                tools.append({
                    "id": f"bl.{entry.stem.lower()}",
                    "kind": "blender_addon",
                    "name": info.get("name", entry.stem),
                    "version": ver,
                    "origin": "user",
                    "path": str(entry),
                    "description": info.get("description", ""),
                    "docs": info.get("doc_url") or info.get("wiki_url") or "",
                    "by": info.get("author", ""),
                    "signature": sig(init.read_bytes()),
                })
        ext_root = cfg / "extensions"
        if ext_root.is_dir():
            for manifest in sorted(ext_root.glob("*/*/blender_manifest.toml")):
                raw = manifest.read_bytes()
                m = {}
                if tomllib:
                    try:
                        m = tomllib.loads(raw.decode("utf-8", errors="replace"))
                    except tomllib.TOMLDecodeError:
                        m = {}
                ext_id = m.get("id") or manifest.parent.name
                tools.append({
                    "id": f"blx.{ext_id.lower()}",
                    "kind": "blender_extension",
                    "name": m.get("name", ext_id),
                    "version": str(m.get("version", "")),
                    "origin": manifest.parent.parent.name,  # extension repository
                    "path": str(manifest.parent),
                    "description": m.get("tagline", ""),
                    "docs": m.get("website", ""),
                    "by": m.get("maintainer", ""),
                    "signature": sig(raw),
                })
    return tools


def scan_mcp(mcp_files):
    tools = []
    for f in map(Path, mcp_files):
        if not f.is_file():
            continue
        try:
            servers = read_json_loose(f).get("mcpServers", {})
        except ValueError:
            continue
        for name, conf in servers.items():
            blob = json.dumps(conf, sort_keys=True).encode()
            tools.append({
                "id": f"mcp.{name.lower()}",
                "kind": "mcp_server",
                "name": name,
                "version": "",
                "origin": str(f),
                "path": conf.get("command") or conf.get("url", ""),
                "description": "",
                "docs": "",
                "by": "",
                "signature": sig(blob),
            })
    return tools


def scan_clis(names):
    tools = []
    for n in names:
        p = shutil.which(n)
        if p:
            tools.append({"id": f"cli.{n.lower()}", "kind": "cli", "name": n, "version": "",
                          "origin": "path", "path": p, "description": "", "docs": "", "by": "",
                          "signature": sig(p.encode())})
    return tools


def scan_libs(lib_dirs):
    tools = []
    for d in map(Path, lib_dirs):
        if not d.is_dir():
            continue
        names = sorted(p.name for p in d.iterdir())[:500]
        tools.append({"id": f"lib.{d.name.lower()}", "kind": "asset_library", "name": d.name,
                      "version": "", "origin": "library", "path": str(d),
                      "description": f"{len(names)} top-level entries", "docs": "", "by": "",
                      "signature": sig("\n".join(names).encode())})
    return tools


def load_manifest(path):
    p = Path(path) if path else None
    if p and p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"machine": None, "tools": {}}


def diff(scan_tools, manifest):
    old = manifest.get("tools", {})
    out = {"new": [], "changed": [], "undocumented": [], "unchanged": [], "missing": []}
    seen = set()
    for t in scan_tools:
        seen.add(t["id"])
        prev = old.get(t["id"])
        if prev is None or prev.get("status") == "missing":
            out["new"].append(t["id"])
        elif prev.get("signature") != t["signature"]:
            out["changed"].append(t["id"])
        elif not prev.get("doc_file"):
            out["undocumented"].append(t["id"])
        else:
            out["unchanged"].append(t["id"])
    out["missing"] = sorted(i for i, v in old.items() if i not in seen and v.get("status") != "missing")
    return out


def update_manifest(manifest_path, scan, machine):
    manifest = load_manifest(manifest_path)
    old = manifest.get("tools", {})
    tools = {}
    for t in scan["tools"]:
        prev = old.get(t["id"], {})
        same = prev.get("signature") == t["signature"]
        entry = {k: t[k] for k in ("kind", "name", "version", "origin", "path", "signature")}
        entry["status"] = "present"
        entry["doc_file"] = prev.get("doc_file") if same else None
        entry["researched"] = prev.get("researched") if same else None
        entry["first_seen"] = prev.get("first_seen") or scan["scanned_at"]
        tools[t["id"]] = entry
    for i, v in old.items():
        if i not in tools:
            tools[i] = dict(v, status="missing")
    manifest.update({"machine": machine, "scanned_at": scan["scanned_at"], "tools": tools})
    Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
    Path(manifest_path).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--machine", required=True)
    ap.add_argument("--ue-root", action="append", default=[])
    ap.add_argument("--uproject")
    ap.add_argument("--all-engine", action="store_true", help="include every engine plugin")
    ap.add_argument("--blender-config", action="append", default=[])
    ap.add_argument("--mcp-file", action="append", default=[".mcp.json"])
    ap.add_argument("--asset-lib", action="append", default=[], help="asset library folder")
    ap.add_argument("--cli", action="append", default=None)
    ap.add_argument("--manifest")
    ap.add_argument("--out")
    ap.add_argument("--update-manifest", metavar="SCAN_JSON", help="merge a scan into the manifest")
    ap.add_argument("--mark", metavar="TOOL_ID", help="record a written instruction file")
    ap.add_argument("--doc")
    a = ap.parse_args()

    if a.mark:
        if not (a.manifest and a.doc):
            ap.error("--mark needs --manifest and --doc")
        m = load_manifest(a.manifest)
        if a.mark not in m.get("tools", {}):
            ap.error(f"{a.mark} is not in the manifest; run --update-manifest first")
        m["tools"][a.mark].update(doc_file=a.doc, researched=now()[:10])
        Path(a.manifest).write_text(json.dumps(m, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"marked {a.mark}")
        return
    if a.update_manifest:
        if not a.manifest:
            ap.error("--update-manifest needs --manifest")
        scan = json.loads(Path(a.update_manifest).read_text(encoding="utf-8"))
        m = update_manifest(a.manifest, scan, a.machine)
        print(f"manifest has {len(m['tools'])} tools")
        return

    tools = (scan_unreal(a.ue_root, a.uproject, a.all_engine) + scan_blender(a.blender_config)
             + scan_mcp(a.mcp_file) + scan_clis(a.cli or DEFAULT_CLIS) + scan_libs(a.asset_lib))
    seen, unique = set(), []
    for t in tools:  # first hit wins, e.g. a project plugin shadowing an engine one
        if t["id"] not in seen:
            seen.add(t["id"])
            unique.append(t)
    result = {"machine": a.machine, "scanned_at": now(), "tools": unique,
              "diff": diff(unique, load_manifest(a.manifest))}
    text = json.dumps(result, indent=2)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text + "\n", encoding="utf-8")
        d = result["diff"]
        print(f"{len(unique)} tools: {len(d['new'])} new, {len(d['changed'])} changed, "
              f"{len(d['undocumented'])} undocumented, {len(d['unchanged'])} unchanged, "
              f"{len(d['missing'])} missing -> {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
