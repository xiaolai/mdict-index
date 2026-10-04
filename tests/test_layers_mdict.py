"""Layers 1 and 3 end to end on small real MDict files written with mdict-utils.

Needs the project dependencies (requirements-dev.txt); the files are
generated, so no copyrighted data is involved.
"""
import sqlite3
import tempfile
import unittest
import zlib
from pathlib import Path

from mdict_utils.base.writemdict import MDictWriter

from build_resources import build as build_resources
from build_resources import norm_key
from serve_unified import _sound_name
from build_unified import SCHEMA, load, temp_beside


def write(path: Path, records: dict, is_mdd: bool = False, encoding: str = "utf8") -> None:
    with open(path, "wb") as f:
        MDictWriter(records, title="t", description="d", is_mdd=is_mdd, encoding=encoding).write(f)


ITEM = {"key": "a", "name": "A", "full": "Alpha", "zh": "", "status": "current", "latest": "1st"}
RECORD = {"n": "A dict", "loc": [{"p": "folder/a"}]}


class Layer1(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        write(self.dir / "a.mdx", {"take": "<b>take</b> 拿", "took": "@@@LINK=take", "Café": "<i>cafe</i>", "blank": " "})
        (self.dir / "a.css").write_text(".b{color:red}")
        (self.dir / "a.js").write_text("var x = 1;")
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.conn.executescript(SCHEMA)

    def tearDown(self):
        self.tmp.cleanup()

    def test_loads_entries_redirects_assets_and_matches_expected_counts(self):
        got = load(self.conn, 1, ITEM, "cat", RECORD, {"content_entries": 2, "redirects": 1, "empty": 1}, folder=self.dir)
        self.assertEqual(got, {"content_entries": 2, "redirects": 1, "empty": 1})
        rows = dict(self.conn.execute("SELECT norm, body FROM entry").fetchall())
        self.assertEqual(zlib.decompress(rows["take"]).decode(), "<b>take</b> 拿")
        self.assertIn("cafe", rows)  # accents folded in the lookup form
        self.assertEqual(self.conn.execute("SELECT headword, target_norm FROM redirect").fetchall(), [("took", "take")])
        css, js = self.conn.execute("SELECT stylesheet, script FROM dictionary").fetchone()
        self.assertIn(".b{color:red}", css)
        self.assertIn("var x = 1;", js)

    def test_headwords_of_a_non_utf8_dictionary_are_not_garbled(self):
        # The reader re-encodes every key as UTF-8; decoding with the file's own encoding garbles them.
        folder = self.dir / "gbk"
        folder.mkdir()
        write(folder / "g.mdx", {"café": "<b>x</b>", "tea": "@@@LINK=café"}, encoding="gbk")
        load(self.conn, 1, ITEM, "cat", RECORD, {"content_entries": 1, "redirects": 1, "empty": 0}, folder=folder)
        self.assertEqual(self.conn.execute("SELECT headword, norm FROM entry").fetchall(), [("café", "cafe")])
        self.assertEqual(self.conn.execute("SELECT target_norm FROM redirect").fetchall(), [("cafe",)])

    def test_only_the_stylesheets_entries_link_are_stored(self):
        # Packs ship alternative themes next to the one their entries link; concatenating them all
        # mixes conflicting rules into every page.
        folder = self.dir / "themed"
        folder.mkdir()
        write(folder / "t.mdx", {"take": '<link rel="stylesheet" href="t.css"><b>take</b>'})
        (folder / "t.css").write_text(".b{color:red}")
        (folder / "t.dark.css").write_text(".b{color:white}")
        (folder / "jquery.js").write_text("var jq = 1;")  # linked as "t.js", which the pack does not ship
        load(self.conn, 1, ITEM, "cat", RECORD, {"content_entries": 1, "redirects": 0, "empty": 0}, folder=folder)
        css, js = self.conn.execute("SELECT stylesheet, script FROM dictionary").fetchone()
        self.assertIn(".b{color:red}", css)
        self.assertNotIn("color:white", css)
        self.assertIn("var jq = 1;", js)  # nothing linked is shipped: every script is kept, as before

    def test_count_mismatch_against_inspection_fails_loudly(self):
        with self.assertRaises(AssertionError):
            load(self.conn, 1, ITEM, "cat", RECORD, {"content_entries": 3, "redirects": 1, "empty": 1}, folder=self.dir)


class NormPath(unittest.TestCase):
    def test_all_reference_styles_meet(self):
        # how the lookup reads an entry's reference: scheme dropped, then the literal .mdd key
        for ref in ["\\img\\A.png", "/img/a.png", "img/A.PNG", "./img/a.png", "file://img/a.png"]:
            self.assertEqual(norm_key(_sound_name(ref)), "img/a.png", ref)
        self.assertEqual(norm_key(_sound_name("sound://uk/Take.MP3")), "uk/take.mp3")
        # "%", "?" and "#" are filename characters, not URL syntax
        self.assertEqual(norm_key(_sound_name("sound://img/a%23b.png?v")), "img/a%23b.png?v")

    def test_mdd_keys_are_literal_paths_not_urls(self):
        # "#", "?" and "%" are filename characters in an .mdd key: two keys differing there stay two.
        keys = ["\\img\\a#first.png", "\\img\\a#second.png", "\\img\\b?x.png", "\\img\\c%20d.png"]
        self.assertEqual([norm_key(k) for k in keys], ["img/a#first.png", "img/a#second.png", "img/b?x.png", "img/c%20d.png"])
        self.assertEqual(norm_key("\\IMG\\A.png"), norm_key("/img/a.png"))


class TempBeside(unittest.TestCase):
    def test_each_build_gets_its_own_temporary_file_next_to_the_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b, c = temp_beside(root / "out.db"), temp_beside(root / "out.db"), temp_beside(root / "out.sqlite")
            self.assertEqual(len({a, b, c}), 3)
            self.assertTrue(all(p.parent == root and p.exists() for p in (a, b, c)))


class Layer3(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db, self.out = root / "u.db", root / "r.db"
        for key in ("a", "b"):
            (root / key).mkdir()
        # a: split across two volumes, with a case/slash duplicate path
        write(root / "a" / "a.mdd", {"\\img\\A.png": b"PNG-A", "\\IMG\\a.PNG": b"PNG-A-dup"}, is_mdd=True)
        write(root / "a" / "a.1.mdd", {"\\sound\\take.mp3": b"SHARED-AUDIO"}, is_mdd=True)
        # b: ships the very same audio bytes under another name
        write(root / "b" / "b.mdd", {"\\take_uk.mp3": b"SHARED-AUDIO"}, is_mdd=True)
        conn = sqlite3.connect(self.db)
        conn.executescript(SCHEMA)
        for i, key in enumerate(("a", "b"), start=1):
            conn.execute("INSERT INTO dictionary VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (i, key, key, None, None, "c", "current", None, "r", "f", "x.mdx", 2.0, "{}", "", ""))
        conn.commit()
        conn.close()
        self.report = dict(build_resources(self.db, self.out, corpus=root))

    def tearDown(self):
        self.tmp.cleanup()

    def test_keys_differing_only_in_url_delimiters_are_all_kept(self):
        root = Path(self.tmp.name)
        write(root / "b" / "b.mdd", {"\\a#first.png": b"FIRST", "\\a#second.png": b"SECOND"}, is_mdd=True)
        report = dict(build_resources(self.db, self.out, corpus=root))
        self.assertEqual((report["b"]["loaded"], report["b"]["duplicate_paths"]), (2, 0))

    def test_a_failed_build_leaves_no_temporary_file(self):
        root = Path(self.tmp.name)
        (root / "a" / "a.1.mdd").write_bytes(b"not an mdd")
        before = sorted(root.iterdir())
        with self.assertRaises(Exception):
            build_resources(self.db, root / "other.db", corpus=root)
        self.assertEqual(sorted(root.iterdir()), before)

    def test_every_key_accounted_for_across_volumes(self):
        a = self.report["a"]
        self.assertEqual((a["files"], a["keys"], a["loaded"], a["duplicate_paths"]), (2, 3, 2, 1))

    def test_identical_bytes_stored_once_and_resolvable_per_dictionary(self):
        conn = sqlite3.connect(self.out)
        self.addCleanup(conn.close)
        # The duplicate path is skipped (first in file order wins: "\\IMG\\a.PNG" sorts first), and the
        # audio both dictionaries ship is one blob: two blobs in all, none unreferenced.
        self.assertEqual(conn.execute("SELECT count(*) FROM blob").fetchone()[0], 2)
        orphans = conn.execute("SELECT count(*) FROM blob WHERE hash NOT IN (SELECT hash FROM resource)").fetchone()[0]
        self.assertEqual(orphans, 0)
        rows = conn.execute("SELECT r.dict_id, r.norm, b.data FROM resource r JOIN blob b ON b.hash = r.hash ORDER BY 1, 2").fetchall()
        self.assertEqual(rows, [(1, "img/a.png", b"PNG-A-dup"), (1, "sound/take.mp3", b"SHARED-AUDIO"),
                                (2, "take_uk.mp3", b"SHARED-AUDIO")])


if __name__ == "__main__":
    unittest.main()
