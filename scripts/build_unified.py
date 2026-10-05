"""Build one SQLite database holding every downloaded dictionary, losslessly.

    .venv/bin/python scripts/build_unified.py [--out corpus/unified.db] [--workers N]

Layer 1 of the unified dictionary: each dictionary's original HTML, keyed
by a shared lookup form of the headword, with redirects kept as data and
each dictionary's own CSS/JS stored alongside (entries only render
correctly with them). Nothing is parsed into senses here; that is layer 2,
done per dictionary.

Schema
  dictionary  one row per dictionary: curated metadata, MDX header, CSS, JS
  entry       one row per content entry: headword, norm, zlib-compressed HTML
  redirect    one row per @@@LINK= entry: headword -> target headword
  headword    every distinct norm, with an FTS5 trigram index for substring
              search (works for CJK, which has no word boundaries)

After loading each dictionary, row counts are checked against
corpus/_inspect/report.json; any mismatch fails the build.

Decoding is the slow part (reading the MDX blocks, normalizing headwords, recompressing
bodies), so each dictionary is decoded by its own worker process into a shard file; the
main process, the only writer of the database, appends the shards in plan order, so entry
ids come out exactly as a one-process build numbers them.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import unicodedata
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"

SCHEMA = """
CREATE TABLE dictionary (
  id INTEGER PRIMARY KEY,
  key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  full_name TEXT,
  zh_name TEXT,
  category TEXT NOT NULL,
  status TEXT NOT NULL,
  latest_edition TEXT,
  source_record TEXT NOT NULL,
  source_folder TEXT NOT NULL,
  source_file TEXT NOT NULL,
  mdx_version REAL NOT NULL,
  header_json TEXT NOT NULL,
  stylesheet TEXT NOT NULL,
  script TEXT NOT NULL
);
CREATE TABLE entry (
  id INTEGER PRIMARY KEY,
  dict_id INTEGER NOT NULL REFERENCES dictionary(id),
  headword TEXT NOT NULL,
  norm TEXT NOT NULL,
  body BLOB NOT NULL            -- zlib(UTF-8 HTML)
);
CREATE TABLE redirect (
  dict_id INTEGER NOT NULL REFERENCES dictionary(id),
  headword TEXT NOT NULL,
  norm TEXT NOT NULL,
  target TEXT NOT NULL,
  target_norm TEXT NOT NULL
);
"""
INDEXES = """
CREATE INDEX entry_norm ON entry(norm, dict_id);
CREATE INDEX redirect_norm ON redirect(norm, dict_id);
-- FTS5 external content needs an integer key on the content table, so no WITHOUT ROWID here.
CREATE TABLE headword (id INTEGER PRIMARY KEY, norm TEXT NOT NULL UNIQUE);
INSERT INTO headword(norm) SELECT norm FROM entry UNION SELECT norm FROM redirect;
CREATE VIRTUAL TABLE headword_fts USING fts5(norm, content='headword', content_rowid='id', tokenize='trigram');
"""


# Printed in headwords but not part of the word: stress marks (OED "ˌblue-ˈblood") and
# syllable dots (LDOCE "re‧cap", MW "base·ment·less").
_NOT_THE_WORD = dict.fromkeys(map(ord, "ˈˌ·‧•"))


def norm(headword: str) -> str:
    """Shared lookup form: NFKC, case-folded, accents, stress marks and syllable dots dropped, whitespace collapsed."""
    headword = headword.translate(_NOT_THE_WORD)
    text = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", headword).casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(unicodedata.normalize("NFC", text).split())


def temp_beside(out: Path) -> Path:
    """A new, uniquely named empty file next to `out`, to build into and then os.replace() over it.

    Unique per call, so two builds (or "x.db" and "x.sqlite" in one folder) never share a
    temporary file; next to `out`, so the final os.replace() stays on one filesystem.
    """
    fd, name = tempfile.mkstemp(dir=out.parent, prefix=f".{out.name}.", suffix=".tmp")
    os.close(fd)
    return Path(name)


# A stylesheet or script an entry links: <link href="x.css">, <script src="x.js">.
_LINKED = re.compile(rb"""(?:href|src)\s*=\s*["']([^"']+\.(?:css|js))(?:[?#][^"']*)?["']""", re.I)


def linked_names(body: bytes) -> list[str]:
    """File names (lower case, directories dropped) of the stylesheets and scripts an entry links."""
    return [m.decode("utf-8", "replace").replace("\\", "/").rsplit("/", 1)[-1].lower() for m in _LINKED.findall(body)]


def assets(folder: Path, suffix: str, linked: dict[str, None] | None = None) -> str:
    """The dictionary's own CSS or JS: the files its entries link, in the order first linked.

    Packs ship alternative themes beside the one their entries link (OALECD's .origin/.new/
    .beautiful variants); those are left out. When the entries link none of the shipped files
    (a packager renamed the file the entries name), every file is kept.
    """
    files = [p for p in sorted(folder.iterdir()) if p.suffix.lower() == suffix]
    by_name = {p.name.lower(): p for p in files}
    chosen = [by_name[n] for n in (linked or {}) if n in by_name] or files
    return "\n".join(f"/* {p.name} */\n" + p.read_text(errors="replace") for p in chosen)


def load(conn: sqlite3.Connection, dict_id: int, item: dict, category: str, record: dict, expected: dict,
         folder: Path | None = None) -> dict:
    from mdict_utils.base.readmdict import MDX  # needs the project venv; imported here so norm() is importable anywhere

    folder = folder or CORPUS / item["key"]
    mdx_path = next(p for p in folder.iterdir() if p.suffix.lower() == ".mdx")
    mdx = MDX(str(mdx_path))
    header = {k.decode("utf-8", "replace"): v.decode("utf-8", "replace") for k, v in mdx.header.items()}
    entries, redirects, empty, batch_e, batch_r = 0, 0, 0, [], []
    linked: dict[str, None] = {}  # stylesheets and scripts the entries link, in first-linked order
    for raw_key, value in mdx.items():
        headword = raw_key.decode("utf-8", errors="replace").strip()  # the reader re-encodes every key as UTF-8
        body = value.strip()
        if not body:
            empty += 1
        elif body.startswith(b"@@@LINK="):
            target = body[8:].decode("utf-8", errors="replace").strip()
            batch_r.append((dict_id, headword, norm(headword), target, norm(target)))
            redirects += 1
        else:
            batch_e.append((dict_id, headword, norm(headword), zlib.compress(value, 6)))
            linked.update(dict.fromkeys(linked_names(value)))
            entries += 1
        if len(batch_e) >= 5000:
            conn.executemany("INSERT INTO entry(dict_id, headword, norm, body) VALUES (?,?,?,?)", batch_e)
            batch_e = []
        if len(batch_r) >= 5000:
            conn.executemany("INSERT INTO redirect VALUES (?,?,?,?,?)", batch_r)
            batch_r = []
    conn.executemany("INSERT INTO entry(dict_id, headword, norm, body) VALUES (?,?,?,?)", batch_e)
    conn.executemany("INSERT INTO redirect VALUES (?,?,?,?,?)", batch_r)
    conn.execute(
        "INSERT INTO dictionary VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (dict_id, item["key"], item["name"], item["full"], item.get("zh") or None, category, item["status"],
         item["latest"], record["n"], record["loc"][0]["p"], mdx_path.name, mdx._version,
         json.dumps(header, ensure_ascii=False), assets(folder, ".css", linked), assets(folder, ".js", linked)),
    )
    conn.commit()

    got = {"content_entries": entries, "redirects": redirects, "empty": empty}
    want = {k: expected[k] for k in got}
    if got != want:
        raise AssertionError(f"{item['key']}: loaded {got}, inspection counted {want}")
    return got


class Source(NamedTuple):
    """One dictionary to load: its id in the database, its recommendation, and the counts to check."""
    dict_id: int
    item: dict
    category: str
    record: dict
    expected: dict
    folder: Path


def load_shard(source: Source, shard: Path) -> tuple[dict, float]:
    """Load one dictionary into its own new database `shard` (a worker's job); counts and seconds taken."""
    t = time.time()
    with contextlib.closing(sqlite3.connect(shard)) as conn:
        conn.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)
        got = load(conn, source.dict_id, source.item, source.category, source.record, source.expected, source.folder)
    return got, time.time() - t


def append_shard(conn: sqlite3.Connection, shard: Path) -> None:
    """Append a shard's rows; entries take the next ids, in the shard's file order."""
    conn.execute("ATTACH DATABASE ? AS shard", (str(shard),))
    try:
        conn.execute("INSERT INTO main.dictionary SELECT * FROM shard.dictionary")
        conn.execute("INSERT INTO main.entry(dict_id, headword, norm, body) "
                     "SELECT dict_id, headword, norm, body FROM shard.entry ORDER BY id")
        conn.execute("INSERT INTO main.redirect SELECT * FROM shard.redirect ORDER BY rowid")
        conn.commit()
    finally:
        conn.execute("DETACH DATABASE shard")


def build(out: Path, plan: list[Source], workers: int) -> None:
    """Build layer 1 at `out` from `plan`, all or nothing: a failure leaves no file behind."""
    tmp = temp_beside(out)  # unique per build: concurrent builds never share or unlink each other's file
    shards = Path(tempfile.mkdtemp(dir=out.parent, prefix=f".{out.name}.shards."))
    try:
        with contextlib.closing(sqlite3.connect(tmp)) as conn, ProcessPoolExecutor(workers) as pool:
            conn.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)
            # Largest first, so the longest decode starts at once; appended in plan order regardless.
            size = {s.dict_id: sum(p.stat().st_size for p in s.folder.iterdir() if p.suffix.lower() == ".mdx") for s in plan}
            order = sorted(plan, key=lambda s: -size[s.dict_id])
            futures = {s.dict_id: pool.submit(load_shard, s, shards / f"{s.dict_id}.db") for s in order}
            try:
                for source in plan:
                    got, seconds = futures[source.dict_id].result()
                    append_shard(conn, shards / f"{source.dict_id}.db")
                    (shards / f"{source.dict_id}.db").unlink()
                    print(f"{source.item['key']:11} {got['content_entries']:>8,} entries {got['redirects']:>8,} redirects  "
                          f"{seconds:5.1f}s", file=sys.stderr)
            except BaseException:
                pool.shutdown(cancel_futures=True)
                raise
            conn.executescript(INDEXES)
            conn.execute("INSERT INTO headword_fts(headword_fts) VALUES ('rebuild')")
            conn.commit()
            conn.execute("VACUUM")
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)  # a failed build leaves nothing behind; after os.replace it is already gone
        shutil.rmtree(shards, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=CORPUS / "unified.db")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    args = ap.parse_args()
    report = json.loads((CORPUS / "_inspect" / "report.json").read_text())
    dicts = {d["id"]: d for d in json.loads((ROOT / "site/data/dicts.json").read_text())}
    rec = json.loads((ROOT / "site/data/recommended.json").read_text())
    picks = [(cat["key"], item) for cat in rec["categories"] for item in cat["items"] if item["id"] is not None]
    plan = [Source(dict_id, item, category, dicts[item["id"]], report[item["key"]]["mdx"][0], CORPUS / item["key"])
            for dict_id, (category, item) in enumerate(picks, start=1)]

    t0 = time.time()
    build(args.out, plan, args.workers)
    print(f"built {args.out} ({args.out.stat().st_size / 1e9:.2f} GB) in {time.time() - t0:.0f}s", file=sys.stderr)

if __name__ == "__main__":
    main()
