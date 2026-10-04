"""Writing an inventory database whole or not at all: `fresh_db` builds it in a .part file beside
the target, from its schema, and moves it over the target only when the build finishes; a
build that raises leaves the target as it was and deletes its .part file.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def fresh_db(out: Path, schema: str) -> Iterator[sqlite3.Connection]:
    """A connection to a new, empty database with `schema`, written to `out` when the block ends.
    A .part file an earlier failed build left is removed first; the block's rows are committed
    at its end."""
    tmp = out.with_name(out.name + ".part")
    tmp.unlink(missing_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(tmp)
    try:
        con.executescript(schema)
        yield con
        con.commit()
    except BaseException:
        con.close()
        tmp.unlink(missing_ok=True)
        raise
    con.close()
    tmp.replace(out)
