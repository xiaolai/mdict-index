"""The compiled inventories in memory: what the matcher and the word annotations look up."""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from analysis import BASE, DATA, SLOTS

PATH = DATA / "analyzer.db"
# Relations the parse can find between a base and one collocate word (see match.py). Not "prep": a
# preposition's meaning turns on its order and article ("faith in" is not "in faith", "at a rate"
# not "at any rate"), so those are matched as patterns, articles and all.
TYPED = frozenset({"verb_obj", "subj_verb", "adj_noun", "noun_noun", "adv_verb", "adv_adj", "verb_adj", "verb_prep"})
ARTICLES = frozenset({"a", "an", "the"})
# Not marked in running text: a noun's prepositions (OCD's "PREP. in a ~, on the ~") are mostly free
# combinations whose sense turns on the article ("in the years 2013-2017" is not "in a year").
UNMARKED_RELATIONS = frozenset({"prep"})


@dataclass(frozen=True)
class Item:
    id: int
    source: str          # phrase | collocation
    source_id: int       # its id in phrases.db or collocations.db
    kind: str            # idiom, phrasal_verb, formula, name, compound, pattern | collocation
    text: str            # canonical form as the dictionaries print it
    base: str            # a collocation's base word; "" for a phrase
    relation: str        # a collocation's relation (adj_noun, verb_obj, ...); "" for a phrase
    n: int               # dictionaries that list it
    publishers: int
    labels: tuple[str, ...]
    definition: str
    definition_zh: str


@dataclass(frozen=True)
class Pattern:
    item: Item
    tokens: tuple[str, ...]   # literal tokens and slots; "~decision" marks a collocation's base word
    words: frozenset[str] = frozenset()  # its literal words, markers off: a sentence lacking one cannot match

    def __post_init__(self):
        if not self.words:
            words = frozenset(t[1:] if t.startswith(BASE) and len(t) > 1 else t for t in self.tokens if t not in SLOTS)
            object.__setattr__(self, "words", words)


@dataclass
class Lexicon:
    forms: dict[str, list[tuple[str, str, int]]] = field(default_factory=dict)   # form -> (lemma, upos, n)
    words: dict[tuple[str, str], dict] = field(default_factory=dict)             # (lemma, upos) -> levels, labels
    by_anchor: dict[str, list[Pattern]] = field(default_factory=dict)
    by_base: dict[str, list[tuple[Item, str]]] = field(default_factory=dict)  # base lemma -> (item, collocate)
    confusables: dict[str, list[dict]] = field(default_factory=dict)
    misspellings: dict[str, list[dict]] = field(default_factory=dict)

    def known(self, word: str) -> bool:
        return word in self.forms


def typed_collocate(item: Item, patterns: list[tuple[str, ...]]) -> tuple[str, str] | None:
    """(base, collocate) when the parse can find this collocation: a typed relation, a one-word
    base, and one collocate word in every pattern ("make a ~decision", "make ~decision"), and no
    slot (in "in {poss} ~word" the possessive is the point)."""
    if item.relation not in TYPED or any(t in SLOTS for p in patterns for t in p):
        return None
    bases = {tuple(t[1:] for t in p if t.startswith(BASE) and len(t) > 1) for p in patterns}
    contents = {tuple(t for t in p if not t.startswith(BASE) and t not in SLOTS and t not in ARTICLES)
                for p in patterns}
    if len(bases) != 1 or len(contents) != 1:
        return None
    (base,), (content,) = bases, contents
    return (base[0], content[0]) if len(base) == 1 and len(content) == 1 else None


def load(path: Path = PATH, min_collocation_n: int = 2) -> Lexicon:
    """Read analyzer.db. Collocations listed by fewer than `min_collocation_n` dictionaries are left
    out: one dictionary's collocation is evidence too thin to mark in running text. So are a noun's
    prepositions (UNMARKED_RELATIONS)."""
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing: run analyzer/build.py (after inventories/build.py)")
    lex = Lexicon()
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as con:
        forms = defaultdict(list)
        for form, lemma, upos, n in con.execute("SELECT form, lemma, upos, n FROM form"):
            forms[form].append((lemma, upos, n))
        lex.forms = dict(forms)
        for lemma, upos, cefr, levels, labels in con.execute("SELECT lemma, upos, cefr, levels, labels FROM word"):
            lex.words[(lemma, upos)] = {"cefr": cefr, "levels": json.loads(levels), "labels": json.loads(labels)}
        items = {}
        for row in con.execute("SELECT id, source, source_id, kind, text, base, relation, n, publishers, labels, "
                               "definition, definition_zh FROM item"):
            iid, source, source_id, kind, text, base, relation, n, pubs, labels, definition, zh = row
            if source == "collocation" and (n < min_collocation_n or relation in UNMARKED_RELATIONS):
                continue
            items[iid] = Item(iid, source, source_id, kind, text, base, relation, n, pubs, tuple(json.loads(labels)),
                              definition, zh)
        patterns = defaultdict(list)
        for iid, tokens, anchor in con.execute("SELECT item_id, tokens, anchor FROM pattern"):
            if iid in items:
                patterns[iid].append((tuple(json.loads(tokens)), anchor))
        by_anchor, by_base = defaultdict(list), defaultdict(list)
        for iid, found in patterns.items():
            if typed := typed_collocate(items[iid], [t for t, _ in found]):
                by_base[typed[0]].append((items[iid], typed[1]))
            else:
                for tokens, anchor in found:
                    by_anchor[anchor].append(Pattern(items[iid], tokens))
        lex.by_anchor, lex.by_base = dict(by_anchor), dict(by_base)
        confusables = defaultdict(list)
        for word, other, kinds, n, note in con.execute("SELECT word, other, kinds, n, note FROM confusable"):
            confusables[word].append({"word": other, "kinds": json.loads(kinds), "n": n, "note": note})
        lex.confusables = dict(confusables)
        misspellings = defaultdict(list)
        for wrong, word, kind, hint in con.execute("SELECT wrong, word, kind, hint FROM misspelling"):
            misspellings[wrong].append({"word": word, "kind": kind, "hint": hint})
        lex.misspellings = dict(misspellings)
    return lex
