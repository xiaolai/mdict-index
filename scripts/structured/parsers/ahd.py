"""The American Heritage Dictionary of the English Language, 5th edition.

Structure (div.results, one homograph per record):
  div.rtseg     b (headword, syllables split by "·"; sup = homograph number),
                the respelling group "(…)" splits at ";" into Prons; an italic phrase or
                capitalised word in it is the Pron.note ("frəm <i>when unstressed</i>",
                "<i>British</i> därˈbē"), while a lower-case one-word italic ("<i>th</i>")
                is a respelling symbol and stays in the ipa,
                further b = variant spellings ("thru·way also through·way"),
                a.sound[href] followed by the respelled pronunciation "(…)",
                span.subject and capitalised italics outside the group are entry labels
                ("Informal", "Computers"), inherited by every ordinary sense
  div.pseg      one part of speech: leading i (pos: "n.", "v.", "tr.", "& adj."; other
                italic heads such as "Informal" or "(used with a sing. verb)" are labels;
                an i directly before b, like "pl.", introduces inflections), b
                (inflections), span.subject (labels), then the definitions:
                div.ds-list (b "1." + text) with optional div.sds-list (b "a."), or
                div.ds-single. Inside a definition, italic text after a colon is an
                example ("To begin or start: <i>set about solving the problem.</i>");
                an italic "(Author)." right after a quoted example is its source.
  div.idmseg    idiom: b > i (the phrase), optional i / span.subject labels, ds-*
  div.pvseg     phrasal verb, same layout
  div.runseg    run-on derivative: b (word), optional pronunciation, i (pos); no definition
  div.etyseg    etymology, in square brackets
  Idiom and phrasal-verb records ("cop out") hold a bare idmseg/pvseg plus
  div.mainentry (the pointer to the main entry). Indo-European root records
  ("Indo-European root: apo-") are a table whose first td has the root, an
  optional "Also …" line and the gloss, one per <br>; the gloss is the definition.

The respelling uses a private-use font (span.MinionNew). The glyphs of the
pronunciation key are mapped to Unicode: \\ue01f primary stress -> ˈ (secondary
stress is printed as ′ already), \\ue013 -> o͞o, \\ue012 -> o͝o, \\ue00a -> KH.
Other private-use glyphs occur only in etymologies (reconstructed Indo-European
forms) and are left as printed. Headwords, forms and phrases lose the syllable
dots and stress marks ("hel·lo" -> "hello").

Coverage: every one of the 97,733 records yields a definition (1.0); no stubs.

Left in layer 1: div.syntx (synonym paragraphs), div.usen (usage notes),
div.wrdhst (word histories), div.notx / div.anttx, pictures (a.arts,
div.figure, div.scp), div.tableseg (tables), span.seesynonym pointers.
"""
from __future__ import annotations

import copy
import re

from structured.markup import class_set, cls, clean, parse as parse_html, text
from structured.model import Entry, Example, Pron, Sense

KEY = "ahd"
COVERS = "definitions"
MIN_COVERAGE = 0.99  # min(0.99, measured 1.0: 97,733 of 97,733)

_GLYPHS = str.maketrans({"\ue01f": "ˈ", "\ue013": "o͞o", "\ue012": "o͝o", "\ue00a": "KH"})
_WORD_MARKS = str.maketrans("", "", "·ˈ′\ue01f")
_POS = re.compile(
    r"^[,&\s]*(?:(?:tr|intr)\.\s*(?:&\s*(?:tr|intr)\.)?\s*)?"
    r"(?:n|v|adj|adv|pl\.\s*n|n\.\s*pl|interj|prep|pron|conj|pref|suff|abbr|aux|aux\.\s*v|def\.\s*art|"
    r"indef\.\s*art|art|tr|intr|contraction|symbol)\.?(?:\s*v\.)?$", re.I)
_CLOSE_GAP = re.compile(r"\s+([.,;:!?)\]])")
_OPEN_GAP = re.compile(r"([(\[])\s+")
_NUMBER = re.compile(r"^(\d+|[a-z])\.$")
_GROUP = re.compile(r"\(([^()]*)\)")
_NOTE_OPEN, _NOTE_CLOSE = "\x01", "\x02"  # brackets around italic notes while a group is split
_NOTES = re.compile("\x01([^\x02]*)\x02")
_WORD_NOTE = re.compile("^([^\x01]*?)\x01(-[^\x02]*)\x02")
_OUTSIDE_NOTES_SEMICOLON = re.compile(";(?![^\x01]*\x02)")
_SOURCE = re.compile(r"^\((.+)\)\.?$")
_SEGMENTS = ("pseg", "idmseg", "pvseg", "runseg")


def _t(value: str) -> str:
    """Map the respelling glyphs, collapse whitespace, and close the gaps left around italic runs."""
    value = clean(value.translate(_GLYPHS))
    return _OPEN_GAP.sub(r"\1", _CLOSE_GAP.sub(r"\1", value))


def _word(el) -> str:
    """A headword, form or phrase without syllable dots and stress marks."""
    copy_ = copy.deepcopy(el)
    for sup in copy_.xpath(".//sup"):
        sup.drop_tree()
    return clean(text(copy_).translate(_WORD_MARKS))


def _is_variant(b) -> bool:
    """A later rtseg b is a variant spelling when introduced by "also" / "or" ("thru·way also
    through·way"); after a comma it is part of a name ("Bach, Johann Sebastian")."""
    prev = b.getprevious()
    before = (prev.tail if prev is not None else b.getparent().text) or ""
    return bool(re.search(r"\b(also|or)\s*$", before))


def _prons(rtseg) -> list[Pron]:
    """Each a.sound is followed by its "(respelling)"; without audio, the first group counts
    only if it uses the respelling font (so a biographical "(1564-1616)" is not taken)."""
    parts: list[str] = [""]
    audios: list[str] = [""]

    def walk(el) -> None:
        for child in el:
            if not isinstance(child.tag, str):
                pass
            elif child.tag == "a" and "sound" in class_set(child):
                parts.append("")
                audios.append(child.get("href") or "")
            elif child.tag == "b" and child.getparent() is rtseg:
                pass  # headword and variants
            elif child.tag == "i":  # italic "th" is a respelling symbol; "before a vowel", "British" are notes
                parts[-1] += f"{_NOTE_OPEN}{text(child)}{_NOTE_CLOSE}" if _is_note(text(child)) else text(child)
            else:
                parts[-1] += child.text or ""
                walk(child)
            parts[-1] += child.tail or ""

    parts[0] += rtseg.text or ""
    walk(rtseg)
    out: list[Pron] = []
    for i, (part, audio) in enumerate(zip(parts, audios, strict=True)):
        m = _GROUP.search(part)
        if i == 0 and (not m or not rtseg.xpath(f".//span[{cls('MinionNew')}]") or len(parts) > 1):
            continue
        audio = audio if audio.startswith("sound://") else ""
        for p in _variants(m.group(1) if m else "", audio):
            if p not in out:
                out.append(p)
    return out


def _is_note(italic: str) -> bool:
    """An italic in a respelling group is a qualifier unless it is a respelling symbol: those are
    single lower-case words ("th"); qualifiers are phrases or capitalised ("British")."""
    return " " in italic or italic[:1].isupper()


def _entry_labels(rtseg) -> list[str]:
    """Labels for the whole entry: span.subject, and capitalised one-word italics outside the
    respelling group ("(kăp′chə) <i>Computers</i>"); "<i>Abbr.</i>" and "(<i>British</i> …)" are not."""
    out: list[str] = []
    depth = 0  # parenthesis depth of the text read so far

    def read(value: str | None) -> None:
        nonlocal depth
        depth = max(0, depth + (value or "").count("(") - (value or "").count(")"))

    read(rtseg.text)
    for child in rtseg:
        if not isinstance(child.tag, str):
            pass
        elif child.tag == "span" and "subject" in class_set(child):
            out.append(text(child))
        elif child.tag == "i" and depth == 0 and re.fullmatch(r"[A-Z][a-z]+", text(child)):
            out.append(text(child))
        elif child.tag != "b":  # headword and variants never open a group
            read(text(child))
        read(child.tail)
    return [label for label in out if label]


def _is_sense_number(el, before: list[tuple[str, str]]) -> bool:
    """The leading b "1." / "a." of a definition (a later bold number is part of the text)."""
    return el.tag == "b" and bool(_NUMBER.match(text(el))) and not "".join(v for _, v in before).strip()


def _variants(group: str, audio: str) -> list[Pron]:
    """ "frŭm, frŏm; frəm <i>when unstressed</i>" -> Prons split at ";" (outside the italic
    notes), each with its italic qualifier as the note. The recording belongs to the first."""
    out: list[Pron] = []
    group = re.sub(";\\s*\x02", "\x02;", group)  # "<i>before a vowel;</i>" still ends a variant
    for piece in _OUTSIDE_NOTES_SEMICOLON.split(group):
        if lead := _WORD_NOTE.match(piece):  # "<i>a</i> t<i>-like sound …</i> tŭt": the note starts mid-word
            piece = f"\x01{lead.group(1)}{lead.group(2)}\x02{piece[lead.end():]}"
        notes = [_t(n).strip(" ,;") for n in _NOTES.findall(piece)]
        ipa = _t(_NOTES.sub(" ", piece)).strip(" ,;")
        note = "; ".join(n for n in notes if n)
        if ipa or (audio and not out):  # the first piece always takes the recording
            out.append(Pron(ipa=ipa, audio="" if out else audio, note=note))
    return out


def _segments(ds) -> list[tuple[str, str]]:
    """Content of a definition as (kind, text): "i" for italic runs, "t" for everything else."""
    out: list[tuple[str, str]] = []

    def walk(el) -> None:
        if el.text:
            out.append(("t", el.text))
        for child in el:
            if isinstance(child.tag, str):
                classes = class_set(child)
                if child.tag == "i":
                    out.append(("i", text(child)))
                elif child.tag == "font" or (child.tag == "span" and not classes):
                    walk(child)
                elif child.tag == "span" and "seesynonym" in classes:
                    nxt = child.getnext()
                    if nxt is not None and nxt.tag == "a":
                        nxt.set("data-skip", "1")
                elif not (child.get("data-skip") or child.tag == "div" or "subject" in classes
                          or _is_sense_number(child, out)):
                    out.append(("t", text(child)))
            if child.tail and not (child.get("data-skip") and child.tail.strip() in (".", ",", ";")):
                out.append(("t", child.tail))

    walk(copy.deepcopy(ds))
    return out


def _split_examples(value: str) -> list[str]:
    if value.startswith(("\"", "“")):
        return [value]
    return [p.strip() for p in value.split("; ") if p.strip()]


def _definition(ds) -> tuple[str, tuple[Example, ...]]:
    parts: list[str] = []
    examples: list[Example] = []
    in_examples = pointer = False
    for kind, value in _segments(ds):
        if pointer:
            continue  # "See Usage Notes at <a>escape</a>, <a>whence</a>." after the examples
        if kind == "i" and not in_examples and clean("".join(parts)).endswith(":"):
            in_examples = True
        if not in_examples:
            parts.append(value if kind == "t" else f" {value} ")
        elif kind == "i":
            source = _SOURCE.match(clean(value))
            if source and examples and not examples[-1].source:
                last = examples[-1]
                examples[-1] = Example(text=last.text, kind="quotation", source=_t(source.group(1)))
            else:
                examples += [Example(text=_t(x)) for x in _split_examples(clean(value))]
        elif clean(value).startswith("See "):
            pointer = True
        elif clean(value).strip(" ;,.()"):
            parts.append(f" {value}")
    definition = _t("".join(parts))
    if examples:
        definition = definition.rstrip(": ")
    return definition, tuple(e for e in examples if e.text)


def _labels(el) -> list[str]:
    return [t for t in (text(s) for s in el.xpath(f"./span[{cls('subject')}]")) if t]


def _senses_of(seg, kind: str, phrase: str, pos: str, labels: list[str]) -> list[Sense]:
    out: list[Sense] = []

    def add(ds, number: str, inherited: list[str]) -> None:
        own = inherited + _labels(ds)
        definition, examples = _definition(ds)
        if definition or examples:
            out.append(Sense(kind=kind, pos=pos, number=number, phrase=phrase,
                             labels=tuple(dict.fromkeys(own)), definition=definition, examples=examples))
        subs = ds.xpath(f"./div[{cls('sds-list')} or {cls('sds-single')}]")
        for sub in subs:
            letter = _NUMBER.match(text(next(iter(sub.xpath("./b")), None)))
            add(sub, number + (letter.group(1) if letter else ""), own)

    for ds in seg.xpath(f".//div[{cls('ds-list')} or {cls('ds-single')}]"):
        numbered = _NUMBER.match(text(next(iter(ds.xpath("./b")), None)))
        add(ds, numbered.group(1) if numbered and "ds-list" in class_set(ds) else "", labels)
    return out


def _pseg(seg, forms: list[str], entry_labels: list[str]) -> tuple[str, list[Sense]]:
    pos_parts: list[str] = []
    labels: list[str] = list(entry_labels)
    for child in seg:
        if not isinstance(child.tag, str):
            continue
        if child.tag == "div":
            break
        if child.tag == "i":
            value = text(child)
            nxt = child.getnext()
            if nxt is not None and nxt.tag == "b" and not _POS.match(value):
                continue  # "pl." / "also" before inflections
            if _POS.match(value):
                pos_parts.append(value)
            elif value[:1].isupper() or value.startswith("("):
                labels.append(value.strip("()"))
        elif child.tag == "b":
            if (form := _word(child)) and form not in forms:
                forms.append(form)
        elif child.tag == "span" and "subject" in class_set(child):
            labels.append(text(child))
    pos = clean(" ".join(pos_parts)).replace(" ,", ",")
    return pos, _senses_of(seg, "sense", "", pos, labels)


def _phrase_seg(seg, kind: str) -> list[Sense]:
    heads: list[str] = []
    labels: list[str] = []
    for child in seg:
        if not isinstance(child.tag, str):
            continue
        if child.tag == "div":
            break
        if child.tag == "b":
            heads.append(_word(child))
        elif child.tag == "i" and (label := text(child)):
            labels.append(label)
        elif child.tag == "span" and "subject" in class_set(child):
            labels.append(text(child))
    phrase = re.sub(r"\s+/", "/", " ".join(h for h in heads if h))
    return _senses_of(seg, kind, phrase, "", labels) if phrase else []


def _runseg(seg) -> list[Sense]:
    word = _word(next(iter(seg.xpath("./b")), None)) if seg.xpath("./b") else ""
    pos = clean(" ".join(text(i) for i in seg.xpath("./i")))
    return [Sense(kind="derivative", phrase=word, pos=pos)] if word else []


def _root(root) -> Sense | None:
    """Indo-European root appendix: root <br> [Also …] <br> gloss <br> Derivatives include …"""
    td = next(iter(root.xpath("//table//td")), None)
    if td is None:
        return None
    lines, current = [], [td.text or ""]
    for child in td:
        if child.tag == "br":
            lines.append(current)
            current = []
        elif child.tag in ("ol", "table"):
            break
        elif isinstance(child.tag, str):
            current.append(f" {text(child)} ")
        current.append(child.tail or "")
    lines.append(current)
    for line in [_t("".join(parts)) for parts in lines][1:]:
        if line and not line.startswith(("Also", "Derivatives")):
            return Sense(definition=line)
    return None


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    rtseg = next(iter(root.xpath(f"//div[{cls('rtseg')}]")), None)
    shown = homograph = ""
    forms: list[str] = []
    prons: list[Pron] = []
    entry_labels: list[str] = []
    if rtseg is not None:
        heads = rtseg.xpath("./b")
        if heads:
            shown = _word(heads[0])
            homograph = text(next(iter(heads[0].xpath("./sup")), None))
        forms += [f for f in (_word(b) for b in heads[1:] if _is_variant(b)) if f]
        prons = _prons(rtseg)
        entry_labels = _entry_labels(rtseg)

    poses: list[str] = []
    senses: list[Sense] = []
    xpath = " or ".join(cls(name) for name in _SEGMENTS)
    for seg in root.xpath(f"//div[{xpath}]"):
        classes = class_set(seg)
        if "pseg" in classes:
            pos, found = _pseg(seg, forms, entry_labels)
            if pos:
                poses.append(pos)
            senses += found
        elif "idmseg" in classes:
            senses += _phrase_seg(seg, "phrase")
        elif "pvseg" in classes:
            senses += _phrase_seg(seg, "phrasal_verb")
        else:
            senses += _runseg(seg)
    if not senses and clean(headword).startswith("Indo-European root:") and (s := _root(root)) is not None:
        senses.append(s)

    etymology = _t(text(next(iter(root.xpath(f"//div[{cls('etyseg')}]")), None))).strip("[] ")
    return Entry(headword=shown or clean(headword), homograph=homograph, pos=tuple(dict.fromkeys(poses)),
                 prons=tuple(prons), senses=tuple(senses), etymology=etymology,
                 forms=tuple(dict.fromkeys(f for f in forms if f and f != shown)))
