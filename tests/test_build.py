"""Behavioural tests for the site build: grouping, dedupe, tracking, guards."""
import json
import tempfile
import unittest
from pathlib import Path

# Run with scripts/ importable: PYTHONPATH=scripts python3 -m unittest discover -s tests
from build_site import build, build_records, group_folder
from classify import classify
from families import aliases_of, brands_of

ROOT = Path(__file__).resolve().parent.parent

D = "01-Jan-2024 00:00"


def f(name, size=100):
    return {"name": name, "size": size, "date": D}


def row(path, size=100, date=D):
    return {"path": path, "size": size, "date": date}


class GroupFolder(unittest.TestCase):
    def test_mdx_claims_same_named_mdd_volumes_and_css(self):
        recs = group_folder("x", [f("A.mdx"), f("A.mdd"), f("A.1.mdd"), f("A.css"), f("B.mdx")])
        a = next(r for r in recs if r.name == "A")
        names = [n for n, _ in a.locations[0]["files"]]
        self.assertEqual(sorted(names), ["A.1.mdd", "A.css", "A.mdd", "A.mdx"])
        self.assertTrue(a.has_resources)

    def test_single_dictionary_folder_owns_differently_named_assets(self):
        (rec,) = group_folder("x", [f("Dict.mdx"), f("style.css"), f("font.ttf"), f("readme.txt")])
        names = sorted(n for n, _ in rec.locations[0]["files"])
        self.assertEqual(names, ["Dict.mdx", "font.ttf", "style.css"])

    def test_unclaimed_mdd_becomes_resource_pack_not_attached_elsewhere(self):
        recs = group_folder("x", [f("Sound.mdx"), f("Sound-fr.mdd"), f("Sound-fr.1.mdd")])
        kinds = sorted((r.kind, r.name) for r in recs)
        self.assertEqual(kinds, [("mdd", "Sound-fr"), ("mdx", "Sound")])
        pack = next(r for r in recs if r.kind == "mdd")
        self.assertEqual(len(pack.locations[0]["files"]), 2)

    def test_archives_are_records(self):
        (rec,) = group_folder("x", [f("OALD9.rar", 5000)])
        self.assertEqual((rec.kind, rec.name, rec.size), ("archive", "OALD9", 5000))

    def test_split_archive_volumes_form_one_record_led_by_entry_volume(self):
        for vols, entry in [
            (["W.part1.rar", "W.part2.rar", "W.part10.rar"], "W.part1.rar"),
            (["H.z01", "H.z02", "H.zip"], "H.zip"),
            (["S.7z.001", "S.7z.002"], "S.7z.001"),
        ]:
            (rec,) = group_folder("x", [f(v, 10) for v in vols])
            files = [n for n, _ in rec.locations[0]["files"]]
            self.assertEqual((rec.name, files[0], len(files), rec.size), (vols[0].split(".")[0], entry, len(vols), 10 * len(vols)))


class BuildRecords(unittest.TestCase):
    def test_identical_copies_merge_into_one_record_with_two_locations(self):
        recs = build_records([row("a/X.mdx", 7), row("b/X.mdx", 7)])
        (rec,) = recs.values()
        self.assertEqual([loc["folder"] for loc in rec.locations], ["a", "b"])

    def test_most_complete_copy_leads_and_resources_count_from_any_copy(self):
        # Same .mdx in two folders; only the second folder has the .mdd.
        recs = build_records([row("a/X.mdx", 7), row("b/X.mdx", 7), row("b/X.mdd", 900)])
        (rec,) = recs.values()
        self.assertEqual([loc["folder"] for loc in rec.locations], ["b", "a"])
        self.assertTrue(rec.has_resources)
        self.assertEqual(rec.size, 907)

    def test_same_name_different_size_stays_separate(self):
        self.assertEqual(len(build_records([row("a/X.mdx", 7), row("b/X.mdx", 8)])), 2)

    def test_video_course_folders_are_skipped(self):
        self.assertEqual(build_records([row("Language_Learning_Videos/a/X.zip")]), {})


class Tracking(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.index = self.dir / "index.jsonl"
        self.out = self.dir / "out"
        self.t2s = ROOT / "site" / "t2s.json"

    def tearDown(self):
        self.tmp.cleanup()

    def run_build(self, paths, today):
        self.index.write_text("".join(json.dumps(row(p)) + "\n" for p in paths))
        meta = build(self.index, self.out, self.t2s, today)
        return meta, json.loads((self.out / "dicts.json").read_text())

    def test_first_build_is_baseline_then_new_records_get_first_seen(self):
        base = [f"d/D{i}.mdx" for i in range(10)]
        meta, dicts = self.run_build(base, "2026-01-01")
        self.assertTrue(all("fs" not in d for d in dicts))
        self.assertEqual(meta["changes"], [])

        meta, dicts = self.run_build(base[1:] + ["d/New.mdx"], "2026-01-08")
        self.assertEqual({d["n"]: d.get("fs") for d in dicts}["New"], "2026-01-08")
        self.assertEqual(meta["changes"][0], {"date": "2026-01-08", "added": ["New"], "removed": ["D0"]})
        self.assertEqual(meta["tracking_since"], "2026-01-01")

    def test_first_seen_survives_later_builds(self):
        base = [f"d/D{i}.mdx" for i in range(10)]
        self.run_build(base, "2026-01-01")
        self.run_build(base + ["d/New.mdx"], "2026-01-08")
        _, dicts = self.run_build(base + ["d/New.mdx"], "2026-01-15")
        self.assertEqual({d["n"]: d.get("fs") for d in dicts}["New"], "2026-01-08")

    def test_large_shrink_is_refused_and_previous_output_kept(self):
        self.run_build([f"d/D{i}.mdx" for i in range(10)], "2026-01-01")
        before = (self.out / "dicts.json").read_text()
        with self.assertRaises(SystemExit):
            self.run_build(["d/D0.mdx"], "2026-01-08")
        self.assertEqual((self.out / "dicts.json").read_text(), before)

    def test_empty_index_is_refused(self):
        self.index.write_text("")
        with self.assertRaises(SystemExit):
            build(self.index, self.out, self.t2s, "2026-01-01")


class Classify(unittest.TestCase):
    def test_known_names(self):
        cases = {
            "100G_Super_Big_Collection/英语/普通词典/[英-英]/Collins Cobuild.mdx": "en-en",
            "x/[英-汉] 牛津高阶英汉双解第7版.mdx": "en-zh",
            "100G_Super_Big_Collection/德语/德英词典.mdx": "en-other",
            "x/康熙字典20191012.mdx": "other",
            "x/LDAE5.mdx": "en-en",
        }
        for path, want in cases.items():
            self.assertEqual(classify(path), want, path)


class Families(unittest.TestCase):
    def test_brand_and_alias_matching_uses_word_boundaries(self):
        self.assertIn("Oxford", brands_of("oald10"))
        self.assertNotIn("Oxford", brands_of("unicode table"))  # "ode" inside a word
        self.assertIn("牛津高阶", aliases_of("oxford advanced learner's dictionary 10th"))
        self.assertIn("LDOCE", aliases_of("longman doce5 extras"))


if __name__ == "__main__":
    unittest.main()
