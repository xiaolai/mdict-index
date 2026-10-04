"""The inventories read the parsed dictionaries where the structured build writes them."""
import unittest

import build_structured
import inventory


class Paths(unittest.TestCase):
    def test_structured_is_the_builds_own_folder(self):
        self.assertIs(inventory.STRUCTURED, build_structured.STRUCTURED)
        self.assertEqual(build_structured.STRUCTURED, build_structured.shard_dir(build_structured.CORPUS / "unified.db"))


if __name__ == "__main__":
    unittest.main()
