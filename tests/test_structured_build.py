"""Layer-2 build: worker, failure rules, merge, Chinese index, definition search.

Uses a synthetic layer-1 database and stub parsers, so it needs neither the
corpus nor lxml.
"""
import contextlib
import dataclasses
import sqlite3
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import build_structured

from build_structured import INDEXES as L2_INDEXES
from build_structured import POPUP_TARGET, SCHEMA as L2_SCHEMA
from build_structured import build, failures, main, merge, merge_popups, parse_dictionary, shard_dir, source_fingerprint, zh_terms
from build_unified import INDEXES as L1_INDEXES
from build_unified import SCHEMA as L1_SCHEMA
from build_unified import norm
from structured.model import Entry, Example, Pron, Sense


def layer1(path: Path, dicts: dict[str, list[str]]) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(L1_SCHEMA)
    for i, (key, headwords) in enumerate(dicts.items(), start=1):
        conn.execute("INSERT INTO dictionary VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (i, key, key, None, None, "c", "current", None, "r", "f", "x.mdx", 2.0, "{}", "", ""))
        conn.executemany("INSERT INTO entry(dict_id, headword, norm, body) VALUES (?,?,?,?)",
                         [(i, h, norm(h), zlib.compress(f"<b>{h}</b>".encode())) for h in headwords])
    conn.commit()
    conn.close()


class InlinePool:
    """ProcessPoolExecutor stand-in: runs each job at once, so tests can patch the parser."""
    def __init__(self, workers):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def submit(self, fn, *args):
        from concurrent.futures import Future
        fut = Future()
        try:
            fut.set_result(fn(*args))
        except Exception as e:  # handed to the caller through the future, as the real pool does
            fut.set_exception(e)
        return fut


def stub(parse, covers="definitions", minimum=0.5):
    return SimpleNamespace(KEY="x", COVERS=covers, MIN_COVERAGE=minimum, parse=parse)


def good(headword, html):
    if headword == "stub":  # a cross-reference stub: excused from coverage
        return Entry(headword=headword, stub="xref")
    if headword.startswith("@origin_"):  # a popup holding the etymology and an example bank of another entry
        return Entry(headword=headword, stub="popup", part_of=headword.split("_", 1)[1], etymology="from Old Norse",
                     forms=("takes",), senses=(Sense(examples=(Example("Bank example."),)),))
    return Entry(
        headword=headword, pos=("verb",), prons=(Pron("teɪk", "uk", "sound://t.mp3"),),
        senses=(Sense(number="1", definition=f"to {headword}", definition_zh="（打电话时的招呼语）喂；你好",
                      examples=(Example("An example.", "例子。"),)),
                Sense(kind="phrase", phrase=f"{headword} off", definition="to leave")),
    )


class Worker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "u.db"
        layer1(self.db, {"a": ["take", "run", "stub", "@origin_take", "@origin_nothing", "cross-examine", "@origin_cross examine"],
                         "b": ["go"]})

    def tearDown(self):
        self.tmp.cleanup()

    def run_worker(self, key, parse, **kw):
        return parse_dictionary(str(self.db), key, str(self.dir / f"{key}.db"), module=stub(parse, **kw))

    def test_report_counts_and_coverage_excludes_stubs(self):
        r = self.run_worker("a", good)
        self.assertEqual((r["entries"], r["stubs"], r["covered"], r["coverage"]), (7, 4, 3, 1.0))
        self.assertEqual(failures(r), [])

    def test_a_stub_that_carries_content_fails(self):
        def cheat(headword, html):  # hiding a real entry as a stub would inflate coverage
            return Entry(headword=headword, stub="xref", senses=(Sense(definition="a real definition"),))
        self.assertIn("contract problems", failures(self.run_worker("a", cheat))[0])

    def test_exceptions_problems_and_low_coverage_all_fail(self):
        def boom(headword, html):
            raise ValueError("bad markup")
        self.assertIn("exceptions", failures(self.run_worker("a", boom))[0])

        def dirty(headword, html):
            return Entry(headword=headword, senses=(Sense(definition="  <b>markup</b>"),))
        self.assertIn("contract problems", failures(self.run_worker("a", dirty))[0])

        def unmarked(headword, html):  # the same stub, but not marked: it now counts against coverage
            return Entry(headword=headword) if headword == "stub" else good(headword, html)
        r = self.run_worker("a", unmarked, minimum=0.9)
        self.assertEqual(r["coverage"], 0.75)
        self.assertIn("coverage", failures(r)[0])

    def test_merge_renumbers_senses_across_dictionaries(self):
        self.run_worker("a", good)
        self.run_worker("b", good)
        merge(self.db, [self.dir / "a.db", self.dir / "b.db"])
        conn = sqlite3.connect(self.db)
        self.addCleanup(conn.close)
        # a: take 2 + run 2 + cross-examine 2 + three popups 1 each; b: go 2
        self.assertEqual(conn.execute("SELECT count(*), count(DISTINCT id) FROM s_sense").fetchone(), (11, 11))
        # every example still points at a sense of the same entry it was parsed from
        orphans = conn.execute("SELECT count(*) FROM s_example x LEFT JOIN s_sense s ON s.id = x.sense_id WHERE s.id IS NULL").fetchone()[0]
        self.assertEqual(orphans, 0)
        go = conn.execute("SELECT s.definition FROM s_sense s JOIN entry e ON e.id = s.entry_id WHERE e.headword = 'go' AND s.kind = 'sense'").fetchone()
        self.assertEqual(go, ("to go",))
        self.assertEqual(conn.execute("SELECT count(*) FROM s_pron").fetchone()[0], 4)

    def test_printed_markup_is_excused_only_for_listed_headwords(self):
        def about_html(headword, html):
            return Entry(headword=headword, senses=(Sense(definition="a line break, <br>"),))
        module = stub(about_html)
        module.PRINTED_MARKUP = frozenset({"take"})
        r = parse_dictionary(str(self.db), "a", str(self.dir / "a.db"), module=module)
        # "take" is listed and passes; "run" (and every other record) still fails the tag check
        self.assertEqual(len(r["problems"]), 6)
        self.assertFalse(any("'take'" in p for p in r["problems"]))

    def test_merge_only_rebuilds_from_existing_shards_and_fails_on_a_missing_one(self):
        shards = shard_dir(self.db)
        shards.mkdir(parents=True)
        parse_dictionary(str(self.db), "a", str(shards / "a.db"), module=stub(good))
        parse_dictionary(str(self.db), "b", str(shards / "b.db"), module=stub(good))
        self.assertEqual(build(self.db, [], ["a", "b"], workers=1), [])  # nothing parsed, everything merged
        conn = sqlite3.connect(self.db)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("SELECT count(DISTINCT dict_id) FROM s_entry").fetchone(), (2,))
        with self.assertRaises(SystemExit):
            build(self.db, [], ["a", "b", "c"], workers=1)

    def test_coverage_is_judged_unrounded(self):
        # 98 of 99 content records is 0.98989...: it rounds to 0.99 but is below MIN_COVERAGE 0.99.
        layer1(self.db.with_name("n.db"), {"n": [f"w{i}" for i in range(99)]})

        def all_but_one(headword, html):
            return Entry(headword=headword) if headword == "w0" else good(headword, html)
        r = parse_dictionary(str(self.db.with_name("n.db")), "n", str(self.dir / "n-shard.db"),
                             module=stub(all_but_one, minimum=0.99))
        self.assertIn("coverage", failures(r)[0])

    def test_a_parser_returning_no_entry_is_reported_not_a_crash(self):
        r = self.run_worker("a", lambda headword, html: None)
        self.assertEqual(len(r["exceptions"]), 7)
        self.assertIn("NoneType", r["exceptions"][0])

    def build_with(self, parse, keys=("a", "b")):
        with mock.patch.object(build_structured, "ProcessPoolExecutor", InlinePool), \
                mock.patch("structured.parsers.load", lambda key: stub(parse)):
            return build(self.db, list(keys), ["a", "b"], workers=1)

    def test_a_failed_parse_keeps_the_last_good_shard(self):
        self.build_with(good)
        before = (shard_dir(self.db) / "a.db").read_bytes()

        def dirty(headword, html):
            return Entry(headword=headword, senses=(Sense(definition="  <b>markup</b>"),))
        with self.assertRaises(SystemExit):
            self.build_with(dirty, keys=("a",))
        self.assertEqual((shard_dir(self.db) / "a.db").read_bytes(), before)
        self.assertEqual(sorted(p.name for p in shard_dir(self.db).iterdir()), ["a.db", "b.db"])  # no temporaries left

    def test_a_passing_shard_is_kept_when_another_fails(self):
        """An interrupted or partly failing run keeps the work that passed: a 2-hour build must not
        start from scratch because a different dictionary failed or the run was stopped."""
        self.build_with(good)
        before_a, before_b = ((shard_dir(self.db) / f"{k}.db").read_bytes() for k in ("a", "b"))
        conn = sqlite3.connect(self.db)
        self.addCleanup(conn.close)
        layer2_before = conn.execute("SELECT count(*), group_concat(definition) FROM s_sense").fetchone()

        def changed(headword, html):  # passes the gate, but reads differently from the last build
            entry = good(headword, html)
            return entry if entry.stub else dataclasses.replace(entry, pos=("noun",))

        def dirty(headword, html):
            return Entry(headword=headword, senses=(Sense(definition="  <b>markup</b>"),))
        parsers = {"a": stub(changed), "b": stub(dirty)}
        with mock.patch.object(build_structured, "ProcessPoolExecutor", InlinePool), \
                mock.patch("structured.parsers.load", lambda key: parsers[key]), self.assertRaises(SystemExit):
            build(self.db, ["a", "b"], ["a", "b"], workers=1)
        self.assertNotEqual((shard_dir(self.db) / "a.db").read_bytes(), before_a)   # passed: kept
        self.assertEqual((shard_dir(self.db) / "b.db").read_bytes(), before_b)      # failed: old one stays
        self.assertEqual(conn.execute("SELECT count(*), group_concat(definition) FROM s_sense").fetchone(),
                         layer2_before)                                              # no merge on a failed run
        self.assertEqual(sorted(p.name for p in shard_dir(self.db).iterdir()), ["a.db", "b.db"])

    def test_shards_belong_to_their_database(self):
        other = self.dir / "other.db"
        layer1(other, {"a": ["x"], "b": ["y"]})
        self.assertNotEqual(shard_dir(self.db), shard_dir(other))
        self.build_with(good)
        # a shard copied in from another database's build is refused, not merged
        shard_dir(other).mkdir(parents=True)
        for key in ("a", "b"):
            (shard_dir(other) / f"{key}.db").write_bytes((shard_dir(self.db) / f"{key}.db").read_bytes())
        with self.assertRaises(SystemExit):
            build(other, [], ["a", "b"], workers=1)

    def test_databases_differing_only_in_suffix_keep_separate_shards(self):
        self.assertNotEqual(shard_dir(self.dir / "u.db"), shard_dir(self.dir / "u.sqlite"))
        self.assertNotEqual(shard_dir(self.dir / "u.db"), shard_dir(self.dir / "u"))

    def copy_with(self, sql: str, *params) -> Path:
        """A copy of the database, changed by `sql`: same dictionaries, ids and record counts."""
        twin = self.dir / "twin" / "u.db"
        twin.parent.mkdir(exist_ok=True)
        twin.write_bytes(self.db.read_bytes())
        with contextlib.closing(sqlite3.connect(twin)) as conn:
            conn.execute(sql, params)
            conn.commit()
        return twin

    def test_shards_of_other_content_with_the_same_ids_are_refused(self):
        self.build_with(good)
        for sql, params in [("UPDATE entry SET body = ? WHERE headword = 'run'", (zlib.compress(b"<b>other</b>"),)),
                            ("UPDATE entry SET headword = 'walk' WHERE headword = 'run'", ())]:
            with self.subTest(sql=sql):
                twin = self.copy_with(sql, *params)
                shards = [shard_dir(self.db) / f"{key}.db" for key in ("a", "b")]
                with self.assertRaises(SystemExit) as stop:
                    merge(twin, shards)
                self.assertIn("a.db", str(stop.exception))       # a's records changed
                self.assertNotIn("b.db", str(stop.exception))    # b's did not

    def test_a_shard_without_a_source_fingerprint_is_refused(self):
        """Shards parsed before fingerprints existed cannot prove their source: re-parse them."""
        self.build_with(good)
        shard = shard_dir(self.db) / "a.db"
        with contextlib.closing(sqlite3.connect(shard)) as conn:
            conn.execute("DROP TABLE s_source")
        with self.assertRaises(SystemExit) as stop:
            merge(self.db, [shard, shard_dir(self.db) / "b.db"])
        self.assertIn("re-parse", str(stop.exception))
        self.assertIn("a.db", str(stop.exception))

    def test_the_fingerprint_is_taken_from_the_records_parsed(self):
        self.build_with(good)
        with contextlib.closing(sqlite3.connect(shard_dir(self.db) / "a.db")) as conn:
            recorded = conn.execute("SELECT dict_id, key, fingerprint FROM s_source").fetchall()
        with contextlib.closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(recorded, [(1, "a", source_fingerprint(conn, 1))])

    def test_a_bad_shard_leaves_the_existing_layer2_untouched(self):
        self.build_with(good)
        conn = sqlite3.connect(self.db)
        self.addCleanup(conn.close)
        before = conn.execute("SELECT count(*) FROM s_sense").fetchone()
        (shard_dir(self.db) / "b.db").write_bytes(b"not a database")
        with self.assertRaises((SystemExit, sqlite3.DatabaseError)):
            merge(self.db, [shard_dir(self.db) / "a.db", shard_dir(self.db) / "b.db"])
        self.assertEqual(conn.execute("SELECT count(*) FROM s_sense").fetchone(), before)

    def test_a_merge_failing_midway_rolls_back_completely(self):
        self.build_with(good)
        conn = sqlite3.connect(self.db)
        self.addCleanup(conn.close)
        before = conn.execute("SELECT count(*), count(DISTINCT dict_id) FROM s_entry").fetchone()
        with mock.patch.object(build_structured, "zh_terms", side_effect=RuntimeError("midway")):
            with self.assertRaises(RuntimeError):
                merge(self.db, [shard_dir(self.db) / "a.db"])
        self.assertEqual(conn.execute("SELECT count(*), count(DISTINCT dict_id) FROM s_entry").fetchone(), before)
        self.assertEqual([p for p in self.dir.iterdir() if p.name.endswith(".tmp")], [])

    def test_unknown_only_keys_are_rejected(self):
        with mock.patch("structured.parsers.registry", lambda: {"a": None, "b": None}), \
                mock.patch.object(sys, "argv", ["build_structured.py", "--db", str(self.db), "--only", "a,typo"]), \
                mock.patch.object(build_structured, "build") as built:
            with self.assertRaises(SystemExit) as stop:
                main()
        self.assertIn("typo", str(stop.exception))
        built.assert_not_called()

    def test_popups_fold_into_their_entry(self):
        self.run_worker("a", good)
        merge(self.db, [self.dir / "a.db"])
        conn = sqlite3.connect(self.db)
        self.addCleanup(conn.close)
        take = conn.execute("SELECT s.entry_id, s.etymology, s.forms FROM s_entry s JOIN entry e ON e.id = s.entry_id "
                            "WHERE e.headword = 'take'").fetchone()
        self.assertEqual(take[1:], ("from Old Norse", '["takes"]'))
        senses = conn.execute("SELECT ord, definition FROM s_sense WHERE entry_id = ? ORDER BY ord", (take[0],)).fetchall()
        self.assertEqual(senses, [(0, "to take"), (1, "to leave"), (2, "")])  # the bank comes after take's own senses
        # "cross examine" is spelt "cross-examine" in the dictionary: punctuation and spaces don't block the match
        cross = conn.execute("SELECT s.etymology FROM s_entry s JOIN entry e ON e.id = s.entry_id WHERE e.headword = 'cross-examine'").fetchone()
        self.assertEqual(cross, ("from Old Norse",))
        # "@origin_nothing" has no entry to join: it stays put rather than vanishing
        orphan = conn.execute("SELECT count(*) FROM s_sense s JOIN entry e ON e.id = s.entry_id WHERE e.headword = '@origin_nothing'").fetchone()
        self.assertEqual(orphan, (1,))
        merged = conn.execute("SELECT e.headword, s.merged_into FROM s_entry s JOIN entry e ON e.id = s.entry_id "
                              "WHERE s.stub = 'popup' ORDER BY 1").fetchall()
        self.assertEqual([m for m in merged if m[0] != "@origin_cross examine"], [("@origin_nothing", None), ("@origin_take", take[0])])
        self.assertEqual(merge_popups(conn), 0)  # idempotent: merged popups are not processed again

    def test_main_entry_keeps_its_own_etymology(self):
        def with_etym(headword, html):
            e = good(headword, html)
            return Entry(**{**e.__dict__, "etymology": "its own"}) if headword == "take" else e
        self.run_worker("a", with_etym)
        merge(self.db, [self.dir / "a.db"])
        conn = sqlite3.connect(self.db)
        self.addCleanup(conn.close)
        etym = conn.execute("SELECT s.etymology FROM s_entry s JOIN entry e ON e.id = s.entry_id WHERE e.headword = 'take'").fetchone()
        self.assertEqual(etym, ("its own",))

    def test_chinese_index_and_definition_search(self):
        self.run_worker("a", good)
        merge(self.db, [self.dir / "a.db"])
        conn = sqlite3.connect(self.db)
        self.addCleanup(conn.close)
        hits = conn.execute("SELECT DISTINCT e.headword FROM zh_term z JOIN s_sense s ON s.id = z.sense_id "
                            "JOIN entry e ON e.id = s.entry_id WHERE z.term = '你好' ORDER BY 1").fetchall()
        self.assertEqual(hits, [("cross-examine",), ("run",), ("take",)])
        fts = conn.execute("SELECT definition FROM sense_fts WHERE sense_fts MATCH 'leave'").fetchall()
        self.assertEqual(fts, [("to leave",)] * 3)  # the "off" phrase of take, run and cross-examine


class QueryPlans(unittest.TestCase):
    def test_popup_lookup_uses_the_headword_index(self):
        # Without this plan, merging the OED's popups takes days instead of seconds.
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.executescript(L1_SCHEMA + L1_INDEXES + L2_SCHEMA + L2_INDEXES)
        plan = " | ".join(r[3] for r in conn.execute("EXPLAIN QUERY PLAN " + POPUP_TARGET, ("take", 1)))
        self.assertTrue(plan.startswith("SEARCH e USING COVERING INDEX entry_norm"), plan)
        self.assertNotIn("s_entry_dict", plan)


class ZhTerms(unittest.TestCase):
    def test_notes_dropped_and_separators_split(self):
        self.assertEqual(zh_terms("（打电话时的招呼语）喂；你好"), ["喂", "你好"])
        self.assertEqual(zh_terms("带走, 拿走、取走/携带"), ["带走", "拿走", "取走", "携带"])

    def test_supplementary_ideographs_are_chinese(self):
        self.assertEqual(zh_terms("𠮷；吉"), ["𠮷", "吉"])

    def test_non_chinese_and_overlong_parts_are_skipped(self):
        self.assertEqual(zh_terms("abc；向某人打招呼；" + "长" * 30), ["向某人打招呼"])


if __name__ == "__main__":
    unittest.main()


class Keys(unittest.TestCase):
    """Entry and sense keys hold across rebuilds that renumber every id."""

    @staticmethod
    def db(dictionaries: list[tuple[int, str, list[str]]]) -> sqlite3.Connection:
        """A layer 1 and 2 with these dictionaries (id, key, headwords in file order), ids as given."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(L1_SCHEMA + L2_SCHEMA + "DROP TABLE IF EXISTS s_source;")
        conn.executescript(L1_INDEXES)
        entry_id = sense_id = 100 * dictionaries[0][0]
        for dict_id, key, headwords in dictionaries:
            conn.execute("INSERT INTO dictionary VALUES (?,?,?,'','', 'native','ok','', '','','',2.0,'{}','','')",
                         (dict_id, key, key))
            for hw in headwords:
                entry_id += 1
                conn.execute("INSERT INTO entry (id, dict_id, headword, norm, body) VALUES (?,?,?,?,?)",
                             (entry_id, dict_id, hw, norm(hw), b""))
                for ord_ in (1, 2):
                    sense_id += 1
                    conn.execute("INSERT INTO s_sense VALUES (?,?,?,?,'sense','','','','[]','','')",
                                 (sense_id, entry_id, dict_id, ord_))
        build_structured.build_keys(conn)
        return conn

    @staticmethod
    def keys(conn, dict_key):
        return (sorted(k for (k,) in conn.execute("SELECT key FROM entry_key WHERE key LIKE ?", (dict_key + ":%",))),
                sorted(k for (k,) in conn.execute("SELECT key FROM sense_key WHERE key LIKE ?", (dict_key + ":%",))))

    def test_a_dictionary_keeps_its_keys_whatever_else_is_built(self):
        alone = self.db([(1, "noad", ["run", "set", "run", "a:b"])])
        beside = self.db([(3, "oald", ["go", "run"]), (7, "noad", ["run", "set", "run", "a:b"])])
        self.assertEqual(self.keys(alone, "noad"), self.keys(beside, "noad"))   # every id differs between the two

    def test_repeated_headwords_are_numbered_in_file_order_and_keys_split_back(self):
        conn = self.db([(1, "noad", ["run", "set", "run", "a:b"])])
        entries, senses = self.keys(conn, "noad")
        self.assertEqual(entries, ["noad:1:a:b", "noad:1:run", "noad:1:set", "noad:2:run"])
        self.assertEqual("noad:1:a:b".split(":", 2), ["noad", "1", "a:b"])          # a ':' in the headword
        self.assertEqual("noad:1:a:b:2".rsplit(":", 1), ["noad:1:a:b", "2"])
        self.assertIn("noad:2:run:2", senses)
        first_run = conn.execute("SELECT entry_id FROM entry_key WHERE key = 'noad:1:run'").fetchone()[0]
        second_run = conn.execute("SELECT entry_id FROM entry_key WHERE key = 'noad:2:run'").fetchone()[0]
        self.assertLess(first_run, second_run)

    def test_versions_ignore_ids_and_follow_content(self):
        def versions(dictionaries, key):
            conn = self.db(dictionaries)
            build_structured.build_versions(conn)
            return conn.execute("SELECT v.records, v.senses FROM dictionary_version v JOIN dictionary d ON d.id = v.dict_id "
                                "WHERE d.key = ?", (key,)).fetchone()
        alone = versions([(1, "noad", ["run", "set"])], "noad")
        self.assertEqual(alone, versions([(3, "oald", ["go"]), (7, "noad", ["run", "set"])], "noad"))  # ids moved
        changed = versions([(1, "noad", ["run", "sat"])], "noad")
        self.assertNotEqual(alone[0], changed[0])
        self.assertNotEqual(alone[1], changed[1])
