"""新世纪英汉大词典 (Hujiang build) parser on synthetic entries mirroring both renderings (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import ncecd

_TABS = """<head><meta charset="utf-8"><link rel="stylesheet" type="text/css" href="dicts_combiner_my_dict22.css">
<script src="dicts_combiner_my_dict22.js"></script></head><div class="javascript_tittle_box">
<div class="each_tittle_first each_tittle_smgs" onclick="js_display(this,0)">沪江小d新世纪英汉</div>
<div class="each_tittle_last each_tittle_smgs" onclick="js_display(this,1)">新世纪英汉</div></div>
<hr class="hr_after_tittle_box">"""

HUJIANG = """<div class="dict_content_display dict_content_display_1" style="display:block">
<link rel="stylesheet" type="text/css" href="hjxsjyh.css"><head11>grelt</head11>
<div ,="" class="word-details-pane-content" data-word="grelt">
<div class="word-details-item detail" data-id="detail"><h2>详细释义</h2><div class="word-details-item-content">
<section class="detail-groups"><dl><dt> vt. <span class="detail-pron">/ɡrelt/</span></dt>
<dd><h3></h3><p>折叠（地图）</p><ul><li>
<p class="def-sentence-from"> She grelts maps.  <a href="sound://ABC.mp3"> <audio-liju> 🔊</audio-liju></a></p>
<p class="def-sentence-to"> 她折地图。</p></li></ul></dd></dl></section></div></div>
<div class="word-details-item phrase" data-id="phrase"><h2>常用短语</h2><div class="word-details-item-content">
<ol class="phrase-items"><li><span>grelt up</span><span class="phrase-def">折好</span></li></ol></div></div>
<div class="word-details-item enen" data-id="enen"><h2>英英释义</h2><div class="word-details-item-content">
<div class="enen-groups"><dl><dt>v.</dt><dd>fold a map the wrong way</dd></dl></div></div></div>
<div class="word-details-item synant" data-id="synant"><h2>同反义词</h2><div class="word-details-item-content synant-content">
<div class="syn"><p>同义词：</p><table><tbody><tr><td><a href="entry://crumple">crumple</a></td></tr></tbody></table></div></div></div>
<div class="word-details-item inflections" data-id="inflections"><h2>词形变化</h2><div class="word-details-item-content">
<ul class="inflections-items"><li><span class="inflections-item-attr">动词过去式: </span><a href="entry://grelted">grelted</a></li>
<li><span class="inflections-item-attr">名词: </span><a href="entry://grelter">grelter</a></li></ul></div></div>
</div></div>"""

ORIGINAL = """<div class="dict_content_display dict_content_display_2" style="display:none">
<style type="text/css"></style><link href="ncecd.css" rel="stylesheet"/>
<span class="header">grelt¹</span><span class="ncecd_con"><pron>/ɡrelt;<span class="sut">sometimes</span>ɡrɛlt/</pron>
<span class="tense">(<span class="tensexxx"><b>grelts</b>,<b>grelting</b>,<b>grelted</b></span>)</span>
<div class="class_box"><span class="abc">🄰</span><span class="class">vt.</span></div>
<div class="sense"><b class="num">1.</b><span class="label">&lt;英,非正式&gt;</span><strong class="brief_ex">(fold badly)</strong><span class="collocation">[+ map, chart]</span><span class="zh">乱折；</span><span class="zh">折坏</span></div>
<p class="ex">He grelted the chart.<span class="zh">他把海图折坏了。</span></p>
<div class="maybe_phrase"><span class="mphr_en to">to grelt sth up<span class="or">or</span>to grelt sth over</span><span class="zh">把某物折起来</span></div>
<div class="sense"><b class="num">2.</b>to grelt sth into sth</div>
<div class="sense"><strong class="brief_ex">(shape)</strong><span class="zh">把…折成…</span></div>
<div class="sense"><strong class="brief_ex">(force)</strong><span class="zh">硬把…塞进…</span></div>
<div class="sense"><b class="num">3.</b>to grelt a mile<span class="also"><b>See</b><a href="entry://mile">mile¹</a></span></div>
<div class="idom"><span class="idom">idiom</span><div class="sense"><span class="dodo">◆</span>grelt and run<span class="label">【航海】</span><span class="zh">收帆就跑</span></div>
<p class="ex">They grelted and ran.<span class="zh">他们收帆就跑。</span></p></div>
<fieldset class="usage"><legend class="usage title">Usage Note</legend><div class="usagezh">此说明为测试编写。</div></fieldset>
<div class="phr"><b>Phrasal Verbs</b><a href="entry://grelt up">grelt up</a></div></span>
<hr class="hr_multi_keys"><span class="header">grelt²</span><span class="ncecd_con"><span class="class">n.</span>
<div class="also"><i>(informal)</i>=<a href="entry://greltage">greltage</a><span class="zh">折痕</span></div></span>
</div>"""

HTML = _TABS + '<div class="main_content_main">' + HUJIANG + ORIGINAL + "</div>"


class NcecdParser(unittest.TestCase):
    def setUp(self):
        self.e = ncecd.parse("grelt", HTML)
        self.zh_senses = [s for s in self.e.senses if s.definition_zh and s.kind != "note"]

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, ncecd.COVERS))

    def test_headword_homograph_pos_forms(self):
        # two homographs in one entry: no single homograph number
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelt", "", ("vt.", "n.")))
        self.assertEqual(self.e.forms, ("grelts", "grelting", "grelted"))  # "名词:" is a derived word, not a form

    def test_prons_from_the_original_rendering(self):
        self.assertEqual([(p.ipa, p.region, p.audio) for p in self.e.prons], [("ɡrelt; sometimes ɡrɛlt", "", "")])

    def test_numbered_sense_with_labels_examples_and_collocations(self):
        s1 = self.zh_senses[0]
        self.assertEqual((s1.kind, s1.pos, s1.number, s1.definition, s1.definition_zh),
                         ("sense", "vt.", "1", "fold badly", "乱折；折坏"))
        self.assertEqual(s1.labels, ("英", "非正式", "+ map, chart"))
        self.assertEqual([(x.kind, x.text, x.text_zh) for x in s1.examples],
                         [("example", "He grelted the chart.", "他把海图折坏了。"),
                          ("collocation", "to grelt sth up or to grelt sth over", "把某物折起来")])

    def test_pattern_heads_its_unnumbered_continuations(self):
        shaped, forced = self.zh_senses[1:3]
        for s in (shaped, forced):
            self.assertEqual((s.kind, s.number, s.phrase), ("phrase", "2", "to grelt sth into sth"))
        self.assertEqual((shaped.definition, forced.definition_zh), ("shape", "硬把…塞进…"))

    def test_cross_reference_sense_is_dropped_and_idiom_is_a_phrase(self):
        self.assertNotIn("to grelt a mile", [s.phrase for s in self.e.senses])
        (idiom,) = [s for s in self.e.senses if s.phrase == "grelt and run"]
        self.assertEqual((idiom.kind, idiom.number, idiom.labels, idiom.definition_zh, idiom.examples[0].text),
                         ("phrase", "", ("航海",), "收帆就跑", "They grelted and ran."))

    def test_equivalence_note_and_english_definitions(self):
        (note,) = [s for s in self.e.senses if s.kind == "note"]
        self.assertEqual(note.definition_zh, "此说明为测试编写。")
        noun = [s for s in self.e.senses if s.pos == "n."]
        self.assertEqual([(s.definition, s.definition_zh) for s in noun], [("(informal)=greltage", "折痕")])
        english = [s for s in self.e.senses if s.pos == "v."]
        self.assertEqual([(s.definition, s.definition_zh) for s in english], [("fold a map the wrong way", "")])

    def test_hujiang_duplicates_and_side_boxes_are_not_counted(self):
        texts = [s.definition_zh for s in self.e.senses] + [x.text for s in self.e.senses for x in s.examples]
        self.assertNotIn("折叠(地图)", " ".join(texts))  # the Hujiang copy of the definitions
        self.assertNotIn("She grelts maps.", texts)
        self.assertNotIn("grelt up", [s.phrase for s in self.e.senses])  # 常用短语 and phrasal-verb links
        self.assertNotIn("crumple", " ".join(texts))

    def test_hujiang_rendering_is_the_fallback(self):
        e = ncecd.parse("grelt", _TABS + '<div class="main_content_main">' + HUJIANG.replace("折叠（地图）", "折叠（地图）&lt;英&gt;【海】") + "</div>")
        self.assertEqual(problems(e), [])
        first, phrase = e.senses[0], [s for s in e.senses if s.kind == "phrase"][0]
        self.assertEqual((first.pos, first.labels, first.definition_zh), ("vt.", ("英", "海"), "折叠（地图）"))
        self.assertEqual([(x.text, x.text_zh) for x in first.examples], [("She grelts maps.", "她折地图。")])
        self.assertEqual((phrase.phrase, phrase.definition_zh), ("grelt up", "折好"))
        self.assertEqual([p.ipa for p in e.prons], ["ɡrelt"])
        self.assertEqual(e.forms, ("grelted",))

    def test_leading_phrase_and_unclosed_header(self):
        e = ncecd.parse("grelt out", '<div class="dict_content_display dict_content_display_2">'
                                     '<span class="header">grelt out<<span class="doble bigword">grelt-out</span>/h2>'
                                     '<span class="ncecd_con"><span class="class">n.</span><div class="maybe_phrase">'
                                     '<span class="mphr_en">the grelt out</span><span class="zh">大折叠</span></div></span></div>')
        self.assertEqual((e.headword, e.forms), ("grelt out", ("grelt-out",)))
        self.assertEqual([(s.kind, s.phrase, s.definition_zh) for s in e.senses], [("phrase", "the grelt out", "大折叠")])
        self.assertEqual(problems(e), [])

    def test_pattern_labels_move_off_the_text(self):
        e = ncecd.parse("grelt", '<div class="dict_content_display dict_content_display_2"><span class="header">grelt</span>'
                                 '<span class="ncecd_con"><span class="class">vt.</span><div class="sense"><span class="zh">折</span></div>'
                                 '<div class="maybe_phrase"><span class="mphr_en to">to grelt a chart</span>'
                                 '<span class="label">&lt;英,非正式&gt;</span><span class="zh">折海图</span></div></span></div>')
        (x,) = e.senses[0].examples
        self.assertEqual((x.kind, x.text, x.text_zh, x.labels), ("collocation", "to grelt a chart", "折海图", ("英", "非正式")))
        self.assertEqual(problems(e), [])

    def test_phrase_after_an_unglossed_sense_is_the_entry_gloss(self):
        e = ncecd.parse("greltinks", '<div class="dict_content_display dict_content_display_2"><span class="header">greltinks</span>'
                                     '<span class="ncecd_con"><span class="class">vt.</span><div class="sense">past tense greltought</div>'
                                     '<div class="maybe_phrase"><span class="mphr_en to">greltinks …</span>'
                                     '<span class="label">&lt;古&gt;</span><span class="zh">我折想…</span></div></span></div>')
        self.assertEqual([(s.kind, s.phrase, s.labels, s.definition_zh) for s in e.senses],
                         [("phrase", "greltinks …", ("古",), "我折想…")])
        self.assertTrue(covered(e, ncecd.COVERS))

    def test_escaped_markup_in_inflections_is_not_a_form(self):
        # the source escapes markup inside the 词形变化 links: an italic label before the form, a broken tag after it
        items = "".join(f'<li><span class="inflections-item-attr">时态: </span><a href="entry://x">{a}</a></li>'
                        for a in ("&lt;i&gt;tr.&lt;/i&gt; grelted", "grelting&lt;&gt;", "grelts&lt;&gt;/b"))
        e = ncecd.parse("grelt", '<div class="dict_content_display dict_content_display_1"><head11>grelt</head11>'
                                 '<div class="word-details-pane-content"><div class="word-details-item inflections">'
                                 f'<ul class="inflections-items">{items}</ul></div></div></div>')
        self.assertEqual(e.forms, ("grelted", "grelting", "grelts"))
        self.assertEqual(problems(e), [])

    def test_space_at_an_inline_boundary_separates_words(self):
        e = ncecd.parse("grelt", '<div class="dict_content_display dict_content_display_2"><span class="header">grelt</span>'
                                 '<span class="ncecd_con"><span class="class">vt.</span><div class="sense"><span class="zh">折</span></div>'
                                 '<div class="maybe_phrase"><span class="mphr_en"><span class="to"><i>to </i>grelt</span> sth</span>'
                                 '<span class="zh">折某物</span></div></span></div>')
        self.assertEqual([x.text for x in e.senses[0].examples], ["to grelt sth"])

    def test_pattern_after_a_label_or_gloss_stays_the_phrase(self):
        body = ('<span class="class">phr v</span>'
                '<div class="sense"><b class="num">1.</b><span class="label">【航海】</span>to grelt sth down</div>'
                '<div class="sense"><span class="collocation">[+ sail]</span><span class="zh">收折</span></div>'
                '<div class="sense"><b class="num">2.</b><strong class="brief_ex">(crush)</strong>to grelt sb down<span class="zh">压垮</span></div>'
                '<div class="sense"><b class="num">3.</b><strong class="brief_ex">(store)</strong>to grelt sth away</div>'
                '<div class="sense"><span class="collocation">[+ maps]</span><span class="zh">收好</span></div>'
                '<div class="sense"><b class="num">4.</b><span class="label">【测量】</span>=grelt line</div>'
                '<div class="sense"><b class="num">5.</b><strong class="brief_ex">(in Wales)</strong>=Grelt Office<span class="zh">折局</span></div>')
        e = ncecd.parse("grelt down", '<div class="dict_content_display dict_content_display_2"><span class="header">grelt down</span>'
                                      f'<span class="ncecd_con">{body}</span></div>')
        self.assertEqual([(s.kind, s.number, s.phrase, s.labels, s.definition, s.definition_zh) for s in e.senses], [
            ("phrase", "1", "to grelt sth down", ("航海", "+ sail"), "", "收折"),
            ("phrase", "2", "to grelt sb down", (), "crush", "压垮"),
            ("phrase", "3", "to grelt sth away", (), "store", ""),
            ("phrase", "3", "to grelt sth away", ("+ maps",), "", "收好"),
            ("sense", "4", "", ("测量",), "=grelt line", ""),
            ("sense", "5", "", (), "(in Wales) =Grelt Office", "折局"),
        ])
        self.assertEqual(problems(e), [])

    def test_homograph_before_a_comma(self):
        e = ncecd.parse("Grelt, Anna", '<div class="dict_content_display dict_content_display_2">'
                                       '<span class="header">Grelt¹, Anna</span><span class="ncecd_con"><span class="class">n.</span>'
                                       '<div class="sense"><span class="zh">格雷尔特(虚构人物)</span></div></span></div>')
        self.assertEqual((e.headword, e.homograph), ("Grelt, Anna", "1"))

    def test_stub_reasons_come_from_markup(self):
        pane2 = '<div class="dict_content_display dict_content_display_2"><span class="header">{0}</span><span class="ncecd_con">{1}</span></div>'
        pane1 = ('<div class="dict_content_display dict_content_display_1"><head11>greltbed</head11><div class="word-details-pane-content">'
                 '<div class="word-details-item inflections"><div class="word-details-item-content"><ul class="inflections-items">'
                 '<li><span class="inflections-item-attr">复数: </span><a href="entry://greltbeds">greltbeds</a></li></ul></div></div></div></div>')
        cases = [
            (pane2.format("Grelt", '<span class="class">n.</span><div class="sense">See Anna Grelt</div>'), "xref"),
            (pane2.format("greltish", '<pron>/ˈɡreltɪʃ/</pron><div class="phr"><b>Phrasal Verb</b><a href="entry://greltish up">greltish up</a></div>'), "xref"),
            (pane1, "inflection"),
            (pane2.format("Grelt-tung", '<pron>/ɡrelt/</pron><span class="class">n.</span><div class="label_box"><span class="label">&lt;过时&gt;</span></div>'), "empty"),
            (pane2.format("grelten", '<div class="sense"><a href="entry://grelt">grelt</a>的过去式</div>'), ""),
            (pane2.format("GRT", '<span class="class">abbr.</span><div class="also">=<a href="entry://grelt">grelt</a></div>'), ""),
            (pane2.format("grel-", '<span class="class">prefix</span><div class="also"><i><span class="etips">'
                                   '<span class="gramm tip">[用在元音前]</span></span></i>=<a href="entry://grelt-">grelt-</a></div>'), ""),
        ]
        for html, reason in cases:
            e = ncecd.parse("x", html)
            self.assertEqual((e.stub, problems(e)), (reason, []), html)
            self.assertEqual(covered(e, ncecd.COVERS), not reason, html)
        self.assertEqual(self.e.stub, "")

    def test_garbage_never_raises(self):
        for junk in ["", "<", "<div class='dict_content_display_2'><span class='header'>", "plain text", "<<<>>>",
                     "<div class='dict_content_display_2'><div class='sense'><b class='num'>1.</b>"]:
            e = ncecd.parse("x", junk)
            self.assertEqual(e.headword, "x")
            self.assertEqual(problems(e), [])


if __name__ == "__main__":
    unittest.main()
