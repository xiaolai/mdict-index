"""Chambers parser on synthetic cb13 records that mirror its markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import chambers

FLORP = """
<cb13_entry class="word_entry"><h2><span class="hw">florp</span><sup>1</sup> <a class="pron">/florp/</a> or
  <span class="var">florpe</span></h2>
 <span class="pos">noun</span> (<span class="GRA">pl</span> <span class="inf">florpsˈ</span>)
 <ol><li>A small wooden spoon (<span class="ctx">Scot</span>)</li>
     <li>In <span class="ctx">Spenser</span>, a ladle</li></ol>
 <span class="pos">transitive verb</span> (<span class="ctx">informal</span>) <p class="dg">To stir with a florp</p>
 <span class="pos">adjective</span> same as <a class="aa">spoony</a> (but rarer)
 <p class="lnk">—Also spelt LINK NOTE</p>
 <div class="etym">Invented <i>florpa</i> &lt; nothing</div>
 <phrase_block><phr_title></phr_title>
  <phrase><phrase_h><span class="mwe">florpˈer</span> <span class="pos">noun</span></phrase_h></phrase>
  <phrase><phrase_h><span class="mwe">florpˈish</span></phrase_h>
   <phrase_def><span class="pos">adjective</span> (with <i>about</i>; <span class="ctx">informal</span>) <p class="dg">Fond of stirring</p></phrase_def></phrase>
  <phrase><phrase_h><span class="mwe">florp up</span></phrase_h><phrase_def><ol><li>To stir hard</li><li>To mix</li></ol></phrase_def></phrase>
  <phrase><phrase_h><span class="mwe">florp the pot</span> <span class="ctx">slang</span></phrase_h><phrase_def><p class="dg">To work for nothing</p></phrase_def></phrase>
  <phrase><phrase_h><span class="mwe">florp fright</span> see under <a class="aa">fright</a></phrase_h></phrase>
 </phrase_block>
</cb13_entry>"""

HTML = f'<link rel="stylesheet" href="cb13.css"><script src="cb13.js"></script><cb13 hw="florp">{FLORP}</cb13>'

# the "florpish" record: the florp block (where florpish is a run-on) and an unrelated affix block
RUN_ON = f"""<cb13 hw="florpish">
<cb13_entry class="word_entry"><h2><span class="hw">florp-</span></h2><span class="pos">prefix</span><p class="dg">AFFIX SENSE</p></cb13_entry>
{FLORP}</cb13>"""

# the "florps" record: an inflection, filed under the lemma's block
INFLECTION = f'<cb13 hw="florps">{FLORP}</cb13>'

EXTRACTED = """<cb13 hw="grelkwinders"><cb13_entry class="extracted_entry"><h2 class="phrase_title">
 <span class="mwe">grelkˈwīnder</span></h2><span class="pos">noun</span> (<span class="ctx">US</span>)
 <p class="dg">A kind of invented watch</p><m_entry>grelk</m_entry></cb13_entry></cb13>"""

# a head that carries the whole entry, and an inflection pointer (data-less)
HEAD_ONLY = """<cb13 hw="flurp"><cb13_entry class="word_entry"><h2><span class="hw">flurp</span> <a class="pron">/flurp/</a>
 or <span class="var">flurpe</span> (<span class="ctx">Spenser</span>) an invented old form of <a class="aa">florp</a></h2></cb13_entry></cb13>"""
POINTER = """<cb13 hw="florpt"><cb13_entry class="word_entry"><h2><span class="hw">florpt</span> <a class="pron">/florpt/</a>
 <span class="GRA">pat</span> and <span class="GRA">pap</span> of <a class="aa">florp</a></h2></cb13_entry></cb13>"""


class ChambersParser(unittest.TestCase):
    def setUp(self):
        self.e = chambers.parse("florp", HTML)

    def test_valid_and_covered(self):
        for e in (self.e, chambers.parse("florpish", RUN_ON), chambers.parse("florps", INFLECTION),
                  chambers.parse("grelkwinders", EXTRACTED)):
            self.assertEqual(problems(e), [])
            self.assertTrue(covered(e, chambers.COVERS))

    def test_head(self):
        e = self.e
        self.assertEqual((e.headword, e.homograph, e.pos), ("florp", "1", ("noun", "transitive verb", "adjective")))
        self.assertEqual([(p.ipa, p.region, p.audio) for p in e.prons], [("florp", "", "")])
        self.assertEqual(e.forms, ("florpe", "florps"))
        self.assertEqual(e.etymology, "Invented florpa < nothing")

    def test_numbered_senses_with_trailing_label(self):
        s1, s2 = self.e.senses[:2]
        self.assertEqual((s1.number, s1.pos, s1.definition, s1.labels), ("1", "noun", "A small wooden spoon", ("Scot",)))
        self.assertEqual((s2.number, s2.definition, s2.labels), ("2", "In Spenser, a ladle", ("Spenser",)))

    def test_label_before_a_definition_and_bare_text_definition(self):
        verb, adj = self.e.senses[2:4]
        self.assertEqual((verb.pos, verb.labels, verb.definition), ("transitive verb", ("informal",), "To stir with a florp"))
        self.assertEqual((adj.pos, adj.definition), ("adjective", "same as spoony (but rarer)"))

    def test_run_ons(self):
        runs = [(s.kind, s.phrase, s.pos, s.number, s.labels, s.definition) for s in self.e.senses[4:]]
        self.assertEqual(runs, [
            ("derivative", "florper", "noun", "", (), ""),
            ("derivative", "florpish", "adjective", "", ("informal", "with about"), "Fond of stirring"),
            ("phrasal_verb", "florp up", "", "1", (), "To stir hard"),
            ("phrasal_verb", "florp up", "", "2", (), "To mix"),
            ("phrase", "florp the pot", "", "", ("slang",), "To work for nothing"),
        ])

    def test_inline_markup_keeps_the_spaces_around_it(self):
        html = """<cb13 hw="gralt"><cb13_entry class="word_entry"><h2><span class="hw">gralt</span></h2>
         <span class="pos">noun</span> A <i>small </i>spoon<i> of</i> wood, or a<b> big </b>one</cb13_entry></cb13>"""
        (s,) = chambers.parse("gralt", html).senses
        self.assertEqual(s.definition, "A small spoon of wood, or a big one")

    def test_a_particle_phrase_is_a_phrasal_verb_only_under_a_verb(self):
        html = """<cb13 hw="gralt"><cb13_entry class="word_entry"><h2><span class="hw">gralt</span></h2>
         <span class="pos">adjective</span><p class="dg">Whole</p><span class="pos">adverb</span><p class="dg">Wholly</p>
         <phrase_block><phrase><phrase_h><span class="mwe">gralt in</span></phrase_h>
          <phrase_def><p class="dg">Worn out</p></phrase_def></phrase></phrase_block></cb13_entry></cb13>"""
        self.assertEqual([(s.kind, s.phrase) for s in chambers.parse("gralt", html).senses if s.phrase],
                         [("phrase", "gralt in")])
        self.assertEqual([(s.kind, s.phrase) for s in chambers.parse("gralt in", html).senses], [("phrase", "gralt in")])
        self.assertEqual({s.kind for s in chambers.parse("florp up", HTML.replace('hw="florp"', 'hw="florp up"')).senses},
                         {"phrasal_verb"})

    def test_a_run_on_with_its_part_of_speech_in_the_body_is_kept(self):
        html = FLORP.replace("</phrase_block>", """<phrase><phrase_h><span class="mwe">florpeeˈ</span></phrase_h>
          <phrase_def><span class="pos">noun</span> (<span class="ctx">informal</span>)<p class="dg"></p></phrase_def></phrase>
         </phrase_block>""")
        e = chambers.parse("florp", f'<cb13 hw="florp">{html}</cb13>')
        self.assertEqual([(s.kind, s.pos, s.labels, s.definition) for s in e.senses if s.phrase == "florpee"],
                         [("derivative", "noun", ("informal",), "")])
        self.assertEqual(problems(e), [])

    def test_side_content_is_left_out(self):
        self.assertNotIn("LINK NOTE", repr(self.e))
        self.assertNotIn("fright", repr(self.e))

    def test_record_of_a_run_on_takes_only_that_run_on(self):
        e = chambers.parse("florpish", RUN_ON)
        self.assertEqual(e.headword, "florpish")
        self.assertEqual([(s.kind, s.phrase, s.definition) for s in e.senses],
                         [("derivative", "florpish", "Fond of stirring")])

    def test_record_of_an_inflection_takes_the_lemma(self):
        e = chambers.parse("florps", INFLECTION)
        self.assertEqual((e.headword, len(e.senses)), ("florp", len(self.e.senses)))

    def test_extracted_entry_drops_respelling_marks(self):
        e = chambers.parse("grelkwinders", EXTRACTED)
        self.assertEqual((e.headword, e.senses[0].labels, e.senses[0].definition),
                         ("grelkwinder", ("US",), "A kind of invented watch"))

    def test_definition_in_the_head(self):
        e = chambers.parse("flurp", HEAD_ONLY)
        self.assertEqual((e.forms, [p.ipa for p in e.prons]), (("flurpe",), ["flurp"]))
        self.assertEqual([(s.labels, s.definition) for s in e.senses], [(("Spenser",), "an invented old form of florp")])
        self.assertEqual(problems(e), [])

    def test_inflection_pointer_is_data_less(self):
        e = chambers.parse("florpt", POINTER)
        self.assertEqual((e.senses, [p.ipa for p in e.prons]), ((), ["florpt"]))

    def test_stubs(self):
        self.assertEqual(self.e.stub, "")
        self.assertEqual(chambers.parse("florpt", POINTER).stub, "inflection")
        listed = """<cb13 hw="florpness"><cb13_entry class="extracted_entry"><h2 class="phrase_title"><span class="mwe">florpˈness</span>
         <span class="pos">noun</span></h2><m_entry>florp</m_entry></cb13_entry></cb13>"""
        self.assertEqual(chambers.parse("florpness", listed).stub, "derivative")
        see = """<cb13 hw="flarp"><cb13_entry class="word_entry"><h2><span class="hw">flarp</span> see <a class="aa">florp</a></h2>
         </cb13_entry></cb13>"""
        self.assertEqual(chambers.parse("flarp", see).stub, "xref")

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", "<cb13><cb13_entry><h2><span class='hw'>", "<<<>>>"]:
            e = chambers.parse("x", junk)
            self.assertEqual((e.headword, problems(e)), ("x", []))


if __name__ == "__main__":
    unittest.main()
