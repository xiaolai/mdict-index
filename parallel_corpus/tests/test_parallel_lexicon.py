"""The bilingual lexicon and its alignment score."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from parallel.lexicon import build, gloss_bigrams, score

SCHEMA = """
CREATE TABLE s_entry (entry_id INTEGER PRIMARY KEY, headword TEXT NOT NULL, forms TEXT NOT NULL);
CREATE TABLE s_sense (id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL, ord INTEGER NOT NULL, definition_zh TEXT NOT NULL);
"""


class Glosses(unittest.TestCase):
    def test_bigrams_without_notes(self):
        self.assertEqual(gloss_bigrams("（木制）书架"), ["书架"])
        self.assertEqual(gloss_bigrams("瞭望台；台"), ["瞭望", "望台", "台"])

    def test_a_repeated_bigram_within_a_run_is_kept_once(self):
        self.assertEqual(gloss_bigrams("哈哈哈哈"), ["哈哈"])


class Build(unittest.TestCase):
    def test_headwords_and_their_forms_get_the_glosses(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "d.db"
            con = sqlite3.connect(db)
            con.executescript(SCHEMA)
            con.executemany("INSERT INTO s_entry VALUES (?,?,?)", [
                (1, "mouse", json.dumps(["mice"])), (2, "the", "[]"), (3, "band saw", "[]")])
            con.executemany("INSERT INTO s_sense VALUES (?,?,?,?)", [(1, 1, 1, "老鼠"), (2, 1, 2, "鼠标"),
                                                                    (3, 2, 1, "这个"), (4, 3, 1, "带锯")])
            con.commit()
            con.close()
            lexicon = build([db])
        self.assertEqual(lexicon["mouse"], ["老鼠", "鼠标"])
        self.assertEqual(lexicon["mice"], ["老鼠", "鼠标"])
        self.assertNotIn("the", lexicon)          # function words are dropped
        self.assertNotIn("band saw", lexicon)     # single words only

    def test_a_word_without_chinese_glosses_is_left_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "d.db"
            con = sqlite3.connect(db)
            con.executescript(SCHEMA)
            con.executemany("INSERT INTO s_entry VALUES (?,?,?)", [(1, "okay", "[]")])
            con.executemany("INSERT INTO s_sense VALUES (?,?,?,?)", [(1, 1, 1, "(OK)")])
            con.commit()
            con.close()
            self.assertNotIn("okay", build([db]))


LEXICON = {"window": frozenset({"窗户", "窗"}), "open": frozenset({"打开", "开"}),
           "cat": frozenset({"猫"}), "study": frozenset({"学习", "研究"})}


class Score(unittest.TestCase):
    def test_share_of_known_words_found_in_the_chinese(self):
        self.assertEqual(score("Mira opened the window.", "米拉打开了窗户。", LEXICON), (1.0, 2))
        self.assertEqual(score("Mira opened the window.", "他买了一辆车。", LEXICON), (0.0, 2))
        self.assertEqual(score("The cat opened it.", "猫把它弄开了。", LEXICON), (1.0, 2))

    def test_traditional_characters_match_simplified_glosses(self):
        self.assertEqual(score("Mira opened the window.", "米拉打開了窗戶。", LEXICON), (1.0, 2))

    def test_inflections_are_looked_up_by_their_stem(self):
        self.assertEqual(score("She studies cats.", "她研究猫。", LEXICON), (1.0, 2))

    def test_unknown_words_do_not_count(self):
        self.assertEqual(score("Zorbiton opened the window.", "佐比顿打开了窗户。", LEXICON), (1.0, 2))
        self.assertEqual(score("Zorbiton left.", "佐比顿走了。", LEXICON), (0.0, 0))

    def test_a_word_with_no_glosses_is_not_known(self):
        self.assertEqual(score("Mira opened the window okay.", "米拉打开了窗户。", {**LEXICON, "okay": frozenset()}),
                         (1.0, 2))

    def test_capitals_do_not_hide_words(self):
        self.assertEqual(score("CATS STUDY.", "猫学习。", LEXICON), score("Cats study.", "猫学习。", LEXICON))
        self.assertEqual(score("CATS STUDY.", "猫学习。", LEXICON), (1.0, 2))


if __name__ == "__main__":
    unittest.main()
