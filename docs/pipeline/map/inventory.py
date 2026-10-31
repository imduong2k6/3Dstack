"""Reads the repo's skills and agents into inventory.json for the map, and prints a digest."""
import ast, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "inventory.json")


def front(text):
    m = re.match(r"---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        return {}, text
    out, key = {}, None
    for line in m.group(1).splitlines():
        kv = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if kv:
            key = kv.group(1)
            out[key] = kv.group(2).strip().strip('"')
            if not out[key]:
                out[key] = []
        elif line.strip().startswith("- ") and key and isinstance(out.get(key), list):
            out[key].append(line.strip()[2:])
    return out, text[m.end():]


def doc_line(path):
    try:
        src = open(path, encoding="utf8", errors="replace").read()
    except OSError:
        return ""
    if path.endswith(".py"):
        try:
            d = ast.get_docstring(ast.parse(src))
        except SyntaxError:
            d = None
        if d:
            return d.strip().splitlines()[0]
    for line in src.splitlines()[:12]:
        s = line.strip().lstrip("#/ ").strip()
        if s and not s.startswith("!"):
            return s
    return ""


skills = []
for d in sorted(glob.glob(os.path.join(ROOT, ".claude", "skills", "*", ""))):
    name = os.path.basename(d.rstrip("\\/"))
    p = os.path.join(d, "SKILL.md")
    if not os.path.exists(p):
        continue
    t = open(p, encoding="utf8").read()
    fm, _ = front(t)
    files = {"scripts": [], "references": [], "templates": []}
    for sub, key in (("scripts", "scripts"), ("assets", "templates"), ("templates", "templates"), ("references", "references")):
        for f in sorted(glob.glob(os.path.join(d, sub, "**", "*"), recursive=True)):
            if os.path.isdir(f) or "__pycache__" in f:
                continue
            rel = os.path.relpath(f, os.path.join(d, sub)).replace("\\", "/")
            item = {"name": rel, "words": len(open(f, encoding="utf8", errors="replace").read().split())}
            if f.endswith((".py", ".sh", ".js", ".ps1")):
                item["doc"] = doc_line(f)[:170]
                files["scripts" if key == "scripts" else "templates"].append(item)
            else:
                files[key].append(item)
    skills.append({"name": name, "desc": str(fm.get("description", "")), "words": len(t.split()), **files,
                   "licensed": os.path.exists(os.path.join(d, "LICENSE"))})

agents = []
for f in sorted(glob.glob(os.path.join(ROOT, ".claude", "agents", "*.md"))):
    t = open(f, encoding="utf8").read()
    fm, body = front(t)
    agents.append({"name": fm.get("name"), "model": fm.get("model"), "effort": fm.get("effort", "agent default"),
                   "skills": fm.get("skills", []), "disallowed": fm.get("disallowedTools", ""),
                   "desc": str(fm.get("description", "")), "words": len(t.split())})

json.dump({"skills": skills, "agents": agents}, open(OUT, "w", encoding="utf8"), indent=1)

for s in skills:
    print(f"\n## {s['name']} ({s['words']}w){' [licensed]' if s['licensed'] else ''}")
    print("  ", s["desc"][:140])
    if s["references"]:
        print("   refs:", ", ".join(r["name"] for r in s["references"]))
    if s["templates"]:
        print("   tmpl:", ", ".join(r["name"] for r in s["templates"]))
    for sc in s["scripts"]:
        print(f"   * {sc['name']}: {sc.get('doc','')[:110]}")
print("\nTOTAL words", sum(s["words"] for s in skills), "skills", len(skills), "scripts", sum(len(s["scripts"]) for s in skills))
