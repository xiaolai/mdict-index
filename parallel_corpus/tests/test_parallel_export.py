"""Exporting parallel.db."""
import io
import json
import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from parallel.build import build
from parallel.export import export, rows, write
from parallel.extract import stage


class Export(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        stage(iter([{"en": "Wait, please.", "zh": "請等一下。", "hw": "wait"},
                    {"en": "Wait please!", "zh": "请等一下！", "hw": "wait"},          # same cluster
                    {"en": "Tom & Jerry agree that 3 < 5 again.", "zh": "汤姆和杰瑞\t又同意3小于5。", "hw": "agree"},
                    {"en": "Tom & Jerry <are> friends again.", "zh": "汤姆和杰瑞又成了朋友。", "hw": "friend"},
                    {"en": "heavy rain", "zh": "大雨", "hw": "rain"}]), d / "staged" / "a.jsonl.gz")
        choice = {"id": "a", "name": "Dict A", "keep": True, "source": "download", "pairs_per_100k_chars": 1.0,
                  "order": "en-zh", "alignment": 0.7}
        build([choice], d / "staged", {"a": {"precision": 0.99}}, d / "p.db")
        self.con = sqlite3.connect(d / "p.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def export(self, fmt, all_pairs=False, kind=None):
        out = io.StringIO()
        n = write(fmt, rows(self.con, all_pairs, kind), out)
        return n, out.getvalue()

    def test_representatives_by_default_everything_with_all(self):
        self.assertEqual(self.export("tsv")[0], 3)
        self.assertEqual(self.export("tsv", all_pairs=True)[0], 4)
        self.assertEqual(self.export("tsv", kind="phrase")[0], 2)  # "Wait, please." (2 words) and "heavy rain"

    def test_text_that_looks_like_markup_never_reaches_an_export(self):
        self.assertNotIn("<are>", self.export("tsv", all_pairs=True)[1])

    def test_jsonl_carries_simplified_and_printed_chinese_and_sources(self):
        first = json.loads(self.export("jsonl")[1].splitlines()[0])
        self.assertEqual((first["zh"], first["zh_printed"], first["sources"]), ("请等一下。", "請等一下。", ["Dict A"]))

    def test_tsv_fields_cannot_break_columns(self):
        lines = self.export("tsv")[1].splitlines()
        self.assertEqual(lines[0], "en\tzh\tkind")
        self.assertTrue(all(line.count("\t") == 2 for line in lines))

    def test_tmx_is_well_formed_and_escaped(self):
        root = ET.fromstring(self.export("tmx")[1])
        tus = root.findall("./body/tu")
        self.assertEqual(len(tus), 3)
        segs = [s.text for s in tus[1].iter("seg")]
        self.assertEqual(segs[0], "Tom & Jerry agree that 3 < 5 again.")
        langs = [t.get("{http://www.w3.org/XML/1998/namespace}lang") for t in tus[0].iter("tuv")]
        self.assertEqual(langs, ["en", "zh-CN"])


class ExportFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def database(self, name, dictionary="Dict A | B"):
        stage(iter([{"en": "She opened the window again.", "zh": "她又打开了窗户。", "hw": "open"}]),
              self.dir / "staged" / "a.jsonl.gz")
        choice = {"id": "a", "name": dictionary, "keep": True, "source": "download", "pairs_per_100k_chars": 1.0,
                  "order": "en-zh", "alignment": 0.7}
        db = self.dir / name
        build([choice], self.dir / "staged", {"a": {"precision": 0.99}}, db)
        return db

    def test_a_dictionary_name_with_the_separator_stays_one_source(self):
        db = self.database("p.db")
        out = self.dir / "out.jsonl"
        self.assertEqual(export(db, "jsonl", out), 1)
        self.assertEqual(json.loads(out.read_text())["sources"], ["Dict A | B"])

    def test_the_output_must_not_be_the_database(self):
        db = self.database("p.db")
        before = db.read_bytes()
        with self.assertRaises(ValueError):
            export(db, "tsv", self.dir / "." / "p.db")
        self.assertEqual(db.read_bytes(), before)

    def test_a_database_path_with_uri_characters_is_opened_as_given(self):
        db = self.database("odd?name#1.db", dictionary="the right one")
        self.database("odd", dictionary="the wrong one")  # what "file:.../odd?name#1.db" would open instead
        out = self.dir / "out.jsonl"
        self.assertEqual(export(db, "jsonl", out), 1)
        self.assertEqual(json.loads(out.read_text())["sources"], ["the right one"])

    def test_the_working_file_is_private_to_this_export(self):
        db = self.database("p.db")
        out = self.dir / "out.tsv"
        other = self.dir / "out.tsv.part"   # what a concurrent export of the same output used to share
        other.write_text("another export")
        export(db, "tsv", out)
        self.assertEqual(other.read_text(), "another export")
        self.assertEqual(sorted(p.name for p in self.dir.glob("out.tsv*")), ["out.tsv", "out.tsv.part"])

    def test_a_failed_export_leaves_no_working_file(self):
        from unittest import mock
        db = self.database("p.db")
        with mock.patch("parallel.export.write", side_effect=ValueError("character not allowed in XML")):
            with self.assertRaises(ValueError):
                export(db, "tmx", self.dir / "out.tmx")
        self.assertEqual(list(self.dir.glob("out.tmx*")), [])
        with self.assertRaises(ValueError):
            export(db, "xml", self.dir / "out.xml")  # not a format


class XmlGuard(unittest.TestCase):
    def test_a_character_xml_forbids_stops_the_tmx(self):
        record = {"id": 1, "en": "Bad \x03 text here.", "zh_hans": "坏文本。", "zh": "坏文本。", "kind": "sentence",
                  "variants": 1, "dictionaries": ["d"]}
        with self.assertRaises(ValueError):
            write("tmx", iter([record]), io.StringIO())


if __name__ == "__main__":
    unittest.main()
