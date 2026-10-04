"""The phrase inventory: idioms, formulas and phrasal verbs, with their slots and variants.

    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/phrases.py

Reads the phrases the parsed dictionaries list (senses of kind phrase and phrasal_verb),
reads their notation into variants of words and slots (inventory/notation.py), and merges
the same phrase across dictionaries: two phrases are one when they share a variant after
their words are reduced to lemmas (inventory/inflections.py: goes public = go public) and
their object slots are unified ({sb}, {sth}, {sb/sth}). Needs data/inflections.db.

Each phrase records every variant, its slots, whether it is separable (put sth off), its
kind (phrasal_verb, formula, idiom, name), the dictionaries and publishers that list it,
and a definition. COBUILD's phrase strings are the bold words of its defining sentences
(goes public, kill stone-dead), so they count as evidence but never give the canonical text;
a phrase only COBUILD gives is left out. A phrase every dictionary tags as a noun, with no
slot, is a compound (the great apes), not an idiom.
The OED is left out: its "phrases" are mostly compounds.

Writes data/phrases.db and data/phrases.jsonl.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "inventories"))
from inventory import DATA, PUBLISHER, STRUCTURED  # noqa: E402
from inventory.db import fresh_db  # noqa: E402
from inventory.evidence import Evidence  # noqa: E402
from inventory.inflect import regular, syllables  # noqa: E402
from inventory.inflection_index import lemma_index, verb_form_index  # noqa: E402
from inventory.notation import PARTICLES, parse  # noqa: E402
from inventory.phrase_kinds import KEYWORDS_ONLY, KindEvidence, kind_evidence, kind_of, refine_kind  # noqa: E402
from inventory.pos import normalize  # noqa: E402

LEFT_OUT = frozenset({"oed", "etym", "peu", "cepd", "lpd", "ocd"})  # no phrase senses, or not phrases
# Order of preference for the canonical text, and the publisher each dictionary belongs to.
PREFERENCE = ("oald", "ldoce", "cald", "mwaled", "med", "oalecd", "ldoce-ec", "ahd", "chambers", "mwu", "ced",
              "odecn", "ncecd", "yhdcd", "cobuild", "cobuild-ec")
NOTE_START = re.compile(r"^(?:comparative|superlative|plural|past tense|past participle|present participle|"
                        r"also |see |abbreviation)", re.I)  # grammar notes listed as phrases
_OBJECT = {"{sb}": "{obj}", "{sth}": "{obj}", "{sb/sth}": "{obj}", "{sb's}": "{poss}", "{one's}": "{poss}",
           "{sth's}": "{poss}"}


@dataclass
class Record:
    """One phrase as one dictionary lists it."""
    dictionary: str
    headword: str
    printed: str
    kind: str        # the dictionary's: phrase | phrasal_verb
    pos: str
    labels: list[str]
    definition: str
    definition_zh: str


@dataclass
class Group:
    records: list[Record] = field(default_factory=list)
    variants: dict[str, set[str]] = field(default_factory=dict)  # variant text -> dictionaries printing it
    separable: bool = False


def key(variant: tuple[str, ...], lemmas: dict[str, str]) -> tuple[str, ...]:
    """The merge key of a variant: words as lemmas, object and possessive slots unified."""
    return tuple(_OBJECT.get(t, t) if t.startswith("{") else lemmas.get(t, t) for t in variant)


_PARTICLE_PLACE = PARTICLES | frozenset("to with for from at into onto upon as after of against without forth toward towards beyond past before "
                                        "aback".split())


def phrasal_shape(variant: str, verbs: set[str], lemmas: dict[str, str],
                  verb_forms: dict[str, frozenset[str]] | None = None) -> bool:
    """A phrasal verb's shape: (be/get/feel) the entry's verb, its object, one or two
    particles, an object: "put {sb} up to {sth}", "be burnt out", "psych {oneself} up". Not an
    idiom filed under one ("it goes without saying", "be whistling in the dark")."""
    tokens = variant.split()
    if tokens[0] in ("not", "never") and len(tokens) > 2:  # "not hold with {sth}", "never tire of {sth}"
        tokens = tokens[1:]
    starts = (0, 1) if tokens[0] in ("be", "get", "feel") and len(tokens) > 2 else (0,)
    return any(_phrasal_from(tokens, i, verbs, lemmas, verb_forms or {}) for i in starts)


def _is_verb_form(word: str, verbs: set[str], lemmas: dict[str, str], verb_forms: dict[str, frozenset[str]]) -> bool:
    if word in verbs or lemmas.get(word, word) in verbs or verb_forms.get(word, frozenset()) & verbs:
        return True
    # "patterned", "heading": headwords themselves, so the lemma index does not send them back
    return any(len(v) >= 3 and word in _regular_forms(v) for v in verbs)


def _regular_forms(verb: str) -> frozenset[str]:
    """A verb's regular inflections, by the rules the inflection inventory uses (inflect.py): not
    any word that starts like it ("shower" is not "show"), nor another verb's forms ("hoped" is
    "hope", "hop" gives "hopped"). The spelling does not show a longer verb's stress, so its
    final consonant may double or not (preferred, offered); a monosyllable's always does."""
    stresses = (None,) if syllables(verb) == 1 else (True, False)
    return frozenset(form for stress in stresses for forms in regular(verb, "VERB", stress).values()
                     for form, _ in forms)


def _phrasal_from(tokens: list[str], i: int, verbs: set[str], lemmas: dict[str, str],
                  verb_forms: dict[str, frozenset[str]]) -> bool:
    if not _is_verb_form(tokens[i], verbs, lemmas, verb_forms):
        return False
    i += 1
    if i < len(tokens) and (tokens[i].startswith("{") or tokens[i] in ("it", "you")):
        i += 1
    particles = 0
    while i < len(tokens) and particles < 2 and tokens[i] in _PARTICLE_PLACE:
        i, particles = i + 1, particles + 1
    if i < len(tokens) and tokens[i] in ("doing", "it", "you"):  # "look forward to doing {sth}", "run away with you"
        i += 1
    if i < len(tokens) and tokens[i].startswith("{"):
        i += 1
    return particles > 0 and i == len(tokens)


def _looks_phrasal(variant: tuple[str, ...]) -> bool:
    return len(variant) >= 2 and any(t in PARTICLES for t in variant[1:3])


def _records(db: Path):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        yield from con.execute(
            "SELECT e.headword, s.kind, s.phrase, s.pos, s.labels, s.definition, s.definition_zh FROM s_sense s "
            "JOIN s_entry e ON e.entry_id = s.entry_id WHERE s.kind IN ('phrase', 'phrasal_verb') AND s.phrase <> ''")
    finally:
        con.close()


def _preference(dictionary: str) -> int:
    return PREFERENCE.index(dictionary) if dictionary in PREFERENCE else len(PREFERENCE)


def group(records: list[tuple[Record, list[tuple[str, ...]], bool]], lemmas: dict[str, str]) -> list[Group]:
    """Anchored grouping, in order of dictionary preference. The first record of a phrase starts
    a group and registers its variants as the group's keys. A later record joins a group when its
    own first variant is one of the group's keys, or when it lists the group's anchor phrase.
    Unlike joining on any shared variant, this does not chain distinct idioms through a record
    that groups near-synonyms (open the door/way; clear/pave/open/prepare the way)."""
    groups: list[Group] = []
    owner: dict[tuple, int] = {}    # variant key -> group, first registration wins
    anchor: dict[tuple, int] = {}   # a group's first variant key -> group
    for i in sorted(range(len(records)), key=lambda i: _preference(records[i][0].dictionary)):
        record, variants, separable = records[i]
        keys = [key(v, lemmas) for v in variants]
        g = owner.get(keys[0])
        if g is None:
            g = next((anchor[k] for k in keys if k in anchor), None)
        if g is None:
            g = len(groups)
            groups.append(Group())
            anchor[keys[0]] = g
            for k in keys:
                owner.setdefault(k, g)
        groups[g].records.append(record)
        groups[g].separable |= separable
        for v in variants:
            groups[g].variants.setdefault(" ".join(v), set()).add(record.dictionary)
    return groups


def canonical(g: Group, evidence=None) -> str:
    """The first variant of the most preferred dictionary that prints the phrase itself."""
    ranked = sorted((r for r in g.records if r.dictionary not in KEYWORDS_ONLY),
                    key=lambda r: _preference(r.dictionary))
    for r in ranked:
        phrases = [v for v in parse(r.printed, r.headword, evidence).variants if is_phrase(v)]
        if phrases:
            return " ".join(phrases[0])
    return max(g.variants, key=lambda v: len(g.variants[v]))  # the variant most dictionaries print, first on a tie


def is_phrase(variant: tuple[str, ...]) -> bool:
    """Two words or more besides slots, or a hyphenated phrase written as one (off-the-cuff);
    a word with its article (the woman) is the word."""
    if len(variant) == 2 and variant[0] in ("the", "a", "an"):
        return False
    return len([t for t in variant if not t.startswith("{")]) >= 2 or len(variant) == 1 and variant[0].count("-") >= 2


SCHEMA = """
CREATE TABLE phrase (id INTEGER PRIMARY KEY, text TEXT NOT NULL, kind TEXT NOT NULL, separable INTEGER NOT NULL,
  slots TEXT NOT NULL, variants TEXT NOT NULL, headwords TEXT NOT NULL, dictionaries TEXT NOT NULL,
  n INTEGER NOT NULL, publishers INTEGER NOT NULL, labels TEXT NOT NULL, definition TEXT NOT NULL,
  definition_zh TEXT NOT NULL, printed TEXT NOT NULL);
CREATE TABLE variant (phrase_id INTEGER NOT NULL, text TEXT NOT NULL, lemmas TEXT NOT NULL, n INTEGER NOT NULL);
CREATE INDEX variant_text ON variant(text);
CREATE INDEX variant_lemmas ON variant(lemmas);
CREATE INDEX phrase_text ON phrase(text);
"""


def build(dbs: list[Path], lemmas: dict[str, str], out: Path, evidence=None,
          kinds_from: KindEvidence | None = None, verb_forms: dict[str, frozenset[str]] | None = None) -> dict:
    parsed: list[tuple[Record, list[tuple[str, ...]], bool]] = []
    unparsed = 0
    for db in dbs:
        if db.stem in LEFT_OUT:
            continue
        for headword, kind, printed, pos, labels, definition, definition_zh in _records(db):
            if NOTE_START.match(printed.strip()):
                continue
            p = parse(printed, headword, evidence)
            variants = [v for v in p.variants if is_phrase(v)]
            if not p.variants:
                unparsed += 1
                continue
            if not variants:
                continue
            parsed.append((Record(db.stem, headword, printed, kind, pos, json.loads(labels), definition,
                                  definition_zh), variants, p.separable))
    groups = group(parsed, lemmas)
    printed = [g for g in groups if not all(r.dictionary in KEYWORDS_ONLY for r in g.records)]
    keywords_only = len(groups) - len(printed)  # only COBUILD's bold words: no reliable text
    groups = printed
    with fresh_db(out, SCHEMA) as con:
        kinds = Counter()
        for i, (text, g) in enumerate(sorted(((canonical(g, evidence), g) for g in groups), key=lambda t: t[0]), 1):
            dictionaries = sorted({r.dictionary for r in g.records})
            publishers = {PUBLISHER.get(d, d) for d in dictionaries}
            kind = kind_of(g.records, text)
            if kind == "idiom" and any(_looks_phrasal(tuple(v.split())) for v in g.variants) \
                    and any(normalize(r.pos).tags & {"VERB"} for r in g.records):
                kind = "phrasal_verb"
            verbs = {r.headword.split()[0].lower() for r in g.records if r.headword.split()}
            if kind == "phrasal_verb" and not any(phrasal_shape(v, verbs, lemmas, verb_forms) for v in g.variants):
                kind = "idiom"  # filed under a phrasal verb, but a sentence: "not know what {sb} sees in {sb}"
            kind = refine_kind(kind, text, dictionaries, lemmas, kinds_from)
            kinds[kind] += 1
            ranked = sorted(g.records, key=lambda r: _preference(r.dictionary))
            definition = next((r.definition for r in ranked if r.definition), "")
            definition_zh = next((r.definition_zh for r in ranked if r.definition_zh), "")
            slots = sorted({t for v in g.variants for t in v.split() if t.startswith("{")})
            labels = sorted({label for r in g.records for label in r.labels})
            con.execute("INSERT INTO phrase VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (i, text, kind, int(g.separable), json.dumps(slots), json.dumps(sorted(g.variants)),
                         json.dumps(sorted({r.headword for r in g.records})), json.dumps(dictionaries),
                         len(dictionaries), len(publishers), json.dumps(labels, ensure_ascii=False), definition,
                         definition_zh, json.dumps(sorted({r.printed for r in g.records}), ensure_ascii=False)))
            con.executemany("INSERT INTO variant VALUES (?,?,?,?)",
                            [(i, v, " ".join(key(tuple(v.split()), lemmas)), len(ds)) for v, ds in g.variants.items()])
    return {"phrases": len(groups), "records": len(parsed), "unparsed": unparsed,
            "keywords_only": keywords_only, **dict(kinds)}


def export_jsonl(db: Path, out: Path) -> int:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cur = con.execute("SELECT id, text, kind, separable, slots, variants, headwords, dictionaries, n, publishers, "
                      "labels, definition, definition_zh FROM phrase ORDER BY id")
    names = [d[0] for d in cur.description]
    tmp = out.with_name(out.name + ".part")
    n = 0
    with tmp.open("w", encoding="utf-8") as f:
        for row in cur:
            r = dict(zip(names, row))
            for k in ("slots", "variants", "headwords", "dictionaries", "labels"):
                r[k] = json.loads(r[k])
            r["separable"] = bool(r["separable"])
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    con.close()
    tmp.replace(out)
    return n


def main() -> None:
    inflections = DATA / "inflections.db"
    if not inflections.exists():
        sys.exit(f"{inflections} is missing: build the inflection inventory first (inventory/inflections.py)")
    grammar = DATA / "grammar.db"
    if not grammar.exists():
        sys.exit(f"{grammar} is missing: build the grammar patterns first (inventory/usage.py)")
    summary = build(sorted(STRUCTURED.glob("*.db")), lemma_index(inflections), DATA / "phrases.db", Evidence(),
                    kind_evidence(ROOT / "corpus" / "unified.db", grammar), verb_form_index(inflections))
    export_jsonl(DATA / "phrases.db", DATA / "phrases.jsonl")
    print(json.dumps(summary, indent=1), file=sys.stderr)


if __name__ == "__main__":
    main()
