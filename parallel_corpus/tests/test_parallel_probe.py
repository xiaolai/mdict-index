"""The range probe on small real .mdx files written with mdict-utils (no network)."""
import ctypes
import json
import random
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from mdict_utils.base.writemdict import MDictWriter

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tests"))  # test_lzo1x: liblzo2 helpers

from parallel.mdxformat import ProbeError, decode_block, layout, record_blocks
from parallel.probe import pick_blocks, probe, signal
from parallel.ranges import BytesSource


def mdx_bytes(records: dict[str, str], **kw) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "t.mdx"
        with open(path, "wb") as f:
            MDictWriter(records, title="t", description="d", **kw).write(f)
        return path.read_bytes()


from test_lzo1x import LIB  # noqa: E402  (liblzo2 via ctypes, or None)


def _lzo(data: bytes) -> bytes:
    out = ctypes.create_string_buffer(len(data) + len(data) // 16 + 64 + 3)
    n = ctypes.c_size_t(0)
    wrk = ctypes.create_string_buffer(1 << 20)
    assert LIB.lzo1x_1_compress(data, ctypes.c_size_t(len(data)), out, ctypes.byref(n), wrk) == 0
    return out.raw[:n.value]


def lzo_mdx(data: bytes) -> bytes:
    """Re-encode a v2 .mdx's record blocks with real LZO (mdict-utils cannot write LZO)."""
    src = BytesSource(data)
    lay = layout(src)
    blocks = record_blocks(src, lay)
    new_blocks, info = [], b""
    for off, comp, dec in blocks:
        raw = data[off:off + comp]
        body = decode_block(raw, dec)
        packed = struct.pack("<L", 1) + raw[4:8] + _lzo(body)  # same Adler-32: it covers the decompressed data
        new_blocks.append(packed)
        info += struct.pack(">QQ", len(packed), dec)
    head = struct.pack(">QQQQ", len(blocks), struct.unpack(">Q", data[lay.record_offset + 8:lay.record_offset + 16])[0],
                       len(info), sum(map(len, new_blocks)))
    return data[:lay.record_offset] + head + info + b"".join(new_blocks)


_rng = random.Random(7)
_letters = "abcdefghijklmnopqrstuvwxyz"


def _filler(n: int) -> str:  # varied text, so the file does not compress to almost nothing
    return " ".join("".join(_rng.choice(_letters) for _ in range(_rng.randint(3, 9))) for _ in range(n))


BILINGUAL = {f"word{i}": (f"<div class='def'>a definition {_filler(30)}</div>"
                          f"<div class='ex'>Mira propped the window open for the florp. 米拉把窗户撑开好让弗洛普进来。</div>")
             for i in range(1500)}
ENGLISH_ONLY = {f"word{i}": f"<div>a definition number {i}</div><div>Mira painted the fence again today.</div>" for i in range(400)}


class Signal(unittest.TestCase):
    def test_pairs_need_an_english_sentence_and_a_chinese_sentence(self):
        self.assertEqual(signal("<p>Pip rode the tram to market. 皮普坐电车去市场。</p>")["pairs"], 1)
        self.assertEqual(signal("<p>to carry something uphill 把某物搬上山</p>")["pairs"], 0)  # a definition
        self.assertEqual(signal("<p>Pip rode the tram to market.</p><p>No translation here at all.</p>")["pairs"], 0)
        self.assertEqual(signal("<p>皮普坐电车去市场。</p>")["pairs"], 0)

    def test_long_text_is_analysed_in_linear_time(self):
        # A backtracking pattern once hung for minutes on real LDOCE blocks. Linear: four times
        # the text takes about four times as long (quadratic would be sixteen). CPU time, not wall
        # time: the cost of the analysis, not how busy the machine is.
        import time

        def seconds(n):
            mixed = "<p>" + "Here is another sentence in English. 这是一个中文句子。" * n + "</p>"
            long_english = "<p>" + "an example word, " * (n * 7) + "</p>"
            long_chinese = "<p>" + "这是一个很长的中文句子，用来测试速度。" * n + "Then some English text follows here.</p>"
            t = time.process_time()
            self.assertEqual(signal(mixed)["pairs"], n)
            self.assertEqual(signal(long_english)["pairs"], 0)
            signal(long_chinese)  # Chinese-first reading of a long Chinese run once went quadratic
            return time.process_time() - t

        small, large = seconds(750), seconds(3000)
        self.assertLess(large / small, 8)
        self.assertLess(large, 5.0)

    def test_several_pairs_in_one_segment_are_each_counted(self):
        self.assertEqual(signal("<p>Pip likes plum jam a lot. 皮普很喜欢李子酱。 Lena likes honey even more. 莉娜更喜欢蜂蜜。</p>")["pairs"], 2)

    def test_real_layouts_are_recognised(self):
        # COBUILD: English and Chinese in separate <p>, English followed by a grammar code
        cobuild = ('<li><p>Pip strolls beside the florp canal most evenings.<span class="tips"> [ VERB ]</span>'
                   '<a class="tts"> </a></p> <p><span class="chinese-text">皮普大多数傍晚都沿着弗洛普运河散步。</span></p></li>')
        # OALECD: words wrapped in links, <xhtml:br> between, audio icons after the Chinese
        oalecd = ('<x><xhtml:a>Each</xhtml:a> <xhtml:a>florp</xhtml:a> <xhtml:a>kettle</xhtml:a> hummed softly.'
                  '<xhtml:br></xhtml:br><chn>每把弗洛普水壶都轻轻地响着。</chn></x><a href="sound://x.mp3">🔊</a> ◆ next')
        # LDOCE: custom example tags inside one span
        ldoce = '<span class="example"><EXAEN>Bakers are proud of every loaf they sell.</EXAEN><EXAMPLE>面包师为卖出的每一条面包感到自豪。</EXAMPLE></span>'
        for name, html in [("cobuild", cobuild), ("oalecd", oalecd), ("ldoce", ldoce)]:
            self.assertEqual(signal(html)["pairs"], 1, name)

    def test_html_entities_are_decoded(self):
        # OALD 7 re-typeset: translations indented with &nbsp; (sometimes without the semicolon)
        oald = ('&nbsp;&nbsp;&nbsp;<SPAN style="color:#008080">Pip shows that even late florps can change. </SPAN>'
                '<br><font style="color:grey;">&nbsp;&nbsp;&nbsp;皮普证明了即使是晚起的弗洛普也能改变。 </font>'
                '<br>&nbsp&nbsp&nbsp<SPAN>We idled away a florp afternoon by the pond. </SPAN><br><font>&nbsp&nbsp&nbsp我们在池塘边虚度了一个弗洛普下午。</font>')
        self.assertEqual(signal(oald)["pairs"], 2)
        # markup escaped twice shows up as text once decoded, and is still markup
        r = signal("<p>&lt;b&gt;Tom&amp;Jerry&lt;/b&gt; are chasing each other again.</p><p>汤姆和杰瑞又在互相追逐了。</p>")
        self.assertEqual(r["candidates"]["en-zh"], [("Tom&Jerry are chasing each other again.", "汤姆和杰瑞又在互相追逐了。")])

    def test_compact_format_style_markers_are_markup(self):
        # MDict "Compact" dictionaries mark styles with backtick-numbered codes instead of tags.
        compact = "`11`~ a concert`12`The florp mayor will ring the harbour bell tomorrow.`13`弗洛普市長明天將敲響港口的鐘。`14`"
        self.assertEqual(signal(compact)["pairs"], 1)

    def test_translations_without_final_punctuation_count_as_loose_pairs(self):
        # Older dictionaries: "The florp mayor will ~ a brief florp song tomorrow. <br>弗洛普市長明晚將唱 [簡短] 弗洛普歌"
        old_style = "`12`The florp mayor will sing a brief florp song tonight. <br>弗洛普市長今晚將唱 [簡短] 弗洛普歌`12`"
        r = signal(old_style)
        self.assertEqual((r["pairs"], r["pairs_loose"]), (0, 1))

    def test_definitions_with_chinese_glosses_are_not_examples(self):
        # A full-sentence English definition followed by a gloss (no 。) is a definition, not an example.
        cobuild_def = "If a florp dims, it gives off less light than before. （使）变暗；（使）发暗"
        ldoce_def = "<span class='def'><EN>a florp levied for parking a cart</EN><TRAN>〔尤指弗洛普镇的〕停车费，泊车费</TRAN></span>"
        for html in (cobuild_def, ldoce_def):
            self.assertEqual(signal(html)["pairs"], 0, html)  # the strict count; the loose one may count them

    def test_other_languages_beside_chinese_are_counted_apart(self):
        # German-, French-, Japanese- and Korean-Chinese dictionaries have the same shape as English ones.
        german = "<p>Er öffnet das Fenster, weil es zu warm ist.</p><p>他打开窗户，因为太热了。</p>"
        french = "<p>Elle ouvre la fenêtre parce qu'il fait chaud.</p><p>她打开窗户，因为很热。</p>"
        japanese = "<p>Mira opened the attic window this morning.</p><p>今朝ミラは屋根裏の窓を開けました。</p>"
        for name, html in [("german", german), ("french", french), ("japanese", japanese)]:
            r = signal(html)
            self.assertEqual((r["pairs"], r["pairs_loose"], r["pairs_foreign"]), (0, 0, 1), name)
        r = signal("<p>Mira opened the attic window this morning.</p><p>米拉今天早上打开了阁楼的窗户。</p>")
        self.assertEqual((r["pairs"], r["pairs_loose"], r["pairs_foreign"]), (1, 1, 0))

    def test_candidates_keep_only_the_example_not_the_definition_before_it(self):
        html = ("<div>open</div><div>to move a lid until the pot is uncovered. "
                "Mira lifted the lid to let the steam out.</div><div>米拉掀开盖子放出蒸汽。</div>")
        self.assertEqual(signal(html)["candidates"]["en-zh"], [("Mira lifted the lid to let the steam out.", "米拉掀开盖子放出蒸汽。")])
        # an example that shares its element with a headword and an unpunctuated definition
        self.assertEqual(signal("<p>open to move a lid The gate swung slowly behind her. 大门在她身后慢慢地摆动。</p>")
                         ["candidates"]["en-zh"][0][1], "大门在她身后慢慢地摆动。")

    def test_both_orders_are_counted_and_aligned_with_a_lexicon(self):
        lexicon = {"window": frozenset({"窗户", "窗"}), "opened": frozenset({"打开"}), "morning": frozenset({"早上"})}
        en_zh = "<p>Mira opened the attic window this morning.</p><p>米拉今天早上打开了阁楼的窗户。</p>"
        r = signal(en_zh, lexicon)
        self.assertEqual((r["pairs_loose"], r["pairs_zh_en"]), (1, 0))
        self.assertEqual(r["scores"]["en-zh"], [1.0])
        zh_en = "<p>米拉今天早上打开了阁楼的窗户。</p><p>Mira opened the attic window this morning.</p>"
        self.assertEqual(signal(zh_en, lexicon)["pairs_zh_en"], 1)
        # misaligned neighbours score low
        wrong = "<p>Mira opened the attic window this morning.</p><p>他昨天买了一辆新车。</p>"
        self.assertEqual(signal(wrong, lexicon)["scores"]["en-zh"], [0.0])
        self.assertEqual(signal(en_zh)["scores"], {"en-zh": [], "zh-en": []})  # no lexicon, no scores


class Sampling(unittest.TestCase):
    def test_sampled_blocks_spread_over_the_whole_file(self):
        self.assertEqual(pick_blocks(list(range(7)), 4), [0, 2, 4, 6])
        self.assertEqual(pick_blocks(list(range(100)), 4), [12, 37, 62, 87])
        self.assertEqual(pick_blocks(list(range(3)), 4), [0, 1, 2])

    def test_a_block_count_must_be_positive(self):
        with self.assertRaises(ValueError):
            pick_blocks(list(range(7)), 0)
        with self.assertRaises(ValueError):
            probe(BytesSource(mdx_bytes(ENGLISH_ONLY, block_size=4096)), n_blocks=-1)


class Main(unittest.TestCase):
    def run_main(self, out, *args):
        import contextlib
        import io
        from unittest import mock
        from parallel import probe as probe_module
        with mock.patch.object(sys, "argv", ["probe.py", "--out", str(out), *args]), \
                contextlib.redirect_stderr(io.StringIO()):
            probe_module.main()

    def test_a_failed_redo_keeps_the_earlier_results(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            out, redo = Path(tmp) / "probe.jsonl", Path(tmp) / "redo.json"
            rows = '{"id": "a", "status": "ok"}\n{"id": "b", "status": "error"}\n'
            out.write_text(rows)
            redo.write_text('["a"]')
            missing = FileNotFoundError("lexicon.json.gz: build it first")
            with mock.patch("parallel.lexicon._lexicon", side_effect=missing), self.assertRaises(FileNotFoundError):
                self.run_main(out, "--redo", str(redo), "--retry-errors")
            self.assertEqual(out.read_text(), rows)

    FOUND = [{"id": i, "name": f"dict {i}"} for i in "abc"]
    ROWS = "".join(json.dumps({"id": i, "name": f"dict {i}", "status": "ok", "pairs": 1}) + "\n" for i in "abc")

    def patched(self, run_one):
        from unittest import mock
        from parallel import probe as probe_module
        stack = mock.patch.multiple(probe_module, candidates=lambda: self.FOUND, run_one=run_one)
        stack.start()
        self.addCleanup(stack.stop)
        lexicon = mock.patch("parallel.lexicon._lexicon", return_value={})
        lexicon.start()
        self.addCleanup(lexicon.stop)

    def test_rows_probed_again_stay_until_every_replacement_is_in(self):
        def run_one(c, n_blocks, lexicon):
            if c["id"] == "b":
                raise RuntimeError("the network went away")
            return {**c, "status": "ok", "pairs": 10}
        self.patched(run_one)
        with tempfile.TemporaryDirectory() as tmp:
            out, redo = Path(tmp) / "probe.jsonl", Path(tmp) / "redo.json"
            out.write_text(self.ROWS)
            redo.write_text('["a", "b"]')
            with self.assertRaises(RuntimeError):
                self.run_main(out, "--redo", str(redo), "--jobs", "1")
            self.assertEqual(out.read_text(), self.ROWS)  # a and b were good rows: both are still there

    def test_an_interrupted_run_is_continued_from_its_journal(self):
        probed = []

        def run_one(c, n_blocks, lexicon):
            probed.append(c["id"])
            return {**c, "status": "ok", "pairs": 10}
        self.patched(run_one)
        with tempfile.TemporaryDirectory() as tmp:
            out, redo = Path(tmp) / "probe.jsonl", Path(tmp) / "redo.json"
            out.write_text(self.ROWS)
            redo.write_text('["a", "b"]')
            # what a run stopped while writing b's result leaves behind
            (Path(tmp) / "probe.jsonl.journal").write_text(
                json.dumps({"id": "a", "name": "dict a", "status": "ok", "pairs": 7}) + '\n{"id": "b", "na')
            self.run_main(out, "--redo", str(redo))
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(probed, ["b"])
            self.assertEqual({r["id"]: r["pairs"] for r in rows}, {"a": 7, "b": 10, "c": 1})
            self.assertEqual(len(rows), 3)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["probe.jsonl", "redo.json"])

    def test_a_first_run_writes_every_result(self):
        self.patched(lambda c, n_blocks, lexicon: {**c, "status": "error" if c["id"] == "b" else "ok", "pairs": 10})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data" / "probe.jsonl"
            self.run_main(out)
            self.assertEqual(sorted(json.loads(line)["id"] for line in out.read_text().splitlines()), ["a", "b", "c"])
            first = out.read_text()
            self.run_main(out)                    # nothing left to do: nothing changes
            self.assertEqual(out.read_text(), first)
            self.patched(lambda c, n_blocks, lexicon: {**c, "status": "ok", "pairs": 20})
            self.run_main(out, "--retry-errors")  # only the failed one is probed again
            self.assertEqual({r["id"]: r["pairs"] for r in map(json.loads, out.read_text().splitlines())},
                             {"a": 10, "b": 20, "c": 10})

    def test_the_block_count_must_be_positive(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            for n in ("0", "-1"):
                with self.assertRaises(SystemExit):
                    self.run_main(Path(tmp) / "probe.jsonl", "--blocks", n)


class HttpRangeFallback(unittest.TestCase):
    def test_a_range_past_the_end_of_a_small_file_falls_back_to_an_open_range(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from parallel.ranges import HttpRange
        body = b"x" * 1000

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                start, _, end = self.headers["Range"].removeprefix("bytes=").partition("-")
                start, end = int(start), int(end) if end else len(body) - 1
                if end >= len(body):
                    self.send_response(416)
                    self.end_headers()
                    return
                chunk = body[start:end + 1]
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(body)}")
                self.send_header("Content-Length", str(len(chunk)))
                self.end_headers()
                self.wfile.write(chunk)

            def log_message(self, *a):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            src = HttpRange(f"http://127.0.0.1:{server.server_address[1]}/f.mdx")
            self.assertEqual(src.read(0, 65536), body)       # 416, then the open range
            self.assertEqual(src.read(10, 5), b"xxxxx")      # ordinary ranges still work
            self.assertEqual(src.size, len(body))             # learnt from Content-Range
        finally:
            server.shutdown()
            server.server_close()


class HttpRangeChecks(unittest.TestCase):
    """A 206 must answer the range asked for."""

    def serve(self, content_range, chunk, content_length=None):
        """A server answering every request with 206, content_range and chunk; Content-Length is
        len(chunk) unless given, and left out when False (the body then ends with the connection)."""
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(206)
                self.send_header("Content-Range", content_range)
                if content_length is not False:
                    self.send_header("Content-Length", str(len(chunk) if content_length is None else content_length))
                self.end_headers()
                self.wfile.write(chunk)

            def log_message(self, *a):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        from parallel.ranges import HttpRange
        return HttpRange(f"http://127.0.0.1:{server.server_address[1]}/f.mdx")

    def test_a_range_starting_elsewhere_is_rejected(self):
        with self.assertRaisesRegex(ProbeError, "Content-Range"):
            self.serve("bytes 0-3/100", b"abcd").read(50, 4)

    def test_a_short_body_is_rejected(self):
        with self.assertRaisesRegex(ProbeError, "Content-Range"):
            self.serve("bytes 50-53/100", b"ab").read(50, 4)

    def test_a_missing_content_range_is_rejected(self):
        with self.assertRaisesRegex(ProbeError, "Content-Range"):
            self.serve("", b"abcd").read(50, 4)

    def test_a_range_longer_than_asked_for_is_rejected(self):
        with self.assertRaisesRegex(ProbeError, "Content-Range"):
            self.serve("bytes 50-60/100", b"abcd").read(50, 4)
        with self.assertRaisesRegex(ProbeError, "Content-Range"):
            self.serve("bytes 50-60/100", b"abcdefghijk").read(50, 4)  # even with the body it promises

    def test_a_range_cut_short_before_the_end_of_the_file_is_rejected(self):
        with self.assertRaisesRegex(ProbeError, "Content-Range"):
            self.serve("bytes 50-51/100", b"ab").read(50, 4)
        with self.assertRaisesRegex(ProbeError, "Content-Range"):
            self.serve("bytes 50-49/100", b"").read(50, 4)

    def test_a_range_ending_with_the_file_is_accepted(self):
        self.assertEqual(self.serve("bytes 98-99/100", b"yz").read(98, 4), b"yz")
        self.assertEqual(self.serve("bytes 50-53/*", b"abcd").read(50, 4), b"abcd")  # the whole range: no length needed

    def test_a_short_range_of_a_file_of_unknown_length_is_rejected(self):
        # nothing shows that byte 99 ends the file
        with self.assertRaisesRegex(ProbeError, "Content-Range"):
            self.serve("bytes 98-99/*", b"yz").read(98, 4)

    def test_an_impossible_range_is_rejected(self):
        for header in ("bytes 50-53/52", "bytes 50-53/53", "bytes 50-53/0", "bytes 53-50/100"):
            with self.assertRaisesRegex(ProbeError, "Content-Range", msg=header):
                self.serve(header, b"abcd").read(50, 4)

    def test_a_body_longer_than_its_range_is_rejected(self):
        with self.assertRaisesRegex(ProbeError, "Content-Length"):
            self.serve("bytes 50-53/100", b"abcdefgh").read(50, 4)
        with self.assertRaisesRegex(ProbeError, "more than 4 bytes"):
            self.serve("bytes 50-53/100", b"abcdefgh", content_length=False).read(50, 4)

    def test_a_body_shorter_than_its_content_length_is_rejected(self):
        with self.assertRaisesRegex(ProbeError, "2 bytes in the body"):
            self.serve("bytes 50-53/100", b"ab", content_length=4).read(50, 4)
        with self.assertRaisesRegex(ProbeError, "2 bytes in the body"):
            self.serve("bytes 50-53/100", b"ab", content_length=False).read(50, 4)

    def test_a_matching_range_is_accepted(self):
        src = self.serve("bytes 50-53/100", b"abcd")
        self.assertEqual((src.read(50, 4), src.size), (b"abcd", 100))


class Layout(unittest.TestCase):
    def test_v2_record_blocks_are_located_and_sampled(self):
        data = mdx_bytes(BILINGUAL, block_size=4096)
        self.assertGreater(len(data), 2 * 65536)  # well beyond the 64 KB first read, so sampling is measurable
        src = BytesSource(data)
        lay = layout(src)
        blocks = record_blocks(src, lay)
        self.assertGreater(len(blocks), 4)
        self.assertEqual(blocks[-1][0] + blocks[-1][1], len(data))  # the last block ends the file
        r = probe(src, n_blocks=3)
        self.assertEqual((r["version"], r["sampled"]), (2.0, 3))
        self.assertGreater(r["pairs"], 0)
        self.assertLess(src.fetched, len(data))  # sampled, not read in full

    def test_v1_format_and_uncompressed_blocks(self):
        src = BytesSource(mdx_bytes(BILINGUAL, version="1.2", compression_type=0, block_size=4096))
        r = probe(src, n_blocks=2)
        self.assertEqual(r["version"], 1.2)
        self.assertGreater(r["pairs"], 0)

    @unittest.skipUnless(LIB, "liblzo2 not installed")
    def test_lzo_compressed_dictionaries_are_read_correctly(self):
        src = BytesSource(lzo_mdx(mdx_bytes(BILINGUAL, compression_type=0, block_size=4096)))
        r = probe(src, n_blocks=3)
        self.assertEqual(r["compression"], [1])
        self.assertGreater(r["pairs"], 0)

    def test_a_block_that_fails_its_checksum_is_rejected_not_scanned(self):
        data = mdx_bytes(BILINGUAL, block_size=4096)
        src = BytesSource(data)
        off, comp, dec = record_blocks(src, layout(src))[2]
        block = bytearray(data[off:off + comp])
        block[4] ^= 0xFF  # corrupt the stored checksum
        with self.assertRaises(ProbeError):
            decode_block(bytes(block), dec)

    def test_a_sample_of_candidate_pairs_is_kept_for_re_judging(self):
        r = probe(BytesSource(mdx_bytes(BILINGUAL, block_size=4096)), n_blocks=3)
        self.assertEqual(len(r["samples"]), 12)
        self.assertEqual(r["samples"][0], {"en": "Mira propped the window open for the florp.",
                                           "zh": "米拉把窗户撑开好让弗洛普进来。", "english_chinese": True})
        self.assertEqual(r["pairs_foreign"], 0)

    def test_a_german_chinese_dictionary_is_not_counted_as_english(self):
        german = {f"wort{i}": f"<div>{_filler(20)}</div><div>Er öffnet das Fenster, weil es zu warm ist.</div>"
                              f"<div>他打开窗户，因为太热了。</div>" for i in range(300)}
        r = probe(BytesSource(mdx_bytes(german, block_size=4096)), n_blocks=3)
        self.assertEqual(r["pairs_loose"], 0)
        self.assertGreater(r["pairs_foreign"], 0)
        self.assertFalse(any(s["english_chinese"] for s in r["samples"]))

    def test_a_truncated_file_is_reported_as_truncated(self):
        # Some files on the server stop partway through their record blocks.
        data = mdx_bytes(BILINGUAL, block_size=4096)
        with self.assertRaisesRegex(ProbeError, "^truncated: the index needs"):
            probe(BytesSource(data[:len(data) * 2 // 3]))

    def test_english_only_dictionary_scores_zero(self):
        self.assertEqual(probe(BytesSource(mdx_bytes(ENGLISH_ONLY, block_size=4096)))["pairs"], 0)

    def test_encrypted_key_sections_are_reported_not_guessed(self):
        data = bytearray(mdx_bytes(BILINGUAL))
        # rewrite the header's Encrypted attribute to "1" (key section encrypted)
        text = data[4:4 + int.from_bytes(data[:4], "big")].decode("utf-16-le")
        self.assertIn('Encrypted="', text)
        patched = text.replace('Encrypted="0"', 'Encrypted="1"').replace('Encrypted="No"', 'Encrypted="1"')
        self.assertNotEqual(patched, text)
        raw = patched.encode("utf-16-le")
        data[4:4 + len(raw)] = raw
        size = int.from_bytes(data[:4], "big")
        data[4 + size:8 + size] = struct.pack("<I", zlib.adler32(bytes(data[4:4 + size])))  # a valid header
        with self.assertRaisesRegex(ProbeError, "encrypted"):
            probe(BytesSource(bytes(data)))

    def test_a_corrupt_header_is_reported(self):
        data = bytearray(mdx_bytes(BILINGUAL))
        data[4 + int.from_bytes(data[:4], "big")] ^= 0xFF  # the header's Adler-32
        with self.assertRaisesRegex(ProbeError, "header checksum"):
            probe(BytesSource(bytes(data)))


if __name__ == "__main__":
    unittest.main()
