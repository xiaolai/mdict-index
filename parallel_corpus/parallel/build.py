"""Build parallel_corpus/data/parallel.db from the staged records of the audited dictionaries.

    PYTHONPATH=scripts:parallel_corpus .venv/bin/python parallel_corpus/parallel/build.py [--allow-unaudited]

Dictionaries are read in priority order: parsed dictionaries (layer 2) first, then by
example density. The first dictionary to print a pair gives its representative text; every
dictionary that prints it is recorded as a source. Each record is judged by
parallel/corpus.py; rejections are counted per dictionary and reason.

A dictionary enters only if its audit (parallel_corpus/data/audit.json, parallel/audit.py)
measured precision of at least MIN_PRECISION. --allow-unaudited admits dictionaries that
have no audit yet (development builds); they are marked with a NULL precision.

Tables:
  dictionary   every candidate, included or not, with counts and why
  pair         one row per distinct pair (exact_key); `cluster` groups pairs that differ only
               in punctuation or spacing, `variants` pairs with the same English
  cluster      loose_key -> representative pair
  en_group     en_key -> how many translations the same English has
  source       pair x dictionary x headword
  pair_en/zh   full-text search (English: stemmed words; Chinese: trigrams)
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sqlite3
import sys
import uuid
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "parallel_corpus"))
from parallel.corpus import clean, clean_en, clean_zh, en_key, exact_key, judge, loose_key, to_simplified  # noqa: E402

from parallel import DATA as PARALLEL  # noqa: E402
MIN_PRECISION = 0.95

SCHEMA = """
CREATE TABLE dictionary (
  id INTEGER PRIMARY KEY,
  source_id TEXT UNIQUE NOT NULL,   -- the freemdict index id
  name TEXT NOT NULL,
  source TEXT NOT NULL,             -- layer2 | mdx
  example_order TEXT NOT NULL,      -- en-zh | zh-en: which the dictionary prints first
  alignment REAL NOT NULL,          -- probe's mean lexicon alignment in that order
  included INTEGER NOT NULL,
  why TEXT NOT NULL,                -- why it is or is not included
  precision REAL,                   -- audited precision; NULL if not audited
  records INTEGER NOT NULL,         -- staged records read
  accepted INTEGER NOT NULL,        -- records that are valid pairs
  new_pairs INTEGER NOT NULL,       -- pairs no earlier dictionary had
  rejected TEXT NOT NULL            -- JSON {reason: count}
);
CREATE TABLE cluster (id INTEGER PRIMARY KEY, loose_key TEXT UNIQUE NOT NULL, representative INTEGER NOT NULL,
                      size INTEGER NOT NULL);
CREATE TABLE en_group (id INTEGER PRIMARY KEY, en_key TEXT UNIQUE NOT NULL, size INTEGER NOT NULL);
CREATE TABLE pair (
  id INTEGER PRIMARY KEY,
  en TEXT NOT NULL,
  zh TEXT NOT NULL,                 -- as first printed
  zh_hans TEXT NOT NULL,            -- simplified characters
  kind TEXT NOT NULL,               -- sentence | phrase
  exact_key TEXT UNIQUE NOT NULL,
  cluster INTEGER NOT NULL REFERENCES cluster(id),
  en_group INTEGER NOT NULL REFERENCES en_group(id),  -- pairs with the same English (translation variants)
  variants INTEGER NOT NULL,        -- how many pairs share en_group
  sources INTEGER NOT NULL          -- how many dictionaries print it
);
CREATE TABLE source (pair_id INTEGER NOT NULL, dictionary_id INTEGER NOT NULL, headword TEXT NOT NULL,
                     PRIMARY KEY (pair_id, dictionary_id, headword)) WITHOUT ROWID;
"""
INDEXES = """
CREATE INDEX pair_cluster ON pair(cluster);
CREATE INDEX pair_en_group ON pair(en_group);
CREATE INDEX source_dictionary ON source(dictionary_id);
CREATE VIRTUAL TABLE pair_en USING fts5(en, content='pair', content_rowid='id', tokenize='porter unicode61');
CREATE VIRTUAL TABLE pair_zh USING fts5(zh_hans, content='pair', content_rowid='id', tokenize='trigram');
INSERT INTO pair_en(pair_en) VALUES ('rebuild');
INSERT INTO pair_zh(pair_zh) VALUES ('rebuild');
"""


def admission(choice: dict, audit: dict, allow_unaudited: bool) -> tuple[bool, str, float | None]:
    """Whether a kept dictionary enters the corpus, why, and its audited precision."""
    result = audit.get(choice["id"])
    if result is None:
        return allow_unaudited, "not audited" + (" (admitted: --allow-unaudited)" if allow_unaudited else ""), None
    p = result["precision"]
    if p < MIN_PRECISION:
        return False, f"audited precision {p:.3f} below {MIN_PRECISION}", p
    return True, f"audited precision {p:.3f}", p


def priority(choice: dict) -> tuple:
    return (choice["source"] != "layer2", -choice["pairs_per_100k_chars"], choice["id"])


def read_staged(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _key_id(con: sqlite3.Connection, table: str, key_column: str, key: str, extra: tuple = ()) -> int:
    """The id of the row with this key, inserting it (with `extra` columns) if it is new."""
    row = con.execute(f"SELECT id FROM {table} WHERE {key_column} = ?", (key,)).fetchone()
    if row:
        return row[0]
    return con.execute(f"INSERT INTO {table} VALUES (NULL, ?{', ?' * len(extra)})", (key, *extra)).lastrowid


def build(choices: list[dict], staged: Path, audit: dict, out: Path, allow_unaudited: bool = False) -> dict:
    """Build the database at out (atomically) and return summary counts.

    Deduplication runs on the database's unique indexes, so memory stays flat however many
    dictionaries are added (in-memory key tables needed 1.3 GB for 0.85 million records).
    """
    # A working file of its own, so concurrent builds never share one; a failed build leaves it for inspection.
    tmp = out.with_name(f"{out.name}.{uuid.uuid4().hex}.part")
    con = sqlite3.connect(tmp)
    try:
        summary = _fill(con, choices, staged, audit, allow_unaudited, tmp)
    finally:
        con.close()
    os.replace(tmp, out)
    return summary


def _fill(con: sqlite3.Connection, choices: list[dict], staged: Path, audit: dict, allow_unaudited: bool,
          tmp: Path) -> dict:
    """Write the whole database through con and return the summary counts."""
    con.executescript("PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF; PRAGMA cache_size = -262144;")
    con.executescript(SCHEMA)
    for dict_id, choice in enumerate(sorted((c for c in choices if c["keep"]), key=priority), 1):
        included, why, precision = admission(choice, audit, allow_unaudited)
        path = staged / f"{choice['id']}.jsonl.gz"
        if included and not path.exists():
            raise FileNotFoundError(f"{path}: {choice['name']} is admitted but was never extracted")
        records = accepted = new = 0
        rejected: Counter = Counter()
        for r in read_staged(path) if included else ():
            records += 1
            v = judge(r["en"], r["zh"])
            if not v.ok:
                rejected[v.reason] += 1
                continue
            accepted += 1
            en, zh = clean_en(r["en"], r["zh"]), clean_zh(r["zh"])
            key = exact_key(en, zh)
            row = con.execute("SELECT id FROM pair WHERE exact_key = ?", (key,)).fetchone()
            if row:
                pid = row[0]
            else:
                new += 1
                pid = con.execute("SELECT coalesce(max(id), 0) + 1 FROM pair").fetchone()[0]
                cluster = _key_id(con, "cluster", "loose_key", loose_key(en, zh), (pid, 0))
                group = _key_id(con, "en_group", "en_key", en_key(en), (0,))
                con.execute("INSERT INTO pair VALUES (?,?,?,?,?,?,?,?,0,0)",
                            (pid, en, zh, to_simplified(zh), v.kind, key, cluster, group))
            con.execute("INSERT OR IGNORE INTO source VALUES (?,?,?)", (pid, dict_id, clean(r.get("hw", ""))))
        con.execute("INSERT INTO dictionary VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (dict_id, choice["id"], choice["name"], "layer2" if choice["source"] == "layer2" else "mdx",
                     choice["order"], choice["alignment"],
                     int(included), why, precision, records, accepted, new,
                     json.dumps(dict(rejected.most_common()), ensure_ascii=False)))
    con.executescript(INDEXES)
    con.executescript("""
        UPDATE cluster SET size = (SELECT count(*) FROM pair WHERE pair.cluster = cluster.id);
        UPDATE en_group SET size = (SELECT count(*) FROM pair WHERE pair.en_group = en_group.id);
        UPDATE pair SET variants = (SELECT size FROM en_group WHERE en_group.id = pair.en_group),
                        sources = (SELECT count(DISTINCT dictionary_id) FROM source WHERE source.pair_id = pair.id);
    """)
    con.commit()
    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError(f"{tmp}: integrity check failed")
    summary = {name: con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
               for name, table in [("pairs", "pair"), ("clusters", "cluster"), ("en_groups", "en_group"),
                                   ("sources", "source")]}
    con.execute("VACUUM")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selected", type=Path, default=PARALLEL / "selected.json")
    ap.add_argument("--audit", type=Path, default=PARALLEL / "audit.json")
    ap.add_argument("--out", type=Path, default=PARALLEL / "parallel.db")
    ap.add_argument("--allow-unaudited", action="store_true")
    args = ap.parse_args()
    audit = json.loads(args.audit.read_text()) if args.audit.exists() else {}
    summary = build(json.loads(args.selected.read_text()), PARALLEL / "staged", audit, args.out, args.allow_unaudited)
    print(json.dumps(summary), "->", args.out, file=sys.stderr)


if __name__ == "__main__":
    main()
