"""Hebrew text primitives: letters, marks, and a word tokenizer.

Every Hebrew letter is referenced through a code point constant, never as a
literal, so that no source file in this project spells out a holy name.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- letters -----------------------------------------------------------------
ALEF = "א"
BET = "ב"
GIMEL = "ג"
DALET = "ד"
HE = "ה"
VAV = "ו"
ZAYIN = "ז"
HET = "ח"
TET = "ט"
YOD = "י"
FINAL_KAF = "ך"
KAF = "כ"
LAMED = "ל"
FINAL_MEM = "ם"
MEM = "מ"
FINAL_NUN = "ן"
NUN = "נ"
SAMEKH = "ס"
AYIN = "ע"
FINAL_PE = "ף"
PE = "פ"
FINAL_TSADI = "ץ"
TSADI = "צ"
QOF = "ק"
RESH = "ר"
SHIN = "ש"
TAV = "ת"

# --- points (niqqud) ---------------------------------------------------------
SHEVA = "ְ"
HATAF_SEGOL = "ֱ"
HATAF_PATAH = "ֲ"
HATAF_QAMATS = "ֳ"
HIRIQ = "ִ"
TSERE = "ֵ"
SEGOL = "ֶ"
PATAH = "ַ"
QAMATS = "ָ"
HOLAM = "ֹ"
HOLAM_HASER_FOR_VAV = "ֺ"
QUBUTS = "ֻ"
DAGESH = "ּ"  # also mappiq
METEG = "ֽ"
RAFE = "ֿ"
SHIN_DOT = "ׁ"
SIN_DOT = "ׂ"
QAMATS_QATAN = "ׇ"

VOWELS = set("ְֱֲֳִֵֶַָׇֹֺֻ")

# --- punctuation -------------------------------------------------------------
MAQAF = "־"
PASEQ = "׀"
SOF_PASUQ = "׃"

LETTERS = "".join(chr(c) for c in range(0x05D0, 0x05EB))
# Combining marks that stay attached to a letter inside a word: cantillation
# (0591-05AF), points (05B0-05BD, 05BF, 05C1, 05C2, 05C4, 05C5, 05C7) and the
# invisible joiners MAM uses to order marks.
_MARKS = "֑-ׇֽֿׁׂׅׄ͏‌‍"
WORD_RE = re.compile(f"(?:[{LETTERS}][{_MARKS}]*)+")
_LETTER_RE = re.compile(f"([{LETTERS}])([{_MARKS}]*)")

_FINALS = {FINAL_KAF: KAF, FINAL_MEM: MEM, FINAL_NUN: NUN, FINAL_PE: PE, FINAL_TSADI: TSADI}


@dataclass
class Letter:
    ch: str
    marks: str
    start: int  # offset of the letter in the source string
    end: int  # offset just past its last mark

    def has(self, mark: str) -> bool:
        return mark in self.marks

    @property
    def vowels(self) -> set[str]:
        return {m for m in self.marks if m in VOWELS}


@dataclass
class Word:
    index: int
    start: int
    end: int
    letters: list[Letter] = field(default_factory=list)
    sep_before: str = ""  # raw text between the previous word and this one

    @property
    def skeleton(self) -> str:
        return "".join(l.ch for l in self.letters)

    @property
    def vocalized(self) -> bool:
        return any(l.vowels for l in self.letters)

    def raw(self, text: str) -> str:
        return text[self.start:self.end]


def tokenize(text: str) -> list[Word]:
    words: list[Word] = []
    prev_end = 0
    for i, m in enumerate(WORD_RE.finditer(text)):
        w = Word(index=i, start=m.start(), end=m.end(), sep_before=text[prev_end:m.start()])
        for lm in _LETTER_RE.finditer(m.group(0)):
            w.letters.append(Letter(lm.group(1), lm.group(2), m.start() + lm.start(), m.start() + lm.end()))
        words.append(w)
        prev_end = m.end()
    return words


def strip_marks(text: str) -> str:
    """Letters only (plus everything that is not a Hebrew mark)."""
    return re.sub(f"[{_MARKS}]", "", text)


def normalize_finals(s: str) -> str:
    return "".join(_FINALS.get(c, c) for c in s)


_GERESH_NUMS = {1: ALEF, 2: BET, 3: GIMEL, 4: DALET, 5: HE, 6: VAV, 7: ZAYIN, 8: HET, 9: TET,
                10: YOD, 20: KAF, 30: LAMED, 40: MEM, 50: NUN, 60: SAMEKH, 70: AYIN, 80: PE,
                90: TSADI, 100: QOF}


def hebrew_numeral(n: int, punctuate: bool = False) -> str:
    """Psalm/verse numbers as Hebrew letters (1..199). 15 -> ט"ו, 16 -> ט"ז."""
    out = ""
    if n >= 100:
        out += QOF
        n -= 100
    if n == 15:
        out += TET + VAV
    elif n == 16:
        out += TET + ZAYIN
    else:
        tens, ones = (n // 10) * 10, n % 10
        if tens:
            out += _GERESH_NUMS[tens]
        if ones:
            out += _GERESH_NUMS[ones]
    if punctuate:
        out = out[:-1] + '"' + out[-1] if len(out) > 1 else out + "'"
    return out
