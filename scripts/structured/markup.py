"""HTML helpers shared by the dictionary parsers (lxml-based).

Named markup.py, not html.py: a module named html next to a script run from this folder
shadows the standard library's html module for every parser."""
from __future__ import annotations

import re

import lxml.html
from lxml.etree import ParserError

# CJK ideographs: Extension A, the unified block, compatibility ideographs, and the supplementary
# planes (Extension B onwards, e.g. "𠮷").
CJK = re.compile(r"[㐀-䶿一-鿿豈-﫿\U00020000-\U0003FFFF]")
_WS = re.compile(r"\s+")
# Superscript digits as printed after a headword ("take¹"): the homograph number they spell.
SUPERSCRIPT = {"¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9"}
_DROP = ("script", "style", "link", "noscript", "template")
# Elements whose boundaries separate words when rendered: "hello<br>world" reads "hello world". The
# block, list-item and table boxes of the HTML Standard's user-agent stylesheet (Rendering, 15.3:
# html/body, flow content, sections and headings, lists, tables, fieldset), plus details/summary (15.5).
_BREAKS = frozenset({
    "br", "hr",
    "html", "body",
    "address", "blockquote", "center", "dialog", "div", "figure", "figcaption", "footer", "form", "header",
    "legend", "listing", "main", "p", "plaintext", "pre", "search", "xmp",
    "article", "aside", "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "nav", "section",
    "dir", "dd", "dl", "dt", "menu", "ol", "ul", "li",
    "table", "caption", "colgroup", "col", "thead", "tbody", "tfoot", "tr", "td", "th",
    "fieldset", "details", "summary",
})
_ALWAYS_BREAKS = frozenset({"br", "hr"})  # empty by nature, and still a break


def parse(html: str):
    """Parse an entry into an lxml element; scripts and styles removed. Never raises on odd input."""
    try:
        root = lxml.html.fragment_fromstring(html, create_parent="div")
    except (ParserError, ValueError):
        root = lxml.html.fragment_fromstring("<div></div>")
    for bad in root.xpath("|".join(f"//{t}" for t in _DROP)):
        bad.drop_tree()
    return root


def cls(name: str) -> str:
    """XPath predicate matching elements whose class list contains `name` exactly."""
    return f"contains(concat(' ', normalize-space(@class), ' '), ' {name} ')"


def class_set(el) -> set[str]:
    """The class names of an element."""
    return set((el.get("class") or "").split())


def has_class(el, name: str) -> bool:
    """Whether an element's class list contains `name` exactly."""
    return name in (el.get("class") or "").split()


def find(el, name: str, tag: str = "*"):
    """Descendants of `el` with class `name`."""
    return el.xpath(f".//{tag}[{cls(name)}]")


def first(el, name: str, tag: str = "*"):
    found = find(el, name, tag)
    return found[0] if found else None


def text(el) -> str:
    """Visible text of an element, whitespace collapsed; '' for None.

    Line breaks and block elements separate words ("hello<br>world", "<p>a</p><p>b</p>");
    inline markup does not ("un<b>believ</b>able"). A block holding no text separates nothing:
    dictionaries style such elements (an audio icon's <div>) inline, so "CARpet<div>🔊</div>,"
    stays "CARpet,". Comments contribute nothing.
    """
    if el is None:
        return ""
    if not hasattr(el, "text_content"):
        return clean(str(el))
    parts: list[str] = []
    texts = 0  # how many non-blank text pieces have been emitted so far
    # (node, its children are done, where its opening separator went, texts before it);
    # iterative, so deep nesting cannot overflow the stack
    stack: list[tuple] = [(el, False, -1, 0)]
    while stack:
        node, done, opened_at, texts_before = stack.pop()
        is_element = isinstance(node.tag, str)  # comments and processing instructions have no str tag
        breaks = is_element and node.tag.lower() in _BREAKS
        if done:
            if breaks:
                if texts > texts_before or node.tag.lower() in _ALWAYS_BREAKS:
                    parts.append(" ")
                else:
                    parts[opened_at] = ""  # it held no text: it separates nothing
            if node is not el and node.tail:
                parts.append(node.tail)
                texts += bool(node.tail.strip())
            continue
        if breaks:
            parts.append(" ")
        stack.append((node, True, len(parts) - 1, texts))
        if is_element and node.text:
            parts.append(node.text)
            texts += bool(node.text.strip())
        stack.extend((child, False, -1, 0) for child in reversed(node))
    return clean("".join(parts))


def clean(value: str) -> str:
    return _WS.sub(" ", value.replace("\xa0", " ")).strip()


def has_cjk(value: str) -> bool:
    return bool(CJK.search(value))


def split_en_zh(value: str) -> tuple[str, str]:
    """Split "English text 中文翻译" at the first CJK character: (english, chinese)."""
    m = CJK.search(value)
    if not m:
        return clean(value), ""
    # keep opening brackets that belong to the Chinese part, spaces inside them too: "（打电话）喂", "（ 中文）"
    start = m.start()
    while True:
        before = start
        while before > 0 and value[before - 1].isspace():
            before -= 1
        if before == 0 or value[before - 1] not in "（(〈【[":
            break
        start = before - 1
    return clean(value[:start]), clean(value[start:])


def strip_slashes(ipa: str) -> str:
    return clean(ipa).strip("/[] ").strip()
