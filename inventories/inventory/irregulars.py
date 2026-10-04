"""Irregular inflections: whether a form that fits no rule is a believable irregular one.
Suppletion (went, better) and mutation plurals (feet, mice) are closed lists; other irregular
forms keep the lemma's stem and change its ending (criterion/criteria, sing/sang), plural
patterns of borrowed nouns support a thinly attested plural (collegium/collegia), and a form one
edit from the regular one is a typo (forgotting). Used by inventory/inflections.py.
"""
from __future__ import annotations

import re

from inventory.inflect import regular


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def past_shaped(form: str, lemma: str) -> bool:
    """Could be an irregular past or participle: not a derivative of the lemma (gleamy, dribbler),
    not ending in a bare vowel (scarpa) or -s, not grown by 3+ letters unless -en (forgotten)."""
    if form.endswith("s") or form[-1] in "aiou":
        return False
    if form.startswith(lemma[:max(1, len(lemma) - 1)]) and _NOT_A_VERB_FORM.search(form) and not form.endswith("en"):
        return False
    return len(form) - len(lemma) < 3 or form.endswith(("en", "ght"))  # forgotten, bought


_NOT_A_VERB_FORM = re.compile(r"(?:er|or|ment|tion|sion|ness|ly|able|ible|ity|ism|ist|ship|ful|less|ance|ence|al|ive|y)$")


def _shared_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


_PLURAL_ENDING = re.compile(r"(?:s|a|ae|i|en|im|x|th|ot|oth|ch|ice|eet|eeth|eese|men|ple|ce|ne)$")

# Suppletion (the form shares no stem with its lemma): a closed set in English, with slots.
SUPPLETIVE: dict[tuple[str, str], tuple[str, tuple[str, ...]]] = {
    ("went", "go"): ("VERB", ("Past",)), ("was", "be"): ("VERB", ("Past",)), ("were", "be"): ("VERB", ("Past",)),
    ("am", "be"): ("VERB", ("Pres",)), ("are", "be"): ("VERB", ("Pres",)), ("is", "be"): ("VERB", ("3Sg",)),
    ("better", "good"): ("ADJ", ("Cmp",)), ("best", "good"): ("ADJ", ("Sup",)),
    ("better", "well"): ("ADV", ("Cmp",)), ("best", "well"): ("ADV", ("Sup",)),
    ("worse", "bad"): ("ADJ", ("Cmp",)), ("worst", "bad"): ("ADJ", ("Sup",)),
    ("worse", "ill"): ("ADJ", ("Cmp",)), ("worst", "ill"): ("ADJ", ("Sup",)),
    ("worse", "badly"): ("ADV", ("Cmp",)), ("worst", "badly"): ("ADV", ("Sup",)),
    ("less", "little"): ("ADJ", ("Cmp",)), ("least", "little"): ("ADJ", ("Sup",)),
    ("more", "much"): ("ADJ", ("Cmp",)), ("most", "much"): ("ADJ", ("Sup",)),
    ("more", "many"): ("ADJ", ("Cmp",)), ("most", "many"): ("ADJ", ("Sup",)),
    ("farther", "far"): ("ADJ", ("Cmp",)), ("further", "far"): ("ADJ", ("Cmp",)),
    ("farthest", "far"): ("ADJ", ("Sup",)), ("furthest", "far"): ("ADJ", ("Sup",)),
    ("people", "person"): ("NOUN", ("Plur",)),
}


# Plurals by vowel change, and other old plurals, also inside compounds (fireman, dormouse).
MUTATIONS = (("man", "men"), ("foot", "feet"), ("tooth", "teeth"), ("goose", "geese"), ("mouse", "mice"),
             ("louse", "lice"), ("penny", "pence"), ("die", "dice"), ("cow", "kine"), ("brother", "brethren"))


def _changed_part(form: str, lemma: str) -> tuple[str, str]:
    """For hyphenated compounds, the one part that changed (agents-general: agents, agent)."""
    if "-" in lemma and form.count("-") == lemma.count("-"):
        changed = [(f, l) for f, l in zip(form.split("-"), lemma.split("-")) if f != l]
        if len(changed) == 1:
            return changed[0]
    return form, lemma


def _skeleton(word: str) -> str:
    return re.sub(r"[aeiouy]+", "", word)


def keeps_consonants(form: str, lemma: str) -> bool:
    """Strong verbs change vowels and keep consonants (sing/sang/sung, write/wrote, fly/flew);
    the -ght pasts keep only the first (teach/taught, bring/brought)."""
    head = _skeleton(lemma)[:-1] or _skeleton(lemma)[:1] or lemma[:1]
    return _skeleton(form).startswith(head) or form.endswith("ght") and form[0] == lemma[0]


def plausible_irregular(form: str, lemma: str, upos: str, slot: str, n: int) -> bool:
    """Whether an irregular form is believable. Suppletion and mutation plurals come from closed
    lists. Otherwise the form keeps the lemma's stem and changes only the ending (criterion/
    criteria, wolf/wolves, fly/flown); that holds however many dictionaries list it, as a
    respelling several list (pinochle/penuchle) is still no plural: a noun's form must be
    shaped like a plural (noun_plural_shaped)."""
    if (form, lemma) in SUPPLETIVE or form == lemma and upos == "NOUN":  # suppletion; zero plural
        return True
    form, lemma = _changed_part(form, lemma)
    if upos == "NOUN":  # any number of dictionaries: a respelling is listed as readily as a plural
        return noun_plural_shaped(form, lemma)
    if len(form) < 2:
        return False
    if upos == "VERB" and slot == "3Sg" and (not form.endswith("s") or _NOT_A_VERB_FORM.search(form[:-1])):
        return False  # feeders
    if upos == "VERB" and slot in ("Past", "PastPart") and not past_shaped(form, lemma):
        return False
    if upos in ("ADJ", "ADV") and not form.endswith({"Cmp": "er", "Sup": "est"}[slot]):
        return False
    if upos == "VERB":
        if not keeps_consonants(form, lemma):  # demist is no form of defog; sang is one of sing
            return False
    elif _shared_prefix(form, lemma) < max(1, len(lemma) - 3) or len(form) > len(lemma) + 4:
        return False
    return True


# Plural patterns of borrowed nouns: (singular ending, plural ending).
PATTERN_PLURALS = (("us", "i"), ("um", "a"), ("on", "a"), ("is", "es"), ("is", "ides"), ("a", "ae"), ("a", "ata"),
                   ("ex", "ices"), ("ix", "ices"), ("yx", "yces"), ("eau", "eaux"), ("f", "ves"), ("fe", "ves"),
                   ("o", "i"), ("a", "e"), ("us", "era"), ("us", "ora"), ("en", "ina"), ("", "im"), ("", "ot"),
                   ("", "oth"), ("", "en"), ("e", "en"), ("", "ren"), ("", "ae"), ("", "i"), ("um", "ums"))


def noun_plural_shaped(form: str, lemma: str) -> bool:
    """A plural by a mutation, a borrowed pattern, or a regular-looking ending the rules did not
    give (cellos, chillies); a respelling (pita/pitta, aureola/aureole) is none of these."""
    form, lemma = _changed_part(form, lemma)
    if any(lemma.endswith(a) and form == lemma[:len(lemma) - len(a)] + b for a, b in MUTATIONS + PATTERN_PLURALS):
        return True
    return form in (lemma + "s", lemma + "es", lemma[:-1] + "ies", lemma[:-1] + "es")


def supported_by_pattern(form: str, lemma: str, upos: str, slot: str, strong: set[tuple]) -> bool:
    """For a form only one or two dictionaries give: a positive reason to believe it. Nouns follow
    a borrowed plural pattern or a mutation (collegium/collegia, junkman/junkmen); verbs are a
    prefixed well-attested irregular form (misbuild/misbuilt from build/built, in `strong`)."""
    if upos == "NOUN":
        return form == lemma or noun_plural_shaped(form, lemma)
    if upos == "VERB":
        return any(form == lemma[:-len(base)] + irregular and len(lemma) - len(base) >= 2
                   for irregular, base, pos, s in strong if pos == "VERB" and s == slot and lemma.endswith(base))
    return form.endswith({"Cmp": "er", "Sup": "est"}.get(slot, "-")) and _shared_prefix(form, lemma) >= len(lemma) - 2


def looks_like_a_typo(form: str, lemma: str, upos: str, slot: str) -> bool:
    """One edit from the regular form of the same slot: forgotting (forgetting), databasees.
    A zero plural (sheep) is the lemma itself, not a misspelling of sheeps."""
    return form != lemma and any(_edit_distance(form, f) == 1 for f, _ in regular(lemma, upos).get(slot, []))
