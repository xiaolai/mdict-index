"""Parts of speech in collocation patterns: the closed-class words, the open-class words the
dictionaries tag, which collocate parts of speech can relate to a base (_RELATIONS), the
collocate's part of speech and position (_collocate_pos), and the base's when no source gives
it (base_from_pattern). Used by inventory/collocations.py.
"""
from __future__ import annotations

from inventory.collocation_sources import QUANT, UNTYPED

BASE = "~"
_LEFT_OUT_OF_KEYS = frozenset({"a", "an", "the", "{poss}", "{...}"})
_OPEN = ("NOUN", "VERB", "ADJ", "ADV")

_RELATIONS = {  # (base, collocate, side) -> relation; side "*" is either
    ("NOUN", "ADJ", "*"): "adj_noun", ("NOUN", "VERB", "before"): "verb_obj", ("NOUN", "VERB", "after"): "subj_verb",
    ("NOUN", "NOUN", "*"): "noun_noun", ("NOUN", "ADP", "*"): "prep", ("NOUN", QUANT, "*"): "quantifier",
    ("VERB", "ADV", "*"): "adv_verb", ("VERB", "NOUN", "after"): "verb_obj", ("VERB", "NOUN", "before"): "subj_verb",
    ("VERB", "VERB", "*"): "verb_verb", ("VERB", "ADP", "*"): "prep", ("VERB", "ADJ", "*"): "verb_adj",
    ("ADJ", "ADV", "*"): "adv_adj", ("ADJ", "NOUN", "*"): "adj_noun", ("ADJ", "VERB", "*"): "verb_adj",
    ("ADJ", "ADP", "*"): "prep", ("ADJ", "ADJ", "*"): "adj_adj",
    ("ADV", "VERB", "*"): "adv_verb", ("ADV", "ADJ", "*"): "adv_adj",
    # verb_prep (a verb reaching the base through a preposition) is set by _through_preposition
}


_FUNCTION = frozenset("be is are was were been being am there it to".split()) | _LEFT_OUT_OF_KEYS
# Closed-class words: the dictionaries' parts of speech for them are unreliable ("of" is a verb
# in "could of"), so they are listed.
_PREPOSITIONS = frozenset(
    "about above across after against along amid among around as at before behind below beneath beside between "
    "beyond by down during for from in inside into like near of off on onto out outside over past round since "
    "than through throughout till to toward towards under until up upon with within without".split())
_CLOSED_WORDS = _PREPOSITIONS | frozenset(
    "a an the this that these those my your his her its our their some any no every each all both either neither "
    "i you he she it we they me him us them myself yourself himself herself itself ourselves themselves "
    "and or but nor so if when while because although though whether not".split())
_CLOSED = {"ADP", "DET", "PRON", "CCONJ", "SCONJ", "AUX", "PART"}
_BEFORE_NOUNS = frozenset("a an the {poss} {one's} {sb's} {sth's} my his her its our their this that these those "
                          "some any no every each".split())


def _is_content(token: str) -> bool:
    return BASE not in token and not token.startswith("{") and token not in _FUNCTION


_BE = frozenset("be is are was were been being am".split())


def _tags(word: str, pos_of: dict[str, set[str]], lemmas: dict[str, str]) -> set[str]:
    if word in _CLOSED_WORDS:
        return set()
    tags = set(pos_of.get(lemmas.get(word, word), ()) or pos_of.get(word, ()))
    return set() if tags & _CLOSED else tags & set(_OPEN)


def _choices(base_upos: str) -> list[str]:
    """The collocate parts of speech that can relate to a base of this part of speech."""
    return [c for c in _OPEN if any(k[0] == base_upos and k[1] == c for k in _RELATIONS)] or list(_OPEN)


def _weight(word: str, upos: str, pos_of, lemmas: dict[str, str]) -> int:
    """How many dictionaries give the word this part of speech (1 when only the set is known)."""
    tags = pos_of.get(lemmas.get(word, word)) or pos_of.get(word) or {}
    return tags.get(upos, 0) if isinstance(tags, dict) else int(upos in tags)


def _mostly_noun(word: str, pos_of, lemmas: dict[str, str]) -> bool:
    """A word the dictionaries make a noun at least twice as often as an adjective: a noun
    modifier (hardback, weather), not an adjective (fancy, individual: near ties)."""
    return _weight(word, "NOUN", pos_of, lemmas) >= 2 * max(1, _weight(word, "ADJ", pos_of, lemmas))


def _collocate_pos(pattern: tuple[str, ...], hint: str, pos_of: dict[str, set[str]],
                   lemmas: dict[str, str], at: int | None = None, base_upos: str = "") -> tuple[str, int]:
    """The collocate's part of speech and position. The collocate is the open-class word
    nearest the base, passing over an adverb that modifies another word (an oddly assorted
    group); its part of speech is the dictionaries' when they give one, else the pattern's:
    before a determiner a verb (set the ~), before a verb base its subject (a noun), just
    before a noun base an adjective, after an article a noun. Prepositions only: ADP."""
    choices = hint.split("|") if hint else _choices(base_upos)
    fallback = choices[0] if hint else UNTYPED
    at = next((i for i, t in enumerate(pattern) if BASE in t), 0) if at is None else at
    content = [(i, t) for i, t in enumerate(pattern) if _is_content(t)]
    if not content:
        return fallback, 0
    open_words = sorted((abs(i - at), i) for i, t in content if _tags(t, pos_of, lemmas))
    if not open_words:
        return ("ADP", content[0][0]) if all(t in _PREPOSITIONS for _, t in content) else (fallback, content[0][0])
    not_adverbs = [(d, i) for d, i in open_words if _tags(pattern[i], pos_of, lemmas) != {"ADV"}]
    i = (not_adverbs or open_words)[0][1]
    tags = _tags(pattern[i], pos_of, lemmas)
    fits = [c for c in choices if c in tags] if not hint else [c for c in choices if c in tags] or choices[:1]
    between = pattern[min(i, at) + 1:max(i, at)]
    if len(fits) > 1:
        if "ADJ" in fits and i == at - 1 and base_upos == "NOUN":
            # a word just before a noun base modifies it: an adjective (a different ~), or a noun
            # when the dictionaries mostly make it one (a mountain ~)
            noun = "NOUN" in fits and _mostly_noun(pattern[i], pos_of, lemmas)
            fits = ["NOUN" if noun else "ADJ"]
        elif i < at and "VERB" in fits and (
                any(t in _BEFORE_NOUNS or t.startswith("{") for t in between)
                or (i == 0 and any(t in _PREPOSITIONS for t in between))):
            fits = ["VERB"]        # set the ~, give {sb} a ~, pack {one's} ~; made to ~ (a verb first)
        elif i < at and base_upos == "VERB" and "NOUN" in fits:
            fits = ["NOUN"]        # a question mark ~ {sth}: the subject
        elif i > at and base_upos == "VERB" and "NOUN" in fits:
            fits = ["NOUN"]        # ~ {sb} {sth}, ~ attention: the object
        elif "NOUN" in fits and i > 0 and pattern[i - 1] in _BEFORE_NOUNS:
            fits = ["NOUN"]
        elif "ADJ" in fits and i == at - 1:
            fits = ["ADJ"]         # lavish ~: a word just before the base modifies it
        elif i > at and base_upos == "ADJ" and "NOUN" in fits:
            fits = ["NOUN"]        # an oddly ~ group: the noun it modifies
        elif i > at and base_upos == "ADV" and "ADJ" in fits:
            fits = ["ADJ"]         # a ~ wise person: the adjective it modifies
    return (fits[0] if len(fits) == 1 or (fits and hint) else fallback), i


def base_from_pattern(pattern: tuple[str, ...], at: int, base: str, pos_of: dict[str, set[str]],
                      lemmas: dict[str, str], located: str = "") -> str:
    """The base's part of speech when no source gives it, from where it stands: after an
    article or possessive a noun (a different ~), after "be" or before an object a verb
    (be ~ in a coup, overturn a ~), before a noun an adjective (dishevelled hair)."""
    if pattern[at] != BASE:
        return ""  # inside a hyphenated word: an ~-dinner speaker
    before = pattern[at - 1] if at > 0 else ""
    after = pattern[at + 1] if at + 1 < len(pattern) else ""
    tags = set(pos_of.get(base, ())) & set(_OPEN)
    if after and "NOUN" in _tags(after, pos_of, lemmas) and located != base and located.endswith(("ed", "ing", "en")):
        return "ADJ"  # a participle before a noun: wilted lettuce, that sinking feeling
    if before in _BEFORE_NOUNS or (at > 1 and pattern[at - 2] in _BEFORE_NOUNS and before not in _PREPOSITIONS):
        return "NOUN"  # a ~; a different ~
    if before in _BE or after in _BEFORE_NOUNS or after.startswith("{"):
        return "VERB" if "VERB" in tags or not tags else "ADJ"
    if len(tags) == 1:
        return next(iter(tags))
    if after and "NOUN" in _tags(after, pos_of, lemmas) and (not tags or "ADJ" in tags):
        return "ADJ"  # dishevelled hair, that sinking feeling
    return ""
