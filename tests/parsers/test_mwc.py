"""MW Collegiate parser on synthetic records that mirror its class-less markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import mwc

NUM = '<b><font color=darkslategray>{}</font></b>'
IND = "&nbsp;&nbsp;"
BOX = ("<div style='display:block;background-color:#f6f0e6;'><span style=\"color: #585858; background-color: #E6E6E6;"
       "font-weight:bold;\">&nbsp;{} </SPAN>&nbsp;{}</font></div>")
TABLE = ('<table width="100%" border="0" bgcolor="#D3D3D3" ><tr><td align="center"><font color= "black" size=-2 >'
         '<b>{}</b></font></td></tr></table>')

HTML = "<br>".join([
    '<font style="font-weight:bold;">grelt·ing</font>' + TABLE.format("I")
    + '<a href="sound://grelt001.spx"><img src="Sound.png" border="0"></a> \\\\ˈgrel-tiŋ\\\\ <b><font color=#CA0000>verb</font></b>',
    '(<b>grolt</b> <a href="sound://grelt002.spx"><img src="Sound.png" border="0"></a> \\\\ˈgrōlt\\\\ ; <b>grelt·ing</b> ; <b>-ings</b>)'
    + BOX.format("ETYMOLOGY", "invented, from <i>greltan</i> to crumple") + BOX.format("DATE", "1901")
    + '<i><font style="color:#CA0000;font-weight:bold;">transitive verb</font></i>',
    NUM.format("1.") + '<font color=black> to fold badly <b>:</b> <a href="entry://crumple">crumple</a></font>',
    IND * 2 + '<font color=#0B3861><i>grelted</i> the map</font>',
    IND * 2 + '<font color=#0B3861>he <i>grelts</i> everything — A. Writer</font>',
    '<i><font color=#a77225>also</font></i> <b>:</b> to fold roughly',
    NUM.format("2."),
    IND + NUM.format("a.") + '<font color=black> <i><font color=#a77225>archaic</font></i> <b>:</b> to tear</font>',
    IND + NUM.format("b.") + '',
    IND * 2 + NUM.format("(1)") + ' to tear paper',
    IND * 2 + NUM.format("(2)") + ' to tear cloth — used of ⟨old⟩ looms',
    IND * 3 + '<font color=#0B3861>said he grelt \\<sic\\> it</font>',
    '• <b>grelt·er</b> <i><font color=#cd0101>noun</font></i>',
    NUM.format("Synonyms."),
    IND + 'SYNONYM PARAGRAPH about <a href="entry://grelt">grelt</a>',
    IND * 3 + '<font color=#0B3861>SYNONYM EXAMPLE</font>',
    '<b>Synonyms:</b> <i>see</i> <a href="entry://frumple">frumple</a>',
    '&nbsp;•&nbsp;•&nbsp;•',
    '- <a href="entry://grelt out">grelt out</a>',
    '',
    TABLE.format("II") + '<b><font color=#CA0000>noun</font></b>' + BOX.format("DATE", "1950"),
    '<b>:</b> a badly folded map',
    '[<font color=navy>grelt 2</font>]',
])


class MwcParser(unittest.TestCase):
    def setUp(self):
        self.e = mwc.parse("grelting", HTML)

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, mwc.COVERS))

    def test_headword_pos_prons_forms_etymology(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelting", "", ("verb", "noun")))
        self.assertEqual([(p.region, p.ipa, p.audio) for p in self.e.prons], [("us", "ˈgrel-tiŋ", "sound://grelt001.spx")])
        self.assertEqual(self.e.forms, ("grolt",))
        self.assertEqual(self.e.etymology, "invented, from greltan to crumple")

    def test_numbered_senses_nest_and_take_the_function_label_as_pos(self):
        numbers = [(s.number, s.definition) for s in self.e.senses if s.kind == "sense"]
        self.assertEqual(numbers, [
            ("1", "to fold badly : crumple; also : to fold roughly"),
            ("2a", "to tear"),
            ("2b(1)", "to tear paper"),
            ("2b(2)", "to tear cloth — used of ⟨old⟩ looms"),
            ("", "a badly folded map"),
        ])
        self.assertEqual(self.e.senses[0].pos, "transitive verb")
        self.assertEqual(self.e.senses[1].labels, ("archaic",))
        self.assertEqual(self.e.senses[-1].pos, "noun")

    def test_examples_quotations_and_escaped_brackets(self):
        s1 = self.e.senses[0]
        self.assertEqual([(x.text, x.kind, x.source) for x in s1.examples],
                         [("grelted the map", "example", ""), ("he grelts everything", "quotation", "A. Writer")])
        self.assertEqual(self.e.senses[3].examples[0].text, "said he grelt ⟨sic⟩ it")

    def test_run_on_is_a_derivative(self):
        (d,) = [s for s in self.e.senses if s.kind == "derivative"]
        self.assertEqual((d.phrase, d.pos, d.definition), ("grelter", "noun", ""))

    def test_synonyms_phrase_lists_and_captions_stay_out(self):
        everything = repr(self.e)
        for leaked in ("SYNONYM", "grelt out", "frumple", "navy", "grelt 2", "1901"):
            self.assertNotIn(leaked, everything)

    def test_stubs_and_name_entries(self):
        see = mwc.parse("grelte", '<font style="font-weight:bold;">grelte</font><br><b><font color=#CA0000>noun</font></b>'
                        "<br><span style='vertical-align:-5%'>⇨</span> see <a href=\"entry://grelt\">grelt</a>")
        variant = mwc.parse("grelts", '<font style="font-weight:bold;">grelts</font><br>'
                            '<i><font color=#a77225>plural of</font></i> <a href="entry://grelt">grelt</a>')
        for stub in (see, variant):
            self.assertEqual((stub.senses, problems(stub)), ((), []))
        name = mwc.parse("Grelt", '<font style="font-weight:bold;">Grelt</font><br><b><font color=#CA0000>biographical name</font></b>'
                         '<br>(<i>or</i> <b>Grelte</b>) Anna 1801-1880 invented folder of maps')
        self.assertEqual((name.forms, name.senses[0].definition), (("Grelte",), "Anna 1801-1880 invented folder of maps"))

    def test_stub_reasons_come_from_the_pointer_line(self):
        head = '<font style="font-weight:bold;">frelt</font><br>'
        cases = {
            "xref": head + "<span style='vertical-align:-5%'>⇨</span> see <a href=\"entry://grelt\">grelt</a>",
            "variant": head + '<i><font color=#a77225>chiefly British variant of</font></i> <a href="entry://grelt">grelt</a>',
            "inflection": head + '<i><font color=#a77225>past participle of</font></i> <a href="entry://grelt">grelt</a>',
        }
        for reason, html in cases.items():
            e = mwc.parse("frelt", html)
            self.assertEqual((e.stub, problems(e)), (reason, []), reason)
            self.assertFalse(covered(e, mwc.COVERS))
        self.assertEqual(self.e.stub, "")
        usage_only = mwc.parse("frelt", head + '<b><font color=#CA0000>pronoun</font></b><br><b><font color=darkslategray>Usage.</font></b><br>'
                               '&nbsp;&nbsp;A USAGE PARAGRAPH')
        self.assertEqual((usage_only.stub, usage_only.senses), ("", ()))  # nothing printed says why: not a stub

    def test_italic_pron_qualifiers_become_notes(self):
        e = mwc.parse("frelt", '<font style="font-weight:bold;">frelt</font><br><a href="sound://frelt001.spx"><img src="Sound.png"></a>'
                      ' \\\\ˈfrelt, <i>chiefly Brit</i> ˈfrɑlt <i>or</i> ˈfrōlt\\\\ <b><font color=#CA0000>noun</font></b><br><b>:</b> a fold')
        self.assertEqual([(p.ipa, p.note, p.audio) for p in e.prons],
                         [("ˈfrelt", "", "sound://frelt001.spx"), ("ˈfrɑlt", "chiefly Brit", ""), ("ˈfrōlt", "or", "")])

    def test_variant_printed_on_a_sense_is_a_form_not_definition_text(self):
        head = '<font style="font-weight:bold;">frelt</font><br><b><font color=#CA0000>noun</font></b><br>'
        brown = '<i><font color=#a77225>{}</font></i>'
        e = mwc.parse("frelt", head + "<br>".join([
            NUM.format("1.") + '<font color=black> a fold</font>',
            NUM.format("2.") + ' ' + brown.format("also") + ' <b>frett</b> <a href="sound://frelt002.spx"><img src="Sound.png" border="0"></a> \\\\ˈfret\\\\',
            IND + NUM.format("a.") + '<font color=black> a crease</font>',
            NUM.format("3.") + ' ' + brown.format("or") + ' <b>frelt·te</b> <b>:</b> the den of a vole',
            NUM.format("4.") + ' ' + brown.format("plural") + ' <b>frelts</b> ' + brown.format("or") + ' <b>frelt</b> '
            + brown.format("British") + ' <b>:</b> a map folder',
            NUM.format("5.") + ' ' + brown.format("or formerly") + ' <b>Freltia</b> \\\\-tē-ə\\\\ ancient city on the plain',
            NUM.format("6.") + ' ' + brown.format("especially") + ' <b>:</b> a small fold',
        ]))
        self.assertEqual([(x.number, x.labels, x.definition) for x in e.senses], [
            ("1", (), "a fold"), ("2a", (), "a crease"), ("3", (), "the den of a vole"), ("4", ("British",), "a map folder"),
            ("5", (), "ancient city on the plain"), ("6", (), "especially : a small fold")])
        self.assertEqual(e.forms, ("frett", "freltte", "frelts", "Freltia"))
        self.assertEqual(e.prons, ())  # the variant's own pronunciation is not the headword's: left in layer 1
        self.assertEqual(problems(e), [])

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", "<br><br>", "<b><font color=darkslategray>1.", "(<b>x", "\\\\<b>", "•"]:
            e = mwc.parse("x", junk)
            self.assertEqual(problems(e), [])
        self.assertEqual(mwc.parse("x", "").headword, "x")


if __name__ == "__main__":
    unittest.main()
