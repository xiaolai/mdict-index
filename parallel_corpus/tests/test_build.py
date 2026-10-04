"""The parallel-corpus pipeline runs its steps in dependency order, and can resume or run one step."""
import unittest
from pathlib import Path

from build import NAMES, plan


class Pipeline(unittest.TestCase):
    def test_order(self):
        self.assertEqual(NAMES, ["lexicon", "probe", "choose", "extract", "audit", "build"])
        self.assertEqual([n for n, _ in plan()], NAMES)

    def test_resume_from_a_step_and_run_a_single_step(self):
        self.assertEqual([n for n, _ in plan(start="audit")], ["audit", "build"])
        self.assertEqual([n for n, _ in plan(only="choose")], ["choose"])

    def test_every_step_is_a_script_that_exists(self):
        root = Path(__file__).resolve().parent.parent.parent  # the repository, where the driver runs the steps
        for name, cmd in plan():
            self.assertTrue((root / cmd[1]).exists(), name)


if __name__ == "__main__":
    unittest.main()
