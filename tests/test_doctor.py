"""The preflight check: each missing prerequisite fails with its fix; jev is optional."""
import sqlite3
import tempfile
import unittest
from importlib import metadata
from pathlib import Path

import doctor


class Checks(unittest.TestCase):
    def test_python_version(self):
        self.assertTrue(doctor.python_version((3, 12, 0)).ok)
        old = doctor.python_version((3, 9, 6))
        self.assertFalse(old.ok)
        self.assertIn("needs 3.12", old.detail)

    def test_packages_missing_or_at_another_version_fail_with_the_install_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = Path(tmp) / "requirements.txt"
            req.write_text("# comment\nlxml==6.1.3\ntqdm==4.70.1  # pinned\nxxhash==4.0.1\n"
                           "en_core_web_sm @ https://example.org/en_core_web_sm-3.8.0-py3-none-any.whl\n"
                           "old_model @ https://example.org/old_model-1.0.0-py3-none-any.whl\n")
            installed = {"lxml": "6.1.3", "tqdm": "4.67.2", "en_core_web_sm": "3.8.0", "old_model": "0.9.0"}

            def version(name):
                if name not in installed:
                    raise metadata.PackageNotFoundError(name)
                return installed[name]
            check = doctor.pinned_packages(req, version)
        self.assertFalse(check.ok)
        self.assertIn("tqdm 4.67.2, pinned 4.70.1", check.detail)
        self.assertIn("xxhash missing", check.detail)
        self.assertNotIn("lxml", check.detail)
        self.assertNotIn("en_core_web_sm", check.detail)          # a URL pin, at its wheel's version
        self.assertIn("old_model 0.9.0, pinned 1.0.0", check.detail)
        self.assertIn("pip install -r requirements-dev.txt", check.detail)

    def test_fts5(self):
        self.assertTrue(doctor.fts5().ok)  # the Python these tests run on must have it: the build needs it

        class NoFts5:
            def execute(self, sql):
                raise sqlite3.OperationalError("no such module: fts5")

            def close(self):
                pass
        self.assertFalse(doctor.fts5(lambda _: NoFts5()).ok)

    def test_curl(self):
        self.assertTrue(doctor.curl(lambda _: "/usr/bin/curl").ok)
        self.assertFalse(doctor.curl(lambda _: None).ok)

    def test_disk_counts_what_is_already_built(self):
        self.assertTrue(doctor.disk(free_gb=10, used=70).ok)     # 8 GB more needed
        self.assertFalse(doctor.disk(free_gb=10, used=0).ok)     # the full 78 GB needed
        self.assertTrue(doctor.disk(free_gb=0, used=80).ok)      # nothing more needed

    def test_jev_is_optional_and_says_what_changes_without_it(self):
        check = doctor.jev(lambda _: None)
        self.assertFalse(check.ok)
        self.assertFalse(check.required)
        self.assertIn("not needed", check.detail)
        self.assertIn("committed answers", check.detail)


if __name__ == "__main__":
    unittest.main()
