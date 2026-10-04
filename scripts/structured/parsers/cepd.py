"""Cambridge English Pronouncing Dictionary, 18th edition (CEPD18).

Structure:
  span.arl                  the search index (hit elements for the headword, its
                            inflections and compounds): navigation, not read
  span.di-head              span.di-title > hw ("tak|e": | marks the stem;
                            span.registered ®); span.di-info: span.pos ("n",
                            "v": CEPD splits homographs with different stress
                            into separate entries), span.var / span.capvar
                            (variant spellings), gloss "(abbrev. for …)"
  span.di-body > span.sense-block, one per pronunciation block (a place name
                            and a trademark of the same spelling get two):
    sense-head span.sense-info   soundfile > a[href=sound://…] with
                                 img[src=uk_sound.png|us_sound.png]
    span.sense-body
      span.prongrp          the headword's transcriptions: span.pron > ipa
                            (sp = superscript optional sound), separated by
                            SEP ", "; span.ussymbol "US" switches to American
                            for the rest of the group; span.comment is a
                            qualifier ("strong form", "in Kent", "occasionally")
      span.inflection       span.inf (the form) + its own prongrp (suffix only)
      span.compound / span.stress_shift   compounds with stress marks
    span.panel / span.usagenote          notes, may quote transcriptions

Prons: per block, each prongrp starts British; the first transcription of a
region carries that region's audio; later partial variants ("-ɪdʒ", "rə-") stay
in layer 1, a partial first one ("US -ɚd") is kept as printed. As in the book,
a block with no US transcription has one pronunciation for both: the British
main one is repeated as US. Forms: the inflections (CEPD lists derived words
such as "taker" among them) and di-info variants. Notes become note senses.
span.comment qualifying a group's transcriptions ("strong form", "in Kent",
"occasionally") is Pron.note up to the group's "US", and on the repeated US copy. Stubs: none (every
record has a pronunciation block). Left in layer 1: compounds, the index.
"""
from __future__ import annotations

from structured.markup import clean, cls, has_class, parse as parse_html, strip_slashes, text
from structured.model import Entry, Pron, Sense

KEY = "cepd"
COVERS = "pronunciation"
MIN_COVERAGE = 0.99  # policy min(0.99, measured): 1.0 over 60,774 content records, no stubs


def _partial(ipa: str) -> bool:
    return ipa.startswith("-") or ipa.endswith("-")


def _audio(block) -> dict[str, str]:
    out = {"uk": "", "us": ""}
    for a in block.xpath(".//soundfile//a[starts-with(@href, 'sound://')]"):
        src = " ".join(a.xpath(".//img/@src")).lower()
        region = "us" if "us_sound" in src else "uk" if "uk_sound" in src else ""
        if region and not out[region]:
            out[region] = a.get("href")
    return out


def _group(prongrp) -> dict[str, list[tuple[str, str]]]:
    """(transcription, qualifier) pairs of one prongrp by region; "US" switches region for the rest of
    the group; a span.comment ("strong form", "in Kent") qualifies the transcriptions after it, up to
    the "US" switch (it cannot be told whether it also covers the US ones, so they are left without)."""
    out: dict[str, list[tuple[str, str]]] = {"uk": [], "us": []}
    region, note = "uk", ""
    for child in prongrp:
        if not isinstance(child.tag, str):
            continue
        if has_class(child, "ussymbol"):
            region, note = "us", ""  # "occasionally: ɡəˈrɑːdʒ, US ɡəˈrɑːʒ": the comment is the British part's
        elif has_class(child, "comment"):
            note = text(child).rstrip(":： ")
        elif has_class(child, "pron"):
            ipa = strip_slashes(text(child))
            # the same transcription under another qualifier is a different statement, as in _block_prons
            if ipa and (ipa, note) not in out[region] and (not out[region] or not _partial(ipa)):
                out[region].append((ipa, note))
    return out


def _block_prons(block) -> list[Pron]:
    audio = _audio(block)
    found: dict[str, list[tuple[str, str]]] = {"uk": [], "us": []}
    for body in block.xpath(f"./*[{cls('sense-body')}]"):
        for prongrp in body.xpath(f"./*[{cls('prongrp')}]"):
            for region, pairs in _group(prongrp).items():
                found[region] += [p for p in pairs if p not in found[region]]
    if not found["us"]:
        found["us"] = found["uk"][:1]  # one transcription serves both unless a US one is given
    out = []
    for region in ("uk", "us"):
        for n, (ipa, note) in enumerate(found[region]):
            out.append(Pron(ipa=ipa, region=region, audio=audio[region] if n == 0 else "", note=note))
        if not found[region] and audio[region]:
            out.append(Pron(ipa="", region=region, audio=audio[region]))
    return out


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    head = next(iter(root.xpath(f"//*[{cls('di-head')}]")), None)
    shown, pos, forms = "", [], []
    if head is not None:
        hw = next(iter(head.xpath(f".//*[{cls('di-title')}]//hw")), None)
        if hw is not None:
            shown = clean("".join(hw.xpath(f".//text()[not(ancestor::*[{cls('registered')}])]")).replace("|", ""))
        pos = [p for p in (text(e) for e in head.xpath(f".//*[{cls('di-info')}]//*[{cls('pos')}]")) if p]
        forms += [text(v) for v in head.xpath(f".//*[{cls('di-info')}]//*[{cls('var')} or {cls('capvar')}]")]

    prons: list[Pron] = []
    senses: list[Sense] = []
    for body in root.xpath(f"//*[{cls('di-body')}]"):
        for block in body.xpath(f".//*[{cls('sense-block')}]"):
            prons += [p for p in _block_prons(block) if p not in prons]
            forms += [text(i) for i in block.xpath(f".//*[{cls('inflection')}]/*[{cls('inf')}]")]
        for note in body.xpath(f".//*[{cls('usagenote')} or {cls('panel-body')}]"):
            value = text(note)
            if value:
                senses.append(Sense(kind="note", definition=value))
    shown = shown or clean(headword)
    return Entry(headword=shown, pos=tuple(dict.fromkeys(pos)), prons=tuple(prons), senses=tuple(senses),
                 forms=tuple(f for f in dict.fromkeys(forms) if f and f != shown))
