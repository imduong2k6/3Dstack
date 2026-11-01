"""Lint the pipeline's skills and agents before a pipeline commit. Plain Python, stdlib only.

    python .claude/skills/checkpoint/scripts/check_skills.py [root]          root defaults to the repo this file sits in

Walks <root>/.claude/skills/*/SKILL.md and <root>/.claude/agents/*.md. Prints `ERROR <file>: ...` and `WARN <file>: ...`, then a summary.
Exit 1 when there is any error, 0 otherwise (warnings never fail).

Errors
  - frontmatter missing, not closed, or not readable as YAML: a line that is not `key: value`, a duplicate key, a quoted value with text after
    the closing quote, or a plain (unquoted) value that holds `: ` or ends in `:` or starts with a YAML indicator (@ ` % * & !). That is what
    makes a skill's description vanish from the skill list, leaving only its name. The fix is quotes around the value.
  - no description, or an empty one
  - `name` missing, or not the folder name (skills) or the file name without `.md` (agents)
  - a `.py` file anywhere under a skill that `ast.parse` rejects
Warnings
  - a file under the skill's references/, templates/ or scripts/ that no other file in the skill mentions by its file name (selftest_* and
    check_* scripts are exempt, and do not count as the mention; a .py also counts as used when another .py imports it)
  - a SKILL.md body over 2,500 words, except for the skills listed in CREDITS.md under "Installed third-party skills" (their size is upstream's)

The YAML check is a subset reader, not PyYAML: it knows plain, quoted, flow (`[..]`, `{..}`) and block (`|`, `>`) values and indented
continuation or list lines, which is all these files use.
"""
import ast
import os
import re
import sys

WORD_LIMIT = 2500
SUPPORT_DIRS = ("references", "templates", "scripts")
TEXT_EXT = (".md", ".py", ".json", ".yaml", ".yml", ".txt", ".js", ".sh", ".html", ".toml", ".csv")
BAD_START = "@`%*&!"
KEY_RE = re.compile(r"^([A-Za-z_][\w.-]*)\s*:(?:\s+(.*)|)$")


def split_frontmatter(text):
    """(frontmatter lines, body, problem). problem is None when the block is there and closed."""
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return None, text, "frontmatter missing (the file does not start with a --- line)"
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return lines[1:i], "\n".join(lines[i + 1:]), None
    return None, text, "frontmatter not closed (no second --- line)"


def _quoted_problem(value):
    """Problem text for a value that starts with a quote, else None. Accepts a quoted string followed only by a comment."""
    q, i = value[0], 1
    while i < len(value):
        c = value[i]
        if q == '"' and c == "\\":
            i += 2
            continue
        if c == q:
            if q == "'" and value[i + 1:i + 2] == "'":
                i += 2
                continue
            rest = value[i + 1:].strip()
            return None if not rest or rest.startswith("#") else f"text after the closing quote: {rest[:30]!r}"
        i += 1
    return "quote never closed"


def parse_frontmatter(lines):
    """({key: value text}, [problems]). Value text joins continuation lines with a space; block scalars keep their words."""
    fm, problems, key, i = {}, [], None, 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[0] in " \t" or raw.startswith("- "):
            if key is None:
                problems.append(f"line {i}: indented text before any key")
            else:
                fm[key]["cont"].append(raw.strip())
            continue
        m = KEY_RE.match(raw.rstrip())
        if not m:
            problems.append(f"line {i}: not `key: value` ({raw.strip()[:40]!r})")
            key = None
            continue
        key = m.group(1)
        if key in fm:
            problems.append(f"line {i}: duplicate key {key!r}")
        fm[key] = {"value": (m.group(2) or "").strip(), "cont": [], "line": i}
    out = {}
    for k, d in fm.items():
        v, cont = d["value"], d["cont"]
        block = v[:1] in ("|", ">")
        if not v and not cont:
            out[k] = ""
            continue
        if block:
            out[k] = " ".join(cont)
            continue
        full = " ".join([v] + cont) if v else " ".join(cont)
        first = full[:1]
        if first in ("'", '"'):
            p = _quoted_problem(full)
            if p:
                problems.append(f"{k}: {p}")
        elif first in "[{":
            if full.count("[") != full.count("]") or full.count("{") != full.count("}"):
                problems.append(f"{k}: brackets do not balance")
        elif not v:
            pass  # a list given as `- item` lines
        else:
            plain = re.split(r"\s#", full)[0]
            if first in BAD_START:
                problems.append(f"{k}: a plain value cannot start with {first!r}; put it in quotes")
            elif ": " in plain or plain.rstrip().endswith(":"):
                problems.append(f"{k}: unquoted ': ' in a plain value (YAML reads it as a nested mapping); put the whole value in quotes")
        out[k] = full.strip("'\"") if first in ("'", '"') else full
    return out, problems


def third_party(root):
    """Skill folder names listed in CREDITS.md under 'Installed third-party skills' (any backticked name in a table row's first cell)."""
    path = os.path.join(root, ".claude", "skills", "CREDITS.md")
    names, on = set(), False
    if not os.path.isfile(path):
        return names
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("#"):
            on = "installed third-party skills" in line.lower()
        elif on and line.startswith("|"):
            cells = line.split("|")
            if len(cells) > 1:
                names.update(re.findall(r"`([^`]+)`", cells[1]))
    return names


def _files(skill_dir):
    for d, dirs, fs in os.walk(skill_dir):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", ".git", "node_modules")]
        for f in fs:
            yield os.path.join(d, f)


def lint_skill(skill_dir, rel, exempt_words, errors, warns):
    folder = os.path.basename(skill_dir)
    md = os.path.join(skill_dir, "SKILL.md")
    text = open(md, encoding="utf-8", errors="replace").read()
    body = lint_frontmatter(md, text, folder, errors, rel)
    if body is not None and len(body.split()) > WORD_LIMIT and folder not in exempt_words:
        warns.append(f"{rel(md)}: body is {len(body.split())} words (limit {WORD_LIMIT}); move detail into references/")
    texts = {}
    for p in _files(skill_dir):
        if p.endswith(".py"):
            try:
                ast.parse(open(p, encoding="utf-8", errors="replace").read(), filename=p)
            except SyntaxError as e:
                errors.append(f"{rel(p)}: does not parse: {e.msg} (line {e.lineno})")
        if p.lower().endswith(TEXT_EXT):
            texts[p] = open(p, encoding="utf-8", errors="replace").read()
    for p in sorted(texts):
        parts = os.path.relpath(p, skill_dir).replace(os.sep, "/").split("/")
        name = parts[-1]
        if parts[0] not in SUPPORT_DIRS or len(parts) < 2 or name.startswith(("selftest_", "check_")):
            continue
        stem = name[:-3] if name.endswith(".py") else None
        for q, t in texts.items():
            qn = os.path.basename(q)
            if q == p or qn.startswith(("selftest_", "check_")):
                continue
            if name in t or (stem and qn.endswith(".py") and re.search(rf"^\s*(?:import|from)\s+{re.escape(stem)}\b", t, re.M)):
                break
        else:
            warns.append(f"{rel(p)}: nothing in the skill links this file")


def lint_frontmatter(path, text, expected_name, errors, rel):
    """Add frontmatter errors for one file; return its body, or None when the frontmatter is unreadable."""
    fm_lines, body, problem = split_frontmatter(text)
    if problem:
        errors.append(f"{rel(path)}: {problem}")
        return None
    fm, problems = parse_frontmatter(fm_lines)
    errors.extend(f"{rel(path)}: frontmatter {p}" for p in problems)
    if not fm.get("description", "").strip():
        errors.append(f"{rel(path)}: no description")
    name = fm.get("name", "").strip()
    if not name:
        errors.append(f"{rel(path)}: no name (expected {expected_name!r})")
    elif name != expected_name:
        errors.append(f"{rel(path)}: name {name!r} does not match {expected_name!r}")
    return body


def lint(root):
    """(errors, warnings) for the repo at root."""
    errors, warns = [], []
    skills = os.path.join(root, ".claude", "skills")
    agents = os.path.join(root, ".claude", "agents")
    exempt = third_party(root)
    rel = lambda p: os.path.relpath(p, root).replace(os.sep, "/")
    if os.path.isdir(skills):
        for name in sorted(os.listdir(skills)):
            d = os.path.join(skills, name)
            if os.path.isdir(d) and os.path.isfile(os.path.join(d, "SKILL.md")):
                lint_skill(d, rel, exempt, errors, warns)
    if os.path.isdir(agents):
        for f in sorted(os.listdir(agents)):
            if f.endswith(".md"):
                p = os.path.join(agents, f)
                lint_frontmatter(p, open(p, encoding="utf-8", errors="replace").read(), f[:-3], errors, rel)
    return errors, warns


def main(argv):
    root = os.path.abspath(argv[0]) if argv else os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
    errors, warns = lint(root)
    for e in errors:
        print("ERROR", e)
    for w in warns:
        print("WARN ", w)
    print(f"check_skills: {len(errors)} error(s), {len(warns)} warning(s) in {root}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
