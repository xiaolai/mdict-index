"""Extract examples from dictionaries that mark them with a style of their own.

Some dictionaries (the American Heritage English-Chinese editions) translate their
definitions too: "A medieval merchant guild. | 中世纪商业行会" reads exactly like an example
and its translation, so no text-level rule (parallel/text.py) can tell them apart. Their
markup can: each edition prints examples in a style definitions do not use (a class such as
ahd3e_en_example or A3A_EnEx, or a colour such as #009999 or navy).

The markup is read as segments: runs of text under the same style (the nearest enclosing
element's class or colour), broken at block boundaries; an example is paired only with
Chinese in its own sense (the smallest container that holds it with something else). Which
style marks examples is learned per dictionary from ground truth: the English texts of each
style are looked up among the examples and the definitions of a parsed dictionary with the
same content (layer 2), and a style is an example style when its texts match examples and
not definitions. Once the example styles are known, all the English inside an element of
such a style is its example, however its words are styled.
"""
from __future__ import annotations

import html
import re
import sqlite3
from collections import Counter
from collections.abc import Iterable, Iterator, Set
from pathlib import Path

from parallel.markup import CLOSE, TEXT, attributes, declarations, tokens

_COLOUR = re.compile(r"#?\w+")
# Elements that hold blocks of their own: a sense, a list item, a table cell.
_CONTAINER = frozenset("div li td th dd dt blockquote section article aside fieldset".split())
_BLOCK = _CONTAINER | frozenset("br p ol ul tr table dl hr h1 h2 h3 h4 h5 h6".split())
_VOID = frozenset("br hr img meta link input wbr".split())
_CJK = re.compile(r"[㐀-鿿]")
_LATIN = re.compile(r"[A-Za-z]")

_EN_XREF = re.compile(r"\s*See (?:Synonyms|Usage Notes?|Regional Notes?|Notes?) at .*$")
_ZH_XREF = re.compile(r"\s*参见.*$")
_EN_PARTS = re.compile(r";\s+")
_ZH_PARTS = re.compile(r"；\s*")

_RUN_END = (".", "?", "!", ":", ";", "。", "？", "！", "：", "；")  # text after these is not mid-sentence
_GOES_ON = re.compile(r"\s*[a-z㐀-鿿,;:.?!)'’”，。；：？！）-]")    # text that continues a sentence, not one that starts

MIN_EXAMPLE_HITS = 20     # a style's English texts found among the ground truth's examples
MIN_RATIO = 5             # at least this many times more often than among its definitions

_Open = tuple[tuple[str, str | None, int], ...]  # the open elements around a text: (tag, style key, serial)


def _key(tag: str, attrs: str) -> str | None:
    """A style key for an element with a class or a colour; None for plain elements. Only the
    class attribute, the color attribute and the color property of the style attribute count:
    not data-class, background-color, or the same words inside another attribute's value."""
    if "=" not in attrs:
        return None
    found = attributes(attrs)
    names = found.get("class", "").split()
    if names:
        return f"{tag}.{names[0].lower()}"
    for name, value in found.items():
        colour = value if name == "color" else declarations(value).get("color", "") if name == "style" else ""
        m = _COLOUR.match(colour.strip())
        if m:
            return f"{tag}#{m.group().lower().lstrip('#')}"
    return None


def segments(markup: str) -> list[tuple[str, str]]:
    """(style key, text) runs, in order. Tolerates unclosed and mismatched tags."""
    return [(key, text) for key, text, _ in _runs(markup)]


def _pieces(markup: str) -> list[tuple[str, _Open] | None]:
    """The texts of the markup, each with the elements open around it; None at a block boundary."""
    stack: list[tuple[str, str | None, int]] = []
    out: list[tuple[str, _Open] | None] = []
    serial = 0
    for kind, value, attrs, closed in tokens(markup):
        if kind == TEXT:
            out.append((value, tuple(stack)))
            continue
        tag = value.lower().rpartition(":")[2]
        if tag in _BLOCK:
            out.append(None)
        if kind == CLOSE:
            for i in range(len(stack) - 1, -1, -1):  # close the nearest open element of that name
                if stack[i][0] == tag:
                    del stack[i:]
                    break
        elif tag not in _VOID and not closed:
            if tag in ("li", "p"):  # an unclosed <li> or <p> ends at the next one
                for i in range(len(stack) - 1, -1, -1):
                    if stack[i][0] == tag:
                        del stack[i:]
                        break
            serial += 1
            stack.append((tag, _key(tag, attrs), serial))
    return out


def _plain(text: str) -> str:
    return " ".join((html.unescape(text) if "&" in text else text).split())


def _style(path: _Open, cjk: bool, example_styles: Set[str]) -> tuple[str, int]:
    """(style key, element) a text is printed in: its nearest styled element, or for English the
    nearest element of an example style, if there is one ("He <span class=emphasis>came</span>
    home." is one example; a translation printed inside it is not part of it)."""
    own = ("", -1)
    for _, key, serial in reversed(path):
        if not key:
            continue
        if own[1] < 0:
            own = (key, serial)
        if cjk or not example_styles:
            break
        if key in example_styles:
            return key, serial
    return own


def _continued(pieces: list, i: int, owner: int, cjk: bool, example_styles: Set[str]) -> tuple[str, int] | None:
    """The (style key, element) of an element around pieces[i] whose own text goes on after it
    in the same sentence: "<em>He</em> came home.", "Dr. <em>Smith</em> came home."."""
    text, path = pieces[i]
    if _plain(text).endswith(_RUN_END):
        return None
    for following in pieces[i + 1:]:
        if following is None:
            return None
        if not _plain(following[0]):
            continue
        key, element = _style(following[1], cjk, example_styles)
        if (element != owner and any(n == element for _, _, n in path) and _GOES_ON.match(following[0])
                and bool(_CJK.search(following[0])) == cjk):
            return key, element
        return None
    return None


def _sense(members: list[_Open], held: Counter) -> int:
    """The sense a run belongs to: the smallest container that holds it with some other text. An
    element holding nothing but the run is only its wrapper (<DIV style="COLOR: #009999">example
    </DIV>), so an example and its translation in two such boxes inside one sense share it, and
    one at the end of a sense does not share it with the Chinese that begins the next. A run that
    no container holds with other text is a sense of its own, its outermost wrapper (two <li>
    holding one run each are two senses); 0 only for a run in no container at all."""
    inside = Counter(n for path in members for _, _, n in path)
    outermost = 0
    for tag, _, serial in reversed(members[0]):
        if tag in _CONTAINER:
            if held[serial] > inside[serial]:
                return serial
            outermost = serial
    return outermost


def _runs(markup: str, example_styles: Set[str] = frozenset()) -> list[tuple[str, str, int]]:
    """(style key, text, sense) runs; a run is never paired across senses (see _sense).

    A run's style is its nearest enclosing element's (see _style), except that an element styled
    differently inside the run's own element, in the middle of its sentence ("He <span
    class=emphasis>came</span> home.", "<em>He</em> came home."), continues the run. It starts
    its own run after a finished sentence or a colon ("Strike: <font color=blue>I was
    struck...") unless the sentence then goes on, when it is of an example style, or when it
    switches between English and Chinese (a translation printed inside its example's element)."""
    pieces = _pieces(markup)
    held: Counter = Counter()  # element -> texts inside it
    for piece in pieces:
        if piece and _plain(piece[0]):
            held.update(n for _, _, n in piece[1])
    out: list[tuple[str, str, int]] = []
    run_key, run_owner = "", -1
    buffer: list[str] = []
    members: list[_Open] = []

    def flush() -> None:
        text = _plain("".join(buffer))
        if text:
            out.append((run_key, text, _sense(members, held)))
        buffer.clear()
        members.clear()

    for i, piece in enumerate(pieces):
        if piece is None:
            flush()
            continue
        text, path = piece
        cjk = bool(_CJK.search(text))
        key, owner = _style(path, cjk, example_styles)
        example = key in example_styles
        so_far = _plain("".join(buffer))
        inside_run = (so_far and not example and not so_far.endswith(_RUN_END) and owner != run_owner
                      and any(n == run_owner for _, _, n in path) and cjk == bool(_CJK.search(so_far)))
        if not inside_run:
            if not example and _plain(text):
                key, owner = _continued(pieces, i, owner, cjk, example_styles) or (key, owner)
            if key != run_key:
                flush()
                run_key = key
            run_owner = owner
        buffer.append(text)
        if _plain(text):
            members.append(path)
    flush()
    return out


def candidates(markup: str, example_styles: Set[str] = frozenset()) -> Iterator[tuple[str, str, str]]:
    """(English style key, English, Chinese): an English segment followed by a Chinese one in the
    same sense. With the example styles known, the segments are read by them (see _runs)."""
    runs = _runs(markup, example_styles)
    for (key, en, sense), (_, zh, zh_sense) in zip(runs, runs[1:]):
        if sense == zh_sense and _LATIN.search(en) and not _CJK.search(en) and _CJK.search(zh):
            yield key, en, zh


def normalize(text: str) -> str:
    return " ".join(text.lower().split()).rstrip(" .:;")


def ground_truth(db: Path) -> tuple[set[str], set[str]]:
    """(examples, definitions) of a parsed dictionary, normalised."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        examples = {normalize(t) for (t,) in con.execute("SELECT text FROM s_example")}
        definitions = {normalize(t) for (t,) in con.execute("SELECT definition FROM s_sense WHERE definition <> ''")}
    finally:
        con.close()
    return examples, definitions


def learn(markups: Iterable[str], examples: set[str], definitions: set[str]) -> dict[str, tuple[int, int]]:
    """The example styles of a dictionary: {style key: (example hits, definition hits)}.

    Each style an English text is printed in is tried as the example style, and its texts are
    then read as pairs() will read them if it is one: all the English inside one of its
    elements, however its words are styled ("<em>Mr</em> Smith came home."), is one text."""
    hits: dict[str, Counter] = {}
    for markup in markups:
        tried = {key for key, _, _ in candidates(markup)}
        for style in tried:
            for key, en, _ in candidates(markup, {style}):
                if key != style:
                    continue
                text = normalize(en)
                counter = hits.setdefault(key, Counter())
                counter["example"] += text in examples
                counter["definition"] += text in definitions
    return {key: (c["example"], c["definition"]) for key, c in hits.items()
            if c["example"] >= MIN_EXAMPLE_HITS and c["example"] >= MIN_RATIO * c["definition"]}


def pairs(markup: str, example_styles: Iterable[str]) -> list[tuple[str, str]]:
    """The (English, Chinese) pairs whose English is printed in an example style.

    Cross-references ("See Synonyms at chafe" / "参见 chafe") are dropped; several examples
    joined by semicolons become one pair each when both sides have the same number of parts.
    """
    styles = frozenset(example_styles)
    out = []
    for key, en, zh in candidates(markup, styles):
        if key not in styles:
            continue
        en, zh = _EN_XREF.sub("", en).strip(), _ZH_XREF.sub("", zh).strip()
        en_parts, zh_parts = _EN_PARTS.split(en), _ZH_PARTS.split(zh)
        if len(en_parts) > 1 and len(en_parts) == len(zh_parts):
            out += [(e.strip(), z.strip()) for e, z in zip(en_parts, zh_parts) if e.strip() and z.strip()]
        elif en and zh:
            out.append((en, zh))
    return out
