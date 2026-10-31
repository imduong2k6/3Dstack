"""Build the Pipeline Map page from data.py, inventory.json, the roadmap report, the Skills Map labels and the local board snapshot."""
import glob, html, json, os, re, subprocess
import blocks as B
import data as D

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
inv = json.load(open(os.path.join(HERE, "inventory.json"), encoding="utf8"))
SK = {s["name"]: s for s in inv["skills"]}
AG = inv["agents"]


def frozen(name):
    return json.load(open(os.path.join(HERE, name), encoding="utf8"))


# Frozen once from sources outside the repo: the Skills Map labels, your board answers, the audit report's roadmap rows.
LABEL = {r[0]: r for r in frozen("labels.json")}
BOARD = frozen("board.json")
ROAD = frozen("roadmap.json")
assert set(LABEL) == set(SK), f"add or remove these skills in labels.json: {set(LABEL) ^ set(SK)}"


def e(s):
    return html.escape(str(s), quote=True)


def md_plain(s):
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = s.replace("**", "")
    return s


def inline(s):
    """Plain text with `code` spans and file-ish names set in mono."""
    parts = re.split(r"`([^`]+)`", s)
    out = []
    for i, p in enumerate(parts):
        out.append(f"<code>{e(p)}</code>" if i % 2 else e(p))
    return "".join(out)


FILE_RE = re.compile(r"(?<![\w/.-])([\w<>./-]+\.(?:yaml|json|md|py|png))(?![\w])")


def tx(s):
    return FILE_RE.sub(r"<code>\1</code>", e(s))


def cbtn(id_, title):
    return f'<button type="button" class="cb" data-id="{e(id_)}" data-title="{e(title)}" aria-label="Comment on {e(title)}"><span class="cb-t">Comment</span></button>'


def badge(st):
    return f'<span class="st st-{st}">{e(D.STATUS[st][0])}</span>'


def chip(name):
    if name in SK:
        return f'<button type="button" class="chip" data-go="skills" data-jump="skill-{name}">{e(name)}</button>'
    return f'<code class="file">{e(name)}</code>'


def rchip(i):
    t = "decisions" if i.startswith("D") else "roadmap"
    return f'<button type="button" class="chip rc" data-go="{t}" data-jump="r-{i}">{e(i)}</button>'


def table(head, rows, cls=""):
    th = "".join(f"<th scope=\"col\">{h}</th>" for h in head)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


# ------------------------------------------------------------------ SVG helpers
def walk_blocks():
    for g in B.GROUPS:
        for b in g["items"]:
            yield b
            yield from b.get("subs", [])


TIPS = {"bl-" + b["id"]: b["does"] for b in walk_blocks()}


def tip(jump):
    """Hover text for a map box that points at a block."""
    return f"<title>{e(TIPS[jump])}</title>" if jump in TIPS else ""


class Fig:
    def __init__(self, w, h, label, mid):
        self.w, self.h, self.label, self.mid, self.o = w, h, label, mid, []

    def box(self, x, y, w, h, t, sub="", go=None, jump=None, cls="", ident=""):
        attrs = ""
        if go:
            attrs = f' class="n {cls}" data-go="{go}"' + (f' data-jump="{jump}"' if jump else "") + f' tabindex="0" role="link" aria-label="{e(t)}"'
        else:
            attrs = f' class="n nn {cls}"'
        s = [f"<g{attrs}>", tip(jump), f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3"/>']
        tx_ = x + 10
        if ident:
            s.append(f'<text x="{x + w - 8}" y="{y + 15}" class="id" text-anchor="end">{e(ident)}</text>')
        lines = t if isinstance(t, list) else [t]
        yy = y + 20
        for ln in lines:
            s.append(f'<text x="{tx_}" y="{yy}" class="t">{e(ln)}</text>')
            yy += 16
        subs = sub if isinstance(sub, list) else ([sub] if sub else [])
        for ln in subs:
            s.append(f'<text x="{tx_}" y="{yy}" class="s">{e(ln)}</text>')
            yy += 14
        s.append("</g>")
        self.o.append("".join(s))

    def gate(self, cx, cy, t, go="stages", jump=None, cls="", r=24):
        pts = f"{cx},{cy - r} {cx + r + 6},{cy} {cx},{cy + r} {cx - r - 6},{cy}"
        j = f' data-jump="{jump}"' if jump else ""
        self.o.append(f'<g class="g {cls}" data-go="{go}"{j} tabindex="0" role="link" aria-label="Gate {e(t)}">{tip(jump)}<polygon points="{pts}"/>'
                      f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" class="gt">{e(t)}</text></g>')

    def arrow(self, pts, label="", lx=None, ly=None, cls="", anchor="middle"):
        d = "M" + " L".join(f"{x} {y}" for x, y in pts)
        self.o.append(f'<path d="{d}" class="a {cls}" marker-end="url(#{self.mid}-ah)"/>')
        if label:
            self.o.append(f'<text x="{lx}" y="{ly}" class="al" text-anchor="{anchor}">{e(label)}</text>')

    def band(self, x, y, w, h, t, cls=""):
        self.o.append(f'<g class="band {cls}"><rect x="{x}" y="{y}" width="{w}" height="{h}"/><text x="{x + 10}" y="{y + 17}" class="bt">{e(t)}</text></g>')

    def text(self, x, y, t, cls="al", anchor="start"):
        self.o.append(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{e(t)}</text>')

    def svg(self, cap, minw=None):
        defs = (f'<defs><marker id="{self.mid}-ah" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                f'<path d="M0 0 L8 4 L0 8 z" fill="currentColor"/></marker>'
                f'<pattern id="{self.mid}-grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0 L0 0 0 40" fill="none" stroke="currentColor" stroke-width=".5" opacity=".1"/></pattern></defs>')
        mw = minw or self.w
        return (f'<figure class="fig"><div class="figscroll"><svg viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{e(self.label)}" style="min-width:{mw}px">'
                f'{defs}<rect width="{self.w}" height="{self.h}" fill="url(#{self.mid}-grid)"/>{"".join(self.o)}</svg></div>'
                f'<figcaption>{cap}</figcaption></figure>')


def review_fig():
    f = Fig(1040, 430, "One review round. The worker's batch goes through lint, which can stop the capture. Reviewers read the same captures in parallel. The manager merges their files into one fix list, the clerk posts it, and you decide. A pass moves on, a fix runs another round.", "r")
    y = 50
    f.box(20, y, 130, 66, ["Worker's", "last batch"], "live editor", cls="st-real")
    f.box(190, y, 130, 66, ["scene-lint"], ["lint.json, 23 checks", "--baseline: what's new"], "scripts", "lint-table", "st-real")
    f.arrow([(150, y + 33), (188, y + 33)], "writes", 169, y + 26)
    f.arrow([(255, y + 66), (255, y + 92), (120, y + 92), (120, y + 68)], "blocker: no capture", 190, y + 108, "bad")
    f.box(360, y, 120, 66, ["Capture set"], ["review cameras, stats"], cls="st-real")
    f.arrow([(320, y + 33), (358, y + 33)], "clean", 339, y + 26)
    # reviewers
    ys = [14, 56, 98, 140, 188]
    names = ["Scale and walkability", "Construction logic", "Light and values", "Names, stats, budgets"]
    for i, (yy, n) in enumerate(zip(ys, names)):
        f.box(530, yy, 190, 36, n, "", "map", f"bl-R4.{i + 1}", "st-real")
        f.arrow([(480, y + 33), (505, y + 33), (505, yy + 18), (528, yy + 18)])
    f.box(530, ys[4], 190, 36, "Art Director: up to 5 notes", "", "map", "bl-R4.5", "st-real")
    f.arrow([(480, y + 33), (505, y + 33), (505, ys[4] + 18), (528, ys[4] + 18)])
    f.text(625, 244, "read-only, one file each", "al", "middle")
    # merge
    f.box(770, 64, 120, 80, ["Manager", "merges"], ["review.md", "fix_issues.json"], cls="st-real")
    for yy in ys:
        f.arrow([(720, yy + 18), (745, yy + 18), (745, 104), (768, 104)])
    f.box(920, 64, 100, 80, ["Clerk"], ["BEFORE pairs", "board post"], "agents", "agent-pipeline-clerk", "st-real")
    f.arrow([(890, 104), (918, 104)])
    f.box(920, 200, 100, 56, ["You"], ["Do it, Later, Skip"], cls="plain")
    f.arrow([(970, 144), (970, 198)], "posted", 1000, 175)
    # outcomes
    f.gate(970, 330, "PASS?", go="stages", jump="st-gates")
    f.arrow([(970, 256), (970, 304)])
    f.box(726, 300, 154, 60, ["Next phase or stage"], "needs PASS and your yes", cls="plain")
    f.arrow([(936, 330), (882, 330)], "yes", 910, 322)
    f.arrow([(970, 356), (970, 400), (70, 400), (70, 118)], "no: one fix list goes to the worker or to fix lanes, AFTER pairs follow · after max_rounds it stops and asks you · failed twice for one reason: research first", 520, 416, "bad")
    return f.svg("One round, as it runs today. Today round 2 only rechecks the fix list and what is new, so an unfixed major can drop out: that is Q2 and <button type=\"button\" class=\"lnk\" data-go=\"decisions\" data-jump=\"r-D4\">D4</button>. The merge and the two middle steps are what S4 would turn into data.", 940)


def lane_fig():
    f = Fig(1040, 400, "Lanes work on copies outside the live editor. Fix lanes write patches that pass a merge test before the one live worker replays them. Blockout lanes freeze part files that a headless join combines.", "l")
    f.band(20, 16, 760, 368, "Headless, on copies · many agents at once")
    f.band(800, 16, 220, 368, "Live editor · one writer", "lane-l")
    f.text(40, 58, "Fix lanes: 10 or more items in 2 or more areas", "bt")
    f.box(40, 70, 110, 60, ["Gate copy"], ["frozen"], cls="plain")
    for yy, t in zip((64, 104, 144), ("Modeler, area 1", "Modeler, area 2", "Modeler, area 3")):
        f.box(190, yy, 150, 34, t, "", "agents", "agent-modeler", "st-real")
        f.arrow([(150, 100), (170, 100), (170, yy + 17), (188, yy + 17)])
        f.arrow([(340, yy + 17), (375, yy + 17), (375, 100), (398, 100)])
    f.text(265, 196, "patches.py, repeat test on a copy", "al", "middle")
    f.box(400, 66, 170, 68, ["Merge test"], ["replays all on a fresh copy", "refuses shared objects"], cls="st-real")
    f.box(610, 66, 150, 68, ["Batch lint"], ["only what's new since", "the round's lint.json"], "scripts", "lint-table", "st-real")
    f.arrow([(570, 100), (608, 100)])
    f.box(830, 66, 170, 68, ["Worker replays"], ["only patches that passed"], "agents", "agent-blender-worker", "st-real")
    f.arrow([(760, 100), (828, 100)], "tested", 795, 92)
    f.text(40, 244, "Blockout lanes: a big build split by area, never by trade", "bt")
    f.box(40, 256, 130, 70, ["Lane briefs"], ["owned prefix, seams,", "metrics, rows"], cls="plain")
    f.box(210, 256, 130, 70, ["Part .blend"], ["one per lane,", "manifest.json"], cls="st-real")
    f.box(380, 256, 130, 70, ["Freeze"], ["SHA-256 in manifest;", "edit means new freeze"], cls="st-real")
    f.box(550, 256, 210, 70, ["Join, one lane at a time"], ["integrate_parts.py on a copy,", "structure, then what hangs on it"], "scripts", "scr-lane-integration", "st-real")
    f.box(830, 256, 170, 70, ["Worker reopens"], ["final checks and captures"], "agents", "agent-blender-worker", "st-real")
    f.arrow([(170, 291), (208, 291)])
    f.arrow([(340, 291), (378, 291)])
    f.arrow([(510, 291), (548, 291)])
    f.arrow([(760, 291), (828, 291)], "result", 795, 283)
    f.text(910, 358, "Asset lane feeds in here too,", "al", "middle")
    f.text(910, 372, "between the worker's steps", "al", "middle")
    return f.svg("The boundary is the point: agents multiply on the left, and the live editor keeps one writer on the right. Inside the lanes about 75 % of the time still goes on hand-computed coordinates, which S1 and A1 go after.", 900)


def data_fig():
    f = Fig(1040, 470, "How plan files connect. Reference photos become the inventory and services files, the layout, and specs. Builders read them, and checks compare the scene back to them, producing the evidence reviewers read.", "d")
    for x, w, t in ((20, 180, "Sources"), (225, 200, "Plan files"), (450, 280, "Who builds from them"), (755, 265, "Who checks against them")):
        f.band(x, 12, w, 446, t)
    rows = [("Your prompt, images", 44), ("refs/index.yaml", 104), ("brief.yaml", 164), ("Research", 224)]
    for t, y in rows:
        f.box(32, y, 156, 40, t, "", cls="plain")
    plan = [("metrics.yaml", 44), ("inventory.yaml", 104), ("services.yaml", 164), ("layout.json", 224), ("kit/*.md, assets.yaml", 284), ("cameras, exposure, lights", 344), ("walk.json", 404)]
    for t, y in plan:
        f.box(237, y, 176, 40, t, "", "files", None, "st-real")
    b = [("Lane briefs: typed by hand", 44, "st-parts"), ("linear_runs.py: rows in, runs out", 164, "st-parts"), ("Blockout lanes: retype shapes", 224, "st-parts"), ("Modelers, Asset Tech", 284, "st-real"), ("Worker, capture.py", 344, "st-real")]
    for t, y, c in b:
        f.box(462, y, 256, 40, t, "", "scripts", None, c)
    k = [("check_inventory.py: counts", 104), ("check_layout.py", 224), ("check_spec.py, validate", 284), ("lint_blender.py: 23 checks", 344), ("visible_set.py: scope", 404)]
    for t, y in k:
        f.box(767, y, 241, 40, t, "", "scripts", None, "st-real")
    f.arrow([(188, 64), (235, 64)], "", cls="")
    f.arrow([(188, 124), (235, 124)])
    f.arrow([(188, 244), (212, 244), (212, 72), (235, 72)])
    f.arrow([(413, 64), (460, 64)], "cited", 437, 58)
    f.arrow([(413, 124), (440, 124), (440, 72), (460, 72)])
    f.arrow([(413, 184), (460, 184)], "rows", 437, 178)
    f.arrow([(413, 244), (460, 244)], "not read", 437, 238, "bad")
    f.arrow([(413, 304), (460, 304)])
    f.arrow([(413, 364), (460, 364)])
    f.arrow([(413, 124), (765, 124)], "counts tagged objects against rows", 590, 118)
    f.arrow([(718, 244), (765, 244)])
    f.arrow([(718, 304), (765, 304)])
    f.arrow([(718, 364), (765, 364)], "lint.json", 742, 358)
    f.arrow([(413, 424), (765, 424)], "sets what lint and reviewers look at", 590, 418)
    return f.svg("Red is the gap S5 and N1 close: <code>layout.json</code> holds the shapes, and blockout lanes retype them by hand. Amber builders are where about 75 % of lane time goes.", 900)


# ------------------------------------------------------------------ Node tree
GATE_IDS = {"G0", "G1", "G2", "K", "T", "G3"}
LOOP_GATES = {"G2", "K", "T", "P·", "L1"}


def leaf(kind, label, body):
    return f'<div class="leaf"><div class="lbox k-{kind}"><span class="lk">{label}</span>{body}</div></div>'


def leafs(b, links=""):
    """One explanation sub-node per thing the block does, checks, researches or writes."""
    out = [leaf("does", "Does", (f'<p class="who">{tx(b["who"])}</p>' if b.get("who") else "") + f'<p>{tx(b["does"])}</p>' + links)]
    for key, label in (("asks", "Asks you"), ("finds", "Researches"), ("checks", "Checks")):
        if b.get(key):
            out.append(leaf(key, label, "<ul>" + "".join(f"<li>{tx(x)}</li>" for x in b[key]) + "</ul>"))
    if b.get("writes"):
        out.append(leaf("writes", "Writes", '<div class="chips">' + "".join(f'<code class="file">{e(x)}</code>' for x in b["writes"]) + "</div>"))
    if b.get("fail"):
        out.append(leaf("fail", "If it fails", f'<p>{tx(b["fail"])}</p>'))
    if b.get("gap"):
        out.append(leaf("gap", "Known limit", f'<p>{tx(b["gap"])}</p>'))
    return f'<div class="leafs">{"".join(out)}</div>'


def col(b):
    i, t, st = b["id"], b["t"], b["status"]
    gate = i in GATE_IDS
    mark = (f'<svg class="gd" viewBox="0 0 46 30" aria-hidden="true"><polygon points="23,1 45,15 23,29 1,15"/><text x="23" y="19" text-anchor="middle">{e(i)}</text></svg>'
            if gate else f'<span class="iid">{e(i)}</span>')
    head = (f'<div class="sp sp-{st}{" gate" if gate else ""}" id="bl-{e(i)}">'
            f'<div class="sp-t">{mark}<span>{e(t)}</span></div>'
            f'<div class="sp-f">{badge(st)}{cbtn("block:" + i, i + " " + t)}'
            f'<button type="button" class="tg" aria-expanded="true" aria-label="Show or hide the sub-nodes of {e(i)}"></button></div></div>')
    links = []
    if i in LOOP_GATES:
        links.append('<button type="button" class="lnk" data-go="map" data-jump="bl-R1">Runs the review loop, R1 to R7</button>')
    if b["stage"]:
        links.append(f'<button type="button" class="lnk" data-go="stages" data-jump="st-{b["stage"]}">{"Gates table" if b["stage"] == "gates" else "Stage card"}</button>')
    lk = f'<p class="blinks">{" · ".join(links)}</p>' if links else ""
    kids = [f'<div class="kid">{leafs(b, lk)}</div>']
    for x in b.get("subs", []):
        kids.append(f'<div class="kid node" data-q="{e((x["id"] + " " + x["t"]).lower())}"><div class="snode" id="bl-{e(x["id"])}"><div class="sp-t"><span class="iid">{e(x["id"])}</span><span>{e(x["t"])}</span></div>'
                    f'{cbtn("block:" + x["id"], x["id"] + " " + x["t"])}</div>{leafs(x)}</div>')
    return f'<div class="col node" data-q="{e((i + " " + t).lower())}">{head}<div class="kids">{"".join(kids)}</div></div>'


def track(g, cls):
    label = e(g["title"]) + (f' <span>{e(g["note"])}</span>' if g.get("note") else "")
    return f'<div class="track {cls}"><p class="trk-l">{label}</p>{"".join(col(b) for b in g["items"])}</div>'


def tree_html():
    start, block, assets, level, finish, loop = B.GROUPS
    stop = ('<div class="col end"><div class="sp sp-plain"><div class="sp-t"><span>Pipeline stops</span></div><p class="sp-n">Textures, post FX and the LUT are yours</p></div></div>')
    root = ('<div class="col root"><div class="sp sp-plain"><div class="sp-t"><span>Your prompt</span></div><p class="sp-n">Images, and the form if needed</p></div></div>')
    return (root + "".join(col(b) for b in start["items"] + block["items"])
            + f'<div class="fork">{track(assets, "lane-a")}{track(level, "lane-l")}</div>'
            + "".join(col(b) for b in finish["items"]) + stop + track(loop, "loop"))


# ------------------------------------------------------------------ Roadmap parsing
GROUPS = [("Q", "Quick fixes", "Plain defects: two files disagree, or a setting is wrong. No design needed."),
          ("S", "Changes to existing skills", "Ranked by expected gain."),
          ("N", "New skill candidates", "In build order. Each takes rows of intent and returns placed geometry or a verdict."),
          ("A", "Earlier retro items", "Proposed earlier, with what the new evidence changes."),
          ("P", "Pipeline-wide changes", "Ranked by expected gain.")]


def verdict_of(i):
    b = BOARD.get(i)
    if not b:
        return ""
    return b.get("verdict") or ""


def status_chip(s):
    low = s.lower()
    if low.startswith("`adopt_now`") or low.startswith("adopt_now"):
        k, t = "ok", "Adopt now"
    elif "test_first" in low[:30]:
        k, t = "test", "Test first"
    elif "later" in low[:12]:
        k, t = "later", "Later"
    elif "adopt_now" in low:
        k, t = "ok", "Adopt, in part"
    else:
        k, t = "test", "See note"
    return f'<span class="rs rs-{k}">{t}</span>'


def roadmap_html():
    out = []
    n = 0
    for k, title, note in GROUPS:
        ids = [i for i in ROAD if i[0] == k]
        out.append(f'<section class="grp" id="rg-{k}"><h3>{e(title)} <span class="ct">{len(ids)}</span></h3><p class="note">{e(note)}</p>')
        for i in ids:
            r = ROAD[i]
            n += 1
            v = verdict_of(i)
            vt = f'<span class="you">You: {e(v)}</span>' if v else ""
            bnote = (BOARD.get(i) or {}).get("note") or ""
            bn = f'<p class="yn">Your note: {tx(bnote)}</p>' if bnote else ""
            moved = f'<p class="moved"><b>Moved since the report:</b> {tx(D.MOVED[i])}</p>' if i in D.MOVED else ""
            body = f'<p>{inline(r["body"])}</p>' if r["body"] else ""
            where = f'<p class="wh">{inline(r["where"])}</p>' if r["where"] else ""
            stat_detail = re.sub(r"^`?(adopt_now|test_first|later)`?;?\s*", "", r["status"]).strip(" .")
            sd = f'<p class="wh">{inline(stat_detail[0].upper() + stat_detail[1:])}</p>' if stat_detail and k != "Q" else ""
            gain = f'<span class="kv"><b>Gain</b> {e(r["gain"].split(";")[0])}</span>' if r["gain"] else ""
            head = inline(r["what"])
            out.append(
                f'<article class="node item" id="r-{i}" data-q="{e((i + " " + r["what"] + " " + r["body"]).lower())}">'
                f'<header><span class="iid">{i}</span><span class="tch">{e(D.TOUCH.get(i, ""))}</span>{status_chip(r["status"])}{vt}{cbtn(i, i + " " + re.sub("[`*]", "", r["what"])[:70])}</header>'
                f'<p class="wt">{head}</p>{body}{where}{sd}{moved}{bn}'
                f'<p class="kvs"><span class="kv"><b>Effort</b> {e(r["effort"])}</span>{gain}</p></article>')
        out.append("</section>")
    return "".join(out), n


def decisions_html():
    out = []
    for i, (q, rec, why, need, conflict) in D.DECISIONS.items():
        v = BOARD.get(i) or {}
        blank = not (v.get("verdict") or v.get("note"))
        out.append(
            f'<article class="node dec" id="r-{i}" data-q="{e((i + " " + q + " " + rec).lower())}"><header><span class="iid">{i}</span>'
            f'<span class="tch">{"No answer on the board yet" if blank else "Answered"}</span>{cbtn(i, i + " " + q[:70])}</header>'
            f'<h3>{tx(q)}</h3><p class="rec"><b>My recommendation.</b> {tx(rec)}</p><p><b>Why.</b> {tx(why)}</p>'
            f'<p><b>What I need from you.</b> {tx(need)}</p>'
            + (f'<p class="warn"><b>Conflict check.</b> {tx(conflict)}</p>' if conflict else "") + "</article>")
    return "".join(out)


def ideas_html():
    out = []
    for i, t, what, why, cost in D.IDEAS:
        out.append(f'<article class="node dec" id="r-{i}" data-q="{e((t + " " + what + " " + why).lower())}"><header><span class="iid">{i}</span>{cbtn(i, i + " " + t)}</header>'
                   f'<h3>{tx(t)}</h3><p class="rec">{tx(what)}</p><p>{tx(why)}</p><p class="kvs"><span class="kv"><b>Cost</b> {tx(cost)}</span></p></article>')
    return "".join(out)


FIRST_BLOCK = {"s0": "S0", "s1": "S1", "s2": "S2", "s3": "S3", "s4": "A1", "s5": "P·", "t": "T", "s6": "L1", "s9": "S9"}


def stages_html():
    out = ['<section class="grp" id="st-gates"><h3>Gates</h3><div class="gr">']
    out.append('<ul class="plainlist">' + "".join(f"<li>{tx(r)}</li>" for r in D.GATE_RULES) + "</ul></div>")
    rows = []
    for g, when, judges, s, m, l in D.GATES:
        rows.append(f'<tr class="node" data-q="{e((g + " " + when + " " + judges).lower())}"><th scope="row"><span class="gl">{e(g)}</span></th><td>{tx(when)}</td><td>{tx(judges)}</td><td>{tx(s)}</td><td>{tx(m)}</td><td>{tx(l)}</td><td>{cbtn("gate:" + g, "Gate " + g)}</td></tr>')
    out.append(table(["Gate", "When", "What it judges", "Tier S answers", "Tier M", "Tier L", ""], rows, "wide"))
    out.append("</section>")
    for s in D.STAGES:
        lst = lambda xs: "<ul>" + "".join(f"<li>{tx(x)}</li>" for x in xs) + "</ul>"
        gate = f'<span class="gl">{e(s["gate"])}</span>' if s["gate"] else '<span class="gl none">No gate</span>'
        scripts = "".join(f'<code class="file">{e(x)}</code>' for x in s["scripts"]) or '<span class="note">None of its own</span>'
        extra = ""
        if s["id"] == "s5":
            rows = [f'<tr class="node" data-q="{e((p + " " + w).lower())}"><th scope="row">{p}</th><td>{tx(w)}</td><td>{cbtn("phase:" + p, "Phase " + p)}</td></tr>' for p, w in D.PHASES]
            extra = '<h4>The ten phases, in real construction order</h4>' + table(["Phase", "What goes in", ""], rows)
        out.append(
            f'<article class="node stage" id="st-{s["id"]}" data-q="{e((s["title"] + " " + " ".join(s["work"])).lower())}">'
            f'<header><span class="sn">{e(s["n"])}</span><h3>{e(s["title"])}</h3>{gate}{badge(s["status"])}{cbtn("stage:" + s["id"], "Stage " + s["n"] + " " + s["title"])}</header>'
            f'<p class="who">{tx(s["who"])} <button type="button" class="lnk" data-go="map" data-jump="bl-{FIRST_BLOCK[s["id"]]}">What each step does</button></p>'
            f'<div class="io"><div><h4>Goes in</h4>{lst(s["inputs"])}</div><div><h4>Comes out</h4>{lst(s["outputs"])}</div></div>'
            f'<h4>Work</h4>{lst(s["work"])}'
            f'<h4>To leave this stage</h4><p>{tx(s["exit"])}</p>'
            f'<h4>Per route</h4><p>{tx(s["route"])}</p>{extra}'
            f'<h4>Skills</h4><div class="chips">{"".join(chip(x) for x in s["skills"])}</div>'
            f'<h4>Scripts</h4><div class="chips">{scripts}</div>'
            f'<h4>Roadmap items that change it</h4><div class="chips">{"".join(rchip(x) for x in s["roadmap"])}</div>'
            f'<p class="myview"><b>My view.</b> {tx(s["view"])}</p></article>')
    return "".join(out)


def preload_words(a):
    return sum(SK[x]["words"] for x in a["skills"] if x in SK)


def agents_html():
    rows = []
    rows.append(f'<tr class="node" id="agent-manager" data-q="manager"><th scope="row">Manager</th><td>The session you start</td><td>Yours</td><td>Main session. Intake, interview, routing, gates, your decisions, merged fix lists, save points.</td><td>No</td><td><code>plan.md</code>, <code>log.md</code>, gate entries</td><td>{SK["house-rules"]["words"] + SK["scene-pipeline"]["words"]:,} words read at start: <span class="chips"><button type="button" class="chip" data-go="skills" data-jump="skill-house-rules">house-rules</button><button type="button" class="chip" data-go="skills" data-jump="skill-scene-pipeline">scene-pipeline</button></span></td><td>{cbtn("agent:manager", "Manager")}</td></tr>')
    for a in AG:
        job, edits, writes = D.AGENT_JOBS[a["name"]]
        ch = "".join(chip(x) for x in a["skills"])
        rows.append(f'<tr class="node" id="agent-{a["name"]}" data-q="{e((a["name"] + " " + job).lower())}"><th scope="row">{e(a["name"])}</th><td>{e(a["model"].capitalize())}</td><td>{e(a["effort"])}</td><td>{tx(job)}</td><td>{tx(edits)}</td><td>{tx(writes)}</td><td>{preload_words(a):,} words: <span class="chips">{ch}</span></td><td>{cbtn("agent:" + a["name"], a["name"])}</td></tr>')
    return table(["Agent", "Model", "Effort", "Job", "Edits the scene", "Writes", "Preloads", ""], rows, "wide")


def skills_html():
    order = [("always", "Always loaded"), ("s0", "Stage 0"), ("s1", "Stage 1"), ("s2", "Stage 2"), ("s3", "Stage 3"), ("s4", "Stage 4"), ("s5", "Stage 5"), ("s6", "Stages 6–8"), ("s9", "Stage 9"), ("review", "Every review round"), ("demand", "On demand")]
    loaders = {}
    for a in AG:
        for s in a["skills"]:
            loaders.setdefault(s, []).append(a["name"])
    cat = {"both": "Both", "game": "Game Art", "cg": "CG"}
    bind = {"rule": "Rule", "default": "Default", "toolkit": "Toolkit"}
    out = []
    for key, title in order:
        names = [n for n, r in LABEL.items() if r[3][0] == key]
        if not names:
            continue
        out.append(f'<h3 class="gh">{e(title)}</h3><div class="skills">')
        for n in names:
            _, c, eng, stages, b, origin, use, why, concern = LABEL[n]
            s = SK[n]
            sp = D.SPLIT.get(n, ("Leave", ""))
            ld = ", ".join(loaders.get(n, [])) or "On demand or by the manager"
            bits = [f'{s["words"]:,} words']
            if s["references"]:
                bits.append(f'{len(s["references"])} refs')
            if s["scripts"]:
                bits.append(f'{len(s["scripts"])} scripts')
            con = f'<p class="note">{tx(concern)}</p>' if concern else ""
            spn = f' {tx(sp[1])}' if sp[1] else ""
            out.append(
                f'<article class="node skill" id="skill-{n}" data-q="{e((n + " " + use).lower())}"><header><code class="nm">{e(n)}</code>'
                f'<span class="tag t-{c}">{cat[c]}</span><span class="tag b-{b}">{bind[b]}</span><span class="tag">{e(eng)}</span>{cbtn("skill:" + n, n)}</header>'
                f'<p>{tx(use)}</p><p class="meta">{" · ".join(bits)} · {e(origin)} · read by {e(ld)}</p>{con}'
                f'<p class="split split-{sp[0].lower()}"><b>{e(sp[0])}.</b>{spn}</p></article>')
        out.append("</div>")
    return "".join(out)


def scripts_html():
    out = ['<h3 id="lint-table">scene-lint, 23 checks</h3><p class="note">Blender only. A blocker stops the captures. Major goes in the fix list. Minor never blocks. Each check reports how many things it looked at, so a zero with nothing checked is not a pass.</p>']
    rows = [f'<tr class="node" data-q="{e((n + " " + t).lower())}"><th scope="row"><code>{e(n)}</code></th><td><span class="cl cl-{c}">{e(c)}</span></td><td>{tx(t)}</td><td>{cbtn("check:" + n, "Lint check " + n)}</td></tr>' for n, c, t in D.LINT]
    out.append(table(["Check", "Class", "Finds", ""], rows))
    out.append('<h3>Scripts by skill</h3><p class="note">Plain Python or headless Blender through <code>bin/blender-bg</code>. Self-tests build a tiny synthetic scene and never touch a project.</p>')
    for n, s in SK.items():
        scr = s["scripts"] + [t for t in s["templates"] if t.get("doc")]
        if not scr:
            continue
        rows = []
        for x in scr:
            nm = x["name"]
            base = os.path.basename(nm)
            kind = "Self-test" if ("selftest" in base or base.startswith("check_capture") or base.startswith("check_fit") or base.startswith("check_palette") or "/" in nm and "test" in nm) else "Tool"
            doc = D.SCRIPT_DOC.get(base) if (base in D.SCRIPT_DOC and (len(x.get("doc", "")) < 22 or base in ("export_delivery.py", "validate.py", "bake_maps.py"))) else x.get("doc", "")
            doc = re.sub(r"\s*\(tested[^)]*\)?", "", doc or "")
            doc = re.sub(r"\s*\(check_\w+\.py is the self-check\)", "", doc)
            rows.append(f'<tr class="node" data-q="{e((nm + " " + doc).lower())}"><th scope="row"><code>{e(nm)}</code></th><td>{kind}</td><td>{tx(doc)}</td><td>{cbtn("script:" + n + "/" + base, nm)}</td></tr>')
        out.append(f'<h4 class="sh" id="scr-{n}"><button type="button" class="lnk" data-go="skills" data-jump="skill-{n}">{e(n)}</button></h4>' + table(["Script", "Kind", "What it does", ""], rows))
    cards = sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(REPO, "toolbox", "tools", "*.md")))
    notes = sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(REPO, "knowledge", "*.md")) if not p.endswith("README.md"))
    out.append(f'<h3>Tool cards <span class="ct">{len(cards)}</span></h3><p class="note">One instruction file per tool found on your PC. Prefixes: <code>ue</code> Unreal plugin, <code>bl</code> and <code>blx</code> Blender add-on and extension, <code>mcp</code> server.</p><div class="chips">' + "".join(f'<code class="file">{e(c)}</code>' for c in cards) + "</div>")
    out.append(f'<h3>Solved problems in knowledge/ <span class="ct">{len(notes)}</span></h3><div class="chips">' + "".join(f'<code class="file">{e(c)}</code>' for c in notes) + "</div>")
    return "".join(out)


def files_html():
    rows = [f'<tr class="node" data-q="{e((p + " " + n).lower())}"><th scope="row"><code>{e(p)}</code></th><td>{tx(w)}</td><td>{tx(r)}</td><td>{tx(n)}</td><td>{cbtn("file:" + re.sub(r"[^A-Za-z0-9_.-]", "_", p)[:60], p)}</td></tr>' for p, w, r, n in D.FILES]
    shared = [f'<tr class="node" data-q="{e((p + " " + n).lower())}"><th scope="row"><code>{e(p)}</code></th><td>{tx(n)}</td><td>{cbtn("shared:" + re.sub(r"[^A-Za-z0-9_.-]", "_", p)[:60], p)}</td></tr>' for p, n in D.SHARED]
    return (table(["File under projects/&lt;slug&gt;/", "Written by", "Read by", "Note", ""], rows, "wide")
            + "<h3>Shared across projects, committed</h3>" + table(["Where", "What", ""], shared))


def routes_html():
    head, *rows = D.ROUTES
    r = [f'<tr class="node" data-q="{e(" ".join(x).lower())}"><th scope="row">{e(x[0])}</th>' + "".join(f"<td>{tx(c)}</td>" for c in x[1:]) + f'<td>{cbtn("route:" + re.sub(r"[^A-Za-z0-9]", "_", x[0]), "Route row " + x[0])}</td></tr>' for x in rows]
    out = ['<h3>Routes</h3>', table([e(h) for h in head] + [""], r, "wide")]
    out.append("<h3>Mode</h3>" + table(["Mode", "Goal", "Adds", ""], [f'<tr class="node" data-q="{e((a + " " + b).lower())}"><th scope="row"><code>{a}</code></th><td>{tx(b)}</td><td>{tx(c)}</td><td>{cbtn("mode:" + a, "Mode " + a)}</td></tr>' for a, b, c in D.MODES]))
    out.append("<h3>Detail</h3>" + table(["Detail", "What gets built", "Generated props", ""], [f'<tr class="node" data-q="{e((a + " " + b).lower())}"><th scope="row"><code>{a}</code></th><td>{tx(b)}</td><td>{tx(c)}</td><td>{cbtn("detail:" + a, "Detail " + a)}</td></tr>' for a, b, c in D.DETAIL]))
    out.append("<h3>Tier</h3>" + table(["Tier", "Typical input", "Research", "Reviews", "Gates you answer", ""], [f'<tr class="node" data-q="{e((a + " " + b).lower())}"><th scope="row">{a}</th><td>{tx(b)}</td><td>{tx(c)}</td><td>{tx(d_)}</td><td>{tx(g)}</td><td>{cbtn("tier:" + a, "Tier " + a)}</td></tr>' for a, b, c, d_, g in D.TIERS], "wide"))
    return "".join(out)


def rules_html():
    r = [f'<tr class="node" data-q="{e((t + " " + b).lower())}"><th scope="row">{n}</th><td><b>{tx(t)}</b><br>{tx(b)}</td><td>{tx(en)}</td><td>{cbtn("rule:" + n, "Rule " + n + " " + t)}</td></tr>' for n, t, b, en in D.RULES]
    m = [f'<tr class="node" data-q="{e((t + " " + b).lower())}"><td><b>{tx(t)}</b><br>{tx(b)}</td><td>{cbtn("mrule:" + re.sub(r"[^A-Za-z]", "", t)[:30], t)}</td></tr>' for t, b in D.MANAGER_RULES]
    mem = [f'<tr class="node" data-q="{e((t + " " + b).lower())}"><td><b>{tx(t)}</b><br>{tx(b)}</td><td>{cbtn("mem:" + re.sub(r"[^A-Za-z]", "", t)[:30], t)}</td></tr>' for t, b in D.MEMORY_RULES]
    return ('<h3>House rules</h3><p class="note">Every agent preloads these. "Caught by" says what stops a break. "None" means only the text does.</p>' + table(["#", "Rule", "Caught by", ""], r)
            + "<h3>Manager's rules</h3>" + table(["Rule", ""], m)
            + '<h3>Standing rules in memory only</h3><p class="note">These work in this account\'s sessions and aren\'t in the repo. Another session on another account wouldn\'t have them.</p>' + table(["Rule", ""], mem))


def status_html():
    def cell(s):
        return f"<td>{badge(s)}</td>" if s in D.STATUS else f'<td class="note">{e(s)}</td>'
    r = [f'<tr class="node" data-q="{e(x[0].lower())}"><th scope="row">{e(x[0])}</th>{cell(x[1])}{cell(x[2])}{cell(x[3])}</tr>' for x in D.ROUTE_STATUS]
    legend = "".join(f'<li>{badge(k)} {e(v[1])}</li>' for k, v in D.STATUS.items())
    gaps = [
        ("Nothing in the roadmap is measured", "Every gain is an estimate from the retro or a source's own claim. Instrument one lane first."),
        ("linear-runs has only run its self-test", "The report's row-driven builders all copy its contract."),
        ("No Unreal lint", "The supervisor checks those items by eye on the Unreal route."),
        ("No Unreal lighting path", "No lookdev or palette script, so blender_unreal also stops at T for light."),
        ("README is out of date", "It calls Unreal the default at about 80 % of work and its scripts sketches. Those scripts ran on UE 5.8.3 through PipelineTools; the route as a whole hasn't."),
        ("FBX through Unreal, untested parts", "Custom normals, UCX collision, LOD groups and sockets through import have never been checked on a real kit piece."),
        ("Reviewer accuracy is unknown", "No seeded test has run. Your marks equalled the defaults every time, so the record can't show if reviews are good."),
        ("Board decisions aren't reaching sessions", "Gate K and this roadmap's later answers sit on another account. I read a local snapshot of the roadmap only."),
        ("Frozen lighting has no route to G3", "No stage row covers lighting_focus: deferred through to sign-off."),
    ]
    g = "".join(f'<li class="node" data-q="{e((a + " " + b).lower())}"><b>{tx(a)}.</b> {tx(b)} {cbtn("gap:" + re.sub(r"[^A-Za-z]", "", a)[:30], a)}</li>' for a, b in gaps)
    return ('<h3>What has really run, per route</h3>' + table(["Stage", "unreal", "blender_unreal", "blender"], r) + f'<ul class="legend">{legend}</ul>'
            + f'<h3>Known gaps</h3><ul class="gaps">{g}</ul>')


# ------------------------------------------------------------------ Page
road, n_road = roadmap_html()
vals = dict(
    TREE=tree_html(), STAGES=stages_html(), REVIEWFIG=review_fig(), LANEFIG=lane_fig(), DATAFIG=data_fig(),
    ROUTES=routes_html(), AGENTS=agents_html(), SKILLS=skills_html(), SCRIPTS=scripts_html(), FILES=files_html(),
    RULES=rules_html(), STATUS=status_html(), ROADMAP=road, DECISIONS=decisions_html(), IDEAS=ideas_html(),
    N_SKILLS=len(SK), N_AGENTS=len(AG) + 1, N_SCRIPTS=sum(len(s["scripts"]) for s in SK.values()), N_ROAD=n_road, N_WORDS=f'{sum(s["words"] for s in SK.values()):,}',
    N_DO=sum(1 for v in BOARD.values() if v.get("verdict") == "do"),
)
rev = subprocess.run(["git", "-C", REPO, "log", "-1", "--format=%h, %cs"], capture_output=True, text=True).stdout.strip()
vals["CHECKED"] = f"Checked against the repo at {rev}"
tpl = open(os.path.join(HERE, "template.html"), encoding="utf8").read()
for k, v in vals.items():
    tpl = tpl.replace("{{" + k + "}}", str(v))
left = [k for k in vals if "{{" + k + "}}" in tpl]
assert not left, left

# Private names must never reach the page.
# The list stays out of the repo: one regex in private_names.txt, git-ignored.
names = open(os.path.join(HERE, "private_names.txt"), encoding="utf8").read().strip()
bad = re.findall("(?i)" + names, re.sub(r"<[^>]+>", " ", tpl))
assert not bad, bad
out = os.path.join(HERE, "pipeline_map.html")
open(out, "w", encoding="utf8").write(tpl)
ids = re.findall(r'data-jump="([^"]+)"', tpl)
miss = sorted({i for i in ids if f'id="{i}"' not in tpl})
print("bytes", len(tpl.encode()), "roadmap", n_road, "missing jump targets", miss, "board docs", len(BOARD), "do", vals["N_DO"])
