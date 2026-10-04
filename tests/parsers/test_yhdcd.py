"""英汉大词典 parser on synthetic entries that mirror the source markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import yhdcd

# Unclosed custom tags (<tr>, <j>, <kg>, <xh>) are reproduced on purpose: the source leaves them open.
HTML = """<link rel="stylesheet" type="text/css" href="ECD.css"/><def><a name="Z_top"></a>
<span class="hw">grel<fgf>·</fgf>tive²<hw></span><span class="tr"> /ˈɡrel<i>ə</i>tɪv/<tr></span>
<span class=Z_POS_G> <a href="entry://#vt." class=Z_REF>vt.</a Z_REF><span class=Z_Z> | </span Z_Z><a href="entry://#n." class=Z_REF>n.</a Z_REF></span Z_POS_G>
<hr class=hr><ii><span class="xhb">I <xhb></span><span class="smb">(grelt<span class="yb">/ɡrelt/<yb></span>, grel<fgf>·</fgf>ting) <smb></span><br>
<span class="xha">❶ <xha></span><span class="tz"><span class="cx">vt. <cx></span><tz></span></ii><br>
<span class="xh">1. <xh></span>折叠<span class="smb">(地图等)<smb></span>：<br>
<span class="ea">She <tdd>grelt</tdd>s the chart.<ea></span><span class="eb">  她把海图折好。<eb></span><br><span class="ea">grelt a sail<ea></span><span class="eb">  收帆 <eb></span><br>
<span class="xh">2. <xh></span><span class="lyb"><lbl>〈</lbl>口<lbr>〉</lbr><lyb></span><span class="lya"><lal>【</lal>海<lar>】</lar><lya></span>犹豫不决 <br>
<span class="xh">3. <xh></span><span class="sma">[用作加强语气]<sma></span><br>
<span class="ea">Grelt and go!<ea></span><span class="eb">  快走吧！<eb></span><br>
<hr class=hr><ii><span class="xhb">II <xhb></span><span class="yb">/ˈɡreltɪf/ <yb></span><br><span class="tz"><span class="cx">n.<cx></span><tz></span></ii><br>
<span class="lya"><lal>【</lal>植<lar>】</lar><lya></span>一种虚构的草<br>
<div class=zqq><span class="zj">◇注解<zj></span>
<span class="zjq">此条为测试而编造 <zjq></span><zqq></div>
<span class="sma"><ciy>[&lt; invented &lt; nothing]</ciy><sma></span>
<div class=ref><a name="phr."></a> <span class="tz"><span class="cxb">phr. <cxb></span><tz></span><span class="ph"><tdd>grelt</tdd> out <ph></span>
<span class="lyb"><lbl>〈</lbl>俚<lbr>〉</lbr><lyb></span><br><span class="xh">1. <xh></span>逃走<br>
<span class="ec">They <tdd>grelt</tdd> out at dawn.<ec></span><span class="ed"> 他们黎明时逃走了。<ed></span><br>
<span class="xh">2. <xh></span>失败<br>
<span class="ph"><tdd>grelt</tdd> the lot <ph></span>
<j>见 <a href="entry://lot">lot</a><kg><br>
<span class="ph">grelt away <ph></span>
浪费<br>
</div></def>"""


class YhdcdParser(unittest.TestCase):
    def setUp(self):
        self.e = yhdcd.parse("greltive²", HTML)
        self.senses = [s for s in self.e.senses if s.kind == "sense"]
        self.phrases = [s for s in self.e.senses if s.kind == "phrase"]

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, yhdcd.COVERS))

    def test_headword_homograph_pos_forms(self):
        self.assertEqual((self.e.headword, self.e.homograph), ("greltive", "2"))
        self.assertEqual(self.e.pos, ("vt.", "n."))
        self.assertEqual(self.e.forms, ("grelt", "grelting"))

    def test_prons_include_the_pos_group_pronunciation(self):
        self.assertEqual([(p.ipa, p.region, p.audio) for p in self.e.prons],
                         [("ˈɡrelətɪv", "", ""), ("ˈɡreltɪf", "", "")])

    def test_numbered_senses_with_examples(self):
        s1, s2, s3, s4 = self.senses
        self.assertEqual((s1.pos, s1.number, s1.definition_zh, s1.definition), ("vt.", "1", "折叠(地图等)", ""))
        self.assertEqual([(x.text, x.text_zh) for x in s1.examples],
                         [("She grelts the chart.", "她把海图折好。"), ("grelt a sail", "收帆")])
        self.assertEqual((s2.labels, s2.definition_zh), (("口", "海"), "犹豫不决"))
        self.assertEqual((s4.pos, s4.number, s4.labels, s4.definition_zh), ("n.", "", ("植",), "一种虚构的草"))

    def test_bracketed_note_is_the_gloss_when_nothing_else_is(self):
        s3 = self.senses[2]
        self.assertEqual((s3.labels, s3.definition_zh, s3.examples[0].text_zh), ((), "用作加强语气", "快走吧！"))

    def _one(self, body: str):
        return yhdcd.parse("grelt", '<def><span class="hw">grelt<hw></span><br>' + body + "</def>").senses

    def test_space_between_inline_elements_is_kept(self):
        (s,) = self._one("<b>fold</b> <i>twice</i> <b>over</b><br>")
        self.assertEqual(s.definition, "fold twice over")
        self.assertEqual(self._one(" <br> \n <br>"), ())  # white space alone is never a sense

    def test_definition_continued_on_the_next_line_keeps_a_space(self):
        (s,) = self._one("fold twice<br>over again<br>")
        self.assertEqual(s.definition, "fold twice over again")

    def test_last_numbered_sense_with_only_a_bracketed_gloss_on_the_next_line(self):
        senses = self._one('<span class="xh">1. <xh></span>折叠<br><span class="xh">2. <xh></span><br>'
                           '<span class="sma">[用作加强语气]<sma></span>')
        self.assertEqual([(s.number, s.labels, s.definition_zh) for s in senses],
                         [("1", (), "折叠"), ("2", (), "用作加强语气")])

    def test_phrases_carry_line_labels_and_skip_cross_references(self):
        self.assertEqual([(p.phrase, p.number, p.labels, p.definition_zh) for p in self.phrases],
                         [("grelt out", "1", ("俚",), "逃走"), ("grelt out", "2", ("俚",), "失败"),
                          ("grelt away", "", (), "浪费")])
        self.assertEqual(self.phrases[0].examples[0].text, "They grelt out at dawn.")

    def test_note_box_and_etymology_stay_out_of_senses(self):
        notes = [s for s in self.e.senses if s.kind == "note"]
        self.assertEqual([n.definition_zh for n in notes], ["此条为测试而编造"])
        self.assertEqual(self.e.etymology, "< invented < nothing")
        texts = " ".join(s.definition_zh + " ".join(x.text for x in s.examples) for s in self.senses + self.phrases)
        self.assertNotIn("测试", texts)
        self.assertNotIn("invented", texts)

    def test_highlighter_residue_is_undone_and_a_residue_br_breaks_the_line(self):
        # the source's highlighter wraps its own tag names when they equal the headword
        e = yhdcd.parse("BX", '<def><span class="hw">BX<hw></span><<tdb>br</tdb>>'
                              '<span class="xh">1. <xh></span>box <<tdb>br</tdb>><span class="xh">2. <xh></span>箱子</def>')
        self.assertEqual([(s.definition, s.definition_zh) for s in e.senses], [("box", ""), ("", "箱子")])
        e = yhdcd.parse("II", '<def><span class="hw">II<hw></span><br>\n<<tdb>ii</tdb>><span class="tz">'
                              '<span class="cx">abbr.<cx></span><tz></span></<tdb>ii</tdb>><br>\ninvented idea 虚构的想法<hh></def>')
        self.assertEqual([s.definition_zh for s in e.senses], ["invented idea 虚构的想法"])
        self.assertEqual(problems(e), [])

    def test_a_less_than_in_an_etymology_stays_as_printed(self):
        e = yhdcd.parse("grelt", '<def><span class="hw">grelt<hw></span><br>折叠<br>'
                                 '<span class="sma"><ciy>[&lt;Invented grelta &lt;Made up&gt;]</ciy><sma></span></def>')
        self.assertEqual((e.etymology, problems(e)), ("<Invented grelta <Made up>", []))

    def test_private_use_glyph_is_a_chinese_definition(self):
        # the new element names are set in a private-use glyph of the dictionary's font
        e = yhdcd.parse("greltium", '<def><span class="hw">grel<fgf>·</fgf>tium<hw></span><span class="tr"> /ˈɡreltɪəm/<tr></span><br>'
                                    '<ii><span class="tz"><span class="cx">n.<cx></span><tz></span></ii><br>'
                                    '<span class="lya"><lal>【</lal>化<lar>】</lar><lya></span>\ue689<hh></def>')
        self.assertEqual([(s.labels, s.definition_zh) for s in e.senses], [(("化",), "\ue689")])
        self.assertEqual((e.stub, problems(e)), ("", []))

    def test_usage_gloss_in_an_etymology_bracket_is_a_gloss(self):
        e = yhdcd.parse("grelt me", '<def><span class="hw">grelt me<hw></span><br><span class="lyb"><lbl>〈</lbl>旧<lbr>〉'
                                    '</lbr><lyb></span><br><span class="sma"><ciy>[用于虚构的礼貌请求] </ciy><sma></span><hh></def>')
        self.assertEqual([(s.labels, s.definition_zh) for s in e.senses], [(("旧",), "用于虚构的礼貌请求")])
        self.assertEqual((e.etymology, e.stub), ("", ""))

    def test_note_text_in_the_title_span(self):
        e = yhdcd.parse("grelt us", '<def><span class="hw">grelt us<hw></span><br><j>见 <a href="entry://grelt">grelt</a><br>'
                                    '<div class=zqq><span class="zj">◇虚构的用法说明<zj></span><zqq></div></def>')
        self.assertEqual([(s.kind, s.definition_zh) for s in e.senses], [("note", "虚构的用法说明")])
        self.assertEqual(e.stub, "")

    def test_stub_reasons_come_from_markup(self):
        derivative = yhdcd.parse("greltively", '<def><span class="hw">grel<fgf>·</fgf>tive<fgf>·</fgf>ly<hw></span><br>'
                                               '<ii><span class="tz"><span class="cx">n. <cx></span>, <span class="cx">ad.<cx></span>'
                                               '<tz></span></ii><hh>\n<hh>\n</def>')
        ipa_only = yhdcd.parse("Greltian", '<def><span class="hw">Grel<fgf>·</fgf>tian<hw></span>'
                                           '<span class="tr"> /ˈɡrelʃən/<tr></span>\n<hh>\n</def>')
        xref = yhdcd.parse("grelt it", '<def><span class="hw">grelt it<hw></span><br><span class="lyb"><lbl>〈</lbl>口'
                                       '<lbr>〉</lbr><lyb></span><j>见 <a href="entry://grelt">grelt</a><kg><hh></def>')
        empty = yhdcd.parse("grelt maker", '<def><span class="hw">grelt maker<hw></span>\n<hh>\n</def>')
        etymology_only = yhdcd.parse("grelter", '<def><span class="hw">grelter<hw></span><br>'
                                                '<span class="sma"><ciy>[invented origin]</ciy><sma></span></def>')
        for e, reason in ((derivative, "derivative"), (ipa_only, "derivative"), (xref, "xref"), (empty, "empty"),
                          (etymology_only, "")):
            self.assertEqual((e.stub, e.senses, problems(e)), (reason, (), []))
            self.assertFalse(covered(e, yhdcd.COVERS))
        self.assertEqual((derivative.headword, derivative.pos), ("greltively", ("n.", "ad.")))
        self.assertEqual(self.e.stub, "")

    def test_garbage_never_raises(self):
        deep = "<def>" + "<j>x" * 3000 + "</def>"
        for junk in ["", "<", "<def><span class='xh'>", "plain text", "<<<>>>", "<ii><ii><span class=\"cx\">", deep]:
            e = yhdcd.parse("x", junk)
            self.assertEqual(e.headword, "x")
            self.assertEqual(problems(e), [])


if __name__ == "__main__":
    unittest.main()
