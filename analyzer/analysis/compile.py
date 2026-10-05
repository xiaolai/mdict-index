"""Compile the inventories into analyzer/data/analyzer.db, the one file the analyzer reads.

    PYTHONPATH=scripts:analyzer .venv/bin/python analyzer/analysis/compile.py

Needs the inventories (inventories/build.py). Tables:

  form         every form a lemma takes (inflections, spelling variants, contractions,
               nonstandard forms) and the lemma itself, with the lemma's part of speech
  word         per lemma and part of speech: its easiest CEFR level, every level scheme, and the
               usage labels that most publishers listing the word give it (two at least, the OED
               aside): "bite" is not archaic because two of twenty dictionaries mark a sense so
  item         each phrase (idiom, phrasal verb, formula, compound...) and each collocation,
               with its evidence, labels and definitions
  pattern      each item's variants as token patterns, tokenized as running text is: literal
               words (lower case; a collocation's base words marked "~decision"), and slots {obj}
               {poss} {oneself} {somewhere} {...}; with the literal that indexes it (the rarest)
  confusable   pairs of commonly confused words, both ways
  misspelling  a wrong spelling and the word it stands for

A pattern is left out when it cannot be told apart from ordinary text: fewer than two
literals; a phrase made only of plain words ("there are", "not be", "of all", "every
other"); "be" and one word ("be drawn", "be going": every passive and progressive has them);
slots with nothing but function words around them ("in {obj}"); or a collocation
whose only other words are determiners ("a ~"), or whose base is itself a plain word ("so
that", "or not").
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import tempfile
from collections import Counter
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "analyzer"), str(ROOT / "inventories"), str(ROOT / "scripts")]
from analysis import BASE, DATA, FUNCTION_WORDS, INVENTORIES, PLAIN_WORDS, SLOTS, load_nlp  # noqa: E402
from inventory import PUBLISHER  # noqa: E402  two editions of one publisher are one voice

PATH = DATA / "analyzer.db"
FORM_KINDS = ("variant", "contraction", "nonstandard")  # of inflections.db's `other`; not historical/derivative
LABEL_SHARE = 0.5          # of the senses, in the dictionaries that give the label
LABEL_PUBLISHERS = 2       # publishers that give it, the OED aside (its labels are historical) ...
LABEL_AGREEMENT = 0.5      # ... and at least this share of the publishers that list the word at all
LABEL_AXES = ("register", "attitude", "time", "frequency", "region")
CEFR = ("a1", "a2", "b1", "b2", "c1", "c2")
_DETERMINER_SLOTS = frozenset({"a", "an", "the", "{poss}", "{...}"})
# Adverb particles: a phrasal verb with one may put its object on either side ("rip up the letter",
# "rip the letter up"), whichever order the dictionary printed. Prepositions stay put ("look after").
SEPARABLE = frozenset("up down out off on in away back over through around round about along apart aside "
                      "together forward forwards ahead across by".split())

SCHEMA = """
CREATE TABLE form (form TEXT NOT NULL, lemma TEXT NOT NULL, upos TEXT NOT NULL, n INTEGER NOT NULL);
CREATE TABLE word (lemma TEXT NOT NULL, upos TEXT NOT NULL, cefr TEXT NOT NULL, levels TEXT NOT NULL,
                   labels TEXT NOT NULL, PRIMARY KEY (lemma, upos)) WITHOUT ROWID;
CREATE TABLE item (id INTEGER PRIMARY KEY, source TEXT NOT NULL, source_id INTEGER NOT NULL, kind TEXT NOT NULL,
                   text TEXT NOT NULL, base TEXT NOT NULL, relation TEXT NOT NULL, n INTEGER NOT NULL,
                   publishers INTEGER NOT NULL, labels TEXT NOT NULL, definition TEXT NOT NULL,
                   definition_zh TEXT NOT NULL);
CREATE TABLE pattern (item_id INTEGER NOT NULL, tokens TEXT NOT NULL, anchor TEXT NOT NULL);
CREATE TABLE confusable (word TEXT NOT NULL, other TEXT NOT NULL, kinds TEXT NOT NULL, n INTEGER NOT NULL,
                         note TEXT NOT NULL);
CREATE TABLE misspelling (wrong TEXT NOT NULL, word TEXT NOT NULL, kind TEXT NOT NULL, hint TEXT NOT NULL);
"""
INDEXES = """
CREATE INDEX form_form ON form(form);
CREATE INDEX pattern_anchor ON pattern(anchor);
CREATE INDEX confusable_word ON confusable(word);
CREATE INDEX misspelling_wrong ON misspelling(wrong);
"""


def _ro(name: str, inventories: Path) -> sqlite3.Connection:
    path = inventories / name
    if not path.exists():
        sys.exit(f"{path} is missing: build the inventories first (inventories/build.py)")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def tokenize_pattern(words: str, tokenizer) -> list[str]:
    """A pattern's words as running text is tokenized ("what's" -> what 's); slots and the base
    marker stay whole."""
    out: list[str] = []
    for w in words.replace("’", "'").lower().split():
        if w in SLOTS or w == BASE:
            out.append(w)
        else:
            out += [t.text for t in tokenizer(w)]
    return out


def strip_open_ends(tokens: list[str]) -> list[str]:
    """An open slot at either end ("what's with {obj} {...}") matches nothing there."""
    while tokens and tokens[-1] == "{...}":
        tokens = tokens[:-1]
    while tokens and tokens[0] == "{...}":
        tokens = tokens[1:]
    return tokens


def with_base(tokens: list[str], base: list[str]) -> list[str]:
    """A collocation pattern with its base marker replaced by the base's own tokens, marked."""
    out: list[str] = []
    for t in tokens:
        out += [BASE + b for b in base] if t == BASE else [t]
    return out


def literal(token: str) -> str:
    return token[1:] if token.startswith(BASE) and len(token) > 1 else token


def phrasal_orders(tokens: list[str]) -> list[list[str]]:
    """A phrasal verb's patterns with the object on either side of its particle: "rip {obj} up" also
    as "rip up {obj}", and the reverse; "take back" also as "take {obj} back"."""
    out = [tokens]
    if len(tokens) >= 3 and tokens[1] == "{obj}" and tokens[2] in SEPARABLE:
        out.append([tokens[0], tokens[2], "{obj}", *tokens[3:]])
    elif len(tokens) >= 2 and tokens[1] in SEPARABLE:
        rest = tokens[3:] if len(tokens) > 2 and tokens[2] == "{obj}" else tokens[2:]
        if len(tokens) == 2 or tokens[2] == "{obj}":
            out.append([tokens[0], "{obj}", tokens[1], *rest])
    return out


def distinctive(tokens: list[str]) -> bool:
    """Whether a pattern can be told apart from ordinary text (see the module docstring)."""
    literals = [t for t in tokens if t not in SLOTS]
    if len(literals) < 2:
        return False
    if any(t.startswith(BASE) for t in literals):  # a collocation: something besides the base and determiners
        if all(literal(t) in PLAIN_WORDS for t in literals if t.startswith(BASE)):
            return False
        return any(t not in _DETERMINER_SLOTS for t in literals if not t.startswith(BASE))
    if literals[0] == "be" and len(literals) == 2:
        return False
    return any(t not in PLAIN_WORDS for t in literals)


def anchor(tokens: list[str], frequency: Counter) -> str:
    """The pattern's rarest literal: the token it is looked up by."""
    return min((literal(t) for t in tokens if t not in SLOTS), key=lambda t: (frequency[t], t))


def _forms(con_infl) -> list[tuple]:
    rows = [(f, l, u, n) for f, l, u, n in con_infl.execute(
        "SELECT form, lemma, upos, max(n) FROM inflection GROUP BY form, lemma, upos")]
    rows += [(l, l, u, n) for l, u, n in con_infl.execute("SELECT lemma, upos, n FROM lemma")]
    marks = ",".join("?" * len(FORM_KINDS))
    rows += [(f, l, "", n) for f, l, n in con_infl.execute(
        f"SELECT form, lemma, max(n) FROM other WHERE kind IN ({marks}) GROUP BY form, lemma", FORM_KINDS)]
    return sorted({(f.lower(), l.lower(), u, n) for f, l, u, n in rows if f and l})


def _publishers(dictionaries: str) -> set[str]:
    return {PUBLISHER.get(d, d) for d in json.loads(dictionaries) if d != "oed"}


def _words(con_levels, con_labels, con_infl) -> list[tuple]:
    levels: dict[tuple[str, str], dict[str, set]] = {}
    for word, pos, scheme, value in con_levels.execute("SELECT word, pos, scheme, value FROM level"):
        levels.setdefault((word.lower(), pos), {}).setdefault(scheme, set()).add(value)
    listed = {(lemma.lower(), upos): _publishers(dicts)
              for lemma, upos, dicts in con_infl.execute("SELECT lemma, upos, dictionaries FROM lemma")}
    labels: dict[tuple[str, str], set] = {}
    marks = ",".join("?" * len(LABEL_AXES))
    for word, pos, axis, value, dicts in con_labels.execute(
            f"SELECT word, pos, axis, value, dictionaries FROM label WHERE kind = 'word' AND share >= ? "
            f"AND axis IN ({marks})", (LABEL_SHARE, *LABEL_AXES)):
        key, giving = (word.lower(), pos), _publishers(dicts)
        known = listed.get(key, set())
        if len(giving) >= LABEL_PUBLISHERS and known and len(giving & known) >= LABEL_AGREEMENT * len(known):
            labels.setdefault(key, set()).add(f"{axis}:{value}")
    out = []
    for key in sorted(levels.keys() | labels.keys()):
        schemes = levels.get(key, {})
        cefr = min(schemes.get("cefr", ()), key=CEFR.index, default="")
        out.append((*key, cefr, json.dumps({s: sorted(v) for s, v in sorted(schemes.items())}),
                    json.dumps(sorted(labels.get(key, ())))))
    return out


def _items(con_phrases, con_colloc, tokenizer) -> tuple[list[tuple], list[tuple[int, list[str]]]]:
    """The items, and each one's (item id, pattern tokens) before filtering."""
    items, patterns = [], []
    variants: dict[int, list[str]] = {}
    for pid, lemmas in con_phrases.execute("SELECT DISTINCT phrase_id, lemmas FROM variant"):
        variants.setdefault(pid, []).append(lemmas)
    for pid, text, kind, n, pubs, labels, definition, definition_zh in con_phrases.execute(
            "SELECT id, text, kind, n, publishers, labels, definition, definition_zh FROM phrase ORDER BY id"):
        iid = len(items) + 1
        items.append((iid, "phrase", pid, kind, text, "", "", n, pubs, labels, definition, definition_zh))
        for lemmas in sorted(variants.get(pid, ())):
            tokens = strip_open_ends(tokenize_pattern(lemmas, tokenizer))
            patterns += [(iid, t) for t in (phrasal_orders(tokens) if kind == "phrasal_verb" else [tokens])]
    by_id: dict[int, int] = {}
    for cid, base, pos, relation, pattern, n, pubs, gloss, zh in con_colloc.execute(
            "SELECT id, base, base_pos, relation, pattern, n, publishers, gloss, zh FROM collocation ORDER BY id"):
        iid = len(items) + 1
        by_id[cid] = iid
        items.append((iid, "collocation", cid, "collocation", pattern, base.lower(), relation, n, pubs, "[]", gloss, zh))
    bases = {cid: tokenize_pattern(base, tokenizer) for cid, base in con_colloc.execute("SELECT id, base FROM collocation")}
    for cid, lemmas in con_colloc.execute("SELECT DISTINCT collocation_id, lemmas FROM pattern"):
        patterns.append((by_id[cid], with_base(strip_open_ends(tokenize_pattern(lemmas, tokenizer)), bases[cid])))
    return items, patterns


def _confusables(con) -> tuple[list[tuple], list[tuple]]:
    pairs = []
    for a, b, kinds, n, note in con.execute("SELECT word_a, word_b, kinds, n, note FROM confusable"):
        pairs += [(a.lower(), b.lower(), kinds, n, note), (b.lower(), a.lower(), kinds, n, note)]
    wrong = [(w.lower(), word.lower(), kind, hint)
             for word, wrongs, kind, hint in con.execute("SELECT word, wrong, kind, hint FROM misspelling")
             for w in json.loads(wrongs)]
    return pairs, wrong


def build(out: Path = PATH, inventories: Path = INVENTORIES, tokenizer=None) -> dict[str, int]:
    """Write analyzer.db atomically; the row count of each table."""
    tokenizer = tokenizer or load_nlp().tokenizer
    with closing(_ro("inflections.db", inventories)) as infl, closing(_ro("levels.db", inventories)) as lv, \
            closing(_ro("labels.db", inventories)) as lb:
        forms = _forms(infl)
        words = _words(lv, lb, infl)
    with closing(_ro("phrases.db", inventories)) as ph, closing(_ro("collocations.db", inventories)) as co:
        items, raw = _items(ph, co, tokenizer)
    with closing(_ro("confusables.db", inventories)) as cf:
        confusables, misspellings = _confusables(cf)
    kept = [(iid, toks) for iid, toks in raw if distinctive(toks)]
    frequency = Counter(literal(t) for _, toks in kept for t in set(toks) if t not in SLOTS)
    seen, patterns = set(), []
    for iid, toks in kept:
        if (iid, tuple(toks)) not in seen:
            seen.add((iid, tuple(toks)))
            patterns.append((iid, json.dumps(toks, ensure_ascii=False), anchor(toks, frequency)))
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out.parent, prefix=out.name, suffix=".part")
    os.close(fd)
    try:
        with closing(sqlite3.connect(tmp)) as con:
            con.executescript(SCHEMA)
            con.executemany("INSERT INTO form VALUES (?,?,?,?)", forms)
            con.executemany("INSERT INTO word VALUES (?,?,?,?,?)", words)
            con.executemany("INSERT INTO item VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", items)
            con.executemany("INSERT INTO pattern VALUES (?,?,?)", patterns)
            con.executemany("INSERT INTO confusable VALUES (?,?,?,?,?)", confusables)
            con.executemany("INSERT INTO misspelling VALUES (?,?,?,?)", misspellings)
            con.executescript(INDEXES)
            con.commit()
        os.replace(tmp, out)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return {"form": len(forms), "word": len(words), "item": len(items), "pattern": len(patterns),
            "patterns left out": len(raw) - len(kept), "confusable": len(confusables),
            "misspelling": len(misspellings)}


def main() -> None:
    print(json.dumps(build(), indent=1))


if __name__ == "__main__":
    main()
