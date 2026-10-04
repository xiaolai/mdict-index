"""LDOCE6 English-Chinese parser on a synthetic record that mirrors its markup (text invented).

The fixture keeps the real quirk that the senses end up nested inside span.buttons,
after the inlined popups (div.at-link).
"""
import unittest

from structured.model import covered, problems
from structured.parsers import ldoce_ec

HTML = """
<link rel="stylesheet" type="text/css" href="ldoce6ec.css"><script src="ldoce6ec.js"></script>
<div><span class="entry"><span class="entryhead"><span class="hwd">grelt</span><span class="homnum">1</span>
 <span class="proncodes"><span class="neutral">/</span><span class="pron">ɡrelt</span><span class="neutral">/</span></span>
 <span class="pos">verb</span>
 <a href="sound://hwd/bre/g/grelt1.mp3"><img src="img/spkr_r.png"></a><a href="sound://hwd/ame/g/grelt1.mp3"><img src="img/spkr_b.png"></a>
 <span class="buttons">
  <span class="popup-button">Word Origin<atl></atl></span><div class="at-link"><span class="entry"><span class="popheader popetym">WORD ORIGIN</span>
   <span class="hyphenation">grelt</span></span><div class="etymology"><b>Origin:</b></div>
   <span class="etymsense"><span class="etymcentury">1900-2000</span> <span class="etymorigin">grelten</span></span></div>
  <span class="popup-button">Examples</span><div class="at-link"><span class="entry"><span class="popheader popexa">EXAMPLES FROM THE CORPUS</span></span>
   <ul class="exas"><li>They <span class="nodeword">grelt</span> maps for fun.</li></ul></div>
  <span class="popup-button">Thesaurus</span><div class="at-link"><span class="entry"><span class="popheader popthes">THESAURUS</span>
   <span class="section"><span class="exponent"><span class="exp display">frump</span><div class="content">
   <span class="def">THESAURUS DEF</span><span class="example">· THESAURUS EXAMPLE</span></div></span></span></span></div>
  <span class="sense newline"><span class="sensenum">1</span><span class="signpost"><signen>fold</signen><sign>折</sign></span>
   <span class="gram">[transitive]</span>
   <span class="def"><en>to fold a map badly</en><tran>把地图折坏</tran></span><deft></deft>
   <span class="example"><exaen><a href="sound://exa/bre/x/p1.mp3"><img src="img/spkr_g.png"></a> He grelted the map.</exaen><example>他把地图折坏了。</example></span><exat></exat>
   <span class="example"> Maps get grelted.</span><exat></exat>
  </span>
  <span class="sense newline"><span class="sensenum">2</span><span class="lexunit">grelt the lot</span>
   <span class="def"><en>to fail completely</en><tran>彻底失败</tran></span></span>
 </span>
</span></span></div>"""


class LdoceEcParser(unittest.TestCase):
    def setUp(self):
        self.e = ldoce_ec.parse("grelt", HTML)

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, ldoce_ec.COVERS))

    def test_headword_homograph_pos_prons(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelt", "1", ("verb",)))
        self.assertEqual([(p.region, p.ipa, p.audio) for p in self.e.prons],
                         [("uk", "ɡrelt", "sound://hwd/bre/g/grelt1.mp3"), ("us", "ɡrelt", "sound://hwd/ame/g/grelt1.mp3")])

    def test_definitions_and_examples_split_english_and_chinese(self):
        s1 = self.e.senses[0]
        self.assertEqual((s1.number, s1.labels, s1.definition, s1.definition_zh),
                         ("1", ("transitive",), "to fold a map badly", "把地图折坏"))
        self.assertEqual([(x.text, x.text_zh) for x in s1.examples],
                         [("He grelted the map.", "他把地图折坏了。"), ("Maps get grelted.", "")])

    def test_phrase_sense(self):
        s2 = self.e.senses[1]
        self.assertEqual((s2.kind, s2.phrase, s2.definition, s2.definition_zh),
                         ("phrase", "grelt the lot", "to fail completely", "彻底失败"))

    def test_inlined_popups_give_etymology_and_example_bank_but_not_thesaurus(self):
        self.assertEqual(self.e.etymology, "1900-2000 grelten")
        bank = self.e.senses[-1]
        self.assertEqual((bank.number, bank.definition, [x.text for x in bank.examples]),
                         ("", "", ["They grelt maps for fun."]))
        self.assertEqual(len(self.e.senses), 3)
        self.assertNotIn("THESAURUS", repr(self.e))

    def test_cross_reference_record_is_an_xref_stub_and_example_labels_are_kept(self):
        e = ldoce_ec.parse("frelt", '<div><span class="entry"><span class="entryhead"><span class="hwd">frelt</span></span>'
                           '<span class="sense"><span class="crossref"><span class="neutral">→</span> '
                           '<a href="entry://grelt"><span class="refhwd">grelt</span></a></span></span></span></div>')
        self.assertEqual((e.stub, e.part_of, problems(e)), ("xref", "", []))
        self.assertEqual(self.e.stub, "")
        labelled = ldoce_ec.parse("grelt", '<span class="entry"><span class="entryhead"><span class="hwd">grelt</span></span>'
                                  '<span class="sense"><span class="def"><en>to fold</en><tran>折</tran></span>'
                                  '<span class="example"><exaen>Grelt it.</exaen><span class="registerlab">spoken</span>'
                                  '<example>折一下。</example></span></span></span>')
        (x,) = labelled.senses[0].examples
        self.assertEqual((x.text, x.text_zh, x.labels), ("Grelt it.", "折一下。", ("spoken",)))

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text 中文", "<span class='def'><en>open", "<div class='at-link'>"]:
            e = ldoce_ec.parse("x", junk)
            self.assertEqual((e.headword, problems(e)), ("x", []))


if __name__ == "__main__":
    unittest.main()
