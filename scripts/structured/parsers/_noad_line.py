"""noad sense-line reader: the part-of-speech tables and abbreviation expansion, and the reader that
takes a sense line's leading number, parts of speech, labels and forms off its definition."""
from __future__ import annotations

import copy
import re

from structured.markup import clean, text

_POS = frozenset({
    "noun", "verb", "adjective", "adverb", "exclamation", "preposition", "pronoun", "conjunction",
    "determiner", "abbreviation", "symbol", "prefix", "suffix", "combining form", "plural noun",
    "predeterminer", "contraction", "auxiliary verb", "modal verb", "article", "number", "cardinal number",
    "ordinal number", "possessive determiner", "possessive pronoun", "infinitive marker", "interjection",
})
_NUMBER = re.compile(r"^\s*(\d+)\)\s*")
# separators and qualifier words between leading labels
_QUALIFIERS = re.compile(r"^[\s,;]*(?:(chiefly|esp\.|especially|often|usu\.|usually|also|or|and)[\s,;]*)*$")
# span.p without a title prints a part of speech (or several), sometimes fused with a
# region: "plural n.", "n. & adj.", "n. Scottish"
_POS_ABBR = {
    "plural n.": "plural noun", "comb. form": "combining form", "modal v.": "modal verb",
    "auxiliary v.": "auxiliary verb", "relative adv.": "relative adverb", "relative pron.": "relative pronoun",
    "possessive pron.": "possessive pronoun", "possessive adj.": "possessive adjective",
    "predic. adj.": "predicative adjective", "attrib. adj.": "attributive adjective",
    "postpositive adj.": "postpositive adjective", "prep. phrase": "prepositional phrase",
    "n.": "noun", "v.": "verb", "adj.": "adjective", "adv.": "adverb", "prep.": "preposition",
    "conj.": "conjunction", "pron.": "pronoun", "exclam.": "exclamation", "abbr.": "abbreviation",
}
_POS_ABBR_RE = re.compile(r"^\s*(" + "|".join(re.escape(k) for k in sorted(_POS_ABBR, key=len, reverse=True))
                          + r")(?=\s|,|&|$)\s*,?\s*&?\s*")


def _cls(el) -> str:
    return (el.get("class") or "") if isinstance(el.tag, str) else ""


def _spelling(value: str) -> str:
    return clean(value.replace("·", ""))


def _expanded(el) -> str:
    """Text of `el` with every abbreviation (span.p) replaced by its title. An abbreviation is a word of its
    own even where the source prints it against the next one ("[with<span>obj.</span>]" is "with object")."""
    el = copy.deepcopy(el)
    for sp in el.iter("span"):
        if _cls(sp) == "p" and sp.get("title"):
            prev = sp.getprevious()
            before = (prev.tail if prev is not None else sp.getparent().text if sp is not el else "") or ""
            after = sp.tail or ""
            sp.text = (" " if before[-1:].isalnum() else "") + sp.get("title") + (" " if after[:1].isalnum() else "")
            for child in list(sp):
                sp.remove(child)
    return text(el)


def _untitled(value: str) -> tuple[str, str]:
    """(part of speech, remaining label) of an untitled abbreviation."""
    parts, rest = [], value
    while m := _POS_ABBR_RE.match(rest):
        parts.append(_POS_ABBR[m.group(1)])
        rest = rest[m.end():]
    return " & ".join(parts), clean(rest)


def _is_token(el) -> bool:
    """Whether `el` is a leading token of a sense line (so qualifier words before it belong
    to a label, not to the definition)."""
    if el is None or not isinstance(el.tag, str):
        return False
    return el.tag in ("i", "br") or _cls(el) in ("p", "gray", "t") or (
        _cls(el) == "color" and text(el).startswith("("))


def _qualifier_words(value: str) -> str:
    return " ".join(w for w in re.findall(r"[\w.]+", value) if w not in ("or", "and", "also"))


def _read_line(line) -> tuple[str, list[str], list[str], list[str], str]:
    """(number, parts of speech, labels, forms, definition) of a sense line.

    Leading tokens (number, "■", abbreviations, italic labels, inflections, a bracketed
    pronunciation) are consumed together with the separators and qualifier words
    between them ("archaic or historical", "chiefly Brit."); the definition starts at
    the first other text. A grammar label may also close the line."""
    line = copy.deepcopy(line)
    for e in line.iter():  # "[]" is a bracket the conversion emptied; it is never content
        if isinstance(e.tag, str):
            e.text = e.text.replace("[]", "") if e.text else e.text
        e.tail = e.tail.replace("[]", "") if e.tail else e.tail
    for t in [e for e in line.iter("span") if _cls(e) == "t"]:  # "[<span class=t>…</span>]"
        prev = t.getprevious()
        if prev is not None and (prev.tail or "").rstrip().endswith("["):
            prev.tail = prev.tail.rstrip()[:-1]
        elif prev is None and t.getparent() is line and (line.text or "").rstrip().endswith("["):
            line.text = line.text.rstrip()[:-1]
        if (t.tail or "").lstrip().startswith("]"):
            t.tail = t.tail.lstrip()[1:]
    number, pos, labels, forms = "", [], [], []
    head = line.text or ""
    if m := _NUMBER.match(head):
        number, head = m.group(1), head[m.end():]
    first = next((c for c in line if isinstance(c.tag, str)), None)
    leading = _QUALIFIERS.match(head) is not None and (not clean(head) or _is_token(first))
    qualifier = _qualifier_words(head) if leading else ""
    line.text = "" if leading else head
    for child in list(line):
        if not isinstance(child.tag, str):
            continue
        name = _cls(child)
        tail = child.tail or ""
        if not leading:
            if child.tag == "i" and _expanded(child).startswith("[") and not clean(tail):
                labels.append(_expanded(child).strip("[] "))  # a trailing grammar label
                child.drop_tree()
            continue
        value = ""
        if name == "p" and child.get("title"):
            value = _expanded(child)
        elif name == "p":
            untitled_pos, value = _untitled(text(child))
            if untitled_pos:
                pos.append(untitled_pos)
        elif child.tag == "i":
            shown = _expanded(child)
            # "(weigh something out)" is a form group, "(also X)" a variant: neither is a label
            value = "" if shown.startswith("(") else shown.strip("[] ")
        elif name == "color" and text(child).startswith("("):
            # "(pl. sons of bitches (sons of bitch·es))": the parenthesized b is the syllabified repeat
            forms += [f for f in (_spelling(text(b)) for b in child.iter("b")) if f and not f.startswith("(")]
        elif not (name in ("gray", "t") or child.tag == "br"):
            leading = False
            continue
        if value in _POS:
            pos.append(value)
        elif value:
            labels.append(clean(f"{qualifier} {value}"))
            qualifier = ""
        if _QUALIFIERS.match(tail) is None or (clean(tail) and not _is_token(child.getnext())):
            leading = False  # the tail is where the definition starts ("abbr. especially")
        else:
            qualifier = clean(f"{qualifier} {_qualifier_words(tail)}")
            child.tail = ""
        child.drop_tree()
    return number, pos, labels, forms, text(line)
