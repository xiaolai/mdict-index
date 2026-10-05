"""The inventory runner: every build module is a step, and each step comes after the steps
whose files it reads."""
import importlib.util
import re
import unittest
from pathlib import Path

INVENTORIES = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("inventory_build", INVENTORIES / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

NOT_STEPS = {"evaluate"}  # runs against hand-checked gold, after a build; not part of it
_DATA_FILE = re.compile(r'DATA\s*/\s*"([\w.]+)"')
_IMPORTED_STEP = re.compile(r"^from inventory\.(\w+) import|^import inventory\.(\w+)", re.M)


def _source(step: str) -> str:
    return (INVENTORIES / "inventory" / f"{step}.py").read_text(encoding="utf-8")


class Steps(unittest.TestCase):
    def test_every_module_that_builds_something_is_a_step(self):
        mains = {p.stem for p in (INVENTORIES / "inventory").glob("*.py")
                 if 'if __name__ == "__main__":' in p.read_text(encoding="utf-8")}
        self.assertEqual(mains - NOT_STEPS, set(build.NAMES))

    def test_each_step_reads_only_files_written_before_it_or_by_itself(self):
        written: dict[str, str] = {}
        for step, outputs in build.STEPS:
            source = _source(step)
            for name in _DATA_FILE.findall(source):
                if name not in outputs:
                    self.assertIn(name, written, f"{step} reads {name}, which no earlier step writes")
            for groups in _IMPORTED_STEP.findall(source):
                used = next(g for g in groups if g)
                if used in build.NAMES and used != step:
                    self.assertIn(used, set(written.values()), f"{step} uses {used} before it is built")
            for name in outputs:
                written[name] = step

    def test_each_step_names_the_files_it_declares(self):
        for step, outputs in build.STEPS:
            named = set(_DATA_FILE.findall(_source(step)))
            for name in outputs:
                self.assertIn(name, named, f"{step} declares {name} but its module never names it")

    def test_check_runs_last(self):
        self.assertEqual(build.NAMES[-1], "check")


class Plan(unittest.TestCase):
    def test_from_and_only(self):
        self.assertEqual(build.plan(), build.NAMES)
        self.assertEqual(build.plan(start="pronunciation"), ["pronunciation", "sameword", "confusables", "check"])
        self.assertEqual(build.plan(only="levels"), ["levels"])

    def test_without_jev_reaches_only_sameword(self):
        self.assertEqual(build.command("sameword", without_jev=True)[-1], "--without-jev")
        self.assertNotIn("--without-jev", build.command("phrases", without_jev=True))
        self.assertNotIn("--without-jev", build.command("sameword"))

    def test_missing_jev_stops_the_build_before_its_first_step(self):
        # Found at the start, not after the eight steps before sameword have run for a quarter hour.
        absent, present = (lambda name: None), (lambda name: "/usr/local/bin/jev")
        why = build.missing_jev(build.plan(), without_jev=False, which=absent)
        self.assertIn("--without-jev", why)
        self.assertIn("Nothing has been built", why)
        self.assertIsNone(build.missing_jev(build.plan(), without_jev=True, which=absent))
        self.assertIsNone(build.missing_jev(build.plan(), without_jev=False, which=present))
        self.assertIsNone(build.missing_jev(build.plan(only="levels"), without_jev=False, which=absent))


if __name__ == "__main__":
    unittest.main()
