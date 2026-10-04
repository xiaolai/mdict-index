"""The parser developer tool's coverage run, on a synthetic layer-1 database and stub parsers."""
import importlib
import sqlite3
import sys
import unittest
import zlib
from types import SimpleNamespace

from build_unified import SCHEMA, norm
from structured import devtool
from structured.devtool import _coverage, rows
from structured.model import Entry, Sense


def database(headwords):
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO dictionary VALUES (1,'a','A',NULL,NULL,'c','current',NULL,'r','f','x.mdx',2.0,'{}','','')")
    conn.executemany("INSERT INTO entry(dict_id, headword, norm, body) VALUES (1,?,?,?)",
                     [(h, norm(h), zlib.compress(f"<b>{h}</b>".encode())) for h in headwords])
    return conn


def module(parse):
    return SimpleNamespace(COVERS="definitions", MIN_COVERAGE=0.5, parse=parse)


class Import(unittest.TestCase):
    def test_importing_leaves_the_importers_path_alone(self):
        # Only run as a script does it swap its own folder for scripts/; a test runner's sys.path[0] stays.
        saved = list(sys.path)
        sys.path.insert(0, "/an/importers/folder")
        try:
            importlib.reload(devtool)
            self.assertEqual(sys.path[0], "/an/importers/folder")
        finally:
            sys.path[:] = saved


class Rows(unittest.TestCase):
    def setUp(self):
        self.conn = database(["a", "b", "c"])
        self.addCleanup(self.conn.close)

    def test_a_limit_means_the_same_with_and_without_a_seed(self):
        for limit, n in [(0, 0), (2, 2), (None, 3)]:
            self.assertEqual(len(list(rows(self.conn, "a", limit))), n, limit)
            self.assertEqual(len(list(rows(self.conn, "a", limit, seed=1))), n, limit)

    def test_a_negative_limit_is_refused(self):
        for seed in (None, 1):
            with self.assertRaises(ValueError):
                list(rows(self.conn, "a", -1, seed=seed))


class Coverage(unittest.TestCase):
    def setUp(self):
        self.conn = database(["a", "b"])
        self.addCleanup(self.conn.close)

    def test_a_parser_returning_no_entry_is_reported_and_the_run_continues(self):
        r = _coverage(module(lambda h, html: None if h == "a" else Entry(h, senses=(Sense(definition="x"),))),
                      "a", self.conn, None, None, 0)
        self.assertEqual((r["entries"], r["exceptions"]), (2, 1))
        self.assertIn("NoneType", r["exception_examples"][0])

    def test_problem_entries_counts_entries_not_violations(self):
        def dirty(h, html):  # three violations in one entry
            return Entry(" " + h, etymology=" x", senses=(Sense(definition=" y"),)) if h == "a" else Entry(h)
        r = _coverage(module(dirty), "a", self.conn, None, None, 0)
        self.assertEqual(r["problem_entries"], 1)
        self.assertEqual(sum(r["problems"].values()), 3)


if __name__ == "__main__":
    unittest.main()
