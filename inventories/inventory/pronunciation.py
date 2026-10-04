"""Pronunciation inventories: where the stress falls, and where it moves.

    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/pronunciation.py

Two inventories, from the IPA transcriptions of the dictionaries that print IPA (AHD's and
Merriam-Webster's respelling systems are left out: their stress marks follow other rules):

    pos_contrast   one spelling, two parts of speech, two pronunciations: object n. ˈɒbdʒɪkt,
                   v. əbˈdʒekt (stress); use n. juːs, v. juːz (voicing); estimate n. -ət, v.
                   -eɪt (ate); live v. lɪv, adj. laɪv (vowel)
    family_stress  words of one family whose primary stress falls on different syllables:
                   photograph ˈfəʊtəɡrɑːf, photography fəˈtɒɡrəfi, photographic ˌfəʊtəˈɡræfɪk

A pronunciation belongs to a part of speech only where the dictionary says so: an entry with
one part of speech, or a homograph block read from the raw page (LDOCE's heads, CEPD's
blocks, LPD's numbered homographs). Two pronunciations are compared only within one
dictionary and one region, so transcription conventions never mix; a contrast or a shift
counts the dictionaries that show it and those that do not.

Needs data/families.db. Writes data/pronunciations.db (tables pron, pos_contrast,
family_stress, family_shift).
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import zlib
from html import unescape
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Iterator, NamedTuple

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "inventories"), str(ROOT / "scripts")]
from inventory import DATA, STRUCTURED  # noqa: E402
from inventory.db import fresh_db  # noqa: E402
from inventory.inflect import syllables as spelled_syllables  # noqa: E402
from inventory.ipa import Stress, analyse, contrast, variants, weak  # noqa: E402
from inventory.pos import normalize as read_pos  # noqa: E402

IPA_PARSED = ("oald", "oalecd", "cald", "med", "mwaled", "ode", "odecn", "ced", "cobuild", "ncecd", "yhdcd", "oed")
RAW = {"ldoce": 2, "lpd": 15, "cepd": 16}   # dictionary ids in corpus/unified.db
PREFERENCE = ("cepd", "lpd", "oald", "ldoce", "cald", "med", "ode", "oalecd", "odecn", "ced", "mwaled", "ncecd",
              "yhdcd", "cobuild", "oed")
REGIONS = {"uk": "GB", "gb": "GB", "bre": "GB", "us": "US", "ame": "US", "": ""}
FAMILY_LINKS = ("suffixed", "prefixed", "sibling")


class Pron(NamedTuple):
    dictionary: str
    word: str
    upos: str      # "" when the source does not tie the pronunciation to one part of speech
    region: str
    ipa: str


def _upos(printed: str) -> str:
    tags = read_pos(printed.strip(" ,")).tags if printed.strip(" ,") else set()
    return next(iter(tags)) if len(tags) == 1 else ""


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).replace("&nbsp;", " ").strip()


# ---- raw readers: (part of speech, region, transcription) ------------------------------------

def _ldoce_forms(head: str) -> set[str]:
    """The headword forms an LDOCE head names: "Alps, the" is Alps; "Zuni, Zuñi" is both."""
    m = re.search(r'<span class="hwd">(.*?)</span>', head)
    text = " ".join(unescape(_text(m.group(1))).split()) if m else ""
    return {f.strip() for f in re.sub(r",\s*(?:the|a|an)$", "", text).split(", ") if f.strip()}


def ldoce_heads(html: str, word: str) -> Iterator[tuple[str, str, str]]:
    """The heads of `word` on its page. LDOCE shows a derivative or an alias the page of the
    word it belongs to ("actuarial" shows "actuary"): those heads are not the word's."""
    for part in html.split('<span class="entryhead">')[1:]:
        head = part[:part.find('class="Sense"')] if 'class="Sense"' in part else part[:4000]
        if word not in _ldoce_forms(head):
            continue
        pos = m.group(1) if (m := re.search(r'<span class="pos">([^<]*)</span>', head)) else ""
        head = head[:m.start()] if m else head  # the word's own transcriptions come before its part of speech
        for pron in re.findall(r'<span class="pron">(.*?)</span>', head):
            yield pos, "GB", _text(pron)
        # the American variant: a "$" span inside, then the transcription
        for us in re.findall(r'<span class="amevarpron">(?:<span class="neutral">[^<]*</span>)?([^<]*)</span>', head):
            yield pos, "US", us.strip()


_CEPD_TOKEN = re.compile(r'<span class="prongrp">|<span class="(comment|pron|ussymbol)">(.*?)</span>')
_CEPD_ORDINARY = frozenset({"ordinary senses", "ordinary sense", "normal form", "strong form", "strong forms",
                            "weak form", "weak forms", "occasional weak form"})


def cepd_blocks(html: str) -> Iterator[tuple[str, str, str]]:
    for block in html.split('<span class="di-head">')[1:]:
        head, _, body = block.partition('<span class="di-body">')
        pos = m.group(1) if (m := re.search(r'<span class="pos">([^<]*)</span>', head)) else ""
        # the word's own forms come first; a usage note's or panel's are examples ('to cut' /təˈkʌt/)
        main = re.split(r'<span class="(?:inflection|compound|derivative|usagenote|panel)"', body)[0]
        region, qualified, given = "GB", False, False
        for token in _CEPD_TOKEN.finditer(main):
            if token.group(0) == '<span class="prongrp">':
                qualified = False  # a label holds to the end of its group
            elif token.group(1) == "comment":
                # a label before the block's first transcription names the homograph (wind n. "air
                # blowing"); after one, it restricts a variant to a sense (present n. "military
                # term: prɪˈzent", control n. "in machinery also: ˈkɒn.trəʊl"), not the word's
                qualified = given and _text(token.group(2)).strip(" :").lower() not in _CEPD_ORDINARY
            elif token.group(1) == "ussymbol":
                region = "US"
            elif not qualified:
                given = True
                yield pos, region, _text(token.group(2))


_LPD_POS = re.compile(r"<i>\s*([a-z ,]+?)\s*</i>")


def lpd_blocks(html: str) -> Iterator[tuple[str, str, str]]:
    blocks = re.split(r"<!--Roman-->", html)
    for block in (blocks[1:] if len(blocks) > 1 else blocks):
        head = block.split("<br>", 1)[0]
        pos = m.group(1) if (m := _LPD_POS.search(head)) else ""
        main = re.search(r"<font color=mediumblue>(.*?)</font>", head, re.S)
        if main:
            yield pos, "GB", _text(main.group(1))
            after = head[main.end():]
            if (us := re.search(r"<font color=green>AmE</font>\s*<font color=mediumblue>(.*?)</font>", after, re.S)):
                yield pos, "US", _text(us.group(1))


RAW_READERS = {"ldoce": ldoce_heads,  # CEPD's and LPD's pages are the word's own (each names it first)
               "cepd": lambda html, _word: cepd_blocks(html), "lpd": lambda html, _word: lpd_blocks(html)}


def raw_prons(unified: Path) -> Iterator[Pron]:
    con = sqlite3.connect(f"file:{unified}?mode=ro", uri=True)
    for name, dict_id in RAW.items():
        for headword, body in con.execute("SELECT headword, body FROM entry WHERE dict_id = ? AND headword NOT LIKE "
                                          "'@%'", (dict_id,)):
            word = " ".join(headword.split())
            for pos, region, field in RAW_READERS[name](zlib.decompress(body).decode("utf-8", "replace"), word):
                for ipa in variants(field):
                    yield Pron(name, word, _upos(pos), region, ipa)  # case kept: COO is not coo
    con.close()


def parsed_prons(db: Path) -> Iterator[Pron]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute("SELECT e.headword, e.pos, p.region, p.ipa FROM s_pron p JOIN s_entry e ON e.entry_id = p.entry_id "
                       "WHERE p.ipa != ''")
    for headword, pos_list, region, field in rows:
        printed = json.loads(pos_list)
        tags = set().union(*(read_pos(p).tags for p in printed)) if printed else set()
        upos = next(iter(tags)) if len(tags) == 1 else ""
        for ipa in variants(field):
            yield Pron(db.stem, " ".join(headword.split()), upos, REGIONS.get(region.lower(), region), ipa)
    con.close()


# ---- the two comparisons -----------------------------------------------------------------------

def collect(prons) -> tuple[dict, list[tuple], set[tuple]]:
    """{(dictionary, region, word): {upos: [(Stress, ipa)]}}, the rows of the pron table, and
    every (dictionary, region, word, upos) printed at all, read or not ("-ˈsɔːrs" is not read)."""
    heard: dict[tuple, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    rows = []
    printed = set()
    for p in prons:
        printed.add((p.dictionary, p.region, p.word, p.upos))
        a = analyse(p.ipa)
        if a is None or _is_affix(p.word) or not _fits_spelling(p.word, a):
            continue
        heard[(p.dictionary, p.region, p.word)][p.upos].append((a, p.ipa))
        rows.append((p.word, p.upos, p.region, p.ipa, a.syllables, a.primary, p.dictionary))
    return heard, rows, printed


def _change(sa: list, sb: list) -> str:
    """How two parts of speech of one word differ in one dictionary and region ("" if not)."""
    stress_a, stress_b = {s.primary for s, _ in sa}, {s.primary for s, _ in sb}
    if not stress_a & stress_b:
        return "stress"
    seg_a, seg_b = {weak(s.segments) for s, _ in sa}, {weak(s.segments) for s, _ in sb}
    if not seg_a & seg_b:  # the sounds always differ: that is the contrast (consummate -ət/-eɪt)
        if not {s.syllables for s, _ in sa} & {s.syllables for s, _ in sb}:
            return "segment"   # a syllable more or less: rite adv. ˈraɪtiː, n. raɪt
        return contrast(min(seg_a), min(seg_b))
    if stress_a != stress_b:
        return "stress (optional)"   # one part of speech takes either stress: adept n.
    return ""


def _is_affix(word: str) -> bool:
    return word.startswith("-") or word.endswith("-")


def _fits_spelling(word: str, a: Stress) -> bool:
    """A transcription with about as many syllables as the spelling: not another word's
    (NCECD gives "palaeoecologic" one of ˈpælətəlɪ), not spelled letter by letter (WHO)."""
    if " " in word:
        return True
    expected = spelled_syllables(word)
    return abs(a.syllables - expected) <= max(1, expected // 2)


def pos_contrasts(heard: dict, printed: set[tuple] = frozenset()) -> list[tuple]:
    """Per (word, part of speech pair): the change, the dictionaries showing it, the others.
    Each dictionary votes once for each change it shows, in however many regions; the example
    is a pair of transcriptions that shows the winning change."""
    changes: dict[tuple, dict[str, dict[str, None]]] = defaultdict(dict)  # key -> dictionary -> its changes
    compared: dict[tuple, set] = defaultdict(set)
    shown: dict[tuple, list] = defaultdict(list)  # key -> (dictionary, region, change, forms a, forms b)
    for (dictionary, region, word), given in heard.items():
        by_pos, inherited = dict(given), set()
        if region == "US":  # LDOCE's "$ ˈædres": a US form printed only where it differs, the British one stands in
            for pos, forms in heard.get((dictionary, "GB", word), {}).items():
                if pos not in by_pos and (dictionary, region, word, pos) not in printed:
                    by_pos[pos] = forms
                    inherited.add(pos)
        for a, b in combinations(sorted(p for p in by_pos if p and p != "X"), 2):
            if {a, b} <= inherited:
                continue  # compared already, as British
            key = (word, a, b)
            compared[key].add(dictionary)
            change = _change(by_pos[a], by_pos[b])
            if not change or inherited & {a, b} and not change.startswith("stress"):
                continue  # a US vowel left unprinted in one block is no contrast (glox n. $ ɡlɑːks)
            changes[key].setdefault(dictionary, {})[change] = None
            shown[key].append((dictionary, region, change, by_pos[a], by_pos[b]))
    rows = []
    for key, by_dictionary in changes.items():
        showing = set(by_dictionary)
        without = compared[key] - showing
        counted = Counter(c for found in by_dictionary.values() for c in found)
        change = counted.most_common(1)[0][0]
        if {"stress", "stress (optional)"} <= set(counted):
            change = "stress (optional)"  # one dictionary lets them share a stress: it does not always differ
        fits = (lambda c: c.startswith("stress")) if change.startswith("stress") else (lambda c: c == change)
        src, region, _, forms_a, forms_b = min((x for x in shown[key] if fits(x[2])), key=lambda x: _rank(x[0], x[1]))
        ipa_a, ipa_b = _showing(forms_a, forms_b, change)
        rows.append((*key, change, ipa_a, ipa_b, src, region,
                     json.dumps(sorted(showing)), len(showing), json.dumps(sorted(without)), len(without)))
    return sorted(rows)


def _showing(sa: list, sb: list, change: str) -> tuple[str, str]:
    """The first pair of transcriptions, one of each part of speech, that shows the change:
    a stress change by two stresses; another change by a pair that differs in it alone, else
    by the pair it was read from (see _change)."""
    pairs = [(x, ia, y, ib) for x, ia in sa for y, ib in sb]
    if change.startswith("stress"):
        found = [p for p in pairs if p[0].primary != p[2].primary]
    else:
        wanted = (min(weak(s.segments) for s, _ in sa), min(weak(s.segments) for s, _ in sb))
        found = [p for p in pairs if p[0].primary == p[2].primary and _change([p[:2]], [p[2:]]) == change] + \
                [p for p in pairs if (weak(p[0].segments), weak(p[2].segments)) == wanted]
    if not found:
        raise ValueError(f"no pair of {[i for _, i in sa]} and {[i for _, i in sb]} shows {change!r}")
    return found[0][1], found[0][3]


def _rank(dictionary: str, region: str) -> tuple[int, bool]:
    """The example's preference: the dictionary, then British first."""
    return PREFERENCE.index(dictionary) if dictionary in PREFERENCE else 99, region != "GB"


def family_stress(heard: dict, links: list[tuple[str, str, str]]) -> list[tuple]:
    """Per family link: whether the primary stress moves, counted per dictionary and region.
    Suffixation keeps the stem at the start, so its syllables count from the start; a prefix
    keeps it at the end, so they count from the end."""
    words: dict[tuple, dict[str, list]] = defaultdict(dict)
    for (dictionary, region, word), by_pos in heard.items():
        if word == word.lower():  # families are of lowercase words: not names, not abbreviations
            words[(dictionary, region)][word] = [x for xs in by_pos.values() for x in xs]
    rows = []
    for base, member, relation in links:
        moved, kept, shown = set(), set(), []
        pos = lambda s: s.primary if relation != "prefixed" else s.syllables - s.primary
        for (dictionary, region), known in words.items():
            if base not in known or member not in known:
                continue
            b, m = {pos(s) for s, _ in known[base]}, {pos(s) for s, _ in known[member]}
            (moved if not b & m else kept).add(dictionary)
            shown.append((dictionary, region, not b & m, known[base], known[member]))
        if moved or kept:
            shift = len(moved) > len(kept)
            # the example agrees with the decision: from a dictionary that shows it, a pair that shows it
            src, region, _, forms_b, forms_m = min((x for x in shown if x[2] == shift), key=lambda x: _rank(x[0], x[1]))
            (sb, ib), (sm, im) = next((x, y) for x in forms_b for y in forms_m if (pos(x[0]) != pos(y[0])) == shift)
            rows.append((base, member, relation, ib, im, f"{sb.primary}/{sb.syllables}", f"{sm.primary}/{sm.syllables}",
                         int(shift), json.dumps(sorted(moved)), len(moved), json.dumps(sorted(kept)), len(kept), src,
                         region))
    return sorted(rows)


SCHEMA = """
CREATE TABLE pron (word TEXT NOT NULL, pos TEXT NOT NULL, region TEXT NOT NULL, ipa TEXT NOT NULL,
  syllables INTEGER NOT NULL, primary_stress INTEGER NOT NULL, dictionary TEXT NOT NULL);
CREATE TABLE pos_contrast (word TEXT NOT NULL, pos_a TEXT NOT NULL, pos_b TEXT NOT NULL, change TEXT NOT NULL,
  ipa_a TEXT NOT NULL, ipa_b TEXT NOT NULL, example_from TEXT NOT NULL, region TEXT NOT NULL,
  dictionaries TEXT NOT NULL, n INTEGER NOT NULL, not_in TEXT NOT NULL, n_not INTEGER NOT NULL);
CREATE TABLE family_stress (base TEXT NOT NULL, member TEXT NOT NULL, relation TEXT NOT NULL, ipa_base TEXT NOT NULL,
  ipa_member TEXT NOT NULL, stress_base TEXT NOT NULL, stress_member TEXT NOT NULL, shift INTEGER NOT NULL,
  moved_in TEXT NOT NULL, n_moved INTEGER NOT NULL, kept_in TEXT NOT NULL, n_kept INTEGER NOT NULL,
  example_from TEXT NOT NULL, region TEXT NOT NULL);
CREATE TABLE family_shift (family_id INTEGER NOT NULL, word TEXT NOT NULL, ipa TEXT NOT NULL,
  primary_stress INTEGER NOT NULL, syllables INTEGER NOT NULL);
CREATE INDEX pron_word ON pron(word);
CREATE INDEX contrast_word ON pos_contrast(word);
CREATE INDEX family_stress_base ON family_stress(base);
"""


def build(prons, links: list[tuple[str, str, str]], families: dict[int, list[str]], out: Path) -> dict:
    heard, pron_rows, printed = collect(prons)
    contrasts = pos_contrasts(heard, printed)
    stress_rows = family_stress(heard, links)
    shifted = {w for r in stress_rows if r[7] for w in r[:2]}
    shape = _representative(heard)
    family_rows = [(fid, w, *shape[w]) for fid, ws in families.items() if any(w in shifted for w in ws)
                   for w in ws if w in shape]
    with fresh_db(out, SCHEMA) as con:
        con.executemany("INSERT INTO pron VALUES (?,?,?,?,?,?,?)", pron_rows)
        con.executemany(f"INSERT INTO pos_contrast VALUES ({','.join('?' * 12)})", contrasts)
        con.executemany(f"INSERT INTO family_stress VALUES ({','.join('?' * 14)})", stress_rows)
        con.executemany("INSERT INTO family_shift VALUES (?,?,?,?,?)", family_rows)
    return {"prons": len(pron_rows), "pos_contrasts": len(contrasts),
            "contrast_kinds": dict(Counter(r[3] for r in contrasts).most_common()),
            "contrasts_2plus": sum(1 for r in contrasts if r[9] >= 2),
            "family_links_compared": len(stress_rows), "family_links_shifted": sum(r[7] for r in stress_rows),
            "families_with_a_shift": len({r[0] for r in family_rows})}


def _representative(heard: dict) -> dict[str, tuple[str, int, int]]:
    """word -> (ipa, primary, syllables) from the most preferred dictionary, British first."""
    best: dict[str, tuple] = {}
    for (dictionary, region, word), by_pos in heard.items():
        rank = (PREFERENCE.index(dictionary) if dictionary in PREFERENCE else 99, region != "GB")
        s, ipa = next(x for xs in by_pos.values() for x in xs)
        if word not in best or rank < best[word][0]:
            best[word] = (rank, (ipa, s.primary, s.syllables))
    return {w: v for w, (_, v) in best.items()}


def main() -> None:
    families_db = DATA / "families.db"
    if not families_db.exists():
        sys.exit(f"{families_db} is missing: run inventory/families.py first")
    con = sqlite3.connect(f"file:{families_db}?mode=ro", uri=True)
    links = con.execute(f"SELECT base, member, relation FROM link WHERE relation IN ({','.join('?' * len(FAMILY_LINKS))})",
                        FAMILY_LINKS).fetchall()
    families: dict[int, list[str]] = defaultdict(list)
    for fid, word in con.execute("SELECT family_id, word FROM family"):
        families[fid].append(word)
    con.close()

    def prons():
        yield from raw_prons(ROOT / "corpus" / "unified.db")
        for name in IPA_PARSED:
            yield from parsed_prons(STRUCTURED / f"{name}.db")
    print(json.dumps(build(prons(), links, families, DATA / "pronunciations.db"), indent=1))


if __name__ == "__main__":
    main()
