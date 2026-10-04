"""Parts of speech as the dictionaries print them, normalised to Universal POS tags.

The dictionaries use 743 different strings ("n.", "N-COUNT", "tr. & intr.v.", "noun plural
but singular in construction", "adjective (or adverb)", 名词...). They are compositional, so
they are read as words from a small vocabulary rather than listed one by one: each word
contributes tags (UPOS: NOUN, VERB, ADJ, ADV, ADP, CCONJ, SCONJ, PRON, DET, INTJ, NUM, PROPN,
SYM, X) and features (Transitivity, Number, Countability, Kind for abbreviations, affixes and
phrases). A string with no recognised word yields no tags, which callers count and report.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# word -> (tags, features). Words are matched after lowercasing, splitting on spaces, commas,
# semicolons, "&", "/", "+", parentheses and hyphens that join COBUILD codes (N-COUNT).
_WORDS: dict[str, tuple[tuple[str, ...], dict[str, str]]] = {}


def _add(words: str, tags: tuple[str, ...] = (), **features: str) -> None:
    for w in words.split():
        _WORDS[w] = (tags, features)


_add("noun n n. nouns substantive 名词 nn", ("NOUN",))
_add("npl npl. pl.n. pl. plural", ("NOUN",), Number="Plur")
_add("sing singular sing.", (), Number="Sing")
_add("count countable c", (), Countability="Count")
_add("uncount uncountable noncount mass u var", (), Countability="Mass")
_add("verb v v. vb vb. 动词 v-link v-erg v-recip link aux auxiliary modal", ("VERB",))
_add("vt vt. tr tr. tr.v. transitive t", ("VERB",), Transitivity="Transitive")
_add("vi vi. intr intr. intr.v. intransitive i", ("VERB",), Transitivity="Intransitive")
_add("adjective adj adj. a. a 形容词 adj-graded", ("ADJ",))
_add("adverb adv adv. ad. 副词 adv-graded", ("ADV",))
_add("preposition prep prep. 介词", ("ADP",))
_add("conjunction conj conj. 连词 conj-coord", ("CCONJ",))
_add("conj-subord subordinating", ("SCONJ",))
_add("pronoun pron pron. 代词", ("PRON",))
_add("determiner det det. article predeterminer quantifier", ("DET",))
_add("interjection interj interj. int. exclamation exclam convention 感叹词 substitute", ("INTJ",))
_add("connector connective", ("ADV",), Kind="Connector")
_add("number num num. numeral cardinal ordinal", ("NUM",))
_add("proper geographical biographical n-proper n-title n-in-names", ("PROPN",))
_add("symbol", ("SYM",))
_add("abbreviation abbr abbr. abbrev abbrev. acronym initialism contraction short", ("X",), Kind="Abbreviation")
_add("prefix pref pref. prefixes", ("X",), Kind="Prefix")
_add("suffix suff suff. suf. suf suffixes", ("X",), Kind="Suffix")
_add("combining comb comb. comb.form combiningform", ("X",), Kind="CombiningForm")
_add("phrase phr phr. phrasal phrase.", (), Kind="Phrase")
_add("prep-phrase", ("ADP",), Kind="Phrase")  # COBUILD: a whole code keeps what its parts say (PREP + PHRASE)
_add("trademark", ("PROPN",), Kind="Trademark")
_add("foreign", ("X",), Kind="Foreign")
_add("suffix.", ("X",), Kind="Suffix")
_add("pluralnoun", ("NOUN",), Number="Plur")
_add("modifier", ("ADJ",), Kind="Modifier")  # a noun used before another noun
_add("colour color", ("ADJ", "NOUN"))       # COBUILD: colour words, adjective and noun
_add("aux.v. v.aux. v.aux", ("VERB",))
_add("quant predet art. def.art. indef.art.", ("DET",))
_add("ord fraction", ("NUM",))
_add("quest", ("PRON",))                     # COBUILD: question words
_add("infinitive infinitivemarker neg", ("PART",))
_add("service certification collective", ("PROPN",), Kind="Trademark")
_add("comp. comp", (), Kind="Compound")      # Chambers: a compound listed under its first element

# "noun plural but singular in construction" (news, mathematics): plural in form, singular in agreement
_CONSTRUCTION = re.compile(r"\b(singular or plural|singular|plural)\s+in\s+construction\b", re.I)
_AGREEMENT = {"singular": "Sing", "plural": "Plur", "singular or plural": "Both"}
_SPLIT = re.compile(r"[\s,;&/+()]+")
_HYPHEN = re.compile(r"(?<=[a-z])-(?=[a-z])")  # joins COBUILD codes: N-COUNT, unless the whole code is a word
_QUALIFIED = re.compile(r"\bsubordinating (?:conjunction|conj\.?)(?!\w)", re.I)  # one tag, not SCONJ and CCONJ
_TRAILING_NUMBER = re.compile(r"\d+$")  # "n.1", "adj.2": homograph numbers
_FUSED = {  # abbreviations printed without spaces
    "tr.v.": ("tr.", "v."), "intr.v.": ("intr.", "v."), "pl.n.": ("pl.", "n."),
    "vt.sep.": ("vt.",), "vt.fus.": ("vt.",),
}


@dataclass(frozen=True)
class Pos:
    tags: frozenset[str]
    features: dict[str, str] = field(default_factory=dict)

    @property
    def known(self) -> bool:
        return bool(self.tags or self.features)


def _words(printed: str) -> list[str]:
    out = []
    for token in _SPLIT.split(printed.strip().lower()):
        whole = _TRAILING_NUMBER.sub("", token)
        for w in [whole] if whole in _WORDS else _HYPHEN.split(token):  # CONJ-SUBORD is SCONJ, not CONJ + SUBORD
            w = _TRAILING_NUMBER.sub("", w) if not w.isdigit() else ""
            if not w:
                continue
            out += list(_FUSED.get(w, (w,)))
    return out


def normalize(printed: str) -> Pos:
    """The tags and features of a printed part of speech. Phrasal verbs are VERB with Kind=Phrase;
    COBUILD's N-COUNT is NOUN with Countability=Count."""
    tags: set[str] = set()
    features: dict[str, str] = {}
    printed = _QUALIFIED.sub("conj-subord", " ".join(printed.split()))  # "singular or  plural" is "singular or plural"
    construction = _CONSTRUCTION.search(printed)
    if construction:
        features["Agreement"] = _AGREEMENT[construction.group(1).lower()]
        printed = printed[:construction.start()] + printed[construction.end():]
    words = _words(printed)
    for w in words:
        if w in _WORDS:
            t, f = _WORDS[w]
        elif "-" in w and all(p in _WORDS for p in w.split("-")):  # COBUILD: N-COUNT, V-ERG, ADJ-GRADED
            t, f = (), {}
            for p in w.split("-"):
                t += _WORDS[p][0]
                f = {**f, **_WORDS[p][1]}
        else:
            continue
        tags.update(t)
        for k, v in f.items():  # "tr. & intr.v.": both transitivities
            features[k] = v if features.get(k, v) == v else "Both"
    if "X" in tags and len(tags) > 1 and features.get("Kind") in ("Prefix", "Suffix", "CombiningForm"):
        tags.discard("NOUN")  # "noun combining form": an affix that forms nouns
    if "PROPN" in tags:
        tags.discard("NOUN")
    return Pos(frozenset(tags), features)
