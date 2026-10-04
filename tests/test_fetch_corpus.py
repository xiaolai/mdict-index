"""Corpus download planning and the resumable fetch, without the network."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fetch_corpus
from fetch_corpus import fetch, plan


class Plan(unittest.TestCase):
    def test_unknown_only_keys_are_rejected_before_anything_runs(self):
        with self.assertRaises(SystemExit) as stop:
            plan(50_000_000, {"no-such-dictionary"})
        self.assertIn("no-such-dictionary", str(stop.exception))

    def test_known_only_keys_select_their_files(self):
        key = plan(50_000_000, None)[0]["key"]
        self.assertEqual({j["key"] for j in plan(50_000_000, {key})}, {key})


class Fetch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "k" / "x.mdx"
        self.job = {"key": "k", "name": "x.mdx", "size": 4, "url": "https://example.invalid/x.mdx", "path": str(self.path)}

    def fake_curl(self, seen):
        def run(cmd, check):
            seen.append(self.path.stat().st_size if self.path.exists() else None)
            self.path.write_bytes(b"GOOD")
        return run

    def test_an_oversized_file_is_restarted_from_zero(self):
        # curl -C - can only append: resuming a file larger than the index says can never fix it.
        self.path.parent.mkdir()
        self.path.write_bytes(b"TOO LONG")
        seen = []
        with mock.patch.object(fetch_corpus.subprocess, "run", self.fake_curl(seen)):
            fetch(self.job)
        self.assertEqual(seen, [None])
        self.assertEqual(self.path.read_bytes(), b"GOOD")

    def test_a_partial_file_is_resumed(self):
        self.path.parent.mkdir()
        self.path.write_bytes(b"GO")
        seen = []
        with mock.patch.object(fetch_corpus.subprocess, "run", self.fake_curl(seen)):
            fetch(self.job)
        self.assertEqual(seen, [2])


if __name__ == "__main__":
    unittest.main()
