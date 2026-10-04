"""MWU parser on synthetic entries that mirror Merriam-Webster Unabridged markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import mwu

HTML = """
<div class="container"><link href="mwu20.css" rel="stylesheet">
<ul class="tab multi"><li><a href="#mwu_1"><span class="entry-text"><sup>1</sup>grelt</span><span class="word-class">(verb)</span></a></li></ul>
<div class="main">
<div class="tab-view"><div class="well content-body">
 <div class="wrapper"><div class="hdword"><sup>1</sup>grelt–ing·ly</div><div class="fl">verb</div>
  <div class="pron"><span class="pr">\\<span class="unicode">ˈ</span>grelt\\</span></div>
  <div class="audio"><a class="play_pron" data-file="grelt001" href="sound://audios/grelt001.wav"><img src="/sound.png"></a></div></div>
 <div class="section variants"><em class="vl">or British</em> <strong>grelte</strong></div>
 <div class="section inf-forms"><span class="in-more"><strong>grelt·ed</strong> <span class="pr">\\NOT A PRON\\</span>;</span>
  <span class="in"><span class="ix"><em>plural</em> <strong>-s</strong></span></span></div>
 <div class="section" data-id="definition"><div class="wordclick"><div>
  <div class="d"><div class="vt">transitive verb</div>
   <div class="sblk"><div class="snum">1</div><div class="scnt">
    <span class="ssens"><em class="sn">a</em> <strong>:</strong>&nbsp; to fold (a map) the   wrong way
      <span class="vi">&lt;he <em>grelted</em> the chart — A. N. Author&gt;</span>
      <span class="called-also"> — called also <em>florping</em></span></span>
    <span class="ssens snblk subsense"><em class="ssn">(1)</em> <em>archaic</em>, <em>chiefly Scottish</em> <strong>:</strong>&nbsp; to crease
      <span class="set">[NOT A DEFINITION]</span> <span class="dx"> — see <a class="dx" href="entry://crease">crease</a></span></span>
    <span class="ssens snblk subsense"><em class="ssn">(2)</em> <strong>:</strong>&nbsp; to crease twice <span class="vir">&lt;grelt<em>ed</em>&gt;</span>, as a rule</span>
   </div></div>
   <div class="sblk"><div class="snum">2</div><div class="scnt"><span class="ssens"><strong>:</strong>&nbsp; to whistle (to a gull &lt;or&gt; a goat)
     <span class="vi">&lt;<span class="psl-container">(<span class="psl">figurative</span>)</span> the engine <em>grelts</em>&gt;</span>
     <span class="snote"><span class="mark">◆</span>NOT A DEFINITION EITHER</span></span></div></div>
   <div class="r"> — <strong>grelt·er</strong> <span class="pr">\\x\\</span> <em>noun,</em>
     <span class="utxt"><span class="vi">&lt;a busy <em>grelter</em>&gt;</span></span></div>
   <div class="dr"> — <strong>grelt out</strong><div class="d"><em>slang</em>
     <div class="sense-block-one"><div class="scnt"><span class="ssens"><strong>:</strong>&nbsp; to scamper off at dusk</span></div></div></div></div>
  </div>
  <div class="d dxnl"><div class="sense-block-one"><div class="scnt">—see also <a class="dxnl" href="entry://x">NOT A SENSE</a></div></div></div>
 </div></div></div>
 <div class="section custom-accordion" data-id="origin"><h2 class="toggle"><span class="text">Origin of GRELT</span></h2>
  <div class="section-content etymology"><div class="sub-well"><p>Middle Florpish <em>grelten</em> to fold</p>
   <p>First Known Use: 14th century (sense 1a)</p></div></div></div>
 <div class="section custom-accordion related-to" data-id="related-to"><h2 class="toggle"><span class="text">Related to GRELT</span></h2>
  <div class="section-content"><div class="sub-well"><dl><dt>Synonyms:</dt><dd><a href="entry://fold">SYNONYM</a></dd></dl></div></div></div>
</div></div>
<div class="tab-view"><div class="well content-body">
 <div class="wrapper"><div class="hdword"><sup>2</sup>grelt</div><div class="fl">noun,</div>
  <div class="pron"><span class="pr">\\<span class="unicode">ˈ</span>grelt\\</span></div>
  <div class="audio"><a class="play_pron" href="sound://audios/grelt001.wav"></a></div></div>
 <div class="section" data-id="definition"><div class="wordclick"><div><div class="d">
  <div class="sense-block-one"><div class="scnt"><strong><span class="ssens"><strong>:</strong>&nbsp; a badly folded map</span></strong></div></div>
 </div></div></div>
 <div class="section custom-accordion" data-id="origin"><div class="section-content etymology"><div class="sub-well"><p>from <sup>1</sup>grelt</p></div></div></div>
</div></div>
<script>googletag.cmd.push(function() { googletag.display('ad'); });</script>
</div></div>"""

STUB = """<div class="container"><div class="main"><div class="tab-view"><div class="well content-body">
 <div class="wrapper"><div class="hdword">grelts</div><div class="audio"></div></div>
 <div class="section" data-id="definition"><div class="wordclick"><div><div class="d"><div class="sense-block-one">
  <div class="scnt"><em>plural of</em> <a class="ct" href="entry://grelt">grelt</a></div></div></div></div></div></div>
</div></div></div></div>"""

PHRASE_PAGE = """<div class="phrase container"><div class="main"><div class="tab-view"><div class="well content-body">
 <div class="dr"> — <strong>grelt up</strong><div class="d"><div class="sense-block-one"><div class="scnt">
  <span class="ssens"><strong>:</strong>&nbsp; to fold completely</span></div></div></div></div>
 <div class="ref"><span class="desc">see: main-entry</span><div class="hdword"><a href="entry://grelt">grelt</a></div></div>
</div></div></div></div>"""


class MwuParser(unittest.TestCase):
    def setUp(self):
        self.e = mwu.parse("grelt", HTML)

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, mwu.COVERS))
        self.assertEqual(self.e.stub, "")

    def test_headword_homograph_pos(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelt-ingly", "", ("verb", "noun")))
        single = mwu.parse("florp", STUB.replace("grelts", "flor·p").replace("<div class=\"hdword\">", "<div class=\"hdword\"><sup>3</sup>"))
        self.assertEqual((single.headword, single.homograph), ("florp", "3"))

    def test_prons_deduplicated_and_forms(self):
        self.assertEqual([(p.region, p.ipa, p.audio) for p in self.e.prons], [("", "ˈgrelt", "sound://audios/grelt001.wav")])
        self.assertEqual(self.e.forms, ("grelte", "grelted"))

    def test_sense_numbers_labels_definitions_examples(self):
        a, a1, a2, two = self.e.senses[:4]
        self.assertEqual((a.number, a.labels, a.definition), ("1a", ("transitive verb",), "to fold (a map) the wrong way"))
        self.assertEqual([(x.text, x.kind) for x in a.examples], [("he grelted the chart — A. N. Author", "example")])
        self.assertEqual((a1.number, a1.labels, a1.definition), ("1a(1)", ("transitive verb", "archaic", "chiefly Scottish"), "to crease"))
        self.assertEqual((a2.number, a2.definition, [x.text for x in a2.examples]), ("1a(2)", "to crease twice, as a rule", ["grelted"]))
        self.assertEqual((two.number, two.definition), ("2", "to whistle (to a gull <or> a goat)"))  # as printed
        self.assertEqual([(x.text, x.labels) for x in two.examples], [("the engine grelts", ("figurative",))])

    def test_derivative_and_run_on_phrase(self):
        der = next(s for s in self.e.senses if s.kind == "derivative")
        self.assertEqual((der.phrase, der.pos, [x.text for x in der.examples]), ("grelter", "noun", ["a busy grelter"]))
        phrase = next(s for s in self.e.senses if s.kind == "phrase")
        self.assertEqual((phrase.phrase, phrase.labels, phrase.definition), ("grelt out", ("slang",), "to scamper off at dusk"))

    def test_second_homograph_and_etymologies(self):
        noun = self.e.senses[-1]
        self.assertEqual((noun.pos, noun.number, noun.definition), ("noun", "", "a badly folded map"))
        self.assertEqual(self.e.etymology, "(1) Middle Florpish grelten to fold (2) from 1grelt")

    def test_side_boxes_notes_and_ads_stay_out(self):
        dump = repr(self.e)
        for leaked in ("SYNONYM", "NOT A SENSE", "NOT A DEFINITION", "NOT A PRON", "googletag", "florping", "First Known Use"):
            self.assertNotIn(leaked, dump)

    def test_cross_reference_stub(self):
        stub = mwu.parse("grelts", STUB)
        self.assertEqual((stub.senses, stub.stub, stub.extra), ((), "inflection", {"see": "plural of grelt"}))
        variant = mwu.parse("grelte", STUB.replace("plural of", "variant spelling of"))
        self.assertEqual(variant.stub, "variant")
        see = mwu.parse("grelte", STUB.replace("<em>plural of</em> <a class=\"ct\"", "<span class=\"ssens\"><span class=\"dx\"> — see <a class=\"dx\"").replace("grelt</a></div>", "grelt</a></span></span></div>"))
        self.assertEqual((see.stub, see.extra), ("xref", {"see": "see grelt"}))
        self.assertFalse(covered(stub, mwu.COVERS))

    def test_pron_qualifiers_become_notes(self):
        page = STUB.replace('<div class="audio"></div>', '<div class="pron"><span class="pr">\\grə, <em>especially when stressed</em> '
                            '(<span class="unicode">¦</span>)grā <em>or</em> grä; <em>variants are not shown</em>\\</span></div>'
                            '<div class="audio"><a class="play_pron" href="sound://audios/grelt002.wav"></a></div>')
        e = mwu.parse("grelts", page)
        self.assertEqual([(p.ipa, p.note, p.audio) for p in e.prons],
                         [("grə", "", "sound://audios/grelt002.wav"), ("(¦)grā", "especially when stressed", ""), ("grä", "or; variants are not shown", "")])
        self.assertEqual(problems(e), [])

    def test_a_sign_ends_the_transcription_unless_printed_straight_before_a_qualifier(self):
        # "dis+, <em>or</em>": the "+" is the transcription's own; "fər, + <em>vowel</em>": it opens the qualifier
        page = STUB.replace('<div class="audio"></div>', '<div class="pron"><span class="pr">\\grəs, (<span class="unicode">ˈ</span>)'
                            'grel+, <em>or</em> -sk- <em>instead of</em> -sg-, + <em>vowel</em> grər\\</span></div>'
                            '<div class="audio"></div>')
        self.assertEqual([(p.ipa, p.note) for p in mwu.parse("grelts", page).prons],
                         [("grəs, (ˈ)grel+", ""), ("-sk-", "or"), ("-sg-", "instead of"), ("grər", "+vowel")])

    def test_plural_pointer_is_a_variant_stub(self):
        self.assertEqual(mwu.parse("grelte", STUB.replace("plural of", "archaic variants of")).stub, "variant")
        self.assertEqual(mwu.parse("grelte", STUB.replace("plural of", "British spellings of")).stub, "variant")

    def test_verb_type_label_reaches_a_nested_d(self):
        sense = '<div class="sense-block-one"><div class="scnt"><span class="ssens"><strong>:</strong> {}</span></div></div>'
        page = STUB.replace('<div class="d"><div class="sense-block-one">', '<div class="d"><div class="vt">transitive verb</div>'
                            '<div class="d"><em>slang</em>' + sense.format("to fold up") + '</div>'
                            '<div class="d"><div class="vt">intransitive verb</div>' + sense.format("to fold") + '</div>'
                            + sense.format("to crease") + '<div class="sense-block-one">')
        self.assertEqual([(x.labels, x.definition) for x in mwu.parse("grelts", page).senses],
                         [(("slang", "transitive verb"), "to fold up"), (("intransitive verb",), "to fold"),
                          (("transitive verb",), "to crease")])

    def test_phrase_page(self):
        e = mwu.parse("grelt up", PHRASE_PAGE)
        self.assertEqual([(s.kind, s.phrase, s.definition) for s in e.senses], [("phrase", "grelt up", "to fold completely")])
        self.assertEqual((e.headword, problems(e)), ("grelt up", []))

    def test_garbage_never_raises(self):
        for junk in ["", "<", "<div class='tab-view'><div class='hdword'>", "plain text", "<<<>>>",
                     "<div class='d'><div class='sblk'><div class='scnt'><span class='ssens'>"]:
            e = mwu.parse("x", junk)
            self.assertEqual(e.headword, "x")
            self.assertEqual(problems(e), [])


if __name__ == "__main__":
    unittest.main()
