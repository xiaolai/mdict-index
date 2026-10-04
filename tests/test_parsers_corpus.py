"""Every registered parser against the real corpus, when it is present.

The corpus is copyrighted and not in the repository, so these tests skip on
GitHub; locally they run each parser over a fixed random sample of its
dictionary and hold it to its MIN_COVERAGE (within sampling error) with zero
exceptions and zero contract problems. The exact full-corpus gate is in
build_structured.py.
"""
import math
import unittest

from build_unified import CORPUS
from structured.parsers import load, registry

SAMPLE = 3000
SEED = 20260929
HAVE_CORPUS = (CORPUS / "unified.db").exists()


class ParserRegistry(unittest.TestCase):
    def test_every_parser_declares_its_contract(self):
        for key, module in registry().items():
            self.assertTrue(0 < module.MIN_COVERAGE <= 1, key)

    def test_printed_markup_exceptions_stay_tiny(self):
        # An escape hatch from the leftover-markup check must stay a reviewed handful.
        for key, module in registry().items():
            self.assertLessEqual(len(getattr(module, "PRINTED_MARKUP", ())), 5, key)

    def test_each_parser_loads_alone_under_its_own_key(self):
        for key in registry():
            self.assertEqual(load(key).KEY, key)
        with self.assertRaises(ModuleNotFoundError):
            load("no-such-dictionary")


@unittest.skipUnless(HAVE_CORPUS, "corpus/unified.db not present (it is never committed)")
class ParsersOnCorpus(unittest.TestCase):
    def test_sampled_coverage_exceptions_and_contract(self):
        from structured.devtool import run_coverage
        for key, module in sorted(registry().items()):
            with self.subTest(key=key):
                r = run_coverage(key, limit=SAMPLE, seed=SEED)
                self.assertEqual(r["exceptions"], 0, r["exception_examples"])
                self.assertEqual(r["problem_entries"], 0, r["problems"])
                # A sample's coverage scatters around the dictionary's true coverage (standard error
                # sqrt(p(1-p)/n)); allow three standard errors so a sample cannot fail by chance. The
                # exact full-dictionary gate is enforced by build_structured.py.
                p, n = module.MIN_COVERAGE, max(r["content_records"], 1)
                margin = 3 * math.sqrt(p * (1 - p) / n)
                self.assertGreaterEqual(r["coverage"], p - margin, r["uncovered_examples"])


if __name__ == "__main__":
    unittest.main()
