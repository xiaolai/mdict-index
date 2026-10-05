"""The same-word tag from the two calibrated answers."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from inventory.sameword import (ANSWERS, SAME, UNRELATED, ask_all, dump_answers, export_answers, load_shared,
                                questions_version,
                                record, state_key, tag, to_ask)


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

    def test_without_jev_asks_nothing_and_counts_what_it_skipped(self):
        self.assertEqual(to_ask(self.STATES, self.CACHED, {}, without_jev=True, jev=None), ([], 2))
        self.assertEqual(to_ask(self.STATES, self.CACHED, {}, without_jev=False, jev=None), ([], 2))

    def test_shared_answers_are_not_asked_again(self):
        shared = {state_key("WORD: refuse ..."): (0.2, 0.4)}
        self.assertEqual(to_ask(self.STATES, self.CACHED, shared, without_jev=False, jev=None), ([], 0))

    def test_with_jev_asks_only_what_is_not_cached(self):
        todo, unasked = to_ask(self.STATES, self.CACHED, {}, without_jev=False, jev="/usr/local/bin/jev")
        self.assertEqual(sorted(q[:20] for q, _ in todo), sorted([SAME[:20], UNRELATED[:20]]))
        self.assertEqual((todo[0][1], unasked), ("WORD: refuse ...", 0))

    def test_everything_cached_needs_no_jev(self):
        everything = {**self.CACHED, f"{SAME[:20]}|WORD: refuse ...": 0.2, f"{UNRELATED[:20]}|WORD: refuse ...": 0.4}
        self.assertEqual(to_ask(self.STATES, everything, {}, without_jev=False, jev=None), ([], 0))

    def test_the_database_says_how_the_step_ran(self):
        con = sqlite3.connect(":memory:")
        record(con, unasked=2, questions=4, shared=1)
        self.assertIn("2 of 4 questions unanswered", con.execute("SELECT value FROM build_info").fetchone()[0])
        record(con, unasked=0, questions=4, shared=1)  # a later full run replaces the note
        self.assertEqual(con.execute("SELECT key, value FROM build_info").fetchall(),
                         [("sameword", "every question answered: 1 contrast from the shared answers, 1 by jev")])


class SharedAnswers(unittest.TestCase):
    """inventories/sameword_answers.json: the mean of several jev answers per contrast, numbers only."""

    def test_export_keeps_numbers_only_the_mean_of_every_sample_for_current_contrasts(self):
        states = {1: "WORD: record ...", 2: "WORD: refuse ..."}
        samples = {f"{SAME[:20]}|{i}|{s}": p for s, ps in (("WORD: record ...", (0.9, 0.8, 0.7)), ("WORD: refuse ...", (0.2, 0.3, 0.4)))
                   for i, p in enumerate(ps)}
        samples.update({f"{UNRELATED[:20]}|{i}|{s}": 0.1 for s in states.values() for i in range(3)})
        samples[f"{SAME[:20]}|0|WORD: gone ..."] = 0.5  # a contrast no longer in the build
        doc = export_answers(states, samples, 3)
        self.assertEqual(doc["questions"], questions_version())
        self.assertEqual(doc["answers"], {state_key("WORD: record ..."): [0.8, 0.1], state_key("WORD: refuse ..."): [0.3, 0.1]})
        self.assertNotIn("record", json.dumps(doc))  # no word or definition, only hashes and numbers
        text = dump_answers(doc)
        self.assertEqual(json.loads(text), doc)
        self.assertEqual(len(text.splitlines()), 4 + 2 + 2 + 1)  # header, "answers" opening, a line each, closing

    def test_export_refuses_a_contrast_missing_a_sample(self):
        with self.assertRaises(ValueError):
            export_answers({1: "WORD: record ..."}, {f"{SAME[:20]}|0|WORD: record ...": 0.9}, 3)

    def test_answers_to_other_questions_are_not_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"
            path.write_text(json.dumps({"questions": "something else", "samples": 3, "answers": {"ab": [0.9, 0.1]}}))
            self.assertEqual(load_shared(path), {})

    def test_the_committed_answers_are_well_formed(self):
        doc = json.loads(ANSWERS.read_text())
        self.assertEqual(doc["questions"], questions_version())
        self.assertGreaterEqual(doc["samples"], 3)
        self.assertGreater(len(doc["answers"]), 500)
        for key, value in doc["answers"].items():
            self.assertRegex(key, r"^[0-9a-f]{64}$")
            self.assertEqual(len(value), 2)
            self.assertTrue(all(0 <= p <= 1 for p in value), key)


if __name__ == "__main__":
    unittest.main()
