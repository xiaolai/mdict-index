"""OALD parser on a synthetic entry that mirrors OALD10's markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import oald

HTML = """
<link rel="stylesheet" href="oald10.css"><script>toggle()</script>
<div class="entry"><div class="top-container"><div class="top-g"><div class="webtop">
 <h1 class="headword">grelt<span class="hm">1</span></h1> <span class="pos">verb</span>
 <span class="phonetics">
  <div class="phons_br"><a href="sound://grelt__gb_1.ogg" class="sound"> </a><span class="phon">/ɡrelt/</span></div>
  <div class="phons_n_am"><a href="sound://grelt__us_1.ogg" class="sound"> </a><span class="phon">/ɡrɛlt/</span></div>
 </span>
 <div class="collapse"><span class="unbox" unbox="verbforms"><table class="verb_forms_table">
  <tr><td class="verb_form"><span class="vf_prefix">past simple</span> grelted</td>
      <td class="verb_phons"><div class="phons_br"><span class="phon">/x/</span></div></td></tr>
 </table></span></div>
</div></div></div>
<ol class="senses_multiple">
 <li class="sense" sensenum="1"><span class="grammar">[transitive]</span> <span class="labels">(informal)</span>
  <span class="def">to fold a   map badly</span>
  <ul class="examples"><li><span class="cf">grelt something</span> <span class="x">He grelted the map.</span></li></ul>
  <div class="collapse"><span class="unbox" unbox="extra_examples"><ul class="examples"><li><span class="unx">Maps get grelted.</span></li></ul></span></div>
  <div class="collapse"><span class="unbox" unbox="synonyms"><span class="def">NOT A SENSE</span><span class="x">NOT AN EXAMPLE</span></span></div>
 </li>
 <li class="sense" sensenum="2"><span class="def">to hesitate</span></li>
</ol>
<span class="idm-g"><div class="webtop"><span class="idm">grelt the lot</span><span class="pos">IDIOM-POS</span></div>
 <ol><li class="sense" sensenum="1"><span class="def">to fail completely</span><ul class="examples"><li><span class="x">We grelted the lot.</span></li></ul></li></ol>
</span>
<span class="unbox" unbox="wordorigin"><span class="box_title">Word Origin</span><span class="body"><span class="p">invented for a test, &lt; nothing</span></span></span>
</div>"""


class OaldParser(unittest.TestCase):
    def setUp(self):
        self.e = oald.parse("grelt", HTML)

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, oald.COVERS))

    def test_headword_homograph_pos(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelt", "1", ("verb",)))

    def test_prons_exclude_the_verb_forms_table(self):
        self.assertEqual([(p.region, p.ipa, p.audio) for p in self.e.prons],
                         [("uk", "ɡrelt", "sound://grelt__gb_1.ogg"), ("us", "ɡrɛlt", "sound://grelt__us_1.ogg")])
        self.assertEqual(self.e.forms, ("grelted",))

    def test_senses_with_labels_and_examples_but_not_box_content(self):
        s1, s2 = [s for s in self.e.senses if s.kind == "sense"]
        self.assertEqual((s1.number, s1.labels, s1.definition), ("1", ("transitive", "informal"), "to fold a map badly"))
        self.assertEqual([x.text for x in s1.examples], ["He grelted the map.", "Maps get grelted."])
        self.assertEqual((s2.number, s2.definition, s2.examples), ("2", "to hesitate", ()))

    def test_idioms_become_phrase_senses(self):
        (idiom,) = [s for s in self.e.senses if s.kind == "phrase"]
        self.assertEqual((idiom.phrase, idiom.definition, idiom.examples[0].text),
                         ("grelt the lot", "to fail completely", "We grelted the lot."))

    def test_etymology_keeps_a_literal_less_than(self):
        self.assertEqual(self.e.etymology, "invented for a test, < nothing")

    def test_each_entry_section_has_its_own_pos_and_pronunciation(self):
        def section(hm, pos, ipa, audio, body):
            return (f'<div class="entry"><div class="top-container"><div class="top-g"><div class="webtop">'
                    f'<h1 class="headword">grelt<span class="hm">{hm}</span></h1> <span class="pos">{pos}</span>'
                    f'<span class="phonetics"><div class="phons_br"><a href="sound://{audio}" class="sound"> </a>'
                    f'<span class="phon">/{ipa}/</span></div></span></div></div></div>{body}</div>')
        idiom = ('<span class="idm-g"><div class="webtop"><span class="idm">a grelt call</span></div>'
                 '<ol><li class="sense"><span class="def">a narrow escape</span></li></ol></span>')
        origin = '<span class="unbox" unbox="wordorigin"><span class="body">{}</span></span>'
        e = oald.parse("grelt", '<div class="oald">'
                       + section(1, "verb", "ɡrelz", "grelt__gb_1.ogg", '<ol><li class="sense" sensenum="1"><span class="def">to fold</span></li>'
                                 '<li class="sense" sensenum="2"><span class="def">to end</span></li></ol>' + origin.format("from Florpish"))
                       + section(1, "noun", "ɡrelz", "grelt__gb_1.ogg", '<ol><li class="sense"><span class="def">the end</span></li></ol>')
                       + section(2, "adjective", "ɡrels", "grelt__gb_2.ogg", '<ol><li class="sense"><span class="def">near</span></li></ol>'
                                 + idiom + origin.format("from Old Grelt"))
                       + '</div>')
        self.assertEqual((e.headword, e.homograph, e.pos), ("grelt", "", ("verb", "noun", "adjective")))  # homographs 1 and 2
        self.assertEqual([(p.region, p.ipa, p.audio) for p in e.prons],
                         [("uk", "ɡrelz", "sound://grelt__gb_1.ogg"), ("uk", "ɡrels", "sound://grelt__gb_2.ogg")])
        self.assertEqual([(s.kind, s.pos, s.number, s.phrase, s.definition) for s in e.senses], [
            ("sense", "verb", "1", "", "to fold"), ("sense", "verb", "2", "", "to end"), ("sense", "noun", "", "", "the end"),
            ("sense", "adjective", "", "", "near"), ("phrase", "", "", "a grelt call", "a narrow escape")])
        self.assertEqual(e.etymology, "from Florpish; from Old Grelt")
        self.assertEqual(problems(e), [])

    def test_use_gloss_stands_in_for_a_missing_definition(self):
        e = oald.parse("-ment", '<div class="entry"><div class="webtop"><h1 class="headword">-ment</h1></div>'
                       '<ol><li class="sense"><span class="use">(makes nouns from verbs)</span>'
                       '<ul class="examples"><li><span class="x">placement</span></li></ul></li></ol></div>')
        self.assertEqual((e.senses[0].definition, e.stub), ("makes nouns from verbs", ""))

    def test_stub_reasons_come_from_markup(self):
        cases = {
            "index": ("@wordlist_1", '<div class="list">words</div>'),
            "inflection": ("sprung", '<div class="entry"><div class="webtop"><h1 class="headword">sprung</h1></div>'
                                     '<ol><li class="sense"><span class="xrefs">past participle of <a>spring</a></span></li></ol></div>'),
            "xref": ("absentee", '<div class="entry"><div class="webtop"><h1 class="headword">absentee</h1></div>'
                                 '<ol><li class="sense"><span class="xr-g"><a class="Ref">in absentee</a></span></li></ol></div>'),
            "empty": ("draft thing", '<div class="entry"><div class="webtop"><h1 class="headword">draft thing</h1></div></div>'),
        }
        for reason, (headword, html) in cases.items():
            e = oald.parse(headword, html)
            self.assertEqual(e.stub, reason, headword)
            self.assertEqual(problems(e), [], headword)

    def test_a_record_with_a_definition_is_never_a_stub(self):
        self.assertEqual(self.e.stub, "")

    def test_garbage_never_raises(self):
        for junk in ["", "<", "<div><span class='def'>", "plain text", "<<<>>>"]:
            self.assertEqual(oald.parse("x", junk).headword, "x")


if __name__ == "__main__":
    unittest.main()
