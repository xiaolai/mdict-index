"""LPD3 parser on synthetic entries that mirror its tag-and-colour markup (transcriptions invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import lpd

_UK = '<font color=green>BrE</font> <a href="sound://uk_{0}.spx"><img src="UK.png" style="margin-bottom:-4px" border="0" ></img></a>'
_US = '<font color=green>AmE</font> <a href="sound://us_{0}.spx"><img src="US.png" style="margin-bottom:-4px" border="0" ></img></a>'
_AUDIO = _UK + " " + _US

HTML = (
    '<!--Roman-->I<!--/Roman-->\n'
    '&nbsp;<b>grel|t</b> <i> noun, verb</i> ' + _AUDIO.format("grelt") +
    ' <font color=mediumblue>ɡrelt</font> ɡrelʔ, <font color=green>§</font> ɡrølt, -elt !!ɡrɛt (= gralt)'
    ' <font color=green>AmE</font> <font color=mediumblue>ɡr<i>ə</i>lt</font><i> (*)</i><br>\n'
    '<m2> —<i> Preference poll, British English:</i> <font color=mediumblue>ɡrelt</font><i> 90%,</i>'
    ' <font color=mediumblue>ɡrølt</font><i> 10%.</i><br>\n'
    '&nbsp;▷ <b>grel|ted</b> <font color=mediumblue>ɪd</font> əd<br>\n'
    '&nbsp;▷ <b>grel|ts</b> <font color=mediumblue>s</font><br>\n'
    '</m2>&nbsp;▶<b><font color=blue>ˈ</font>grelt box</b> ' + _AUDIO.format("grelt_box") + '<br>\n'
    '<!--Roman-->II<!--/Roman-->\n'
    '&nbsp;<b>grelt</b> <i> (i)</i> ' + _AUDIO.format("grelt2") + ' <font color=mediumblue>ɡriːlt</font><i>, (ii)</i> '
    + _AUDIO.format("grelt3") + ' <font color=mediumblue>ɡrɑːlt</font><font color=green><i> —French</i></font>'
    ' [<font color=mediumblue>ɡʁalt</font>]<br>\n'
)


class LpdParser(unittest.TestCase):
    def setUp(self):
        self.e = lpd.parse("grelt", HTML)
        self.prons = [(p.region, p.ipa, p.audio) for p in self.e.prons]

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, lpd.COVERS))
        self.assertEqual(self.e.senses, ())

    def test_headword_pos_and_forms(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelt", "", ("noun", "verb")))
        self.assertEqual(self.e.forms, ("grelted", "grelts"))  # the ▶ compound is not a form

    def test_main_transcriptions_carry_the_region_audio(self):
        self.assertEqual(self.prons[:2], [("uk", "ɡrelt", "sound://uk_grelt.spx"), ("uk", "ɡrelʔ", "")])
        self.assertIn(("us", "ɡrəlt", "sound://us_grelt.spx"), self.prons)

    def test_variants_keep_non_rp_and_drop_partials_flags_and_homophones(self):
        ipas = [ipa for _, ipa, _ in self.prons]
        self.assertIn("ɡrølt", ipas)  # after §: a non-RP BrE variant
        for dropped in ("-elt", "!!ɡrɛt", "ɡrɛt", "(= gralt)", "gralt"):
            self.assertNotIn(dropped, ipas)

    def test_polls_and_compounds_are_not_read_and_foreign_forms_are_marked(self):
        foreign = [p for p in self.e.prons if p.ipa == "ɡʁalt"]
        self.assertEqual([(p.region, p.audio, p.note) for p in foreign], [("", "", "French")])
        self.assertNotIn("sound://uk_grelt_box.spx", [a for _, _, a in self.prons])
        self.assertEqual(sum(1 for _, ipa, _ in self.prons if ipa == "ɡrølt"), 1)  # not again from the poll

    def test_alternatives_restart_in_british_and_one_transcription_serves_both(self):
        self.assertIn(("uk", "ɡriːlt", "sound://uk_grelt2.spx"), self.prons)
        self.assertIn(("us", "ɡriːlt", "sound://us_grelt2.spx"), self.prons)
        self.assertIn(("uk", "ɡrɑːlt", ""), self.prons)

    def test_transcription_on_the_line_after_a_base_reference(self):
        e = lpd.parse("grelten", '&nbsp;<b>grelten</b> <i> past participle of</i><br>\n'
                                 '&nbsp;▷ <b>grelt</b> <font color=mediumblue>ˈɡrelt ən</font><br>')
        self.assertEqual([(p.region, p.ipa) for p in e.prons], [("uk", "ˈɡrelt ən"), ("us", "ˈɡrelt ən")])
        self.assertEqual(e.forms, ())  # "grelt" is the base word, not a form of "grelten"

    def test_qualifiers_become_pron_notes(self):
        notes = {(p.region, p.ipa): p.note for p in self.e.prons}
        self.assertEqual(notes[("uk", "ɡrølt")], "§")
        self.assertEqual((notes[("uk", "ɡrelt")], notes[("uk", "ɡrelʔ")]), ("", ""))
        self.assertEqual((notes[("uk", "ɡriːlt")], notes[("us", "ɡriːlt")], notes[("uk", "ɡrɑːlt")]), ("(i)", "(i)", "(ii)"))
        e = lpd.parse("grel", '&nbsp;<b>grel</b> <i> strong form</i> ' + _AUDIO.format("grel") +
                      ' <font color=mediumblue>ɡrel</font><i>, weak forms</i> <font color=mediumblue>ɡrəl, ɡrl</font><br>')
        self.assertEqual([(p.region, p.ipa, p.note) for p in e.prons],
                         [("uk", "ɡrel", "strong form"), ("uk", "ɡrəl", "weak forms"), ("uk", "ɡrl", "weak forms"),
                          ("us", "ɡrel", "strong form")])
        self.assertEqual(problems(e), [])

    def test_or_is_a_connector_whatever_its_spacing(self):
        for connector in ("<i> or</i>", "<i>or</i>"):
            e = lpd.parse("grel", '&nbsp;<b>grel</b> <font color=mediumblue>ɡrel</font> ' + connector
                          + ' <font color=mediumblue>ɡrəl</font><br>')
            self.assertEqual([p.ipa for p in e.prons if p.region == "uk"], ["ɡrel", "ɡrəl"], connector)

    def test_the_same_transcription_under_another_qualifier_is_kept(self):
        e = lpd.parse("grel", '&nbsp;<b>grel</b> <i> strong form</i> <font color=mediumblue>ɡrel</font><i>, weak forms</i> '
                              '<font color=mediumblue>ɡrel, ɡrl</font><br>')
        self.assertEqual([(p.ipa, p.note) for p in e.prons if p.region == "uk"],
                         [("ɡrel", "strong form"), ("ɡrel", "weak forms"), ("ɡrl", "weak forms")])

    def test_comma_separated_inflections_are_separate_forms(self):
        e = lpd.parse("grel", "&nbsp;<b>grel</b> <font color=mediumblue>ɡrel</font><br>\n"
                              "&nbsp;▷ <b>grel'd, greled, \\~x</b> <font color=mediumblue>d</font><br>")
        self.assertEqual(e.forms, ("grel'd", "greled"))  # "~x" abbreviates a form that is not spelled out

    def test_headword_stress_line_gives_the_audio(self):
        e = lpd.parse("grelt box", '&nbsp;<b>grelt box</b> <br>\n&nbsp;▶<b><font color=blue>  ˈ</font>grelt '
                                   '<font color=blue>ˌ</font>box</b> ' + _AUDIO.format("grelt_box") + '<br>')
        self.assertEqual([(p.region, p.audio) for p in e.prons],
                         [("uk", "sound://uk_grelt_box.spx"), ("us", "sound://us_grelt_box.spx")])
        self.assertEqual((e.stub, problems(e)), ("", []))

    def test_cross_reference_is_a_stub(self):
        for html in ('&nbsp;<b>grelti...</b> <i> —see</i> ↑&lt;&lt;grelt&gt;&gt;<br>',
                     '&nbsp;<b>grelts...</b> <i> —-see</i> <b>greltz...</b> (↑&lt;&lt;greltize&gt;&gt;)<br>',
                     "&nbsp;<b>G'...</b> <i> in this dictionary listed alphabetically as if written</i><br>"
                     "&nbsp;▷ <b>Gre...</b><br>"):
            e = lpd.parse("x", html)
            self.assertEqual((e.stub, e.prons, problems(e)), ("xref", (), []))
            self.assertFalse(covered(e, lpd.COVERS))
        self.assertEqual(self.e.stub, "")

    def test_garbage_never_raises(self):
        for junk in ["", "<", "<b>", "plain text", "<<<>>>", "&nbsp;<b>x</b> <font color=mediumblue>",
                     "<font color=green>AmE</font><a href='sound://us_x.spx'>"]:
            e = lpd.parse("x", junk)
            self.assertEqual(e.headword, "x")
            self.assertEqual(problems(e), [])


if __name__ == "__main__":
    unittest.main()
