"""ODE parser on synthetic entries that mirror the obfuscated ODE 3e markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import ode

HTML = """<link rel="stylesheet" href="ODE.css"><script src="ODE.js"></script>
<div class="Od3"><div class="k0i">
<div class="h1s"><a id="grelt"></a><h2 class="z2h">grel<span class="tfr"></span>t<span class="lx6">1</span></h2>
 <span class="pxt">/ɡrɛlt <img src="pr.png" onclick="o0e.a(this,0,'g/gre/grelt/grelt__gb_1')" class="a8e">/</span></div>
<div><div><span class="rqo">(also <span class="l6p">grelte</span>)</span>
<div class="k0z"><span class="nvt"><span class="xno">verb</span> <span class="pzg"><span class="rlx">(</span>plural <span class="iko">grelts</span> <span class="p2h">/ɡrɛlts/</span><span class="rlx">)</span></span></span>
 <em class="tb0"><span class="rlx">[</span>with object<span class="rlx">]</span></em>
 <div class="se2"><div class="u2n"><div class="ysl"><a id="grelt__2"></a><span class="vkq">1</span>
  <span class="cvq">chiefly</span> <em class="u0f">British</em> <i class="rnr">informal</i>
  <span class="aw5">Fold (a <a href="entry://map">map</a>) badly:</span><div class="cn_def"><span class="cn_def_text">乱折</span>折皱</div>
  <span class="xxn"><em class="xv4">he grelted the map</em></span><p class="cn">他把地图折坏了。</p>
  <span onclick="o0e.mg(this)" class="x3z"></span><div class="ld9"><ul class="dhk"><li class="lmn">Maps get grelted in &lt;i&gt;The Grelt Book&lt;/i&gt; too.</li></ul></div>
  <span onclick="o0e.mg(this)" class="sdh"></span><div class="pzw"><div><a href="entry://crumple"><b>NOT A SYNONYM SENSE</b></a></div></div>
  <ul class="s6x"><li>NOT A DEFINITION: taxonomy.</li></ul>
 </div></div>
 <div class="ewq"><div class="ysl"><a id="grelt__3"></a><span class="vkq">1.1</span> <em class="u0f">Heraldry</em>
  <span class="aw5">Fold into a shield shape.</span></div></div></div>
 <div class="dzg"><div class="ysl"><p>NOT A SENSE: an encyclopedic note.</p></div></div>
</div>
<div class="k0z"><span class="nvt"><span class="xno">noun</span></span>
 <div class="ulk"><div class="ysl"><a id="grelt__9"></a><span class="aw5">A badly folded map.</span></div></div></div>
</div></div>
<div class="s0c"><h2><span class="tki">Phrases</span></h2><div class="dwy"><p><a href="entry://grelt%20it">grelt it</a></p></div></div>
<div class="f0t"><h2><span class="tki">Derivatives</span></h2><div class="dwy">
 <div class="b6i"><a id="grelt__19"></a><div class="ysl"><h4>grelter</h4></div> <span class="pxt">/ˈɡrɛltə/</span> <span class="xno">noun</span>
  <span onclick="o0e.mg(this)" class="x3z"></span><ul class="rpz"><li class="lmn">The grelter struck again.</li></ul></div></div></div>
<div class="e8l"><h2><span class="tki">Origin</span></h2><div class="ysl"><p><span class="q5j">Invented</span>: from <em>grel</em>.</p>
 <ul class="dhk"><li><p class="p9h">NOT ETYMOLOGY: a long word story.</p></li></ul></div></div>
<div class="m7g"><h2><span class="tki">Rhymes</span></h2><div class="ysl"><a href="entry://pelt">pelt</a></div></div>
<div class="uxu"><h2><span class="tki">Usage</span></h2><div class="ysl"><p>NOT A NOTE SENSE.</p></div></div>
</div>
<div class="k0i"><div class="h1s"><h2 class="z2h">grelt<span class="lx6">2</span></h2>
 <span class="pxt">/ɡrɛlt <img src="pr.png" onclick="o0e.a(this,0,'g/gre/grelt/grelt__us_1')" class="a8e">/</span></div>
 <div><div><div class="k0z"><span class="nvt"><span class="xno">adjective</span></span>
  <div class="ulk"><div class="ysl"><span class="aw5">Slightly creased.</span></div></div></div></div></div></div>
</div>"""

PHRASE_ENTRY = """<div class="Od3"><div class="k0i"><div class="h1s"><h2 class="z2h">grelt the lot</h2></div>
<div><div><div class="k0z"><div class="ulk"><div class="ysl"><span class="aw5">Fail completely:</span><div class="cn_def">彻底失败</div>
<span class="xxn"><em class="xv4">we grelted the lot</em></span><p class="cn">我们全搞砸了。</p></div></div></div></div></div>
<div class="n3h"><span class="aw5">See parent entry: <a class="cw6" href="entry://grelt">grelt</a></span></div></div></div>"""

POINTER_STUB = """<div class="Od3"><div class="b6i"><a id="grelt__26"></a> <div class="ysl"><h4>grelt away</h4></div>
<div class="ysl"><span class="aw5">see <a class="cw6" href="entry://away">away</a>.</span></div></div>
<span class="mbw">See parent entry: <a href="entry://grelt">grelt</a></span></div>"""


class OdeParser(unittest.TestCase):
    def setUp(self):
        self.e = ode.parse("grelt", HTML)

    def of(self, kind):
        return [s for s in self.e.senses if s.kind == kind]

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, ode.COVERS))

    def test_headword_homographs_pos(self):
        # two homographs share the entry, so no single homograph number applies
        self.assertEqual((self.e.headword, self.e.homograph), ("grelt", ""))
        self.assertEqual(self.e.pos, ("verb", "noun", "adjective"))

    def test_prons_take_the_played_file_and_region_from_the_onclick_handler(self):
        # onclick path "g/gre/grelt/grelt__gb_1" is played from the .mdd file "mp3/grelt_gb_1.mp3"
        self.assertEqual([(p.region, p.ipa, p.audio) for p in self.e.prons],
                         [("uk", "ɡrɛlt", "mp3/grelt_gb_1.mp3"), ("us", "ɡrɛlt", "mp3/grelt_us_1.mp3")])

    def test_forms_are_variants_and_plurals(self):
        self.assertEqual(self.e.forms, ("grelte", "grelts"))

    def test_numbered_sense_with_labels_bilingual_definition_and_examples(self):
        s1 = self.of("sense")[0]
        self.assertEqual((s1.pos, s1.number, s1.labels),
                         ("verb", "1", ("with object", "chiefly British", "informal")))
        self.assertEqual((s1.definition, s1.definition_zh), ("Fold (a map) badly", "乱折 折皱"))
        self.assertEqual([(x.text, x.text_zh) for x in s1.examples],
                         [("he grelted the map", "他把地图折坏了。"), ("Maps get grelted in The Grelt Book too.", "")])

    def test_subsense_and_unnumbered_sense(self):
        sub, noun, adj = self.of("sense")[1:]
        self.assertEqual((sub.number, sub.labels, sub.definition), ("1.1", ("with object", "Heraldry"), "Fold into a shield shape."))
        self.assertEqual((noun.pos, noun.number, noun.definition), ("noun", "", "A badly folded map."))
        self.assertEqual(adj.pos, "adjective")

    def test_boxes_do_not_leak(self):
        flat = repr(self.e.senses) + self.e.etymology
        for leaked in ("NOT A SYNONYM", "NOT A DEFINITION", "NOT A SENSE", "NOT ETYMOLOGY", "NOT A NOTE", "pelt", "grelt it"):
            self.assertNotIn(leaked, flat)
        self.assertEqual(len(self.of("sense")), 4)

    def test_derivative_with_examples(self):
        (dr,) = self.of("derivative")
        self.assertEqual((dr.phrase, dr.pos, dr.definition, [x.text for x in dr.examples]),
                         ("grelter", "noun", "", ["The grelter struck again."]))

    def test_etymology_is_the_origin_paragraph_only(self):
        self.assertEqual(self.e.etymology, "Invented: from grel.")

    def test_phrase_entry_senses_are_ordinary_senses(self):
        e = ode.parse("grelt the lot", PHRASE_ENTRY)
        self.assertEqual(problems(e), [])
        self.assertEqual([(s.kind, s.definition, s.definition_zh, s.examples[0].text_zh) for s in e.senses],
                         [("sense", "Fail completely", "彻底失败", "我们全搞砸了。")])

    def test_see_alone_is_a_definition_and_headword_alternatives_are_not_forms(self):
        html = PHRASE_ENTRY.replace('grelt the lot</h2>', 'grelt <span class="rqo">(or <span class="l6p">fold</span>)</span> the lot</h2>')
        html = html.replace('<span class="aw5">Fail completely:</span>', '<span class="aw5">See:</span>')
        e = ode.parse("grelt the lot", html)
        self.assertEqual((e.headword, e.forms, e.senses[0].definition), ("grelt (or fold) the lot", (), "See"))

    def test_only_escaped_formatting_tags_are_removed(self):
        html = PHRASE_ENTRY.replace("we grelted the lot", "fold it &lt;EM&gt;now&lt;/EM&gt;: turn &lt; &gt; and &lt;(em&gt;")
        e = ode.parse("grelt the lot", html)
        self.assertEqual((problems(e), e.senses[0].examples[0].text), ([], "fold it now: turn < > and <(em>"))

    def test_see_pointer_stub_is_uncovered(self):
        e = ode.parse("grelt away", POINTER_STUB)
        self.assertEqual((e.headword, e.senses, e.stub, problems(e)), ("grelt away", (), "xref", []))
        self.assertEqual(self.e.stub, "")
        self.assertFalse(covered(e, ode.COVERS))

    def test_see_also_pointer_is_a_pointer_too(self):
        e = ode.parse("grelt away", POINTER_STUB.replace(">see <a", ">see also <a"))
        self.assertEqual((e.senses, e.stub, problems(e)), ((), "xref", []))

    def test_derivative_labels_follow_its_headword_wrapper(self):
        # "(chiefly Law)" is printed after div.ysl > h4, the derivative's own headword
        labelled = ('<span class="xno">noun</span> (<span class="cvq">chiefly</span> <em class="u0f">Heraldry</em> ) '
                    '<i class="rnr">informal</i>')
        e = ode.parse("grelt", HTML.replace('<span class="xno">noun</span>\n  <span onclick', labelled + '\n  <span onclick'))
        (dr,) = [s for s in e.senses if s.kind == "derivative"]
        self.assertEqual((dr.phrase, dr.pos, dr.labels), ("grelter", "noun", ("chiefly Heraldry", "informal")))
        # a derivative that carries definitions: each of its senses inherits those labels
        defined = labelled + '<div class="ysl"><em class="tb0">[count noun]</em><span class="aw5">One who grelts.</span></div>'
        e = ode.parse("grelt", HTML.replace('<span class="xno">noun</span>\n  <span onclick', defined + '\n  <span onclick'))
        (dr,) = [s for s in e.senses if s.kind == "derivative"]
        self.assertEqual((dr.definition, dr.labels), ("One who grelts.", ("chiefly Heraldry", "informal", "count noun")))
        self.assertEqual(problems(e), [])

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", '<div class="k0i"><div class="k0z"><div class="ulk"><div class="ysl">',
                     "<<<>>>", '<div class="Od3"><div class="b6i"><div class="ysl"><h4>']:
            self.assertEqual(problems(ode.parse("x", junk)), [])
        self.assertEqual(ode.parse("x", "").headword, "x")


if __name__ == "__main__":
    unittest.main()
