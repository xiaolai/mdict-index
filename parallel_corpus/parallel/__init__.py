"""The English-Chinese parallel corpus of dictionary examples (see parallel_corpus/README.md)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent   # the repository: shared inputs live there
DATA = ROOT / "parallel_corpus" / "data"               # everything built; git-ignored (dictionary content)
