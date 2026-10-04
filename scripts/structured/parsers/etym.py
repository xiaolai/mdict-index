"""Online Etymology Dictionary (etymonline, 2020 snapshot).

The etymology text is the entry: COVERS "etymology".

Structure (one entry = every homograph of one headword):
  div.word (one per homograph) > object > div.spare >
      h1.word__name        the word, with span.word_c = its label ("n.", "v.2", "adj., n.", or a
                           bare homograph number "1" for affixes and roots); a few roots print the
                           number in the name instead: "*(s)mer- (1)"
      section.word__defination > p | blockquote   the etymology prose (blockquote = quoted
                           citations and verse, part of the text); rare tables stay in layer 1
      blockquote.word_summary--1nri6   a condensed restatement of the prose: skipped (it would
                           double count)
      div.chart--2x1ib     a usage-frequency chart image: skipped
  div.related > h3 + ul.related__container > li.related__word > a   "Related Entries"
  div.word__scrabble > h2.h2_title + div.sc_related > a.scrabble__node   the "Words related
                           to X" / "Suffix" list pages: no etymology at all

Mapping: the words whose name matches the headword (in practice all of them; if none match,
all are used) give Entry.etymology. One word -> its paragraphs joined by spaces. Several words
-> each word's text prefixed with its label in parentheses, "(v.) ... (n.) ...", so the
homographs stay distinguishable in one string. pos = the part-of-speech labels without their
homograph digits; homograph = the number when the entry holds a single numbered word. The
related-words lists never enter the etymology; their link texts go to extra["related"]
("; "-joined, the "See all related words" link excluded).

Stubs: the 494 list pages (491 "Words related to X", plus "Prefix", "Suffix" and
"Proto-Indo-European root") have no div.word; they are link lists whose content lives in the
linked entries: stub "index". A record with neither is stub "empty".
"""
from __future__ import annotations

import re

from structured.markup import clean, cls, parse as parse_html, text
from structured.model import Entry

KEY = "etym"
COVERS = "etymology"
MIN_COVERAGE = 0.99

_NUMBERED_NAME = re.compile(r"^(.*\S)\s*\((\d+)\)$")
_HOMOGRAPH = re.compile(r"^(.*?)(\d+)$")


def _name_and_label(h1) -> tuple[str, str]:
    label = text(next(iter(h1.xpath(f".//span[{cls('word_c')}]")), None))
    name = text(h1)
    if label and name.endswith(label):
        name = name[: -len(label)].strip()
    if not label and (m := _NUMBERED_NAME.match(name)):
        name, label = m.group(1), m.group(2)
    return name, label


def _prose(word) -> str:
    parts = word.xpath(f".//section[{cls('word__defination')}]/*[self::p or self::blockquote]")
    return clean(" ".join(text(p) for p in parts))


def _pos(label: str) -> list[str]:
    out = []
    for part in re.split(r"[,/]", label):
        part = part.strip()
        m = _HOMOGRAPH.match(part)
        if m:
            part = m.group(1).strip()
        if part:
            out.append(part)
    return out


def _norm(value: str) -> str:
    return clean(value).casefold()


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    words = []
    for div in root.xpath(f"//div[{cls('word')}]"):
        h1 = next(iter(div.xpath(f".//h1[{cls('word__name')}]")), None)
        name, label = _name_and_label(h1) if h1 is not None else ("", "")
        words.append((name, label, _prose(div)))
    matching = [w for w in words if _norm(w[0]) == _norm(headword)] or words
    matching = [w for w in matching if w[2]] or matching

    if len(matching) == 1:
        etymology = matching[0][2]
    else:
        etymology = clean(" ".join(f"({label}) {prose}" if label else prose for _, label, prose in matching if prose))
    pos = [p for _, label, _ in matching for p in _pos(label)]
    homograph = ""
    if len(matching) == 1 and (m := _HOMOGRAPH.match(matching[0][1])):
        homograph = m.group(2)

    related = [text(a) for a in root.xpath(
        f"//li[{cls('related__word')}][not({cls('related__more')})]/a | //a[{cls('scrabble__node')}]")]
    related = [r for r in dict.fromkeys(related) if r]
    shown = matching[0][0] if matching else text(next(iter(root.xpath(f"//h2[{cls('h2_title')}]")), None))
    stub = ""
    if not etymology:  # a "Words related to X" / "Suffix" list page, or nothing at all
        stub = "index" if root.xpath(f"//div[{cls('word__scrabble')}]") else "empty"
    return Entry(headword=shown or clean(headword), homograph=homograph, pos=tuple(dict.fromkeys(pos)),
                 etymology=etymology, stub=stub, extra={"related": "; ".join(related)} if related else {})
