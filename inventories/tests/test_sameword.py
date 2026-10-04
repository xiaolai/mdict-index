"""The same-word tag from the two calibrated answers."""
import unittest

from inventory.sameword import ask_all, tag


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


if __name__ == "__main__":
    unittest.main()
