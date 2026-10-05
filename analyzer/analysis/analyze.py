"""Analyse English text: every word's lemma, level, labels and flags; every phrase and collocation.

The result is plain data (JSON-ready), with character offsets into the text as given:

  sentences  [start, end] of each sentence
  tokens     per token: text, offsets, part of speech, lemma, and for words the CEFR level and
             every level scheme, usage labels, words it is often confused with, and spelling
             flags (a known misspelling, or an unknown word with suggestions)
  spans      per phrase or collocation: what it is (kind, the inventory's text, relation,
             evidence, labels, definitions; the variant that matched, which may differ from the
             item's name: "switch on" matches the entry printed "switch sth on/off"); the
             character ranges of its own words, more than
             one when something comes between them ("gave" ... "up" in "gave it up"); and its
             extent, slots included ("gave it up"); and a confidence, "likely" or "possible"
             (match.confidence): a verb with a preposition may be literal, "standing in his boat"
"""
from __future__ import annotations

import string

from analysis import BASE, FUNCTION_WORDS
from analysis.lexicon import Lexicon
from analysis.match import Tok, confidence, match_collocations, match_patterns, resolve

MAX_CHARS = 200_000       # one call; longer text is the caller's to split
_LETTERS = frozenset(string.ascii_lowercase)


def _lemmas(t, lex: Lexicon) -> tuple[str, frozenset[str]]:
    """The token's lemma, and every lemma it may stand for in a pattern. The inventories' lemmas
    for this form in the part of speech spaCy tagged come first; spaCy's lemma when they have
    none in that part of speech."""
    lower = t.lower_.replace("’", "'")
    known = lex.forms.get(lower, [])
    same = [k for k in known if k[1] == t.pos_]
    spacy_lemma = t.lemma_.lower().replace("’", "'")
    chosen = max(same, key=lambda k: k[2])[0] if same else spacy_lemma
    return chosen, frozenset({lower, spacy_lemma, chosen, *(k[0] for k in (same or known))})


def edits1(word: str) -> set[str]:
    """Every string one deletion, transposition, replacement or insertion away."""
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    return ({a + b[1:] for a, b in splits if b}
            | {a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1}
            | {a + c + b[1:] for a, b in splits if b for c in _LETTERS}
            | {a + c + b for a, b in splits for c in _LETTERS})


def suggestions(word: str, lex: Lexicon, limit: int = 3) -> list[str]:
    """Known forms one edit away, best attested first."""
    found = [(max(n for _, _, n in lex.forms[w]), w) for w in edits1(word) if w in lex.forms and w != word]
    return [w for _, w in sorted(found, key=lambda x: (-x[0], x[1]))[:limit]]


EDITORIAL = frozenset({"confused", "which_word"})  # a dictionary's own warning, not a computed sound-alike


def notable(confusion: dict) -> bool:
    """A confusion worth pointing out in running text: a dictionary's warning that two dictionaries
    give, or an OALD Which Word? box."""
    kinds = set(confusion["kinds"])
    return "which_word" in kinds or (bool(kinds & EDITORIAL) and confusion["n"] >= 2)


def _word(t, lemma: str, lex: Lexicon) -> dict:
    """What the inventories say about one word: its levels and labels in the part of speech it has
    here (pos-less schemes such as frequency bands added), and the words it is confused with."""
    lower = t.lower_.replace("’", "'")
    info = lex.words.get((lemma, t.pos_)) or {}
    posless = lex.words.get((lemma, "")) or {}
    out: dict = {}
    if info or posless:
        out["cefr"] = info.get("cefr", "")
        out["levels"] = {**posless.get("levels", {}), **info.get("levels", {})}
        out["labels"] = info.get("labels", [])
    if lemma in lex.confusables:
        out["confusable"] = [{**c, "notable": notable(c) and lemma not in FUNCTION_WORDS}
                             for c in lex.confusables[lemma]]
    flags = []
    if lower in lex.misspellings:
        flags += [{"kind": "misspelling", "word": m["word"], "source": m["kind"], "hint": m["hint"]}
                  for m in lex.misspellings[lower]]
    elif (lower.isalpha() and len(lower) > 2 and not lex.known(lower) and lower not in FUNCTION_WORDS
          and t.pos_ not in ("PROPN", "X") and not t.is_upper and not t.like_url and not t.like_email):
        flags.append({"kind": "unknown", "suggestions": suggestions(lower, lex)})
    if flags:
        out["flags"] = flags
    return out


def _span(m, sent: list[Tok], offset: int) -> dict:
    item = m.item
    ranges: list[list[int]] = []
    for i in m.literals:
        t = sent[i]
        if ranges and i - 1 in m.literals:
            ranges[-1][1] = t.end
        else:
            ranges.append([t.start, t.end])
    return {"source": item.source, "source_id": item.source_id, "kind": item.kind, "id": item.id, "text": item.text,
            "variant": " ".join(t.lstrip(BASE) if t != BASE else t for t in m.variant), "base": item.base,
            "confidence": confidence(item, m.variant, m.literals, sent),
            "relation": item.relation, "n": item.n, "publishers": item.publishers, "labels": list(item.labels),
            "definition": item.definition, "definition_zh": item.definition_zh,
            "tokens": [offset + i for i in m.tokens], "ranges": ranges,
            "extent": [sent[m.tokens[0]].start, sent[m.tokens[-1]].end]}


def analyze(text: str, nlp, lex: Lexicon) -> dict:
    if len(text) > MAX_CHARS:
        raise ValueError(f"{len(text):,} characters: analyse at most {MAX_CHARS:,} at a time")
    return analyze_doc(nlp(text), lex)


def analyze_doc(doc, lex: Lexicon, resolve_overlaps: bool = True) -> dict:
    """The analysis of text spaCy has already parsed (nlp.pipe parses many at once). Without
    resolve_overlaps every match is kept, overlapping or not (for measuring the matcher)."""
    tokens, spans, sentences = [], [], []
    for s in doc.sents:
        sentences.append([s.start_char, s.end_char])
        sent: list[Tok] = []
        for t in s:
            lemma, lemmas = _lemmas(t, lex)
            sent.append(Tok(t.i - s.start, t.text, t.lower_, t.idx, t.idx + len(t.text), t.pos_, t.tag_, t.dep_,
                            t.head.i - s.start, lemma, lemmas, t.is_punct or t.is_space))
            entry = {"i": t.i, "text": t.text, "start": t.idx, "end": t.idx + len(t.text), "pos": t.pos_,
                     "lemma": lemma}
            if t.is_alpha:
                entry.update(_word(t, lemma, lex))
            tokens.append(entry)
        found = match_patterns(sent, lex) + match_collocations(sent, lex)
        found = resolve(found) if resolve_overlaps else found
        spans += [_span(m, sent, s.start) for m in sorted(found, key=lambda m: (m.tokens[0], -len(m.tokens)))]
    return {"sentences": sentences, "tokens": tokens, "spans": spans}
