"""Compile the analyzer's lexicon from the inventories: analyzer/data/analyzer.db.

    .venv/bin/python analyzer/build.py

Needs the inventories (inventories/build.py) and spaCy's English model (requirements-dev.txt).
Everything it writes is under analyzer/data/, which is never committed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parent.parent / "scripts")]
from analysis.compile import build  # noqa: E402

if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
