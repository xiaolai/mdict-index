"""Tag each pronunciation contrast: one word in two parts of speech, or two words that share a spelling.

    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/sameword.py

`record` n. and v. are one word; `refuse` n. (rubbish) and v. (decline) are two that happen
to be spelled alike. For every row of pos_contrast (data/pronunciations.db) the dictionaries'
definitions of the two parts of speech are put to a calibrated model (Jev) as two questions:
are they one word with related meanings, and are they unrelated words. Its answers rank well
(AUC 0.96 and 0.97 against 78 hand-labelled contrasts) but it is reluctant to call words
unrelated (never above 0.45), so the tag uses thresholds read off that ranking:

    same word                 p_same >= 0.8 and p_unrelated < 0.15
    likely different words    p_unrelated >= 0.15 and p_same < 0.8
    uncertain                 the rest, and rows without definitions for both parts of speech

On 40 fresh hand-labelled contrasts: "same word" 21 of 22 right, "likely different words" 7
of 10. A part of speech's definitions are not tied to the pronunciation in the contrast (lead
n. /led/, the metal, got the definitions of "the lead", in front), which is the main source of
error.

Answers are cached in data/sameword_cache.json, so a rebuild asks only new questions.
Adds word_relation, p_same and p_unrelated to pos_contrast.

Without jev the step refuses to run unless given --without-jev. Then nothing is asked: cached
answers are still used, every other contrast is tagged "uncertain", and the build_info table
of pronunciations.db records how many contrasts went unasked, so a degraded build never passes
for a full one.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "inventories"), str(ROOT / "scripts")]
from inventory import DATA, STRUCTURED  # noqa: E402
from inventory.pos import normalize  # noqa: E402

DEFINING = ("oald", "ldoce", "cald", "med", "ode", "ced", "mwaled", "noad", "odecn", "ncecd", "chambers", "oed")
SAME = ("These two definitions belong to the same English word used as two parts of speech with related meanings "
        "(like 'record' the noun and 'record' the verb), not to two unrelated words that happen to be spelled alike.")
UNRELATED = ("These are two unrelated English words that merely share a spelling: their meanings are not connected "
             "(like 'refuse' meaning rubbish and 'refuse' meaning to decline), rather than one word used as two "
             "parts of speech.")
SAME_AT, UNRELATED_AT = 0.8, 0.15


def tag(p_same: float | None, p_unrelated: float | None) -> str:
    if p_same is None or p_unrelated is None:
        return "uncertain"
    if p_same >= SAME_AT and p_unrelated < UNRELATED_AT:
        return "same word"
    if p_unrelated >= UNRELATED_AT and p_same < SAME_AT:
        return "likely different words"
    return "uncertain"


def definitions(words: set[str]) -> dict[str, dict[str, list[str]]]:
    """word -> part of speech -> up to three definitions, from the defining dictionaries."""
    out: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    marks = ",".join("?" * len(words))
    for name in DEFINING:
        con = sqlite3.connect(f"file:{STRUCTURED / (name + '.db')}?mode=ro", uri=True)
        rows = con.execute(f"SELECT e.headword, e.pos, s.pos, s.definition FROM s_sense s JOIN s_entry e "
                           f"ON e.entry_id = s.entry_id WHERE e.headword IN ({marks}) AND s.kind = 'sense' "
                           f"AND s.definition != ''", list(words))
        for headword, entry_pos, sense_pos, definition in rows:
            tags = normalize(sense_pos).tags if sense_pos.strip() else set()
            if not tags and len(printed := json.loads(entry_pos)) == 1:
                tags = normalize(printed[0]).tags
            if len(tags) == 1 and len(found := out[headword][next(iter(tags))]) < 3:
                found.append(definition[:160])
        con.close()
    return out


def ask(question: str, state: str) -> float | None:
    done = subprocess.run(["jev", "noul", question, "--state", state], capture_output=True, text=True, timeout=90)
    if done.returncode != 0:
        raise RuntimeError(f"jev failed: {done.stderr.strip()[:200]}")
    return float(done.stdout.split()[-1])


def ask_all(todo: list[tuple[str, str]], cache: dict[str, float], ask=ask) -> list[str]:
    """Ask every (question, state), caching each answer as it comes; a failed question does
    not stop the others. Returns the failures."""
    failures = []
    with cf.ThreadPoolExecutor(8) as pool:
        futures = {pool.submit(ask, q, s): (q, s) for q, s in todo}
        for done in cf.as_completed(futures):
            q, s = futures[done]
            try:
                cache[f"{q[:20]}|{s}"] = done.result()
            except Exception as e:  # noqa: BLE001 - every failure is collected and raised by the caller
                failures.append(f"{q[:20]}|{s[:60]!r}: {e}")
    return failures


def to_ask(states: dict[int, str], cache: dict[str, float], without_jev: bool,
           jev: str | None) -> tuple[list[tuple[str, str]], int]:
    """The (question, state) pairs to put to jev, and how many go unasked. Without jev, and
    without --without-jev, there is no build: the caller must choose to degrade."""
    todo = [(q, s) for s in states.values() for q in (SAME, UNRELATED) if f"{q[:20]}|{s}" not in cache]
    if without_jev:
        return [], len(todo)
    if todo and jev is None:
        sys.exit(f"jev is not installed, and {len(todo)} questions are not cached. Install jev "
                 "(with a TypeSafe API key), or pass --without-jev to tag those contrasts 'uncertain'.")
    return todo, 0


def record(con: sqlite3.Connection, unasked: int, questions: int) -> None:
    """Say in the database how the step ran: the invariant check reports a degraded build."""
    con.execute("CREATE TABLE IF NOT EXISTS build_info (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    value = (f"without jev: {unasked} of {questions} questions unasked; their contrasts are 'uncertain'"
             if unasked else "every question answered by jev (asked now or cached)")
    con.execute("INSERT OR REPLACE INTO build_info VALUES ('sameword', ?)", (value,))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--without-jev", action="store_true",
                    help="ask nothing; tag every contrast without a cached answer 'uncertain'")
    args = ap.parse_args()
    db = DATA / "pronunciations.db"
    cache_path = DATA / "sameword_cache.json"
    cache: dict[str, float] = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    con = sqlite3.connect(db)
    rows = con.execute("SELECT rowid, word, pos_a, pos_b FROM pos_contrast").fetchall()
    defs = definitions({r[1] for r in rows})
    states = {}
    for rowid, word, a, b in rows:
        da, db_ = defs.get(word, {}).get(a), defs.get(word, {}).get(b)
        if da and db_:
            states[rowid] = f"WORD: {word}\n{a}: {' / '.join(da)}\n{b}: {' / '.join(db_)}"
    todo, unasked = to_ask(states, cache, args.without_jev, shutil.which("jev"))
    try:
        failures = ask_all(todo, cache)
    finally:  # answers already paid for are kept even when a question fails
        cache_path.write_text(json.dumps(cache, ensure_ascii=False))
    if failures:
        sys.exit(f"{len(failures)} of {len(todo)} questions failed (the other answers are cached; run again):\n"
                 + "\n".join(failures[:10]))
    for column in ("word_relation TEXT", "p_same REAL", "p_unrelated REAL"):
        try:
            con.execute(f"ALTER TABLE pos_contrast ADD COLUMN {column}")
        except sqlite3.OperationalError:
            pass  # already there from an earlier run
    tags = Counter()
    for rowid, *_ in rows:
        s = states.get(rowid)
        p_same = cache.get(f"{SAME[:20]}|{s}") if s else None
        p_unrel = cache.get(f"{UNRELATED[:20]}|{s}") if s else None
        t = tag(p_same, p_unrel)
        tags[t] += 1
        con.execute("UPDATE pos_contrast SET word_relation = ?, p_same = ?, p_unrelated = ? WHERE rowid = ?",
                    (t, p_same, p_unrel, rowid))
    record(con, unasked, 2 * len(states))
    con.commit()
    con.close()
    print(json.dumps({"contrasts": len(rows), "asked": len(todo), "unasked": unasked, "tags": dict(tags)}, indent=1))


if __name__ == "__main__":
    main()
