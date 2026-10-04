"""Evidence: does a word sequence occur in the dictionaries' English examples?

    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/evidence.py   # build the index

A notation can often be read more than one way ("long-running show/musical/soap opera":
a shared "opera", or three alternatives). The readings the examples attest are the right
ones. data/evidence.db is a contentless full-text index of the parsed dictionaries'
example sentences (the OED's quotations left out: historical English), queried by phrase.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "inventories"), str(ROOT / "scripts")]
from inventory import DATA, STRUCTURED  # noqa: E402

LEFT_OUT = frozenset({"oed", "etym"})
PATH = DATA / "evidence.db"


def build(out: Path = PATH, structured: Path = STRUCTURED) -> int:
    """Index the examples of every parsed dictionary but those LEFT_OUT; the number indexed.
    The index replaces `out` only when it holds examples: a missing or empty source folder,
    or a broken source, fails and leaves the old index (and no temporary file) behind."""
    if not structured.is_dir():
        raise FileNotFoundError(f"{structured} is missing: run scripts/build_structured.py first")
    sources = [db for db in sorted(structured.glob("*.db")) if db.stem not in LEFT_OUT]
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=out.name + ".", suffix=".part", dir=out.parent)  # one per build
    os.close(fd)
    tmp = Path(name)
    try:
        n = 0
        with closing(sqlite3.connect(tmp)) as con:
            con.execute("CREATE VIRTUAL TABLE example USING fts5(text, content='', tokenize='unicode61')")
            for db in sources:
                with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as src:
                    rows = src.execute("SELECT text FROM s_example WHERE kind IN ('example', 'collocation') "
                                       "AND text != ''")
                    n += con.executemany("INSERT INTO example(text) VALUES (?)", rows).rowcount
            if not n:
                raise RuntimeError(f"no examples in {structured} ({len(sources)} dictionaries): "
                                   f"{out} left as it was")
            con.execute("INSERT INTO example(example) VALUES ('optimize')")
            con.commit()
        tmp.replace(out)
    finally:
        tmp.unlink(missing_ok=True)
    return n


class Evidence:
    """Phrase lookups in the example index; a variant counts as attested when every run of
    two to four words between its slots occurs in some example, and every four-word window
    of a longer run does."""

    def __init__(self, path: Path = PATH) -> None:
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing: run inventory/evidence.py first")
        self.con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        self.occurs = lru_cache(maxsize=1_000_000)(self._occurs)

    def _occurs(self, words: tuple[str, ...]) -> bool:
        query = '"' + " ".join(w.replace('"', "") for w in words) + '"'
        try:
            return self.con.execute("SELECT 1 FROM example WHERE example MATCH ? LIMIT 1", (query,)).fetchone() is not None
        except sqlite3.OperationalError as error:
            if "syntax error" in str(error) or "fts5" in str(error):
                return False  # a phrase the query language cannot express: not attested
            raise             # a locked or broken index must not pass as "nothing attested"

    def attested(self, variant: tuple[str, ...]) -> bool | None:
        """True or False; None when the variant has no run of two words to look up."""
        runs, run = [], []
        for token in variant + ("{",):
            if token.startswith("{") or token == "~":
                if len(run) >= 2:
                    runs.append(tuple(run))
                run = []
            else:
                run.append(token)
        if not runs:
            return None
        # a long run is plausible when every four-word window occurs: "be deposed in a coup" is
        # rarely printed whole, its windows are. Shorter windows let garbage through: the index
        # ignores punctuation, so "give get the" matches "... give, get the ..."
        return all(self.occurs(r) if len(r) <= 4 else all(self.occurs(r[i:i + 4]) for i in range(len(r) - 3))
                   for r in runs)


def main() -> None:
    print(f"{build()} examples indexed in {PATH}")


if __name__ == "__main__":
    main()
