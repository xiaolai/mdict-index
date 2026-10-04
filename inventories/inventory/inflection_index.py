"""Readers of the inflection inventory (data/inflections.db) for the inventories built on it:
form -> lemma (lemma_index), form -> the verbs it is a form of (verb_form_index), lemma -> its
parts of speech (pos_index) and its forms (forms_index), and every lemma and form
(inflection_words). families.lemma_index is another thing: every lemma of each form, built
from a forms mapping, not read from the database.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path


def lemma_index(inflections_db: Path) -> dict[str, str]:
    """form -> lemma, for reducing phrase words; a word that is itself a lemma is kept."""
    con = sqlite3.connect(f"file:{inflections_db}?mode=ro", uri=True)
    lemmas = {lemma for (lemma,) in con.execute("SELECT DISTINCT lemma FROM lemma")}
    index: dict[str, str] = {}
    for form, lemma in con.execute("SELECT form, lemma FROM inflection ORDER BY n DESC, lemma"):
        if form not in lemmas:
            index.setdefault(form, lemma)
    con.close()
    return index


def verb_form_index(inflections_db: Path) -> dict[str, frozenset[str]]:
    """form -> the verbs it is a form of, those that are lemmas too (strung: string)."""
    con = sqlite3.connect(f"file:{inflections_db}?mode=ro", uri=True)
    index: dict[str, set[str]] = defaultdict(set)
    for form, lemma in con.execute("SELECT form, lemma FROM inflection WHERE upos = 'VERB'"):
        index[form].add(lemma)
    con.close()
    return {form: frozenset(verbs) for form, verbs in index.items()}


def pos_index(inflections_db: Path) -> dict[str, dict[str, int]]:
    """lemma -> the parts of speech the dictionaries give it, with how many give each."""
    con = sqlite3.connect(f"file:{inflections_db}?mode=ro", uri=True)
    index: dict[str, dict[str, int]] = defaultdict(dict)
    for lemma, upos, n in con.execute("SELECT lemma, upos, n FROM lemma"):
        index[lemma][upos] = n
    con.close()
    return dict(index)


def forms_index(inflections_db: Path) -> dict[str, frozenset[str]]:
    """lemma -> its inflected forms."""
    con = sqlite3.connect(f"file:{inflections_db}?mode=ro", uri=True)
    index: dict[str, set[str]] = defaultdict(set)
    for form, lemma in con.execute("SELECT form, lemma FROM inflection"):
        index[lemma].add(form)
    con.close()
    return {k: frozenset(v) for k, v in index.items()}


def inflection_words(inflections_db: Path) -> set[str]:
    """Every lemma and every inflected form."""
    words: set[str] = set()
    con = sqlite3.connect(f"file:{inflections_db}?mode=ro", uri=True)
    words |= {w for (w,) in con.execute("SELECT DISTINCT lemma FROM lemma")}
    words |= {w for (w,) in con.execute("SELECT DISTINCT form FROM inflection")}
    con.close()
    return words
