"""Staging raw example records for the parallel corpus."""
import gzip
import json
import sqlite3
import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from parallel.extract import layer2, mdx_pairs, stage

SCHEMA = """
CREATE TABLE s_entry (entry_id INTEGER PRIMARY KEY, headword TEXT NOT NULL);
CREATE TABLE s_sense (id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL, ord INTEGER NOT NULL);
CREATE TABLE s_example (sense_id INTEGER NOT NULL, ord INTEGER NOT NULL, text TEXT NOT NULL, text_zh TEXT NOT NULL);
"""


class Layer2(unittest.TestCase):
    def test_translated_examples_come_out_in_dictionary_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "x.db"
            con = sqlite3.connect(db)
            con.executescript(SCHEMA)
            con.executemany("INSERT INTO s_entry VALUES (?, ?)", [(1, "open"), (2, "quiet")])
            con.executemany("INSERT INTO s_sense VALUES (?, ?, ?)", [(10, 1, 2), (11, 1, 1), (20, 2, 1)])
            con.executemany("INSERT INTO s_example VALUES (?, ?, ?, ?)", [
                (10, 1, "The bakery opens at seven.", "面包店七点开门。"),
                (11, 2, "Mira opened the shed.", "米拉打开了棚屋。"),
                (11, 1, "Open the hatch, please.", "请打开舱口。"),
                (20, 1, "a quiet pond", ""),                 # untranslated: not a parallel example
            ])
            con.commit()
            con.close()
            self.assertEqual([r["en"] for r in layer2(db)],
                             ["Open the hatch, please.", "Mira opened the shed.", "The bakery opens at seven."])
            self.assertEqual(next(layer2(db))["hw"], "open")

    def test_a_missing_database_is_an_error_not_an_empty_source(self):
        with self.assertRaises(FileNotFoundError):
            list(layer2(Path("/nonexistent/x.db")))


RECORDS = {
    "open": "<div class='def'>to move a lid</div><p>Mira lifted the lid to check the stew.</p><p>米拉掀开盖子看看炖菜。</p>",
    "opened": "@@@LINK=open",
    "quiet": "<p>making little sound</p><p>The barn was very still after the storm.</p><p>暴风雨过后谷仓里非常寂静。</p>",
}


class Mdx(unittest.TestCase):
    def write(self, tmp, **kw):
        from test_parallel_probe import mdx_bytes
        path = Path(tmp) / "d.mdx"
        path.write_bytes(mdx_bytes(RECORDS, **kw))
        return path

    def test_every_record_is_scanned_and_cross_references_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = list(mdx_pairs(self.write(tmp)))
        self.assertEqual(got, [
            {"en": "Mira lifted the lid to check the stew.", "zh": "米拉掀开盖子看看炖菜。", "hw": "open"},
            {"en": "The barn was very still after the storm.", "zh": "暴风雨过后谷仓里非常寂静。", "hw": "quiet"},
        ])

    def test_a_chinese_first_dictionary_is_read_in_its_order(self):
        from test_parallel_probe import mdx_bytes
        records = {"开": "<p>掀开</p><p>米拉掀开盖子看看炖菜。</p><p>Mira lifted the lid to check the stew.</p>"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.mdx"
            path.write_bytes(mdx_bytes(records))
            self.assertEqual(list(mdx_pairs(path, order="zh-en")),
                             [{"en": "Mira lifted the lid to check the stew.", "zh": "米拉掀开盖子看看炖菜。", "hw": "开"}])

    def test_an_unreadable_key_index_falls_back_to_the_record_blocks(self):
        from test_parallel_probe import mdx_bytes
        from parallel.mdxformat import _header
        from parallel.ranges import BytesSource
        data = bytearray(mdx_bytes(RECORDS))
        _, key_section = _header(BytesSource(bytes(data)))
        data[key_section + 44:key_section + 48] = b"\x07\x00\x00\x00"   # key index in a form mdict-utils rejects
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.mdx"
            path.write_bytes(bytes(data))
            got = list(mdx_pairs(path))
        self.assertEqual([(r["en"], r["hw"]) for r in got],   # the pairs survive; headwords are unknown
                         [("Mira lifted the lid to check the stew.", ""), ("The barn was very still after the storm.", "")])

    def test_records_split_across_record_blocks_are_read_whole(self):
        import struct
        import zlib
        from test_parallel_probe import mdx_bytes
        from parallel.mdx import _records_without_keys
        from parallel.mdxformat import decode_block, layout, record_blocks
        from parallel.ranges import BytesSource
        data = mdx_bytes(RECORDS)
        src = BytesSource(data)
        lay = layout(src)
        body = b"".join(decode_block(data[o:o + c], d) for o, c, d in record_blocks(src, lay))
        # re-cut the records into 7-byte blocks: records, and the characters in them, now span blocks
        chunks = [body[i:i + 7] for i in range(0, len(body), 7)]
        blocks = [struct.pack("<L", 0) + struct.pack(">I", zlib.adler32(c)) + c for c in chunks]
        info = b"".join(struct.pack(">QQ", len(b), len(c)) for b, c in zip(blocks, chunks))
        entries = data[lay.record_offset + 8:lay.record_offset + 16]
        head = struct.pack(">Q", len(blocks)) + entries + struct.pack(">QQ", len(info), sum(map(len, blocks)))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.mdx"
            path.write_bytes(data[:lay.record_offset] + head + info + b"".join(blocks))
            got = [markup for _, markup in _records_without_keys(path)]
        self.assertEqual(sorted(got), sorted(RECORDS.values()))

    def test_a_corrupt_header_is_an_error_not_a_reason_to_read_without_keys(self):
        from test_parallel_probe import mdx_bytes
        from parallel.mdx import records
        from parallel.mdxformat import ProbeError
        data = bytearray(mdx_bytes(RECORDS))
        size = int.from_bytes(data[:4], "big")
        data[4 + size] ^= 0xFF  # the header's Adler-32
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.mdx"
            path.write_bytes(bytes(data))
            with self.assertRaisesRegex(ProbeError, "header checksum"):
                list(records(path))
            path.write_bytes(mdx_bytes(RECORDS))
            self.assertEqual(len(list(records(str(path)))), len(RECORDS))  # a path as a string works too

    def test_lzo_compressed_dictionaries_are_read(self):
        from test_parallel_probe import LIB, lzo_mdx, mdx_bytes
        if not LIB:
            self.skipTest("liblzo2 not installed")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lzo.mdx"
            path.write_bytes(lzo_mdx(mdx_bytes(RECORDS)))
            self.assertEqual(len(list(mdx_pairs(path))), 2)


class Styled(unittest.TestCase):
    RECORDS = {f"w{i}": (f"<li>To fix a fault number {i}:<br>替…修理：<br>"
                         f"<font color=teal>The piper answered with tune {i}.</font><br>"
                         f"<font color=teal>风笛手又吹了第{i}首曲子。</font>") for i in range(30)}

    def setUp(self):
        from test_parallel_probe import mdx_bytes
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "d.mdx").write_bytes(mdx_bytes(self.RECORDS))
        self.truth = self.dir / "truth.db"
        con = sqlite3.connect(self.truth)
        con.executescript("CREATE TABLE s_example (text TEXT); CREATE TABLE s_sense (definition TEXT);")
        con.executemany("INSERT INTO s_example VALUES (?)", [(f"The piper answered with tune {i}.",) for i in range(30)])
        con.executemany("INSERT INTO s_sense VALUES (?)", [(f"To fix a fault number {i}",) for i in range(30)])
        con.commit()
        con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_examples_are_taken_by_their_learned_style_and_the_style_recorded(self):
        from parallel.extract import learn_styles, stage, styled_pairs
        learned = learn_styles(self.dir / "d.mdx", self.truth)
        self.assertEqual(stage(styled_pairs(self.dir / "d.mdx", learned), self.dir / "d.jsonl.gz", learned), 30)
        with gzip.open(self.dir / "d.jsonl.gz", "rt") as f:
            self.assertTrue(all(json.loads(line)["en"].startswith("The piper") for line in f))  # no definitions
        self.assertEqual(json.loads((self.dir / "d.styles.json").read_text()),
                         {"font#teal": {"example_hits": 30, "definition_hits": 0}})

    def test_a_failed_restaging_keeps_the_styles_of_the_records_it_keeps(self):
        from unittest import mock
        from parallel.extract import learn_styles, stage, styled_pairs
        styles, out = self.dir / "d.styles.json", self.dir / "d.jsonl.gz"
        styles.write_text('{"old": {}}\n')
        out.write_bytes(b"old records")
        learned = learn_styles(self.dir / "d.mdx", self.truth)
        calls = []

        def failing(markup, learned):
            calls.append(1)
            if len(calls) == 5:
                raise RuntimeError("extraction failed")
            return [("The piper played.", "风笛手吹了。")]
        with mock.patch("parallel.styled.pairs", failing), self.assertRaises(RuntimeError):
            stage(styled_pairs(self.dir / "d.mdx", learned), out, learned)
        self.assertEqual((styles.read_text(), out.read_bytes()), ('{"old": {}}\n', b"old records"))
        self.assertEqual(sorted(p.name for p in self.dir.glob("d.*")), ["d.jsonl.gz", "d.mdx", "d.styles.json"])

    def test_a_failed_publication_never_leaves_one_runs_styles_beside_anothers_records(self):
        import os
        from unittest import mock
        from parallel.extract import learn_styles, stage, styled_pairs
        styles, out = self.dir / "d.styles.json", self.dir / "d.jsonl.gz"
        learned = learn_styles(self.dir / "d.mdx", self.truth)
        real = os.replace
        for failing, records in ((".jsonl.gz", b"old records"), (".styles.json", None)):
            styles.write_text('{"old": {}}\n')
            out.write_bytes(b"old records")

            def replace(src, dst):
                if str(dst).endswith(failing):
                    raise OSError("the disk is full")
                return real(src, dst)
            with mock.patch("parallel.extract.os.replace", replace), self.assertRaises(OSError):
                stage(styled_pairs(self.dir / "d.mdx", learned), out, learned)
            # the records are the old ones or the new ones; neither has the other's styles beside it
            self.assertFalse(styles.exists(), failing)
            self.assertEqual(out.read_bytes() == b"old records", records is not None, failing)
            self.assertEqual(sorted(p.name for p in self.dir.glob("d.*")), ["d.jsonl.gz", "d.mdx"], failing)

    def test_two_runs_never_publish_into_one_target_at_once(self):
        # run B tries to publish while run A is between its renames, and A's last rename fails:
        # B must wait for A, so that whatever A leaves, B's records end up beside B's styles
        import os
        import threading
        from unittest import mock
        from parallel.extract import stage
        styles, out = self.dir / "d.styles.json", self.dir / "d.jsonl.gz"
        styles.write_text('{"old": {}}\n')
        out.write_bytes(b"old records")
        real = os.replace
        b_done = threading.Event()
        b_errors = []

        def run_b():
            try:
                stage(iter([{"en": "B", "zh": "乙", "hw": "b"}]), out, {"font#b": (20, 0)})
            except BaseException as e:  # reported by the main thread
                b_errors.append(e)
            finally:
                b_done.set()
        b = threading.Thread(target=run_b)

        def replace(src, dst):
            if threading.current_thread() is b:
                return real(src, dst)
            if str(dst).endswith(".jsonl.gz"):  # A, about to publish its records: B arrives
                b.start()
                self.assertFalse(b_done.wait(0.5), "B published while A was publishing")
                return real(src, dst)
            raise OSError("the disk is full")    # A's styles rename
        with mock.patch("parallel.extract.os.replace", replace), self.assertRaises(OSError):
            stage(iter([{"en": "A", "zh": "甲", "hw": "a"}]), out, {"font#a": (20, 0)})
        b.join(10)
        self.assertEqual(b_errors, [])
        self.assertEqual([json.loads(line)["en"] for line in gzip.open(out, "rt")], ["B"])
        self.assertEqual(list(json.loads(styles.read_text())), ["font#b"])
        self.assertEqual(sorted(p.name for p in self.dir.glob("d.*")), ["d.jsonl.gz", "d.mdx", "d.styles.json"])

    def test_records_extracted_without_styles_have_no_styles_file(self):
        from parallel.extract import stage
        styles, out = self.dir / "d.styles.json", self.dir / "d.jsonl.gz"
        styles.write_text('{"old": {}}\n')
        stage(iter([{"en": "A", "zh": "甲", "hw": "a"}]), out)
        self.assertFalse(styles.exists())

    def test_the_styles_are_written_only_after_the_records_are_closed(self):
        from unittest import mock
        from parallel.extract import learn_styles, stage, styled_pairs
        styles, out = self.dir / "d.styles.json", self.dir / "d.jsonl.gz"
        styles.write_text('{"old": {}}\n')
        out.write_bytes(b"old records")
        learned = learn_styles(self.dir / "d.mdx", self.truth)
        real = gzip.GzipFile.close

        def close(f):
            real(f)
            raise OSError("the disk is full")
        with mock.patch.object(gzip.GzipFile, "close", close), self.assertRaises(OSError):
            stage(styled_pairs(self.dir / "d.mdx", learned), out, learned)
        self.assertEqual((styles.read_text(), out.read_bytes()), ('{"old": {}}\n', b"old records"))
        self.assertEqual(sorted(p.name for p in self.dir.glob("d.*")), ["d.jsonl.gz", "d.mdx", "d.styles.json"])

    def test_the_dictionary_is_streamed_not_held_in_memory(self):
        from unittest import mock
        from parallel import mdx
        from parallel.extract import learn_styles, styled_pairs
        real, opened, held = mdx.records, [], []

        def records(path):
            opened.append(path)
            for i, r in enumerate(real(path)):
                held.append(i)
                yield r
        with mock.patch.object(mdx, "records", records):
            learned = learn_styles(self.dir / "d.mdx", self.truth)
            self.assertEqual((len(opened), held.count(0), held.count(29)), (1, 1, 1))
            got = styled_pairs(self.dir / "d.mdx", learned)
            first = next(got)
            # the second pass has read only as far as the first pair, not the whole file again
            self.assertEqual((len(opened), held.count(0), held.count(29)), (2, 2, 1))
            self.assertEqual(len([first, *got]), 30)


class Run(unittest.TestCase):
    def test_one_failing_dictionary_is_reported_and_the_others_finish(self):
        from concurrent.futures import ThreadPoolExecutor
        from parallel.extract import _run
        done = []

        def work(c):
            if c["id"] == "bad":
                raise RuntimeError("corrupt file")
            done.append(c["id"])
            return 1
        choices = [{"id": i, "name": f"dict {i}", "source": "download"} for i in ("a", "bad", "b")]
        with ThreadPoolExecutor(2) as pool:
            failures = _run(pool, work, choices, "staged")
        self.assertEqual(sorted(done), ["a", "b"])
        self.assertEqual(failures, ["bad dict bad: RuntimeError: corrupt file"])


class Stage(unittest.TestCase):
    def test_another_runs_working_file_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "d1.jsonl.gz"
            other = Path(tmp) / "d1.jsonl.gz.part"  # what a concurrent run used to share
            other.write_bytes(b"another run's records")
            stage(iter([{"en": "Morning, Pip, all well?", "zh": "早，皮普，一切都好吗？", "hw": "hello"}]), out)
            self.assertEqual(other.read_bytes(), b"another run's records")
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), [".d1.lock", "d1.jsonl.gz", "d1.jsonl.gz.part"])

    def test_records_are_written_whole_or_not_at_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "staged" / "d1.jsonl.gz"
            self.assertEqual(stage(iter([{"en": "Morning, Pip, all well?", "zh": "早，皮普，一切都好吗？", "hw": "hello"}]), out), 1)
            with gzip.open(out, "rt") as f:
                self.assertEqual(json.loads(f.readline())["zh"], "早，皮普，一切都好吗？")

            def broken():
                yield {"en": "a", "zh": "b", "hw": "c"}
                raise RuntimeError("extractor failed")
            with self.assertRaises(RuntimeError):
                stage(broken(), out)
            with gzip.open(out, "rt") as f:  # the previous good file is untouched
                self.assertEqual(len(f.readlines()), 1)
            self.assertEqual(sorted(p.name for p in out.parent.iterdir()), [".d1.lock", "d1.jsonl.gz"])  # no partial file left; the lock stays


if __name__ == "__main__":
    unittest.main()
