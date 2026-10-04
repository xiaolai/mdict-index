"""Cambridge Advanced Learner's Dictionary, 4th edition (CALD4).

Presentational HTML: roles are carried by font colours, inline styles and glyphs, and an
entry is a flat run of lines (the root's children), read here as a state machine.

  b > font[size=+1]              headword
  font[size=+0] | div header     font[blue|navy|darkblue] > b = headword as stressed;
      a[href^=sound://] > img snd_uk.png / snd_us.png = audio; "/…/" = IPA, a second
      "/…/" after font[green] > b "aep" is the American one, a sub "STRONG" / "WEAK"
      before one is its note, and those inside "( … )" belong to a plural or variant
      ("(PLURAL -men /-mən/)") and are skipped; font[green] > b = part of
      speech; font[green] (no b) "[C]" and sub > font[indigo|darkviolet] "INFORMAL" =
      labels for everything below; font[midnightblue] > b = inflections;
      font[mediumblue] > b after "ALSO" = variants; font[mediumvioletred] = guideword
  div > font[crimson] > b "Ⅰ"    a new block (one per part of speech and guideword); the
      div after it holds the header: a styled span badge = part of speech, or
      "keep (sth) up — phrasal verb with keep …" for a phrasal verb
  div > span "1" + next div      a numbered sense; span starting "►" = unnumbered sense.
      A sense line opens with the English Profile level (font[green] > b "B2", "F0")
      and its labels ("[C]", "[C, usually singular]", sub "INFORMAL"), then the
      definition, printed with a trailing colon when examples follow
  span > font[gray] "» …"        an example; font[limegreen] "(= …)" is a gloss inside it;
      the grammar codes and small-capital labels that open it ("[+ that]", "MAINLY US")
      are its labels (Example.labels), taken out of the text; later ones stay in it
  font[olive] > u "Extra Examples"   examples for the block as a whole
  other font[olive] > u headers  side boxes: Thesaurus, Word partners, Collocations,
      Common mistake, Word Builder, Note, See picture; darkred "→ SEE …" is a cross-ref

Extra examples are attached to the block's only sense when it has one; otherwise they
become one definition-less sense of the block (the dictionary does not tie them to a
sense). A phrasal-verb page yields phrasal_verb senses whose phrase is its header form;
its "with keep /kiːp/ verb (kept, kept)" part describes the base verb and is ignored.
"Verb Endings for X" pages yield their conjugated forms only. A suffix form ("-men"
beside "batman") becomes the full form ("batmen") when it aligns with the headword's
ending (at most one letter differs), otherwise it is dropped. A sub printing more than
its coloured fonts ("MAINLY US") is one label; otherwise each font is one ("UK",
"INFORMAL"). A run-on derivative keeps only its own header's labels.

A definition that only names another entry is dropped: "→ PLASTERBOARD", or a
small-capital lead-in plus a capitalised target ("US FOR HOB", "PAST SIMPLE OF WEEP").
An abbreviation's expansion is kept ("ABBREVIATION FOR DEEP VEIN THROMBOSIS").

Stubs (records with no definition): "popup" for "Verb Endings for X" (part_of X; their
conjugated forms are kept in forms), "index" for thesaurus pages ("↑…", "♯ …") and the
two help pages, "xref" for "⇒ X" redirects and "→ X" / "X FOR Y" senses, "inflection"
and "variant" for "PAST SIMPLE OF X" / "SPELLING OF X", "derivative" for run-ons whose
only link is "Main Entry: X" (they keep their pos, pron and examples), "empty" otherwise.

Left in layer 1: levels, guidewords, side boxes, cross-references, "Main Entry" links,
sense-level phrase headers ("set expression/phrase"), and thesaurus pages.

Coverage (full run, 67,674 records): 18,398 stubs (popup 5,210, derivative 4,901,
index 4,097, xref 4,062, inflection 108, variant 18, empty 2: "get into a lather" and
"-in-waiting"); all 49,276 content records are covered (1.0).
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from structured.markup import clean, parse as parse_html, text
from structured.model import Entry, Example, Pron, Sense
from structured.parsers._cald_header import (
    _HEAD_COLORS, _LABEL_COLORS, _LEVEL, _Header, _color, _expand, _fonts, _is_badge, _read_header, _style, _sub_labels,
)

KEY = "cald"
COVERS = "definitions"
MIN_COVERAGE = 0.99

_ROMAN = re.compile(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+$")
_LEAD_JUNK = re.compile(r"^[\s\[\],;]+")
# a definition that only names another headword: small-capital lead-in + capitalised target
# ("PAST SIMPLE OF ARISE"); "INFORMAL FOR an advertisement" carries a gloss and is kept
_POINTER_DEF = re.compile(r"^[A-Z][A-Z' ,-]* (?:FOR|OF) [^a-z]*$")
# except for an abbreviation, whose expansion is its meaning ("ABBREVIATION FOR DEEP VEIN THROMBOSIS")
_EXPANSION = re.compile(r"^[A-Z' ,-]*(?:ABBREVIATION|SHORT FORM)")
_INFLECTION = re.compile(r"^[A-Z ]*(?:PAST|PARTICIPLE|PLURAL|COMPARATIVE|SUPERLATIVE)[A-Z ]* OF ")
_VARIANT = re.compile(r"^[A-Z ]*SPELLING OF ")
_ENDINGS = "Verb Endings for"
_CF = re.compile(r"\s*\(Cf\.\s*↑[^)]*\)")  # a cross-reference the conversion inlined
# "WRITTEN ABBREVIATION FOR x", "PAST SIMPLE OF x": the small capitals open the definition
_LEADS_IN = re.compile(r"\b(OF|FOR|TO)$")


@dataclass
class _Draft:
    kind: str
    pos: str
    number: str = ""
    phrase: str = ""
    labels: list[str] = field(default_factory=list)
    definition: str = ""
    examples: list[Example] = field(default_factory=list)

    def freeze(self) -> Sense | None:
        if not (self.definition or self.examples):
            return None
        return Sense(kind=self.kind, pos=self.pos, number=self.number, phrase=self.phrase,
                     labels=tuple(dict.fromkeys(self.labels)), definition=self.definition,
                     examples=tuple(self.examples))


def _read_example(line) -> tuple[str, list[str]]:
    """(text, labels) of an example line "» [+ that] UK They proved that …": the grammar
    codes and small-capital labels that open it are its labels; later ones stay in the text."""
    gray = copy.deepcopy(next(iter(_fonts(line, "gray"))))
    gray.text = (gray.text or "").replace("»", "", 1)
    labels: list[str] = []
    if not _LEAD_JUNK.sub("", gray.text or ""):
        for child in list(gray):
            if not isinstance(child.tag, str):
                continue
            if _color(child) == "green" and not _LEVEL.match(text(child)):
                labels.append(text(child).strip("[] "))
            elif child.tag == "sub" and _fonts(child, *_LABEL_COLORS) and not _LEADS_IN.search(text(child)):
                labels += _sub_labels(child)
            else:
                break
            started = bool(_LEAD_JUNK.sub("", child.tail or ""))
            if not started:
                child.tail = ""
            child.drop_tree()
            if started:
                break
    return _LEAD_JUNK.sub("", clean(_CF.sub("", text(gray)))), [lab for lab in labels if lab]


def _read_sense_line(el) -> tuple[list[str], str, str]:
    """(labels, definition, pointer) of a sense line: level and leading labels taken out.
    A definition that only names another entry is dropped; `pointer` says what kind of
    reference it was (a STUB_KINDS reason)."""
    el = copy.deepcopy(el)
    labels: list[str] = []
    started = bool(_LEAD_JUNK.sub("", (el.text or "").replace("►", "")))
    for child in list(el):
        if not isinstance(child.tag, str) or started:
            break
        value = text(child)
        if value == "►" or (_color(child) == "green" and _LEVEL.match(value)):
            pass
        elif _color(child) == "green":
            labels.append(value.strip("[] "))
        elif child.tag == "sub" and _fonts(child, *_LABEL_COLORS) and not _LEADS_IN.search(value):
            labels += _sub_labels(child)
        else:
            break
        started = bool(_LEAD_JUNK.sub("", child.tail or ""))
        if not started:
            child.tail = ""
        child.drop_tree()
    el.text = (el.text or "").replace("►", "")
    definition = _LEAD_JUNK.sub("", _CF.sub("", text(el)))
    if definition.endswith(":"):
        definition = definition[:-1].rstrip()
    pointer = ""
    if definition.startswith("→") or (_POINTER_DEF.match(definition) and not _EXPANSION.match(definition)):
        # "→ ABDOMINALS", "US FOR BA", "PAST SIMPLE OF ARISE": the meaning lives in that entry
        pointer = "inflection" if _INFLECTION.match(definition) else "variant" if _VARIANT.match(definition) else "xref"
        definition = ""
    return [lab for lab in labels if lab], definition, pointer


def _olive_header(el) -> str:
    u = next((u for f in _fonts(el, "olive") for u in f.iter("u")), None)
    return text(u)


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    top = next((b for b in root if isinstance(b.tag, str) and b.tag == "b"), None)
    shown = text(top) if top is not None else ""
    pos_list: list[str] = []
    prons: list[Pron] = []
    forms: list[str] = []
    drafts: list[_Draft] = []
    block: list[_Draft] = []
    extras: list[Example] = []
    entry_labels: list[str] = []
    block_labels: list[str] = []
    run_on_labels: list[str] = []
    main_form = ""
    pointers: set[str] = set()      # STUB_KINDS reasons of dropped pointer definitions
    pos, kind, phrase, number = "", "sense", "", ""
    mode = "sense"
    in_block = expect_block_header = False

    def close_block() -> None:
        nonlocal extras
        if extras:
            if len(block) == 1:
                block[0].examples += extras
            else:
                drafts.append(_Draft(kind=kind, pos=pos, phrase=phrase, labels=labels_now(), examples=list(extras)))
        extras = []

    def labels_now() -> list[str]:
        # a run-on derivative has its own header; the main word's labels do not reach it
        return list(run_on_labels) if kind == "derivative" else entry_labels + block_labels

    def take_header(h: _Header) -> None:
        nonlocal pos, kind, phrase, main_form, run_on_labels, block
        main_form = main_form or h.form
        if h.form and h.form.casefold() != main_form.casefold() and not h.phrasal_verb:
            # a run-on derivative printed inside the entry: "—amazingly /-li/ adverb";
            # it ends the block before it, whose extra examples are settled first
            close_block()
            block = []
            kind, phrase, run_on_labels = "derivative", h.form, list(h.labels)
            pos = h.pos[0] if len(h.pos) == 1 else ""
            return
        run_on_labels = []
        target = block_labels if in_block else entry_labels
        pos_list.extend(p for p in h.pos if p not in pos_list)
        if h.pos:  # a header listing several parts of speech does not say which sense is which
            pos = h.pos[0] if len(h.pos) == 1 else ""
        target.extend(lab for lab in h.labels if lab not in target)
        forms.extend(f for f in (_expand(main_form, v) for v in h.forms) if f and f not in forms)
        seen = {(p.ipa, p.region) for p in prons}
        prons.extend(p for p in h.prons if (p.ipa, p.region) not in seen)
        if h.phrasal_verb:
            kind, phrase = "phrasal_verb", h.phrasal_verb

    for line in root:
        if not isinstance(line.tag, str) or line.tag in ("br", "b"):
            continue
        whole = text(line)
        if not whole:
            continue
        # Verb Endings pages: the conjugated forms
        forms.extend(v for f in _fonts(line, "sienna") if (v := text(f)) and v not in forms)
        if line.tag == "font" and _fonts(line, *_HEAD_COLORS):
            take_header(_read_header(line))
            continue
        if line.tag == "div":
            if _fonts(line, "crimson") and _ROMAN.match(whole):
                close_block()
                block, block_labels, mode, in_block, expect_block_header = [], [], "sense", True, True
                kind, phrase, run_on_labels = "sense", "", []
                continue
            if expect_block_header and (any(_is_badge(s) for s in line.iter("span")) or _fonts(line, *_HEAD_COLORS)):
                take_header(_read_header(line))
                expect_block_header = False
                continue
            if "display:block" in _style(line) and whole.isdigit():
                number, mode = whole, "sense"
                continue
            if _fonts(line, "lightgray"):  # "• • •"
                continue
            if number and "margin-left" in _style(line):
                labels, definition, pointer = _read_sense_line(line)
                pointers.add(pointer)
                draft = _Draft(kind=kind, pos=pos, number=number, phrase=phrase,
                               labels=labels_now() + labels, definition=definition)
                drafts.append(draft)
                block.append(draft)
                number, mode = "", "sense"
            continue
        if line.tag != "span":
            continue
        header = _olive_header(line)
        if header == "Extra Examples":
            mode = "extra"
            continue
        if header:  # a side box; the one-line Thesaurus links do not open a box
            if header != "Thesaurus":
                mode = "box"
            continue
        first = next((c for c in line if isinstance(c.tag, str)), None)
        if first is not None and text(first) == "►":
            labels, definition, pointer = _read_sense_line(line)
            pointers.add(pointer)
            draft = _Draft(kind=kind, pos=pos, phrase=phrase, labels=labels_now() + labels, definition=definition)
            drafts.append(draft)
            block.append(draft)
            mode = "sense"
            continue
        gray = _fonts(line, "gray")
        if gray and whole.startswith("»") and mode in ("sense", "extra"):
            value, labels = _read_example(line)
            example = Example(value, labels=tuple(labels))
            if example.text:
                if mode == "extra":
                    extras.append(example)
                elif block:
                    block[-1].examples.append(example)
    close_block()

    shown = shown or clean(headword)
    senses = tuple(s for d in drafts if (s := d.freeze()) is not None)
    stub, part_of = "", ""
    if not any(s.definition for s in senses):
        stub, part_of = _stub_reason(root, clean(headword), shown, senses, pointers)
    return Entry(headword=shown, pos=tuple(pos_list), prons=tuple(prons), senses=senses,
                 forms=tuple(f for f in forms if f != shown), stub=stub, part_of=part_of)


def _stub_reason(root, key: str, shown: str, senses, pointers: set[str]) -> tuple[str, str]:
    """(stub reason, part_of) for a record without a definition; part_of only for "popup"."""
    if shown.startswith(_ENDINGS):
        return "popup", shown[len(_ENDINGS):].strip()  # the conjugation table of that verb
    if key.startswith(("↑", "♯", "000***")):
        return "index", ""  # a thesaurus category or a help page
    if any(text(f) == "⇒" for f in _fonts(root, "darkmagenta")):
        return "xref", ""
    if any(text(f) == "Main Entry" for f in _fonts(root, "darkmagenta")):
        return "derivative", ""  # a run-on form defined at its main entry
    for reason in ("inflection", "variant", "xref"):
        if reason in pointers:
            return reason, ""
    return ("empty", "") if not senses else ("", "")
