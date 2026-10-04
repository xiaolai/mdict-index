"""Longman Pronunciation Dictionary, 3rd edition (LPD3).

No class names: the structure is carried by tags, font colours and <br> lines.
Custom container tags (<m2> around preference polls, stray tags named after
words) are flattened; the atoms read are:

  a line starting with <b>          a headword line; "garag|e": | marks the stem.
                                    Several (after <!--Roman-->I, II comments)
                                    when the word has pronunciation sections
  <i> right after that <b>          "noun, verb", "trademark", "strong form"...:
                                    kept as pos only when every part is a pos word
  <font color=green>BrE|AmE</font>  followed by <a href="sound://uk_…|us_…">
                                    <img src="UK.png|US.png">: the audio for
                                    that region; followed by a mediumblue font:
                                    the region of the transcriptions after it
  <font color=mediumblue>           a transcription; the first one on the line is
                                    BrE (LPD: it also stands for AmE when no AmE
                                    one is given); <i>/<sup> inside mark optional
                                    sounds and are kept as printed
  bare text after a transcription   variants "ˈiːð-, ɡə ˈrɑːʒ"; <font>§</font>
                                    marks non-RP BrE variants (kept)
  connector <i>                     ", weak forms", "or", ", (ii)" (a second
                                    alternative, which starts BrE again): more
                                    transcriptions follow, qualified by it
  other <i> notes / green labels    commentary (polls, "(*)"): nothing after
                                    them on the line is read, except audio links;
                                    a "—French" label reads the one bracketed
                                    foreign transcription after it first
  a later <b> on the line           a compound or example word: reading stops
  ▷ <b>form</b> <font>…</font>      inflected forms ("corral|led" -> corralled);
                                    when the headword line has no transcription
                                    ("ate  past of", "Teflon trademark,") the
                                    next ▷ line carries the headword's own, and
                                    its <b> is a base word, not a form, after "of"
  ▶ <b>compound</b>                 compounds with stress marks: not read
  line starting with <i> or ▶ <i>   "with stress-neutral suffix ¦fəʊt əʊ": how a
                                    combining form is said; read only when the
                                    headword line has no transcription

Prons: per region, the main transcription carries the region's audio; complete
variants follow without audio. Pron.note is the printed qualifier: the italic
before the first transcription unless it is a pos ("strong form", "family name
(i)", "with stress-neutral suffix"), a connector after it (", weak forms",
"(ii)"), "§" on the variant it marks, and the language of a foreign form
("—French [bal mæ̃]" -> region "", note "French"). ▶ lines are read only when
the compound is the headword itself ("spending money" / "▶ ˈspending ˌmoney"
with its audio). Partial variants ("-ˈræl", "kɒ-"), stress patterns ("ˈ•••"),
homophone notes "(= thane)" and "!!"-flagged non-standard forms stay in layer
1, as do the polls and notes. There are no senses: the dictionary covers
pronunciation.

Stubs, from markup: no transcription font and no audio link anywhere, and an
italic "—see" / "listed alphabetically as if written" -> "xref". The one
record that is the conversion's about page (":about", an HTML document
with no headword line) is left unmarked: no stub reason fits it.
"""
from __future__ import annotations

import re

from structured.markup import clean, parse as parse_html, strip_slashes, text
from structured.model import Entry, Pron

KEY = "lpd"
COVERS = "pronunciation"
MIN_COVERAGE = 0.99  # policy min(0.99, measured): 67,318 of 67,319 content records (730 xref stubs)

_ATOMS = frozenset({"b", "i", "font", "a", "img", "sup", "sub", "br"})
_POS_WORDS = frozenset({"noun", "verb", "adjective", "adverb", "preposition", "conjunction", "pronoun",
                        "interjection", "determiner", "prefix", "suffix", "combining form", "noun pl"})
_SPLIT = re.compile(r"[,;]")
_ALTERNATIVE = re.compile(r"^\((i|ii|iii|iv|v)\)$")
_CONNECTORS = frozenset({"or", "in", "is", "to", "as"})  # italic words as short as an optional sound
_HOMOPHONE = re.compile(r"\(=[^()]*\)")  # "θeɪn (= thane)": a homophone note


def _flat(root) -> list:
    """Top-level nodes in document order: atoms (elements) and strings; containers are opened."""
    out: list = []

    def walk(el) -> None:
        if el.text:
            out.append(el.text)
        for child in el:
            if not isinstance(child.tag, str):
                pass
            elif child.tag in _ATOMS:
                out.append(child)
            else:
                walk(child)
            if child.tail:
                out.append(child.tail)

    walk(root)
    return out


def _lines(nodes: list) -> list[list]:
    lines: list[list] = [[]]
    for node in nodes:
        if not isinstance(node, str) and node.tag == "br":
            lines.append([])
        else:
            lines[-1].append(node)
    return [line for line in lines if line]


def _color(el) -> str:
    return (el.get("color") or "").strip().lower() if el.tag == "font" else ""


def _audio_region(a) -> str:
    img = " ".join(a.xpath(".//img/@src")).upper()
    href = a.get("href") or ""
    if "US.PNG" in img or href.startswith("sound://us_"):
        return "us"
    if "UK.PNG" in img or href.startswith("sound://uk_"):
        return "uk"
    return ""


def _usable(variant: str) -> bool:
    return bool(variant) and not (variant.startswith(("-", "!!", "+")) or variant.endswith(("-", "+"))
                                  or "•" in variant or "..." in variant or "=" in variant)


class _Line:
    """Reads the transcriptions (with their printed qualifiers) and audio of one headword line."""

    def __init__(self) -> None:
        self.ipas: dict[str, list[tuple[str, str]]] = {"uk": [], "us": [], "": []}  # "": foreign forms
        self.audio: dict[str, str] = {"uk": "", "us": ""}
        self.pos: list[str] = []
        self.lead = ""  # the first italic note ("past of", "trademark,")

    def _put(self, region: str, ipa: str, note: str) -> None:
        if (ipa, note) not in self.ipas[region]:  # the same sounds under another qualifier are said again
            self.ipas[region].append((ipa, note))

    def read(self, line: list) -> None:
        region, stopped, collecting = "uk", False, False
        note, mark, foreign = "", "", ""  # current qualifier; "§" for the next variant; "—French" pending
        buffer: list[str] = []
        seen_ipa = False

        def flush() -> None:
            nonlocal mark
            for part in _SPLIT.split(_HOMOPHONE.sub("", clean("".join(buffer)))):
                variant = strip_slashes(part)
                if _usable(variant):
                    self._put(region, variant, mark or note)
                if variant:
                    mark = ""
            buffer.clear()

        for i, node in enumerate(line):
            if isinstance(node, str):
                if collecting and not stopped:
                    buffer.append(node)
                continue
            tag, color = node.tag, _color(node)
            if tag == "b":
                if seen_ipa:
                    break  # a compound or example word: its own pronunciation follows
                continue  # "aka —see <b>also known as</b>; sometimes said aloud as ...": a reference
            if tag == "a" and (node.get("href") or "").startswith("sound://"):
                where = _audio_region(node) or region
                if where in self.audio and not self.audio[where]:
                    self.audio[where] = node.get("href")
            elif color == "green":
                label = text(node)
                if label in ("BrE", "AmE"):
                    if not self._labels_audio(line, i):
                        flush()
                        region, collecting = ("uk" if label == "BrE" else "us"), False
                elif label == "§":
                    flush()
                    mark = "§"  # the variant after it is a non-RP British one
                else:
                    flush()
                    collecting = False
                    if not stopped and label.startswith("—"):
                        foreign = label.lstrip("—").strip()  # "—French [bal mæ̃]": the source-language form
                    else:
                        stopped = True
            elif color == "mediumblue":
                flush()
                if foreign:
                    for part in _SPLIT.split(text(node)):
                        if strip_slashes(part):
                            self._put("", strip_slashes(part), foreign)
                    foreign, stopped = "", True
                elif not stopped:
                    for part in _SPLIT.split(text(node)):
                        ipa = strip_slashes(part)
                        known = self.ipas[region]
                        # the first transcription of a region is its main one, partial or not
                        if ipa and not ipa.startswith("!!") and (not known or _usable(ipa)):
                            self._put(region, ipa, mark or note)
                            mark = ""
                    collecting, seen_ipa = True, True
            elif tag in ("sup", "sub") or (tag == "i" and _inline(node)):
                if collecting and not stopped:
                    buffer.append(node.text_content())
            elif tag == "i":
                value = text(node)
                bare = value.strip(" ,;")
                self.lead = self.lead or bare
                flush()
                if not seen_ipa:
                    parts = [clean(p).rstrip(".") for p in value.split(",") if clean(p)]
                    if parts and all(p in _POS_WORDS for p in parts):
                        self.pos = self.pos or parts
                    elif bare:
                        note = bare.lstrip("—").strip()  # "strong form", "family name (i)", "trademark"
                    continue
                if _ALTERNATIVE.match(bare):
                    region, collecting, note = "uk", False, bare  # "(i) rəʊf AmE roʊf, (ii) rɒlf"
                elif "weak form" in value or "strong form" in value:
                    collecting, note = False, bare  # "ænd, weak forms ənd, ən"
                elif bare in ("", "or"):
                    collecting = False  # "ˈæk ə or ˌeɪ keɪ ˈeɪ": more follow
                else:
                    stopped, collecting = True, False
        flush()

    @staticmethod
    def _labels_audio(line: list, i: int) -> bool:
        """Whether the green label at line[i] names the audio link right after it."""
        for node in line[i + 1:]:
            if isinstance(node, str):
                if node.strip():
                    return False
                continue
            return node.tag == "a" and (node.get("href") or "").startswith("sound://")
        return False


def _inline(i_el) -> bool:
    """<i>ə</i> inside a transcription (an optional sound), as opposed to an italic note."""
    value = i_el.text_content()
    return 0 < len(value.strip()) <= 2 and " " not in value and "(" not in value and value not in _CONNECTORS


_ROMAN = re.compile(r"^[IVX]+$")
_STRESS = re.compile(r"[ˈˌ]")
_BASE_NOTE = re.compile(r"(\bof|^from)$")  # "past of", "plural of", "from": the ▷ word is a base, not a form


def _first_element(nodes: list):
    return next((n for n in nodes if not isinstance(n, str) or n.strip()), None)


def _kind(line: list) -> tuple[str, object]:
    """("headword" | "form" | "combining" | "", lead element) for a line."""
    for node in line:
        if isinstance(node, str):
            value = node.strip()
            if not value or _ROMAN.match(value):  # "<!--Roman-->II<!--/Roman-->" section numbers
                continue
            if value.startswith(("▷", "▶")):
                lead = _first_element(line[line.index(node) + 1:])
                if isinstance(lead, str) or lead is None:
                    return "", None
                if value.startswith("▷"):
                    # "▷ <i> — </i><b>likin'</b>": an example word, not a form
                    return ("form", lead) if lead.tag == "b" else ("", None)
                if lead.tag == "b":
                    return "compound", lead
                return ("combining", lead) if lead.tag == "i" else ("", None)
            return "", None
        if node.tag == "b":
            return "headword", node
        if node.tag == "i":  # "<m2><i> with stress-neutral suffix</i> ¦fəʊt əʊ": a combining-form line
            return "combining", node
        return "", None
    return "", None


def _form_list(value: str) -> list[str]:
    """ "aah'd, aahed" -> each form; "~x" abbreviates a form the line does not spell out, and is left."""
    return [form for form in (clean(v) for v in value.split(",")) if form and "~" not in form]


def _add(prons: list[Pron], reader: _Line) -> None:
    for region in ("uk", "us", ""):
        found = reader.ipas[region]
        if region == "us" and not found:
            found = reader.ipas["uk"][:1]  # LPD: one transcription serves both unless AmE is given
        audio = reader.audio.get(region, "")
        for n, (ipa, note) in enumerate(found):
            pron = Pron(ipa=ipa, region=region, audio=audio if n == 0 else "", note=note)
            if pron not in prons:
                prons.append(pron)
        if not found and audio and Pron(ipa="", region=region, audio=audio) not in prons:
            prons.append(Pron(ipa="", region=region, audio=audio))


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    shown, forms, pos = "", [], []
    prons: list[Pron] = []
    combining: list[_Line] = []
    pending: _Line | None = None  # a headword line without transcription: the next ▷ line carries it
    for line in _lines(_flat(root)):
        kind, lead = _kind(line)
        if kind == "form":
            value = text(lead).replace("|", "")
            reader = _Line()
            if pending is not None:
                # "ate  past of / ▷ eat et eɪt", "Teflon trademark / ▷ t~ ˈtef lɒn": the headword's own
                reader.read(line[line.index(lead) + 1:])
                _add(prons, reader)
                if not _BASE_NOTE.search(pending.lead):
                    forms += _form_list(value)
                if any(reader.ipas.values()):
                    pending = None
            elif value:
                forms += _form_list(value)
            continue
        pending = None
        if kind == "compound" and shown and clean(_STRESS.sub("", text(lead))) == shown:
            # "spending money" / "▶ ˈspending ˌmoney BrE <a> AmE <a>": the headword's own stress line
            reader = _Line()
            reader.read(line[line.index(lead) + 1:])
            _add(prons, reader)
        elif kind == "combining":
            # "▶ with stress-neutral suffix ¦æk rəʊ": how a combining form is said; read only if the
            # headword line itself has no transcription
            reader = _Line()
            reader.read(line[line.index(lead):])
            combining.append(reader)
        elif kind == "headword":
            names = [clean(n) for n in text(lead).replace("|", "").split(",")]
            if not shown and names[0]:
                shown = names[0]
                forms += [n for n in names[1:] if n and "~" not in n]
            reader = _Line()
            reader.read(line[line.index(lead) + 1:])
            pos += [p for p in reader.pos if p not in pos]
            _add(prons, reader)
            if not any(reader.ipas.values()):
                pending = reader
    if not any(p.ipa for p in prons):
        for reader in combining:
            _add(prons, reader)
    shown = shown or clean(headword)
    return Entry(headword=shown, pos=tuple(pos), prons=tuple(prons),
                 forms=tuple(f for f in dict.fromkeys(forms) if f and f != shown), stub=_stub(root))


_SEE = re.compile(r"(^|[—\s-])see\b|listed alphabetically as if")


def _stub(root) -> str:
    """"abutt…  —see ↑<<abut>>", "M'…  in this dictionary listed alphabetically as if written ▷ Mac…":
    a record with no transcription font and no audio that points elsewhere is a cross-reference."""
    if root.xpath("//font[translate(@color, 'MEDIUMBLUE', 'mediumblue')='mediumblue']") \
            or root.xpath("//a[starts-with(@href, 'sound://')]"):
        return ""
    notes = " ".join(text(i) for i in root.xpath("//i"))
    return "xref" if _SEE.search(notes) else ""
