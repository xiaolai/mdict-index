"""The same-word tag from the two calibrated answers."""
import sqlite3
import unittest

from inventory.sameword import SAME, UNRELATED, ask_all, record, tag, to_ask


class Tag(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(tag(0.95, 0.05), "same word")
        self.assertEqual(tag(0.40, 0.30), "likely different words")
        self.assertEqual(tag(0.83, 0.17), "uncertain")     # refuse: the two answers disagree
        self.assertEqual(tag(None, None), "uncertain")      # no definitions to judge by



class AskAll(unittest.TestCase):
    def test_one_failure_keeps_every_other_answer_and_is_reported(self):
        def ask(question, state):
            if state == "bad":
                raise RuntimeError("jev failed")
            return {"good": 0.9, "fine": 0.1}[state]
        cache = {}
        failures = ask_all([("Q1", "good"), ("Q1", "bad"), ("Q2", "fine")], cache, ask)
        self.assertEqual(cache, {"Q1|good": 0.9, "Q2|fine": 0.1})
        self.assertEqual(len(failures), 1)
        self.assertIn("jev failed", failures[0])


class WithoutJev(unittest.TestCase):
    STATES = {1: "WORD: record ...", 2: "WORD: refuse ..."}
    CACHED = {f"{SAME[:20]}|WORD: record ...": 0.9, f"{UNRELATED[:20]}|WORD: record ...": 0.1}

    def test_a_missing_jev_stops_the_build_unless_degrading_is_chosen(self):
        with self.assertRaises(SystemExit) as stop:
            to_ask(self.STATES, self.CACHED, without_jev=False, jev=None)
        self.assertIn("--without-jev", str(stop.exception))

    def test_without_jev_asks_nothing_and_counts_what_it_skipped(self):
        self.assertEqual(to_ask(self.STATES, self.CACHED, without_jev=True, jev=None), ([], 2))

    def test_with_jev_asks_only_what_is_not_cached(self):
        todo, unasked = to_ask(self.STATES, self.CACHED, without_jev=False, jev="/usr/local/bin/jev")
        self.assertEqual(sorted(q[:20] for q, _ in todo), sorted([SAME[:20], UNRELATED[:20]]))
        self.assertEqual((todo[0][1], unasked), ("WORD: refuse ...", 0))

    def test_everything_cached_needs_no_jev(self):
        everything = {**self.CACHED, f"{SAME[:20]}|WORD: refuse ...": 0.2, f"{UNRELATED[:20]}|WORD: refuse ...": 0.4}
        self.assertEqual(to_ask(self.STATES, everything, without_jev=False, jev=None), ([], 0))

    def test_the_database_says_how_the_step_ran(self):
        con = sqlite3.connect(":memory:")
        record(con, unasked=2, questions=4)
        self.assertIn("without jev: 2 of 4", con.execute("SELECT value FROM build_info").fetchone()[0])
        record(con, unasked=0, questions=4)  # a later full run replaces the note
        self.assertEqual(con.execute("SELECT key, value FROM build_info").fetchall(), [("sameword", "every question answered by jev (asked now or cached)")])


if __name__ == "__main__":
    unittest.main()
