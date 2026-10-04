"""Measure the inventories' readers against hand-checked gold items.

    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/evaluate.py          # score
    PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/evaluate.py --sample # draw candidates

A gold item is a real input and the output it should give:

    notation     a printed phrase          -> its variants
    collocation  a raw collocation record  -> its patterns and relation
    label        a printed label           -> its (axis, value) pairs
    family       a derivative link         -> its relation
    kind         a phrase's canonical text -> its kind (idiom, phrasal_verb, pattern...)

Scoring runs today's code on the inputs, so the gold stays valid across rebuilds; a phrase's
kind depends on the whole build, so it is read from data/phrases.db (rebuild it first). The gold
quotes dictionaries, so it lives in data/gold/ (git-ignored). --sample writes candidates,
each expected output prefilled with today's output, to data/gold/candidates/; they become
gold once checked by hand and moved up one folder. It never overwrites gold.

Scoring prints the training gold (data/gold/*.jsonl), then each held-out set (data/gold/heldout,
heldout2) without the items whose input the training gold or an earlier held-out set also holds:
the rules were tuned on those.
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "inventories"), str(ROOT / "scripts")]
from inventory import DATA, STRUCTURED  # noqa: E402

GOLD = DATA / "gold"


# ---- today's output for one input ------------------------------------------------------

def notation_output(item: dict, ctx: dict) -> list[str]:
    from inventory.notation import parse
    return sorted(" ".join(v) for v in parse(item["printed"], item.get("headword", ""), ctx["evidence"]).variants)


def collocation_output(item: dict, ctx: dict) -> dict:
    from inventory.collocation_sources import Raw
    from inventory.collocations import base_pos, place
    from inventory.notation import parse
    raw = Raw(**item["raw"])
    if "examples" in item:  # an LDOCE corpus collocate: read as the reader reads it
        from inventory.collocation_sources import corpus_raw
        raw = corpus_raw(raw.base, raw.base_upos, raw.coll, raw.printed, raw.gloss, item["examples"], ctx["forms_of"])
    upos = base_pos(raw, ctx["pos_of"])
    placed = [p for v in parse(raw.printed, raw.base, ctx["evidence"]).variants
              if (p := place(raw, v, upos, ctx["pos_of"], ctx["lemmas"], ctx["forms_of"]))]
    return {"patterns": sorted({" ".join(p.pattern) for p in placed}),
            "relation": Counter(p.relation for p in placed).most_common(1)[0][0] if placed else ""}


def label_output(item: dict, _ctx: dict) -> list[str]:
    from inventory.labels import normalize
    return sorted(f"{l.axis}:{l.value}" for l in normalize(item["label"]))


def family_output(item: dict, ctx: dict) -> str:
    from inventory.families import relation
    return relation(item["base"], item["member"], ctx["words"], ctx["attested"].get(item["base"], frozenset()),
                    ctx["lemma_of"])


def kind_output(item: dict, ctx: dict) -> str:
    if "phrases" not in ctx:
        ctx["phrases"] = sqlite3.connect(f"file:{DATA / 'phrases.db'}?mode=ro", uri=True)
    rows = ctx["phrases"].execute("SELECT kind FROM phrase WHERE text = ?", (item["text"],)).fetchall()
    if len(rows) != 1:  # the phrase must still exist, once: a gold item that silently scores nothing is no gold
        raise LookupError(f"phrase {item['text']!r}: {len(rows)} rows in phrases.db")
    return rows[0][0]


OUTPUTS: dict[str, Callable[[dict, dict], object]] = {
    "notation": notation_output, "collocation": collocation_output, "label": label_output, "family": family_output,
    "kind": kind_output}


def context() -> dict:
    from inventory.families import lemma_index  # every lemma of each form, from a forms mapping
    from inventory.inflection_index import forms_index, pos_index
    from inventory.inflection_index import lemma_index as form_lemma_index  # form -> one lemma, from the database
    inflections = DATA / "inflections.db"
    con = sqlite3.connect(f"file:{inflections}?mode=ro", uri=True)
    words = frozenset(w for (w,) in con.execute("SELECT DISTINCT lemma FROM lemma WHERE n >= 2"))
    attested: dict[str, set[str]] = {}
    for form, lemma in con.execute("SELECT form, lemma FROM inflection WHERE source = 'attested'"):
        attested.setdefault(lemma, set()).add(form)
    con.close()
    from inventory.evidence import Evidence
    return {"evidence": Evidence(), "lemmas": form_lemma_index(inflections), "pos_of": pos_index(inflections),
            "forms_of": forms_index(inflections),
            "words": words, "attested": {k: frozenset(v) for k, v in attested.items()},
            "lemma_of": lemma_index(attested)}  # every lemma of a form, as families.py builds it


# ---- scoring ------------------------------------------------------------------------------

def score(items: list[dict], ctx: dict) -> dict:
    """{inventory: {"n", "right", "accuracy", "wrong": [(input, expected, got)]}}."""
    out: dict[str, dict] = {}
    for item in items:
        got = OUTPUTS[item["inventory"]](item["input"], ctx)
        expected = item["expected"]
        # a collocation is scored twice: its patterns, and its relation
        checks = ([(f"{item['inventory']}.{k}", expected[k], got[k]) for k in ("patterns", "relation")]
                  if item["inventory"] == "collocation" else [(item["inventory"], expected, got)])
        for name, want, have in checks:
            r = out.setdefault(name, {"n": 0, "right": 0, "wrong": []})
            r["n"] += 1
            if have == want:
                r["right"] += 1
            else:
                r["wrong"].append((item["input"], want, have))
    for r in out.values():
        r["accuracy"] = round(r["right"] / r["n"], 3)
    return out


def load(folder: Path) -> list[dict]:
    items = []
    for path in sorted(folder.glob("*.jsonl")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                item = json.loads(line)
                if not {"inventory", "input", "expected"} <= set(item) or item["inventory"] not in OUTPUTS:
                    raise ValueError(f"{path}:{n}: not a gold item (needs inventory, input, expected)")
                items.append(item)
    return items


# ---- drawing candidates -----------------------------------------------------------------------

# What makes two inputs the same input, whatever else an item records (a label's count of uses
# moves). A collocation is its source's record, not what reading it gave: an LDOCE corpus collocate
# drawn before its examples were stored unread carries the side they gave, and the words most of
# them put between it and the base ("cry" before "sleep"; "persist to this day")
_IDENTITY: dict[str, Callable[[dict], object]] = {
    "notation": lambda i: [i["printed"], i.get("headword", "")],
    "collocation": lambda i: {k: v for k, v in i["raw"].items() if k != "side"},
    "label": lambda i: i["label"], "family": lambda i: [i["base"], i["member"]], "kind": lambda i: i["text"]}
Known = dict[str, set[str]]  # inventory -> the identities of inputs drawn already


def _identity(inventory: str, item: dict) -> str:
    return json.dumps(_IDENTITY[inventory](item), ensure_ascii=False, sort_keys=True)


def _identities(inventory: str, item: dict) -> list[str]:
    """Every identity an input drawn earlier may stand for: an LDOCE collocate read with words
    between it and the base is any of the bare collocates that whole could have come from."""
    out = [_identity(inventory, item)]
    raw = item.get("raw", {}) if inventory == "collocation" else {}
    if raw.get("dictionary") == "ldoce" and not raw.get("side"):
        words, base = raw["printed"].split(), raw["base"].split()
        if words[:len(base)] == base:      # base, gap, collocate
            bare = [words[k:] for k in range(len(base) + 1, len(words))]
        elif words[-len(base):] == base:   # collocate, gap, base
            bare = [words[:k] for k in range(1, len(words) - len(base))]
        else:
            bare = []
        out += [_identity(inventory, {**item, "raw": {**raw, "printed": " ".join(b)}}) for b in bare]
    return out


def known_inputs(gold: Path, folder: Path) -> Known:
    """The inputs of every gold item under `gold` but the sample `folder` belongs to (its
    candidates and the gold checked from them, one folder up): a held-out sample must not
    repeat what the rules were tuned on, nor the training gold a held-out item. Files of
    other shapes (the kind and confusable samples) hold no gold items."""
    items = []
    for path in sorted(gold.rglob("*.jsonl")):
        if path.parent == folder.parent or path.is_relative_to(folder):
            continue
        items += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return _known(items)


def _known(items: list) -> Known:
    known: Known = defaultdict(set)
    for item in items:
        if isinstance(item, dict) and item.get("inventory") in _IDENTITY and "input" in item:
            known[item["inventory"]].update(_identities(item["inventory"], item["input"]))
    return known


def without_training(items: list[dict], training: list[dict]) -> tuple[list[dict], int]:
    """A held-out set's items but those whose input the training gold holds too (a label drawn
    again with a new count of uses, a collocate the training gold holds read): the rules were
    tuned on those, so they measure nothing held out. Returns the rest and how many were left out."""
    known = _known(training)
    kept = [i for i in items if _identity(i["inventory"], i["input"]) not in known.get(i["inventory"], set())]
    return kept, len(items) - len(kept)


def _fresh(inventory: str, items: list, known: Known | None, item: Callable = lambda x: x) -> list:
    seen = (known or {}).get(inventory, set())
    return [x for x in items if _identity(inventory, item(x)) not in seen]


def _phrase_inputs(rng: random.Random, k: int, known: Known | None = None) -> list[dict]:
    pool = []
    for db in sorted(STRUCTURED.glob("*.db")):
        if db.stem in ("oed", "etym", "peu", "cepd", "lpd", "ocd", "cobuild", "cobuild-ec"):
            continue
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        for headword, printed in con.execute("SELECT e.headword, s.phrase FROM s_sense s JOIN s_entry e "
                                             "ON e.entry_id = s.entry_id WHERE s.kind IN ('phrase', 'phrasal_verb') "
                                             "AND (s.phrase LIKE '%/%' OR s.phrase LIKE '%(%' OR s.phrase LIKE '% or %' "
                                             "OR s.phrase LIKE '%etc%' OR s.phrase LIKE '%或%')"):
            pool.append({"printed": printed, "headword": headword, "dictionary": db.stem})
        con.close()
    return rng.sample(_fresh("notation", pool, known), k)


def _collocation_item(raw) -> dict:
    """A collocation input: the record as its source gives it; an LDOCE corpus collocate with
    its examples, unread, so scoring reads them with today's code (collocation_output)."""
    from dataclasses import asdict
    from inventory.collocation_sources import Corpus
    if isinstance(raw, Corpus):
        return {"raw": asdict(raw.raw), "examples": list(raw.examples)}
    return {"raw": asdict(raw)}


def _collocation_inputs(rng: random.Random, k_per_source: int, ctx: dict, known: Known | None = None) -> list[dict]:
    from inventory import collocation_sources as sources
    unified = ROOT / "corpus" / "unified.db"
    streams = {"ocd": sources.ocd(STRUCTURED / "ocd.db"), "ldoce": sources.ldoce(unified, ctx["forms_of"], unread=True),
               "med": sources.med(unified), "ncecd": sources.ncecd(STRUCTURED / "ncecd.db")}
    out = []
    for name, stream in streams.items():
        pool = _fresh("collocation", [_collocation_item(r) for r in stream], known)
        out += rng.sample(pool, k_per_source)
    return out


def _label_uses() -> Counter[str]:
    from inventory.usage import LEFT_OUT
    uses: Counter[str] = Counter()
    for db in sorted(STRUCTURED.glob("*.db")):
        if db.stem in LEFT_OUT:
            continue
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        for (labels,) in con.execute("SELECT labels FROM s_sense WHERE labels != '[]'"):
            uses.update(json.loads(labels))
        con.close()
    return uses


def _weighted_sample(rng: random.Random, population: list, weights: list[float], k: int) -> list:
    """k different items, each drawn in proportion to its weight among those not yet drawn
    (Efraimidis and Spirakis): never fewer than k, as deduplicated draws with replacement can be."""
    if k > len(population):
        raise ValueError(f"cannot draw {k} from {len(population)}")
    ranked = sorted(((rng.random() ** (1 / w), i) for i, w in enumerate(weights)), reverse=True)
    return [population[i] for _, i in ranked[:k]]


def _label_inputs(rng: random.Random, k_weighted: int, k_tail: int, uses: Counter[str],
                  known: Known | None = None) -> list[dict]:
    labels = _fresh("label", list(uses), known, lambda l: {"label": l})
    chosen = _weighted_sample(rng, labels, [uses[l] for l in labels], k_weighted)
    tail = [l for l in labels if 5 <= uses[l] <= 300 and l not in chosen]
    return [{"label": l, "uses": uses[l]} for l in chosen + rng.sample(tail, k_tail)]


def _kind_inputs(rng: random.Random, k: int, known: Known | None = None) -> list[dict]:
    con = sqlite3.connect(f"file:{DATA / 'phrases.db'}?mode=ro", uri=True)
    texts = [{"text": t} for (t,) in con.execute("SELECT text FROM phrase ORDER BY text")]
    con.close()
    return rng.sample(_fresh("kind", texts, known), k)


def _family_inputs(rng: random.Random, k: int, known: Known | None = None) -> list[dict]:
    con = sqlite3.connect(f"file:{DATA / 'families.db'}?mode=ro", uri=True)
    rows = [{"base": b, "member": m, "dictionaries": json.loads(d)} for b, m, d in con.execute(
        "SELECT base, member, dictionaries FROM link WHERE relation NOT IN ('family', 'opposite')")]
    con.close()
    return rng.sample(_fresh("family", rows, known), k)


def sample(seed: int = 2026, folder: Path = GOLD / "candidates", scale: float = 1.0) -> None:
    ctx = context()
    rng = random.Random(seed)
    folder.mkdir(parents=True, exist_ok=True)
    known = known_inputs(GOLD, folder)
    k = lambda n: max(1, round(n * scale))
    drawn = {"notation": _phrase_inputs(rng, k(120), known), "collocation": _collocation_inputs(rng, k(30), ctx, known),
             "label": _label_inputs(rng, k(60), k(40), _label_uses(), known),
             "family": _family_inputs(rng, k(100), known), "kind": _kind_inputs(rng, k(120), known)}
    for inventory, inputs in drawn.items():
        path = folder / f"{inventory}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for item in inputs:
                expected = OUTPUTS[inventory](item, ctx)
                f.write(json.dumps({"inventory": inventory, "input": item, "expected": expected, "note": ""},
                                   ensure_ascii=False) + "\n")
        print(f"{path}: {len(inputs)} candidates")


def main() -> None:
    if "--sample" in sys.argv:
        sample()
        return
    if "--heldout" in sys.argv:  # a fresh sample, never used while changing the rules
        sample(seed=7, folder=GOLD / "heldout" / "candidates", scale=0.4)
        return
    if "--heldout2" in sys.argv:  # the second, drawn once the first had been used to fix rules
        sample(seed=11, folder=GOLD / "heldout2" / "candidates", scale=0.4)
        return
    items = load(GOLD)
    if not items:
        sys.exit(f"no gold items in {GOLD}: draw candidates with --sample, check them, move them there")
    ctx = context()
    print("dev")
    _report(score(items, ctx))
    tuned, earlier = items, []
    for name in HELD_OUT:
        if not (GOLD / name).is_dir():
            continue
        held = load(GOLD / name)
        kept, excluded = without_training(held, tuned)
        print(f"{name}: {excluded} of {len(held)} items left out, also in the training gold"
              + "".join(f" or {e}" for e in earlier))
        _report(score(kept, ctx))
        tuned, earlier = tuned + held, earlier + [name]


# Drawn with --heldout, --heldout2, in this order: each was used to fix rules before the next
# was drawn, so each is scored without the training gold and the sets before it
HELD_OUT = ("heldout", "heldout2")


def _report(scores: dict) -> None:
    for inventory, r in sorted(scores.items()):
        print(f"{inventory:12} {r['right']:>4}/{r['n']:<4} {r['accuracy']:.3f}")
        for given, expected, got in r["wrong"][:20 if "-v" in sys.argv else 0]:
            print(f"    {json.dumps(given, ensure_ascii=False)[:100]}\n      expected {expected}\n      got      {got}")


if __name__ == "__main__":
    main()
