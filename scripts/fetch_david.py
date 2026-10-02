"""The David lens: psalms whose heading names an event in David's life.

For every such psalm, collects from Sefaria:
- the links between the heading verse(s) and the books of Samuel;
- Rashi's and Radak's comments on the heading, with their own Samuel links;
- the text of the Samuel passage (masked).
The Samuel mapping comes only from those links, never from memory.
Writes data/david_events.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import quotes  # noqa: E402
import sefaria  # noqa: E402
from heading_vocab import EVENT_PSALMS  # noqa: E402
from hebrew import strip_marks, tokenize  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SAMUEL = {"I Samuel": "שמואל א", "II Samuel": "שמואל ב"}
COMMENTATORS = {"Rashi": "רש\"י", "Radak": "רד\"ק"}


def flat(t) -> str:
    if isinstance(t, str):
        return t
    return " ".join(flat(x) for x in t)


def plain(html: str) -> str:
    return re.sub(r"\s+", " ", strip_marks(re.sub(r"<[^>]+>", "", html))).strip()


def samuel_links(ref: str) -> list[str]:
    links = sefaria.get_json(f"links/{ref.replace(' ', '_')}", {"with_text": 0})
    out = []
    for l in links:
        if l.get("index_title") in SAMUEL and l["ref"] not in out:
            out.append(l["ref"])
    return out


_PREFIX = re.compile("^[\u05D5\u05D4\u05D1\u05DC\u05DE\u05DB\u05E9]{1,2}(?=...)")


def words_of(text: str) -> set[str]:
    """Consonant skeletons with common prefix letters removed, for a rough overlap score."""
    return {_PREFIX.sub("", w.skeleton) for w in tokenize(text) if len(w.skeleton) > 1}


def overlap(heading: set[str], verses: list[dict]) -> int:
    return len(heading & set().union(*(words_of(v["text"]) for v in verses))) if verses else 0


def ref_key(ref: str) -> tuple:
    m = re.match(r"(I+) Samuel (\d+)(?::(\d+))?", ref)
    return (len(m[1]), int(m[2]), int(m[3] or 0)) if m else (9, 0, 0)


def he_ref(ref: str) -> str:
    m = re.match(r"(I+ Samuel) (.+)$", ref)
    return f"{SAMUEL[m[1]]} {m[2]}" if m else ref


_VALID: dict[str, bool] = {}


def valid(ref: str) -> bool:
    """Some Sefaria links point at verses that do not exist; drop those."""
    if ref not in _VALID:
        try:
            sefaria.get_json(f"v3/texts/{ref.replace(' ', '_')}", {"version": f"hebrew|{sefaria.MAM}"}, tries=2)
            _VALID[ref] = True
        except Exception:
            _VALID[ref] = False
    return _VALID[ref]


_VALID: dict[str, bool] = {}


def valid(ref: str) -> bool:
    """Some Sefaria links point at verses that do not exist; drop those."""
    if ref not in _VALID:
        try:
            sefaria.get_json(f"v3/texts/{ref.replace(' ', '_')}", {"version": f"hebrew|{sefaria.MAM}"}, tries=2)
            _VALID[ref] = True
        except Exception:
            _VALID[ref] = False
    return _VALID[ref]


_VALID: dict[str, bool] = {}


def valid(ref: str) -> bool:
    """Some Sefaria links point at verses that do not exist; drop those."""
    if ref not in _VALID:
        try:
            sefaria.get_json(f"v3/texts/{ref.replace(' ', '_')}", {"version": f"hebrew|{sefaria.MAM}"}, tries=2)
            _VALID[ref] = True
        except Exception:
            _VALID[ref] = False
    return _VALID[ref]


def samuel_text(ref: str) -> list[dict]:
    d = sefaria.get_json(f"v3/texts/{ref.replace(' ', '_')}", {"version": f"hebrew|{sefaria.MAM}"})
    v = d["versions"][0]["text"]
    verses = v if isinstance(v, list) else [v]
    start = d.get("sections", [0, 1])
    first = int(start[1]) if len(start) > 1 else 1
    out = []
    for i, t in enumerate(verses):
        if isinstance(t, list):
            t = flat(t)
        t = re.sub(r'<span class="mam-spi-[^"]*">\{.\}</span>', "", t)
        raw = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t).replace("&thinsp;", " ").replace("&nbsp;", " ")).strip()
        out.append({"v": first + i, "text": quotes.mask_quoted(raw)})
        del raw
    return out


def context_ref(ref: str) -> str:
    """A single linked verse, widened to the few verses before it (where places are usually named)."""
    m = re.match(r"(I+ Samuel) (\d+):(\d+)$", ref)
    if not m:
        return ref
    v = int(m[3])
    return f"{m[1]} {m[2]}:{max(1, v - 4)}-{v}"


_SAM_INDEX: dict | None = None


def samuel_index() -> dict:
    """Trigram index of the books of Samuel (masked text, letters only): trigram -> refs."""
    global _SAM_INDEX
    if _SAM_INDEX is None:
        _SAM_INDEX = {}
        for book in SAMUEL:
            shape = sefaria.get_json(f"shape/{book.replace(' ', '_')}")
            chapters = (shape[0] if isinstance(shape, list) else shape)["chapters"]
            for ch in range(1, len(chapters) + 1):
                for v in samuel_text(f"{book} {ch}"):
                    sk = [w.skeleton for w in tokenize(v["text"])]
                    for tri in zip(sk, sk[1:], sk[2:]):
                        _SAM_INDEX.setdefault(" ".join(tri), set()).add(f"{book} {ch}:{v['v']}")
    return _SAM_INDEX


def quoted_verse(text: str) -> tuple[str, str] | None:
    """The single Samuel verse whose wording a commentary quotes (three words in a row, rare in Samuel)."""
    idx = samuel_index()
    sk = [w.skeleton for w in tokenize(text)]
    hits: dict[str, list[str]] = {}
    for tri in zip(sk, sk[1:], sk[2:]):
        key = " ".join(tri)
        refs = idx.get(key, set())
        if 0 < len(refs) <= 2 and all(len(t) > 1 for t in tri):
            for r in refs:
                hits.setdefault(r, []).append(key)
    if not hits:
        return None
    best = max(hits.values(), key=len)
    winners = [r for r, h in hits.items() if len(h) == len(best)]
    return (winners[0], best[0]) if len(winners) == 1 else None


def find_places(text: str, places: list[dict]) -> list[str]:
    """Place ids whose name (one or two words, letters only) occurs in the text."""
    skels = [w.skeleton for w in tokenize(text)]
    skels += [k[1:] for k in skels if len(k) > 3 and k[0] in "\u05D1\u05D5\u05DC\u05DE\u05D4"]  # בירושלם → ירושלם
    pairs = {a + " " + b for a, b in zip(skels, skels[1:])} | {a + b for a, b in zip(skels, skels[1:])}
    found = []
    for pl in places:
        if any(m in skels or m in pairs for m in pl["match"]):
            found.append(pl["id"])
    return found


def main() -> int:
    places = json.loads((ROOT / "data" / "places.json").read_text(encoding="utf-8"))["places"]
    psalms = {n: json.loads((ROOT / "data" / "psalms" / f"{n:03d}.json").read_text(encoding="utf-8"))
              for n in EVENT_PSALMS}
    events = []
    for n in sorted(EVENT_PSALMS):
        h = psalms[n]["heading"]
        hverses = list(range(1, h["end"]["v"] + 1))
        direct = []
        for v in hverses:
            for r in samuel_links(f"Psalms {n}:{v}"):
                if r not in direct:
                    direct.append(r)
        comments = []
        for en, he in COMMENTATORS.items():
            for v in hverses:
                ref = f"{en} on Psalms {n}:{v}"
                try:
                    d = sefaria.get_json(f"v3/texts/{ref.replace(' ', '_')}", {"version": "hebrew"}, tries=2)
                except Exception:  # no comment on this verse
                    continue
                ver = d["versions"][0] if d.get("versions") else None
                if not ver:
                    continue
                segs = ver["text"] if isinstance(ver["text"], list) else [ver["text"]]
                for i, seg in enumerate(segs, start=1):
                    text = quotes.mask_quoted(plain(flat(seg)))
                    if not text:
                        continue
                    sref = f"{ref}:{i}"
                    comments.append({
                        "commentator": he, "ref": sref, "text": text,
                        "samuel": samuel_links(sref),
                        "version": ver.get("versionTitle", ""), "license": ver.get("license", ""),
                        "url": "https://www.sefaria.org/" + sref.replace(" ", "_") + "?lang=he",
                    })
        invalid = [r for r in direct if not valid(r)]
        direct = [r for r in direct if r not in invalid]
        texts = {r: samuel_text(r) for r in direct}
        heading_words = words_of(h["historical_event"] or "")
        scored = sorted(direct, key=lambda r: (-overlap(heading_words, texts[r]), ref_key(r)))
        primary = scored[:1]
        origin = "sefaria-link" if primary else None
        placement = primary[0] if primary else None
        if not primary:
            # no direct link: a commentary whose links all point to one chapter of Samuel
            for c in comments:
                ok = sorted((r for r in c["samuel"] if valid(r)), key=ref_key)
                if ok and len({ref_key(r)[:2] for r in ok}) == 1:
                    placement, origin = ok[0], f"commentary:{c['commentator']}"
                    break
        if not placement:
            # still nothing: a commentary that quotes the wording of a verse in Samuel
            for c in comments:
                hit = quoted_verse(c["text"])
                if hit:
                    placement, origin = hit[0], f"commentary-quote:{c['commentator']}"
                    c["quotes_samuel"] = {"ref": hit[0], "phrase": hit[1]}
                    break
        passages = [{"ref": r, "he_ref": he_ref(r), "verses": texts[r], "score": overlap(heading_words, texts[r]),
                     "url": "https://www.sefaria.org/" + r.replace(" ", "_") + "?lang=he"} for r in scored]
        if not passages and placement and ":" in placement:
            passages = [{"ref": placement, "he_ref": he_ref(placement), "verses": samuel_text(placement), "score": 0,
                         "url": "https://www.sefaria.org/" + placement.replace(" ", "_") + "?lang=he"}]
        # places: from the heading's wording, else from the linked Samuel passage
        where, where_from = find_places(h["historical_event"] or "", places), "heading"
        if not where and passages:
            ctx_ref = context_ref(passages[0]["ref"])
            ctx = samuel_text(ctx_ref) if ctx_ref != passages[0]["ref"] else passages[0]["verses"]
            where, where_from = find_places(" ".join(v["text"] for v in ctx), places), f"samuel:{ctx_ref}"
        events.append({
            "places": where,
            "places_from": where_from if where else None,
            "psalm": n,
            "heading_event": h["historical_event"],
            "heading_verses": hverses,
            "samuel_direct": direct,
            "samuel_invalid_links": invalid,
            "samuel_invalid_links": invalid,
            "samuel_invalid_links": invalid,
            "samuel_primary": primary,
            "samuel_placement": placement,
            "samuel_origin": origin,
            "order": list(ref_key(placement)) if placement else None,
            "passages": passages,
            "comments": comments,
            "status": "auto",
        })
    doc = {
        "_note": ("אירועים מחיי דוד שבכותרות. המיפוי לשמואל לקוח מקישורי ספריא לפסוקי הכותרת, ואם אין כאלה "
                  "מקישורי פירושי רש\"י ורד\"ק על הכותרת. status: auto = טרם אומת ידנית."),
        "events": events,
    }
    (ROOT / "data" / "david_events.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for e in events:
        print(e["psalm"], e["samuel_primary"], e["samuel_placement"], e["samuel_origin"],
              [(p["ref"], p["score"]) for p in e["passages"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
