"""ncecd's Hujiang rendering (dict_content_display_1): detail-group and phrase senses (a fallback),
English definitions, and the inflection list, with Hujiang's trailing labels split off."""
from __future__ import annotations

import re

from structured.markup import clean, cls, text
from structured.model import Example, Sense
from structured.parsers._ncecd_markup import _labels, _split_def

_NOT_FORMS = re.compile(r"^(名词|形容词|副词|动词)(扩展)?$|扩展$")
_TRAILING_LABEL = re.compile(r"\s*(<[^<>]*>|【[^【】]*】)\s*$")


def _trailing_labels(value: str) -> tuple[str, list[str]]:
    """Hujiang appends labels to a gloss: "女孩；姑娘<方，Britain:England:East_Anglia>" -> gloss, labels."""
    labels: list[str] = []
    while m := _TRAILING_LABEL.search(value):
        labels = _labels(m.group(1)) + labels
        value = value[: m.start()]
    return value, labels


def _hujiang_senses(pane) -> tuple[list[Sense], list[str], list[str]]:
    """Senses, pos and prons from the Hujiang rendering's 详细释义 and 常用短语 (fallback only)."""
    senses, pos_list, prons = [], [], []
    for dl in pane.xpath(f".//section[{cls('detail-groups')}]/dl"):
        dt = next(iter(dl.xpath("./dt")), None)
        pron_el = next(iter(dt.xpath(f".//*[{cls('detail-pron')}]")), None) if dt is not None else None
        if pron_el is not None:
            prons.append(text(pron_el))
        pos = clean("".join(dt.xpath("./text()"))) if dt is not None else ""
        if pos:
            pos_list.append(pos)
        for dd in dl.xpath("./dd"):
            gloss, labels = _trailing_labels(" ".join(text(p) for p in dd.xpath("./p|./h3/p|./h3[not(p)]")))
            definition, zh = _split_def(gloss)
            examples = []
            for li in dd.xpath("./ul/li"):
                src = next(iter(li.xpath(f".//p[{cls('def-sentence-from')}]")), None)
                dst = next(iter(li.xpath(f".//p[{cls('def-sentence-to')}]")), None)
                english = clean("".join(src.xpath("./text()"))) if src is not None else ""
                if english or text(dst):
                    examples.append(Example(text=english, text_zh=text(dst)))
            if definition or zh or examples:
                senses.append(Sense(pos=pos, labels=tuple(dict.fromkeys(labels)), definition=definition,
                                    definition_zh=zh, examples=tuple(examples)))
    for li in pane.xpath(f".//ol[{cls('phrase-items')}]/li"):
        phrase = clean("".join(li.xpath(f"./a//text()|./span[not({cls('phrase-def')})]//text()")))
        definition, zh = _split_def(" ".join(text(d) for d in li.xpath(f"./*[{cls('phrase-def')}]")))
        if phrase and (definition or zh):
            senses.append(Sense(kind="phrase", phrase=phrase, definition=definition, definition_zh=zh))
    return senses, pos_list, prons


def _english_senses(pane) -> list[Sense]:
    out = []
    for dl in pane.xpath(f".//div[{cls('enen-groups')}]/dl"):
        pos = text(next(iter(dl.xpath("./dt")), None))
        for dd in dl.xpath("./dd"):
            definition, zh = _split_def(text(dd))
            if definition or zh:
                out.append(Sense(pos=pos, definition=definition, definition_zh=zh))
    return out


_ESCAPED_LABEL = re.compile(r"<i>[^<>]*</i>", re.I)


def _form(value: str) -> str:
    """A form from text the source escaped markup in, which decodes into literal tags: an italic label
    before it is dropped and broken markup after it cut off ("<i>tr.</i> containerized", "impress<>/b")."""
    return clean(_ESCAPED_LABEL.sub("", value).split("<")[0])


def _inflections(pane) -> list[str]:
    out = []
    for li in pane.xpath(f".//ul[{cls('inflections-items')}]/li"):
        attr = text(next(iter(li.xpath(f"./*[{cls('inflections-item-attr')}]")), None)).rstrip(":： ")
        if _NOT_FORMS.search(attr):
            continue
        out += [f for f in (_form(text(a)) for a in li.xpath("./a")) if f]
    return out
