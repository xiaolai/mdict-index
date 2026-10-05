"""Reading the dictionaries' phrase notation into variants of words and slots."""
import unittest

from inventory.notation import MAX_VARIANTS, parse


def texts(printed, headword=""):
    return sorted(" ".join(v) for v in parse(printed, headword).variants)


class Slots(unittest.TestCase):
    def test_placeholders_become_typed_slots(self):
        self.assertEqual(texts("send somebody to Coventry"), ["send {sb} to coventry"])
        self.assertEqual(texts("put sth by"), ["put {sth} by"])
        self.assertEqual(texts("pin sb. down"), ["pin {sb} down"])
        self.assertEqual(texts("take somebody/something for granted"), ["take {sb/sth} for granted"])
        self.assertEqual(texts("keep your hair on"), ["keep {one's} hair on"])
        self.assertEqual(texts("befoul one's nest"), ["befoul {one's} nest"])
        self.assertEqual(texts("pull yourself together"), ["pull {oneself} together"])
        self.assertEqual(texts("chalk something up to experience"), ["chalk {sth} up to experience"])

    def test_a_leading_to_before_a_possessive_placeholder_is_a_preposition(self):
        self.assertEqual(texts("to somebody's face"), ["to {sb's} face"])
        self.assertEqual(texts("to sb's glim"), ["to {sb's} glim"])
        self.assertEqual(texts("to something's credit"), ["to {sth's} credit"])
        self.assertEqual(texts("to jack sth up"), ["jack {sth} up"])  # an infinitive "to" still goes

    def test_a_possessive_pair_starting_with_its_is_one_slot(self):
        self.assertEqual(texts("its/his/her own glim"), ["{one's} own glim"])
        self.assertEqual(texts("his/her/its own glim"), ["{one's} own glim"])
        self.assertEqual(texts("in its/their glim"), ["in its glim", "in their glim"])  # a thing's: no slot
        self.assertEqual(texts("in their/its glim"), ["in its glim", "in their glim"])

    def test_an_ellipsis_is_an_open_slot(self):
        self.assertEqual(texts("how about…?"), ["how about {...}"])


class Alternatives(unittest.TestCase):
    def test_single_word_alternatives(self):
        self.assertEqual(texts("be/go out like a light"), ["be out like a light", "go out like a light"])
        self.assertEqual(texts("the last minute/moment"), ["the last minute", "the last moment"])

    def test_multi_word_alternatives_replace_from_the_repeated_word(self):
        self.assertEqual(texts("as easy as anything/as pie/as ABC"),
                         ["as easy as abc", "as easy as anything", "as easy as pie"])

    def test_whole_phrase_alternatives_joined_by_or(self):
        self.assertEqual(texts("to jack sth up or to jack up sth"), ["jack up {sth}", "jack {sth} up"])

    def test_multi_word_alternatives_replace_the_last_word(self):
        self.assertEqual(texts("rip sb/sth apart/to shreds/to bits"),
                         ["rip {sb/sth} apart", "rip {sb/sth} to bits", "rip {sb/sth} to shreds"])
        self.assertEqual(texts("fall apart/to pieces"), ["fall apart", "fall to pieces"])
        self.assertEqual(texts("dwell on/upon something"), ["dwell on {sth}", "dwell upon {sth}"])
        self.assertEqual(texts("as of/as from"), ["as from", "as of"])
        self.assertEqual(texts("go down/drop like ninepins"), ["drop like ninepins", "go down like ninepins"])
        self.assertEqual(texts("be in/get into a state"), ["be in a state", "get into a state"])
        self.assertEqual(texts("rise/come back/return from the dead"),
                         ["come back from the dead", "return from the dead", "rise from the dead"])
        self.assertEqual(texts("get into/hit your stride"), ["get into {one's} stride", "hit {one's} stride"])
        self.assertEqual(texts("spiral down/downward"), ["spiral down", "spiral downward"])
        self.assertEqual(texts("go through/put someone through the wringer"),
                         ["go through the wringer", "put {sb} through the wringer"])
        self.assertEqual(texts("find out/learn something to your cost"),
                         ["find out {sth} to {one's} cost", "learn {sth} to {one's} cost"])
        self.assertEqual(texts("turn to/feel like jelly"), ["feel like jelly", "turn to jelly"])
        self.assertEqual(texts("crammed with/crammed full of something"),
                         ["crammed full of {sth}", "crammed with"])
        self.assertEqual(texts("come close (to something/to doing something)"),
                         ["come close", "come close to doing {sth}", "come close to {sth}"])

    def test_alternative_verbs_sharing_a_particle_and_a_tail(self):
        self.assertEqual(texts("get up/build up/work up a head of steam"),
                         ["build up a head of steam", "get up a head of steam", "work up a head of steam"])

    def test_whole_alternatives_ending_alike(self):
        self.assertEqual(texts("God/oh (my) God/good God (almighty)"),
                         ["god", "good god", "good god almighty", "oh god", "oh my god"])
        self.assertEqual(texts("good grief/God/Lord!"), ["good god", "good grief", "good lord"])

    def test_a_placeholder_pair_is_one_slot_not_alternatives(self):
        self.assertEqual(texts("give (somebody) the OK/get the OK"), sorted(
            ["give the ok", "give {sb} the ok", "get the ok"]))


class RealNotation(unittest.TestCase):
    def test_curly_apostrophes(self):
        self.assertEqual(texts("rub somebody’s nose in it"), ["rub {sb's} nose in it"])
        self.assertEqual(texts("arrow in one’s quiver"), ["arrow in {one's} quiver"])

    def test_ldoce_separability_arrow(self):
        p = parse("use something ↔ up")
        self.assertEqual([" ".join(v) for v in p.variants], ["use {sth} up"])
        self.assertTrue(p.separable)

    def test_oald_bar_separates_whole_alternatives(self):
        self.assertEqual(texts("the lesser of two evils | the lesser evil"), ["the lesser evil", "the lesser of two evils"])

    def test_a_possessive_pair_is_one_slot(self):
        self.assertEqual(texts("enter somebody’s/your name"), ["enter {sb's} name"])

    def test_or_in_parentheses_replaces_as_many_words(self):
        self.assertEqual(texts("let it drop (或 rest)"), ["let it drop", "let it rest"])
        self.assertEqual(texts("have a monkey on a house (或 up the chimney)"),
                         ["have a monkey on a house", "have a monkey up the chimney"])
        self.assertEqual(texts("hang out (或 hang up 或 set up) one's shingle"),
                         ["hang out {one's} shingle", "hang up {one's} shingle", "set up {one's} shingle"])
        self.assertEqual(texts("spit blood (or 〈澳〉chips)"), ["spit blood", "spit chips"])

    def test_more_or_notations(self):
        self.assertEqual(texts("get (或have) sb.'s number"), ["get {sb's} number", "have {sb's} number"])
        self.assertEqual(texts("make no mistake (about it 或 that)"),
                         ["make no mistake", "make no mistake about it", "make no mistake about that"])
        self.assertEqual(texts("in arrears (also〔主律〕 in arrear)"), ["in arrear", "in arrears"])
        self.assertEqual(texts("do…justice（或do justice to…）"), ["do justice to {...}", "do {...} justice"])
        self.assertEqual(texts("free on board (or rail) (缩略词: f.o.b.)"), ["free on board", "free on rail"])

    def test_broken_strings_give_no_variants(self):
        self.assertEqual(texts("(get"), [])
        self.assertEqual(texts("<"), [])
        # a variant still holding apparatus is dropped, the clean ones kept
        self.assertNotIn("(", " ".join(texts("you can bet your life/your bottom dollar (on something/(that)…)")))

    def test_a_comma_list_ending_in_etc_is_alternatives(self):
        self.assertEqual(texts("come, turn, etc. full circle"), ["come full circle", "turn full circle"])
        self.assertEqual(texts("trust you, him, her, etc. (to do something)"),
                         ["trust her", "trust her to do {sth}", "trust him", "trust him to do {sth}",
                          "trust you", "trust you to do {sth}"])

    def test_plain_or_between_long_alternatives(self):
        self.assertEqual(texts("a rap on the knuckles or a rap over the knuckles"),
                         ["a rap on the knuckles", "a rap over the knuckles"])
        self.assertEqual(texts("sink or swim"), ["sink or swim"])            # an idiom with "or" in it
        self.assertEqual(texts("take it or leave it"), ["take it or leave it"])
        self.assertEqual(texts("no rhyme or reason for it"), ["no rhyme or reason for it"])  # sides unlike
        self.assertEqual(texts("crowd sb/sth into/onto sth"), ["crowd {sb/sth} into {sth}", "crowd {sb/sth} onto {sth}"])

    def test_an_alternative_starting_with_a_determiner_replaces_as_many_words(self):
        self.assertEqual(texts("crack a book/the books"), ["crack a book", "crack the books"])

    def test_a_slash_after_an_optional_part_joins_whole_words(self):
        self.assertEqual(texts("get (yourself)/be in a stew"),
                         ["be in a stew", "get in a stew", "get {oneself} in a stew"])

    def test_etc_inside_an_optional_part(self):
        self.assertEqual(texts("pack a (hard/strong etc) punch"), ["pack a hard punch", "pack a punch", "pack a strong punch"])
        self.assertEqual(texts("walk off (the/your etc job)"), ["walk off", "walk off the job", "walk off {one's} job"])

    def test_a_headword_printed_with_its_variant_spelling(self):
        self.assertEqual(texts("hit the bull's-eye, bullseye", headword="bull's-eye, bullseye"),
                         ["hit the bull's-eye", "hit the bullseye"])

    def test_alternative_verbs_some_phrasal(self):
        self.assertEqual(texts("draw up/devise a plan"), ["devise a plan", "draw up a plan"])
        self.assertEqual(texts("reach/come to/arrive at a decision"),
                         ["arrive at a decision", "come to a decision", "reach a decision"])
        self.assertEqual(texts("fall apart/to pieces"), ["fall apart", "fall to pieces"])
        self.assertEqual(texts("dwell on/upon something"), ["dwell on {sth}", "dwell upon {sth}"])
        self.assertEqual(texts("as of/as from"), ["as from", "as of"])
        self.assertEqual(texts("go down/drop like ninepins"), ["drop like ninepins", "go down like ninepins"])
        self.assertEqual(texts("be in/get into a state"), ["be in a state", "get into a state"])
        self.assertEqual(texts("rise/come back/return from the dead"),
                         ["come back from the dead", "return from the dead", "rise from the dead"])
        self.assertEqual(texts("get into/hit your stride"), ["get into {one's} stride", "hit {one's} stride"])
        self.assertEqual(texts("spiral down/downward"), ["spiral down", "spiral downward"])
        self.assertEqual(texts("go through/put someone through the wringer"),
                         ["go through the wringer", "put {sb} through the wringer"])
        self.assertEqual(texts("find out/learn something to your cost"),
                         ["find out {sth} to {one's} cost", "learn {sth} to {one's} cost"])
        self.assertEqual(texts("turn to/feel like jelly"), ["feel like jelly", "turn to jelly"])
        self.assertEqual(texts("crammed with/crammed full of something"),
                         ["crammed full of {sth}", "crammed with"])

    def test_full_width_punctuation(self):
        self.assertEqual(texts("what's the betting？"), ["what's the betting"])


class Optional(unittest.TestCase):
    def test_optional_parts_give_both_variants(self):
        self.assertEqual(texts("go Dutch (with somebody)"), ["go dutch", "go dutch with {sb}"])
        self.assertEqual(texts("be taken aback (by somebody/something)"),
                         ["be taken aback", "be taken aback by {sb/sth}"])

    def test_many_optional_parts_stop_at_the_variant_limit(self):
        # 2**40 combinations: only the first MAX_VARIANTS are ever built
        printed = "glim " + " ".join(f"(w{i})" for i in range(40))
        variants = texts(printed)
        self.assertEqual(len(variants), MAX_VARIANTS)
        self.assertIn("glim", variants)

    def test_many_or_groups_stop_at_the_variant_limit(self):
        printed = " ".join(f"w{i} (or v{i})" for i in range(40))  # 2**40 readings
        self.assertEqual(len(texts(printed)), MAX_VARIANTS)

    def test_etc_is_apparatus(self):
        self.assertEqual(texts("half as big/much (etc.) as"), ["half as big as", "half as much as"])


class GluedApparatus(unittest.TestCase):
    """Shapes that once left words glued together or punctuation inside a variant."""

    def variants(self, printed):
        return [" ".join(v) for v in parse(printed).variants]

    def test_a_gloss_glued_to_the_phrase_is_dropped(self):
        self.assertEqual(self.variants("a fast buck or a quick buck(easy money)"), ["a fast buck", "a quick buck"])
        self.assertEqual(self.variants("to get shot of sb/sth or to be shot of sb/sth(be rid of)"),
                         ["get shot of {sb/sth}", "be shot of {sb/sth}"])

    def test_a_glued_or_group_is_not_a_gloss(self):
        self.assertIn("a needle in the haystack", self.variants("a needle in a(\u6216 the) haystack"))

    def test_a_semicolon_separates_whole_alternatives(self):
        self.assertEqual(self.variants("do justice to somebody/something; do somebody/something justice"),
                         ["do justice to {sb/sth}", "do {sb/sth} justice"])
        self.assertEqual(self.variants("to be on strike;to be out on strike"), ["be on strike", "be out on strike"])

    def test_an_etc_list_in_the_headword_is_not_a_list_of_spellings(self):
        printed = "in his/her/its, etc. (infinite) wisdom"
        self.assertEqual([" ".join(v) for v in parse(printed, printed).variants],
                         ["in {one's} wisdom", "in {one's} infinite wisdom"])

    def test_or_group_alternatives_may_be_separated_by_a_semicolon_and_also(self):
        self.assertEqual(self.variants("the other way round (or around; also about)"),
                         ["the other way round", "the other way around", "the other way about"])

    def test_a_proverbs_own_semicolon_is_not_a_separator(self):
        self.assertTrue(all("divine" in v and "human" in v for v in self.variants("To err is human; to forgive, divine.")))

    def test_nothing_stays_glued_to_a_slot(self):
        self.assertEqual(self.variants("a pox on sb/sth!\u2026"), ["a pox on {sb/sth} {...}"])
        self.assertEqual(self.variants("speak for myself/herself/himself, etc."), ["speak for myself", "speak for {oneself}"])

    def test_a_slot_with_an_apostrophe_s_is_a_possessive(self):
        self.assertEqual(self.variants("in someone/thing's (own) way"), ["in {sb's} way", "in {sb's} own way"])


class Headword(unittest.TestCase):
    def test_a_tilde_stands_for_the_headword(self):
        self.assertEqual(texts("take a ~ at", headword="look"), ["take a look at"])


class Separable(unittest.TestCase):
    def test_an_object_between_verb_and_particle(self):
        self.assertTrue(parse("put sth off").separable)
        self.assertFalse(parse("give up sth").separable)
        self.assertTrue(parse("to jack sth up or to jack up sth").separable)


if __name__ == "__main__":
    unittest.main()
