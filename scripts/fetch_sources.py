"""Fetch the rabbinic passages the site quotes, mask names, save data/sources.json.

Every quotation on the site comes from here, never from memory (spec §0.3).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import names  # noqa: E402
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
    "psalms_1_2": {
        "title": "ברכות ט ע\"ב – י ע\"א",
        "segments": ["Berakhot.9b.30", "Berakhot.10a.1"],
        "version": TALMUD,
        "topic": "מזמורים א–ב כפרשה אחת",
    },
}


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
            masked, _ = names.mask(raw, names.detect(raw))
            del raw
            segs.append({"ref": ref, "he_ref": d.get("heRef", ""), "text": masked})
            license_ = v.get("license", "")
        out[key] = {
            **{k: src[k] for k in ("title", "topic", "version")},
            "license": license_,
            "segments": segs,
            "url": "https://www.sefaria.org/" + src["segments"][0].rsplit(".", 1)[0] + "?lang=he",
        }
    path = ROOT / "data" / "sources.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
