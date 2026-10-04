"""The collocation inventory: which words go with which, in what relation and order.

    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/collocations.py

Reads the collocations of the OCD, LDOCE, MED and NCECD (inventory/collocation_sources.py),
reads their notation into variants (inventory/notation.py), and turns each into a pattern
with the base written "~":

    OCD      VERB + DECISION: make               ->  make ~             verb_obj
    OCD      VERB + DECISION: arrive at          ->  arrive at ~        verb_prep
    LDOCE    verbs: reach/come to a decision     ->  reach a ~, come to a ~
    OCD      RAIN + VERB: pour down              ->  ~ pour down        subj_verb
    OCD      … OF RAIN: drop                     ->  drop of ~          quantifier
    MED      Adverbs frequently used with rain   ->  ~ heavily          adv_verb (order free)

The relation comes from the base's part of speech, the collocate's and its side: adj_noun,
verb_obj, subj_verb, noun_noun, quantifier, prep, adv_verb, adv_adj, verb_adj, verb_verb,
adj_adj, phrase, or untyped when no source says (NCECD's, and LDOCE's collocations from
other entries, unless their one open-class word has a single part of speech). A pattern
whose order the source does not give (a bare adverb) is marked order "free".

The same collocation from several sources is one row: patterns match on their lemmas, with
articles and possessives left out (OCD's "make ~" is LDOCE's "make a ~"). Needs
data/inflections.db. Writes data/collocations.db and data/collocations.jsonl.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "inventories"), str(ROOT / "scripts")]
from inventory import DATA, PUBLISHER, STRUCTURED  # noqa: E402
from inventory import collocation_sources as sources  # noqa: E402
from inventory.collocation_sources import PHRASE, QUANT, UNTYPED, Raw  # noqa: E402
from inventory.collocation_pos import (BASE, _LEFT_OUT_OF_KEYS, _OPEN, _PREPOSITIONS, _RELATIONS,  # noqa: E402
                                       _collocate_pos, _is_content, _mostly_noun, base_from_pattern)
from inventory.db import fresh_db  # noqa: E402
from inventory.evidence import Evidence  # noqa: E402
from inventory.inflection_index import forms_index, lemma_index, pos_index  # noqa: E402
from inventory.notation import parse  # noqa: E402
from inventory.phrases import key as phrase_key  # noqa: E402

PREFERENCE = ("ldoce", "ocd", "med", "ncecd")  # for the canonical pattern: LDOCE prints collocations whole
# Where a collocate stands when no source says: (base, collocate) -> side
_CONVENTIONAL = {("VERB", "ADV"): "after", ("ADJ", "ADV"): "before", ("NOUN", "NOUN"): "after",
                 ("NOUN", "ADJ"): "before", ("VERB", "NOUN"): "after", ("VERB", "VERB"): "before",
                 ("ADJ", "NOUN"): "after", ("ADJ", "VERB"): "before",
                 ("NOUN", "VERB"): "before", ("ADV", "VERB"): "before", ("ADV", "ADJ"): "after",
                 ("NOUN", "ADP"): "after", ("VERB", "ADP"): "after", ("ADJ", "ADP"): "after"}


def relation(base_upos: str, coll: str, side: str) -> str:
    if coll == PHRASE:
        return "phrase"
    return _RELATIONS.get((base_upos, coll, side)) or _RELATIONS.get((base_upos, coll, "*")) or "untyped"


def locate(tokens: tuple[str, ...], base: tuple[str, ...], lemmas: dict[str, str],
           forms: frozenset[str] = frozenset()) -> tuple[int, int] | None:
    """Where the base stands among the tokens, any inflection of its first word allowed
    (`forms`: its inflections, including those that are lemmas themselves, like "came")."""
    n = len(base)
    for i in range(len(tokens) - n + 1):
        if tokens[i] == base[0] or tokens[i] in forms or lemmas.get(tokens[i]) == base[0]:
            if all(lemmas.get(t, t) == b or t == b for t, b in zip(tokens[i + 1:i + n], base[1:])):
                return i, i + n
    return None


def _hyphened(tokens: tuple[str, ...], base: str) -> tuple[str, ...] | None:
    """"rain-drenched" -> "~-drenched"."""
    for i, t in enumerate(tokens):
        parts = t.split("-")
        if len(parts) > 1 and base in parts:
            return tokens[:i] + ("-".join(BASE if p == base else p for p in parts),) + tokens[i + 1:]
    return None


@dataclass
class Placed:
    pattern: tuple[str, ...]
    relation: str
    free: bool  # the order is not given by the source
    base_upos: str = ""  # the base's part of speech the relation was named for; "" when no source gives it


def place(raw: Raw, tokens: tuple[str, ...], base_upos: str, pos_of: dict[str, set[str]],
          lemmas: dict[str, str], forms_of: dict[str, frozenset[str]] | None = None) -> Placed | None:
    """The pattern and relation of one variant of a raw record; None when the base cannot be placed."""
    base = tuple(raw.base.split())
    span = locate(tokens, base, lemmas, (forms_of or {}).get(base[0], frozenset()))
    if span:
        pattern = tokens[:span[0]] + (BASE,) + tokens[span[1]:]
    elif len(base) == 1 and (hyphened := _hyphened(tokens, base[0])):
        pattern = hyphened
    else:
        pattern = None
    coll, given = raw.coll, base_upos
    if pattern is not None:
        at = next((i for i, t in enumerate(pattern) if BASE in t), 0)
        located = tokens[span[0]] if span else ""
        base_upos = base_upos or base_from_pattern(pattern, at, raw.base, pos_of, lemmas, located)
        base_upos = "NOUN" if base_upos in ("PRON", "PROPN", "NUM") else base_upos  # have none; a million ~
        if coll == UNTYPED or "|" in coll:
            coll, where = _collocate_pos(pattern, coll, pos_of, lemmas, at, base_upos)
        else:
            where = next((i for i, t in enumerate(pattern) if _is_content(t)), at)
        side = "before" if where < at else "after"
        rel = relation(base_upos, coll, side) if base_upos else "untyped"
        if base_upos == "VERB" and coll == "NOUN" and where == at + 1 and located.endswith(("ed", "en", "ing")) \
                and located != raw.base:
            rel = "adj_noun"  # wilted lettuce: a participle modifying a noun
        if rel == "untyped" and base_upos == "VERB" and at + 1 < len(pattern) \
                and pattern[at + 1] in ("{oneself}", "{sb}", "{sth}", "{sb/sth}"):
            rel = "verb_obj"  # overstrain {oneself}
        # a part of speech read off the pattern alone stays "": the row joins a typed one (_join_unknown)
        return Placed(pattern, _through_preposition(rel, pattern, where, at, base_upos, coll), False,
                      base_upos if given else "")
    if coll in (UNTYPED, PHRASE):
        return None  # a full collocation or phrase that lacks the base: not readable
    if "|" in coll:
        coll, _ = _collocate_pos(tokens, coll, pos_of, lemmas)
    if coll == "ADJ" and len(tokens) == 1 and _mostly_noun(tokens[0], pos_of, lemmas):
        coll = "NOUN"  # OCD lists noun modifiers under ADJECTIVE: business ~, family ~
    if (base_upos, coll) not in {(k[0], k[1]) for k in _RELATIONS} and "VERB" in pos_of.get(raw.base, set()) \
            and ("VERB", coll) in {(k[0], k[1]) for k in _RELATIONS}:
        base_upos = "VERB"  # object + strenuously: the entry's noun, the collocate's verb
    side, free = raw.side, False
    if not side:
        side, free = _CONVENTIONAL.get((base_upos, coll), ""), True
    if not side:
        return None
    if coll == QUANT:
        pattern = tokens + ("of", BASE)
    else:
        pattern = tokens + (BASE,) if side == "before" else (BASE,) + tokens
    rel = relation(base_upos, coll, side)
    if free and rel in ("verb_obj", "subj_verb"):
        rel = "untyped"  # subject or object: the side decides, and no source gave it
    at = pattern.index(BASE)
    rel = _through_preposition(rel, pattern, 0 if side == "before" else len(pattern) - 1, at, base_upos, coll)
    return Placed(pattern, rel, free, base_upos)


_PARTICLES = frozenset("up down out away back off apart aside together forward ahead".split())  # draw up a ~


def _through_preposition(rel: str, pattern: tuple[str, ...], where: int, at: int, base_upos: str = "",
                         coll: str = "") -> str:
    """A preposition between collocate and base decides the relation: a verb collocate reaching
    the base through one is verb_prep ("crush {sb} to ~", "agree on ~"); otherwise the base and
    its collocate stand in a prepositional relation, prep ("a study in ~", "~ to this day")."""
    between = pattern[min(where, at) + 1:max(where, at)]
    # a particle-like word is a preposition once an object stands before it: take {sb} off ~
    preps = [t for i, t in enumerate(between) if t in _PREPOSITIONS
             and (t not in _PARTICLES or any(b.startswith("{") for b in between[:i]))]
    if base_upos == "VERB" and at > 0 and pattern[at - 1] == "to":
        preps = [t for t in preps if t != "to"]  # attempt to ~: the infinitive, not a preposition
    if not preps:
        return rel
    if coll == "VERB" and where < at:
        return "verb_prep"  # the verb collocate, the preposition, then the base: crush {sb} to ~
    if rel in ("verb_obj", "verb_verb", "noun_noun", "adj_noun", "subj_verb", "untyped") and base_upos in ("NOUN", "VERB"):
        return "prep"       # a study in ~; persist to this day; be ~ in a coup
    return rel


def base_pos(raw: Raw, pos_of: dict[str, set[str]]) -> str:
    """The base's part of speech: the source's, else the dictionaries' when they give one."""
    if raw.base_upos:
        return raw.base_upos
    if raw.coll == UNTYPED:
        return ""  # a full collocation of unknown part of speech: joins a typed one, or stays unknown
    tags = pos_of.get(raw.base, set())
    preferred = {"ADJ": ("NOUN",), "ADV": ("VERB", "ADJ"), "NOUN": ("VERB", "ADJ", "NOUN"),
                 "VERB": ("NOUN", "ADV"), QUANT: ("NOUN",), "ADP": ("NOUN", "VERB", "ADJ")}.get(raw.coll, _OPEN)
    return next((t for t in preferred if t in tags), next((t for t in _OPEN if t in tags), ""))


def key(base: str, base_upos: str, pattern: tuple[str, ...], lemmas: dict[str, str]) -> tuple:
    """Patterns match on lemmas, articles and possessives left out, object slots one."""
    return (base, base_upos, tuple(t for t in phrase_key(pattern, lemmas) if t not in _LEFT_OUT_OF_KEYS))


@dataclass
class Collocation:
    base: str
    base_upos: str
    relations: Counter = field(default_factory=Counter)
    patterns: Counter = field(default_factory=Counter)
    by_dictionary: dict = field(default_factory=dict)  # dictionary -> first pattern it gives
    dictionaries: Counter = field(default_factory=Counter)
    free: bool = True
    gloss: str = ""
    zh: str = ""
    printed: list = field(default_factory=list)


SCHEMA = """
CREATE TABLE collocation (id INTEGER PRIMARY KEY, base TEXT NOT NULL, base_pos TEXT NOT NULL,
  relation TEXT NOT NULL, pattern TEXT NOT NULL, word_order TEXT NOT NULL, patterns TEXT NOT NULL,
  dictionaries TEXT NOT NULL, n INTEGER NOT NULL, publishers INTEGER NOT NULL, gloss TEXT NOT NULL,
  zh TEXT NOT NULL, printed TEXT NOT NULL);
CREATE TABLE pattern (collocation_id INTEGER NOT NULL, text TEXT NOT NULL, lemmas TEXT NOT NULL);
CREATE INDEX collocation_base ON collocation(base);
CREATE INDEX pattern_lemmas ON pattern(lemmas);
"""


def build(raws: Iterable[Raw], lemmas: dict[str, str], pos_of: dict[str, set[str]], out: Path,
          forms_of: dict[str, frozenset[str]] | None = None, evidence=None) -> dict:
    groups: dict[tuple, Collocation] = {}
    seen: Counter[str] = Counter()
    placed_n: Counter[str] = Counter()
    unreadable: Counter[str] = Counter()
    for raw in raws:
        seen[raw.dictionary] += 1
        upos = base_pos(raw, pos_of)
        variants = parse(raw.printed, raw.base, evidence).variants
        placed = [p for v in variants if (p := place(raw, v, upos, pos_of, lemmas, forms_of))]
        if not placed:
            unreadable[raw.dictionary] += 1
            continue
        placed_n[raw.dictionary] += 1
        for p in placed:
            k = key(raw.base, p.base_upos, p.pattern, lemmas)
            g = groups.setdefault(k, Collocation(raw.base, p.base_upos))
            text = " ".join(p.pattern)
            g.relations[p.relation] += 1
            g.patterns[text] += 1
            g.by_dictionary.setdefault(raw.dictionary, text)
            g.dictionaries[raw.dictionary] += 1
            g.free &= p.free
            g.gloss = g.gloss or raw.gloss
            g.zh = g.zh or raw.zh
            if raw.printed not in g.printed and len(g.printed) < 5:
                g.printed.append(raw.printed)
    return _write(_join_unknown(groups), lemmas, out, seen, placed_n, unreadable)


def _join_unknown(groups: dict[tuple, Collocation]) -> dict[tuple, Collocation]:
    """A collocation whose base's part of speech no source gives joins the typed one with the
    same pattern (the most attested, if several)."""
    typed: dict[tuple, list[tuple]] = defaultdict(list)
    for k in groups:
        if k[1]:
            typed[(k[0], k[2])].append(k)
    for k in [k for k in groups if not k[1]]:
        targets = typed.get((k[0], k[2]))
        if not targets:
            continue
        g = groups.pop(k)
        t = groups[max(targets, key=lambda x: sum(groups[x].dictionaries.values()))]
        t.relations.update(g.relations)
        t.patterns.update(g.patterns)
        for d, text in g.by_dictionary.items():
            t.by_dictionary.setdefault(d, text)
        t.dictionaries.update(g.dictionaries)
        t.free &= g.free
        t.gloss, t.zh = t.gloss or g.gloss, t.zh or g.zh
        t.printed += [p for p in g.printed if p not in t.printed][:max(0, 5 - len(t.printed))]
    return groups


def _canonical(g: Collocation) -> str:
    for d in PREFERENCE:
        if d in g.by_dictionary:
            return g.by_dictionary[d]
    return g.patterns.most_common(1)[0][0]


def _relation(g: Collocation) -> str:
    typed = [(n, r) for r, n in g.relations.items() if r != "untyped"]
    return max(typed)[1] if typed else "untyped"


def _write(groups, lemmas, out: Path, seen, placed_n, unreadable) -> dict:
    with fresh_db(out, SCHEMA) as con:
        relations: Counter[str] = Counter()
        rows = sorted(groups.values(), key=lambda g: (g.base, g.base_upos, _canonical(g)))
        jsonl = out.with_suffix(".jsonl.part")
        with jsonl.open("w", encoding="utf-8") as f:
            for i, g in enumerate(rows, 1):
                rel = _relation(g)
                relations[rel] += 1
                dictionaries = sorted(g.dictionaries)
                row = {"id": i, "base": g.base, "base_pos": g.base_upos, "relation": rel, "pattern": _canonical(g),
                       "word_order": "free" if g.free else "fixed", "patterns": sorted(g.patterns),
                       "dictionaries": dictionaries, "n": sum(g.dictionaries.values()),
                       "publishers": len({PUBLISHER.get(d, d) for d in dictionaries}), "gloss": g.gloss, "zh": g.zh,
                       "printed": g.printed}
                con.execute("INSERT INTO collocation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (i, g.base, g.base_upos, rel, row["pattern"], row["word_order"], json.dumps(row["patterns"]),
                             json.dumps(dictionaries), row["n"], row["publishers"], g.gloss, g.zh,
                             json.dumps(g.printed, ensure_ascii=False)))
                for text in g.patterns:
                    con.execute("INSERT INTO pattern VALUES (?,?,?)",
                                (i, text, " ".join(phrase_key(tuple(text.split()), lemmas))))
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    jsonl.replace(out.with_suffix(".jsonl"))
    return {"collocations": len(rows), "relations": dict(relations.most_common()),
            "records": dict(seen), "placed": dict(placed_n), "unreadable": dict(unreadable),
            "two_or_more_publishers": sum(1 for g in rows if len({PUBLISHER.get(d, d) for d in g.dictionaries}) >= 2)}


def main() -> None:
    inflections = DATA / "inflections.db"
    if not inflections.exists():
        sys.exit(f"{inflections} is missing: run inventory/inflections.py first")
    lemmas, pos_of, forms_of = lemma_index(inflections), pos_index(inflections), forms_index(inflections)
    unified = ROOT / "corpus" / "unified.db"

    def raws():
        yield from sources.ocd(STRUCTURED / "ocd.db")
        yield from sources.ldoce(unified, forms_of)
        yield from sources.med(unified)
        yield from sources.ncecd(STRUCTURED / "ncecd.db")
    summary = build(raws(), lemmas, pos_of, DATA / "collocations.db", forms_of, Evidence())
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
