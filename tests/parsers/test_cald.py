"""CALD parser on synthetic entries that mirror the presentational CALD4 markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import cald

BADGE = 'style="font-weight: bold;text-transform: uppercase;color: white;background-color: #3F7373;"'
NUM = 'style="float:left;overflow:hidden;display:block;width: 14px;"'
LINE = 'style="margin-left:20px;display:block;"'

HTML = f"""<b><font size="+1">grelt</font></b><br><br>
<font size="+0">—<font color="blue"><b>ˈgrelt</b></font> <a href="sound://ukgrelt001.spx"><img src="snd_uk.png" border="0"></a>
 <a href="sound://grelt.spx"><img src="snd_us.png" border="0"></a> /ɡrelt/ <font color="green"><b>aep</b></font> /ɡrɛlt/
 (<sub><font size="-0"><font color="indigo">UK</font> ALSO</font></sub> <font color="mediumblue"><b>grelte</b></font>)</font><br>
<br><div style="margin-top:8px;"></div>
<div style="float:left;overflow:hidden;"><font color="crimson"><b>Ⅰ</b></font></div>
<div style="margin-left:20px;"><span {BADGE}>noun</span> <font color="green">[C]</font> <font color="mediumvioletred"><b>(FOLD)</b></font></div>
<div style="margin-top:6px;"></div>
<div {NUM}><span style="color:darkred;font-weight:bold;">1</span></div>
<div style="margin-left:20px;"><font color="green"><b>B2</b></font> <sub><font size="-0"><font color="indigo">INFORMAL</font></font></sub> a map folded the wrong way: </div>
<span {LINE}><font color="gray">» He handed me a grelt <font color="limegreen">(= a badly folded map)</font>.</font></span>
<span {LINE}><font color="gray">» <font color="green">[+ that]</font> <sub><font size="-0">MAINLY <font color="indigo">US</font></font></sub> They proved that <sub><font size="-0"><font color="indigo">UK</font></font></sub> maps grelt.</font></span>
<span {LINE}><font color="olive"><u>Thesaurus</u><sup>+</sup></font>: <a href="entry://%E2%86%91Maps">↑Maps</a></span>
<div {NUM}><span style="color:darkred;font-weight:bold;">2</span></div>
<div style="margin-left:20px;"><font color="green"><b>F0</b></font> [<font color="green"><b>C</b></font>, <font color="green"><b>usually singular</b></font>] a crease in paper</div>
<span {LINE}><font color="gray">» There was a grelt in the page.</font></span>
<span {LINE}><font color="olive"><u>Word partners</u></font> for <font color="blue"><b>grelt</b></font></span>
<span {LINE}><font color="gray"><font color="darkred">•</font> NOT AN EXAMPLE a grelt</font></span>
<span {LINE}><font color="olive"><u>Collocations</u></font>:</span>
<span {LINE}><font color="gray">» NOT AN EXAMPLE EITHER.</font></span>
<div style="margin-left:20px;"><font size="+0" color="lightgray">• • •</font></div>
<span {LINE}><font color="olive"><u>Extra Examples</u></font>:</span>
<span {LINE}><font color="gray">» Grelts happen.</font></span>
<br><div style="margin-top:8px;"></div>
<div style="float:left;overflow:hidden;"><font color="crimson"><b>Ⅱ</b></font></div>
<div style="margin-left:20px;"><span {BADGE}>verb</span> <font color="green">[T]</font> ↑<a href="entry://Verb Endings for grelt">Verb Endings for grelt</a></div>
<span {LINE}><font style="color:darkred;font-size:70%;">►</font> <font color="green"><b>F0</b></font> to fold something badly: </span>
<span {LINE}><font color="gray">» She grelted the map.</font></span>
<div style="margin-left:20px;"><font size="+0" color="lightgray">• • •</font></div>
<span {LINE}><font color="olive"><u>Extra Examples</u></font>:</span>
<span {LINE}><font color="gray">» Never grelt a chart.</font></span>
<font size="+0">—<font color="navy"><b>ˈgreltly</b></font> <a href="sound://ukgreltly.spx"><img src="snd_uk.png" border="0"></a> /-li/ <font color="green"><b>adverb</b></font></font><br>
<span {LINE}><font>►</font> <font color="green"><b>F0</b></font></span>
<span {LINE}><font color="gray">» He smiled greltly.</font></span>
</div>"""

PHRASAL_VERB = f"""<b><font size="+1">grelt sth up</font></b><br>
<font size="+0"><font color="blue"><b>grelt sth up</b></font> <sub><font size="-0">FORMAL</font></sub> — <font color="green"><b>phrasal verb</b></font>
 with <font color="blue"><b>grelt</b></font> <a href="sound://ukgrelt001.spx"><img src="snd_uk.png"></a> /ɡrelt/ <font color="green"><b>verb</b></font></font><br>
<span {LINE}><font>►</font> <font color="green"><b>B1</b></font> to fold something upwards: </span>
<span {LINE}><font color="gray">» Grelt the corner up.</font></span>"""

POINTER = f"""<b><font size="+1">grelte</font></b><br>
<font size="+0"><font color="blue"><b>grelte</b></font> <font color="green"><b>noun</b></font></font><br>
<span {LINE}><font>►</font> <font color="green"><b>F0</b></font> <sub><font size="-0"><font color="darkviolet">US</font> FOR</font></sub>
 <font color="dodgerblue"><b>GRELT</b></font>(<font color="green"><b>Cf.</b></font> ↑<a href="entry://grelt">grelt</a>)</span>"""

REDIRECT = """<font color="darkmagenta"><b>⇒</b></font> <a href="entry://grelt">grelt</a>"""

VERB_ENDINGS = f"""<b><font size="+1">Verb Endings for grelt</font></b><br>
<font size="+0"><font color="blue"><b>Verb Endings for grelt</b></font></font><br>
<span {LINE}><font color="gray">he/she/it <font color="sienna">grelts</font></font></span>
<span {LINE}><font color="olive"><u>past simple</u></font>: <font color="sienna">grelted</font></span>"""


class CaldParser(unittest.TestCase):
    def setUp(self):
        self.e = cald.parse("grelt", HTML)

    def of(self, kind):
        return [s for s in self.e.senses if s.kind == kind]

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, cald.COVERS))

    def test_headword_pos_prons_forms(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelt", "", ("noun", "verb")))
        self.assertEqual([(p.region, p.ipa, p.audio) for p in self.e.prons],
                         [("uk", "ɡrelt", "sound://ukgrelt001.spx"), ("us", "ɡrɛlt", "sound://grelt.spx")])
        self.assertEqual(self.e.forms, ("grelte",))

    def test_numbered_senses_take_block_and_leading_labels_but_not_the_level(self):
        s1, s2 = self.of("sense")[:2]
        self.assertEqual((s1.pos, s1.number, s1.labels, s1.definition),
                         ("noun", "1", ("C", "INFORMAL"), "a map folded the wrong way"))
        self.assertEqual([(x.text, x.labels) for x in s1.examples],
                         [("He handed me a grelt (= a badly folded map).", ()),
                          ("They proved that UK maps grelt.", ("+ that", "MAINLY US"))])
        self.assertEqual((s2.number, s2.labels, s2.definition), ("2", ("C", "usually singular"), "a crease in paper"))

    def test_extra_examples_of_a_multi_sense_block_become_their_own_sense(self):
        extra = self.of("sense")[2]
        self.assertEqual((extra.pos, extra.definition, [x.text for x in extra.examples]), ("noun", "", ["Grelts happen."]))

    def test_extra_examples_of_a_single_sense_block_join_that_sense(self):
        verb = self.of("sense")[3]
        self.assertEqual((verb.pos, verb.number, verb.labels, verb.definition), ("verb", "", ("T",), "to fold something badly"))
        self.assertEqual([x.text for x in verb.examples], ["She grelted the map.", "Never grelt a chart."])

    def test_side_boxes_do_not_leak(self):
        flat = repr(self.e.senses)
        for leaked in ("NOT AN EXAMPLE", "Maps", "FOLD", "Verb Endings"):
            self.assertNotIn(leaked, flat)
        self.assertEqual(len(self.of("sense")), 4)

    def test_run_on_derivative_keeps_its_own_pos_and_not_the_entry_prons(self):
        (dr,) = self.of("derivative")
        self.assertEqual((dr.phrase, dr.pos, dr.definition, [x.text for x in dr.examples]),
                         ("greltly", "adverb", "", ["He smiled greltly."]))
        self.assertNotIn("adverb", self.e.pos)
        self.assertEqual(dr.labels, ())  # the main word's "[T]" does not reach it
        self.assertNotIn("-li", [p.ipa for p in self.e.prons])

    def test_strong_and_weak_forms_are_pron_notes_and_form_transcriptions_are_skipped(self):
        html = """<b><font size="+1">grelt</font></b><br>
<font size="+0"><font color="blue"><b>grelt</b></font> <a href="sound://ukg.spx"><img src="snd_uk.png"></a>
 <a href="sound://usg.spx"><img src="snd_us.png"></a> <sub><font size="-0">WEAK</font></sub> /ɡrəlt/
 <sub><font size="-0">STRONG</font></sub> /ɡrelt/ <font color="green"><b>noun</b></font>
 (<sub><font size="-0">PLURAL</font></sub> <font color="midnightblue"><b>-elf</b></font> <a href="sound://ukform.spx"><img src="snd_uk.png"></a> /-elf/)</font><br>
<span style="margin-left:20px;display:block;"><font>►</font> <font color="green"><b>F0</b></font> a fold</span>"""
        e = cald.parse("grelt", html)
        self.assertEqual([(p.region, p.ipa, p.audio, p.note) for p in e.prons],
                         [("uk", "ɡrəlt", "sound://ukg.spx", "WEAK"), ("uk", "ɡrelt", "", "STRONG"),
                          ("us", "ɡrəlt", "sound://usg.spx", "WEAK")])
        self.assertEqual((e.forms, e.senses[0].labels), (("grelf",), ()))

    def test_phrasal_verb_page_ignores_the_base_verb_header(self):
        e = cald.parse("grelt sth up", PHRASAL_VERB)
        self.assertEqual((problems(e), e.pos, e.prons), ([], ("phrasal verb",), ()))
        self.assertEqual([(s.kind, s.phrase, s.labels, s.definition) for s in e.senses],
                         [("phrasal_verb", "grelt sth up", ("FORMAL",), "to fold something upwards")])

    def test_phrasal_verb_header_keeps_a_whole_small_capital_label(self):
        html = PHRASAL_VERB.replace('<sub><font size="-0">FORMAL</font></sub>',
                                    '<sub><font size="-0">MAINLY <font color="indigo">US</font></font></sub>')
        (s,) = cald.parse("grelt sth up", html).senses
        self.assertEqual(s.labels, ("MAINLY US",))
        variant = PHRASAL_VERB.replace('<sub><font size="-0">FORMAL</font></sub>',
                                       '(<sub><font size="-0"><font color="indigo">UK</font> ALSO</font></sub> '
                                       '<font color="mediumblue"><b>grelt round</b></font>)')
        (s,) = cald.parse("grelt sth up", variant).senses
        self.assertEqual(s.labels, ())  # "UK" labels the variant

    def test_pointer_definition_is_not_a_definition(self):
        e = cald.parse("grelte", POINTER)
        self.assertEqual((e.senses, e.stub, problems(e)), ((), "xref", []))
        past = POINTER.replace('<font color="darkviolet">US</font> FOR', '<font color="darkviolet">PAST SIMPLE</font> OF')
        self.assertEqual(cald.parse("grelte", past).stub, "inflection")
        self.assertEqual(self.e.stub, "")
        self.assertFalse(covered(e, cald.COVERS))

    def test_abbreviation_expansion_is_a_definition(self):
        html = POINTER.replace('<font color="darkviolet">US</font> FOR', '<font color="indigo">ABBREVIATION</font> FOR')
        self.assertEqual(cald.parse("grelte", html).senses[0].definition, "ABBREVIATION FOR GRELT")

    def test_redirect_and_verb_endings_pages(self):
        redirect = cald.parse("grelting", REDIRECT)
        self.assertEqual((redirect.headword, redirect.senses, redirect.stub, problems(redirect)),
                         ("grelting", (), "xref", []))
        endings = cald.parse("Verb Endings for grelt", VERB_ENDINGS)
        self.assertEqual((endings.forms, endings.senses, endings.stub, endings.part_of, problems(endings)),
                         (("grelts", "grelted"), (), "popup", "grelt", []))
        self.assertEqual(cald.parse("↑Maps", '<b><font size="+1">↑Maps</font></b>').stub, "index")

    def test_run_on_record_is_a_derivative_stub(self):
        html = HTML.split('<br><div style="margin-top:8px;"></div>')[0].replace("ˈgrelt", "grelter") + """
<span style="margin-left:20px;display:block;"><font>►</font> <font color="green"><b>F0</b></font></span>
<span style="margin-left:20px;display:block;"><font color="gray">» A grelter came.</font></span>
<font size="+0"><font color="darkmagenta"><b>Main Entry</b></font>: ↑<a href="entry://grelt">grelt</a></font>"""
        e = cald.parse("grelter", html)
        self.assertEqual((e.stub, [x.text for s in e.senses for x in s.examples], problems(e)),
                         ("derivative", ["A grelter came."], []))

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", '<font size="+0"><font color="blue"><b>', "<<<>>>",
                     '<div style="display:block;"><span>1</span></div><div style="margin-left:20px;">',
                     '<span><font>►</font>']:
            self.assertEqual(problems(cald.parse("x", junk)), [])
        self.assertEqual(cald.parse("x", "").headword, "x")


if __name__ == "__main__":
    unittest.main()
