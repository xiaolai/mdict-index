"""Regular English inflection: the forms a lemma takes when it follows the rules.

Used two ways by the inflection inventory: to recognise which slot an attested form fills
(abandons = 3rd person singular of abandon), and to generate the regular forms of lemmas no
dictionary lists forms for. Every generated form is marked as generated, never as attested.

Final-consonant doubling depends on stress (preFER -> preferred, OFFer -> offered), which the
spelling does not show; the dictionaries' IPA does, so callers pass the stressed-syllable
position when they know it. Without it, only monosyllables double. British English doubles a
final l after a single vowel regardless of stress (travelled); both spellings are produced,
the British one marked Region=GB.
"""
from __future__ import annotations

import re

from inventory.ipa import analyse

SLOTS = {
    "NOUN": ("Plur",),
    "VERB": ("3Sg", "Past", "PastPart", "PresPart"),
    "ADJ": ("Cmp", "Sup"),
}
_SIBILANT = re.compile(r"(?:s|x|z|ch|sh)$")
_CONS_Y = re.compile(r"[^aeiou]y$")
# a single vowel then a consonant (not w, x, y); the u of qu is part of the consonant (quit, equip)
_CVC = re.compile(r"(?:^|[^aeiou]|qu)[aeiou][^aeiouwxy]$")
# British English doubles a final l after one vowel sound (travel, dial, fuel), not after a
# digraph (fail, reveal, pool, cool).
_L_DOUBLES = re.compile(r"(?:(?:^|[^aeiou])[aeiou]|ia|ua|ue|io)l$")
_E_KEEP = re.compile(r"(?:ee|oe|ye|ie)$")                # agree -> agreeing, hoe -> hoeing, dye -> dyeing


def syllables(word: str) -> int:
    """Rough vowel-group count; enough to tell monosyllables from longer words."""
    groups = re.findall(r"[aeiouy]+", word.lower())
    n = len(groups)
    if word.endswith("e") and n > 1 and not word.endswith(("le", "ee", "ye")):
        n -= 1
    return max(n, 1)


def _doubles(word: str, final_stress: bool | None) -> bool:
    if not _CVC.search(word):
        return False
    if final_stress is None:
        return syllables(word) == 1
    return final_stress


def _suffix(word: str, suffix: str, final_stress: bool | None) -> list[tuple[str, str]]:
    """word + a vowel suffix (-ed, -ing, -er, -est): [(form, region)]; region "" = everywhere."""
    if suffix in ("ed", "er", "est") and word.endswith("e"):
        return [(word + suffix[1:], "")]
    if suffix == "ing" and word.endswith("ie"):
        return [(word[:-2] + "ying", "")]
    if suffix == "ing" and word.endswith("e") and not _E_KEEP.search(word) and len(word) > 2:
        return [(word[:-1] + "ing", "")]
    if suffix in ("ed", "er", "est") and _CONS_Y.search(word):
        return [(word[:-1] + "i" + suffix, "")]
    if word.endswith("c") and suffix in ("ed", "ing") and syllables(word) > 1:
        return [(word + "k" + suffix, "")]  # panic -> panicked
    if _doubles(word, final_stress):
        return [(word + word[-1] + suffix, "")]
    if suffix in ("ed", "ing") and _L_DOUBLES.search(word) and (syllables(word) > 1 or re.search(r"(?:ia|ua|ue|io)l$", word)):
        return [(word + suffix, "US"), (word + "l" + suffix, "GB")]  # traveled / travelled
    return [(word + suffix, "")]


def _s(word: str) -> str:
    if word.endswith("sis") and len(word) > 4:
        return word[:-2] + "es"  # thesis -> theses, mutagenesis -> mutageneses
    if word.endswith("z") and _doubles(word, None):
        return word + "zes"  # quiz -> quizzes, like quizzed
    if _SIBILANT.search(word):
        return word + "es"
    if _CONS_Y.search(word):
        return word[:-1] + "ies"
    if re.search(r"[^aeiou]o$", word):
        return word + "es"  # heroes; the -os exceptions (pianos) are attested in the dictionaries
    return word + "s"


def regular(lemma: str, upos: str, final_stress: bool | None = None) -> dict[str, list[tuple[str, str]]]:
    """{slot: [(form, region)]} for a lemma of the given part of speech. A hyphenated lemma inflects its
    last part (flight-test -> flight-testing); spaced and capitalised lemmas return {}."""
    m = re.fullmatch(r"((?:[a-z]+-)*)([a-z]+)", lemma)  # flight-test: the last part inflects
    if not m:
        return {}
    head, word = m.group(1), m.group(2)
    if head:
        return {slot: [(head + form, region) for form, region in forms]
                for slot, forms in regular(word, upos, final_stress).items()}
    if upos == "NOUN":
        return {"Plur": [(_s(word), "")]}
    if upos == "VERB":
        past = _suffix(word, "ed", final_stress)
        return {"3Sg": [(_s(word), "")], "Past": past, "PastPart": past, "PresPart": _suffix(word, "ing", final_stress)}
    if upos == "ADJ":
        return {"Cmp": _suffix(word, "er", final_stress), "Sup": _suffix(word, "est", final_stress)}
    return {}


def final_stress_from_ipa(ipa: str) -> bool | None:
    """Whether the last syllable carries primary stress, from an IPA transcription with ˈ marks;
    None when the transcription gives no stress mark (monosyllables usually have none) or cannot
    be read. Syllables are inventory.ipa's nuclei: a syllabic consonant counts (ˈbʌtn̩: two)."""
    ipa = ipa.split(",")[0].strip()
    if "ˈ" not in ipa:
        return None
    stress = analyse(ipa)
    return None if stress is None else stress.primary == stress.syllables
