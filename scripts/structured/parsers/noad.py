"""New Oxford American Dictionary, 3rd edition (NOAD3, converted from Lingvo DSL).

The DSL conversion leaves presentational markup only: an entry is a flat run of lines
(top-level p / div elements), so this parser is a line-by-line state machine.

  p.s > b "I", "II"          homograph (all homographs share one MDict entry)
  p / p.ss                   header: span.t = pronunciation "[pāl]", b > span.color =
                             headword with syllable dots, "(also X or chiefly Brit. Y)"
  div.m1 > b > span.color    headword line (same content, when no p header)
  div.m1 | div.m2            a sense line, read left to right:
      "1)" number, or span.gray "■" for a subsense (no number printed)
      span.p[@title]         an abbreviation; the title is its expansion. A part of speech
                             ("n." title "noun") sets the POS; any other ("Brit.") is a label
      i > span.color         a label ("Statistics", "archaic"); if it opens with "(" it is
                             a form group "(weigh something out)" or variant, not a label
      i "[no obj.]"          grammar label, leading or trailing
      span.color "(pl. X)"   inflections, b = the forms
      the rest               definition
  div.m1 > i "[...]" alone   before example lines: a label of those examples ("[no obj.]", "figurative").
                             Otherwise a POS-level grammar label the conversion moved to the end of
                             the POS block; it applies to every sense of that block, except a sense
                             (and its subsenses) printing its own label of that kind ("[no obj.]"
                             against the block's "[with obj.]")
  div.m1 > div.opt > span.ex example of the latest sense; an opt line holding only an
                             italic label ("[as submodifier]") labels the examples after it
  div.opt "•" / "••"         start of the phrase list: "- <a>phrase</a>" links only
  div.opt > b "Derivatives:" then lines "<b>word</b> <b>(syl·la·bles)</b> [pron]"
  div.opt > b "Origin:"      then the etymology lines
  div.opt > b "Phrasal Verbs:" then links only

Labels and parts of speech use the span.p title (the dictionary's own expansion, so
"n." is "noun" and "Brit." is "British", matching ODE's wording). Headword, forms and
derivatives drop the syllabification dots. NOAD transcribes American English only, so
its respellings are recorded with region "us"; they are NOAD respellings, not IPA.

A definition "see X" whose X is a link is a cross-reference, not a definition ("see",
"see or observe" are definitions). Stubs: a record with no definition is "xref" when it
points elsewhere ("See X" lines, "see X", phrase links only), "empty" when it has no sense.

Left in layer 1: phrase and phrasal-verb link lists (each has its own entry), "See also"
lines, usage pointers, sense-level pronunciations and form groups, and pictures.

Coverage (full run, 98,541 records): 1,120 stubs (xref 1,118, e.g. "a bed of roses":
see bed, "West Berlin": See Berlin, "behalf": phrase links only; empty 2: "sheatfish",
only a plural, and "talk to", only an example); all 97,421 content records are
covered (1.0).
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from structured.markup import clean, parse as parse_html, text
from structured.model import Entry, Example, Pron, Sense
from structured.parsers._noad_line import _POS, _cls, _expanded, _read_line, _spelling

KEY = "noad"
COVERS = "definitions"
MIN_COVERAGE = 0.99

_POINTER = re.compile(r"^see\b", re.I)
_ALSO = re.compile(r"\(also ([^)]*)\)")
_ALSO_PREFIX = re.compile(r"^(?:(?:chiefly|esp\.|especially|usu\.|usually)\s+)+")
_SLASHED = re.compile(r"/[^/]*/")
_HEADERS = {"Derivatives:": "derivatives", "Origin:": "origin", "Phrasal Verbs:": "links", "Usage:": "other"}


@dataclass
class _Draft:
    """A sense being assembled; frozen into a model.Sense at the end."""
    kind: str
    pos: str
    number: str = ""
    phrase: str = ""
    labels: list[str] = field(default_factory=list)
    definition: str = ""
    examples: list[Example] = field(default_factory=list)
    parent: "_Draft | None" = None  # the numbered sense a "■" subsense belongs to

    def takes(self, label: str) -> bool:
        """Whether a label printed for the whole part-of-speech block applies here: not when this sense, or
        the sense it is a subsense of, prints its own label of the same kind ("no object" against "with object")."""
        own = self.labels + (self.parent.labels if self.parent is not None else [])
        return not any(_same_kind(x, label) for x in own)

    def freeze(self) -> Sense | None:
        if not (self.definition or self.examples or (self.kind != "sense" and self.phrase)):
            return None
        return Sense(kind=self.kind, pos=self.pos, number=self.number, phrase=self.phrase,
                     labels=tuple(dict.fromkeys(self.labels)), definition=self.definition,
                     examples=tuple(self.examples))


def _same_kind(label: str, other: str) -> bool:
    """Whether two grammar labels are about the same thing: their last words agree, abbreviated or not
    ("no object" and "with object", "with two objs." and "with object"; not "informal" and "with infinitive")."""
    a, b = (x.split()[-1].rstrip(".").removesuffix("s").lower() if x.split() else "" for x in (label, other))
    return len(a) >= 3 and len(b) >= 3 and (a.startswith(b) or b.startswith(a))


def _opt_of(line):
    """The div.opt of a line (the line itself, or its child), if it has one."""
    return line if _cls(line) == "opt" else next((c for c in line if _cls(c) == "opt"), None)


def _labels_only(line) -> bool:
    """Whether a sense line holds nothing but labels ("[no obj.]", "figurative")."""
    if line.tag != "div" or _opt_of(line) is not None:
        return False
    _, pos, labels, _, definition = _read_line(line)
    return bool(labels) and not pos and not definition


def _labels_examples(lines: list, index: int) -> bool:
    """Whether the label line at `index` is printed before example lines (further label lines may come
    between): it then labels those examples, not the senses of its part-of-speech block."""
    following = index + 1
    while following < len(lines) and _labels_only(lines[following]):
        following += 1
    opt = _opt_of(lines[following]) if following < len(lines) else None
    return opt is not None and bool(_examples(opt))


def _is_pointer(definition: str, line) -> bool:
    """"see bed" (a link) is a cross-reference; "see", "see or observe" are definitions."""
    m = _POINTER.match(definition)
    link = next((a for a in line.iter("a") if (a.get("href") or "").startswith("entry://")), None)
    return bool(m) and link is not None and definition[m.end():].strip().startswith(text(link))


def _head_bold(line, anywhere: bool = False):
    """The b holding the headword (b > span.color or span.color > b), if `line` shows one.
    A div line shows it only as its first element; a p header may show it anywhere."""
    candidates = [c for c in line if isinstance(c.tag, str)]
    if not anywhere:
        if clean(line.text or "") or not candidates:
            return None
        candidates = candidates[:1]
    for c in candidates:
        if c.tag == "b" and any(_cls(s) == "color" for s in c.iter("span")):
            return c
        # span.color > b is also the shape of "(pl. battles royal)", which is not a headword
        if _cls(c) == "color" and not text(c).startswith("(") and (b := next(iter(c.iter("b")), None)) is not None:
            return b
    return None


def _headword_and_variants(line, bold) -> tuple[str, list[str]]:
    head = _spelling(text(bold))
    stripped = copy.deepcopy(line)
    for sp in [s for s in stripped.iter("span") if _cls(s) in ("p", "t")]:
        sp.drop_tree()
    variants = []
    for group in _ALSO.findall(text(stripped)):
        for part in re.split(r",| or ", _SLASHED.sub("", group)):
            value = _spelling(_ALSO_PREFIX.sub("", clean(part)))
            if value and value != head:
                variants.append(value)
    return head, variants


def _examples(opt, labels: tuple[str, ...] = ()) -> list[Example]:
    return [Example(value, labels=labels) for x in opt.iter("span") if _cls(x) == "ex" and (value := text(x))]


def _bracketed(line) -> set[str]:
    """The labels a label line prints in square brackets: grammar labels ("[no obj.]", "[as adj.]"), unlike a
    register or subject label ("figurative", "dated")."""
    return {_expanded(i).strip("[]: ") for i in line.iter("i") if _expanded(i).lstrip().startswith("[")}


def _scoped(label: str) -> bool:
    """Whether a grammar label classes the sense's use rather than one example's construction: transitivity
    ("no object", "with object") and word class ("as adverb"). "[as modifier]", "[with clause]", "[after prep.]"
    describe only the examples printed after them."""
    return label in ("no object", "with object") or (label.startswith("as ") and label[3:] in _POS)


def _label_line(opt) -> tuple[str, ...]:
    """Labels of an opt line that holds nothing else ("[as submodifier]"); they qualify the
    example lines that follow it."""
    kids = [c for c in opt if isinstance(c.tag, str)]
    if clean(opt.text or "") or not kids or any(c.tag != "i" or clean(c.tail or "") for c in kids):
        return ()
    return tuple(v for c in kids if (v := _expanded(c).strip("[]: ")))


class _Reader:
    """The line-by-line state machine: one handler per kind of line, and the state they share."""

    def __init__(self, lines: list) -> None:
        self.lines = lines
        self.shown = ""
        self.homographs: list[str] = []
        self.pos_list: list[str] = []
        self.prons: list[Pron] = []
        self.forms: list[str] = []
        self.origins: list[str] = []
        self.drafts: list[_Draft] = []
        self.block: list[_Draft] = []        # senses of the current part of speech
        self.target: _Draft | None = None    # the sense or derivative that example lines belong to
        self.mode, self.pos = "senses", ""
        self.pointed = False                 # the record points elsewhere ("See X", "see X", phrase links)
        self.example_labels: tuple[str, ...] = ()  # from a label line, for the example lines right after it
        self.labelled = False                # the line just read was a label line (its labels are open to more)
        self.carried: tuple[str, ...] = ()   # the grammar labels the current group took from the group before

    def run(self) -> None:
        for index, line in enumerate(self.lines):
            if line.tag == "p":
                self._header(line)
                continue
            pending, self.example_labels = self.example_labels, ()
            labelled, self.labelled = self.labelled, False
            opt = _opt_of(line)
            if opt is not None:
                self._opt_line(opt, pending)
            elif line.tag == "div":
                self._div_line(index, line, pending, labelled)

    def _add(self, draft: _Draft) -> None:
        self.drafts.append(draft)
        self.target = draft

    def _add_prons(self, el) -> None:
        for t in el.iter("span"):
            if _cls(t) == "t" and (ipa := clean(text(t).strip("[]/ "))):
                if (p := Pron(ipa=ipa, region="us")) not in self.prons:
                    self.prons.append(p)

    def _headword(self, line, bold) -> None:
        head, variants = _headword_and_variants(line, bold)
        self.shown = self.shown or head
        self.forms += [v for v in dict.fromkeys(variants) if v not in self.forms]

    def _header(self, line) -> None:
        """A p line: homograph number, pronunciation, headword; it starts a new part-of-speech block."""
        if _cls(line) == "s":
            self.homographs.append(text(next(iter(line.iter("b")), None)))
        self._add_prons(line)
        if (bold := _head_bold(line, anywhere=True)) is not None:
            self._headword(line, bold)
        self.mode, self.pos, self.block = "senses", "", []

    def _opt_line(self, opt, pending: tuple[str, ...]) -> None:
        """A div.opt line: an example, an example label, a section heading, or a line of that section."""
        label = text(opt)
        if self.mode in ("senses", "derivatives") and (own := _label_line(opt)):
            self.example_labels = self._group(own, _bracketed(opt), pending, False)
            return
        bold = next(iter(opt.iter("b")), None)
        self.pointed = self.pointed or label.startswith("- ")  # a link to a phrase's own entry
        if label in ("•", "••"):
            self.mode = "links"
        elif bold is not None and text(bold) in _HEADERS and label.startswith(text(bold)):
            self.mode = _HEADERS[text(bold)]
            if self.mode == "origin" and (rest := clean(label[len(text(bold)):])):
                self.origins.append(rest)
        elif self.mode == "origin":
            if label:
                self.origins.append(label)
        elif self.mode == "derivatives" and bold is not None and (word := _spelling(text(bold))):
            self._add(_Draft(kind="derivative", pos="", phrase=word, examples=_examples(opt)))
        elif self.mode in ("senses", "derivatives") and self.target is not None and (examples := _examples(opt, pending)):
            self.target.examples += examples
            self.example_labels = pending  # it also covers the next example line

    def _div_line(self, index: int, line, pending: tuple[str, ...], labelled: bool) -> None:
        """A div line without an opt: a pointer, the headword, a pronunciation, or a sense line."""
        whole = text(line)
        if not whole or whole.startswith(("See ", "See also")) or whole.startswith("- "):
            self.pointed = self.pointed or bool(whole)
        elif (bold := _head_bold(line)) is not None:
            self._headword(line, bold)
        elif whole.startswith("[") and whole.endswith("]") and not list(line.iter("i")):
            self._add_prons(line)  # a pronunciation line
        else:
            self._sense_line(index, line, pending, labelled)

    def _sense_line(self, index: int, line, pending: tuple[str, ...], labelled: bool) -> None:
        number, line_pos, labels, line_forms, definition = _read_line(line)
        self.forms += [f for f in dict.fromkeys(line_forms) if f not in self.forms]
        if line_pos:
            self.pos = ", ".join(line_pos)  # "n., adv., & adj.": one sense shared by every part of speech printed
            self.pos_list += line_pos
            self.block = []
        if not definition:
            if labels and not line_pos:
                self._label_only(index, line, labels, pending, labelled)
            return
        self.mode = "senses"
        if _is_pointer(definition, line):
            definition, self.pointed = "", True  # "see bed": the meaning lives in another entry
        subsense = any(_cls(c) == "gray" for c in line)  # "■": a subsense of the latest sense line
        draft = _Draft(kind="sense", pos=self.pos, number=number, labels=labels, definition=definition,
                       parent=(self.block[-1].parent or self.block[-1]) if subsense and self.block else None)
        self._add(draft)
        self.block.append(draft)

    def _group(self, labels, bracketed: set[str], pending: tuple[str, ...], labelled: bool) -> tuple[str, ...]:
        """The labels of the examples after a label line. Label lines printed one after another add up. A label
        line after examples starts a new group. The earlier group's transitivity and word-class labels (see
        _scoped) carry over unless the new group prints a grammar label (in brackets) of its own; its other labels
        never do ("[no obj.]" + an example, then "figurative" + an example: that example is "no object" and
        "figurative"; "[as noun]" + an example, then "[as adj.]" + an example: that example is "as adjective"
        only; "[as modifier]" + an example, then "figurative" + an example: that example is "figurative" only).
        The group's lines decide together: a grammar label on its second line still replaces what its first
        line carried over."""
        if not labelled:
            self.carried = tuple(x for x in pending if _scoped(x))
            pending = self.carried
        kept = tuple(x for x in pending if not (bracketed and x in self.carried))
        return tuple(dict.fromkeys(kept + tuple(labels)))

    def _label_only(self, index: int, line, labels: list[str], pending: tuple[str, ...], labelled: bool) -> None:
        if _labels_examples(self.lines, index):
            # "[no obj.]", "dated" before example lines: the labels of those examples (see _group)
            self.example_labels = self._group(labels, _bracketed(line), pending, labelled)
            self.labelled = True
        else:  # a grammar label moved to the end of its POS block: the block's default
            for d, taken in [(d, [x for x in labels if d.takes(x)]) for d in self.block]:
                d.labels += taken


def parse(headword: str, html: str) -> Entry:
    r = _Reader([line for line in parse_html(html) if isinstance(line.tag, str)])
    r.run()
    shown = r.shown or clean(headword)
    senses = tuple(s for d in r.drafts if (s := d.freeze()) is not None)
    stub = ""
    if not any(s.definition for s in senses):
        stub = "xref" if r.pointed else "empty" if not senses else ""
    return Entry(headword=shown, homograph=r.homographs[0] if len(r.homographs) == 1 else "",
                 pos=tuple(dict.fromkeys(r.pos_list)), prons=tuple(r.prons), senses=senses,
                 etymology=" ".join(r.origins), forms=tuple(f for f in r.forms if f != shown), stub=stub)
