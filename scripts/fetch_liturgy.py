"""Where each psalm is said: Sefaria's links from Psalms to three siddurim.

Writes data/liturgy.json. Only links that cover most of a psalm count as
"saying the psalm" (a single verse quoted in a piyyut is not). Every entry
keeps the siddur reference it came from and is marked for manual review.
The link data holds references only, no text.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sefaria  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MIN_COVERAGE = 0.6

SIDDURIM = {
    "Siddur Ashkenaz": "ashkenaz",
    "Siddur Sefard": "sefard",
    "Siddur Edot HaMizrach": "edot",
}
NUSACHIM = {"ashkenaz": "אשכנז", "sefard": "ספרד", "edot": "עדות המזרח"}

# (id, label, keywords searched in the Hebrew section path). First match wins.
CONTEXTS = [
    ("shir_shel_yom", "שיר של יום", ["שיר של יום"]),
    ("hallel", "הלל", [r"(^|[ ,])הלל($|[ ,])"]),
    ("kabbalat_shabbat", "קבלת שבת", ["קבלת שבת"]),
    ("tikkun_chatzot", "תיקון חצות", ["תיקון חצות"]),
    ("selichot", "סליחות, וידוי ותעניות", ["סליחות", "וידוי", "תעני", "יום כיפור קטן"]),
    ("bedtime", "קריאת שמע על המיטה", ["על המיטה", "על המטה", "שעל המיטה"]),
    ("birkat_hamazon", "ברכת המזון", ["ברכת המזון"]),
    ("levana", "ברכת הלבנה", ["לבנה"]),
    ("motzaei_shabbat", "מוצאי שבת", ["מוצאי שבת", "מלוה מלכה", "ויתן לך"]),
    ("rosh_chodesh", "ראש חודש", ["ראש חודש", "ברכי נפשי"]),
    ("festivals", "מועדים", ["חגים", "רגלים", "חנוכה", "פסח", "סוכות", "שבועות", "ראש השנה",
                             "יום כיפור", "עומר", "הושענות", "שמיני עצרת", "ניסן", "יוצרות"]),
    ("life", "מעגל החיים ובקשות", ["ברית מילה", "נשמות", "אבל", "הדרך", "בקשות", "סגולות"]),
    ("ashrei", "אשרי (תהלה לדוד)", ["אשרי"]),
    ("pesukei", "פסוקי דזמרה", ["פסוקי ד", "הודו", "ישתבח", "ליום השבת"]),
    ("tachanun", "תחנון", ["תחנון", "נפילת אפ"]),
    ("shabbat", "שבת (תפילות נוספות)", ["שבת", "קידוש"]),
    ("weekday", "תפילות החול", ["ימי חול", "לימות החול", "לימי החול"]),
    ("other", "תפילות נוספות", [""]),
]


# Hallel is psalms 113-118 in every nusach (Pesachim 117a). Other psalms that Sefaria
# files under a Hallel section (Ashrei after it, the Great Hallel in the Haggadah)
# fall through to the next matching context.
HALLEL = range(113, 119)


def context_of(section: str, psalm: int) -> str:
    for cid, _, kws in CONTEXTS:
        if cid == "hallel" and psalm not in HALLEL:
            continue
        if any(re.search(k, section) for k in kws):
            return cid
    return "other"


def spans(anchor: str) -> list[tuple[int, int, int]]:
    """'Psalms 144:15-145:21' -> [(144, 15, 15), (145, 1, 21)] (to-verse is clipped later)."""
    m = re.match(r"Psalms (\d+):(\d+)(?:-(?:(\d+):)?(\d+))?$", anchor)
    if not m:
        return []
    c1, v1 = int(m[1]), int(m[2])
    c2 = int(m[3]) if m[3] else c1
    v2 = int(m[4]) if m[4] else v1
    if c1 == c2:
        return [(c1, v1, v2)]
    return [(c1, v1, 999)] + [(c, 1, 999) for c in range(c1 + 1, c2)] + [(c2, 1, v2)]


def section_of(he_ref: str) -> str:
    """Hebrew section path without the trailing segment number or psalm label."""
    s = re.sub(r"\s+[א-ת]+[׳״\"']?[א-ת]*$", "", he_ref)
    s = re.sub(r",\s*תהילים\s.*$", "", s)
    return re.sub(r"\s+", " ", s).strip(" ,")


SCHEMA_PSALMS: list[dict] = []  # leaves of a siddur's structure that are a whole psalm ("Psalm 96")


def schema_order(title: str) -> dict[str, int]:
    """Position of every leaf node of a siddur in reading order ('Siddur Ashkenaz, Shabbat, ...' -> n).
    Also records leaves named 'Psalm N', which say outright that the whole psalm is said there."""
    d = sefaria.get_json("v2/index/" + title.replace(" ", "_"))
    order: dict[str, int] = {}

    def name(n, lang):
        return next((x["text"] for x in n.get("titles", []) if x["lang"] == lang and x.get("primary")), n.get("key", ""))

    def walk(n, path, hepath):
        t, h = name(n, "en"), name(n, "he")
        p = path + [t] if t else path
        hp = hepath + [h] if h else hepath
        if "nodes" in n:
            for c in n["nodes"]:
                walk(c, p, hp)
        else:
            order[", ".join(p)] = len(order)
            m = re.fullmatch(r"Psalms? (\d+)", t or "")
            if m:
                SCHEMA_PSALMS.append({"psalm": int(m[1]), "siddur": title, "ref": ", ".join(p),
                                      "section": ", ".join(hp[:-1]), "pos": (order[", ".join(p)], 0)})

    walk(d["schema"], [], [])
    return order


def position(ref: str, order: dict[str, int]) -> tuple[int, int]:
    """(node index, segment) of a siddur ref, for sorting psalms in the order they are said."""
    m = re.match(r"^(.*?)\s+(\d+)(?::\d+)?(?:-\d+(?::\d+)?)?$", ref)
    node, seg = (m[1], int(m[2])) if m else (ref, 0)
    return order.get(node, 99999), seg


def main() -> int:
    shape = sefaria.get_json("shape/Psalms")
    lengths = (shape[0] if isinstance(shape, list) else shape)["chapters"]

    def fetch(n):
        return n, sefaria.get_json(f"links/Psalms.{n}", {"with_text": 0})

    orders = {t: schema_order(t) for t in SIDDURIM}
    groups: dict[tuple, dict] = {}
    with cf.ThreadPoolExecutor(3) as ex:
        for n, links in ex.map(fetch, range(1, 151)):
            for l in links:
                nus = SIDDURIM.get(l.get("index_title", ""))
                if l.get("category") != "Liturgy" or not nus:
                    continue
                sec = section_of(l.get("sourceHeRef") or "")
                pos = position(l["ref"], orders[l["index_title"]])
                for c, a, b in spans(l.get("anchorRef", "")):
                    b = min(b, lengths[c - 1])
                    g = groups.setdefault((c, nus, sec), {"verses": set(), "pos": pos, "ref": l["ref"]})
                    g["verses"].update(range(a, b + 1))  # a psalm may be linked in several pieces
                    if pos < g["pos"]:
                        g["pos"], g["ref"] = pos, l["ref"]
    for sp in SCHEMA_PSALMS:  # the siddur's own structure names the psalm: the whole psalm is said there
        g = groups.setdefault((sp["psalm"], SIDDURIM[sp["siddur"]], sp["section"]),
                              {"verses": set(), "pos": sp["pos"], "ref": sp["ref"]})
        g["verses"].update(range(1, lengths[sp["psalm"] - 1] + 1))
        g["pos"] = min(g["pos"], sp["pos"])
    best: dict[tuple, dict] = {}
    for (c, nus, sec), g in groups.items():
        cov = len(g["verses"]) / lengths[c - 1]
        if cov < MIN_COVERAGE:
            continue
        best[(c, nus, sec)] = {
            "psalm": c, "nusach": nus, "context": context_of(sec, c), "section": sec,
            "from": min(g["verses"]), "to": max(g["verses"]), "coverage": round(cov, 2), "ref": g["ref"],
            "order": list(g["pos"]),
            "url": "https://www.sefaria.org/" + g["ref"].replace(" ", "_").replace(",", "%2C") + "?lang=he",
            "status": "auto",
        }
    entries = sorted(best.values(), key=lambda e: (e["psalm"], e["nusach"], e["context"], e["section"]))
    doc = {
        "_note": ("נבנה מקישורי ספריא (קטגוריית Liturgy) בין תהילים לשלושה סידורים. נכלל רק קישור שמכסה לפחות "
                  f"{int(MIN_COVERAGE * 100)}% מהמזמור. status: auto = טרם אומת ידנית."),
        "nusachim": NUSACHIM,
        "contexts": [{"id": c, "label": lbl} for c, lbl, _ in CONTEXTS],
        "entries": entries,
    }
    (ROOT / "data" / "liturgy.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(entries)} liturgy entries for {len({e['psalm'] for e in entries})} psalms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
