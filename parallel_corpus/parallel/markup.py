"""Read dictionary markup as tags, comments and text.

Shared by parallel/text.py and parallel/styled.py, so that both see the same tags. A tag is
read attribute by attribute, as a browser reads it, not up to the first ">": a quoted value
may hold "<" and ">" (title="a < x > b") and be of any length, and an attribute's name is
looked for among the attributes, never inside another one's value (title="use color:red" is
not a colour). A style attribute is read as CSS: comments and quoted strings are not
declarations (see declarations()).

Dictionary markup is often broken, so nothing here raises. A tag that cannot be read attribute
by attribute (an unclosed quote) ends at its first ">", and a "<" that starts no tag is text.

The reading is linear in the markup: every search for a character or a closing tag starts
where the previous search for it stopped (see _Next), so no stretch of text is searched again
however many broken tags point into it.
"""
from __future__ import annotations

import html
import re
from collections.abc import Callable, Iterator

TEXT, OPEN, CLOSE = "text", "open", "close"
RAW = frozenset({"script", "style"})  # elements holding code, not text (by local name: xhtml:script too)

_NAME = re.compile(r"(/?)([A-Za-z][\w:.-]*+)")
_SPACE = re.compile(r"[\s/]*+")
_ATTRIBUTE_NAME = re.compile(r"""[^\s/>=<"']++""")
_EQUALS = re.compile(r"\s*+=\s*+")
_UNQUOTED = re.compile(r"""[^\s>"'<]++""")
_BROKEN = re.compile(r"""(/?)([A-Za-z][\w:.-]*+)([^<>]*+)>""")   # a tag read up to its first ">"
_DECLARATION_TAG = re.compile(r"[!?][A-Za-z][^<>]*+>")            # <!DOCTYPE ...>, <?xml ...?>
_AFTER_VALUE = frozenset(" \t\n\r\f/>")
# HTML ends raw text at "</name" followed by space, "/" or ">", whatever then runs to the ">"
_RAW_END = {name: re.compile(rf"</(?:[\w.-]+:)?{name}(?=[\s/>])[^>]*>", re.I) for name in RAW}
NUL = "\x00"  # ends a record in a block of records


class _Next:
    """The first match at or after a position (len(text) if none). Positions asked for only
    grow while a tag or a record is read, so a search resumes from the last one: if the last
    search from `at` found `found`, every position up to `found` has the same answer."""

    def __init__(self, text: str, search: Callable[[int], int]):
        self.text, self.search = text, search
        self.at, self.found = 0, -1

    def __call__(self, pos: int) -> int:
        if not self.at <= pos <= self.found:
            self.at, self.found = pos, self.search(pos)
        return self.found


def _finder(text: str, needle: str) -> _Next:
    return _Next(text, lambda pos: i if (i := text.find(needle, pos)) >= 0 else len(text))


def _pattern_finder(text: str, pattern: re.Pattern) -> _Next:
    return _Next(text, lambda pos: m.start() if (m := pattern.search(text, pos)) else len(text))


def tokens(markup: str) -> Iterator[tuple[str, str, str, bool]]:
    """(kind, text or tag name, attributes, self-closing), in order.

    Comments and declarations are dropped, and so are the contents of a script or style
    element (by its local name, so xhtml:script too), from a real opening tag (not one inside a
    comment or an attribute value) to its closing tag, or, without one, to the end of its record,
    as a browser runs an unclosed script to the end of its document.
    """
    n = len(markup)
    find: dict[str, _Next] = {ch: _finder(markup, ch) for ch in ('"', "'", "<", ">", NUL)}
    raw_end = {name: _pattern_finder(markup, p) for name, p in _RAW_END.items()}
    last_close = markup.rfind("-->")  # found once: a comment opened after it cannot close, and is text
    pos = search = 0  # where the current text starts; where to look for the next "<"
    while (lt := markup.find("<", search)) >= 0:
        tag = _tag(markup, lt, find, last_close)
        if tag is None:  # a "<" that starts no tag is text
            search = lt + 1
            continue
        kind, name, attrs, closed, end = tag
        if lt > pos:
            yield TEXT, markup[pos:lt], "", False
        pos = search = end
        if kind is None:  # a comment or a declaration
            continue
        yield kind, name, attrs, closed
        prefix, _, local = name.lower().rpartition(":")
        # HTML ignores "/>" on a script or style (not void elements: <script/> still opens one);
        # XML, which a prefix marks (xhtml:script), honours it
        if kind == OPEN and local in RAW and not (closed and prefix):
            pos = search = min(raw_end[local](pos), find[NUL](pos))  # its closing tag, or the end of its record
    if pos < n:
        yield TEXT, markup[pos:], "", False


def _tag(markup: str, i: int, find: dict[str, _Next], last_close: int) -> tuple[str | None, str, str, bool, int] | None:
    """The tag starting at markup[i] == "<": (kind, name, attributes, self-closing, end), with
    kind None for a comment or a declaration; None if the "<" starts no tag."""
    if markup.startswith("<!--", i):
        end = markup.find("-->", i + 4) if i + 4 <= last_close else -1
        return None if end < 0 else (None, "", "", False, end + 3)
    m = _DECLARATION_TAG.match(markup, i + 1)
    if m:
        return None, "", "", False, m.end()
    m = _NAME.match(markup, i + 1)
    if not m:
        return None
    closing, name = m[1], m[2]
    end = _attributes_end(markup, m.end(), find)
    if end is not None:
        attrs = markup[m.end():end - 1]
    else:  # broken: up to the first ">"
        b = _BROKEN.match(markup, i + 1)
        if not b:
            return None
        attrs, end = b[3], b.end()
    closed = attrs.rstrip().endswith("/")
    return (CLOSE if closing else OPEN), name, attrs, (closed and not closing), end


def _attributes_end(markup: str, j: int, find: dict[str, _Next]) -> int | None:
    """The end (just past ">") of a tag whose attributes start at j, read attribute by
    attribute; None if they cannot be read so. A quoted value runs to its closing quote, which
    must be in the same record; if it holds "<" or ">" the quote must be followed by a space, "/"
    or ">", since after an unclosed quote (color='red>He's home.) the next quote is somewhere in
    the text with a letter after it."""
    n = len(markup)
    while True:
        j = _SPACE.match(markup, j).end()
        if j >= n:
            return None
        if markup[j] == ">":
            return j + 1
        m = _ATTRIBUTE_NAME.match(markup, j)
        if not m:
            return None
        j = m.end()
        eq = _EQUALS.match(markup, j)
        if not eq:
            continue
        j = eq.end()
        if j < n and markup[j] in "\"'":
            close = find[markup[j]](j + 1)
            if close >= n or find[NUL](j + 1) < close:
                return None
            angled = find["<"](j + 1) < close or find[">"](j + 1) < close
            if angled and (close + 1 >= n or markup[close + 1] not in _AFTER_VALUE):
                return None
            j = close + 1
            continue
        m = _UNQUOTED.match(markup, j)
        if not m:
            return None
        j = m.end()


# In a broken tag the closing quote may be missing (color='red): the value is then the word after the quote.
_PAIR = re.compile(r"""([^\s/>=<"']+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|["']?([^\s>"'<]+)))?""")


def attributes(attrs: str) -> dict[str, str]:
    """The attributes of a tag, by lowercase name, their values with entities decoded; the first
    of a repeated name counts, as in a browser."""
    out: dict[str, str] = {}
    for m in _PAIR.finditer(attrs):
        value = next((v for v in m.groups()[1:] if v is not None), "")
        out.setdefault(m[1].lower(), html.unescape(value) if "&" in value else value)
    return out


_CSS_NAME = re.compile(r"-?[A-Za-z_][\w-]*")


def declarations(style: str) -> dict[str, str]:
    """The properties of a style attribute, by lowercase name; the last of a repeated name
    counts, as in CSS. Read as CSS is: comments are removed, and a ";" or ":" inside a quoted
    string or brackets ("url(a;b)") separates nothing. A name that is not a plain identifier
    (one written with CSS escapes) is not read."""
    out: dict[str, str] = {}
    for declaration in _css_declarations(style):
        name, colon, value = declaration.partition(":")
        name = name.strip()
        if colon and _CSS_NAME.fullmatch(name):
            out[name.lower()] = value.strip()
    return out


def _css_declarations(style: str) -> list[str]:
    """The text between the top-level semicolons of a style, without its comments."""
    parts: list[str] = []
    buf: list[str] = []
    depth, i, n = 0, 0, len(style)
    while i < n:
        ch = style[i]
        if ch == "/" and style.startswith("/*", i):
            end = style.find("*/", i + 2)
            i = n if end < 0 else end + 2  # an unclosed comment runs to the end
            buf.append(" ")
            continue
        if ch in "\"'":
            j = i + 1
            while j < n and style[j] != ch:
                j += 2 if style[j] == "\\" else 1
            buf.append(style[i:j + 1])
            i = j + 1
            continue
        if ch == "\\":
            buf.append(style[i:i + 2])
            i += 2
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            parts.append("".join(buf))
            buf.clear()
            i += 1
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts
