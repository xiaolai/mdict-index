"""The parallel corpus reads the parsed dictionaries where the structured build writes them."""
import unittest

import build_structured
from parallel import extract, lexicon


class Paths(unittest.TestCase):
    def test_structured_is_the_builds_own_folder(self):
        self.assertIs(lexicon.STRUCTURED, build_structured.STRUCTURED)
        self.assertIs(extract.STRUCTURED, build_structured.STRUCTURED)


if __name__ == "__main__":
    unittest.main()
