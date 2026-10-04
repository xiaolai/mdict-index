"""Printed parts of speech normalised to Universal POS tags and features."""
import unittest

from inventory.pos import normalize


def tags(printed):
    return set(normalize(printed).tags)


class Normalize(unittest.TestCase):
    def test_the_common_spellings(self):
        for printed, expected in [("noun", {"NOUN"}), ("n.", {"NOUN"}), ("adjective", {"ADJ"}), ("a.", {"ADJ"}),
                                  ("adv.", {"ADV"}), ("ad.", {"ADV"}), ("prep.", {"ADP"}), ("pron.", {"PRON"}),
                                  ("determiner", {"DET"}), ("exclamation", {"INTJ"}), ("名词", {"NOUN"})]:
            self.assertEqual(tags(printed), expected, printed)

    def test_verbs_carry_transitivity(self):
        self.assertEqual(normalize("vt.").features["Transitivity"], "Transitive")
        self.assertEqual(normalize("intr.v.").features["Transitivity"], "Intransitive")
        self.assertEqual(normalize("tr. & intr.v.").features["Transitivity"], "Both")
        self.assertEqual(tags("tr.v."), {"VERB"})

    def test_cobuild_codes(self):
        self.assertEqual((tags("N-COUNT"), normalize("N-COUNT").features), ({"NOUN"}, {"Countability": "Count"}))
        self.assertEqual(tags("ADJ-GRADED"), {"ADJ"})
        self.assertEqual(tags("V-ERG"), {"VERB"})
        self.assertEqual(tags("N-PROPER"), {"PROPN"})
        self.assertEqual(normalize("PHRASAL VERB").features["Kind"], "Phrase")
        self.assertEqual(tags("COLOUR"), {"ADJ", "NOUN"})  # colour words
        self.assertEqual(tags("QUANT"), {"DET"})

    def test_registered_hyphenated_codes_win_over_their_parts(self):
        self.assertEqual(tags("CONJ-SUBORD"), {"SCONJ"})
        self.assertEqual(tags("N-TITLE"), {"PROPN"})
        self.assertEqual(tags("N-IN-NAMES"), {"PROPN"})
        self.assertEqual(tags("CONJ-COORD"), {"CCONJ"})

    def test_a_registered_hyphenated_code_loses_nothing_its_parts_say(self):
        found = normalize("PREP-PHRASE")
        self.assertEqual((set(found.tags), found.features), ({"ADP"}, {"Kind": "Phrase"}))
        from inventory.pos import _HYPHEN, _WORDS
        for code in (w for w in _WORDS if _HYPHEN.search(w)):  # whole, a code may retag (SCONJ), never untag
            parts = [_WORDS[p] for p in _HYPHEN.split(code) if p in _WORDS]
            whole = normalize(code)
            self.assertTrue(whole.tags or not any(t for t, _ in parts), code)
            self.assertLessEqual({k for _, f in parts for k in f}, set(whole.features), code)

    def test_a_qualified_conjunction_is_one_tag(self):
        self.assertEqual(tags("subordinating conjunction"), {"SCONJ"})
        self.assertEqual(tags("conjunction"), {"CCONJ"})

    def test_agreement_phrases_ignore_spacing(self):
        both = normalize("noun singular or  plural in construction").features
        self.assertEqual(both, {"Agreement": "Both"})
        self.assertEqual(normalize("noun plural  but\tsingular  in construction").features,
                         {"Number": "Plur", "Agreement": "Sing"})

    def test_combinations_and_homograph_numbers(self):
        self.assertEqual(tags("n. & v."), {"NOUN", "VERB"})
        self.assertEqual(tags("adjective (or adverb)"), {"ADJ", "ADV"})
        self.assertEqual(tags("n.1"), {"NOUN"})
        news = normalize("noun plural but singular in construction").features
        self.assertEqual((news["Number"], news["Agreement"]), ("Plur", "Sing"))

    def test_abbreviations_affixes_and_names(self):
        self.assertEqual(normalize("abbr.").features["Kind"], "Abbreviation")
        self.assertEqual((tags("noun combining form"), normalize("noun combining form").features["Kind"]),
                         ({"X"}, "CombiningForm"))
        self.assertEqual(tags("geographical name"), {"PROPN"})

    def test_unknown_strings_are_reported_not_guessed(self):
        self.assertFalse(normalize("informal").known)  # a register label, not a part of speech
        self.assertFalse(normalize("").known)


if __name__ == "__main__":
    unittest.main()
