"""Reading collocations from the dictionaries that list them, as raw records.

    OCD     the Oxford Collocations Dictionary (parsed layer): collocates under labels
            such as "VERB + DECISION", "ADJECTIVE", "used with these nouns as the object"
    LDOCE   its collocation pages (@collocations_<word>, raw HTML): collocations printed in
            full under headings (verbs, adjectives, phrases), collocations from other
            entries, and bare collocates from its corpus, grouped by part of speech
    MED     Macmillan's "Collocates" boxes (raw HTML): "Verbs frequently used with X as
            the object", "Nouns frequently used as objects of Y"
    NCECD   collocations among its examples (parsed layer), with Chinese

Each source says, in its own way, the collocate's part of speech and on which side of the
base it stands; a record keeps what the source says and nothing more. Reading the notation,
placing the base and naming the relation is inventory/collocations.py's work.
"""
from __future__ import annotations

import re
import sqlite3
import zlib
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from inventory.pos import normalize
from structured.markup import find, first, parse as parse_html, text

# The collocate's part of speech: a Universal POS tag, or one of these.
QUANT = "QUANT"      # "a drop of rain": … OF RAIN
PHRASE = "PHRASE"    # a phrase containing the base
UNTYPED = ""         # the source does not say


@dataclass(frozen=True)
class Raw:
    dictionary: str
    base: str        # the base as the source names it, lowercased
    base_upos: str   # "" when the source does not say
    coll: str        # the collocate's part of speech (see above); "ADJ|NOUN" when either
    side: str        # where the collocate stands when the text lacks the base: before | after | ""
    printed: str     # the collocate or the whole collocation, as printed
    gloss: str = ""
    zh: str = ""


@dataclass(frozen=True)
class Corpus:
    """A bare collocate from LDOCE's corpus before its examples are read (corpus_raw reads them):
    what the evaluation stores, so scoring re-reads the examples with today's code."""
    raw: Raw                     # side "", printed the bare collocate
    examples: tuple[str, ...]


# ---- OCD -----------------------------------------------------------------------------

_OCD_WORD = {"VERB": "VERB", "NOUN": "NOUN", "ADJECTIVE": "ADJ", "ADJ": "ADJ", "ADVERB": "ADV", "ADV": "ADV"}
_OCD_LABELS = {  # label -> (collocate, side, base part of speech when the entry does not say)
    "ADJECTIVE": ("ADJ", "before", "NOUN"),
    "PREPOSITION": ("ADP", "after", ""),
    "PHRASES": (PHRASE, "", ""),
    "ADVERB": ("ADV", "", ""),
    "VERBS": ("VERB", "before", "ADJ"),
    "used with these nouns": ("NOUN", "after", "ADJ"),
    "used with these nouns as the object": ("NOUN", "after", "VERB"),
    "used with these nouns as the subject": ("NOUN", "before", "VERB"),
    "used before these nouns": ("NOUN", "after", "NOUN"),
    "used after these nouns": ("NOUN", "before", "NOUN"),
    "used with these verbs": ("VERB", "", "ADV"),
    "used with these adjectives": ("ADJ", "after", "ADV"),
}
_OF = re.compile(r"^(?:…|\.\.\.)\s*OF\s+\S")


def ocd_label(label: str, base: str) -> tuple[str, str, str] | None:
    """(collocate, side, base part of speech) of an OCD label; None for notes and unknowns.

    "VERB + DECISION" -> VERB before; "DECISION + NOUN" -> NOUN after; "… OF RAIN" -> QUANT."""
    label = label.strip()
    if label in _OCD_LABELS:
        return _OCD_LABELS[label]
    if _OF.match(label):
        return QUANT, "before", "NOUN"
    if "+" in label:
        left, _, right = (s.strip() for s in label.partition("+"))
        heads = [h.strip() for h in re.split(r"[,/]", base) if h.strip()]  # "actor, actress"
        forms = {f.casefold() for h in heads for f in (h, h + "s", h + "es", re.sub("y$", "ies", h), *h.split())}

        def is_base(side: str, prefix: bool) -> bool:
            words = side.casefold().split()  # CLICHé: the label keeps the accent's case
            return bool(words) and (side.casefold() in forms or any(
                any(alt in forms or prefix and w.split("/")[0].startswith(f) for alt in w.split("/") for f in forms)
                for w in words if w not in ("a", "an", "the") and not (prefix and w.upper() in _OCD_WORD)))
        # a whole form first; a prefix only then, and never of a part-of-speech label
        # (ADJECTIVE + AD: "adjective" starts with "ad", and is not the base)
        readings = ((right, "after", left), (left, "before", right))  # (the other side, its side, the base's)
        other, side = next(((o, s) for prefix in (False, True) for o, s, b in readings if is_base(b, prefix)), ("", ""))
        word = other.split()[-1] if other else ""
        if word in _OCD_WORD and side:
            return _OCD_WORD[word], side, "NOUN"  # the entry's own part of speech overrides
    return None


def ocd(db: Path) -> Iterator[Raw]:
    with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as con:  # closed when a reader stops early too
        yield from _ocd(con)


def _ocd(con: sqlite3.Connection) -> Iterator[Raw]:
    rows = con.execute("""SELECT e.headword, s.pos, s.phrase, x.text FROM s_example x
                          JOIN s_sense s ON s.id = x.sense_id JOIN s_entry e ON e.entry_id = s.entry_id
                          WHERE x.kind = 'collocation' AND s.kind = 'collocation' ORDER BY x.sense_id, x.ord""")
    for headword, pos, label, printed in rows:
        base = headword.lower().strip()
        read = ocd_label(label, base)
        if read is None:
            continue
        coll, side, implied = read
        tags = normalize(pos).tags if pos.strip() and pos.strip() != "phr verb" else (
            {"VERB"} if pos.strip() == "phr verb" else set())
        base_upos = next(iter(tags)) if len(tags) == 1 else implied
        if label.strip() in ("VERBS", "ADVERB") and "ADJ" in tags:
            base_upos = "ADJ"
        yield Raw("ocd", base, base_upos, coll, side, printed)


# ---- LDOCE collocation pages -----------------------------------------------------------

_LDOCE_HEADINGS = {"verbs": "VERB", "adjectives": "ADJ", "nouns": "NOUN", "adverbs": "ADV",
                   "phrases": PHRASE, "phrase": PHRASE,
                   "verb": "VERB", "adjective": "ADJ", "noun": "NOUN", "adverb": "ADV"}
_LDOCE_SKIP = re.compile(r"common errors|collocations check", re.I)
_HOMOGRAPH = re.compile(r"_\d+$")
_WORD = re.compile(r"[a-z][a-z'-]*")


def ldoce_heading(heading: str, base: str) -> tuple[str, str] | None:
    """(collocate, side) of a heading on an LDOCE collocation page; None to skip the section.

    "verbs" -> VERB; "ADJECTIVES/NOUN + rain" -> ADJ|NOUN before; "rain + NOUN" -> NOUN after."""
    h = heading.strip()
    if _LDOCE_SKIP.search(h):
        return None
    if h.lower() in _LDOCE_HEADINGS:
        return _LDOCE_HEADINGS[h.lower()], ""
    if "+" in h:
        left, _, right = (s.strip() for s in h.partition("+"))
        other, side = (right, "after") if left.lower() == base else (left, "before") if right.lower() == base \
            else ("", "")
        tags = [_LDOCE_HEADINGS.get(w.lower().rstrip("s"), _LDOCE_HEADINGS.get(w.lower())) for w in other.split("/")]
        if other and all(tags):
            return "|".join(dict.fromkeys(tags)), side
    return UNTYPED, ""


_REFLEXIVE = frozenset("myself yourself himself herself itself ourselves yourselves themselves oneself".split())
_POSSESSIVE = frozenset("my your his her its our their".split())
_GRAMMATICAL = frozenset("oneself about across after against along among around as at before behind between by "
                         "down for from in into like of off on onto out over past round through to towards under "
                         "up upon with within without away back".split())
MAX_GAP = 3  # words between collocate and base worth keeping: "persist to this day", "cry out in his sleep"


def _slot(word: str) -> str:
    return "oneself" if word in _REFLEXIVE else "one's" if word in _POSSESSIVE else word


def order_in_examples(examples: list[str], base: frozenset[str],
                      collocate: frozenset[str]) -> tuple[str, tuple[str, ...]]:
    """Where the collocate stands in the corpus examples (before | after | ""), and the words
    between it and the base that most examples share, pronouns as slots: "cried herself to
    sleep" -> ("before", ("oneself", "to")). `base` and `collocate` are each word's forms."""
    sides: Counter[str] = Counter()
    gaps: dict[str, Counter[tuple[str, ...]]] = {"before": Counter(), "after": Counter()}
    for example in examples:
        pair = _nearest_pair(example, base, collocate)
        if pair is None:
            continue
        words, at, other = pair
        where = "before" if other < at else "after"
        sides[where] += 1
        lo, hi = sorted((at, other))
        if hi - lo - 1 <= MAX_GAP:
            gap = tuple(_slot(w) for w in words[lo + 1:hi])
            # only a preposition, particle or reflexive makes the words between part of the
            # collocation (persist to this day); a determiner or possessive varies (make a/make ~)
            gaps[where][gap if any(w in _GRAMMATICAL for w in gap) else ()] += 1
    if not sides:
        return "", ()
    where = sides.most_common(1)[0][0]
    ranked = gaps[where].most_common(2) + [((), 0), ((), 0)]  # fewer than two readings: pad
    (gap, votes), runner_up = ranked[0], ranked[1][1]
    # a dominant reading: more than one example, and most of them or twice the next reading
    shared = gap if votes >= 2 and (votes * 2 > sum(gaps[where].values()) or votes >= 2 * runner_up) else ()
    return where, shared


_SENTENCE = re.compile(r"[.;!?]+")


def _nearest_pair(example: str, base: frozenset[str],
                  collocate: frozenset[str]) -> tuple[list[str], int, int] | None:
    """The words of the sentence holding the closest base and collocate, and their positions;
    None when no sentence holds both ("Sleep matters; I cry myself to sleep": the second)."""
    best = None
    for sentence in _SENTENCE.split(example.lower()):
        words = _WORD.findall(sentence)
        ats = [i for i, w in enumerate(words) if w in base]
        others = [i for i, w in enumerate(words) if w in collocate]
        for at in ats:
            for other in others:
                if at != other and (best is None or abs(at - other) < abs(best[1] - best[2])):
                    best = (words, at, other)
    return best


def side_in_examples(examples: list[str], base: frozenset[str], collocate: frozenset[str]) -> str:
    """Where the collocate stands in the corpus examples, by majority: before | after | ""."""
    return order_in_examples(examples, base, collocate)[0]


def _ldoce_base_pos(con: sqlite3.Connection, base: str, homograph: str) -> str:
    row = con.execute("SELECT body FROM entry WHERE norm = ? AND dict_id = ? AND headword NOT LIKE '@%'",
                      (base, LDOCE_ID)).fetchone()
    if not row:
        return ""
    root = parse_html(zlib.decompress(row[0]).decode("utf-8", "replace"))
    entries = [e for e in find(root, "entry", "span") if e.get("id")]
    chosen = next((e for e in entries if homograph and e.get("id", "").endswith("_" + homograph)), None)
    chosen = chosen if chosen is not None else (entries[0] if entries else root)
    tags = normalize(text(first(chosen, "pos"))).tags
    return next(iter(tags)) if len(tags) == 1 else ""


LDOCE_ID, MED_ID = 2, 5  # dictionary ids in corpus/unified.db


def _following_examples(collocate) -> list:
    """The examples of a collocate: lxml closes the span before its div, making them a sibling."""
    after = collocate.getnext()
    return find(after, "example", "span") if after is not None and "content" in (after.get("class") or "") else []


def _forms(word: str, forms_of: dict[str, frozenset[str]]) -> frozenset[str]:
    return forms_of.get(word, frozenset()) | {word}


def ldoce_page(html: str, base: str, base_upos: str, forms_of: dict[str, frozenset[str]],
               unread: bool = False) -> Iterator[Raw | Corpus]:
    """The collocations of one @collocations_<word> page; with `unread`, a bare corpus
    collocate comes as a Corpus, its examples not yet read."""
    root = parse_html(html)
    for block in find(root, "entry", "span"):
        kind = block.get("type", "")
        if kind == "dictionary":  # from other entries: printed in full, no heading, any part of speech
            for c in find(block, "collocate", "span"):
                yield Raw("ldoce", base, "", UNTYPED, "", text(first(c, "colloc")))
            continue
        for section in find(block, "section", "span"):
            read = ldoce_heading(text(first(section, "secheading")), base)
            if read is None:
                continue
            coll, side = read
            for c in find(section, "collocate", "span"):
                printed = text(first(c, "colloc"))
                gloss = text(first(c, "collgloss")).strip(" (=)")
                if kind == "corpus_collos" and not side:  # a bare collocate: its examples show the order
                    examples = [text(e) for e in find(c, "example", "span") + _following_examples(c)]
                    yield Corpus(Raw("ldoce", base, base_upos, coll, "", printed, gloss), tuple(examples)) if unread \
                        else corpus_raw(base, base_upos, coll, printed, gloss, examples, forms_of)
                    continue
                yield Raw("ldoce", base, base_upos, coll, side, printed, gloss)
                for variant in find(c, "lexvar", "span"):  # keep a promise (also fulfil a promise)
                    yield Raw("ldoce", base, base_upos, coll, side, text(variant).strip(" ,"), gloss)


def corpus_raw(base: str, base_upos: str, coll: str, printed: str, gloss: str, examples: list[str],
               forms_of: dict[str, frozenset[str]]) -> Raw:
    """A bare collocate from LDOCE's corpus: its examples give the side, and the words most of
    them put between it and the base become part of the collocation ("persist to this day")."""
    where, gap = order_in_examples(examples, _forms(base, forms_of), _forms(printed, forms_of))
    if gap and where:
        whole = (printed, *gap, base) if where == "before" else (base, *gap, printed)
        return Raw("ldoce", base, base_upos, coll, "", " ".join(whole), gloss)
    return Raw("ldoce", base, base_upos, coll, where, printed, gloss)


def ldoce(unified: Path, forms_of: dict[str, frozenset[str]], unread: bool = False) -> Iterator[Raw | Corpus]:
    """Every LDOCE collocation page's collocations (`unread`: see ldoce_page)."""
    with closing(sqlite3.connect(f"file:{unified}?mode=ro", uri=True)) as con:
        yield from _ldoce(con, forms_of, unread)


def _ldoce(con: sqlite3.Connection, forms_of: dict[str, frozenset[str]], unread: bool) -> Iterator[Raw | Corpus]:
    pages = con.execute("SELECT headword, body FROM entry WHERE dict_id = ? AND headword LIKE '@collocations\\_%' "
                        "ESCAPE '\\' ORDER BY headword", (LDOCE_ID,)).fetchall()
    seen: set[Raw | Corpus] = set()
    for name, body in pages:
        html = zlib.decompress(body).decode("utf-8", "replace")
        m = re.search(r'id="entry_([^"]+)"', html) or re.search(r'id="corpus_collos_([^"]+)"', html)
        stem = name[len("@collocations_"):]
        homograph = _HOMOGRAPH.search(stem)
        base = _HOMOGRAPH.sub("", m.group(1) if m else stem).replace("_", " ").lower()
        base_upos = _ldoce_base_pos(con, base, homograph.group(0)[1:] if homograph else "")
        for raw in ldoce_page(html, base, base_upos, forms_of, unread):
            if raw not in seen:  # every homograph's page repeats the collocations from other entries
                seen.add(raw)
                yield raw


# ---- MED Collocates boxes ---------------------------------------------------------------

_MED_HEADER = re.compile(r"^(adjectives?|verbs?|nouns?|adverbs?) frequently used "
                         r"(?:(with)|as (objects|subjects) of) (.+?)(?:\s+as the (object|subject))?$", re.I)
_MED_WORD = {"adjective": "ADJ", "verb": "VERB", "noun": "NOUN", "adverb": "ADV"}


def med_header(header: str, entry_upos: str) -> tuple[str, str, str, str] | None:
    """(base, base part of speech, collocate, side) of a MED box header."""
    m = _MED_HEADER.match(" ".join(header.split()))
    if not m:
        return None
    word, _, role_of, base, role = (g.lower() if g else g for g in m.groups())  # OBJECTS, SUBJECT: any case
    coll = _MED_WORD[word.rstrip("s")]
    base = base.strip()
    if role_of:  # Nouns frequently used as objects of abandon: the base is a verb
        return base, "VERB", coll, "after" if role_of == "objects" else "before"
    # the header fixes the base's part of speech: adjectives and verbs taking it as object or
    # subject go with a noun; the entry's own is used only for adverbs and nouns "used with" it
    if coll in ("ADJ", "VERB"):
        base_upos = "NOUN"
    elif " " in base and entry_upos == "VERB":  # "Noun frequently used with call on": a phrasal verb
        base_upos = "VERB"
    else:
        base_upos = entry_upos
    if coll == "ADJ":
        side = "before"
    elif coll == "VERB":
        side = {"object": "before", "subject": "after"}.get(role or "", "before")
    elif coll == "NOUN":
        side = "after" if base_upos == "ADJ" else ""  # a verb's nouns: subjects or objects, it does not say
    else:
        side = ""
    return base, base_upos, coll, side


def med_entry(html: str) -> Iterator[Raw]:
    root = parse_html(html)
    head = first(root, "PART-OF-SPEECH", "span")
    tags = normalize(text(head)).tags if head is not None else set()
    entry_upos = next(iter(tags)) if len(tags) == 1 else ""
    for box in find(root, "sidebox", "div"):
        if not text(first(box, "ONEBOX-HEAD")).startswith("Collocates"):
            continue
        body = first(box, "sideboxbody")
        if body is None:
            continue
        header = body.text or ""
        for child in body:
            if "p" in (child.get("class") or "").split():
                read = med_header(header, entry_upos)
                if read:
                    base, base_upos, coll, side = read
                    for c in find(child, "ONE-COLLOCATE", "span"):
                        yield Raw("med", base, base_upos, coll, side, text(c))
                header = child.tail or ""
            else:
                header += text(child) + (child.tail or "")


def med(unified: Path) -> Iterator[Raw]:
    with closing(sqlite3.connect(f"file:{unified}?mode=ro", uri=True)) as con:
        for (body,) in con.execute("SELECT body FROM entry WHERE dict_id = ? ORDER BY id", (MED_ID,)):
            html = zlib.decompress(body).decode("utf-8", "replace")
            if "Collocates:" in html:
                yield from med_entry(html)


# ---- NCECD --------------------------------------------------------------------------------

def ncecd(db: Path) -> Iterator[Raw]:
    with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as con:
        rows = con.execute("""SELECT e.headword, s.pos, x.text, x.text_zh FROM s_example x
                              JOIN s_sense s ON s.id = x.sense_id JOIN s_entry e ON e.entry_id = s.entry_id
                              WHERE x.kind = 'collocation' ORDER BY x.sense_id, x.ord""")
        for headword, pos, printed, zh in rows:
            tags = normalize(pos).tags
            yield Raw("ncecd", headword.lower().strip(), next(iter(tags)) if len(tags) == 1 else "", UNTYPED, "",
                      printed.rstrip("…. "), zh=zh)
