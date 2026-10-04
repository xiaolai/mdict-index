"""Check every built inventory against its invariants; exit 1 on any violation.

    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/check.py

Each check is a query that must return no rows (or a condition that must hold). Run it after
a rebuild: a build that quietly writes empty fields, dangling references or impossible
values passes its own run but fails here. So does one that writes nothing: an inventory's
main tables must hold rows, or every query above them returns none and proves nothing.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "inventories"), str(ROOT / "scripts")]
from inventory import DATA  # noqa: E402

RELATIONS = ("adj_noun", "verb_obj", "subj_verb", "noun_noun", "quantifier", "prep", "verb_prep", "adv_verb",
             "adv_adj", "verb_adj", "verb_verb", "adj_adj", "phrase", "untyped")
FAMILY = ("suffixed", "prefixed", "sibling", "compound", "conversion", "inflection", "variant", "related", "family",
          "opposite")
KINDS = ("idiom", "phrasal_verb", "formula", "name", "compound", "pattern")
AXES = ("register", "attitude", "time", "frequency", "region", "domain", "selection", "language", "use", "form",
        "kind", "author")
CHANGES = ("stress", "stress (optional)", "vowel", "ate", "voicing", "segment")
SCHEMES = {"oxford3000": "a1 a2 b1 b2", "oxford5000": "b2 c1", "cefr": "a1 a2 b1 b2 c1 c2", "opal": "written spoken",
           "academic": "yes", "core": "high medium low", "spoken": "S1 S2 S3", "written": "W1 W2 W3", "awl": "yes",
           "frequency_band": "1 2 3 4 5", "stars": "1 2 3", "oed_band": "1 2 3 4 5 6 7 8"}


def _in(values) -> str:
    return "(" + ",".join("'" + v.replace("'", "''") + "'" for v in values) + ")"


CHECKS: dict[str, list[tuple[str, str]]] = {
    "inflections.db": [
        ("empty form or lemma", "SELECT * FROM inflection WHERE form = '' OR lemma = ''"),
        ("unknown slot", "SELECT * FROM inflection WHERE slot NOT IN ('Plur','3Sg','Past','PastPart','PresPart','Pres','Cmp','Sup')"),
        ("unknown source", "SELECT * FROM inflection WHERE source NOT IN ('attested','rule')"),
        ("rule rows claim dictionaries", "SELECT * FROM inflection WHERE source = 'rule' AND n > 0"),
    ],
    "phrases.db": [
        ("empty text", "SELECT * FROM phrase WHERE trim(text) = ''"),
        ("unknown kind", f"SELECT * FROM phrase WHERE kind NOT IN {_in(KINDS)}"),
        ("more publishers than dictionaries", "SELECT * FROM phrase WHERE publishers > json_array_length(dictionaries)"),
        ("variant of no phrase", "SELECT * FROM variant WHERE phrase_id NOT IN (SELECT id FROM phrase)"),
        ("phrase without variants", "SELECT * FROM phrase WHERE id NOT IN (SELECT phrase_id FROM variant)"),
    ],
    "collocations.db": [
        ("pattern without the base", "SELECT * FROM collocation WHERE pattern NOT LIKE '%~%'"),
        ("unknown relation", f"SELECT * FROM collocation WHERE relation NOT IN {_in(RELATIONS)}"),
        ("unknown word order", "SELECT * FROM collocation WHERE word_order NOT IN ('fixed','free')"),
        ("canonical not among its patterns",
         "SELECT * FROM collocation c WHERE NOT EXISTS (SELECT 1 FROM json_each(c.patterns) WHERE value = c.pattern)"),
        ("pattern of no collocation", "SELECT * FROM pattern WHERE collocation_id NOT IN (SELECT id FROM collocation)"),
        ("fewer records than dictionaries", "SELECT * FROM collocation WHERE n < json_array_length(dictionaries)"),
    ],
    "labels.db": [
        ("unknown axis", f"SELECT * FROM label WHERE axis NOT IN {_in(AXES)}"),
        ("share out of range", "SELECT * FROM label WHERE share <= 0 OR share > 1"),
        ("n is not the dictionaries", "SELECT * FROM label WHERE n != json_array_length(dictionaries)"),
        ("empty value", "SELECT * FROM label WHERE trim(value) = ''"),
    ],
    "grammar.db": [
        ("no evidence", "SELECT * FROM pattern WHERE senses + examples = 0"),
        ("share out of range", "SELECT * FROM pattern WHERE share < 0 OR share > 1"),
        ("a class placeholder left with a known class",
         "SELECT * FROM pattern WHERE pattern LIKE '~%' AND pos IN ('VERB','NOUN','ADJ','ADV')"),
    ],
    "levels.db": [
        (f"{scheme}: unknown value", f"SELECT * FROM level WHERE scheme = '{scheme}' AND value NOT IN {_in(values.split())}")
        for scheme, values in SCHEMES.items()
    ] + [("unknown scheme", f"SELECT * FROM level WHERE scheme NOT IN {_in(SCHEMES)}")],
    "families.db": [
        ("unknown relation", f"SELECT * FROM link WHERE relation NOT IN {_in(FAMILY)}"),
        ("a word in two families", "SELECT word FROM family GROUP BY word HAVING count(DISTINCT family_id) > 1"),
        ("a family of one", "SELECT family_id FROM family GROUP BY family_id HAVING count(*) < 2"),
        ("a variant row without its link",
         "SELECT * FROM variant v WHERE NOT EXISTS (SELECT 1 FROM link l WHERE l.base = v.word AND l.member = v.variant "
         "AND l.relation = 'variant')"),
    ],
    "pronunciations.db": [
        ("stress beyond the syllables", "SELECT * FROM pron WHERE primary_stress < 1 OR primary_stress > syllables"),
        ("unknown change", f"SELECT * FROM pos_contrast WHERE change NOT IN {_in(CHANGES)}"),
        ("one part of speech against itself", "SELECT * FROM pos_contrast WHERE pos_a >= pos_b"),
        ("untagged contrast", "SELECT * FROM pos_contrast WHERE word_relation IS NULL OR word_relation NOT IN "
                              "('same word','likely different words','uncertain')"),
        ("probability out of range", "SELECT * FROM pos_contrast WHERE p_same < 0 OR p_same > 1 OR p_unrelated < 0 "
                                     "OR p_unrelated > 1"),
        ("a stress row with no dictionary", "SELECT * FROM family_stress WHERE n_moved + n_kept < 1"),
        ("shift disagrees with its counts", "SELECT * FROM family_stress WHERE shift != (n_moved > n_kept)"),
    ],
    "confusables.db": [
        ("a pair out of order or doubled", "SELECT * FROM confusable WHERE word_a >= word_b"),
        ("n is not the dictionaries", "SELECT * FROM confusable WHERE n != json_array_length(dictionaries)"),
        ("unknown kind", "SELECT * FROM confusable c WHERE EXISTS (SELECT 1 FROM json_each(c.kinds) WHERE value NOT IN "
                         "('which_word','homophone','confused','sound_alike'))"),
        ("a misspelling that lists itself as wrong",
         "SELECT * FROM misspelling m WHERE EXISTS (SELECT 1 FROM json_each(m.wrong) WHERE value = m.word)"),
        ("unknown misspelling kind", "SELECT * FROM misspelling WHERE kind NOT IN ('learner_error','misspelling','nonstandard')"),
    ],
}
# The tables each inventory exists to fill: an empty one is a failed build
CORE: dict[str, tuple[str, ...]] = {
    "inflections.db": ("inflection", "lemma"), "phrases.db": ("phrase", "variant"),
    "collocations.db": ("collocation", "pattern"), "labels.db": ("label",), "grammar.db": ("pattern",),
    "levels.db": ("level",), "families.db": ("link", "family"), "pronunciations.db": ("pron",),
    "confusables.db": ("misspelling", "confusable")}


def check_db(name: str, path: Path) -> list[str]:
    """The failures of one inventory: empty main tables, violated invariants, and queries that
    cannot run (malformed JSON, a missing table), each a failure rather than a crash."""
    failures = []
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as con:
        for table in CORE[name]:
            try:
                if con.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() is None:
                    failures.append(f"{name}: {table} is empty")
            except sqlite3.Error as error:
                failures.append(f"{name}: {table}: cannot run: {error}")
        if failures:
            return failures  # nothing to check the invariants against
        for label, query in CHECKS[name]:
            try:
                rows = con.execute(query).fetchmany(3)
                if rows:
                    total = con.execute(f"SELECT count(*) FROM ({query})").fetchone()[0]
                    failures.append(f"{name}: {label}: {total} rows, e.g. {json.dumps(rows, ensure_ascii=False)[:200]}")
            except sqlite3.Error as error:
                failures.append(f"{name}: {label}: cannot run: {error}")
    return failures


def main(data: Path = DATA) -> int:
    failures = 0
    for name, checks in CHECKS.items():
        path = data / name
        if not path.exists():
            print(f"MISSING  {name}")
            failures += 1
            continue
        found = check_db(name, path)
        for failure in found:
            print(f"FAIL     {failure}")
        failures += len(found)
        print(f"checked  {name}: {len(CORE[name])} tables, {len(checks)} invariants")
    print("all invariants hold" if not failures else f"{failures} invariant(s) violated")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
