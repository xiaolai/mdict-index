"""Oxford Dictionary of English, 3rd edition ("ODE 3e 20191231M" build, with Chinese glosses).

This build obfuscates its class names into three-character hashes; the parser relies on
tag nesting plus those hashes, whose roles were worked out from the stylesheet and the
content. The one readable class is cn_def (Chinese merged in from the ODECN data).

  div.Od3 > div.k0i                 one per homograph (an MDict entry holds them all)
    div.h1s > h2.z2h | h2.hxy       headword; span.lx6 = homograph number
              span.pxt "/…/"        IPA; its img.a8e plays the audio through
                                    onclick="o0e.a(this,0,'p/pal/pale_/pale__gb_1')"
    span.rqo > span.l6p             "(also a)": a variant spelling of the headword
    div.k0z                         one per part of speech
      span.nvt > span.xno           part of speech; span.pzg > span.iko = plural forms
      em.tb0 | em.u0f | i.rnr       POS-wide labels: grammar "[no object]", region or
        (span.cvq "chiefly" joins    subject "British", register "informal"
         the label after it)
      div.se2 > div.u2n > div.ysl   numbered sense;  div.ewq > div.ysl  subsense
      div.ulk > div.ysl             unnumbered sense
        span.vkq = number, the same label elements, span.aw5 = definition (one or
        more), div.cn_def = Chinese, span.xxn > em.xv4 = example + following p.cn =
        its Chinese, div.ld9 > ul.dhk > li.lmn = further examples (collapsed),
        span.sdh + div.pzw = synonyms box, ul.s6x = taxonomic note
    div.f0t > div.dwy > div.b6i     derivatives: h4 word, span.xno pos, ul.rpz > li.lmn
    div.s0c                         phrases: links to the phrases' own entries only
    div.e8l > div.ysl > p           origin; its ul.dhk > li > p.p9h is a word story
    div.m7g rhymes, div.uxu usage, div.dzg encyclopedic note, div.n3h "See parent entry"
A few phrase stubs are div.Od3 > div.b6i whose only sense is "see X".

Definitions drop their trailing colon (printed only to introduce the example). A few
example sentences carry their italics as escaped formatting tags ("&lt;i&gt;Title&lt;/i&gt;");
those element tags are removed, any other bracketed text is kept as printed. A
phrase is its own entry here, so its meanings are ordinary senses of that headword.
Pron audio: no sound:// href exists; the onclick handler passes a path to ODE's player
(o0e.a), which plays the .mdd file "mp3/<last segment with __ collapsed to _>.mp3":
"t/tak/take_/take__gb_1" -> "mp3/take_gb_1.mp3". The parser stores that file path, so it
resolves in the resource store (95% of references do; the rest, mostly US recordings of
proper names, are not in the .mdd). Region comes from the "__gb_" / "__us_" marker.

Left in layer 1: synonyms (pzw), usage notes (uxu), encyclopedic notes (dzg), taxonomic
notes (s6x), the word story, rhymes, sense-level variant forms (rqo, qbl), phrase link
lists, "see X" pointers, and images.

Stubs: a record whose senses only say "See X" (see + a link; "See" alone is the
definition of "clap eyes on") is "xref".

Coverage (full run, 205,378 records): 597 xref stubs, phrase stubs (div.b6i) and name
records such as "Alighieri, Dante" -> "See Dante"; all 204,781 content records are
covered (1.0).
"""
from __future__ import annotations

import copy
import re
from dataclasses import replace

from structured.markup import clean, cls, parse as parse_html, strip_slashes
from structured.markup import text as _raw_text
from structured.model import Entry, Example, Pron, Sense

KEY = "ode"
COVERS = "definitions"
MIN_COVERAGE = 0.99

_LABELS = ("tb0", "u0f", "rnr")          # grammar, region/subject, register
_QUALIFIER = "cvq"                       # "chiefly", "especially": joins the next label
_AUDIO = re.compile(r"o0e\.a\(\s*this\s*,\s*\d+\s*,\s*'([^']+)'")
_REGION = re.compile(r"__(gb|us)_")


def _audio_file(onclick_path: str) -> str:
    """The .mdd file ODE's player plays for an onclick path (see module docstring)."""
    return "mp3/" + onclick_path.rsplit("/", 1)[-1].replace("__", "_") + ".mp3"


_POINTER = re.compile(r"^(see also|see)\b", re.I)  # longer first: "see" alone also matches "see also"
# some example sentences carry their italics as escaped markup ("&lt;i&gt;Title&lt;/i&gt;",
# "&lt;EM&gt;"): formatting elements printed as text. Only those element tags are removed;
# other bracketed text ("< >", "<(em>") is printed content and stays
_ESCAPED_TAG = re.compile(r"</?(?:i|em|b|strong|sup|sub|u)\s*/?>", re.I)


def text(el) -> str:
    """Visible text, without inline tags that the source escaped into literal text."""
    return clean(_ESCAPED_TAG.sub("", _raw_text(el)))


def _kids(el, name: str, tag: str = "*"):
    return el.xpath(f"./{tag}[{cls(name)}]")


def _first(el, name: str, tag: str = "*"):
    found = _kids(el, name, tag)
    return found[0] if found else None


def _classes(el) -> set[str]:
    return set((el.get("class") or "").split()) if isinstance(el.tag, str) else set()


def _labels(container) -> list[str]:
    """Label elements that are direct children of `container`, before its definition."""
    out: list[str] = []
    qualifier = ""
    for child in container:
        names = _classes(child)
        if "ysl" in names and child.xpath("./h4") and not _kids(child, "aw5", "span"):
            continue  # a derivative's headword wrapper: its labels are printed after it
        if "aw5" in names or "ysl" in names or "se2" in names or "ulk" in names:
            break
        if _QUALIFIER in names:
            qualifier = text(child)
        elif names & set(_LABELS):
            value = clean(f"{qualifier} {text(child).strip('[]() ')}")
            qualifier = ""
            if value and value not in out:
                out.append(value)
    return out


def _definition(ysl) -> str:
    parts = [text(d) for d in _kids(ysl, "aw5", "span")]
    value = clean(" ".join(p for p in parts if p))
    return value[:-1].rstrip() if value.endswith(":") else value


def _zh(cn_def) -> str:
    """Chinese gloss; a leading span.cn_def_text (a gloss of the English) is kept apart."""
    glosses = cn_def.xpath(f".//span[{cls('cn_def_text')}]")
    rest = copy.deepcopy(cn_def)
    for g in rest.xpath(f".//span[{cls('cn_def_text')}]"):
        g.drop_tree()
    return clean(" ".join(p for p in [text(g) for g in glosses] + [text(rest)] if p))


def _examples(container) -> list[Example]:
    out: list[Example] = []
    for xxn in _kids(container, "xxn", "span"):
        nxt = xxn.getnext()
        zh = text(nxt) if nxt is not None and nxt.tag == "p" and "cn" in _classes(nxt) else ""
        if (en := text(xxn)) or zh:
            out.append(Example(text=en, text_zh=zh))
    for li in container.xpath(f"./div[{cls('ld9')}]/ul/li | ./ul[{cls('rpz')}]/li"):
        if value := text(li):
            out.append(Example(text=value))
    return out


def _is_pointer(definition: str, ysl) -> bool:
    """"See Dante." (a link) is a cross-reference; "See" alone defines "clap eyes on"."""
    m = _POINTER.match(definition)
    link = next(iter(ysl.xpath(f"./span[{cls('aw5')}]//a")), None)
    return bool(m) and link is not None and definition[m.end():].lstrip(" :").startswith(text(link))


def _sense(ysl, pos: str, inherited: list[str]) -> Sense | None:
    definition = _definition(ysl)
    if _is_pointer(definition, ysl):
        definition = ""
    definition_zh = clean(" ".join(_zh(c) for c in _kids(ysl, "cn_def", "div")))
    examples = _examples(ysl)
    if not (definition or definition_zh or examples):
        return None
    labels = list(inherited) + [lab for lab in _labels(ysl) if lab not in inherited]
    return Sense(pos=pos, number=text(_first(ysl, "vkq", "span")), labels=tuple(labels),
                 definition=definition, definition_zh=definition_zh, examples=tuple(examples))


def _prons(scope) -> list[Pron]:
    out: list[Pron] = []
    for pxt in _kids(scope, "pxt", "span"):
        onclick = next(iter(pxt.xpath(".//img/@onclick")), "")
        audio = m.group(1) if (m := _AUDIO.search(onclick)) else ""
        region = {"gb": "uk", "us": "us"}.get(m.group(1), "") if (m := _REGION.search(audio)) else ""
        pron = Pron(ipa=strip_slashes(text(pxt)), region=region, audio=_audio_file(audio) if audio else "")
        if (pron.ipa or pron.audio) and pron not in out:
            out.append(pron)
    return out


def _derivative(b6i) -> list[Sense]:
    """A derivative: its word, pos and examples, plus any definitions it carries."""
    word = text(next(iter(b6i.xpath(f"./div[{cls('ysl')}]/h4")), None))
    if not word:
        return []
    pos = text(_first(b6i, "xno", "span"))
    examples = tuple(_examples(b6i))
    labels = _labels(b6i)
    own = [replace(s, kind="derivative", phrase=word)
           for ysl in _kids(b6i, "ysl", "div") if (s := _sense(ysl, pos, labels)) is not None]
    if not own:
        return [Sense(kind="derivative", pos=pos, phrase=word, labels=tuple(labels), examples=examples)]
    return [replace(own[0], examples=own[0].examples + examples)] + own[1:]


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    shown, homographs, pos_list, prons, forms, senses, origins = "", [], [], [], [], [], []

    for block in root.xpath(f"//div[{cls('k0i')}]"):
        top = _first(block, "h1s", "div")
        if top is not None:
            h2 = next(iter(top.xpath(f"./h2[{cls('z2h')} or {cls('hxy')}]")), None)
            if h2 is not None:
                hm = text(_first(h2, "lx6", "span"))
                if hm and hm not in homographs:
                    homographs.append(hm)
                name = text(h2)
                shown = shown or (name[: -len(hm)].strip() if hm and name.endswith(hm) else name)
            prons += [p for p in _prons(top) if p not in prons]
        # "(also a)" beside the headword; one inside the h2 is part of a phrase ("clap (or lay) eyes on")
        for rqo in block.xpath(f".//span[{cls('rqo')}][not(ancestor::div[{cls('ysl')}])][not(ancestor::h2)]"):
            forms += [f for f in (text(v) for v in rqo.xpath(f".//span[{cls('l6p')}]")) if f and f not in forms]

        for k0z in block.xpath(f".//div[{cls('k0z')}]"):
            nvt = _first(k0z, "nvt", "span")
            pos = text(_first(nvt, "xno", "span")) if nvt is not None else ""
            if pos:
                pos_list.append(pos)
            if nvt is not None:
                forms += [f for f in (text(i) for i in nvt.xpath(f".//span[{cls('iko')}]")) if f and f not in forms]
            prons += [p for p in _prons(k0z) if p not in prons]
            inherited = _labels(k0z)
            for ysl in k0z.xpath(f"./div/div[{cls('ysl')}] | ./div/div/div[{cls('ysl')}]"):
                if not (_classes(ysl.getparent()) & {"u2n", "ewq", "ulk"}):
                    continue
                if (s := _sense(ysl, pos, inherited)) is not None:
                    senses.append(s)

        for b6i in block.xpath(f"./div[{cls('f0t')}]/div[{cls('dwy')}]/div[{cls('b6i')}]"):
            senses += _derivative(b6i)

        for p in block.xpath(f"./div[{cls('e8l')}]/div[{cls('ysl')}]/p"):
            if (origin := text(p)) and origin not in origins:
                origins.append(origin)

    for b6i in root.xpath(f"//div[{cls('Od3')}]/div[{cls('b6i')}]"):  # a phrase stub entry
        shown = shown or text(next(iter(b6i.xpath(f"./div[{cls('ysl')}]/h4")), None))
        senses += [s for ysl in _kids(b6i, "ysl", "div") if (s := _sense(ysl, "", [])) is not None]

    return Entry(headword=shown or clean(headword), homograph=homographs[0] if len(homographs) == 1 else "",
                 pos=tuple(dict.fromkeys(pos_list)), prons=tuple(prons), senses=tuple(senses),
                 etymology=" ".join(origins), forms=tuple(f for f in forms if f != (shown or clean(headword))),
                 stub=_stub_reason(root, senses))


def _stub_reason(root, senses) -> str:
    """Why a record has no definition: its senses only say "See X"."""
    if any(s.definition or s.definition_zh for s in senses):
        return ""
    if any(_is_pointer(_definition(ysl), ysl) for ysl in root.xpath(f"//div[{cls('ysl')}]")):
        return "xref"
    return "" if senses else "empty"
