"""Fetch the rabbinic passages the site quotes, mask names, save data/sources.json.

Every quotation on the site comes from here, never from memory (spec §0.3).
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import names  # noqa: E402
import quotes  # noqa: E402
import sefaria  # noqa: E402
from hebrew import strip_marks  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TALMUD = "Wikisource Talmud Bavli"

SOURCES = {
    "ten_elders": {
        "title": "בבא בתרא יד ע\"ב – טו ע\"א",
        "segments": ["Bava_Batra.14b.12", "Bava_Batra.15a.1"],
        "version": TALMUD,
        "topic": "עשרה זקנים שעל ידם נכתב ספר תהלים",
    },
    "eitan_avraham": {
        "title": "בבא בתרא טו ע\"א",
        "segments": ["Bava_Batra.15a.9"],
        "version": TALMUD,
        "topic": "איתן האזרחי",
    },
    "ashrei_nun": {
        "title": "ברכות ד ע\"ב",
        "segments": ["Berakhot.4b.21", "Berakhot.4b.22"],
        "version": TALMUD,
        "topic": "האות נו\"ן החסרה במזמור קמה",
    },
    "shir_shel_yom": {
        "title": "משנה תמיד ז, ד",
        "segments": ["Mishnah_Tamid.7.4"],
        "version": "Torat Emet 357",
        "topic": "השיר שהיו הלוים אומרים במקדש",
    },
    "tikkun_haklali": {
        "title": "שיחות הר\"ן, סימן קמא",
        "segments": ["Sichot_HaRan.141.26"],
        "version": "rabenubook",
        "topic": "עשרת המזמורים של התיקון הכללי",
    },
    "psalms_1_2": {
        "title": "ברכות ט ע\"ב – י ע\"א",
        "segments": ["Berakhot.9b.30", "Berakhot.10a.1"],
        "version": TALMUD,
        "topic": "מזמורים א–ב כפרשה אחת",
    },
}


# Passages from Hebrew Wikisource: the excerpt runs from `start` to the end of `end`.
WIKISOURCE = {
    "chida_sansan": {
        "title": "חיד\"א, סנסן ליאיר, סימן יא (\"דברים המועילים לרפואה\"), אות ב",
        "page": "סנסן ליאיר",
        "start": "דברים המועילים לרפואה",
        "end": "מספר ליקוטי תהלים.",
        "topic": "קריאת פסוקי תהלים לפי אותיות השם",
    },
    "chida_kaf_achat": {
        "title": "חיד\"א, כף אחת, אות ה",
        "page": "כף אחת",
        "start": "לאחר פסוקי לקוטי תהלים",
        "end": "אשר ראשיהם אותיות שם פלוני",
        "topic": "תפילה אחרי פסוקי ליקוטי תהלים",
    },
}


def wikisource(src: dict) -> dict:
    url = "https://he.wikisource.org/w/index.php?" + urllib.parse.urlencode({"title": src["page"], "action": "raw"})
    raw = strip_marks(sefaria.get_text(url))
    raw = re.sub(r"\{\{ש\}\}|=+|\[\[|\]\]|'{2,}", " ", raw)
    a = raw.index(src["start"])
    b = raw.index(src["end"], a) + len(src["end"])
    text = re.sub(r"\s+", " ", raw[a:b]).strip()
    masked = quotes.mask_quoted(text)
    del raw, text
    return {"title": src["title"], "topic": src["topic"], "version": "ויקיטקסט", "license": "CC-BY-SA",
            "segments": [{"ref": src["page"], "he_ref": src["page"], "text": masked}],
            "url": "https://he.wikisource.org/wiki/" + urllib.parse.quote(src["page"].replace(" ", "_"))}


def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", strip_marks(s)).strip()


def main() -> int:
    out = {}
    for key, src in SOURCES.items():
        segs = []
        for ref in src["segments"]:
            d = sefaria.get_json(f"v3/texts/{ref}", {"version": f"hebrew|{src['version']}"})
            v = d["versions"][0]
            raw = clean(v["text"] if isinstance(v["text"], str) else " ".join(v["text"]))
            masked = quotes.mask_quoted(raw)
            del raw
            segs.append({"ref": ref, "he_ref": d.get("heRef", ""), "text": masked})
            license_ = v.get("license", "")
        out[key] = {
            **{k: src[k] for k in ("title", "topic", "version")},
            "license": license_,
            "segments": segs,
            "url": "https://www.sefaria.org/" + src["segments"][0].rsplit(".", 1)[0] + "?lang=he",
        }
    for key, src in WIKISOURCE.items():
        out[key] = wikisource(src)
    path = ROOT / "data" / "sources.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
