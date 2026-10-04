"""Build the whole unified dictionary, in order, stopping at the first failure.

    .venv/bin/python scripts/build_corpus.py [--from STEP] [--only STEP] [--dry-run]

Steps
  fetch      download the recommended dictionaries (all .mdx and .mdd) into corpus/
  inspect    read every dictionary once; counts that later steps are checked against
  layer1     corpus/unified.db: every entry's HTML, redirects, CSS/JS, headword index
  layer2     structured senses, pronunciations, examples; Chinese index; definition search
  layer3     corpus/resources.db: every audio/image resource, stored once by content hash
Everything is written under corpus/, which is never committed.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
STEPS = [
    ("fetch", [PY, "scripts/fetch_corpus.py", "--max-mdd-mb", "100000"]),
    ("inspect", [PY, "scripts/inspect_corpus.py"]),
    ("layer1", [PY, "scripts/build_unified.py"]),
    ("layer2", [PY, "scripts/build_structured.py"]),
    ("layer3", [PY, "scripts/build_resources.py"]),
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
            subprocess.run(cmd, cwd=ROOT, check=True, env={**os.environ, "PYTHONPATH": "scripts"})


if __name__ == "__main__":
    main()
