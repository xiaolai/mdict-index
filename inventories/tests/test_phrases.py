"""Merging phrases across dictionaries."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from inventory.phrase_kinds import KindEvidence, attested_pattern, refine_kind, valency_pattern
from inventory.phrases import build, key, phrasal_shape

SCHEMA = """
CREATE TABLE s_entry (entry_id INTEGER PRIMARY KEY, headword TEXT);
CREATE TABLE s_sense (id INTEGER PRIMARY KEY, entry_id INTEGER, kind TEXT, phrase TEXT, pos TEXT, labels TEXT,
                      definition TEXT, definition_zh TEXT);
"""
LEMMAS = {"goes": "go", "taken": "take", "pulls": "pull"}


def dictionary(folder, name, senses):
    con = sqlite3.connect(folder / f"{name}.db")
    con.executescript(SCHEMA)
    for i, (headword, kind, phrase, pos, definition) in enumerate(senses, 1):
        con.execute("INSERT INTO s_entry VALUES (?, ?)", (i, headword))
        con.execute("INSERT INTO s_sense VALUES (?,?,?,?,?, '[]', ?, '')", (i, i, kind, phrase, pos, definition))
    con.commit()
    con.close()
    return folder / f"{name}.db"


class Key(unittest.TestCase):
    def test_words_become_lemmas_and_object_slots_one(self):
        self.assertEqual(key(("goes", "public"), LEMMAS), ("go", "public"))
        self.assertEqual(key(("take", "{sth}", "for", "granted"), LEMMAS), key(("take", "{sb/sth}", "for", "granted"), LEMMAS))


class Build(unittest.TestCase):
    def run_build(self, dictionaries):
        self.tmp = tempfile.TemporaryDirectory()
        folder = Path(self.tmp.name)
        dbs = [dictionary(folder, name, senses) for name, senses in dictionaries.items()]
        summary = build(dbs, LEMMAS, folder / "out.db")
        con = sqlite3.connect(folder / "out.db")
        rows = [dict(zip([d[0] for d in con.execute("SELECT * FROM phrase").description], r))
                for r in con.execute("SELECT * FROM phrase ORDER BY text")]
        con.close()
        self.tmp.cleanup()
        return summary, rows

    def test_the_same_phrase_from_several_dictionaries_is_one(self):
        summary, rows = self.run_build({
            "oald": [("grant", "phrase", "take somebody/something for granted", "", "to stop noticing a florp...")],
            "ldoce": [("grant", "phrase", "take something for granted", "", "to frelt a grelt...")],
            "cobuild": [("public", "phrase", "goes public", "", "When Grelt Ltd goes public...")],
            "mwaled": [("public", "phrase", "go public", "", "to sell frelt shares to anyone")]})
        self.assertEqual(summary["phrases"], 2)
        granted = next(r for r in rows if "granted" in r["text"])
        self.assertEqual(granted["text"], "take {sb/sth} for granted")   # OALD is preferred
        self.assertEqual((granted["n"], granted["publishers"]), (2, 2))
        public = next(r for r in rows if "public" in r["text"])
        self.assertEqual(public["text"], "go public")                    # never COBUILD's keywords
        self.assertEqual(json.loads(public["dictionaries"]), ["cobuild", "mwaled"])

    def test_a_record_grouping_near_synonyms_does_not_chain_idioms(self):
        summary, rows = self.run_build({
            "oald": [("way", "phrase", "clear/pave/open/prepare the way (for something)", "", "")],
            "ldoce": [("door", "phrase", "open the door/way", "", ""), ("way", "phrase", "pave the way", "", "")],
            "cald": [("light", "phrase", "go out like a light", "", "")],
            "mwaled": [("light", "phrase", "be/go out like a light", "", "")]})
        texts = sorted(r["text"] for r in rows)
        self.assertEqual(texts, ["clear the way", "go out like a light", "open the door"])
        light = next(r for r in rows if "light" in r["text"])
        self.assertEqual(light["n"], 2)                                  # cald joins mwaled's group
        way = next(r for r in rows if r["text"] == "clear the way")
        self.assertEqual(json.loads(way["dictionaries"]), ["ldoce", "oald"])  # "pave the way" joins it

    def test_a_variant_counts_dictionaries_not_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            dbs = [dictionary(folder, "oald", [("glim", "phrase", "glim it up", "", ""),
                                               ("up", "phrase", "glim it up", "", "")]),
                   dictionary(folder, "ldoce", [("glim", "phrase", "glim it up", "", "")])]
            build(dbs, LEMMAS, folder / "out.db")
            con = sqlite3.connect(folder / "out.db")
            variants = con.execute("SELECT text, n FROM variant").fetchall()
            con.close()
        self.assertEqual(variants, [("glim it up", 2)])

    def test_same_publisher_counts_once(self):
        _, rows = self.run_build({"oald": [("x", "phrase", "out and about", "", "")],
                                  "oalecd": [("x", "phrase", "out and about", "", "")]})
        self.assertEqual((rows[0]["n"], rows[0]["publishers"]), (2, 1))

    def test_kinds_and_separability(self):
        _, rows = self.run_build({"cald": [("put", "phrasal_verb", "put sth off", "phrasal verb", ""),
                                           ("thank", "phrase", "thank God", "exclamation", ""),
                                           ("sea", "phrase", "the North Sea", "n.", ""),
                                           ("light", "phrase", "go out like a light", "", "")]})
        by_text = {r["text"]: r for r in rows}
        self.assertEqual((by_text["put {sth} off"]["kind"], by_text["put {sth} off"]["separable"]), ("phrasal_verb", 1))
        self.assertEqual(by_text["thank god"]["kind"], "formula")
        self.assertEqual(by_text["the north sea"]["kind"], "name")
        self.assertEqual(by_text["go out like a light"]["kind"], "idiom")

    def test_the_canonical_text_is_never_a_single_word(self):
        _, rows = self.run_build({"oald": [("god", "phrase", "God/oh (my) God/good God (almighty)", "", "")]})
        self.assertEqual(rows[0]["text"], "oh god")

    def test_compounds_notes_and_keyword_only_groups(self):
        summary, rows = self.run_build({
            "ldoce": [("ape", "phrase", "the great apes", "noun", ""), ("x", "phrase", "take it easy", "", ""),
                      ("limit", "phrase", "be over the limit", "noun", "")],
            "ncecd": [("zigzag", "phrase", "comparative zigzaggier superlative zigzaggiest", "adj.", "")],
            "cobuild": [("battle", "phrase", "battles it out with", "", "")]})
        kinds = {r["text"]: r["kind"] for r in rows}
        self.assertEqual(kinds, {"the great apes": "compound", "take it easy": "idiom",
                                 "be over the limit": "idiom"})       # the entry's POS, not the phrase's
        self.assertEqual(summary["keywords_only"], 1)

    def test_single_words_are_not_phrases(self):
        summary, rows = self.run_build({"ldoce": [("x", "phrase", "particulars", "noun", ""),
                                                  ("x", "phrase", "off-the-cuff", "", ""),
                                                  ("woman", "phrase", "the woman", "n.", "")]})
        self.assertEqual([r["text"] for r in rows], ["off-the-cuff"])


class NcecdKinds(unittest.TestCase):
    EVIDENCE = KindEvidence(frozenset({"glimmer pine", "ease the glim"}), {"endeavour": frozenset({"V to-inf"}),
                                                                        "glimpervious": frozenset({"ADJ to n"})})

    def test_valency_patterns(self):
        self.assertEqual(valency_pattern("endeavour to do {sth}", {}), ("endeavour", "~ to-inf"))
        self.assertEqual(valency_pattern("be glimpervious to {sth}", {}), ("glimpervious", "~ to n"))
        self.assertIsNone(valency_pattern("be long in the tooth", {}))
        self.assertEqual(attested_pattern("glimpervious to {sth}", {}, self.EVIDENCE.grammar), "ADJ to n")
        self.assertEqual(attested_pattern("glimpervious to {oneself}", {}, self.EVIDENCE.grammar), "")

    def test_refined_kinds(self):
        refine = lambda text, kind="idiom", dicts=("ncecd",): refine_kind(kind, text, list(dicts), {}, self.EVIDENCE)
        self.assertEqual(refine("glimmer pine"), "compound")
        self.assertEqual(refine("ease the glim"), "idiom")                   # a verb and its object
        self.assertEqual(refine("endeavour to do {sth}"), "pattern")
        self.assertEqual(refine("endeavour to do {sth}", "phrasal_verb"), "phrasal_verb")
        self.assertEqual(refine("glimmer pine", dicts=("ncecd", "oald")), "idiom")   # measured on NCECD only
        self.assertEqual(refine("endeavour to do {sth}", dicts=("ldoce",)), "pattern")  # any dictionary's grammar

    def test_phrasal_shape(self):
        lemmas = {"burnt": "burn", "sees": "see", "whistling": "whistle", "goes": "go"}
        self.assertTrue(phrasal_shape("put {sb} up to {sth}", {"put"}, lemmas))
        self.assertTrue(phrasal_shape("be burnt out", {"burn"}, lemmas))
        self.assertTrue(phrasal_shape("dish it out", {"dish"}, lemmas))
        self.assertTrue(phrasal_shape("look after {sb}", {"look"}, lemmas))
        self.assertFalse(phrasal_shape("not know what {sb} sees in {sb}", {"see"}, lemmas))
        self.assertFalse(phrasal_shape("it goes without saying", {"go"}, lemmas))
        self.assertFalse(phrasal_shape("be whistling in the dark", {"whistle"}, lemmas))
        self.assertTrue(phrasal_shape("psych {oneself} up", {"psych"}, lemmas))
        self.assertTrue(phrasal_shape("get on with", {"get"}, lemmas))
        self.assertTrue(phrasal_shape("call forth {sth}", {"call"}, lemmas))
        self.assertTrue(phrasal_shape("be patterned on {sth}", {"pattern"}, lemmas))
        self.assertTrue(phrasal_shape("not hold with {sth}", {"hold"}, lemmas))
        self.assertTrue(phrasal_shape("look forward to doing {sth}", {"look"}, lemmas))
        self.assertTrue(phrasal_shape("go beyond {sth}", {"go"}, lemmas))
        self.assertFalse(phrasal_shape("throw in the towel", {"throw"}, lemmas))
        self.assertTrue(phrasal_shape("strung out", {"string"}, lemmas, {"strung": frozenset({"string"})}))
        self.assertTrue(phrasal_shape("never tire of {sth}", {"tire"}, lemmas))
        self.assertTrue(phrasal_shape("put before", {"put"}, lemmas))
        self.assertTrue(phrasal_shape("run away with you", {"run"}, lemmas))

    def test_a_verb_form_outside_the_lemma_index_is_an_inflection_not_any_prefix(self):
        self.assertTrue(phrasal_shape("heading off", {"head"}, {}))
        self.assertTrue(phrasal_shape("glimmed out", {"glim"}, {}))     # a doubled consonant
        self.assertTrue(phrasal_shape("glaking up", {"glake"}, {}))     # a dropped "e"
        self.assertTrue(phrasal_shape("glied off", {"gly"}, {}))        # y -> ie
        self.assertTrue(phrasal_shape("glakes up", {"glake"}, {}))
        self.assertFalse(phrasal_shape("shower down", {"show"}, {}))    # another word starting like the verb
        self.assertFalse(phrasal_shape("glimpse out", {"glim"}, {}))

    def test_another_verbs_inflection_is_not_this_verbs(self):
        for variant, verb in (("glimed out", "glim"), ("gliming out", "glim"),   # glime's forms: glim doubles
                              ("glated up", "glat"), ("glakeed up", "glake"), ("glyed off", "gly"),
                              ("glimes out", "glim"), ("glyes off", "gly")):
            self.assertFalse(phrasal_shape(variant, {verb}, {}), variant)
        for variant, verb in (("glished out", "glish"), ("glishes out", "glish"), ("gloes off", "glo"),
                              ("glaffered up", "glaffer"), ("glaferred up", "glafer"),   # a longer verb: either
                              ("glavelled off", "glavel"), ("glaveled off", "glavel")):
            self.assertTrue(phrasal_shape(variant, {verb}, {}), variant)


if __name__ == "__main__":
    unittest.main()
