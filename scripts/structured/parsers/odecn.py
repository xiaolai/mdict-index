"""Oxford Dictionary of English, English-Chinese edition (新牛津英汉双解大词典, 2nd ed., ODECN).

Structure: one div.ODECN per homograph (an MDict entry holds all of a word's homographs).
  div.headword > h2 (sup = homograph number), span.pron "/…/" (no region, no audio),
                 div.variant "(亦作 X)" = variant spelling, or an entry-wide label
                 ("informal<非正式>"); div.panel / div.spanel are navigation only.
                 A few entries use div.wordhead > h2 + div.pron > span instead.
  div.item      one per part of speech: div.pos, span.transitivity (item-wide label),
                span.pos_inflections ("pl. -ies": suffix patterns, not forms),
                div.defs > span.num, div.en_def, div.cn_def, div.example > p.en + p.cn,
                           div.sub_defs (the same shape, nested; numbered "1.1")
                en_def carries its labels inline: span.sense-regions (register,
                region, subject) and span.grammatical-note; a.form-groups names a
                form the sense applies to. cn_def may open with span.cn_def_text.
  div.phrases / div.phrasal_verbs > div.phrase > a.phrase_head, span.phrase_info, div.defs
  div.derivatives > div.body > h3.inflection + span.pos   (no definitions)
  div.origin > div.body                                     etymology
A cross-reference entry is only div.cross_reference ("See twelve").

Labels are the label spans that open an en_def, before its first word; the same
classes also mark titles and terms in running text, which stay in the definition.
An entry-wide label in div.variant applies to every sense and phrase below it, the item's transitivity to every sense
below them. A suffix variant ("-ise" beside "organize") becomes "organise" when it
aligns with the headword's ending (at most one letter differs), otherwise is dropped.

Left in layer 1: div.usage notes, div.addition (encyclopedic notes), sense-level
span.origin_text, a.form-groups, span.phrase_info, pos_inflections, images and navigation
panels. The labels that open an example ("figurative", "as modifier") go to
Example.labels and out of the example text.

A zh-only definition that is just a pointer ("见 PENNY", "同 X") is not counted as one.

Stubs: a record with no definition is "xref" when it is a div.cross_reference record or
its only gloss is a "见 X" pointer, else "empty".

Coverage (full run, 107,730 records): 5,618 stubs, all read by class and sampled by hand:
  4,585  div.cross_reference only ("See twelve"), content lives in the target entry
  1,025  a sense whose only text is a Chinese pointer "见 X" (618 phrase records under
         a cross_reference, 407 headword records such as "acne rosacea": 见 ROSACEA)
      7  a cross_reference plus a phrase with an empty or definition-less div.defs
      1  "Bruneian" (empty), whose only en_def text is its part of speech
All 102,112 content records are covered (1.0).
"""
from __future__ import annotations

import copy
import re

from structured.markup import clean, cls, parse as parse_html, strip_slashes, text
from structured.model import Entry, Example, Pron, Sense

KEY = "odecn"
COVERS = "definitions"
MIN_COVERAGE = 0.99

_LABEL_CLASSES = ("sense-regions", "grammatical-note")
_VARIANT = re.compile(r"亦作")
_SEPARATOR = re.compile(r"[\s,;]+")
_LIST_SEP = re.compile(r"[,，;；]|或")
_BEFORE_ZH = re.compile(r"[<〈〔（(]|[㐀-䶿一-鿿]")
# after a variant's em, the spelling's own point or hyphen: before the closing bracket or a list separator
# ("cres.)", "di-)", "b.c.c., b.c.c.", "ult. 或"), not a sentence end ("dinges. 读音同")
_OWN_POINT = re.compile(r"([.\-]+)\s*(?:[)）,，;；]|或|$)")
_NOT_A_LABEL = re.compile(r"^/|\bof [A-Z]{2}")  # div.variant also holds "/ɪpə/" and "past participle of BREAK"
_POINTER_WORDS = frozenset({"", "见", "参见", "同", "亦作"})
_EDGE = "\ue000"  # a private-use marker (lxml refuses control characters)
_GLUED = re.compile(r"(?<=\w)\ue000+(?=\w)")


def _kids(el, name: str, tag: str = "*"):
    """Direct children of `el` with class `name`."""
    return el.xpath(f"./{tag}[{cls(name)}]")


def _without(el, *names: str, tags: tuple[str, ...] = ()) -> str:
    """Text of `el` with descendants of the given classes / tags removed (their tails kept)."""
    if el is None:
        return ""
    el = copy.deepcopy(el)
    paths = [f".//*[{cls(n)}]" for n in names] + [f".//{t}" for t in tags]
    for bad in el.xpath(" | ".join(paths)) if paths else []:
        if bad.getparent() is not None:
            bad.drop_tree()
    # ODECN.css renders a space around every link and label span ("another term
    # for<a>X</a>", "such as<span class=sense-regions>Title</span>"); keep one where
    # the element abuts a word on both sides, none next to spaces or punctuation
    for a in el.xpath(".//a | " + " | ".join(f".//span[{cls(n)}]" for n in _LABEL_CLASSES)):
        a.text, a.tail = _EDGE + (a.text or ""), _EDGE + (a.tail or "")
    value = _GLUED.sub(" ", text(el)).replace(_EDGE, "")
    return clean(value)


def _split_leading(el) -> tuple[str, list[str]]:
    """(text, labels) of an en_def / p.en whose opening label spans (and form-groups) are
    taken out. Only spans before the first word count: the same class also marks titles
    and terms in running text ("His novels, such as <span>Fathers and Sons</span>")."""
    el = copy.deepcopy(el)
    labels: list[str] = []
    if not _SEPARATOR.sub("", el.text or ""):
        for child in list(el):
            if not isinstance(child.tag, str):
                if _SEPARATOR.sub("", child.tail or ""):
                    break  # a comment followed by the definition's first words
                continue
            names = set((child.get("class") or "").split())
            if not names & (set(_LABEL_CLASSES) | {"form-groups"}):
                break
            if names & set(_LABEL_CLASSES):
                value = _without(child).strip(",;()[] ")
                if value and value not in labels:
                    labels.append(value)
            stop = bool(_SEPARATOR.sub("", child.tail or ""))
            child.drop_tree()
            if stop:
                break
    return _without(el), labels


def _zh(cn_def) -> str:
    """Chinese definition; a leading cn_def_text gloss is kept apart from the equivalents."""
    glosses = [_without(g) for g in cn_def.xpath(f".//span[{cls('cn_def_text')}]")]
    rest = _without(cn_def, "cn_def_text")
    return clean(" ".join(p for p in glosses + [rest] if p))


def _pointer(cn_def) -> bool:
    """A Chinese "definition" that is only a cross-reference: "见 PENNY", "同 X"."""
    rest = _without(cn_def, tags=("a",)).strip(" 。.;；()（）")
    return bool(cn_def.xpath(".//a")) and rest in _POINTER_WORDS


def _examples(defs) -> list[Example]:
    out = []
    for ex in _kids(defs, "example", "div"):
        texts, labels = [], []
        for p in _kids(ex, "en", "p"):  # "<span sense-regions>figurative</span> the city was ..."
            value, own = _split_leading(p)
            texts.append(value)
            labels += [lab for lab in dict.fromkeys(own) if lab not in labels]
        zh = " ".join(_without(p) for p in _kids(ex, "cn", "p"))
        example = Example(text=clean(" ".join(texts)), text_zh=clean(zh), labels=tuple(labels))
        if example.text or example.text_zh:
            out.append(example)
    return out


def _senses(defs, kind: str, phrase: str, pos: str, inherited: list[str]) -> list[Sense]:
    """The sense in a div.defs / div.sub_defs, then its nested sub_defs."""
    labels = list(inherited)
    parts = []
    for d in _kids(defs, "en_def", "div"):
        part, own = _split_leading(d)
        parts.append(part)
        labels += [lab for lab in dict.fromkeys(own) if lab not in labels]
    definition = clean(" ".join(parts))
    definition_zh = clean(" ".join(_zh(d) for d in _kids(defs, "cn_def", "div") if not _pointer(d)))
    examples = _examples(defs)
    out = []
    if definition or definition_zh or examples:
        out.append(Sense(kind=kind, pos=pos, number=text(next(iter(_kids(defs, "num", "span")), None)),
                         phrase=phrase, labels=tuple(labels), definition=definition,
                         definition_zh=definition_zh, examples=tuple(examples)))
    for sub in _kids(defs, "sub_defs", "div"):
        out += _senses(sub, kind, phrase, pos, inherited)
    return out


def _headword_block(block):
    return next(iter(block.xpath(f"./div[{cls('headword')}] | .//div[{cls('wordhead')}]")), None)


def _expand(headword: str, variant: str) -> str:
    """"-ise" beside "organize" is "organise": a suffix variant replaces the aligned tail of
    the headword when the two differ by at most one letter; otherwise it is dropped,
    since no reliable spelling can be built from it."""
    if not variant.startswith("-") or headword.startswith("-"):
        return variant
    tail = variant[1:]
    if tail and len(headword) > len(tail) and sum(a != b for a, b in zip(headword[-len(tail):], tail)) <= 1:
        return headword[: -len(tail)] + tail
    return ""


def _spellings(variant) -> list[str]:
    """The em spellings of a div.variant, each with the points and hyphens printed outside its em:
    "<em>b</em>.<em>c</em>.<em>c</em>." is "b.c.c.", "<em>di</em>-)" is "di-", and so is a point before a list
    separator ("<em>b</em>.<em>c</em>.<em>c</em>., <em>b.c.c.</em>": one spelling, printed twice). A point followed by
    more text ("<em>dinges</em>. 读音同") ends a sentence and is not part of the spelling."""
    out: list[str] = []
    joined = False
    for em in variant.xpath(".//em"):
        out = out[:-1] + [out[-1] + _without(em)] if joined else out + [_without(em)]
        tail, nxt = em.tail or "", em.getnext()
        joined = bool(tail) and not tail.strip(".-") and nxt is not None and nxt.tag == "em"
        if joined:
            out[-1] += tail
        elif m := _OWN_POINT.match(tail):
            out[-1] += m.group(1)
    return out


def _variant(head, headword: str) -> tuple[list[str], list[str]]:
    """(variant spellings, entry-wide labels) from div.variant."""
    forms, labels = [], []
    for v in _kids(head, "variant", "div"):
        raw = _without(v).strip("() ")
        if _VARIANT.search(raw):
            values = _spellings(v) or [raw.split("亦作", 1)[1]]
            forms += [_expand(headword, clean(f).strip("() ")) for val in values for f in _LIST_SEP.split(val)]
        elif raw:
            labels.append(_BEFORE_ZH.split(raw)[0].strip(" ,;"))
    return [f for f in forms if f and f != headword], [lab for lab in labels if lab and not _NOT_A_LABEL.search(lab)]


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    blocks = root.xpath(f"//div[{cls('ODECN')}]") or [root]
    shown, homographs, pos_list, prons, forms, senses, origins = "", [], [], [], [], [], []
    for block in blocks:
        head = _headword_block(block)
        entry_labels: list[str] = []
        if head is not None:
            h2 = next(iter(head.xpath(".//h2")), None)
            if h2 is not None:
                hm = text(next(iter(h2.xpath(".//sup")), None))
                if hm and hm not in homographs:
                    homographs.append(hm)
                shown = shown or _without(h2, tags=("sup",))
            for p in head.xpath(f".//*[{cls('pron')}]"):
                ipa = strip_slashes(text(p))
                if ipa and ipa not in prons:
                    prons.append(ipa)
            variants, entry_labels = _variant(head, shown or clean(headword))
            forms += [f for f in dict.fromkeys(variants) if f not in forms]

        for item in _kids(block, "item", "div"):
            pos = text(next(iter(_kids(item, "pos", "div")), None))
            if pos:
                pos_list.append(pos)
            for p in _kids(item, "pron", "span"):
                ipa = strip_slashes(text(p))
                if ipa and ipa not in prons:
                    prons.append(ipa)
            item_labels = entry_labels + [text(t) for t in _kids(item, "transitivity", "span") if text(t)]
            for defs in _kids(item, "defs", "div"):
                senses += _senses(defs, "sense", "", pos, item_labels)

        # a standalone phrase entry has its div.phrase directly in the block
        for group, kind in (("phrases", "phrase"), ("phrasal_verbs", "phrasal_verb"), ("", "phrase")):
            path = f"./div[{cls(group)}]/div[{cls('phrase')}]" if group else f"./div[{cls('phrase')}]"
            for phrase_el in block.xpath(path):
                phrase = _without(next(iter(_kids(phrase_el, "phrase_head", "a")), None), *_LABEL_CLASSES)
                if not phrase:
                    continue
                for defs in _kids(phrase_el, "defs", "div"):
                    senses += _senses(defs, kind, phrase, "", entry_labels)

        for body in block.xpath(f"./div[{cls('derivatives')}]/div[{cls('body')}]"):
            for h3 in body.xpath(f"./h3[{cls('inflection')}]"):
                word = _without(h3)
                pos_el = next(iter(h3.xpath(f"following-sibling::span[{cls('pos')}][1]")), None)
                if word:
                    senses.append(Sense(kind="derivative", pos=text(pos_el), phrase=word))

        for body in block.xpath(f"./div[{cls('origin')}]/div[{cls('body')}]"):
            if (origin := _without(body)) and origin not in origins:
                origins.append(origin)

    return Entry(headword=shown or clean(headword), homograph=homographs[0] if len(homographs) == 1 else "",
                 pos=tuple(dict.fromkeys(pos_list)), prons=tuple(Pron(ipa=p) for p in prons),
                 senses=tuple(senses), etymology=" ".join(origins), forms=tuple(forms),
                 stub=_stub_reason(root, senses))


def _stub_reason(root, senses) -> str:
    """Why a record has no definition: it is a "See X" record or its only gloss is "见 X"."""
    if any(s.definition or s.definition_zh for s in senses):
        return ""
    pointers = root.xpath(f"//div[{cls('cross_reference')}] | //div[{cls('cn_def')}]")
    if any(_pointer(el) or "cross_reference" in (el.get("class") or "").split() for el in pointers):
        return "xref"
    return "empty" if not root.xpath(f"//div[{cls('example')}]") else ""
