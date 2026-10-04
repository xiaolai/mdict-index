"""Layer 3: every audio/image/stylesheet resource of every dictionary, stored once.

    .venv/bin/python scripts/build_resources.py [--db corpus/unified.db] [--out corpus/resources.db]

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
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
import sqlite3
import sys
import time
import unicodedata
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
    from mdict_utils.base.readmdict import MDD  # needs the project venv

    stats = {"files": 0, "keys": 0, "loaded": 0, "duplicate_paths": 0, "bytes": 0, "new_blobs": 0}
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
            before = conn.total_changes
            conn.execute("INSERT OR IGNORE INTO blob VALUES (?,?,?)", (digest, len(data), data))
            stats["new_blobs"] += conn.total_changes - before
        if seen != expected:
            raise AssertionError(f"{path.name}: read {seen} of {expected} resources")
        stats["files"] += 1
        stats["keys"] += seen
        conn.commit()
    return stats


def build(db: Path, out: Path, corpus: Path = CORPUS) -> list[tuple[str, dict]]:
    dicts = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = dicts.execute("SELECT id, key FROM dictionary ORDER BY id").fetchall()
    dicts.close()
    tmp = temp_beside(out)  # unique per build: concurrent builds never share or unlink each other's file
    try:
        with contextlib.closing(sqlite3.connect(tmp)) as conn:
            conn.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)
            report = []
            for dict_id, key in rows:
                t = time.time()
                stats = load_dictionary(conn, dict_id, mdd_files(corpus / key))
                if stats["loaded"] + stats["duplicate_paths"] != stats["keys"]:
                    raise AssertionError(f"{key}: {stats}")
                report.append((key, stats))
                print(f"{key:11} {stats['files']} mdd  {stats['keys']:>8,} resources  {stats['bytes'] / 1e9:6.2f} GB  "
                      f"{stats['new_blobs']:>8,} new blobs  {time.time() - t:5.0f}s", file=sys.stderr)
            conn.execute("CREATE INDEX resource_hash ON resource(hash)")
            conn.commit()
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)  # a failed build leaves nothing behind; after os.replace it is already gone
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=CORPUS / "unified.db")
    ap.add_argument("--out", type=Path, default=CORPUS / "resources.db")
    args = ap.parse_args()
    t0 = time.time()
    report = build(args.db, args.out)
    total = sum(s["bytes"] for _, s in report)
    stored = args.out.stat().st_size
    print(f"built {args.out}: {total / 1e9:.2f} GB of resources stored in {stored / 1e9:.2f} GB "
          f"in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
