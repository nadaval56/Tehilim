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


class Liturgy(unittest.TestCase):
    def test_orders_read_from_the_siddur(self):
        doc = json.loads((ROOT / "data" / "orders.json").read_text(encoding="utf-8"))["orders"]
        self.assertEqual([x["psalm"] for x in doc["tachanun"]["ashkenaz"]["psalms"]], [6])
        self.assertEqual([x["psalm"] for x in doc["tachanun"]["sefard"]["psalms"]], [6])
        self.assertEqual([x["psalm"] for x in doc["tachanun"]["edot"]["psalms"]], [25])
        for slug in ("pesukei-dezimra", "pesukei-dezimra-shabbat"):
            for nus, o in doc[slug].items():
                p130 = [x for x in o["psalms"] if x["psalm"] == 130]
                self.assertTrue(p130 and p130[0].get("rubric"), (slug, nus))
        for nus in ("ashkenaz", "sefard", "edot"):
            p91 = [x for x in doc["motzaei-shabbat"][nus]["psalms"] if x["psalm"] == 91]
            self.assertTrue(p91 and p91[0]["lead"]["psalm"] == 90 and p91[0]["lead"]["to"] == 17, nus)
        self.assertEqual([x["psalm"] for x in doc["kabbalat-shabbat"]["ashkenaz"]["psalms"]],
                         [95, 96, 97, 98, 99, 29, 92, 93])

    def test_hallel_is_113_to_118_in_every_nusach(self):
        doc = json.loads((ROOT / "data" / "liturgy.json").read_text(encoding="utf-8"))
        for nus in doc["nusachim"]:
            got = {e["psalm"] for e in doc["entries"] if e["context"] == "hallel" and e["nusach"] == nus}
            self.assertEqual(got, set(range(113, 119)), nus)

    def test_shir_shel_yom_found_for_every_day(self):
        doc = json.loads((ROOT / "data" / "liturgy.json").read_text(encoding="utf-8"))
        days = doc["shir_shel_yom_mishnah"]
        self.assertEqual(len(days), 7)
        self.assertTrue(all(d["psalm"] for d in days))

    def test_quoted_verse_masks_short_names(self):
        import quotes
        from hebrew import ALEF, LAMED, NUN, QOF, MEM, VAV, TAV, HE
        el, nqmwt = ALEF + LAMED, NUN + QOF + MEM + VAV + TAV
        text = " ".join([el, nqmwt, HE + "'", el, nqmwt])  # unvocalized quote of 94:1
        words = quotes.mask_quoted(text).split()
        self.assertEqual(words[0], ALEF + "-" + LAMED)
        self.assertEqual(words[3], ALEF + "-" + LAMED)
        # an unrelated "el" (the preposition) stays as written
        self.assertEqual(quotes.mask_quoted(el + " " + HE + "x").split()[0], el)


class David(unittest.TestCase):
    def test_events(self):
        doc = json.loads((ROOT / "data" / "david_events.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(e["psalm"] for e in doc["events"]),
                         [3, 7, 18, 34, 51, 52, 54, 56, 57, 59, 60, 63, 142])
        places = {p["id"] for p in json.loads((ROOT / "data" / "places.json").read_text(encoding="utf-8"))["places"]}
        for e in doc["events"]:
            self.assertTrue(set(e["places"]) <= places)
            if e["order"]:
                self.assertIsNotNone(e["samuel_placement"])


class Inyanim(unittest.TestCase):
    def test_every_source_names_psalms(self):
        doc = json.loads((ROOT / "data" / "inyanim.json").read_text(encoding="utf-8"))
        for need in doc["needs"]:
            for src in need["sources"]:
                self.assertTrue(src["psalms"], src["title"])
                self.assertTrue(all(1 <= n <= 150 for n in src["psalms"]))


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
