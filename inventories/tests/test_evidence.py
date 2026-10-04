"""Building the example index: never from nothing, never over another build's file."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from inventory.evidence import Evidence, build


def source(folder: Path, name: str, examples: list[str] | None) -> None:
    con = sqlite3.connect(folder / f"{name}.db")
    if examples is not None:
        con.execute("CREATE TABLE s_example (kind TEXT, text TEXT)")
        con.executemany("INSERT INTO s_example VALUES ('example', ?)", [(e,) for e in examples])
    else:
        con.execute("CREATE TABLE s_sense (id INTEGER)")  # not a parsed dictionary
    con.commit()
    con.close()


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src, self.out = self.root / "structured", self.root / "data" / "evidence.db"
        self.src.mkdir()
        self.out.parent.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_an_index_of_the_examples(self):
        source(self.src, "glimdict", ["a bold glim was seen", ""])
        source(self.src, "oed", ["the glum glim of yore"])  # left out
        self.assertEqual(build(self.out, self.src), 1)
        evidence = Evidence(self.out)
        self.addCleanup(evidence.con.close)
        self.assertTrue(evidence.occurs(("bold", "glim")))
        self.assertFalse(evidence.occurs(("glum", "glim")))

    def test_no_sources_is_an_error_and_the_old_index_stays(self):
        self.out.write_bytes(b"old")
        with self.assertRaisesRegex(RuntimeError, "no examples"):
            build(self.out, self.src)
        with self.assertRaisesRegex(FileNotFoundError, "missing"):
            build(self.out, self.root / "nowhere")
        self.assertEqual(self.out.read_bytes(), b"old")
        self.assertEqual(sorted(p.name for p in self.out.parent.iterdir()), ["evidence.db"])

    def test_a_broken_source_leaves_nothing_behind(self):
        source(self.src, "glimdict", None)
        with self.assertRaises(sqlite3.OperationalError):
            build(self.out, self.src)
        self.assertEqual(list(self.out.parent.iterdir()), [])

    def test_another_build_in_progress_is_left_alone(self):
        other = self.out.with_name(self.out.name + ".part")
        other.write_bytes(b"another build's")
        source(self.src, "glimdict", ["a bold glim"])
        build(self.out, self.src)
        self.assertEqual(other.read_bytes(), b"another build's")


if __name__ == "__main__":
    unittest.main()
