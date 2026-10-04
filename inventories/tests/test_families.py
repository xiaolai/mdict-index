"""Word families and spelling variants (invented words and markup)."""
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from inventory.families import Link, build, inflection_links, lemma_index, oald_family, relation
from inventory.spelling import spelling_regions


class Relation(unittest.TestCase):
    def test_suffixed_with_a_changed_stem(self):
        self.assertEqual(relation("glide", "glision"), "suffixed")
        self.assertEqual(relation("reserve", "reservation"), "suffixed")
        self.assertEqual(relation("glim", "glimmishness"), "suffixed")
        self.assertEqual(relation("skydiving", "skydiver"), "sibling")          # two suffixes on one stem
        self.assertEqual(relation("glimscription", "glimscriptive"), "sibling")    # -ion/-ive on one stem
        self.assertEqual(relation("glimothermic", "glimothermism"), "sibling")     # -ic/-ism
        self.assertEqual(relation("glamour", "glamor"), "variant")
        self.assertEqual(relation("glimpose", "glimposer"), "suffixed")          # a silent e

    def test_prefixed_also_on_a_derivative(self):
        self.assertEqual(relation("glided", "unglided"), "prefixed")
        self.assertEqual(relation("glide", "unglisive"), "prefixed")

    def test_spellings_no_alternation_names(self):
        self.assertEqual(relation("glowcker", "glowccer"), "variant")
        self.assertEqual(relation("glimafin", "glimaphin"), "variant")
        self.assertEqual(relation("co-glimation", "coglimation"), "variant")
        self.assertEqual(relation("glimor", "glimory"), "suffixed")        # a suffix, not a spelling
        self.assertEqual(relation("glexane", "glexene"), "related")        # a vowel alone: another word
        self.assertEqual(relation("glim club", "glimclub"), "variant")
        self.assertEqual(relation("glimangi-", "glimangio-"), "variant")
        self.assertEqual(relation("glesiodic", "glesiodian"), "sibling")

    def test_two_inflections_and_regular_verb_forms(self):
        lemma_of = {"glimming": "glim", "glimmed": "glim"}
        self.assertEqual(relation("glimming", "glimmed", lemma_of=lemma_of), "inflection")
        self.assertEqual(relation("glimicize", "glimicized"), "inflection")

    def test_a_form_of_two_lemmas_keeps_both(self):
        # "glimses" is both the verb glimse's -s form and the noun glimsis's plural: neither lemma may win
        lemma_of = lemma_index({"glimse": {"glimsed", "glimses"}, "glimsis": {"glimses"}})
        self.assertEqual(lemma_of["glimses"], frozenset({"glimse", "glimsis"}))
        self.assertEqual(relation("glimsed", "glimses", lemma_of=lemma_of), "inflection")
        self.assertEqual(relation("glimsed", "glimses", lemma_of=lemma_index({"glimsis": {"glimses"},
                                                                               "glimse": {"glimsed", "glimses"}})),
                         "inflection")  # whichever lemma is read last

    def test_inflections_and_affix_entries(self):
        self.assertEqual(relation("glide", "glided", forms=frozenset({"glided", "glides"})), "inflection")
        self.assertEqual(relation("re-", "reglide"), "prefixed")
        self.assertEqual(relation("-glimeter", "barglimeter"), "suffixed")
        self.assertEqual(relation("estivate", "aestivates"), "related")   # a spelling, not a prefix "a"

    def test_compounds_and_the_rest(self):
        self.assertEqual(relation("fibre", "fibreboard", frozenset({"board"})), "compound")
        self.assertEqual(relation("strip", "strip map"), "compound")
        self.assertEqual(relation("glim", "glim"), "conversion")
        self.assertEqual(relation("glim", "zorbax"), "related")

    def test_regions_of_a_spelling_pair(self):
        self.assertEqual(spelling_regions("glamour", "glamor"), ("GB", "US"))
        self.assertEqual(spelling_regions("theater", "theatre"), ("US", "GB"))
        self.assertEqual(spelling_regions("organise", "organize"), ("", ""))


BOX = """<span class="unbox" unbox="wordfamily"><span class="box_title">Word Family</span><span class="body"><ul class="ul">
<li class="li"><span class="p"><span class="wfw">glide</span> <span class="wfp" wfp="v">verb</span></span></li>
<li class="li"><span class="p"><span class="wfw">glision</span> <span class="wfp" wfp="n">noun</span>
<span class="wfo">(≠ unglision)</span></span></li></ul></span></span>"""


class InflectionLinks(unittest.TestCase):
    def test_two_forms_of_one_lemma_are_inflections(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "inflections.db"
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE other (form TEXT, lemma TEXT, kind TEXT, dictionaries TEXT)")
            con.execute("INSERT INTO other VALUES ('displuffed', 'displuffing', 'derivative', '[\"ode\"]')")
            con.commit()
            con.close()
            forms = {"displuff": frozenset({"displuffed", "displuffing", "displuffs"})}
            links = list(inflection_links(db, forms, lemma_index(forms)))
        self.assertEqual(links, [Link("displuffing", "displuffed", "", "inflection", "ode")])


class Words(unittest.TestCase):
    def test_stress_marks_are_not_letters(self):
        from inventory.families import _word
        self.assertEqual(_word("misˈglimly"), "misglimly")


class Oald(unittest.TestCase):
    def test_a_word_family_box(self):
        self.assertEqual(oald_family(BOX), [("glide", "verb", []), ("glision", "noun", ["unglision"])])


class Build(unittest.TestCase):
    def test_families_join_derivatives_and_variants_but_not_compounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f.db"
            summary = build([Link("glide", "glision", "NOUN", "suffixed", "ode"),
                             Link("glide", "glision", "NOUN", "suffixed", "ced"),
                             Link("glision", "unglision", "NOUN", "opposite", "oald"),
                             Link("glide", "glidepath", "NOUN", "compound", "chambers"),
                             Link("glamour", "glamor", "", "variant", "ode"),
                             Link("re-", "reglide", "", "prefixed", "ode"), Link("re-", "reglim", "", "prefixed", "ode")],
                            out)
            with closing(sqlite3.connect(out)) as con:
                families = con.execute("SELECT family_id, group_concat(word, ' ') FROM family GROUP BY family_id").fetchall()
                links = con.execute("SELECT base, member, relation, n FROM link ORDER BY base, member").fetchall()
                variants = con.execute("SELECT * FROM variant").fetchall()
        self.assertEqual(sorted(f[1] for f in families), ["glamor glamour", "glide glision unglision"])
        self.assertIn(("glide", "glision", "suffixed", 2), links)
        self.assertEqual(variants, [("glamour", "glamor", "GB", "US", '["ode"]', 1)])
        self.assertEqual(summary["relations"]["compound"], 1)


if __name__ == "__main__":
    unittest.main()
