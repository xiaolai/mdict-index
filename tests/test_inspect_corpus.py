"""Corpus inspection on small generated MDict files (no copyrighted data)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mdict_utils.base.writemdict import MDictWriter

import inspect_corpus
from inspect_corpus import inspect_mdx


def write(path: Path, records: dict, encoding: str = "utf8") -> None:
    with open(path, "wb") as f:
        MDictWriter(records, title="t", description="d", encoding=encoding).write(f)


class InspectMdx(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_headwords_of_a_non_utf8_dictionary_are_read_correctly(self):
        # The reader hands every key over re-encoded as UTF-8, whatever the file's own encoding.
        write(self.dir / "g.mdx", {"café": "<b>x</b>", "茶": "<b>tea</b>"}, encoding="gbk")
        r = inspect_mdx(self.dir / "g.mdx")
        self.assertNotEqual(r["encoding"], "UTF-8")
        self.assertEqual((r["cjk_headwords"], r["multiword_headwords"]), (1, 0))
        self.assertEqual(r["unique_headwords"], 2)

    def test_cjk_anywhere_in_an_entry_counts(self):
        write(self.dir / "c.mdx", {"late": "<p>" + "x" * 5000 + " 迟</p>", "none": "<p>plain</p>",
                                   "rare": "<p>𠮷</p>"})
        self.assertAlmostEqual(inspect_mdx(self.dir / "c.mdx")["cjk_entry_share"], 0.667)


class Main(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.corpus = Path(self.tmp.name)
        for key in ("a", "b"):
            (self.corpus / key).mkdir()
            write(self.corpus / key / f"{key}.mdx", {"word": "<b>word</b>"})
        out = self.corpus / "_inspect"
        self.patches = [mock.patch.object(inspect_corpus, "CORPUS", self.corpus), mock.patch.object(inspect_corpus, "OUT", out)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.report = out / "report.json"

    def run_main(self, *argv):
        with mock.patch("sys.argv", ["inspect_corpus.py", *argv]), \
                mock.patch.object(inspect_corpus, "ProcessPoolExecutor", InlinePool):
            inspect_corpus.main()

    def test_only_updates_its_keys_and_keeps_the_rest_of_the_report(self):
        self.run_main()
        self.run_main("--only", "b")
        self.assertEqual(sorted(json.loads(self.report.read_text())), ["a", "b"])

    def test_unknown_only_keys_are_rejected(self):
        with self.assertRaises(SystemExit) as stop:
            self.run_main("--only", "typo")
        self.assertIn("typo", str(stop.exception))
        self.assertFalse(self.report.exists())


class InlinePool:
    """ProcessPoolExecutor stand-in: runs each job at once, inside the test's patches."""
    def __init__(self, workers):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def submit(self, fn, *args):
        from concurrent.futures import Future
        fut = Future()
        fut.set_result(fn(*args))
        return fut


if __name__ == "__main__":
    unittest.main()
