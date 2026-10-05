"""Build every lexical inventory, in dependency order, stopping at the first failure.

    .venv/bin/python inventories/build.py [--from STEP] [--only STEP] [--dry-run] [--without-jev]

Needs layer 2 of the unified dictionary (scripts/build_corpus.py). Steps (all output under
inventories/data/, which is never committed)
  inflections    every inflected form and its lemma; the others use its lemmas and forms
  evidence       a full-text index of the dictionaries' examples, to read ambiguous notation with
  usage          usage labels and grammar patterns (labels.db, grammar.db)
  levels         word levels: CEFR, Oxford 3000/5000, frequency bands, ...
  families       word families and spelling variants
  phrases        idioms, phrasal verbs and other phrases, with their slots
  collocations   collocations by relation
  pronunciation  pronunciations by part of speech; stress across word families
  sameword       is a stress contrast one word or two? Asks jev; --without-jev tags every
                 contrast "uncertain" instead, and the database records that it did
  confusables    commonly misspelled and commonly confused words
  check          the invariants every inventory must hold
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the repository
PY = sys.executable
# (step, the files it writes under inventories/data/); each step's module is inventory/<step>.py
STEPS: list[tuple[str, tuple[str, ...]]] = [
    ("inflections", ("inflections.db", "inflections.tsv")),
    ("evidence", ("evidence.db",)),
    ("usage", ("labels.db", "grammar.db", "labels_unread.tsv")),
    ("levels", ("levels.db",)),
    ("families", ("families.db",)),
    ("phrases", ("phrases.db", "phrases.jsonl")),
    ("collocations", ("collocations.db",)),
    ("pronunciation", ("pronunciations.db",)),
    ("sameword", ("sameword_cache.json",)),  # and fills pronunciations.db's word_relation
    ("confusables", ("confusables.db",)),
    ("check", ()),
]
NAMES = [name for name, _ in STEPS]


def plan(start: str | None = None, only: str | None = None) -> list[str]:
    if only:
        return [only]
    return NAMES[NAMES.index(start):] if start else list(NAMES)


def command(step: str, without_jev: bool = False) -> list[str]:
    cmd = [PY, f"inventories/inventory/{step}.py"]
    if step == "sameword" and without_jev:
        cmd.append("--without-jev")
    return cmd


def missing_jev(steps: list[str], without_jev: bool, which=shutil.which) -> str | None:
    """Why the build cannot start, if it would reach sameword with no jev and no --without-jev."""
    if "sameword" not in steps or without_jev or which("jev"):
        return None
    return """jev is not installed. Nothing has been built yet.

The inventories use jev for one thing only: deciding whether a word whose stress moves with
its part of speech ("REcord" the noun, "reCORD" the verb) is one word or two. Every other
inventory comes out the same without it.

To build without jev, run the same command with --without-jev:

    .venv/bin/python inventories/build.py --without-jev

Those stress contrasts are then tagged "uncertain" instead of "same word" or "likely different
words", and the database records that it was built without jev. Answers jev gave before,
cached in inventories/data/sameword_cache.json, are still used."""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", choices=NAMES)
    ap.add_argument("--only", choices=NAMES)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--without-jev", action="store_true",
                    help="tag every stress contrast 'uncertain' instead of asking jev")
    args = ap.parse_args()
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_structured import STRUCTURED
    if not args.dry_run and not STRUCTURED.is_dir():
        sys.exit(f"{STRUCTURED} does not exist: build layer 2 first (scripts/build_corpus.py)")
    if not args.dry_run and (why := missing_jev(plan(args.start, args.only), args.without_jev)):
        sys.exit(why)
    for step in plan(args.start, args.only):
        cmd = command(step, args.without_jev)
        print(f"== {step}: {' '.join(cmd[1:])}", file=sys.stderr, flush=True)
        if not args.dry_run:
            subprocess.run(cmd, cwd=ROOT, check=True, env={**os.environ, "PYTHONPATH": "scripts:inventories"})


if __name__ == "__main__":
    main()
