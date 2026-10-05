"""Local lookup server over all three layers of the unified dictionary.

    .venv/bin/python scripts/serve_unified.py [--port 8766]   ->  http://127.0.0.1:8766/

Routes
  /                      search page (scripts/lookup_ui/index.html)
  /analyze               text analysis page (scripts/lookup_ui/analyze.html; POST /api/analyze below)
  /static/NAME           the page's own CSS/JS and the website's design tokens (allow-listed)
  /api/entry/ID          one entry's complete structured data (the unified view's "show all")
  /api/lookup?q=WORD     every dictionary's entries for WORD (redirects followed), each with a
                         layer-2 summary; suggestions when nothing matches
  /api/zh?q=中文         Chinese -> English via the Chinese gloss index, ranked by agreement
  /api/define?q=words    English definitions matching the words ("which word means ...")
  /entry/ID              one entry as a full page: its dictionary's CSS and JS, relative
                         resources resolved to that dictionary's store, sound:// playable,
                         entry:// links turned into searches
  /res/KEY/PATH          a resource (audio, image, stylesheet) from resources.db
  POST /api/analyze      {"text": "..."} -> the text analyzer's result (analyzer/README.md); JSON
                         only, so another site's page cannot make the server work for it

The routing and responses live in App, which never touches a socket, so every
route is testable directly. Binds to 127.0.0.1 only.
"""
from __future__ import annotations

import argparse
import contextlib
import html
import json
import mimetypes
import re
import shlex
import sqlite3
import sys
import threading
import time
import urllib.parse
import zlib
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_resources import SCHEMES, norm_key  # noqa: E402
from build_unified import CORPUS  # noqa: E402
from unified_lookup import lookup, suggest  # noqa: E402

SUMMARY_SENSES = 6       # senses per entry in a lookup; the rest via /api/entry/ID
SUMMARY_EXAMPLES = 2     # examples per sense in a lookup
UI = Path(__file__).resolve().parent / "lookup_ui"
SITE = Path(__file__).resolve().parent.parent / "site"
# The only files served besides the APIs: an allow-list, never a filesystem path from the URL.
STATIC = {
    "lookup.css": (UI / "lookup.css", "text/css; charset=utf-8"),
    "lookup.js": (UI / "lookup.js", "text/javascript; charset=utf-8"),
    "render.js": (UI / "render.js", "text/javascript; charset=utf-8"),
    "analyze.js": (UI / "analyze.js", "text/javascript; charset=utf-8"),
    "analysis.js": (UI / "analysis.js", "text/javascript; charset=utf-8"),
    "tokens.css": (SITE / "tokens.css", "text/css; charset=utf-8"),  # the website's design tokens
    "site.css": (SITE / "style.css", "text/css; charset=utf-8"),  # the website's base styles
}
ZH_LIMIT = 40
ZH_ROWS = 5000          # gloss rows considered; exact matches are taken first
DEFINE_LIMIT = 50
EXTRA_TYPES = {".spx": "audio/ogg", ".ogg": "audio/ogg", ".mp3": "audio/mpeg", ".wav": "audio/wav",
               ".css": "text/css", ".js": "text/javascript", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf"}
_SOUND = re.compile(r"""(href|src)\s*=\s*(["'])sound://([^"']+)\2""", re.I)
_ENTRY = re.compile(r"""href\s*=\s*(["'])(?:entry|bword)://([^"']*)\1""", re.I)
# Google ad-tag calls scraped along with some online dictionaries' pages: they only throw
# "googletag is not defined". Dropped when rendering; the stored entry is untouched.
# Root-relative src/href ("/images/x.png"; AHD, OED, MWU, Etymonline, MW Learner's): <base> does
# not apply to them, so they are pointed at the dictionary's resource store explicitly.
_ROOT_RELATIVE = re.compile(r"""\b(src|href)\s*=\s*(["'])/(?!/)""", re.I)
_AD_SCRIPT = re.compile(r"<script\b[^>]*>(?:(?!</script>).)*?googletag(?:(?!</script>).)*</script>", re.I | re.S)

# Runs in the entry's frame. Sound links play instead of navigating, and in-page "#anchor"
# links scroll: with <base href> pointing at the resource store they would otherwise leave the page.
_PLAYER = """<script>document.addEventListener('click',function(e){
var a=e.target.closest('a');if(!a)return;var raw=a.getAttribute('href')||'';
if(a.hasAttribute('data-audio')){e.preventDefault();new Audio(a.href).play().catch(function(err){a.title='Playback failed: '+err.message;});return;}
if(raw.charAt(0)==='#'){e.preventDefault();var t=document.getElementById(raw.slice(1))||document.getElementsByName(raw.slice(1))[0];
if(t)t.scrollIntoView();}},true);</script>"""


def _json(data, status: int = 200):
    return status, {"Content-Type": "application/json; charset=utf-8"}, json.dumps(data, ensure_ascii=False).encode()


_ID = re.compile(r"[0-9]{1,19}")
SQLITE_MAX_INT = 2 ** 63 - 1


def _entry_id(part: str) -> int | None:
    """An entry id from the URL: ASCII digits within SQLite's integer range, else None."""
    return int(part) if _ID.fullmatch(part) and int(part) <= SQLITE_MAX_INT else None


def _sound_name(ref: str) -> str:
    """The resource a sound:// (file://, mdd://) reference names, taken literally: it is an .mdd file
    name, so "?", "#" and "%" are characters of it, not URL syntax."""
    for scheme in SCHEMES:
        if ref.lower().startswith(scheme):
            return ref[len(scheme):]
    return ref


def _url_path(name: str) -> str:
    """A resource name as a URL path: every character but "/" percent-encoded (UTF-8), so it comes
    back unchanged from handle(), which percent-decodes each path segment."""
    return urllib.parse.quote(name, safe="/")


def _text(message: str, status: int):
    return status, {"Content-Type": "text/plain; charset=utf-8"}, message.encode()


class ZhIndexMissing(RuntimeError):
    """The database predates the Chinese trigram index: a 503 that says how to add it."""


ANALYZE_MAX_BYTES = 1_000_000  # the analyzer itself takes up to 200,000 characters
# Memory-mapped reads halve a warm lookup (1.06 -> 0.48 ms median, 500 random words); SQLite as built
# here caps the mapping at 2 GB, which covers every index a lookup reads.
MMAP_BYTES = 2_147_418_112
# What a lookup reads, walked once at start (in the background) so the first lookups find it in memory;
# the entries and examples themselves are read only when shown.
PREWARM = [
    ("headwords", "SELECT count(*) FROM headword"),
    ("entries by headword", "SELECT count(*) FROM entry INDEXED BY entry_norm WHERE norm IS NOT NULL"),
    ("redirects", "SELECT count(*) FROM redirect INDEXED BY redirect_norm WHERE norm IS NOT NULL"),
    ("layer-2 entries", "SELECT count(*) FROM s_entry INDEXED BY s_entry_dict WHERE dict_id IS NOT NULL"),
    ("senses by entry", "SELECT count(*) FROM s_sense INDEXED BY s_sense_entry WHERE entry_id IS NOT NULL"),
    ("pronunciations", "SELECT count(*) FROM s_pron INDEXED BY s_pron_entry WHERE entry_id IS NOT NULL"),
    ("examples by sense", "SELECT count(*) FROM s_example INDEXED BY s_example_sense WHERE sense_id IS NOT NULL"),
    ("Chinese terms", "SELECT count(*) FROM zh_term INDEXED BY zh_term_term WHERE term IS NOT NULL"),
    ("Chinese trigrams", "SELECT count(*) FROM zh_fts_data"),
    ("headword trigrams", "SELECT count(*) FROM headword_fts_data"),
]


class Analyzer:
    """The text analyzer, loaded on first use (spaCy and the lexicon take seconds and memory)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._loaded = None

    def __call__(self, text: str) -> dict:
        with self._lock:
            if self._loaded is None:
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analyzer"))
                from analysis import load_nlp
                from analysis.lexicon import load
                self._loaded = (load_nlp(), load())
        from analysis.analyze import analyze
        return analyze(text, *self._loaded)


class App:
    def __init__(self, db: Path, resources: Path | None = None, analyzer=None):
        self.db = db
        self.resources = resources if resources and resources.exists() else None
        self.analyzer = analyzer or Analyzer()

    def handle_post(self, raw_path: str, content_type: str, body: bytes):
        """POST /api/analyze: {"text": ...} -> the analysis."""
        if urllib.parse.urlsplit(raw_path).path.rstrip("/") != "/api/analyze":
            return _text("not found", 404)
        if content_type.split(";")[0].strip().lower() != "application/json":
            return _text("send JSON: Content-Type application/json", 415)
        if len(body) > ANALYZE_MAX_BYTES:
            return _text(f"at most {ANALYZE_MAX_BYTES:,} bytes", 413)
        try:
            text = json.loads(body.decode("utf-8"))["text"]
            if not isinstance(text, str):
                raise TypeError("text must be a string")
        except (ValueError, KeyError, TypeError) as error:
            return _text(f'expected {{"text": "..."}}: {error}', 400)
        try:
            return _json(self.analyzer(text))
        except FileNotFoundError as error:  # analyzer.db not built
            return _text(str(error), 503)
        except ValueError as error:          # too long
            return _text(str(error), 413)

    def prewarm(self) -> list[str]:
        """Read what a lookup reads (PREWARM), so the first lookups after a restart are warm; the
        names of the parts read. A part this database lacks is skipped and named as such."""
        done = []
        with contextlib.closing(self._conn()) as conn:
            for name, sql in PREWARM:
                try:
                    conn.execute(sql).fetchone()
                    done.append(name)
                except sqlite3.OperationalError:
                    done.append(f"{name} (not in this database)")
        return done

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True, check_same_thread=False)
        conn.execute(f"PRAGMA mmap_size={MMAP_BYTES}")
        if self.resources:
            conn.execute("ATTACH DATABASE ? AS res", (f"file:{self.resources}?mode=ro",))
        return conn

    @staticmethod
    def _has_layer2(conn) -> bool:
        return conn.execute("SELECT 1 FROM sqlite_master WHERE name = 's_sense'").fetchone() is not None

    # ---- routing ---------------------------------------------------------------------
    def handle(self, raw_path: str):
        url = urllib.parse.urlsplit(raw_path)
        query = urllib.parse.parse_qs(url.query)
        q = (query.get("q") or [""])[0].strip()
        if "\x00" in q:  # no query holds one; SQLite's query syntax cannot (full-text search fails on it)
            return _text("a query cannot contain a NUL character", 400)
        parts = [urllib.parse.unquote(p) for p in url.path.split("/") if p]
        conn = self._conn()
        try:
            if not parts:
                return 200, {"Content-Type": "text/html; charset=utf-8"}, (UI / "index.html").read_bytes()
            if parts == ["analyze"]:
                return 200, {"Content-Type": "text/html; charset=utf-8"}, (UI / "analyze.html").read_bytes()
            if len(parts) == 2 and parts[0] == "static":
                if parts[1] not in STATIC:
                    return _text("not found", 404)
                path, ctype = STATIC[parts[1]]
                return 200, {"Content-Type": ctype, "Cache-Control": "no-cache"}, path.read_bytes()
            if len(parts) == 3 and parts[:2] == ["api", "entry"]:
                entry_id = _entry_id(parts[2])
                return _text("bad entry id", 400) if entry_id is None else self.api_entry(conn, entry_id)
            if parts == ["api", "lookup"]:
                return _json(self.api_lookup(conn, q))
            if parts == ["api", "zh"]:
                try:
                    return _json(self.api_zh(conn, q))
                except ZhIndexMissing as missing:
                    return _text(str(missing), 503)
            if parts == ["api", "define"]:
                return _json(self.api_define(conn, q))
            if len(parts) == 2 and parts[0] == "entry":
                entry_id = _entry_id(parts[1])
                return _text("bad entry id", 400) if entry_id is None else self.entry_page(conn, entry_id)
            if len(parts) >= 3 and parts[0] == "res":
                return self.resource(conn, parts[1], "/".join(parts[2:]))
            return _text("not found", 404)
        finally:
            conn.close()

    # ---- APIs ------------------------------------------------------------------------
    def summary(self, conn, entry_id: int, full: bool = False) -> dict | None:
        """One entry's layer-2 data, the input of the unified view.

        By default the first SUMMARY_SENSES senses with up to SUMMARY_EXAMPLES examples each;
        full=True returns everything. `totals` says how much there is, so the page can offer
        the rest (/api/entry/ID).
        """
        row = conn.execute("SELECT headword, homograph, pos, etymology, forms, stub FROM s_entry WHERE entry_id = ?",
                           (entry_id,)).fetchone()
        if row is None:
            return None
        headword, homograph, pos, etymology, forms, stub = row
        dict_id, key = conn.execute("SELECT d.id, d.key FROM entry e JOIN dictionary d ON d.id = e.dict_id "
                                    "WHERE e.id = ?", (entry_id,)).fetchone()
        prons = [{"region": r, "ipa": i, "note": n, "audio": self.audio_url(conn, dict_id, key, a)}
                 for r, i, a, n in conn.execute("SELECT region, ipa, audio, note FROM s_pron WHERE entry_id = ? ORDER BY ord", (entry_id,))]
        total_senses = conn.execute("SELECT count(*) FROM s_sense WHERE entry_id = ?", (entry_id,)).fetchone()[0]
        total_examples = conn.execute("SELECT count(*) FROM s_example x JOIN s_sense s ON s.id = x.sense_id "
                                      "WHERE s.entry_id = ?", (entry_id,)).fetchone()[0]
        limit = -1 if full else SUMMARY_SENSES
        senses = []
        for sid, kind, spos, number, phrase, labels, definition, definition_zh in conn.execute(
                "SELECT id, kind, pos, number, phrase, labels, definition, definition_zh FROM s_sense "
                "WHERE entry_id = ? ORDER BY ord LIMIT ?", (entry_id, limit)):
            examples = [{"kind": k, "text": t, "text_zh": tz, "source": so, "date": da, "labels": json.loads(lb)}
                        for k, t, tz, so, da, lb in conn.execute(
                            "SELECT kind, text, text_zh, source, date, labels FROM s_example WHERE sense_id = ? "
                            "ORDER BY ord LIMIT ?", (sid, -1 if full else SUMMARY_EXAMPLES))]
            senses.append({"kind": kind, "pos": spos, "number": number, "phrase": phrase, "labels": json.loads(labels),
                           "definition": definition, "definition_zh": definition_zh, "examples": examples})
        return {"entry_id": entry_id, "headword": headword, "homograph": homograph, "pos": json.loads(pos),
                "forms": json.loads(forms), "etymology": etymology, "stub": stub, "prons": prons, "senses": senses,
                "totals": {"senses": total_senses, "examples": total_examples}}

    def api_entry(self, conn, entry_id: int):
        entry = self.summary(conn, entry_id, full=True) if self._has_layer2(conn) else None
        if entry is None:
            return _text("no structured entry", 404)
        return _json(entry)

    def audio_url(self, conn, dict_id: int, key: str, ref: str) -> str:
        """A playable URL for a pronunciation's audio reference, or "" when there is nothing to play.

        Some dictionaries play audio from the publisher's site (CED): those URLs pass through.
        Others reference files in their .mdd; a reference is offered only if the file is in the
        resource store, so a dictionary that shipped without audio (OED) shows no dead button.
        """
        if not ref:
            return ""
        if ref.startswith(("http://", "https://")):
            return ref
        if not self.resources:
            return ""
        path = norm_key(_sound_name(ref))
        found = conn.execute("SELECT 1 FROM res.resource WHERE dict_id = ? AND norm = ?", (dict_id, path)).fetchone()
        return f"/res/{_url_path(key)}/{_url_path(path)}" if found else ""

    def api_lookup(self, conn, q: str) -> dict:
        if not q:
            return {"query": q, "hits": [], "suggestions": []}
        layer2 = self._has_layer2(conn)
        # One card per (dictionary, headword): homographs share it, in entry order.
        cards: dict[tuple[str, str], dict] = {}
        for h in lookup(conn, q):
            card = cards.setdefault((h.dict_key, h.headword), {
                "dict": h.dict_key, "dict_name": h.dict_name, "headword": h.headword, "via": list(h.via),
                "entry_ids": [], "summaries": []})
            card["entry_ids"].append(h.entry_id)
            if layer2:
                card["summaries"].append(self.summary(conn, h.entry_id))
        hits = list(cards.values())
        return {"query": q, "hits": hits, "suggestions": [] if hits else suggest(conn, q)}

    def api_zh(self, conn, q: str) -> dict:
        """English words for a Chinese term: senses whose Chinese gloss is the term, then those whose
        gloss contains it (shortest terms first), ZH_ROWS senses at most; ranked by how many
        dictionaries give the exact term, then any. Exact terms come from zh_term's index; terms
        containing the query from zh_fts, a trigram index of the distinct terms (build_structured.py),
        so no query scans the two million zh_term rows."""
        if not q or not self._has_layer2(conn):
            return {"query": q, "results": []}
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'zh_fts'").fetchone() is None:
            raise ZhIndexMissing("the Chinese index zh_fts is missing: run PYTHONPATH=scripts .venv/bin/python "
                                 f"scripts/build_structured.py --db {shlex.quote(str(self.db))} --derived-only")
        sql = ("SELECT e.headword, d.key, s.definition_zh FROM zh_term z JOIN s_sense s ON s.id = z.sense_id "
               "JOIN entry e ON e.id = s.entry_id JOIN dictionary d ON d.id = s.dict_id WHERE z.term = ?")
        rows = [(*r, True) for r in conn.execute(sql + " LIMIT ?", (q, ZH_ROWS))]
        # Every term gives at least one row, so the rows still wanted bound the terms needed.
        budget = ZH_ROWS - len(rows)
        if len(q) >= 3:  # a trigram index answers MATCH for three characters or more; LIKE below that
            where, arg = "zh_fts MATCH ?", '"' + q.replace('"', '""') + '"'
        else:
            where = "term LIKE ? ESCAPE '\\'"
            arg = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        containing = [t for (t,) in conn.execute(
            f"SELECT term FROM zh_fts WHERE {where} AND term != ? ORDER BY length(term), term LIMIT ?",
            (arg, q, budget))] if budget > 0 else []
        for term in containing:
            if len(rows) >= ZH_ROWS:
                break
            rows += [(*r, False) for r in conn.execute(sql + " LIMIT ?", (term, ZH_ROWS - len(rows)))]
        groups: dict[str, dict] = defaultdict(lambda: {"dicts": set(), "exact_dicts": set(), "glosses": []})
        for headword, dict_key, gloss, exact in rows:
            g = groups[headword.lower()]
            g.setdefault("headword", headword)
            g["dicts"].add(dict_key)
            if exact:
                g["exact_dicts"].add(dict_key)
            if gloss not in g["glosses"] and len(g["glosses"]) < 4:
                g["glosses"].append(gloss)
        ranked = sorted(groups.values(), key=lambda g: (-len(g["exact_dicts"]), -len(g["dicts"]), len(g["headword"]), g["headword"]))
        return {"query": q, "results": [{"headword": g["headword"], "dicts": sorted(g["dicts"]), "exact": len(g["exact_dicts"]),
                                         "glosses": g["glosses"]} for g in ranked[:ZH_LIMIT]]}

    def api_define(self, conn, q: str) -> dict:
        words = re.findall(r"[A-Za-z][A-Za-z'-]*", q)
        if not words or not self._has_layer2(conn):
            return {"query": q, "results": []}
        match = " ".join('"' + w.replace('"', "") + '"' for w in words)
        rows = conn.execute(
            "SELECT e.headword, d.key, s.definition FROM sense_fts f JOIN s_sense s ON s.id = f.rowid "
            "JOIN entry e ON e.id = s.entry_id JOIN dictionary d ON d.id = s.dict_id "
            "WHERE sense_fts MATCH ? ORDER BY f.rank LIMIT ?", (match, DEFINE_LIMIT)).fetchall()
        return {"query": q, "results": [{"headword": h, "dict": k, "definition": d} for h, k, d in rows]}

    # ---- entries and resources ---------------------------------------------------------
    def entry_page(self, conn, entry_id: int):
        row = conn.execute("SELECT e.body, d.key, d.stylesheet, d.script FROM entry e JOIN dictionary d ON d.id = e.dict_id "
                           "WHERE e.id = ?", (entry_id,)).fetchone()
        if row is None:
            return _text("no such entry", 404)
        body, key, css, js = row
        content = _AD_SCRIPT.sub("", zlib.decompress(body).decode("utf-8", "replace"))
        base = f"/res/{_url_path(key)}/"
        content = _ROOT_RELATIVE.sub(lambda m: f"{m.group(1)}={m.group(2)}{base}", content)  # before our own rewrites
        # The captured reference is attribute text: decode its entities ("&#63;" is "?"), then percent-encode
        # the file name, so "?", "#", "%" and "&" stay in the path and reach resource() unchanged.
        content = _SOUND.sub(lambda m: f'{m.group(1)}="{base}{_url_path(html.unescape(m.group(3)))}" data-audio', content)
        content = _ENTRY.sub(lambda m: f'href="/?q={urllib.parse.quote(html.unescape(m.group(2)))}" target="_top"', content)
        doc = (f'<!doctype html><html><head><meta charset="utf-8"><base href="{base}">'
               f"<style>{css}</style><script>{js}</script>{_PLAYER}</head><body>{content}</body></html>")
        return 200, {"Content-Type": "text/html; charset=utf-8"}, doc.encode()

    def resource(self, conn, key: str, path: str):
        if not self.resources:
            return _text("resources.db not built", 404)
        row = conn.execute("SELECT b.data FROM res.resource r JOIN res.blob b ON b.hash = r.hash "
                           "JOIN dictionary d ON d.id = r.dict_id WHERE d.key = ? AND r.norm = ?", (key, norm_key(path))).fetchone()
        if row is None:
            return _text("no such resource", 404)
        ext = Path(path).suffix.lower()
        ctype = EXTRA_TYPES.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"
        return 200, {"Content-Type": ctype, "Cache-Control": "max-age=31536000, immutable"}, row[0]


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server naming)
            status, headers, body = app.handle(self.path)
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if not 0 <= length <= ANALYZE_MAX_BYTES:
                status, headers, body = _text(f"Content-Length must be 0 to {ANALYZE_MAX_BYTES:,}", 413)
            else:
                status, headers, body = app.handle_post(self.path, self.headers.get("Content-Type", ""),
                                                        self.rfile.read(length))
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    return Handler


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=CORPUS / "unified.db")
    ap.add_argument("--resources", type=Path, default=CORPUS / "resources.db")
    ap.add_argument("--port", type=int, default=8766)
    args = ap.parse_args()
    app = App(args.db, args.resources)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(app))
    print(f"serving http://127.0.0.1:{args.port}/", file=sys.stderr)

    def warm():
        started = time.time()
        parts = app.prewarm()
        print(f"warmed in {time.time() - started:.1f}s: {', '.join(parts)}", file=sys.stderr)
    threading.Thread(target=warm, daemon=True).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
