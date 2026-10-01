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


def context_of(section: str) -> str:
    for cid, _, kws in CONTEXTS:
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


def main() -> int:
    shape = sefaria.get_json("shape/Psalms")
    lengths = (shape[0] if isinstance(shape, list) else shape)["chapters"]

    def fetch(n):
        return n, sefaria.get_json(f"links/Psalms.{n}", {"with_text": 0})

    best: dict[tuple, dict] = {}
    with cf.ThreadPoolExecutor(3) as ex:
        for n, links in ex.map(fetch, range(1, 151)):
            for l in links:
                nus = SIDDURIM.get(l.get("index_title", ""))
                if l.get("category") != "Liturgy" or not nus:
                    continue
                for c, a, b in spans(l.get("anchorRef", "")):
                    b = min(b, lengths[c - 1])
                    cov = (b - a + 1) / lengths[c - 1]
                    if cov < MIN_COVERAGE:
                        continue
                    sec = section_of(l.get("sourceHeRef") or "")
                    key = (c, nus, sec)
                    if key not in best or cov > best[key]["coverage"]:
                        best[key] = {
                            "psalm": c, "nusach": nus, "context": context_of(sec), "section": sec,
                            "from": a, "to": b, "coverage": round(cov, 2), "ref": l["ref"],
                            "url": "https://www.sefaria.org/" + l["ref"].replace(" ", "_").replace(",", "%2C") + "?lang=he",
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
