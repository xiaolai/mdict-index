"""Levels: how common or how advanced each word is, by every scale the dictionaries print.

    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/levels.py

The parsed layer does not keep these marks, so they are read from the raw entries in
corpus/unified.db:

    scheme          dictionary        values
    oxford3000      OALD              a1 a2 b1 b2   (the Oxford 3000, with its CEFR level)
    oxford5000      OALD              b2 c1         (the words the Oxford 5000 adds)
    opal            OALD              written spoken (the Oxford Phrasal Academic Lexicon)
    academic        OALD              yes           (OALD's academic word mark)
    cefr            OALD              a1 ... c2     (per sense: `senses` counts them)
    core            LDOCE             high medium low (Longman Communication 3000 dots)
    spoken          LDOCE             S1 S2 S3      (top 1000/2000/3000 spoken words)
    written         LDOCE             W1 W2 W3
    awl             LDOCE             yes           (the Academic Word List)
    frequency_band  COBUILD, CED      1 ... 5       (Collins frequency dots; 5 = most common)
    stars           MED               1 2 3         (Macmillan's red words)
    oed_band        OED               1 ... 8       (8 = most frequent)

Writes data/levels.db, table level(word, pos, scheme, value, dictionary, senses): one row per
word, part of speech, scheme, value and dictionary, its senses summed over the dictionary's
homographs (lead¹ n., lead² n.); an entry body met twice counts once, and so does a phrasal
verb printed again in the entry of each of its forms (get in | get into {sth}).
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import zlib
from collections import Counter
from pathlib import Path
from typing import Iterator, NamedTuple

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "inventories"), str(ROOT / "scripts")]
from inventory import DATA  # noqa: E402
from inventory.db import fresh_db  # noqa: E402
from inventory.notation import parse  # noqa: E402
from inventory.pos import normalize as read_pos  # noqa: E402

DICTIONARIES = {1: "oald", 2: "ldoce", 3: "cobuild", 5: "med", 12: "ced", 14: "oed"}  # ids in corpus/unified.db


class Level(NamedTuple):
    pos: str       # as printed; the inventory reads it into a Universal POS tag
    scheme: str
    value: str
    senses: int = 0
    word: str = ""  # a phrasal verb marked inside its verb's entry; "" for the headword


_TAG = re.compile(r"<[^>]+>")


def _text(html: str) -> str:
    return " ".join(_TAG.sub(" ", html).split())


_OALD_SUBENTRIES = re.compile(r'<span class="(?:pv-g|idm-g|idioms)"')


def oald(html: str) -> Iterator[Level]:
    """One body can hold several entries (august adj., August n.): each <h1> starts one."""
    heads = list(re.finditer(r"<h1 [^>]*>", html))
    for i, head in enumerate(heads):
        yield from _oald_entry(head.group(0), html[head.end():heads[i + 1].start() if i + 1 < len(heads) else None])


def _oald_entry(attrs: str, after: str) -> Iterator[Level]:
    head = after[:after.find("<ol")] if "<ol" in after else after
    sub = _OALD_SUBENTRIES.search(head)
    marked = bool(re.search(r"ox[35]ksym_", head[:sub.start()] if sub else head))
    levels = list(_oald_levels(attrs, after))
    if marked and not any(l.scheme.startswith("oxford") and not l.word for l in levels):
        raise ValueError("an OALD head carries an Oxford 3000/5000 mark no rule reads")
    yield from levels


def _oald_levels(attrs: str, after: str) -> Iterator[Level]:
    sub = _OALD_SUBENTRIES.search(after)
    own = after[:sub.start()] if sub else after          # the headword's part, before idioms and phrasal verbs
    top = own[:own.find("<ol")] if "<ol" in own else own  # its head, before the senses
    pos = m.group(1) if (m := re.search(r'<span class="pos"[^>]*>([^<]*)</span>', top)) else ""
    for kind, level in re.findall(r'ox([35])ksym_([abc][12])', top):
        yield Level(pos, "oxford3000" if kind == "3" else "oxford5000", level)
    for opal in ("written", "spoken"):
        if f'opal_{opal}="y"' in attrs:
            yield Level(pos, "opal", opal)
    if 'academic="y"' in attrs:
        yield Level(pos, "academic", "yes")
    for level, n in Counter(re.findall(r'<li class="sense"[^>]*\bcefr="([abc][12])"', own)).items():
        yield Level(pos, "cefr", level, n)
    yield from _oald_phrasal_verbs(after)


def _oald_phrasal_verbs(after: str) -> Iterator[Level]:
    """A phrasal verb's level is its own symbol, else the lowest its marked senses carry; each
    form it prints has it (decide on/upon {sth}: decide on {sth}, decide upon {sth})."""
    for block in re.split(r'(?=<span class="pv-g")', after)[1:]:
        if not (m := re.search(r'<span class="pv"[^>]*>(.*?)</span>', block, re.S)):
            continue
        variants = parse(_text(m.group(1))).variants
        words = [" ".join(v) for v in variants] if variants else [_text(m.group(1)).lower()]
        head = block[:block.find("<ol")] if "<ol" in block else block
        marks = re.findall(r'ox([35])ksymsub_([abc][12])', head) or re.findall(r'ox([35])ksym_([abc][12])', block)
        senses = Counter(re.findall(r'<li class="sense"[^>]*\bcefr="([abc][12])"', block))
        for word in dict.fromkeys(words):
            for kind in sorted({k for k, _ in marks}):
                level = min(lv for k, lv in marks if k == kind)
                yield Level("phrasal verb", "oxford3000" if kind == "3" else "oxford5000", level, 0, word)
            for level, n in senses.items():
                yield Level("phrasal verb", "cefr", level, n, word)


_CORE = {"High-frequency": "high", "Medium-frequency": "medium", "Lower-frequency": "low"}


def ldoce(html: str) -> Iterator[Level]:
    for part in html.split('<span class="entryhead">')[1:]:
        head = part[:part.find('class="Sense"')] if 'class="Sense"' in part else part[:4000]
        pos = m.group(1) if (m := re.search(r'<span class="pos">([^<]*)</span>', head)) else ""
        # each mark is one span: the core dots, a frequency band, the Academic Word List (whose span
        # may itself be class "freq")
        marks = len(re.findall(r'title="Core vocabulary:', head)) + len(re.findall(r'<span class="(?:freq|ac)"', head))
        read = re.findall(r'title="Core vocabulary: [\w-]+"|<span class="freq"(?![^>]*Academic)[^>]*>[SW][123]</span>|'
                          r'<span class="(?:freq|ac)"[^>]*title="Academic Word List"', head)
        if marks != len(read):  # every mark in a head is read, or the build fails
            raise ValueError(f"an LDOCE head carries a level mark no rule reads: {head[:120]!r}")
        if m := re.search(r'title="Core vocabulary: ([\w-]+)"', head):
            if m.group(1) not in _CORE:  # a tier not known here would vanish from the inventory
                raise ValueError(f"LDOCE core vocabulary tier not known: {m.group(1)!r}")
            yield Level(pos, "core", _CORE[m.group(1)])
        for band in re.findall(r'<span class="freq"[^>]*>([SW][123])</span>', head):
            yield Level(pos, "spoken" if band[0] == "S" else "written", band)
        if 'title="Academic Word List"' in head:
            yield Level(pos, "awl", "yes")


def collins(html: str) -> Iterator[Level]:
    """COBUILD and CED print one frequency for the headword: count its filled dots."""
    m = re.search(r'class="word-frequency-img"', html)
    if m:  # five dots follow, the filled ones "roundRed"
        dots = re.findall(r'class="level level\d( roundRed)?\s*"', html[m.end():m.end() + 1000])[:5]
        if len(dots) == 5 and any(dots):
            yield Level("", "frequency_band", str(sum(1 for d in dots if d)))


def med(html: str) -> Iterator[Level]:
    for stars in re.finditer(r'<div class="stars_grp">(.*?)(?=<div id="headbar")', html, re.S):
        n = stars.group(1).count('class="icon_star"')  # the group's own divs nest: count up to the headbar
        after = html[stars.end():]
        pos = _text(m.group(1)) if (m := re.search(r'<span class="PART-OF-SPEECH">(.*?)</span>\s*<', after)) else ""
        if n:
            yield Level(pos, "stars", str(n))


def oed(html: str) -> Iterator[Level]:
    for part in re.split(r'<hr class="hr_multi_keys"', html):
        band = re.search(r'class="frequencyBand(\d)"', part)
        if band:
            pos = _text(m.group(1)) if (m := re.search(r'<span class="ps">(.*?)</span>', part)) else ""
            yield Level(re.sub(r"\d", "", pos).strip(), "oed_band", band.group(1))


READERS = {"oald": oald, "ldoce": ldoce, "cobuild": collins, "ced": collins, "med": med, "oed": oed}
# What shows an entry has a level mark: an entry with one that reads as nothing is a reader's failure.
MARKERS = {"oald": re.compile(r"ox[35]ksym"), "ldoce": re.compile(r"Core vocabulary:|class=\"freq\"|Academic Word List"),
           "cobuild": re.compile(r'class="word-frequency-img"'), "ced": re.compile(r'class="word-frequency-img"'),
           "med": re.compile(r'class="stars_grp"'), "oed": re.compile(r'class="frequencyBand\d')}


def upos_of(printed: str) -> str:
    tags = read_pos(printed).tags if printed.strip() else set()
    return next(iter(tags)) if len(tags) == 1 else ""


SCHEMA = """
CREATE TABLE level (word TEXT NOT NULL, pos TEXT NOT NULL, scheme TEXT NOT NULL, value TEXT NOT NULL,
  dictionary TEXT NOT NULL, senses INTEGER NOT NULL);
CREATE INDEX level_word ON level(word);
CREATE INDEX level_scheme ON level(scheme, value);
"""


def build(entries: Iterator[tuple[str, str, str]], out: Path) -> dict:
    """entries: (dictionary, headword, html)."""
    # (word, upos, scheme, value, dictionary) -> {entry body: senses}. A headword's senses are its
    # bodies' senses, so homographs add up (in one body or in two). A phrasal verb's block is printed
    # again, under other sense ids, in the entry of each of its forms (get in | get into {sth}): its
    # blocks add up within a body, and of the bodies the one that prints most of them counts
    senses: dict[tuple, dict[bytes, int]] = {}
    seen: set[tuple[str, str, bytes]] = set()
    missed: Counter[str] = Counter()
    for dictionary, headword, html in entries:
        word = " ".join(headword.lower().split())
        body = hashlib.blake2b(html.encode(), digest_size=16).digest()
        if (dictionary, word, body) in seen:  # one entry under two keys (Glim, glim): one source
            continue
        seen.add((dictionary, word, body))
        levels = list(READERS[dictionary](html))
        if not levels and MARKERS[dictionary].search(html):
            missed[f"{dictionary}: {headword}"] += 1
        here: Counter[tuple] = Counter()  # this body's senses per level
        for level in levels:
            key = (level.word or word, upos_of(level.pos), level.scheme, level.value, dictionary)
            here[(key, b"" if level.word else body)] += level.senses
        for (key, place), n in here.items():
            counted = senses.setdefault(key, {})
            counted[place] = max(counted.get(place, 0), n)
    rows = [(*key, sum(places.values())) for key, places in senses.items()]
    if missed:  # fail loud: a mark the readers do not understand would silently drop a word's level
        raise ValueError(f"{len(missed)} entries carry a level mark no reader read, e.g. {list(missed)[:5]}")
    with fresh_db(out, SCHEMA) as con:
        con.executemany("INSERT INTO level VALUES (?,?,?,?,?,?)", sorted(rows))
    by_scheme = Counter((r[2], r[3]) for r in rows if r[2] != "cefr")
    words = Counter(r[2] for r in {(r[0], r[1], r[2]) for r in rows})
    return {"rows": len(rows), "words_per_scheme": dict(words.most_common()),
            "values": {f"{s}:{v}": n for (s, v), n in sorted(by_scheme.items())}}


def main() -> None:
    con = sqlite3.connect(f"file:{ROOT / 'corpus' / 'unified.db'}?mode=ro", uri=True)

    def entries():
        for dict_id, name in DICTIONARIES.items():
            for headword, body in con.execute("SELECT headword, body FROM entry WHERE dict_id = ? AND headword NOT "
                                              "LIKE '@%'", (dict_id,)):
                yield name, headword, zlib.decompress(body).decode("utf-8", "replace")
    summary = build(entries(), DATA / "levels.db")
    con.close()
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
