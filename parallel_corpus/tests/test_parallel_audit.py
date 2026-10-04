"""The per-dictionary precision audit (jev is replaced by a stand-in judge)."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parallel import audit
from parallel.audit import NothingToAudit, import_labels, needs_review, sample, screen, summarize
from parallel.extract import stage


def staged(tmp, records):
    path = Path(tmp) / "d.jsonl.gz"
    stage(iter(records), path)
    return path


GOOD = [{"en": f"She opened window number {i} today.", "zh": f"她今天打开了{i}号窗户。", "hw": "open"} for i in range(200)]
INVALID = {"en": "Er öffnet das Fenster, weil es zu warm ist.", "zh": "他打开窗户，因为太热了。", "hw": "x"}


class Sample(unittest.TestCase):
    def test_the_sample_is_uniform_repeatable_and_only_of_accepted_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = staged(tmp, [INVALID] * 50 + GOOD)
            a, b = sample(path, 20, "seed"), sample(path, 20, "seed")
            self.assertEqual(a, b)
            self.assertEqual(len(a), 20)
            self.assertNotIn(INVALID, a)
            self.assertNotEqual(a, sample(path, 20, "other"))
            self.assertGreater(max(GOOD.index(r) for r in a), 100)  # not just the first records

    def test_a_small_dictionary_is_sampled_whole(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(len(sample(staged(tmp, GOOD[:5]), 60, "s")), 5)


def scores(usable):
    return {"usable": usable, "aligned": 0.9, "residue": 0.1}


class Screen(unittest.TestCase):
    def test_pairs_below_the_screen_are_flagged(self):
        def ask(record):  # every fourth pair looks unusable
            return scores(0.2 if int(record["en"].split()[4]) % 4 == 0 else 0.8)
        with tempfile.TemporaryDirectory() as tmp:
            judged = screen(staged(tmp, GOOD), "s", 200, ask, jobs=4)
        self.assertEqual(sum(j["flagged"] for j in judged), 50)
        self.assertEqual(set(judged[0]), {"en", "zh", "hw", "usable", "aligned", "residue", "flagged"})

    def test_a_dictionary_with_nothing_to_audit_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(NothingToAudit):
                screen(staged(tmp, [INVALID]), "s", 60, lambda r: {})

    def test_a_failing_judge_fails_the_audit(self):
        def ask(record):
            raise RuntimeError("jev exited 2")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                screen(staged(tmp, GOOD), "s", 10, ask)


def judged(flags):
    return [{"flagged": f} for f in flags]


class Summarize(unittest.TestCase):
    def test_flags_count_as_bad_until_reviewed(self):
        pairs = judged([True] * 6 + [False] * 54)
        self.assertEqual(summarize(pairs, {}),
                         {"n": 60, "flagged": 6, "reviewed": 0, "bad": 0, "precision": 0.9})
        review = {"0": "bad", "1": "good", "2": "good", "3": "good", "4": "good", "5": "good"}
        self.assertEqual(summarize(pairs, review)["precision"], 1 - 1 / 60)

    def test_pairs_the_rules_now_reject_leave_the_sample(self):
        pairs = judged([True, True, False, False])
        self.assertEqual(summarize(pairs, {"0": "bad"}, excluded=frozenset({"0"})),
                         {"n": 3, "flagged": 1, "reviewed": 0, "bad": 0, "precision": 1 - 1 / 3})

    def test_review_labels_are_checked(self):
        pairs = judged([True, False])
        with self.assertRaises(ValueError):
            summarize(pairs, {"1": "bad"})     # not a flagged pair
        with self.assertRaises(ValueError):
            summarize(pairs, {"0": "maybe"})

    def test_only_reviews_that_could_change_the_verdict_are_asked_for(self):
        few = summarize(judged([True] * 2 + [False] * 58), {})       # passes as it is
        many = summarize(judged([True] * 10 + [False] * 50), {})     # could pass if most flags are false
        hopeless = summarize(judged([True] * 10 + [False] * 50), {str(i): "bad" for i in range(10)})
        self.assertEqual([needs_review(s, 0.95) for s in (few, many, hopeless)], [False, True, False])
        empty = {"n": 0, "flagged": 0, "reviewed": 0, "bad": 0, "precision": 0.0}
        self.assertFalse(needs_review(empty, 0.95))

    def test_precision_is_not_rounded_up_to_the_threshold(self):
        # 51 flags in 1,019 pairs is 0.94995...: rounding to 4 places would make it 0.95 and admit it
        s = summarize(judged([True] * 51 + [False] * 968), {})
        self.assertLess(s["precision"], 0.95)
        self.assertTrue(needs_review(s, 0.95))


class ImportLabels(unittest.TestCase):
    def test_labels_merge_into_review_files_and_are_checked(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "d.jsonl").write_text("".join(json.dumps({"flagged": f}) + "\n" for f in (True, False, True)))
            self.assertEqual(import_labels({"d": {"0": "bad"}}, folder), 1)
            self.assertEqual(import_labels({"d": {"2": "good"}}, folder), 1)
            self.assertEqual(json.loads((folder / "d.review.json").read_text()), {"0": "bad", "2": "good"})
            with self.assertRaises(ValueError):
                import_labels({"d": {"1": "good"}}, folder)  # pair 1 was never flagged
            self.assertEqual(json.loads((folder / "d.review.json").read_text()), {"0": "bad", "2": "good"})


class Main(unittest.TestCase):
    """The command line, on a temporary data folder with jev replaced."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        (self.data / "selected.json").write_text(json.dumps([{"id": "d", "name": "dict d", "keep": True}]))
        self.stage(GOOD[:20])
        for patch in (mock.patch.object(audit, "PARALLEL", self.data),
                      mock.patch.object(audit, "jev", lambda r: scores(0.2 if r["en"].split()[4] == "3" else 0.9))):
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def stage(self, records):
        from parallel.extract import stage
        stage(iter(records), self.data / "staged" / "d.jsonl.gz")

    def run_main(self, *args):
        with mock.patch.object(sys, "argv", ["audit.py", *args]), contextlib.redirect_stdout(io.StringIO()) as out, \
                contextlib.redirect_stderr(io.StringIO()):
            audit.main()
        return out.getvalue()

    def results(self):
        return json.loads((self.data / "audit.json").read_text())

    def test_a_rescreen_that_finds_nothing_replaces_the_old_sample(self):
        self.run_main()
        (self.data / "audit" / "d.review.json").write_text(json.dumps({"3": "good"}))
        self.run_main()
        self.assertEqual(self.results()["d"]["precision"], 1.0)
        self.stage([INVALID])                      # the dictionary now has nothing the rules accept
        self.run_main("--redo")
        self.assertEqual((self.results()["d"]["n"], self.results()["d"]["precision"]), (0, 0.0))
        self.run_main()                            # a later run must not restore the stale sample
        self.assertEqual((self.results()["d"]["n"], self.results()["d"]["precision"]), (0, 0.0))
        self.assertIn("note", self.results()["d"])
        self.assertFalse((self.data / "audit" / "d.review.json").exists())

    def test_a_malformed_jev_answer_fails_the_run(self):
        with mock.patch.object(audit, "jev", lambda r: scores(float("not a number"))):
            with self.assertRaises(ValueError):
                self.run_main()
        self.assertFalse((self.data / "audit.json").exists())

    def test_the_queue_leaves_out_pairs_the_rules_now_reject(self):
        self.run_main()
        judged = [json.loads(line) for line in (self.data / "audit" / "d.jsonl").read_text().splitlines()]
        flagged = [i for i, j in enumerate(judged) if j["flagged"]]
        self.assertEqual(len(flagged), 1)
        # more flags, one of them on a pair the current rules reject
        judged[0] = {**INVALID, **scores(0.2), "flagged": True}
        for i in (1, 2, 4):
            judged[i] = {**judged[i], "usable": 0.2, "flagged": True}
        (self.data / "audit" / "d.jsonl").write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in judged))
        self.run_main()
        queue = json.loads(self.run_main("--queue"))
        self.assertTrue(queue["d"]["pairs"])
        self.assertNotIn("0", queue["d"]["pairs"])


if __name__ == "__main__":
    unittest.main()
