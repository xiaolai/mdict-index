"""Practical English Usage, 4th edition (Swan).

Every entry is one numbered usage article; its sections become Sense(kind="note").

Structure (div.peu-contents-full > span.grammarEntry[@ge_num]):
  span.institle        the article title (headword as shown)
  span.arl / span.breadcrumb / span.peu-btns / div.PEU_contents
                       index terms, navigation, contents link: never content
  span.title > span.hang (article number) + span.indent (title)
  span.section[@section_level='1'|'2']
      span.title > span.hang (section number "1", or letter "a" for a level-2
                   subsection) + span.indent (section title)
      span.block       explanatory prose (may inline span.example as mentioned words)
      span.constructGroup > span.construct   a grammar pattern ("could have + past participle")
      span.exampleGroup > span.example       the examples; "(not ...)" corrections inside
                                             an example are printed text and stay in it
      span.lettered|bulleted|numbered|plain > span.li   lists wrapping more blocks / groups
      span.section     a level-2 subsection nested inside its level-1 section
  span.notes > span.note    trailing notes of the article (or of a section)
Introduction articles ("adjectives introduction") use span.introduction around the same
sections, plus span.contents_box (a table of contents: skipped).

Mapping: each section -> Sense(kind="note", number=its hang text as printed, phrase=its title,
definition=its blocks and constructs joined, examples=its exampleGroup examples). A section's
own content excludes its nested subsections, which become senses of their own. Notes directly
under the article (not inside a section) become one extra note sense each; notes inside a
section belong to that section. extra["ge_num"] holds the article number.

Left in layer 1: span.tabular tables (abbreviation lists, the "what's wrong?" quizzes of the
introduction articles), span.vocabBox word boxes, images, and the cross-reference numbers'
link targets (their printed text stays in the prose).

Stubs: 135 of the 927 entries are "See also:" pages (h3.entry_name + div.seealso links) that
exist only to point at other articles: stub "xref", their link texts in extra["see_also"]
("; "-joined). "Contents overview" is the book's table of contents (a link tree, no
grammarEntry): stub "index". Every other record is a grammarEntry article.
"""
from __future__ import annotations

from copy import deepcopy

from structured.markup import clean, cls, parse as parse_html, text
from structured.model import Entry, Example, Sense

KEY = "peu"
COVERS = "notes"
MIN_COVERAGE = 0.99

_SKIP = ("tabular", "vocabBox", "contents_box")
_NOT_SKIPPED = " and ".join(f"not(ancestor::*[{cls(k)}])" for k in _SKIP)


def _own(section, xpath: str) -> list:
    """Descendants of `section` matching `xpath` that belong to it, not to a nested section."""
    return [el for el in section.xpath(f"{xpath}[{_NOT_SKIPPED}]")
            if next(iter(el.xpath(f"ancestor::*[{cls('section')}][1]")), None) is section]


def _spaced_text(el) -> str:
    """text() of an element whose dialogue lines (span.locution) are adjacent without whitespace."""
    if not el.xpath(f".//*[{cls('locution')}]"):
        return text(el)
    el = deepcopy(el)
    for line in el.xpath(f".//*[{cls('locution')}]"):
        line.tail = " " + (line.tail or "")
    return text(el)


def _prose(elements: list) -> str:
    """Joined text of the outermost block/construct elements, without any example group they wrap."""
    parts = []
    for el in elements:
        if el.xpath(f"ancestor::*[{cls('block')} or {cls('construct')}]"):
            continue  # already part of an enclosing block
        el = deepcopy(el)
        for inner in el.xpath(f".//*[{cls('exampleGroup')} or {' or '.join(cls(k) for k in _SKIP)}]"):
            inner.drop_tree()
        parts.append(_spaced_text(el))
    return clean(" ".join(p for p in parts if p))


def _examples(found: list) -> tuple[Example, ...]:
    return tuple(e for e in (Example(_spaced_text(x)) for x in found) if e.text)


_PROSE = f".//*[{cls('block')} or {cls('construct')}]"
_EXAMPLES = f".//span[{cls('exampleGroup')}]//span[{cls('example')}][not(ancestor::*[{cls('example')}])]"


def _section(section) -> Sense | None:
    title = next(iter(section.xpath(f"./span[{cls('title')}]")), None)
    number = text(next(iter(title.xpath(f"./span[{cls('hang')}]")), None)) if title is not None else ""
    phrase = text(next(iter(title.xpath(f"./span[{cls('indent')}]")), None)) if title is not None else ""
    definition = _prose(_own(section, _PROSE))
    examples = _examples(_own(section, _EXAMPLES))
    if not (definition or examples):
        return None
    return Sense(kind="note", number=number, phrase=phrase, definition=definition, examples=examples)


def _note(note) -> Sense | None:
    definition = _prose(note.xpath(f"{_PROSE}[{_NOT_SKIPPED}]"))
    examples = _examples(note.xpath(f"{_EXAMPLES}[{_NOT_SKIPPED}]"))
    if not (definition or examples):
        return None
    return Sense(kind="note", definition=definition, examples=examples)


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    article = next(iter(root.xpath(f"//span[{cls('grammarEntry')}]")), None)
    if article is None:
        shown = text(next(iter(root.xpath(f"//h3[{cls('entry_name')}]")), None))
        targets = [text(a) for a in root.xpath(f"//div[{cls('seealso')}]/a")]
        extra = {"see_also": "; ".join(dict.fromkeys(t for t in targets if t))} if any(targets) else {}
        stub = "xref" if extra else "index" if root.xpath("//a[starts-with(@href, 'entry://')]") else "empty"
        return Entry(headword=shown or clean(headword), stub=stub, extra=extra)

    shown = text(next(iter(article.xpath(f".//span[{cls('institle')}]")), None))
    senses: list[Sense] = []
    for section in article.xpath(f".//span[{cls('section')}][{_NOT_SKIPPED}]"):
        if (s := _section(section)) is not None:
            senses.append(s)
    for note in article.xpath(f".//span[{cls('note')}][not(ancestor::*[{cls('section')}])][{_NOT_SKIPPED}]"):
        if (s := _note(note)) is not None:
            senses.append(s)
    ge_num = clean(article.get("ge_num") or "")
    return Entry(headword=shown or clean(headword), senses=tuple(senses),
                 extra={"ge_num": ge_num} if ge_num else {})
