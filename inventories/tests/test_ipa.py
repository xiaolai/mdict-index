"""Reading IPA: nuclei, stress, segments."""
import unittest

from inventory.ipa import Stress, analyse, contrast, variants, weak


class Analyse(unittest.TestCase):
    def test_stress_position(self):
        self.assertEqual(analyse("ˈɒbdʒɪkt")[:2], (2, 1))
        self.assertEqual(analyse("əbˈdʒekt")[:2], (2, 2))
        self.assertEqual(analyse("ˌekəˈnɒmɪk◂"), Stress(4, 3, (1,), "ekənɒmɪk"))
        self.assertEqual(analyse("fəˈtɒɡ.rə.fi")[:2], (4, 2))
        self.assertEqual(analyse("ˈfəʊt ə ɡrɑːf")[:2], (3, 1))       # LPD spaces

    def test_nuclei(self):
        self.assertEqual(analyse("ˈbiːɪŋ")[0], 2)                      # a long vowel ends its nucleus
        self.assertEqual(analyse("ɪˈkeɪʃn̩")[0], 3)                     # a syllabic consonant
        self.assertEqual(analyse("haʊs"), Stress(1, 1, (), "haʊs"))    # a diphthong, no stress mark needed

    def test_a_colon_is_a_length_mark(self):
        self.assertEqual(analyse("ˈɡlɜ:d"), analyse("ˈɡlɜːd"))
        self.assertEqual(contrast(analyse("ˈɡlɜ:d").segments, analyse("ˈɡlɜːd").segments), "")
        self.assertEqual(analyse("ˈɡli:ɪŋ")[0], 2)                     # it ends its nucleus, as ː does

    def test_hiatus_is_marked_in_the_segments(self):
        self.assertEqual(analyse("ˈɡle.ɪ").segments, "ɡle.ɪ")
        self.assertEqual(analyse("ˈɡleɪ").segments, "ɡleɪ")            # a diphthong
        self.assertEqual(analyse("ˈɡliːɪŋ").segments, analyse("ˈɡliː.ɪŋ").segments)  # printed break or not
        self.assertEqual(analyse("ˈfaɪə").segments, analyse("ˈfaɪ.ə").segments)

    def test_no_analysis(self):
        self.assertIsNone(analyse("-ˈnɑː.mɪk"))   # partial
        self.assertIsNone(analyse("ˈɑːb-"))
        self.assertIsNone(analyse("iːkənɒmɪk"))   # several syllables, no stress mark

    def test_variants(self):
        self.assertEqual(variants("ˈɒb.dʒɪkt, -dʒekt"), ["ˈɒb.dʒɪkt", "-dʒekt"])


class Contrast(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(contrast("juːs", "juːz"), "voicing")
        self.assertEqual(contrast("estɪmət", "estɪmeɪt"), "ate")
        self.assertEqual(contrast("estəmət", "estɪmeɪt"), "ate")   # the stem's own vowel varies too
        self.assertEqual(contrast("lɪv", "laɪv"), "vowel")
        self.assertEqual(contrast("rekɔːd", "rekɔːd"), "")

    def test_weak_vowels_are_one(self):
        self.assertEqual(weak("riːɪnfɔːsiŋ"), weak("riːɪnfɔːsɪŋ"))
        self.assertEqual(weak("skavɪndʒ"), weak("skavəndʒ"))
        self.assertNotEqual(weak("lɪv"), weak("laɪv"))                     # a diphthong is not weak
        self.assertNotEqual(weak("feɪ"), weak("feə"))
        self.assertEqual(weak("ɪkskjuːs")[-3:], "uːs")

    def test_weak_vowels_in_hiatus_are_one(self):
        self.assertEqual(weak(analyse("ˈɡle.ɪ").segments), weak(analyse("ˈɡle.ə").segments))
        self.assertNotEqual(weak(analyse("ˈɡleɪ").segments), weak(analyse("ˈɡle.ə").segments))
        self.assertEqual(weak(analyse("ˈɡle.ɪ").segments), "ɡleə")     # the key carries no marks


if __name__ == "__main__":
    unittest.main()
