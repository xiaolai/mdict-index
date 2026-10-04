"""Build the English-Chinese parallel corpus of example sentences, in order, stopping at the first failure.

    .venv/bin/python parallel_corpus/build.py [--from STEP] [--only STEP] [--dry-run]

Steps (all output under parallel_corpus/data/, which is never committed)
  lexicon   English -> Chinese gloss lexicon from the parsed dictionaries (needs layer 2)
  probe     sample every .mdx on freemdict by HTTP range requests: pairs, order, alignment
  choose    keep the dictionaries whose sampled pairs are English-Chinese translations
  extract   stage every kept dictionary's pairs (parsed ones from layer 2, the rest downloaded)
  audit     screen a sample of each dictionary's pairs with jev; flagged pairs await review
  build     parallel.db from the dictionaries whose audited precision reaches 0.95

Between audit and build, `parallel_corpus/parallel/audit.py --queue` lists the flagged pairs whose
review could change a verdict; labels go in parallel_corpus/data/audit/<id>.review.json and a
second `--only audit` run folds them in. Exports: parallel_corpus/parallel/export.py.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the repository
PY = sys.executable
STEPS = [
    ("lexicon", [PY, "parallel_corpus/parallel/lexicon.py"]),
    ("probe", [PY, "parallel_corpus/parallel/probe.py", "--blocks", "6", "--retry-errors"]),
    ("choose", [PY, "parallel_corpus/parallel/choose.py"]),
    ("extract", [PY, "parallel_corpus/parallel/extract.py"]),
    ("audit", [PY, "parallel_corpus/parallel/audit.py"]),
    ("build", [PY, "parallel_corpus/parallel/build.py"]),
]
NAMES = [name for name, _ in STEPS]


def plan(start: str | None = None, only: str | None = None) -> list[tuple[str, list[str]]]:
    if only:
        return [s for s in STEPS if s[0] == only]
    return STEPS[NAMES.index(start):] if start else list(STEPS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", choices=NAMES)
    ap.add_argument("--only", choices=NAMES)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for name, cmd in plan(args.start, args.only):
        print(f"== {name}: {' '.join(cmd[1:])}", file=sys.stderr, flush=True)
        if not args.dry_run:
            subprocess.run(cmd, cwd=ROOT, check=True, env={**os.environ, "PYTHONPATH": "scripts:parallel_corpus"})


if __name__ == "__main__":
    main()
