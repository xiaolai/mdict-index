"""DICTIONARIES.md is what scripts/recommended_doc.py writes from the recommendation files."""
import json
import unittest
from pathlib import Path

import recommended_doc

ROOT = Path(__file__).resolve().parent.parent


class Doc(unittest.TestCase):
    def test_the_committed_file_is_up_to_date(self):
        expected = recommended_doc.render(json.loads((ROOT / "site/data/recommended.json").read_text(encoding="utf-8")),
                                          json.loads((ROOT / "site/data/dicts.json").read_text(encoding="utf-8")))
        self.assertEqual((ROOT / "DICTIONARIES.md").read_text(encoding="utf-8"), expected,
                         "DICTIONARIES.md is out of date: run python3 scripts/recommended_doc.py")

    def test_every_recommended_dictionary_is_listed_and_a_missing_one_says_so(self):
        resolved = {"reviewed": "2026-01-01", "categories": [{"en": "E", "zh": "中", "items": [
            {"key": "a", "full": "Alpha", "zh": "", "latest": "2nd", "src": "https://x", "status": "current", "id": "r1"},
            {"key": "b", "full": "Beta", "zh": "乙", "latest": "1st", "src": "https://y", "status": "missing", "starter": True}]}]}
        dicts = [{"id": "r1", "n": "Alpha 2nd", "loc": [{"p": "folder/a", "f": [["a.mdx", 2_000_000], ["a.mdd", 3_000_000]]}]}]
        text = recommended_doc.render(resolved, dicts)
        self.assertIn("| `a` | Alpha | [2nd](https://x) | Alpha 2nd (`folder/a`) | current | 2, 5 MB |", text)
        self.assertIn("| `b` | Beta · 乙 ★ | [1st](https://y) | — | missing | — |", text)
        self.assertIn("built from: 1 with a copy on", text)


if __name__ == "__main__":
    unittest.main()
