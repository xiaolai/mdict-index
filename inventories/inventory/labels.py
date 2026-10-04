"""The dictionaries' usage labels, read into (axis, value) pairs.

    "informal"                   register: informal
    "Brit. informal"             region: GB; register: informal
    "chiefly N. Amer."           region: NAm (qualifiers like chiefly, esp., mainly are dropped)
    "美口"                        region: US; register: informal
    "Medicine", "医"              domain: medicine
    "C", "countable"             grammar: N count
    "+ to infinitive"            grammar: ~ to-inf  (~ is the word's own class: V, N, ADJ)
    "usu ADJ n" (COBUILD)        grammar: ADJ n

Axes: register, attitude, time, frequency, region, domain, language (of origin), use
(figurative), author (Chambers' Shakespeare, Spenser...), form (capitalized), kind
(trademark, saying), grammar. Grammar values follow COBUILD's pattern notation (V n,
V to-inf, N uncount, ADJ n, v-link ADJ). The OED's structural markers (α., (a), Compounds)
are not labels: `normalize` returns them as axis "none".

A label is read part by part (split at commas, "and", "&", "/", semicolons; Chinese labels
into known abbreviations). A label with a part not understood gives no pairs at all, so
nothing is half-read.
"""
from __future__ import annotations

import re

from inventory.label_grammar import GRAMMAR, _cobuild
from inventory.label_tables import (ATTITUDE, AUTHOR, DOMAIN, FORM, FREQUENCY, KIND, LANGUAGE, NOISE, REGION,
                                    REGISTER, TIME, USE, _FIELD, Label)
from inventory.label_zh import _CJK, _chinese

_PREPOSITIONS = frozenset("about above across after against along among around as at before behind between by for "
                          "from in into like of off on onto out over past round than through to towards under "
                          "upon with within without".split())
_QUALIFIER = re.compile(r"^(?:chiefly|mainly|mostly|esp\.?|especially|usually|usu\.?|often|sometimes|also|now|both|and|"
                        r"in|widely|very|rather|somewhat|slightly|increasingly|"
                        r"generally|occasionally|freq\.?|frequently)\s+", re.I)
_HEDGES = frozenset("chiefly mainly mostly esp especially usually usu often sometimes also now widely generally "
                    "occasionally freq frequently".split())  # not "formerly", "orig": those change what is said
_PROTECT = ((re.compile(r"\badverb\s*/\s*preposition\b|\badv\.?\s*/\s*prep\b\.?", re.I), "adverb or preposition"),
            (re.compile(r"\b(?:usu(?:ally|\.)? )?in (?:questions and negatives|negatives and questions)\b", re.I),
             "with brd-neg"))
_SPLIT = re.compile(r"\s*(?:,|;|\s&\s|\sand\s|/|(?<=\w)\s\+\s(?=\w))\s*", re.I)  # US AND AUSTRALIAN ENGLISH
_SPLIT_OR = re.compile(r"\s*(?:,|;|\s&\s|\sand\s|\sor\s|/|(?<=\w)\s\+\s(?=\w))\s*", re.I)  # "informal + old-fashioned": two labels
_TABLES = (REGISTER, ATTITUDE, TIME, FREQUENCY, REGION, LANGUAGE, USE, AUTHOR, FORM, KIND, GRAMMAR, DOMAIN)

_JUNK = re.compile(r"\d{3,4}|\[see |see below|see above|【|^(?:or|all meanings|all senses|in the sense|"
                   r"in the second sense|in some|either |another reading)\b|^plural [a-z]+, |[,;] *[,;]")  # the OED's dates, cross-references and stray fragments


def _lookup(part: str) -> tuple[Label, ...] | None:
    key = re.sub(r"\s+", " ", part.strip().rstrip(".:").strip().lower())
    if key[:1] + key[-1:] in ("()", "[]"):
        key = key[1:-1].strip()
    key = key.lstrip("& ").strip()
    if not key:
        return ()
    if key in NOISE or re.fullmatch(r"[a-z]\.|\([a-z]\)", part.strip()):  # the OED's "a.", "(b)": sense divisions
        return (Label("none", key),)
    for table in _TABLES:
        if key in table:
            return table[key]
    if re.fullmatch(r"(?:the )?[a-z]-", key):  # "also M-": a form with a capital
        return (Label("form", "capitalized"),)
    if _JUNK.search(key):
        return (Label("none", key),)
    if m := re.fullmatch(r"(?:often |usu |usually )?foll(?:owed)?\.? by (\w+)", key):  # "often foll by up"
        return (Label("grammar", f"~ {m.group(1)}"),)
    if m := re.fullmatch(r"((?:[\w'.-]+ ){1,3})(?:sl|slang)", key):  # "comput sl", "British vulgar slang"
        prefix = m.group(1).split()
        known = _lookup(" ".join(prefix)) or _two_words(prefix)
        if known is None:
            return None  # "zorblax slang": a part not understood, so nothing is read
        return tuple(l for l in known if l.axis != "none") + (Label("register", "slang"),)
    if m := re.fullmatch(r"(?:in )?(?:the )?names of (\w+(?: \w+)?)", key):  # "now chiefly in the names of buildings"
        return Label("kind", "in names"), Label("selection", m.group(1))
    if m := re.fullmatch(r"\+\s*of ([\w ,]+)", key):  # "+of animal": what it goes with
        return tuple(Label("selection", w.strip()) for w in m.group(1).split(","))
    if m := re.fullmatch(r"\+\s*([\w]+(?:, [\w]+)+)|([\w]+(?:, [\w]+)+) \+", key):  # "+ person, animal"
        return tuple(Label("selection", w.strip()) for w in (m.group(1) or m.group(2)).split(","))
    if key in _PREPOSITIONS:  # "countable + of": the second part
        return (Label("grammar", f"~ {key}"),)
    if m := re.fullmatch(r"\+\s*(\w+)", key):  # "+ between": a preposition; "+ person": what it goes with
        word = m.group(1)
        return (Label("grammar", f"~ {word}"),) if word in _PREPOSITIONS else (Label("selection", word),)
    if m := re.fullmatch(r"of ((?:(?:a|an|the) )?\w+(?:, (?:(?:a|an|the) )?\w+)+),? etc", key):  # of institutions, the state, etc
        return tuple(Label("selection", re.sub(r"^(?:a|an|the) ", "", w.strip())) for w in m.group(1).split(","))
    if m := re.fullmatch(r"(\w+)\s*\+|of (?:a |an |the )?(\w+(?: \w+)?)", key):  # "person +", "of a horse"
        return (Label("selection", m.group(1) or m.group(2)),)
    words = key.split()
    # a field name no table lists: "Cell Biology", "Classical Prosody"; not a label with known
    # words in it ("informal mainly disapproving", "gr grammar"), a list, or "in platonism"
    looks_like_field = (len(words) <= 3 and not re.search(r"\band\b|&", key)
                        and words[0] not in ("in", "of", "for", "the", "with")
                        and not any(_known(w) for w in words[:-1]) and not _known(words[-1], domain=False))
    if looks_like_field and (_FIELD.match(key) or " ".join(words[1:]) in DOMAIN
                             or len(words) == 2 and words[-1] in DOMAIN):
        return (Label("domain", key),)
    return None


def _known(word: str, domain: bool = True) -> bool:
    """Whether a word is a label on its own (in any table but, optionally, the domains)."""
    tables = _TABLES if domain else tuple(t for t in _TABLES if t is not DOMAIN)
    return word in NOISE or any(word in t for t in tables)


def _unqualified(part: str) -> str:
    while (stripped := _QUALIFIER.sub("", part)) != part:
        part = stripped
    return part


def normalize(label: str) -> tuple[Label, ...]:
    """The (axis, value) pairs of one printed label; () when any part is not understood."""
    label = label.strip()
    if not label:
        return ()
    if _CJK.search(label):
        return _chinese(label) or ()
    for read in (lambda: _cobuild(label), lambda: _lookup(label), lambda: _lookup(_unqualified(label))):
        found = read()
        if found:
            return found
    for pattern, whole in _PROTECT:  # phrases the splitters would cut: "adverb/preposition"
        label = pattern.sub(whole, label)
    inner = re.fullmatch(r"(.*?)\s*\((.*)\)\s*", label)  # "colloquial (originally U.S.)"
    for split in (_SPLIT, _SPLIT_OR):  # "or" inside one label first (singular or plural verb), then between two
        parts = split.split(inner.group(1)) + [inner.group(2)] if inner else split.split(label)
        read = _read_parts(parts)
        if read is not None:
            return read
    return ()


def _read_parts(parts: list[str]) -> tuple[Label, ...] | None:
    out: list[Label] = []
    for raw_part in parts:
        raw_part = re.sub(r"^\s*(?:originally|orig\.?) and (?=(?:chiefly|mainly|now|still)\b)", "", raw_part, flags=re.I)
        if re.match(r"\s*(?:originally|orig\.?)(?:\s|$)", raw_part, re.I):
            break  # "(originally North American)", "orig, from": where the word came from, not its use
        found = _lookup(raw_part.strip())  # "usually passive" before "passive": the qualifier can be the value
        part = _unqualified(raw_part.strip())
        found = found if found is not None else _lookup(part)
        if found is None:
            found = _two_words(part.split())  # "Brit. informal", "US sl", "N. Amer. informal"
        if found is None:
            return None
        out.extend(found)
    real = [l for l in out if l.axis != "none"]
    return tuple(dict.fromkeys(real or out))


def _two_words(words: list[str]) -> tuple[Label, ...] | None:
    """A part read as two labels side by side; a half that is only noise does not count, or
    "formal or literary" would read as formal alone."""
    kept = [w for w in words if w.lower().rstrip(".") not in _HEDGES]
    if kept != words:  # "informal mainly disapproving", "BrE also": a hedge says how often, not what
        if not kept:
            return None
        whole = _lookup(" ".join(kept))
        return whole if whole is not None else _two_words(kept)
    noise = lambda found: found is not None and all(l.axis == "none" for l in found)
    for cut in range(len(words) - 1, 0, -1):
        left, right = _lookup(" ".join(words[:cut])), _lookup(" ".join(words[cut:]))
        if noise(left) or noise(right):
            continue
        if left is not None and right is not None:
            return left + right
        if left is not None:
            rest = _two_words(words[cut:])
            if rest is not None:
                return left + rest
    return None
