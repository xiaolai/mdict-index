"""yhdcd's token stream: the entry walked in document order into (kind, value) pairs, undoing the
source highlighter's broken tags, plus the plain-text and header-forms readers it uses."""
from __future__ import annotations

import copy
import re

from structured.markup import class_set, clean, cls, text

_LABEL_BRACKETS = "【】〈〉<>[]［］ "
# The source's headword highlighter wrapped its own tag names when they equal the headword:
# "<<tdb>br</tdb>>" in BR, "</<tdb>ii</tdb>>" in II. _Tokens undoes it (a residue "br" is a line break).
_SOURCE_TAGS = frozenset({"br", "hh", "ii", "tr", "hw", "kg", "def", "j", "ja", "ref", "tz", "cx"})
_HIGHLIGHT_TAGS = frozenset({"tda", "tdb", "tdc", "tdd"})
# "[用以表示不在乎…]" in an etymology bracket is a usage gloss, never an etymology
_USAGE_GLOSS = re.compile(r"(用以|用于|表示|相当于)")
_BROKEN_END = re.compile(r"\s*(\w+)>")


def _plain(el) -> str:
    """Text of an element without syllable dots."""
    for dot in el.xpath(".//fgf"):
        dot.text = ""
    return text(el)


class _Tokens:
    """Document-order token stream of an entry: (kind, value) pairs.

    Only the elements whose meaning is fixed are interpreted here; whether a
    token belongs to a header or to a sense line is decided by _Builder, since
    unclosed source tags make tree ancestry meaningless.
    """

    def __init__(self) -> None:
        self.out: list[tuple[str, object]] = []

    def emit(self, kind: str, value: object = "") -> None:
        self.out.append((kind, value))

    def text(self, value: str | None) -> None:
        if value:  # white space alone too: it separates "<b>alpha</b> <i>beta</i>"
            self.emit("text", value)

    def walk(self, el) -> None:
        """Emit tokens for `el` itself; the caller emits el.tail."""
        tag = el.tag if isinstance(el.tag, str) else ""
        klass = class_set(el)
        if tag == "br":
            self.emit("br")
        elif tag == "hr" or "cxb" in klass:
            self.emit("hr")
        elif tag == "ii":
            self.emit("header_open")
            self._children(el)
            self.emit("header_close")
        elif klass & {"hw", "Z_POS_G", "cxa", "xha", "xhb"}:
            pass
        elif "tr" in klass:
            self._tr(el)
        elif "xh" in klass:
            self.emit("number", text(el).rstrip(". "))
        elif "cx" in klass:
            self.emit("pos", clean(text(el)))
        elif klass & {"lya", "lyb", "lyc"}:
            self.emit("label", text(el).strip(_LABEL_BRACKETS))
        elif "sma" in klass:
            etym = el.xpath(".//ciy")
            if etym and _USAGE_GLOSS.match(text(etym[0]).strip("[] ")):
                self.emit("gram", text(etym[0]).strip("[] "))  # the etymology bracket misused for a gloss
            elif etym:
                self.emit("etymology", text(etym[0]).strip("[] "))
            else:
                self.emit("gram", text(el).strip(_LABEL_BRACKETS))
        elif "smb" in klass:
            self.emit("smb", (el.text_content(), _forms(el)))
        elif "yb" in klass:
            self.emit("yb", el.text_content())
        elif klass & {"ea", "ec"}:
            self.emit("ex_en", text(el))
        elif klass & {"eb", "ed"}:
            self.emit("ex_zh", text(el))
        elif "ph" in klass:
            self.emit("phrase", _plain(el))
        elif "zqq" in klass:
            body = " ".join(text(z) for z in el.xpath(f".//*[{cls('zjq')}]"))
            if not body:  # the note text sometimes sits in the title span itself: "◇当及物动词 help …"
                body = " ".join(text(z) for z in el.xpath(f".//*[{cls('zj')}]")).removeprefix("◇注解").lstrip("◇ ")
            self.emit("note", body)
        elif tag == "j":
            self.emit("xref")
            self._children(el)
        else:
            self._children(el)

    def _children(self, el) -> None:
        self.text(el.text)
        for child in el:
            tail = child.tail
            if not isinstance(child.tag, str):  # a comment; "</<tdb>ii</tdb>>" parses as <!--<tdb--> + "ii>"
                m = _BROKEN_END.match(tail or "") if (child.text or "").startswith("<td") else None
                self.text(tail[m.end():] if m and m.group(1).lower() in _SOURCE_TAGS else tail)
                continue
            if self._residue(child):
                self.text(tail.lstrip()[1:])
                continue
            self.walk(child)
            self.text(tail)

    def _residue(self, child) -> bool:
        """"<" + <tdb>br</tdb> + ">": a source tag broken by the highlighter, not text."""
        name = (child.text or "").strip().lower() if len(child) == 0 else ""
        prev = self.out[-1] if self.out else None
        if not (child.tag in _HIGHLIGHT_TAGS and name in _SOURCE_TAGS and (child.tail or "").lstrip().startswith(">")
                and prev is not None and prev[0] == "text" and str(prev[1]).rstrip().endswith("<")):
            return False
        self.out[-1] = ("text", str(prev[1]).rstrip()[:-1].rstrip("</"))
        if name == "br":
            self.emit("br")
        return True

    def _tr(self, el) -> None:
        """span.tr: skip the IPA part (read separately), walk what the source's <tr> tag swallowed."""
        started = False
        for child in el:
            if not started and child.tag == "tr":
                started = True
            if started:
                self.walk(child)
                self.text(child.tail)


def _forms(smb) -> list[str]:
    """Inflected forms in a header smb: "(took /tʊk/, tak·en /ˈteɪkən/)" -> took, taken."""
    smb = copy.deepcopy(smb)
    for drop in smb.xpath(f".//*[{cls('yb')} or {cls('sma')}]"):
        drop.drop_tree()  # the forms' own IPA and "[复]"; drop_tree keeps the tail text
    raw = _plain(smb).strip()
    if raw.startswith("(") and raw.endswith(")"):
        raw = raw[1:-1]
    return [f for f in (clean(part) for part in re.split(r"[,，;；]", raw)) if f]
