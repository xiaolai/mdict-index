"""oed pre-entry readers: a main entry block's pronunciations (by variety), inflected forms,
etymology and headword line (headword, homograph, parts of speech)."""
from __future__ import annotations

from copy import deepcopy

from structured.markup import clean, cls, strip_slashes, text
from structured.model import Pron

_REGIONS = {"Brit.": "uk", "U.S.": "us"}


def _prons(block) -> list[Pron]:
    out = []
    for div in block.xpath(f".//div[{cls('pronunciation')}]"):
        wrappers = div.xpath(f".//div[{cls('pronunciation-wrapper')}]")
        if wrappers:
            out += _prons_of(wrappers, None)
        else:  # older entries: /span.phonetics/ straight in the div, with no variety label
            audios = div.xpath(".//a[starts-with(@href, 'sound://')]/@href")
            ipas = [strip_slashes(text(el)) for el in div.xpath(f".//span[{cls('phonetics')}]")]
            audio = audios[0] if len(ipas) == 1 and len(audios) == 1 else ""
            out += [Pron(ipa=ipa, audio=audio) for ipa in ipas if ipa]
    return out


def _prons_of(wrappers: list, previous: Pron | None) -> list[Pron]:
    """Prons of pronunciation-wrappers; an unlabelled wrapper continues the previous label."""
    out: list[Pron] = []
    region, note = (previous.region, previous.note) if previous else ("", "")
    for wrapper in wrappers:
        label = clean(wrapper.text or "")
        if label:
            region = _REGIONS.get(label, "")
            note = "" if label in _REGIONS else label  # "Scottish", "Irish English", ...
        ipa = strip_slashes(text(next(iter(wrapper.xpath(f".//span[{cls('phonetics')}]")), None)))
        audio = next(iter(wrapper.xpath(".//a[starts-with(@href, 'sound://')]/@href")), "")
        if ipa or audio:
            out.append(Pron(ipa=ipa, region=region, audio=audio, note=note))
    return out


def _forms(block) -> list[str]:
    found = block.xpath(f".//div[{cls('forms')}]/strong[position() > 1]"
                        f" | .//div[{cls('inflections')}]/em")
    return [f for f in (text(el).strip(",;. ") for el in found) if f]


def _etymology(block) -> str:
    div = next(iter(block.xpath(f".//div[{cls('etymology')}][{cls('preEntry')}]")), None)
    if div is None:
        return ""
    div = deepcopy(div)
    for el in div.xpath(f"./strong[1] | .//a[{cls('more')}]"):
        el.drop_tree()
    return text(div)


def _headword(block) -> tuple[str, str, list[str]]:
    """(headword, homograph, pos list) from a main entry's h1."""
    sect = next(iter(block.xpath(f".//h1//span[{cls('hwSect')}]")), None)
    if sect is None:
        return "", "", []
    hw = text(next(iter(sect.xpath(f"./span[{cls('hw')}]")), None))
    homograph = text(next(iter(sect.xpath(f".//sup[{cls('hm')}]")), None))
    pos = []
    for ps in sect.xpath(f"./span[{cls('ps')}]"):
        ps = deepcopy(ps)
        for hm in ps.xpath(f".//sup[{cls('hm')}]"):
            hm.drop_tree()
        if value := text(ps):
            pos.append(value)
    return hw, homograph, pos
