"""Misspellings and confusions, as the dictionaries phrase them (invented text)."""
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from inventory.confusables import Confusion, build, clean_words, confusions, misspellings, notes_text, peu_title

LEX = frozenset({"glim", "glum", "glimmer", "glummer", "their", "there", "glimate", "glimmate", "your", "reader"})


def pairs(name, headword, text, html=""):
    return [c.words for c in confusions(name, headword, html, text)]


def _query(path: Path, sql: str) -> list[tuple]:
    with closing(sqlite3.connect(path)) as con:
        return con.execute(sql).fetchall()


class Confusions(unittest.TestCase):
    def test_peu_titles(self):
        self.assertEqual(peu_title("glim , glum and glimmer"), ("glim", "glum", "glimmer"))
        self.assertEqual(peu_title("glimate(ly) and glimmate(ly)"), ("glimate", "glimmate"))
        self.assertEqual(peu_title("(a)glim and glum (noun and verb)"), ("glim", "glum"))
        self.assertEqual(peu_title("glim and glum : verbs"), ("glim", "glum"))
        self.assertEqual(peu_title("glim / glum and glummer"), ("glim", "glum", "glummer"))
        self.assertIsNone(peu_title("Glim and Glum introduction"))
        self.assertIsNone(peu_title("-glim and -glum"))
        self.assertIsNone(peu_title("ability : glim and glum"))  # the words are the topic's, after the colon
        self.assertIsNone(peu_title("glim , glum etc"))
        def entry(title, section):
            return (f'<span class="institle">{title}</span><span class="breadcrumb"><span class="l1" isparent="y">'
                    f'<a class="Ref" href="entry://{section} introduction">x</a></span></span>')
        self.assertEqual(pairs("peu", "", "", entry("glim ,  glum  and  glimmer", "word problems from a to z")),
                         [("glim", "glum", "glimmer")])
        self.assertEqual(pairs("peu", "", "", entry("glim and glum", "adverbs and adverbials")), [("glim", "glum")])
        self.assertEqual(pairs("peu", "", "", entry("glim , glum and glimmer", "adverbs and adverbials")), [])
        self.assertEqual(pairs("peu", "", "", entry("glims and glums", "modal auxiliary verbs")), [])
        self.assertEqual(pairs("peu", "", "", entry("gl and lg", "word formation and spelling")), [])

    def test_grammar_terms_are_not_words_to_confuse(self):
        self.assertEqual(clean_words(("adjectives", "glim"), LEX | {"adjectives"}), ("glim",))
        self.assertIn(("glim", "glum"), pairs("cald", "glim", "Do not confuse with the noun, glum . Thesaurus"))

    def test_a_title_is_read_whole_or_not_at_all(self):
        topic = Confusion("peu", ("glim", "glum", "glummest adjectives"), "confused", "", whole=True)
        prose = Confusion("cald", ("glim", "glimmer", "glummest adjectives"), "confused", "")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "c.db"
            build([], [topic, prose], LEX, out)
            found = _query(out, "SELECT word_a, word_b FROM confusable")
        self.assertEqual(found, [("glim", "glimmer")])

    def test_one_set_filed_under_each_word_is_one_set(self):
        sets = [Confusion("peu", w, "confused", "", whole=True) for w in (("glim", "glum", "glimmer"),
                                                                           ("glum", "glimmer", "glim"))]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "c.db"
            build([], sets, LEX, out)
            found = _query(out, "SELECT words FROM confusable_set")
        self.assertEqual(found, [('["glim", "glimmer", "glum"]',)])

    def test_phrasings(self):
        self.assertIn(("glim", "glum"), pairs("cobuild", "glim", "Usage Note : Do not confuse glim and glum ."))
        self.assertIn(("glum", "glim"), pairs("ldoce", "glum", "Do not confuse the adjective glum /ɡlʌm/ with the verb glim ."))
        self.assertIn(("glim", "glum"), pairs("ode", "glim", "For an explanation of the difference between glim and glum , see"))
        self.assertIn(("glim", "glum"), pairs("cald", "glim", "Common mistake : glim or glum? ! Warning: Choose the right word!"))
        self.assertIn(("glim", "glum"), pairs("cobuild", "glim", "Glim and glum are often confused."))
        self.assertIn(("glim", "glum"), pairs("oald", "glim", "Do not confuse this verb with to glum (= to frown) ."))

    def test_things_confused_with_things_are_not_words_confused(self):
        self.assertEqual(pairs("ode", "glim", "Glim is often confused with the glum moth, which ..."), [])
        self.assertIn(("glim", "glum"), pairs("ode", "glim", "Glim is often confused with the verb glum ."))
        self.assertEqual([clean_words(p, LEX | {"and"}) for p in pairs("ode", "glim", "and are sometimes confused with glum")],
                         [("glum",)])

    def test_examples_are_not_warnings(self):
        html = '<span class="def">a sweet</span><span class="x">the difference between glim and glum is small</span>'
        self.assertEqual(pairs("ode", "glim", "the difference between glim and glum is small", html), [])

    def test_an_example_with_markup_inside_is_left_out_whole(self):
        html = ('<span class="def">a sweet</span><span class="x"><span class="hl">Glim</span> and glum are often '
                'confused.</span>')
        self.assertEqual(notes_text(html), "a sweet")
        self.assertEqual(pairs("ode", "glim", "a sweet Glim and glum are often confused.", html), [])

    def test_the_word_after_the_target_is_not_part_of_it(self):
        found = list(confusions("oald", "glim", "", "glim , not to be confused with glum which means sad ."))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "c.db"
            build([], found, LEX, out)
            rows = _query(out, "SELECT word_a, word_b FROM confusable")
        self.assertEqual(rows, [("glim", "glum")])

    def test_sound_keys(self):
        from inventory.sound_alikes import _sound_key, _weak_form
        from inventory.ipa import analyse
        self.assertEqual(_sound_key("əˈfekt"), _sound_key("ɪˈfekt"))      # affect, effect
        self.assertNotEqual(_sound_key("it"), _sound_key("ɪt"))           # eat, it
        self.assertNotEqual(_sound_key("ˈfʊlə"), _sound_key("ˈfʊli"))     # fuller, fully
        self.assertTrue(_weak_form(analyse("əz")))
        self.assertFalse(_weak_form(analyse("sɝː")))                     # a full r-coloured vowel (sir)
        self.assertTrue(_weak_form(analyse("ɚ")))                        # a reduced one

    def test_oald_boxes(self):
        html = ('<span class="unbox" unbox="homophone" id="x"><span class="box_title">Homophones '
                '<span class="closed">glim | glum</span></span>')
        self.assertEqual(list(confusions("oald", "glim", html, "")), [Confusion("oald", ("glim", "glum"), "homophone", "")])

    def test_cleaning(self):
        self.assertEqual(clean_words(("your reader", "glim"), LEX), ("glim",))
        self.assertEqual(clean_words(("their", "there"), LEX, free_text=False), ("their", "there"))


class Misspellings(unittest.TestCase):
    def test_cald_learner_errors_with_hint(self):
        found = list(misspellings("cald", "glimmer", "! Warning: Check your spelling! ! Glimmer is one of the 50 words "
                                  "most often spelled wrongly by learners. ! Remember: the correct spelling has 'mm'. ", LEX))
        self.assertEqual([(m.word, m.hint, m.kind) for m in found], [("glimmer", "the correct spelling has 'mm'.", "learner_error")])

    def test_med_wrong_forms(self):
        text = "Get It Right!: glimmate Note that the correct spelling is glimmate (not 'glimate'): ✗ A glimmmate day."
        found = list(misspellings("med", "glimmate", text, LEX | {"day"}))
        self.assertEqual(found[0].wrong, ("glimmmate",))   # 'glimate' is itself a word here; glimmmate is not

    def test_chambers_misspellings_but_not_etymologies(self):
        def read(headword, text):
            return [(m.word, m.wrong) for m in misspellings("chambers", headword, text, LEX)]
        self.assertEqual(read("glimate", "glīˈmate noun A misspelling of glimmate"), [("glimmate", ("glimate",))])
        self.assertEqual(read("glimate", "glimate an obsolete misspelling of glimmate"), [("glimmate", ("glimate",))])
        self.assertEqual(read("glum", "glum (also gloom) from Old Glim, a facetious misspelling of glim correct"), [])

    def test_often_misspelled(self):
        found = list(misspellings("noad", "glimmer", "Usage: Glimmer is often misspelled as glimer .", LEX))
        self.assertEqual([(m.word, m.wrong) for m in found], [("glimmer", ("glimer",))])


if __name__ == "__main__":
    unittest.main()
