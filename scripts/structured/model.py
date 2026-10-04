"""The shared structured model every dictionary parser produces.

One model for 25 very different dictionaries, so it is deliberately small:
anything a dictionary has that does not fit stays in layer 1 (the original
HTML, always one join away via entry_id).

Strings are as printed, whitespace-collapsed, with no markup. Empty string /
empty tuple means "this dictionary does not say", never "unknown parse".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SENSE_KINDS = frozenset({
    "sense",         # an ordinary numbered or unnumbered meaning
    "phrase",        # a fixed phrase or idiom inside the entry
    "phrasal_verb",  # "take off", "set out"
    "derivative",    # a run-on derived word ("takingly", "-ness" forms)
    "collocation",   # a collocation group (Oxford Collocations)
    "note",          # a usage note / explanatory section (PEU, usage boxes)
})
EXAMPLE_KINDS = frozenset({"example", "collocation", "quotation"})
REGIONS = frozenset({"", "uk", "us"})
STUB_KINDS = frozenset({
    "xref",        # the record only points elsewhere ("see X", "⇨ X", "= X")
    "popup",       # a satellite record of another entry (LDOCE example banks, word origins); set part_of
    "inflection",  # "past tense of X", "plural of X"
    "variant",     # "variant spelling of X"
    "derivative",  # a run-on derived form printed with no definition of its own
    "index",       # a thesaurus / category / index page that repeats other entries
    "image",       # an illustration-only record
    "empty",       # nothing but the headword
})
COVERAGE_KINDS = frozenset({"definitions", "pronunciation", "etymology", "collocations", "notes"})


@dataclass(frozen=True)
class Pron:
    ipa: str                 # transcription as printed, without enclosing slashes: IPA, or the
                             # dictionary's own respelling system (NOAD, MW); `note` or the parser says which
    region: str = ""         # "uk", "us", or "" when unspecified
    audio: str = ""          # path of the audio inside the dictionary's .mdd, as the entry references it:
                             # a sound:// link, or another path (ODE takes it from an onclick handler)
    note: str = ""           # qualifier as printed: "strong form", "in Kent", "esp. before a vowel"


@dataclass(frozen=True)
class Example:
    text: str
    text_zh: str = ""        # Chinese translation, when the dictionary gives one
    kind: str = "example"    # example | collocation | quotation
    source: str = ""         # quotation source (OED) or other attribution
    date: str = ""           # quotation date as printed (OED: "1392", "a1400")
    labels: tuple[str, ...] = ()  # labels on this example or collocation ("esp. BrE", "informal")


@dataclass(frozen=True)
class Sense:
    kind: str = "sense"
    pos: str = ""                        # part of speech as printed ("verb", "n.", "vt.")
    number: str = ""                     # as printed: "1", "1.1", "a", "I"
    phrase: str = ""                     # the phrase itself, for every kind except "sense"
    labels: tuple[str, ...] = ()         # grammar / register / region / subject labels
    definition: str = ""                 # English definition
    definition_zh: str = ""              # Chinese definition or gloss
    examples: tuple[Example, ...] = ()


@dataclass(frozen=True)
class Entry:
    headword: str
    homograph: str = ""                  # "1", "2" when the dictionary numbers homographs
    pos: tuple[str, ...] = ()            # every part of speech the entry covers
    prons: tuple[Pron, ...] = ()
    senses: tuple[Sense, ...] = ()
    etymology: str = ""
    forms: tuple[str, ...] = ()          # inflections and variant spellings
    stub: str = ""                       # set (to a STUB_KINDS reason) when the record cannot carry content
    part_of: str = ""                    # for stub "popup": headword of the entry this record belongs to
    extra: dict[str, str] = field(default_factory=dict, compare=False)  # dictionary-specific, documented per parser


# Markup left in text: a real HTML element tag (known element name, then attributes, "/" or ">").
# Syntax alone cannot separate "<x y z>" from "<input disabled checked>", but the name can:
# leftover markup is always a real element; "< Latin", "<a, b>", "<x y z>" are dictionary text.
_HTML_ELEMENTS = (
    "a|abbr|b|big|blockquote|body|br|center|cite|code|col|dd|del|dfn|div|dl|dt|em|font|h[1-6]|head|hr|html|i|img|"
    "input|ins|kbd|li|link|meta|nobr|ol|p|pre|q|rb|rp|rt|ruby|s|samp|script|small|source|span|strike|strong|style|"
    "sub|sup|table|tbody|td|tfoot|th|thead|tr|tt|u|ul|var|wbr|audio|video|svg|path|button|label|form|section|"
    "article|aside|header|footer|nav|main|figure|figcaption|details|summary|mark|time|xhtml:[a-z]+"
)
_TAG = re.compile(
    rf"""</?(?:{_HTML_ELEMENTS})(?:\s+[a-zA-Z_:][-\w:.]*(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)*\s*/?>""",
    re.I,
)


def _check(value: str, where: str, tags: bool = True) -> list[str]:
    # Whitespace-collapsed means exactly what markup.clean() produces: any run of whitespace
    # (tab, CR, no-break space, ideographic space...) is one ASCII space, none at either end.
    if value != " ".join(value.split()) or (tags and _TAG.search(value)):
        return [f"{where}: not a clean string: {value[:60]!r}"]
    return []


def problems(entry: Entry, printed_markup: bool = False) -> list[str]:
    """Contract violations in a parsed entry; empty means valid.

    printed_markup=True skips only the leftover-tag check, for the few entries whose
    printed text is *about* HTML ("the HTML tag that signified a line break, <br>").
    Parsers list those headwords in PRINTED_MARKUP; every other check still applies.
    """
    def _clean(value: str, where: str) -> list[str]:
        return _check(value, where, tags=not printed_markup)

    out: list[str] = []
    if not entry.headword:
        out.append("empty headword")
    if entry.stub and entry.stub not in STUB_KINDS:
        out.append(f"stub reason {entry.stub!r}")
    if entry.part_of and entry.stub != "popup":
        out.append("part_of set on a record that is not a popup stub")
    if entry.stub == "popup" and not entry.part_of:
        out.append("popup stub without part_of")
    for name in ("headword", "homograph", "etymology", "part_of"):
        out += _clean(getattr(entry, name), name)
    for p in entry.pos:
        out += _clean(p, "pos")
    for form in entry.forms:
        out += _clean(form, "form")
    for p in entry.prons:
        if not p.ipa and not p.audio:
            out.append("pron with neither ipa nor audio")
        if p.region not in REGIONS:
            out.append(f"pron region {p.region!r}")
        out += _clean(p.ipa, "ipa") + _clean(p.note, "pron.note")
    for i, s in enumerate(entry.senses):
        where = f"sense[{i}]"
        if s.kind not in SENSE_KINDS:
            out.append(f"{where}: kind {s.kind!r}")
        if s.kind != "sense" and not s.phrase and s.kind not in ("note", "collocation"):
            out.append(f"{where}: kind {s.kind} needs a phrase")
        if not (s.definition or s.definition_zh or s.examples or s.phrase):
            out.append(f"{where}: empty sense")
        for name in ("pos", "number", "phrase", "definition", "definition_zh"):
            out += _clean(getattr(s, name), f"{where}.{name}")
        for label in s.labels:
            out += _clean(label, f"{where}.label")
        for j, ex in enumerate(s.examples):
            if not (ex.text or ex.text_zh):
                out.append(f"{where}.example[{j}]: empty")
            if ex.kind not in EXAMPLE_KINDS:
                out.append(f"{where}.example[{j}]: kind {ex.kind!r}")
            for name in ("text", "text_zh", "source", "date"):
                out += _clean(getattr(ex, name), f"{where}.example[{j}].{name}")
            for label in ex.labels:
                out += _clean(label, f"{where}.example[{j}].label")
    return out


def stub_problem(entry: Entry, kind: str) -> str:
    """A record marked as a stub must not carry the content it was excused from."""
    return f"stub ({entry.stub}) that is covered for {kind}" if entry.stub and covered(entry, kind) else ""


def covered(entry: Entry, kind: str) -> bool:
    """Whether a parsed entry carries the data its dictionary exists to provide."""
    if kind == "definitions":
        return any(s.definition or s.definition_zh for s in entry.senses)
    if kind == "pronunciation":
        return bool(entry.prons)
    if kind == "etymology":
        return bool(entry.etymology)
    if kind == "collocations":
        return any(ex.kind == "collocation" for s in entry.senses for ex in s.examples)
    if kind == "notes":
        return any(s.definition or s.examples for s in entry.senses)
    raise ValueError(f"unknown coverage kind {kind!r}")
