"""The text analyzer, on a small hand-made lexicon and spaCy's English model (no dictionary data)."""
import unittest
from collections import Counter

from analysis import load_nlp
from analysis.analyze import MAX_CHARS, analyze, edits1
from analysis.compile import anchor, distinctive, phrasal_orders, strip_open_ends, tokenize_pattern, with_base
from analysis.lexicon import Item, Lexicon, Pattern, typed_collocate
from analysis.match import Tok, connected, slot_fits

NLP = load_nlp()


def item(iid, text, kind="idiom", source="phrase", base="", relation="", n=3):
    return Item(iid, source, iid, kind, text, base, relation, n, 2, (), f"definition of {text}", "")


def lexicon(phrases=(), collocations=()) -> Lexicon:
    """phrases: (item, [variant lemma strings]); collocations: (item, [pattern strings with ~])."""
    lex = Lexicon()
    lex.forms = {"give": [("give", "VERB", 5)], "gave": [("give", "VERB", 5)], "made": [("make", "VERB", 5)],
                 "decision": [("decision", "NOUN", 5)], "decisions": [("decision", "NOUN", 5)],
                 "accommodation": [("accommodation", "NOUN", 5)], "bold": [("bold", "ADJ", 5)],
                 "difficult": [("difficult", "ADJ", 5)], "court": [("court", "NOUN", 5)],
                 "affect": [("affect", "VERB", 9)], "effect": [("effect", "NOUN", 9)]}
    lex.words = {("decision", "NOUN"): {"cefr": "a2", "levels": {"cefr": ["a2"]}, "labels": []},
                 ("affect", "VERB"): {"cefr": "b1", "levels": {}, "labels": ["register:formal"]}}
    lex.confusables = {"affect": [{"word": "effect", "kinds": ["confused"], "n": 9, "note": ""}]}
    lex.misspellings = {"accomodation": [{"word": "accommodation", "kind": "learner_error", "hint": ""}]}
    compiled = []
    for it, variants in phrases:  # as compile.py does
        for v in variants:
            toks = strip_open_ends(tokenize_pattern(v, NLP.tokenizer))
            compiled += [(it, t) for t in (phrasal_orders(toks) if it.kind == "phrasal_verb" else [toks])]
    for it, variants in collocations:
        compiled += [(it, with_base(strip_open_ends(tokenize_pattern(v, NLP.tokenizer)), [it.base])) for v in variants]
    frequency = Counter(t.lstrip("~") for _, toks in compiled for t in set(toks))
    by_anchor, by_base = {}, {}
    grouped: dict[int, list] = {}
    for it, toks in compiled:
        grouped.setdefault(it.id, (it, []))[1].append(tuple(toks))
    for it, pats in grouped.values():
        if typed := typed_collocate(it, pats):
            by_base.setdefault(typed[0], []).append((it, typed[1]))
        else:
            for toks in pats:
                by_anchor.setdefault(anchor(list(toks), frequency), []).append(Pattern(it, toks))
    lex.by_anchor, lex.by_base = by_anchor, by_base
    return lex


GIVE_UP = item(1, "give up", kind="phrasal_verb")
MIND = item(2, "make up one's mind")
GRANTED = item(3, "take sb/sth for granted")
MAKE_DECISION = item(10, "make a ~", source="collocation", kind="collocation", base="decision", relation="verb_obj")
BOLD_DECISION = item(11, "a bold ~", source="collocation", kind="collocation", base="decision", relation="adj_noun")
LEX = lexicon(
    phrases=[(GIVE_UP, ["give up", "give up {obj}", "give {obj} up"]), (MIND, ["make up {poss} mind", "make {poss} mind up"]),
             (GRANTED, ["take {obj} for granted"])],
    collocations=[(MAKE_DECISION, ["make a ~", "make ~"]), (BOLD_DECISION, ["a bold ~", "bold ~"])])


def spans(text, lex=LEX):
    result = analyze(text, NLP, lex)
    return [(s["text"], [text[a:b] for a, b in s["ranges"]]) for s in result["spans"]]


class Compile(unittest.TestCase):
    def test_patterns_are_tokenized_as_text_is(self):
        self.assertEqual(tokenize_pattern("what's with {obj} {...}", NLP.tokenizer), ["what", "'s", "with", "{obj}", "{...}"])
        self.assertEqual(strip_open_ends(["{...}", "what", "'s", "{...}"]), ["what", "'s"])

    def test_indistinct_patterns_are_left_out(self):
        self.assertFalse(distinctive(["in", "{obj}"]))             # only function words around a slot
        self.assertFalse(distinctive(["gosh"]))                     # one word is a word, not a phrase
        self.assertFalse(distinctive(["a", "~decision"]))          # a collocation of a determiner
        self.assertFalse(distinctive(["there", "are"]))             # grammar, not a phrase to mark
        self.assertFalse(distinctive(["every", "other"]))
        self.assertFalse(distinctive(["be", "drawn"]))               # every passive has it
        self.assertTrue(distinctive(["be", "in", "raptures"]))
        self.assertTrue(distinctive(["at", "least"]))
        self.assertTrue(distinctive(["give", "{obj}", "up"]))
        self.assertTrue(distinctive(["make", "a", "~decision"]))

    def test_the_rarest_literal_anchors_a_pattern(self):
        self.assertEqual(anchor(["give", "{obj}", "up"], Counter({"up": 90, "give": 5})), "give")
        self.assertEqual(anchor(["make", "a", "~decision"], Counter({"make": 50, "a": 99, "decision": 3})), "decision")

    def test_a_typed_collocation_with_one_collocate_goes_to_the_parse(self):
        self.assertEqual(typed_collocate(MAKE_DECISION, [("make", "a", "~decision"), ("make", "~decision")]),
                         ("decision", "make"))
        untyped = item(12, "a ~ of", source="collocation", base="decision", relation="untyped")
        self.assertIsNone(typed_collocate(untyped, [("a", "~decision", "of", "sorts")]))


class Phrases(unittest.TestCase):
    def test_a_phrasal_verb_split_by_its_object(self):
        self.assertIn(("give up", ["gave", "up"]), spans("She gave it up last year."))
        self.assertIn(("give up", ["gave", "up"]), spans("She gave the whole plan up last year."))
        extent = analyze("She gave it up.", NLP, LEX)["spans"][0]["extent"]
        self.assertEqual("She gave it up."[extent[0]:extent[1]], "gave it up")

    def test_a_possessive_slot(self):
        self.assertIn(("make up one's mind", ["made up", "mind"]), spans("Rafa finally made up his mind about the boat."))
        self.assertIn(("make up one's mind", ["made up", "mind"]), spans("That made up the old man's mind."))

    def test_an_object_slot_inside_an_idiom(self):
        self.assertIn(("take sb/sth for granted", ["took", "for granted"]), spans("She took her parents for granted."))

    def test_the_longer_phrase_wins_an_overlap(self):
        found = [t for t, _ in spans("Rafa made up his mind about the boat.", lexicon(phrases=[
            (MIND, ["make up {poss} mind"]), (item(4, "make up", kind="phrasal_verb"), ["make up"])]))]
        self.assertEqual(found, ["make up one's mind"])

    def test_a_phrasal_verb_in_either_order(self):
        rip = (item(5, "rip sth up", kind="phrasal_verb"), ["rip {obj} up"])
        take = (item(6, "take back", kind="phrasal_verb"), ["take back"])
        lex = lexicon(phrases=[rip, take])
        self.assertIn(("rip sth up", ["ripped up"]), spans("Tom ripped up the old receipts.", lex))
        self.assertIn(("take back", ["take", "back"]), spans("The shop will take it back tomorrow.", lex))

    def test_a_prepositional_verb_keeps_its_order(self):
        from analysis.compile import phrasal_orders
        self.assertEqual(phrasal_orders(["look", "after", "{obj}"]), [["look", "after", "{obj}"]])
        self.assertEqual(phrasal_orders(["put", "up", "with", "{obj}"]), [["put", "up", "with", "{obj}"]])

    def test_modifiers_may_come_inside_an_idiom(self):
        lex = lexicon(phrases=[(item(7, "make headway"), ["make headway"]), (item(8, "with bad grace"), ["with bad grace"])])
        self.assertIn(("make headway", ["made", "headway"]), spans("The talks made little headway after lunch.", lex))
        self.assertIn(("with bad grace", ["with", "bad grace"]), spans("He agreed with obvious bad grace.", lex))
        self.assertEqual(spans("Rafa made coffee and checked the headway.", lex), [])   # not a modifier of it

    def test_crossing_phrases_are_both_kept(self):
        lex = lexicon(phrases=[(item(9, "take back", kind="phrasal_verb"), ["take back"]),
                               (item(10, "sb can take it"), ["{obj} can take it"])])
        found = {t for t, _ in spans("I can take it back.", lex)}
        self.assertEqual(found, {"take back", "sb can take it"})

    def test_a_formula_only_on_its_own(self):
        lex = lexicon(phrases=[(item(11, "I see", kind="formula"), ["i see"])])
        self.assertIn(("I see", ["I see"]), spans("I see. Thank you.", lex))
        self.assertEqual(spans("I see in him outrageous strength.", lex), [])

    def test_a_phrasal_verbs_verb_must_be_a_verb(self):
        lex = lexicon(phrases=[(item(16, "turn on", kind="phrasal_verb"), ["turn on"])])
        self.assertIn(("turn on", ["turned on"]), spans("Rafa turned on the porch lamp.", lex))
        self.assertEqual(spans("He took a few turns on the deck.", lex), [])

    def test_words_side_by_side_are_not_a_phrase(self):
        self.assertEqual(spans("Give, up there, is the sign."), [])


class Collocations(unittest.TestCase):
    def test_found_through_the_parse_whatever_the_order(self):
        self.assertIn(("make a ~", ["made", "decision"]), spans("She made a difficult decision."))
        self.assertIn(("make a ~", ["decision", "made"]), spans("The decision that the court made was final."))
        self.assertIn(("make a ~", ["decision", "made"]), spans("A decision was made yesterday."))
        self.assertIn(("a bold ~", ["bold decision"]), spans("It was a bold decision."))   # adjacent: one range

    def test_not_found_when_the_words_are_only_near_each_other(self):
        self.assertEqual(spans("He made coffee before the decision."), [])

    def test_a_relative_clause_only_where_the_noun_fills_the_verbs_open_role(self):
        self.assertEqual(spans("It was a decision that made history."), [])   # the decision made history
        self.assertIn(("make a ~", ["decision", "made"]), spans("The decision that she made surprised everyone."))
        self.assertEqual(spans("We chose a method that employs a filter.", lexicon(collocations=[
            (item(15, "employ a ~", source="collocation", kind="collocation", base="method", relation="verb_obj"),
             ["employ a ~"])])), [])

    def test_a_prepositional_collocation_keeps_its_order_and_a_slot_its_role(self):
        from analysis.lexicon import typed_collocate
        faith_in = item(13, "~ in", source="collocation", kind="collocation", base="faith", relation="prep")
        self.assertIsNone(typed_collocate(faith_in, [("~faith", "in")]))     # matched as a pattern
        in_word = item(14, "in {sb's} ~", source="collocation", kind="collocation", base="word", relation="verb_prep")
        self.assertIsNone(typed_collocate(in_word, [("in", "{poss}", "~word")]))
        lex = lexicon(collocations=[(faith_in, ["~ in"])])
        self.assertIn(("~ in", ["faith in"]), spans("She has great faith in him.", lex))
        self.assertEqual(spans("There was something noble in the simple faith of our visitor.", lex), [])

    def test_a_nouns_prepositions_are_not_marked(self):
        import sqlite3, tempfile
        from pathlib import Path
        from analysis.compile import SCHEMA
        from analysis.lexicon import load
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "a.db"
            con = sqlite3.connect(db)
            con.executescript(SCHEMA)
            con.execute("INSERT INTO item VALUES (1,'collocation',1,'collocation','in a ~','year','prep',5,3,'[]','','')")
            con.execute("INSERT INTO item VALUES (2,'collocation',2,'collocation','make a ~','decision','verb_obj',5,3,'[]','','')")
            con.execute("INSERT INTO pattern VALUES (1,'[\"in\", \"a\", \"~year\"]','year')")
            con.execute("INSERT INTO pattern VALUES (2,'[\"make\", \"a\", \"~decision\"]','decision')")
            con.commit()
            con.close()
            lex = load(db)
        self.assertNotIn("year", lex.by_anchor)
        self.assertIn("decision", lex.by_base)


class Words(unittest.TestCase):
    def setUp(self):
        self.text = "The accomodation affects my decision about the gromble."
        self.result = analyze(self.text, NLP, LEX)
        self.by_text = {t["text"]: t for t in self.result["tokens"]}

    def test_offsets_point_into_the_text(self):
        for t in self.result["tokens"]:
            self.assertEqual(self.text[t["start"]:t["end"]], t["text"])

    def test_levels_labels_and_confusions(self):
        self.assertEqual(self.by_text["decision"]["cefr"], "a2")
        self.assertEqual(self.by_text["affects"]["lemma"], "affect")
        self.assertEqual(self.by_text["affects"]["labels"], ["register:formal"])
        self.assertEqual(self.by_text["affects"]["confusable"][0]["word"], "effect")
        self.assertTrue(self.by_text["affects"]["confusable"][0]["notable"])   # "confused", 9 dictionaries

    def test_only_a_warning_two_dictionaries_give_is_notable(self):
        from analysis.analyze import notable
        self.assertTrue(notable({"kinds": ["confused"], "n": 2}))
        self.assertTrue(notable({"kinds": ["which_word"], "n": 1}))
        self.assertFalse(notable({"kinds": ["confused"], "n": 1}))
        self.assertFalse(notable({"kinds": ["homophone", "sound_alike"], "n": 3}))

    def test_spelling(self):
        flag = self.by_text["accomodation"]["flags"][0]
        self.assertEqual((flag["kind"], flag["word"], flag["source"]), ("misspelling", "accommodation", "learner_error"))
        self.assertEqual(self.by_text["gromble"]["flags"][0]["kind"], "unknown")
        self.assertNotIn("flags", self.by_text["decision"])

    def test_suggestions_are_one_edit_away(self):
        self.assertIn("decision", edits1("decison"))

    def test_too_long_a_text_is_refused(self):
        with self.assertRaises(ValueError):
            analyze("a" * (MAX_CHARS + 1), NLP, LEX)


class Slots(unittest.TestCase):
    @staticmethod
    def tok(i, text, head, pos="NOUN", tag="NN", dep="dobj", punct=False):
        return Tok(i, text, text.lower(), 0, 0, pos, tag, dep, head, text.lower(), frozenset({text.lower()}), punct)

    def test_an_object_is_one_subtree_headed_by_a_noun(self):
        the, plan = self.tok(1, "the", 2, "DET", "DT", "det"), self.tok(2, "plan", 0)
        self.assertTrue(slot_fits("{obj}", [the, plan]))
        self.assertFalse(slot_fits("{obj}", [the]))                   # a determiner heads nothing
        his = self.tok(1, "his", 2, "PRON", "PRP$", "poss")
        self.assertFalse(slot_fits("{obj}", [his]))                   # it belongs to the noun after it

    def test_connected(self):
        a, b, c = self.tok(0, "give", 0), self.tok(1, "it", 0), self.tok(2, "up", 0)
        self.assertTrue(connected({0, 1, 2}, [a, b, c]))
        loose = self.tok(2, "up", 3)
        self.assertFalse(connected({0, 2}, [a, b, loose, self.tok(3, "there", 3)]))

    def test_siblings_side_by_side_are_connected_but_not_across_a_gap(self):
        knew, early, on = self.tok(0, "knew", 0), self.tok(1, "early", 0), self.tok(2, "on", 0)
        self.assertTrue(connected({1, 2}, [knew, early, on]))                    # both hang from "knew"
        x = self.tok(3, "x", 0)
        self.assertFalse(connected({1, 3}, [knew, early, on, x]))                # not side by side
        room = self.tok(3, "room", 0)
        the, main = self.tok(1, "the", 3), self.tok(2, "main", 3)
        self.assertFalse(connected({0, 1, 2}, [self.tok(0, "in", 4), the, main, room, self.tok(4, "sat", 4)]))


if __name__ == "__main__":
    unittest.main()
