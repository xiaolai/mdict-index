"""The inflection inventory: every word form, its lemma, part of speech and slot.

    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/inflections.py

Built from the forms the parsed dictionaries list (corpus/_structured/unified.db/*.db, Entry.forms),
which are untyped and mixed: inflections, spelling variants (colour/color), derivatives
(abet/abetter), contractions (isn't), forms of other parts of speech, and pronunciations
glued on (analyses/ənælɪsiːz/). Each form is classified against its lemma's parts of speech:

  regular     it is what the rules (inventory/inflect.py) give for a slot
  irregular   it fits no rule but belongs to a slot by shape: went, gone, children, better
  variant     a spelling of the lemma itself (colour/color): goes to word families
  derivative  another word (abetter): goes to word families
  contraction isn't, aren't
  historical  a dictionary's historical spellings (OED: quhyit = white), not inflections

An irregular form is kept only when plausible_irregular() accepts it; the rest are listed as
"unclassified" for inspection.

Attested forms are merged across dictionaries, each recording which ones list it. Lemmas
with no attested form for a slot get the regular form, marked source=rule, when at least two
dictionaries besides OED give the part of speech; adjectives get generated comparison only
when some dictionary attests comparison for them, nouns no dictionary counts as countable get
no plural, and neither does a plural listed as its own entry (a dictionary prints it "plural
noun", or it is another noun's plural), nor a verb's participle listed as its own entry. A regular form only one dictionary gives, beside an irregular form many give
for the same slot (goed beside went), is set aside as "nonstandard".

Writes inventories/data/inflections.db and inflections.tsv.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "inventories"))
from inventory import DATA, STRUCTURED  # noqa: E402
from inventory.inflect import SLOTS, regular  # noqa: E402
from inventory.inflection_io import _entries, _write, export_tsv  # noqa: E402
from inventory.irregulars import (SUPPLETIVE, _PLURAL_ENDING, looks_like_a_typo, past_shaped,  # noqa: E402
                                  plausible_irregular, supported_by_pattern)
from inventory.spelling import is_variant  # noqa: E402

INFLECTING = ("NOUN", "VERB", "ADJ", "ADV")
_LEMMA = re.compile(r"[a-z][a-z'-]*")
_IPA_TAIL = re.compile(r"/.*$")
_PAST_PART_SHAPE = re.compile(r"(?:n|en|ne|wn|un|ung|unk|um|ought|aught)$")
_PARTICIPLE_ONLY = re.compile(r"(?:en|wn)$")  # no English past ends so: proven, swollen, hewn, been


@dataclass(frozen=True)
class Found:
    form: str
    lemma: str
    upos: str
    slot: str          # an inflection slot, or "" for variant / derivative / contraction
    kind: str          # regular | irregular | variant | derivative | contraction
    region: str = ""


_ALTERNATIVES = re.compile(r"\s+(?:also|or)\s+|\s*或\s*|\s*[,;]\s*")
_ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\ufeff]")
HISTORICAL = frozenset({"oed"})  # its forms are historical spellings (quhyit = white), not inflections


def clean_forms(forms: list[str]) -> list[str]:
    """Split alternatives ("am/are", "x also y", "x or y", "x 或 y"), drop pronunciations glued on
    ("analyses/ənælɪsiːz/")."""
    out = []
    for printed in forms:
        for f in _ALTERNATIVES.split(_ZERO_WIDTH.sub("", printed).strip()):
            parts = [p.strip() for p in f.split("/")]
            if len(parts) > 1 and not all(re.fullmatch(r"[A-Za-z' -]+", p) for p in parts if p):
                parts = [_IPA_TAIL.sub("", f).strip()]  # a word then its pronunciation
            out += [p for p in parts if p]
    return list(dict.fromkeys(out))


def classify(lemma: str, upos: Iterable[str], forms: list[str], final_stress: bool | None) -> list[Found]:
    """Classify the forms a dictionary lists for one entry. upos is ordered as the entry prints
    its parts of speech (foot: noun, verb): an unmatched form goes to the first that fits it."""
    order = list(dict.fromkeys(upos))
    upos = set(order)
    out: list[Found] = []
    expected: dict[str, list[tuple[str, str, str]]] = defaultdict(list)  # form -> [(upos, slot, region)]
    for pos in upos & set(SLOTS):
        for stress in {final_stress, True, False}:  # recognise either doubling: the dictionary decides
            for slot, generated in regular(lemma, pos, stress).items():
                for form, region in generated:
                    if (pos, slot, region) not in expected[form]:
                        expected[form].append((pos, slot, region))
    pool: list[str] = []  # irregular verb forms awaiting Past / PastPart
    again: int | None = None  # where among them the lemma is printed again (ran, run; hurts, hurting, hurt)
    after_past = False        # ... right after the one irregular past printed since the -ing form (came, come)
    pooled = False
    ing_at = 0                # how many of them were printed before the last -ing form
    for i, form in enumerate(clean_forms(forms)):
        low = form.lower()
        follows_pooled, pooled = pooled, False
        if low == lemma:
            if again is None and i > 0 and form == lemma:  # not "Shadow", "ZIP": a capitalized use
                again, after_past = len(pool), follows_pooled and len(pool) - ing_at == 1
            continue
        if "'" in form or "’" in form:
            out.append(Found(form, lemma, "", "", "contraction"))
            continue
        if is_variant(low, lemma):
            out.append(Found(low, lemma, "", "", "variant"))
            continue
        if not _LEMMA.fullmatch(low):
            continue
        if (low, lemma) in SUPPLETIVE:
            pos, slots = SUPPLETIVE[(low, lemma)]
            out += [Found(low, lemma, pos, slot, "irregular") for slot in slots]
            continue
        if low in expected:
            out += [Found(low, lemma, pos, slot, "regular", region) for pos, slot, region in expected[low]]
            ing_at = len(pool) if any(slot == "PresPart" for _, slot, _ in expected[low]) else ing_at
            continue
        for pos in order:  # the entry's parts of speech in printed order: the first whose shape fits
            if pos == "NOUN" and _PLURAL_ENDING.search(low) and not low.endswith(("ing", "ed")):
                out.append(Found(low, lemma, "NOUN", "Plur", "irregular"))
            elif pos == "VERB" and low.endswith("ing"):
                out.append(Found(low, lemma, "VERB", "PresPart", "irregular"))
                ing_at = len(pool)
            elif pos == "VERB" and low.endswith("s") and low[:2] == lemma[:2] and len(low) <= len(lemma) + 3:
                out.append(Found(low, lemma, "VERB", "3Sg", "irregular"))
            elif pos == "VERB" and past_shaped(low, lemma):
                pool.append(low)
                pooled = True
            elif pos in ("ADJ", "ADV") and low.endswith("st"):
                out.append(Found(low, lemma, pos, "Sup", "irregular"))
            elif pos in ("ADJ", "ADV") and low.endswith(("er", "se", "ss", "re")):
                out.append(Found(low, lemma, pos, "Cmp", "irregular"))
            else:
                continue
            break
        else:
            out.append(Found(low, lemma, "", "", "derivative"))
    pasts = [f for f in out if f.upos == "VERB" and f.slot in ("Past", "PastPart")]
    # slots a suppletive form fills (went, was); a regular form is another way to say an irregular
    # one (goed, comed), and leaves the irregular forms their slots
    filled = {f.slot for f in pasts if f.kind == "irregular"}
    # The lemma among a verb entry's forms is an unchanged participle where it is printed right
    # after the entry's one irregular past (came, come; not "spat or spit", two pasts), and an
    # unchanged past or participle where nothing else fills those slots: no regular past (caused ...
    # cause, decarbonised ... decarbonize) and at most one other past form. First, it is the
    # entry's base form (OALD: run, runs, ran)
    alternatives = {a.lower() for printed in forms if len(group := clean_forms([printed])) > 1 for a in group}
    if again is not None and order[:1] == ["VERB"] and (after_past and lemma not in alternatives
                                                        or not pasts and len(pool) <= 1):
        if after_past and again > 1:
            # the past and the lemma as its participle printed after the -ing form, the forms
            # before it are other spellings of the verb (Chambers: rin, running, ran, run)
            out += [Found(f, lemma, "", "", "variant") for f in pool[:again - 1]]
            pool, again = pool[again - 1:], 1
        pool.insert(again, lemma)
    out += [Found(f, lemma, "VERB", slot, "irregular") for f, slot in _past_slots(pool, lemma, filled)]
    return out


def _past_slots(pool: list[str], lemma: str, filled: set[str]) -> list[tuple[str, str]]:
    """The Past / PastPart slots of the irregular verb forms an entry prints, in printed order;
    `filled` are the slots a suppletive form has (went, was). One form fills whichever of the two
    is open (went, gone: gone is no past), or both (taught). Of several, the first is the past
    unless that slot is filled (went, gone, gaun); after it, the lemma is the participle (ran, run;
    came, come), with the -n forms printed after it (bade, bid, bad, bidden); with no lemma, the
    -n forms are (began, begun; flew, flown), or all of them. A form the lemma grows into by -en or
    -wn is a participle only, alone too (proved, proven; being, been)."""
    if not pool:
        return []
    only = {f for f in pool if _PARTICIPLE_ONLY.search(f) and len(f) > len(lemma)}  # not ren, a spelling of run
    if len(pool) == 1:
        open_slots = [s for s in ("Past", "PastPart") if s not in filled] or ["Past", "PastPart"]
        return [(pool[0], slot) for slot in (["PastPart"] if pool[0] in only else open_slots)]
    rest = pool if "Past" in filled or pool[0] in only else pool[1:]
    if lemma in rest:
        participles = [lemma] + [f for f in rest[rest.index(lemma) + 1:] if _PAST_PART_SHAPE.search(f)]
    else:
        participles = [f for f in rest if _PAST_PART_SHAPE.search(f)] or rest
    return [(f, "PastPart" if f in participles or f in only else "Past") for f in pool]


def others_regular_forms(lemmas: Iterable[tuple[str, str]]) -> dict[str, set[str]]:
    """form -> the lemmas it is a regular inflection of (planned -> plan, feeders -> feeder)."""
    out: dict[str, set[str]] = defaultdict(set)
    for lemma, pos in lemmas:
        for forms in regular(lemma, pos).values():
            for form, _ in forms:
                out[form].add(lemma)
    return out


WIDELY_ATTESTED = 3  # dictionaries (historical spellings not counted) that make an irregular form trusted


# Zero plurals (sheep, deer, aircraft): ODE and its family write "same"; COBUILD lists the noun
# itself. Elsewhere the lemma among its own forms is only the base form (OALD: fish, fishes...).
LEMMA_AS_PLURAL = frozenset({"cobuild", "cobuild-ec"})


def classify_source(name: str, lemma: str, upos: Iterable[str], forms: list[str], final_stress: bool | None) -> list[Found]:
    """classify(), with each dictionary's conventions: historical spellings (OED) and zero plurals."""
    if name in HISTORICAL:
        return [Found(f.lower(), lemma, "", "", "historical") for f in clean_forms(forms) if f.lower() != lemma]
    upos = list(upos)
    nouns_only = "NOUN" in upos and not {"VERB", "ADJ", "ADV"} & set(upos)  # spread: a verb's base form
    zero = "NOUN" in upos and ("same" in forms or name in LEMMA_AS_PLURAL and lemma in forms and nouns_only)
    found = classify(lemma, upos, [f for f in forms if f != "same"], final_stress)
    return found + [Found(lemma, lemma, "NOUN", "Plur", "irregular")] if zero else found


def build(dbs: list[Path], out: Path) -> dict:
    attested: dict[tuple, set[str]] = defaultdict(set)   # (form, lemma, upos, slot, region, kind) -> dictionaries
    others: dict[tuple, set[str]] = defaultdict(set)     # (form, lemma, kind) -> dictionaries
    lemmas: dict[tuple, set[str]] = defaultdict(set)     # (lemma, upos) -> dictionaries
    stresses: dict[str, Counter] = defaultdict(Counter)
    mass: dict[str, list[bool]] = defaultdict(list)  # per dictionary: are all its noun senses uncountable?
    printed_plural: set[str] = set()  # some dictionary prints the lemma as a plural noun
    apart: dict[tuple, set[str]] = defaultdict(set)  # a participle printed as one, not a lone past read as both
    # first pass: every lemma's parts of speech, from all dictionaries: the pronouncing
    # dictionaries (cepd, lpd) list inflected forms but print no part of speech
    for db in dbs:
        for entry in _entries(db):
            lemma = entry.headword.strip()
            if not _LEMMA.fullmatch(lemma):
                continue
            upos = set(entry.order) & set(INFLECTING)
            for pos in upos:
                lemmas[(lemma, pos)].add(db.stem)
            if entry.final_stress is not None:
                stresses[lemma][entry.final_stress] += 1
            if "NOUN" in upos:
                mass[lemma].append(entry.mass_only)
            if entry.plural_noun:
                printed_plural.add(lemma)
    all_upos: dict[str, set[str]] = defaultdict(set)
    for lemma, pos in lemmas:
        all_upos[lemma].add(pos)
    for db in dbs:
        name = db.stem
        for entry in _entries(db):
            lemma = entry.headword.strip()
            if not entry.forms or not _LEMMA.fullmatch(lemma):
                continue
            upos = [p for p in entry.order if p in INFLECTING] or sorted(all_upos.get(lemma, set()))
            found = classify_source(name, lemma, upos, entry.forms, entry.final_stress)
            pasts = {f.form for f in found if f.upos == "VERB" and f.slot == "Past"}
            for f in found:
                if f.slot:
                    key = (f.form, f.lemma, f.upos, f.slot, f.region, f.kind)
                    attested[key].add(name)
                    if f.upos == "VERB" and f.slot == "PastPart" and f.form not in pasts:
                        apart[key].add(name)
                else:
                    others[(f.form, f.lemma, f.kind)].add(name)
    # POS evidence without OED, which lists every part of speech a word ever had
    supported = {k for k, names in lemmas.items() if len(names - HISTORICAL) >= 2}
    taken = others_regular_forms(supported)
    def strong_forms() -> set[tuple]:
        return {k[:4] for k, names in attested.items()
                if k[5] == "irregular" and len(names - HISTORICAL) >= WIDELY_ATTESTED
                and plausible_irregular(k[0], k[1], k[2], k[3], len(names - HISTORICAL))}

    # Another form many dictionaries give the slot: a regular one, an irregular past, or a
    # participle printed as one (not a past printed alone, read as both)
    widely = lambda names: len(names - HISTORICAL) >= WIDELY_ATTESTED
    rival = ({(k[1], k[3]) for k, names in attested.items() if k[2] == "VERB" and widely(names)
              and (k[5] == "regular" or k[3] == "Past")}
             | {(k[1], k[3]) for k, names in apart.items() if widely(names)})

    def doubtful(k: tuple, names: set[str], strong: set[tuple]) -> bool:
        n = len(names - HISTORICAL)
        thin = n < WIDELY_ATTESTED and (k[0], k[1]) not in SUPPLETIVE
        # the verb itself as its past or participle (run, run): two dictionaries that print it so, or
        # one for a verb in -t or -d, the shape of those that never change (cut, spread); and no rival
        # (see, see is no participle beside seen)
        unchanged = (k[0] == k[1] and k[2] == "VERB" and (n >= 2 or k[1].endswith(("t", "d")))
                     and (k[1], k[3]) not in rival)
        return (not plausible_irregular(k[0], k[1], k[2], k[3], n)
                or thin and bool(taken.get(k[0], {k[1]}) - {k[1]} or looks_like_a_typo(k[0], k[1], k[2], k[3])
                                 or not (unchanged or supported_by_pattern(k[0], k[1], k[2], k[3], strong))))

    # A past printed alone is read as the participle too (taught). Where the dictionaries that do
    # print a participle give the verb itself (ran, run; came, come), that reading is wrong for the
    # ones that print only the past (OALD: become, becomes, became): they stop attesting it. Many
    # dictionaries must say so: a few print a second participle so (spat; spit, spit)
    strong = strong_forms()
    unchanged = {k[1] for k, names in attested.items() if k[0] == k[1] and k[2:4] == ("VERB", "PastPart")
                 and k[5] == "irregular" and widely(names) and not doubtful(k, names, strong)}
    for k in [k for k in attested if k[1] in unchanged and k[0] != k[1] and k[2:4] == ("VERB", "PastPart")
              and k[5] == "irregular"]:
        attested[k] &= apart[k]
        if not attested[k]:
            del attested[k]
    strong = strong_forms()
    unclassified = [k for k, names in attested.items() if k[5] == "irregular" and doubtful(k, names, strong)]
    for k in unclassified:  # kept visible, not dropped: other(kind="unclassified")
        others[(k[0], k[1], "unclassified")] |= attested.pop(k)
    # a regular form one dictionary gives where many give an irregular one (goed beside went)
    strong_slots = {(k[1], k[2], k[3]) for k, names in attested.items()
                    if k[5] == "irregular" and len(names - HISTORICAL) >= WIDELY_ATTESTED}
    nonstandard = [k for k, names in attested.items()
                   if k[5] == "regular" and (k[1], k[2], k[3]) in strong_slots and len(names - HISTORICAL) <= 1]
    for k in nonstandard:
        others[(k[0], k[1], "nonstandard")] |= attested.pop(k)
    # generate regular forms for slots no dictionary attests
    have = {(k[1], k[2], k[3]) for k in attested}
    # a verb with an irregular past or participle gets no regular one for the other slot: misdrove
    # beside "misdrived", forthcame beside "forthcomed" (its participle, if no dictionary prints
    # it, stays unknown)
    strong_verbs = {k[1] for k in attested if k[2] == "VERB" and k[3] in ("Past", "PastPart") and k[5] == "irregular"}
    # a plural or a participle listed as its own entry inflects no further (biorhythms, subtitled),
    # unless dictionaries attest its own forms of that part of speech (feed beside fee/feed). A
    # noun in -s with no such evidence is taken as plural too (afteryears, aerobics), counted or
    # not: a singular in -s prints its plural (lens: lenses), and the only counted ones that do
    # not have none (schnapps, boerewors: not schnappses)
    own = {(k[1], k[2]) for k in attested}
    form_of_another = {(k[0], k[2], k[3]) for k in attested if k[0] != k[1]}
    plural_entries = printed_plural | others_regular_forms(k for k in supported if k[1] == "NOUN").keys()
    compared = {k[1] for k in attested if k[3] in ("Cmp", "Sup")}
    generated: dict[tuple, set[str]] = {}
    for (lemma, pos), names in lemmas.items():
        if pos not in SLOTS or (pos == "ADJ" and lemma not in compared) or (lemma, pos) not in supported:
            continue
        if pos == "NOUN" and mass[lemma] and all(mass[lemma]):  # information: no dictionary counts it
            continue
        if (lemma, pos) not in own and (
                pos == "NOUN" and (lemma in plural_entries or (lemma, "NOUN", "Plur") in form_of_another
                                   or re.search(r"[^suiaoe']s$", lemma))
                or pos == "VERB" and {(lemma, "VERB", "Past"), (lemma, "VERB", "PastPart")} & form_of_another):
            continue
        stress = stresses[lemma].most_common(1)[0][0] if stresses[lemma] else None
        for slot, forms in regular(lemma, pos, stress).items():
            if (lemma, pos, slot) in have or slot in ("Past", "PastPart") and lemma in strong_verbs:
                continue
            for form, region in forms:
                generated[(form, lemma, pos, slot, region, "regular")] = set()
    return _write(out, attested, generated, others, lemmas)


def main() -> None:
    dbs = sorted(STRUCTURED.glob("*.db"))
    if not dbs:
        sys.exit(f"no parsed dictionaries in {STRUCTURED} (scripts/build_corpus.py builds them)")
    summary = build(dbs, DATA / "inflections.db")
    export_tsv(DATA / "inflections.db", DATA / "inflections.tsv")
    print(json.dumps(summary, indent=1), file=sys.stderr)


if __name__ == "__main__":
    main()
