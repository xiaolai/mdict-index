"""Developer tool for writing parsers against the real corpus (needs corpus/unified.db).

    .venv/bin/python scripts/structured/devtool.py sample KEY [--word take] [--n 3] [--random]
    .venv/bin/python scripts/structured/devtool.py coverage KEY [--limit N] [--show 5]

sample    prints raw entry HTML (pretty-printed) to study a dictionary's structure
coverage  runs KEY's parser over its entries: exceptions, contract problems,
          coverage against MIN_COVERAGE, field fill rates, and uncovered examples
"""
from __future__ import annotations

import argparse
import contextlib
import json
import random
import sqlite3
import sys
import time
import zlib
from collections import Counter
from pathlib import Path

# Run as a script, this file's own folder would be sys.path[0], and structured/markup.py (once html.py) would
# shadow the standard library's html module for every parser. Replace it with scripts/ -- only then: imported
# as structured.devtool, sys.path[0] belongs to the importer (a test runner's top-level folder, say).
_HERE = Path(__file__).resolve().parent
if sys.path and Path(sys.path[0] or ".").resolve() == _HERE:
    sys.path[0] = str(_HERE.parent)
from build_unified import CORPUS, norm  # noqa: E402
from structured.model import Entry, covered, problems, stub_problem  # noqa: E402
from structured.parsers import load  # noqa: E402

DB = CORPUS / "unified.db"


def connect() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def rows(conn, key: str, limit: int | None = None, seed: int | None = None):
    """(id, headword, body) of `key`'s entries: the first `limit` in id order, or with `seed` a random
    `limit` of them. limit=None means all; 0 means none."""
    if limit is not None and limit < 0:
        raise ValueError(f"limit must be >= 0 or None, not {limit}")
    dict_id = conn.execute("SELECT id FROM dictionary WHERE key = ?", (key,)).fetchone()[0]
    if seed is None:
        sql = "SELECT id, headword, body FROM entry WHERE dict_id = ? ORDER BY id" + ("" if limit is None else f" LIMIT {int(limit)}")
        yield from conn.execute(sql, (dict_id,))
        return
    ids = [r[0] for r in conn.execute("SELECT id FROM entry WHERE dict_id = ?", (dict_id,))]
    random.Random(seed).shuffle(ids)
    for eid in ids[:limit]:
        yield conn.execute("SELECT id, headword, body FROM entry WHERE id = ?", (eid,)).fetchone()


def run_coverage(key: str, limit: int | None = None, seed: int | None = None, show: int = 0) -> dict:
    module = load(key)
    with contextlib.closing(connect()) as conn:
        return _coverage(module, key, conn, limit, seed, show)


def _coverage(module, key: str, conn, limit, seed, show) -> dict:
    n = cov = problem_entries = 0
    errors, bad, uncovered = [], Counter(), []  # bad: violations by kind; problem_entries: entries with any
    fill, stubs = Counter(), Counter()
    t0 = time.time()
    for eid, headword, body in rows(conn, key, limit, seed):
        n += 1
        html = zlib.decompress(body).decode("utf-8", "replace")
        try:
            entry = module.parse(headword, html)
            if not isinstance(entry, Entry):
                raise TypeError(f"parse() returned {type(entry).__name__}, not Entry")
        except Exception as e:  # a parser must never raise; every one is reported
            errors.append(f"{eid} {headword!r}: {type(e).__name__}: {e}")
            continue
        printed = headword in getattr(module, "PRINTED_MARKUP", frozenset())
        found = problems(entry, printed_markup=printed) + [q for q in [stub_problem(entry, module.COVERS)] if q]
        for p in found:
            bad[p.split(":")[0] + ": " + p.split(":")[-1].strip()[:50]] += 1
        problem_entries += bool(found)
        if entry.stub:
            stubs[entry.stub] += 1
        elif covered(entry, module.COVERS):
            cov += 1
        elif len(uncovered) < show:
            uncovered.append((eid, headword))
        fill["prons"] += bool(entry.prons)
        fill["senses"] += bool(entry.senses)
        fill["definition"] += any(s.definition for s in entry.senses)
        fill["definition_zh"] += any(s.definition_zh for s in entry.senses)
        fill["examples"] += any(s.examples for s in entry.senses)
        fill["pos"] += bool(entry.pos) or any(s.pos for s in entry.senses)
        fill["etymology"] += bool(entry.etymology)
        fill["pron_note"] += any(p.note for p in entry.prons)
        fill["sense_labels"] += any(s.labels for s in entry.senses)
        fill["example_labels"] += any(x.labels for s in entry.senses for x in s.examples)
    content = n - sum(stubs.values())
    return {
        "key": key, "entries": n, "seconds": round(time.time() - t0, 1),
        "stubs": dict(stubs.most_common()), "content_records": content,
        # coverage is over content records only: stubs are excused, and a stub with content is a problem
        "coverage": round(cov / content, 4) if content else 0, "min_coverage": module.MIN_COVERAGE, "covers": module.COVERS,
        "exceptions": len(errors), "exception_examples": errors[:5],
        "problem_entries": problem_entries, "problems": dict(bad.most_common(8)),
        "fill": {k: round(v / n, 3) for k, v in fill.items()} if n else {},
        "uncovered_examples": uncovered,
    }


def sample(key: str, word: str | None, n: int, rand: bool) -> None:
    import lxml.html
    with contextlib.closing(connect()) as conn:
        _sample(conn, key, word, n, rand, lxml.html)


def _sample(conn, key, word, n, rand, lxml_html) -> None:
    if n < 0:  # SQLite reads a negative LIMIT as "no limit"
        raise ValueError(f"n must be >= 0, not {n}")
    dict_id = conn.execute("SELECT id FROM dictionary WHERE key = ?", (key,)).fetchone()[0]
    if word:
        found = conn.execute("SELECT id, headword, body FROM entry WHERE dict_id = ? AND norm = ? LIMIT ?", (dict_id, norm(word), n)).fetchall()
    elif rand:
        found = list(rows(conn, key, n, seed=random.randrange(1 << 30)))
    else:
        found = conn.execute("SELECT id, headword, body FROM entry WHERE dict_id = ? LIMIT ?", (dict_id, n)).fetchall()
    for eid, headword, body in found:
        html = zlib.decompress(body).decode("utf-8", "replace")
        pretty = lxml_html.tostring(lxml_html.fragment_fromstring(html, create_parent="div"), pretty_print=True, encoding="unicode")
        print(f"===== entry {eid}: {headword!r} ({len(html)} bytes)\n{pretty}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample"); s.add_argument("key"); s.add_argument("--word"); s.add_argument("--n", type=int, default=2); s.add_argument("--random", action="store_true")
    c = sub.add_parser("coverage"); c.add_argument("key"); c.add_argument("--limit", type=int); c.add_argument("--seed", type=int); c.add_argument("--show", type=int, default=5)
    a = ap.parse_args()
    if a.cmd == "sample":
        sample(a.key, a.word, a.n, a.random)
    else:
        print(json.dumps(run_coverage(a.key, a.limit, a.seed, a.show), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
