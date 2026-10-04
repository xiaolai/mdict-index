"""The kind of a phrase: phrasal verb, name, formula, compound, idiom (kind_of), and the
corrections refine_kind makes from other evidence (kind_evidence): a noun-shaped NCECD "idiom"
another dictionary has as a headword is a compound, an idiom that is one word with its slots
is a grammar pattern when the dictionaries give that word the pattern. Used by
inventory/phrases.py.
"""
from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from inventory.pos import normalize

if TYPE_CHECKING:
    from inventory.phrases import Record

KEYWORDS_ONLY = frozenset({"cobuild", "cobuild-ec"})               # bold words, not the phrase as printed
FORMULA_POS = re.compile(r"convention|exclamation|interjection|exclam|sentence", re.I)


def kind_of(records: list[Record], text: str) -> str:
    if any(r.kind == "phrasal_verb" or "phrasal" in r.pos.lower() for r in records):
        return "phrasal_verb"
    printed = [r.printed for r in records if r.dictionary not in KEYWORDS_ONLY] or [r.printed for r in records]
    if all(_is_name(p) for p in printed):
        return "name"
    if any(FORMULA_POS.search(r.pos) for r in records) or any(p.rstrip().endswith(("?", "!")) for p in printed):
        return "formula"
    if all(r.pos and normalize(r.pos).tags == {"NOUN"} for r in records) and _noun_shaped(text):
        return "compound"  # the great apes, cubic zirconia: a noun compound, not an idiom
    return "idiom"


# Words a noun compound does not contain. Phrase senses often carry their entry's part of
# speech ("be over the limit" under the noun "limit"), so the words must agree.
_NOT_IN_COMPOUNDS = frozenset(
    "to in into on onto at by for from with out off up down about over under through as like than "
    "some any many much no every each this that these those my his her its our their your "
    "i you he she it we they me him us them be is are was were been being am have has had do does did "
    "not can could will would shall should may might must if when".split())


def _noun_shaped(text: str) -> bool:
    """An optional article, then content words, "of" or "and" only inside: debt of honour."""
    words = text.split()
    if words and words[0] in ("the", "a", "an"):
        words = words[1:]
    inner_article = any(w in ("the", "a", "an") and words[i - 1] != "of" for i, w in enumerate(words) if i)
    return (bool(words) and not any(w.startswith("{") or w in _NOT_IN_COMPOUNDS for w in words)
            and not inner_article  # ease the helm: a verb and its object; the first epistle of john is fine
            and words[0] not in ("of", "and") and words[-1] not in ("of", "and"))


class KindEvidence(NamedTuple):
    """What corrects the kinds of NCECD's phrases (measured on NCECD-only phrases)."""
    headwords: frozenset[str]           # multiword headwords of the other dictionaries
    grammar: dict[str, frozenset[str]]  # word -> its grammar patterns (data/grammar.db)


_PATTERN_WORDS = frozenset("a an the of to in on at by for from with be and or not no as into onto it do doing "
                           "about over upon through against".split())


def valency_pattern(text: str, lemmas: dict[str, str]) -> tuple[str, str] | None:
    """(word, pattern) of a phrase that is one content word with its slots, in COBUILD's
    notation, the class left as "~": "endeavour to do {sth}" -> ("endeavour", "~ to-inf")."""
    tokens = text.split()
    if tokens[:1] == ["be"]:
        tokens = tokens[1:]
    content = [i for i, t in enumerate(tokens) if not t.startswith("{") and t not in _PATTERN_WORDS]
    if len(content) != 1 or not any(t.startswith("{") for t in tokens):
        return None
    i = content[0]
    shape = " ".join(tokens[:i] + ["~"] + tokens[i + 1:])
    shape = re.sub(r"\bto do \{(?:sth|\.\.\.)\}", "to-inf", shape)
    shape = re.sub(r"\bdoing \{sth\}", "-ing", shape)
    shape = re.sub(r"\{(?:sb|sth|sb/sth|oneself)\}", "n", shape).replace("{...}", "cl")
    return lemmas.get(tokens[i], tokens[i]), shape


def attested_pattern(text: str, lemmas: dict[str, str], grammar: dict[str, frozenset[str]]) -> str:
    """The grammar pattern a phrase is, when the dictionaries give its word that pattern."""
    if text.split()[-1] == "{oneself}":
        return ""  # the slot filled for good: "full of {oneself}" is conceited, not the grammar of "full"
    found = valency_pattern(text, lemmas)
    if not found:
        return ""
    word, shape = found
    for pattern in sorted(grammar.get(word, ())):
        core = re.sub(r"^(?:usu|oft|also)\s+", "", pattern)
        for cls in ("V", "ADJ", "N"):
            wanted = shape.replace("~", cls)
            if core in (wanted, "v-link " + wanted, wanted.replace(" n", "", 1)):
                return core
    return ""


def refine_kind(kind: str, text: str, dictionaries: list[str], lemmas: dict[str, str],
                evidence: KindEvidence | None) -> str:
    """NCECD lists terms (pectoralis minor) among its phrases: an "idiom" only NCECD gives is a
    compound when it is noun-shaped and another dictionary has it as a headword. Any
    dictionary may list a word's grammar (endeavour to do sth, LDOCE's proceed to do sth): an
    idiom that is one word with its slots is a pattern when the dictionaries give that word
    that grammar pattern."""
    if evidence is None or kind != "idiom":
        return kind
    if dictionaries == ["ncecd"] and _noun_shaped(text) and text in evidence.headwords:
        return "compound"  # NCECD only: elsewhere a noun-shaped idiom is often a true one (red herring)
    if attested_pattern(text, lemmas, evidence.grammar):
        return "pattern"
    return kind


def kind_evidence(unified: Path, grammar_db: Path) -> KindEvidence:
    con = sqlite3.connect(f"file:{unified}?mode=ro", uri=True)
    ncecd = con.execute("SELECT id FROM dictionary WHERE name = '新世纪英汉'").fetchone()
    headwords = frozenset(n for (n,) in con.execute("SELECT DISTINCT norm FROM entry WHERE dict_id != ? AND norm LIKE "
                                                    "'% %'", (ncecd[0] if ncecd else -1,)))
    con.close()
    con = sqlite3.connect(f"file:{grammar_db}?mode=ro", uri=True)
    grammar: dict[str, set[str]] = defaultdict(set)
    for word, pattern in con.execute("SELECT word, pattern FROM pattern"):
        grammar[word].add(pattern)
    con.close()
    return KindEvidence(headwords, {w: frozenset(p) for w, p in grammar.items()})


def _is_name(printed: str) -> bool:
    """The North Sea, the Royal Academy: every word but function words capitalised."""
    words = [w for w in re.findall(r"[^\W\d_][\w'-]*", printed) if w.lower() not in {"the", "of", "and", "de", "la"}]
    return len(words) >= 1 and all(w[0].isupper() for w in words)
