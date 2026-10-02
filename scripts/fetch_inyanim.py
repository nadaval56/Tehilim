"""Psalms by need (לרפואה, בעת צרה, למקשה לילד ...), only from fetched sources.

Each need lists quotations from sources (Sefaria, Hebrew Wikisource). The
psalms of each quotation are read from the quotation itself: Hebrew
numerals, explicit references "(תהלים צא, א)", or a quoted opening of a
psalm ("מזמור יענך", "יושב בסתר"). Shimush Tehillim (Wikisource) adds, per
psalm, the opening of its stated use; it is classified by words in that
text. Writes data/inyanim.json.
"""
from __future__ import annotations

import html as html_mod
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import quotes  # noqa: E402
import sefaria  # noqa: E402
from hebrew import strip_marks, tokenize, hebrew_numeral, normalize_finals  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

NEEDS = [
    {"id": "refua", "title": "לרפואה ולחולה", "kw": ["חולה", "חולי", "לרפואה", "קדחת", "ויתרפא", "יתרפא", "לרפאות"]},
    {"id": "tzara", "title": "בעת צרה", "kw": ["צרה", "להנצל", "סכנה"]},
    {"id": "leida", "title": "למקשה לילד ולמעוברת", "kw": ["מקשה", "מעוברת", "יולדת", "תפיל", "תלד", "לילד"]},
    {"id": "shmira", "title": "לשמירה", "kw": ["שמירה", "להשמר", "מזיק", "מזיקין", "שדים", "לסטים"]},
    {"id": "hatzlacha", "title": "להצלחה ולחן", "kw": ["חן", "הצלחה", "להצליח", "ותצליח"]},
    {"id": "derech", "title": "בדרך ובים", "kw": ["בדרך", "לדרך", "בים", "לים", "מסערת", "בלילה"]},
    {"id": "geshamim", "title": "לגשמים", "kw": ["גשם", "גשמים", "למטר"]},
    {"id": "goses", "title": "ליד גוסס", "kw": []},
]

# (need, Sefaria ref(s), version or None, window start, window end) — the window trims the quotation.
SOURCES = [
    ("refua", ["Sansan_LeYair.3.24", "Sansan_LeYair.3.25", "Sansan_LeYair.3.32"], None, None, None,
     "חיד\"א, סנסן ליאיר ג, כד–לב (מבחר)"),
    ("tzara", ["Sansan_LeYair.1.17"], None, None, "י״ב פעמים", "חיד\"א, סנסן ליאיר א, יז"),
    ("leida", ["Sansan_LeYair.3.8"], None, None, "ככתוב לעיל", "חיד\"א, סנסן ליאיר ג, ח"),
    ("leida", ["Likutei_Moharan,_Part_II.2.10.1"], None, None, "דהינו לומר אותו.", "ליקוטי מוהר\"ן תנינא ב, י"),
    ("shmira", ["Shevuot.15b.10"], "Wikisource Talmud Bavli", None, None, "שבועות טו ע\"ב"),
    ("hatzlacha", ["Sansan_LeYair.3.35", "Sansan_LeYair.3.36"], None, None, "ימצא חיים:", "חיד\"א, סנסן ליאיר ג, לה"),
    ("geshamim", ["Kaf_HaChayim_on_Shulchan_Arukh,_Orach_Chayim.579.18"], None, None, "קל\"ו.",
     "כף החיים, אורח חיים תקעט, יח"),
    ("goses", ["Ma'avar_Yabbok,_Siftei_Renanot.5.1"], None, None, "קמ\"ט ק\"נ", "מעבר יבק, שפתי רננות ה, א"),
]

MATRES = str.maketrans("", "", "וי")  # ignore vav/yod when comparing openings (plene vs defective)


def norm(sk: str) -> str:
    return sk.translate(MATRES)


def psalm_openings() -> tuple[dict, dict]:
    """First two words of each psalm after its heading, and unique two-word headings."""
    openings, headings, firsts = {}, {}, {}
    for n in range(1, 151):
        p = json.loads((ROOT / "data" / "psalms" / f"{n:03d}.json").read_text(encoding="utf-8"))
        h = p["heading"]
        v = p["verses"][h["end"]["v"] - 1] if h else p["verses"][0]
        text = v["text"][h["end"]["offset"]:] if h else v["text"]
        if h and not text.strip() and h["end"]["v"] < len(p["verses"]):
            text = p["verses"][h["end"]["v"]]["text"]
        ws = [norm(w.skeleton) for w in tokenize(text)][:2]
        openings[tuple(ws)] = openings.get(tuple(ws), []) + [n]
        firsts[ws[0]] = firsts.get(ws[0], []) + [n]
        if h:
            hw = tuple(norm(w.skeleton) for w in tokenize(h["text"])[:2])
            headings[hw] = headings.get(hw, []) + [n]
    global FIRST
    FIRST = {k: v[0] for k, v in firsts.items() if len(v) == 1}
    return ({k: v[0] for k, v in openings.items() if len(v) == 1},
            {k: v[0] for k, v in headings.items() if len(v) == 1})


FIRST: dict = {}


OPEN, HEAD = None, None
NUM = {"\u05DA": 20, "\u05DD": 40, "\u05DF": 50, "\u05E3": 80, "\u05E5": 90}  # final letters
NUM.update({c: v for v, c in [(1, "א"), (2, "ב"), (3, "ג"), (4, "ד"), (5, "ה"), (6, "ו"), (7, "ז"), (8, "ח"), (9, "ט"),
                          (10, "י"), (20, "כ"), (30, "ל"), (40, "מ"), (50, "נ"), (60, "ס"), (70, "ע"), (80, "פ"),
                          (90, "צ"), (100, "ק")]})


def numerals(text: str) -> list[int]:
    out = []
    for tok in re.findall(r"[א-ת]+(?:[\"'׳״][א-ת]?)", text):
        letters = re.sub(r"[\"'׳״]", "", tok)
        if letters and all(c in NUM for c in letters):
            v = sum(NUM[c] for c in letters)
            if 1 <= v <= 150 and hebrew_numeral(v) == normalize_finals(letters):
                out.append(v)
    return out


def psalms_in(text: str) -> list[int]:
    """Psalms named in a quotation: explicit refs, numeral lists, or quoted openings."""
    global OPEN, HEAD
    if OPEN is None:
        OPEN, HEAD = psalm_openings()
    found = []
    for m in re.finditer(r"\(תהלים ([א-ת\"'׳״]+)", text):
        found += numerals(m.group(1) + "'") or numerals(m.group(1))
    if re.search(r"מזמורים|מזמור [א-ת]+[\"'׳״]", text):
        tail = text[re.search(r"מזמורים|מזמור [א-ת]+[\"'׳״]", text).start():]
        found += numerals(tail)
    ws = [norm(w.skeleton) for w in tokenize(text)]
    ws = ["מזמר" if w.endswith("מזמר") and len(w) <= 6 else w for w in ws]  # "שמזמור" -> "מזמור"
    for a, b in zip(ws, ws[1:]):
        if a == "מזמר" and b in FIRST:  # "מזמור יענך": a psalm named by its (unique) first word
            found.append(FIRST[b])
        if (a, b) in OPEN:
            found.append(OPEN[(a, b)])
        if (a, b) in HEAD:
            found.append(HEAD[(a, b)])
    out = []
    for n in found:
        if n not in out:
            out.append(n)
    return out


def plain(t) -> str:
    if isinstance(t, list):
        t = " ".join(plain(x) for x in t)
    return re.sub(r"\s+", " ", strip_marks(re.sub(r"<[^>]+>", "", t))).strip()


def fetch_sefaria(refs, version, end):
    segs, meta = [], {}
    for r in refs:
        d = sefaria.get_json(f"v3/texts/{r}", {"version": "hebrew" + (f"|{version}" if version else "")})
        v = d["versions"][0]
        raw = plain(v["text"])
        if end and end in raw:
            raw = raw[: raw.index(end) + len(end)]
        segs.append({"ref": r, "he_ref": d.get("heRef", ""), "text": quotes.mask_quoted(raw)})
        meta = {"version": v.get("versionTitle", ""), "license": v.get("license", "")}
        del raw
    return segs, meta


def fetch_shimush() -> list[dict]:
    """Shimush Tehillim (Hebrew Wikisource): per psalm, the opening of its stated use."""
    url = "https://he.wikisource.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": "שמוש תהלים/הכל", "prop": "text", "format": "json", "formatversion": "2"})
    html = json.loads(sefaria.get_text(url))["parse"]["text"]
    out = []
    for m in re.finditer(r"<h2[^>]*>.*?פרק ([א-ת]+).*?</h2>(.*?)(?=<h2|\Z)", html, re.S):
        n = sum(NUM.get(c, 0) for c in m.group(1))
        body = html_mod.unescape(html_mod.unescape(plain(re.sub(r"<sup.*?</sup>", "", m.group(2)))))
        body = re.sub(r"[‪-‮]|&(?:amp;)*#\d+;", " ", body).strip()
        if not body or "חסר" in body[:40]:
            continue
        words = body.split()
        # the use comes after the psalm's opening words: from the first '.' or ',' on
        cut = re.search(r"[.,׳]\s", body[:120])
        use = body[cut.end():] if cut else body
        # quote only the stated use: stop before letter combinations ("ושם שלו ...") and prayers
        use = re.split(r"(?:ו?שם שלו|ו?השם|יהי רצון|כיצד)", use)[0].strip(" ,.:׃")
        if not use or len(re.findall(r"\([\u05D0-\u05EA]{1,3}\)", use)) >= 2:
            continue  # empty, or a list of other psalms rather than a use
        snippet = " ".join(use.split()[:16])
        out.append({"psalm": n, "text": quotes.mask_quoted(snippet) + ("…" if len(use.split()) > 16 else ""),
                    "_kw": use})
        del body, use
    return out


def main() -> int:
    needs = {n["id"]: {**{k: v for k, v in n.items() if k != "kw"}, "sources": [], "shimush": []} for n in NEEDS}
    for need, refs, version, _start, end, title in SOURCES:
        segs, meta = fetch_sefaria(refs, version, end)
        text = " ".join(s["text"] for s in segs)
        needs[need]["sources"].append({
            "title": title, "segments": segs, **meta,
            "url": "https://www.sefaria.org/" + refs[0] + "?lang=he",
            "psalms": psalms_in(text),
        })
    shimush = fetch_shimush()
    for e in shimush:
        for n in NEEDS:
            if any(re.search(rf"(^|\s)[ולבהמש]?{k}($|[\s,.:׃])", e["_kw"]) for k in n["kw"]):
                needs[n["id"]]["shimush"].append({"psalm": e["psalm"], "text": e["text"]})
    doc = {
        "_note": ("מזמורים לעניינים, רק מתוך מקורות שנשלפו. המזמורים של כל מקור נקראו מתוך לשונו (מספרים, הפניות "
                  "או פתיחת המזמור). שמוש תהלים מוויקיטקסט מסווג לפי מילים בלשונו. status: auto."),
        "shimush_source": {"title": "שמוש תהלים", "url": "https://he.wikisource.org/wiki/" + urllib.parse.quote("שמוש_תהלים"),
                           "license": "CC BY-SA 4.0 (ויקיטקסט)"},
        "needs": list(needs.values()),
    }
    (ROOT / "data" / "inyanim.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for n in doc["needs"]:
        print(n["id"], [(s["title"], s["psalms"]) for s in n["sources"]], [x["psalm"] for x in n["shimush"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
