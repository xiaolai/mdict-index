"""The lookup server over all three layers, on synthetic databases."""
import html
import json
import re
import sqlite3
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
import zlib
from http.server import ThreadingHTTPServer
from pathlib import Path

from build_resources import SCHEMA as L3_SCHEMA
from build_resources import norm_key
from build_structured import INDEXES as L2_INDEXES
from build_structured import SCHEMA as L2_SCHEMA
from build_unified import INDEXES as L1_INDEXES
from build_unified import SCHEMA as L1_SCHEMA
from build_unified import norm
from serve_unified import App, make_handler

ENTRIES = [  # (id, dict_id, headword, html)
    (1, 1, "take", '<a href="sound://uk/Take.mp3">▶</a> <a href="entry://took">took</a> <a href="#idioms">jump</a> <img src="img/A.png">'),
    (2, 1, "take", "<b>take</b> (second homograph)<script>googletag.cmd.push(function(){});</script><script>keep()</script>"),
    (3, 2, "go", '<b>go</b> <img src="/Img/Go.png"> <img src="//cdn.example/x.png"> <a href="/view/go">page</a>'),
    (4, 1, "both", '<a href="sound://salt&amp;pepper.mp3">▶</a>'),
    # Sound file names holding URL syntax, written with entities and literally (invented names).
    (5, 1, "odd", '<a href="sound://q&#63;a.mp3">1</a> <a href="sound://h&#35;b.mp3">2</a> <a href="sound://p%20c.mp3">3</a> '
                  "<a href='sound://s p&amp;d.mp3'>4</a> <a href=\"sound://uk/naïve 词.mp3\">5</a>"),
]
ODD_SOUNDS = {"q?a.mp3": b"Q", "h#b.mp3": b"H", "p%20c.mp3": b"P", "s p&d.mp3": b"S", "uk/naïve 词.mp3": b"N"}
REDIRECTS = [(2, "went", "go")]
SENSES = [  # (id, entry_id, dict_id, ord, kind, pos, number, phrase, labels, definition, definition_zh)
    (1, 1, 1, 0, "sense", "verb", "1", "", "[]", "to carry something away", "带走；拿走"),
    (2, 1, 1, 1, "sense", "verb", "2", "", "[]", "to leave with somebody", "打招呼"),
    (3, 3, 2, 0, "sense", "verb", "1", "", "[]", "to leave a place", "离开；向某人打招呼"),
]


def build(root: Path) -> tuple[Path, Path]:
    db, res = root / "u.db", root / "r.db"
    conn = sqlite3.connect(db)
    conn.executescript(L1_SCHEMA)
    for i, key in ((1, "a"), (2, "b")):
        conn.execute("INSERT INTO dictionary VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (i, key, key.upper(), None, None, "c", "current", None, "r", "f", "x.mdx", 2.0, "{}", f".{key}{{}}", ""))
    conn.executemany("INSERT INTO entry VALUES (?,?,?,?,?)",
                     [(i, d, h, norm(h), zlib.compress(b.encode())) for i, d, h, b in ENTRIES])
    conn.executemany("INSERT INTO redirect VALUES (?,?,?,?,?)", [(d, h, norm(h), t, norm(t)) for d, h, t in REDIRECTS])
    conn.executescript(L1_INDEXES)
    conn.execute("INSERT INTO headword_fts(headword_fts) VALUES ('rebuild')")
    conn.executescript(L2_SCHEMA)
    conn.executemany("INSERT INTO s_entry VALUES (?,?,?,?,?,?,?,?,?,?,NULL)",
                     [(1, 1, "take", "", '["verb"]', "", "[]", "{}", "", ""), (2, 1, "take", "", "[]", "", "[]", "{}", "", ""),
                      (3, 2, "go", "", '["verb"]', "", "[]", "{}", "", "")])
    conn.executemany("INSERT INTO s_pron VALUES (?,?,?,?,?,?)", [
        (1, 0, "uk", "teɪk", "sound://uk/Take.mp3", "strong form"),   # in the resource store
        (1, 1, "us", "teɪk", "https://publisher.example/take.mp3", ""),  # played from the publisher's site
        (1, 2, "", "teɪk", "sound://never/shipped.mp3", ""),          # referenced but not in any .mdd
    ])
    conn.executemany("INSERT INTO s_sense VALUES (?,?,?,?,?,?,?,?,?,?,?)", SENSES)
    conn.executescript(L2_INDEXES)
    from build_structured import zh_terms
    conn.executemany("INSERT INTO zh_term VALUES (?,?)", [(t, s[0]) for s in SENSES for t in zh_terms(s[10])])
    conn.execute("INSERT INTO sense_fts(sense_fts) VALUES ('rebuild')")
    conn.commit()
    conn.close()
    r = sqlite3.connect(res)
    r.executescript(L3_SCHEMA)
    odd = [(1, "\\" + name.replace("/", "\\"), data) for name, data in ODD_SOUNDS.items()]
    for dict_id, path, data in [(1, "\\uk\\take.mp3", b"MP3"), (1, "\\img\\a.png", b"PNG"), (1, "\\img\\a#2.png", b"PNG2")] + odd:
        r.execute("INSERT INTO blob VALUES (?,?,?)", (path, len(data), data))
        r.execute("INSERT INTO resource VALUES (?,?,?,?)", (dict_id, norm_key(path), path, path))
    r.commit()
    r.close()
    return db, res


class ServerApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db, cls.res = build(Path(cls.tmp.name))
        cls.app = App(cls.db, cls.res)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def get(self, path):
        return self.app.handle(path)

    def get_json(self, path):
        status, headers, body = self.get(path)
        self.assertEqual((status, headers["Content-Type"]), (200, "application/json; charset=utf-8"))
        return json.loads(body)

    def test_search_page_and_its_allow_listed_assets(self):
        status, headers, body = self.get("/")
        self.assertEqual(status, 200)
        for asset in (b"/static/tokens.css", b"/static/site.css", b"/static/lookup.css", b"/static/lookup.js"):
            self.assertIn(asset, body)
        for name, ctype in [("lookup.js", "text/javascript"), ("render.js", "text/javascript"),
                            ("lookup.css", "text/css"), ("tokens.css", "text/css"), ("site.css", "text/css")]:
            status, headers, body = self.get(f"/static/{name}")
            self.assertEqual(status, 200, name)
            self.assertTrue(headers["Content-Type"].startswith(ctype), name)
            self.assertTrue(body, name)
        self.assertIn(b"--c-accent", self.get("/static/tokens.css")[2])  # the website's design tokens

    def test_only_allow_listed_static_files_are_served(self):
        for path in ["/static/index.html", "/static/serve_unified.py", "/static/..%2Fserve_unified.py",
                     "/static/../../site/app.js", "/static/"]:
            self.assertEqual(self.get(path)[0], 404, path)

    def test_entry_api_returns_everything_while_lookup_is_trimmed(self):
        full = self.get_json("/api/entry/1")
        self.assertEqual((full["headword"], full["totals"]["senses"], len(full["senses"])), ("take", 2, 2))
        self.assertEqual(full["senses"][0]["examples"], [])
        self.assertEqual(self.get("/api/entry/999")[0], 404)
        card = self.get_json("/api/lookup?q=take")["hits"][0]
        self.assertEqual(card["summaries"][0]["totals"], {"senses": 2, "examples": 0})

    def test_lookup_groups_homographs_and_carries_layer2(self):
        r = self.get_json("/api/lookup?q=TAKE")
        (card,) = r["hits"]
        self.assertEqual((card["dict"], card["headword"], card["entry_ids"]), ("a", "take", [1, 2]))
        first = card["summaries"][0]
        self.assertEqual([p["audio"] for p in first["prons"]],
                         ["/res/a/uk/take.mp3", "https://publisher.example/take.mp3", ""])
        self.assertEqual(first["prons"][0]["note"], "strong form")
        self.assertEqual([s["definition_zh"] for s in first["senses"]], ["带走；拿走", "打招呼"])

    def test_lookup_follows_redirects_and_suggests(self):
        (card,) = self.get_json("/api/lookup?q=went")["hits"]
        self.assertEqual((card["headword"], card["via"]), ("go", ["go"]))
        r = self.get_json("/api/lookup?q=takke")
        self.assertEqual((r["hits"], r["suggestions"][:1]), ([], ["take"]))

    def test_chinese_to_english_ranks_exact_matches_first(self):
        r = self.get_json("/api/zh?q=" + urllib.parse.quote("打招呼"))
        self.assertEqual([x["headword"] for x in r["results"]], ["take", "go"])  # take: exact term; go: substring
        self.assertEqual(r["results"][0]["exact"], 1)

    def test_define_searches_english_definitions(self):
        r = self.get_json("/api/define?q=leave")
        self.assertEqual({x["headword"] for x in r["results"]}, {"take", "go"})
        self.assertEqual(self.get_json("/api/define?q=")["results"], [])

    def test_entry_page_wires_resources_audio_and_links(self):
        status, headers, body = self.get("/entry/1")
        page = body.decode()
        self.assertEqual(status, 200)
        self.assertIn('<base href="/res/a/">', page)
        self.assertIn(".a{}", page)
        self.assertIn('href="/res/a/uk/Take.mp3" data-audio', page)
        self.assertIn('href="/?q=took" target="_top"', page)
        self.assertIn("scrollIntoView", page)  # in-page anchors survive the <base> element
        self.assertEqual(self.get("/entry/999")[0], 404)

    def test_root_relative_paths_point_into_the_dictionarys_store(self):
        # A <base> element does not apply to "/..." paths, so they are rewritten explicitly.
        page = self.get("/entry/3")[2].decode()
        self.assertIn('src="/res/b/Img/Go.png"', page)
        self.assertIn('href="/res/b/view/go"', page)
        self.assertIn('src="//cdn.example/x.png"', page)  # protocol-relative URLs are left alone

    def test_scraped_ad_scripts_are_dropped_but_other_scripts_kept(self):
        page = self.get("/entry/2")[2].decode()
        self.assertNotIn("googletag", page)
        self.assertIn("<script>keep()</script>", page)

    def test_resources_resolve_case_and_slash_insensitively(self):
        for path, ctype, data in [("/res/a/uk/Take.mp3", "audio/mpeg", b"MP3"), ("/res/a/IMG/A.PNG", "image/png", b"PNG")]:
            status, headers, body = self.get(path)
            self.assertEqual((status, headers["Content-Type"], body), (200, ctype, data), path)
        self.assertEqual(self.get("/res/a/missing.png")[0], 404)
        self.assertEqual(self.get("/res/b/uk/take.mp3")[0], 404)  # resources are per dictionary
        self.assertEqual(self.get("/nowhere")[0], 404)

    def test_a_literal_hash_in_a_resource_name_is_part_of_the_name(self):
        # The browser sends "#" in a file name as %23; once decoded it is a character, not a fragment.
        self.assertEqual(self.get("/res/a/img/a%232.png")[2], b"PNG2")
        self.assertEqual(self.get("/res/a/img/a.png")[2], b"PNG")

    def test_entry_ids_must_be_ascii_decimals_in_sqlite_range(self):
        for bad in ["%C2%B2", "9" * 30, str(2 ** 63)]:  # "²" passes str.isdigit(); the others overflow SQLite
            for route in ("/api/entry/", "/entry/"):
                self.assertEqual(self.get(route + bad)[0], 400, route + bad)
        self.assertEqual(self.get(f"/entry/{2 ** 63 - 1}")[0], 404)  # in range, just absent

    def test_sound_links_with_entities_are_escaped_once(self):
        page = self.get("/entry/4")[2].decode()
        self.assertIn('href="/res/a/salt%26pepper.mp3" data-audio', page)  # &amp; is "&", sent once as %26

    def sound_hrefs(self, entry_id):
        page = self.get(f"/entry/{entry_id}")[2].decode()
        return [html.unescape(h) for h in re.findall(r'href="([^"]*)" data-audio', page)]

    def test_any_sound_file_name_round_trips_through_its_link(self):
        # "?", "#", "%", space, "&" and non-ASCII are characters of the file name, not URL syntax.
        hrefs = self.sound_hrefs(5)
        self.assertEqual(len(hrefs), len(ODD_SOUNDS))
        for href, (name, data) in zip(hrefs, ODD_SOUNDS.items()):
            parts = urllib.parse.urlsplit(href)
            self.assertEqual((parts.query, parts.fragment), ("", ""), href)  # nothing leaks out of the path
            self.assertTrue(href.isascii(), href)
            self.assertEqual(urllib.parse.unquote(parts.path), "/res/a/" + name, href)
            self.assertEqual(self.get(href)[:3:2], (200, data), href)

    def test_a_pronunciation_names_its_audio_file_literally(self):
        conn = self.app._conn()
        self.addCleanup(conn.close)
        self.assertEqual(self.app.audio_url(conn, 1, "a", "sound://h#b.mp3"), "/res/a/h%23b.mp3")
        self.assertEqual(self.get("/res/a/h%23b.mp3")[2], b"H")
        self.assertEqual(self.app.audio_url(conn, 1, "a", "sound://q?a.mp3"), "/res/a/q%3Fa.mp3")

    def test_failed_playback_in_an_entry_page_is_caught(self):
        self.assertIn(".play().catch(", self.get("/entry/1")[2].decode())

    def test_without_a_resource_store_only_external_audio_is_offered(self):
        card = json.loads(App(self.db, None).handle("/api/lookup?q=take")[2])["hits"][0]
        self.assertEqual([p["audio"] for p in card["summaries"][0]["prons"]], ["", "https://publisher.example/take.mp3", ""])

    def test_resources_missing_database_is_a_clear_404(self):
        status, _, body = App(self.db, None).handle("/res/a/uk/take.mp3")
        self.assertEqual((status, body), (404, b"resources.db not built"))


class ServerSocket(unittest.TestCase):
    def test_http_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, res = build(Path(tmp))
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(db, res)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_address[1]}/api/lookup?q=go"
                with urllib.request.urlopen(url) as resp:
                    self.assertEqual(resp.status, 200)
                    self.assertEqual(json.loads(resp.read())["hits"][0]["headword"], "go")
                odd = f"http://127.0.0.1:{server.server_address[1]}/res/a/" + urllib.parse.quote("s p&d.mp3")
                with urllib.request.urlopen(odd) as resp:
                    self.assertEqual(resp.read(), b"S")
            finally:
                server.shutdown()
                server.server_close()


class AnalyzeRoute(unittest.TestCase):
    """POST /api/analyze, with the analyzer replaced: the route's own rules."""

    def app(self, analyzer=lambda text: {"echo": text}):
        return App(Path("/nonexistent.db"), None, analyzer)

    def post(self, body, content_type="application/json", path="/api/analyze", **kw):
        return self.app(**kw).handle_post(path, content_type, body if isinstance(body, bytes) else body.encode())

    def test_json_in_json_out(self):
        status, headers, body = self.post(json.dumps({"text": "She gave it up."}))
        self.assertEqual((status, json.loads(body)), (200, {"echo": "She gave it up."}))
        self.assertTrue(headers["Content-Type"].startswith("application/json"))

    def test_only_json_so_other_sites_cannot_post_plain_text(self):
        self.assertEqual(self.post("She gave it up.", content_type="text/plain")[0], 415)
        self.assertEqual(self.post(json.dumps({"text": "x"}), content_type="application/json; charset=utf-8")[0], 200)

    def test_malformed_requests(self):
        self.assertEqual(self.post("not json")[0], 400)
        self.assertEqual(self.post(json.dumps({"words": "x"}))[0], 400)
        self.assertEqual(self.post(json.dumps({"text": 5}))[0], 400)
        self.assertEqual(self.post(json.dumps({"text": "x"}), path="/api/elsewhere")[0], 404)

    def test_size_and_build_errors_are_reported(self):
        self.assertEqual(self.post(b'{"text": "' + b"a" * 1_000_001 + b'"}')[0], 413)

        def unbuilt(text):
            raise FileNotFoundError("analyzer.db is missing: run analyzer/build.py")
        status, _, body = self.post(json.dumps({"text": "x"}), analyzer=unbuilt)
        self.assertEqual(status, 503)
        self.assertIn(b"analyzer/build.py", body)

    def test_over_http(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app()))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{server.server_address[1]}/api/analyze",
                                         data=json.dumps({"text": "hi"}).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(json.loads(resp.read()), {"echo": "hi"})
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
