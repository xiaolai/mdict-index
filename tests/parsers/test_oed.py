"""OED parser on synthetic records that mirror OED online markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import oed

Q = """<div class="quotation"><span class="noIndent"><span>{date}&nbsp;&nbsp;</span>  <span class="smallCaps">A. Writer</span>
 <em><a class="sourcePopup" href="javascript:void(0)">Invented Bk.</a></em> ii. 4</span>&nbsp;&nbsp;{text}</div>"""

# like the real records, a homograph's divs are left unclosed before the next <body>
MAIN = """
<body><a target="_new" href="/view/Entry/1"></a><link href="OED.css" rel="stylesheet"><script src="OED.js"></script>
<title>grelt, n.1 : Oxford English Dictionary</title>
<div id="mainContent"><h1><span class="hwSect"><span class="hw">grelt</span>, <span class="ps">n.<sup class="hm">1</sup></span></span></h1>
<div class="cssBaseOne">
 <div class="pronunciation preEntry"><strong><span>Pronunciation:</span></strong>
  <div class="pronunciation-wrapper">Brit.<a href="sound://audio/gb1.mp3"><img src="file://img/sound.png" alt="sound"></a>/<span class="phonetics">ɡrɛlt</span>/</div>,
  <div class="pronunciation-wrapper"><a href="sound://audio/gb2.mp3"></a>/<span class="phonetics">ɡrelt</span>/</div>,
  <div class="pronunciation-wrapper">U.S.<a href="sound://audio/us1.mp3"></a>/<span class="phonetics">ɡrɛlt</span>/</div>,
  <div class="pronunciation-wrapper">Scottish<a href="sound://audio/sc1.mp3"></a>/<span class="phonetics">ɡrɛltʃ</span>/</div></div>
 <div class="forms preEntry"><strong>Forms:</strong> ME <strong>grellte</strong>, 15– <strong>grelt</strong>.</div>
 <div class="frequencyBand preEntry"><strong>Frequency (in current use):</strong></div>
 <div class="preEntry"><strong>Origin:</strong><span class="etymSummary">SUMMARY ONLY</span></div>
 <div class="etymology preEntry"><strong>Etymology: </strong>&lt; Florpish <em>grelta</em>, &lt;florp v.<a href="#" class="more">(Show Less)</a></div>
 <div class="senseSect entryBase"><div class="senseWrap"><span class="numbering"><strong>A.</strong></span> <span class="ps">n.</span>
  <div class="senseGroup scrollUnit"><div class="top"><div class="corner"></div><h3> <span class="numbering"><strong>1.</strong></span>
   <em>transitive</em>. <em>U.S.</em> A badly folded   map.<span class="note">EDITORIAL NOTE</span></h3></div>
   <div class="frame"><div class="quotationsBlock">""" + Q.format(date="1850", text="He left the <span class=\"quotationKeyword\">grelt</span> on the table.") + """
    <div class="quotation"><span class="noIndent"><span><i>a</i>1400 (<span class="dateWedge">▸<i>c</i>1350)</span>&nbsp;&nbsp;</span>
     <em><span class="sourcePopup">Old Tale</span></em> 12</span>&nbsp;&nbsp;A grelt, a grelt.</div>
   </div><div class="quotationsBlockSibling"><em>transf.</em>""" + Q.format(date="1901", text="[ Grelts everywhere.]") + """</div>
   <p class="quotations"><span class="quotationDate t-invisible">1400—1901</span></p></div></div>
  <div class="senseGroup"><div class="top"><h3>†<span class="numbering"><strong>2.</strong></span>  <em>Nautical</em>. A knot. <em>Obsolete</em>.</h3></div></div>
 </div></div>
 <div class="lemSect entryBase"><h3 class="lemSectType">Derivatives</h3><div class="senseWrap">
  <div class="senseGroup"><div class="top"><h3><span class="lemma">ˈgreltish</span><span class="almostInvisible"> </span><span> </span>
   <span class="ps">adj.</span> somewhat like a grelt.</h3></div>
   <div class="frame"><div class="quotationsBlock">""" + Q.format(date="1920", text="A greltish fold.") + """</div></div></div></div></div>
 <div class="lemSect entryBase"><h3 class="lemSectType">Phrasal verbs</h3><div class="senseWrap">
  <span class="numbering"><strong>PV1.</strong></span> With adverbs.
  <span class="subentryInline"><span class="lemma">to grelt up</span><span class="almostInvisible"> </span><div class="senseSect entryBase">
   <div class="senseWrap"><div class="senseGroup"><div class="top"><h3> <span class="numbering"><strong>1.</strong></span> <em>intransitive</em>. To give up.</h3></div></div></div></div></span>
 </div></div>
 <div class="rev"><p>This entry has been updated (INVENTED NOTE).</p></div>
</body><hr class="hr_multi_keys" style="border-top:3px solid div;">
<body><title>grelt, v. : Oxford English Dictionary</title>
<div id="mainContent"><h1><span class="hwSect"><span class="hw">grelt</span>, <span class="ps">v.</span></span></h1>
<div class="cssBaseOne"><div class="etymology preEntry"><strong>Etymology: </strong>From the noun.</div>
 <div class="senseSect entryBase"><div class="senseWrap"><div class="senseGroup"><div class="top"><h3>  To fold badly.</h3></div></div></div></div>
</div></div></body>"""

SUB = """<link href="OED.css"><script src="OED.js"></script><span class="hw1">grelt-maker</span>
<div class="phrase"><div class="senseGroup scrollUnit"><div class="top"><div class="corner"></div>
 <h3><span class="lemma">grelt-maker</span><span></span> <span class="ps">n.</span>
  <div class="pronunciation-wrapper">Brit.<a href="sound://audio/sub_gb.mp3"></a><span class="sup-phonetics">/<span class="phonetics">ˈɡrɛltˌmeɪkə</span>/</span></div></h3></div>
 <div class="frame"><div class="quotationsBlock">""" + Q.format(date="1777", text="The grelt-maker came.") + """</div></div></div>
 <div class="ref"><span class="see_label"></span><span class="main_entry"></span><a class="link" href="entry://grelt">grelt</a></div></div>"""

STUB = """<span class="hw1">grelted</span><div class="phrase"><div class="senseGroup shortSense"><div class="top">
<h3><span class="lemma">grelted</span> <span class="ps">adj.</span></h3></div></div>
<div class="ref"><a class="link" href="entry://grelt">grelt</a></div></div>"""

OLD = """<div id="mainContent"><h1><span class="hwSect"><span class="hw">florp</span>, <span class="ps">n.</span></span></h1>
<div class="cssBaseOne"><div class="pronunciation preEntry"><strong><span>Pronunciation:</span></strong>
 <a href="sound://audio/florp.mp3"><img src="file://img/sound.png"></a>/<span class="phonetics">flɔːp</span>/</div>
<div class="senseSect entryBase"> <em>Linguistics</em>.<div class="senseWrap"><div class="senseWrap">
 <div class="senseWrap"> <span class="numbering"><strong>a.</strong></span> A sign.</div>
 <div class="senseWrap"> <span class="numbering"><strong>b.</strong></span> A unit.</div></div></div></div></div></div>"""

class OedParser(unittest.TestCase):
    def setUp(self):
        self.e = oed.parse("grelt", MAIN)

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, oed.COVERS))
        self.assertEqual(self.e.stub, "")

    def test_headword_and_homographs(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelt", "", ("n.", "v.")))
        single = oed.parse("grelt", MAIN.split('<hr class="hr_multi_keys"')[0])
        self.assertEqual((single.homograph, single.pos), ("1", ("n.",)))

    def test_prons_with_inherited_region(self):
        self.assertEqual([(p.region, p.ipa, p.audio) for p in self.e.prons],
                         [("uk", "ɡrɛlt", "sound://audio/gb1.mp3"), ("uk", "ɡrelt", "sound://audio/gb2.mp3"),
                          ("us", "ɡrɛlt", "sound://audio/us1.mp3"), ("", "ɡrɛltʃ", "sound://audio/sc1.mp3")])
        self.assertEqual([p.note for p in self.e.prons], ["", "", "", "Scottish"])

    def test_forms_and_etymologies(self):
        self.assertEqual(self.e.forms, ("grellte", "grelt"))
        self.assertEqual(self.e.etymology, "(n.1) < Florpish grelta, <florp v. (v.) From the noun.")  # as printed

    def test_sense_number_labels_definition(self):
        one = self.e.senses[0]
        self.assertEqual((one.kind, one.pos, one.number, one.labels, one.definition),
                         ("sense", "n.", "A.1", ("transitive", "U.S."), "A badly folded map."))
        two = self.e.senses[1]
        self.assertEqual((two.number, two.labels, two.definition, two.examples), ("A.2", ("†", "Nautical"), "A knot. Obsolete.", ()))

    def test_quotations(self):
        self.assertEqual([(x.kind, x.date, x.source, x.text, x.labels) for x in self.e.senses[0].examples], [
            ("quotation", "1850", "A. Writer Invented Bk. ii. 4", "He left the grelt on the table.", ()),
            ("quotation", "a1400 (▸c1350)", "Old Tale 12", "A grelt, a grelt.", ()),
            ("quotation", "1901", "A. Writer Invented Bk. ii. 4", "[ Grelts everywhere.]", ("transf.",))])

    def test_form_group_block_labels_its_quotations(self):
        e = oed.parse("grelt", MAIN.replace("<em>transf.</em>", "β."))
        self.assertEqual(e.senses[0].examples[-1].labels, ("β.",))

    def test_derivative_and_phrasal_verb(self):
        der = next(s for s in self.e.senses if s.kind == "derivative")
        self.assertEqual((der.phrase, der.pos, der.definition, der.examples[0].date), ("ˈgreltish", "adj.", "somewhat like a grelt.", "1920"))
        pv = next(s for s in self.e.senses if s.kind == "phrasal_verb")
        self.assertEqual((pv.phrase, pv.number, pv.labels, pv.definition), ("to grelt up", "PV1.1", ("intransitive",), "To give up."))

    def test_second_homograph_senses_carry_their_pos(self):
        # lxml nests the second mainContent inside the first; each sense must still be read once
        self.assertEqual([s.kind for s in self.e.senses], ["sense", "sense", "derivative", "phrasal_verb", "sense"])
        self.assertEqual((self.e.senses[-1].pos, self.e.senses[-1].definition), ("v.", "To fold badly."))

    def test_notes_summary_and_publication_info_stay_out(self):
        dump = repr(self.e)
        for leaked in ("EDITORIAL NOTE", "SUMMARY ONLY", "INVENTED NOTE", "Show Less", "Frequency", "1400—1901", "With adverbs"):
            self.assertNotIn(leaked, dump)

    def test_sub_entry_record(self):
        e = oed.parse("grelt-maker", SUB)
        self.assertEqual((e.headword, e.pos, [(p.region, p.ipa) for p in e.prons]), ("grelt-maker", ("n.",), [("uk", "ˈɡrɛltˌmeɪkə")]))
        (s,) = e.senses
        self.assertEqual((s.kind, s.phrase, s.definition, s.examples[0].text), ("sense", "", "", "The grelt-maker came."))
        self.assertFalse(covered(e, oed.COVERS))  # a quotation-only sub-entry has no definition to cover
        self.assertEqual((e.stub, e.part_of), ("popup", "grelt"))  # ... it is defined as a group in its parent
        self.assertEqual(problems(e), [])
        orphan = oed.parse("grelt-maker", SUB.split('<div class="ref">')[0])
        self.assertEqual((orphan.stub, orphan.part_of), ("derivative", ""))
        selfish = oed.parse("grelt-maker", SUB.replace('href="entry://grelt">grelt</a>', 'href="entry://grelt-maker">grelt-maker</a>'))
        self.assertEqual((selfish.stub, selfish.part_of), ("derivative", ""))
        defined = oed.parse("grelt-maker", SUB.replace("</h3>", " one who grelts.</h3>", 1))
        self.assertEqual((defined.senses[0].definition, defined.stub, defined.part_of), ("one who grelts.", "", ""))

    def test_stub_has_no_senses(self):
        e = oed.parse("grelted", STUB)
        self.assertEqual((e.headword, e.senses, e.stub, e.part_of, problems(e)), ("grelted", (), "popup", "grelt", []))
        self.assertEqual(oed.parse("grelted", STUB.replace('<div class="ref"><a class="link" href="entry://grelt">grelt</a></div>', "")).stub,
                         "empty")

    def test_stub_keeps_the_pos_and_prons_its_heading_prints(self):
        e = oed.parse("grelted", STUB)
        self.assertEqual((e.pos, e.senses, e.stub, problems(e)), (("adj.",), (), "popup", []))
        spoken = STUB.replace("</h3>", '<div class="pronunciation-wrapper">U.S.<span class="sup-phonetics">/'
                                       '<span class="phonetics">ˈɡrɛltɪd</span>/</span></div></h3>')
        e = oed.parse("grelted", spoken)
        self.assertEqual((e.pos, [(p.region, p.ipa) for p in e.prons], e.stub), (("adj.",), [("us", "ˈɡrɛltɪd")], "popup"))

    def test_quotation_with_a_second_class_is_not_a_block_label(self):
        e = oed.parse("grelt", MAIN.replace('<div class="quotation">', '<div class="quotation extra">'))
        self.assertEqual([x.labels for x in e.senses[0].examples], [(), (), ("transf.",)])

    def test_older_layout_bare_wraps_and_unlabelled_phonetics(self):
        e = oed.parse("florp", OLD)
        self.assertEqual([(p.region, p.ipa, p.audio) for p in e.prons], [("", "flɔːp", "sound://audio/florp.mp3")])
        self.assertEqual([(s.number, s.labels, s.definition) for s in e.senses],
                         [("a", ("Linguistics",), "A sign."), ("b", ("Linguistics",), "A unit.")])
        self.assertEqual(problems(e), [])

    def test_garbage_never_raises(self):
        for junk in ["", "<", "<div id='mainContent'><h1><span class='hwSect'>", "plain text", "<<<>>>",
                     "<div class='senseGroup'><div class='top'><h3>†", "<span class='subentryInline'>"]:
            e = oed.parse("x", junk)
            self.assertEqual(e.headword, "x")
            self.assertEqual(problems(e), [])


if __name__ == "__main__":
    unittest.main()
