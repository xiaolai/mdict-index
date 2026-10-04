"""Oxford Advanced Learner's Dictionary, 10th edition (OALD10).

Structure (one div.entry per part of speech; "close" has five: verb, noun, adjective, adverb, noun):
  webtop: h1.headword (span.hm = homograph), span.pos,
          span.phonetics > div.phons_br|phons_n_am > span.phon + a.sound
  Each div.entry gives its senses its own part of speech; Entry.pos and Entry.prons collect every
  section's (identical pronunciations once); the homograph number is kept only when all sections agree.
  verb forms: table td.verb_form (span.vf_prefix is the label, not the form)
  senses: li.sense[@sensenum] > span.grammar|labels, span.def, ul.examples span.x;
          extra examples: [@unbox='extra_examples'] span.unx
  idioms: span.idm-g > span.idm (the phrase) + its own li.sense
  word origin: [@unbox='wordorigin'] span.body (several sections' origins are joined with "; ")
  a sense with no span.def is glossed by span.use ("(makes adverbs from ...)"; 17 senses, e.g. "-ally")
Other boxes (synonyms, grammar notes, collocations) stay in layer 1.

Stubs (records with no definition), each identified by its markup:
  index       "@opal_..." word-list pages (no entry structure; 548)
  inflection  "past tense of X" cross-references ("awoke")
  xref        only cross-references or jump links to where the content lives ("absentia", "accustom")
  empty       headword and pronunciation only ("draft pick")
"""
from __future__ import annotations

import re

from structured.markup import cls, clean, parse as parse_html, strip_slashes, text
from structured.model import Entry, Example, Pron, Sense

KEY = "oald"
COVERS = "definitions"
MIN_COVERAGE = 0.99  # min(0.99, measured content coverage rounded down); measured 1.0 with stubs classified

_NOT_IN_BOX = "not(ancestor::*[@unbox])"
_NOT_IN_IDIOM = f"not(ancestor::*[{cls('idm-g')}])"


def _labels(sense) -> tuple[str, ...]:
    out = []
    for el in sense.xpath(f".//span[{cls('grammar')} or {cls('labels')}][{_NOT_IN_BOX}]"):
        label = text(el).strip("[]() ")
        if label and label not in out:
            out.append(label)
    return tuple(out)


_INFLECTION = re.compile(r"^(past tense|past participle|plural|present participle|comparative|superlative)\b.*\bof\b", re.I)


def _sense(li, kind: str, phrase: str, pos: str) -> Sense | None:
    definition = text(next(iter(li.xpath(f".//span[{cls('def')}][{_NOT_IN_BOX}]")), None))
    if not definition:  # suffix and function-word senses are glossed by span.use instead
        definition = text(next(iter(li.xpath(f".//span[{cls('use')}][{_NOT_IN_BOX}]")), None)).strip("() ")
    examples = [Example(text(x)) for x in li.xpath(f".//span[{cls('x')}][{_NOT_IN_BOX}]")]
    examples += [Example(text(x)) for x in li.xpath(f".//*[@unbox='extra_examples']//span[{cls('unx')}]")]
    examples = [e for e in examples if e.text]
    if not (definition or examples):
        return None
    return Sense(kind=kind, pos=pos, number=clean(li.get("sensenum") or ""), phrase=phrase,
                 labels=_labels(li), definition=definition, examples=tuple(examples))


def _prons(webtop) -> list[Pron]:
    out = []
    for region, klass in (("uk", "phons_br"), ("us", "phons_n_am")):
        for box in webtop.xpath(f".//div[{cls(klass)}][not(ancestor::table)]"):
            ipa = strip_slashes(text(next(iter(box.xpath(f".//span[{cls('phon')}]")), None)))
            audio = next(iter(box.xpath(".//a[starts-with(@href, 'sound://')]/@href")), "")
            if ipa or audio:
                out.append(Pron(ipa=ipa, region=region, audio=audio))
    return out


def _section_senses(section, pos: str) -> list[Sense]:
    """Senses of one div.entry: its ordinary senses under its own part of speech, then its idioms."""
    out = []
    for li in section.xpath(f".//li[{cls('sense')}][{_NOT_IN_IDIOM}][{_NOT_IN_BOX}]"):
        if (s := _sense(li, "sense", "", pos)) is not None:
            out.append(s)
    for group in section.xpath(f".//span[{cls('idm-g')}]"):
        phrase = text(next(iter(group.xpath(f".//span[{cls('idm')}]")), None))
        for li in group.xpath(f".//li[{cls('sense')}]"):
            if phrase and (s := _sense(li, "phrase", phrase, "")) is not None:
                out.append(s)
    return out


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    # A record holds one div.entry per part of speech ("close": verb, noun, adjective, adverb, noun), each
    # with its own webtop; a record without that structure is read as a single section.
    sections = root.xpath(f"//div[{cls('entry')}]") or [root]
    shown = ""
    homographs: list[str] = []
    pos_list: list[str] = []
    prons: list[Pron] = []
    senses: list[Sense] = []
    webtops = []
    for section in sections:
        webtop = next(iter(section.xpath(f".//div[{cls('webtop')}][{_NOT_IN_IDIOM}]")), None)
        section_pos: list[str] = []
        hw_el = next(iter(section.xpath(f".//h1[{cls('headword')}]")), None)
        if hw_el is not None:
            homograph = text(next(iter(hw_el.xpath(f".//*[{cls('hm')}]")), None))
            name = text(hw_el)
            if homograph and name.endswith(homograph):
                name = name[: -len(homograph)].strip()
            shown = shown or name
            homographs.append(homograph)
        if webtop is not None:
            webtops.append(webtop)
            section_pos = [p for p in (text(e) for e in webtop.xpath(f".//span[{cls('pos')}]")) if p]
            pos_list += section_pos
            prons += [p for p in _prons(webtop) if p not in prons]
        senses += _section_senses(section, section_pos[0] if section_pos else "")

    forms = []
    for td in root.xpath(f"//td[{cls('verb_form')}]"):
        prefix = text(next(iter(td.xpath(f".//span[{cls('vf_prefix')}]")), None))
        form = text(td)[len(prefix):].strip() if text(td).startswith(prefix) else text(td)
        if form and form not in forms:
            forms.append(form)

    origins = [text(body) for body in root.xpath(f"//*[@unbox='wordorigin']//span[{cls('body')}]")]
    homograph = homographs[0] if len(set(homographs)) == 1 else ""  # sections of homographs 1 and 2: no single number
    stub = "" if any(s.definition for s in senses) else _stub_reason(root, headword, webtops[0] if webtops else None)
    return Entry(headword=shown or clean(headword), homograph=homograph, pos=tuple(dict.fromkeys(pos_list)),
                 prons=tuple(prons), senses=tuple(senses), etymology="; ".join(dict.fromkeys(o for o in origins if o)),
                 forms=tuple(forms), stub=stub)


def _stub_reason(root, headword: str, webtop) -> str:
    """Why a record has no definition, from positive evidence in its markup ('' if none found)."""
    if headword.startswith("@") and webtop is None:
        return "index"
    xrefs = root.xpath(f"//*[{cls('xrefs')} or {cls('xr-g')}]")
    senses = root.xpath(f"//li[{cls('sense')}]")
    pointer_text = text(senses[0]) if senses else (text(xrefs[0]) if xrefs else "")
    if _INFLECTION.match(pointer_text):
        return "inflection"
    if xrefs or root.xpath(f"//*[{cls('jumplinks')}]"):
        return "xref"
    if webtop is not None and not root.xpath(f"//li[{cls('sense')}]"):
        return "empty"
    return ""
