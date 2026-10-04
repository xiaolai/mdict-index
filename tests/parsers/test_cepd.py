"""CEPD18 parser on synthetic entries that mirror its markup (transcriptions and text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import cepd


def _pron(ipa: str) -> str:
    return f'<span class="pron"><ipa>{ipa}</ipa></span>'


_SEP = "<SEP>, </SEP>"
HTML = (
    '<link rel=stylesheet href="cepd18.css" type="text/css">'
    '<span class="arl"><hit id="1" targettype="hw"><span class="results"><span class="base"><hw>grelt</hw></span></span>'
    '<span class="forms"><span class="inflections"><span class="base">grelt</span></span></span></hit>'
    '<hit id="2" targettype="inflection"><span class="results"><span class="base"><span class="inf">greltz</span></span></span></hit></span>'
    '<span class="di-head"><span class="di-title"><hw>grel|t<span class="registered">®</span></hw><SEP>, </SEP></span>'
    '<span class="di-info"><span class="var">grellt</span><SEP> </SEP><span class="pos">v</span></span></span>'
    '<span class="di-body"><span class="sense-block"><sense-head><span class="sense-info">'
    '<soundfile><a href="sound://UKGRELT01.spx"><img src="uk_sound.png" border="0"></img></a></soundfile>'
    '<soundfile><a href="sound://USGRELT01.spx"><img src="us_sound.png" border="0"></img></a></soundfile>'
    '<pronunciation-practice/></span></sense-head><span class="sense-body">'
    '<span class="prongrp"><SEP> </SEP>' + _pron("ˈɡrel.t<sp>ə</sp>") + _SEP + _pron("-tɪ") + _SEP
    + '<SEP> </SEP><span class="ussymbol">US</span><SEP> </SEP>' + _pron("-tɚ") + '</span>'
    '<span class="prongrp"><SEP> </SEP><span class="comment">occasionally<SEP class="SEP-colon">: </SEP></span>'
    '<SEP> </SEP>' + _pron("ɡrəlˈtə") + '</span>'
    '<span class="inflection"><SEP> </SEP><span class="inf">grelt<b>ed</b></span>'
    '<span class="prongrp"><SEP> </SEP>' + _pron("-ɪd") + '</span></span>'
    '<span class="compound"><SEP> </SEP><span class="cm">ˈgrelt ˌbox</span></span></span></span>'
    '<span class="sense-block"><sense-head><span class="sense-info">'
    '<soundfile><a href="sound://UKGRELT02.spx"><img src="uk_sound.png" border="0"></img></a></soundfile>'
    '</span></sense-head><span class="sense-body"><span class="prongrp"><SEP> </SEP>'
    '<span class="comment">place in Nowhere<SEP class="SEP-colon">: </SEP></span><SEP> </SEP>' + _pron("ɡriːlt") + '</span></span></span>'
    '<span class="usagenote">Note: An invented note; compare /' + _pron("ɡrɒlt") + '/.</span></span>'
)


class CepdParser(unittest.TestCase):
    def setUp(self):
        self.e = cepd.parse("grelt", HTML)
        self.prons = [(p.region, p.ipa, p.audio) for p in self.e.prons]

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, cepd.COVERS))

    def test_headword_pos_and_forms(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelt", "", ("v",)))
        self.assertEqual(self.e.forms, ("grellt", "grelted"))  # not the search index's "greltz"

    def test_first_block_regions_and_audio(self):
        self.assertEqual(self.prons[:4], [
            ("uk", "ˈɡrel.tə", "sound://UKGRELT01.spx"),
            ("uk", "ɡrəlˈtə", ""),            # a later group restarts British; "-tɪ" is a partial variant
            ("us", "-tɚ", "sound://USGRELT01.spx"),  # the first US transcription is kept as printed
            ("uk", "ɡriːlt", "sound://UKGRELT02.spx"),
        ])
        self.assertEqual([p.note for p in self.e.prons[:4]], ["", "occasionally", "", "place in Nowhere"])

    def test_block_without_us_transcription_serves_both(self):
        self.assertEqual(self.prons[4:], [("us", "ɡriːlt", "")])

    def test_inflection_compound_and_note_transcriptions_are_not_headword_prons(self):
        ipas = [ipa for _, ipa, _ in self.prons]
        for other in ("-ɪd", "ɡrɒlt", "-tɪ"):
            self.assertNotIn(other, ipas)

    def test_comments_become_pron_notes_up_to_the_us_switch(self):
        e = cepd.parse("grelt", '<span class="di-head"><span class="di-title"><hw>grelt</hw></span></span>'
                                '<span class="di-body"><span class="sense-block"><span class="sense-body">'
                                '<span class="prongrp"><span class="comment">strong form<SEP class="SEP-colon">: </SEP></span>'
                                + _pron("ɡrelt") + '</span><span class="prongrp"><span class="comment">weak form'
                                '<SEP class="SEP-colon">: </SEP></span>' + _pron("ɡrəlt") + _SEP
                                + '<span class="ussymbol">US</span>' + _pron("ɡrɚlt") + '</span></span></span></span>')
        self.assertEqual([(p.region, p.ipa, p.note) for p in e.prons],
                         [("uk", "ɡrelt", "strong form"), ("uk", "ɡrəlt", "weak form"), ("us", "ɡrɚlt", "")])
        self.assertEqual(problems(e), [])

    def test_a_repeated_transcription_with_another_qualifier_is_kept(self):
        e = cepd.parse("grelt", '<span class="di-head"><span class="di-title"><hw>grelt</hw></span></span>'
                                '<span class="di-body"><span class="sense-block"><span class="sense-body">'
                                '<span class="prongrp">' + _pron("ɡrelt") + _SEP + _pron("ɡrelt")
                                + '<span class="comment">in Nowhere<SEP class="SEP-colon">: </SEP></span>'
                                + _pron("ɡrelt") + '</span></span></span></span>')
        self.assertEqual([(p.region, p.ipa, p.note) for p in e.prons if p.region == "uk"],
                         [("uk", "ɡrelt", ""), ("uk", "ɡrelt", "in Nowhere")])

    def test_note_on_the_repeated_us_copy(self):
        us = [p for p in self.e.prons if p.region == "us" and p.ipa == "ɡriːlt"]
        self.assertEqual([p.note for p in us], ["place in Nowhere"])
        self.assertEqual(self.e.stub, "")

    def test_note_becomes_a_note_sense(self):
        self.assertEqual([(s.kind, s.definition) for s in self.e.senses],
                         [("note", "Note: An invented note; compare /ɡrɒlt/.")])

    def test_garbage_never_raises(self):
        for junk in ["", "<", '<span class="di-body"><span class="sense-block">', "plain text", "<<<>>>",
                     '<span class="prongrp"><span class="ussymbol">US</span>']:
            e = cepd.parse("x", junk)
            self.assertEqual(e.headword, "x")
            self.assertEqual(problems(e), [])


if __name__ == "__main__":
    unittest.main()
