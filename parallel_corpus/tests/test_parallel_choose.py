"""Which probed dictionaries the parallel corpus is built from."""
import unittest

from parallel.choose import choose, kept_twice, parsed_dictionaries


def row(**kw):
    base = {"id": "d1", "name": "An English-Chinese dictionary", "folder": "f", "file": "d.mdx", "bytes": 1000,
            "status": "ok", "pairs": 10, "pairs_loose": 12, "pairs_foreign": 0, "pairs_zh_en": 9,
            "align_en_zh": 0.72, "aligned_en_zh": 40, "align_zh_en": 0.35, "aligned_zh_en": 30,
            "pairs_per_100k_chars": 40.0}
    return {**base, **kw}


class Choose(unittest.TestCase):
    def test_a_bilingual_dictionary_is_downloaded_in_its_better_order(self):
        c = choose(row(), {})
        self.assertTrue(c.keep)
        self.assertEqual((c.source, c.order, c.alignment), ("download", "en-zh", 0.72))
        c = choose(row(align_en_zh=0.3, align_zh_en=0.7), {})
        self.assertEqual((c.keep, c.order), (True, "zh-en"))

    def test_an_already_parsed_dictionary_is_read_from_layer2(self):
        c = choose(row(), {"d1": "cobuild-ec"})
        self.assertEqual((c.keep, c.source, c.key), (True, "layer2", "cobuild-ec"))

    def test_chinese_that_does_not_translate_the_english_is_dropped(self):
        c = choose(row(align_en_zh=0.18, align_zh_en=0.09), {})  # a blog
        self.assertFalse(c.keep)
        self.assertEqual(c.reason, "alignment 0.18 over 40 pairs: not clearly translations")

    def test_a_middling_alignment_needs_enough_pairs_to_count(self):
        # an encyclopedia's few stray sentences vs a Chinese-first dictionary with idiomatic English
        self.assertFalse(choose(row(align_en_zh=0.43, aligned_en_zh=7, align_zh_en=None, aligned_zh_en=0), {}).keep)
        self.assertTrue(choose(row(align_en_zh=None, aligned_en_zh=0, align_zh_en=0.46, aligned_zh_en=40), {}).keep)

    def test_the_order_that_qualifies_wins_over_a_higher_mean_on_too_few_pairs(self):
        c = choose(row(align_en_zh=0.65, aligned_en_zh=4, align_zh_en=0.506, aligned_zh_en=8), {})
        self.assertEqual((c.keep, c.order, c.alignment, c.aligned), (True, "zh-en", 0.506, 8))
        # with neither order qualifying, the reason still describes the higher mean
        c = choose(row(align_en_zh=0.65, aligned_en_zh=4, align_zh_en=0.2, aligned_zh_en=8), {})
        self.assertEqual((c.keep, c.reason), (False, "4 scored pairs in the sample"))

    def test_too_few_scored_pairs_is_dropped(self):
        c = choose(row(aligned_en_zh=3, aligned_zh_en=1), {})
        self.assertFalse(c.keep)
        self.assertEqual(c.reason, "3 scored pairs in the sample")
        c = choose(row(align_en_zh=None, aligned_en_zh=0, align_zh_en=None, aligned_zh_en=0), {})
        self.assertEqual(c.reason, "0 scored pairs in the sample")

    def test_a_dictionary_of_another_language_beside_chinese_is_dropped(self):
        # a Japanese-Chinese dictionary: a few romanised lines look English, most pairs do not
        c = choose(row(pairs_loose=2, pairs_foreign=254), {})
        self.assertFalse(c.keep)
        self.assertTrue(c.reason.startswith("mostly another language"), c.reason)

    def test_unreadable_and_failed_probes_are_dropped_with_their_reason(self):
        c = choose(row(status="unreadable", reason="truncated: the index needs 9 bytes, the file has 5"), {})
        self.assertFalse(c.keep)
        self.assertEqual(c.reason, "unreadable: truncated: the index needs 9 bytes, the file has 5")


class KeptTwice(unittest.TestCase):
    def test_one_file_under_two_ids_is_found(self):
        old, new = choose(row(id="old", name="Dict V2"), {}), choose(row(id="new", name="Dict V2.4"), {})
        self.assertEqual(kept_twice([old, new]), ["f/d.mdx"])
        self.assertEqual(kept_twice([old, choose(row(id="other", file="e.mdx"), {})]), [])

    def test_a_dropped_duplicate_is_no_duplicate(self):
        dropped = choose(row(id="old", status="error", reason="x"), {})
        self.assertFalse(dropped.keep)
        self.assertEqual(kept_twice([dropped, choose(row(id="new"), {})]), [])


class Extractors(unittest.TestCase):
    def test_a_styled_dictionary_is_kept_with_its_extractor(self):
        from parallel.choose import with_extractor
        overrides = {"d1": {"extractor": "styled", "truth": "ahd"}}
        c = with_extractor(choose(row(align_en_zh=0.2, align_zh_en=0.1), {}), overrides)  # text alignment low
        self.assertEqual((c.keep, c.extractor, c.truth), (True, "styled", "ahd"))
        self.assertEqual(with_extractor(choose(row(), {}), {}).extractor, "text")
        broken = choose(row(status="unreadable", reason="truncated"), {})
        self.assertFalse(with_extractor(broken, overrides).keep)

    def test_the_committed_overrides_are_well_formed(self):
        from parallel.choose import extractor_overrides
        for id, v in extractor_overrides().items():
            self.assertRegex(id, r"^[0-9a-f]{12}$")
            self.assertEqual(set(v), {"extractor", "truth"})
            self.assertIn(v["extractor"], {"styled"})


class Parsed(unittest.TestCase):
    def test_every_parsed_dictionary_maps_to_a_real_parser(self):
        from structured.parsers import registry
        parsed = parsed_dictionaries()
        self.assertGreaterEqual(len(parsed), 20)
        self.assertTrue(set(parsed.values()) <= set(registry()))


if __name__ == "__main__":
    unittest.main()
