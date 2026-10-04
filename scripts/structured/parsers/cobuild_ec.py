"""柯林斯COBUILD高阶英汉双解学习词典 (Collins COBUILD Advanced, English-Chinese, 8th ed.).

Structure (no pronunciations or audio in this build):
  head:   font[size="+1"] (headword), font[color="gold"] (frequency stars, ignored)
  body:   div.tab_content > div.part_main (one per "NOUN USES" / "VERB USES" part)
          > div.collins_content, whose children are, in order:
    div.collins_en_cn     a sense: div.caption > span.num ("1."), span.st (grammar code,
                          English then Chinese: "N-COUNT 可数名词"), span.text_blue (the
                          Chinese gloss), the English definition as the caption's remaining
                          text, and span > div[id^=word_gram] > div > div lines such as
                          "【语法信息】：V n" / "【STYLE标签】：INFORMAL 非正式" (labels);
                          then ul > li > p (English) + p (Chinese).
                          li.en_tip inside the ul is a follow-on note ("X is also a noun.",
                          or an idiom with b + span.text_blue gloss) with its own ul.vli.
    div.vExplain_r        a run-on derivative: b.text_blue (the word), optional caption
                          (span.st), ul examples; may nest li.en_tip notes
  Cross-references are skipped: span.st "See also:" + b.text_blue link, span.text_gray
  "→see: X" with no gloss, and div.caption > dl (the "相关词组" phrasal-verb index).

Left in layer 1: div.en_tip directly in a collins_en_cn (introductory notes),
div.vExplain_s ("in AM, use …"), div.vEn_tip (Usage Note boxes), the star band,
and the word-list pages ("五星级词汇"), which hold only links.

A phrase is the bold run(s) of its definition sentence; alternatives the sentence gives are
joined with " | " ("by all accounts | from all accounts"), as in the English build.
Pos is the English half of span.st ("N-COUNT"); the Chinese half only translates it.
A definition misplaced into the example list (empty caption, first example's
Chinese is a gloss rather than a sentence ending in "。") is moved back.

Stubs (Entry.stub, set only on records with no definition), full run of 36,330
records: 1,945 "empty" (1,873 records holding only the headword, 72 with an empty
collins_content), 552 "xref" ("→see: X", "See also:", the 相关词组 index), 5
"index" (the star-band word lists), 3 "variant" (only "in BRIT, also use …").
Coverage over the 33,825 content records is 0.9999: the 2 uncovered records
("cut off", "let down") hold one example and no definition, kept as an
example-only sense, so they are content, not stubs.
"""
from __future__ import annotations

import copy
import re
from dataclasses import replace

from structured.markup import cls, clean, has_cjk, parse as parse_html, split_en_zh, text
from structured.model import Entry, Example, Sense, covered
from structured.parsers._cobuild_phrase import _drop_target, _only_points, phrase_of  # the same caption grammar as the English build

KEY = "cobuild-ec"
COVERS = "definitions"
MIN_COVERAGE = 0.99  # min(0.99, measured 0.9999 over content records); see above

_XREFS = ("→see:", "→see also:", "→compare:")  # a caption made only of these points elsewhere
_POINTERS = _XREFS + ("→see usage note at:",)      # dropped, with their target, from a definition
_SEE_ALSO = "See also:"
_LABEL_PREFIX = re.compile(r"^【[^】]*】[：:]?\s*")
_ALSO = re.compile(r"\b(is|are) also (a|an|used)\b|\bmeans the same as\b", re.I)


def _cls_of(el) -> set[str]:
    return set((el.get("class") or "").split())


def _labels(el) -> tuple[str, ...]:
    out: list[str] = []
    for line in el.xpath("./span/div[starts-with(@id, 'word_gram')]/div/div"):
        value = _LABEL_PREFIX.sub("", text(line))
        english, _ = split_en_zh(value)
        label = (english or value).strip(" ;,")
        if label and label not in out:
            out.append(label)
    return tuple(out)


def _gloss(el) -> str:
    for span in el.xpath(f"./span[{cls('text_blue')}]"):
        if (value := text(span)) and has_cjk(value):
            return value
    return ""


def _english(el) -> str:
    """Definition text of a caption or note: everything but gloss, codes, labels and links."""
    en = copy.deepcopy(el)
    for child in en.xpath("./ul|./dl|./div|./a|./span[not(@class)]"):
        child.drop_tree()
    # last first: a pointer's phrase starts after the separator ("; ") closing the pointer before it
    for marker in reversed(en.xpath(f"./span[{cls('st')}]|./span[{cls('text_gray')}]")):
        if text(marker) == _SEE_ALSO or text(marker).startswith(_POINTERS):
            _drop_target(marker)
    for child in en.xpath(f"./span[{cls('num')} or {cls('st')} or {cls('text_blue')}]"):
        child.drop_tree()
    for gray in en.xpath(f"./span[{cls('text_gray')}]"):  # "→another name for:" stays, as prose
        gray.text = (gray.text or "").replace("→", " ") + " "
    definition = text(en).lstrip("; ").strip()
    return definition if re.search(r"\w", definition) else ""  # punctuation left between dropped parts defines nothing


def _is_xref(caption) -> bool:
    if caption.xpath("./dl"):
        return True
    grays = [text(g) for g in caption.xpath(f"./span[{cls('text_gray')}]")]
    return bool(grays) and not _gloss(caption) and all(g.startswith(_XREFS) for g in grays)


def _examples(container) -> tuple[Example, ...]:
    out: list[Example] = []
    for li in container.xpath(f"./ul/li[not({cls('en_tip')})]"):
        paras = li.xpath("./p")
        if not paras:
            continue
        english = text(paras[0])
        chinese = " ".join(t for t in (text(p) for p in paras[1:]) if t)
        if not chinese and has_cjk(english):
            english, chinese = split_en_zh(english)
        if english or chinese:
            out.append(Example(text=english, text_zh=clean(chinese)))
    return tuple(out)


def _st(caption) -> str:
    """The English half of the first grammar code ("N-COUNT 可数名词" -> "N-COUNT")."""
    for st in caption.xpath(f"./span[{cls('st')}]"):
        value = text(st)
        if value and value != _SEE_ALSO:
            return split_en_zh(value)[0] or value
    return ""


def _kind(st: str) -> str:
    upper = st.upper()
    if upper.startswith(("PHRASAL VERB", "PHR-V")):
        return "phrasal_verb"
    if upper == "PHRASE" or upper.startswith("PHR-"):
        return "phrase"
    return "sense"


def _sense_block(block) -> Sense | None:
    caption = next(iter(block.xpath(f"./div[{cls('caption')}]")), None)
    examples = _examples(block)
    if caption is None:  # a bare example list (a few phrasal-verb stubs)
        return Sense(examples=examples) if examples else None
    if _is_xref(caption):
        return None
    st = _st(caption)
    kind = _kind(st)
    definition, definition_zh = _english(caption), _gloss(caption)
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
                 number=text(next(iter(caption.xpath(f"./span[{cls('num')}]")), None)).rstrip("."),
                 labels=_labels(caption), definition=definition, definition_zh=definition_zh,
                 examples=examples)


def _tip(li) -> Sense | None:
    """li.en_tip: "X is also a noun." (a sense) or an idiom in bold with its gloss (a phrase)."""
    definition = _english(li)
    phrase = "" if _ALSO.search(definition) else phrase_of(li)
    examples = _examples(li)
    definition_zh = _gloss(li)
    if not (definition or definition_zh or examples):
        return None
    return Sense(kind="phrase" if phrase else "sense", phrase=phrase, labels=_labels(li),
                 definition=definition, definition_zh=definition_zh, examples=examples)


def _tips(el) -> list[Sense]:
    return [s for li in el.xpath(f"./ul/li[{cls('en_tip')}]") if (s := _tip(li)) is not None]


def _derivative(block) -> list[Sense]:
    word = text(next(iter(block.xpath(f"./b[{cls('text_blue')}]")), None))
    caption = next(iter(block.xpath(f"./div[{cls('caption')}]")), None)
    pos = definition = definition_zh = ""
    labels: tuple[str, ...] = ()
    if caption is not None and not _is_xref(caption):
        pos, definition, definition_zh, labels = _st(caption), _english(caption), _gloss(caption), _labels(caption)
    out: list[Sense] = []
    examples = _examples(block)
    if word and (definition or definition_zh or examples):
        out.append(Sense(kind="derivative", pos=pos, phrase=word, labels=labels, definition=definition,
                         definition_zh=definition_zh, examples=examples))
    return out + _tips(block)


def _senses(root) -> list[Sense]:
    out: list[Sense] = []
    for content in root.xpath(f"//div[{cls('collins_content')}]"):
        for block in content.xpath("./div"):
            classes = _cls_of(block)
            if "collins_en_cn" in classes:
                if (s := _sense_block(block)) is not None:
                    out.append(s)
                out += _tips(block)
            elif "vExplain_r" in classes:
                out += _derivative(block)
    return out


def _stub(root, senses: list[Sense]) -> str:
    """Why a record without definitions has none, when its markup says so; else ""."""
    if senses:
        return ""  # an example without a definition is content, not a stub
    if root.xpath(f"//div[{cls('wl_char_list')}]"):
        return "index"  # the star-band word lists
    if root.xpath(f"//div[{cls('caption')}]/span[{cls('text_gray')}][starts-with(normalize-space(), '→')]"
                  f" | //span[{cls('st')}][normalize-space()='{_SEE_ALSO}'] | //div[{cls('caption')}]/dl"):
        return "xref"
    if root.xpath(f"//div[{cls('vExplain_s')}]"):
        return "variant"  # "in BRIT, also use fiddle about" and nothing else
    if not root.xpath(f"//div[{cls('collins_content')}]/*"):
        return "empty"  # the headword alone, or an empty content shell
    return ""


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    shown = text(next(iter(root.xpath("//font[@size='+1']")), None))
    senses = _senses(root)
    pos = tuple(dict.fromkeys(s.pos for s in senses if s.pos))
    entry = Entry(headword=shown or clean(headword), pos=pos, senses=tuple(senses))
    return entry if covered(entry, COVERS) else replace(entry, stub=_stub(root, senses))
