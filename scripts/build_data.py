"""Derive book-level data from data/psalms: books.json, names_stats.json, doublets.json.

Offline: reads only committed (masked) data.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hebrew import tokenize  # noqa: E402
from names import TYPES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

BOOKS = [
    {"n": 1, "first": 1, "last": 41, "closing": [{"psalm": 41, "verses": [14]}]},
    {"n": 2, "first": 42, "last": 72, "closing": [{"psalm": 72, "verses": [18, 19, 20]}],
     "note_verse": {"psalm": 72, "verse": 20}},
    {"n": 3, "first": 73, "last": 89, "closing": [{"psalm": 89, "verses": [53]}]},
    {"n": 4, "first": 90, "last": 106, "closing": [{"psalm": 106, "verses": [48]}]},
    {"n": 5, "first": 107, "last": 150, "closing": []},
]

# Doublets named in the spec (§5). Ranges are in the Hebrew verse numbering.
KNOWN_DOUBLETS = [
    {"id": "14-53", "a": [{"psalm": 14, "from": 1, "to": 7}], "b": [{"psalm": 53, "from": 1, "to": 7}]},
    {"id": "40-70", "a": [{"psalm": 40, "from": 14, "to": 18}], "b": [{"psalm": 70, "from": 1, "to": 6}]},
    {"id": "108-57-60", "a": [{"psalm": 108, "from": 1, "to": 14}],
     "b": [{"psalm": 57, "from": 8, "to": 12}, {"psalm": 60, "from": 7, "to": 14}]},
]


def load_psalms() -> list[dict]:
    return [json.loads((DATA / "psalms" / f"{n:03d}.json").read_text(encoding="utf-8")) for n in range(1, 151)]


def verse_tokens(v: dict) -> list[str]:
    """Normalized tokens: consonant skeletons; every name collapses to its type."""
    spans = [(e["start"], e["end"], e["type"]) for e in v["names"]]
    out, last_span = [], None
    for w in tokenize(v["text"]):
        span = next((s for s in spans if s[0] <= w.start < s[1]), None)
        if span is not None:
            if span is not last_span:
                out.append("§" + span[2])
            last_span = span
            continue
        last_span = None
        out.append(w.skeleton)
    return out


def generic(tokens: list[str]) -> list[str]:
    return ["§" if t.startswith("§") else t for t in tokens]


def find_doublets(psalms: list[dict]) -> list[dict]:
    """Runs of highly similar consecutive verses in different psalms."""
    def heading_only(p, v):
        h = p["heading"]
        return bool(h and h["own_verse"] and v["v"] <= h["end"]["v"])

    verses = [(p["n"], v["v"], generic(verse_tokens(v))) for p in psalms for v in p["verses"]
              if not heading_only(p, v)]
    index = defaultdict(set)
    for i, (_, _, t) in enumerate(verses):
        for bg in zip(t, t[1:]):
            index[bg].add(i)
    pairs = {}
    for i, (pn, vn, t) in enumerate(verses):
        if len(t) < 4:
            continue
        shared = Counter()
        for bg in set(zip(t, t[1:])):
            for j in index[bg]:
                if j > i and verses[j][0] != pn:
                    shared[j] += 1
        for j, c in shared.items():
            if c < 3:
                continue
            r = SequenceMatcher(None, t, verses[j][2], autojunk=False).ratio()
            if r >= 0.7:
                pairs[(pn, vn, verses[j][0], verses[j][1])] = r
    # chain consecutive pairs into runs
    runs, seen = [], set()
    for (a, va, b, vb) in sorted(pairs):
        if (a, va, b, vb) in seen:
            continue
        run = [(va, vb, pairs[(a, va, b, vb)])]
        seen.add((a, va, b, vb))
        k = 1
        while (a, va + k, b, vb + k) in pairs:
            run.append((va + k, vb + k, pairs[(a, va + k, b, vb + k)]))
            seen.add((a, va + k, b, vb + k))
            k += 1
        runs.append({"a": a, "b": b, "a_from": run[0][0], "a_to": run[-1][0],
                     "b_from": run[0][1], "b_to": run[-1][1], "verses": len(run),
                     "mean_similarity": round(sum(x[2] for x in run) / len(run), 3)})
    runs.sort(key=lambda r: (-r["verses"], -r["mean_similarity"]))
    return runs


LETTER_SLUGS = ["alef", "bet", "gimel", "dalet", "he", "vav", "zayin", "het", "tet", "yod", "kaf",
                "lamed", "mem", "nun", "samekh", "ayin", "pe", "tsadi", "qof", "resh", "shin", "tav"]
ALEFBET = [chr(c) for c in range(0x05D0, 0x05EB) if chr(c) not in "\u05DA\u05DD\u05DF\u05E3\u05E5"]


def chida(psalms: list[dict]) -> dict:
    """Every verse of the book, grouped by the first letter of the verse as written."""
    groups = {c: [] for c in ALEFBET}
    for p in psalms:
        for v in p["verses"]:
            words = tokenize(v["text"])
            first = words[0].letters[0].ch
            # The masked form of HAVAYAH starts with a different letter than the word itself.
            if any(e["start"] == words[0].start and e["type"] == "HAVAYAH" and not e["prefix"] for e in v["names"]):
                first = "\u05D9"
            groups[first].append({"psalm": p["n"], "verse": v["v"]})
    return {
        "_note": ("תהלים החיד\"א: כל פסוקי הספר מסודרים לפי האות הראשונה של הפסוק. "
                  "הכלל כאן: האות הראשונה של הפסוק כפי שהוא כתוב, כולל פסוקי כותרת. ממתין לאישור בעל הפרויקט."),
        "rule": "first-letter-as-written",
        "letters": [{"letter": c, "slug": LETTER_SLUGS[i], "count": len(groups[c]), "verses": groups[c]}
                    for i, c in enumerate(ALEFBET)],
    }


def main() -> int:
    psalms = load_psalms()

    # names per psalm and per book
    per_psalm = []
    for p in psalms:
        c = p["names_count"]
        h, e = c["HAVAYAH"], c["ELOKIM"]
        per_psalm.append({"n": p["n"], "book": p["book"], "counts": c,
                          "havayah_share": round(h / (h + e), 4) if h + e else None})
    per_book = []
    for b in BOOKS:
        tot = Counter()
        for p in psalms[b["first"] - 1:b["last"]]:
            tot.update(p["names_count"])
        per_book.append({"book": b["n"], "counts": {t: tot.get(t, 0) for t in TYPES}})
    seg = {"42-83": Counter(), "rest": Counter()}
    for p in psalms:
        seg["42-83" if 42 <= p["n"] <= 83 else "rest"].update(p["names_count"])
    totals = Counter()
    combos = Counter()
    for p in psalms:
        totals.update(p["names_count"])
        combos.update(p["names_combos"])
    stats = {
        "per_psalm": per_psalm,
        "per_book": per_book,
        "segments": {k: {t: v.get(t, 0) for t in TYPES} for k, v in seg.items()},
        "totals": {t: totals.get(t, 0) for t in TYPES},
        "combos": dict(combos.most_common()),
        "uncounted": {
            "halleluyah_and_chol": "הללויה ושמות חול שאושרו אינם נספרים",
            "ktiv": "מופע בכתיב (בסוגריים עגולים) אינו נספר; נספר הקרי",
        },
    }

    books = []
    for b in BOOKS:
        ps = psalms[b["first"] - 1:b["last"]]
        books.append({**b, "count": len(ps), "verses": sum(p["verse_count"] for p in ps)})

    computed = find_doublets(psalms)
    known_pairs = {(14, 53), (40, 70), (57, 108), (60, 108)}
    for r in computed:
        r["status"] = "known" if (r["a"], r["b"]) in known_pairs else "candidate"
    doublets = {
        "_note": "known = מופיע באפיון. candidate = נמצא חישובית לפי דמיון של פסוקים רצופים; ממתין לאישור.",
        "known": KNOWN_DOUBLETS,
        "computed": computed,
    }
    doublet_of = {}
    for d in KNOWN_DOUBLETS:
        for side, other in (("a", "b"), ("b", "a")):
            for r in d[side]:
                doublet_of.setdefault(r["psalm"], []).append(d["id"])

    def dump(name, obj):
        (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    dump("books.json", books)
    dump("names_stats.json", stats)
    dump("doublets.json", doublets)
    dump("chida.json", chida(psalms))

    for p in psalms:  # back-link doublets into the psalm files
        new = doublet_of.get(p["n"])
        if p["doublet_of"] != new:
            p["doublet_of"] = new
            (DATA / "psalms" / f"{p['n']:03d}.json").write_text(
                json.dumps(p, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"books, stats, {len(computed)} doublet runs ({sum(r['status'] == 'candidate' for r in computed)} candidates)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
