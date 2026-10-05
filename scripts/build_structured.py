"""Layer 2: parse every dictionary's entries into structured tables.

    .venv/bin/python scripts/build_structured.py [--db corpus/unified.db] [--only key,key] [--merge-only]

Runs each registered parser (scripts/structured/parsers) over every content
entry of its dictionary, in parallel, and writes into the unified database:

  s_entry    entry_id -> headword, homograph, pos, etymology, forms
  s_pron     pronunciations (region, IPA, audio reference)
  s_sense    senses (kind, pos, number, phrase, labels, definition, definition_zh)
  s_example  examples / collocations / quotations per sense
  zh_term    Chinese gloss terms -> sense, the Chinese-to-English index
  zh_fts     the distinct terms in a trigram index: "contains" queries without scanning zh_term
  sense_fts  full-text index over English definitions ("words meaning ...")

The build fails if any parser raises, produces a contract problem, or covers
less of its dictionary than its declared MIN_COVERAGE. Re-running replaces
the layer-2 tables; layer 1 is untouched.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import sqlite3
import struct
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_unified import CORPUS, temp_beside  # noqa: E402
from structured.model import Entry, covered, problems, stub_problem  # noqa: E402

SCHEMA = """
DROP TABLE IF EXISTS sense_fts;
DROP TABLE IF EXISTS zh_fts;
DROP TABLE IF EXISTS zh_term;
DROP TABLE IF EXISTS s_example;
DROP TABLE IF EXISTS s_sense;
DROP TABLE IF EXISTS s_pron;
DROP TABLE IF EXISTS s_entry;
DROP TABLE IF EXISTS s_coverage;
CREATE TABLE s_entry (
  entry_id INTEGER PRIMARY KEY REFERENCES entry(id),
  dict_id INTEGER NOT NULL,
  headword TEXT NOT NULL,
  homograph TEXT NOT NULL,
  pos TEXT NOT NULL,          -- JSON list
  etymology TEXT NOT NULL,
  forms TEXT NOT NULL,        -- JSON list
  extra TEXT NOT NULL,        -- JSON object, parser-specific
  stub TEXT NOT NULL,         -- '' for a content record, else why it carries no content (model.STUB_KINDS)
  part_of TEXT NOT NULL,      -- for popups: the headword whose entry this record belongs to
  merged_into INTEGER         -- for popups: the entry_id it was folded into (NULL until merged, or if no match)
);
CREATE TABLE s_pron (entry_id INTEGER NOT NULL, ord INTEGER NOT NULL, region TEXT NOT NULL, ipa TEXT NOT NULL,
                     audio TEXT NOT NULL, note TEXT NOT NULL);
CREATE TABLE s_sense (
  id INTEGER PRIMARY KEY,
  entry_id INTEGER NOT NULL,
  dict_id INTEGER NOT NULL,
  ord INTEGER NOT NULL,
  kind TEXT NOT NULL,
  pos TEXT NOT NULL,
  number TEXT NOT NULL,
  phrase TEXT NOT NULL,
  labels TEXT NOT NULL,       -- JSON list
  definition TEXT NOT NULL,
  definition_zh TEXT NOT NULL
);
CREATE TABLE s_example (sense_id INTEGER NOT NULL, ord INTEGER NOT NULL, kind TEXT NOT NULL,
                        text TEXT NOT NULL, text_zh TEXT NOT NULL, source TEXT NOT NULL, date TEXT NOT NULL,
                        labels TEXT NOT NULL);  -- JSON list
CREATE TABLE s_coverage (dict_id INTEGER PRIMARY KEY, covers TEXT NOT NULL, entries INTEGER NOT NULL,
                         stubs INTEGER NOT NULL, covered INTEGER NOT NULL, min_coverage REAL NOT NULL);
"""
# Shards only: the layer-1 records a shard was parsed from (source_fingerprint), checked before merging.
SHARD_SCHEMA = """
DROP TABLE IF EXISTS s_source;
CREATE TABLE s_source (dict_id INTEGER PRIMARY KEY, key TEXT NOT NULL, fingerprint TEXT NOT NULL);
"""
INDEXES = """
CREATE INDEX s_entry_dict ON s_entry(dict_id);
CREATE INDEX s_pron_entry ON s_pron(entry_id);
CREATE INDEX s_sense_entry ON s_sense(entry_id, ord);
CREATE INDEX s_example_sense ON s_example(sense_id, ord);
CREATE TABLE zh_term (term TEXT NOT NULL, sense_id INTEGER NOT NULL);
CREATE VIRTUAL TABLE sense_fts USING fts5(definition, content='s_sense', content_rowid='id', tokenize='porter unicode61');
"""

def build_zh_index(conn: sqlite3.Connection) -> int:
    """Index zh_term: by term (exact queries), and in zh_fts, a trigram index of its distinct terms
    (queries for terms containing a string read this, not every zh_term row); how many terms."""
    conn.execute("CREATE INDEX IF NOT EXISTS zh_term_term ON zh_term(term)")
    conn.execute("DROP TABLE IF EXISTS zh_fts")
    conn.execute("CREATE VIRTUAL TABLE zh_fts USING fts5(term, tokenize='trigram')")
    conn.execute("INSERT INTO zh_fts(term) SELECT DISTINCT term FROM zh_term")
    return conn.execute("SELECT count(*) FROM zh_fts").fetchone()[0]


def build_derived(conn: sqlite3.Connection) -> dict[str, int]:
    """Everything built from layers 1 and 2 rather than parsed: the Chinese indexes."""
    return {"zh terms": build_zh_index(conn)}


def rebuild_derived(db: Path, build=build_derived) -> dict[str, int]:
    """build_derived on an existing layer 2, in one transaction: a failure midway leaves the old
    tables whole (without one, Python's sqlite3 commits each DROP and CREATE at once)."""
    with contextlib.closing(sqlite3.connect(db, autocommit=False)) as conn:
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'zh_term'").fetchone() is None:
            raise SystemExit(f"{db} has no layer 2 (zh_term): build it first")
        try:
            n = build(conn)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return n


# Chinese glosses: "（打电话时的招呼语）喂；你好" -> ["喂", "你好"]
_ZH_NOTE = re.compile(r"[（(〈【\[][^）)〉】\]]*[）)〉】\]]")
_ZH_SPLIT = re.compile(r"[；;，,、/|]+")
_CJK = re.compile(r"[㐀-鿿豈-﫿\U00020000-\U0003FFFF]")  # BMP and supplementary-plane ideographs
MAX_TERM = 16


def zh_terms(definition_zh: str) -> list[str]:
    """Chinese gloss terms of a definition: bracketed notes dropped, split on separators."""
    out = []
    for part in _ZH_SPLIT.split(_ZH_NOTE.sub(" ", definition_zh)):
        term = part.strip(" .。…～~:：\"'“”‘’")
        if term and _CJK.search(term) and len(term) <= MAX_TERM and term not in out:
            out.append(term)
    return out


def source_fingerprint(conn: sqlite3.Connection, dict_id: int, schema: str = "main") -> str:
    """SHA-256 over one dictionary's layer-1 records (id, headword, stored body) in id order.

    Taken when a shard is parsed and again when it is merged, so a shard is merged only into a
    database holding exactly the records it was parsed from. Each field is length-prefixed, so
    no two different record lists hash the same input. About 6-12 s for the OED (1 GB of bodies).
    """
    h = hashlib.sha256()
    for entry_id, headword, body in conn.execute(
            f"SELECT id, headword, body FROM {schema}.entry WHERE dict_id = ? ORDER BY id", (dict_id,)):
        hw = headword.encode("utf-8")
        h.update(struct.pack("<qQQ", entry_id, len(hw), len(body)))
        h.update(hw)
        h.update(body)
    return h.hexdigest()


def parse_dictionary(db: str, key: str, shard: str, module=None) -> dict:
    """Worker: parse one dictionary into its own shard database. Returns its report.

    `module` defaults to the registered parser for `key`; tests pass a stub.
    """
    if module is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from structured.parsers import load
        module = load(key)
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    src.execute("BEGIN")  # one read snapshot: the fingerprint and the parse see the same records
    dict_id = src.execute("SELECT id FROM dictionary WHERE key = ?", (key,)).fetchone()[0]
    out = sqlite3.connect(shard)
    out.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA + SHARD_SCHEMA)
    out.execute("INSERT INTO s_source VALUES (?,?,?)", (dict_id, key, source_fingerprint(src, dict_id)))
    n = cov = stubs = 0
    errors: list[str] = []
    bad: list[str] = []
    sense_id = 0
    for entry_id, headword, body in src.execute("SELECT id, headword, body FROM entry WHERE dict_id = ? ORDER BY id", (dict_id,)):
        n += 1
        try:
            e = module.parse(headword, zlib.decompress(body).decode("utf-8", "replace"))
            if not isinstance(e, Entry):
                raise TypeError(f"parse() returned {type(e).__name__}, not Entry")
        except Exception as exc:  # every failure is reported; any one fails the build
            errors.append(f"entry {entry_id} {headword!r}: {type(exc).__name__}: {exc}")
            continue
        printed = headword in getattr(module, "PRINTED_MARKUP", frozenset())
        if (p := problems(e, printed_markup=printed) + [q for q in [stub_problem(e, module.COVERS)] if q]):
            bad.append(f"entry {entry_id} {headword!r}: {p[0]}")
            continue
        if e.stub:
            stubs += 1
        else:
            cov += covered(e, module.COVERS)
        out.execute("INSERT INTO s_entry VALUES (?,?,?,?,?,?,?,?,?,?,NULL)", (
            entry_id, dict_id, e.headword, e.homograph, json.dumps(list(e.pos), ensure_ascii=False), e.etymology,
            json.dumps(list(e.forms), ensure_ascii=False), json.dumps(e.extra, ensure_ascii=False), e.stub, e.part_of))
        out.executemany("INSERT INTO s_pron VALUES (?,?,?,?,?,?)",
                        [(entry_id, i, p.region, p.ipa, p.audio, p.note) for i, p in enumerate(e.prons)])
        for i, s in enumerate(e.senses):
            sense_id += 1
            out.execute("INSERT INTO s_sense VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                sense_id, entry_id, dict_id, i, s.kind, s.pos, s.number, s.phrase,
                json.dumps(list(s.labels), ensure_ascii=False), s.definition, s.definition_zh))
            out.executemany("INSERT INTO s_example VALUES (?,?,?,?,?,?,?,?)",
                            [(sense_id, j, x.kind, x.text, x.text_zh, x.source, x.date, json.dumps(list(x.labels), ensure_ascii=False))
                             for j, x in enumerate(s.examples)])
    out.execute("INSERT INTO s_coverage VALUES (?,?,?,?,?,?)", (dict_id, module.COVERS, n, stubs, cov, module.MIN_COVERAGE))
    out.commit()
    out.close()
    src.close()
    content = n - stubs
    # Coverage is over content records: stubs are excused, and a stub that carries content is a problem above.
    # Unrounded: the MIN_COVERAGE gate compares it (0.98999 must not pass 0.99); round only for display.
    return {"key": key, "entries": n, "stubs": stubs, "covered": cov,
            "coverage": cov / content if content else 0.0,
            "min_coverage": module.MIN_COVERAGE, "exceptions": errors, "problems": bad}


def failures(report: dict) -> list[str]:
    out = []
    if report["exceptions"]:
        out.append(f"{report['key']}: {len(report['exceptions'])} exceptions, e.g. {report['exceptions'][0]}")
    if report["problems"]:
        out.append(f"{report['key']}: {len(report['problems'])} contract problems, e.g. {report['problems'][0]}")
    if report["coverage"] < report["min_coverage"]:
        out.append(f"{report['key']}: coverage {report['coverage']:.6f} < MIN_COVERAGE {report['min_coverage']}")
    return out


# The main entry a popup belongs to. CROSS JOIN fixes the join order so SQLite starts from the
# headword index (entry_norm): left to itself it walks the whole dictionary's s_entry rows for
# every popup, which for the OED is ~81k popups x ~576k rows. test_popup_lookup_uses_the_headword_index
# holds the plan in place.
POPUP_TARGET = (
    "SELECT s.entry_id, s.etymology, s.forms FROM entry e CROSS JOIN s_entry s ON s.entry_id = e.id "
    "WHERE e.norm = ? AND e.dict_id = ? AND s.stub = '' ORDER BY e.id LIMIT 1"
)


def _compact(key: str) -> str:
    return "".join(ch for ch in key if ch.isalnum())


def merge_popups(conn: sqlite3.Connection) -> int:
    """Fold popup records into the entry they belong to (same dictionary, headword = part_of).

    The main entry keeps its own etymology when it has one; forms are unioned; the popup's
    senses are re-attached after the main entry's own. A popup whose main entry cannot be
    found stays where it is (and is counted, so a silent mismatch shows in the build log).
    Returns the number of popups merged. Does not commit: it runs inside merge()'s transaction.
    """
    from build_unified import norm
    merged = unmatched = 0
    loose: dict[int, dict[str, int]] = {}  # per dictionary: compact headword -> first content entry
    popups = conn.execute("SELECT entry_id, dict_id, part_of, etymology, forms FROM s_entry "
                          "WHERE stub = 'popup' AND merged_into IS NULL").fetchall()
    for popup_id, dict_id, part_of, etymology, forms in popups:
        main = conn.execute(POPUP_TARGET, (norm(part_of), dict_id)).fetchone()
        if main is None:
            # Popups name their entry loosely: "cross examine" for "cross-examine", "a s level" for
            # "A/S level". Retry with punctuation and spaces removed, within the same dictionary.
            if dict_id not in loose:
                loose[dict_id] = {}
                for entry_id, n in conn.execute(
                        "SELECT s.entry_id, e.norm FROM s_entry s JOIN entry e ON e.id = s.entry_id "
                        "WHERE s.dict_id = ? AND s.stub = '' ORDER BY s.entry_id", (dict_id,)):
                    loose[dict_id].setdefault(_compact(n), entry_id)
            target = loose[dict_id].get(_compact(norm(part_of)))
            if target is not None:
                main = conn.execute("SELECT entry_id, etymology, forms FROM s_entry WHERE entry_id = ?", (target,)).fetchone()
        if main is None:
            unmatched += 1
            continue
        main_id, main_etym, main_forms = main
        union = list(dict.fromkeys(json.loads(main_forms) + json.loads(forms)))
        conn.execute("UPDATE s_entry SET etymology = ?, forms = ? WHERE entry_id = ?",
                     (main_etym or etymology, json.dumps(union, ensure_ascii=False), main_id))
        base = conn.execute("SELECT coalesce(max(ord) + 1, 0) FROM s_sense WHERE entry_id = ?", (main_id,)).fetchone()[0]
        conn.execute("UPDATE s_sense SET entry_id = ?, ord = ord + ? WHERE entry_id = ?", (main_id, base, popup_id))
        conn.execute("UPDATE s_entry SET merged_into = ? WHERE entry_id = ?", (main_id, popup_id))
        merged += 1
    if popups:
        print(f"popups: {merged} merged into their entries, {unmatched} without a matching entry", file=sys.stderr)
    return merged


def shard_dir(db: Path) -> Path:
    """Where `db`'s per-dictionary shards are cached: one folder per database file, named by the
    file's full name (u.db and u.sqlite in one folder are two databases), so two databases never
    overwrite or merge each other's shards."""
    return db.parent / "_structured" / db.name


# The default database's shards: the parsed dictionaries every later stage reads (inventories,
# parallel corpus). Readers import this rather than spell the path, so they move with the writer.
STRUCTURED = shard_dir(CORPUS / "unified.db")


def _union(db: Path, shards: list[Path], staging: Path) -> None:
    """Copy every shard into `staging`, renumbering senses, and check each shard belongs to `db`.

    Raises SystemExit (or sqlite3.DatabaseError for a file that is not a shard) before `db` is touched.
    """
    with contextlib.closing(sqlite3.connect(staging)) as st:
        st.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)
        st.execute("ATTACH DATABASE ? AS u", (str(db),))
        ids = dict(st.execute("SELECT key, id FROM u.dictionary"))
        wrong: dict[str, str] = {}  # shard key -> why it is refused
        offset = 0
        for shard in shards:
            st.execute("ATTACH DATABASE ? AS sh", (str(shard),))
            # Provenance: the shard was parsed from exactly this database's records of this dictionary.
            # Shards from before fingerprints have no s_source and are refused: they cannot show their source.
            dict_id = ids.get(shard.stem)
            has_source = st.execute("SELECT count(*) FROM sh.sqlite_master WHERE name = 's_source'").fetchone()[0]
            if not has_source:
                wrong[shard.stem] = f"{shard.name} (no source fingerprint: parsed before fingerprints were recorded)"
            else:
                source = st.execute("SELECT dict_id, key, fingerprint FROM sh.s_source").fetchall()
                cov = st.execute("SELECT dict_id, entries FROM sh.s_coverage").fetchall()
                n = st.execute("SELECT count(*) FROM u.entry WHERE dict_id = ?", (dict_id,)).fetchone()[0]
                strays = st.execute("SELECT count(*) FROM sh.s_entry s LEFT JOIN u.entry e ON e.id = s.entry_id "
                                    "AND e.dict_id = s.dict_id WHERE e.id IS NULL OR s.dict_id != ?", (dict_id,)).fetchone()[0]
                expected = [(dict_id, shard.stem, source_fingerprint(st, dict_id, "u"))] if dict_id is not None else None
                if source != expected or cov != [(dict_id, n)] or strays:
                    wrong[shard.stem] = (f"{shard.name} (not parsed from {shard.stem}'s current records in {db.name}: "
                                         f"fingerprint {'matches' if source == expected else 'differs'}, "
                                         f"coverage rows {cov}, {strays} stray records)")
            st.execute("INSERT INTO s_entry SELECT * FROM sh.s_entry")
            st.execute("INSERT INTO s_pron SELECT * FROM sh.s_pron")
            st.execute("INSERT INTO s_sense SELECT id + ?, entry_id, dict_id, ord, kind, pos, number, phrase, labels, definition, definition_zh FROM sh.s_sense", (offset,))
            st.execute("INSERT INTO s_example SELECT sense_id + ?, ord, kind, text, text_zh, source, date, labels FROM sh.s_example", (offset,))
            st.execute("INSERT INTO s_coverage SELECT * FROM sh.s_coverage")
            offset = st.execute("SELECT coalesce(max(id), 0) FROM s_sense").fetchone()[0]
            st.commit()
            st.execute("DETACH DATABASE sh")
        if wrong:
            raise SystemExit(f"shards not built from {db}: {'; '.join(wrong.values())}; "
                             f"re-parse them (--only {','.join(wrong)}, without --merge-only)")


def merge(db: Path, shards: list[Path]) -> None:
    """Replace layer 2 in `db` with the union of `shards`, all or nothing.

    The shards are first copied and checked in a staging file beside `db`; only then is layer 2
    replaced, in one transaction, so a bad shard or a failure midway leaves the old layer 2 intact.
    """
    staging = temp_beside(db)
    try:
        _union(db, shards, staging)
        with contextlib.closing(sqlite3.connect(db, autocommit=False)) as conn:
            conn.execute("PRAGMA journal_mode=DELETE")  # a rollback journal: the transaction below is undoable
            try:
                conn.executescript(SCHEMA)  # with autocommit=False, executescript does not commit
                # Attached only now: SCHEMA's unqualified DROPs would otherwise find the staging tables.
                conn.execute("ATTACH DATABASE ? AS st", (str(staging),))
                for table in ("s_entry", "s_pron", "s_sense", "s_example", "s_coverage"):
                    conn.execute(f"INSERT INTO main.{table} SELECT * FROM st.{table}")
                conn.executescript(INDEXES)
                merge_popups(conn)
                rows = conn.execute("SELECT id, definition_zh FROM s_sense WHERE definition_zh != ''")
                conn.executemany("INSERT INTO zh_term VALUES (?,?)", ((t, sid) for sid, zh in rows for t in zh_terms(zh)))
                build_derived(conn)
                conn.execute("INSERT INTO sense_fts(sense_fts) VALUES ('rebuild')")
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
    finally:
        staging.unlink(missing_ok=True)


def build(db: Path, keys: list[str], all_keys: list[str], workers: int) -> list[dict]:
    """Parse `keys` into shards, then merge the shards of *all* registered parsers.

    Rebuilding a subset (--only) must not drop the other dictionaries' layer 2,
    so the merge always takes every registered parser's shard and fails if one
    has never been built. A shard is parsed into a temporary file and replaces the
    cached one as soon as it passes its own gate, so the cache only ever holds shards
    that passed, and a run stopped or failed midway keeps the dictionaries it finished
    (layer 2 of the large ones takes hours). The merge runs only when every requested
    dictionary passed.
    """
    shards_at = shard_dir(db)
    shards_at.mkdir(parents=True, exist_ok=True)
    reports = []
    fresh = {k: temp_beside(shards_at / f"{k}.db") for k in keys}
    try:
        with ProcessPoolExecutor(workers) as pool:
            futures = {pool.submit(parse_dictionary, str(db), k, str(fresh[k])): k for k in keys}
            for fut in as_completed(futures):
                r = fut.result()
                reports.append(r)
                if not failures(r):
                    os.replace(fresh[r["key"]], shards_at / f"{r['key']}.db")
                state = "FAIL" if failures(r) else "ok  "
                print(f"{state} {r['key']:11} {r['entries']:>8,} records  {r['stubs']:>8,} stubs  "
                      f"content coverage {r['coverage']:.4f} (min {r['min_coverage']})", file=sys.stderr)
        problems_found = [f for r in reports for f in failures(r)]
        if problems_found:
            raise SystemExit("layer 2 failed:\n  " + "\n  ".join(problems_found))
    finally:
        for tmp in fresh.values():
            tmp.unlink(missing_ok=True)
    shards = [shards_at / f"{k}.db" for k in sorted(all_keys)]
    missing = [s.stem for s in shards if not s.exists()]
    if missing:
        raise SystemExit(f"no layer-2 shard for {missing}; run without --only first")
    merge(db, shards)
    return reports


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from structured.parsers import registry
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=CORPUS / "unified.db")
    ap.add_argument("--only", default="")
    ap.add_argument("--merge-only", action="store_true", help="re-merge existing shards without parsing (e.g. after an interrupted merge)")
    ap.add_argument("--derived-only", action="store_true",
                    help="only (re)build what is derived from layers 1 and 2 (the Chinese indexes)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    args = ap.parse_args()
    if args.derived_only:
        counts = rebuild_derived(args.db)
        print("derived: " + ", ".join(f"{k} {v:,}" for k, v in counts.items()), file=sys.stderr)
        return
    all_keys = sorted(registry())
    requested = set(filter(None, args.only.split(",")))
    if unknown := sorted(requested - set(all_keys)):
        raise SystemExit(f"--only: no parser for {unknown}; registered: {', '.join(all_keys)}")
    keys = [k for k in all_keys if k in requested] if requested else all_keys
    if args.merge_only:
        keys = []
    t0 = time.time()
    build(args.db, keys, all_keys, args.workers)
    print(f"layer 2 built for {len(keys)} dictionaries in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
