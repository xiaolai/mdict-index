"""新世纪英汉大词典 (New Century English-Chinese Dictionary), Hujiang (沪江) build.

Each entry carries two renderings of the same dictionary, switched by tabs:

  div.dict_content_display_1  "沪江小d新世纪英汉": Hujiang's re-rendering
      head11 = headword; div.word-details-item.detail > section.detail-groups >
      dl > dt (pos, span.detail-pron) + dd (p = Chinese definition; ul > li >
      p.def-sentence-from / p.def-sentence-to = example English / Chinese, the
      English with an <a href="sound://..."> example-audio link);
      .enen = 英英释义, English definitions (dl > dt pos + dd); .inflections >
      li (span.inflections-item-attr "复数:" + a form); .phrase = 常用短语
      (phrase-items li: span|a phrase + span.phrase-def); .synant, .analyzes
  div.dict_content_display_2  "新世纪英汉": the original dictionary
      span.header (headword, trailing ¹² = homograph, sup.business ®, span.doble
      = variant headword) + span.ncecd_con, repeated per homograph; inside:
      pron; span.tense (b forms, span.plural with span.pluralor "or");
      span.class (pos, sometimes in div.class_box after span.abc 🄰);
      div.label_box / div.sense.grammar = labels for the section;
      div.sense = b.num, strong.brief_ex (English gloss), span.label,
        span.collocation "[+ time]", span.etips > span.gramm tip, span.zh
        (Chinese definition, several per sense possible), span.also (See X),
        and bare text = the phrase or pattern the sense defines ("to take sth
        to sth", "=Sudan"); a numbered div.sense holding only a pattern is
        continued by the unnumbered div.sense elements after it;
      p.ex (English + span.zh) and div.maybe_phrase (span.mphr_en + span.zh)
        follow the div.sense they belong to, as siblings;
      div.idom (span.dodo ◆) = idioms; div.also = "=X" / "See also X";
      fieldset.culture / fieldset.usage = notes; div.phr = phrasal-verb links.

Senses come from the original rendering (2) when it has any, since the Hujiang
rendering repeats the same definitions and examples without numbers, labels or
homographs; only when (2) yields nothing are (1)'s detail groups and phrases
used. English definitions from 英英释义 (a different text, not a duplicate) are
added as senses with `definition` only. Prons: (2)'s pron, else (1)'s
detail-pron; the dictionary has no headword audio. Forms: (2)'s tense/plural
plus (1)'s inflections (derived words such as "名词:" are not forms).

Mapping: brief_ex -> definition; zh -> definition_zh; label, collocation and
grammar tips -> labels; a sense with its own bare phrase is kind "phrase" with
that phrase; maybe_phrase -> Example(kind="collocation", labels = its span.label
"<英,非正式>", kept out of the text). A superscript in the header, at the end or
before a comma ("Bandaranaike¹, Chandrika"), is the homograph number. Entries without any
div.sense put their gloss elsewhere, and those forms are senses too: a
maybe_phrase or p.ex before any div.sense ("the Midas touch" 点金术), bare text
directly in ncecd_con, "=X" after a pattern-only sense ("the IMF" / "=the
International Monetary Fund"), a maybe_phrase after an unglossed div.sense
("methinks": "past tense methought", then "methinks …" 我想…). A span.header
the source left unclosed swallows the body; its children are read as body. Hujiang glosses carry trailing labels
("…<方>【农业】"), split off into labels. Left in layer 1:
example audio, synonyms/antonyms, the phrasal-verb link list, abbreviation and
symbol notes, the 常用短语 list when (2) exists (it repeats (2)'s maybe_phrase).

Stubs, from markup, for a record whose renderings hold no gloss markup (zh,
brief_ex, p.ex, maybe_phrase, notes, a div.sense or div.also with a gloss or
"=X", bare body text, Hujiang definitions): "See X" senses, See/See also or
phrasal-verb links -> "xref"; only a 词形变化 list -> "inflection"; headword,
pos, pron or labels alone -> "empty". Glossed inflection records ("ate":
"eat的过去式") are content.
"""
from __future__ import annotations

import re

from structured.markup import SUPERSCRIPT, clean, cls, has_class, parse as parse_html, strip_slashes, text
from structured.model import Entry, Pron
from structured.parsers._ncecd_hujiang import _english_senses, _hujiang_senses, _inflections
from structured.parsers._ncecd_markup import _flat, _is_header_text
from structured.parsers._ncecd_original import _EQUIVALENCE, _Original, _also_lead, _read_sense_div

KEY = "ncecd"
COVERS = "definitions"
MIN_COVERAGE = 0.99  # policy min(0.99, measured): 1.0 over 232,164 content records (119 stubs)

_HOMOGRAPH = re.compile(f"([{''.join(SUPERSCRIPT)}]+)(?=,|$)")  # "take¹", "Bandaranaike¹, Chandrika"


def _headword(header) -> tuple[str, str, list[str]]:
    """(headword, homograph, variant forms) from a span.header."""
    variants = [text(v) for v in header.xpath(f"./*[{cls('doble')}]")]
    shown = _flat(header, lambda e: e.tag == "sup" or not _is_header_text(e) or has_class(e, "doble") or has_class(e, "differ"))
    shown = clean(shown.split("<")[0])  # "hacek<<span class=doble>háček</span>/h2>": the source's broken tag
    homograph = ""
    if m := _HOMOGRAPH.search(shown):
        homograph = "".join(SUPERSCRIPT[c] for c in m.group(1))
        shown = clean(shown[: m.start()] + shown[m.end():])
    return shown, homograph, [v for v in variants if v]


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    original = next(iter(root.xpath(f"//div[{cls('dict_content_display_2')}]")), None)
    hujiang = next(iter(root.xpath(f"//div[{cls('dict_content_display_1')}]")), None)

    shown, homographs, forms = "", [], []
    reader = _Original()
    if original is not None:
        for header in original.xpath(f".//span[{cls('header')}]"):
            name, number, variants = _headword(header)
            shown = shown or name
            homographs.append(number)
            forms += variants
        for differ in original.xpath(f".//span[{cls('differ')}]"):
            forms += [f for f in (clean(re.sub(r"<[^<>]*>", "", part)) for part in text(differ).split(",")) if f]
        reader.read(original)
        forms += reader.forms

    senses, pos_list, prons = reader.senses, reader.pos_list, reader.prons
    if hujiang is not None:
        if not senses:
            senses, pos_list, hj_prons = _hujiang_senses(hujiang)
            prons = prons or hj_prons
        elif not prons:
            prons = _hujiang_senses(hujiang)[2]
        senses = senses + _english_senses(hujiang)
        forms += _inflections(hujiang)
        shown = shown or text(next(iter(hujiang.xpath(".//head11")), None))

    homograph = homographs[0] if len(homographs) == 1 else ""
    ipas = [strip_slashes(p) for p in prons]
    shown = shown or clean(headword)
    return Entry(headword=shown, homograph=homograph, pos=tuple(dict.fromkeys(p for p in pos_list if p)),
                 prons=tuple(Pron(ipa=i) for i in dict.fromkeys(ipas) if i), senses=tuple(senses),
                 forms=tuple(f for f in dict.fromkeys(forms) if f and f != shown), stub=_stub(original, hujiang))


_GLOSS_MARKUP = " or ".join(cls(c) for c in ("zh", "brief_ex", "maybe_phrase", "ex"))


def _has_gloss_markup(original, hujiang) -> bool:
    """Whether either rendering holds a gloss, example, equivalence, note or definition in its markup."""
    if original is not None:
        if original.xpath(f".//*[{_GLOSS_MARKUP}]|.//fieldset"):
            return True
        if any(_read_sense_div(div)[2].has_gloss() for div in original.xpath(f".//div[{cls('sense')}]")):
            return True  # "eat的过去式", "=Australian Capital Territory"
        if any(_EQUIVALENCE.match(_also_lead(div)) for div in original.xpath(f".//div[{cls('also')}]")):
            return True
        if any(re.search(r"\w", t) for con in original.xpath(f".//span[{cls('ncecd_con')}]") for t in con.xpath("./text()")):
            return True  # bare text in the body (a foreign motto, then its Chinese gloss)
    if hujiang is not None and hujiang.xpath(
            f".//section[{cls('detail-groups')}]//dd|.//div[{cls('enen-groups')}]//dd|.//ol[{cls('phrase-items')}]/li"):
        return True
    return False


def _stub(original, hujiang) -> str:
    """Stub reason from markup, for a record with no gloss markup in either rendering: "See X" senses,
    See/See also links or a phrasal-verb link list -> xref; only a 词形变化 list -> inflection;
    headword, pos, pron or labels alone -> empty."""
    if _has_gloss_markup(original, hujiang):
        return ""
    if original is not None and (
            original.xpath(f".//*[{cls('also')} or {cls('phr')}]|.//a[starts-with(@href, 'entry://')]")
            or any(_flat(div).startswith("See ") for div in original.xpath(f".//div[{cls('sense')}]"))):
        return "xref"
    if hujiang is not None and hujiang.xpath(f".//ul[{cls('inflections-items')}]/li"):
        return "inflection"
    return "empty"
