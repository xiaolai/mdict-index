"""Regular inflection rules."""
import unittest

from inventory.inflect import final_stress_from_ipa, regular


def forms(lemma, upos, slot, stress=None):
    return [f for f, _ in regular(lemma, upos, stress)[slot]]


class Nouns(unittest.TestCase):
    def test_plurals(self):
        for lemma, plural in [("cat", "cats"), ("box", "boxes"), ("church", "churches"), ("city", "cities"),
                              ("day", "days"), ("hero", "heroes"), ("radio", "radios"), ("thesis", "theses"),
                              ("mutagenesis", "mutageneses"), ("gliz", "glizzes"), ("quiz", "quizzes")]:
            self.assertEqual(forms(lemma, "NOUN", "Plur"), [plural], lemma)


class Verbs(unittest.TestCase):
    def test_the_four_slots(self):
        self.assertEqual({k: [f for f, _ in v] for k, v in regular("walk", "VERB").items()},
                         {"3Sg": ["walks"], "Past": ["walked"], "PastPart": ["walked"], "PresPart": ["walking"]})

    def test_spelling_changes(self):
        self.assertEqual(forms("hope", "VERB", "Past"), ["hoped"])
        self.assertEqual(forms("hope", "VERB", "PresPart"), ["hoping"])
        self.assertEqual(forms("agree", "VERB", "PresPart"), ["agreeing"])
        self.assertEqual(forms("die", "VERB", "PresPart"), ["dying"])
        self.assertEqual(forms("carry", "VERB", "Past"), ["carried"])
        self.assertEqual(forms("carry", "VERB", "3Sg"), ["carries"])
        self.assertEqual(forms("stop", "VERB", "Past"), ["stopped"])
        self.assertEqual(forms("panic", "VERB", "Past"), ["panicked"])

    def test_doubling_follows_stress(self):
        self.assertEqual(forms("prefer", "VERB", "Past", stress=True), ["preferred"])
        self.assertEqual(forms("offer", "VERB", "Past", stress=False), ["offered"])
        self.assertEqual(forms("offer", "VERB", "Past"), ["offered"])       # unknown stress: no doubling
        self.assertEqual(forms("visit", "VERB", "Past"), ["visited"])

    def test_qu_is_a_consonant(self):
        self.assertEqual(forms("quit", "VERB", "PresPart"), ["quitting"])
        self.assertEqual(forms("equip", "VERB", "Past", stress=True), ["equipped"])
        self.assertEqual(forms("equip", "VERB", "PresPart", stress=True), ["equipping"])
        self.assertEqual(forms("quiz", "VERB", "3Sg"), ["quizzes"])
        self.assertEqual(forms("quiz", "VERB", "Past"), ["quizzed"])

    def test_monosyllables_in_en_on_om_double(self):
        self.assertEqual(forms("pen", "VERB", "Past"), ["penned"])
        self.assertEqual(forms("pen", "VERB", "PresPart"), ["penning"])
        self.assertEqual(forms("glon", "VERB", "Past"), ["glonned"])
        self.assertEqual(forms("glom", "VERB", "Past"), ["glommed"])
        self.assertEqual(forms("offer", "VERB", "Past"), ["offered"])       # unknown stress, two syllables
        self.assertEqual(forms("glisten", "VERB", "Past"), ["glistened"])

    def test_british_and_american_l(self):
        self.assertEqual(regular("travel", "VERB")["Past"], [("traveled", "US"), ("travelled", "GB")])
        self.assertEqual(regular("dial", "VERB")["Past"], [("dialed", "US"), ("dialled", "GB")])
        self.assertEqual(regular("fuel", "VERB")["PresPart"], [("fueling", "US"), ("fuelling", "GB")])
        self.assertEqual(forms("reveal", "VERB", "Past"), ["revealed"])
        self.assertEqual(forms("fail", "VERB", "Past"), ["failed"])


class Adjectives(unittest.TestCase):
    def test_comparison(self):
        self.assertEqual(forms("tall", "ADJ", "Cmp"), ["taller"])
        self.assertEqual(forms("big", "ADJ", "Sup"), ["biggest"])
        self.assertEqual(forms("happy", "ADJ", "Cmp"), ["happier"])
        self.assertEqual(forms("late", "ADJ", "Sup"), ["latest"])


class Stress(unittest.TestCase):
    def test_final_stress_from_ipa(self):
        self.assertTrue(final_stress_from_ipa("prɪˈfɜː(r)"))
        self.assertFalse(final_stress_from_ipa("ˈɒfə(r)"))
        self.assertTrue(final_stress_from_ipa("əˈdmɪt"))
        self.assertIsNone(final_stress_from_ipa("stɒp"))

    def test_a_syllabic_consonant_is_a_syllable(self):
        self.assertFalse(final_stress_from_ipa("ˈɡlʌtn̩"))
        self.assertEqual(forms("glutton", "VERB", "Past", stress=final_stress_from_ipa("ˈɡlʌtn̩")), ["gluttoned"])

    def test_vowels_in_hiatus_are_two_syllables(self):
        self.assertFalse(final_stress_from_ipa("ˈɡliː.ɪt"))    # a long vowel then another: two nuclei
        self.assertTrue(final_stress_from_ipa("ɡləˈmeɪt"))      # a diphthong is one


class NotInflected(unittest.TestCase):
    def test_hyphenated_lemmas_inflect_their_last_part(self):
        self.assertEqual(forms("flight-test", "VERB", "PresPart"), ["flight-testing"])
        self.assertEqual(forms("scrum-half", "NOUN", "Plur"), ["scrum-halfs"])

    def test_multiword_and_names_are_left_alone(self):
        self.assertEqual(regular("mother in law", "NOUN"), {})
        self.assertEqual(regular("London", "NOUN"), {})


if __name__ == "__main__":
    unittest.main()
