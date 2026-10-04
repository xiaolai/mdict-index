"""Export parallel.db as JSONL, TSV or TMX.

    PYTHONPATH=scripts:parallel_corpus .venv/bin/python parallel_corpus/parallel/export.py FORMAT OUT [--all] [--kind sentence|phrase]

FORMAT is jsonl, tsv or tmx. By default one pair per cluster is written (its representative:
pairs differing only in punctuation or spacing are one); --all writes every distinct pair.
The Chinese is written in simplified characters (zh_hans); JSONL also carries the text as
printed. Exports are derived from copyrighted dictionaries: for personal use, like corpus/.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parallel import DATA  # noqa: E402

FORMATS = ("jsonl", "tsv", "tmx")
_XML_INVALID = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")  # characters XML 1.0 forbids


def _xml(text: str) -> str:
    if _XML_INVALID.search(text):  # the pair rules reject these; a TMX that does not parse must never be written
        raise ValueError(f"character not allowed in XML: {text!r}")
    return escape(text)


_QUERY = """
SELECT p.id, p.en, p.zh, p.zh_hans, p.kind, p.variants, p.sources,
       (SELECT json_group_array(name) FROM (SELECT DISTINCT d.name FROM source s
        JOIN dictionary d ON d.id = s.dictionary_id WHERE s.pair_id = p.id ORDER BY d.id)) AS dictionaries
FROM pair p {join} {where} ORDER BY p.id
"""


def rows(con: sqlite3.Connection, all_pairs: bool, kind: str | None) -> Iterator[dict]:
    join = "" if all_pairs else "JOIN cluster c ON c.representative = p.id"
    where, params = ("WHERE p.kind = ?", (kind,)) if kind else ("", ())
    cur = con.execute(_QUERY.format(join=join, where=where), params)
    names = [d[0] for d in cur.description]
    for row in cur:
        r = dict(zip(names, row))
        r["dictionaries"] = json.loads(r["dictionaries"])  # JSON, as a name may contain any separator
        yield r


def _tsv_field(text: str) -> str:
    return text.replace("\t", " ").replace("\n", " ")


def write(fmt: str, records: Iterator[dict], out) -> int:
    n = 0
    if fmt == "tmx":
        out.write('<?xml version="1.0" encoding="UTF-8"?>\n<tmx version="1.4">\n'
                  '<header creationtool="dictionary-collection parallel/export.py" creationtoolversion="1" '
                  'segtype="sentence" o-tmf="sqlite" adminlang="en" srclang="en" datatype="plaintext"/>\n<body>\n')
    elif fmt == "tsv":
        out.write("en\tzh\tkind\n")
    for r in records:
        if fmt == "jsonl":
            out.write(json.dumps({"id": r["id"], "en": r["en"], "zh": r["zh_hans"], "zh_printed": r["zh"],
                                  "kind": r["kind"], "variants": r["variants"], "sources": r["dictionaries"]},
                                 ensure_ascii=False) + "\n")
        elif fmt == "tsv":
            out.write(f"{_tsv_field(r['en'])}\t{_tsv_field(r['zh_hans'])}\t{r['kind']}\n")
        else:
            out.write(f'<tu tuid="{r["id"]}"><prop type="x-kind">{r["kind"]}</prop>'
                      f'<tuv xml:lang="en"><seg>{_xml(r["en"])}</seg></tuv>'
                      f'<tuv xml:lang="zh-CN"><seg>{_xml(r["zh_hans"])}</seg></tuv></tu>\n')
        n += 1
    if fmt == "tmx":
        out.write("</body>\n</tmx>\n")
    return n


def export(db: Path, fmt: str, out: Path, all_pairs: bool = False, kind: str | None = None) -> int:
    """Write the export to out atomically; returns how many pairs."""
    if fmt not in FORMATS:
        raise ValueError(f"format must be one of {FORMATS}")
    if out.resolve() == db.resolve() or (out.exists() and out.samefile(db)):  # also a hard link
        raise ValueError(f"{out}: the output would replace the database it is exported from")
    # as_uri() escapes ? and #, which would otherwise start the URI's query and fragment
    con = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    tmp = out.with_name(f"{out.name}.{uuid.uuid4().hex}.part")  # its own, so concurrent exports never share one
    try:
        with tmp.open("w", encoding="utf-8") as f:
            n = write(fmt, rows(con, all_pairs, kind), f)
        tmp.replace(out)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        con.close()
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("format", choices=FORMATS)
    ap.add_argument("out", type=Path)
    ap.add_argument("--db", type=Path, default=DATA / "parallel.db")
    ap.add_argument("--all", action="store_true", help="every distinct pair, not one per cluster")
    ap.add_argument("--kind", choices=("sentence", "phrase"))
    args = ap.parse_args()
    n = export(args.db, args.format, args.out, args.all, args.kind)
    print(f"{n:,} pairs -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
