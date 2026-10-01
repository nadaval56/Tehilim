"""Tests for name detection and masking.

Sample words are assembled from code point constants; no holy name is
written out in this file.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import names  # noqa: E402
from hebrew import (  # noqa: E402
    ALEF, BET, DALET, HE, VAV, YOD, LAMED, MEM, NUN, SHIN, TSADI, TAV, AYIN, FINAL_MEM,
    SHEVA, HATAF_SEGOL, HATAF_PATAH, HIRIQ, TSERE, SEGOL, PATAH, QAMATS, HOLAM, DAGESH, SHIN_DOT,
    MAQAF, hebrew_numeral, tokenize,
)

HAVAYAH = YOD + SHEVA + HE + VAV + QAMATS + HE
ELOKIM = ALEF + HATAF_SEGOL + LAMED + HOLAM + HE + HIRIQ + YOD + FINAL_MEM
EL = ALEF + TSERE + LAMED
EL_PREP = ALEF + SEGOL + LAMED  # "to": not a name
YAH = YOD + QAMATS + HE + DAGESH
ADNI = ALEF + HATAF_PATAH + DALET + HOLAM + NUN + QAMATS + YOD
ADONI = ALEF + HATAF_PATAH + DALET + HOLAM + NUN + HIRIQ + YOD  # "my master": not a name
SHADDAI = SHIN + SHIN_DOT + PATAH + DALET + DAGESH + PATAH + YOD
TZVAOT = TSADI + SHEVA + BET + QAMATS + ALEF + VAV + HOLAM + TAV
HALLELU = HE + PATAH + LAMED + SHEVA + LAMED + VAV + DAGESH
HAAMIM = HE + QAMATS + AYIN + PATAH + MEM + DAGESH + HIRIQ + YOD + FINAL_MEM  # "the peoples"


def types(text):
    return [m.type for m in names.find_unmasked(text)]


class Detect(unittest.TestCase):
    def test_each_name(self):
        for word, t in [(HAVAYAH, "HAVAYAH"), (ELOKIM, "ELOKIM"), (EL, "EL"), (YAH, "YAH"),
                        (ADNI, "ADNI"), (SHADDAI, "SHADDAI")]:
            self.assertEqual(types(word), [t], t)

    def test_prefixes(self):
        self.assertEqual(types(LAMED + PATAH + HAVAYAH), ["HAVAYAH"])
        self.assertEqual(types(VAV + TSERE + ELOKIM), ["ELOKIM"])

    def test_not_names(self):
        self.assertEqual(types(EL_PREP), [])
        self.assertEqual(types(ADONI), [])
        self.assertEqual(types(HALLELU + MAQAF + YAH), [])  # Halleluyah is written plainly

    def test_tzvaot_after_name(self):
        self.assertEqual(types(HAVAYAH + " " + TZVAOT), ["HAVAYAH", "TZVAOT"])

    def test_chol_candidate_context(self):
        ms = names.detect(ELOKIM[:-2] + SEGOL + YOD + " " + HAAMIM)  # "gods of the peoples"
        self.assertEqual(ms[0].chol_reason, "next-word")

    def test_unvocalized_prose(self):
        plain = YOD + HE + VAV + HE
        self.assertEqual(types("abc " + plain + " xyz"), ["HAVAYAH"])
        self.assertEqual(types(ALEF + LAMED), [])  # unvocalized "el" is ambiguous: not flagged


class Mask(unittest.TestCase):
    def test_mask_removes_every_name(self):
        text = " ".join([LAMED + PATAH + HAVAYAH, ELOKIM, EL, YAH, ADNI, SHADDAI, HAVAYAH, TZVAOT])
        masked, entries = names.mask(text, names.detect(text))
        self.assertEqual(names.find_unmasked(masked), [])
        self.assertEqual(len(entries), 8)
        self.assertTrue(masked.startswith(LAMED + PATAH + HE + "'"))
        for e in entries:
            mark = "'" if e["type"] == "HAVAYAH" else "-"
            self.assertIn(mark, masked[e["start"]:e["end"]])

    def test_hyphen_keeps_niqqud(self):
        masked, _ = names.mask(ELOKIM, names.detect(ELOKIM))
        self.assertEqual(masked, ALEF + HATAF_SEGOL + "-" + LAMED + HOLAM + HE + HIRIQ + YOD + FINAL_MEM)

    def test_halleluyah_untouched(self):
        text = HALLELU + MAQAF + YAH
        masked, entries = names.mask(text, names.detect(text))
        self.assertEqual(masked, text)
        self.assertEqual(entries, [])


class Data(unittest.TestCase):
    """Stage 0 acceptance tests on the committed data."""

    def setUp(self):
        self.files = sorted((ROOT / "data" / "psalms").glob("*.json"))

    def test_150_files(self):
        self.assertEqual([f.stem for f in self.files], [f"{n:03d}" for n in range(1, 151)])

    def test_no_unmasked_names_in_data(self):
        for f in self.files:
            doc = json.loads(f.read_text(encoding="utf-8"))
            for v in doc["verses"]:
                allowed = {v["text"][e["start"]:e["end"]] for e in v["names"] if e["chol"]}
                for m in names.find_unmasked(v["text"]):
                    w = tokenize(v["text"])[m.word]
                    self.assertIn(w.raw(v["text"]), allowed, f"{f.name} v{v['v']}")

    def test_counts_match_entries(self):
        for f in self.files:
            doc = json.loads(f.read_text(encoding="utf-8"))
            n = sum(1 for v in doc["verses"] for e in v["names"] if e["counted"])
            self.assertEqual(n, sum(doc["names_count"].values()), f.name)

    def test_numerals(self):
        self.assertEqual(hebrew_numeral(15), "טו")
        self.assertEqual(hebrew_numeral(150), "קנ")
        self.assertEqual(hebrew_numeral(23, punctuate=True), 'כ"ג')


class Chida(unittest.TestCase):
    def test_every_verse_once(self):
        doc = json.loads((ROOT / "data" / "chida.json").read_text(encoding="utf-8"))
        refs = [(r["psalm"], r["verse"]) for l in doc["letters"] for r in l["verses"]]
        self.assertEqual(len(refs), len(set(refs)))
        total = sum(json.loads(f.read_text(encoding="utf-8"))["verse_count"]
                    for f in (ROOT / "data" / "psalms").glob("*.json"))
        self.assertEqual(len(refs), total)
        self.assertEqual(len(doc["letters"]), 22)


if __name__ == "__main__":
    unittest.main()
