"""The pipeline runs its steps in dependency order, and can resume or run one step."""
import unittest

from build_corpus import NAMES, plan


class Pipeline(unittest.TestCase):
    def test_order_is_fetch_inspect_then_layers(self):
        self.assertEqual(NAMES, ["fetch", "inspect", "layer1", "layer2", "layer3"])
        self.assertEqual([n for n, _ in plan()], NAMES)

    def test_resume_from_a_step_and_run_a_single_step(self):
        self.assertEqual([n for n, _ in plan(start="layer2")], ["layer2", "layer3"])
        self.assertEqual([n for n, _ in plan(only="inspect")], ["inspect"])

    def test_every_step_is_a_script_that_exists(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        for name, cmd in plan():
            self.assertTrue((root / cmd[1]).exists(), name)


if __name__ == "__main__":
    unittest.main()
