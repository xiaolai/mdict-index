"""Tag each pronunciation contrast: one word in two parts of speech, or two words that share a spelling.

    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/sameword.py [--without-jev]
    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/sameword.py --export-answers

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

jev's answers vary from one asking to the next (by up to 0.25), so a contrast near a threshold
could change its tag between two builds. inventories/sameword_answers.json (committed) holds,
per contrast, the mean of SAMPLES answers to each question, keyed by the SHA-256 of what jev was
shown: numbers only, no word or definition. Every build takes its answers from there first, so
builds agree, and a build without jev loses nothing. A contrast the file lacks (its definitions
changed with a download or a parser) is asked of jev, its answer cached in
data/sameword_cache.json; without jev, or with --without-jev, it is tagged "uncertain", and the
build_info table of pronunciations.db records how many were, so a degraded build never passes
for a full one. --export-answers asks every current contrast SAMPLES times (kept locally in
data/sameword_samples.json, so an interrupted run resumes) and rewrites the committed file.
Adds word_relation, p_same and p_unrelated to pos_contrast.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
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
ANSWERS = ROOT / "inventories" / "sameword_answers.json"
SAMPLES = 3  # answers averaged per question: the mean of three varies about 0.6 as much as one answer


def state_key(state: str) -> str:
    """What a shared answer is filed under: the hash of exactly what jev was shown."""
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def questions_version() -> str:
    """Changes when either question's wording does: answers to other wording are not these answers."""
    return hashlib.sha256(f"{SAME}\n{UNRELATED}".encode("utf-8")).hexdigest()[:16]


def load_shared(path: Path = ANSWERS) -> dict[str, tuple[float, float]]:
    """state_key -> (p_same, p_unrelated) from the committed answers; none if they answer other questions."""
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc["questions"] != questions_version():
        print(f"{path.name} answers other questions (the wording changed): not used; "
              "rewrite it with --export-answers", file=sys.stderr)
        return {}
    return {k: (v[0], v[1]) for k, v in doc["answers"].items()}


def dump_answers(doc: dict) -> str:
    """The committed file's text: one contrast a line, so a change to it reads as a diff of contrasts."""
    head = json.dumps({k: v for k, v in doc.items() if k != "answers"}, indent=1)
    lines = ",\n".join(f"  {json.dumps(k)}: {json.dumps(v)}" for k, v in doc["answers"].items())
    return head[:-2] + ',\n "answers": {\n' + lines + "\n }\n}\n"


def export_answers(states: dict[int, str], samples: dict[str, float], n: int) -> dict:
    """The committed file's content: per current contrast, the mean of its n samples of each question."""
    answers = {}
    for state in states.values():
        means = []
        for q in (SAME, UNRELATED):
            got = [samples.get(f"{q[:20]}|{i}|{state}") for i in range(n)]
            if None in got:
                raise ValueError(f"{state[:40]!r}: {got.count(None)} of {n} samples of {q[:20]!r} missing")
            means.append(round(sum(got) / n, 3))
        answers[state_key(state)] = means
    return {"about": "Mean jev answers per stress contrast, keyed by the SHA-256 of what jev was shown "
                     "(inventories/inventory/sameword.py); numbers only.",
            "questions": questions_version(), "samples": n, "answers": dict(sorted(answers.items()))}


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


def ask_all(todo: list[tuple[str, str]], cache: dict[str, float], ask=ask,
            key=lambda q, s: f"{q[:20]}|{s}") -> list[str]:
    """Ask every (question, state), caching each answer under key(question, state) as it comes;
    a failed question does not stop the others. Returns the failures."""
    failures = []
    with cf.ThreadPoolExecutor(8) as pool:
        futures = {pool.submit(ask, q, s): (q, s) for q, s in todo}
        for done in cf.as_completed(futures):
            q, s = futures[done]
            try:
                cache[key(q, s)] = done.result()
            except Exception as e:  # noqa: BLE001 - every failure is collected and raised by the caller
                failures.append(f"{q[:20]}|{s[:60]!r}: {e}")
    return failures


def to_ask(states: dict[int, str], cache: dict[str, float], shared: dict[str, tuple[float, float]],
           without_jev: bool, jev: str | None) -> tuple[list[tuple[str, str]], int]:
    """The (question, state) pairs to put to jev, and how many go unanswered: those neither the
    shared answers nor the cache hold, when jev is missing or not to be asked."""
    todo = [(q, s) for s in states.values() if state_key(s) not in shared
            for q in (SAME, UNRELATED) if f"{q[:20]}|{s}" not in cache]
    if without_jev or jev is None:
        return [], len(todo)
    return todo, 0


def record(con: sqlite3.Connection, unasked: int, questions: int, shared: int) -> None:
    """Say in the database how the step ran: the invariant check reports a degraded build."""
    con.execute("CREATE TABLE IF NOT EXISTS build_info (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    source = f"{shared} contrast{'s' * (shared != 1)} from the shared answers, {questions // 2 - shared} by jev"
    value = (f"{unasked} of {questions} questions unanswered (no jev); their contrasts are 'uncertain'; {source}"
             if unasked else f"every question answered: {source}")
    con.execute("INSERT OR REPLACE INTO build_info VALUES ('sameword', ?)", (value,))


def sample(states: dict[int, str], samples_path: Path) -> dict[str, float]:
    """SAMPLES answers to each question for every contrast, asking only the ones not yet kept."""
    samples: dict[str, float] = json.loads(samples_path.read_text()) if samples_path.exists() else {}
    if shutil.which("jev") is None:
        sys.exit("--export-answers asks jev, which is not installed")
    try:
        for i in range(SAMPLES):
            todo = [(q, s) for s in states.values() for q in (SAME, UNRELATED) if f"{q[:20]}|{i}|{s}" not in samples]
            failures = ask_all(todo, samples, key=lambda q, s, i=i: f"{q[:20]}|{i}|{s}")
            if failures:
                sys.exit(f"{len(failures)} of {len(todo)} questions failed (the other answers are kept; run again):\n"
                         + "\n".join(failures[:10]))
    finally:  # answers already paid for are kept even when a question fails
        samples_path.write_text(json.dumps(samples, ensure_ascii=False))
    return samples


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--without-jev", action="store_true",
                    help="never ask jev; contrasts the shared answers and the cache lack are tagged 'uncertain'")
    ap.add_argument("--export-answers", action="store_true",
                    help=f"ask jev {SAMPLES} times per question for every contrast and rewrite {ANSWERS.name}")
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
    if args.export_answers:
        doc = export_answers(states, sample(states, DATA / "sameword_samples.json"), SAMPLES)
        ANSWERS.write_text(dump_answers(doc), encoding="utf-8")
        print(f"wrote {len(doc['answers'])} contrasts' answers to {ANSWERS.relative_to(ROOT)}", file=sys.stderr)
    shared = load_shared()
    todo, unasked = to_ask(states, cache, shared, args.without_jev, shutil.which("jev"))
    try:
        failures = ask_all(todo, cache)
    finally:  # answers already paid for are kept even when a question fails
        cache_path.write_text(json.dumps(cache, ensure_ascii=False))
    if failures:
        sys.exit(f"{len(failures)} of {len(todo)} questions failed (the other answers are cached; run again):\n"
                 + "\n".join(failures[:10]))
    if unasked:
        print(f"{unasked} questions are in neither the shared answers nor the cache, and jev is "
              f"{'not to be asked' if args.without_jev else 'not installed'}: their contrasts are tagged 'uncertain'",
              file=sys.stderr)
    for column in ("word_relation TEXT", "p_same REAL", "p_unrelated REAL"):
        try:
            con.execute(f"ALTER TABLE pos_contrast ADD COLUMN {column}")
        except sqlite3.OperationalError:
            pass  # already there from an earlier run
    tags, from_shared = Counter(), 0
    for rowid, *_ in rows:
        s = states.get(rowid)
        if s and state_key(s) in shared:
            p_same, p_unrel = shared[state_key(s)]
            from_shared += 1
        else:
            p_same = cache.get(f"{SAME[:20]}|{s}") if s else None
            p_unrel = cache.get(f"{UNRELATED[:20]}|{s}") if s else None
        t = tag(p_same, p_unrel)
        tags[t] += 1
        con.execute("UPDATE pos_contrast SET word_relation = ?, p_same = ?, p_unrelated = ? WHERE rowid = ?",
                    (t, p_same, p_unrel, rowid))
    record(con, unasked, 2 * len(states), from_shared)
    con.commit()
    con.close()
    print(json.dumps({"contrasts": len(rows), "from shared answers": from_shared, "asked": len(todo),
                      "unanswered": unasked, "tags": dict(tags)}, indent=1))

if __name__ == "__main__":
    main()
