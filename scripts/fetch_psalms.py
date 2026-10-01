"""Fetch the 150 psalms from Sefaria, mask the holy names in memory, count
them, parse the superscriptions, and write data/psalms/NNN.json.

Usage:  python scripts/fetch_psalms.py [N ...]

Nothing unmasked is ever written to disk or printed.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import names  # noqa: E402
import sefaria  # noqa: E402
from hebrew import SAMEKH, LAMED, HE, tokenize  # noqa: E402
from heading_vocab import parse_heading  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "psalms"
CHOL = ROOT / "data" / "annotations" / "chol_names.json"

BOOKS = [(1, 1, 41), (2, 42, 72), (3, 73, 89), (4, 90, 106), (5, 107, 150)]
SELAH = SAMEKH + LAMED + HE


def book_of(n: int) -> int:
    return next(b for b, lo, hi in BOOKS if lo <= n <= hi)


# --- Sefaria markup ----------------------------------------------------------
def clean(v: str) -> tuple[str, bool]:
    """Strip MAM HTML. Returns (text, ends_with_petucha_or_setuma).

    Ketiv is kept in (round) brackets and qeri in [square] brackets, as in
    the plain MAM presentation; paseq/legarmeih is kept as U+05C0.
    """
    para = bool(re.search(r'class="mam-spi-(pe|samekh)"', v))
    v = re.sub(r'<span class="mam-spi-[^"]*">\{.\}</span>', "", v)
    v = re.sub(r"<br\s*/?>", " ", v)
    v = re.sub(r"<[^>]+>", "", v)
    v = v.replace("&thinsp;", " ").replace("&nbsp;", " ")
    v = re.sub(r"\s+", " ", v).strip()
    return v, para


def ktiv_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(r"\([^)]*\)", text)]


# --- chol annotations --------------------------------------------------------
def load_chol() -> dict:
    if CHOL.exists():
        return json.loads(CHOL.read_text(encoding="utf-8"))
    return {"approved": False, "entries": []}


DOUBTFUL = {  # (psalm, verse, occurrence-in-verse): reason
    (82, 1, 2): "ספק — הוזכר באפיון (סעיף 0.1) כמקרה מסופק",
    (82, 6, 0): "ספק — הוזכר באפיון (סעיף 0.1) כמקרה מסופק",
}
REASONS = {
    "next-word": "המילה הבאה (למשל העמים / אחרים / זר / נכר)",
    "after-kol": "בא אחרי \"כל\" או \"כמוך\"",
    "construct-chain": "סמיכות אחרי שם (\"... ה...\")",
    "not-after-name": "צ-באות שאינו סמוך לשם",
}


# --- per psalm ---------------------------------------------------------------
def process(n: int, raw_verses: list[str], chol_status: dict) -> tuple[dict, list[dict]]:
    verses, candidates = [], []
    names_count = Counter()
    forms = {t: Counter() for t in names.TYPES}
    combos = Counter()
    selah = 0
    paragraph_after = []
    raw_clean = []

    for vi, rv in enumerate(raw_verses, start=1):
        text, para = clean(rv)
        if para:
            paragraph_after.append(vi)
        raw_clean.append(text)
        words = tokenize(text)
        ms = names.detect(text, words)
        real = sorted([m for m in ms if m.type != names.HALLELUYAH], key=lambda m: m.word)

        keep = set()
        for occ, m in enumerate(real):
            key = (n, vi, occ)
            status = chol_status.get(key)
            if status is None and key in DOUBTFUL:
                status = "doubtful"
            if status is None and m.chol_reason:
                status = "candidate"
            if status == "approved_chol":
                keep.add(m.word)
            if status:
                candidates.append({"psalm": n, "verse": vi, "occurrence": occ, "type": m.type,
                                   "word": m.word, "status": status,
                                   "reason": DOUBTFUL.get(key) or REASONS.get(m.chol_reason or "", "")})

        masked, entries = names.mask(text, ms, keep)
        kspans = ktiv_spans(masked)
        prev_word = None
        prev_entry = None
        for e, m in zip(entries, real):
            e["ktiv"] = any(a <= e["start"] < b for a, b in kspans)
            counted = not e["chol"] and not e["ktiv"]
            e["counted"] = counted
            if counted:
                names_count[e["type"]] += 1
                forms[e["type"]][e["suffix"] or "base"] += 1
                if prev_entry is not None and prev_word == e["word"] - 1:
                    combos[f"{prev_entry['type']}+{e['type']}"] += 1
                prev_entry, prev_word = e, e["word"]
        # candidates get the masked form for review
        for c in candidates:
            if c["psalm"] == n and c["verse"] == vi and "form" not in c:
                e = next(x for x in entries if x["word"] == c["word"])
                c["form"] = masked[e["start"]:e["end"]]
                c["context"] = masked
        selah += sum(1 for w in words if w.skeleton == SELAH)
        verses.append({"v": vi, "text": masked, "names": entries})

    heading = parse_heading(n, raw_clean, verses)
    doc = {
        "n": n,
        "book": book_of(n),
        "heading": heading,
        "verse_count": len(verses),
        "verses": verses,
        "paragraph_after": paragraph_after,
        "names_count": {t: names_count.get(t, 0) for t in names.TYPES},
        "names_forms": {t: dict(forms[t]) for t in names.TYPES if forms[t]},
        "names_combos": dict(combos),
        "selah_count": selah,
        "doublet_of": None,
        "liturgy": [],
        "sources": {
            "text": f"sefaria:Psalms.{n}",
            "version": sefaria.MAM,
            "license": "CC-BY-SA",
            "url": f"https://www.sefaria.org/Psalms.{n}?lang=he",
        },
    }
    return doc, candidates


def main(argv: list[str]) -> int:
    only = [int(a) for a in argv] or list(range(1, 151))
    shape = sefaria.get_json("shape/Psalms")
    shape = shape[0] if isinstance(shape, list) else shape
    lengths = shape["chapters"]

    chol = load_chol()
    chol_status = {(e["psalm"], e["verse"], e["occurrence"]): e["status"]
                   for e in chol.get("entries", []) if e.get("status") in ("approved_chol", "rejected")}

    def fetch(n):
        return n, sefaria.psalm_raw(n)["versions"][0]["text"]

    OUT.mkdir(parents=True, exist_ok=True)
    all_candidates = [e for e in chol.get("entries", []) if e["psalm"] not in only]
    problems = []
    with cf.ThreadPoolExecutor(3) as ex:
        for n, raw in ex.map(fetch, only):
            doc, cands = process(n, raw, chol_status)
            del raw
            if doc["verse_count"] != lengths[n - 1]:
                problems.append(f"psalm {n}: {doc['verse_count']} verses, Sefaria shape says {lengths[n - 1]}")
            all_candidates.extend(cands)
            (OUT / f"{n:03d}.json").write_text(
                json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    all_candidates.sort(key=lambda e: (e["psalm"], e["verse"], e["occurrence"]))
    chol_doc = {
        "_note": ("מופעים שעשויים להיות שמות חול. נבנה חישובית ומחכה לאישור בעל הפרויקט. "
                  "status: candidate / doubtful = עדיין בכינוי ונספר כקודש; approved_chol = נכתב כלשונו "
                  "ואינו נספר; rejected = נשאר קודש. לאחר שינוי יש להריץ שוב את fetch_psalms.py."),
        "approved": chol.get("approved", False),
        "entries": all_candidates,
    }
    CHOL.parent.mkdir(parents=True, exist_ok=True)
    CHOL.write_text(json.dumps(chol_doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    for p in problems:
        print("WARNING:", p)
    print(f"wrote {len(only)} psalms; {len(all_candidates)} chol candidates")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
