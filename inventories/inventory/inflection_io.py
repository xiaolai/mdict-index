"""The inflection inventory's database input and output: the entries of the parsed dictionaries
(_entries: headword, parts of speech, forms, final stress, countability), the schema of
data/inflections.db and its writing (_write), and the TSV export.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

from inventory.db import fresh_db
from inventory.inflect import final_stress_from_ipa
from inventory.pos import normalize

_MASS = frozenset("uncountable u mass noun mass noncount 不可数".split()) | {"mass noun", "uncountable noun"}
_COUNT = frozenset("countable c count noun count".split()) | {"count noun", "countable noun", "countable, uncountable",
                                                             "c, u", "count, noncount"}


def countability(pos: str, labels: list[str]) -> str:
    """"Count", "Mass" or "" for one noun sense, from its printed part of speech and labels."""
    feature = normalize(pos).features.get("Countability", "") if pos else ""
    marks = {label.strip().lower() for label in labels}
    if marks & _COUNT or feature == "Count":
        return "Count"
    if marks & _MASS or feature == "Mass":
        return "Mass"
    return ""


class _Entry(NamedTuple):
    headword: str
    order: list[str]           # its parts of speech, printed order first
    forms: list[str]
    final_stress: bool | None  # from the first UK pronunciation, else the first one
    mass_only: bool            # every noun sense uncountable
    plural_noun: bool          # printed a plural noun ("plural noun", "N-PLURAL")


def _entries(db: Path) -> Iterable[_Entry]:
    """Every content entry of a parsed dictionary."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        senses: dict[int, set[str]] = defaultdict(set)
        counts: dict[int, set[str]] = defaultdict(set)
        plural: set[int] = set()
        for entry_id, pos, labels in con.execute(
                "SELECT entry_id, pos, labels FROM s_sense WHERE kind = 'sense'"):
            if pos:
                senses[entry_id] |= normalize(pos).tags
                plural |= {entry_id} if _plural_noun(pos) else set()
            counts[entry_id].add(countability(pos, json.loads(labels)))
        prons: dict[int, str] = {}
        uk: set[int] = set()
        for entry_id, ipa, region in con.execute("SELECT entry_id, ipa, region FROM s_pron ORDER BY entry_id, ord"):
            if entry_id in uk:
                continue
            if region == "uk":
                prons[entry_id] = ipa
                uk.add(entry_id)
            else:
                prons.setdefault(entry_id, ipa)
        for entry_id, headword, pos, forms in con.execute(
                "SELECT entry_id, headword, pos, forms FROM s_entry WHERE stub = ''"):
            tags = set(senses.get(entry_id, ()))
            for p in json.loads(pos):
                tags |= normalize(p).tags
            ipa = prons.get(entry_id, "")
            mass_only = counts.get(entry_id) == {"Mass"}
            printed = [t for p in json.loads(pos) for t in sorted(normalize(p).tags)]
            order = list(dict.fromkeys(printed + sorted(tags)))  # printed order first
            plural_noun = entry_id in plural or any(_plural_noun(p) for p in json.loads(pos))
            yield _Entry(headword, order, json.loads(forms), final_stress_from_ipa(ipa) if ipa else None, mass_only,
                         plural_noun)
    finally:
        con.close()


def _plural_noun(printed: str) -> bool:
    """A part of speech printed as a plural noun ("plural noun", "N-PLURAL", "npl")."""
    found = normalize(printed)
    return "NOUN" in found.tags and found.features.get("Number") == "Plur"


SCHEMA = """
CREATE TABLE inflection (form TEXT NOT NULL, lemma TEXT NOT NULL, upos TEXT NOT NULL, slot TEXT NOT NULL,
  region TEXT NOT NULL, kind TEXT NOT NULL, source TEXT NOT NULL, dictionaries TEXT NOT NULL, n INTEGER NOT NULL,
  PRIMARY KEY (form, lemma, upos, slot, region)) WITHOUT ROWID;
CREATE TABLE other (form TEXT NOT NULL, lemma TEXT NOT NULL, kind TEXT NOT NULL, dictionaries TEXT NOT NULL,
  n INTEGER NOT NULL, PRIMARY KEY (form, lemma, kind)) WITHOUT ROWID;
CREATE TABLE lemma (lemma TEXT NOT NULL, upos TEXT NOT NULL, dictionaries TEXT NOT NULL, n INTEGER NOT NULL,
  PRIMARY KEY (lemma, upos)) WITHOUT ROWID;
CREATE INDEX inflection_form ON inflection(form);
CREATE INDEX inflection_lemma ON inflection(lemma);
"""


def _write(out: Path, attested: dict[tuple, set[str]], generated: dict[tuple, set[str]],
           others: dict[tuple, set[str]], lemmas: dict[tuple, set[str]]) -> dict:
    """Writes the inventory; returns the counts by source and kind."""
    with fresh_db(out, SCHEMA) as con:
        con.executemany("INSERT INTO inflection VALUES (?,?,?,?,?,?,?,?,?)",
                        [(*k[:5], k[5], "attested", json.dumps(sorted(v)), len(v)) for k, v in attested.items()]
                        + [(*k[:5], k[5], "rule", "[]", 0) for k in generated if k not in attested])
        con.executemany("INSERT INTO other VALUES (?,?,?,?,?)",
                        [(*k, json.dumps(sorted(v)), len(v)) for k, v in others.items()])
        con.executemany("INSERT INTO lemma VALUES (?,?,?,?)",
                        [(*k, json.dumps(sorted(v)), len(v)) for k, v in lemmas.items()])
        summary = {row[0]: row[1] for row in con.execute("SELECT source || '/' || kind, count(*) FROM inflection GROUP BY 1")}
        summary.update({f"other/{row[0]}": row[1] for row in con.execute("SELECT kind, count(*) FROM other GROUP BY 1")})
        summary["lemmas"] = con.execute("SELECT count(DISTINCT lemma) FROM lemma").fetchone()[0]
    return summary


def export_tsv(db: Path, out: Path) -> int:
    """form, lemma, upos, slot, region, kind, source, n: one row per inflection, sorted by form."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    tmp = out.with_name(out.name + ".part")
    n = 0
    with tmp.open("w", encoding="utf-8") as f:
        f.write("form\tlemma\tupos\tslot\tregion\tkind\tsource\tn\n")
        for row in con.execute("SELECT form, lemma, upos, slot, region, kind, source, n FROM inflection "
                               "ORDER BY form, lemma, upos, slot"):
            f.write("\t".join(map(str, row)) + "\n")
            n += 1
    con.close()
    tmp.replace(out)
    return n
