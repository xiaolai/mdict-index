"""Layer 3: every audio/image/stylesheet resource of every dictionary, stored once.

    .venv/bin/python scripts/build_resources.py [--db corpus/unified.db] [--out corpus/resources.db] [--workers N]

Reads each dictionary's .mdd files (corpus/<key>/*.mdd, including split
volumes like X.1.mdd) into a content-addressed store:

  blob      sha256 -> bytes          identical files (LDOCE and its bilingual
                                     edition ship the same audio) stored once
  resource  (dict_id, norm) -> sha256, plus the path as written in the .mdd

Entries reference resources inconsistently ("\\img\\x.jpg", "/img/x.jpg",
"sound://x.mp3", different letter case) and MDict matches them loosely, so
lookups go through norm_key() (a literal path; serve_unified drops a
reference's scheme first). A separate file from unified.db: it is ~20 GB
and changes on a different schedule; readers ATTACH it.

Every .mdd key must be loaded (or be a case/slash duplicate of one already
loaded in the same dictionary: the first in file order wins); otherwise the
build fails. No blob is stored without a resource pointing at it.

Each dictionary is read by its own worker process into a shard file, its blobs appended in
file order. The main process then writes every shard's blobs into `blob` in hash order, a
merge of the shards' sorted hash indexes: `blob` is keyed by a random SHA-256, and inserting
in arrival order lands each row at a random place in a table of millions, which slowed a
one-process build to a crawl as the table grew.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import heapq
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_unified import CORPUS, temp_beside  # noqa: E402

SCHEMA = """
CREATE TABLE blob (hash TEXT PRIMARY KEY, size INTEGER NOT NULL, data BLOB NOT NULL) WITHOUT ROWID;
CREATE TABLE resource (
  dict_id INTEGER NOT NULL,
  norm TEXT NOT NULL,
  path TEXT NOT NULL,     -- as written in the .mdd
  hash TEXT NOT NULL REFERENCES blob(hash),
  PRIMARY KEY (dict_id, norm)
) WITHOUT ROWID;
"""
# A worker's shard: resources as in SCHEMA; blobs appended in arrival order (unique by
# construction), with a hash index for the merge to read them back in hash order.
SHARD_SCHEMA = """
CREATE TABLE resource (dict_id INTEGER NOT NULL, norm TEXT NOT NULL, path TEXT NOT NULL, hash TEXT NOT NULL,
  PRIMARY KEY (dict_id, norm)) WITHOUT ROWID;
CREATE TABLE blob (hash TEXT NOT NULL, size INTEGER NOT NULL, data BLOB NOT NULL);
"""
SCHEMES = ("sound://", "file://", "mdd://")


def norm_key(path: str) -> str:
    """Canonical form of a resource path taken literally (an .mdd key, or a URL path already
    percent-decoded): "\\" -> "/", leading slashes and "./" dropped, NFC, lower case.

    Nothing in it is URL syntax: "#", "?" and "%" are ordinary filename characters here.
    """
    path = unicodedata.normalize("NFC", path.strip()).replace("\\", "/")
    while path.startswith(("./", "/")):
        path = path[2:] if path.startswith("./") else path[1:]
    return path.lower()


def mdd_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.suffix.lower() == ".mdd")


def load_dictionary(conn: sqlite3.Connection, dict_id: int, files: list[Path]) -> dict:
    """Read one dictionary's .mdd files into a shard (SHARD_SCHEMA); each distinct file's bytes once."""
    from mdict_utils.base.readmdict import MDD  # needs the project venv

    stats = {"files": 0, "keys": 0, "loaded": 0, "duplicate_paths": 0, "bytes": 0}
    stored: set[str] = set()
    for path in files:
        mdd = MDD(str(path))
        expected = len(mdd)
        seen = 0
        for raw_key, data in mdd.items():
            seen += 1
            key = raw_key.decode("utf-8", errors="replace") if isinstance(raw_key, bytes) else str(raw_key)
            digest = hashlib.sha256(data).hexdigest()
            # A path that differs from an earlier one only by case or slashes is skipped: the first
            # in file order wins. Its bytes are stored only if the path is kept, so no blob is orphaned.
            before = conn.total_changes
            conn.execute("INSERT OR IGNORE INTO resource VALUES (?,?,?,?)", (dict_id, norm_key(key), key, digest))
            if conn.total_changes == before:
                stats["duplicate_paths"] += 1
                continue
            stats["loaded"] += 1
            stats["bytes"] += len(data)
            if digest not in stored:
                stored.add(digest)
                conn.execute("INSERT INTO blob VALUES (?,?,?)", (digest, len(data), data))
        if seen != expected:
            raise AssertionError(f"{path.name}: read {seen} of {expected} resources")
        stats["files"] += 1
        stats["keys"] += seen
    conn.execute("CREATE UNIQUE INDEX blob_hash ON blob(hash)")
    conn.commit()
    return stats


def load_shard(dict_id: int, files: list[Path], shard: Path) -> tuple[dict, float]:
    """A worker's job: one dictionary into its own new shard file; its counts and the seconds taken."""
    t = time.time()
    with contextlib.closing(sqlite3.connect(shard)) as conn:
        conn.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SHARD_SCHEMA)
        stats = load_dictionary(conn, dict_id, files)
    return stats, time.time() - t


def merge_blobs(conn: sqlite3.Connection, shards: list[Path]) -> list[int]:
    """Write every shard's blobs into `blob` in hash order, each hash once; how many each shard added.

    A file several dictionaries ship counts as new for the first shard listed, as in a build that
    loads the dictionaries one after another.
    """
    readers = [contextlib.closing(sqlite3.connect(f"file:{s}?mode=ro", uri=True)) for s in shards]
    new = [0] * len(shards)
    with contextlib.ExitStack() as stack:
        def tagged(i: int, reader):  # i bound per call: a generator expression would see only the last i
            for h, size, data in stack.enter_context(reader).execute("SELECT hash, size, data FROM blob ORDER BY hash"):
                yield h, i, size, data

        # (hash, shard index, ...): ties on a hash come out in shard order, so the first shard's copy wins.
        rows = heapq.merge(*(tagged(i, r) for i, r in enumerate(readers)))

        def first_of_each_hash():
            last = None
            for h, i, size, data in rows:
                if h != last:
                    last = h
                    new[i] += 1
                    yield h, size, data

        conn.executemany("INSERT INTO blob VALUES (?,?,?)", first_of_each_hash())
    conn.commit()
    return new


def build(db: Path, out: Path, corpus: Path = CORPUS, workers: int = max(1, (os.cpu_count() or 2) - 2)) -> list[tuple[str, dict]]:
    dicts = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = dicts.execute("SELECT id, key FROM dictionary ORDER BY id").fetchall()
    dicts.close()
    tmp = temp_beside(out)  # unique per build: concurrent builds never share or unlink each other's file
    shard_dir = Path(tempfile.mkdtemp(dir=out.parent, prefix=f".{out.name}.shards."))
    shards = [shard_dir / f"{dict_id}.db" for dict_id, _ in rows]
    try:
        files = {dict_id: mdd_files(corpus / key) for dict_id, key in rows}
        with ProcessPoolExecutor(workers) as pool:
            # Largest first, so the longest read starts at once.
            order = sorted(range(len(rows)), key=lambda n: -sum(p.stat().st_size for p in files[rows[n][0]]))
            futures = {n: pool.submit(load_shard, rows[n][0], files[rows[n][0]], shards[n]) for n in order}
            try:
                results = [futures[n].result() for n in range(len(rows))]
            except BaseException:
                pool.shutdown(cancel_futures=True)
                raise
        report = []
        for (dict_id, key), (stats, _) in zip(rows, results):
            if stats["loaded"] + stats["duplicate_paths"] != stats["keys"]:
                raise AssertionError(f"{key}: {stats}")
        with contextlib.closing(sqlite3.connect(tmp)) as conn:
            conn.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)
            for shard in shards:  # in dictionary order, each sorted by norm: appended at the end of the table
                with contextlib.closing(sqlite3.connect(f"file:{shard}?mode=ro", uri=True)) as src:
                    conn.executemany("INSERT INTO resource VALUES (?,?,?,?)",
                                     src.execute("SELECT dict_id, norm, path, hash FROM resource ORDER BY dict_id, norm"))
            conn.commit()
            t = time.time()
            new = merge_blobs(conn, shards)
            for (dict_id, key), (stats, seconds), n in zip(rows, results, new):
                stats = {**stats, "new_blobs": n}
                report.append((key, stats))
                print(f"{key:11} {stats['files']} mdd  {stats['keys']:>8,} resources  {stats['bytes'] / 1e9:6.2f} GB  "
                      f"{stats['new_blobs']:>8,} new blobs  {seconds:5.0f}s", file=sys.stderr)
            print(f"blobs merged in hash order in {time.time() - t:.0f}s", file=sys.stderr)
            conn.execute("CREATE INDEX resource_hash ON resource(hash)")
            conn.commit()
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)  # a failed build leaves nothing behind; after os.replace it is already gone
        shutil.rmtree(shard_dir, ignore_errors=True)
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=CORPUS / "unified.db")
    ap.add_argument("--out", type=Path, default=CORPUS / "resources.db")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    args = ap.parse_args()
    t0 = time.time()
    report = build(args.db, args.out, workers=args.workers)
    total = sum(s["bytes"] for _, s in report)
    stored = args.out.stat().st_size
    print(f"built {args.out}: {total / 1e9:.2f} GB of resources stored in {stored / 1e9:.2f} GB "
          f"in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
