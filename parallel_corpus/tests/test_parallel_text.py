"""Finding example pairs in dictionary markup (shared by the probe and the extractor)."""
import unittest

from parallel.corpus import clean_en, clean_zh
from parallel.markup import TEXT, tokens
from parallel.text import pairs, stream


class Stream(unittest.TestCase):
    def test_boundaries_are_blocks_breaks_and_style_markers(self):
        self.assertEqual(stream("<p>one <b>two</b> <a href='#'>three</a></p><p>four</p>"), "one two three\nfour")
        self.assertEqual(stream("alpha<br>beta`12`gamma"), "alpha\nbeta\ngamma")
        # inline HTML adds no space (a highlighted ending stays in its word); unknown tags add one
        self.assertEqual(stream("He knead<b>ed</b> the dough well."), "He kneaded the dough well.")
        self.assertEqual(stream("<def>a cost</def><ex>It rose.</ex>"), "a cost It rose.")
        self.assertEqual(stream("<xhtml:a>word</xhtml:a> <xhtml:a>by</xhtml:a> word"), "word by word")
        self.assertEqual(stream("a&nbsp;b &lt;br&gt;c <!-- note --> d"), "a b\nc d")

    def test_a_quoted_attribute_may_contain_an_angle_bracket(self):
        self.assertEqual(stream('<p title="a > b">Pip came home.</p>'), "Pip came home.")
        self.assertEqual(stream("<p title='a > b'>Pip came home.</p>"), "Pip came home.")
        self.assertEqual(stream("<font color='red>Pip came home.</font>"), "Pip came home.")  # an unclosed quote
        self.assertEqual(stream('<p title="a < x > b">Pip came home.</p>'), "Pip came home.")
        self.assertEqual(stream("<p title='if a<b then c>d' class=x>Pip came home.</p>"), "Pip came home.")
        self.assertEqual(stream('<a href="x" title="2 > 1">one</a> <b title="<p>">two</b>'), "one two")
        self.assertEqual(pairs('<p title="a < x > b">Pip cycled to the florp mill yesterday.</p><p>皮普昨天骑车去了弗洛普磨坊。</p>'),
                         [("Pip cycled to the florp mill yesterday.", "皮普昨天骑车去了弗洛普磨坊。")])
        # after an unclosed quote the next quote is in the text, with a letter after it: no attribute ends so
        self.assertEqual(stream("<font color='red>Pip's home and Lena's out.</font>"), "Pip's home and Lena's out.")
        self.assertEqual(stream("<!DOCTYPE html><?xml version='1.0'?><p>Pip came home.</p>"), "Pip came home.")
        self.assertEqual(stream("<p>The sign &lt;!&gt; means florp.</p>"), "The sign <!> means florp.")  # no name: text

    def test_a_quoted_attribute_of_any_length_is_read_whole(self):
        example = "Pip cycled to the florp mill yesterday.</p><p>皮普昨天骑车去了弗洛普磨坊。</p>"
        for length in (1_999, 2_001, 50_000):
            for value in ("a" * length + " > b", "<" + "x" * length + ">", "a" * length):
                markup = f'<p title="{value}">' + example
                self.assertEqual(pairs(markup), [("Pip cycled to the florp mill yesterday.", "皮普昨天骑车去了弗洛普磨坊。")], (length, value[:3]))
                markup = f"<p class=x title='{value}' lang=en>" + example
                self.assertEqual(pairs(markup), [("Pip cycled to the florp mill yesterday.", "皮普昨天骑车去了弗洛普磨坊。")], (length, value[:3]))

    def test_reading_is_linear_in_the_markup(self):
        import time
        units = ("<a title=\"x>", "<!--", "<script>", "<a b=\"<a b=\"", "<p title='>x ", "<a b=1 ", "<", "<a title=\"x\" c",
                 "<style>a</b>", "<x:script>\x00")

        def cost(markup):
            start = time.perf_counter()
            for _ in tokens(markup):
                pass
            return time.perf_counter() - start
        for unit in units:
            small = min(cost(unit * 5_000 + "Pip came home.") for _ in range(3))
            large = min(cost(unit * 40_000 + "Pip came home.") for _ in range(3))
            self.assertLess(large, 16 * small + 0.05, unit)  # 8 times the text: 64 times the time if quadratic

    def test_script_and_style_contents_are_not_text(self):
        self.assertEqual(stream('<p>One.</p><script>var s = "Pip came home.";</script><style>p {}</style><p>Two.</p>'),
                         "One.\nTwo.")
        self.assertEqual(pairs("<script>// Pip cycled to the florp mill yesterday. 皮普昨天骑车去了弗洛普磨坊。</script>"), [])
        self.assertEqual(stream("<SCRIPT type='x'>a < b</SCRIPT ><p>One.</p>"), "One.")

    def test_only_a_real_script_tag_starts_a_script(self):
        # in a comment or an attribute value it is not a tag: what follows is text
        example = "<p>Pip cycled to the florp mill yesterday.</p><p>皮普昨天骑车去了弗洛普磨坊。</p>"
        for before in ("<!-- <script> -->", '<p title="<script>">One.</p>', "<!-- <style> -->"):
            markup = before + example + "<script>var a;</script><style>p {}</style>"
            self.assertEqual(pairs(markup), [("Pip cycled to the florp mill yesterday.", "皮普昨天骑车去了弗洛普磨坊。")], before)

    def test_an_unclosed_script_runs_to_the_end_of_its_record(self):
        # as a browser runs it to the end of the document; the next record (after its NUL) is text
        example = "<p>Pip cycled to the florp mill yesterday.</p><p>皮普昨天骑车去了弗洛普磨坊。</p>"
        for opener in ("<script>", "<style>", "<script type='text/javascript'>", "<xhtml:script>", "<SCRIPT>"):
            self.assertEqual(stream("<p>One.</p>" + opener + "<p>Two.</p>"), "One.", opener)
            self.assertEqual(pairs(opener + example), [], opener)
            texts = [v for kind, v, _, _ in tokens("<p>One.</p>" + opener + "<p>Two.</p>\x00<p>Three.</p>") if kind == TEXT]
            self.assertEqual(texts, ["One.", "\x00", "Three."], opener)
        self.assertEqual(pairs("<p>x</p><script>var a;" + "\x00" + example), [("Pip cycled to the florp mill yesterday.", "皮普昨天骑车去了弗洛普磨坊。")])

    def test_a_script_or_style_with_a_namespace_prefix_is_one(self):
        example = "<p>Pip cycled to the florp mill yesterday.</p><p>皮普昨天骑车去了弗洛普磨坊。</p>"
        for element in ("xhtml:script", "xhtml:style", "XHTML:SCRIPT", "h:style"):
            markup = f"<{element}>{example}</{element}><p>Two.</p>"
            self.assertEqual(pairs(markup), [], element)
            self.assertEqual(stream(markup), "Two.", element)
        # closed by its local name, with or without the prefix
        self.assertEqual(stream("<xhtml:script>var a;</script><p>Two.</p>"), "Two.")
        self.assertEqual(stream("<script>var a;</xhtml:script><p>Two.</p>"), "Two.")

    def test_an_end_tag_with_attributes_or_a_slash_ends_a_script(self):
        # HTML ends a script at "</script" followed by space, "/" or ">", whatever follows up to ">"
        for end in ('</script data-x="y">', "</script >", "</script/>", "</SCRIPT\tfoo>"):
            self.assertEqual(stream("<script>var a;" + end + "<p>Two.</p>"), "Two.", end)
        # but not a longer name that starts the same way
        self.assertEqual(stream("<script>var a = '</scripts>';</script><p>Two.</p>"), "Two.")

    def test_html_ignores_a_self_closing_slash_on_a_script(self):
        # <script/> still opens a script in HTML (not a void element); in XML (a prefix) it is closed
        example = "<p>Pip cycled to the florp mill yesterday.</p><p>皮普昨天骑车去了弗洛普磨坊。</p>"
        for opener in ("<script src=/assets/app.js/>", "<script/>", '<style media="x" />'):
            close = "</style>" if "style" in opener else "</script>"
            self.assertEqual(pairs(opener + example + close + "<p>Two.</p>"), [], opener)
            self.assertEqual(stream(opener + "var a;" + close + "<p>Two.</p>"), "Two.", opener)
        self.assertEqual(pairs("<xhtml:script/>" + example), [("Pip cycled to the florp mill yesterday.", "皮普昨天骑车去了弗洛普磨坊。")])


class Pairs(unittest.TestCase):
    def test_the_definition_before_an_example_is_left_out(self):
        compact = "`11`~ a recital`12`The brass band will play here again on Sunday.`13`铜管乐队星期天将再次在这里演奏。"
        self.assertEqual(pairs(compact), [("The brass band will play here again on Sunday.", "铜管乐队星期天将再次在这里演奏。")])

    def test_an_example_keeps_as_many_sentences_as_its_translation(self):
        self.assertEqual(pairs("<p>to move quickly</p><p>Come on! The florp ferry leaves soon.</p><p>快点！弗洛普渡轮马上就开了。</p>"),
                         [("Come on! The florp ferry leaves soon.", "快点！弗洛普渡轮马上就开了。")])
        self.assertEqual(pairs("<p>A long note here. The goat dozed quietly in the shed.</p><p>山羊在棚里静静地打盹。</p>"),
                         [("The goat dozed quietly in the shed.", "山羊在棚里静静地打盹。")])

    def test_the_translation_ends_with_its_element(self):
        # a label element after the translation is not part of it
        cobuild = ("<p>Pip bakes florp buns for us all.<span> [ N ]</span></p>"
                   "<p><span>皮普为我们大家烤弗洛普面包。</span></p><p>语法信息</p>")
        self.assertEqual(pairs(cobuild), [("Pip bakes florp buns for us all.", "皮普为我们大家烤弗洛普面包。")])

    def test_an_opening_quotation_mark_belongs_to_the_translation(self):
        self.assertEqual(pairs("<p>'The florp is ready,' Lena told him.</p><p>“弗洛普好了，”莉娜对他说。</p>"),
                         [("'The florp is ready,' Lena told him.", "“弗洛普好了，”莉娜对他说。")])
        self.assertEqual(pairs("<p>'Is the tea hot?' 'Yes, very.' “茶热吗？”“很热。”</p>"),
                         [("'Is the tea hot?' 'Yes, very.'", "“茶热吗？”“很热。”")])

    def test_a_highlighted_headword_inside_an_example_does_not_cut_it(self):
        oalecd = ('<und>to boom sth out<chn>指大声喊出</chn>：</und><x>He <ebi>boomed out</ebi> '
                  'the florp score at once.<chnsep> </chnsep><chn>他立刻大声报出了弗洛普比分。</chn></x>')
        self.assertEqual(pairs(oalecd), [("He boomed out the florp score at once.", "他立刻大声报出了弗洛普比分。")])

    def test_bullets_separate_a_label_from_the_example(self):
        self.assertEqual(pairs("<x>SYN hand down ◆ These florp recipes go from aunt to niece.<chn>这些弗洛普食谱由姑姑传给侄女。</chn></x>"),
                         [("These florp recipes go from aunt to niece.", "这些弗洛普食谱由姑姑传给侄女。")])
        self.assertEqual(pairs("<span>British English · I never knew knitting could be so relaxing.</span><span>我从不知道织毛衣这么令人放松。</span>"),
                         [("I never knew knitting could be so relaxing.", "我从不知道织毛衣这么令人放松。")])
        self.assertEqual(stream("the hold·all bag"), "the hold·all bag")  # a syllable dot is not a bullet

    def test_a_collocation_in_its_own_tag_is_cut_from_the_example(self):
        ldoce = "<colloc>hum with</colloc> <ex>Lena's kitchen was humming with chatter.</ex><tr>莉娜的厨房里满是说笑声。</tr>"
        self.assertEqual(pairs(ldoce), [("Lena's kitchen was humming with chatter.", "莉娜的厨房里满是说笑声。")])

    def test_latin_letters_inside_the_chinese_do_not_cut_it(self):
        self.assertEqual(pairs("<p>The crack only shows up on new X-ray scanners.</p><p>只有新的X光扫描仪才能显示出这道裂缝。</p>"),
                         [("The crack only shows up on new X-ray scanners.", "只有新的X光扫描仪才能显示出这道裂缝。")])
        # a whole English sentence between two translations still starts a new pair
        self.assertEqual(len(pairs("<p>Pip likes plum jam a lot. 皮普很喜欢李子酱。 Lena likes honey even more. 莉娜更喜欢蜂蜜。</p>")), 2)

    def test_an_abbreviation_does_not_end_a_sentence(self):
        self.assertEqual(pairs("<p>I phoned Dr. Smith about the rash.</p><p>我打电话向史密斯医生询问皮疹的事。</p>"),
                         [("I phoned Dr. Smith about the rash.", "我打电话向史密斯医生询问皮疹的事。")])
        self.assertEqual(pairs("<p>She met J. R. Hartley at the florp fair.</p><p>她在弗洛普集市上见到了哈特利。</p>"),
                         [("She met J. R. Hartley at the florp fair.", "她在弗洛普集市上见到了哈特利。")])

    def test_a_title_before_a_name_does_not_end_a_sentence(self):
        for title in ("Rev.", "Capt.", "Sgt.", "Gov.", "Mme.", "Supt.", "Col.", "Gen."):
            en = f"I phoned {title} Smith twice."
            self.assertEqual(pairs(f"<p>{en}</p><p>我给史密斯打了两次电话。</p>"), [(en, "我给史密斯打了两次电话。")], title)
        # a name that ends a sentence still ends it, whatever starts the next one
        for second in ("The goat dozed quietly in the shed.", "Smith dozed quietly in the shed.", "'The goat dozed in the shed.'"):
            self.assertEqual([en for en, _ in pairs(f"<p>We sailed on to Rome. {second}</p><p>山羊在棚里静静地打盹。</p>")],
                             [second], second)

    def test_latin_text_with_full_stops_or_a_tag_ending_the_chinese_stays_in_it(self):
        for zh in ("皮普自学了如何使用Python3.11。", "皮普自学了如何使用<ebi>Python</ebi>。", "皮普自学了如何使用U.S.B.。",
                   "皮普自学了如何使用<b>Python</b> 3.11？"):
            plain = zh.replace("<ebi>", "").replace("</ebi>", "").replace("<b>", "").replace("</b>", "")
            html = f"<p>Pip taught himself to use Python.</p><p>{zh}</p><p>Next we went home together.</p>"
            self.assertEqual(pairs(html), [("Pip taught himself to use Python.", plain)], zh)
            self.assertEqual(pairs(f"<p>{zh}</p><p>Pip taught himself to use Python.</p>", order="zh-en"),
                             [("Pip taught himself to use Python.", plain)], zh)
        # an English sentence in its own element is not the Chinese sentence's ending, even before a ！
        markup = "<cn>我们大声喊了加油。</cn><en>They all shouted come on！</en><cn>他们都喊加油！</cn>"
        self.assertEqual(pairs(markup, order="zh-en"), [("They all shouted come on！", "我们大声喊了加油。")][:0])
        self.assertEqual(pairs("<p>皮普学会了。</p><p>Pip learned it. Fine。</p><p>好。</p>", order="zh-en"), [])

    def test_an_abbreviation_before_what_it_qualifies_never_ends_a_sentence(self):
        zh = "我打电话向史密斯助理教授求助，价格含增值税。"
        for en in ("I called Asst. Prof. Smith about florps.", "I met Lt. Col. Jones at the old base.",
                   "The price is twenty florps incl. VAT and florp delivery.", "It costs ten florps excl. VAT here.",
                   "It took approx. Ten Downing Street staff a week.", "Read the old tales, esp. Beowulf and others.",
                   "Compare the two, cf. Smith on the florp page.", "It was England vs. Germany in the final.",
                   "Many cities, e.g. London and Paris, grew fast.", "One city, i.e. London, grew very fast.",
                   "The vase dates from ca. AD 1200 or so.", "I met Assoc. Prof. Smith at the old base."):
            self.assertEqual(pairs(f"<p>{en}</p><p>{zh}</p>"), [(en, zh)], en)
            # the same where the English is read up to its last finished sentence or loses a tail
            self.assertEqual(pairs(f"<p>{zh}</p><p>{en}</p>", order="zh-en"), [(en, zh)], en)
        # with no full stop at the end, the text after the abbreviation is not a stray tail
        self.assertEqual(pairs("<p>Pip was treated at home by Dr. Smith 皮普由史密斯医生在家中诊治。</p>"), [])
        self.assertEqual(pairs("<p>皮普由史密斯医生在家中诊治。</p><p>Pip was treated at home by Dr. Smith</p>", order="zh-en"), [])
        # at the end of the English nothing follows, so the full stop ends it whatever it is
        self.assertEqual(pairs("<p>侧向弗洛普漂移</p><p>lateral florp drift (+L.F.)</p>", order="zh-en"),
                         [("lateral florp drift (+L.F.)", "侧向弗洛普漂移")])
        # "I" is the pronoun, not an initial: "So do I." ends a sentence
        self.assertEqual([en for en, _ in pairs("<p>Nobody will help, so do I. The goat dozed quietly in the shed.</p>"
                                                 "<p>山羊在棚里静静地打盹。</p>")], ["The goat dozed quietly in the shed."])
        # abbreviations that follow what they qualify may end a sentence
        for first in ("He works at Acme Inc.", "Bring pens, paper, etc."):
            self.assertEqual([en for en, _ in pairs(f"<p>{first} The goat dozed quietly in the shed.</p><p>山羊在棚里静静地打盹。</p>")],
                             ["The goat dozed quietly in the shed."], first)

    def test_latin_text_of_any_length_ending_the_chinese_stays_in_it(self):
        for latin in ("Microsoft Visual Studio Code", "the New York Times Book Review", "Visual Studio Code 1.85 for Mac"):
            en, zh = f"Pip taught himself to use {latin}.", f"皮普自学了如何使用{latin}。"
            self.assertEqual(pairs(f"<p>{en}</p><p>{zh}</p><p>Next we went home together.</p>"), [(en, zh)], latin)
            self.assertEqual(pairs(f"<p>{zh}</p><p>{en}</p>", order="zh-en"), [(en, zh)], latin)
            tagged = f"皮普自学了如何使用<ebi>{latin}</ebi>。"
            self.assertEqual(pairs(f"<p>{en}</p><p>{tagged}</p>"), [(en, zh)], latin)
        # after a finished Chinese sentence, Latin text ending in 。 starts something else
        self.assertEqual(pairs("<p>Pip taught himself to knit well.</p><p>皮普学会了。Microsoft Visual Studio Code。</p>"),
                         [("Pip taught himself to knit well.", "皮普学会了。")])

    def test_latin_words_ending_the_chinese_stay_in_it(self):
        html = "<p>Pip taught himself to use Python.</p><p>皮普自学了如何使用Python。</p><p>Next we went home together.</p>"
        self.assertEqual(pairs(html), [("Pip taught himself to use Python.", "皮普自学了如何使用Python。")])
        self.assertEqual(pairs("<p>皮普自学了如何使用Python。</p><p>Pip taught himself to use Python.</p>", order="zh-en"),
                         [("Pip taught himself to use Python.", "皮普自学了如何使用Python。")])

    def test_merged_translations_keep_the_sentences_they_translate(self):
        # one Chinese sentence for two English ones: the length ratio decides
        self.assertEqual(pairs("<p>The florp kettle boiled over. That ended our chat.</p><p>弗洛普水壶烧开了，我们的闲聊到此结束。</p>"),
                         [("The florp kettle boiled over. That ended our chat.", "弗洛普水壶烧开了，我们的闲聊到此结束。")])
        # a definition before a short example stays out
        self.assertEqual(pairs("<p>If you grumble, you moan florpishly. He grumbled at the cat.</p><p>他冲猫抱怨。</p>"),
                         [("He grumbled at the cat.", "他冲猫抱怨。")])

    def test_latin_words_starting_the_translation_belong_to_it(self):
        self.assertEqual(pairs("<p>Can Pip spell 'grelt' in florp?</p><p>grelt 皮普会用弗洛普语拼吗？</p>"),
                         [("Can Pip spell 'grelt' in florp?", "grelt 皮普会用弗洛普语拼吗？")])
        self.assertEqual(pairs("<p>Our kitten arrived on 4th December.</p><p>我们的小猫是 12 月 4 号来的。</p>")[0][1],
                         "我们的小猫是 12 月 4 号来的。")
        # a grammar code after the sentence is not moved into the translation
        self.assertEqual(pairs("<p>Pip tolerates florp noise daily. [ VERB ]</p><p>皮普每天都忍受弗洛普的噪音。</p>")[0][1],
                         "皮普每天都忍受弗洛普的噪音。")

    def test_a_tag_inside_a_sentence_does_not_cut_it(self):
        # an explanatory gloss in its own tag
        oalecd = ('<x>Shall Pip give the <cl>nod</cl> <gl-blk>(= <gl>signal yes</gl>)</gl-blk> to Tom?'
                  '<xhtml:br></xhtml:br><chn><mark></mark>皮普要向汤姆点头示意吗？</chn></x>')
        self.assertEqual(pairs(oalecd), [("Shall Pip give the nod (= signal yes) to Tom?", "皮普要向汤姆点头示意吗？")])
        # a highlighted phrase that begins the second sentence of an example
        oalecd = ('<x>That seems a sound idea. <cl-blk><cl>Try it now</cl></cl-blk>!<xhtml:br></xhtml:br>'
                  '<chn>这似乎是个好主意。现在就试试吧！</chn></x>')
        self.assertEqual(pairs(oalecd), [("That seems a sound idea. Try it now!", "这似乎是个好主意。现在就试试吧！")])

    def test_no_cut_inside_a_gloss_after_a_comma_or_in_word_by_word_tagging(self):
        cases = {
            "<x>One florp of this sauce can go a <cl>long way</cl> (= <gl>florps suffice</gl>).<chn>这种酱一个弗洛普就够了。</chn></x>":
                "One florp of this sauce can go a long way (= florps suffice).",
            "<x><cl>When the florp chimes</cl>, <cl>I</cl> plan to rest by the florp stove.<chn>弗洛普响的时候，我打算在弗洛普炉边休息。</chn></x>":
                "When the florp chimes, I plan to rest by the florp stove.",
            "<x><f></f>Could <f></f>Lena <f></f>steady <f></f>the <f></f>ladder <f></f>while <f></f>I <f></f>fix <f></f>the "
            "<f></f>florp?<chn>我修弗洛普的时候莉娜能扶稳梯子吗？</chn></x>": "Could Lena steady the ladder while I fix the florp?",
        }
        for markup, en in cases.items():
            self.assertEqual([e for e, _ in pairs(markup)], [en])

    def test_an_example_starting_with_i_after_a_label_tag_is_cut_from_it(self):
        ldoce = "<colloc>doubt that</colloc> <ex>I doubt that florps grow here.</ex><tr>我怀疑弗洛普在这里长不了。</tr>"
        self.assertEqual([e for e, _ in pairs(ldoce)], ["I doubt that florps grow here."])

    def test_a_dialogue_with_every_word_tagged_stays_whole(self):
        oalecd = ("<x><ft></ft>'<ft></ft>Did <ft></ft>the <ft></ft>florp <ft></ft>finish <ft></ft>its <ft></ft>soup?<ft></ft>' "
                  "<ft></ft>'<ft></ft>Nearly.<ft></ft>'<br><chn>“弗洛普把汤喝完了吗？” “快了。”</chn></x>")
        self.assertEqual(pairs(oalecd), [("'Did the florp finish its soup?' 'Nearly.'", "“弗洛普把汤喝完了吗？” “快了。”")])

    def test_consecutive_examples_in_custom_tags_stay_apart(self):
        ldoce = ('<span class="example"><EXAEN><a href="sound://x.mp3"><img src="i.png"></a>&nbsp;Pip walked home slowly, '
                 'humming a tune.</EXAEN><EXAMPLE>皮普哼着曲子慢慢走回家。</EXAMPLE></span><exat></exat>'
                 '<span class="example"><EXAEN>Lena yawned.</EXAEN><EXAMPLE>莉娜打了个哈欠。</EXAMPLE></span>')
        self.assertEqual([zh for _, zh in pairs(ldoce)], ["皮普哼着曲子慢慢走回家。"])  # "Lena yawned." is too short

    def test_a_heading_in_its_own_tag_is_not_merged_into_the_translation(self):
        ldoce = ("<EXAEN>Florps can reach the grelt island at low water.</EXAEN><EXAMPLE>水位低时弗洛普可以到达格尔特岛。</EXAMPLE>"
                 "<sense><num>31</num><sign>sport</sign><gram>体育</gram></sense>")
        self.assertEqual([zh for _, zh in pairs(ldoce)], ["水位低时弗洛普可以到达格尔特岛。"])

    def test_old_style_backtick_quotes_are_kept(self):
        self.assertEqual(clean_en(pairs("<p>`Hurry up, you two,' Lena yelled at the florps.</p><p>“快点，你们俩。”莉娜对弗洛普们喊道。</p>")[0][0]),
                         "`Hurry up, you two,' Lena yelled at the florps.")

    def test_a_label_in_angle_brackets_is_not_part_of_the_translation(self):
        [(en, zh)] = pairs("<p>Who will eat all this florp?</p><p>&lt;非正式&gt;谁会吃完这些弗洛普？</p>")
        self.assertEqual((en, clean_zh(zh)), ("Who will eat all this florp?", "谁会吃完这些弗洛普？"))

    def test_phrase_templates_and_definitions_with_sb_or_sth_are_not_sentences(self):
        self.assertEqual(pairs("<p>to pass sth along in silence.</p><p>默默传递。</p>"), [])
        self.assertEqual(pairs("<p>If you florp sb, you thank them warmly.</p><p>向某人道谢。</p>"), [])

    def test_chinese_first_dictionaries_are_read_in_their_order(self):
        cedict = "<p>她轻轻地关上了柜门。She closed the cupboard very gently.</p>"
        self.assertEqual(pairs(cedict, order="zh-en"), [("She closed the cupboard very gently.", "她轻轻地关上了柜门。")])
        self.assertEqual(pairs(cedict), [])  # nothing Chinese follows the English

    def test_a_gloss_before_a_chinese_example_is_left_out(self):
        markup = "<p>关上；关</p><p>她轻轻地关上了那扇门。</p><p>She gently closed that door.</p><p>close</p>"
        self.assertEqual(pairs(markup, order="zh-en"), [("She gently closed that door.", "她轻轻地关上了那扇门。")])
        # separated only by a dictionary tag, a gloss is dropped when the length ratio clearly says so
        markup = "<gl>关闭；关上</gl><ex>她轻轻地关上了那扇门。</ex><tr>She gently closed that door.</tr>"
        self.assertEqual(pairs(markup, order="zh-en"), [("She gently closed that door.", "她轻轻地关上了那扇门。")])

    def test_a_number_starting_a_chinese_first_example_stays_with_it(self):
        markup = ('<lct><cn>弗洛普季节池塘水位下降了一点。</cn><en>The pond level dropped slightly during florp season.</en></lct>'
                  '<lct><cn>20 多只海鸥开始向码头俯冲。</cn><en>More than 20 gulls began to swoop towards the pier.</en></lct>')
        self.assertEqual([zh for _, zh in pairs(markup, order="zh-en")],
                         ["弗洛普季节池塘水位下降了一点。", "20 多只海鸥开始向码头俯冲。"])

    def test_a_highlighted_word_in_a_chinese_example_does_not_cut_it(self):
        markup = "<ex>她<hw>关上</hw>了那扇旧柜门。</ex><tr>She closed the old cupboard.</tr>"
        self.assertEqual(pairs(markup, order="zh-en"), [("She closed the old cupboard.", "她关上了那扇旧柜门。")])

    def test_names_and_titles_are_not_sentences(self):
        for name in ("<p>Advanced Micro Widgets Inc.</p><p>先进微部件公司</p>",
                     "<p>PACIFIC ISLAND AIRWAYS CO. LTD.</p><p>太平洋岛屿航空公司</p>"):
            self.assertEqual(pairs(name), [], name)
        self.assertEqual(len(pairs("<p>Who ruled after James I?</p><p>詹姆斯一世之后是谁统治的？</p>")), 1)

    def test_other_languages_and_definitions_are_not_pairs(self):
        self.assertEqual(pairs("<p>Er öffnet das Fenster, weil es zu warm ist.</p><p>他打开窗户，因为太热了。</p>"), [])
        self.assertEqual(pairs("<p>to carry something uphill</p><p>把某物搬上山</p>"), [])  # a phrase: not taken

    def test_loose_translations_without_final_punctuation_are_kept_by_default(self):
        old = "`12`The florp mayor will sing a brief florp song tonight. <br>弗洛普市長今晚將唱弗洛普歌`12`"
        self.assertEqual(pairs(old), [("The florp mayor will sing a brief florp song tonight.", "弗洛普市長今晚將唱弗洛普歌")])
        self.assertEqual(pairs(old, strict=True), [])


if __name__ == "__main__":
    unittest.main()
