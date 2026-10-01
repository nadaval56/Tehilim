"""Detection and masking of the holy names.

The full names never appear in this file: every pattern is assembled from the
letter constants in hebrew.py. Detection runs on the raw text in memory;
callers persist only the masked text returned by `mask()`.

Name types (keys used throughout the data):
  HAVAYAH, ELOKIM, EL, ELOAH, YAH, ADNI, SHADDAI, TZVAOT
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from hebrew import (
    ALEF, BET, DALET, HE, VAV, YOD, KAF, LAMED, MEM, NUN, SHIN, TSADI, TAV, AYIN, RESH, GIMEL,
    HET, ZAYIN, FINAL_MEM, FINAL_KAF, FINAL_NUN,
    TSERE, HIRIQ, QAMATS, PATAH, DAGESH, SHIN_DOT, MAQAF,
    Word, tokenize,
)

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "kinuyim.json").read_text(encoding="utf-8"))

TYPES = ["HAVAYAH", "ELOKIM", "EL", "ELOAH", "YAH", "ADNI", "SHADDAI", "TZVAOT"]
HALLELUYAH = "HALLELUYAH"

# --- stems -------------------------------------------------------------------
_HAVAYAH = YOD + HE + VAV + HE
_ELOK = ALEF + LAMED + HE  # stem of ELOKIM and of the defective ELOAH
_ELOKIM_SUFFIXES = [
    YOD + FINAL_MEM, YOD, YOD + NUN + VAV, YOD + FINAL_KAF, YOD + KAF + FINAL_MEM, YOD + VAV,
    YOD + HE + FINAL_MEM, YOD + HE, YOD + KAF + FINAL_NUN, YOD + HE + FINAL_NUN,
]
_EL = ALEF + LAMED
_ELOAH = ALEF + LAMED + VAV + HE
_YAH = YOD + HE
_ADNI = [ALEF + DALET + NUN + YOD, ALEF + DALET + VAV + NUN + YOD]
_ADNI_SUFFIX = NUN + VAV  # "...our" form
_SHADDAI = SHIN + DALET + YOD
_TZVAOT = TSADI + BET + ALEF + VAV + TAV
_HALLELU = HE + LAMED + LAMED + VAV
PREFIX_LETTERS = set(VAV + BET + KAF + LAMED + MEM + HE + SHIN)

# Words whose presence next to a name suggests a non-holy (chol) sense.
# These only produce *candidates* for the owner's review; nothing is unmasked
# until an entry is approved in data/annotations/chol_names.json.
_CHOL_NEXT = {
    HE + AYIN + MEM + YOD + FINAL_MEM,  # the peoples
    HE + GIMEL + VAV + YOD + FINAL_MEM,  # the nations
    ALEF + HET + RESH + YOD + FINAL_MEM,  # other
    ALEF + HET + RESH,
    ZAYIN + RESH,  # strange
    NUN + KAF + RESH,  # foreign
    HE + NUN + KAF + RESH,
}
_CHOL_PREV = {
    KAF + LAMED, MEM + KAF + LAMED, BET + KAF + LAMED,  # "all"
    KAF + MEM + VAV + FINAL_KAF,  # "like You (among ...)"
}


@dataclass
class Match:
    type: str
    word: int  # index of the word in the verse tokenization
    stem: int  # index of the first stem letter inside the word
    prefix: str  # prefix letters (skeleton), e.g. "ו"
    suffix: str  # possessive suffix (skeleton) or ""
    chol_reason: str | None = None


def _split_prefix(skel: str, stem_and_suffix: str) -> str | None:
    """Return the prefix if `skel` == prefix + stem_and_suffix, else None."""
    if not skel.endswith(stem_and_suffix):
        return None
    p = skel[: len(skel) - len(stem_and_suffix)]
    if len(p) <= 3 and all(c in PREFIX_LETTERS for c in p):
        return p
    return None


def _classify(w: Word) -> tuple[str, str, str] | None:
    """(type, prefix, suffix) for a single word, or None."""
    s = w.skeleton
    voc = w.vocalized
    L = w.letters

    if _HAVAYAH in s:
        i = s.index(_HAVAYAH)
        return "HAVAYAH", s[:i], s[i + 4:]

    for suf in _ELOKIM_SUFFIXES:
        p = _split_prefix(s, _ELOK + suf)
        if p is not None:
            return "ELOKIM", p, suf

    p = _split_prefix(s, _ELOAH)
    if p is not None:
        return "ELOAH", p, ""

    if voc:
        p = _split_prefix(s, _ELOK)
        if p is not None and L[-1].has(DAGESH):  # defective spelling with mappiq
            return "ELOAH", p, ""

        p = _split_prefix(s, _EL)
        if p is not None and L[len(p)].has(TSERE):
            return "EL", p, ""
        p = _split_prefix(s, _EL + YOD)
        if p is not None and L[len(p)].has(TSERE) and L[len(p) + 1].has(HIRIQ):
            return "EL", p, YOD

        p = _split_prefix(s, _YAH)
        if p is not None and L[len(p)].has(QAMATS) and L[-1].has(DAGESH):
            return "YAH", p, ""

        for stem in _ADNI:
            p = _split_prefix(s, stem)
            if p is not None and L[len(p) + len(stem) - 2].has(QAMATS):
                return "ADNI", p, ""
            p = _split_prefix(s, stem + _ADNI_SUFFIX)
            if p is not None:
                return "ADNI", p, YOD + _ADNI_SUFFIX

        p = _split_prefix(s, _SHADDAI)
        if p is not None and L[len(p)].has(SHIN_DOT) and L[len(p) + 1].has(PATAH):
            return "SHADDAI", p, ""
    else:
        # Unvocalized prose: only spellings that are unambiguous without niqqud.
        for stem in _ADNI[:1]:
            p = _split_prefix(s, stem)
            if p is not None:
                return "ADNI", p, ""
        p = _split_prefix(s, _SHADDAI)
        if p is not None:
            return "SHADDAI", p, ""

    p = _split_prefix(s, _TZVAOT)
    if p is not None:
        return "TZVAOT", p, ""
    return None


def _is_kinui(w: Word, text: str) -> bool:
    """A word that is already a kinui (ה' or a hyphenated form)."""
    after = text[w.end:w.end + 1]
    before = text[w.start - 1:w.start] if w.start else ""
    return after in ("'", "-", "׳") or before == "-"


def detect(text: str, words: list[Word] | None = None) -> list[Match]:
    words = tokenize(text) if words is None else words
    out: list[Match] = []
    for w in words:
        c = _classify(w)
        if c is None:
            continue
        t, prefix, suffix = c
        if t == "YAH":
            prev = words[w.index - 1] if w.index else None
            if prev is not None and MAQAF in w.sep_before and prev.skeleton.endswith(_HALLELU):
                t = HALLELUYAH
        out.append(Match(t, w.index, len(prefix), prefix, suffix))
    # Halleluyah written as a single word (its "prefix" is too long to match).
    for w in words:
        if w.skeleton.endswith(_HALLELU + _YAH) and not any(m.word == w.index for m in out):
            out.append(Match(HALLELUYAH, w.index, len(w.skeleton) - 2, w.skeleton[:-2], ""))

    names_at = {m.word for m in out if m.type != HALLELUYAH}
    for m in out:
        if m.type in ("ELOKIM", "EL", "ELOAH"):
            nxt = words[m.word + 1].skeleton if m.word + 1 < len(words) else ""
            prv = words[m.word - 1].skeleton if m.word else ""
            if nxt in _CHOL_NEXT:
                m.chol_reason = "next-word"
            elif prv in _CHOL_PREV:
                m.chol_reason = "after-kol"
            elif m.type == "ELOKIM" and m.prefix.endswith(HE) and (m.word - 1) in names_at:
                m.chol_reason = "construct-chain"
        if m.type == "TZVAOT":
            prev_is_name = (m.word - 1) in names_at or (m.word and _is_kinui(words[m.word - 1], text))
            if not prev_is_name:
                if not words[m.word].vocalized:
                    m.type = "NOT_A_NAME"  # unvocalized "armies" in prose
                else:
                    m.chol_reason = "not-after-name"
    return [m for m in out if m.type != "NOT_A_NAME"]


def kinui_for(word_raw: str, w: Word, m: Match) -> str:
    """The display form of a matched word."""
    style = CONFIG["types"][m.type]
    letters = w.letters
    base = w.start
    stem_first = letters[m.stem]
    prefix_raw = word_raw[: stem_first.start - base]
    if style["display"] == "replace":
        return prefix_raw + style["replacement"]
    # hyphen after the first letter of the stem (with its marks)
    cut = stem_first.end - base
    return word_raw[:cut] + CONFIG["hyphen"] + word_raw[cut:]


def mask(text: str, matches: list[Match], keep: set[int] | None = None) -> tuple[str, list[dict]]:
    """Return (masked_text, entries). Words in `keep` (approved chol) stay as is."""
    keep = keep or set()
    words = tokenize(text)
    out, pos, entries = [], 0, []
    for m in sorted(matches, key=lambda m: m.word):
        w = words[m.word]
        out.append(text[pos:w.start])
        start = sum(len(x) for x in out)
        raw = w.raw(text)
        if m.type == HALLELUYAH or m.word in keep:
            form = raw
        else:
            form = kinui_for(raw, w, m)
        out.append(form)
        pos = w.end
        if m.type != HALLELUYAH:
            entries.append({
                "type": m.type,
                "word": m.word,
                "start": start,
                "end": start + len(form),
                "prefix": m.prefix,
                "suffix": m.suffix,
                "chol": m.word in keep,
            })
    out.append(text[pos:])
    return "".join(out), entries


def find_unmasked(text: str) -> list[Match]:
    """Matches that would reveal a full name (used by check_names)."""
    return [m for m in detect(text) if m.type != HALLELUYAH]
