"""Regressions for the defects an independent code review found (invented words where possible)."""
import unittest

from inventory.collocation_sources import ocd_label
from inventory.confusables import confusions, misspellings
from inventory.families import relation
from inventory.labels import normalize
from inventory.levels import ldoce
from inventory.notation import parse
from inventory.sound_alikes import _sound_key
from inventory.spelling import spelled_alike


def read(label):
    return sorted(f"{l.axis}:{l.value}" for l in normalize(label))


class Findings(unittest.TestCase):
    def test_a_vowel_alone_is_not_a_respelling(self):
        self.assertFalse(spelled_alike("glimplement", "glimpliment"))   # complement/compliment
        self.assertFalse(spelled_alike("glesson", "glessen"))           # lesson/lessen
        self.assertTrue(spelled_alike("cajuglut", "kajeglut"))          # a c/k respelling beside the vowel
        self.assertNotEqual(relation("glimplement", "glimpliment"), "variant")

    def test_or_joins_two_labels(self):
        self.assertEqual(read("formal or literary"), ["register:formal", "register:literary"])
        self.assertEqual(read("transitive, usually passive"), ["grammar:V n", "grammar:usu passive"])
        self.assertEqual(read("dated, informal (Brit.)"), ["region:GB", "register:informal", "time:dated"])

    def test_a_hedge_inside_a_label_is_dropped_not_noise(self):
        self.assertEqual(read("INFORMAL MAINLY DISAPPROVING"), ["attitude:disapproving", "register:informal"])
        self.assertEqual(read("BrE also"), ["region:GB"])
        self.assertEqual(read("Chiefly British Vulgar Slang"), ["region:GB", "register:slang", "register:vulgar"])
        self.assertEqual(read("formal or literary"), ["register:formal", "register:literary"])

    def test_hedged_labels_from_the_fresh_sample(self):
        self.assertEqual(read("colloquial (originally and chiefly U.S.)"), ["region:US", "register:informal"])
        self.assertEqual(read("dialect chiefly British"), ["region:GB", "region:dialect"])
        self.assertEqual(read("transitive usually + adverb/preposition"), ["grammar:V n", "grammar:~ adv/prep"])
        self.assertEqual(read("intransitive, transitive usually in questions and negatives"),
                         ["grammar:V", "grammar:V n", "grammar:with negative"])
        self.assertEqual(read("when tr, usually passive"), ["grammar:V n", "grammar:usu passive"])
        self.assertEqual(read("mainly tr; often takes a clause as object or an infinitive"),
                         ["grammar:usu V n", "grammar:~ that", "grammar:~ to-inf"])
        self.assertEqual(read("with obj. and usu. infinitive"), ["grammar:V n to-inf"])
        self.assertEqual(read("also especially ScotE"), ["region:SC"])
        self.assertEqual(read("now chiefly in the names of buildings"), ["kind:in names", "selection:buildings"])
        self.assertEqual(read("another reading as; now"), ["none:another reading as; now"])  # a textual note
        self.assertEqual(read("originally U.S."), [])  # where it came from, not where it is used

    def test_separable_only_before_a_final_particle(self):
        self.assertTrue(parse("glim something off").separable)
        self.assertTrue(parse("glim somebody off with something").separable)
        self.assertFalse(parse("glim somebody on their toes").separable)
        self.assertFalse(parse("glim something in aspic").separable)

    def test_a_spaced_slash(self):
        self.assertEqual(sorted(" ".join(v) for v in parse("be / glim out like a light").variants),
                         ["be out like a light", "glim out like a light"])

    def test_ocd_labels_with_plurals_accents_and_two_headwords(self):
        self.assertEqual(ocd_label("VERB + GLIMS", "glim")[:2], ("VERB", "before"))
        self.assertEqual(ocd_label("VERB + CLICHé", "cliché")[:2], ("VERB", "before"))
        self.assertEqual(ocd_label("GLIM/GLAM + VERB", "glim, glam")[:2], ("VERB", "after"))

    def test_nonstandard_takes_one_word(self):
        found = list(misspellings("noad", "glang", "glang nonstandard spelling of glong representing speech", frozenset()))
        self.assertEqual([(m.word, m.wrong) for m in found], [("glong", ("glang",))])

    def test_a_relative_pronoun_is_the_headword(self):
        words = [c.words for c in confusions("ode", "glimitate", "", "glimitate, which is often confused with glumitate .")]
        self.assertIn(("glimitate", "glumitate"), words)

    def test_a_colon_for_length(self):
        self.assertEqual(_sound_key("ˈɡliːm"), _sound_key("ˈɡli:m"))

    def test_an_ldoce_mark_no_rule_reads_fails(self):
        head = ('<span class="entryhead"><span class="freq" title="Top">X9</span><span class="pos"> noun</span>'
                '</span><span class="Sense">x</span>')
        with self.assertRaises(ValueError):
            list(ldoce(head))


if __name__ == "__main__":
    unittest.main()
