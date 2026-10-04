"""The Chambers Dictionary, 13th edition (cb13).

A record is a <cb13 hw="…"> holding one or more cb13_entry blocks (word_entry,
extracted_entry, phrase_entry, phrases_entry). The MDict build files every block
that mentions a word under that word, so the "yucky" record also carries the
whole "yuck" and "yuke" entries (in whose run-on lists "yucky" appears), and
"unrepaid" carries the whole "un-" prefix entry. Attribution therefore:
  1. blocks whose head (h2 > span.hw | span.mwe | span.var) is the record's word
     are parsed in full;
  2. from the other blocks, only the phrase_block > phrase items whose span.mwe
     is the record's word are taken;
  3. if neither matches (the record is an inflection, "triticales" -> the
     "triticale" block), every block except affix entries ("un-", "-ness") is
     parsed in full, and the headword shown is the block's.
Words are compared case-, accent-, stress-mark- and punctuation-insensitively.

Block structure:
  h2 > span.hw (or span.mwe in h2.phrase_title), sup (homograph number),
       a.pron (Chambers respelling, one per alternative, slashes around the group),
       span.var (variant spellings), span.ctx (labels of the headword; not copied
       to senses, as they may qualify a variant only)
  body, in document order: span.pos (sets the part of speech), span.ctx (labels for
       the definitions that follow), span.inf (inflections), ol > li (numbered
       definitions) or p.dg (a single definition), div.etym, phrase_block,
       def_hide > c_hide (a collapsed definition of the base form; parsed as body)
  phrase_block > phrase > phrase_h > span.mwe (+ span.pos, span.ctx, a.aa "see under")
                        > phrase_def (the same body structure)
       A phrase with a part of speech is a run-on derivative or compound; one
       without is an idiom, or a phrasal verb when it is the headword plus particles and
       the entry that lists it has a verb part of speech ("all in" under "all" is an idiom).
       A derivative listed with only its part of speech is kept (phrase + pos, no
       definition); an item that only says "see under X" is dropped.
  span.ctx wrapped in parentheses at the end of a definition ("… (Spenser)") is
  moved from the definition to the labels; mid-sentence it stays in the text.
  Respelling marks (stress ˈ, macron, breve) are removed from headwords, phrases
  and forms; other diacritics stay.

Left in layer 1: p.lnk ("—Also spelt …", notes), m_entry (the parent entry's
name), span.xg (the base word of a prefixed form), a.aa cross-references.

A block's head may carry the whole entry after the words and pronunciations
("abricock /abˈri-kok/ an obsolete form of <a>apricot</a>", "about-turn noun and
intransitive verb same as about-face above"); that text is a definition only when
the block has no ol / p.dg of its own. Text between the head words ("or", "(esp)",
"also") is not. A head with span.GRA ("pat and pap of aby") is an inflection pointer.

Stubs (Entry.stub, set only on records with no definition), full run of 305,069
records: 50,299 "derivative" (run-ons printed with a part of speech only, extracted
run-ons with nothing more, and un-/non-/super- formations listed under the prefix),
1,162 "xref" ("see under X", "see above"), 331 "inflection" (span.GRA heads),
16 "variant" (a form printed inside another word's definition, or "Spenserian for X"),
4 "empty" (the head alone). Coverage over the 253,257 content records is 0.99999:
"barrio" and "prosoma" have a pronunciation and an etymology but no definition.
"""
from __future__ import annotations

import copy
import re
import unicodedata
from dataclasses import replace

from structured.markup import class_set, cls, clean, parse as parse_html, strip_slashes, text
from structured.model import Entry, Pron, Sense, covered

KEY = "chambers"
COVERS = "definitions"
MIN_COVERAGE = 0.99  # min(0.99, measured 253,255 / 253,257 content records); see above

_PARTICLES = frozenset(
    "about above across after against along apart around aside at away back behind by down for forth "
    "forward from in into off on onto out over past round through to together under up upon with without".split())
_TRAILING_PARENS = re.compile(r"\s*\(([^()]*)\)$")
_EMPTY_PARENS = re.compile(r"\s*\(\s*\)")
_INLINE = frozenset({"a", "i", "b", "em", "sup", "sub", "span", "small"})
_INLINE_GRAMMAR = frozenset({"ctx", "inf", "GRA", "INFLX", "NUM", "xg"})  # never part of a loose definition
_GRAMMAR_PARENS = re.compile(r"\((?:\s|[,;:]|\band\b|\bor\b)*\)")  # "(pl … or …)" once its spans are gone
_WRAPPED = re.compile(r"\((.*)\)\.?")
_CONNECTIVES = r"\b(?:and|or|etc|also|now|esp|orig|formerly|sometimes|chiefly)\b"
_RESIDUE = re.compile(rf"(?:\s|[,;:.()]|{_CONNECTIVES})*")  # "noun and transitive verb" leaves only "and"
_LEADING = re.compile(rf"^(?:\s|[),;:]|{_CONNECTIVES})+")  # "etc same as X", ") a Spenserian spelling of X"
_SEE = re.compile(r"\bsee\b", re.I)
_VERB = re.compile(r"\bverb\b")  # "transitive verb", "verb", not "adverb"
_RESPELL = re.compile("[\u0304\u0306]")  # combining macron, breve: vowel-length marks, not spelling


def _key(value: str) -> str:
    """Comparison key: lower case, no accents, macrons, stress marks, spaces or punctuation."""
    value = unicodedata.normalize("NFKD", value.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in value if not unicodedata.combining(c)))


def _unstress(value: str) -> str:
    """Drop Chambers' respelling marks from a word: stress (ˈ), macron and breve (tāˈken -> taken)."""
    value = unicodedata.normalize("NFD", value.replace("ˈ", "").replace("ʹ", ""))
    return clean(unicodedata.normalize("NFC", _RESPELL.sub("", value)))


def _heads(block) -> list[str]:
    return [text(x) for x in block.xpath(f"./h2/span[{cls('hw')} or {cls('mwe')} or {cls('var')}]")]


def _is_affix(block) -> bool:
    heads = _heads(block)
    return bool(heads) and (heads[0].endswith("-") or heads[0].startswith("-"))


def _definition(el) -> tuple[str, tuple[str, ...]]:
    """(definition, labels) of an li or p.dg; labels are its span.ctx."""
    labels = tuple(dict.fromkeys(t for t in (text(c) for c in el.xpath(f".//span[{cls('ctx')}]")) if t))
    full = text(el)
    m = _TRAILING_PARENS.search(full)
    if labels and m and clean(re.sub(r"[,;]|\band\b|\bor\b", " ", m.group(1))) == " ".join(labels):
        full = full[: m.start()]
    return clean(_EMPTY_PARENS.sub("", full)), labels


class _Body:
    """Walks one body (a block, a phrase_def or a c_hide) collecting senses, forms and etymology.

    Besides ol > li and p.dg, a definition may be bare text after the part of speech
    ("noun same as <a.aa>ether</a> (but not …)"); such loose text is gathered between
    structural elements and becomes a definition once the grammar residue is removed.
    """

    def __init__(self, kind: str, phrase: str, pos: str, labels: tuple[str, ...] = ()):
        self.kind, self.phrase, self.pos = kind, phrase, pos
        self.pending: list[str] = list(labels)
        self.senses: list[Sense] = []
        self.forms: list[str] = []
        self.prons: list[Pron] = []
        self.etymology = ""
        self.poses: list[str] = [pos] if pos else []
        self._loose: list[str] = []

    def _append(self, definition: str, labels: tuple[str, ...], number: str) -> None:
        if definition:
            self.senses.append(Sense(kind=self.kind, pos=self.pos, number=number, phrase=self.phrase,
                                     labels=tuple(dict.fromkeys(self.pending + list(labels))),
                                     definition=definition))

    def _flush(self) -> None:
        loose, self._loose = "".join(self._loose), []
        previous = None
        while previous != loose:  # "(pat and pap (Spenser) breadˈed)" empties from the inside out
            previous, loose = loose, _GRAMMAR_PARENS.sub("", loose)
        loose = clean(loose).strip(",;: ")
        if _RESIDUE.fullmatch(loose):
            return
        if not loose.startswith("("):
            loose = _LEADING.sub("", loose)
        if loose.endswith(")") and loose.count(")") > loose.count("("):
            loose = loose[:-1].rstrip()
        if (m := _WRAPPED.fullmatch(loose)) and "(" not in m.group(1):
            # "(with <i>with</i>; informal)" before a definition: a construction note, kept as a label
            if (note := clean(m.group(1)).strip(",;: ")) and note not in self.pending:
                self.pending.append(note)
            return
        if loose.lower().startswith("see "):
            return  # "see under yuck": a pointer, not a definition
        self._append(loose, (), "")

    def walk(self, container, phrases: list[Sense] | None, skip=None) -> None:
        """Walk the children of `container` (except `skip`, the block's h2); run-on
        phrases go to `phrases`, or are ignored when it is None (inside a phrase)."""
        if container.text:
            self._loose.append(container.text)
        for el in container:
            if isinstance(el.tag, str) and el is not skip:
                self._element(el, phrases)
            if el.tail:
                self._loose.append(el.tail)
        self._flush()

    def _element(self, el, phrases: list[Sense] | None) -> None:
        classes = class_set(el)
        if el.tag == "span" and classes & _INLINE_GRAMMAR:
            if "ctx" in classes and (label := text(el)) and label not in self.pending:
                self.pending.append(label)
            elif "inf" in classes and (form := _unstress(text(el))) and form not in self.forms:
                self.forms.append(form)
            return
        if el.tag == "a" and "pron" in classes:
            if ipa := strip_slashes(text(el)):
                self.prons.append(Pron(ipa=ipa))
            return
        if el.tag in _INLINE and not (el.tag == "span" and "pos" in classes):
            raw = el.text_content()  # text() strips: keep the spaces inside the markup ("A <i>small </i>spoon")
            self._loose.append((" " if raw[:1].isspace() else "") + text(el) + (" " if raw[-1:].isspace() else ""))
            return
        self._flush()  # a structural element ends any loose definition
        if el.tag == "span" and "pos" in classes:
            self.pos = text(el)
            self.pending = []
            if self.pos and self.pos not in self.poses:
                self.poses.append(self.pos)
        elif el.tag == "ol":
            for i, li in enumerate(el.xpath("./li"), 1):
                self._append(*_definition(li), str(i))
        elif el.tag == "p" and "dg" in classes:
            self._append(*_definition(el), "")
        elif el.tag == "div" and "etym" in classes:
            self.etymology = self.etymology or text(el)
        elif el.tag == "def_hide":
            for hidden in el.xpath("./c_hide"):
                self.walk(hidden, phrases)
        elif el.tag == "phrase_block" and phrases is not None:
            for item in el.xpath("./phrase"):
                phrases.extend(_phrase(item))


def _phrase_kind(phrase: str, has_pos: bool, verbal: bool) -> str:
    """`verbal`: the phrase is listed under a verb; "all in" under an adjective is an idiom."""
    if has_pos:
        return "derivative"
    words = phrase.lower().split()
    return "phrasal_verb" if verbal and len(words) >= 2 and all(w in _PARTICLES for w in words[1:]) else "phrase"


def _under_a_verb(item) -> bool:
    """Whether the entry that lists this phrase has a verb among its own parts of speech."""
    block = next(item.iterancestors("cb13_entry"), None)
    return block is not None and any(
        _VERB.search(text(p)) for p in block.xpath(f".//span[{cls('pos')}][not(ancestor::phrase)]"))


def _phrase(item, prefer: str = "") -> list[Sense]:
    """Senses of one phrase_block item; `prefer` picks which of "yukˈy or yuckˈy" names it."""
    head = next(iter(item.xpath("./phrase_h")), None)
    if head is None:
        return []
    names = [_unstress(text(m)) for m in head.xpath(f"./span[{cls('mwe')}]")]
    phrase = next((n for n in names if prefer and _key(n) == prefer), names[0] if names else "")
    if not phrase:
        return []
    head_pos = text(next(iter(head.xpath(f"./span[{cls('pos')}]")), None))
    head_labels = tuple(t for t in (text(c) for c in head.xpath(f"./span[{cls('ctx')}]")) if t)
    defs = item.xpath("./phrase_def")
    has_pos = bool(head_pos) or any(d.xpath(f"./span[{cls('pos')}]") for d in defs)
    kind = _phrase_kind(phrase, has_pos, _under_a_verb(item))
    body = _Body(kind, phrase, head_pos, head_labels)
    for d in defs:
        body.walk(d, None)
    if body.senses:
        return body.senses
    if head_pos:  # a run-on derivative listed with its part of speech only
        return [Sense(kind=kind, pos=head_pos, phrase=phrase, labels=head_labels)]
    if has_pos:  # the same, with the part of speech (and labels) in the body: "<pos>noun</pos> (informal)"
        own = tuple(t for d in defs for c in d.xpath(f"./span[{cls('ctx')}]") if (t := text(c)))
        return [Sense(kind=kind, pos=body.pos, phrase=phrase, labels=tuple(dict.fromkeys(head_labels + own)))]
    return []


def _head_rest(h2):
    """What follows the last word of the h2 (headword, variant, pron, homograph number):
    its pos and any cross-reference definition ("/abˈri-kok/ an obsolete form of
    <a>apricot</a>"). Text between the words ("or", "(esp)", "also") is not taken.
    An inflection pointer ("<span.GRA>pat</span> and pap of aby") is data-less."""
    rest = copy.deepcopy(h2)  # an lxml.html element, emptied
    for child in list(rest):
        rest.remove(child)
    rest.text = rest.tail = None
    if h2.xpath(f"./span[{cls('GRA')}]"):
        return rest
    words = h2.xpath(f"./span[{cls('hw')} or {cls('mwe')} or {cls('var')}] | ./sup | ./a[{cls('pron')}]")
    if not words:
        return rest
    last = words[-1]
    rest.text = last.tail
    nxt = last.getnext()
    while nxt is not None:
        rest.append(copy.deepcopy(nxt))
        nxt = nxt.getnext()
    return rest


def _prons(el, path: str) -> list[Pron]:
    return [Pron(ipa=ipa) for ipa in (strip_slashes(text(a)) for a in el.xpath(path)) if ipa]


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    blocks = root.xpath("//cb13_entry")
    want = _key(headword)
    primary = [b for b in blocks if want and any(_key(h) == want for h in _heads(b))]
    matched_phrases = [
        item for b in blocks if b not in primary for item in b.xpath(".//phrase")
        if any(_key(text(m)) == want for m in item.xpath(f"./phrase_h/span[{cls('mwe')}]"))]
    if not primary and not matched_phrases:
        primary = [b for b in blocks if not _is_affix(b)]

    shown = homograph = etymology = ""
    poses: list[str] = []
    prons: list[Pron] = []
    forms: list[str] = []
    senses: list[Sense] = []
    for block in primary:
        h2 = next(iter(block.xpath("./h2")), None)
        body = _Body("sense", "", "")
        if h2 is not None:
            head = next(iter(h2.xpath(f"./span[{cls('hw')} or {cls('mwe')}]")), None)
            if not shown and head is not None:
                shown = _unstress(text(head))
                if "mwe" in class_set(head) and _key(shown) == want:
                    shown = clean(headword)  # an mwe is respelled (macrons); the record key is the spelling
                homograph = text(next(iter(h2.xpath("./sup")), None))
            forms += [_unstress(text(v)) for v in h2.xpath(f"./span[{cls('var')}]")]
            prons += _prons(h2, f".//a[{cls('pron')}]")
            body.walk(_head_rest(h2), None)  # a pos, and "an obsolete form of <a>apricot</a>"
            body.pending = []  # a label in the head may qualify a variant only
            if block.xpath(f"./ol | ./p[{cls('dg')}] | ./def_hide"):
                body.senses.clear()  # the block defines the word itself; text in its head is a note
        phrases: list[Sense] = []
        body.walk(block, phrases, skip=h2)
        senses += body.senses + phrases
        prons += body.prons
        forms += body.forms
        poses += body.poses
        etymology = etymology or body.etymology
    for item in matched_phrases:
        senses += _phrase(item, want)
        prons += _prons(item, f".//a[{cls('pron')}]")
        poses += [text(p) for p in item.xpath(f".//span[{cls('pos')}]")]

    entry = Entry(headword=shown or clean(headword), homograph=homograph,
                 pos=tuple(dict.fromkeys(p for p in poses if p)),
                 prons=tuple(dict.fromkeys(prons)), senses=tuple(senses), etymology=etymology,
                 forms=tuple(dict.fromkeys(f for f in forms if f and _key(f) != want)))
    return entry if covered(entry, COVERS) else replace(entry, stub=_stub(blocks, primary, matched_phrases, entry, want))


def _stub(blocks, primary, matched_phrases, entry: Entry, want: str) -> str:
    """Why a record without definitions has none, when its markup says so; else "".
    Only the heads attributed to this record count: its own blocks and matched run-ons."""
    if any(b.xpath(f"./h2/span[{cls('GRA')}]") for b in primary):
        return "inflection"  # "abought  pat and pap of aby"
    heads = [h for b in primary for h in b.xpath("./h2")] + [h for i in matched_phrases for h in i.xpath("./phrase_h")]
    if any(_SEE.search(text(h)) for h in heads):
        return "xref"  # "take fright  see under fright", "areaway  see above"
    head_pos = any(b.xpath(f"./h2/span[{cls('pos')}]") for b in primary)
    listed = primary and all("extracted_entry" in class_set(b) for b in primary)
    if entry.pos or head_pos or entry.senses or listed or (blocks and all(_is_affix(b) for b in blocks)):
        return "derivative"  # listed under its base word with a pos at most, or formed with a prefix
    if any(_key(text(i)) == want for b in blocks for i in b.xpath(f".//span[{cls('inf')}]")):
        return "variant"  # "cor blimey": an alternative printed inside another word's definition
    for b in primary:
        words = copy.deepcopy(next(iter(b.xpath("./h2")), b))
        for el in words.xpath(f"./span | ./a[{cls('pron')}] | ./sup"):
            el.drop_tree()
        if not _RESIDUE.fullmatch(text(words)):
            return "variant"  # "poursew … Spenserian for pursue", "thrae  another form of Scots frae"
    if primary and not entry.etymology and all(len(b.xpath("./*")) == 1 for b in primary):
        return "empty"  # the head (word and pronunciation) and nothing else
    return ""
