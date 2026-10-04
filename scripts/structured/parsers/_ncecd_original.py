"""ncecd's original rendering (dict_content_display_2): the sense-div reader and the flat walk that
turns headers, sections, senses, examples, collocations, equivalences and notes into senses."""
from __future__ import annotations

import re

from structured.markup import clean, cls, has_cjk, has_class, text
from structured.model import Example, Sense
from structured.parsers._ncecd_markup import _EDGE, _flat, _is_header_text, _join_zh, _labels, _pron_text, _split_def


class _Sense:
    """A sense under construction."""

    def __init__(self, number: str, pattern: str, labels: list[str]) -> None:
        self.number, self.pattern, self.labels = number, pattern, list(labels)
        self.definition: list[str] = []
        self.zh: list[str] = []
        self.examples: list[Example] = []

    def has_gloss(self) -> bool:
        return bool(clean(" ".join(self.definition)) or _join_zh(self.zh))

    def build(self, pos: str, kind_if_phrase: str = "phrase") -> Sense | None:
        definition = clean(" ".join(self.definition)).strip(_EDGE)
        zh = _join_zh(self.zh)
        if has_cjk(definition):
            zh, definition = _join_zh([definition, zh]), ""
        examples = tuple(e for e in self.examples if e.text or e.text_zh)
        if not (definition or zh or examples):
            return None
        phrase = clean(self.pattern)
        return Sense(kind=kind_if_phrase if phrase else "sense", pos=pos, number=self.number, phrase=phrase,
                     labels=tuple(dict.fromkeys(self.labels)), definition=definition, definition_zh=zh,
                     examples=examples)


def _read_sense_div(div) -> tuple[str, str, _Sense]:
    """(number, own pattern, sense parts) of a div.sense; children are read in order."""
    number, pattern, after = "", [], []
    parts = _Sense("", "", [])
    seen_content = False  # the Chinese gloss: labels and the English brief gloss come before the pattern too
    pattern_at = 0  # how many definition parts precede the pattern, to keep order if it is a gloss after all

    def free(value: str | None) -> None:
        nonlocal pattern_at, seen_content
        if value and value.strip():
            if pattern and value.lstrip().startswith("="):
                seen_content = True  # "the Big Dipper <美> =Plough": the equivalence ends the pattern
            if not seen_content and not pattern:
                pattern_at = len(parts.definition)
            (after if seen_content else pattern).append(value)

    free(div.text)
    for child in div:
        if not isinstance(child.tag, str):
            free(child.tail)
            continue
        if has_class(child, "num"):
            number = text(child).rstrip(". ")
        elif has_class(child, "brief_ex"):
            parts.definition.append(text(child))
        elif has_class(child, "zh"):
            inner = child.xpath(f".//*[{cls('label')}]")  # "<span class=zh><span class=label>【军】</span>海军部</span>"
            parts.labels += [lb for lab in inner for lb in _labels(text(lab))]
            parts.zh.append(_flat(child, lambda e: has_class(e, "label")))
            seen_content = True
        elif has_class(child, "label") or has_class(child, "collocation") or has_class(child, "etips") or has_class(child, "tip"):
            parts.labels += _labels(text(child))
        elif has_class(child, "also") or has_class(child, "dodo"):
            pass
        elif has_class(child, "or"):
            free(" or ")
        else:
            free(child.text_content())
        free(child.tail)
    pattern_text = clean("".join(pattern)).rstrip(",;， ")
    if pattern_text and (pattern_text.startswith(("=", "(")) or has_cjk(pattern_text) or not re.search(r"\w", pattern_text)):
        # "=Australian Capital Territory" (an equivalence), "(flat)" (an English gloss), "eat的过去式"
        # (a gloss), "(obstacle) …" (a gloss continued in Chinese): not a phrase
        parts.definition.insert(pattern_at, pattern_text)
        pattern_text = ""
    tail = clean("".join(after))
    if tail:
        parts.definition.append(tail)
    if len(parts.definition) == 1 and re.fullmatch(r"\(([^()]*)\)", parts.definition[0].strip()):
        parts.definition = [parts.definition[0].strip()[1:-1]]
    return number, pattern_text, parts


class _Original:
    """Reads the original rendering (dict_content_display_2): one call per span.ncecd_con."""

    def __init__(self) -> None:
        self.senses: list[Sense] = []
        self.pos_list: list[str] = []
        self.prons: list[str] = []
        self.forms: list[str] = []

    def read(self, pane) -> None:
        """The whole rendering, walked flat: a span.header starts a homograph, span.ncecd_con is its body
        (its content sometimes sits after an empty ncecd_con, as siblings)."""
        self.current: _Sense | None = None
        self._reset()
        for child in pane:
            self._dispatch(child, idiom=False)
        self._close()

    def _reset(self) -> None:
        self.pos = ""
        self.section_labels: list[str] = []
        self.head_number, self.head_pattern, self.head_labels = "", "", []
        self.sense_seen = False

    def _close(self) -> None:
        if self.current is not None:
            built = self.current.build(self.pos)
            if built is not None:
                self.senses.append(built)
        self.current = None

    def _section(self, pos: str) -> None:
        self._close()
        self.pos = pos
        self.section_labels = []
        self.head_number, self.head_pattern, self.head_labels = "", "", []
        self.sense_seen = False
        if pos:
            self.pos_list.append(pos)

    def _container(self, el, idiom: bool) -> None:
        self._stray(el.text)
        for child in el:
            self._dispatch(child, idiom)
            self._stray(child.tail)

    def _stray(self, value: str | None) -> None:
        """Bare text directly in ncecd_con is a gloss (a foreign motto -> its Chinese gloss)."""
        if value and re.search(r"\w", value):
            self._close()
            sense = _Sense("", "", self.section_labels)
            sense.definition = [value]
            self.current = sense
            self._close()

    def _dispatch(self, child, idiom: bool) -> None:
        if isinstance(child.tag, str):
            tag = child.tag
            if has_class(child, "header"):
                self._close()
                self._reset()
                for sub in child:  # a header left unclosed by the source swallows the body that follows it
                    if not _is_header_text(sub):
                        self._dispatch(sub, idiom)
            elif has_class(child, "ncecd_con"):
                self._container(child, idiom)
            elif tag == "hr" or tag == "style" or has_class(child, "abbre") or has_class(child, "symbol") or has_class(child, "differ"):
                pass
            elif tag == "pron":
                self.prons.append(_pron_text(child))
            elif has_class(child, "tense"):
                self.forms += _tense_forms(child)
            elif has_class(child, "class"):
                self._section(text(child))
            elif has_class(child, "class_box"):
                pos = next(iter(child.xpath(f".//*[{cls('class')}]")), None)
                self._section(text(pos))
            elif has_class(child, "label_box") or (has_class(child, "sense") and has_class(child, "grammar")):
                for lab in child.xpath(f".//*[{cls('label')} or {cls('tip')}]"):
                    self.section_labels += _labels(text(lab))
            elif has_class(child, "sense"):
                self._sense(child, idiom)
            elif tag == "p" and has_class(child, "ex"):
                self._example(child)
            elif has_class(child, "maybe_phrase"):
                self._collocation(child)
            elif has_class(child, "idom") and tag == "div":
                self._close()
                self.head_number, self.head_pattern, self.head_labels = "", "", []
                self._container(child, idiom=True)
                self._close()
                self.head_number, self.head_pattern, self.head_labels = "", "", []
            elif has_class(child, "also") and tag == "div":
                self._also(child)
            elif tag == "fieldset":
                self._note(child)

    def _sense(self, div, idiom: bool) -> None:
        number, pattern, parts = _read_sense_div(div)
        if not (number or pattern or parts.has_gloss()):
            self.section_labels += parts.labels  # "<div class=sense>[用作单]</div>": a label for what follows
            return
        self._close()
        self.sense_seen = True
        labels = self.section_labels + parts.labels
        if number or (pattern and not parts.zh and not idiom):
            # a numbered sense, or one naming a pattern without its Chinese gloss, heads the unnumbered senses
            # after it: they share its pattern, and its labels when it has no gloss at all ("【航空】to talk sb down")
            self.head_pattern = pattern if not parts.zh else ""
            self.head_labels = parts.labels if not parts.has_gloss() else []
        if number:
            self.head_number = number
        elif not idiom:
            number = self.head_number
            if not pattern and self.head_pattern:
                pattern, labels = self.head_pattern, self.section_labels + self.head_labels + parts.labels
        sense = _Sense(number, pattern, labels)
        sense.definition, sense.zh = parts.definition, parts.zh
        self.current = sense

    def _holder(self) -> _Sense:
        if self.current is None:
            self.current = _Sense("", "", self.section_labels)
        return self.current

    def _example(self, p) -> None:
        zh = " ".join(text(z) for z in p.xpath(f"./*[{cls('zh')}]"))
        english = _flat(p, lambda e: has_class(e, "zh"))
        if self.current is None and not self.sense_seen and english and zh:
            # an "example" before any sense is the entry's own phrase and gloss (source markup slip)
            sense = _Sense("", english, self.section_labels)
            sense.zh = [zh]
            self.current = sense
            return
        self._holder().examples.append(Example(text=english, text_zh=clean(zh)))

    def _collocation(self, div) -> None:
        phrase = next(iter(div.xpath(f"./*[{cls('mphr_en')}]")), None)
        english = _flat(phrase, lambda e: has_class(e, "label")) if phrase is not None else ""
        zh = " ".join(text(z) for z in div.xpath(f"./*[{cls('zh')}]"))
        # "to take a degree <英> 攻读学位": the pattern's own labels
        labels = [lb for lab in div.xpath(f"./*[{cls('label')}]|./*[{cls('mphr_en')}]//*[{cls('label')}]")
                  for lb in _labels(text(lab))]
        if not (english or zh):
            return
        current = self.current
        if english.startswith("=") and current is not None and not current.has_gloss() and not current.examples:
            # "the IMF" then "=the International Monetary Fund 国际货币基金组织": the phrase's own gloss
            current.definition, current.zh = [english], [zh]
            return
        if not self.sense_seen or (current is not None and not current.has_gloss() and not current.examples):
            # before any glossed div.sense, a maybe_phrase is the entry's own phrase and gloss ("the Midas
            # touch"; "methinks" after an unglossed "past tense methought")
            self._close()
            equivalence = english.startswith("=")
            sense = _Sense("", "" if equivalence else english, self.section_labels + labels)
            sense.definition = [english] if equivalence else []
            sense.zh = [zh]
            self.current = sense
            return
        self._holder().examples.append(Example(text=english, text_zh=clean(zh), kind="collocation",
                                               labels=tuple(dict.fromkeys(labels))))

    def _also(self, div) -> None:
        """div.also: "=X" (an equivalence, a definition) or "See also X" (a cross-reference, skipped)."""
        lead = _also_lead(div)
        if not _EQUIVALENCE.match(lead) and not div.xpath(f"./*[{cls('zh')}]"):
            return
        self._close()
        sense = _Sense("", "", self.section_labels + [lb for t in div.xpath(f".//*[{cls('tip')}]") for lb in _labels(text(t))])
        sense.definition = [lead]
        sense.zh = [text(z) for z in div.xpath(f"./*[{cls('zh')}]")]
        self.current = sense
        self._close()

    def _note(self, fieldset) -> None:
        self._close()
        body = " ".join(text(t) for t in fieldset.xpath(f".//*[{cls('txt')} or {cls('usagezh')}]"))
        title = next((text(t) for t in fieldset.xpath(f"./div[{cls('notetitle')}]") if text(t)), "")
        definition, zh = _split_def(body)
        if definition or zh:
            self.senses.append(Sense(kind="note", phrase=title, definition=definition, definition_zh=zh))


def _tense_forms(span) -> list[str]:
    out = [text(b) for b in span.xpath(".//b")]
    for plural in span.xpath(f".//*[{cls('plural')}]"):
        out += [clean(p) for p in _flat(plural).split(" or ")]
    return [f for f in out if f]


_EQUIVALENCE = re.compile(r"(\([^()]*\)\s*)?=")  # "=X", "(formerly)=X"


def _also_lead(div) -> str:
    """div.also text without its grammar tip, gloss and "See" heading: "[用在元音字母前]=Euro-" -> "=Euro-"."""
    return _flat(div, lambda e: has_class(e, "etips") or has_class(e, "zh") or e.tag == "b")
