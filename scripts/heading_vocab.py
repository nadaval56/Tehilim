"""Superscription (כותרת) parsing, using only the wording of the headings.

The boundary between heading and psalm is decided as follows:
- In psalms whose heading is a verse of its own in the Hebrew verse
  numbering (HEADING_VERSES), the whole first verse is the heading, and in
  51, 52, 54 and 60 the first two verses.
- Elsewhere the heading is the run of heading words at the start of verse 1
  (possibly empty).
Every result is marked "review": "auto" until checked by hand.
"""
from __future__ import annotations

from hebrew import ALEF, LAMED, HE, YOD, FINAL_MEM, tokenize

_HA_ELOKIM = HE + ALEF + LAMED + HE + YOD + FINAL_MEM  # "the G-d" in 90:1, built from code points

HEADING_VERSES = {
    3, 4, 5, 6, 7, 8, 9, 12, 13, 18, 19, 20, 21, 22, 30, 31, 34, 36, 38, 39, 40, 41, 42, 44, 45,
    46, 47, 48, 49, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 67, 68, 69, 70,
    75, 76, 77, 80, 81, 83, 84, 85, 88, 89, 92, 102, 108, 140, 142,
}
TWO_VERSE_HEADINGS = {51, 52, 54, 60}

# Psalms whose heading names an event in David's life (spec §6).
EVENT_PSALMS = {3, 7, 18, 34, 51, 52, 54, 56, 57, 59, 60, 63, 142}

RUN_VOCAB = {
    "למנצח", "לדוד", "מזמור", "שיר", "המעלות", "למעלות", "תפלה", "תהלה", "משכיל", "מכתם",
    "לאסף", "לשלמה", "למשה", "איש", _HA_ELOKIM, "לתודה", "לבני", "קרח", "ליום", "השבת",
    "להזכיר", "לידותון", "לידיתון", "שגיון",
}

ATTRIBUTIONS = [
    (("לדוד",), "דוד"),
    (("לבני", "קרח"), "בני קרח"),
    (("לאסף",), "אסף"),
    (("למשה",), "משה"),
    (("לשלמה",), "שלמה"),
    (("להימן",), "הימן"),
    (("לאיתן",), "איתן"),
]

TYPES = [
    (("שיר", "המעלות"), "שיר המעלות"),
    (("שיר", "למעלות"), "שיר המעלות"),
    (("מזמור",), "מזמור"),
    (("שיר",), "שיר"),
    (("משכיל",), "משכיל"),
    (("מכתם",), "מכתם"),
    (("תפלה",), "תפלה"),
    (("תהלה",), "תהלה"),
    (("שגיון",), "שגיון"),
]

MUSICAL = [
    (("למנצח",), "למנצח"),
    (("בנגינות",), "בנגינות"),
    (("בנגינת",), "בנגינת"),
    (("על", "נגינת"), "על נגינת"),
    (("על", "השמינית"), "על השמינית"),
    (("על", "הגתית"), "על הגתית"),
    (("אל", "הנחילות"), "אל הנחילות"),
    (("עלמות", "לבן"), "על מות לבן"),
    (("על", "מות", "לבן"), "על מות לבן"),
    (("על", "אילת", "השחר"), "על אילת השחר"),
    (("על", "שושן", "עדות"), "על שושן עדות"),
    (("אל", "שושן", "עדות"), "אל שושן עדות"),
    (("על", "ששנים", "עדות"), "על ששנים עדות"),
    (("אל", "ששנים", "עדות"), "אל ששנים עדות"),
    (("על", "ששנים"), "על ששנים"),
    (("על", "שושנים"), "על שושנים"),
    (("אל", "ששנים"), "אל ששנים"),
    (("אל", "שושנים"), "אל שושנים"),
    (("על", "מחלת", "לענות"), "על מחלת לענות"),
    (("על", "מחלת"), "על מחלת"),
    (("על", "יונת", "אלם", "רחקים"), "על יונת אלם רחקים"),
    (("אל", "תשחת"), "אל תשחת"),
    (("על", "ידותון"), "על ידותון"),
    (("על", "ידיתון"), "על ידיתון"),
    (("לידותון",), "לידותון"),
    (("לידיתון",), "לידיתון"),
    (("על", "עלמות"), "על עלמות"),
    (("ללמד",), "ללמד"),
    (("להזכיר",), "להזכיר"),
    (("לתודה",), "לתודה"),
    (("ליום", "השבת"), "ליום השבת"),
    (("חנכת", "הבית"), "חנכת הבית"),
    (("ידידת",), "שיר ידידת"),
    (("לענות",), "לענות"),
]


def _find(seq: list[str], table) -> list[str]:
    found, used = [], set()
    for pat, label in table:
        k = len(pat)
        for i in range(len(seq) - k + 1):
            if tuple(seq[i:i + k]) == pat and not used & set(range(i, i + k)):
                if label not in found:
                    found.append(label)
                used |= set(range(i, i + k))
    return found


def _masked_offset(raw: str, verse: dict, last_word: int) -> int:
    """Offset in the masked verse text that corresponds to the end of raw word `last_word`."""
    words = tokenize(raw)
    delta = 0
    for e in verse["names"]:
        if e["word"] <= last_word:
            w = words[e["word"]]
            delta += (e["end"] - e["start"]) - (w.end - w.start)
    return words[last_word].end + delta


def parse_heading(n: int, raw_verses: list[str], verses: list[dict]) -> dict | None:
    """Analyse the heading of psalm n. raw_verses are unmasked (memory only);
    every string returned is taken from the masked `verses` or is a label."""
    if n in HEADING_VERSES:
        nv = 2 if n in TWO_VERSE_HEADINGS else 1
        seq = [w.skeleton for v in raw_verses[:nv] for w in tokenize(v)]
        text = " ".join(v["text"] for v in verses[:nv])
        end = {"v": nv, "offset": len(verses[nv - 1]["text"])}
        run_len = 0
        for s in seq:
            if s in RUN_VOCAB or (run_len and s in {"על", "אל"}):
                run_len += 1
            else:
                break
    else:
        words = tokenize(raw_verses[0])
        run_len = 0
        for w in words:
            if w.skeleton in RUN_VOCAB:
                run_len += 1
            else:
                break
        if run_len == 0:
            return None
        if run_len == len(words):  # should not happen outside HEADING_VERSES
            run_len -= 1
        seq = [w.skeleton for w in words[:run_len]]
        off = _masked_offset(raw_verses[0], verses[0], run_len - 1)
        text = verses[0]["text"][:off].rstrip(" ־")
        end = {"v": 1, "offset": off}

    event = None
    if n in EVENT_PSALMS:
        # the clause after the heading words (e.g. "בברחו מפני אבשלום בנו")
        flat = [(vi, w) for vi, v in enumerate(raw_verses[:end["v"]]) for w in tokenize(v)]
        # skip the formal heading words, then any musical/attribution words
        i = 0
        known = RUN_VOCAB | {"על", "אל", "יונת", "אלם", "רחקים", "תשחת", "שושן", "עדות", "מחלת",
                             "בנגינת", "בנגינות", "ללמד", "לעבד"}
        while i < len(flat):
            s = flat[i][1].skeleton
            after_servant = i and flat[i - 1][1].skeleton == "לעבד"
            if s in known or after_servant:  # "the servant of [the Name]" (18:1)
                i += 1
            else:
                break
        if i < len(flat):
            vi, w = flat[i]
            raw = raw_verses[vi]
            # masked offset of the start of word w
            off = _masked_offset(raw, verses[vi], w.index) - (w.end - w.start)
            # adjust if w itself is a masked name
            for e in verses[vi]["names"]:
                if e["word"] == w.index:
                    off = e["start"]
            parts = [verses[vi]["text"][off:]] + [verses[j]["text"] for j in range(vi + 1, end["v"])]
            event = " ".join(parts).strip()

    return {
        "text": text,
        "end": end,
        "attribution": [label for pat, label in ATTRIBUTIONS if _find(seq, [(pat, label)])],
        "types": _find(seq, TYPES),
        "musical_terms": _find(seq, MUSICAL),
        "historical_event": event,
        "own_verse": n in HEADING_VERSES,
        "review": "auto",
    }
