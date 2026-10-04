"""Reading an IPA transcription: its syllable nuclei, where the stress falls, its segments.

    analyse("əbˈdʒekt")      -> Stress(syllables=2, primary=2, secondary=(), segments="əbdʒekt")
    analyse("ˌekəˈnɒmɪk◂")   -> Stress(syllables=4, primary=3, secondary=(1,), segments="ekənɒmɪk")

A nucleus is a vowel, a diphthong (eɪ aɪ ɔɪ aʊ əʊ oʊ ɪə eə ʊə ɛə), or a syllabic consonant
(n̩). A long vowel ends its nucleus (being: biː.ɪŋ, two). Stress marks, syllable dots and
spaces separate nuclei; a colon is a length mark (ˈbɜ:d = ˈbɜːd). The primary stress is the
syllable after the ˈ mark: one more than the nuclei before it. The segments keep one mark, a
"." between two vowels of different nuclei (hiatus: ˈe.ɪ, biː.ɪŋ), printed or not, so that a
hiatus is no diphthong (eɪ). A transcription of two or more syllables without a ˈ, or one only
partly given ("-ˈnɑː.mɪk", "ˈɑːb-"), gives no analysis.
"""
from __future__ import annotations

import re
from typing import NamedTuple

VOWELS = frozenset("iɪeɛæaɑɒɔoʊuʌəɜɐyøœɘɵɤɯᵻᵿɚɝ")
DIPHTHONGS = frozenset({"eɪ", "aɪ", "ɔɪ", "aʊ", "əʊ", "oʊ", "ɪə", "eə", "ʊə", "ɛə", "ɛɪ", "ɑɪ", "ɒɪ", "ɑʊ", "ɔʊ"})
MODIFIERS = frozenset("ː̯̃˞ˑ")
SYLLABIC = "̩"   # n̩, l̩
BREAKS = frozenset(".ˈˌ ‿")
_DROP = re.compile("[◂▸()|/\\[\\]§*'‘’]|<[^>]*>")


class Stress(NamedTuple):
    syllables: int
    primary: int                  # 1-based syllable carrying the primary stress
    secondary: tuple[int, ...]
    segments: str                 # the sounds, marks and breaks removed but "." at a hiatus


def variants(field: str) -> list[str]:
    """The transcriptions one field gives: "ˈɒbdʒɪkt, -dʒekt" -> both, the second partial."""
    field = field.replace("\xa0", " ")
    return [" ".join(v.split()) for v in re.split("[,;；，]", field) if v.strip()]


def analyse(ipa: str) -> Stress | None:
    text = _DROP.sub("", ipa).strip().replace(":", "ː")
    if not text or text.startswith("-") or text.endswith("-") or "…" in text:
        return None
    nuclei = 0
    primary = 0
    secondary: list[int] = []
    prev = ""            # the vowel letters of the current nucleus, "" between nuclei
    long_vowel = False
    segments: list[str] = []
    after_vowel = False  # the last sound kept was a vowel (or its length / nasal mark)
    for ch in text:
        if ch in BREAKS:
            if ch == "ˈ":
                primary = nuclei + 1
            elif ch == "ˌ":
                secondary.append(nuclei + 1)
            prev, long_vowel = "", False
        elif ch in VOWELS:
            if prev and not long_vowel and prev[-1] + ch in DIPHTHONGS and len(prev) == 1:
                prev += ch                                 # a diphthong: one nucleus
            else:                                          # aɪə: a third vowel is its own nucleus
                prev, long_vowel = ch, False
                nuclei += 1
                if after_vowel:
                    segments.append(".")                   # a hiatus
            segments.append(ch)
            after_vowel = True
        elif ch in MODIFIERS:
            if ch == "ː":
                long_vowel = True
            if ch != "ˑ":
                segments.append(ch)
        elif ch == SYLLABIC:
            nuclei += 1
            prev, long_vowel = "", False
            segments.append(ch)
            after_vowel = False
        else:
            prev, long_vowel = "", False
            if ch != "-":
                segments.append(ch)
                after_vowel = False
    if nuclei == 0:
        return None
    if not primary:
        if nuclei > 1:
            return None
        primary = 1
    if primary > nuclei:
        return None
    return Stress(nuclei, primary, tuple(s for s in secondary if s <= nuclei), "".join(segments))


_WEAK = re.compile("ᵻ|(?<![eaɔoɒɛɑ])ɪ(?![əː])|(?<![eaɔoəɑɒ])i(?!ː)|ə(?![ʊɪ])")  # not inside a diphthong


def weak(segments: str) -> str:
    """Segments with the weak vowels one (ɪ ᵻ i ə): transcriptions write them variously. A weak
    vowel in hiatus is weak too (ˈe.ɪ, ˈe.ə); the key keeps no hiatus mark."""
    return _WEAK.sub("ə", segments.replace("ᵿ", "ʊ")).replace(".", "")


_VOICING = {frozenset(p) for p in (("s", "z"), ("θ", "ð"), ("f", "v"))}
_VOWEL_CLASS = re.compile(f"[{''.join(sorted(VOWELS))}ː]")


def contrast(a: str, b: str) -> str:
    """What separates two segment strings of one word: voicing of the last consonant (use
    /s/ ~ /z/), the -ate ending (estimate -ət ~ -eɪt), vowels only, or other segments."""
    if a == b:
        return ""
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    if len(a) == len(b) and n == len(a) - 1 and frozenset((a[-1], b[-1])) in _VOICING:
        return "voicing"
    ending = lambda w: "eɪt" if w.endswith(("eɪt", "ɛɪt")) else "ət" if w.endswith(("ət", "ɪt")) else ""
    if {ending(a), ending(b)} == {"eɪt", "ət"} and \
            _VOWEL_CLASS.sub("", a[:-3 if ending(a) == "eɪt" else -2]) == \
            _VOWEL_CLASS.sub("", b[:-3 if ending(b) == "eɪt" else -2]):
        return "ate"  # estimate n. -ət, v. -eɪt (the stem's own vowels may vary too)
    if _VOWEL_CLASS.sub("", a) == _VOWEL_CLASS.sub("", b):
        return "vowel"
    return "segment"
