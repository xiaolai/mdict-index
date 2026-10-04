"""COBUILD (Overhaul build) parser on a synthetic entry that mirrors its markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import cobuild

HTML = """
<link href="colcobuildstyle.css" rel="stylesheet" type="text/css"><script src="colcobuildoverhaul_switch.js"></script>
<div class="collinsbody"><a name="cobuild_x"></a><div class="word_entry">
 <span class="word_key">florp</span>
 <div class="word-frequency-img" title="Rare"><span class="level level1 roundRed"></span></div>
 <span class="pron"><a href="sound://COLmp3/1.mp3"> <span class="pron type_uk">fl<span class="hi rend-u">ɒ</span>p </span> <span class="icon-speak-uk">\ue027</span></a>
  <a href="sound://COLmp3/en_us_florp.mp3"> <span class="pron type_us">ˈflɑrp </span> <span class="icon-speak-us">\ue027</span></a></span>
 <div class="form_inflected"><span class="also">(also <span>florpe</span>)</span><span class="form inflected_forms type-infl"><span class="var">Word forms: </span>
  <span class="lbl type-gram">plural</span> <a class="orth" href="sound://COLmp3/2.mp3"> florps<span class="icon-speak-form">\ue027</span></a></span></div>
</div>
<div name="collins_cobuild_x"><div class="tab_content tab_content_tab_3"><div class="part_main"><div class="collins_content">
 <div class="collins_en_cn example"><div class="caption hide_cn"><a class="anchor" name="florp_1"></a><span class="num">1</span>
   <span class="st" title="可数名词">N-COUNT </span>
   <span class="def_cn cn_before"><span class="chinese-text">弯铜勺</span></span> A <b>florp</b> is a   bent copper ladle.
   <span class="def_cn cn_after"><span class="chinese-text">弯铜勺</span></span>
   <span class="tips_box"><span class="lbl type-register"><span class="span"> [</span>informal<span class="span">]</span></span></span></div>
  <ul><li><p>Mira stirred the jam with a <span class="text_blue">florp</span>. <span class="tips_sentence"><span class="span">[</span>+ with<span class="span">]</span></span><a class="tts_button"> </a></p>
       <p><span class="chinese-text">米拉用弯铜勺搅果酱。</span></p></li></ul>
  <div class="synonym"><b>SYN</b><span class="form"><a class="ref explain" href="entry://spoon">NOT A SENSE</a></span></div>
 </div>
 <div class="note type-sense example"><b>Florp</b> is also a verb.<span class="text_blue"></span>
  <ul class="vli"><li><p>He florped the soup.<a class="tts_button"> </a></p><p><span class="chinese-text">他搅了汤。</span></p></li></ul></div>
 <div class="collins_en_cn example"><div class="caption hide_cn"><a class="anchor" name="florp_2"></a><span class="num">2</span>
   <span class="st">PHRASE</span><span class="def_cn cn_before"><span class="chinese-text">瞎忙</span></span>
   If you <b>florp the pot</b>, you fuss over nothing.<span class="def_cn cn_after"><span class="chinese-text">瞎忙</span></span></div><ul></ul></div>
 <div class="collins_en_cn example"><div class="caption hide_cn"><a class="anchor" name="florp_3"></a><span class="num">3</span>
   <span class="st">PHRASAL VERB</span><span class="def_cn cn_before"><span class="chinese-text">搅起</span></span>
   If you <b>florp</b> something <b>up</b>, you stir it hard.<span class="def_cn cn_after"><span class="chinese-text">搅起</span></span></div><ul></ul></div>
 <div class="collins_en_cn example"><div class="caption hide_cn"><a class="anchor" name="florp_4"></a><span class="num">4</span>
   <span class="def_cn cn_before"></span>to florp the waters <span class="text_gray">→see:</span><b class="text_blue"><a class="explain" href="entry://water">water</a></b>
   <span class="def_cn cn_after"></span></div><ul></ul></div>
 <div class="note type-drv example"><a class="anchor" name="florpish"></a><b class="text_blue">florpish</b>
  <ul><li><p>A florpish grin.<a class="tts_button"> </a></p><p><span class="chinese-text">一个傻笑。</span></p></li>
   <li class="note type-phrase example hide_cn">If you are <b>all florpish</b>, you are silly.<span class="def_cn"><span class="chinese-text">傻乎乎的</span></span></li></ul></div>
 <div class="note type-usage no-before example"><strong class="text_gray">Usage Note</strong>:<ul><li><p>USAGE NOTE TEXT</p></li></ul></div>
 <div class="collins_en_cn grammarInfo addon folded"><div class="caption"><div class="cc_addon_text">Thesaurus</div></div>
  <div class="gInfoContent"><p class="block">THESAURUS WORD</p></div></div>
 <div class="collins_en_cn addon trend folded"><div class="caption"><div class="cc_addon_text">Trends of <b>florp</b></div></div>
  <div class="trendContent"><div class="trendChart" data-frequencydata="1:2"></div></div></div>
</div></div></div></div></div>"""


class CobuildParser(unittest.TestCase):
    def setUp(self):
        self.e = cobuild.parse("florp", HTML)

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, cobuild.COVERS))

    def test_headword_pos_and_forms(self):
        self.assertEqual((self.e.headword, self.e.homograph), ("florp", ""))
        self.assertEqual(self.e.pos, ("N-COUNT", "PHRASAL VERB"))
        self.assertEqual(self.e.forms, ("florpe", "florps"))  # no icon-font glyph

    def test_prons_with_region_and_audio(self):
        self.assertEqual([(p.region, p.ipa, p.audio) for p in self.e.prons],
                         [("uk", "flɒp", "sound://COLmp3/1.mp3"), ("us", "ˈflɑrp", "sound://COLmp3/en_us_florp.mp3")])

    def test_bilingual_sense_with_labels_and_examples(self):
        s = self.e.senses[0]
        self.assertEqual((s.kind, s.number, s.pos, s.labels), ("sense", "1", "N-COUNT", ("informal",)))
        self.assertEqual((s.definition, s.definition_zh), ("A florp is a bent copper ladle.", "弯铜勺"))
        self.assertEqual([(x.text, x.text_zh, x.labels) for x in s.examples],
                         [("Mira stirred the jam with a florp.", "米拉用弯铜勺搅果酱。", ("+ with",))])  # pattern is a label
        self.assertEqual(self.e.senses[1].examples[0].labels, ())

    def test_also_a_verb_note_is_a_sense(self):
        s = self.e.senses[1]
        self.assertEqual((s.kind, s.definition, s.examples[0].text_zh), ("sense", "Florp is also a verb.", "他搅了汤。"))

    def test_phrase_and_phrasal_verb(self):
        phrase, phrasal = self.e.senses[2], self.e.senses[3]
        self.assertEqual((phrase.kind, phrase.phrase, phrase.definition_zh), ("phrase", "florp the pot", "瞎忙"))
        self.assertEqual((phrasal.kind, phrasal.phrase, phrasal.pos), ("phrasal_verb", "florp … up", "PHRASAL VERB"))

    @staticmethod
    def _caption(inner: str, st: str = "PHRASE") -> str:
        return ('<div class="collinsbody"><div class="word_entry"><span class="word_key">florp</span></div>'
                '<div class="collins_content"><div class="collins_en_cn example"><div class="caption hide_cn">'
                f'<span class="num">1</span> <span class="st">{st}</span> '
                f'<span class="def_cn cn_before"><span class="chinese-text">搅</span></span>{inner}</div><ul></ul></div></div></div>')

    def _phrase_of(self, inner: str) -> str:
        (s,) = cobuild.parse("florp", self._caption(inner)).senses
        return s.phrase

    def test_alternative_phrases_are_kept_apart(self):
        self.assertEqual(self._phrase_of("If something is <b>florp down</b>, it is low. If it is <b>florp up</b>, it is high."),
                         "florp down | florp up")
        self.assertEqual(self._phrase_of("If you <b>keep</b> your <b>florps off</b> a jar or <b>take</b> your <b>florps off</b> it, the jam is safe."),
                         "keep … florps off | take … florps off")

    def test_and_between_whole_phrases_and_a_same_as_reference(self):
        self.assertEqual(self._phrase_of("You use <b>any florp at all</b> and <b>some florp at all</b> to refer to spoons."),
                         "any florp at all | some florp at all")
        self.assertEqual(self._phrase_of("If you <b>florp</b> and <b>dine</b> someone, you bake them a pie."), "florp and dine")
        self.assertEqual(self._phrase_of("<b>Florp off</b> means the same as <b>florpen off</b> ."), "Florp off")
        self.assertEqual(self._phrase_of("<b>Florp your back</b> means the same as florp your <b>rear</b>."), "Florp your back")
        self.assertEqual(self._phrase_of("To <b>florp off</b> means to <b>leave</b>."), "florp off")
        self.assertEqual(self._phrase_of("To <b>florp a damper on</b> a thing means the same as to <b>florp a dampener on</b> it."),
                         "florp a damper on | florp a dampener on")

    def test_an_inflected_repeat_of_the_phrase_is_not_an_alternative(self):
        self.assertEqual(self._phrase_of("If you <b>florp down</b>, or if someone <b>florps</b> you <b>down</b>, you rest."),
                         "florp down")
        self.assertEqual(self._phrase_of("If you <b>florp</b> someone or something <b>out</b>, you stir them."), "florp … out")
        self.assertEqual(self._phrase_of("If you <b>florp up</b> a thing or if it <b>florps up</b>, it rises."), "florp up")
        self.assertEqual(self._phrase_of("If a thing <b>takes the florp</b> or <b>takes</b> all <b>the florp</b>, it wins."),
                         "takes the florp")

    def test_a_comma_inside_one_printed_phrase_does_not_split_it(self):
        # Bold runs joined only by a comma are one phrase ("year in, year out") unless the commas list
        # alternatives: a list is closed by "or"/"and" before a further bold, ends "and so on", or follows "such as".
        self.assertEqual(self._phrase_of("When Mira calls a gadget <b>all-florping</b> ,<b>all-dancing</b>, she likes its buttons."),
                         "all-florping all-dancing")
        self.assertEqual(self._phrase_of("If it happens <b>florp in</b> ,<b>florp out</b>, it happens every florp."),
                         "florp in florp out")
        self.assertEqual(self._phrase_of("<b>to all florps</b> ,<b>from all florps</b>, or <b>by all florps</b> means so."),
                         "to all florps | from all florps | by all florps")
        self.assertEqual(self._phrase_of("Expressions such as <b>a florp</b> ,<b>one florp</b> ,<b>not a florp</b> are used."),
                         "a florp | one florp | not a florp")
        self.assertEqual(self._phrase_of("If it happens <b>twice florp</b> ,<b>three times florp</b> and so on, it recurs."),
                         "twice florp | three times florp")
        self.assertEqual(self._phrase_of("You use <b>the next florp</b> or such as '<b>one florp</b> the cat sat here<b>, the next</b> "
                                         "it fled'."), "the next florp | one florp …, the next")

    def test_or_before_a_new_clause_starts_an_alternative(self):
        # "or" right after a bold, or "or" + a clause word, starts another phrase; "or" between the
        # words filling a slot ("someone or something") does not, nor does a particle closing the phrase.
        self.assertEqual(self._phrase_of("If a teapot is knocked <b>off the florp of the earth</b> or rolls "
                                         "<b>from the florp of the earth</b>, nobody finds it."),
                         "off the florp of the earth | from the florp of the earth")
        self.assertEqual(self._phrase_of("If geese <b>florp out of</b> a pond or if their keeper <b>pulls</b> them "
                                         "<b>out</b>, they waddle off."), "florp out of | pulls … out")
        self.assertEqual(self._phrase_of("If you <b>give</b> someone or something <b>a wide florp</b>, you walk round it."),
                         "give … a wide florp")
        self.assertEqual(self._phrase_of("If you <b>florp yourself</b> or a shed <b>up</b>, it looks neat."), "florp yourself … up")

    def test_alternatives_share_the_words_around_the_part_that_varies(self):
        # Coordinated bold runs are the varying part of one phrase: a one-word alternative takes the words after
        # the last alternative's first word and before the first alternative's last word (as "be/go out like a light").
        self.assertEqual(self._phrase_of("If a letter <b>florps</b> or <b>puts the seal on</b> a deal, the deal is done."),
                         "florps the seal on | puts the seal on")
        self.assertEqual(self._phrase_of("If you <b>put</b> ,<b>bring</b>, or <b>carry</b> a scheme or wish <b>into florp</b>, "
                                         "it comes about."), "put … into florp | bring … into florp | carry … into florp")
        self.assertEqual(self._phrase_of("If you are <b>on the florp of</b> your <b>seat</b> or <b>chair</b>, you gape."),
                         "on the florp of … seat | on the florp of … chair")
        self.assertEqual(self._phrase_of("If you <b>place</b> one cake <b>above</b> ,<b>before</b>, or <b>over</b> a pie, "
                                         "you rank it higher."), "place … above | place … before | place … over")
        # a list printed inside one bold run and closed by "or" lists alternatives too
        self.assertEqual(self._phrase_of("If Tomas <b>is called, held</b>, or <b>brought to florp</b> for the mess, he explains."),
                         "is called to florp | is held to florp | is brought to florp")
        self.assertEqual(self._phrase_of("If a cart <b>comes</b> or <b>grinds to a florp</b> or <b>is brought to a florp</b>, "
                                         "the mule rests."), "comes to a florp | grinds to a florp | is brought to a florp")
        # whole alternatives (none of one word, or one word that only repeats its neighbour) share nothing
        self.assertEqual(self._phrase_of("If you <b>take florp</b> or <b>take a florp in</b> knitting, you smile."),
                         "take florp | take a florp in")
        self.assertEqual(self._phrase_of("<b>In the florptime</b> or <b>florptime</b> means meanwhile."),
                         "In the florptime | florptime")

    def test_a_frame_and_a_slot_possessive_are_read_as_one_phrase(self):
        # "as … as can be": a lone word the next run repeats across a slot word is not an alternative of its own;
        # the words a phrase leaves out between its runs are a slot, "…"
        self.assertEqual(self._phrase_of("If Mo is <b>as</b> happy <b>as can florp</b> or <b>as</b> quiet "
                                         "<b>as could florp</b>, he hums."), "as … as can florp | as … as could florp")
        # the possessive "'s" printed in bold after a slot word goes with the slot word (both are the slot)
        self.assertEqual(self._phrase_of("If you are <b>under</b> someone<b>'s florp</b>, you follow them about."), "under … florp")
        # "and" printed inside one phrase is kept; after a phrase with a slot it starts the next phrase
        self.assertEqual(self._phrase_of("If you <b>wine</b> and <b>florp</b> someone, you bake them a pie."), "wine and florp")
        self.assertEqual(self._phrase_of("If you <b>laugh</b> your <b>florp off</b> and <b>scream</b> your <b>florp off</b>, "
                                         "you make a racket."), "laugh … florp off | scream … florp off")
        # the word mentioned before "in expressions such as" is not part of the expressions
        self.assertEqual(self._phrase_of("Mira says <b>florp</b> in expressions such as <b>to be florp</b> or "
                                         "<b>let's be florp</b>."), "florp | to be florp | let's be florp")
        self.assertEqual(self._phrase_of("If the parcel comes <b>in</b> a week<b>'s florp</b> or <b>in</b> two weeks<b>' florp</b>, "
                                         "Mo waits."), "in … florp")

    def test_a_see_pointer_takes_the_whole_phrase_printed_since_the_last_boundary(self):
        # the phrase may be bold runs with slot words between them, or plain words of any length after a
        # sentence end or after the separator of the pointer before it
        html = self._caption('If you <b>florp yourself for</b> a swim, you stretch first. to <b>florp</b> your <b>loins</b>'
                             '<span class="text_gray" style="font-weight:bold;">→see: </span>'
                             '<b class="text_blue"><a class="explain" href="entry://loin">loin</a></b>; ', st="VERB")
        (s,) = cobuild.parse("florp", html).senses
        self.assertEqual(s.definition, "If you florp yourself for a swim, you stretch first.")
        html = self._caption('If a hat <b>florps out</b>, everyone sees it. to <b>florp out a mile</b>'
                             '<span class="text_gray">→see: </span><b class="text_blue"><a class="explain" '
                             'href="entry://mile">mile</a></b>; to florp out like a very sore green thumb'
                             '<span class="text_gray">→see: </span><b class="text_blue"><a class="explain" '
                             'href="entry://thumb">thumb</a></b>; ', st="PHRASAL VERB")
        (s,) = cobuild.parse("florp", html).senses
        self.assertEqual((s.phrase, s.definition), ("florps out", "If a hat florps out, everyone sees it."))
        # plain words opening the caption, with no boundary before them, are the definition ("vide supra →see: vide")
        html = self._caption('florp supra <span class="text_gray">→see:</span><b class="text_blue"><a class="explain" '
                             'href="entry://supra">supra</a></b>', st="ABBREVIATION")
        (s,) = cobuild.parse("florp", html).senses
        self.assertEqual(s.definition, "florp supra")
        # a caption of pointers only is a cross-reference even with a gloss: "见" ("see") translates them
        html = self._caption('to <b>florp</b> your <b>lips</b> <span class="text_gray">→see: </span><b class="text_blue">'
                             '<a class="explain" href="entry://lip">lip</a></b>&nbsp; to florp into shape'
                             '<span class="text_gray">→see: </span><b class="text_blue"><a class="explain" '
                             'href="entry://shape">shape</a></b>&nbsp; ', st="").replace("搅", "见")
        self.assertEqual(cobuild.parse("florp", html).senses, ())

    def test_see_also_links_go_whatever_stands_between_them_and_the_marker(self):
        html = self._caption('<span class="st">See also:</span><span class="tips_box"><span class="lbl type-syntax">'
                             '<span class="span"> [</span>no cont<span class="span">]</span></span></span> '
                             '<b class="text_blue"><a class="explain" href="entry://florplet">florplet</a></b>&nbsp; '
                             '<b class="text_blue"><a class="explain" href="entry://florped">florped</a></b>&nbsp; '
                             'If one person <b>florps</b> another, they stir.', st="VERB")
        (s,) = cobuild.parse("florp", html).senses
        self.assertEqual((s.definition, s.labels), ("If one person florps another, they stir.", ("no cont",)))

    def test_a_reference_only_caption_is_not_a_sense(self):
        html = self._caption("", st="See also:").replace(
            "</div><ul>", '<b class="text_blue"><a class="explain" href="entry://florped">florped</a></b>&nbsp; '
                          '<b class="text_blue"><a class="explain" href="entry://florp and tear">florp and tear</a></b>. </div><ul>'
        ).replace('<span class="def_cn cn_before"><span class="chinese-text">搅</span></span>', "")
        e = cobuild.parse("florp", html)
        self.assertEqual((e.senses, e.stub), ((), "xref"))

    def test_a_pointer_takes_its_phrase_and_separator_with_it(self):
        html = self._caption('When a thing happens <b>florp</b> a wall, it is wide. <b>florp the board</b>'
                             '<span class="text_gray" style="font-weight:bold;">→see: </span>'
                             '<b class="text_blue"><a class="explain" href="entry://board">board</a></b>; ', st="PREP")
        (s,) = cobuild.parse("florp", html).senses
        self.assertEqual(s.definition, "When a thing happens florp a wall, it is wide.")
        plain = self._caption('A <b>florp</b> is a crooked tin ladle. ballpoint florp<span class="text_gray">→see: </span>'
                              '<b class="text_blue"><a class="explain" href="entry://ballpoint">ballpoint</a></b>; to '
                              '<b>oil the florp</b><span class="text_gray">→see: </span>'
                              '<b class="text_blue"><a class="explain" href="entry://oil">oil</a></b>; ', st="N-COUNT")
        (s,) = cobuild.parse("florp", plain).senses
        self.assertEqual(s.definition, "A florp is a crooked tin ladle.")

    def test_only_a_see_pointer_names_a_phrase_before_it(self):
        # A usage-note or see-also pointer is about the whole definition: the words before it are definition text.
        html = self._caption('<b>Florp</b> counts drumbeats. Its sign is a tiny florplet <span class="text_gray">→see usage note at:</span> '
                             '<b class="text_blue"><a class="explain" href="entry://heat">heat</a></b>', st="ADJ")
        (s,) = cobuild.parse("florp", html).senses
        self.assertEqual(s.definition, "Florp counts drumbeats. Its sign is a tiny florplet")
        html = self._caption('one of four florps; the florp hummed by florpers <span class="text_gray">→see also:</span> '
                             '<b class="text_blue"><a class="explain" href="entry://attic">Attic</a></b>', st="N")
        (s,) = cobuild.parse("florp", html).senses
        self.assertEqual(s.definition, "one of four florps; the florp hummed by florpers")

    def test_derivative_and_nested_phrase(self):
        (drv,) = [s for s in self.e.senses if s.kind == "derivative"]
        self.assertEqual((drv.phrase, [(x.text, x.text_zh) for x in drv.examples]),
                         ("florpish", [("A florpish grin.", "一个傻笑。")]))
        nested = [s for s in self.e.senses if s.phrase == "all florpish"]
        self.assertEqual([(s.kind, s.definition_zh) for s in nested], [("phrase", "傻乎乎的")])

    def test_cross_references_and_side_boxes_are_left_out(self):
        self.assertEqual(len(self.e.senses), 6)
        blob = repr(self.e)
        for leaked in ("NOT A SENSE", "USAGE NOTE", "THESAURUS", "water", "Trends"):
            self.assertNotIn(leaked, blob)

    def test_stubs(self):
        self.assertEqual(self.e.stub, "")
        xref = """<div class="collinsbody"><div class="word_entry"><span class="word_key">florped</span></div>
        <div class="tab_content"><div class="part_main"><div class="collins_content"><div class="collins_en_cn"><div class="caption">
        <span class="num">1</span><span class="text_blue cn_before"></span><span class="text_gray">→see:</span>
        <b class="text_blue"><a class="explain" href="entry://florp">florp</a></b>;</div><ul></ul></div></div></div></div></div>"""
        e = cobuild.parse("florped", xref)
        self.assertEqual((e.stub, e.senses, problems(e)), ("xref", (), []))

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", "<div class='collins_content'><div class='collins_en_cn'>", "<<<>>>"]:
            e = cobuild.parse("x", junk)
            self.assertEqual((e.headword, problems(e)), ("x", []))


if __name__ == "__main__":
    unittest.main()
