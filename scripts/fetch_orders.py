"""Network: which whole psalms each prayer order contains, read from the siddur text.

For every order and nusach, the siddur sections on Sefaria are read in order and
each psalm is found by its own words: the opening of its first (or second) verse,
followed within the expected length by the end of its last verse. A passage that
only quotes part of a psalm (the verses of Hodu from Chronicles, for example) is
therefore not counted. The siddur's own instruction printed just before a psalm
("בעשרת ימי תשובה מוסיפין") is kept verbatim when it limits the psalm to a time
or a custom.

Writes data/orders.json. Text from Sefaria is masked before anything is stored.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import names  # noqa: E402
import sefaria  # noqa: E402
from hebrew import normalize_finals, strip_marks  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
A, S, E = "Siddur Ashkenaz", "Siddur Sefard", "Siddur Edot HaMizrach"
TITLES = {"ashkenaz": A, "sefard": S, "edot": E}

# order slug -> nusach -> siddur nodes (every leaf under each prefix, in siddur order)
ORDERS = {
    "kabbalat-shabbat": {"ashkenaz": [f"{A}, Shabbat, Kabbalat Shabbat"],
                         "sefard": [f"{S}, Kabbalat Shabbat"],
                         "edot": [f"{E}, Kabbalat Shabbat"]},
    "pesukei-dezimra": {"ashkenaz": [f"{A}, Weekday, Shacharit, Pesukei Dezimra"],
                        "sefard": [f"{S}, Weekday Shacharit, Hodu", f"{S}, Weekday Shacharit, Yishtabach"],
                        "edot": [f"{E}, Weekday Shacharit, Hodu", f"{E}, Weekday Shacharit, Pesukei D'Zimra"]},
    "pesukei-dezimra-shabbat": {"ashkenaz": [f"{A}, Shabbat, Shacharit, Pesukei Dezimra"],
                                "sefard": [f"{S}, Shabbat Morning Services, Pesukei D'Zimrah"],
                                "edot": [f"{E}, Shabbat Shacharit, Psalms for Shabbat",
                                         f"{E}, Shabbat Shacharit, Pesukei D'Zimra"]},
    "tachanun": {"ashkenaz": [f"{A}, Weekday, Shacharit, Post Amidah, Tachanun, Nefilat Apayim"],
                 "sefard": [f"{S}, Weekday Shacharit, Tachanun"],
                 "edot": [f"{E}, Weekday Shacharit, Vidui"]},
    "kriat-shema-al-hamita": {"ashkenaz": [f"{A}, Weekday, Maariv, Keri'at Shema al Hamita"],
                              "sefard": [f"{S}, Bedtime Shema"],
                              "edot": [f"{E}, Bedtime Shema"]},
    "birkat-hamazon": {"ashkenaz": [f"{A}, Berachot, Birkat HaMazon"],
                       "sefard": [f"{S}, Birchat HaMazon, Birchat HaMazon"],
                       "edot": [f"{E}, Post Meal Blessing"]},
    "birkat-halevana": {"ashkenaz": [f"{A}, Weekday, Maariv, Birkat HaLevana"],
                        "sefard": [f"{S}, Kiddush Levanah"],
                        "edot": [f"{E}, Blessing of the Moon"]},
    "motzaei-shabbat": {"ashkenaz": [f"{A}, Weekday, Maariv, Additions for Motza'ei Shabbat"],
                        "sefard": [f"{S}, Weekday Maariv, Motzaei Shabbat"],
                        # inside weekday Arvit, from the rubric for Motzaei Shabbat to the Kaddish after it
                        "edot": [(f"{E}, Weekday Arvit, Amidah", "במוצאי שבת אומרים", "קדיש תתקבל")]},
    "tikkun-chatzot": {"edot": [f"{E}, The Midnight Rite"]},
}

# Orders where a psalm is said only in part by custom, as the siddur prints it:
# (order, nusach) -> psalms to read as an opening run of verses.
PARTIAL = {("kriat-shema-al-hamita", "edot"): {91}}

NIQQUD = re.compile(r"[֑-ׇ]")
# Names (and their look-alikes, such as the preposition) are left out on both sides,
# so a name written in full, abbreviated or as a kinui compares the same.
NAMEISH = re.compile("^[" + "".join(sorted(names.PREFIX_LETTERS)) + "]{0,3}(?:" + "|".join(
    [names._HAVAYAH, names._YAH, names._EL, names._ELOAH, names._ELOK + "\\w*", *names._ADNI,
     names._SHADDAI, names._TZVAOT]) + ")$")
CONDITION = re.compile(r"(^|\s)(ב|וב)(עשרת|שבת|ראש|יום|ימי|ימים|חנוכה|פורים|חול|ערב|מוצאי|תשעה|תענית|צום|בית)"
                       r"|נוהגים|נוהגין|יש אומרים|מנהג|אם חל")
SAYS = re.compile(r"אומרים|אומרין|מוסיפים|מוסיפין|לומר|יאמר|מדלגים")
OTHER = re.compile(r"שליח הציבור|ש\"ץ|עננו|ממשיכים")


def leaves(title: str) -> list[str]:
    d = sefaria.get_json("v2/index/" + title.replace(" ", "_"))
    out: list[str] = []

    def name(n):
        return next((x["text"] for x in n.get("titles", []) if x["lang"] == "en" and x.get("primary")), n.get("key", ""))

    def walk(n, path):
        t = name(n)
        p = path + [t] if t else path
        if "nodes" in n:
            for c in n["nodes"]:
                walk(c, p)
        else:
            out.append(", ".join(p))

    walk(d["schema"], [])
    return out


def segments(ref: str) -> list[str]:
    d = sefaria.get_json("v3/texts/" + urllib.parse.quote(ref), {"version": "hebrew"})
    t = d["versions"][0]["text"] if d.get("versions") else []
    t = t if isinstance(t, list) else [t]
    flat: list[str] = []
    for x in t:  # a leaf can be nested one level deeper
        flat += [y for y in x if isinstance(y, str)] if isinstance(x, list) else [x] if isinstance(x, str) else []
    return [re.sub(r"<[^>]+>", " ", s) for s in flat]


def words(text: str) -> list[str]:
    """Comparable words: no marks, no names (in any spelling), kri over ktiv."""
    text = re.sub(r"\([^)]*\)", " ", text)            # ktiv in the psalm data
    text = text.replace("[", " ").replace("]", " ")
    text = strip_marks(text)
    text = re.sub(r"הללו[\s־\-]+יה(?=[\s:׃.,]|$)", "הללויה", text)  # one word in the psalm, two in some siddurim
    out = []
    for w in re.split(r"[\s־׀|]+", text):
        if not w or "'" in w or "׳" in w or "-" in w:
            continue                                     # a kinui, or an abbreviated name
        w = normalize_finals(re.sub(r"[^א-ת]", "", w))
        if w and not NAMEISH.match(w):
            w = re.sub("[\u05D5\u05D9]", "", w) or w    # full and defective spelling compare the same
            out.append(w)
    return out


VERSES: dict[int, list[list[str]]] = {}


def psalm_keys() -> dict[int, tuple]:
    keys = {}
    for n in range(1, 151):
        p = json.loads((ROOT / "data" / "psalms" / f"{n:03d}.json").read_text(encoding="utf-8"))
        vs = [words(v["text"]) for v in p["verses"]]
        VERSES[n] = vs
        total = sum(len(v) for v in vs)
        starts = [v[:3] for v in vs[:2] if len(v) >= 3]
        # the end of the last verse, or of the one before it (a kri the siddur writes as ktiv)
        allw = [w for v in vs for w in v]
        ends = [((vs[-1][-3:] if len(vs[-1]) >= 3 else (vs[-2] + vs[-1])[-3:]), allw),
                ((vs[-2][-3:] if len(vs) > 1 else []), [w for v in vs[:-1] for w in v])]
        keys[n] = (starts, [e for e in ends if len(e[0]) == 3], total, allw)
    return keys


def plain_before(segs: list[str], si: int, text_before: str) -> str:
    """Unvocalized words printed right before the psalm, in its segment or the one before."""
    own = []
    for w in reversed(text_before.split()):
        if NIQQUD.search(w):
            break
        own.insert(0, w)
    if own:
        return " ".join(own)
    if si > 0 and segs[si - 1].strip() and not NIQQUD.search(segs[si - 1]):
        return segs[si - 1].strip()
    return ""


def covered(psalm_words: list[str], window: list[str]) -> float:
    have = set(window)
    return sum(w in have for w in psalm_words) / max(len(psalm_words), 1)


def scan(refs: list, keys, verses: dict[int, list[list[str]]] | None = None, partial: set[int] | None = None) -> list[dict]:
    refs = list(refs)
    verses = verses or VERSES
    stream: list[tuple[str, int, int, str]] = []   # (word, leaf index, segment index, ref)
    leaf_segs: list[list[str]] = []
    for li, spec in enumerate(refs):
        ref, begin, stop = (spec, None, None) if isinstance(spec, str) else spec
        refs[li] = ref
        try:
            segs = segments(ref)
        except Exception as ex:
            print("  skip", ref, ex)
            segs = []
        leaf_segs.append(segs)
        plain = [NIQQUD.sub("", s) for s in segs]
        lo = next((i for i, s in enumerate(plain) if begin in s), 0) if begin else 0
        hi = next((i for i, s in enumerate(plain) if i > lo and stop in s), len(segs)) if stop else len(segs)
        for si, s in enumerate(segs):
            if not lo <= si < hi:
                continue
            for w in words(s):
                stream.append((w, li, si, ref))
    W = [x[0] for x in stream]
    found = []
    for n, (starts, ends, total, _) in keys.items():
        for start in starts:
            k = len(start)
            for i in range(len(W) - k + 1):
                if W[i:i + k] != start:
                    continue
                limit = min(len(W), i + int(total * 1.4) + 12)
                hit = False
                for end, upto in ends:
                    for j in range(i + int(total * 0.6), limit - 2):
                        if W[j:j + 3] == end and covered(upto, W[i:j + 3]) >= 0.85:
                            hit = True
                            break
                    if hit:
                        found.append((i, n))
                        break
    until: dict[int, dict] = {}
    for n in partial or ():
        starts = keys[n][0][:1]
        for i in range(len(W) - 2):
            if W[i:i + 3] != starts[0]:
                continue
            k, v = i, 0
            vs = verses[n]
            while v < len(vs) and W[k:k + len(vs[v])] == vs[v]:
                k += len(vs[v])
                v += 1
            if v < len(vs) and v >= 3:  # an opening run, ending inside verse v+1
                m = 0
                while m < len(vs[v]) and k + m < len(W) and W[k + m] == vs[v][m]:
                    m += 1
                found.append((i, n))
                until[n] = {"v": v + 1 if m else v, "words": m or None}
            break
    found.sort()
    out, seen = [], set()
    for i, n in found:
        if n in seen:
            continue
        seen.add(n)
        _, li, si, ref = stream[i]
        seg = leaf_segs[li][si]
        # text of the segment before the psalm's first word
        first = next((m.start() for m in re.finditer(r"\S+", seg) if words(m.group()) == [stream[i][0]]), 0)
        rub = re.sub(r"\s+", " ", plain_before(leaf_segs[li], si, seg[:first])).strip()
        item = {"psalm": n, "ref": f"{ref} {si + 1}",
                "url": "https://www.sefaria.org/" + urllib.parse.quote(f"{ref} {si + 1}".replace(" ", "_")) + "?lang=he"}
        if n in until:
            item["until"] = until[n]
        if 4 <= len(rub) <= 200 and CONDITION.search(rub) and SAYS.search(rub) and not OTHER.search(rub):
            item["rubric"] = names.mask(rub, names.detect(rub))[0]
        # closing verses of the psalm before it, said as its opening ("ויהי נעם" before 91)
        if n > 1:
            prev = verses[n - 1]
            k, v = i, len(prev)
            while v >= 1 and prev[v - 1] and W[max(k - len(prev[v - 1]), 0):k] == prev[v - 1]:
                k -= len(prev[v - 1])
                v -= 1
            if v < len(prev):
                item["lead"] = {"psalm": n - 1, "from": v + 1, "to": len(prev)}
        out.append(item)
    for item in out:  # a psalm said in full before it is not an opening
        if item.get("lead", {}).get("psalm") in seen:
            del item["lead"]
    return out


def main() -> int:
    keys = psalm_keys()
    all_leaves = {nus: leaves(t) for nus, t in TITLES.items()}
    doc = {"_note": "נקרא מנוסח הסידורים שבספריא: מזמור נמנה רק כשהוא נאמר במלואו. "
                    "rubric: ההוראה שבסידור לפני המזמור, כלשונה.", "orders": {}}
    for slug, by_nus in ORDERS.items():
        doc["orders"][slug] = {}
        for nus, prefixes in by_nus.items():
            refs = [p if not isinstance(p, str) else l for p in prefixes
                    for l in (all_leaves[nus] if isinstance(p, str) else [p[0]])
                    if not isinstance(p, str) or l == p or l.startswith(p + ",")]
            items = scan(refs, keys, partial=PARTIAL.get((slug, nus)))
            doc["orders"][slug][nus] = {"sections": [{"ref": p, "url": "https://www.sefaria.org/" + urllib.parse.quote(p.replace(" ", "_")) + "?lang=he"} for p in (x if isinstance(x, str) else x[0] for x in prefixes)],
                                        "psalms": items}
            print(slug, nus, [(x["psalm"], x.get("rubric", "")[:40]) for x in items])
    (ROOT / "data" / "orders.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
