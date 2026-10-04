"""Word families and spelling variants.

    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/families.py

Links between words, each from the dictionaries that give it:

    derivative senses     the words dictionaries list under a headword (embezzle: embezzlement)
    OALD Word Family      its family boxes (decide, decision, decisive, undecided) and their
                          opposites (decision ≠ indecision), from the raw entries
    inflections.db        the forms the inflection inventory found to be derivatives or variants
    comma headwords       "beedie, beedi" when the two spell one word (a known alternation)

A link's relation is read from the two words: suffixed (reserve, reservation), prefixed
(decided, undecided), conversion (the same word, another part of speech), compound (fibre,
fibreboard; strip, strip map), opposite, family (OALD's box), or related (listed together,
no rule explains how). Families are the connected groups of words joined by suffixed,
prefixed, conversion, inflection, opposite and family links, and by spelling variants;
compounds and affix entries (re-, -meter) join no family: they would chain fibre to board,
and every re- word to each other.

Spelling variants carry the region where the alternation says one (colour GB, color US).
Needs data/inflections.db. Writes data/families.db.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Iterator, Mapping, NamedTuple

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "inventories"), str(ROOT / "scripts")]
from inventory import DATA, PUBLISHER, STRUCTURED  # noqa: E402
from inventory.inflect import regular  # noqa: E402
from inventory.db import fresh_db  # noqa: E402
from inventory.pos import normalize as read_pos  # noqa: E402
from inventory.spelling import is_variant, spelled_alike, spelling_regions  # noqa: E402

LEFT_OUT = frozenset({"etym", "lpd", "cepd", "peu", "ocd"})
OALD_ID = 1  # in corpus/unified.db

SUFFIXES = sorted(set("""ness ly ment ation ition tion sion ion er or ar ist ism ity ty ive ative itive al ial ical
    ic ous ious eous uous able ible ful less ish ize ise ing ed en ship hood dom ance ence ancy ency ant ent ary
    ery ory ure age an ian ean ese ite ward wards wise y ie ette let ling ee eer ess ology ologist logist ologic
    ological some th ia ine ile oid ification ify fy ate ator atory istic ics ite s es ies ied ier iest est
    ability ibility ically ally ism ist ite ician ette ery nce cy ia ist ism aceous ide et osity iferous ferous
    icity ium um ule ular ulous ival ivity atic etic otic osis itis ation ational ationally ancy ency ible ibly
    ably ingly edly fully lessly ishly ously ively ize izer ization iser isation ery ry ility inary ific fic
    acea aceae id iid iform ogue ogy""".split()), key=len,
                  reverse=True)
PREFIXES = sorted(set("""un in im il ir dis non mis re pre post anti de over under out co counter inter intra
    super sub semi mid ex extra hyper hypo micro macro mono multi poly pro trans ultra up down fore self well ill
    be en em bi tri auto neo pseudo quasi mal""".split()), key=len, reverse=True)  # not "a": aestivate is a spelling
FAMILY_RELATIONS = frozenset({"suffixed", "prefixed", "sibling", "conversion", "opposite", "family", "variant",
                              "inflection"})


def _suffix_chain(rest: str, depth: int = 0) -> bool:
    """Whether rest is one or more suffixes: "ation", "ishness", "ically"."""
    if not rest:
        return depth > 0
    return any(rest.startswith(s) and _suffix_chain(rest[len(s):], depth + 1) for s in SUFFIXES if depth < 4)


_STEM_ENDINGS = ("e", "y", "le", "ue", "um", "us", "is", "a", "on", "ia", "ium")  # dropped before a suffix


def lemma_index(forms_of: Mapping[str, Iterable[str]]) -> dict[str, frozenset[str]]:
    """Each inflected form's lemmas, every one of them: a form can inflect two words (the -s of a verb
    and the plural of a noun), and keeping one would make the other's forms look like siblings."""
    lemmas: dict[str, set[str]] = defaultdict(set)
    for lemma, forms in forms_of.items():
        for form in forms:
            lemmas[form].add(lemma)
    return {form: frozenset(ls) for form, ls in lemmas.items()}


def relation(base: str, member: str, words: frozenset[str] = frozenset(), forms: frozenset[str] = frozenset(),
             lemma_of: Mapping[str, frozenset[str] | str] | None = None) -> str:
    """How member is formed from base; `words` lets a compound's other part be recognised,
    `forms` are the base's inflections, `lemma_of` maps inflected forms to their lemmas, as
    lemma_index builds it (dictionaries list "continues", or "discouraged" under "discouraging",
    among derivatives). A plain str value is read as a form's only lemma."""
    b, m = base.lower(), member.lower()
    if m == b:
        return "conversion"
    if m in forms or _lemmas(m, lemma_of) & (_lemmas(b, lemma_of) | {b}) or m in _verb_forms(b):
        return "inflection"
    if _is_affix(b) and _is_affix(m) and re.sub("[aio]*-$", "", b) == re.sub("[aio]*-$", "", m):
        return "variant"  # lymphangi- / lymphangio-: one combining form
    if b.endswith("-") and len(b) > 2 and m.replace("-", "").startswith(b[:-1].replace("-", "")):
        return "prefixed"  # an entry for a prefix: re- / refocus, ortho- / orthodiagonal
    if b.startswith("-") and len(b) > 2 and m.endswith(b[1:]) and len(m) > len(b) - 1:
        return "suffixed"  # an entry for a suffix: -meter / barometer
    if " " in m or " " in b:
        if m.replace(" ", "").replace("-", "") == b.replace(" ", "").replace("-", ""):
            return "variant"  # night club / nightclub
        return "compound" if set(b.split()) & set(m.split()) or b in m else "related"
    m_plain, b_plain = m.replace("-", ""), b.replace("-", "")
    if not _is_affix(b) and (m_plain == b_plain or is_variant(m_plain, b_plain) or spelled_alike(m_plain, b_plain)):
        return "variant"  # co-ordination; calisthenic, callisthenic; twocker, twoccer
    for p in PREFIXES:  # undecided, disbelief, non-member; also a prefix on a derivative: indecisive
        if m_plain.startswith(p) and len(m_plain) > len(p) + 2:
            rest = m_plain[len(p):]
            if rest == b_plain or relation(b_plain, rest) == "suffixed":
                return "prefixed"
    stems = [b_plain] + ([b_plain[:-3] + "t"] if b_plain.endswith("sis") else [])  # synthesis -> synthet-ic
    for stem in stems:  # two different suffixes on one stem: hesiodic/hesiodian, -acea/-iform
        common = len(_common_prefix(stem, m_plain))
        if common in (len(stem), len(m_plain)):
            continue  # one word extends the other: a suffix (motor/motory), not a sibling
        for lcp in range(common, max(common - 3, 2), -1):
            b_rest, m_rest = stem[lcp:], m_plain[lcp:]
            if b_rest and m_rest and b_rest not in _STEM_ENDINGS and _suffix_chain(b_rest) and _suffix_chain(m_rest):
                return "sibling"
    for stem in stems:
        common = len(_common_prefix(stem, m_plain))
        for lcp in range(common, max(common - 3, 2), -1):  # a stem that alternates: -ion/-ive, -ic/-ism
            b_rest, m_rest = stem[lcp:], m_plain[lcp:]
            stem_change = not b_rest or b_rest in _STEM_ENDINGS
            if lcp >= 3 and len(b_rest) <= 3 and _suffix_chain(m_rest) and (stem_change or lcp == common):
                if not stem_change and _suffix_chain(b_rest):
                    return "sibling"   # icebreaker/icebreaking, -ist/-ism: two suffixes on one stem
                return "suffixed"      # decide/decision: deci + de | sion; reserve/reservation
            if lcp >= 3 and _suffix_chain(b_rest) and (_suffix_chain(m_rest) or not m_rest):
                return "sibling"       # oscitancy/oscitate; skydiving/skydiver
    common = len(_common_prefix(b_plain, m_plain))
    b_rest, m_rest = b_plain[common:], m_plain[common:]
    if common >= 2 and not b_rest and m_rest[:1] == b_plain[-1:] and _suffix_chain(m_rest[1:]):
        return "suffixed"  # a doubled consonant: run/runner, big/bigger
    if m_plain.startswith(b_plain) and (m_plain[len(b_plain):] in words or "-" in m):
        return "compound"  # fibreboard, fibre-optic
    if m_plain.endswith(b_plain) and m_plain[:-len(b_plain)] in words:
        return "compound"  # headboard under board
    return "related"


def _lemmas(form: str, lemma_of: Mapping[str, frozenset[str] | str] | None) -> frozenset[str]:
    found = (lemma_of or {}).get(form, frozenset())
    return frozenset({found}) if isinstance(found, str) else found


def _verb_forms(lemma: str) -> set[str]:
    """The regular verb forms of a word: a listed "turkicized" under "turkicize" is one."""
    if " " in lemma or not lemma.isalpha():
        return set()
    return {form for forms in regular(lemma, "VERB").values() for form, _ in forms}


def _common_prefix(a: str, b: str) -> str:
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return a[:n]


class Link(NamedTuple):
    base: str
    member: str
    member_pos: str
    relation: str
    dictionary: str


# ---- sources -------------------------------------------------------------------------------

def derivative_links(db: Path, words: frozenset[str], forms_of: dict[str, frozenset[str]],
                     lemma_of: Mapping[str, frozenset[str]]) -> Iterator[Link]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute("SELECT e.headword, s.phrase, s.pos FROM s_sense s JOIN s_entry e ON e.entry_id = s.entry_id "
                       "WHERE s.kind = 'derivative' AND s.phrase != ''")
    for headword, member, pos in rows:
        base, member = _word(headword), _word(member)
        if base and member:
            yield Link(base, member, _upos(pos),
                       relation(base, member, words, forms_of.get(base, frozenset()), lemma_of), db.stem)
    con.close()


def comma_variants(db: Path) -> Iterator[Link]:
    """"beedie, beedi": a headword printing two spellings of one word."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    for (headword,) in con.execute("SELECT headword FROM s_entry WHERE headword LIKE '%, %'"):
        parts = [_word(p) for p in headword.split(",") if p.strip()]
        for other in parts[1:]:
            if parts[0] and other and is_variant(other, parts[0]):
                yield Link(parts[0], other, "", "variant", db.stem)
    con.close()


def inflection_links(inflections_db: Path, forms_of: Mapping[str, frozenset[str]],
                     lemma_of: Mapping[str, frozenset[str]]) -> Iterator[Link]:
    """The forms inflections.db set aside as variants or derivatives; with the attested forms in
    hand, a "derivative" that is another form of one lemma (discouraged under discouraging) is an
    inflection, as it is in the dictionaries' derivative lists."""
    con = sqlite3.connect(f"file:{inflections_db}?mode=ro", uri=True)
    for form, lemma, kind, dictionaries in con.execute(
            "SELECT form, lemma, kind, dictionaries FROM other WHERE kind IN ('variant', 'derivative')"):
        rel = "variant" if kind == "variant" else relation(lemma, form, forms=forms_of.get(lemma, frozenset()),
                                                          lemma_of=lemma_of)
        for d in json.loads(dictionaries):
            if d not in LEFT_OUT and d != "oed":
                yield Link(lemma, form, "", rel, d)
    con.close()


_WFW = re.compile(r'<span class="wfw">(.*?)</span>\s*<span class="wfp"[^>]*>([^<]*)</span>'
                  r'(?:\s*<span class="wfo">\(≠\s*(.*?)\)</span>)?', re.S)


def oald_family(html: str) -> list[tuple[str, str, list[str]]]:
    """The members of an OALD Word Family box: (word, part of speech, opposites)."""
    box = re.search(r'unbox="wordfamily">(.*?)</ul>', html, re.S)
    if not box:
        return []
    return [(_word(re.sub(r"<[^>]+>", "", w)), pos.strip(), [_word(o) for o in re.split(r",\s*", opp or "") if o.strip()])
            for w, pos, opp in _WFW.findall(box.group(1))]


def oald_links(unified: Path) -> Iterator[Link]:
    con = sqlite3.connect(f"file:{unified}?mode=ro", uri=True)
    for (body,) in con.execute("SELECT body FROM entry WHERE dict_id = ?", (OALD_ID,)):
        html = zlib.decompress(body).decode("utf-8", "replace")
        if 'unbox="wordfamily"' not in html:
            continue
        members = oald_family(html)
        for word, pos, opposites in members:
            yield Link(members[0][0], word, _upos(pos), "family", "oald")
            for opposite in opposites:
                yield Link(word, opposite, _upos(pos), "opposite", "oald")
    con.close()


_MARKS = re.compile("[ˈˌ·ʹ‧]")  # stress and syllable marks the OED prints inside words


def _word(text: str) -> str:
    return " ".join(_MARKS.sub("", text.replace("’", "'")).split()).lower().strip(" ,;")


def _upos(printed: str) -> str:
    tags = read_pos(printed.strip(" ,")).tags if printed.strip(" ,") else set()
    return next(iter(tags)) if len(tags) == 1 else ""


# ---- families --------------------------------------------------------------------------------

def _is_affix(word: str) -> bool:
    return word.startswith("-") or word.endswith("-")


class _Groups:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def join(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


SCHEMA = """
CREATE TABLE link (base TEXT NOT NULL, member TEXT NOT NULL, member_pos TEXT NOT NULL, relation TEXT NOT NULL,
  dictionaries TEXT NOT NULL, n INTEGER NOT NULL, publishers INTEGER NOT NULL);
CREATE TABLE family (family_id INTEGER NOT NULL, word TEXT NOT NULL);
CREATE TABLE variant (word TEXT NOT NULL, variant TEXT NOT NULL, word_region TEXT NOT NULL,
  variant_region TEXT NOT NULL, dictionaries TEXT NOT NULL, n INTEGER NOT NULL);
CREATE INDEX link_base ON link(base);
CREATE INDEX link_member ON link(member);
CREATE INDEX family_word ON family(word);
CREATE INDEX variant_word ON variant(word);
"""


def build(links: Iterable[Link], out: Path) -> dict:
    merged: dict[tuple, dict] = {}
    for link in links:
        if link.base == link.member and link.relation != "conversion":
            continue
        key = (link.base, link.member, link.relation)
        row = merged.setdefault(key, {"pos": Counter(), "dictionaries": set()})
        if link.member_pos:
            row["pos"][link.member_pos] += 1
        row["dictionaries"].add(link.dictionary)
    groups = _Groups()
    for (base, member, rel) in merged:
        if rel in FAMILY_RELATIONS and not _is_affix(base) and not _is_affix(member):
            groups.join(base, member)  # an affix entry (re-, -meter) would chain every word it forms
    members: dict[str, list[str]] = defaultdict(list)
    for word in groups.parent:
        members[groups.find(word)].append(word)
    families = sorted((sorted(ws) for ws in members.values() if len(ws) > 1), key=lambda ws: ws[0])
    with fresh_db(out, SCHEMA) as con:
        for (base, member, rel), row in sorted(merged.items()):
            dicts = sorted(row["dictionaries"])
            pos = row["pos"].most_common(1)[0][0] if row["pos"] else ""
            con.execute("INSERT INTO link VALUES (?,?,?,?,?,?,?)", (base, member, pos, rel, json.dumps(dicts),
                                                                   len(dicts), len({PUBLISHER.get(d, d) for d in dicts})))
            if rel == "variant":
                a, b = spelling_regions(base, member)
                con.execute("INSERT INTO variant VALUES (?,?,?,?,?,?)",
                            (base, member, a, b, json.dumps(dicts), len(dicts)))
        for i, words in enumerate(families, 1):
            con.executemany("INSERT INTO family VALUES (?,?)", [(i, w) for w in words])
    sizes = sorted((len(f) for f in families), reverse=True)
    return {"links": len(merged), "relations": dict(Counter(k[2] for k in merged).most_common()),
            "families": len(families), "words_in_families": sum(sizes), "largest": sizes[:10]}


def main() -> None:
    inflections = DATA / "inflections.db"
    if not inflections.exists():
        sys.exit(f"{inflections} is missing: run inventory/inflections.py first")
    con = sqlite3.connect(f"file:{inflections}?mode=ro", uri=True)
    words = frozenset(w for (w,) in con.execute("SELECT DISTINCT lemma FROM lemma WHERE n >= 2"))
    forms: dict[str, set[str]] = defaultdict(set)
    for form, lemma in con.execute("SELECT form, lemma FROM inflection WHERE source = 'attested'"):  # not "jumper"
        forms[lemma].add(form)
    forms_of = {k: frozenset(v) for k, v in forms.items()}
    lemma_of = lemma_index(forms_of)
    con.close()

    def links() -> Iterator[Link]:
        for db in sorted(STRUCTURED.glob("*.db")):
            if db.stem not in LEFT_OUT:
                yield from derivative_links(db, words, forms_of, lemma_of)
                yield from comma_variants(db)
        yield from inflection_links(inflections, forms_of, lemma_of)
        yield from oald_links(ROOT / "corpus" / "unified.db")
    print(json.dumps(build(links(), DATA / "families.db"), indent=1))


if __name__ == "__main__":
    main()
