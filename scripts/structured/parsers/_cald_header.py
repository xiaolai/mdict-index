"""cald header lines: the font-colour and badge helpers, and the reader that takes a header line or
block header apart into its form, parts of speech, labels, variant forms and pronunciations."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from structured.markup import clean, text
from structured.model import Pron

_HEAD_COLORS = frozenset({"blue", "navy", "darkblue"})
_LABEL_COLORS = frozenset({"indigo", "darkviolet"})
_LEVEL = re.compile(r"^(?:[ABC][12]|F0)$")
_STRESS = re.compile(r"[ˈˌ·]")
# green bold words in a header are parts of speech only when they name one; the same
# style also prints labels ("informal", "specialized") and "aep" (the US pronunciation mark)
_POS_WORDS = frozenset({
    "noun", "verb", "adjective", "adverb", "phrasal verb", "suffix", "prefix", "exclamation", "preposition",
    "pronoun", "determiner", "conjunction", "number", "ordinal number", "modal verb", "auxiliary verb",
    "predeterminer", "abbreviation", "adj", "short form", "combining form", "plural noun",
})
_POS_SPLIT = re.compile(r"\s*(?:,|\bor\b|\band\b|&)\s*")
_MARK = "\ue001"  # brackets the markers that stand in for elements while reading transcriptions
_PRON_TOKEN = re.compile(r"/[^/]*/|[()]|\ue001[^\ue001]*\ue001")
_PRON_NOTES = frozenset({"STRONG", "WEAK"})


def _color(el) -> str:
    return (el.get("color") or "") if isinstance(el.tag, str) else ""


def _style(el) -> str:
    return (el.get("style") or "") if isinstance(el.tag, str) else ""


def _fonts(el, *colors: str):
    return [f for f in el.iter("font") if _color(f) in colors]


def _is_badge(el) -> bool:
    return el.tag == "span" and "background-color" in _style(el)


@dataclass
class _Header:
    form: str = ""                  # the word the header is about, stress marks removed
    pos: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    forms: list[str] = field(default_factory=list)
    prons: list[Pron] = field(default_factory=list)
    phrasal_verb: str = ""


def _expand(headword: str, form: str) -> str:
    """"-men" beside "batman" is "batmen": a suffix form replaces the aligned end of the
    headword when the two differ by at most one letter; otherwise it is dropped."""
    if not form.startswith("-") or headword.startswith("-"):
        return form
    tail = form[1:]
    if tail and len(headword) > len(tail) and sum(a != b for a, b in zip(headword[-len(tail):], tail)) <= 1:
        return headword[: -len(tail)] + tail
    return ""


def _is_pos(word: str) -> bool:
    return all(part in _POS_WORDS for part in _POS_SPLIT.split(word) if part)


def _stream(el):
    """Document-order walk: ("text", str) chunks and ("open", element) events."""
    if el.text:
        yield "text", el.text
    for child in el:
        if isinstance(child.tag, str):
            yield "open", child
            yield from _stream(child)
        if child.tail:
            yield "text", child.tail


def _prons(el) -> list[Pron]:
    """The header's pronunciations, read in order from its own text.

    British transcriptions come first and the American one follows the green "aep" mark
    (without it the transcription serves both); a sub "STRONG" / "WEAK" before a
    transcription is its note. Transcriptions and sound links inside "( … )" belong to
    a plural or variant ("(PLURAL -men /-mən/)") and are skipped, as is text inside
    labels, so "[+ sing/pl verb]" cannot pose as a transcription."""
    parts = [el.text or ""]
    for child in el:
        if not isinstance(child.tag, str):
            parts.append(child.tail or "")
            continue
        value = text(child)
        if child.tag == "sup":
            parts.append(value)  # part of a transcription: /ˌnʌm.bə<sup>r</sup>/
        elif child.tag == "sub" and value in _PRON_NOTES:
            parts.append(f"{_MARK}note:{value}{_MARK}")
        elif (_color(child) == "green" or _is_badge(child)) and value == "aep":  # some badges print it
            parts.append(f"{_MARK}us{_MARK}")
        elif child.tag == "a" and (href := child.get("href") or "").startswith("sound://"):
            img = next(iter(child.iter("img")), None)
            src = (img.get("src") or "") if img is not None else ""
            if src.startswith(("snd_uk", "snd_us")):
                parts.append(f"{_MARK}sound:{src[4:6]}:{href}{_MARK}")
        parts.append(child.tail or "")
    region, depth, note = "uk", 0, ""
    ipas: dict[str, list[tuple[str, str]]] = {"uk": [], "us": []}
    sounds: dict[str, str] = {}
    for token in _PRON_TOKEN.findall("".join(parts)):
        if token == "(":
            depth += 1
        elif token == ")":
            depth = max(0, depth - 1)
        elif depth:
            continue
        elif token.startswith(_MARK):
            kind, _, value = token.strip(_MARK).partition(":")
            if kind == "us":
                region = "us"
            elif kind == "note":
                note = value
            elif kind == "sound":
                where, _, href = value.partition(":")
                sounds.setdefault(where, href)
        elif ipa := clean(token.strip("/")):
            ipas[region].append((ipa, note))
            note = ""
    if region == "uk":
        ipas["us"] = ipas["uk"][:1]
    out = []
    for where in ("uk", "us"):
        found = ipas[where] if where == "uk" else ipas[where][:1]
        for i, (ipa, note) in enumerate(found or ([("", "")] if sounds.get(where) else [])):
            out.append(Pron(ipa=ipa, region=where, audio=sounds.get(where, "") if i == 0 else "", note=note))
    return out


def _read_header(el) -> _Header:
    """Part of speech, labels, forms and pronunciations of a header line or block header.

    A green bold word is a part of speech outside brackets and a grammar code inside
    them ("noun [C or U]"); a mediumblue word is a variant only after "ALSO" ("US
    USUALLY assign" names a different word)."""
    h = _Header()
    whole = text(el)
    head = next(iter(_fonts(el, *_HEAD_COLORS)), None)
    h.form = clean(_STRESS.sub("", text(head)))
    if "— phrasal verb with" in whole:
        h.pos, h.phrasal_verb = ["phrasal verb"], text(head)
        for event, value in _stream(el):  # labels before the dash; the rest is the base verb
            if event == "text" and "—" in value:
                break
            if event == "open" and value.tag == "sub" and "ALSO" not in text(value):
                h.labels += _sub_labels(value)  # "(UK ALSO hand round)" labels the variant, not this verb
        return h
    depth, parens, also = 0, 0, False
    for event, value in _stream(el):
        if event == "text":
            depth = max(0, depth + value.count("[") - value.count("]"))
            parens = max(0, parens + value.count("(") - value.count(")"))
            also = also and ")" not in value
            continue
        node = value
        if _is_badge(node) and _is_pos(badge := text(node)):
            h.pos.append(badge)
        elif node.tag == "sub":
            if "ALSO" in text(node):
                also = True
            elif text(node) not in _PRON_NOTES and not parens:
                # "STRONG" / "WEAK" qualify a transcription; "(PLURAL -men)" introduces a form
                h.labels += _sub_labels(node)
        elif _color(node) == "green":
            word = text(node).strip("[] ")
            if not word or word == "aep" or _LEVEL.match(word):
                continue
            if node.find("b") is not None and depth == 0 and _is_pos(word):
                h.pos.append(word)
            else:
                h.labels.append(word)
        elif _color(node) == "midnightblue" or (_color(node) == "mediumblue" and also):
            if v := text(node):
                h.forms.append(v)
    h.prons = _prons(el)
    return h


def _sub_labels(sub) -> list[str]:
    """Labels printed in small capitals: one per coloured font ("UK", "INFORMAL"), or the
    whole sub when it prints more than its fonts ("MAINLY US", "US USUALLY")."""
    fonts = [v for f in _fonts(sub, *_LABEL_COLORS) if (v := text(f))]
    whole = text(sub)
    rest = whole
    for f in fonts:
        rest = rest.replace(f, "", 1)
    return [whole] if clean(rest) or not fonts else fonts
