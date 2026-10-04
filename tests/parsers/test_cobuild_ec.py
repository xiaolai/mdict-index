"""COBUILD English-Chinese parser on a synthetic entry that mirrors its markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import cobuild_ec

HTML = """
<font size="+1" color="purple">florp</font><font color="gold">★★☆☆☆</font>
<link href="collins.css" rel="stylesheet" type="text/css">
<div class="tab_content" id="dict_tab_101" style="display:block">
<div class="part_list"><ul><li>1. NOUN USES 名词用法</li></ul></div>
<div class="part_main"><h3 class="close menu_switch" id="h3_1">NOUN USES</h3><div class="collins_content" id="menu_1">
 <div class="collins_en_cn"><div class="caption"><span class="num">1.</span><span class="st" tid="1_1">N-COUNT\t可数名词</span><span class="text_blue">小木勺</span>
   A <b>florp</b> is a small   wooden spoon. <span><div id="word_gram_1_1"><div><div><br>【搭配模式】：oft N <l>of</l> n</div>
   <div><br>【STYLE标签】：INFORMAL 非正式</div></div></div></span></div>
  <ul><li><p>She stirred the tea with a <span class="text_blue">florp</span>...</p><p>她用小木勺搅茶。</p></li>
   <li class="en_tip"><b>Florp</b> is also a verb.<span class="text_blue"></span>
    <ul class="vli"><li><p>He <span class="text_blue">florp</span>ed the soup.</p><p>他搅了汤。</p></li></ul></li></ul></div>
 <div class="collins_en_cn"><div class="caption"><span class="num">2.</span><span class="st" tid="2_1">PHRASE 短语</span><span class="text_blue">白费力气</span>
   If you <b>florp the pot</b>, you work for nothing.</div><ul></ul></div>
 <div class="collins_en_cn"><div class="caption"><span class="num">3.</span><span class="st" tid="3_1">PHRASAL VERB 短语动词</span>
   <span class="st">See also:</span><b class="text_blue"><a class="explain" href="entry://florp-up">florp-up</a></b>;
   <span class="text_blue">搅起</span>If you <b>florp</b> something <b>up</b>, you stir it hard.</div><ul></ul></div>
 <div class="collins_en_cn"><div class="caption"><span class="num">4.</span><span class="text_blue"></span>
   <span class="text_gray">→see:</span><b class="text_blue"><a class="explain" href="entry://water">water</a></b>;</div><ul></ul></div>
 <div class="collins_en_cn"><div class="caption"><dl><dt>相关词组：</dt><dd><a class="explain" href="entry://florp up">florp up</a></dd></dl></div></div>
 <div class="vExplain_r"><b class="text_blue">florpish</b>
  <ul><li><p>A <span class="text_blue">florp</span>ish grin.</p><p>一个傻笑。</p></li></ul></div>
 <div class="vExplain_s">in AM, use 美国英语用 REGIONAL NOTE</div>
 <div class="vEn_tip"><strong class="text_gray">Usage Note</strong>:<p>USAGE NOTE TEXT</p><p>用法说明</p></div>
</div></div></div>"""


class CobuildEcParser(unittest.TestCase):
    def setUp(self):
        self.e = cobuild_ec.parse("florp", HTML)

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, cobuild_ec.COVERS))

    def test_headword_and_english_pos(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.prons), ("florp", "", ()))
        self.assertEqual(self.e.pos, ("N-COUNT", "PHRASAL VERB"))

    def test_sense_splits_english_and_chinese_and_reads_labels(self):
        s = self.e.senses[0]
        self.assertEqual((s.kind, s.number, s.pos), ("sense", "1", "N-COUNT"))
        self.assertEqual((s.definition, s.definition_zh), ("A florp is a small wooden spoon.", "小木勺"))
        self.assertEqual(s.labels, ("oft N of n", "INFORMAL"))
        self.assertEqual([(x.text, x.text_zh) for x in s.examples], [("She stirred the tea with a florp...", "她用小木勺搅茶。")])

    def test_en_tip_is_its_own_sense(self):
        s = self.e.senses[1]
        self.assertEqual((s.definition, [(x.text, x.text_zh) for x in s.examples]),
                         ("Florp is also a verb.", [("He florped the soup.", "他搅了汤。")]))

    def test_phrase_and_phrasal_verb_without_the_see_also_link(self):
        phrase, phrasal = self.e.senses[2], self.e.senses[3]
        self.assertEqual((phrase.kind, phrase.phrase, phrase.definition_zh), ("phrase", "florp the pot", "白费力气"))
        self.assertEqual((phrasal.kind, phrasal.phrase, phrasal.definition, phrasal.definition_zh),
                         ("phrasal_verb", "florp … up", "If you florp something up, you stir it hard.", "搅起"))

    @staticmethod
    def _caption(inner: str, st: str = "PHRASE\t短语") -> str:
        return ('<font size="+1">florp</font><div class="tab_content"><div class="part_main"><div class="collins_content">'
                f'<div class="collins_en_cn"><div class="caption"><span class="num">1.</span><span class="st">{st}</span>'
                f'<span class="text_blue">搅</span> {inner}</div><ul></ul></div></div></div></div>')

    def test_alternative_phrases_are_kept_apart(self):
        (s,) = cobuild_ec.parse("florp", self._caption(
            "If you say a thing is true <b>by all florps</b> or <b>from all florps</b>, you believe it.")).senses
        self.assertEqual((s.kind, s.phrase), ("phrase", "by all florps | from all florps"))
        (s,) = cobuild_ec.parse("florp", self._caption(
            "If you <b>florp up</b>, or if a thing <b>florps</b> you <b>up</b>, you rise.", "PHRASAL VERB\t短语动词")).senses
        self.assertEqual(s.phrase, "florp up")

    def test_a_pointer_takes_its_phrase_and_separator_with_it(self):
        (s,) = cobuild_ec.parse("florp", self._caption(
            'When a thing happens <b>florp</b> a wall, it is wide. <b>florp the board</b>'
            '<span class="text_gray" style="font-weight:bold;">→see: </span>'
            '<b class="text_blue"><a class="explain" href="entry://board">board</a></b>; ', "PREP\t介词")).senses
        self.assertEqual(s.definition, "When a thing happens florp a wall, it is wide.")

    def test_a_usage_note_pointer_keeps_the_definition_before_it(self):
        (s,) = cobuild_ec.parse("florp", self._caption(
            '<b>Florp</b> is a scale. It is shown by the symbol <span class="text_gray">→see usage note at:</span>'
            '<b class="text_blue"><a class="explain" href="entry://heat">heat</a></b>', "ADJ\t形容词")).senses
        self.assertEqual(s.definition, "Florp is a scale. It is shown by the symbol")

    def test_alternatives_share_the_words_around_the_part_that_varies(self):
        (s,) = cobuild_ec.parse("florp", self._caption(
            "If you <b>put</b> ,<b>bring</b>, or <b>carry</b> a plan or idea <b>into florp</b>, it happens.")).senses
        self.assertEqual(s.phrase, "put … into florp | bring … into florp | carry … into florp")
        (s,) = cobuild_ec.parse("florp", self._caption(
            "If something <b>florps</b> or <b>puts the seal on</b> something, it is sure.")).senses
        self.assertEqual(s.phrase, "florps the seal on | puts the seal on")

    def test_a_see_pointer_takes_the_whole_phrase_printed_since_the_last_boundary(self):
        (s,) = cobuild_ec.parse("florp", self._caption(
            'If you <b>florp yourself for</b> a fight, you prepare for it. to <b>florp</b> your <b>loins</b>'
            '<span class="text_gray" style="font-weight:bold;">→see: </span>'
            '<b class="text_blue"><a class="explain" href="entry://loin">loin</a></b>; ', "VERB\t动词")).senses
        self.assertEqual(s.definition, "If you florp yourself for a fight, you prepare for it.")
        (s,) = cobuild_ec.parse("florp", self._caption(
            'If something <b>florps out</b>, it is noticeable. to <b>florp out a mile</b><span class="text_gray">→see: </span>'
            '<b class="text_blue"><a class="explain" href="entry://mile">mile</a></b>; to florp out like a very sore green '
            'thumb<span class="text_gray">→see: </span><b class="text_blue"><a class="explain" href="entry://thumb">thumb</a>'
            '</b>; ', "PHRASAL VERB\t短语动词")).senses
        self.assertEqual((s.phrase, s.definition), ("florps out", "If something florps out, it is noticeable."))

    def test_a_comma_inside_one_printed_phrase_does_not_split_it(self):
        (s,) = cobuild_ec.parse("florp", self._caption(
            "If you call a thing <b>all-florping</b> ,<b>all-dancing</b>, you mean it is modern.")).senses
        self.assertEqual(s.phrase, "all-florping all-dancing")

    def test_derivative(self):
        drv = self.e.senses[4]
        self.assertEqual((drv.kind, drv.phrase, drv.examples[0].text, drv.examples[0].text_zh),
                         ("derivative", "florpish", "A florpish grin.", "一个傻笑。"))

    def test_cross_references_and_side_boxes_are_left_out(self):
        self.assertEqual(len(self.e.senses), 5)
        blob = repr(self.e)
        for leaked in ("water", "REGIONAL NOTE", "USAGE NOTE", "相关词组", "★"):
            self.assertNotIn(leaked, blob)

    def test_stubs(self):
        self.assertEqual(self.e.stub, "")
        self.assertEqual(cobuild_ec.parse("florpy", '<font size="+1" color="purple">florpy</font>').stub, "empty")
        xref = """<font size="+1">florped</font><div class="tab_content"><div class="part_main"><div class="collins_content">
        <div class="collins_en_cn"><div class="caption"><span class="num">1.</span><span class="text_blue"></span>
        <span class="text_gray">→see:</span><b class="text_blue"><a class="explain" href="entry://florp">florp</a></b>;</div><ul></ul></div>
        </div></div></div>"""
        self.assertEqual(cobuild_ec.parse("florped", xref).stub, "xref")

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", "<div class='collins_content'><div class='collins_en_cn'><div class='caption'>", "<<<>>>"]:
            e = cobuild_ec.parse("x", junk)
            self.assertEqual((e.headword, problems(e)), ("x", []))


if __name__ == "__main__":
    unittest.main()
