"""Collins English Dictionary (the collinsdictionary.com "Collins_Eng_Dict" markup).

A record holds one div.dictentry per homograph ("set" 1 and 2):
  head:   *.h2_entry > span.orth (headword) + span.homnum; div.mini_h2 holds variant
          spellings (span.orth), span.pron (type- full, type-partial) with an
          a[data-mp3] link to the recording (region read from "en_gb_" / "en_us_");
          a span.lbl inside a span.pron, or a span.lbl.type-lang just before it, is
          the Pron.note ("nautical", "Hebrew")
  body:   div.content.definitions > div.hom, one per part of speech:
            span.gramGrp.pos (or span.gramGrp > span.pos), span.gramGrp.subc ("(mainly tr)")
            and span.lbl (labels for every sense of the hom), span.form.inflected_forms >
            span.orth (inflections), then
            div.sense > span.sensenum, span.lbl / span.gramGrp.subc (labels), div.def,
                        div.cit.type-example (examples), nested div.sense ("a.", "b."),
                        or instead of div.def a span.xr / div.sense.xr ("a less common
                        word for <a>manly</a>"), kept as the definition
            div.sense.def   the sense element is itself the definition
            div.def + div.cit directly in the hom (idiom extracts: "the whole nine yards")
            div.re.type-idm idiom: span.form.type-idm (the phrase) + its own div.sense
          div.content.derivs > div.re.type-drv: span.form.type-drv > span.orth (the derived
            word, with its stress in the tail) + div.hom.gramGrp > span.pos; no definition
          div.content.etyms: the etymology after div.entry_title ("Word origin"); with several
            homographs, each one's is kept, numbered: "(1) C15: … (2) C12: …"
  Pointers are skipped: a.xr.ref alone ("set eyes on"), span.xr "See full dictionary
  entry for …", and "Also called: X" (span.lbl before span.form.type-var): X is an
  alternative name for one sense, neither a label nor a spelling of the headword.

Left in layer 1: the "Grammar-…" pages (standalone grammar essays with no dictentry),
the word-frequency band, "Explore … in the dictionary" links.

Stubs (Entry.stub, set only on records with no definition): a record whose only
sense is a bare link is "inflection" when its pos says so ("plural noun",
"past tense of verb", "comparative adjective", …; 8,400 in the full run of
185,683) and "xref" otherwise (1,638). Coverage over the 175,645 content records
is 0.9993; the 116 uncovered are the "Grammar-…" essays.

"""
from __future__ import annotations

import copy
import re
from dataclasses import replace

from structured.markup import class_set, cls, clean, parse as parse_html, strip_slashes, text
from structured.model import Entry, Example, Pron, Sense, covered

KEY = "ced"
COVERS = "definitions"
MIN_COVERAGE = 0.99  # min(0.99, measured 0.9993 over content records); 116 grammar essays uncovered

_DROP_IN_DEF = frozenset({"sensenum", "lbl", "gramGrp", "cit", "sense", "form", "punctuation", "xr"})
_REGION = re.compile(r"/en_(gb|us)_")
_INFLECTION = re.compile(r"plural|past|participle|comparative|superlative|person singular|genitive|singular noun")


def _is_also_called(lbl) -> bool:
    nxt = lbl.getnext()
    return nxt is not None and "type-var" in class_set(nxt)


def _leads_xref(lbl) -> bool:
    """ "a less common word for <a>manly</a>": the lbl is the lead of a definition, not a label."""
    nxt = lbl.getnext()
    return nxt is not None and nxt.tag == "a"


def _labels(el) -> list[str]:
    """span.lbl and span.gramGrp.subc directly under a hom or sense, without their parentheses."""
    out: list[str] = []
    for child in el.xpath(f"./span[{cls('lbl')}] | ./span[{cls('gramGrp')}][{cls('subc')}] "
                          f"| ./span[{cls('gramGrp')}]/span[{cls('subc')}]"):
        if "lbl" in class_set(child) and (_is_also_called(child) or _leads_xref(child)):
            continue
        label = text(child).strip("()[],;: ")
        if label and label not in out:
            out.append(label)
    return out


def _def_text(el) -> str:
    """Text of a div.def, or of a div.sense.def minus its structural children."""
    if "sense" not in class_set(el):
        return text(el)
    copy_ = copy.deepcopy(el)
    for child in list(copy_):
        if isinstance(child.tag, str) and class_set(child) & _DROP_IN_DEF:
            child.drop_tree()
    return text(copy_)


def _xref_definition(el) -> str:
    """ "a less common word for <a>manly</a>": a cross-reference that serves as the definition,
    with every target as printed ("short for acetate rayon, cellulose acetate")."""
    for xr in [el] if "xr" in class_set(el) else el.xpath(f"./span[{cls('xr')}]"):
        lead = text(next(iter(xr.xpath(f"./span[{cls('lbl')}]")), None))
        if lead and xr.xpath("./a") and not lead.startswith("See "):
            copy_ = copy.deepcopy(xr)
            for child in list(copy_):  # punctuation before the lead closes the text before it (". another name for")
                if "lbl" in class_set(child):
                    break
                if "punctuation" in class_set(child):
                    child.drop_tree()
            return text(copy_)
    return ""


def _examples(el) -> tuple[Example, ...]:
    return tuple(Example(text=t) for t in (text(c) for c in el.xpath(f"./div[{cls('cit')}]")) if t)


def _sense(el, kind: str, phrase: str, pos: str, inherited: list[str], prefix: str) -> list[Sense]:
    number = text(next(iter(el.xpath(f"./span[{cls('sensenum')}]")), None)).rstrip(".")
    number = prefix + number if prefix and number and not number.isdigit() else number or prefix
    labels = list(dict.fromkeys(inherited + _labels(el)))
    if "def" in class_set(el):
        definition = _def_text(el)
    else:
        definition = "; ".join(t for t in (text(d) for d in el.xpath(f"./div[{cls('def')}]")) if t)
    definition = definition or _xref_definition(el)
    examples = _examples(el)
    out: list[Sense] = []
    if definition or examples:
        out.append(Sense(kind=kind, pos=pos, number=number, phrase=phrase, labels=tuple(labels),
                         definition=definition, examples=examples))
    for sub in el.xpath(f"./div[{cls('sense')}]"):
        out += _sense(sub, kind, phrase, pos, labels, number)
    return out


def _hom(hom, forms: list[str]) -> tuple[str, list[Sense]]:
    pos = text(next(iter(hom.xpath(f"./span[{cls('pos')}] | ./span[{cls('gramGrp')}]/span[{cls('pos')}]")), None))
    labels = _labels(hom)
    for orth in hom.xpath(f"./span[{cls('inflected_forms')}]/span[{cls('orth')}]"):
        if (form := text(orth)) and form not in forms:
            forms.append(form)
    out: list[Sense] = []
    bare_defs = hom.xpath(f"./div[{cls('def')}][not({cls('sense')})]")  # div.sense.def is a sense below
    if "sense" in class_set(hom) or bare_defs:
        definition = "; ".join(t for t in (text(d) for d in bare_defs) if t) or _xref_definition(hom)
        examples = _examples(hom)
        if definition or examples:
            out.append(Sense(pos=pos, labels=tuple(labels), definition=definition, examples=examples))
    for child in hom.xpath(f"./div[{cls('sense')}] | ./div[{cls('re')}]"):
        if "re" in class_set(child):
            out += _run_on(child, labels)
        else:
            out += _sense(child, "sense", "", pos, labels, "")
    return pos, out


def _run_on(re_, inherited: list[str]) -> list[Sense]:
    """div.re: an idiom (type-idm) with senses, or a derived form (type-drv) with a pos only."""
    kind = "phrase" if "type-idm" in class_set(re_) else "derivative"
    head = next(iter(re_.xpath(f"./span[{cls('form')}]")), None)
    if head is None:
        return []
    orth = head if "orth" in class_set(head) else next(iter(head.xpath(f"./span[{cls('orth')}]")), None)
    phrase = text(orth)
    if not phrase:
        return []
    pos_path = f"./div[{cls('gramGrp')}]//span[{cls('pos')}] | ./span[{cls('gramGrp')}]/span[{cls('pos')}]"
    pos = text(next(iter(re_.xpath(pos_path)), None))
    labels = list(dict.fromkeys(inherited + _labels(re_)))
    out: list[Sense] = []
    for sense in re_.xpath(f"./div[{cls('sense')}]"):
        out += _sense(sense, kind, phrase, pos if kind == "derivative" else "", labels, "")
    if not out and kind == "derivative":
        out.append(Sense(kind=kind, pos=pos, phrase=phrase, labels=tuple(labels)))
    return out


def _prons(mini) -> list[Pron]:
    """span.pron in the head. A span.lbl inside it ("nautical", "pronounced as an alveolar
    click …"), or a language label just before it ("Hebrew"), is the pronunciation's note."""
    out: list[Pron] = []
    for span in mini.xpath(f"./span[{cls('pron')}]"):
        notes = [text(lbl) for lbl in span.xpath(f"./span[{cls('lbl')}]")]
        prev = span.getprevious()
        while prev is not None and "punctuation" in class_set(prev):
            prev = prev.getprevious()
        if prev is not None and "lbl" in class_set(prev):
            notes.insert(0, text(prev))
        copy_ = copy.deepcopy(span)
        for bad in copy_.xpath(f".//span[{cls('punctuation')} or {cls('ptr')} or {cls('lbl')}]"):
            bad.drop_tree()
        ipa = strip_slashes(text(copy_))
        audio = next(iter(span.xpath(".//a/@data-mp3")), "")
        audio = audio if audio.endswith((".mp3", ".ogg", ".wav")) else ""
        found = _REGION.search(audio)
        region = {"gb": "uk", "us": "us"}[found.group(1)] if found else ""
        note = "; ".join(n for n in notes if n)
        if not region and note in ("US", "US English"):
            region = "us"  # the label names the pronunciation's region
        if (ipa or audio) and (p := Pron(ipa=ipa, audio=audio, region=region, note=note)) not in out:
            out.append(p)
    return out


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    shown = homograph = ""
    etymologies: list[tuple[str, str]] = []  # (homograph number, etymology), one per dictentry that has one
    poses: list[str] = []
    prons: list[Pron] = []
    forms: list[str] = []
    senses: list[Sense] = []
    for entry in root.xpath(f"//div[{cls('dictentry')}]"):
        title = next(iter(entry.xpath(f".//*[{cls('h2_entry')}]")), None)
        if title is not None and not shown:
            orth = next(iter(title.xpath(f"./span[{cls('orth')}]")), None)
            shown = text(orth if orth is not None else title)
            homograph = text(next(iter(title.xpath(f"./span[{cls('homnum')}]")), None))
        for mini in entry.xpath(f".//div[{cls('mini_h2')}]"):
            prons += [p for p in _prons(mini) if p not in prons]
            forms += [f for f in (text(o) for o in mini.xpath(f"./span[{cls('orth')}]")) if f]
        for hom in entry.xpath(f".//div[{cls('definitions')}]/div[{cls('hom')}]"):
            pos, found = _hom(hom, forms)
            if pos:
                poses.append(pos)
            senses += found
        for re_ in entry.xpath(f".//div[{cls('derivs')}]//div[{cls('re')}][{cls('type-drv')}]"):
            senses += _run_on(re_, [])
        ety = next(iter(entry.xpath(f".//div[{cls('etyms')}]")), None)
        if ety is not None:
            ety = copy.deepcopy(ety)
            for title_el in ety.xpath(f".//*[{cls('entry_title')}]"):
                title_el.drop_tree()
            number = text(next(iter(title.xpath(f"./span[{cls('homnum')}]")), None)) if title is not None else ""
            if (found := (number, text(ety))) not in etymologies and found[1]:
                etymologies.append(found)
    # several homographs' etymologies: "(1) … (2) …", as in mwu
    etymology = clean(" ".join(f"({n}) {e}" if n and len(etymologies) > 1 else e for n, e in etymologies))
    shown = shown or clean(headword)
    entry = Entry(headword=shown, homograph=homograph, pos=tuple(dict.fromkeys(poses)), prons=tuple(prons),
                 senses=tuple(senses), etymology=etymology,
                 forms=tuple(dict.fromkeys(f for f in forms if f and f != shown)))
    return entry if covered(entry, COVERS) else replace(entry, stub=_stub(root, poses))


def _stub(root, poses: list[str]) -> str:
    """Why a record without definitions has none, when its markup says so; else "".
    The pointer is a bare link: "abaci  plural noun → abacus", "abetted  past tense of verb → abet"."""
    pointer = f"//div[{cls('sense')}][{cls('xr')}] | //a[{cls('xr')}] | //span[{cls('xr')}]"
    if not root.xpath(pointer):
        return ""
    return "inflection" if any(_INFLECTION.search(p) for p in poses) else "xref"
