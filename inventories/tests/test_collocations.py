"""Placing the base, naming the relation, merging collocations across sources."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from inventory.collocation_sources import PHRASE, QUANT, UNTYPED, Raw
from inventory.collocations import build, place, relation
from inventory.notation import parse

LEMMAS = {"plans": "plan", "drafted": "draft", "snowing": "snow", "made": "make"}
POS = {"of": {"VERB"}, "splash": {"NOUN", "VERB"}, "successful": {"ADJ"}, "back": {"NOUN", "ADV", "VERB", "ADJ"},
       "idea": {"NOUN"}, "loose": {"ADJ", "VERB"}, "plan": {"NOUN", "VERB"}, "bold": {"ADJ"}, "draft": {"VERB", "NOUN"}, "make": {"VERB"},
       "snow": {"NOUN", "VERB"}, "heavily": {"ADV"}, "cunning": {"ADJ", "NOUN"}, "sudden": {"ADJ"},
       "for": {"ADP"}, "flake": {"NOUN"}}


FORMS = {"come": frozenset({"comes", "came", "coming"})}


def placed(raw, upos):
    return [(" ".join(p.pattern), p.relation, p.free)
            for v in parse(raw.printed, raw.base).variants if (p := place(raw, v, upos, POS, LEMMAS, FORMS))]


class Place(unittest.TestCase):
    def test_a_bare_collocate_goes_on_its_side(self):
        self.assertEqual(placed(Raw("ocd", "plan", "NOUN", "VERB", "before", "draw up"), "NOUN"),
                         [("draw up ~", "verb_obj", False)])
        self.assertEqual(placed(Raw("ocd", "plan", "NOUN", "VERB", "after", "fail"), "NOUN"),
                         [("~ fail", "subj_verb", False)])
        self.assertEqual(placed(Raw("ocd", "snow", "NOUN", QUANT, "before", "flake"), "NOUN"),
                         [("flake of ~", "quantifier", False)])

    def test_a_full_collocation_places_its_base_wherever_it_is(self):
        self.assertEqual(placed(Raw("ldoce", "plan", "NOUN", "VERB", "", "draw up/devise a plan"), "NOUN"),
                         [("draw up a ~", "verb_obj", False), ("devise a ~", "verb_obj", False)])
        self.assertEqual(placed(Raw("ocd", "snow", "VERB", PHRASE, "", "start snowing"), "VERB"),
                         [("start ~", "phrase", False)])

    def test_an_adverb_without_a_side_is_free(self):
        self.assertEqual(placed(Raw("med", "snow", "VERB", "ADV", "", "heavily"), "VERB"),
                         [("~ heavily", "adv_verb", True)])

    def test_an_adverb_with_a_side_keeps_its_order(self):
        self.assertEqual(placed(Raw("ldoce", "snow", "VERB", "ADV", "before", "heavily"), "VERB"),
                         [("heavily ~", "adv_verb", False)])

    def test_subject_or_object_unknown(self):
        self.assertEqual(placed(Raw("med", "snow", "VERB", "NOUN", "", "flake"), "VERB"), [("~ flake", "untyped", True)])

    def test_untyped_collocations_take_their_one_open_word(self):
        self.assertEqual(placed(Raw("ncecd", "plan", "NOUN", UNTYPED, "", "a sudden plan"), "NOUN"),
                         [("a sudden ~", "adj_noun", False)])
        self.assertEqual(placed(Raw("ncecd", "plan", "NOUN", UNTYPED, "", "to plan for sth"), "VERB"),
                         [("~ for {sth}", "prep", False)])

    def test_function_words_are_not_the_collocate(self):
        self.assertEqual(placed(Raw("ncecd", "splash", "NOUN", UNTYPED, "", "a splash of sth"), "NOUN"),
                         [("a ~ of {sth}", "prep", False)])
        self.assertEqual(placed(Raw("ncecd", "colossally", "ADV", UNTYPED, "", "to be colossally successful"), "ADV"),
                         [("be ~ successful", "adv_adj", False)])

    def test_the_pattern_decides_an_ambiguous_word(self):
        pos = dict(POS, set={"VERB", "NOUN", "ADJ"}, mood={"NOUN"}, group={"NOUN", "VERB"}, oddly={"ADV"})
        got = lambda raw, upos: [(" ".join(p.pattern), p.relation) for v in parse(raw.printed, raw.base).variants
                                 if (p := place(raw, v, upos, pos, LEMMAS, FORMS))]
        self.assertEqual(got(Raw("ncecd", "mood", "NOUN", UNTYPED, "", "to set the mood"), "NOUN"), [("set the ~", "verb_obj")])
        self.assertEqual(got(Raw("ncecd", "assorted", "ADJ", UNTYPED, "", "an oddly assorted group"), "ADJ"),
                         [("an oddly ~ group", "adj_noun")])

    def test_a_word_after_an_article_is_a_noun(self):
        self.assertEqual(placed(Raw("ncecd", "crick", "VERB", UNTYPED, "", "to crick your back"), "VERB"),
                         [("~ {one's} back", "verb_obj", False)])

    def test_inflections_that_are_lemmas_themselves(self):
        self.assertEqual(placed(Raw("ldoce", "come", "", UNTYPED, "", "came loose"), ""), [("~ loose", "untyped", False)])

    def test_a_full_collocation_without_its_base_is_unreadable(self):
        self.assertEqual(placed(Raw("ldoce", "plan", "NOUN", UNTYPED, "", "a cunning scheme"), "NOUN"), [])

    def test_either_part_of_speech_by_the_word(self):
        self.assertEqual(placed(Raw("ldoce", "snow", "NOUN", "ADJ|NOUN", "before", "sudden"), "NOUN"),
                         [("sudden ~", "adj_noun", False)])

    def test_a_verb_through_a_preposition(self):
        self.assertEqual(placed(Raw("ocd", "plan", "NOUN", "VERB", "before", "crush sb to"), "NOUN"),
                         [("crush {sb} to ~", "verb_prep", False)])
        self.assertEqual(placed(Raw("ldoce", "snow", "VERB", "NOUN", "", "snow to this day"), "VERB"),
                         [("~ to this day", "prep", False)])          # the base is the verb: prep
        self.assertEqual(placed(Raw("ldoce", "plan", "NOUN", "VERB", "", "strike a plan at sth"), "NOUN"),
                         [("strike a ~ at {sth}", "verb_obj", False)])   # the preposition is after the base

    def test_a_particle_word_after_an_object_is_a_preposition(self):
        self.assertEqual(placed(Raw("ocd", "plan", "NOUN", "VERB", "before", "take sb off"), "NOUN"),
                         [("take {sb} off ~", "verb_prep", False)])  # take sb off the list: not a particle

    def test_relations(self):
        self.assertEqual(relation("VERB", "NOUN", "after"), "verb_obj")
        self.assertEqual(relation("ADJ", "ADV", "before"), "adv_adj")
        self.assertEqual(relation("NOUN", "INTJ", "before"), "untyped")


class Build(unittest.TestCase):
    def test_the_same_collocation_from_several_sources_is_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "c.db"
            summary = build([Raw("ocd", "plan", "NOUN", "VERB", "before", "draft"),
                             Raw("ldoce", "plan", "NOUN", "VERB", "", "draft a plan", "write one"),
                             Raw("med", "plan", "NOUN", "ADJ", "before", "bold"),
                             Raw("ldoce", "plan", "NOUN", UNTYPED, "", "a cunning scheme")], LEMMAS, POS, out)
            con = sqlite3.connect(out)
            rows = con.execute("SELECT pattern, relation, dictionaries, publishers, gloss, word_order "
                               "FROM collocation ORDER BY pattern").fetchall()
            con.close()
        self.assertEqual(rows, [("bold ~", "adj_noun", '["med"]', 1, "", "fixed"),
                                ("draft a ~", "verb_obj", '["ldoce", "ocd"]', 2, "write one", "fixed")])
        self.assertEqual((summary["collocations"], summary["unreadable"]), (2, {"ldoce": 1}))

    def test_a_collocation_of_unknown_part_of_speech_joins_the_typed_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "c.db"
            build([Raw("ocd", "plan", "NOUN", "ADJ", "before", "bold"),
                   Raw("ldoce", "plan", "", UNTYPED, "", "a bold plan"),
                   Raw("ldoce", "plan", "", UNTYPED, "", "plan ahead")], LEMMAS, POS, out)
            con = sqlite3.connect(out)
            rows = con.execute("SELECT base_pos, relation, pattern, dictionaries FROM collocation ORDER BY id").fetchall()
            con.close()
        self.assertEqual(rows, [("", "untyped", "~ ahead", '["ldoce"]'),
                                ("NOUN", "adj_noun", "a bold ~", '["ldoce", "ocd"]')])

    def test_the_base_part_of_speech_place_settles_on_is_stored(self):
        pos = dict(POS, glimmer={"NOUN", "VERB"}, heavily={"ADV"})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "c.db"
            build([Raw("med", "glimmer", "NOUN", "ADV", "", "heavily")], LEMMAS, pos, out)  # glimmer + heavily: the verb
            con = sqlite3.connect(out)
            rows = con.execute("SELECT base_pos, relation, pattern FROM collocation").fetchall()
            con.close()
        self.assertEqual(rows, [("VERB", "adv_verb", "~ heavily")])


if __name__ == "__main__":
    unittest.main()
