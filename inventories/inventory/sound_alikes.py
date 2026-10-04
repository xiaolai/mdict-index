"""Sound-alikes: common words two dictionaries or more transcribe alike, weak vowels before the
stress read as one (affect əˈfekt, effect ɪˈfekt). Spelling variants and a word with its -s are
not sound-alikes. Used by inventory/confusables.py, which files each pair as a confusion of kind
"sound_alike".
"""
from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from collections.abc import Iterator
from itertools import combinations
from pathlib import Path

from inventory.ipa import VOWELS, analyse, weak
from inventory.spelling import is_variant, spelled_alike

_REDUCED = frozenset("əɚᵻᵿ")  # schwa, r-coloured schwa, the reduced ɪ/ʊ; every other vowel is full (ɝ in sir)
_FULL_VOWEL = re.compile(f"[{''.join(sorted(VOWELS - _REDUCED))}]")


def _weak_form(a) -> bool:
    """A reduced form: one syllable whose only vowel is reduced, or a syllabic consonant."""
    return a.syllables == 1 and not _FULL_VOWEL.search(a.segments)


def _sound_key(ipa: str) -> str:
    """The sounds of a transcription; weak vowels as one only before the stressed syllable
    (affect əˈfekt, effect ɪˈfekt), where transcriptions differ; the stressed vowel and what
    follows must match exactly (eat/it, fuller/fully are not homophones)."""
    text = re.sub(r"[ˌ.\s|()◂]", "", ipa)
    before, _, after = text.rpartition("ˈ")
    return weak(before.replace(":", "ː")) + "ˈ" + after.replace(":", "ː")  # a colon for length, in some


def sound_alikes(pron_db: Path, common: frozenset[str],
                 variants: set[frozenset]) -> Iterator[tuple[str, tuple[str, ...]]]:
    """(dictionary, words) for each pair of common words two dictionaries or more transcribe
    alike, weak vowels as one."""
    con = sqlite3.connect(f"file:{pron_db}?mode=ro", uri=True)
    heard: dict[tuple, list] = defaultdict(list)
    for word, ipa, dictionary, region in con.execute("SELECT word, ipa, dictionary, region FROM pron"):
        if word in common and (a := analyse(ipa)):
            heard[(dictionary, region, word)].append((a, ipa))
    con.close()
    groups: dict[tuple, set[str]] = defaultdict(set)
    for (dictionary, region, word), analyses in heard.items():
        if len(word) < 2 or word in ("a", "an"):
            continue  # letter names, the article's two forms
        full = [x for x in analyses if not _weak_form(x[0])] or analyses  # as /æz/, not its weak /əz/
        a, ipa = full[0]  # the word's main pronunciation: not lead's rare Lied /liːd/ against lied
        groups[(dictionary, region, a.primary, a.syllables, _sound_key(ipa))].add(word)
    seen: dict[frozenset, set[str]] = defaultdict(set)
    for (dictionary, *_), words in groups.items():
        for a, b in combinations(sorted(words), 2):
            pair = frozenset((a, b))
            if pair in variants or is_variant(a, b) or spelled_alike(a, b) or a.rstrip("s") == b.rstrip("s"):
                continue
            seen[pair].add(dictionary)
    for pair, dictionaries in seen.items():
        if len(dictionaries) >= 2:
            for d in sorted(dictionaries):
                yield d, tuple(sorted(pair))
