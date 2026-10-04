"""Spelling variants: two accepted spellings of one word. is_variant knows the alternations
(colour/color, programme/program, judgement/judgment), spelled_alike the respellings no
alternation names (twocker/twoccer, cajuput/kajeput), spelling_regions which of two spellings
is British and which American. Used by the inflection, family and confusable inventories.
"""
from __future__ import annotations

import re

# Spelling alternations: British/American and other accepted respellings. Two spellings are
# variants when rewriting both the same way makes them equal; edit distance would also call
# vowel-change inflections variants (foot/feet, write/wrote).
_ALTERNATIONS = [
    (re.compile(r"[\s-]"), ""),                      # home stretch / home-stretch / homestretch
    (re.compile(r"our(?=$|s$|ed$|ing$|ful|less|ite|able)"), "or"),   # colour / color
    (re.compile(r"(?<=[^aeiou])re$"), "er"),          # centre / center
    (re.compile(r"(?<=[aiy])s(?=e$|ed$|es$|er$|ers$|ing$|ation)"), "z"),  # organise, analyse, catalyser
    (re.compile(r"ogue$"), "og"),                     # catalogue / catalog
    (re.compile(r"mme$"), "m"),                       # programme / program
    (re.compile(r"ence$"), "ense"),                   # defence / defense
    (re.compile(r"(?<=g)ement$"), "ment"),            # judgement / judgment
    (re.compile(r"ae|oe(?=[^s]|$)"), "e"),            # anaemia / anemia, foetus / fetus
    (re.compile(r"xion$"), "ction"),                  # connexion / connection
    (re.compile(r"(?<=[aeiou])ll(?=$|s$|ment|ments$)"), "l"),  # fulfil / fulfill, fulfilment / fulfillment
    (re.compile(r"^fore(?=[bcdfghjklmnpqrstvwxz])"), "for"),    # forswear / foreswear
    (re.compile(r"^e(?=[mn][bcdfgpqstvz])"), "i"),              # impale / empale, inquire / enquire
    (re.compile(r"ey$"), "ay"),                                 # grey / gray
]


def _alternation_key(word: str) -> str:
    for pattern, replacement in _ALTERNATIONS:
        word = pattern.sub(replacement, word)
    return word


def is_variant(form: str, lemma: str) -> bool:
    """Whether form spells lemma another accepted way (colour/color, programme/program)."""
    return form != lemma and _alternation_key(form.lower()) == _alternation_key(lemma.lower())


_SKELETON_SUBS = [("ph", "f"), ("ck", "k"), ("c", "k"), ("q", "k")]


def _skeleton(word: str) -> str:
    """Consonants only, c/k/q and ph/f as one, doubled letters as one: kajeput, cajuput -> kjpt."""
    w = _consonant_spelling(word)
    return w[:1] + re.sub("[aeiouy]", "", w[1:])


def _raw_skeleton(word: str) -> str:
    w = word.lower().replace("-", "").replace(" ", "")
    return w[:1] + re.sub("[aeiouy]", "", w[1:])


def _consonant_spelling(word: str) -> str:
    """c/k/q and ph/f as one, doubled letters as one; vowels kept."""
    w = word.lower().replace("-", "").replace(" ", "")
    for a, b in _SKELETON_SUBS:
        w = w.replace(a, b)
    return re.sub(r"(.)\1", r"\1", w)


def spelled_alike(a: str, b: str) -> bool:
    """Two spellings of one word no alternation names: the same once c/k, ph/f and doubled
    letters are set aside (twocker/twoccer, xerafin/xeraphin, nuggety/nuggetty), or the same
    consonants with such a respelling beside a changed vowel (cajuput/kajeput). A vowel change
    alone is another word (hexane/hexene); one word extending the other is a suffix."""
    if a == b or min(len(a), len(b)) < 4 or abs(len(a) - len(b)) > 2 or a[-1] != b[-1]:
        return False
    if a.startswith(b) or b.startswith(a):  # puckerood/puckerooed: a suffix
        return False
    if _consonant_spelling(a) == _consonant_spelling(b):
        return True
    # a vowel change counts only beside a real respelling: the raw consonants differ, the
    # normalised ones agree (cajuput/kajeput); complement/compliment differ in a vowel alone
    return _skeleton(a) == _skeleton(b) and _raw_skeleton(a) != _raw_skeleton(b)


_REGIONAL = [  # (GB pattern, US pattern): colour/color, centre/center, catalogue/catalog...
    (re.compile(r"our(?=$|s$|ed$|ing$|ful|less|ite|able)"), "or"), (re.compile(r"(?<=[^aeiou])re$"), "er"),
    (re.compile(r"ogue$"), "og"), (re.compile(r"mme$"), "m"), (re.compile(r"ence$"), "ense"),
    (re.compile(r"(?<=[aeiou])ll(?=ed|ing|er|ers)"), "l"), (re.compile(r"(?:ae|oe)(?=[^s]|$)"), "e"),
    (re.compile(r"(?<=g)ement$"), "ment")]


def spelling_regions(a: str, b: str) -> tuple[str, str]:
    """(region of a, region of b) when a known alternation tells them apart: GB and US."""
    for pattern, us in _REGIONAL:
        if pattern.search(a) and pattern.sub(us, a) == b:
            return "GB", "US"
        if pattern.search(b) and pattern.sub(us, b) == a:
            return "US", "GB"
    return "", ""
