"""Oxford Collocations Dictionary, 2nd edition (OCD2).

The markup is a flat run of siblings, read in document order:
  span.ocd_hw                  the headword; a later ocd_hw names a phrasal verb
                               (usually after span.ocd_psv "PHRASAL VERB", which a
                               few records omit: "break down" in "break")
  hr.ocd_hr + span.ocd_seg     "I", "II": a new part-of-speech section
  span.ocd_class > ocd_pos     the section's part of speech ("noun", "verb")
  span.ocd_m1                  a sense header: span.ocd_def = span.ocd_li
                               (number) + the gloss; or <trn> with span.ocd_als
                               (variant spelling: a form) and span.ocd_fed (pos)
  span.ocd_m2 > ocd_ps         a collocation group label ("ADJECTIVE", "VERB + RUN")
  span.ocd_m3 > b + text       "2 start crying": a sense header in place of ocd_m1
                               (phrasal verbs' later senses)
  span.ocd_m3s > ocd_m3 > ocd_cc   one line of collocations: span.ocd_co parts;
                               ", " separates alternatives, a bare space joins the
                               parts of one ("at a" + "run"); ocd_reg (esp. BrE),
                               ocd_fed (field label "law") and <i>(= gloss)</i>
                               qualify items of the line
  span.ocd_m4s > ocd_m4 > ocd_ex   an example sentence for the line above
  span.ocd_m2_1                "Take is used with these nouns as the object: map,
                               chart, …": the collocates listed under their
                               relation (most records have nothing else)

Model: each sense with a gloss is Sense(kind="sense", pos, number,
definition=gloss); each group is Sense(kind="collocation", pos, number of the
sense it belongs to, phrase=group label) whose examples are its collocations
(Example kind "collocation", labels = the ocd_reg/ocd_fed labels: one right
after an item, or inside a plain "( …" after it, is that item's; one inside
"(both …" is the two items before the bracket's, inside "(all …" every item's
before it) followed by its example sentences (kind "example"). A used-with list is one
group, phrase = "used with these nouns as the object".

Phrasal verbs, an order-based relationship: Sense(kind="phrasal_verb",
phrase="bear on/upon sb/sth") is followed by the collocation groups (and glossed
senses, also kind "phrasal_verb") that belong to it; they have pos "" and last
until the next phrasal verb or the next I/II section. The model has no field
linking a group to its phrasal verb, so consumers must read senses in order.

Stubs, from markup: no group, collocation line, example, gloss or used-with
list, plus a "⇨ See" link -> "xref"; plus nothing -> "empty".
Left in layer 1: "(= …)" glosses on collocation lines, "See also" links.
"""
from __future__ import annotations

import re

from structured.markup import clean, cls, has_class, parse as parse_html, text
from structured.model import Entry, Example, Sense

KEY = "ocd"
COVERS = "collocations"
MIN_COVERAGE = 0.99  # policy min(0.99, measured): 1.0 over 20,802 content records (77 stubs: 56 empty, 21 xref)

_WANTED = ("ocd_hw", "ocd_seg", "ocd_pos", "ocd_m1", "ocd_m3", "ocd_ps", "ocd_cc", "ocd_ex", "ocd_m2_1")
_SCOPE = re.compile(r"\b(both|all)\b")  # "(both esp. BrE", "(informal, both AmE", "(all BrE"


def _collocations(cc) -> list[tuple[str, tuple[str, ...]]]:
    """The collocations of one ocd_cc line, each with its labels.

    A label (ocd_reg "esp. BrE", ocd_fed "law") right after an item, or inside a plain "( …" after
    it, belongs to that item; inside "(both …" to the two items before the bracket, inside "(all …"
    to every item before it. The source often omits the ")", so the next item also ends a bracket.
    """
    out: list[list] = []
    parts: list[str] = []
    bracket = False
    span: int | None = 1  # how many of the items before the bracket its labels qualify; None: all

    def finish() -> None:
        value = clean(" ".join(parts))
        parts.clear()
        if value and value != "etc." and value not in [c[0] for c in out]:  # "five-mile, etc.": not one
            out.append([value, []])

    def scope(words: str) -> None:
        nonlocal span
        if m := _SCOPE.search(words):
            span = 2 if m.group(1) == "both" else None

    for child in cc:
        if isinstance(child.tag, str):
            if has_class(child, "ocd_co"):
                bracket, span = False, 1
                parts.append(text(child))
            elif has_class(child, "ocd_reg") or has_class(child, "ocd_fed"):
                finish()
                label = text(child)
                if bracket and (m := _SCOPE.match(label)):  # "(both informal": the scope word is printed in the label
                    scope(m.group(0))
                    label = clean(label[m.end():])
                for item in (out if span is None else out[-span:]) if label else ():
                    item[1].append(label)
        tail = child.tail or ""
        if tail.strip(" \xa0\t\n"):  # ", " or " (both …": the alternative ends here
            finish()
            if "(" in tail:
                bracket, span = True, 1
                scope(tail.split("(")[-1])
            elif bracket:
                scope(tail)
            if ")" in tail.split("(")[-1]:
                bracket, span = False, 1
    finish()
    return [(value, tuple(dict.fromkeys(labels))) for value, labels in out]


class _Reader:
    def __init__(self) -> None:
        self.headword = ""
        self.pos_list: list[str] = []
        self.forms: list[str] = []
        self.senses: list[Sense] = []
        self.pos, self.number, self.verb = "", "", ""
        self.group: dict | None = None

    def close_group(self) -> None:
        group, self.group = self.group, None
        if group is None:
            return
        examples = tuple(Example(text=c, kind="collocation", labels=labels) for c, labels in group["collocations"])
        examples += tuple(Example(text=e) for e in group["examples"])
        if examples:
            self.senses.append(Sense(kind="collocation", pos=group["pos"], number=group["number"],
                                     phrase=group["label"], examples=examples))

    def feed(self, el) -> None:
        if has_class(el, "ocd_hw"):
            value = text(el)
            if not self.headword:
                self.headword = value
            elif value:
                self.close_group()
                self.verb, self.number = value, ""
                self.senses.append(Sense(kind="phrasal_verb", phrase=value))
        elif has_class(el, "ocd_seg"):
            self.close_group()
            self.pos, self.number, self.verb = "", "", ""
        elif has_class(el, "ocd_pos"):
            self._set_pos(text(el))
        elif has_class(el, "ocd_m1"):
            self._sense_header(el)
        elif has_class(el, "ocd_m3"):
            self._numbered_header(el)
        elif has_class(el, "ocd_ps"):
            self.close_group()
            self.group = {"label": text(el), "pos": "" if self.verb else self.pos, "number": self.number,
                          "collocations": [], "examples": []}
        elif has_class(el, "ocd_cc"):
            self._current()["collocations"] += _collocations(el)
        elif has_class(el, "ocd_ex"):
            value = text(el)
            if value:
                self._current()["examples"].append(value)
        elif has_class(el, "ocd_m2_1"):
            self._used_with(el)

    def _used_with(self, line) -> None:
        """"<b>Take</b> is used with these nouns as the object: abuse, action, …": a group of its own."""
        self.close_group()
        lead = clean("".join(b.tail or "" for b in line.xpath("./b")) or text(line))
        label, sep, _ = lead.partition(":")
        if not sep:
            return
        body = text(line)
        words = body[body.index(":") + 1:] if ":" in body else ""
        label = clean(label)
        label = label[3:] if label.startswith("is ") else label
        self.group = {"label": label, "pos": "" if self.verb else self.pos, "number": self.number,
                      "collocations": [(w, ()) for w in (clean(p) for p in words.split(",")) if w], "examples": []}
        self.close_group()

    def _set_pos(self, pos: str) -> None:
        if pos:
            self.pos = pos
            if pos not in self.pos_list:
                self.pos_list.append(pos)

    def _sense_header(self, m1) -> None:
        self.close_group()
        self.forms += [text(a) for a in m1.xpath(f".//*[{cls('ocd_als')}]") if text(a)]
        for fed in m1.xpath(f".//trn//*[{cls('ocd_fed')}]"):
            self._set_pos(text(fed))
        definition = next(iter(m1.xpath(f".//*[{cls('ocd_def')}]")), None)
        if definition is None:
            return
        number = text(next(iter(definition.xpath(f".//*[{cls('ocd_li')}]")), None))
        self._sense(number, clean("".join(definition.xpath(f".//text()[not(ancestor::*[{cls('ocd_li')}])]"))))

    def _numbered_header(self, m3) -> None:
        """"<b>2</b> start crying" directly in an ocd_m3 (no ocd_cc line): a sense header."""
        first = next(iter(m3), None)
        if first is None or first.tag != "b" or (m3.text or "").strip() or not text(first).isdigit():
            return  # a collocation line (ocd_cc) or an example (ocd_ex)
        self.close_group()
        self._sense(text(first), clean("".join(m3.xpath("./text() | ./*[position() > 1]//text()"))))

    def _sense(self, number: str, gloss: str) -> None:
        self.number = number
        if gloss:
            if self.verb:
                self.senses.append(Sense(kind="phrasal_verb", number=number, phrase=self.verb, definition=gloss))
            else:
                self.senses.append(Sense(kind="sense", pos=self.pos, number=number, definition=gloss))

    def _current(self) -> dict:
        if self.group is None:
            self.group = {"label": "", "pos": "" if self.verb else self.pos, "number": self.number,
                          "collocations": [], "examples": []}
        return self.group


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    wanted = " or ".join(cls(name) for name in _WANTED)
    reader = _Reader()
    for el in root.xpath(f"//*[{wanted}][not(ancestor::*[{cls('ocd_m2_1')}])]"):
        reader.feed(el)
    reader.close_group()
    shown = reader.headword or clean(headword)
    return Entry(headword=shown, pos=tuple(reader.pos_list), senses=tuple(reader.senses),
                 forms=tuple(f for f in dict.fromkeys(reader.forms) if f != shown), stub=_stub(root))


_CONTENT = " or ".join(cls(name) for name in ("ocd_ps", "ocd_cc", "ocd_ex", "ocd_def", "ocd_m2_1"))


def _stub(root) -> str:
    """A record with no group, collocation line, example, sense gloss or used-with list: "⇨ See X"
    (a link or the arrow) is a cross-reference; otherwise only the headword and pos are printed."""
    if root.xpath(f"//*[{_CONTENT}]"):
        return ""
    if root.xpath("//a[starts-with(@href, 'entry://')]") or "⇨" in text(root):
        return "xref"
    return "empty"
