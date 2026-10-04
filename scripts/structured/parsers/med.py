"""Macmillan English Dictionary (MED, British edition, from macmillandictionary.com).

Records are scraped web pages; every class is upper-case. A record holds one or
more homographs as a flat run of siblings, so homographs are tracked in
document order:
  span.BASE[@id]  (direct child of the page; id "take_1" -> homograph 1)
  div#headbar:    span.PART-OF-SPEECH, span.SYNTAX-CODING|STYLE-LEVEL|DIALECT (entry labels, inherited
                  by the homograph's senses; a phrase inside it does not take the SYNTAX-CODING ones),
                  span.PRONS > per variant a[href$="_British_English_pronunciation_*.mp3"] (uk) and
                  a[..._American_English_...] (us, audio only: MED prints British IPA), then span.PRON "/teɪk/",
                  div.wordforms span.INFLECTION-ENTRY -> forms,
                  h2.VARIANT (after the headbar) span.MAINENTRY span.BASE -> forms (its own PRONS are skipped)
  senses:         div.SENSE > div.SENSE-BODY > div.SENSE-NUM, span.MULTIWORD|SENSE-VARIANT span.BASE
                  (a phrase inside the entry), span.SYNTAX-CODING|STYLE-LEVEL|DIALECT|SUBJECT-AREA|
                  RESTRICTION-CLASS (labels), span.DEFINITION, div.EXAMPLES > p.EXAMPLE;
                  ol.SUB-SENSES > li > div.SUB-SENSE-BODY > div.SENSE-NUM "a." + div.SUB-SENSE-CONTENT
                  (same children). Senses flagged "From our crowdsourced Open Dictionary"
                  (div.greybackground) are part of the page and are kept.
  embedded phrasal verbs: div.phrasalverb > div.PV-HEAD (h2.ENTRY span.BASE = the phrase, labels)
                  + div.SENSE > div.phrasalverbsense (same children as SENSE-BODY)
  side content (never senses): div.THES (thesaurus snippet), div.sidebox (usage notes),
                  div.ONE-BOX, div.SENSE-INFO, div.block_relatedframe ("Related words"),
                  span.details (Open Dictionary submitter), phrases_container / phrasal_verbs_container
                  (links: phrases and phrasal verbs are records of their own).
Phrase and phrasal-verb records (headbar pos "phrase" / "phrasal verb") yield kind
"phrase" / "phrasal_verb" senses whose phrase is the headword.
Buzzword pages (div#wotwentry: p.wotwdefinition + div.example > p, span.source, span.sourcedate)
give one sense with quotation examples when the record has no ordinary definition; the essay
(div#wotwarticle) stays in layer 1.

Stubs (only for a record with no definition, and only on the markup that says why):
  h1.cattitle "... - thesaurus"             -> "index": a category page listing other entries
  span.GREF-TYPE "a British spelling of"    -> "variant";  "the past tense of" -> "inflection"
  span.SAMEAS "same as X", span.MAIN-XREF, div.ONE-BOX "See ..." -> "xref"
Country pages holding only a fact table (span.PROPERTIES) stay content records, uncovered.

Coverage (full run, 68,989 records): stubs index 3,772, variant 622, inflection 350, xref 220;
64,025 content records, 0.9970 covered, so MIN_COVERAGE = 0.99. The ~190 uncovered are country
pages holding only a fact table (span.PROPERTIES), which no printed marker excuses.
"""
from __future__ import annotations

import re

from structured.markup import clean, cls, parse as parse_html, strip_slashes, text
from structured.model import Entry, Example, Pron, Sense

KEY = "med"
COVERS = "definitions"
MIN_COVERAGE = 0.99

_BOXES = ("THES", "sidebox", "ONE-BOX", "SENSE-INFO", "block_relatedframe", "details", "am-dictionary")
_IN_BOX = "ancestor::*[" + " or ".join(cls(b) for b in _BOXES) + "]"
_LABELS = ("SYNTAX-CODING", "STYLE-LEVEL", "DIALECT", "SUBJECT-AREA", "RESTRICTION-CLASS")
_LABEL_XP = "./span[" + " or ".join(cls(c) for c in _LABELS) + "]"
_HOMNUM = re.compile(r"_(\d+)$")
_KIND_BY_POS = {"phrase": "phrase", "phrasal verb": "phrasal_verb"}


def _first(el, xpath: str):
    found = el.xpath(xpath)
    return found[0] if found else None


def _text_skip(el, skip: tuple[str, ...]) -> str:
    """Visible text of `el` without the subtrees carrying one of the `skip` classes."""
    parts: list[str] = []

    def walk(e) -> None:
        if not isinstance(e.tag, str) or set((e.get("class") or "").split()) & set(skip):
            return
        if e.text:
            parts.append(e.text)
        for child in e:
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(el)
    return clean("".join(parts))


def _labels(body, xpath: str = _LABEL_XP) -> list[str]:
    out = []
    for el in body.xpath(xpath):
        label = text(el).strip("[]() ,")
        if label and label not in out:
            out.append(label)
    return out


def _definition(body) -> str:
    parts = [_text_skip(d, ("SYNTAX-CODING",)) for d in body.xpath(f"./span[{cls('DEFINITION')}]")]
    return clean(" ".join(p for p in parts if p))


def _examples(body) -> tuple[Example, ...]:
    out = []
    for p in body.xpath(f"./div[{cls('EXAMPLES')}]/p[{cls('EXAMPLE')}]"):
        value = text(p)
        if value:
            out.append(Example(text=value))
    return tuple(out)


def _sense_phrase(body) -> str:
    return text(_first(body, f"./span[{cls('MULTIWORD')}]//span[{cls('BASE')}] | "
                             f"./div[{cls('SENSE-VARIANT')}]//span[{cls('BASE')}]"))


def _senses(sense, pos: str, kind: str, phrase: str, entry_labels: list[str], grammar: list[str]) -> list[Sense]:
    """`entry_labels` are the headbar's labels, inherited by the homograph's own senses; those also in
    `grammar` (its SYNTAX-CODING) describe the headword and are not passed on to a phrase inside it.
    An embedded phrasal verb inherits its own head's labels instead."""
    body = _first(sense, f"./div[{cls('SENSE-BODY')} or {cls('phrasalverbsense')}]")
    if body is None:
        return []
    inherited = list(entry_labels)
    pv = _first(sense, f"ancestor::div[{cls('phrasalverb')}]")
    head = _first(pv, f"./div[{cls('PV-HEAD')}]") if pv is not None else None
    if head is not None:
        kind, pos = "phrasal_verb", "phrasal verb"
        phrase = text(_first(head, f".//span[{cls('BASE')}]")) or phrase
        inherited = _labels(head)
    number = text(_first(body, f"./div[{cls('SENSE-NUM')}]")).rstrip(".")
    own_phrase = _sense_phrase(body)
    if own_phrase:
        kind, phrase = ("phrase" if kind == "sense" else kind), own_phrase
        if head is None:
            inherited = [x for x in inherited if x not in grammar]
    labels = inherited + [x for x in _labels(body) if x not in inherited]
    out = []
    definition, examples = _definition(body), _examples(body)
    if definition or examples:
        out.append(Sense(kind=kind, pos=pos, number=number, phrase=phrase, labels=tuple(labels),
                         definition=definition, examples=examples))
    for sub in body.xpath(f"./ol[{cls('SUB-SENSES')}]/li/div[{cls('SUB-SENSE-BODY')}]"):
        letter = text(_first(sub, f"./div[{cls('SENSE-NUM')}]")).rstrip(".")
        content = _first(sub, f"./div[{cls('SUB-SENSE-CONTENT')}]")
        if content is None:
            continue
        sub_phrase = _sense_phrase(content)
        sub_kind, sub_phrase = (("phrase" if kind == "sense" else kind), sub_phrase) if sub_phrase else (kind, phrase)
        sub_def, sub_examples = _definition(content), _examples(content)
        if sub_def or sub_examples:
            base = [x for x in labels if x not in grammar] if sub_phrase != phrase and head is None else labels
            sub_labels = base + [x for x in _labels(content) if x not in base]
            out.append(Sense(kind=sub_kind, pos=pos, number=number + letter, phrase=sub_phrase,
                             labels=tuple(sub_labels), definition=sub_def, examples=sub_examples))
    return out


def _prons(headbar) -> list[Pron]:
    """A PRONS block prints, per variant, its audio links and then its span.PRON; each transcription
    takes the British recording printed with it ("/ˈeəriən/" and "/ˈæriən/" have one each)."""
    out: list[Pron] = []

    def add(ipa: str, audio: dict[str, str]) -> None:
        found = [Pron(ipa=ipa, region="uk", audio=audio["uk"])] if ipa or audio["uk"] else []
        found += [Pron(ipa="", region="us", audio=audio["us"])] if audio["us"] else []
        out.extend(p for p in found if p not in out)

    for prons in headbar.xpath(f"./span[{cls('PRONS')}]"):
        audio = {"uk": "", "us": ""}
        for el in prons.xpath(f".//a[@href] | .//span[{cls('PRON')}]"):
            if el.tag == "span":
                add(strip_slashes(text(el)), audio)
                audio = {"uk": "", "us": ""}
            else:
                href = el.get("href")
                region = "uk" if "_British_English_" in href else "us" if "_American_English_" in href else ""
                if region and not audio[region]:
                    audio[region] = href
        if audio["uk"] or audio["us"]:
            add("", audio)  # recordings with no transcription after them
    return out


def _wotw(root) -> list[Sense]:
    box = _first(root, "//div[@id='wotwentry']")
    if box is None:
        return []
    definition = text(_first(box, f".//p[{cls('wotwdefinition')}]"))
    examples = []
    for ex in box.xpath(f".//div[{cls('example')}]"):
        quote = text(_first(ex, "./p")).strip("'‘’ ")
        date = text(_first(ex, f".//span[{cls('sourcedate')}]"))
        source = text(_first(ex, f".//span[{cls('source')}]"))
        if date and source.endswith(date):
            source = source[: -len(date)].strip()
        if quote:
            examples.append(Example(text=quote, kind="quotation", source=source, date=date))
    pos = text(_first(box, f".//span[{cls('part-of-speech')}]"))
    if not (definition or examples):
        return []
    return [Sense(pos=pos, definition=definition, examples=tuple(examples))]


def _pointer_kind(printed: str) -> str:
    """Stub reason for a printed pointer phrase ("a British spelling of", "the past tense of")."""
    words = set(printed.lower().replace(",", " ").split())
    if words & {"spelling", "spellings", "variant"}:
        return "variant"
    if words & {"past", "plural", "participle", "tense", "form", "case", "comparative", "superlative", "person"}:
        return "inflection"
    return "xref"


def _stub(root) -> str:
    """Why a record without a definition carries none, read from the markup that says so."""
    if root.xpath(f"//h1[{cls('cattitle')}]"):
        return "index"  # thesaurus category page: "Ways of folding - thesaurus"
    gref = _first(root, f"//span[{cls('GREF-TYPE')}]")
    if gref is not None:
        return _pointer_kind(text(gref))  # "a British spelling of hello", "the past tense of keep"
    if root.xpath(f"//span[{cls('SAMEAS')} or {cls('MAIN-XREF')}] | //div[{cls('ONE-BOX')}]"):
        return "xref"  # "same as lift", "See also main entry: take", a lone "See" box
    return ""


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    top = "/*/span[@id][" + cls("BASE") + "]"
    order = root.xpath(f"{top} | //div[@id='headbar'] | //div[{cls('SENSE')}][not({_IN_BOX})]")

    shown = homograph = word = ""
    homographs = 0
    pos = ""
    kind, phrase = "sense", ""
    entry_labels: list[str] = []  # the current homograph's headbar labels, and the grammar codes among them
    grammar: list[str] = []
    all_pos: list[str] = []
    prons: list[Pron] = []
    forms: list[str] = []
    senses: list[Sense] = []
    for el in order:
        classes = (el.get("class") or "").split()
        if "BASE" in classes:
            homographs += 1
            word = text(el)
            shown = shown or word
            m = _HOMNUM.search(el.get("id") or "")
            homograph = m.group(1) if m and homographs == 1 else ""
            pos, kind, phrase = "", "sense", ""
            entry_labels, grammar = [], []
        elif el.get("id") == "headbar":
            pos = text(_first(el, f"./span[{cls('PART-OF-SPEECH')}]"))
            if pos and pos not in all_pos:
                all_pos.append(pos)
            kind = _KIND_BY_POS.get(pos, "sense")
            phrase = word if kind != "sense" else ""
            entry_labels, grammar = _labels(el), _labels(el, f"./span[{cls('SYNTAX-CODING')}]")
            prons += [p for p in _prons(el) if p not in prons]
            forms += [text(f) for f in el.xpath(f".//span[{cls('INFLECTION-ENTRY')}]")]
        else:
            senses += _senses(el, pos, kind, phrase, entry_labels, grammar)

    forms += [text(b) for b in root.xpath(f"//*[{cls('VARIANT')}][not({_IN_BOX})]"
                                          f"//span[{cls('MAINENTRY')}]//span[{cls('BASE')}]")]
    if not any(s.definition for s in senses):
        senses += _wotw(root)
    shown = shown or clean(headword)
    stub = "" if any(s.definition for s in senses) else _stub(root)
    return Entry(headword=shown, homograph=homograph if homographs == 1 else "", pos=tuple(all_pos),
                 prons=tuple(prons), senses=tuple(senses),
                 forms=tuple(f for f in dict.fromkeys(forms) if f and f != shown), stub=stub)
