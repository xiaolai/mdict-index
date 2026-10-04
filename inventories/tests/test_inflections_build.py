"""Building the inflection inventory from parsed dictionaries."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from inventory.inflections import build


SCHEMA = """
CREATE TABLE s_entry (entry_id INTEGER PRIMARY KEY, headword TEXT, pos TEXT, forms TEXT, stub TEXT);
CREATE TABLE s_sense (id INTEGER PRIMARY KEY, entry_id INTEGER, kind TEXT, pos TEXT, labels TEXT);
CREATE TABLE s_pron (entry_id INTEGER, ord INTEGER, ipa TEXT, region TEXT);
"""


class Build(unittest.TestCase):
    def test_attested_forms_merge_and_missing_ones_are_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for name, entries in {"a": [("go", ["verb"], ["goes", "went", "gone", "going"]), ("walk", ["verb"], []),
                                        ("information", ["noun"], []), ("cat", ["noun"], []), ("child", ["noun"], [])],
                                  "b": [("go", ["verb"], ["went", "gone"]), ("cat", ["noun"], []), ("walk", ["verb"], []),
                                        ("child", ["verb"], [])]}.items():
                con = sqlite3.connect(tmp / f"{name}.db")
                con.executescript(SCHEMA)
                for i, (hw, pos, forms) in enumerate(entries, 1):
                    con.execute("INSERT INTO s_entry VALUES (?,?,?,?, '')", (i, hw, json.dumps(pos), json.dumps(forms)))
                    labels = ["uncountable"] if hw == "information" else []
                    con.execute("INSERT INTO s_sense VALUES (?,?, 'sense', ?, ?)", (i, i, pos[0], json.dumps(labels)))
                con.commit()
                con.close()
            build([tmp / "a.db", tmp / "b.db"], tmp / "out.db")
            con = sqlite3.connect(tmp / "out.db")
            rows = {r[:4]: r[4:] for r in con.execute(
                "SELECT form, lemma, upos, slot, kind, source, n FROM inflection")}
            con.close()
        self.assertEqual(rows[("went", "go", "VERB", "Past")], ("irregular", "attested", 2))
        self.assertEqual(rows[("walked", "walk", "VERB", "Past")], ("regular", "rule", 0))
        self.assertEqual(rows[("cats", "cat", "NOUN", "Plur")], ("regular", "rule", 0))
        self.assertNotIn(("goed", "go", "VERB", "Past"), rows)          # attested irregular: no regular form
        self.assertFalse(any(k[1] == "information" for k in rows))    # uncountable: no plural
        self.assertFalse(any(k[1] == "child" and k[2] == "VERB" for k in rows))  # a verb in one dictionary only

    def test_a_verb_with_an_irregular_past_gets_no_regular_participle(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for name in ("a", "b", "c"):
                con = sqlite3.connect(tmp / f"{name}.db")
                con.executescript(SCHEMA)
                con.execute("INSERT INTO s_entry VALUES (1, 'glive', '[\"verb\"]', '[\"glove\", \"gliven\"]', '')")
                # misglove: a past, as glove is; no dictionary prints its participle
                con.execute("INSERT INTO s_entry VALUES (2, 'misglive', '[\"verb\"]', ?, '')",
                            (json.dumps(["misglove"] if name == "a" else []),))
                con.commit()
                con.close()
            build([tmp / f"{n}.db" for n in "abc"], tmp / "out.db")
            con = sqlite3.connect(tmp / "out.db")
            rows = set(con.execute("SELECT form, slot FROM inflection WHERE lemma = 'misglive'"))
            con.close()
        self.assertIn(("misglove", "Past"), rows)
        self.assertFalse({r for r in rows if r[1] == "PastPart"}, rows)   # not "misglived"
        self.assertIn(("misgliving", "PresPart"), rows)                    # the other slots are still generated

    def test_a_past_printed_alone_is_no_participle_where_the_verb_itself_is_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            prints = {"a": ["glan", "glin", "glinning"], "b": ["glan", "glin"], "c": ["glins", "glan", "glin"],
                      # the verb first, its past alone: as often as the participle is printed
                      "d": ["glin", "glins", "glan", "glinning"], "e": ["glin", "glan"], "f": ["glin", "glan", "glins"]}
            for name, forms in prints.items():
                con = sqlite3.connect(tmp / f"{name}.db")
                con.executescript(SCHEMA)
                con.execute("INSERT INTO s_entry VALUES (1, 'glin', '[\"verb\"]', ?, '')", (json.dumps(forms),))
                con.execute("INSERT INTO s_entry VALUES (2, 'glit', '[\"verb\"]', '[\"glits\", \"glat\"]', '')")
                con.commit()
                con.close()
            build([tmp / f"{n}.db" for n in prints], tmp / "out.db")
            con = sqlite3.connect(tmp / "out.db")
            rows = {r[:3]: r[3] for r in con.execute("SELECT form, lemma, slot, n FROM inflection WHERE upos = 'VERB' "
                                                     "AND slot IN ('Past', 'PastPart')")}
            con.close()
        self.assertEqual(rows, {("glan", "glin", "Past"): 6, ("glin", "glin", "PastPart"): 3,
                                ("glat", "glit", "Past"): 6, ("glat", "glit", "PastPart"): 6})   # glat alone: both

    def test_a_few_dictionaries_printing_the_verb_as_its_participle_overrule_no_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            prints = {"a": ["glat", "glit"], "b": ["glat", "glit", "glitting"], "c": ["glits", "glat"], "d": ["glat"],
                      "e": ["glat", "glitting"],
                      # a verb with a participle many print as one: the verb itself is none
                      "f": ["glam", "glim", "glimmen"], "g": ["glam", "glim", "glimmen"], "h": ["glam", "glimmen"],
                      "i": ["glam", "glimmen"]}
            for name, forms in prints.items():
                con = sqlite3.connect(tmp / f"{name}.db")
                con.executescript(SCHEMA)
                lemma = "glim" if name in "fghi" else "glit"
                con.execute("INSERT INTO s_entry VALUES (1, ?, '[\"verb\"]', ?, '')", (lemma, json.dumps(forms)))
                con.execute("INSERT INTO s_entry VALUES (2, ?, '[\"verb\"]', '[]', '')", ("glit" if lemma == "glim" else "glim",))
                con.commit()
                con.close()
            build([tmp / f"{n}.db" for n in prints], tmp / "out.db")
            con = sqlite3.connect(tmp / "out.db")
            rows = {r[:2]: r[2] for r in con.execute("SELECT form, slot, n FROM inflection WHERE slot = 'PastPart'")}
            con.close()
        self.assertEqual(rows[("glat", "PastPart")], 3)    # c, d, e: printed alone, glat is both
        self.assertEqual(rows[("glit", "PastPart")], 2)    # a, b: kept, beside it
        self.assertNotIn(("glim", "PastPart"), rows)        # f, g: beside glimmen, printed as one by all four
        self.assertEqual(rows[("glimmen", "PastPart")], 4)

    def test_one_dictionary_printing_a_t_verb_as_its_past_is_believed_over_the_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for name in ("a", "b"):
                con = sqlite3.connect(tmp / f"{name}.db")
                con.executescript(SCHEMA)
                con.execute("INSERT INTO s_entry VALUES (1, 'glut', '[\"verb\"]', ?, '')",
                            (json.dumps(["glutting", "glut"] if name == "a" else []),))
                con.execute("INSERT INTO s_entry VALUES (2, 'glum', '[\"verb\"]', ?, '')",
                            (json.dumps(["gluming", "glum"] if name == "a" else []),))
                con.commit()
                con.close()
            build([tmp / "a.db", tmp / "b.db"], tmp / "out.db")
            con = sqlite3.connect(tmp / "out.db")
            rows = {r[:3]: r[3] for r in con.execute("SELECT form, lemma, slot, source FROM inflection "
                                                     "WHERE slot IN ('Past', 'PastPart')")}
            con.close()
        self.assertEqual({k: v for k, v in rows.items() if k[1] == "glut"},
                         {("glut", "glut", "Past"): "attested", ("glut", "glut", "PastPart"): "attested"})   # not glutted
        self.assertEqual(rows[("glummed", "glum", "Past")], "rule")   # one dictionary, another shape: the rule

    def test_a_lone_regular_form_beside_a_well_attested_irregular_is_nonstandard(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for name in ("a", "b", "c", "d"):
                forms = ["went", "gone"] + (["goed"] if name == "d" else [])
                con = sqlite3.connect(tmp / f"{name}.db")
                con.executescript(SCHEMA)
                con.execute("INSERT INTO s_entry VALUES (1, 'go', '[\"verb\"]', ?, '')", (json.dumps(forms),))
                con.commit()
                con.close()
            build([tmp / f"{n}.db" for n in "abcd"], tmp / "out.db")
            con = sqlite3.connect(tmp / "out.db")
            self.assertEqual(con.execute("SELECT count(*) FROM inflection WHERE form = 'goed'").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT kind FROM other WHERE form = 'goed'").fetchone()[0], "nonstandard")
            con.close()

    def test_the_tsv_export_has_every_row(self):
        from inventory.inflection_io import export_tsv
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            con = sqlite3.connect(tmp / "a.db")
            con.executescript(SCHEMA)
            con.execute("INSERT INTO s_entry VALUES (1, 'walk', '[\"verb\"]', '[\"walks\", \"walked\", \"walking\"]', '')")
            con.commit()
            con.close()
            build([tmp / "a.db"], tmp / "out.db")
            self.assertEqual(export_tsv(tmp / "out.db", tmp / "out.tsv"), 4)  # walks, walked (past, participle), walking
            lines = (tmp / "out.tsv").read_text().splitlines()
            self.assertEqual(lines[0].split("\t"), ["form", "lemma", "upos", "slot", "region", "kind", "source", "n"])
            self.assertEqual(len(lines), 5)

    def _build(self, tmp, dicts, prons=()):
        for name, entries in dicts.items():
            con = sqlite3.connect(tmp / f"{name}.db")
            con.executescript(SCHEMA)
            for i, (hw, pos, forms) in enumerate(entries, 1):
                con.execute("INSERT INTO s_entry VALUES (?,?,?,?, '')", (i, hw, json.dumps(pos), json.dumps(forms)))
                con.execute("INSERT INTO s_sense VALUES (?,?, 'sense', ?, '[]')", (i, i, pos[0] if pos else ""))
            con.executemany("INSERT INTO s_pron VALUES (?,?,?,?)", prons)
            con.commit()
            con.close()
        build([tmp / f"{n}.db" for n in dicts], tmp / "out.db")
        con = sqlite3.connect(tmp / "out.db")
        rows = set(con.execute("SELECT form, lemma, upos, slot, source FROM inflection"))
        con.close()
        return rows

    def test_the_uk_pronunciation_decides_the_stress(self):
        from inventory.inflection_io import _entries
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "a.db"
            con = sqlite3.connect(db)
            con.executescript(SCHEMA)
            con.execute("INSERT INTO s_entry VALUES (1, 'glimmet', '[\"verb\"]', '[]', '')")
            con.executemany("INSERT INTO s_pron VALUES (?,?,?,?)",
                            [(1, 1, "ˈɡlɪmɪt", "us"), (1, 2, "ɡlɪˈmet", "uk"), (1, 3, "ˈɡlɪmət", "uk")])
            con.commit()
            con.close()
            self.assertEqual([e.final_stress for e in _entries(db)], [True])

    def test_a_noun_in_s_or_a_plural_entry_gets_no_plural(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = self._build(Path(tmp), {
                "a": [("glens", ["noun"], []), ("glumbers", ["plural noun"], []), ("glimworks", ["noun"], []),
                      ("glimwork", ["noun"], []), ("glimnetics", ["noun"], []), ("glimae", ["noun"], [])],
                "b": [("glens", ["N-COUNT"], []), ("glumbers", ["noun"], []), ("glimworks", ["noun"], []),
                      ("glimwork", ["noun"], []), ("glimnetics", ["noun"], []), ("glimae", ["N-PLURAL"], [])]})
        self.assertFalse(any(r[1] == "glens" for r in rows))    # counted but no plural printed: zero (schnapps)
        self.assertFalse(any(r[1] == "glimnetics" for r in rows))       # in -s and nobody counts it
        self.assertFalse(any(r[1] == "glimae" for r in rows))           # a plural, whatever its ending
        self.assertFalse(any(r[1] == "glumbers" for r in rows))         # printed a plural noun
        self.assertFalse(any(r[1] == "glimworks" for r in rows))        # another noun's regular plural
        self.assertIn(("glimworks", "glimwork", "NOUN", "Plur", "rule"), rows)

    def test_a_verb_in_ed_gets_forms_unless_it_is_anothers_participle(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = self._build(Path(tmp), {
                "a": [("gleed", ["verb"], []), ("glimtitle", ["verb"], ["glimtitled"]), ("glimtitled", ["verb"], [])],
                "b": [("gleed", ["verb"], []), ("glimtitle", ["verb"], []), ("glimtitled", ["verb"], [])]})
        self.assertIn(("gleeds", "gleed", "VERB", "3Sg", "rule"), rows)
        self.assertIn(("gleeding", "gleed", "VERB", "PresPart", "rule"), rows)
        self.assertFalse(any(r[1] == "glimtitled" for r in rows))       # a participle listed as its own entry

    def test_a_dictionary_without_parts_of_speech_borrows_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for name, entries in {"a": [("dial", ["noun", "verb"], [])], "lpd": [("dial", [], ["dials", "dialled"])]}.items():
                con = sqlite3.connect(tmp / f"{name}.db")
                con.executescript(SCHEMA)
                for i, (hw, pos, forms) in enumerate(entries, 1):
                    con.execute("INSERT INTO s_entry VALUES (?,?,?,?, '')", (i, hw, json.dumps(pos), json.dumps(forms)))
                con.commit()
                con.close()
            build([tmp / "a.db", tmp / "lpd.db"], tmp / "out.db")
            con = sqlite3.connect(tmp / "out.db")
            rows = set(con.execute("SELECT form, upos, slot, source FROM inflection WHERE lemma = 'dial'"))
            con.close()
        self.assertIn(("dials", "VERB", "3Sg", "attested"), rows)
        self.assertIn(("dialled", "VERB", "Past", "attested"), rows)


if __name__ == "__main__":
    unittest.main()
