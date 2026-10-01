"""Build the static site into build/ from the committed data. No network access.

Usage: python scripts/build_site.py
"""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

sys.path.insert(0, str(Path(__file__).resolve().parent))

import a11y_snippets  # noqa: E402
from build_data import verse_tokens  # noqa: E402
from hebrew import hebrew_numeral, tokenize  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"
OUT = ROOT / "build"
CONFIG = json.loads((ROOT / "config" / "site.json").read_text(encoding="utf-8"))
KINUYIM = json.loads((ROOT / "config" / "kinuyim.json").read_text(encoding="utf-8"))

NAME_LABELS = {t: v["label"] for t, v in KINUYIM["types"].items()}
NAME_LABELS["HAVAYAH"] = "שם הויה"
NAME_SHORT = {t: v["label"] for t, v in KINUYIM["types"].items()}
NAME_SHORT["HAVAYAH"] = "ה'"
BOOK_NAMES = {1: "ספר ראשון", 2: "ספר שני", 3: "ספר שלישי", 4: "ספר רביעי", 5: "ספר חמישי"}
AUTHOR_SLOTS = {"דוד": 1, "בני קרח": 2, "אסף": 3, "משה": 4, "שלמה": 5, "הימן": 6, "איתן": 6}
AUTHOR_LEGEND = [(1, "דוד"), (2, "בני קרח"), (3, "אסף"), (4, "משה"), (5, "שלמה"), (6, "הימן / איתן"), (0, "ללא מחבר בכותרת")]
TYPE_SLOTS = {"מזמור": 1, "שיר": 2, "שיר המעלות": 3, "משכיל": 4, "מכתם": 5, "תפלה": 6, "תהלה": 6, "שגיון": 6}
TYPE_LEGEND = [(1, "מזמור"), (2, "שיר"), (3, "שיר המעלות"), (4, "משכיל"), (5, "מכתם"), (6, "תפלה / תהלה / שגיון"), (0, "ללא כינוי סוג")]
CGJ = "͏"


TEAMIM = re.compile("[\u0591-\u05AF]")


def dual(h: str) -> Markup:
    """Verse HTML shown without te'amim by default; the full text waits in data-t
    for the te'amim toggle (app.js). Tags never contain cantillation marks."""
    return Markup('<span class="vt" data-t="{}">{}</span>').format(str(h), Markup(TEAMIM.sub("", str(h))))


def heb(n: int) -> str:
    return hebrew_numeral(n)


def heb_p(n: int) -> str:
    return hebrew_numeral(n, punctuate=True)


# --- verse rendering ---------------------------------------------------------
def render_verse(v: dict, heading_end: int | None = None, para: bool = False) -> Markup:
    """Verse text as HTML: name spans, heading part, ketiv/qeri styling."""
    text = v["text"]
    events = []  # (offset, order, html)
    for e in v["names"]:
        cls = f"nm nm-{e['type']}"
        events.append((e["start"], 1, f'<span class="{cls}">'))
        events.append((e["end"], 0, "</span>"))
    if heading_end is not None and heading_end > 0:
        events.append((0, -1, '<span class="heading-text">'))
        events.append((heading_end, -2, "</span>"))
    events.sort(key=lambda x: (x[0], x[1]))
    out, pos = [], 0
    for off, _, tag in events:
        out.append(html.escape(text[pos:off], quote=False))
        out.append(tag)
        pos = off
    out.append(html.escape(text[pos:], quote=False))
    s = "".join(out).replace(CGJ, "")
    s = re.sub(r"\(([^)]*)\)", r'<span class="ktiv" title="כתיב">(\1)</span>', s)
    return Markup(s)


def psalm_verses_html(p: dict) -> list[dict]:
    h = p["heading"]
    rows = []
    for v in p["verses"]:
        he = None
        if h:
            if v["v"] < h["end"]["v"]:
                he = len(v["text"])
            elif v["v"] == h["end"]["v"]:
                he = h["end"]["offset"]
        rows.append({"v": v["v"], "heb": heb(v["v"]), "html": dual(render_verse(v, he)),
                     "para": v["v"] in p["paragraph_after"]})
    return rows


# --- alphabetic psalms ------------------------------------------------------
ALPHABET = [chr(c) for c in range(0x05D0, 0x05EB) if chr(c) not in "\u05DA\u05DD\u05DF\u05E3\u05E5"]


def initials(p: dict) -> list[tuple[int, str]]:
    """First letter of each verse, after the heading."""
    h = p["heading"]
    out = []
    for v in p["verses"]:
        text = v["text"]
        if h and v["v"] < h["end"]["v"]:
            continue
        if h and v["v"] == h["end"]["v"]:
            text = text[h["end"]["offset"]:]
            if not text.strip():
                continue
        letters = tokenize(text)
        if letters:
            out.append((v["v"], letters[0].letters[0].ch))
    return out


def alphabetic(psalms: dict) -> list[dict]:
    out = []
    for n in (25, 34, 145):
        ini = initials(psalms[n])
        seen = [c for _, c in ini]
        out.append({"n": n, "kind": "פסוק לכל אות", "initials": seen,
                    "missing": [c for c in ALPHABET if c not in seen],
                    "extra": [(heb(v), c) for v, c in ini if seen.count(c) > 1 or c not in ALPHABET]})
    ini = initials(psalms[119])
    groups = [ini[i:i + 8] for i in range(0, len(ini), 8)]
    ok = len(groups) == 22 and all(len({c for _, c in g}) == 1 and g[0][1] == ALPHABET[i] for i, g in enumerate(groups))
    out.append({"n": 119, "kind": "שמונה פסוקים לכל אות", "initials": [g[0][1] for g in groups],
                "missing": [] if ok else ["(לא נמצאה התאמה מלאה)"], "extra": [], "verified": ok})
    for n in (111, 112):
        out.append({"n": n, "kind": "אות לכל חצי פסוק", "initials": [], "missing": None, "extra": []})
    return out


# --- charts ------------------------------------------------------------------
def hbar(items: list[tuple[str, int, str]], title: str, unit: str = "") -> Markup:
    """Horizontal bar chart (inline SVG): [(label, value, css colour)]. Labels on the right (RTL)."""
    W, row, lab, pad = 640, 30, 150, 46
    vmax = max(v for _, v, _ in items) or 1
    scale = (W - lab - pad) / vmax
    h = row * len(items) + 8
    parts = [f'<svg class="chart" style="direction: ltr" viewBox="0 0 {W} {h}" role="img" aria-label="{html.escape(title)}">']
    desc = "; ".join(f"{l}: {v}{unit}" for l, v, _ in items)
    parts.append(f"<title>{html.escape(title)}</title><desc>{html.escape(desc)}</desc>")
    for i, (label, v, color) in enumerate(items):
        y = i * row + 4
        w = max(v * scale, 2)
        x = W - lab - w
        parts.append(f'<text x="{W - 4}" y="{y + 17}" text-anchor="end">{html.escape(label)}</text>')
        parts.append(f'<rect x="{x:.1f}" y="{y + 3}" width="{w:.1f}" height="18" rx="4" style="fill: {color}"/>')
        parts.append(f'<text class="val" x="{x - 6:.1f}" y="{y + 17}" text-anchor="end">{v}</text>')
    parts.append(f'<line class="grid" x1="{W - lab}" x2="{W - lab}" y1="0" y2="{h}"/></svg>')
    return Markup("".join(parts))


def structure_charts(psalms: dict, books: list) -> dict:
    b = hbar([(BOOK_NAMES[x["n"]], x["count"], f"var(--b{x['n']})") for x in books], "מזמורים בכל ספר")
    bv = hbar([(BOOK_NAMES[x["n"]], x["verses"], f"var(--b{x['n']})") for x in books], "פסוקים בכל ספר")
    a_counts = []
    for slot, label in AUTHOR_LEGEND:
        names_ = [k for k, v in AUTHOR_SLOTS.items() if v == slot] if slot else []
        if slot:
            n = sum(1 for p in psalms.values() if p["heading"] and any(a in p["heading"]["attribution"] for a in names_))
        else:
            n = sum(1 for p in psalms.values() if not p["heading"] or not p["heading"]["attribution"])
        a_counts.append((label, n, f"var(--c{slot})" if slot else "var(--c-none)"))
    t_counts = []
    for slot, label in TYPE_LEGEND:
        names_ = [k for k, v in TYPE_SLOTS.items() if v == slot] if slot else []
        if slot:
            n = sum(1 for p in psalms.values() if p["heading"] and any(t in p["heading"]["types"] for t in names_))
        else:
            n = sum(1 for p in psalms.values() if not p["heading"] or not p["heading"]["types"])
        t_counts.append((label, n, f"var(--c{slot})" if slot else "var(--c-none)"))
    return {"book": b, "book_verses": bv,
            "author": hbar(a_counts, "מזמורים לפי המחבר שבכותרת"),
            "type": hbar(t_counts, "מזמורים לפי כינוי הסוג שבכותרת")}


# --- liturgy -----------------------------------------------------------------
_NUM = {c: v for v, c in [(1, "א"), (2, "ב"), (3, "ג"), (4, "ד"), (5, "ה"), (6, "ו"), (7, "ז"), (8, "ח"), (9, "ט"),
                          (10, "י"), (20, "כ"), (30, "ל"), (40, "מ"), (50, "נ"), (60, "ס"), (70, "ע"), (80, "פ"),
                          (90, "צ"), (100, "ק")]}


def parse_heb_numbers(text: str) -> list[int]:
    """'ט"ז. ל"ב. צ'.' -> [16, 32, 90]"""
    out = []
    for tok in re.findall(r"[\u05D0-\u05EA]+[\"'][\u05D0-\u05EA]?", text):
        letters = re.sub(r"[\"']", "", tok)
        if all(c in _NUM for c in letters):
            out.append(sum(_NUM[c] for c in letters))
    return [n for n in out if 1 <= n <= 150]


def liturgy_view(lit: dict) -> dict:
    nus = list(lit["nusachim"])
    ctx_label = {c["id"]: c["label"] for c in lit["contexts"]}
    per = {n: {k: set() for k in nus} for n in range(1, 151)}
    table = {c["id"]: {k: [] for k in nus} for c in lit["contexts"]}
    for e in lit["entries"]:
        per[e["psalm"]][e["nusach"]].add(e["context"])
        if e["psalm"] not in table[e["context"]][e["nusach"]]:
            table[e["context"]][e["nusach"]].append(e["psalm"])
    cells = []
    for n in range(1, 151):
        counts = {k: len(per[n][k]) for k in nus}
        all_ctx = set().union(*per[n].values())
        counts["all"] = len(all_ctx)
        cells.append({"n": n, "heb": heb(n), "counts": counts,
                      "bucket": {k: min(v, 5) for k, v in counts.items()},
                      "ctx": sorted(all_ctx),
                      "label": f"מזמור {heb(n)} · " + (", ".join(ctx_label[c] for c in sorted(all_ctx)) or "לא נמצא בסידורים")})
    used = [c for c in lit["contexts"] if any(table[c["id"]][k] for k in nus)]
    return {"cells": cells, "table": table, "contexts": used, "nusach_ids": nus, "ctx_label": ctx_label}


# --- doublet diff ------------------------------------------------------------
def space_tokens(v: dict) -> list[tuple[str, str, str | None]]:
    """[(display, key, name_type)] split on spaces; key normalizes names to their type."""
    text = v["text"].replace(CGJ, "")
    out = []
    for m in re.finditer(r"\S+", text):
        a, b = m.start(), m.end()
        names_in = [e for e in v["names"] if a <= e["start"] < b]
        key_parts = []
        for w in tokenize(m.group(0)):
            absw = a + w.start
            e = next((e for e in names_in if e["start"] <= absw < e["end"]), None)
            key_parts.append("§" + e["type"] if e else w.skeleton)
        dedup = [k for i, k in enumerate(key_parts) if i == 0 or k != key_parts[i - 1] or not k.startswith("§")]
        out.append((m.group(0), " ".join(dedup), names_in[0]["type"] if names_in else None))
    return out


def side_stream(psalms: dict, ranges: list[dict]) -> list[dict]:
    toks = []
    for r in ranges:
        p = psalms[r["psalm"]]
        for v in p["verses"]:
            if r["from"] <= v["v"] <= r["to"]:
                toks.append({"marker": f"{heb(r['psalm'])}:{heb(v['v'])}"})
                for disp, key, nt in space_tokens(v):
                    toks.append({"disp": disp, "key": key, "name": nt})
    return toks


def diff_sides(a: list[dict], b: list[dict]) -> tuple[Markup, Markup, int, int]:
    ka = [t.get("key") for t in a if "key" in t]
    kb = [t.get("key") for t in b if "key" in t]
    ia = [i for i, t in enumerate(a) if "key" in t]
    ib = [i for i, t in enumerate(b) if "key" in t]
    mark_a, mark_b = {}, {}
    name_diffs = 0
    for op, a1, a2, b1, b2 in SequenceMatcher(None, ka, kb, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        for i in range(a1, a2):
            mark_a[ia[i]] = "diff"
        for j in range(b1, b2):
            mark_b[ib[j]] = "diff"
        if op == "replace":
            # pair the names inside the changed block in order of appearance
            na = [ia[i] for i in range(a1, a2) if a[ia[i]]["name"]]
            nb = [ib[j] for j in range(b1, b2) if b[ib[j]]["name"]]
            for x, y in zip(na, nb):
                if a[x]["name"] != b[y]["name"]:
                    mark_a[x] = f"diff-name-{a[x]['name']}"
                    mark_b[y] = f"diff-name-{b[y]['name']}"
                    name_diffs += 1

    def render(toks, marks):
        parts = []
        for i, t in enumerate(toks):
            if "marker" in t:
                parts.append(f'<span class="vnum">{t["marker"]}</span>')
                continue
            d = html.escape(t["disp"], quote=False)
            parts.append(f'<span class="{marks[i]}">{d}</span>' if i in marks else d)
        return Markup(" ".join(parts))

    return render(a, mark_a), render(b, mark_b), len(mark_a), name_diffs


# --- site --------------------------------------------------------------------
def main() -> int:
    psalms = {n: json.loads((DATA / "psalms" / f"{n:03d}.json").read_text(encoding="utf-8")) for n in range(1, 151)}
    books = json.loads((DATA / "books.json").read_text(encoding="utf-8"))
    stats = json.loads((DATA / "names_stats.json").read_text(encoding="utf-8"))
    doublets = json.loads((DATA / "doublets.json").read_text(encoding="utf-8"))
    sources = json.loads((DATA / "sources.json").read_text(encoding="utf-8"))
    chida = json.loads((DATA / "chida.json").read_text(encoding="utf-8"))
    lit = json.loads((DATA / "liturgy.json").read_text(encoding="utf-8"))
    chol = json.loads((DATA / "annotations" / "chol_names.json").read_text(encoding="utf-8"))

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SITE / "assets", OUT / "assets")
    (OUT / ".nojekyll").write_text("")

    env = Environment(loader=FileSystemLoader(SITE / "templates"), autoescape=select_autoescape(["html", "j2"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters["heb"] = heb
    env.filters["heb_p"] = heb_p
    env.filters["plain"] = lambda t: TEAMIM.sub("", t or "")
    version = date.today().strftime("%Y%m%d")
    pages = []

    def page(path: str, template: str, **ctx):
        depth = path.count("/") + 1 if path else 0
        root = "../" * depth
        ctx.update(root=root, site=CONFIG, path=path, version=version,
                   a11y_head=Markup(a11y_snippets.head(root, version)),
                   a11y_foot=Markup(a11y_snippets.foot(root, version)),
                   NAME_LABELS=NAME_LABELS, NAME_SHORT=NAME_SHORT, BOOK_NAMES=BOOK_NAMES)
        target = OUT / path / "index.html" if path else OUT / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(env.get_template(template).render(**ctx), encoding="utf-8")
        pages.append(path)

    # map cells
    cells = []
    for n, p in psalms.items():
        h = p["heading"] or {}
        att = h.get("attribution") or []
        typ = h.get("types") or []
        c = p["names_count"]
        hv, el = c["HAVAYAH"], c["ELOKIM"]
        if hv + el == 0:
            nm, k, strong = "0", 0, False
        else:
            share = hv / (hv + el)
            nm = "h" if share >= .5 else "e"
            k = round(abs(share - .5) * 200)
            strong = k >= 50
        a_slot = AUTHOR_SLOTS.get(att[0], 0) if att else 0
        t_slot = TYPE_SLOTS.get(typ[0], 0) if typ else 0
        base = f"מזמור {heb(n)}"
        cells.append({
            "n": n, "heb": heb(n), "book": p["book"], "author": a_slot, "type": t_slot, "names": nm, "k": k,
            "strong": strong,
            "labels": {
                "book": f"{base} · {BOOK_NAMES[p['book']]}",
                "author": f"{base} · {', '.join(att) if att else 'ללא מחבר בכותרת'}",
                "type": f"{base} · {', '.join(typ) if typ else 'ללא כינוי סוג'}",
                "names": f"{base} · ה' {hv}, א-להים {el}",
            },
        })

    # names chart (per book, HAVAYAH vs ELOKIM)
    chart_max = max(max(b["counts"]["HAVAYAH"], b["counts"]["ELOKIM"]) for b in stats["per_book"])

    pairs = []
    for d in doublets["known"]:
        a = side_stream(psalms, d["a"])
        b = side_stream(psalms, d["b"])
        ha, hb, ndiff, name_diffs = diff_sides(a, b)
        title = " ↔ ".join([
            " + ".join(f"{heb(r['psalm'])}" + (f" {heb(r['from'])}–{heb(r['to'])}" if r["from"] > 1 or r["to"] < psalms[r["psalm"]]["verse_count"] else "") for r in side)
            for side in (d["a"], d["b"])])
        count = lambda side: {t: sum(e["counted"] and e["type"] == t for r in side for v in psalms[r["psalm"]]["verses"]  # noqa: E731
                                     if r["from"] <= v["v"] <= r["to"] for e in v["names"]) for t in ("HAVAYAH", "ELOKIM")}
        pairs.append({**d, "title": title, "html_a": dual(ha), "html_b": dual(hb), "diffs": ndiff,
                      "name_diffs": name_diffs, "count_a": count(d["a"]), "count_b": count(d["b"])})

    common = dict(psalms=psalms, books=books, stats=stats, cells=cells, sources=sources, chol=chol,
                  pairs=pairs, doublets=doublets, AUTHOR_LEGEND=AUTHOR_LEGEND, TYPE_LEGEND=TYPE_LEGEND,
                  chart_max=chart_max, kinuyim=KINUYIM, alpha=alphabetic(psalms), chida=chida, lit=lit, charts=structure_charts(psalms, books), litv=liturgy_view(lit),
                  tikkun=parse_heb_numbers(" ".join(x["text"] for x in sources["tikkun_haklali"]["segments"])),
                  chida_total=sum(l["count"] for l in chida["letters"]))

    page("", "index.html.j2", **common)
    page("sefer", "sefer.html.j2", **common)
    page("shemot", "shemot.html.j2", **common)
    for pr in pairs:
        page(f"kfulim/{pr['id']}", "pair.html.j2", pair=pr, **common)
    page("tefila", "tefila.html.j2", **common)
    page("chida", "chida.html.j2", **common)
    L = chida["letters"]
    for i, l in enumerate(L):
        rows = [{"psalm": r["psalm"], "verse": r["verse"],
                 "html": dual(render_verse(psalms[r["psalm"]]["verses"][r["verse"] - 1]))} for r in l["verses"]]
        page(f"chida/{l['slug']}", "chida_letter.html.j2", letter=l, rows=rows,
             prev=L[i - 1] if i else None, next=L[i + 1] if i + 1 < len(L) else None, **common)
    page("shita", "shita.html.j2", **common)
    page("about", "about.html.j2", **common)
    page("accessibility", "accessibility.html.j2", **common)
    page("privacy", "privacy.html.j2", **common)
    for n, p in psalms.items():
        page(f"mizmor/{n}", "psalm.html.j2", p=p, n=n, verses=psalm_verses_html(p),
             prev=n - 1 if n > 1 else None, next=n + 1 if n < 150 else None,
             pair_ids=p["doublet_of"] or [], **common)

    (OUT / "404.html").write_text(env.get_template("404.html.j2").render(
        root=CONFIG["base_path"], site=CONFIG, path="404", version=version,
        a11y_head=Markup(a11y_snippets.head(CONFIG["base_path"], version)),
        a11y_foot=Markup(a11y_snippets.foot(CONFIG["base_path"], version))), encoding="utf-8")

    base = CONFIG["base_url"].rstrip("/") + "/"
    urls = "\n".join(f"  <url><loc>{base}{p + '/' if p else ''}</loc></url>" for p in pages)
    (OUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n',
        encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n", encoding="utf-8")
    print(f"built {len(pages)} pages into {OUT.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
