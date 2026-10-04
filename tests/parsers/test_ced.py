"""Collins English Dictionary parser on a synthetic record that mirrors its markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import ced

SOUND = "https://www.collinsdictionary.com/sounds/hwd_sounds/en_gb_florp.mp3"
HTML = f"""<link rel="stylesheet" href="ced.css">
<div class="dc page"><div class="dictionary Collins_Eng_Dict">
<div class="dictentry dictlink"><div class="cB cB-def" id="florp__1">
 <div class="cB-h"><div class="title_container"><div class="title_frequency_container">
  <div class="word-frequency-container res_hos frenquency-title"><div class="label">Word Frequency</div></div>
  <h2 class="h2_entry"><span class="orth">florp</span><span class="homnum">1</span></h2></div></div></div>
 <div class="mini_h2"><span class="italics">or</span> <span class="orth">florpe</span> <span class="punctuation">(</span>
  <span class="pron type-">ˈflɒrp<span class="ptr hwd_sound type-hwd_sound"><a class="hwd_sound sound" data-mp3="{SOUND}"></a></span></span>
  <span class="pron type-partial"><span class="punctuation">,</span>-rəp</span>
  <span class="pron type-"><span class="punctuation">,</span><span class="lbl type-subj">nautical</span>ˈflɔːp</span>
  <span class="punctuation">,</span> <span class="lbl type-lang">Dutch</span> <span class="pron type-">ˈflœrp</span>
  <span class="punctuation">,</span> <span class="lbl type-geo">US</span> <span class="pron type-">ˈflɔrp</span><span class="punctuation">)</span></div>
 <div class="content definitions ced">
  <div class="hom"><span class="gramGrp pos">noun</span>
   <span class="form inflected_forms type-infl"><b class="var">Word forms:</b> <span class="orth">florps</span></span>
   <div class="sense"><span class="sensenum">1.</span><span class="lbl type-subj">cookery</span>
    <div class="def">a small <a class="ref type-def" href="entry://wooden">wooden</a> spoon</div>
    <div class="cit type-example quote">she stirred the tea with a florp</div></div>
   <div class="sense"><span class="sensenum">2.</span><span class="lbl type-register">informal</span>
    <span class="lbl">Also called</span><span class="form type-var"><span class="punctuation">:</span><span class="orth">ALSO NAME</span></span>
    <div class="sense"><span class="sensenum">a.</span><div class="def">a ladle</div></div>
    <div class="sense"><span class="sensenum">b.</span><div class="def">a pair of ladles, written &lt;a, b&gt;</div></div></div>
   <div class="sense xr"><span class="lbl">a less common word for</span> <a class="ref" href="entry://spoonlet">spoonlet</a></div>
   <div class="sense"><span class="sensenum">4.</span><a class="xr ref" href="entry://florp the pot">florp the pot</a></div>
   <div class="re type-idm"><span class="form type-idm orth">florp the pot</span><span class="lbl type-register">slang</span>
    <div class="sense"><div class="def">to work for nothing</div></div></div>
  </div>
  <div class="hom"><span class="gramGrp"><span class="pos">verb</span><span class="subc"><span class="punctuation">(</span>mainly tr<span class="punctuation">)</span></span></span>
   <div class="sense def">to stir with a florp</div></div>
 </div>
 <div class="content derivs"><div class="re hom_subsec type-drv"><div class="cB-h entry_title">Derived forms</div>
  <span class="form type-drv"><span class="orth">florpish</span> (ˈflɒrpɪʃ)</span><div class="hom gramGrp"><span class="pos">adjective</span></div></div></div>
 <div class="content etyms etym hom_subsec"><div class="cB-h entry_title">Word origin</div>C21: invented <span class="hi rend-i">florpa</span></div>
</div></div>
<div class="dictentry dictlink"><div class="cB cB-def" id="florp__2">
 <div class="cB-h"><h2 class="h2_entry"><span class="orth">florp</span><span class="homnum">2</span></h2></div>
 <div class="mini_h2"></div>
 <div class="content definitions ced"><div class="hom"><span class="gramGrp pos">adjective</span>
  <div class="sense"><div class="def">very wobbly</div></div></div></div>
</div></div>
</div></div>"""

EXTRACT = """<div class="dc page"><div class="dictionary dictentry"><div class="dictlink"><div class="cB cB-def">
 <div class="cB-h"><h2 class="h2_entry"><span class="orth">the whole florp</span></h2></div><div class="mini_h2"></div>
 <div class="content definitions ced"><div class="hom sense"><span class="lbl type-register">informal</span>
  <div class="def">everything at once</div></div>
  <span class="xr"><span class="lbl">See full dictionary entry for</span> <a class="ref" href="entry://florp">florp</a></span></div>
</div></div></div></div>"""


class CedParser(unittest.TestCase):
    def setUp(self):
        self.e = ced.parse("florp", HTML)

    def test_valid_and_covered(self):
        for e in (self.e, ced.parse("the whole florp", EXTRACT)):
            self.assertEqual(problems(e), [])
            self.assertTrue(covered(e, ced.COVERS))

    def test_head_across_homographs(self):
        e = self.e
        self.assertEqual((e.headword, e.homograph, e.pos), ("florp", "1", ("noun", "verb", "adjective")))
        self.assertEqual(e.forms, ("florpe", "florps"))
        self.assertEqual(e.etymology, "C21: invented florpa")

    def test_prons_with_notes_kept_out_of_the_ipa(self):
        self.assertEqual([(p.region, p.ipa, p.audio, p.note) for p in self.e.prons],
                         [("uk", "ˈflɒrp", SOUND, ""), ("", "-rəp", "", ""), ("", "ˈflɔːp", "", "nautical"),
                          ("", "ˈflœrp", "", "Dutch"), ("us", "ˈflɔrp", "", "US")])

    def test_sense_with_label_and_example(self):
        s = self.e.senses[0]
        self.assertEqual((s.number, s.pos, s.labels, s.definition), ("1", "noun", ("cookery",), "a small wooden spoon"))
        self.assertEqual([x.text for x in s.examples], ["she stirred the tea with a florp"])

    def test_subsenses_inherit_labels_and_tuples_stay_as_printed(self):
        a, b = self.e.senses[1:3]
        self.assertEqual((a.number, a.labels, a.definition), ("2a", ("informal",), "a ladle"))
        self.assertEqual((b.number, b.definition), ("2b", "a pair of ladles, written <a, b>"))

    def test_cross_reference_definition_and_pointer(self):
        xr = self.e.senses[3]
        self.assertEqual((xr.definition, xr.labels), ("a less common word for spoonlet", ()))
        self.assertFalse([s for s in self.e.senses if s.number == "4"])

    def test_idiom_verb_derivative_and_second_homograph(self):
        rest = [(s.kind, s.phrase, s.pos, s.labels, s.definition) for s in self.e.senses[4:]]
        self.assertEqual(rest, [("phrase", "florp the pot", "", ("slang",), "to work for nothing"),
                                ("sense", "", "verb", ("mainly tr",), "to stir with a florp"),
                                ("derivative", "florpish", "adjective", (), ""),
                                ("sense", "", "adjective", (), "very wobbly")])

    def test_a_cross_reference_definition_keeps_every_target(self):
        html = HTML.replace('<span class="lbl">a less common', '<span class="punctuation">. </span><span class="lbl">a less common')
        html = html.replace('<a class="ref" href="entry://spoonlet">spoonlet</a>',
                            '<a class="ref" href="entry://spoonlet">spoonlet</a><span class="bold">, </span> '
                            '<a class="ref" href="entry://ladlet">ladlet</a> <span class="punctuation">(</span>sense 2'
                            '<span class="punctuation">)</span>')
        xr = ced.parse("florp", html).senses[3]
        self.assertEqual(xr.definition, "a less common word for spoonlet, ladlet (sense 2)")

    def test_every_homographs_etymology_is_kept(self):
        second = '<div class="content etyms etym hom_subsec"><div class="cB-h entry_title">Word origin</div>C22: guessed</div>'
        html = HTML.replace("very wobbly</div></div></div></div>", "very wobbly</div></div></div></div>" + second)
        self.assertEqual(ced.parse("florp", html).etymology, "(1) C21: invented florpa (2) C22: guessed")
        self.assertEqual(self.e.etymology, "C21: invented florpa")  # one etymology: no number

    def test_also_called_is_neither_label_nor_form(self):
        self.assertNotIn("ALSO NAME", repr(self.e))
        self.assertNotIn("Also called", repr(self.e))

    def test_idiom_extract_skips_its_pointer(self):
        e = ced.parse("the whole florp", EXTRACT)
        self.assertEqual([(s.labels, s.definition) for s in e.senses], [(("informal",), "everything at once")])

    def test_stubs(self):
        self.assertEqual(self.e.stub, "")
        plural = """<div class="dictentry"><h2 class="h2_entry"><span class="orth">florpi</span></h2><div class="mini_h2"></div>
         <div class="content definitions ced"><div class="hom"><span class="gramGrp pos">plural noun</span>
         <div class="sense xr"><a class="ref" href="entry://florp">florp</a></div></div></div></div>"""
        e = ced.parse("florpi", plural)
        self.assertEqual((e.stub, e.senses, problems(e)), ("inflection", (), []))

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", "<div class='dictentry'><div class='definitions'><div class='hom'>", "<<<>>>"]:
            e = ced.parse("x", junk)
            self.assertEqual((e.headword, problems(e)), ("x", []))


if __name__ == "__main__":
    unittest.main()
