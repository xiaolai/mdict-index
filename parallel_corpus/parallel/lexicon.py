"""Does the Chinese translate the English? A score from a bilingual lexicon.

    PYTHONPATH=scripts:parallel_corpus .venv/bin/python parallel_corpus/parallel/lexicon.py     # build parallel_corpus/data/lexicon.json.gz

The lexicon maps English words to the Chinese character bigrams of their glosses, taken from
the parsed English-Chinese dictionaries (s_sense.definition_zh in corpus/_structured/unified.db/*.db).
A pair's score is the share of its English content words, among those the lexicon knows,
with a gloss bigram present in the Chinese (converted to simplified characters, as the
glosses are). Bigrams tolerate rephrasing (演奏台 matches a
translation saying 在台上演奏); function words and unknown words (usually names) are left out.

Used to choose a dictionary's orientation (English then Chinese, or Chinese then English) and
to tell translations from Chinese text that merely sits next to English.
"""
from __future__ import annotations

import gzip
import json
import re
import sqlite3
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "parallel_corpus"))
from parallel.corpus import _EN_FUNCTION, to_simplified  # noqa: E402  (the same function-word list)

from parallel import DATA  # noqa: E402

LEXICON = DATA / "lexicon.json.gz"
from build_structured import STRUCTURED  # noqa: E402  the parsed dictionaries, where the build writes them
SOURCES = ("cobuild-ec", "oalecd", "ldoce-ec", "ncecd", "yhdcd", "odecn")
MAX_BIGRAMS = 60             # per word: the commonest senses' glosses come first
_CJK_RUN = re.compile(r"[㐀-鿿]+")
_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")  # any case: "CATS" is one word, not four letters
_NOTE = re.compile(r"[（(〈【\[][^）)〉】\]]*[）)〉】\]]")
_SUFFIXES = (("ies", "y"), ("ied", "y"), ("ing", ""), ("ing", "e"), ("ed", ""), ("ed", "e"), ("es", ""), ("s", ""),
             ("er", ""), ("est", ""), ("ly", ""), ("'s", ""))


def gloss_bigrams(definition_zh: str) -> list[str]:
    """Character bigrams of a Chinese gloss, bracketed notes dropped; a single character counts as itself."""
    out = []
    for run in _CJK_RUN.findall(_NOTE.sub(" ", definition_zh)):
        for g in [run] if len(run) == 1 else (run[i:i + 2] for i in range(len(run) - 1)):
            if g not in out:  # checked one by one: a run repeats its own bigrams (哈哈哈哈)
                out.append(g)
    return out


def build(dbs: list[Path]) -> dict[str, list[str]]:
    """English word (lowercase, single words only) -> gloss bigrams, from structured databases."""
    lexicon: dict[str, list[str]] = {}
    for db in dbs:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute("SELECT e.headword, e.forms, s.definition_zh FROM s_sense s "
                           "JOIN s_entry e ON e.entry_id = s.entry_id WHERE s.definition_zh <> '' "
                           "ORDER BY e.entry_id, s.ord")
        for headword, forms, definition_zh in rows:
            grams = gloss_bigrams(definition_zh)
            if not grams:  # nothing Chinese to match: a word known only this way would never align
                continue
            for word in [headword, *json.loads(forms)]:
                word = word.lower()
                if not word.isalpha() or word in _EN_FUNCTION:
                    continue
                known = lexicon.setdefault(word, [])
                known += [g for g in grams if g not in known][:MAX_BIGRAMS - len(known)]
        con.close()
    return lexicon


@lru_cache(maxsize=1)
def _lexicon() -> dict[str, frozenset[str]]:
    if not LEXICON.exists():
        raise FileNotFoundError(f"{LEXICON}: build it first (parallel_corpus/parallel/lexicon.py)")
    with gzip.open(LEXICON, "rt", encoding="utf-8") as f:
        return {w: frozenset(g) for w, g in json.load(f).items()}


def _lookup(word: str, lexicon) -> frozenset[str] | None:
    word = word.lower()
    if word in lexicon:
        return lexicon[word]
    for suffix, replacement in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            stem = word[:-len(suffix)] + replacement
            if stem in lexicon:
                return lexicon[stem]
    return None


def score(en: str, zh: str, lexicon=None) -> tuple[float, int]:
    """(share of known English content words whose gloss appears in zh, how many were known)."""
    lexicon = _lexicon() if lexicon is None else lexicon
    zh_grams = set()
    for run in _CJK_RUN.findall(to_simplified(zh)):  # the glosses are simplified: 窗戶 must match 窗户
        zh_grams.update(run)
        zh_grams.update(run[i:i + 2] for i in range(len(run) - 1))
    known = matched = 0
    for word in {w.lower() for w in _WORD.findall(en)}:
        if word in _EN_FUNCTION or len(word) < 3:
            continue
        grams = _lookup(word, lexicon)
        if not grams:  # unknown, or known without a gloss to look for
            continue
        known += 1
        matched += bool(grams & zh_grams)
    return (matched / known if known else 0.0), known


def main() -> None:
    dbs = [STRUCTURED / f"{key}.db" for key in SOURCES]
    missing = [str(db) for db in dbs if not db.exists()]
    if missing:
        sys.exit(f"missing structured databases (build_structured.py): {missing}")
    lexicon = build(dbs)
    LEXICON.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(LEXICON, "wt", encoding="utf-8") as f:
        json.dump(lexicon, f, ensure_ascii=False)
    print(f"{len(lexicon):,} words -> {LEXICON}", file=sys.stderr)


if __name__ == "__main__":
    main()
