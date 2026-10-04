"""Usage labels and grammar patterns: what the dictionaries say about how a word is used.

    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/usage.py

Reads every sense's labels from the parsed dictionaries (and, for grammar, the labels on
its examples: CALD's "+ to infinitive", COBUILD's "VERB noun"), reads them with
inventory/labels.py, and writes two inventories:

    data/labels.db   word, part of speech, axis (register, region, time, domain, attitude...),
                     value, the dictionaries that give it, and the share of the word's senses
                     in those dictionaries that carry it (1.0: the word itself is labelled)
    data/grammar.db  word, part of speech, pattern in COBUILD's notation (V n, V to-inf,
                     N uncount, ADJ n, v-link ADJ), the dictionaries, senses and examples

A phrase's labels belong to the phrase (kind "phrase"), not to its headword. The OCD's
example labels (esp. BrE) describe collocations and are left out, as are the notes of
the pronouncing and usage dictionaries. Labels no rule reads are counted and listed in
data/labels_unread.tsv.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "inventories"), str(ROOT / "scripts")]
from inventory import DATA, PUBLISHER, STRUCTURED  # noqa: E402
from inventory.db import fresh_db  # noqa: E402
from inventory.labels import normalize as read_label  # noqa: E402
from inventory.notation import parse  # noqa: E402
from inventory.pos import normalize as read_pos  # noqa: E402

LEFT_OUT = frozenset({"etym", "lpd", "cepd", "peu", "ocd"})
CLASS = {"VERB": "V", "AUX": "V", "NOUN": "N", "PROPN": "N", "ADJ": "ADJ", "ADV": "ADV"}
_CACHE: dict[str, tuple] = {}


def labels_of(printed: str) -> tuple:
    if printed not in _CACHE:
        _CACHE[printed] = read_label(printed)
    return _CACHE[printed]


def upos_of(sense_pos: str, entry_pos: list[str]) -> str:
    """One part of speech for the sense: its own, else its entry's when that is one (pass the
    entry's only for a sense of the headword itself)."""
    tags = read_pos(sense_pos).tags if sense_pos.strip() else set()
    if not tags and len(entry_pos) == 1:
        tags = read_pos(entry_pos[0]).tags
    return next(iter(tags)) if len(tags) == 1 else ""


EVIDENCE = None  # set by main(): the example index, so a phrase reads as it does in phrases.db


def word_of(headword: str, kind: str, phrase: str) -> tuple[str, str]:
    """(word, kind): a phrase's or derivative's own text when it has one; a phrase in the
    phrase inventory's notation (its first reading: "see what {sb/sth} can do")."""
    if kind in ("phrase", "phrasal_verb") and phrase.strip():
        variants = parse(phrase, headword, EVIDENCE).variants
        return (" ".join(variants[0]) if variants else " ".join(phrase.lower().split())), "phrase"
    text = phrase if kind == "derivative" and phrase.strip() else headword
    return " ".join(text.replace("’", "'").split()).lower(), "word"


def pattern(value: str, upos: str) -> str:
    """A grammar value with "~" written as the word's class: "~ to-inf" -> "ADJ to-inf"."""
    return re.sub(r"(?<![\w-])~(?![\w-])", CLASS.get(upos, "~"), value)


class Tally:
    def __init__(self) -> None:
        self.senses: Counter[tuple] = Counter()                           # (word, kind, pos, dict) -> senses
        self.labels: dict[tuple, Counter] = defaultdict(Counter)         # (word, kind, pos, axis, value) -> dict -> senses
        self.grammar: dict[tuple, Counter] = defaultdict(Counter)        # (word, kind, pos, pattern) -> dict -> senses
        self.grammar_examples: dict[tuple, Counter] = defaultdict(Counter)
        self.unread: Counter[str] = Counter()
        self.uses = Counter()

    def sense(self, dictionary: str, word: tuple[str, str], upos: str, printed: list[str]) -> None:
        self.senses[(*word, upos, dictionary)] += 1
        pairs = set()
        for label in printed:
            read = labels_of(label)
            self.uses["read" if read else "unread"] += 1
            if not read:
                self.unread[label] += 1
            pairs.update(l for l in read if l.axis != "none")
        # once per sense, after "~" is resolved: "+ that" and "V that" on one verb sense are one pattern
        for p in {pattern(value, upos) for axis, value in pairs if axis == "grammar"}:
            self.grammar[(*word, upos, p)][dictionary] += 1
        for axis, value in pairs:
            if axis != "grammar":
                self.labels[(*word, upos, axis, value)][dictionary] += 1

    def example(self, dictionary: str, word: tuple[str, str], upos: str, printed: list[str]) -> None:
        # once per example, after "~" is resolved, as for a sense
        for p in {pattern(value, upos) for label in printed for axis, value in labels_of(label) if axis == "grammar"}:
            self.grammar_examples[(*word, upos, p)][dictionary] += 1


def read_dictionary(db: Path, tally: Tally) -> None:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    senses: dict[int, tuple] = {}
    rows = con.execute("SELECT e.headword, e.pos, s.id, s.kind, s.pos, s.phrase, s.labels FROM s_sense s "
                       "JOIN s_entry e ON e.entry_id = s.entry_id WHERE s.kind != 'note'")
    for headword, entry_pos, sense_id, kind, pos, phrase, labels in rows:
        word = word_of(headword, kind, phrase)
        # the entry's part of speech is its headword's, not a phrase's or a derivative's ("take advice" under "advice")
        upos = upos_of(pos, json.loads(entry_pos) if word == word_of(headword, "sense", "") else [])
        tally.sense(db.stem, word, upos, json.loads(labels))
        senses[sense_id] = (word, upos)
    for sense_id, labels in con.execute("SELECT sense_id, labels FROM s_example WHERE labels != '[]'"):
        if sense_id in senses:
            tally.example(db.stem, *senses[sense_id], json.loads(labels))
    con.close()


LABELS_SCHEMA = """
CREATE TABLE label (word TEXT NOT NULL, kind TEXT NOT NULL, pos TEXT NOT NULL, axis TEXT NOT NULL,
  value TEXT NOT NULL, dictionaries TEXT NOT NULL, n INTEGER NOT NULL, publishers INTEGER NOT NULL,
  senses INTEGER NOT NULL, share REAL NOT NULL);
CREATE INDEX label_word ON label(word);
CREATE INDEX label_value ON label(axis, value);
"""
GRAMMAR_SCHEMA = """
CREATE TABLE pattern (word TEXT NOT NULL, kind TEXT NOT NULL, pos TEXT NOT NULL, pattern TEXT NOT NULL,
  dictionaries TEXT NOT NULL, n INTEGER NOT NULL, publishers INTEGER NOT NULL, senses INTEGER NOT NULL,
  examples INTEGER NOT NULL, share REAL NOT NULL);
CREATE INDEX pattern_word ON pattern(word);
CREATE INDEX pattern_pattern ON pattern(pattern);
"""


def _write(out: Path, schema: str, table: str, rows: list[tuple]) -> None:
    with fresh_db(out, schema) as con:
        marks = ",".join("?" * len(rows[0])) if rows else ""
        if rows:
            con.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)


def _share(tally: Tally, word: tuple, by_dict: Counter) -> float:
    total = sum(tally.senses[(*word, d)] for d in by_dict)
    return round(sum(by_dict.values()) / total, 3) if total else 0.0


def write(tally: Tally, labels_out: Path, grammar_out: Path, unread_out: Path) -> dict:
    label_rows = []
    for (word, kind, upos, axis, value), by_dict in tally.labels.items():
        dicts = sorted(by_dict)
        label_rows.append((word, kind, upos, axis, value, json.dumps(dicts), len(dicts),
                           len({PUBLISHER.get(d, d) for d in dicts}), sum(by_dict.values()),
                           _share(tally, (word, kind, upos), by_dict)))
    grammar_rows = []
    for key in tally.grammar.keys() | tally.grammar_examples.keys():
        word, kind, upos, pat = key
        by_sense, by_example = tally.grammar.get(key, Counter()), tally.grammar_examples.get(key, Counter())
        dicts = sorted(set(by_sense) | set(by_example))
        grammar_rows.append((word, kind, upos, pat, json.dumps(dicts), len(dicts),
                             len({PUBLISHER.get(d, d) for d in dicts}), sum(by_sense.values()),
                             sum(by_example.values()), _share(tally, (word, kind, upos), by_sense) if by_sense else 0.0))
    label_rows.sort()
    grammar_rows.sort()
    _write(labels_out, LABELS_SCHEMA, "label", label_rows)
    _write(grammar_out, GRAMMAR_SCHEMA, "pattern", grammar_rows)
    unread_out.write_text("".join(f"{n}\t{label}\n" for label, n in tally.unread.most_common()), encoding="utf-8")
    axes = Counter(r[3] for r in label_rows)
    return {"senses": sum(tally.senses.values()), "label_uses": dict(tally.uses),
            "read": round(tally.uses["read"] / max(1, sum(tally.uses.values())), 4),
            "label_rows": len(label_rows), "axes": dict(axes.most_common()),
            "grammar_rows": len(grammar_rows), "patterns": len({r[3] for r in grammar_rows})}


def main() -> None:
    global EVIDENCE
    from inventory.evidence import Evidence
    EVIDENCE = Evidence()
    tally = Tally()
    for db in sorted(STRUCTURED.glob("*.db")):
        if db.stem not in LEFT_OUT:
            read_dictionary(db, tally)
    summary = write(tally, DATA / "labels.db", DATA / "grammar.db", DATA / "labels_unread.tsv")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
