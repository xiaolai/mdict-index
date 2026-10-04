"""Collins COBUILD Advanced (the "CollinsCOBUILDOverhaul" MDict build).

Listed as English-English, but every sense carries a Chinese gloss and every
example a Chinese translation; both go into the _zh fields.

Structure (div.collinsbody; an entry may hold several word blocks, e.g.
"build up" + "build-up", each a div.word_entry followed by its content):
  head:   div.word_entry > span.word_key (headword),
          span.pron > a[href=sound://…] > span.pron.type_uk|type_us (IPA),
          div.form_inflected > span.also (variant spellings), a.orth (inflections)
  body:   div.collins_content (one per part: "NOUN USES", "VERB USES", …), whose
          children are, in order:
    div.collins_en_cn.example       a sense: div.caption > span.num, span.st (the
                                    grammar code: N-COUNT, VERB, PHRASE, PHRASAL VERB…),
                                    span.def_cn.cn_before (Chinese gloss; repeated as
                                    cn_after), span.tips_box > span.lbl (labels), and the
                                    English definition as the caption's remaining text;
                                    then ul > li > p (English) + p (Chinese).
                                    span.tips_sentence inside an example is its grammar
                                    pattern ("[+ of]", "[VERB noun]"): Example.labels,
                                    without the brackets, and not part of the text.
    div.note.type-sense             "X is also a noun." + its own ul.vli examples
    div.note.type-phrase            a phrase: b (the phrase) + definition + span.def_cn;
                                    alternatives the sentence gives are joined with " | "
    div.note.type-drv               a run-on derivative: b.text_blue (the word),
                                    optional caption (span.st), ul examples; may nest
                                    li.note.type-sense|type-phrase, parsed on their own
  Cross-reference senses are skipped: span.st "See also:", captions whose only
  content is span.text_gray "→see: X" / "→compare: X" with an empty def_cn, and
  div.caption.about (the phrasal-verb index). Plain div.collins_en_cn (no
  "example" class) is always such a cross-reference stub.

Left in layer 1: div.synonym (SYN lists), div.collins_en_cn.addon (trends,
thesaurus / grammar panels), div.note.type-usage and type-note (usage notes),
type-regional ("in AM, use …"), type-quotation (Quotations panel), images, the
word-frequency band.

A definition misplaced into the example list (empty caption, first example's
Chinese is a gloss rather than a sentence ending in "。") is moved back.

Stubs (Entry.stub, set only on records with no definition): the full run
(45,435 records) finds 9,959 "xref" (cross-reference stubs: "intensively →see:
intensive", inflections, spelling variants, idioms filed under their key word,
plain div.collins_en_cn), 15 "index" (only the phrasal-verb list) and 1 "empty"
(the build's "testdebug" page). None of them has a Chinese gloss or an example.
Coverage over the 35,460 content records is 1.0.
"""
from __future__ import annotations

import copy
import re
from dataclasses import replace

from structured.markup import cls, clean, has_cjk, parse as parse_html, text
from structured.model import Entry, Example, Pron, Sense, covered
from structured.parsers._cobuild_phrase import _WORD, _drop_target, _only_points, phrase_of

KEY = "cobuild"
COVERS = "definitions"
MIN_COVERAGE = 0.99  # min(0.99, measured 1.0 over content records); stubs are classified (see above)

_XREFS = ("→see:", "→see also:", "→compare:")  # a caption made only of these points elsewhere
_POINTERS = _XREFS + ("→see usage note at:",)      # dropped, with their target, from a definition
_SEE_ALSO = "See also:"                             # span.st form of a cross-reference
_ICON = re.compile(r"[\ue000-\uf8ff]")  # icon-font glyphs (span.icon-speak-*)
_EMPTY_PARENS = re.compile(r"\(\s*=?\s*\)")  # what is left of "(书面缩略=)" once the Chinese is lifted out


def _drop(el, *classes: str) -> None:
    for name in classes:
        for bad in el.xpath(f".//*[{cls(name)}]"):
            if bad.getparent() is not None:
                bad.drop_tree()


def _labels(el) -> tuple[str, ...]:
    out: list[str] = []
    for lbl in el.xpath(f"./span[{cls('tips_box')}]//span[{cls('lbl')}]"):
        label = text(lbl).strip("[](),; ")
        if label and label not in out:
            out.append(label)
    return tuple(out)


def _examples(container) -> tuple[Example, ...]:
    """Examples of a block: its own ul > li (not nested notes), English p then Chinese p."""
    out: list[Example] = []
    for li in container.xpath(f"./ul/li[not({cls('note')})]"):
        paras = li.xpath("./p")
        if not paras:
            continue
        en = copy.deepcopy(paras[0])
        labels = tuple(dict.fromkeys(
            t for t in (text(x).strip("[] ") for x in en.xpath(f".//span[{cls('tips_sentence')}]")) if t))
        _drop(en, "tips_sentence", "tts_button")
        english = text(en)
        chinese = " ".join(t for t in (text(p) for p in paras[1:]) if t)
        if has_cjk(english) and not chinese:
            # a translation that shares the English paragraph
            zh = " ".join(text(s) for s in en.xpath(f".//span[{cls('chinese-text')}]"))
            if zh:
                _drop(en, "chinese-text")
                english, chinese = text(en), zh
        if english or chinese:
            out.append(Example(text=english, text_zh=clean(chinese), labels=labels))
    return tuple(out)


def _gloss(el) -> str:
    """The Chinese gloss of a caption or note (def_cn; cn_after repeats cn_before)."""
    for dc in el.xpath(f"./span[{cls('def_cn')}]"):
        if (value := text(dc)) and has_cjk(value):
            return value
    return ""


def _english(el) -> tuple[str, str]:
    """(definition, inline Chinese) of a caption or note: everything but the structural spans."""
    en = copy.deepcopy(el)
    for child in en.xpath(f"./ul|./a[{cls('anchor')}]|./div|./li|./dl"):
        child.drop_tree()
    # the labels first: a tips_box may stand between "See also:" and its links
    _drop(en, "num", "def_cn", "tips_box", "tips_sentence", "tts_button")
    # last first: a pointer's phrase starts after the separator ("; ") closing the pointer before it
    for marker in reversed(en.xpath(f"./span[{cls('st')}]|./span[{cls('text_gray')}]")):
        if text(marker) == _SEE_ALSO or text(marker).startswith(_POINTERS):
            _drop_target(marker)
    _drop(en, "st")
    zh = [text(s) for s in en.xpath(f".//span[{cls('chinese-text')}]")]
    _drop(en, "chinese-text")
    for gray in en.xpath(f"./span[{cls('text_gray')}]"):  # "→another name for:" stays, as prose
        gray.text = (gray.text or "").replace("→", " ") + " "
    definition = clean(_EMPTY_PARENS.sub("", text(en)))
    if not _WORD.search(definition):
        definition = ""  # only the punctuation between dropped parts is left: nothing was defined
    return definition, " ".join(z for z in zh if z)


def _is_xref(caption) -> bool:
    """The phrasal-verb index, or a caption that only points elsewhere ("→see: X" with no gloss)."""
    if caption.xpath(f"self::*[{cls('about')}]") or caption.xpath("./dl"):
        return True
    grays = [text(g) for g in caption.xpath(f"./span[{cls('text_gray')}]")]
    return bool(grays) and not _gloss(caption) and all(g.startswith(_XREFS) for g in grays)


def _kind(st: str) -> str:
    upper = st.upper()
    if upper.startswith(("PHRASAL VERB", "PHR-V")):
        return "phrasal_verb"
    if upper == "PHRASE" or upper.startswith("PHR-"):
        return "phrase"
    return "sense"


def _sense_block(block) -> Sense | None:
    caption = next(iter(block.xpath(f"./div[{cls('caption')}]")), None)
    if caption is None or _is_xref(caption):
        return None
    st = text(next(iter(caption.xpath(f"./span[{cls('st')}]")), None))
    st = "" if st == _SEE_ALSO else st
    kind = _kind(st)
    definition, inline_zh = _english(caption)
    definition_zh = _gloss(caption) or inline_zh
    examples = _examples(block)
    if not (definition or definition_zh) and examples and not examples[0].text_zh.endswith("。"):
        # markup slip: the definition sits in the example list ("A diadem is …" / "小王冠");
        # a translated example sentence ends in "。", a gloss does not
        definition, definition_zh, examples = examples[0].text, examples[0].text_zh, examples[1:]
    phrase = phrase_of(caption) if kind != "sense" else ""
    if kind != "sense" and not phrase:
        kind = "sense"
    if not (definition or definition_zh or examples) or _only_points(caption, definition, examples):
        return None
    return Sense(kind=kind, pos=st if kind != "phrase" else "", phrase=phrase,
                 number=text(next(iter(caption.xpath(f"./span[{cls('num')}]")), None)),
                 labels=_labels(caption), definition=definition, definition_zh=definition_zh,
                 examples=examples)


def _note_block(note, kind: str) -> Sense | None:
    """div/li.note.type-sense|type-phrase: definition text, def_cn, ul.vli examples."""
    definition, inline_zh = _english(note)
    phrase = phrase_of(note) if kind == "phrase" else ""
    if kind == "phrase" and not phrase:
        kind = "sense"
    examples = _examples(note)
    definition_zh = _gloss(note) or inline_zh
    if not (definition or definition_zh or examples):
        return None
    return Sense(kind=kind, phrase=phrase, labels=_labels(note), definition=definition,
                 definition_zh=definition_zh, examples=examples)


def _derivative(note) -> list[Sense]:
    word = text(next(iter(note.xpath(f"./b[{cls('text_blue')}]")), None))
    caption = next(iter(note.xpath(f"./div[{cls('caption')}]")), None)
    pos = definition = definition_zh = ""
    labels: tuple[str, ...] = ()
    if caption is not None and not _is_xref(caption):
        pos = text(next(iter(caption.xpath(f"./span[{cls('st')}]")), None))
        pos = "" if pos == _SEE_ALSO else pos
        definition, inline_zh = _english(caption)
        definition_zh = _gloss(caption) or inline_zh
        labels = _labels(caption)
    out: list[Sense] = []
    examples = _examples(note)
    if word and (definition or definition_zh or examples):
        out.append(Sense(kind="derivative", pos=pos, phrase=word, labels=labels, definition=definition,
                         definition_zh=definition_zh, examples=examples))
    out += _nested_notes(note)
    return out


def _nested_notes(el) -> list[Sense]:
    out: list[Sense] = []
    for li in el.xpath(f"./ul/li[{cls('note')}]"):
        kind = "phrase" if li.xpath(f"self::*[{cls('type-phrase')}]") else "sense"
        if (s := _note_block(li, kind)) is not None:
            out.append(s)
    return out


def _senses(root) -> list[Sense]:
    out: list[Sense] = []
    for content in root.xpath(f"//div[{cls('collins_content')}]"):
        for block in content.xpath("./div"):
            classes = set((block.get("class") or "").split())
            s: Sense | None = None
            if "collins_en_cn" in classes:
                if classes & {"addon", "image", "grammarInfo", "trend"}:
                    continue
                s = _sense_block(block)
            elif "type-drv" in classes:
                out += _derivative(block)
            elif "type-sense" in classes:
                s = _note_block(block, "sense")
            elif "type-phrase" in classes:
                s = _note_block(block, "phrase")
            if s is not None:
                out.append(s)
    return out


def _prons(root) -> list[Pron]:
    """span.pron > a[href] > span.pron.type_uk|type_us; a span.pron.type_* may also stand without audio."""
    out: list[Pron] = []
    for head in root.xpath(f"//div[{cls('word_entry')}]"):
        for span in head.xpath(f"./span[{cls('pron')}]/a/span[{cls('pron')}] | ./span[{cls('pron')}]/span[{cls('pron')}]"):
            region = "uk" if "type_uk" in span.get("class", "") else "us" if "type_us" in span.get("class", "") else ""
            ipa = _ICON.sub("", text(span)).strip("/ ")
            parent = span.getparent()
            href = (parent.get("href") or "") if parent.tag == "a" else ""
            audio = href if href.startswith("sound://") else ""
            if (ipa or audio) and (p := Pron(ipa=ipa, region=region, audio=audio)) not in out:
                out.append(p)
    return out


def _forms(root) -> list[str]:
    out: list[str] = []
    for head in root.xpath(f"//div[{cls('word_entry')}]"):
        for el in head.xpath(f".//span[{cls('also')}]/span|.//a[{cls('orth')}]"):
            form = _ICON.sub("", text(el)).strip(",; ")
            if form and form not in out:
                out.append(form)
    return out


def _stub(root) -> str:
    """Why a record without definitions has none, when its markup says so; else ""."""
    xref = (f"//div[@class='collins_en_cn'] | //div[{cls('caption')}]/span[{cls('text_gray')}]"
            f"[starts-with(normalize-space(), '→')] | //span[{cls('st')}][normalize-space()='{_SEE_ALSO}']")
    if root.xpath(xref):
        return "xref"
    if root.xpath(f"//div[{cls('caption')}][{cls('about')}]"):
        return "index"  # the phrasal-verb list only
    if not root.xpath(f"//div[{cls('collins_content')}]/*"):
        return "empty"
    return ""


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    shown = text(next(iter(root.xpath(f"//span[{cls('word_key')}]")), None))
    senses = _senses(root)
    pos = tuple(dict.fromkeys(s.pos for s in senses if s.pos))
    entry = Entry(headword=shown or clean(headword), pos=pos, prons=tuple(_prons(root)),
                  senses=tuple(senses), forms=tuple(_forms(root)))
    return entry if covered(entry, COVERS) else replace(entry, stub=_stub(root))
