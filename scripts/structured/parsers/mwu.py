"""Merriam-Webster Unabridged (online, 2020 snapshot).

Structure (div.container > div.main; a page holds every homograph of its headword):
  ul.tab               homograph tabs (navigation only)
  div.tab-view > div.well.content-body   one per homograph:
    div.wrapper > div.hdword (sup = homograph number; "·" marks syllable breaks),
                  div.fl (part of speech), div.pron > span.pr ("\\ˈtāk\\"; an em inside it is a qualifier
                  that splits the pron: "\\ə, especially emphatic (¦)ā\\" -> "ə" and "(¦)ā" with that note),
                  div.audio > a.play_pron[href="sound://..."]
    div.section.inf-forms  span.in|in-more > strong   inflected forms (pronunciations inside skipped)
    div.section.variants   em.vl + strong             variant spellings
    div.section[@data-id='definition'] > div.wordclick > div > div.d
        div.d > em          labels for every sense of this d ("archaic", "Scots law")
              > div.vt      verb-type label for the senses that follow ("transitive verb")
              > div.sblk > div.snum ("1") + div.scnt > span.ssens (one sense each)
              > div.sense-block-one > div.scnt > span.ssens   (an unnumbered single sense)
              > div.r       run-on derivative: strong (the word) + em (its pos) + span.utxt > span.vi
              > div.dr      defined run-on phrase: strong (the phrase) + its own div.d
        div.d.dxnl          "see also" links: skipped
    span.ssens: em.sn ("a") + em.ssn ("(1)") number the sense; leading em / span.sgram are
          labels; strong ":" opens the definition; span.vi|vir are verbal illustrations "<...>";
          div.us is a "See Usage Discussion at" pointer (skipped).
    div.section[@data-id='origin'] .sub-well > p   etymology; "First Known Use: ..." p skipped
  Phrase pages (div.phrase.container) hold a div.dr directly in the well.

Mapping: one Sense per span.ssens, number = snum + sn + ssn as MW prints them ("1a(1)"; a
subsense without its own letter keeps the current one). definition = the ssens text without
its numbers, labels, illustrations, cross-references ("— see", "—compare"), "called also",
sense notes (span.snote), sense etymologies (span.set), variants (em.vl + strong) and
pronunciations; the leading ":" is dropped, inner " : " separators kept as printed. Examples =
span.vi|vir text without the enclosing angle brackets and without a leading
span.psl-container "(figurative)", which becomes Example.labels. Attributions stay in the
text: they are not marked up, so splitting them would be guesswork. Printed angle brackets
inside the text ("(as <or> or ≠") stay as printed. Derivatives -> kind "derivative", defined
run-ons -> kind "phrase". Several homographs' etymologies are joined as "(1) ... (2) ...".

Left in layer 1: the Related-to (synonyms), synonym discussion, artwork and first-known-use
accordions, tabs, sense notes and inflection pronunciations. A page with no definition that only
points elsewhere ("past tense of scar", "variant spelling of X", "— see X") gets that pointer in
extra["see"] ("; "-joined).

Stubs. MWU keeps a page for every inflection and variant spelling. A page with no definition
whose only content is such a pointer is a stub: "inflection" ("plural of", "past tense of",
"present participle of", "comparative of", ...), "variant" ("variant spelling of", "Scottish
variant of", "British spelling of"), or "xref" ("taxonomic synonym of X", "— see X"). Before
stubs existed the full run measured 14,246 such pages of 278,522 (13,532 "<label> of X" pages
and 714 "— see X" pages), and no other uncovered page.
The page's ad/googletag scripts are removed by the HTML helper.
"""
from __future__ import annotations

import re
from copy import deepcopy

from structured.markup import class_set, clean, cls, parse as parse_html, text
from structured.model import Entry, Example, Pron, Sense

KEY = "mwu"
COVERS = "definitions"
MIN_COVERAGE = 0.99
# "tag": an example sentence prints the HTML line-break tag it is talking about ("..., <br>").
PRINTED_MARKUP = frozenset({"tag"})

_DROP_IN_SENSE = ("vi", "vir", "dx", "us", "called-also", "snote", "set", "pr", "play_pron", "utxt")
_EXAMPLE = f"[{cls('vi')} or {cls('vir')}]"
_ORPHAN_PUNCT = re.compile(r"\s+([,;.)])")  # the space a removed illustration leaves before punctuation
_SYLLABLE = "·"
_INFLECTION = re.compile(r"\b(plural|singular|past|participle|tense|comparative|superlative) of\b|\bpast tense\b")
_VARIANT = re.compile(r"\b(variants?|spellings?)\b")  # "archaic variants of eccentric"


def _word(value: str) -> str:
    """A headword or form without MW's syllable dots; its en dash is the printed hyphen."""
    return clean(value.replace(_SYLLABLE, "").replace("–", "-"))


def _labels_and_definition(ssens) -> tuple[list[str], str]:
    """Split one span.ssens into its leading labels and its definition text."""
    copy = deepcopy(ssens)
    for el in copy.xpath(" | ".join(f".//*[{cls(k)}]" for k in _DROP_IN_SENSE)):
        if el.getparent() is not None:
            el.drop_tree()
    labels: list[str] = []
    leading = not clean(copy.text or "")
    for child in list(copy):
        if not isinstance(child.tag, str) or child.getparent() is None:
            continue
        kinds = class_set(child)
        has_tail = bool(clean(child.tail or "").strip(",;"))  # "archaic, chiefly British": still labels
        if kinds & {"sn", "ssn", "break"}:
            child.drop_tree()
        elif leading and ((child.tag == "em" and not kinds) or "sgram" in kinds):
            if label := text(child).strip("[]() ,;"):
                labels.append(label)
            child.drop_tree()
        else:
            leading = False
            if "vl" in kinds:  # "or British", "also" + the variant word(s): not definition text
                nxt = child.getnext()
                if nxt is not None and nxt.tag == "strong" and text(nxt) != ":":
                    nxt.drop_tree()
                child.drop_tree()
        if has_tail:
            leading = False
    definition = _ORPHAN_PUNCT.sub(r"\1", text(copy)).lstrip(":,; ").strip()
    return labels, definition


def _example(vi) -> Example:
    labels: tuple[str, ...] = ()
    if found := vi.xpath(f".//span[{cls('psl-container')}]"):  # "<(figurative) But only ...>"
        labels = tuple(t for t in (text(el).strip("() ") for el in found) if t)
        vi = deepcopy(vi)
        for el in vi.xpath(f".//span[{cls('psl-container')}]"):
            el.drop_tree()
    value = text(vi)
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1].strip()
    return Example(value, labels=labels)


def _senses_of_d(d, kind: str, phrase: str, pos: str, inherited: tuple[str, ...], vt: str = "") -> list[Sense]:
    """Senses of one div.d; `vt` is the verb-type label in force where a nested d starts (its own div.vt overrides it)."""
    labels_d = inherited + tuple(t for t in (text(e).strip(",; ") for e in d.xpath("./em[not(@class)]")) if t)
    out: list[Sense] = []

    def blocks(block, number: str) -> None:
        letter = ""
        for ssens in block.xpath(f"./div[{cls('scnt')}]//span[{cls('ssens')}]"):  # a stray <strong> may wrap it
            sn = text(next(iter(ssens.xpath(f"./em[{cls('sn')}]")), None))
            ssn = text(next(iter(ssens.xpath(f"./em[{cls('ssn')}]")), None))
            if sn:
                letter = sn
            own, definition = _labels_and_definition(ssens)
            examples = tuple(e for e in (_example(v) for v in ssens.xpath(f".//span{_EXAMPLE}")) if e.text)
            if not (definition or examples):
                continue
            labels = tuple(dict.fromkeys(labels_d + ((vt,) if vt else ()) + tuple(own)))
            out.append(Sense(kind=kind, pos=pos, number=number + letter + ssn, phrase=phrase, labels=labels,
                             definition=definition, examples=examples))

    for child in d:
        if not isinstance(child.tag, str):
            continue
        kinds = class_set(child)
        if "vt" in kinds:
            vt = text(child)
        elif "sblk" in kinds:
            blocks(child, text(next(iter(child.xpath(f"./div[{cls('snum')}]")), None)))
        elif "sense-block-one" in kinds:
            blocks(child, "")
        elif "r" in kinds:
            out += _derivative(child)
        elif "dr" in kinds:
            out += _run_on_phrase(child, labels_d)
        elif "d" in kinds and "dxnl" not in kinds:  # a d nested in a d
            out += _senses_of_d(child, kind, phrase, pos, labels_d, vt)
    return out


def _derivative(r) -> list[Sense]:
    word = _word(text(next(iter(r.xpath("./strong")), None)))
    pos = text(next(iter(r.xpath("./em[not(@class)]")), None)).rstrip(", ")
    examples = tuple(e for e in (_example(v) for v in r.xpath(f".//span{_EXAMPLE}")) if e.text)
    return [Sense(kind="derivative", pos=pos, phrase=word, examples=examples)] if word else []


def _run_on_phrase(dr, inherited: tuple[str, ...]) -> list[Sense]:
    phrase = _word(text(next(iter(dr.xpath("./strong")), None)))
    labels = inherited + tuple(t for t in (text(e) for e in dr.xpath("./em[not(@class)]")) if t)
    if not phrase:
        return []
    return [s for d in dr.xpath(f"./div[{cls('d')}]") for s in _senses_of_d(d, "phrase", phrase, "", labels)]


def _pron_parts(pr) -> list[tuple[str, str]]:
    """Split one printed pronunciation at its italic qualifiers: each qualifies what follows it.

    "ə, <em>especially emphatic</em> (¦)ā" -> [("ə", ""), ("(¦)ā", "especially emphatic")]. A sign printed
    straight before a qualifier is part of it ("; −<em>R</em> -mə̄" -> note "−R"); a qualifier with no
    transcription after it qualifies the last one ("also -zə <em>especially in sense 3</em>").
    """
    out: list[tuple[str, str]] = []
    ipa: list[str] = [pr.text or ""]
    note: list[str] = []

    def flush(before_qualifier: bool) -> str:
        """Close the transcription read so far; returns the sign that opens the next qualifier, if any."""
        nonlocal ipa, note
        raw = clean("".join(ipa))
        ipa = []
        # only a sign with nothing but space between it and the qualifier opens it ("fər, + <em>vowel</em>");
        # one closed off by punctuation is the transcription's own ("dis+, <em>or</em>"), and so is a final one
        sign = raw[-1] if before_qualifier and raw[-1:] in ("−", "+") else ""
        if value := clean(raw[:len(raw) - len(sign)]).strip("\\ ,;—"):
            out.append((value, " ".join(note)))
            note = []
        return sign

    for child in pr:
        if isinstance(child.tag, str) and child.tag == "em":
            sign = flush(True)
            if label := text(child):
                note.append(sign + label)
        elif isinstance(child.tag, str):
            ipa.append(child.text_content())
        ipa.append(child.tail or "")
    flush(False)
    if note and out:
        last, earlier = out[-1]
        out[-1] = (last, "; ".join(x for x in (earlier, " ".join(note)) if x))
    return out


def _add_pron(prons: list[Pron], ipa: str, audio: str, note: str = "") -> list[Pron]:
    """prons plus this one, unless it repeats one already there (homographs share pronunciations)."""
    if not (ipa or audio) or any(p.ipa == ipa and p.note == note and (p.audio == audio or not audio) for p in prons):
        return prons
    return [p for p in prons if not (p.ipa == ipa and p.note == note and not p.audio)] + [Pron(ipa=ipa, audio=audio, note=note)]


def _etymology(view) -> str:
    paras = [text(p) for p in view.xpath(f".//div[@data-id='origin']//div[{cls('sub-well')}]/p")]
    return clean(" ".join(p for p in paras if p and not p.startswith("First Known Use")))


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    shown = homograph = ""
    pos_list: list[str] = []
    prons: list[Pron] = []
    forms: list[str] = []
    senses: list[Sense] = []
    etymologies: list[tuple[str, str]] = []
    views = root.xpath(f"//div[{cls('tab-view')}]")
    for view in views:
        hdword = next(iter(view.xpath(f".//div[{cls('wrapper')}]/div[{cls('hdword')}]")), None)
        number = text(next(iter(hdword.xpath("./sup")), None)) if hdword is not None else ""
        word = _word(text(hdword).removeprefix(number))
        if not shown and word:
            shown, homograph = word, number
        pos = text(next(iter(view.xpath(f".//div[{cls('wrapper')}]/div[{cls('fl')}]")), None)).rstrip(", ")
        if pos:
            pos_list.append(pos)
        wrapper = f".//div[{cls('wrapper')}]"
        printed = [_pron_parts(p) for p in view.xpath(f"{wrapper}/div[{cls('pron')}]/span[{cls('pr')}]")]
        audios = view.xpath(f"{wrapper}/div[{cls('audio')}]//a[{cls('play_pron')}]/@href")
        for i in range(max(len(printed), len(audios))):
            # the n-th audio link is the first transcription of the n-th printed pronunciation
            parts = (printed[i] if i < len(printed) else []) or [("", "")]
            for j, (ipa, note) in enumerate(parts):
                prons = _add_pron(prons, ipa, audios[i] if j == 0 and i < len(audios) else "", note)
        for strong in view.xpath(f".//div[{cls('inf-forms')} or {cls('variants')}]//strong"):
            form = _word(text(strong))
            if form and not form.startswith("-") and form not in forms:
                forms.append(form)
        definitions = f".//div[@data-id='definition']/div[{cls('wordclick')}]/div/div[{cls('d')}][not({cls('dxnl')})]"
        for d in view.xpath(definitions):
            senses += _senses_of_d(d, "sense", "", pos, ())
        for dr in view.xpath(f"./div[{cls('well')}]/div[{cls('dr')}]"):
            senses += _run_on_phrase(dr, ())
        if etymology := _etymology(view):
            etymologies.append((number, etymology))

    if len(views) != 1:
        homograph = ""
    if len(etymologies) == 1:
        etymology = etymologies[0][1]
    else:
        etymology = clean(" ".join(f"({n}) {e}" if n else e for n, e in etymologies))
    extra, stub = {}, ""
    if not any(s.definition for s in senses) and (refs := _cross_references(root)):
        extra["see"] = refs
        stub = "inflection" if _INFLECTION.search(refs) else "variant" if _VARIANT.search(refs) else "xref"
    return Entry(headword=shown or clean(headword), homograph=homograph, pos=tuple(dict.fromkeys(pos_list)),
                 prons=tuple(prons), senses=tuple(senses), etymology=etymology, forms=tuple(forms), stub=stub,
                 extra=extra)


def _cross_references(root) -> str:
    """The printed pointer of a stub page: "past tense of scar", "see musa, jebel"."""
    found = root.xpath(f"//div[{cls('d')}][not({cls('dxnl')})]//div[{cls('scnt')}][not(span[{cls('ssens')}])]"
                       f" | //div[{cls('d')}][not({cls('dxnl')})]//span[{cls('ssens')}]/*[{cls('dx')}]")
    return "; ".join(dict.fromkeys(t for t in (text(el).lstrip("—- ") for el in found) if t))
