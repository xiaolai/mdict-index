"""Merriam-Webster's Advanced Learner's English Dictionary (MWALED, learnersdictionary.com).

A record holds one div.entry per homograph. The page prints every headword block
twice (desktop div.hw_d / div.hw_infs_d / div.hw_vars_d and mobile div.hw_m / ...);
only the desktop copies are read.
  headword: div.hw_d > span.hw_txt (sup.homograph = homograph number), span.hpron_word "/ˈteɪk/"
            (preceded by span.hpron_label_b "Brit" for a British variant; otherwise US),
            a.play_pron[@data-pron] (audio, paired with the pron whose IPA equals data-pron), span.fl (pos)
  forms:    div.hw_infs_d span.i_text (inflections), div.hw_vars_d span.v_text (variants)
  senses:   div.sblocks > div.sblock_entry > div.sblock_c > strong.sn_block_num + div.scnt >
            div.sblock_labels (labels shared by the block) + div.sense (strong.sn_letter;
            span.sgram|wsgram|sl|ssla|slb|lb labels; span.def_text, several joined " : ";
            span.isyns = a synonym used as the definition; span.un_text = usage-note-as-definition
            when there is no def_text; ul.vis > li.vi > div.vi_content = "verbal illustrations", the examples;
            a sense holding nothing but span.snote "◊ ..." is defined by that note's div.both_text)
  phrases:  div.dros > div.dro > h2.dre (the phrase) + span.gram "[phrasal verb]" + its own
            div.sblock_dro senses -> kind "phrasal_verb" or "phrase"
  run-ons:  div.uros > div.uro > h2.ure "— word" + span.fl + span.gram, div.uro_def examples -> kind "derivative";
            a record that is only a run-on (no div.hw_d) takes the run-on's span.pron_w and span.fl as its own
  side content (never senses): div.usage_par / span.snote / div.snotebox (usage notes),
            div.synpar (synonym paragraphs), div.cas ("called also"), span.dxs (cross-references),
            div.arts (pictures), the "other words" list and page chrome.

Stubs (only for a record with no definition, and only on the markup that says why):
  a bare <img> ("IMG_apron")                              -> "image"
  div.uro + a.realmainentry ("tabulation" -> TABULATE)    -> "derivative": the run-on is printed
      again inside its main entry, so it is not a popup (merging it would count it twice)
  div.cxs span.cl "British spelling of" / "past tense of" -> "variant" / "inflection"
  a.realmainentry alone ("⇒ Main Entry: FUND" for "funds"), span.dxs -> "xref": the record
      prints no relation, only the pointer, so "inflection" would be a guess
A pron label other than "Brit" is kept as Pron.note: span.hpron_label_b ("sometimes") and "or" on the pron
after it, span.hpron_label_a ("before vowel sounds", "elsewhere") on the pron before it; the sounds that
"after" names ("/əd/ after /t/ or /d/") are part of that note, not pronunciations.

Coverage (full run, 87,545 records): stubs xref 35,311, derivative 7,629, image 375,
inflection 197, variant 178; 43,855 content records, all covered, so MIN_COVERAGE = 0.99.
"""
from __future__ import annotations

from structured.markup import clean, cls, parse as parse_html, strip_slashes, text
from structured.model import Entry, Example, Pron, Sense

KEY = "mwaled"
COVERS = "definitions"
MIN_COVERAGE = 0.99

_BOXES = ("usage_par", "snote", "snotebox", "synpar", "cas", "dxs", "arts", "vis_w", "vi_more")
_NOT_IN_BOX = "not(ancestor::*[" + " or ".join(cls(b) for b in _BOXES) + "])"
_LABELS = ("sgram", "wsgram", "sl", "ssla", "slb", "lb")
_LABEL_XP = "span[" + " or ".join(cls(c) for c in _LABELS) + "]"
_EXAMPLE_BOXES = ("usage_par", "snote", "snotebox", "synpar")
_EXAMPLE_OK = "not(ancestor::*[" + " or ".join(cls(b) for b in _EXAMPLE_BOXES) + "])"


def _first(el, xpath: str):
    found = el.xpath(xpath) if el is not None else []
    return found[0] if found else None


def _cls_of(el) -> set[str]:
    return set((el.get("class") or "").split()) if isinstance(el.tag, str) else set()


def _labels(scope, xpath_prefix: str) -> list[str]:
    out = []
    for el in scope.xpath(f"{xpath_prefix}{_LABEL_XP}[{_NOT_IN_BOX}]"):
        label = text(el).strip("[]() ,")
        if label and label not in out:
            out.append(label)
    return out


def _examples(scope) -> tuple[Example, ...]:
    out = []
    for vi in scope.xpath(f".//li[{cls('vi')}][{_EXAMPLE_OK}]/div[{cls('vi_content')}]"):
        value = text(vi)
        if value:
            out.append(Example(text=value))
    return tuple(out)


def _definition(sense) -> str:
    defs = [text(d) for d in sense.xpath(f".//span[{cls('def_text')}][{_NOT_IN_BOX}]")]
    if not any(defs):
        defs = [text(s) for s in sense.xpath(f".//span[{cls('isyns')}][{_NOT_IN_BOX}]")]
    if not any(defs):
        defs = [text(u) for u in sense.xpath(f".//span[{cls('un_text')}][{_NOT_IN_BOX}]")]
    return clean(" : ".join(d for d in defs if d))


def _block_senses(sblock, kind: str, phrase: str, pos: str, inherited: tuple[str, ...] = ()) -> list[Sense]:
    body = _first(sblock, f"./div[{cls('sblock_c')}]")
    if body is None:
        return []
    num = text(_first(body, f"./strong[{cls('sn_block_num')}]"))
    block_labels = list(inherited)
    for box in body.xpath(f".//div[{cls('sblock_labels')}]"):
        block_labels += [x for x in dict.fromkeys(_labels(box, "./")) if x not in block_labels]
    out = []
    for sense in body.xpath(f".//div[{cls('sense')}]"):
        letter = text(_first(sense, f"./strong[{cls('sn_letter')}]"))
        labels = block_labels + [x for x in _labels(sense, ".//") if x not in block_labels]
        definition, examples = _definition(sense), _examples(sense)
        note = _first(sense, f"./span[{cls('snote')}]")
        if not definition and note is not None:
            # A sense whose only content is a "◊" note: the note is how the phrase is explained.
            definition = text(_first(note, f"./*[{cls('both_text')}]")).lstrip("◊ ")
            examples += tuple(Example(text=text(v)) for v in note.xpath(f".//div[{cls('vi_content')}]") if text(v))
        if definition or examples:
            out.append(Sense(kind=kind, pos=pos, number=num + letter, phrase=phrase, labels=tuple(labels),
                             definition=definition, examples=examples))
    return out


def _pron_tokens(head, word_class: str) -> list[tuple[str, str]]:
    """The pronunciation line as ("word", ipa) | ("before", label) | ("after", label) tokens, in print order.

    span.hpron_label_b is printed before the pron it qualifies ("sometimes /x/"), span.hpron_label_a after it
    ("/x/ before vowel sounds"); "Brit" and a label opening with "or" ("or", "or a prolonged") lead the next
    pron in either class, unless the "or" closes the sounds an "after" names (see _context_end).
    """
    out = []
    for el in head.xpath(f"./span[{cls(word_class)} or {cls('hpron_label_a')} or {cls('hpron_label_b')}]"):
        classes = _cls_of(el)
        if word_class in classes:
            out.append(("word", strip_slashes(text(el))))
        elif label := text(el):
            leads = "hpron_label_b" in classes or label == "Brit" or label.split()[0] == "or"  # "or a prolonged /m/"
            out.append(("before" if leads else "after", label))
    return out


def _context_end(tokens: list[tuple[str, str]], start: int) -> int:
    """Index just past the sounds that "after" (at start - 1) names: "after /p/ /t/ or /θ/" runs through
    the sound following "or"; with no "or" before the next label it is the one sound ("after /v/")."""
    for i in range(start, len(tokens)):
        kind, value = tokens[i]
        if kind != "word":
            if value == "or" and i + 1 < len(tokens) and tokens[i + 1][0] == "word":
                return i + 2
            if value.startswith("or "):  # "after /v/ or a vowel": the last alternative, in words
                return i + 1
            break
    return min(start + 1, len(tokens))


def _prons(head, word_class: str = "hpron_word") -> list[Pron]:
    anchors = head.xpath(".//a[starts-with(@href, 'sound://')]")
    used: set[int] = set()
    tokens = _pron_tokens(head, word_class)
    found: list[list] = []  # [ipa, is British, note parts]
    leading: list[str] = []
    i = 0
    while i < len(tokens):
        kind, value = tokens[i]
        i += 1
        if kind == "word":
            found.append([value, "Brit" in leading, [x for x in leading if x != "Brit"]])
            leading = []
        elif kind == "before" or not found:
            leading.append(value)
        elif value == "after":
            # "/əd/ after /t/ or /d/": the sounds name where the pron is used; they are not prons of the headword
            end = _context_end(tokens, i)
            found[-1][2] += [value] + [f"/{v}/" if k == "word" else v for k, v in tokens[i:end]]
            i = end
        else:
            found[-1][2].append(value)
    out = []
    for ipa, brit, notes in found:
        audio = ""
        for n, a in enumerate(anchors):
            if n not in used and clean(a.get("data-pron") or "") == ipa:
                used.add(n)
                audio = a.get("href") or ""
                break
        if ipa or audio:
            out.append(Pron(ipa=ipa, region="uk" if brit else "us", audio=audio, note=" ".join(notes)))
    for n, a in enumerate(anchors):
        if n not in used and a.get("href"):
            out.append(Pron(ipa="", region="us", audio=a.get("href")))
    return out


def _pointer_kind(printed: str) -> str:
    """Stub reason for a printed pointer phrase ("variant spelling of", "past tense of")."""
    words = set(printed.lower().replace(",", " ").split())
    if words & {"spelling", "spellings", "variant"}:
        return "variant"
    if words & {"past", "plural", "participle", "tense", "form", "case", "comparative", "superlative", "person"}:
        return "inflection"
    return "xref"


def _stub(root, entries) -> str:
    """Why a record without a definition carries none, read from the markup that says so."""
    if not entries and root.xpath("//img"):
        return "image"  # "IMG_apron": a bare <img>
    if root.xpath(f"//div[{cls('uro')}]") and root.xpath(f"//a[{cls('realmainentry')}]"):
        return "derivative"  # "tabulation": a run-on, printed again inside its main entry
    cl = _first(root, f"//div[{cls('cxs')}]/span[{cls('cl')}]")
    if cl is not None:
        return _pointer_kind(text(cl))  # "British spelling of color", "past tense of understand"
    if root.xpath(f"//a[{cls('realmainentry')}] | //*[{cls('dxs')}] | //div[{cls('cxs')}]"):
        return "xref"  # "⇒ Main Entry: FUND" for "funds"; "— see ..."
    return ""


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    entries = root.xpath(f"//div[{cls('entry')}]")
    shown = homograph = ""
    all_pos: list[str] = []
    prons: list[Pron] = []
    forms: list[str] = []
    senses: list[Sense] = []
    heads = 0
    for entry in entries:
        head = _first(entry, f"./div[{cls('hw_d')}]")
        pos = ""
        if head is not None:
            heads += 1
            hom = text(_first(head, f".//sup[{cls('homograph')}]"))
            word = text(_first(head, f"./span[{cls('hw_txt')}]"))
            if hom and word.startswith(hom):
                word = word[len(hom):].strip()
            if not shown:
                shown, homograph = word, hom
            pos = text(_first(head, f"./span[{cls('fl')}]"))
            if pos and pos not in all_pos:
                all_pos.append(pos)
            for p in _prons(head):
                if not any(q.ipa == p.ipa and q.region == p.region and q.note == p.note
                           and (q.audio == p.audio or not p.audio) for q in prons):
                    prons.append(p)
        forms += [text(i).strip(" ;,") for i in entry.xpath(f"./div[{cls('hw_infs_d')}]/span[{cls('i_text')}]")]
        forms += [text(v).strip(" ;,") for v in entry.xpath(f"./div[{cls('hw_vars_d')}]/span[{cls('v_text')}]")]

        for sblock in entry.xpath(f"./div[{cls('sblocks')}]/div[{cls('sblock_entry')}]"):
            senses += _block_senses(sblock, "sense", "", pos)
        for dro in entry.xpath(f".//div[{cls('dro')}]"):
            line = _first(dro, f"./div[{cls('dro_line')}]")
            phrase = text(_first(line, f"./*[{cls('dre')}]"))
            gram = text(_first(line, f"./span[{cls('gram')}]")).strip("[] ")
            kind, dro_pos = ("phrasal_verb", "phrasal verb") if gram == "phrasal verb" else ("phrase", "")
            if not phrase:
                continue
            for sblock in dro.xpath(f"./div[{cls('sblocks')}]/div[{cls('sblock')}]"):
                senses += _block_senses(sblock, kind, phrase, dro_pos, tuple(_labels(line, "./")))
        for uro in entry.xpath(f".//div[{cls('uro')}]"):
            line = _first(uro, f"./div[{cls('uro_line')}]")
            phrase = text(_first(line, f"./*[{cls('ure')}]")).lstrip("—-– ").strip()
            if not phrase:
                continue
            labels = _labels(line, "./") + [g for g in (text(x).strip("[] ") for x in line.xpath(f"./span[{cls('gram')}]")) if g]
            senses.append(Sense(kind="derivative", pos=text(_first(line, f"./span[{cls('fl')}]")),
                                phrase=phrase, labels=tuple(dict.fromkeys(labels)), examples=_examples(uro)))
            if heads == 0 and phrase == clean(headword):
                # A run-on's own record ("tabulation" -> TABULATE): its pronunciation is the headword's.
                prons += [p for p in dict.fromkeys(_prons(line, "pron_w")) if p not in prons]
                run_pos = text(_first(line, f"./span[{cls('fl')}]"))
                if run_pos and run_pos not in all_pos:
                    all_pos.append(run_pos)

    shown = shown or clean(headword)
    stub = "" if any(s.definition for s in senses) else _stub(root, entries)
    return Entry(headword=shown, homograph=homograph if heads == 1 else "", pos=tuple(all_pos),
                 prons=tuple(prons), senses=tuple(senses),
                 forms=tuple(f for f in dict.fromkeys(forms) if f and f != shown), stub=stub)
