"""ncecd text helpers shared by both renderings: flattening with "or" markers, pron text, label
splitting, joining Chinese glosses, and sending a definition to English or Chinese."""
from __future__ import annotations

import re

from structured.markup import clean, has_cjk, has_class

_LABEL_SPLIT = re.compile(r"[,，;；]")
_EDGE = " :：;；,，"


def _flat(el, skip=lambda e: False) -> str:
    """Text of `el` with children matching `skip` left out and "or" markers spelled out."""
    return clean(_flat_raw(el, skip))


def _flat_raw(el, skip) -> str:
    # whitespace is kept until the whole text is joined: "<i>to </i>grelt" is "to grelt", not "togrelt"
    out = [el.text or ""]
    for child in el:
        if isinstance(child.tag, str) and not skip(child):
            out.append(" or " if has_class(child, "or") or has_class(child, "pluralor") else _flat_raw(child, skip))
        out.append(child.tail or "")
    return "".join(out)


def _pron_text(pron) -> str:
    """IPA as printed; a note inside it ("sometimes", "Scottish") is set off by spaces."""
    out = [pron.text or ""]
    for child in pron:
        if isinstance(child.tag, str):
            note = has_class(child, "sut") or has_class(child, "ggs")
            out.append(f" {child.text_content()} " if note else child.text_content())
        out.append(child.tail or "")
    return clean("".join(out))


def _labels(value: str) -> list[str]:
    value = clean(value).strip("<>〈〉【】[]［］ ")
    if not value:
        return []
    if value.startswith("+") or value.endswith("+"):  # collocation "[+ bag, camera]" is one label
        return [value]
    return [p for p in (clean(part).strip("<>〈〉【】 ") for part in _LABEL_SPLIT.split(value)) if p and "<" not in p]


def _join_zh(parts: list[str]) -> str:
    out = ""
    for part in (clean(p) for p in parts):
        if not part:
            continue
        if out and out[-1] not in "；;，,。":
            out += "；"
        out += part
    return out.strip(_EDGE)


def _split_def(value: str) -> tuple[str, str]:
    """A definition string goes to definition_zh when it has any CJK, else to definition."""
    value = clean(value).strip(_EDGE)
    return ("", value) if has_cjk(value) else (value, "")


def _is_header_text(el) -> bool:
    """Children of span.header that are part of the headword line (not swallowed body content)."""
    return el.tag in ("sub", "sup", "i", "b") or any(has_class(el, c) for c in ("doble", "or", "differ"))
