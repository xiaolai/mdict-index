"""Oxford English Dictionary (OED online, 2020 snapshot).

Two kinds of record:
  main entries   div#mainContent (several per record when homographs share a key, separated by
                 hr.hr_multi_keys), each with:
      h1 > span.hwSect > span.hw (headword) + span.ps (part of speech, sup.hm = homograph)
                       + span.obs ("†", obsolete headword)
      div.pronunciation.preEntry > div.pronunciation-wrapper  ("Brit." / "U.S." / "Scottish" ...
                 then a[href=sound://...] and /span.phonetics/; an unlabelled wrapper continues
                 the previous label); older entries put /span.phonetics/ straight in the div
      div.forms.preEntry > strong           the spellings ("Forms:" is the first strong)
      div.inflections.preEntry > em         irregular inflections
      div.preEntry > span.etymSummary       a one-line "Origin:" summary: skipped (double count)
      div.etymology.preEntry                the etymology ("Etymology:" label and the
                                             "(Show Less)" toggle removed)
      div.senseSect                         the senses
      div.lemSect > h3.lemSectType          "Compounds", "Derivatives", "Phrases", "Phrasal verbs"
      div.rev / div.unrev / div.revSect     publication notes; revSect ("Draft additions")
                                             senses are read like any others
  sub-entries    span.hw1 (the sub-entry lemma) + the senseGroup(s) of that lemma, often in
                 div.phrase, span.subentryInline or a senseWrap, and div.ref (link to the
                 main entry: skipped)
Senses:
  div.senseWrap > span.numbering ("A.", "I.", "1."), span.ps, em (labels for the whole
                 group), span.lemmaInDef (a phrase heading), then senseGroups / senseWraps; a wrap
                 with neither (rare: "a. A sign.") is itself a sense, read like an h3
  span.subentryInline > span.lemma + div.senseSect   a phrasal verb or phrase heading its own
                 senses (in lemSects); inside an h3 it is just the lemma + definition
  div.senseGroup > div.top > h3: span.numbering, span.lemma (compound/derivative lemma),
                 span.ps, leading em labels ("intransitive. ", "Chess and Draughts. "), the
                 definition, span.note (editorial note: skipped); pronunciation-wrappers inside
                 a sub-entry h3 are skipped
                 div.frame > div.quotationsBlock|quotationsBlockSibling (a sibling block may first
                 print a label, "figurative.", or a form group, "β.": Example.labels of its
                 quotations, as printed) > div.quotation >
                 span.noIndent (first span = the date as printed, rest = author, title, place)
                 + the quotation text

Mapping: one Sense per senseGroup. number = the numbering path in OED citation style: pieces
without their final "." joined, with a "." only after a capital letter or Roman numeral
("A.1", "I.3b", "2a", "b(a)"). labels = inherited group labels + the h3's leading label
segments, each up to its ". " and italic except for glue words ("colloquial (originally
U.S.)"); a "†" (obsolete) sense gets the label "†"; a senseSect's leading em ("Obsolete.")
labels all its senses. Senses in a lemSect get kind derivative (Derivatives), phrasal_verb
(Phrasal verbs) or phrase (Compounds, Phrases, others) with phrase = the lemma; a lemSect sense without
its own lemma keeps kind "sense" and gets the section name as a label. A senseSect sense
headed by a lemma is a phrase. In a sub-entry record the senses of the record's own lemma
are ordinary senses. Quotations -> Example(kind="quotation", text, date, source).
Several homographs in one record: pos lists all, homograph is left empty, and the etymologies
are joined as "(n.1) ... (v.) ...". Pronunciation region: Brit. -> uk, U.S. -> us, any other
variety -> "" with the variety in Pron.note ("Scottish"). audio is the href as referenced.

Stubs. More than half of the records are sub-entries, and many are never defined by OED:
compounds and derivatives ("ABC boy", "African-born", "ˈrumpling") printed as lemma + part of
speech (+ quotations), whose meaning is given collectively by the group heading in the parent
entry's Compounds/Derivatives section. Such a sub-entry record without a definition is
stub "popup" with part_of = the parent entry named by its div.ref link (its quotations are
kept); without that link (or with a link to the record itself) it is stub "derivative" (lemma + pos + quotations, "MacˈGyvered")
or, with nothing at all, "empty". Main entries are never stubbed: the
few without a definition (quotation-only obsolete words, etymology-only entries) count as
uncovered. Full run: 575,916 records, 81,643 stubs (popup 81,466, derivative 175, empty 2),
coverage 0.9985 of the 494,273 content records.

Left in layer 1: frequency bands, the Origin summary, editorial notes, the date range line,
pronunciations of lemmas other than the record's own, cross-reference link targets and
publication notes. A sub-entry record takes its prons from the h3 of its own lemma.
"""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import replace

from structured.markup import class_set, clean, cls, parse as parse_html, text
from structured.model import Entry, Example, Pron, Sense, covered
from structured.parsers._oed_preentry import _etymology, _forms, _headword, _prons, _prons_of

KEY = "oed"
COVERS = "definitions"
MIN_COVERAGE = 0.99
# "in-line": a quotation names the HTML <iframe> element it describes.
PRINTED_MARKUP = frozenset({"in-line"})

_SECTION_KINDS = {"Derivatives": "derivative", "Phrasal verbs": "phrasal_verb"}
_ROMAN_OR_CAPITAL = re.compile(r"^(?:[A-Z]|[IVXLC]+)$")
# roman words that may join italic labels: "colloquial (originally and chiefly U.S.)"
_LABEL_GLUE = frozenset("and or in now chiefly originally also often usually occasionally esp especially "
                        "freq frequently rare rarely later earlier early of with the".split())
_ORPHAN_PUNCT = re.compile(r"\s+([,;.)])")  # the space a skipped pronunciation leaves before punctuation
_CONNECTOR = re.compile(r"^[\s,;:.&]*(?:and|or)?[\s,;:.]*$")
_LEADING_DROP = ("numbering", "lemma", "lemmaInDef", "ps", "almostInvisible", "obs",
                 "pronunciation-wrapper", "sup-phonetics")
_SKIP_IN_TREE = ("preEntry", "ref", "rev", "unrev", "quotationsBlock", "quotationsBlockSibling")


def _number(pieces: list[str]) -> str:
    out = ""
    parts = [p for p in (clean(x).replace("†", "").strip().rstrip(".").strip() for x in pieces) if p]
    for i, piece in enumerate(parts):
        out += piece
        if i + 1 < len(parts) and (_ROMAN_OR_CAPITAL.match(piece) or piece[-1].isdigit() and parts[i + 1][0].isdigit()):
            out += "."
    return out


def _wrap_labels(wrap) -> list[str]:
    """The em labels a senseWrap prints before anything else ("5. intransitive."), for all its senses."""
    labels: list[str] = []
    if clean(wrap.text or ""):
        return labels
    for child in wrap:
        if not isinstance(child.tag, str):
            continue
        kinds = class_set(child)
        if kinds & {"senseGroup", "senseWrap"}:
            break
        if child.tag == "em" and not kinds:
            labels.append(text(child))
        elif not (kinds & set(_LEADING_DROP) or not text(child)):
            break
        if not _CONNECTOR.match(child.tail or ""):
            break
    return [label for label in labels if label]


def _quotation(q) -> Example | None:
    head = next(iter(q.xpath(f"./span[{cls('noIndent')}]")), None)
    date = source = ""
    quote = text(q)
    if head is not None:
        date = text(next(iter(head.xpath("./span[not(@class)]")), None))
        source = text(head)
        at = quote.find(source)  # noIndent comes first (after a "[" for a bracketed quotation)
        if source and at >= 0:
            quote = clean(quote[:at] + " " + quote[at + len(source):])
        if date and source.startswith(date):
            source = source[len(date):].strip()
    return Example(text=quote, kind="quotation", date=date, source=source) if quote else None


def _quotations(group) -> tuple[Example, ...]:
    out: list[Example] = []
    for block in group.xpath(f"./div[{cls('frame')}]/div[{cls('quotationsBlock')} or {cls('quotationsBlockSibling')}]"):
        labels = _block_labels(block)
        for q in block.xpath(f".//div[{cls('quotation')}]"):
            if (e := _quotation(q)) is not None:
                out.append(replace(e, labels=labels) if labels else e)
    return tuple(out)


def _block_labels(block) -> tuple[str, ...]:
    """What a quotation block prints before its first quotation: "figurative.", a form group "β."."""
    found = [clean(block.text or "")]
    for child in block:
        if isinstance(child.tag, str) and "quotation" in class_set(child):
            break
        if isinstance(child.tag, str):
            found.append(text(child))
        found.append(clean(child.tail or ""))
    return tuple(label for label in found if label)


class _Heading:
    """What an h3 says: its number piece, lemma, pos, labels and definition."""

    def __init__(self, h3) -> None:
        self.number = self.lemma = self.pos = ""
        self.labels: list[str] = []
        self.prons: list[Pron] = []
        self.definition = ""
        if h3 is None:
            return
        h3 = deepcopy(h3)
        for inline in h3.xpath(f"./span[{cls('subentryInline')}]"):
            inline.drop_tag()
        for el in h3.xpath(f".//span[{cls('note')}]"):
            el.drop_tree()
        ems: list[str] = []
        lemmas: list[str] = []
        if clean(h3.text or "") == "†":  # "†" printed before the number: an obsolete sense
            self.labels.append("†")
            h3.text = ""
        leading = not clean(h3.text or "")
        for child in list(h3):
            if not isinstance(child.tag, str):
                continue
            kinds = class_set(child)
            tail = child.tail or ""
            if leading and (kinds & set(_LEADING_DROP) or not text(child)):
                if "numbering" in kinds:
                    self.number = text(child)
                elif "pronunciation-wrapper" in kinds:
                    self.prons += _prons_of([child], self.prons[-1] if self.prons else None)
                elif kinds & {"lemma", "lemmaInDef"} and not self.lemma:
                    self.lemma = text(child)
                elif "ps" in kinds and not self.pos:
                    self.pos = text(child)
                if "obs" in kinds or "†" in text(child):
                    self.labels.append("†")
                if _CONNECTOR.match(tail):
                    child.tail = ""
                else:
                    leading = False  # definition text follows
                child.drop_tree()
                continue
            leading = False
            if child.tag == "em" and not kinds:
                ems.append(text(child))
            elif "lemmaInDef" in kinds:
                lemmas.append(text(child))
            elif kinds & {"pronunciation-wrapper", "sup-phonetics"}:
                child.drop_tree()
        rest = text(h3).lstrip(":;,. ")
        for _ in range(6):
            if any(e and rest.startswith(e) for e in ems):
                cut = rest.find(". ")
                if not 0 < cut <= 80:
                    break
                label = rest[:cut].strip()
                if any(e.endswith(".") and (label + ".").endswith(e) for e in ems):
                    label += "."  # the label's own abbreviation point: "U.S."
                plain = label
                for e in sorted((e for e in ems if e), key=len, reverse=True):
                    plain = plain.replace(e, "")
                if any(w.lower() not in _LABEL_GLUE for w in re.findall(r"[^\W\d_]+", plain)):
                    break  # roman words other than label glue: a definition, not a label
                if label:
                    self.labels.append(label)
                rest = rest[cut + 2:].lstrip(":;,. ")
            elif not self.lemma and any(lm and rest.startswith(lm) for lm in lemmas):
                self.lemma = next(lm for lm in lemmas if lm and rest.startswith(lm))
                rest = rest[len(self.lemma):].lstrip(":;,. ")
            else:
                break
        self.definition = _ORPHAN_PUNCT.sub(r"\1", rest)


class _Walker:
    def __init__(self, record_lemma: str, entry_pos: str) -> None:
        self.record_lemma = record_lemma
        self.entry_pos = entry_pos
        self.senses: list[Sense] = []
        self.prons: list[Pron] = []  # a sub-entry record's own pronunciations, printed in its h3
        self.pos: list[str] = []     # ... and its own parts of speech, also when the h3 defines nothing

    def walk(self, el, path: list[str], labels: list[str], section: str, phrase: str, pos: str) -> None:
        for child in el:
            if not isinstance(child.tag, str):
                continue
            kinds = class_set(child)
            if child.tag == "h1" or kinds & set(_SKIP_IN_TREE):
                continue
            if "senseWrap" in kinds and not child.xpath(f".//div[{cls('senseGroup')} or {cls('senseWrap')}]"):
                self.sense(child, path, labels, section, phrase, pos, bare=True)  # a wrap that is itself a sense
            elif "senseWrap" in kinds:
                num = text(next(iter(child.xpath(f"./span[{cls('numbering')}]")), None))
                own_labels = _wrap_labels(child)
                own_phrase = text(next(iter(child.xpath(f"./span[{cls('lemmaInDef')} or {cls('lemma')}]")), None))
                own_pos = text(next(iter(child.xpath(f"./span[{cls('ps')}]")), None))
                self.walk(child, path + [num], labels + own_labels, section, own_phrase or phrase, own_pos or pos)
            elif "senseGroup" in kinds:
                self.sense(child, path, labels, section, phrase, pos)
            elif "subentryInline" in kinds:  # a phrasal verb / sub-entry lemma heading its own senseSect
                lemma = text(next(iter(child.xpath(f"./span[{cls('lemma')}]")), None))
                dagger = ["†"] if clean(child.text or "") == "†" else []
                self.walk(child, path, labels + dagger, section, lemma or phrase, pos)
            elif "senseSect" in kinds:  # may print labels for the whole entry first: "Obsolete."
                self.walk(child, path, labels + _wrap_labels(child), section, phrase, pos)
            elif "lemSect" in kinds:
                name = text(next(iter(child.xpath(f"./h3[{cls('lemSectType')}]")), None))
                self.walk(child, [], [], name or "Other", "", "")
            elif child.tag in ("h3", "script", "link", "title", "hr"):
                continue
            else:
                self.walk(child, path, labels, section, phrase, pos)

    def sense(self, group, path: list[str], labels: list[str], section: str, phrase: str, pos: str,
              bare: bool = False) -> None:
        head = _Heading(group if bare else next(iter(group.xpath(f"./div[{cls('top')}]/h3")), None))
        examples = () if bare else _quotations(group)
        lemma = head.lemma or phrase
        if lemma and lemma == self.record_lemma:  # the record's own heading: "Balm of Gilead n." may be all of it
            self.prons += [p for p in head.prons if p not in self.prons]
            self.pos += [p for p in [head.pos] if p and p not in self.pos]
        if not (head.definition or examples):
            return
        all_labels = list(labels) + head.labels
        if section:
            kind = _SECTION_KINDS.get(section, "phrase") if lemma else "sense"
            if not lemma:
                all_labels.append(section)
        else:
            kind = "phrase" if lemma else "sense"
        if lemma and lemma == self.record_lemma:
            kind = "sense"
        if kind == "sense":
            lemma = ""
        self.senses.append(Sense(
            kind=kind, pos=head.pos or pos or (self.entry_pos if kind == "sense" else ""),
            number=_number(path + [head.number]), phrase=lemma,
            labels=tuple(dict.fromkeys(label for label in all_labels if label)),
            definition=head.definition, examples=examples))


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    blocks = root.xpath("//div[@id='mainContent']")
    for block in blocks:  # lxml nests each later homograph inside the one before: detach them
        if block.xpath("ancestor::div[@id='mainContent']"):
            block.getparent().remove(block)
    if not blocks:  # a sub-entry record
        lemma = text(next(iter(root.xpath(f"//span[{cls('hw1')}]")), None))
        walker = _Walker(lemma or clean(headword), "")
        walker.walk(root, [], [], "", "", "")
        pos = [s.pos for s in walker.senses if s.kind == "sense" and s.pos] + walker.pos
        entry = Entry(headword=lemma or clean(headword), pos=tuple(dict.fromkeys(pos)), prons=tuple(walker.prons),
                      senses=tuple(walker.senses))
        if covered(entry, COVERS):
            return entry
        parent = text(next(iter(root.xpath(f"//div[{cls('ref')}]/a[{cls('link')}]")), None))
        if parent and parent.casefold() != entry.headword.casefold():  # a link to itself names no parent
            # an undefined compound / derivative, defined as a group in its parent entry
            return replace(entry, stub="popup", part_of=parent)
        return replace(entry, stub="derivative" if entry.senses else "empty")  # no link back to a parent

    shown = homograph = ""
    pos_all: list[str] = []
    prons: list[Pron] = []
    forms: list[str] = []
    senses: list[Sense] = []
    etymologies: list[tuple[str, str]] = []
    for block in blocks:
        hw, hm, pos = _headword(block)
        if not shown and hw:
            shown, homograph = hw, hm
        pos_all += pos
        prons += [p for p in _prons(block) if p not in prons]
        forms += [f for f in _forms(block) if f not in forms]
        walker = _Walker(hw, pos[0] if len(pos) == 1 else "")
        walker.walk(block, [], [], "", "", "")
        senses += walker.senses
        if etymology := _etymology(block):
            etymologies.append((" and ".join(pos) + hm, etymology))
    if len(blocks) > 1:
        homograph = ""
    if len(etymologies) == 1:
        etymology = etymologies[0][1]
    else:
        etymology = clean(" ".join(f"({label}) {e}" if label else e for label, e in etymologies))
    return Entry(headword=shown or clean(headword), homograph=homograph, pos=tuple(dict.fromkeys(pos_all)),
                 prons=tuple(prons), senses=tuple(senses), etymology=etymology, forms=tuple(forms))
