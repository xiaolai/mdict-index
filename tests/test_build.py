"""Behavioural tests for the site build: grouping, dedupe, tracking, guards."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

# Run with scripts/ importable: PYTHONPATH=scripts python3 -m unittest discover -s tests
from build_site import build, build_records, group_folder, record_id
from classify import classify
from families import aliases_of, brands_of
from recommended import resolve_recommended

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

    def test_numbered_mdx_names_keep_their_number(self):
        # "X.1.mdx" and "X.2.mdx" are two dictionaries, not volumes of one.
        recs = build_records([row("a/Wordlist.1.mdx", 7), row("a/Wordlist.2.mdx", 7)])
        self.assertEqual(sorted(r.name for r in recs.values()), ["Wordlist.1", "Wordlist.2"])

    def test_resource_pack_is_led_by_its_unnumbered_volume(self):
        # Adding numbered volumes must not change which file identifies the pack.
        (alone,) = group_folder("x", [f("Pack.mdd", 50)])
        (pack,) = group_folder("x", [f("Pack.1.mdd", 10), f("Pack.mdd", 50), f("Pack.2.mdd", 20)])
        self.assertEqual([n for n, _ in pack.locations[0]["files"]], ["Pack.mdd", "Pack.1.mdd", "Pack.2.mdd"])
        self.assertEqual(pack.locations[0]["main_size"], alone.locations[0]["main_size"])
        # Without an unnumbered volume, the lowest number leads (numerically: 2 before 10).
        (pack,) = group_folder("x", [f("Pack.10.mdd"), f("Pack.2.mdd")])
        self.assertEqual(pack.locations[0]["files"][0][0], "Pack.2.mdd")
        # A volume numbered 0 is still a numbered volume, and sorts after the unnumbered one.
        (pack,) = group_folder("x", [f("Pack.0.mdd", 10), f("Pack.mdd", 50)])
        self.assertEqual(pack.locations[0]["files"][0][0], "Pack.mdd")
        self.assertEqual(record_id(pack), record_id(alone))

    def test_same_named_archives_of_different_formats_stay_separate(self):
        recs = group_folder("x", [f("Tales.rar", 10), f("Tales.zip", 20)])
        self.assertEqual(sorted((r.name, r.size) for r in recs), [("Tales", 10), ("Tales", 20)])
        # A split archive is still one record, and a standalone .zip beside a .zip.NNN set is not part of it.
        recs = group_folder("x", [f("S.zip.001"), f("S.zip.002"), f("S.zip", 5)])
        self.assertEqual(sorted(len(r.locations[0]["files"]) for r in recs), [1, 2])


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

    def test_copy_with_resources_leads_even_when_another_copy_is_larger(self):
        # Copy "a" is larger only because of a big stylesheet; "b" has the .mdd.
        recs = build_records([row("a/X.mdx", 7), row("a/X.css", 5000), row("b/X.mdx", 7), row("b/X.mdd", 900)])
        (rec,) = recs.values()
        self.assertEqual([loc["folder"] for loc in rec.locations], ["b", "a"])
        self.assertEqual(rec.size, 907)

    def test_equal_sized_main_files_of_different_formats_stay_separate(self):
        # The id holds the main file's format and volume scheme, not only name and size.
        for a, b in [("Tales.rar", "Tales.zip"), ("Tales.rar", "Tales.part1.rar"),
                     ("Tales.7z", "Tales.7z.001"), ("Pack.mdd", "Pack.1.mdd")]:
            recs = build_records([row(f"a/{a}", 10), row(f"b/{b}", 10)])
            self.assertEqual(len(recs), 2, (a, b))
        # Copies in the same format still merge.
        self.assertEqual(len(build_records([row("a/Tales.zip", 10), row("b/Tales.zip", 10)])), 1)

    def test_plain_dictionary_ids_do_not_depend_on_the_format_suffix(self):
        # Ids are published: only the formats that used to collide gained a suffix.
        def plain(key):
            return hashlib.sha1(key.encode()).hexdigest()[:12]
        for name, key in [("X.mdx", "mdx|x|100"), ("X.mdd", "mdd|x|100")]:
            (r,) = group_folder("x", [f(name)])
            self.assertEqual(record_id(r), plain(key), name)
        (r,) = group_folder("x", [f("X.rar")])
        self.assertEqual(record_id(r), plain("archive|x|100|.rar"))

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

    def publish_as(self, records):
        """Overwrite the previous build's dicts.json, as an older id scheme might have written it."""
        (self.out / "dicts.json").write_text(json.dumps([
            {"id": rid, "k": k, "n": n, "l": "unknown", "b": [], "a": [], "s": 1, "d": "2024-01-01",
             "loc": [{"p": "d", "f": files}], **({"fs": fs} if fs else {})}
            for rid, k, n, files, fs in records
        ]))

    def test_records_reidentified_by_a_rule_change_keep_their_history(self):
        # The previous build ran older rules: other ids, other names, other groupings.
        # A record whose main file was published before is not new, whatever it was called.
        base = [f"d/D{i}.mdx" for i in range(10)]
        self.run_build(base, "2026-01-01")
        old = json.loads((self.out / "dicts.json").read_text())
        self.publish_as(
            [(d["id"], d["k"], d["n"], d["loc"][0]["f"], None) for d in old]
            + [
                ("old-ud7", "mdx", "UD7", [["UD7.1.mdx", 100]], "2025-11-01"),  # was named without its number
                ("old-tales", "archive", "Tales", [["Tales.rar", 100], ["Tales.zip", 100]], "2025-12-01"),  # was merged
                ("old-pack", "mdd", "Pack", [["Pack.1.mdd", 100], ["Pack.mdd", 100]], None),  # was led by Pack.1.mdd
            ]
        )
        meta, dicts = self.run_build(
            base + ["d/UD7.1.mdx", "d/Tales.rar", "d/Tales.zip", "d/Pack.mdd", "d/Pack.1.mdd", "d/New.mdx"], "2026-01-08"
        )
        seen = {(d["k"], d["n"]): d.get("fs") for d in dicts}
        self.assertEqual(seen[("mdx", "UD7.1")], "2025-11-01")
        self.assertEqual([d.get("fs") for d in dicts if d["k"] == "archive"], ["2025-12-01", "2025-12-01"])
        self.assertIsNone(seen[("mdd", "Pack")])  # part of the baseline
        self.assertIsNone(seen[("mdx", "D0")])
        self.assertEqual(seen[("mdx", "New")], "2026-01-08")
        self.assertEqual(meta["changes"][0], {"date": "2026-01-08", "added": ["New"], "removed": []})

    def test_a_record_none_of_whose_main_files_survives_is_removed(self):
        self.run_build([f"d/D{i}.mdx" for i in range(10)], "2026-01-01")
        old = json.loads((self.out / "dicts.json").read_text())
        self.publish_as([(d["id"], d["k"], d["n"], d["loc"][0]["f"], None) for d in old]
                        + [("old-gone", "mdx", "Gone", [["Gone.mdx", 100], ["D0.css", 100]], None)])
        meta, _ = self.run_build([f"d/D{i}.mdx" for i in range(10)] + ["d/D0.css"], "2026-01-08")
        self.assertEqual(meta["changes"][0], {"date": "2026-01-08", "added": [], "removed": ["Gone"]})

    def test_large_shrink_is_refused_and_previous_output_kept(self):
        self.run_build([f"d/D{i}.mdx" for i in range(10)], "2026-01-01")
        before = (self.out / "dicts.json").read_text()
        with self.assertRaises(SystemExit):
            self.run_build(["d/D0.mdx"], "2026-01-08")
        self.assertEqual((self.out / "dicts.json").read_text(), before)

    def test_outputs_are_written_through_private_temporary_files(self):
        # A file at a fixed temporary name (another build's) must be left alone.
        self.out.mkdir()
        other = self.out / "dicts.json.tmp"
        other.write_text("another build")
        self.run_build([f"d/D{i}.mdx" for i in range(3)], "2026-01-01")
        self.assertEqual(other.read_text(), "another build")
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["dicts.json", "dicts.json.tmp", "meta.json"])
        self.assertEqual((self.out / "dicts.json").stat().st_mode & 0o044, 0o044)  # readable when published

    def test_empty_index_is_refused(self):
        self.index.write_text("")
        with self.assertRaises(SystemExit):
            build(self.index, self.out, self.t2s, "2026-01-01")


def rec(rid, name, size=10, folder="x", kind="mdx"):
    return {"id": rid, "k": kind, "n": name, "s": size, "loc": [{"p": folder, "f": []}]}


def curated(*items):
    cat = {"key": "c", "zh": "c", "en": "c", "tab_zh": "c", "tab_en": "c", "items": list(items)}
    return {"reviewed": "2026-01-01", "categories": [cat]}


def item(key, pick, status="current"):
    return {"key": key, "name": key, "status": status, "pick": pick}


class Recommended(unittest.TestCase):
    def ids(self, out):
        return [i["id"] for i in out["categories"][0]["items"]]

    def test_folder_hint_picks_among_same_named_records(self):
        dicts = [rec("a", "LDOCE6", folder="x/Longman/LDOCE6"), rec("b", "LDOCE6", folder="y/other")]
        out, warnings = resolve_recommended(curated(item("l", {"name": "LDOCE6", "folder": "Longman"})), dicts)
        self.assertEqual((self.ids(out), warnings), (["a"], []))

    def test_vanished_pick_resolves_to_null_with_warning(self):
        out, warnings = resolve_recommended(curated(item("g", {"name": "Gone"})), [rec("a", "Other")])
        self.assertEqual(self.ids(out), [None])
        self.assertEqual(len(warnings), 1)

    def test_ambiguous_pick_takes_most_complete_and_warns(self):
        dicts = [rec("small", "X", 10), rec("big", "X", 99)]
        out, warnings = resolve_recommended(curated(item("x", {"name": "X"})), dicts)
        self.assertEqual(self.ids(out), ["big"])
        self.assertEqual(len(warnings), 1)

    def test_archives_never_match(self):
        out, _ = resolve_recommended(curated(item("x", {"name": "X"})), [rec("arc", "X", kind="archive")])
        self.assertEqual(self.ids(out), [None])

    def test_authoring_errors_raise(self):
        for bad in [
            curated(item("x", {"name": "X"}, status="great")),
            curated(item("x", None, status="current")),
            curated(item("x", {"name": "X"}), item("x", {"name": "X"})),
            curated({**item("x", {"name": "X"}), "src": "javascript:alert(1)"}),
            {"reviewed": "x", "categories": [{"key": "c", "zh": "c", "en": "c", "items": []}]},
        ]:
            with self.assertRaises(ValueError):
                resolve_recommended(bad, [rec("a", "X")])

    def test_committed_curation_resolves_every_pick_exactly(self):
        # Catches typos in data/recommended.json against the committed index.
        dicts = json.loads((ROOT / "site" / "data" / "dicts.json").read_text())
        cur = json.loads((ROOT / "data" / "recommended.json").read_text())
        out, warnings = resolve_recommended(cur, dicts)
        self.assertEqual(warnings, [])
        for cat in out["categories"]:
            for i in cat["items"]:
                self.assertEqual(i["id"] is None, i["status"] == "missing", i["key"])


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

    def test_abbreviations_must_be_whole_tokens(self):
        # "ce" inside a word is not "C-E" (English-Chinese).
        self.assertEqual(classify("x/QWDOCE 5.mdx"), "unknown")
        self.assertEqual(classify("x/frobsource-2016.mdx"), "unknown")
        self.assertEqual(classify("x/Frob E-C.mdx"), "en-zh")
        self.assertEqual(classify("x/Frob Thesaurus EN-ZH.mdx"), "en-zh")

    def test_english_monolingual_markers_are_not_bilingual(self):
        for name in ["WordNet大型英英词典", "[英-英] 牛津学习词典", "[英-英] Frob Thesaurus", "朗文当代(英英)Longman Frob"]:
            self.assertEqual(classify(f"x/{name}.mdx"), "en-en", name)
        # An explicit bilingual marker still wins.
        for name in ["新牛津英英 + 新牛津双解", "汉英英汉地质词典", "[英-英] 牛津高阶(英英,添加双解版)"]:
            self.assertEqual(classify(f"x/{name}.mdx"), "en-zh", name)

    def test_english_chinese_spelled_in_english(self):
        self.assertEqual(classify("x/Frob English-Chinese Dictionary.mdx"), "en-zh")
        self.assertEqual(classify("x/A Frob Chinese English Dictionary.mdx"), "en-zh")

    def test_english_side_needs_english_evidence(self):
        # French-Chinese and French-only works: generic markers (双解, etymology) are not English.
        self.assertEqual(classify("x/拉鲁斯法汉双解词典v0.1.3.mdx"), "other")
        self.assertEqual(classify("x/Grand Robert etymologie.mdx"), "other")
        # The language named, or an English publisher, is evidence.
        self.assertEqual(classify("x/Frob Wörterbuch Englisch-Deutsch.mdx"), "en-other")
        self.assertEqual(classify("x/Frob Dizionario Inglese-Italiano.mdx"), "en-other")
        self.assertEqual(classify("x/Duden-Oxford Frob.mdx"), "en-other")

    def test_a_language_tag_outweighs_a_publisher_name(self):
        # "[其他语种]" (other languages) or "[俄语]" says there is no English side; a publisher does not say there is.
        self.assertEqual(classify("x/[其他语种] 牛津弗罗布俄语词典.mdx"), "other")
        self.assertEqual(classify("x/[德语] Duden-Oxford Frob.mdx"), "other")
        # A tag naming English, or English named outright, still counts.
        self.assertEqual(classify("x/[英-德] Duden-Oxford Frob.mdx"), "en-other")
        self.assertEqual(classify("x/[其他语种] 牛津弗罗布英俄词典.mdx"), "en-other")


class Families(unittest.TestCase):
    def test_brand_and_alias_matching_uses_word_boundaries(self):
        self.assertIn("Oxford", brands_of("oald10"))
        self.assertNotIn("Oxford", brands_of("unicode table"))  # "ode" inside a word
        self.assertIn("牛津高阶", aliases_of("oxford advanced learner's dictionary 10th"))
        self.assertIn("LDOCE", aliases_of("longman doce5 extras"))

    def test_aliases_and_brands_do_not_leak_across_publishers(self):
        for other in ["cambridge advanced learner's dictionary 4th", "collins cobuild advanced learner's dictionary",
                      "macmillan english dictionary for advanced learners", "merriam-webster's advanced learner's dictionary"]:
            self.assertNotIn("OALD", aliases_of(other), other)
        for other in ["random house webster's unabridged dictionary", "dictionary.com unabridged 2016"]:
            self.assertNotIn("Webster's Third", aliases_of(other), other)
        self.assertIn("Webster's Third", aliases_of("mwu2020"))
        self.assertNotIn("Merriam-Webster", brands_of("random house webster's unabridged dictionary"))
        self.assertNotIn("Merriam-Webster", brands_of("webster's new world college dictionary"))
        self.assertIn("Merriam-Webster", brands_of("merriam-webster's collegiate dictionary 11th"))
        for noise in ["20211114 new sound icon and css", "laad3_no.sound.icon", "merriam-webster's collegiate dictionary 11th(pic&sound)"]:
            self.assertNotIn("pronunciation", aliases_of(noise), noise)
        for pack in ["sound-en_gb(british.english,word.93612)", "sound", "longman pronunciation dictionary"]:
            self.assertIn("pronunciation", aliases_of(pack), pack)

    def test_an_edition_number_may_carry_a_tag(self):
        # Catalog names like "OALD8C" and "MW11sound": the tag follows the edition number.
        self.assertIn("Oxford", brands_of("oald8c"))
        self.assertIn("Oxford", brands_of("ode3e"))
        self.assertIn("Merriam-Webster", brands_of("mw11sound"))
        self.assertNotIn("Oxford", brands_of("odessa"))

    def test_collins_titles_are_cobuild_only_with_cobuild_evidence(self):
        self.assertNotIn("COBUILD", aliases_of("柯林斯英英词典第8版"))
        self.assertIn("Collins", aliases_of("柯林斯英英词典第8版"))
        for name in ["柯林斯高阶英汉双解学习词典", "柯林斯双解", "collins cobuild advanced"]:
            self.assertIn("COBUILD", aliases_of(name), name)

    def test_slang_dictionaries_are_not_urban_dictionary(self):
        for name in ["美国俚语词典", "frob dictionary of american slang"]:
            self.assertNotIn("Urban Dictionary", aliases_of(name), name)
            self.assertIn("slang", aliases_of(name), name)
        self.assertIn("Urban Dictionary", aliases_of("urban dictionary 2020"))


if __name__ == "__main__":
    unittest.main()
