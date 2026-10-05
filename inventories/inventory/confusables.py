"""Commonly misspelled words, and commonly confused words.

    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/confusables.py

Misspellings, from what the dictionaries say outright (raw entries in corpus/unified.db):

    learner_error   CALD's "Check your spelling! X is one of the 50 words most often spelled
                    wrongly by learners" (the Cambridge Learner Corpus), with its hint;
                    COBUILD's "Be careful with the spelling of this word"; Macmillan's "Get It
                    Right!" spelling boxes, the wrong forms taken from their ✗ sentences
    misspelling     "X is often misspelled as Y"; Chambers' "a misspelling of X"; a spelling
                    "regarded as an error" (miniscule)
    nonstandard     "a nonstandard spelling of X": spellings that represent speech ('nother)

Confusions, pairs of words the dictionaries tell learners apart, or that sound alike:

    which_word      OALD's Which Word? boxes (affect / effect)
    homophone       OALD's Homophones boxes (base | bass)
    confused        "Do not confuse X and Y", "X is often confused with Y", "not to be
                    confused with Y" in any dictionary; PEU's entries titled "X and Y"
    sound_alike     words the pronunciation inventory transcribes alike (weak vowels as one)
                    in two dictionaries or more, both common (in a level list: the Oxford
                    3000/5000, the Longman Communication 3000, Macmillan's stars, Collins'
                    top three frequency bands) and not spellings of one word

Needs data/inflections.db, data/levels.db, data/pronunciations.db. Writes
data/confusables.db (tables misspelling, confusable, confusable_set).
"""
from __future__ import annotations

import json
import re
import unicodedata
import sqlite3
import sys
import zlib
from collections import Counter
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from typing import Iterator, NamedTuple

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "inventories"), str(ROOT / "scripts")]
from inventory import DATA, PUBLISHER  # noqa: E402
from inventory.db import fresh_db  # noqa: E402
from inventory.inflection_index import inflection_words  # noqa: E402
from inventory.sound_alikes import sound_alikes  # noqa: E402
from inventory.spelling import is_variant  # noqa: E402

IDS = {"oald": 1, "ldoce": 2, "cobuild": 3, "cald": 4, "med": 5, "mwaled": 6, "mwc": 7, "mwu": 8, "ode": 9,
       "noad": 10, "ahd": 11, "ced": 12, "chambers": 13, "peu": 18, "odecn": 24}


class Misspelling(NamedTuple):
    dictionary: str
    word: str             # the correct spelling
    wrong: tuple          # wrong spellings, when the source gives them
    hint: str
    kind: str


class Confusion(NamedTuple):
    dictionary: str
    words: tuple
    kind: str
    note: str
    whole: bool = False   # every word must be a word of the dictionaries, or none is read (a PEU title)
    open_end: bool = False  # the last word may run on past the target ("with glum which ..."): see clean_words


def text_of(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).replace("&nbsp;", " ").replace("’", "'").replace("‘", "'").split())


# ---- misspellings ------------------------------------------------------------------------------

_CALD = re.compile(r"Check your spelling! ! ([\w'-]+) is one of the (\d+) words most often spelled wrongly by learners\."
                   r"(?: ! Remember: (.*?)(?= Common mistake|!| Ⅰ| Ⅱ|$))?")
_OFTEN_MISSPELLED = re.compile(r"([\w'-]+) is (?:often|frequently|commonly) (?:misspelled|misspelt) as ([\w'-]+)")
_NONSTANDARD = re.compile(r"(?:a )?nonstandard spelling of ((?:[\w']+ )*[\w']+\?|[\w'-]+)")  # "am I right?"; else one word
# Chambers: a run-on form with its part of speech ("idēˈalogue noun A misspelling of ideologue"), or an entry
# whose own headword opens it ("dispathy an obsolete misspelling of dyspathy"). Not an etymology's aside
# ("oll korrekt, a facetious misspelling of all correct"; "a misspelling of L pirus").
_MISSPELLING_OF = re.compile(r"([\w'ˈˌ-]+) (?:noun|adjective|verb|adverb)\s*(?:An? )?misspelling of ([\w'-]+)", re.I)
_MISSPELLING_ENTRY = re.compile(r"^([\w'ˈˌ-]+) (?:an? )?(?:obsolete |erroneous |common )?misspelling of ([\w'-]+)", re.I)
_REGARDED_ERROR = re.compile(r"(?:variant|spelling) of ([a-z][\w'-]+)[^.]{0,300}?regarded as an error", re.I)
_GET_IT_RIGHT = re.compile(r"Get It Right!: ([\w' -]+?) (.*?)(?=Get It Right!:|$)")


def misspellings(name: str, headword: str, text: str, lexicon: frozenset[str]) -> Iterator[Misspelling]:
    if name == "cald":
        for m in _CALD.finditer(text):
            yield Misspelling(name, m.group(1).lower(), (), (m.group(3) or "").strip(" !"), "learner_error")
    if name == "cobuild" and "careful with the spelling of this word" in text:
        yield Misspelling(name, headword.lower(), (), "", "learner_error")
    if name == "med":
        for m in _GET_IT_RIGHT.finditer(text):
            word, box = m.group(1).strip().lower(), m.group(2)[:900]
            if len(word) >= 3 and re.search(r"spell|written as (?:one|two) words?|double ‘|double '", box):
                yield Misspelling(name, word, _wrong_forms(word, box, lexicon), box[:160], "learner_error")
    for m in _OFTEN_MISSPELLED.finditer(text):
        yield Misspelling(name, m.group(1).lower(), (m.group(2).lower(),), "", "misspelling")
    if name != "chambers":
        for m in _NONSTANDARD.finditer(text[:400]):
            yield Misspelling(name, m.group(1).lower(), (headword.lower(),), "", "nonstandard")
    if name == "chambers":
        entry = _MISSPELLING_ENTRY.match(text.strip())
        found = [*_MISSPELLING_OF.finditer(text)]
        if entry and entry.group(1).lower() == headword.lower():
            found.append(entry)
        for m in found:
            if not re.search(r"(?:obsolete|Latin|Greek|from)\s*$", text[:m.start()][-25:]):
                wrong = "".join(ch for ch in unicodedata.normalize("NFKD", re.sub("[ˈˌ]", "", m.group(1)))
                                if not unicodedata.combining(ch)).lower()  # idēalogue -> idealogue
                yield Misspelling(name, m.group(2).lower(), (wrong,), "", "misspelling")
    if name in ("mwc", "mwu", "mwaled"):
        for m in _REGARDED_ERROR.finditer(text):
            yield Misspelling(name, m.group(1).lower(), (headword.lower(),), "", "misspelling")


def _wrong_forms(word: str, box: str, lexicon: frozenset[str]) -> tuple:
    """Wrong spellings a Get It Right! box shows: quoted ('independance') or in ✗ sentences,
    not words of the language, and close to the word."""
    found = re.findall(r"'([\w-]+)'", box)
    for bad in re.findall(r"✗ (.*?)(?=✓|✗|$)", box):
        found += re.findall(r"[A-Za-z][a-z-]+", bad)
    out = [w.lower() for w in found if w.lower() not in lexicon and w.lower() != word and w.lower()[:3] == word[:3]
           and SequenceMatcher(None, w.lower(), word).ratio() >= 0.8]  # happyness is not happy's
    return tuple(dict.fromkeys(out))


# ---- confusions ----------------------------------------------------------------------------------

_POS_WORD = r"(?:(?:the|this) (?:noun|verb|adjective|adverb|word|preposition|conjunction) )?"
_IPA = r"(?: /[^/]{1,30}/)?"
_DO_NOT = re.compile(rf"(?:Do not|Don't|not to|Take care not to) (?:confuse|mix up) {_POS_WORD}([\w' -]{{1,40}}?){_IPA} "
                     rf"(?:and|with) {_POS_WORD}(?:to )?([\w' -]{{1,40}}?){_IPA}(?=\s*[.,;:(=]| 。|$)")
_DIFFERENCE = re.compile(r"(?:explanation of|On|For) the difference(?:s)? between ([\w'-]+) and ([\w'-]+)")
_CHOOSE = re.compile(r"Common mistake : ([\w'-]+) or ([\w'-]+)\? ! Warning: Choose the right word")
_BOTH_CONFUSED = re.compile(r"([\w'-]+) and ([\w'-]+) are (?:often |frequently |sometimes |commonly |easily )?confused")
_DO_NOT_WITH = re.compile(r"Do not confuse with (?:the (?:noun|verb|adjective|adverb),? )?([\w' -]{1,40}?)(?=\s*[.,;:(]|$)")
# "confused with the ..." names a word only through a word-class phrase ("the verb affect", "the
# similar-sounding word ..."); "is often confused with the oak apple gall" is about things, not words.
_OFTEN = re.compile(r"([\w'-]+) (?:is|are) (?:often |frequently |sometimes |commonly )?confused with "
                    r"(?:(?:the )?(?:similar-sounding )?(?:words? |verb |noun |adjective ))?(?!the |a |an )"
                    r"([\w'-]+)(?: and ([\w'-]+))?")
_NOT_TO_BE = re.compile(r"(?:should not|not to) be confused with (?:the )?(?:words? |verb |noun |adjective )?"
                        r"([\w'-]+(?: [\w'-]+)?)")
_FUNCTION = frozenset("your you the a an this that it them him her his my our their reader readers people anyone "
                      "someone something and or nor".split())  # "... and are sometimes confused with": a lost subject


_EXAMPLE = re.compile(r'<(span|li|div|em|i)[^>]*class="(?:x|unx|example|examples|exa|eg|EXAMPLE|ex|cit|quote|'
                      r'colloexa|exampleGroup|sentence|vi|ex-sent)(?:[ "][^>]*)?>')
LEARNERS = frozenset({"oald", "ldoce", "cald", "cobuild", "med", "mwaled"})
_ANAPHOR = re.compile(r"^(?:this|that|the) (?:noun|verb|adjective|adverb|word|preposition|conjunction)s?$")


def notes_text(html: str) -> str:
    """An entry's text without its example sentences: confusion warnings live in notes."""
    return text_of(_drop_examples(html))


def _drop_examples(html: str) -> str:
    """The html without its example elements, each up to its own closing tag: an example
    holds tags of its own (<span class="x"><span class="hl">..</span> ..</span>). An example
    never closed is kept, as a regular expression would keep it."""
    out, pos = [], 0
    while m := _EXAMPLE.search(html, pos):
        tag = re.compile(rf"<(/?){m.group(1)}\b[^>]*>", re.I)
        depth, end = 1, None
        for t in tag.finditer(html, m.end()):
            depth += -1 if t.group(1) else 1
            if depth == 0:
                end = t.end()
                break
        if end is None:
            out.append(html[pos:m.end()])
            pos = m.end()
            continue
        out.append(html[pos:m.start()] + " ")
        pos = end
    return "".join(out) + html[pos:]


def confusions(name: str, headword: str, html: str, text: str) -> Iterator[Confusion]:
    if name == "oald":
        for kind, sep in (("which_word", "/"), ("homophone", "|")):
            for m in re.finditer(rf'unbox="{kind}"[^>]*>\s*<span class="box_title"[^>]*>[^<]*<span class="closed">'
                                 rf'([^<]*)</span>', html):
                words = tuple(w.strip().lower() for w in m.group(1).split(sep) if w.strip())
                if len(words) >= 2:
                    yield Confusion(name, words, kind, "")
    if name == "peu" and (m := re.search(r'<span class="institle">(.*?)</span>', html)) \
            and (words := peu_title(text_of(m.group(1)))):  # the printed title: its commas are gone from the headword
        section = m.group(1) if (m := _PEU_SECTION.search(html)) else ""
        # a list only where PEU sets words side by side ("allow , permit and let"); in the grammar
        # chapters a list is a topic ("manner, place and time"), and "ie and ei" is spelling
        topic = section != _PEU_WORDS and (len(words) > 2 or all(w.endswith("s") and len(w) > 3 for w in words))
        if not topic and "spelling" not in section:  # "instructions and requests : will, would …" is a topic
            yield Confusion(name, words, "confused", headword, whole=True)
    if name == "chambers" or not re.search(r"confus|differences? between|Choose the right word|mix up", text, re.I):
        return
    text = notes_text(html) if html else text
    for m in _DO_NOT.finditer(text):
        a = m.group(1).lower()
        a = headword.lower() if _ANAPHOR.match(a) else a   # "Do not confuse this verb with lose"
        yield Confusion(name, (a, m.group(2).lower()), "confused", text[m.start():m.start() + 120])
    for m in re.finditer(r"Do not confuse this (?:noun|verb|adjective|adverb|word) with (?:to |the )?([\w'-]+)", text):
        yield Confusion(name, (headword.lower(), m.group(1).lower()), "confused", text[m.start():m.start() + 120])
    if name == "cald":
        for m in _DO_NOT_WITH.finditer(text):
            yield Confusion(name, (headword.lower(), m.group(1).lower()), "confused", text[m.start():m.start() + 120])
    for pattern in (_DIFFERENCE, _CHOOSE, _BOTH_CONFUSED):
        for m in pattern.finditer(text):
            yield Confusion(name, (m.group(1).lower(), m.group(2).lower()), "confused", text[m.start():m.start() + 120])
    for m in _OFTEN.finditer(text):
        words = tuple(w.lower() for w in m.groups() if w)
        if words[0] in ("which", "that", "who", "word", "words", "it", "this", "verb", "noun", "adjective"):
            words = (headword.lower(), *words[1:])  # "which is often confused with glumate": the headword
        yield Confusion(name, words, "confused", text[m.start():m.start() + 120])
    if name in LEARNERS:  # elsewhere "not to be confused with" draws encyclopedic lines (Austin vs Black Friars)
        for m in _NOT_TO_BE.finditer(text):
            yield Confusion(name, (headword.lower(), m.group(1).lower()), "confused",
                            text[max(0, m.start() - 40):m.start() + 100], open_end=True)


_PEU_SECTION = re.compile(r'<span class="l1"[^>]*>\s*<a class="Ref" href="entry://([^"]+)"')
_PEU_WORDS = "word problems from a to z introduction"
_GRAMMAR_TERMS = frozenset("noun nouns verb verbs adjective adjectives adverb adverbs adverbials pronoun pronouns "
                           "preposition prepositions conjunction conjunctions determiner determiners quantifiers "
                           "subjects objects complements prefixes suffixes comparatives superlatives infinitives "
                           "clauses sentences plurals".split())  # a title naming grammar terms is a topic, not a confusion


def peu_title(headword: str) -> tuple[str, ...] | None:
    """The words a PEU entry title sets side by side: "allow , permit and let", "continual(ly)
    and continuous(ly)", "end and finish : verbs". Not a grammar chapter ("Be , have and do
    introduction"); a topic ("comparative and superlative adjectives") fails as a whole later,
    when one of its parts is not a word."""
    if re.search(r"[A-Z]|introduction", headword):
        return None
    text = re.sub(r"\([^)]*\)", "", headword.split(" : ")[0])  # alternate(ly), (a)round, back (adverb); ": verbs"
    words = tuple(" ".join(w.split()) for w in re.split(r"\s*(?:,|;|/|\band\b)\s*", text))
    if len(words) < 2 or any(not w or w.startswith("-") or len(w) < 2 or "etc" in w.split() or len(w.split()) > 3
                             for w in words):
        return None  # "-ise and -ize", "ch , tch , k and ck": spellings, not words; "north , northern etc"
    return words


def clean_words(words: tuple, lexicon: frozenset[str], free_text: bool = True, open_end: bool = False) -> tuple:
    """Words a learner could confuse: known to the dictionaries; from free text, not pronouns
    or "your reader" ("Do not confuse your reader with jargon"). Boxes and transcriptions
    name words on purpose, so their/there and its/it's stay. With `open_end` the last word was
    read up to a word too far ("confused with glum which ..."): its longest start the
    dictionaries know is the word."""
    out = []
    for n, w in enumerate(words):
        w = re.sub(r"^(?:the|a|an|to) ", "", w.strip(" ")) if free_text else w.strip()
        if open_end and n == len(words) - 1 and w not in lexicon:
            parts = w.split()
            w = next((" ".join(parts[:k]) for k in range(len(parts) - 1, 0, -1) if " ".join(parts[:k]) in lexicon), w)
        if w and w not in _GRAMMAR_TERMS and not (free_text and (w in _FUNCTION or set(w.split()) & _FUNCTION)) \
                and len(w.split()) <= 3 and not re.search(r"\d", w) and w in lexicon:
            out.append(w)
    return tuple(dict.fromkeys(out))


# ---- build -------------------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE misspelling (word TEXT NOT NULL, wrong TEXT NOT NULL, hint TEXT NOT NULL, kind TEXT NOT NULL,
  dictionaries TEXT NOT NULL, n INTEGER NOT NULL);
CREATE TABLE confusable (word_a TEXT NOT NULL, word_b TEXT NOT NULL, kinds TEXT NOT NULL, dictionaries TEXT NOT NULL,
  n INTEGER NOT NULL, publishers INTEGER NOT NULL, note TEXT NOT NULL);
CREATE TABLE confusable_set (words TEXT NOT NULL, kind TEXT NOT NULL, dictionary TEXT NOT NULL);
CREATE INDEX confusable_a ON confusable(word_a);
CREATE INDEX confusable_b ON confusable(word_b);
"""


def build(spellings: list[Misspelling], confusables: list[Confusion], lexicon: frozenset[str], out: Path) -> dict:
    by_word: dict[tuple, dict] = {}
    for s in spellings:
        if s.word not in lexicon:
            continue  # a misread: not a word of the dictionaries
        row = by_word.setdefault((s.word, s.kind), {"wrong": [], "hint": "", "dictionaries": set()})
        row["wrong"] += [w for w in s.wrong if w not in row["wrong"] and w != s.word]
        row["hint"] = row["hint"] or s.hint
        row["dictionaries"].add(s.dictionary)
    pairs: dict[tuple, dict] = {}
    sets = set()
    for c in confusables:
        words = clean_words(c.words, lexicon, free_text=c.kind == "confused" and not c.whole, open_end=c.open_end)
        if len(words) < 2 or c.whole and len(words) < len(set(c.words)):
            continue
        if len(words) > 2:
            sets.add((json.dumps(sorted(words)), c.kind, c.dictionary))  # PEU files one set under each word
        for a, b in combinations(sorted(words), 2):
            if a == b or (c.kind == "sound_alike" and is_variant(a, b)):
                continue  # a dictionary that names two words as confused is not overruled: ensure/insure
            row = pairs.setdefault((a, b), {"kinds": set(), "dictionaries": set(), "note": ""})
            row["kinds"].add(c.kind)
            row["dictionaries"].add(c.dictionary)
            row["note"] = row["note"] or c.note
    with fresh_db(out, SCHEMA) as con:
        nonstandard = {w for (_, k), r in by_word.items() if k == "nonstandard" for w in r["wrong"]}
        by_word = {(w, k): r for (w, k), r in by_word.items() if not (k == "nonstandard" and w in nonstandard)}
        for (word, kind), r in sorted(by_word.items()):  # (youse as "nonstandard spelling of youse": left out)
            dicts = sorted(r["dictionaries"])
            con.execute("INSERT INTO misspelling VALUES (?,?,?,?,?,?)",
                        (word, json.dumps(r["wrong"]), r["hint"], kind, json.dumps(dicts), len(dicts)))
        for (a, b), r in sorted(pairs.items()):
            dicts = sorted(r["dictionaries"])
            con.execute("INSERT INTO confusable VALUES (?,?,?,?,?,?,?)",
                        (a, b, json.dumps(sorted(r["kinds"])), json.dumps(dicts), len(dicts),
                         len({PUBLISHER.get(d, d) for d in dicts}), r["note"]))
        con.executemany("INSERT INTO confusable_set VALUES (?,?,?)", sorted(sets))
    kinds = Counter(k for r in pairs.values() for k in r["kinds"])
    return {"misspellings": len(by_word), "misspelling_kinds": dict(Counter(k for _, k in by_word)),
            "confusable_pairs": len(pairs), "pair_kinds": dict(kinds), "sets": len(sets)}


def lexicon_of(inflections_db: Path, unified: Path) -> frozenset[str]:
    words = inflection_words(inflections_db)
    con = sqlite3.connect(f"file:{unified}?mode=ro", uri=True)  # not PEU's lists: "allow permit and let" is no word
    words |= {n for (n,) in con.execute("SELECT DISTINCT norm FROM entry WHERE dict_id != ? OR norm NOT LIKE '% and %'",
                                        (IDS["peu"],))}
    con.close()
    return frozenset(w.lower() for w in words)


def common_words(levels_db: Path) -> frozenset[str]:
    con = sqlite3.connect(f"file:{levels_db}?mode=ro", uri=True)
    rows = con.execute("SELECT DISTINCT word FROM level WHERE scheme IN ('oxford3000', 'oxford5000', 'core', 'stars') "
                       "OR (scheme = 'frequency_band' AND CAST(value AS INTEGER) >= 3)")
    out = frozenset(w for (w,) in rows if w.replace("'", "").isalpha())
    con.close()
    return out


def main() -> None:
    unified = ROOT / "corpus" / "unified.db"
    lexicon = lexicon_of(DATA / "inflections.db", unified)
    con = sqlite3.connect(f"file:{DATA / 'families.db'}?mode=ro", uri=True)
    variants = {frozenset((a, b)) for a, b in con.execute("SELECT word, variant FROM variant")}
    con.close()
    spellings: list[Misspelling] = []
    confusables: list[Confusion] = []
    con = sqlite3.connect(f"file:{unified}?mode=ro", uri=True)
    for name, dict_id in IDS.items():
        for headword, body in con.execute("SELECT headword, body FROM entry WHERE dict_id = ? AND headword NOT LIKE "
                                          "'@%'", (dict_id,)):
            html = zlib.decompress(body).decode("utf-8", "replace")
            text = text_of(html)
            spellings += misspellings(name, headword, text, lexicon)
            confusables += confusions(name, headword, html, text)
    con.close()
    confusables += (Confusion(d, words, "sound_alike", "")
                    for d, words in sound_alikes(DATA / "pronunciations.db", common_words(DATA / "levels.db"), variants))
    print(json.dumps(build(spellings, confusables, lexicon, DATA / "confusables.db"), indent=1))


if __name__ == "__main__":
    main()
