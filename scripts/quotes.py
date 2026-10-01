"""Mask names in unvocalized quotations of Psalms verses.

In unvocalized prose some names (the short forms EL and YAH) cannot be told
apart from ordinary words, so names.py leaves them alone. When a rabbinic
source quotes a verse, though, the verse itself tells us: if a run of words
in the source matches consecutive words of a psalm verse, and the aligned
word in the verse is a name, the word in the source is masked too.
"""
from __future__ import annotations

import json
from pathlib import Path

import names
from hebrew import tokenize

ROOT = Path(__file__).resolve().parent.parent
WINDOW = 2  # words of context on each side that must match the verse


def _verse_words(v: dict) -> list[tuple[str, str | None]]:
    """[(skeleton, name_type or None)] per original word of a masked verse."""
    text = v["text"]
    spans = sorted((e["start"], e["end"], e["type"]) for e in v["names"])
    out, i = [], 0
    words = tokenize(text)
    while i < len(words):
        w = words[i]
        span = next((s for s in spans if s[0] <= w.start < s[1]), None)
        if span:
            skel = ""
            while i < len(words) and words[i].start < span[1]:
                skel += words[i].skeleton
                i += 1
            out.append((skel, span[2]))
        else:
            out.append((w.skeleton, None))
            i += 1
    return out


class VerseIndex:
    def __init__(self):
        self.verses = []
        self.by_word: dict[str, list[tuple[int, int]]] = {}
        for f in sorted((ROOT / "data" / "psalms").glob("*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            for v in doc["verses"]:
                ws = _verse_words(v)
                k = len(self.verses)
                self.verses.append(ws)
                for j, (s, _) in enumerate(ws):
                    self.by_word.setdefault(s, []).append((k, j))

    def name_at(self, ctx: list[str], pos: int) -> str | None:
        """If ctx (source skeletons) matches a verse around ctx[pos], the name type there."""
        for k, j in self.by_word.get(ctx[pos], []):
            ws = self.verses[k]
            if ws[j][1] not in ("EL", "YAH", "ELOAH", "ADNI", "SHADDAI", "TZVAOT"):
                continue
            ok = 0
            for d in range(1, WINDOW + 1):
                for a, b in ((pos - d, j - d), (pos + d, j + d)):
                    if 0 <= a < len(ctx) and 0 <= b < len(ws) and ctx[a] == ws[b][0]:
                        ok += 1
            if ok >= WINDOW:
                return ws[j][1]
        return None


# Stem letters of each name; the hyphen goes after the stem's first letter.
STEMS = {
    "EL": "\u05D0\u05DC", "YAH": "\u05D9\u05D4", "ELOAH": "\u05D0\u05DC\u05D5\u05D4",
    "ADNI": "\u05D0\u05D3", "SHADDAI": "\u05E9\u05D3\u05D9", "TZVAOT": "\u05E6\u05D1\u05D0",
}

_INDEX: VerseIndex | None = None


def mask_quoted(text: str) -> str:
    """Mask names (names.py), then names that are only identifiable as part of a quoted verse."""
    global _INDEX
    if _INDEX is None:
        _INDEX = VerseIndex()
    text, _ = names.mask(text, names.detect(text))
    words = tokenize(text)
    ctx = [w.skeleton for w in words]
    hyphen = names.CONFIG["hyphen"]
    out, pos = [], 0
    for i, w in enumerate(words):
        if w.vocalized or text[w.end:w.end + 1] in ("'", hyphen) or text[w.start - 1:w.start] == hyphen:
            continue
        t = _INDEX.name_at(ctx, i)
        if t is None:
            continue
        k = max(w.skeleton.rfind(STEMS[t]), 0)  # skip prefix letters (ל, ב, ו...)
        cut = w.letters[k].end
        out.append(text[pos:cut] + hyphen)
        pos = cut
    out.append(text[pos:])
    return "".join(out)
