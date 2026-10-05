"""The invariant checker: an empty or unreadable inventory must fail, not pass."""
import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from inventory.check import CHECKS, check_db, main, notes
from inventory.collocations import SCHEMA


def collocations_db(path: Path, dictionaries: str = '["ocd"]', rows: bool = True) -> Path:
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    if rows:
        con.execute("INSERT INTO collocation VALUES (1, 'glim', 'NOUN', 'adj_noun', 'bold ~', 'fixed', '[\"bold ~\"]', "
                    "?, 1, 1, '', '', '[]')", (dictionaries,))
        con.execute("INSERT INTO pattern VALUES (1, 'bold ~', 'bold ~')")
    con.commit()
    con.close()
    return path


class CheckDb(unittest.TestCase):
    def test_a_sound_inventory_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = collocations_db(Path(tmp) / "collocations.db")
            self.assertEqual(check_db("collocations.db", path), [])

    def test_an_empty_inventory_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = collocations_db(Path(tmp) / "collocations.db", rows=False)
            failures = check_db("collocations.db", path)
        self.assertTrue(failures and all("empty" in f for f in failures), failures)

    def test_malformed_json_is_a_failure_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = collocations_db(Path(tmp) / "collocations.db", dictionaries="not json")
            failures = check_db("collocations.db", path)
        self.assertTrue(any("cannot run" in f for f in failures), failures)

    def test_every_inventory_is_checked_after_a_broken_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            collocations_db(Path(tmp) / "collocations.db", dictionaries="not json")
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(Path(tmp)), 1)
        reported = out.getvalue()
        self.assertIn("cannot run", reported)
        for name in CHECKS:  # the ones after it too: missing, reported, not skipped by a crash
            self.assertIn(name, reported)


class Notes(unittest.TestCase):
    def test_a_degraded_step_is_reported_from_its_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = collocations_db(Path(tmp) / "collocations.db")
            self.assertEqual(notes(path), [])  # no build_info: nothing to say
            con = sqlite3.connect(path)
            con.execute("CREATE TABLE build_info (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            con.execute("INSERT INTO build_info VALUES ('sameword', 'without jev: 4 of 6 questions unasked')")
            con.commit()
            con.close()
            self.assertEqual(notes(path), ["sameword: without jev: 4 of 6 questions unasked"])
            self.assertEqual(check_db("collocations.db", path), [])  # degraded is still valid


if __name__ == "__main__":
    unittest.main()
