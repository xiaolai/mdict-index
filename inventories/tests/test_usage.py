"""Usage labels and grammar patterns from sense labels (invented fixtures)."""
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from inventory.usage import Tally, pattern, read_dictionary, upos_of, word_of, write

def _query(path: Path, sql: str) -> list[tuple]:
    with closing(sqlite3.connect(path)) as con:
        return con.execute(sql).fetchall()


SCHEMA = """
CREATE TABLE s_entry (entry_id INTEGER PRIMARY KEY, headword TEXT, pos TEXT);
CREATE TABLE s_sense (id INTEGER PRIMARY KEY, entry_id INTEGER, kind TEXT, pos TEXT, phrase TEXT, labels TEXT);
CREATE TABLE s_example (sense_id INTEGER, labels TEXT);
"""


def dictionary(folder, name, entries):
    con = sqlite3.connect(folder / f"{name}.db")
    con.executescript(SCHEMA)
    sid = 0
    for eid, (headword, entry_pos, senses) in enumerate(entries, 1):
        con.execute("INSERT INTO s_entry VALUES (?,?,?)", (eid, headword, json.dumps(entry_pos)))
        for kind, pos, phrase, labels, example_labels in senses:
            sid += 1
            con.execute("INSERT INTO s_sense VALUES (?,?,?,?,?,?)", (sid, eid, kind, pos, phrase, json.dumps(labels)))
            for ex in example_labels:
                con.execute("INSERT INTO s_example VALUES (?,?)", (sid, json.dumps(ex)))
    con.commit()
    con.close()
    return folder / f"{name}.db"


class Pieces(unittest.TestCase):
    def test_the_class_placeholder(self):
        self.assertEqual(pattern("~ to-inf", "ADJ"), "ADJ to-inf")
        self.assertEqual(pattern("~ n", "NOUN"), "N n")
        self.assertEqual(pattern("V n", "VERB"), "V n")
        self.assertEqual(pattern("~ that", ""), "~ that")

    def test_word_and_part_of_speech(self):
        self.assertEqual(word_of("Glim", "sense", ""), ("glim", "word"))
        self.assertEqual(word_of("glim", "phrase", "glim  it up"), ("glim it up", "phrase"))
        self.assertEqual(word_of("glim", "phrase", "glim somebody/something"), ("glim {sb/sth}", "phrase"))
        self.assertEqual(upos_of("", ["noun"]), "NOUN")
        self.assertEqual(upos_of("", ["noun", "verb"]), "")


class OncePerSense(unittest.TestCase):
    def test_two_labels_for_one_pattern_count_once(self):
        tally = Tally()
        tally.sense("cald", ("glim", "word"), "VERB", ["+ that", "V that"])
        self.assertEqual(dict(tally.grammar), {("glim", "word", "VERB", "V that"): {"cald": 1}})

    def test_two_labels_for_one_pattern_on_one_example_count_once(self):
        tally = Tally()
        tally.example("cald", ("glim", "word"), "VERB", ["+ that", "V that"])
        self.assertEqual(dict(tally.grammar_examples), {("glim", "word", "VERB", "V that"): {"cald": 1}})


class EntryPartOfSpeech(unittest.TestCase):
    def test_only_the_headword_inherits_its_entrys_part_of_speech(self):
        with tempfile.TemporaryDirectory() as tmp:
            tally = Tally()
            read_dictionary(dictionary(Path(tmp), "cobuild", [
                ("glim", ["noun"], [("sense", "", "", [], []), ("phrase", "", "take glim", [], []),
                                    ("derivative", "", "glimly", [], []), ("phrase", "verb", "do a glim", [], [])])]),
                tally)
        self.assertEqual(sorted(tally.senses), [("do a glim", "phrase", "VERB", "cobuild"),
                                                ("glim", "word", "NOUN", "cobuild"),
                                                ("glimly", "word", "", "cobuild"),
                                                ("take glim", "phrase", "", "cobuild")])


class Build(unittest.TestCase):
    def test_labels_and_patterns_with_their_share(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            tally = Tally()
            read_dictionary(dictionary(folder, "cald", [
                ("glim", ["noun"], [("sense", "noun", "", ["C", "INFORMAL"], []),
                                    ("sense", "noun", "", ["U"], [])]),
                ("glimmy", ["adjective"], [("sense", "adjective", "", ["UK"], [["+ to infinitive"]])])]), tally)
            read_dictionary(dictionary(folder, "oald", [
                ("glim", ["noun"], [("sense", "noun", "", ["informal", "zorblax"], [])])]), tally)
            summary = write(tally, folder / "l.db", folder / "g.db", folder / "u.tsv")
            labels = _query(folder / "l.db",
                            "SELECT word, pos, axis, value, dictionaries, senses, share FROM label ORDER BY word, value")
            grammar = _query(folder / "g.db",
                             "SELECT word, pos, pattern, senses, examples FROM pattern ORDER BY word, pattern")
            unread = (folder / "u.tsv").read_text()
        self.assertEqual(labels, [("glim", "NOUN", "register", "informal", '["cald", "oald"]', 2, 0.667),
                                  ("glimmy", "ADJ", "region", "GB", '["cald"]', 1, 1.0)])
        self.assertEqual(grammar, [("glim", "NOUN", "N count", 1, 0), ("glim", "NOUN", "N uncount", 1, 0),
                                   ("glimmy", "ADJ", "ADJ to-inf", 0, 1)])
        self.assertEqual(unread, "1\tzorblax\n")
        self.assertEqual(summary["label_uses"], {"read": 5, "unread": 1})


if __name__ == "__main__":
    unittest.main()
