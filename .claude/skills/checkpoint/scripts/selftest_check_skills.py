"""Self-test for check_skills.py: builds fixture repos in a temp folder and checks the errors, warnings and exit codes.

    python .claude/skills/checkpoint/scripts/selftest_check_skills.py

Ends with CHECK_SKILLS SELFTEST OK, or FAILED and exit 1. Plain Python, stdlib only.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("check_skills", os.path.join(HERE, "check_skills.py"))
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("FAIL", msg)


def make(files):
    """A fixture repo: {relative path: text}. Returns its root."""
    root = tempfile.mkdtemp(prefix="check_skills_")
    for rel, text in files.items():
        p = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    return root


def skill(name, desc='description: A fine skill that does one thing.', body="Body text.\n", extra_fm="", crlf=False, nm=None):
    text = f"---\nname: {nm or name}\n{desc}\n{extra_fm}---\n\n{body}"
    return text.replace("\n", "\r\n") if crlf else text


def run(files):
    errors, warns = cs.lint(make(files))
    return errors, warns


def has(items, *needles):
    return any(all(n in i for n in needles) for i in items)


S = ".claude/skills/"

# ---- a clean repo gives nothing ---------------------------------------------------------------------------------------------------------
e, w = run({
    S + "good/SKILL.md": skill("good", body="See references/guide.md and scripts/tool.py and templates/t.md.\n", crlf=True),
    S + "good/references/guide.md": "guide\n", S + "good/templates/t.md": "t\n", S + "good/scripts/tool.py": "import helper\nprint(1)\n",
    S + "good/scripts/helper.py": "X = 1\n", S + "good/scripts/selftest_tool.py": "print('t')\n", S + "good/scripts/check_tool.py": "print('c')\n",
    ".claude/agents/worker.md": "---\nname: worker\ndescription: Does work.\nmodel: opus\nskills:\n  - good\n---\nBody\n",
})
check(not e and not w, f"clean repo should be silent, got {e} {w}")

# ---- frontmatter errors -----------------------------------------------------------------------------------------------------------------
cases = {
    "no-fm": ("# Title only\n", "frontmatter missing"),
    "open-fm": ("---\nname: open-fm\ndescription: x\n\nBody\n", "not closed"),
    "colon": (skill("colon", "description: Split a blockout. It covers: the brief and the join."), "unquoted ': '"),
    "trailing-colon": (skill("trailing-colon", "description: Covers the following:"), "unquoted ': '"),
    "colon-cont": (skill("colon-cont", "description: First line of text\n  and a second with a: colon in it"), "unquoted ': '"),
    "at-start": (skill("at-start", "description: @mention first"), "cannot start with"),
    "open-quote": (skill("open-quote", 'description: "never closed'), "quote never closed"),
    "after-quote": (skill("after-quote", 'description: "closed" and more text'), "text after the closing quote"),
    "bad-line": (skill("bad-line", "description: fine\nthis line is not a key"), "not `key: value`"),
    "dup-key": (skill("dup-key", "description: one\ndescription: two"), "duplicate key"),
    "no-desc": ("---\nname: no-desc\nmodel: x\n---\nBody\n", "no description"),
    "empty-desc": ("---\nname: empty-desc\ndescription:\n---\nBody\n", "no description"),
    "empty-quoted": ('---\nname: empty-quoted\ndescription: ""\n---\nBody\n', "no description"),
    "wrong-name": (skill("wrong-name", nm="other-name"), "does not match"),
    "no-name": ("---\ndescription: fine\n---\nBody\n", "no name"),
}
for folder, (text, needle) in cases.items():
    e, w = run({S + f"{folder}/SKILL.md": text})
    check(has(e, f"{folder}/SKILL.md", needle), f"{folder}: expected an error containing {needle!r}, got {e}")

# ---- values that must pass --------------------------------------------------------------------------------------------------------------
ok_descs = {
    "dq": 'description: "Split a blockout. It covers: the brief and the join."',
    "sq": "description: 'It covers: this, and it''s fine'",
    "folded": "description: >\n  A folded description that covers: a colon,\n  over two lines.",
    "literal": "description: |\n  Literal with: colon",
    "comment": "description: Fine text # a comment: here",
    "midcolon": "description: Time is 10:30 and the ratio is 3:1 (no space after the colon)",
    "flow": "description: [one, two]",
    "dq-comment": 'description: "quoted" # note',
}
for folder, desc in ok_descs.items():
    e, w = run({S + f"{folder}/SKILL.md": skill(folder, desc)})
    check(not e, f"{folder}: should pass, got {e}")
e, w = run({S + "lists/SKILL.md": skill("lists", extra_fm="allowed-tools:\n  - Read\n- Edit\n")})
check(not e, f"list items should pass: {e}")

# ---- agents -----------------------------------------------------------------------------------------------------------------------------
e, w = run({".claude/agents/a.md": "---\nname: b\ndescription: ok\n---\nx\n"})
check(has(e, "agents/a.md", "does not match"), f"agent name mismatch: {e}")
e, w = run({".claude/agents/c.md": "---\nname: c\ndescription: Does it: badly\n---\nx\n"})
check(has(e, "agents/c.md", "unquoted"), f"agent colon: {e}")

# ---- python syntax ----------------------------------------------------------------------------------------------------------------------
e, w = run({S + "py/SKILL.md": skill("py", body="scripts/ok.py scripts/broken.py deep/x.py\n"), S + "py/scripts/ok.py": "x = 1\n",
            S + "py/scripts/broken.py": "def f(:\n  pass\n", S + "py/deep/x.py": "print(\n"})
check(has(e, "py/scripts/broken.py", "does not parse"), f"syntax error in scripts/ not reported: {e}")
check(has(e, "py/deep/x.py", "does not parse"), f"syntax error outside scripts/ not reported: {e}")
check(not has(e, "py/scripts/ok.py"), f"a good .py was reported: {e}")

# ---- unlinked supporting files ----------------------------------------------------------------------------------------------------------
e, w = run({
    S + "orph/SKILL.md": skill("orph", body="Use references/used.md only.\n"),
    S + "orph/references/used.md": "mentions chain.md\n", S + "orph/references/chain.md": "linked from another reference\n",
    S + "orph/references/lonely.md": "nobody links me\n", S + "orph/templates/lonely_t.md": "nope\n",
    S + "orph/scripts/lonely.py": "x = 1\n", S + "orph/scripts/selftest_lonely.py": "x = 1\n", S + "orph/scripts/check_lonely.py": "x = 1\n",
    S + "orph/scripts/only_selftest_uses.py": "x = 1\n", S + "orph/scripts/selftest_other.py": "import only_selftest_uses\n",
    S + "orph/notes/extra.md": "outside the three folders, not checked\n",
})
check(not e, f"orphans are warnings, not errors: {e}")
for f in ("references/lonely.md", "templates/lonely_t.md", "scripts/lonely.py", "scripts/only_selftest_uses.py"):
    check(has(w, "orph/" + f, "links"), f"expected an unlinked warning for {f}: {w}")
for f in ("references/used.md", "references/chain.md", "selftest_lonely", "check_lonely", "selftest_other", "notes/extra.md"):
    check(not has(w, f), f"{f} should not be warned about: {w}")

# ---- word count and the third-party exemption -------------------------------------------------------------------------------------------
long_body = "word " * 2600
credits = ("# Credits\n\n## Skills adapted\n\n| Skill | Based on |\n| --- | --- |\n| `adapted-big` | x |\n\n"
           "## Installed third-party skills\n\n| Skill | Upstream |\n| --- | --- |\n| `upstream-big`, `other` | y |\n\n## Installed tools\n\n| `tool-big` | z |\n")
e, w = run({S + "own-big/SKILL.md": skill("own-big", body=long_body), S + "upstream-big/SKILL.md": skill("upstream-big", body=long_body),
            S + "adapted-big/SKILL.md": skill("adapted-big", body=long_body), S + "small/SKILL.md": skill("small", body="word " * 2400),
            S + "CREDITS.md": credits})
check(has(w, "own-big", "2600 words"), f"over-long skill not warned: {w}")
check(has(w, "adapted-big", "words"), f"adapted skills are not exempt: {w}")
check(not has(w, "upstream-big"), f"third-party skill should be exempt: {w}")
check(not has(w, "small"), f"2400 words should pass: {w}")
check(not e, f"word warnings are not errors: {e}")
check(not has(w, "frontmatter") and not any(len(x.split()) > 0 and "CREDITS" in x for x in w), f"CREDITS.md itself linted: {w}")

# ---- command line: exit codes, root argument ----------------------------------------------------------------------------------------------
script = os.path.join(HERE, "check_skills.py")


def cli(files):
    root = make(files)
    r = subprocess.run([sys.executable, script, root], capture_output=True, text=True)
    return r.returncode, r.stdout


code, out = cli({S + "bad/SKILL.md": skill("bad", "description: a: b")})
check(code == 1 and "ERROR" in out and "1 error(s)" in out, f"cli with an error should exit 1: {code} {out}")
code, out = cli({S + "fine/SKILL.md": skill("fine"), S + "fine/references/orphan.md": "x\n"})
check(code == 0 and "WARN" in out and "0 error(s), 1 warning(s)" in out, f"cli with only warnings should exit 0: {code} {out}")
code, out = cli({})
check(code == 0 and "0 error(s), 0 warning(s)" in out, f"an empty root is fine: {code} {out}")

print("CHECK_SKILLS SELFTEST", "FAILED: %d" % len(fails) if fails else "OK")
sys.exit(1 if fails else 0)
