"""英汉大词典 第2版 (The English-Chinese Dictionary, 2nd edition).

The markup is a flat, line-oriented stream: most structure is carried by <br>
line breaks and by short class codes, and the source's custom tags (<tr>, <j>,
<kg>, ...) are often left unclosed, so the lxml tree nests them arbitrarily.
The parser therefore never trusts nesting below <def>: it walks the tree in
document order into a token stream and rebuilds the entry line by line.

Class codes, decoded from real entries:
  hw            headword as printed; <fgf>·</fgf> syllable dots are dropped,
                a trailing superscript digit (¹²³) is the homograph number
  tr            span whose own leading text is the IPA, "/ˈeɪ/" or "/a/,/b/";
                everything after its inner <tr> tag is the rest of the entry
  Z_POS_G       navigation bar listing the entry's parts of speech (skipped)
  ii            a part-of-speech header block: xhb (I, II: homograph-like
                group), xha (❶ ❷: pos group), tz > cx (the pos, "vt."), cxa
                ("&" joining two pos), smb inside the header = inflected forms
                "(took /tʊk/, tak·en /ˈteɪkən/)", with yb = the forms' IPA and
                sma "[复]" = "plural"; a yb directly in the header is the IPA
                of that pos group ("II /dɪˈmɪdɪət/ a."): an extra pron; a
                label inside the header applies to every sense after it
  xh            sense number "1."
  lya / lyb / lyc  labels: 【医】 subject, 〈口〉 register/region, <美>
  sma           bracketed grammar/usage note "[常用被动语态]" (kept as a label);
                an sma wrapping <ciy> is the etymology "[< OE tacan ...]"
  smb / smc / dh  inline parentheses and "＝ X" equivalences: part of the text
  ea / eb       example English / Chinese, in a numbered-sense block
  ec / ed       example English / Chinese, inside the phrase section
  cxb "phr."    opens the phrase section (div.ref); each ph is a phrase, its
                senses follow exactly like headword senses
  <j>           "见 X" cross-reference: the rest of its line is not a definition
  div.zqq       "◇注解" usage note box: zj title, zjq body -> a note sense
  hr            separator between homograph-like groups (I / II)

A definition line is the text after an optional xh number and labels; it is
almost always Chinese (-> definition_zh); a line with no CJK at all (Latin
expansions of abbreviations, "= X") goes to definition. Plain definition text
before an example is one sense; an unnumbered line after a header or phrase is
an unnumbered sense. Senses in the phrase section are kind "phrase" (the
dictionary does not separate phrasal verbs from idioms). Source damage handled:
the headword highlighter wrapped the source's own tag names when they equal the
headword ("<<tdb>br</tdb>>" in BR, "</<tdb>ii</tdb>>" in II); the tokenizer drops
that residue, and a residue "br" is still a line break. A literal "<" in text
(etymology "[<Hind bel]") is dictionary text and stays as printed.

Stubs, from what the record's markup holds when it has no gloss, example,
phrase or note (checked on every record, 232,686): only "见 X" lines -> "xref";
a pos header or IPA without any definition, the dictionary's run-on derivative
format ("frig·id·ness n.") -> "derivative"; the headword alone -> "empty". A
record with only an etymology bracket is content (and uncovered). The bracket
is sometimes misused for a usage gloss ("what the hey": "[用以表示不在乎…]");
one starting 用以/用于/表示/相当于 is read as a gloss, not an etymology. The
new element names (bohrium, meitnerium) are set in private-use glyphs of the
dictionary's font; such a glyph is a Chinese definition as printed. A 注解
note whose text sits in its title span (zj without zjq) is read from there.
The 5 uncovered content records (full run): 2 with only an etymology, and 3
"见 X" records ("worse luck", "think fit (to do)", "die in the last ditch")
carrying example sentences that belong to a neighbouring headword.
"""
from __future__ import annotations

import re

from structured.markup import SUPERSCRIPT, clean, cls, has_cjk, parse as parse_html, strip_slashes
from structured.model import Entry, Example, Pron, Sense
from structured.parsers._yhdcd_tokens import _Tokens, _plain

KEY = "yhdcd"
COVERS = "definitions"
MIN_COVERAGE = 0.99  # policy min(0.99, measured): 198,916 of 198,921 content records (33,765 stubs)

_HOMOGRAPH = re.compile(f"([{''.join(SUPERSCRIPT)}]+)$")
_IPA = re.compile(r"/([^/]+)/")
_EDGE_PUNCT = " :：;；,，"
# a Chinese name set in a private-use glyph (the new element names: bohrium, meitnerium)
_WORD = re.compile(r"[\w\ue000-\uf8ff]")


def _zh(value: str) -> bool:
    return has_cjk(value) or bool(re.search(r"[\ue000-\uf8ff]", value))


class _Builder:
    """Rebuilds senses from the token stream, one <br> line at a time.

    Labels are (kind, value) pairs: kind "gram" marks a bracketed sma note from
    a sense line, which becomes the definition when the sense has no other
    Chinese gloss ("[用以表示不在乎…]" followed only by examples).
    """

    def __init__(self) -> None:
        self.senses: list[Sense] = []
        self.pos_list: list[str] = []
        self.forms: list[str] = []
        self.etymology: list[str] = []
        self.prons: list[str] = []
        self.kind, self.phrase, self.pos = "sense", "", ""
        self.block_labels: list[tuple[str, str]] = []
        self.block_start = 0
        self.header = False
        self.cur: dict | None = None
        # markup evidence for stub records: what kinds of content the record's markup holds
        self.seen_content = self.seen_xref = self.seen_header = False
        self._new_line()

    def _new_line(self) -> None:
        self.line_labels: list[tuple[str, str]] = []
        self.line_has_content = False
        self.line_xref = False

    def _open(self, number: str = "") -> dict:
        self.flush()
        self.cur = {"number": number, "labels": list(self.block_labels), "text": [], "examples": []}
        return self.cur

    def _sense(self, number: str, labels: list[tuple[str, str]], definition: str, examples: tuple) -> None:
        definition = clean(definition).strip(_EDGE_PUNCT)
        plain = [clean(v) for _, v in labels]
        if not _zh(definition):
            glosses = [clean(v) for k, v in labels if k == "gram" and has_cjk(v)]
            if glosses:
                plain = [v for v in plain if v not in glosses]
                definition = clean(" ".join(glosses + [definition])).strip(_EDGE_PUNCT)
        if not (definition or examples):
            return
        zh = _zh(definition)
        kind = self.kind if self.phrase else "sense"
        self.senses.append(Sense(
            kind=kind, pos=self.pos if kind == "sense" else "", number=number,
            phrase=self.phrase if kind != "sense" else "", labels=tuple(dict.fromkeys(v for v in plain if v)),
            definition="" if zh else definition, definition_zh=definition if zh else "", examples=examples))

    def flush(self) -> None:
        cur, self.cur = self.cur, None
        if cur is not None:
            examples = tuple(Example(text=clean(e.text), text_zh=clean(e.text_zh)) for e in cur["examples"])
            examples = tuple(e for e in examples if e.text or e.text_zh)
            self._sense(cur["number"], cur["labels"], clean("".join(cur["text"])).strip(_EDGE_PUNCT), examples)

    def close_block(self) -> None:
        self._end_line()  # first: a last line of labels only ("2." then "[用以…]") belongs to the open sense
        self.flush()
        if len(self.senses) == self.block_start and any(k == "gram" for k, _ in self.block_labels):
            self._sense("", self.block_labels, "", ())  # a block whose only gloss is a bracketed note
        self.block_start = len(self.senses)
        self.block_labels = []
        self._new_line()

    def _block(self, kind: str, phrase: str, pos: str) -> None:
        self.close_block()
        self.kind, self.phrase, self.pos = kind, phrase, pos

    def feed(self, kind: str, value) -> None:
        if kind == "text" and not _WORD.search(value):
            if self.header:
                return  # "n., vt. & vi.": punctuation between parts of speech
        elif self.header and kind not in ("header_close", "pos", "label", "gram", "smb", "yb", "br", "etymology"):
            self.header = False  # header text in malformed entries ("〈古〉work的过去式") is a sense
        if kind in ("header_open", "pos"):
            self.seen_header = True
        elif kind in ("ex_en", "ex_zh", "phrase", "note", "number") or (kind == "gram" and not self.header):
            self.seen_content = True
        if self.header:
            self._feed_header(kind, value)
        elif kind == "header_open":
            self._block("sense", "", "")
            self.header = True
        elif kind == "pos":
            if value:
                self._block("sense", "", value)
                self.pos_list.append(value)
        elif kind == "phrase":
            phrase = clean(value)
            self._block("phrase" if phrase else "sense", phrase, "" if phrase else self.pos)
        elif kind == "hr":
            self.close_block()
        elif kind == "number":
            self._open(value)
            self._take_line_labels()
            self.line_has_content = True
        elif kind in ("label", "gram"):
            if value:
                target = self.cur["labels"] if self.cur is not None and self.line_has_content else self.line_labels
                target.append((kind, value))
        elif kind in ("text", "smb", "yb"):
            self._text(value[0] if kind == "smb" else value)
        elif kind == "ex_en":
            self._example().append(Example(text=clean(value)))
        elif kind == "ex_zh":
            examples = self._example()
            if examples and not examples[-1].text_zh:
                examples[-1] = Example(text=examples[-1].text, text_zh=clean(value))
            else:
                examples.append(Example(text="", text_zh=clean(value)))
        elif kind == "xref":
            self.line_xref = self.seen_xref = True
        elif kind == "note":
            self.flush()
            note = clean(value)
            if note:
                zh = _zh(note)
                self.senses.append(Sense(kind="note", definition="" if zh else note, definition_zh=note if zh else ""))
        elif kind == "etymology":
            self._etymology(value)
        elif kind == "br":
            self._end_line()
            self._new_line()
            self._space()  # a definition continued on the next line: "alpha<br>beta"

    def _feed_header(self, kind: str, value) -> None:
        if kind == "header_close":
            self.header = False
        elif kind == "pos" and value:
            self.pos_list.append(value)
            self.pos = self.pos or value  # "a. & n.": the block's senses carry the first
        elif kind in ("label", "gram") and value:
            self.block_labels.append(("label", value))  # header labels govern the block, never become glosses
        elif kind == "smb":
            self.forms += value[1]
        elif kind == "yb":
            self.prons.append(value)  # "II /dɪˈmɪdɪət/ a.": the pronunciation of this pos group
        elif kind == "etymology":
            self._etymology(value)

    def _text(self, value: str) -> None:
        if self.line_xref:
            return
        if not value.strip():
            self._space()
            return
        self.seen_content = self.seen_content or bool(_WORD.search(value))
        if self.cur is None or (not self.line_has_content and self.cur["examples"]):
            self._open()
        if not self.line_has_content:
            self._take_line_labels()
        self.cur["text"].append(value)
        self.line_has_content = True

    def _space(self) -> None:
        """White space printed inside the open sense's definition; never content of its own."""
        if self.cur is not None and self.cur["text"]:
            self.cur["text"].append(" ")

    def _end_line(self) -> None:
        if self.line_labels and not self.line_has_content:
            # a line of labels only ("〈口〉" under a phrase) governs the senses that follow it
            if self.cur is not None and not self.cur["text"] and not self.cur["examples"]:
                self._take_line_labels()
            else:
                self.block_labels += self.line_labels
        self.line_labels = []

    def _take_line_labels(self) -> None:
        self.cur["labels"] += self.line_labels
        self.line_labels = []

    def _etymology(self, value: str) -> None:
        value = clean(value)
        if value and value not in self.etymology:
            self.etymology.append(value)

    def _example(self) -> list[Example]:
        if self.cur is None:
            self._open()
        return self.cur["examples"]


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    hw_el = next(iter(root.xpath(f"//*[{cls('hw')}]")), None)
    shown = clean(_plain(hw_el)) if hw_el is not None else ""
    homograph = ""
    if m := _HOMOGRAPH.search(shown):
        homograph = "".join(SUPERSCRIPT[c] for c in m.group(1))
        shown = shown[: m.start()].strip()

    prons: list[Pron] = []
    tr = next(iter(root.xpath(f"//span[{cls('tr')}]")), None)
    if tr is not None:
        parts = [tr.text or ""]
        for child in tr:
            if child.tag == "tr":
                break
            parts += [child.text_content(), child.tail or ""]
        raw = clean("".join(parts))
        ipas = _IPA.findall(raw) or ([raw] if raw else [])
        prons = [Pron(ipa=ipa) for ipa in (strip_slashes(i) for i in ipas) if ipa]

    tokens = _Tokens()
    body = next(iter(root.xpath("//def")), root)
    tokens.walk(body)
    builder = _Builder()
    for kind, value in tokens.out:
        builder.feed(kind, value)
    builder.close_block()
    for raw in builder.prons:
        ipa = strip_slashes(clean(raw))
        if ipa and Pron(ipa=ipa) not in prons:
            prons.append(Pron(ipa=ipa))

    etymology = " ".join(builder.etymology)
    return Entry(headword=shown or clean(headword), homograph=homograph,
                 pos=tuple(dict.fromkeys(builder.pos_list)), prons=tuple(prons), senses=tuple(builder.senses),
                 etymology=etymology, forms=tuple(dict.fromkeys(builder.forms)),
                 stub=_stub(builder, bool(prons), bool(etymology)))


def _stub(builder: _Builder, has_ipa: bool, has_etymology: bool) -> str:
    """Stub reason from what the record's markup holds, when it holds no gloss, example, phrase or note:
    only "见 X" lines -> xref; a pos header or IPA (with forms, etymology) -> a run-on derivative printed
    without a definition; the headword alone -> empty. An etymology alone is content (uncovered)."""
    if builder.seen_content:
        return ""
    if builder.seen_xref:
        return "xref"
    if builder.seen_header or has_ipa:
        return "derivative"
    return "" if has_etymology else "empty"
