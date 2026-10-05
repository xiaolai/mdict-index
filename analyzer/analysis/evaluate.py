"""Measure the analyzer's recall on the dictionaries' own examples.

    PYTHONPATH=scripts:analyzer .venv/bin/python analyzer/analysis/evaluate.py [--n 2000] [--misses 15]

Every example a dictionary prints under a phrase sense illustrates that phrase. So recall needs
no hand labels: does the analyzer find that very item (by its inventory id) in its own example?
Items are mapped from a sense to the inventory through the printed form both record.

Collocations have no such gold: what OCD prints under a collocation group are the collocates
themselves ("used before these nouns": grade, string, team), not sentences. They are judged by
precision on running text instead.

Three measures, each a share of the examples:

  exact    the item itself is among the analyzer's spans
  words    a span's matched variant has the words of one of the item's variants (slots aside):
           the right words, though under another inventory item (the inventories keep "bring
           out" beside "bring sth out", and file "switch on" under "switch sth on/off")
  matched  the item, or one of its variants, matched before overlaps were resolved: the
           matcher's own recall; the gap to "words" is a longer phrase winning the overlap

A miss is "not compiled" when the item has no pattern the analyzer can match (left out as
indistinct, or a single word), and "not found" when it has one and the example still did not
match: a form the patterns lack, a parse the slots reject, or an example that does not use the
phrase itself.

One caveat: the phrase readings were chosen with the help of these same examples
(inventory/evidence.py), which raises phrase recall a little.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "analyzer"), str(ROOT / "scripts")]
from analysis import INVENTORIES, SLOTS, load_nlp  # noqa: E402
from analysis.analyze import analyze_doc  # noqa: E402
from analysis.lexicon import load  # noqa: E402
from build_structured import STRUCTURED  # noqa: E402

KINDS = {"phrasal_verb": "phrase", "phrase": "phrase"}


def _printed_index(db: Path, table: str) -> dict[tuple[str, str], set[int]]:
    """(dictionary, printed form) -> the inventory ids that record it."""
    out: dict[tuple[str, str], set[int]] = defaultdict(set)
    with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as con:
        for iid, printed, dicts in con.execute(f"SELECT id, printed, dictionaries FROM {table}"):
            for p in json.loads(printed):
                for d in json.loads(dicts):
                    out[(d, p.strip())].add(iid)
    return out


def literal_words(tokens) -> str:
    """A pattern's words without its slots: "bring out {obj}" and "bring out" are the same words."""
    return " ".join(t.lstrip("~") for t in tokens if t not in SLOTS)


def gold(structured: Path = STRUCTURED, inventories: Path = INVENTORIES) -> tuple[list[dict], Counter]:
    """Every (example, the inventory ids it illustrates), and how many senses had no inventory item."""
    index = {"phrase": _printed_index(inventories / "phrases.db", "phrase")}
    rows, unmapped = [], Counter()
    for shard in sorted(structured.glob("*.db")):
        name = shard.stem
        with closing(sqlite3.connect(f"file:{shard}?mode=ro", uri=True)) as con:
            for kind, phrase, text in con.execute(
                    "SELECT s.kind, s.phrase, x.text FROM s_sense s JOIN s_example x ON x.sense_id = s.id "
                    "WHERE s.kind IN ('phrasal_verb', 'phrase') AND x.kind = 'example' AND x.text != ''"):
                source = KINDS[kind]
                ids = index[source].get((name, phrase.strip()))
                if not ids:
                    unmapped[source] += 1
                    continue
                rows.append({"dictionary": name, "kind": kind, "source": source, "ids": sorted(ids),
                             "phrase": phrase, "text": text})
    return rows, unmapped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000, help="examples sampled per kind")
    ap.add_argument("--misses", type=int, default=15, help="misses printed per kind")
    ap.add_argument("--seed", default="analyzer")
    ap.add_argument("--likely", action="store_true", help="count only the spans shown by default (confidence likely)")
    args = ap.parse_args()
    rows, unmapped = gold()
    by_kind = defaultdict(list)
    for r in rows:
        by_kind[r["kind"]].append(r)
    rng = random.Random(args.seed)
    sample = [r for kind in sorted(by_kind) for r in rng.sample(by_kind[kind], min(args.n, len(by_kind[kind])))]
    nlp, lex = load_nlp(), load(min_collocation_n=1)
    variants: dict[tuple[str, int], set[str]] = defaultdict(set)
    for ps in lex.by_anchor.values():
        for p in ps:
            variants[(p.item.source, p.item.source_id)].add(literal_words(p.tokens))
    for base, pairs in lex.by_base.items():
        for it, collocate in pairs:
            variants[(it.source, it.source_id)] |= {f"{collocate} {base}", f"{base} {collocate}"}
    compiled = set(variants)
    tally: dict[str, Counter] = defaultdict(Counter)
    per_dict: dict[tuple[str, str], Counter] = defaultdict(Counter)
    misses: dict[str, list[str]] = defaultdict(list)
    def hit(spans, wanted, words):
        return any((s["source"], s["source_id"]) in wanted or literal_words(s["variant"].split()) in words
                   for s in spans)
    for r, doc in zip(sample, nlp.pipe((r["text"] for r in sample), batch_size=256)):
        wanted = {(r["source"], i) for i in r["ids"]}
        words = set().union(*(variants.get(w, set()) for w in wanted))
        spans = [s for s in analyze_doc(doc, lex)["spans"] if not args.likely or s["confidence"] == "likely"]
        if any((s["source"], s["source_id"]) in wanted for s in spans):
            outcome = "exact"
        elif hit(spans, set(), words):
            outcome = "words"
        elif hit(analyze_doc(doc, lex, resolve_overlaps=False)["spans"], wanted, words):
            outcome = "matched"
        elif not compiled & wanted:
            outcome = "not compiled"
        else:
            outcome = "not found"
            if len(misses[r["kind"]]) < args.misses:
                misses[r["kind"]].append(f"{r['phrase']!r} in {r['text'][:110]!r}")
        tally[r["kind"]][outcome] += 1
        per_dict[(r["kind"], r["dictionary"])][outcome] += 1
    print(f"gold: {len(rows):,} examples mapped; senses without an inventory item: {dict(unmapped)}")
    for kind, c in sorted(tally.items()):
        total = sum(c.values())
        exact, words, matched = c["exact"], c["exact"] + c["words"], c["exact"] + c["words"] + c["matched"]
        print(f"{kind:13} of {total:,}: exact {exact / total:.1%}, words {words / total:.1%}, "
              f"matched {matched / total:.1%}; not found {c['not found']}, not compiled {c['not compiled']}")
    print("by dictionary (words):")
    for (kind, d), c in sorted(per_dict.items()):
        total = sum(c.values())
        if total >= 50:
            print(f"   {kind:13} {d:11} {(c['exact'] + c['words']) / total:.1%} of {total}")
    for kind, lines in sorted(misses.items()):
        print(f"not found, {kind}:")
        for line in lines:
            print("   ", line)


if __name__ == "__main__":
    main()
