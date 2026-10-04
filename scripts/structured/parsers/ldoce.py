"""Longman Dictionary of Contemporary English, 6th edition (LDOCE6).

One MDict record holds every homograph of a word, each a top-level
span.entry (id "take_1", "take_2"); several homographs leave Entry.homograph
empty and each Sense carries its own pos: its head's, all of them when the head prints several
("determiner, pronoun, adverb"). The head's labels (span.gram|geo|registerlab: "[transitive]",
"[only before noun]") are inherited by its ordinary senses; a phrase (span.lexunit) does not take
the grammar ones, which describe the headword.

Structure of a top-level span.entry:
  entryhead: span.hwd, span.homnum, span.pos (", noun" for a second pos),
             proncodes > span.pron (+ span.amevarpron "$ -ˈloʊ" = the US variant),
             a[href^="sound://hwd/bre"] (uk audio), a[href^="sound://hwd/ame"] (us audio),
             span.inflections > span.pasttense|pastpart|pluralform|... (label in
             span.infllab / span.italic), span.variant|amevariant|brevariant > span.orthvar|lexvar
  senses:    span.sense > span.sensenum, span.lexunit (a phrase), span.gram|geo|registerlab,
             span.def, span.example (also inside span.gramexa / span.colloexa);
             span.subsense > span.sensenum "a)" + its own def / examples
  phrasal verbs: span.phrvbentry > span.phrvbhwd (+ object) and its own span.sense list
  derivatives:   span.runon > span.deriv "—abandonment", span.pos, span.gram, optional def/examples
  side boxes (never senses): span.thesbox, grambox, usagebox, collobox, f2nbox, errorbox,
             thescollobox, span.hint; span.tail holds them next to the run-ons.

Popups. LDOCE6 stores each popup as its own record keyed "@<kind>_<word>[_<homnum>]"
(95k of the 148k records), the key spelling the word with every non-alphanumeric
character as "_". Each is a stub:
  stub "popup", part_of = the entry's word, headword = the same word:
    @etymologies_  span.etymsense               -> etymology
    @verbs_        div.verbtable span.verb_form -> forms
    @examples_     ul.exas > li (EXAMPLES FROM OTHER DICTIONARIES / FROM THE CORPUS)
                   -> one unnumbered, definition-less Sense (the example bank)
    @collocations_, @phrases_ (corpus examples per phrase), @entrymenu_, @thesaurus_m_<word>
                   -> nothing; their content stays in layer 1
  stub "index", headword = the key: @wordfamilies_0586, @thesaurus_ws0213 / _wsrefs2066 (word sets),
    @thesaurus_a4996 (Activator sections): numbered pages shared by many entries.
part_of is the key's word as the popup prints it: "_" matches any non-alphanumeric
character in span.hyphenation / div.lemma, then in the popup's text ("able_bodied" ->
"able-bodied"); unmatched, an edge "_" is an affix hyphen ("_aholic" -> "-aholic") and
an inner one a space. A trailing "_the" is dropped ("cia_the" -> the entry "CIA") and a
curly apostrophe straightened, as in the entry keys.
Main records whose only content is span.crossref or span.relatedwd "→ wi-fi" (no span.def
outside the side boxes) are stub "xref": "vivo -> in vivo", "Ascot -> Royal Ascot", "snook -> cock a snook at cock".

Labels printed inside an example (span.geo, span.registerlab) go to Example.labels.
A qualifier between two prons (span.pronstrong "strong", "spelling pronunciation")
goes to Pron.note of the pron after it.

Shared with ldoce_ec (LDOCE6 English-Chinese), whose markup is this one plus
def > en|tran, example > exaen|example, signpost > signen|sign, and the popups
inlined as div.at-link after a span.popup-button.
"""
from __future__ import annotations

import re

from structured.markup import clean, cls, has_cjk, parse as parse_html, split_en_zh, text
from structured.model import Entry, Example, Pron, Sense

KEY = "ldoce"
COVERS = "definitions"
MIN_COVERAGE = 0.99  # min(0.99, measured content coverage 1.0 over 52,333 content records, full build)

# Containers whose content is never a sense, a definition or an example of the entry.
_BOXES = ("thesbox", "grambox", "usagebox", "collobox", "f2nbox", "errorbox", "thescollobox",
          "hint", "at-link", "entrymenu", "verbtable")
_IN_BOX = "ancestor::*[" + " or ".join(cls(b) for b in _BOXES) + "]"
_LABELS = ("gram", "geo", "registerlab")
_FORM_CLASSES = ("pasttense", "pastpart", "ptandpp", "prespart", "t3perssing", "pluralform", "comp", "superl")
_POPUP = re.compile(r"^@(etymologies|verbs|examples|collocations|thesaurus|phrases|entrymenu|wordfamilies)_(.*)$")
_HOMNUM = re.compile(r"^(.+?)_(\d+)$")
_NUMBERED_KEY = re.compile(r"(?:ws|wsrefs|a)?\d+")
_PAREN_LABEL = re.compile(r"\s*\((?:BrE|AmE)\)")


def _classes(el) -> set[str]:
    return set((el.get("class") or "").split()) if isinstance(el.tag, str) else set()


def _text_skip(el, skip_classes=(), skip_tags=()) -> str:
    """Visible text of `el` without the subtrees whose class or tag is listed."""
    if el is None:
        return ""
    parts: list[str] = []

    def walk(e) -> None:
        if isinstance(e.tag, str):
            if e.tag in skip_tags or _classes(e) & set(skip_classes):
                return
            if e.text:
                parts.append(e.text)
            for child in e:
                walk(child)
                if child.tail:
                    parts.append(child.tail)

    if isinstance(el.tag, str) and el.text:
        parts.append(el.text)
    for child in el:
        walk(child)
        if child.tail:
            parts.append(child.tail)
    return clean("".join(parts))


def _first(el, xpath: str):
    found = el.xpath(xpath)
    return found[0] if found else None


def _en_zh(el, en_tag: str, zh_tag: str, skip=()) -> tuple[str, str]:
    """English and Chinese halves of a def or example; the tags only exist in LDOCE6 E-C."""
    en_el, zh_el = _first(el, f".//{en_tag}"), _first(el, f".//{zh_tag}")
    if en_el is not None or zh_el is not None:
        return _text_skip(en_el, skip) if en_el is not None else "", text(zh_el)
    value = _text_skip(el, skip)
    return split_en_zh(value) if has_cjk(value) else (value, "")


def _labels(sense, classes: tuple[str, ...] = _LABELS) -> list[str]:
    out = []
    for el in sense.xpath("./span[" + " or ".join(cls(c) for c in classes) + "]"):
        label = text(el).strip("[]() ,")
        if label and label not in out:
            out.append(label)
    return out


def _examples(scope, exclude_subsenses: bool, axis: str = ".//") -> tuple[Example, ...]:
    not_sub = f" and not(ancestor::*[{cls('subsense')}])" if exclude_subsenses else ""
    out = []
    for ex in scope.xpath(f"{axis}span[{cls('example')} and not({_IN_BOX}){not_sub}]"):
        en, zh = _en_zh(ex, "exaen", "example", skip=("geo", "registerlab"))
        en = en.lstrip("·").strip()
        labels = [text(x).strip("[]() ,") for x in ex.xpath(f".//span[{cls('geo')} or {cls('registerlab')}]")]
        if en or zh:
            out.append(Example(text=en, text_zh=zh, labels=tuple(dict.fromkeys(x for x in labels if x))))
    return tuple(out)


def _examples_by_subsense(sense) -> dict[int, tuple[Example, ...]]:
    """The sense's own examples by the subsense they are printed after (-1: before the first).
    LDOCE closes a subsense before its examples: "<subsense>b) def</subsense>: example example"."""
    out: dict[int, tuple[Example, ...]] = {}
    current = -1
    for child in sense:
        if "subsense" in _classes(child):
            current += 1
        elif isinstance(child.tag, str):
            out[current] = out.get(current, ()) + _examples(child, exclude_subsenses=True, axis="descendant-or-self::")
    return out


def _definition(scope) -> tuple[str, str]:
    ens, zhs = [], []
    for d in scope.xpath(f"./span[{cls('def')}]"):
        en, zh = _en_zh(d, "en", "tran")
        if en:
            ens.append(en)
        if zh:
            zhs.append(zh)
    return clean(" ".join(ens)), clean(" ".join(zhs))


def _senses_of(sense, kind: str, phrase: str, pos: str, inherited: tuple[str, ...] | list[str] = (),
               grammar: tuple[str, ...] | list[str] = ()) -> list[Sense]:
    """One span.sense -> one Sense, or one per span.subsense. `inherited` are the head's labels;
    those also in `grammar` describe the headword and are not passed on to a phrase (span.lexunit).

    A sense that only groups subsenses (no definition) gives its examples to the subsense they are
    printed after; those before the first subsense stay with the sense itself."""
    number = text(_first(sense, f"./span[{cls('sensenum')}]"))
    lexunit = text(_first(sense, f"./span[{cls('lexunit')}]"))
    if lexunit:
        phrase = lexunit
        kind = "phrase" if kind == "sense" else kind
        inherited = [x for x in inherited if x not in grammar]
    labels = list(inherited) + [x for x in _labels(sense) if x not in inherited]
    out = []
    definition, definition_zh = _definition(sense)
    subs = sense.xpath(f"./span[{cls('subsense')}]")
    own_examples = _examples(sense, exclude_subsenses=True)
    trailing: dict[int, tuple[Example, ...]] = {}
    if subs and not (definition or definition_zh):
        trailing = _examples_by_subsense(sense)
        own_examples = trailing.pop(-1, ())
    if definition or definition_zh or own_examples:
        out.append(Sense(kind=kind, pos=pos, number=number, phrase=phrase, labels=tuple(labels),
                         definition=definition, definition_zh=definition_zh, examples=own_examples))
    for sub in subs:
        letter = text(_first(sub, f"./span[{cls('sensenum')}]")).strip("()")
        d_en, d_zh = _definition(sub)
        examples = _examples(sub, exclude_subsenses=False) + trailing.get(subs.index(sub), ())
        if d_en or d_zh or examples:
            sub_labels = labels + [x for x in _labels(sub) if x not in labels]
            out.append(Sense(kind=kind, pos=pos, number=number + letter, phrase=phrase, labels=tuple(sub_labels),
                             definition=d_en, definition_zh=d_zh, examples=examples))
    return out


def _pos_list(head) -> list[str]:
    out = []
    for el in head.xpath(f"./span[{cls('pos')}]"):
        p = text(el).strip(", ")
        if p and p not in out:
            out.append(p)
    return out


def _prons(head) -> list[Pron]:
    codes = _first(head, f"./*[local-name()='proncodes' or {cls('proncodes')}]")
    uk_all: list[tuple[str, str]] = []  # (ipa, note) for each span.pron, in order
    us = ""
    if codes is not None:
        for el in codes.xpath(f"./span[{cls('pron')}]"):
            prev = el.getprevious()
            note = text(prev).strip(";, ") if prev is not None and "pronstrong" in _classes(prev) else ""
            ipa = _text_skip(el, ("neutral",)).strip("/ ")
            if ipa:
                uk_all.append((ipa, note))
        us = text(_first(codes, f".//span[{cls('amevarpron')}]")).lstrip("$ ").strip("/ ")
    uk = uk_all[0][0] if uk_all else ""
    uk_audio = next(iter(head.xpath("./a[starts-with(@href, 'sound://hwd/bre')]/@href")), "")
    us_audio = next(iter(head.xpath("./a[starts-with(@href, 'sound://hwd/ame')]/@href")), "")
    out = []
    if uk or uk_audio:
        out.append(Pron(ipa=uk, region="uk", audio=uk_audio, note=uk_all[0][1] if uk_all else ""))
    # An unmarked LDOCE pronunciation serves both varieties; "$ x" gives the American one.
    if us or us_audio or (uk and "$" not in text(codes)):
        us_ipa = us or uk
        if us_ipa or us_audio:
            out.append(Pron(ipa=us_ipa, region="us", audio=us_audio))
    out += [Pron(ipa=ipa, region="uk", note=note) for ipa, note in uk_all[1:]]
    return out


def _forms(head) -> list[str]:
    out = []
    infl = " or ".join(cls(c) for c in _FORM_CLASSES)
    for el in head.xpath(f".//span[{cls('inflections')}]/span[{infl}]"):
        out.append(_text_skip(el, ("infllab", "italic", "neutral"), ("proncodes",)))
    for el in head.xpath(f"./span[{cls('variant')} or {cls('amevariant')} or {cls('brevariant')}]"
                         f"/span[{cls('orthvar')} or {cls('lexvar')}]"):
        out += [v.strip() for v in text(el).split(",")]
    return [f.strip(" ,()") for f in out if f.strip(" ,()")]


def _verb_table(scope) -> list[str]:
    return [text(v) for v in scope.xpath(f".//span[{cls('verb_form')}]")]


def _etymology(scope) -> str:
    return clean(" ".join(text(e) for e in scope.xpath(f".//span[{cls('etymsense')}]")))


def _example_bank(scope) -> tuple[Example, ...]:
    out = []
    for li in scope.xpath(f".//ul[{cls('exas')}]/li"):
        en, zh = split_en_zh(text(li)) if has_cjk(text(li)) else (text(li), "")
        if en or zh:
            out.append(Example(text=en, text_zh=zh))
    return tuple(out)


def _popup_kind(link) -> str:
    """Kind of an inlined popup (LDOCE6 E-C div.at-link), from its header class."""
    header = _first(link, f".//*[{cls('popheader')}]")
    classes = _classes(header) if header is not None else set()
    for kind, klass in (("etymologies", "popetym"), ("examples", "popexa")):
        if klass in classes:
            return kind
    return "verbs" if link.xpath(f".//*[{cls('verbtable')}]") else ""


def _homograph_entries(root) -> list:
    return root.xpath(f"//span[{cls('entry')}][span[{cls('entryhead')}]][not({_IN_BOX})]")


def _owner(el, entries) -> int:
    """Index of the top-level entry that contains `el`."""
    for anc in el.iterancestors():
        for i, e in enumerate(entries):
            if anc is e:
                return i
    return 0


def _part_of(word: str, root) -> str:
    """The entry a popup belongs to, spelled as printed.

    The key's "_" stands for any non-alphanumeric character, so the word is looked up in
    what the popup prints: its headword (span.hyphenation, div.lemma), then its text
    ("Every able-bodied man" for able_bodied). Without a printed match a leading or trailing
    "_" is read as the hyphen of an affix ("_aholic" -> "-aholic") and any other as a space.
    """
    if not word.strip("_"):
        return ""
    if word.endswith("_the"):  # "@collocations_cia_the" belongs to "CIA" (printed "CIA, the")
        word = word[: -len("_the")]
    pattern = re.compile(r"(?<![0-9a-z])" + "[^0-9a-z]".join(re.escape(p) for p in word.lower().split("_"))
                         + r"(?![0-9a-z])", re.I)
    heads = [_PAREN_LABEL.sub("", text(el)).replace("‧", "")
             for el in root.xpath(f"//span[{cls('hyphenation')}] | //div[{cls('lemma')}]")]
    for candidate in heads:
        m = pattern.search(candidate)
        if m:  # entry keys spell the apostrophe straight: "citizen’s arrest" -> "citizen's arrest"
            return clean(m.group(0).replace("’", "'"))
    # in running text a sentence may open with the word ("Swirl the wine …"): a spelling without
    # capitals is the word's own, and only a word printed with them everywhere keeps them ("CIA")
    found = [m.group(0) for m in pattern.finditer(text(root))]
    if found:
        return clean(next((f for f in found if f == f.lower()), found[0]).replace("’", "'"))
    core = word.strip("_").replace("_", " ")
    return clean(("-" if word.startswith("_") else "") + core + ("-" if word.endswith("_") else ""))


def _parse_popup(kind: str, rest: str, headword: str, root) -> Entry:
    m = _HOMNUM.match(rest)
    word, homograph = (m.group(1), m.group(2)) if m else (rest, "")
    if kind == "thesaurus" and word.startswith("m_"):
        word = word[2:]
    # Word families, word sets and Activator sections are numbered pages shared by many entries.
    if kind == "wordfamilies" or (kind == "thesaurus" and _NUMBERED_KEY.fullmatch(word)) or not word:
        return Entry(headword=headword, stub="index")
    part_of = _part_of(word, root) or headword
    base = {"headword": part_of, "homograph": homograph, "stub": "popup", "part_of": part_of}
    if kind == "etymologies":
        return Entry(**base, etymology=_etymology(root))
    if kind == "verbs":
        forms = [f for f in dict.fromkeys(_PAREN_LABEL.sub("", v).strip() for v in _verb_table(root)) if f and f != part_of]
        return Entry(**base, forms=tuple(forms))
    if kind == "examples":
        bank = _example_bank(root)
        return Entry(**base, senses=(Sense(examples=bank),) if bank else ())
    return Entry(**base)


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    given = clean(headword)
    m = _POPUP.match(given)
    if m:
        return _parse_popup(m.group(1), m.group(2), given, root)

    entries = _homograph_entries(root)
    heads = [_first(e, f"./span[{cls('entryhead')}]") for e in entries]
    shown = text(_first(heads[0], f"./span[{cls('hwd')}]")) if heads else ""
    homnums = [text(_first(h, f"./span[{cls('homnum')}]")) for h in heads]
    homograph = homnums[0] if len(heads) == 1 else ""

    pos_by_entry = [_pos_list(h) for h in heads]
    prons: list[Pron] = []
    forms: list[str] = []
    for h in heads:
        for p in _prons(h):
            if p not in prons and (p.ipa or all(p.audio != q.audio for q in prons)):
                prons.append(p)
        forms += _forms(h)

    bank_by_entry: dict[int, list[Example]] = {}
    etymologies: list[str] = []
    # Inlined popups (LDOCE6 E-C only): word origin, verb table, example bank.
    for link in root.xpath(f"//div[{cls('at-link')}]"):
        kind = _popup_kind(link)
        if kind == "etymologies":
            etymologies.append(_etymology(link))
        elif kind == "verbs":
            forms += _verb_table(link)
        elif kind == "examples":
            bank_by_entry.setdefault(_owner(link, entries), []).extend(_example_bank(link))

    # Senses and run-ons in document order, grouped by the homograph that owns them.
    by_entry: dict[int, list[Sense]] = {}
    for el in root.xpath(f"//span[{cls('sense')} or {cls('runon')}][not({_IN_BOX})]"):
        i = _owner(el, entries)
        # a head printing several parts of speech ("determiner, pronoun, adverb") shares them all
        pos = ", ".join(pos_by_entry[i]) if i < len(pos_by_entry) else ""
        out = by_entry.setdefault(i, [])
        if "runon" in _classes(el):
            deriv = text(_first(el, f".//span[{cls('deriv')}]")).lstrip("—-– ").strip()
            if deriv:
                definition, definition_zh = _definition(el)
                out.append(Sense(kind="derivative", pos=text(_first(el, f"./span[{cls('pos')}]")).strip(", "),
                                 phrase=deriv, labels=tuple(_labels(el)), definition=definition,
                                 definition_zh=definition_zh, examples=_examples(el, exclude_subsenses=False)))
            continue
        pv = _first(el, f"ancestor::span[{cls('phrvbentry')}]")
        if pv is not None:
            pv_head = _first(pv, f"./span[{cls('entryhead')}]")
            pv_head = pv if pv_head is None else pv_head
            out += _senses_of(el, "phrasal_verb", text(_first(pv_head, f".//span[{cls('phrvbhwd')}]")),
                              text(_first(pv_head, f".//span[{cls('pos')}]")), _labels(pv_head))
        else:
            head = heads[i] if i < len(heads) else None
            out += _senses_of(el, "sense", "", pos, _labels(head) if head is not None else (),
                              _labels(head, ("gram",)) if head is not None else ())
    for i, bank in bank_by_entry.items():
        if bank:
            pos = ", ".join(pos_by_entry[i]) if i < len(pos_by_entry) else ""
            by_entry.setdefault(i, []).append(Sense(pos=pos, examples=tuple(bank)))
    senses = [s for i in sorted(by_entry) for s in by_entry[i]]

    all_pos = [p for ps in pos_by_entry for p in ps]
    # A record whose senses hold only a cross-reference ("vivo -> in vivo", "→ wi-fi") is an xref
    # stub: no span.def outside the side boxes, and a span.crossref / span.relatedwd outside them.
    has_def = bool(root.xpath(f"//span[{cls('def')}][not({_IN_BOX})][normalize-space()]"))
    is_xref = not has_def and bool(root.xpath(f"//span[{cls('crossref')} or {cls('relatedwd')}][not({_IN_BOX})]"))
    shown_forms = [f for f in dict.fromkeys(forms) if f and f != shown]
    return Entry(headword=shown or given, homograph=homograph, pos=tuple(dict.fromkeys(all_pos)),
                 prons=tuple(prons), senses=tuple(senses), etymology=clean("; ".join(e for e in etymologies if e)),
                 forms=tuple(shown_forms), stub="xref" if is_xref else "")
