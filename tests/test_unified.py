"""Lookup behaviour of the unified database, on a synthetic in-memory database."""
import sqlite3
import unittest
import zlib

from build_unified import INDEXES, SCHEMA, norm
from unified_lookup import lookup, suggest


def make_db(entries, redirects):
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    for i, key in enumerate(["a", "b"], start=1):
        conn.execute(
            "INSERT INTO dictionary VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (i, key, key.upper(), None, None, "c", "current", None, "r", "f", "x.mdx", 2.0, "{}", "", ""),
        )
    conn.executemany(
        "INSERT INTO entry(dict_id, headword, norm, body) VALUES (?,?,?,?)",
        [(d, hw, norm(hw), zlib.compress(body.encode())) for d, hw, body in entries],
    )
    conn.executemany(
        "INSERT INTO redirect VALUES (?,?,?,?,?)", [(d, hw, norm(hw), t, norm(t)) for d, hw, t in redirects]
    )
    conn.executescript(INDEXES)
    conn.execute("INSERT INTO headword_fts(headword_fts) VALUES ('rebuild')")
    return conn


class Norm(unittest.TestCase):
    def test_case_accents_width_and_spaces_fold(self):
        self.assertEqual(norm("  Café  au   LAIT "), "cafe au lait")
        self.assertEqual(norm("ＯＡＬＤ"), "oald")
        self.assertEqual(norm("naïve"), norm("NAIVE"))

    def test_stress_marks_and_syllable_dots_are_not_part_of_the_word(self):
        self.assertEqual(norm("ˌblue-ˈblood"), "blue-blood")
        self.assertEqual(norm("re‧cap"), "recap")
        self.assertEqual(norm("base·ment·less"), "basementless")
        self.assertEqual(norm("serenˈdipitously"), "serendipitously")

    def test_cjk_is_unchanged(self):
        self.assertEqual(norm("牛津高阶"), "牛津高阶")


class Lookup(unittest.TestCase):
    def setUp(self):
        self.conn = make_db(
            entries=[(1, "take", "<b>take</b> A1"), (1, "take", "<b>take</b> A2"), (2, "Take", "<i>take</i> B"),
                     (2, "go", "go B"), (1, "café", "cafe A")],
            redirects=[(1, "took", "take"), (2, "took", "went"), (2, "went", "go"),
                       (1, "loop1", "loop2"), (1, "loop2", "loop1"), (2, "only-b", "take")],
        )
        self.addCleanup(self.conn.close)

    def test_direct_hits_from_every_dictionary_keep_homograph_order(self):
        hits = lookup(self.conn, "TAKE")
        self.assertEqual([(h.dict_key, h.html) for h in hits],
                         [("a", "<b>take</b> A1"), ("a", "<b>take</b> A2"), ("b", "<i>take</i> B")])
        self.assertTrue(all(h.via == () for h in hits))

    def test_redirect_chains_are_followed_within_each_dictionary(self):
        hits = lookup(self.conn, "took")
        # a has two "take" homographs; both are reached through the redirect.
        self.assertEqual([(h.dict_key, h.headword, h.via) for h in hits],
                         [("a", "take", ("take",)), ("a", "take", ("take",)), ("b", "go", ("went", "go"))])

    def test_redirects_never_cross_dictionaries(self):
        # "only-b" redirects to "take" in b; a has "take" but no "only-b".
        self.assertEqual([h.dict_key for h in lookup(self.conn, "only-b")], ["b"])

    def test_redirect_loops_terminate(self):
        self.assertEqual(lookup(self.conn, "loop1"), [])

    def test_every_target_of_an_ambiguous_redirect_is_followed(self):
        conn = make_db(
            entries=[(1, "alpha", "A"), (1, "beta", "B"), (1, "gamma", "G")],
            # "abbr" points at three entries; the first target is dead, the
            # second reaches its entry through one more hop.
            redirects=[(1, "abbr", "dead"), (1, "abbr", "via"), (1, "via", "beta"), (1, "abbr", "alpha"),
                       (1, "abbr", "gamma"), (1, "dup", "alpha"), (1, "dup", "alpha")],
        )
        self.addCleanup(conn.close)
        hits = lookup(conn, "abbr")
        self.assertEqual(sorted((h.headword, h.via) for h in hits),
                         [("alpha", ("alpha",)), ("beta", ("via", "beta")), ("gamma", ("gamma",))])
        # Two redirects to the same entry yield it once.
        self.assertEqual([h.headword for h in lookup(conn, "dup")], ["alpha"])

    def test_accents_fold_on_lookup(self):
        self.assertEqual([h.headword for h in lookup(self.conn, "CAFE")], ["café"])

    def test_suggestions_catch_misspellings(self):
        self.assertEqual(suggest(self.conn, "takke")[0], "take")
        self.assertEqual(suggest(self.conn, "caffe")[0], "cafe")
        self.assertEqual(suggest(self.conn, "zzzzzz"), [])
        self.assertEqual(lookup(self.conn, "missing"), [])

    def test_short_query_suggestions_are_relevant(self):
        conn = make_db(entries=[(1, w, w) for w in ["ab", "abc", "box", "cat", "dog", "zebra", "a"]], redirects=[])
        self.addCleanup(conn.close)
        got = suggest(conn, "bx")
        self.assertIn("box", got)
        self.assertFalse({"cat", "dog", "zebra"} & set(got), got)
        # Candidates that sort before the query are not excluded.
        self.assertIn("a", suggest(conn, "ax"))
        self.assertEqual(suggest(conn, "ab")[:2], ["ab", "abc"])


if __name__ == "__main__":
    unittest.main()
