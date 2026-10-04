"""ODECN parser on synthetic entries that mirror the ODECN.mdx markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import odecn

HTML = """<link href="ODECN.css" rel="stylesheet" type="text/css"><script src="ODECN.js"></script>
<div class="ODECN"><div class="headword">
 <div class="panel"><a class="mul active" href="#grelt___1">1</a><a class="mul" href="#grelt___2">2</a></div>
 <h2 id="grelt___1">grelt<sup>1</sup></h2><span class="pron">/ɡrelt/</span>
 <div class="variant"> (亦作<em>grelte</em>) </div>
 <div class="spanel" id="grelt_0"><a href="#grelt_1">verb</a></div>
</div>
<div class="item"><div class="pos" id="grelt_1"><a href="#grelt_0">verb</a></div>
 <span class="pos_inflections">-ed, -ing</span><span class="transitivity">with obj.</span>
 <div class="defs"><span class="num">1</span>
  <div class="en_def"><span class="sense-regions">informal</span><span class="grammatical-note">in combination</span>fold (a map) as in<span class="sense-regions">The Grelt Book</span></div>
  <div class="cn_def"><span class="cn_def_text">乱折</span>折皱，揉</div>
  <div class="example"><p class="en"><span class="sense-regions">figurative</span> he grelted the <strong>whole map</strong>.</p><p class="cn">他把整张地图揉皱了。</p></div>
  <div class="addition">NOT A SENSE: an encyclopedic note.</div>
  <span class="origin_text">ORIGIN: NOT ETYMOLOGY.</span>
  <div class="sub_defs"><span class="num">1.1</span><div class="en_def">another term for<a href="entry://FOLD">FOLD</a></div>
   <div class="cn_def">同<a href="entry://FOLD">FOLD</a></div></div>
 </div>
</div>
<div class="phrases"><div class="label">Phrases</div>
 <div class="phrase"><a class="phrase_head" id="phrase_count_1" name="phrase_count_1">grelt the lot</a>
  <span class="phrase_info"> (usu. <em>be grelted</em>) </span>
  <div class="defs"><div class="en_def">fail completely</div><div class="cn_def">彻底失败</div>
   <div class="example"><p class="en">we grelted the lot.</p><p class="cn">我们全搞砸了。</p></div></div></div>
</div>
<div class="phrasal_verbs"><div class="label">Phrasal Verbs</div>
 <div class="phrase"> <a class="phrase_head" id="phrase_count_2">grelt up</a><div class="defs"><span class="num">1</span>
  <div class="en_def">fold upwards</div><div class="cn_def">向上折</div></div></div>
</div>
<div class="derivatives"><div class="label">Derivatives</div><div class="body">
 <h3 class="inflection">grelter</h3> <span class="word-ext"> (also <em>greltor</em>) </span><span class="pos">noun</span>
 <h3 class="inflection">greltly</h3><span class="pos">adverb</span></div></div>
<div class="usage"><div class="label">Usage</div><div class="body">NOT A NOTE SENSE.</div></div>
<div class="origin"><div class="label">Origin</div><div class="body">invented: from <i>grel</i> (see <a href="entry://GREL">GREL</a>).</div></div>
</div>"""

TWO_HOMOGRAPHS = """<div class="ODECN"><div class="headword"><h2 id="x___1">vorp<sup>1</sup></h2></div>
<div class="item"><div class="pos">noun</div><div class="defs"><div class="en_def">a small hill</div><div class="cn_def">小山</div></div></div>
<div class="origin"><div class="label">Origin</div><div class="body">first origin.</div></div></div>
<div class="ODECN"><div class="headword"><h2 id="x___2">vorp<sup>2</sup></h2></div>
<div class="item"><div class="pos">verb</div><div class="defs"><div class="en_def">to climb</div><div class="cn_def">爬</div></div></div>
<div class="origin"><div class="label">Origin</div><div class="body">second origin.</div></div></div>"""

CROSS_REFERENCE = """<div class="ODECN"><div class="cross_reference">See <a href="entry://grelt#phrase_count_1">grelt</a></div>
<a class="form-groups" id="phrase_count_1" name="phrase_count_1">grelt it</a></div>"""

STANDALONE_PHRASE = """<div class="ODECN"><div class="cross_reference">See <a href="entry://grelt#phrase_count_3">grelt</a></div>
<div class="phrase"><a class="phrase_head" id="phrase_count_3">grelt away</a><div class="defs"><span class="num">1</span>
<div class="en_def">fold and hide</div><div class="cn_def">折起藏好</div></div></div></div>"""

POINTER_PHRASE = """<div class="ODECN"><div class="cross_reference">See <a href="entry://grelt#phrase_count_4">grelt</a></div>
<div class="phrase"><a class="phrase_head">a grelt too far</a><div class="defs"><div class="cn_def">见<a href="entry://FAR">FAR</a> </div></div></div></div>"""


class OdecnParser(unittest.TestCase):
    def setUp(self):
        self.e = odecn.parse("grelt", HTML)

    def of(self, kind):
        return [s for s in self.e.senses if s.kind == kind]

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, odecn.COVERS))

    def test_headword_homograph_pos_pron_forms(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelt", "1", ("verb",)))
        self.assertEqual([(p.ipa, p.region, p.audio) for p in self.e.prons], [("ɡrelt", "", "")])
        self.assertEqual(self.e.forms, ("grelte",))

    def test_sense_labels_are_the_opening_spans_only(self):
        s1 = self.of("sense")[0]
        self.assertEqual((s1.pos, s1.number), ("verb", "1"))
        self.assertEqual(s1.labels, ("with obj.", "informal", "in combination"))
        self.assertEqual(s1.definition, "fold (a map) as in The Grelt Book")

    def test_bilingual_definition_and_example(self):
        s1 = self.of("sense")[0]
        self.assertEqual(s1.definition_zh, "乱折 折皱，揉")
        self.assertEqual([(x.text, x.text_zh, x.labels) for x in s1.examples],
                         [("he grelted the whole map.", "他把整张地图揉皱了。", ("figurative",))])
        self.assertEqual(self.of("phrase")[0].examples[0].labels, ())

    def test_sub_sense_keeps_link_spacing_and_inherits_item_labels(self):
        sub = self.of("sense")[1]
        self.assertEqual((sub.number, sub.labels, sub.definition, sub.definition_zh),
                         ("1.1", ("with obj.",), "another term for FOLD", ""))

    def test_side_content_does_not_leak(self):
        flat = repr(self.e.senses)
        for leaked in ("NOT A SENSE", "NOT ETYMOLOGY", "NOT A NOTE", "be grelted", "-ed, -ing"):
            self.assertNotIn(leaked, flat)
        self.assertEqual(len(self.of("sense")), 2)

    def test_phrases_phrasal_verbs_derivatives(self):
        (phrase,) = self.of("phrase")
        self.assertEqual((phrase.phrase, phrase.definition, phrase.definition_zh, phrase.examples[0].text_zh),
                         ("grelt the lot", "fail completely", "彻底失败", "我们全搞砸了。"))
        (pv,) = self.of("phrasal_verb")
        self.assertEqual((pv.phrase, pv.number, pv.definition), ("grelt up", "1", "fold upwards"))
        self.assertEqual([(d.phrase, d.pos) for d in self.of("derivative")], [("grelter", "noun"), ("greltly", "adverb")])

    def test_etymology(self):
        self.assertEqual(self.e.etymology, "invented: from grel (see GREL).")

    def test_homographs_in_one_entry(self):
        e = odecn.parse("vorp", TWO_HOMOGRAPHS)
        self.assertEqual(problems(e), [])
        self.assertEqual((e.headword, e.homograph, e.pos), ("vorp", "", ("noun", "verb")))
        self.assertEqual(e.etymology, "first origin. second origin.")

    def test_suffix_variant_expands_only_when_it_aligns(self):
        head = '<div class="ODECN"><div class="headword"><h2>organize</h2><div class="variant"> (亦作{}) </div></div></div>'
        self.assertEqual(odecn.parse("organize", head.format("-ise")).forms, ("organise",))
        self.assertEqual(odecn.parse("organize", head.format("-our")).forms, ())

    def test_variant_spelling_keeps_the_points_printed_between_its_ems(self):
        head = '<div class="ODECN"><div class="headword"><h2>{}</h2><div class="variant"> ({}) </div></div></div>'
        for headword, variant, forms in (
                ("gqz", "亦作<em>g</em>.<em>q</em>.<em>z</em>.", ("g.q.z.",)),
                ("gqz", "亦作 <em>g.q.z</em>.", ("g.q.z.",)),
                ("grela-", "在元音前亦作<em>grel</em>-", ("grel-",)),
                ("grelt", "亦作<em>grelte</em>. 读音同", ("grelte",)),            # a sentence point, not the spelling's
                ("grelt", "亦作<em>grelte</em>/-tə/或<em>greld</em>", ("grelte", "greld")),
                ("grelt", "亦作<em>grelte</em>, <em>grelte</em>", ("grelte",)),  # a repeated alternative is one form
                # the point before a list separator is the spelling's; the same spelling printed whole is one form
                ("gqz", "亦作<em>g</em>.<em>q</em>.<em>z</em>., <em>g.q.z.</em>", ("g.q.z.",)),
                ("gqz", "亦作<em>g</em>.<em>q</em>.<em>z</em>. 或<em>gqz</em>", ("g.q.z.",))):
            self.assertEqual(odecn.parse(headword, head.format(headword, variant)).forms, forms, variant)

    def test_entry_wide_label_reaches_the_phrases(self):
        html = HTML.replace('<div class="variant"> (亦作<em>grelte</em>) </div>',
                            '<div class="variant"><i>Brit. informal</i>&lt;英, 非正式&gt; </div>')
        e = odecn.parse("grelt", html)
        self.assertEqual({s.kind: s.labels for s in e.senses if s.kind != "derivative"},
                         {"sense": ("Brit. informal", "with obj."), "phrase": ("Brit. informal",),
                          "phrasal_verb": ("Brit. informal",)})

    def test_inflection_pointer_and_pronunciation_in_variant_are_not_labels(self):
        for variant in ('past participle of <a href="entry://GRELT">GRELT</a><sup>1</sup>. <a href="entry://GRELT">GRELT</a>的过去分词。',
                        "present participle of <em>GRELT<sup>2</sup></em>. <em>GRELT</em>的现在分词。", "/ɡrelt/"):
            html = HTML.replace(' (亦作<em>grelte</em>) ', variant)
            self.assertEqual({s.labels for s in odecn.parse("grelt", html).senses if s.kind in ("phrase", "phrasal_verb")},
                             {()}, variant)

    def test_text_after_a_comment_ends_the_leading_labels(self):
        html = ('<div class="ODECN"><div class="item"><div class="defs"><div class="en_def"><!--note-->a '
                '<span class="sense-regions">technical term</span> for a fold</div></div></div></div>')
        (s,) = odecn.parse("grelt", html).senses
        self.assertEqual((s.labels, s.definition), ((), "a technical term for a fold"))
        html = html.replace("<!--note-->a ", "<!--note--> ").replace(" for a fold", "a fold")
        (s,) = odecn.parse("grelt", html).senses
        self.assertEqual((s.labels, s.definition), (("technical term",), "a fold"))

    def test_cross_reference_with_a_second_class_is_still_one(self):
        e = odecn.parse("grelt it", CROSS_REFERENCE.replace('class="cross_reference"', 'class="cross_reference extra"'))
        self.assertEqual((e.senses, e.stub), ((), "xref"))

    def test_broken_escaped_link_stays_as_printed(self):
        html = ('<div class="ODECN"><div class="item"><div class="defs"><div class="cn_def">湖。亦称'
                '&lt;a class="refer" href="entry://LAKE&gt;LAKE &lt;北美&gt;</div></div></div></div>')
        e = odecn.parse("lake", html)
        self.assertEqual((problems(e), e.senses[0].definition_zh),
                         ([], '湖。亦称<a class="refer" href="entry://LAKE>LAKE <北美>'))

    def test_cross_reference_stub_is_uncovered(self):
        e = odecn.parse("grelt it", CROSS_REFERENCE)
        self.assertEqual((e.headword, e.senses, e.stub, problems(e)), ("grelt it", (), "xref", []))
        self.assertFalse(covered(e, odecn.COVERS))
        self.assertEqual((self.e.stub, odecn.parse("grelt away", STANDALONE_PHRASE).stub), ("", ""))

    def test_standalone_phrase_entry(self):
        e = odecn.parse("grelt away", STANDALONE_PHRASE)
        self.assertEqual([(s.kind, s.phrase, s.definition, s.definition_zh) for s in e.senses],
                         [("phrase", "grelt away", "fold and hide", "折起藏好")])

    def test_pointer_only_chinese_is_not_a_definition(self):
        e = odecn.parse("a grelt too far", POINTER_PHRASE)
        self.assertEqual((e.senses, e.stub, problems(e)), ((), "xref", []))

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", '<div class="ODECN"><div class="defs">', "<<<>>>",
                     '<div class="phrase"><a class="phrase_head">', '<div class="variant">(亦作']:
            self.assertEqual(problems(odecn.parse("x", junk)), [])
        self.assertEqual(odecn.parse("x", "").headword, "x")


if __name__ == "__main__":
    unittest.main()
