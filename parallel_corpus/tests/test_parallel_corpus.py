"""The parallel corpus's pair rules: validity, sentence vs phrase, and the three dedup keys."""
import unittest

from parallel.corpus import clean_en, clean_zh, en_key, exact_key, judge, loose_key


class Judge(unittest.TestCase):
    def test_sentences_and_phrases(self):
        self.assertEqual(judge("Mira opened the kitchen window.", "米拉打开了厨房的窗户。"),
                         judge("Mira opened the kitchen window.", "米拉打开了厨房的窗户。"))
        self.assertEqual(judge("Mira opened the kitchen window.", "米拉打开了厨房的窗户。").kind, "sentence")
        self.assertEqual(judge("wet socks", "湿袜子").kind, "phrase")
        self.assertEqual(judge("Mira opened the kitchen window", "米拉打开了厨房的窗户").kind, "phrase")  # no final punctuation

    def test_rejections_say_why(self):
        cases = {
            ("", "中文"): "empty side",
            ("A <b>bold</b> claim here.", "一个大胆的说法。"): "markup in text",
            ("米拉打开了厨房的窗户。", "Mira opened the kitchen window."): "Chinese on the English side",
            ("12345", "一二三四五"): "no English words",
            ("Mira opened the kitchen window.", "Mira opened it."): "no Chinese on the Chinese side",
            ("Mira opened the kitchen window; her florp heard the rain drumming outside.", "开"): "length ratio",
        }
        for (en, zh), reason in cases.items():
            v = judge(en, zh)
            self.assertFalse(v.ok, (en, zh))
            self.assertTrue(v.reason.startswith(reason), v.reason)

    def test_the_latin_side_must_be_english(self):
        foreign = {
            "German": "Er öffnet das Fenster, weil es im Zimmer zu warm ist.",
            "French": "Elle ouvre la fenêtre parce qu'il fait trop chaud.",
            "Spanish": "Ella abre la ventana porque hace mucho calor aquí.",
            "Italian": "Lei apre la finestra perché fa molto caldo qui.",
            "Dutch": "Zij opent het raam omdat het te warm is in de kamer.",
            "romanised Japanese": "Kanojo wa mado o akemashita.",
        }
        for language, sentence in foreign.items():
            v = judge(sentence, "她打开窗户，因为房间里太热了。")
            self.assertFalse(v.ok, language)
            self.assertEqual(v.reason, "the Latin-script side is not English", language)
        self.assertTrue(judge("Mira opens the attic window because it is stuffy.", "米拉打开阁楼的窗户，因为太闷了。").ok)
        self.assertTrue(judge("Is the café by the pier open on Mondays?", "码头边的咖啡馆星期一开门吗？").ok)  # a loanword accent is fine

    def test_english_without_function_words_is_still_english(self):
        # Real phrases and short sentences often have no "the", "of", "is"...
        for en, zh in [("stubbornly cold spring nights", "持续寒冷的春夜"),
                       ("Three window seats, please.", "请给我三个靠窗的座位。"),
                       ("trucks hauling winter grain", "运送冬粮的卡车"),
                       ("the Los Angeles Police Department", "洛杉矶警察局")]:
            self.assertTrue(judge(en, zh).ok, en)

    def test_pinyin_is_not_english(self):
        self.assertEqual(judge("mànman zǒu.", "慢慢走。").reason, "the Latin-script side is not English")

    def test_the_chinese_or_marker_in_english_examples_becomes_or(self):
        # Chinese-made dictionaries write alternatives as "(或 with)"
        self.assertEqual(clean_en("a kettle of (或 with) florp handles"), "a kettle of (or with) florp handles")
        self.assertEqual(clean_en("clamber (或scramble) onto the florp"), "clamber (or scramble) onto the florp")
        self.assertEqual(judge("Lena was cross with (或 at) the puppy.", "莉娜生小狗的气。").reason,
                         "alternative versions")  # notation for alternatives, not a sentence as written
        self.assertEqual(clean_en("We swapped turns (on, at 或 in) rowing the dinghy."),
                         "We swapped turns (on, at or in) rowing the dinghy.")
        # the Chinese side keeps its own 或: "(或深秋)" is Chinese for "(or late autumn)"
        self.assertEqual(clean_zh("在初冬(或深秋)"), "在初冬(或深秋)")
        self.assertEqual(judge("in the cold months", "在初冬(或深秋)").ok, True)

    def test_chinese_register_labels_are_dropped_from_the_english(self):
        self.assertEqual(clean_en("grumble about (或〈古〉at) the cold soup"), "grumble about (or at) the cold soup")
        self.assertEqual(clean_en("the third shelf<英><美>"), "the third shelf")
        self.assertEqual(judge("Those are (或〈谑〉Them's) my old boots.", "那些是我的旧靴子。").reason,
                         "alternative versions")

    def test_dictionary_apparatus_is_removed(self):
        # grammar labels, explanatory glosses and usage labels are the dictionary's, not the example's
        self.assertEqual(clean_en("[with object]: he painted the gate"), "he painted the gate")
        self.assertEqual(clean_en("(as adjective cracked) a cracked teacup"), "a cracked teacup")
        self.assertEqual(clean_en("a farrier (= one who fits horseshoes) in the village"), "a farrier in the village")
        self.assertEqual(clean_en("( + adv./prep.) Tilda is going sailing on Florp Lake."), "Tilda is going sailing on Florp Lake.")
        self.assertEqual(clean_en("(~ sth to sb) Tilda passed the salt to him."), "Tilda passed the salt to him.")
        self.assertEqual(clean_zh("〈俚〉她真是个夜猫子。"), "她真是个夜猫子。")
        # ordinary brackets stay
        self.assertEqual(clean_en("The lamp (torch) flickered twice."), "The lamp (torch) flickered twice.")
        self.assertEqual(clean_en("[Laughter] Nobody saw that coming."), "[Laughter] Nobody saw that coming.")
        self.assertEqual(clean_zh("他写了〈晨雾〉这篇文章。"), "他写了〈晨雾〉这篇文章。")  # a title, not a label

    def test_layout_residue_at_the_edges_is_removed(self):
        self.assertEqual(clean_en("Pip saw no florp reason to hurry home ."), "Pip saw no florp reason to hurry home.")
        self.assertEqual(clean_en("What is Pip baking ?"), "What is Pip baking?")
        self.assertEqual(clean_en("· I think Pip is joking."), "I think Pip is joking.")
        self.assertEqual(clean_en("◆ ...the sleepy calm of the harbour."), "...the sleepy calm of the harbour.")
        self.assertEqual(clean_en("'Fine,' Pip said."), "'Fine,' Pip said.")  # quotes stay
        self.assertEqual(clean_zh("🔊我们没有雨伞。"), "我们没有雨伞。")
        self.assertEqual(clean_zh("◆“早安，”她说。"), "“早安，”她说。")
        self.assertEqual(clean_zh("《红楼梦》很长。"), "《红楼梦》很长。")
        self.assertEqual(clean_zh("……然后她睡着了。"), "……然后她睡着了。")

    def test_pronunciation_is_not_an_example(self):
        self.assertEqual(judge("grelton /ˈɡrɛltən/ n.", "格尔顿石").reason, "pronunciation in text")

    def test_subject_and_register_labels_leave_the_chinese(self):
        self.assertEqual(clean_zh("【地质】岩层断裂带"), "岩层断裂带")
        self.assertEqual(clean_zh("<非正式>你在逗我吧？"), "你在逗我吧？")

    def test_templates_with_sb_or_sth_are_not_examples(self):
        # reviewers: "sb" stands in for "somebody" as "~" does for the headword
        self.assertEqual(judge("give a florp to sb.", "给某人一个弗洛普").reason, "a template with placeholders (sb/sth)")

    def test_a_gloss_after_a_sentence_is_not_its_translation(self):
        # a sentence-like definition followed by the headword's glosses
        self.assertEqual(judge("If a kettle sings, it whistles as it boils.", "（水壶）鸣响；呜呜叫").reason,
                         "a gloss, not a translation")
        self.assertTrue(judge("...the trouble with moths and beetles.", "虫害").ok)       # a phrase-like translation
        self.assertTrue(judge("garden/kitchen/office tools", "园艺工具；厨房工具；办公工具").ok)  # a phrase: not judged so
        self.assertTrue(judge("Pip was hungry; he wanted soup now.", "皮普饿了；他想喝汤。").ok)

    def test_the_exact_key_ignores_spacing_in_chinese(self):
        self.assertEqual(exact_key("Our kitten arrived on 4th December.", "我们的小猫是 12 月 4 号来的。"),
                         exact_key("Our kitten arrived on 4th December.", "我们的小猫是12月4号来的。"))

    def test_a_bracketed_label_is_not_a_translation(self):
        v = judge("If a florp glows, it shines a faint green.", "【语法信息】")
        self.assertEqual(v.reason, "a label, not a translation")
        self.assertEqual(judge("Grelt means a small grey pebble.", "【STYLE 标签】：LITERARY 文").reason,
                         "a label, not a translation")

    def test_translated_definitions_are_not_examples(self):
        self.assertEqual(judge("A sleepy florp town of northern Florpland near Grelton.",
                               "弗洛普镇：弗洛普兰北部的小集镇。").reason, "a translated definition, not an example")
        self.assertEqual(judge("To tap softly, using a spoon.", "敲，叩：用勺子轻轻地敲。").reason,
                         "a translated definition, not an example")
        # dialogue labels, reported speech and ordinary colons are part of examples
        self.assertTrue(judge("A: Is the florp awake? B: No, not yet.", "甲：弗洛普醒了吗？乙：还没有。").ok)
        self.assertTrue(judge("'I left the florp outside,' she said quietly.", "她小声地说：“我把弗洛普留在外面了。”").ok)
        self.assertTrue(judge("Friends and neighbours, the market opens now.", "朋友们，邻居们：集市现在开张了。").ok)
        self.assertTrue(judge("Pip shouted: 'The bus is here!'", "皮普喊道：“公交车来了！”").ok)
        self.assertTrue(judge("Pip lifted his mug slowly. 'To the cooks.'", "皮普举起杯子： “敬厨师们！”").ok)

    def test_reviewer_found_apparatus_is_rejected(self):
        cases = {
            ("Pip bought a ~ of cheese at the market.", "皮普在集市上买了一块奶酪。"): "a placeholder for the headword",
            ("hold sb. to a bargain", "让某人遵守约定"): "a template with placeholders (sb/sth)",
            ("Florp, open the jar. or Florp, try the jar.", "弗洛普，把罐子打开。"): "alternative versions",
            ("The fog has lifted. / The fog has cleared.", "雾散了。"): "alternative versions",
            ("a kettle of (or with) florp handles", "带弗洛普把手的水壶"): "alternative versions",
            ("Pip is a lark, ie he wakes very early.", "皮普是个早起的人，他醒得很早。"): "an explanatory note (ie/eg)",
            ("Pip baked two or three pies that week.", "那周皮普烤了［不止一两个］馅饼。"): "apparatus in the Chinese",
            ("They kept warm links with the florp guild.", "SYNONYM 同义词 他们和弗洛普行会关系密切。"): "apparatus in the Chinese",
            ("The map was right in every detail. } &amp;b{.", "地图的每个细节都是对的。"): "markup in text",
            ("Festina lente is the old motto.", "〈拉〉欲速则不达。"): "the Latin-script side is not English",
        }
        for (en, zh), reason in cases.items():
            self.assertEqual(judge(en, zh).reason, reason, en)

    def test_reviewer_found_apparatus_is_removed(self):
        self.assertEqual(clean_en("Pip was mangling [=twisting] the tune again."), "Pip was mangling the tune again.")
        self.assertEqual(clean_en("Pip dropped [with obj.] the teapot by accident."), "Pip dropped the teapot by accident.")
        self.assertEqual(clean_en("Pip was snowed under (ie he had a florp to finish) that month."), "Pip was snowed under that month.")
        self.assertEqual(clean_en("g) Rang the bell for supper."), "Rang the bell for supper.")
        self.assertEqual(clean_en("[VN -ing] Pip could hear the kettle whistling softly."),
                         "Pip could hear the kettle whistling softly.")
        self.assertEqual(clean_en("[U] Grelt is good for baking."), "Grelt is good for baking.")
        # after a bullet, and chained with a register label
        self.assertEqual(clean_en("◆ [VN] (figurative) I was juggling soup and the laundry."),
                         "I was juggling soup and the laundry.")
        self.assertEqual(clean_en("(informal) Pass me that spoon, will you?"), "Pass me that spoon, will you?")
        for code in ("[V (that)]", "[V +adv./prep.]", "[VN, usually +adv./prep.]", "[C, usually sing.]", "[NOTE]"):
            self.assertEqual(clean_en(f"{code} Pip promised to bake florp pies."), "Pip promised to bake florp pies.", code)
        # brackets that only highlight words inside the sentence go; the words stay
        self.assertEqual(clean_en("[Of course] the florp may stay."), "Of course the florp may stay.")
        self.assertEqual(clean_en("[Quiet] patience kept them going."), "Quiet patience kept them going.")
        self.assertEqual(clean_en("[Of course] I fixed the gate."), "Of course I fixed the gate.")
        self.assertEqual(clean_en("[Last week], the florp turned green."), "Last week, the florp turned green.")
        self.assertEqual(clean_en("[Laughter] Nobody saw that coming."), "[Laughter] Nobody saw that coming.")  # not a code
        self.assertEqual(clean_en("8 He keeps florp pickles."), "He keeps florp pickles.")
        self.assertEqual(clean_en("12 The gate creaked loudly."), "The gate creaked loudly.")
        self.assertEqual(clean_en("◆ 2 A nine-page florp report is due soon."), "A nine-page florp report is due soon.")
        self.assertEqual(clean_en("1 May I borrow the florp, please?"), "May I borrow the florp, please?")

    def test_text_that_only_looks_like_apparatus_stays(self):
        # a quantity is not a sense number, a minus sign or currency is not a bullet
        self.assertEqual(clean_en("3 Canadians joined the picnic yesterday."), "3 Canadians joined the picnic yesterday.")
        self.assertEqual(clean_en("-5 degrees is far too chilly."), "-5 degrees is far too chilly.")
        self.assertEqual(clean_en("$20 is steep for a kite."), "$20 is steep for a kite.")
        self.assertEqual(clean_en("- I think Pip is joking."), "I think Pip is joking.")  # a dash bullet still goes
        self.assertEqual(clean_zh("-5度太冷了。"), "-5度太冷了。")
        self.assertEqual(clean_zh("￥20太贵了。"), "￥20太贵了。")
        # "(as ...)" is a grammar label only when it names a part of speech
        self.assertEqual(clean_en("(as usual) Pip turned up late."), "(as usual) Pip turned up late.")
        self.assertEqual(clean_en("(also as noun) a cracked teacup"), "a cracked teacup")
        self.assertEqual(clean_en("(as modifier) a ferry company"), "a ferry company")
        # ...and the form it names, if any, is the one the example uses
        self.assertEqual(clean_en("(as plural noun the bold) the bold get lucky"), "the bold get lucky")
        self.assertEqual(clean_en("(as adjective, with submodifier crafted) a neatly crafted box"),
                         "a neatly crafted box")
        self.assertEqual(clean_en("(as adjective, in combination -lit) a candlelit kitchen"), "a candlelit kitchen")
        for sentence in ("(as singular as it sounds) Pip turned up late.", "(as plural as they come) Florps honked.",
                         "(as noun phrases go) Mine is quite tidy.", "(prep school) Pip liked every hour of it."):
            self.assertEqual(clean_en(sentence), sentence)
        self.assertEqual(judge("(as singular as it sounds) Pip turned up late.", "（听起来很奇特）皮普迟到了。").kind, "sentence")
        self.assertEqual(judge("(as usual) Pip turned up late.", "皮普照例来晚了。").kind, "sentence")
        self.assertEqual(clean_zh("②他钓鱼钓得很好。"), "他钓鱼钓得很好。")
        # word-level alternatives and optional words stay
        self.assertTrue(judge("Pip waved/nodded to the florp guests at the gate.", "皮普在大门口向弗洛普客人招手。").ok)
        self.assertTrue(judge("Quite (so), the florp needs salt.", "的确，弗洛普需要盐。").ok)
        self.assertTrue(judge("3 people joined the picnic yesterday.", "昨天有3个人来野餐。").ok)

    def test_a_sign_in_front_of_a_number_is_text_whatever_the_sign(self):
        # by what the character is (a sign, a currency), not by a list of them
        for text in ("－5 degrees is far too chilly.", "−5 degrees is far too chilly.", "＋5 degrees is mild for March.",
                     "±2 degrees is the tolerance.", "￡20 is steep for a kite.", "＄20 is steep for a kite.",
                     "₩500 buys one of them.", "<5 people joined the picnic.", "＃1 is always the favourite.", "-.5 is the average."):
            self.assertEqual(clean_en(text), text)
        for text in ("－5度太冷了。", "±2度是公差。", "￡20太贵了。", "₩500一个。", "＋5度算温和。"):
            self.assertEqual(clean_zh(text), text)
        self.assertTrue(judge("－5 degrees is far too chilly.", "－5度太冷了。").ok)
        # a dash, a plus or an arrow before anything else is still a bullet
        for bullet in ("－", "–", "+", "→", "＝"):
            self.assertEqual(clean_en(f"{bullet} I think Pip is joking."), "I think Pip is joking.", bullet)
        self.assertEqual(clean_zh("→皮普在开玩笑。"), "皮普在开玩笑。")
        self.assertEqual(clean_en("→5 people joined the picnic."), "5 people joined the picnic.")  # an arrow is no sign

    def test_a_number_before_a_noun_that_looks_like_a_function_word_is_a_quantity(self):
        # the letter A, shown by a plural agreeing with the number; the month May
        for text in ("3 A grades are needed for florp class.", "2 A levels were enough for the class.",
                     "25 May is a florp holiday in Florpland.", "11 May, a florp holiday, fell on a Tuesday."):
            self.assertEqual(clean_en(text), text)
        self.assertTrue(judge("3 A grades are needed for florp class.", "弗洛普课需要3个A。").ok)
        # a sense number before the same words
        self.assertEqual(clean_en("5 A bundle of florps came with the parcel."), "A bundle of florps came with the parcel.")
        self.assertEqual(clean_en("2 An odd glow hung above the florp."), "An odd glow hung above the florp.")

    def test_the_translation_tells_a_letter_or_a_month_from_a_function_word(self):
        # a letter is kept in the Chinese, whatever the verb; a date has its month there
        for en, zh in (("3 A grades won Pip a florp award.", "3个A等成绩为皮普赢得了弗洛普奖。"),
                       ("2 A pupils won the cup this spring.", "两名Ａ等生今年春天赢得了奖杯。"),
                       ("25 May is a florp holiday in Florpland.", "5月25日在弗洛普兰是弗洛普节。"),
                       ("1 May we all met by the pond.", "五月一日我们都在池塘边见了面。"),
                       ("1 May, kept as Florp Day, means no school.", "五一弗洛普节不用上学。"),
                       ("1 May 1987 saw the florp shop open.", "弗洛普店于1987年的那一天开张。")):
            self.assertEqual(clean_en(en, zh), en, en)
            self.assertEqual(judge(en, zh).kind, "sentence", en)
        # a word joined to the next by a hyphen is not a function word
        for text in ("3 A-levels were enough for the class.", "2 I-beams hold up the whole shed."):
            self.assertEqual(clean_en(text), text)
            self.assertEqual(clean_en(text, "两根工字梁撑起了整个棚子。"), text)
        # sense numbers: the letter in the Chinese is the one the rest of the English has, or none
        for en, zh, clean in (("1 I read Volume I last spring.", "我去年春天读了第I卷。", "I read Volume I last spring."),
                              ("1 A woman bought a type A kite.", "一个女人买了一只A型风筝。", "A woman bought a type A kite."),
                              ("2 A bundle of florps came with it.", "随附一捆弗洛普。", "A bundle of florps came with it."),
                              ("1 May we feed the florp now?", "我们现在可以喂弗洛普了吗？", "May we feed the florp now?"),
                              ("1 May I borrow the florp, please?", "我可以借用弗洛普吗？", "May I borrow the florp, please?")):
            self.assertEqual(clean_en(en, zh), clean, en)

    def test_a_sign_before_a_currency_amount_is_text(self):
        # the number after a sign may start with currency signs or be another numeral
        for text in ("-$5 is the florp balance in my jar.", "-£5 is what I owe Pip.", "+€3 was the change Pip got.",
                     "−½ cup is too little for this.", "-$.50 is the fee per ride."):
            self.assertEqual(clean_en(text), text)
            self.assertTrue(judge(text, "这是一个足够长的中文翻译句子。").ok, text)
        for text in ("－＄5是我罐子里的余额。", "-€3是找的零钱。"):
            self.assertEqual(clean_zh(text), text)
        # a sign before a sign before a number: the first is a bullet; a sign and a space, a list
        self.assertEqual(clean_en("-- 5 people joined the picnic."), "5 people joined the picnic.")
        self.assertEqual(clean_en("- $5 is the fee per ride."), "$5 is the fee per ride.")
        self.assertEqual(clean_en("+ I think Pip is joking."), "I think Pip is joking.")

    def test_a_parenthesis_is_a_grammar_label_only_in_the_label_grammar(self):
        # comparisons, clauses and phrases that only start like a label are part of the sentence
        for sentence in ("(as singular as it sounds) Pip spelt florp just as it sounds.",
                         "(as plural as they come) Each florp was as plural as they come.",
                         "(as noun phrases go) These noun phrases go unnoticed.",
                         "(as a verb of motion) The word motion is a noun.",
                         "(as adjective as it gets) This sentence is as adjective as it gets.",
                         "(as nouns go) Nouns go first here."):
            self.assertEqual(clean_en(sentence), sentence)
        # every shape of form the dictionaries use
        for label, rest in (("(as noun telling off)", "Pip got a telling off at the florp market"),
                            ("(as noun grelt and florp)", "a week of grelt and florp in town"),
                            ("(as plural noun the sleepy)", "a quiet corner kept for the sleepy"),
                            ("(as adjective, with submodifier crafted)", "a lovingly crafted stool"),
                            ("(as modifier usually ferry)", "a ferry timetable"),
                            ("(as noun knitting)", "knitting's appeal grew again"),
                            ("(as adjective, with submodifier planned)", "a well-planned florp party"),
                            ("(as a noun)", "a loud thump upstairs")):
            self.assertEqual(clean_en(f"{label} {rest}"), rest, label)
        # the form must be a word of the example, not part of one
        self.assertEqual(clean_en("(as noun ring) they sang during the evening"), "(as noun ring) they sang during the evening")

    def test_etymology_is_not_an_example(self):
        self.assertEqual(judge("[Fr < Ital grelto pot metal < ? from the old port.", "意大利地名，以产陶器著称。").reason,
                         "etymology")
        self.assertTrue(judge("Pip noted that 3 < 5 holds for florps.", "皮普指出3小于5对弗洛普也成立。").ok)

    def test_a_single_word_is_a_gloss_not_an_example(self):
        self.assertEqual(judge("grelton.", "格尔顿石").reason, "a single word, not an example")
        self.assertEqual(judge("sky-blue", "天蓝色的").reason, "a single word, not an example")
        self.assertTrue(judge("wet socks", "湿袜子").ok)

    def test_garbled_text_is_rejected(self):
        self.assertEqual(judge("Florp the grelt, [`fl\x03r\x10p\x01] they said.", "他们说，把格尔特弄平。").reason,
                         "garbled text")

    def test_notes_about_words_are_not_examples(self):
        # the word under discussion reappears, untranslated, in the Chinese
        self.assertEqual(judge("Grelt covers big and tiny pebbles alike.",
                               "grelt 既可指大卵石也可指小卵石。").reason, "a note about a word, not an example")
        self.assertEqual(judge("It goes ahead of florp names.", "florp 用在弗洛普名称之前。").reason,
                         "a note about a word, not an example")
        self.assertEqual(judge("Loud drilling ruined the picnic. Togrelt is to dull its shine.",
                               "大声的钻孔声毁了野餐。 grelt 是使其失去光泽。").reason, "a note about a word, not an example")
        self.assertEqual(judge("Pip coaxed her into joining the choir. Toflorp is to lure by humming.",
                               "皮普哄她加入了合唱团。 Florp 意为用哼唱引诱。").reason, "a note about a word, not an example")
        self.assertTrue(judge("Tom is my oldest friend from school.", "Tom 是我上学时最老的朋友。").ok)  # a name, not a note
        # acronyms and names carried over are ordinary translation
        self.assertTrue(judge("All our kettles carry the CE mark now.", "我们所有的水壶现在都带有 CE 标志。").ok)
        self.assertTrue(judge("Lena's aunt lives in Palm Springs now.", "莉娜的姑姑现在住在 Palm Springs。").ok)

    def test_english_with_loanwords_and_citations_is_english(self):
        for en in ["Pip and Lena had a tête-à-tête over the soup.", "the crème de la crème of village bakers",
                   "research by Grelt et al., 2019", "Kettle £15 o.n.o."]:
            self.assertTrue(judge(en, "他们边喝汤边促膝谈心。").ok, en)

    def test_the_cjk_side_must_be_chinese_not_japanese_or_korean(self):
        self.assertEqual(judge("Mira opened the kitchen window.", "ミラは台所の窓を開けました。").reason,
                         "Japanese or Korean on the Chinese side")
        self.assertEqual(judge("Mira opened the kitchen window.", "미라는 부엌 창문을 열었다。").reason,
                         "Japanese or Korean on the Chinese side")

    def test_whitespace_is_tidied_but_text_kept(self):
        self.assertTrue(judge("  Mira  opened the kitchen window. ", " 米拉打开了厨房的窗户。 ").ok)


class Keys(unittest.TestCase):
    def test_exact_key_ignores_case_width_quotes_spacing_and_script(self):
        a = exact_key("Pip said “It’s done” — honestly.", "皮普说：“做完了。”")
        b = exact_key("pip said \"It's done\" - honestly.", "皮普說：“做完了。”")  # traditional, straight quotes, hyphen
        self.assertEqual(a, b)
        self.assertEqual(exact_key("ＡＢＣ word.", "中文"), exact_key("abc word.", "中文"))

    def test_loose_key_also_ignores_punctuation(self):
        self.assertNotEqual(exact_key("Wait, please.", "请等一下。"), exact_key("Wait please!", "请等一下！"))
        self.assertEqual(loose_key("Wait, please.", "请等一下。"), loose_key("Wait please!", "请等一下！"))

    def test_translation_variants_share_the_english_key_only(self):
        self.assertEqual(en_key("Mira opened the kitchen window."), en_key("mira opened the kitchen window"))
        self.assertNotEqual(loose_key("Mira opened the kitchen window.", "米拉打开了厨房的窗户。"),
                            loose_key("Mira opened the kitchen window.", "米拉把厨房的窗户打开了。"))


if __name__ == "__main__":
    unittest.main()
