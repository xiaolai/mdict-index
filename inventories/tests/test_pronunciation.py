"""Pronunciation inventories (invented markup and words)."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from inventory.pronunciation import Pron, build, cepd_blocks, ldoce_heads, lpd_blocks

def _query(path: Path, sql: str) -> list[tuple]:
    with closing(sqlite3.connect(path)) as con:
        return con.execute(sql).fetchall()


LDOCE = """<span class="entry"><span class="entryhead"><span class="hwd">glect</span><span class="pron">ˈɡlekt</span>
<span class="amevarpron"><span class="neutral"> $ </span>ˈɡlɑːkt</span><span class="pos"> noun</span></span><span class="Sense">x</span></span>
<span class="entry"><span class="entryhead"><span class="hwd">glect</span><span class="pron">ɡləˈkɛt</span><span class="pos"> verb</span></span></span>"""
CEPD = """<span class="di-head"><span class="di-title">glect </span><span class="di-info"><span class="pos">n</span></span></span>
<span class="di-body"><span class="prongrp"> <span class="pron">ˈɡlek.t</span>, <span class="ussymbol">US</span> <span class="pron">ˈɡlɑːk-</span></span>
<span class="inflection"> <span class="pron">-s</span></span></span>"""
LPD = """<!--Roman-->I<!--/Roman-->&nbsp;<b>glect</b> <i> noun</i> <font color=green>BrE</font> <font color=mediumblue>ˈɡlek t</font>
<font color=green>AmE</font> <font color=mediumblue>ˈɡlɑːk t</font><br>&nbsp;▷ <b>glect|s</b> <font color=mediumblue>s</font><br>
<!--Roman-->II<!--/Roman-->&nbsp;<b>glect</b> <i> verb</i> <font color=green>BrE</font> <font color=mediumblue>ɡlə ˈkɛt</font><br>"""


class Readers(unittest.TestCase):
    def test_ldoce(self):
        self.assertEqual(list(ldoce_heads(LDOCE, "glect")), [(" noun", "GB", "ˈɡlekt"), (" noun", "US", "ˈɡlɑːkt"),
                                                    (" verb", "GB", "ɡləˈkɛt")])

    def test_ldoce_a_page_shown_for_another_headword_is_not_its_pronunciation(self):
        # LDOCE shows "glectish" the page of "glect": glect's transcriptions are not glectish's
        self.assertEqual(list(ldoce_heads(LDOCE, "glectish")), [])
        named = ('<span class="entryhead"><span class="hwd">Glects, the</span><span class="pron">ɡlekts</span>'
                 '<span class="pos"> noun</span></span><span class="entryhead"><span class="hwd">glim, glimm</span>'
                 '<span class="pron">ɡlɪm</span><span class="pos"> verb</span></span>')
        self.assertEqual(list(ldoce_heads(named, "Glects")), [(" noun", "GB", "ɡlekts")])
        self.assertEqual(list(ldoce_heads(named, "glimm")), [(" verb", "GB", "ɡlɪm")])
        self.assertEqual(list(ldoce_heads(named, "Glim")), [])  # case kept: COO is not coo

    def test_cepd(self):
        self.assertEqual(list(cepd_blocks(CEPD)), [("n", "GB", "ˈɡlek.t"), ("n", "US", "ˈɡlɑːk-")])

    def test_cepd_a_labelled_transcription_is_one_sense_s(self):
        block = ('<span class="di-head"><span class="pos">n</span></span><span class="di-body">'
                 '<span class="prongrp"><span class="comment">ordinary senses: </span><span class="pron">ˈɡlez.ənt</span></span>'
                 '<span class="prongrp"><span class="comment">military term: </span><span class="pron">ɡlɪˈzent</span>, '
                 '<span class="pron">ɡlə-</span></span><span class="prongrp"><span class="pron">ˈɡlez.nt</span></span></span>')
        self.assertEqual(list(cepd_blocks(block)), [("n", "GB", "ˈɡlez.ənt"), ("n", "GB", "ˈɡlez.nt")])
        gloss = ('<span class="di-head"><span class="pos">n</span></span><span class="di-body"><span class="prongrp">'
                 '<span class="comment">air blowing: </span><span class="pron">ɡlɪnd</span></span></span>')
        self.assertEqual(list(cepd_blocks(gloss)), [("n", "GB", "ɡlɪnd")])  # names the homograph: wind n.

    def test_cepd_usage_note_examples_are_not_the_word(self):
        note = CEPD.replace('<span class="inflection">', '<span class="usagenote">Note: e.g. \'glect it\' /<span class="pron">'
                                                          'ˈɡlek.tɪt</span>/</span><span class="inflection">')
        self.assertEqual(list(cepd_blocks(note)), list(cepd_blocks(CEPD)))

    def test_lpd(self):
        self.assertEqual(list(lpd_blocks(LPD)), [("noun", "GB", "ˈɡlek t"), ("noun", "US", "ˈɡlɑːk t"),
                                                 ("verb", "GB", "ɡlə ˈkɛt")])


class Build(unittest.TestCase):
    def test_contrasts_and_family_stress(self):
        prons = [Pron("oald", "glect", "NOUN", "GB", "ˈɡlekt"), Pron("oald", "glect", "VERB", "GB", "ɡlɪˈkekt"),
                 Pron("ldoce", "glect", "NOUN", "GB", "ˈɡlekt"), Pron("ldoce", "glect", "VERB", "GB", "ˈɡlekt"),
                 Pron("oald", "gluse", "NOUN", "GB", "ɡluːs"), Pron("oald", "gluse", "VERB", "GB", "ɡluːz"),
                 Pron("oald", "glograph", "NOUN", "GB", "ˈɡləʊtəɡrɑːf"),
                 Pron("oald", "glography", "NOUN", "GB", "ɡləˈtɒɡrəfi"),
                 Pron("oald", "glographer", "NOUN", "GB", "ɡləˈtɒɡrəfə")]
        links = [("glograph", "glography", "suffixed"), ("glography", "glographer", "sibling")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "p.db"
            summary = build(prons, links, {1: ["glograph", "glography", "glographer"]}, out)
            contrasts = _query(out, "SELECT word, pos_a, pos_b, change, n, n_not FROM pos_contrast ORDER BY word")
            stress = _query(out, "SELECT base, member, stress_base, stress_member, shift FROM family_stress "
                                  "ORDER BY base")
            family = _query(out, "SELECT word, primary_stress FROM family_shift ORDER BY word")
        self.assertEqual(contrasts, [("glect", "NOUN", "VERB", "stress", 1, 1), ("gluse", "NOUN", "VERB", "voicing", 1, 0)])
        self.assertEqual(stress, [("glograph", "glography", "1/3", "2/4", 1), ("glography", "glographer", "2/4", "2/4", 0)])
        self.assertEqual(family, [("glograph", 1), ("glographer", 2), ("glography", 2)])
        self.assertEqual(summary["families_with_a_shift"], 1)

    def test_dictionaries_disagreeing_on_stress_make_it_optional(self):
        prons = [Pron("ldoce", "gledress", "NOUN", "GB", "ˈɡliːdres"), Pron("ldoce", "gledress", "VERB", "GB", "ɡlɪˈdres"),
                 Pron("cepd", "gledress", "NOUN", "GB", "ˈɡliːdres"), Pron("cepd", "gledress", "NOUN", "GB", "ɡlɪˈdres"),
                 Pron("cepd", "gledress", "VERB", "GB", "ɡlɪˈdres")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "p.db"
            build(prons, [], {}, out)
            found = _query(out, "SELECT change, n FROM pos_contrast")
        self.assertEqual(found, [("stress (optional)", 2)])

    def test_a_dictionary_votes_once_and_the_example_shows_the_winning_change(self):
        # oald shows a stress change in three regions, cald and med another change in one each:
        # two dictionaries outvote one, and the example comes from one that shows the winner
        prons = [Pron("oald", "glecter", pos, region, ipa) for region in ("GB", "US", "")
                 for pos, ipa in (("NOUN", "ˈɡlektə"), ("VERB", "ɡlekˈtə"))]
        prons += [Pron(d, "glecter", pos, "GB", ipa) for d in ("cald", "med")
                  for pos, ipa in (("NOUN", "ˈɡlektə"), ("VERB", "ˈɡlegtə"))]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "p.db"
            build(prons, [], {}, out)
            found = _query(out, "SELECT change, ipa_a, ipa_b, example_from, n FROM pos_contrast")
        self.assertEqual(len(found), 1)
        change, ipa_a, ipa_b, src, n = found[0]
        self.assertNotIn(change, ("stress", "stress (optional)"))
        self.assertEqual((ipa_a, ipa_b, src, n), ("ˈɡlektə", "ˈɡlegtə", "cald", 3))

    def test_the_example_pair_shows_an_optional_stress(self):
        prons = [Pron("oald", "gledress", "NOUN", "GB", "ɡlɪˈdres"), Pron("oald", "gledress", "NOUN", "GB", "ˈɡliːdres"),
                 Pron("oald", "gledress", "VERB", "GB", "ɡlɪˈdres")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "p.db"
            build(prons, [], {}, out)
            found = _query(out, "SELECT change, ipa_a, ipa_b FROM pos_contrast")
        self.assertEqual(found, [("stress (optional)", "ˈɡliːdres", "ɡlɪˈdres")])

    def test_the_family_example_shows_the_decision(self):
        # oald (preferred) keeps the stress, cald and med move it: the shift wins, and its example moves too
        prons = [Pron("oald", "glograph", "NOUN", "GB", "ˈɡləʊtəɡrɑːf"), Pron("oald", "glography", "NOUN", "GB", "ˈɡləʊtɒɡrəfi")]
        for d in ("cald", "med"):
            prons += [Pron(d, "glograph", "NOUN", "GB", "ˈɡləʊtəɡrɑːf"), Pron(d, "glography", "NOUN", "GB", "ɡləˈtɒɡrəfi")]
        # kept: the pair shown shares a stress, though the first transcriptions do not
        prons += [Pron("oald", "gloment", "NOUN", "GB", "ˈɡləʊment"), Pron("oald", "gloment", "NOUN", "GB", "ɡləˈment"),
                  Pron("oald", "glomental", "ADJ", "GB", "ˌɡləʊˈmentəl")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "p.db"
            build(prons, [("glograph", "glography", "suffixed"), ("gloment", "glomental", "suffixed")], {}, out)
            found = _query(out, "SELECT base, ipa_base, ipa_member, stress_base, stress_member, shift, "
                                 "example_from FROM family_stress ORDER BY base")
        self.assertEqual(found, [("glograph", "ˈɡləʊtəɡrɑːf", "ɡləˈtɒɡrəfi", "1/3", "2/4", 1, "cald"),
                                 ("gloment", "ɡləˈment", "ˌɡləʊˈmentəl", "2/2", "2/3", 0, "oald")])

    def test_a_us_form_printed_only_where_it_differs(self):
        prons = [Pron("ldoce", "gladdress", "NOUN", "GB", "ɡləˈdres"), Pron("ldoce", "gladdress", "NOUN", "US", "ɡləˈdres"),
                 Pron("ldoce", "gladdress", "NOUN", "US", "ˈɡlædres"), Pron("ldoce", "gladdress", "VERB", "GB", "ɡləˈdres"),
                 # a US vowel the verb's block leaves out is not a contrast: only stress is read from the British form
                 Pron("ldoce", "glox", "NOUN", "GB", "ɡlɒks"), Pron("ldoce", "glox", "NOUN", "US", "ɡlɑːks"),
                 Pron("ldoce", "glox", "VERB", "GB", "ɡlɒks"),
                 # a US form printed but partial ("$ -ˈsɔːrs") is not a missing one: nothing stands in for it
                 Pron("ldoce", "glesource", "NOUN", "GB", "ɡlɪˈzɔːs"), Pron("ldoce", "glesource", "NOUN", "US", "ˈɡliːsɔːrs"),
                 Pron("ldoce", "glesource", "VERB", "GB", "ɡlɪˈzɔːs"), Pron("ldoce", "glesource", "VERB", "US", "-ˈsɔːrs")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "p.db"
            build(prons, [], {}, out)
            contrasts = _query(out, "SELECT word, change, region FROM pos_contrast")
        self.assertEqual(contrasts, [("gladdress", "stress (optional)", "US")])


if __name__ == "__main__":
    unittest.main()
