"""Merriam-Webster's Collegiate Dictionary, 11th edition (MWC).

The markup has no class names: an entry is a flat run of lines separated by <br>,
recognised by tag shape and font colour. The record is cut into segments at <br>,
at the ETYMOLOGY/DATE boxes and at the homograph tables, and each segment is
classified by its opening markup:
  <font style="font-weight:bold;">hel·lo</font>     headword (syllable dots removed)
  <table ...><b>II</b></table>                        homograph number (roman, as printed)
  <a href="sound://x.spx"> \\pron\\ <b><font color=#CA0000>noun</font></b>
                                                      audio + pronunciation (MW respelling, backslashes
                                                      removed; region "us") + part of speech
  \\ə <i>also</i> (ˈ)ā\\                            italic qualifiers split one printed pron into several,
                                                      each qualifier becoming the Pron.note of what follows
  (<i>plural</i> <b>hellos</b>) / (<b>took</b> ; <b>tak·en</b>)   inflections -> forms
  <i>or</i> <b>Alost</b>                              variant -> forms
  <div ...>ETYMOLOGY ...</div>                        etymology; the DATE box stays in layer 1
  <i><font style="color:#CA0000;...">transitive verb</font></i>   function label: pos of the senses below
  <b><font color=darkslategray>1.</font></b> def    numbered sense; "a." and "(1)" nest -> "1", "1a", "1a(1)"
  <b>:</b> def                                        unnumbered sense
  <b><font color=darkslategray>10.</font></b> <i><font color=#a77225>also</font></i> <b>sett</b> \\pron\\
                                                      a variant or inflection of one sense -> forms; its own
                                                      sound link and pronunciation stay in layer 1
  <i><font color=#a77225>archaic</font></i> <b>:</b> def   label + sense; "also", "especially",
                                                      "specifically", "broadly", "or" continue the previous sense
  <font color=#0B3861>...</font>                      verbal illustration -> example ("... — Author" -> quotation)
  — used ...                                          usage gloss, appended to the sense (or the sense itself)
  • <b>abandonment</b> <i><font color=#cd0101>noun</font></i>   run-on -> derivative
  plain text                                          the definition of name/abbreviation entries
Printed angle brackets arrive escaped as a lone backslash ("\\<sic\\>") and become ⟨ ⟩.

Stubs (only for a record with no definition, and only on the pointer line it prints):
  "⇨ see X"                                   -> "xref"  ("figure skater" -> figure skating)
  <i><font color=#a77225>variant of</font></i> X -> "variant" (also "British variant of", ...)
  "plural of", "past of", "present part of", ... -> "inflection"

Left in layer 1: "Synonyms." / "Usage." paragraphs, "Synonym(s): see ..." lines,
"• • •" phrase lists (links to other records), [illustration captions], cross-reference
stubs ("variant of X", "past of X", "⇨ see X").

Coverage (full run, 119,775 records): stubs xref 28,926, variant 919, inflection 254;
89,676 content records, 0.99999 covered (only "me", a usage paragraph), so MIN_COVERAGE = 0.99.
"""
from __future__ import annotations

import re

from structured.markup import clean, parse as parse_html, text as el_text
from structured.model import Entry, Example, Pron, Sense

KEY = "mwc"
COVERS = "definitions"
MIN_COVERAGE = 0.99

_SEGMENT = re.compile(
    r"(<br\s*/?>|<div style='display:block;background-color:#f6f0e6;'>.*?</div>|<table\b.*?</table>)",
    re.I | re.S)
_LEAD = re.compile(r"^(?:\s|&nbsp;)+")
_HEADWORD = re.compile(r'<font style="font-weight:bold;">(.*?)</font>', re.S)
_POS = re.compile(r'<b><font color=#CA0000>(.*?)</font></b>', re.S)
_FUNCTION = re.compile(r'^<i><font style="color:#CA0000;[^"]*">(.*?)</font></i>', re.S)
_NUMBER = re.compile(r"^<b><(?:font color=|c )darkslategray>(.*?)</(?:font|c)></b>", re.S)
_LABEL = re.compile(r"^<i><font color=#a77225>(.*?)</font></i>", re.S)
_EXAMPLE = re.compile(r"^<font color=#0B3861>", re.S)
_COLON = re.compile(r"^<b>:</b>")
_PRON = re.compile(r"\\\\(.+?)\\\\")
_SOUND = re.compile(r'href="(sound://[^"]+)"')
_BOLD = re.compile(r"<b>(.*?)</b>", re.S)
_ITALIC = re.compile(r"<i>(.*?)</i>", re.S)
_RUNON = re.compile(r"^•\s*<b>(.*?)</b>(.*)$", re.S)
_RUNON_POS = re.compile(r"<font color=#cd0101>(.*?)</font>", re.S)
_ROMAN = re.compile(r"<b>([IVXLC]+)</b>")
_ANGLE_OPEN = re.compile(r"(?<!\\)\\<")
_ANGLE_CLOSE = re.compile(r"(?<!\\)\\>")
# A brown label straight before a bold word introduces a variant or inflection of one sense
# ("10. also <b>sett</b> \\ˈset\\", "plural <b>bricks</b> or <b>brick</b>"), with its own sound link and pronunciation.
_SENSE_FORM = re.compile(
    r'^<i><font color=#a77225>[^<]*</font></i>\s*<b>(?!:)(.*?)</b>\s*(?:<a href="sound://[^>]*>.*?</a>\s*)?(?:\\\\.+?\\\\\s*)?',
    re.S)
_DIVIDERS = frozenset({"also", "especially", "specifically", "broadly", "or", "in particular", "or formerly"})
_SIDE_HEADINGS = frozenset({"Synonyms.", "Usage.", "Synonym."})


def _plain(fragment: str) -> str:
    # lxml unescaping (the helper module that once shadowed the stdlib html module is now markup.py).
    if "<" not in fragment and "&" not in fragment:
        return clean(fragment)
    return el_text(parse_html(fragment))


def _word(fragment: str) -> str:
    return _plain(fragment).replace("·", "")


class _Builder:
    """Accumulates senses; a sense stays open so continuation lines can extend it."""

    def __init__(self) -> None:
        self.senses: list[Sense] = []
        self.open: dict | None = None
        self.levels = ["", "", ""]
        self.pos = ""

    def close(self) -> None:
        s = self.open
        self.open = None
        if s and (s["definition"] or s["examples"] or (s["kind"] != "sense" and s["phrase"])):
            self.senses.append(Sense(kind=s["kind"], pos=s["pos"], number=s["number"], phrase=s["phrase"],
                                     labels=tuple(s["labels"]), definition=clean(s["definition"]),
                                     examples=tuple(s["examples"])))

    def start(self, number: str = "", definition: str = "", labels: tuple[str, ...] = (),
              kind: str = "sense", phrase: str = "", pos: str | None = None) -> None:
        self.close()
        self.open = {"kind": kind, "pos": self.pos if pos is None else pos, "number": number, "phrase": phrase,
                     "labels": list(labels), "definition": definition, "examples": []}

    def number(self, raw: str) -> str:
        n = raw.strip().rstrip(".")
        if n.startswith("("):
            self.levels[2] = n
        elif n.isalpha() and len(n) == 1:
            self.levels[1], self.levels[2] = n, ""
        else:
            self.levels = [n, "", ""]
        return "".join(self.levels)

    def reset_numbers(self) -> None:
        self.levels = ["", "", ""]


def _label_and_rest(fragment: str) -> tuple[str, str]:
    """Split a leading brown italic label off a definition fragment."""
    m = _LABEL.match(fragment)
    if not m:
        return "", fragment
    return _plain(m.group(1)), fragment[m.end():]


def _sense_forms(fragment: str) -> tuple[list[str], str]:
    """Split the variants and inflections printed at the head of a sense off its text: (forms, rest)."""
    forms = []
    while m := _SENSE_FORM.match(fragment):
        forms.append(_word(m.group(1)))
        fragment = fragment[m.end():]
    return forms, fragment


def _definition_text(fragment: str) -> str:
    return _plain(fragment).lstrip(":").strip()


def _example(fragment: str) -> Example | None:
    value = _plain(fragment)
    if not value:
        return None
    head, sep, source = value.rpartition(" — ")
    if sep and head and 0 < len(source) <= 80 and source[:1].isupper():  # "... — Anthony Lewis"
        return Example(text=head, kind="quotation", source=source)
    return Example(text=value)


def _pointer_kind(printed: str) -> str:
    """Stub reason for a printed pointer label ("chiefly British variant of", "past participle of")."""
    words = set(printed.lower().replace("&", " ").split())
    if words & {"variant", "spelling"}:
        return "variant"
    if words & {"past", "plural", "participle", "part", "present", "singular", "case", "comparative", "superlative"}:
        return "inflection"
    return "xref"


def _split_paren(segment: str) -> tuple[str, str]:
    """Split "(...)rest" after the parenthesis that closes the leading one."""
    depth = 0
    for i, ch in enumerate(segment):
        depth += (ch == "(") - (ch == ")")
        if depth == 0:
            return segment[: i + 1], segment[i + 1:]
    return segment, ""


def _pron_parts(raw: str) -> list[tuple[str, str]]:
    """Split one printed pronunciation at its italic qualifiers: each qualifies what follows it.

    "ə <i>also</i> (ˈ)ā" -> [("ə", ""), ("(ˈ)ā", "also")].
    """
    pieces = _ITALIC.split(raw)  # text, label, text, label, text ...
    out = []
    for i in range(0, len(pieces), 2):
        ipa = _plain(pieces[i]).strip(" ,;")
        note = _plain(pieces[i - 1]) if i else ""
        if ipa:
            out.append((ipa, note))
    return out


def _add_prons(fragment: str, prons: list[Pron]) -> None:
    """Pair the n-th sound:// link with the first transcription of the n-th \\pron\\ of a headword line."""
    sounds = _SOUND.findall(fragment)
    groups = [_pron_parts(p) for p in _PRON.findall(fragment)]
    for i in range(max(len(sounds), len(groups))):
        parts = groups[i] if i < len(groups) else []
        audio = sounds[i] if i < len(sounds) else ""
        candidates = [Pron(ipa=ipa, region="us", audio=audio if j == 0 else "", note=note)
                      for j, (ipa, note) in enumerate(parts)] or [Pron(ipa="", region="us", audio=audio)]
        for p in candidates:
            if (p.ipa or p.audio) and p not in prons and (p.ipa or all(q.audio != p.audio for q in prons)):
                prons.append(p)


class _Reader:
    """Reads a record's segments in order; the state its lines share lives here."""

    def __init__(self) -> None:
        self.shown = self.homograph = ""
        self.homographs = 0
        self.all_pos: list[str] = []
        self.prons: list[Pron] = []
        self.forms: list[str] = []
        self.etymology: list[str] = []
        self.b = _Builder()
        self.skipping = False  # inside a Synonyms./Usage. paragraph or a "• • •" phrase list
        self.pointers: list[str] = []  # stub reasons printed by pointer lines, in order

    def read(self, seg: str) -> None:
        if seg.startswith("<div"):
            body = _plain(seg)
            if body.startswith("ETYMOLOGY"):
                self.etymology.append(body[len("ETYMOLOGY"):].strip())
            return
        if seg.lower().startswith("<table"):
            self._new_block()
            m = _ROMAN.search(seg)
            self.homographs += 1
            if m and self.homographs == 1:
                self.homograph = m.group(1)
            return
        head = _HEADWORD.match(seg)
        if head:
            self.shown = self.shown or _word(head.group(1))
            seg = seg[head.end():].strip()
            if not seg:
                return
        if not (self._headword_line(seg) or self._side_line(seg)):
            self._sense_line(seg)

    def _new_block(self) -> None:
        """A homograph table or a part-of-speech line: the open sense, the numbering and any skipping end."""
        self.b.close()
        self.b.reset_numbers()
        self.skipping = False

    def _headword_line(self, seg: str) -> bool:
        """Part of speech, pronunciations, inflections and variants; True when the line was one of them."""
        b = self.b
        pos_m = _POS.search(seg)
        if pos_m and not seg.startswith("(<"):
            self._new_block()
            b.pos = _plain(pos_m.group(1))
            if b.pos and b.pos not in self.all_pos:
                self.all_pos.append(b.pos)
            _add_prons(seg[:pos_m.start()], self.prons)
        elif seg.startswith('<a href="sound://') or seg.startswith("\\"):
            _add_prons(seg, self.prons)  # a headword pronunciation printed without a part of speech
        elif seg.startswith("(<"):
            inflections, rest = _split_paren(seg)
            self.forms += [w for w in (_word(x) for x in _BOLD.findall(inflections)) if w and not w.startswith("-")]
            rest = _plain(_PRON.sub("", rest))
            if rest:  # "(<i>or</i> <b>III</b>) 1075-1137 king of Germany": a name entry's definition follows
                b.start(definition=rest)
        elif seg.startswith("<i>or</i>") or seg.startswith("<i>also</i>"):
            self.forms += [w for w in (_word(x) for x in _BOLD.findall(seg)) if w]
        else:
            return False
        return True

    def _side_line(self, seg: str) -> bool:
        """Side paragraphs, phrase lists and run-ons, and the lines skipped inside them; True when handled."""
        b = self.b
        number = _NUMBER.match(seg)
        if number and _plain(number.group(1)) in _SIDE_HEADINGS:
            b.close()
            self.skipping = True
        elif seg.startswith("<b>Synonym"):
            b.close()
        elif seg.startswith("•"):
            b.close()
            run = _RUNON.match(seg)
            self.skipping = run is None
            if run:
                phrase = _word(run.group(1))
                pos = _plain(" ".join(_RUNON_POS.findall(run.group(2))))
                if phrase:  # a run-on has no definition; it is kept for its phrase and any examples
                    b.start(kind="derivative", phrase=phrase, pos=pos)
        elif not (self.skipping or seg.startswith("- <a") or seg.startswith("[<font color=navy>")):
            return False
        return True

    def _sense_line(self, seg: str) -> None:
        b = self.b
        function = _FUNCTION.match(seg)
        if function:
            b.close()
            b.reset_numbers()
            b.pos = _plain(function.group(1))
        elif _EXAMPLE.match(seg):
            ex = _example(seg)
            if ex and b.open is not None:
                b.open["examples"].append(ex)
        elif number := _NUMBER.match(seg):
            self._numbered(number, seg)
        elif _COLON.match(seg):
            text = _definition_text(seg)
            if b.open is not None and not b.open["definition"]:
                b.open["definition"] = text
            else:
                b.start(definition=text)
        elif _LABEL.match(seg):
            self._labelled(seg)
        else:
            self._plain_line(seg)

    def _numbered(self, number: re.Match, seg: str) -> None:
        b = self.b
        full = b.number(_plain(number.group(1)))
        sense_forms, rest = _sense_forms(_LEAD.sub("", seg[number.end():]).removeprefix("<font color=black>").strip())
        self.forms += [w for w in sense_forms if w and not w.startswith("-")]
        label, rest = _label_and_rest(rest)
        definition = _definition_text(rest)
        if label in _DIVIDERS:  # "especially : ..." opening a sense is part of its text, not a label
            label, definition = "", f"{label} : {definition}"
        b.start(number=full, definition=definition, labels=(label,) if label else ())

    def _labelled(self, seg: str) -> None:
        b = self.b
        label, rest = _label_and_rest(seg)
        if not label:
            self._plain_line(seg)
            return
        text = _definition_text(rest)
        if label.endswith(" of"):
            self.pointers.append(_pointer_kind(label))  # "variant of X", "past of X": a cross-reference, not a definition
        elif label in _DIVIDERS and b.open is not None:
            previous = b.open["definition"].rstrip(";")
            b.open["definition"] = clean(f"{previous}; {label} : {text}" if previous else f"{label} : {text}")
        else:
            b.start(definition=text, labels=(label,))

    def _plain_line(self, seg: str) -> None:
        b = self.b
        text = _plain(seg)
        if text.startswith("⇨"):
            self.pointers.append("xref")  # "⇨ see café": a cross-reference record
        elif text.startswith("—") and b.open is not None:
            b.open["definition"] = clean(f"{b.open['definition']} {text}")
        elif text:
            b.start(definition=text)


def parse(headword: str, html: str) -> Entry:
    r = _Reader()
    # The source escapes printed angle brackets as \< and \> ("\<sic\>", "f \<u(x)\>"); a lone
    # backslash, unlike the doubled one around pronunciations.
    source = _ANGLE_OPEN.sub("⟨", _ANGLE_CLOSE.sub("⟩", html or ""))
    for raw in _SEGMENT.split(source):
        seg = _LEAD.sub("", raw or "").strip()
        if seg and not re.fullmatch(r"<br\s*/?>", seg, re.I):
            r.read(seg)
    r.b.close()

    shown = r.shown or clean(headword)
    stub = "" if any(s.definition for s in r.b.senses) or not r.pointers else r.pointers[0]
    homograph = r.homograph if r.homographs == 1 else ""
    return Entry(headword=shown, homograph=homograph, pos=tuple(r.all_pos), prons=tuple(r.prons),
                 senses=tuple(r.b.senses), etymology=clean("; ".join(e for e in r.etymology if e)),
                 forms=tuple(f for f in dict.fromkeys(r.forms) if f and f != shown), stub=stub)
