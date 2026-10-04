"""Examples told from translated definitions by the style a dictionary prints them in."""
import unittest

from parallel.styled import candidates, learn, pairs, segments

# Layouts of the American Heritage English-Chinese editions, with invented text.
CLASSED = ('<ol><li><span class="x_define"><span class="en_define">To fix a fault for:</span>'
           '<span class="cn_define">替…修理：</span></span><span class="x_example">'
           '<span class="en_example">The piper answered with one more tune.</span>'
           '<span class="cn_example">风笛手又吹了一首曲子。</span></span></li></ol>')
COLOURED = ('<DIV style="MARGIN: 4px 0px">To fix a fault for:<DIV style="COLOR: #01259a">替…修理：</DIV>'
            '<DIV style="COLOR: #009999">The piper answered with one more tune.</DIV>'
            '<DIV style="COLOR: #01259a">风笛手又吹了一首曲子。</DIV></DIV>')
SAME_COLOUR = ('<ol class="L1"><li>To fix a fault for:<br>替…修理：<br>'
               '<font color=navy>The piper answered with one more tune.</font><br>'
               '<font color=navy>风笛手又吹了一首曲子。</font></ol>')


class Segments(unittest.TestCase):
    def test_runs_break_at_style_changes_and_blocks(self):
        self.assertEqual(segments(SAME_COLOUR), [
            ("ol.l1", "To fix a fault for:"), ("ol.l1", "替…修理："),
            ("font#navy", "The piper answered with one more tune."), ("font#navy", "风笛手又吹了一首曲子。")])

    def test_inline_formatting_does_not_split_a_run(self):
        self.assertEqual(segments('<font color=teal>He <b>answered</b> us.</font>'), [("font#teal", "He answered us.")])

    def test_unclosed_list_items_end_at_the_next(self):
        self.assertEqual([k for k, _ in segments('<li class=a>one<li class=b>two')], ["li.a", "li.b"])

    def test_only_the_class_and_color_attributes_count(self):
        self.assertEqual(segments('<span data-class="note">a word</span>'), [("", "a word")])
        self.assertEqual(segments('<font style="background-color: red; color: navy">a word</font>'),
                         [("font#navy", "a word")])
        self.assertEqual(segments('<font data-color=red color=navy>a word</font>'), [("font#navy", "a word")])
        self.assertEqual(segments('<p style="color:teal">a word</p>'), [("p#teal", "a word")])
        # the attributes are read one by one: the same words inside another one's value are not attributes
        self.assertEqual(segments('<font title="use color:red" color=navy>a word</font>'), [("font#navy", "a word")])
        self.assertEqual(segments('<font title="class=note" color=navy>a word</font>'), [("font#navy", "a word")])
        self.assertEqual(segments("<font alt='a class=\"note\" b' style='font-family: \"color: red\"; color: teal'>a word</font>"),
                         [("font#teal", "a word")])
        self.assertEqual(segments('<font title="a > color=red" COLOR="#00FF00">a word</font>'), [("font#00ff00", "a word")])
        self.assertEqual(segments('<span title="x" class="ex first">a word</span>'), [("span.ex", "a word")])
        self.assertEqual(segments("<font color='red>a word</font>"), [("font#red", "a word")])  # an unclosed quote

    def test_a_style_attribute_is_read_as_css(self):
        # comments, strings and brackets hold no declarations; entities are decoded first
        for style in ("/* note; color:red; */ color:navy", "color:navy /* color:red */", "/* color:red */color:navy;",
                      "background: url(a;color:red) ; color: navy", "content: 'a; color: red'; color: navy",
                      "color: red; color: navy", "COLOR : navy !important", "color:&#110;avy",
                      "/* unclosed ; color:red", "color:navy; /* unclosed ; color:red"):
            expected = ("" if style.startswith("/* unclosed") else "font#navy", "a word")
            self.assertEqual(segments(f'<font style="{style}">a word</font>'), [expected], style)
        # a name written with CSS escapes is not read
        self.assertEqual(segments('<font style="col\\6f r: red">a word</font>'), [("", "a word")])

    def test_a_styled_word_inside_an_example_stays_in_it(self):
        markup = ('<span class="en_example">He <span class="emphasis">walked</span> home.</span>'
                  '<span class="cn_example">他走回家了。</span>')
        self.assertEqual(segments(markup), [("span.en_example", "He walked home."), ("span.cn_example", "他走回家了。")])
        # a translation printed inside its example's element still starts its own run
        inside = '<span class="en_example">He walked home. <span class="cn_example">他走回家了。</span></span>'
        self.assertEqual(segments(inside), [("span.en_example", "He walked home."), ("span.cn_example", "他走回家了。")])

    def test_a_styled_word_starting_a_sentence_or_after_an_abbreviation_stays_in_it(self):
        chinese = '<span class="cn_example">他走回家了。</span>'
        for en in ('<span class="emphasis">He</span> walked home.', 'Dr. <span class="emphasis">Smith</span> walked home.',
                   'I met Dr. <span class="emphasis">Smith</span> at home.'):
            plain = en.replace('<span class="emphasis">', "").replace("</span>", "")
            self.assertEqual(segments(f'<span class="en_example">{en}</span>{chinese}'),
                             [("span.en_example", plain), ("span.cn_example", "他走回家了。")], en)
        self.assertEqual(segments('<span class="cn_example"><span class="emphasis">他</span>走回家了。</span>'),
                         [("span.cn_example", "他走回家了。")])
        # an example after a finished definition is not part of it, though the definition's element goes on
        self.assertEqual(segments('<span class="def">To nudge. <font color=blue>I was nudged by a goat.</font> Also used of boats.</span>'),
                         [("span.def", "To nudge."), ("font#blue", "I was nudged by a goat."), ("span.def", "Also used of boats.")])

    def test_a_lone_angle_bracket_is_text(self):
        self.assertEqual(segments("<p>If x < 3 then y > 2.</p>"), [("", "If x < 3 then y > 2.")])

    def test_script_and_style_contents_are_not_text(self):
        self.assertEqual(segments('<script>var a = "He came.";</script><style>p {color: red}</style><p>Text.</p>'),
                         [("", "Text.")])

    def test_quoted_attributes_may_contain_angle_brackets(self):
        self.assertEqual(segments('<font title="a > b" color=teal>a word</font>'), [("font#teal", "a word")])


class Learn(unittest.TestCase):
    EXAMPLES = {"the piper answered with one more tune"}
    DEFINITIONS = {"to fix a fault for"}

    def test_the_example_style_is_the_one_matching_known_examples(self):
        for layout, style in [(CLASSED, "span.en_example"), (COLOURED, "div#009999"), (SAME_COLOUR, "font#navy")]:
            learned = learn([layout] * 25, self.EXAMPLES, self.DEFINITIONS)
            self.assertEqual(list(learned), [style], layout)
            self.assertEqual(pairs(layout, learned), [("The piper answered with one more tune.", "风笛手又吹了一首曲子。")])

    def test_an_example_style_is_learned_however_its_words_are_styled(self):
        # emphasis on its first word, on a title before a name, or on most of its words
        examples = {"mr smith walked home", "the piper answered with one more tune", "he walked home at last"}
        for en in ('<span class="emphasis">Mr</span> Smith walked home.', "<i class=\"t\">Mr</i> Smith walked home.",
                   '<span class="emphasis">The piper</span> answered with <b class="w">one more</b> tune.',
                   '<span class="emphasis">He</span> <span class="emphasis">walked</span> home at last.'):
            layout = f'<li>To fix a fault for:<br>替…修理：<br><span class="en_ex">{en}</span><br>风笛手又吹了一首曲子。</li>'
            learned = learn([layout] * 25, examples, self.DEFINITIONS)
            self.assertEqual(list(learned), ["span.en_ex"], en)

    def test_too_little_evidence_learns_nothing(self):
        self.assertEqual(learn([CLASSED] * 5, self.EXAMPLES, self.DEFINITIONS), {})

    def test_a_style_shared_with_definitions_is_not_an_example_style(self):
        mixed = '<font color=teal>To fix a fault for:</font><br><font color=teal>替…修理：</font>'
        learned = learn([mixed] * 30 + [SAME_COLOUR.replace("navy", "teal")] * 25, self.EXAMPLES, self.DEFINITIONS)
        self.assertEqual(learned, {})  # 25 example hits against 30 definition hits

    def test_definitions_are_never_candidates_in_the_example_style(self):
        learned = learn([COLOURED] * 25, self.EXAMPLES, self.DEFINITIONS)
        self.assertNotIn("To fix a fault for:", [en for en, _ in pairs(COLOURED, learned)])
        self.assertEqual(len(list(candidates(COLOURED))), 2)  # definition and example are both candidates


class Pairs(unittest.TestCase):
    STYLE = {"font#teal"}

    def test_an_untranslated_example_does_not_take_the_next_senses_chinese(self):
        markup = ('<ol><li>To fix a fault for:<br><font color=teal>The piper answered with one more tune.</font></li>'
                  '<li><font color=teal>风笛手又吹了一首曲子。</font></li></ol>')
        self.assertEqual(pairs(markup, self.STYLE), [])
        same_sense = markup.replace("</li><li>", "<br>")
        self.assertEqual(pairs(same_sense, self.STYLE), [("The piper answered with one more tune.", "风笛手又吹了一首曲子。")])

    def test_all_the_english_inside_an_example_element_is_the_example(self):
        # with the example styles known, no guess from punctuation or capitals is needed
        chinese = '<span class="cn_example">他走回家了。</span>'
        for en in ('<span class="emphasis">Mr</span> Smith walked home.', '<span class="emphasis">He</span> walked home.',
                   'Dr. <span class="emphasis">Smith</span> walked <b class="x">home</b>.',
                   'Wait: <span class="emphasis">Smith</span> <i class="y">Came</i> Home.'):
            plain = en.replace('<span class="emphasis">', "").replace("</span>", "")
            for tag in ('<b class="x">', "</b>", '<i class="y">', "</i>"):
                plain = plain.replace(tag, "")
            self.assertEqual(pairs(f'<span class="en_example">{en}</span>{chinese}', {"span.en_example"}),
                             [(plain, "他走回家了。")], en)
        # a translation printed inside its example's element is still the translation
        inside = '<span class="en_example">He walked home. <span class="cn_example">他走回家了。</span></span>'
        self.assertEqual(pairs(inside, {"span.en_example"}), [("He walked home.", "他走回家了。")])
        # an example in the middle of a definition's sentence is an example all the same
        nested = '<span class="def">as in <font color=teal>nudged by a goat</font></span><br><font color=teal>被山羊顶了</font>'
        self.assertEqual(pairs(nested, self.STYLE), [("nudged by a goat", "被山羊顶了")])

    def test_a_sense_is_any_container_not_only_a_list_item(self):
        example = "<font color=teal>The piper answered with one more tune.</font>"
        chinese = "<font color=teal>风笛手又吹了一首曲子。</font>"
        for tag, end in (('div class="sense"', "div"), ("div", "div"), ("td", "td"), ("dd", "dd"), ("li", "li"),
                         ("section", "section")):
            other_sense = f"<{tag}>To fix a fault for:<br>{example}</{end}><{tag}>{chinese}</{end}>"
            self.assertEqual(pairs(other_sense, self.STYLE), [], tag)
            other_sense = f"<{tag}>{example}</{end}><{tag}>{chinese}<br>替…修理：</{end}>"
            self.assertEqual(pairs(other_sense, self.STYLE), [], tag)
            same_sense = f"<{tag}>To fix a fault for:<br>{example}<br>{chinese}</{end}><{tag}>替…修理：</{end}>"
            self.assertEqual(pairs(same_sense, self.STYLE), [("The piper answered with one more tune.", "风笛手又吹了一首曲子。")], tag)
            # one run in each: two senses all the same, however many wrappers
            self.assertEqual(pairs(f"<{tag}>{example}</{end}><{tag}>{chinese}</{end}>", self.STYLE), [], tag)
            self.assertEqual(pairs(f"<{tag}><div>{example}</div></{end}><{tag}><div>{chinese}</div></{end}>", self.STYLE),
                             [], tag)
            self.assertEqual(pairs(f"<ol><{tag}>{example}</{end}><{tag}>{chinese}</{end}></ol>", self.STYLE), [], tag)
            # one in a sense, the other in none
            self.assertEqual(pairs(f"<{tag}>{example}</{end}>{chinese}", self.STYLE), [], tag)
            self.assertEqual(pairs(f"{example}<{tag}>{chinese}</{end}>", self.STYLE), [], tag)
            # each in a box of its own inside the sense: the boxes are wrappers, not senses
            boxed = f"<{tag}>To fix a fault for:<div>{example}</div><div>{chinese}</div></{end}>"
            self.assertEqual(pairs(boxed, self.STYLE), [("The piper answered with one more tune.", "风笛手又吹了一首曲子。")], tag)
            boxed = f"<{tag}><div>{example}</div><div>{chinese}</div></{end}>"  # the sense holds only the pair
            self.assertEqual(pairs(boxed, self.STYLE), [("The piper answered with one more tune.", "风笛手又吹了一首曲子。")], tag)
        # in no container at all, nothing separates them
        self.assertEqual(pairs(f"{example}<br>{chinese}", self.STYLE), [("The piper answered with one more tune.", "风笛手又吹了一首曲子。")])

    def test_examples_joined_by_semicolons_become_separate_pairs(self):
        markup = ('<font color=teal>mapping each bend of the florp; map every grelt in the valley.</font><br>'
                  '<font color=teal>绘制弗洛普的每道弯；绘制山谷里的每块格尔特</font>')
        self.assertEqual(pairs(markup, self.STYLE), [("mapping each bend of the florp", "绘制弗洛普的每道弯"),
                                                     ("map every grelt in the valley.", "绘制山谷里的每块格尔特")])
        # when the parts do not correspond, the pair stays whole
        uneven = markup.replace("；绘制", "，绘制")
        self.assertEqual(len(pairs(uneven, self.STYLE)), 1)

    def test_cross_references_are_removed(self):
        markup = ('<font color=teal>the paint of fences worn by rain.See Synonyms at chafe</font><br>'
                  '<font color=teal>由于下雨，篱笆上的油漆被磨损了 参见 chafe</font>')
        self.assertEqual(pairs(markup, self.STYLE), [("the paint of fences worn by rain.", "由于下雨，篱笆上的油漆被磨损了")])


if __name__ == "__main__":
    unittest.main()
