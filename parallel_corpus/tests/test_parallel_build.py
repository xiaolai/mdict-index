"""Building parallel.db: judging, the three dedup levels, sources, the audit gate, search."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from parallel.build import build
from parallel.extract import stage


def choice(id, source="download", density=10.0, keep=True):
    return {"id": id, "name": f"dict {id}", "keep": keep, "source": source, "pairs_per_100k_chars": density,
            "order": "en-zh", "alignment": 0.7}


def rec(en, zh, hw="w"):
    return {"en": en, "zh": zh, "hw": hw}


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.staged = self.dir / "staged"
        self.out = self.dir / "parallel.db"

    def tearDown(self):
        self.tmp.cleanup()

    def stage(self, id, records):
        stage(iter(records), self.staged / f"{id}.jsonl.gz")

    def run_build(self, choices, audit=None, allow_unaudited=False):
        audit = audit if audit is not None else {c["id"]: {"precision": 0.99} for c in choices}
        summary = build(choices, self.staged, audit, self.out, allow_unaudited)
        con = sqlite3.connect(self.out)
        self.addCleanup(con.close)
        return summary, con

    def test_the_three_dedup_levels(self):
        self.stage("a", [
            rec("Mira opened the kitchen window.", "米拉打开了厨房的窗户。", "open"),
            rec("mira opened the kitchen window.", "米拉打開了廚房的窗戶。", "window"),   # exact duplicate once normalised
            rec("Mira opened the kitchen window!", "米拉打开了厨房的窗户！"),   # same cluster: punctuation only
            rec("Mira opened the kitchen window.", "米拉把厨房的窗户打开了。"),   # a translation variant
        ])
        summary, con = self.run_build([choice("a")])
        self.assertEqual((summary["pairs"], summary["clusters"], summary["en_groups"]), (3, 2, 1))
        first = con.execute("SELECT en, zh, variants, sources FROM pair WHERE id = 1").fetchone()
        self.assertEqual(first, ("Mira opened the kitchen window.", "米拉打开了厨房的窗户。", 3, 1))  # text as first printed
        self.assertEqual(con.execute("SELECT headword FROM source WHERE pair_id = 1 ORDER BY 1").fetchall(),
                         [("open",), ("window",)])

    def test_parsed_dictionaries_lead_and_every_source_is_recorded(self):
        self.stage("d", [rec("Pip bakes fresh bread every morning.", "皮普每天早上都烤新鲜面包。")])
        self.stage("p", [rec("Pip bakes fresh bread every morning.", "皮普每天早上都烤新鲜面包。"),
                         rec("The florp is humming again today.", "弗洛普今天又在哼歌了。")])
        _, con = self.run_build([choice("d", density=500), choice("p", source="layer2", density=1)])
        self.assertEqual(con.execute("SELECT source_id, new_pairs FROM dictionary ORDER BY id").fetchall(),
                         [("p", 2), ("d", 0)])
        self.assertEqual(con.execute("SELECT sources FROM pair WHERE en LIKE 'Pip bakes%'").fetchone(), (2,))

    def test_traditional_text_gets_a_simplified_form(self):
        self.stage("t", [rec("The harbour looks calm today.", "今天港口看起來很平靜。")])
        _, con = self.run_build([choice("t")])
        self.assertEqual(con.execute("SELECT zh, zh_hans FROM pair").fetchone(), ("今天港口看起來很平靜。", "今天港口看起来很平静。"))

    def test_rejections_are_counted_by_reason(self):
        self.stage("r", [rec("Er öffnet das Fenster, weil es zu warm ist.", "他打开窗户，因为太热了。"),
                         rec("Mira opened the kitchen window; her florp heard the rain drumming outside.", "开"),
                         rec("wet socks", "湿袜子")])
        _, con = self.run_build([choice("r")])
        row = con.execute("SELECT records, accepted, rejected FROM dictionary").fetchone()
        self.assertEqual(row[:2], (3, 1))
        self.assertEqual(json.loads(row[2]), {"the Latin-script side is not English": 1,
                                              "length ratio implausible for a translation": 1})
        self.assertEqual(con.execute("SELECT kind FROM pair").fetchone(), ("phrase",))

    def test_the_audit_gate(self):
        for id in "gbu":
            self.stage(id, [rec(f"This is example sentence {id}.", f"这是例句{id}。")])
        audit = {"g": {"precision": 0.97}, "b": {"precision": 0.80}}
        _, con = self.run_build([choice("g"), choice("b"), choice("u")], audit)
        rows = dict((r[0], r[1:]) for r in con.execute("SELECT source_id, included, why, precision FROM dictionary"))
        self.assertEqual(rows["g"], (1, "audited precision 0.970", 0.97))
        self.assertEqual(rows["b"], (0, "audited precision 0.800 below 0.95", 0.8))
        self.assertEqual(rows["u"], (0, "not audited", None))
        self.assertEqual(con.execute("SELECT count(*) FROM pair").fetchone(), (1,))
        _, con = self.run_build([choice("g"), choice("u")], audit, allow_unaudited=True)
        self.assertEqual(con.execute("SELECT count(*) FROM pair").fetchone(), (2,))

    def test_an_admitted_dictionary_that_was_never_extracted_fails_the_build(self):
        import gc
        import warnings
        with warnings.catch_warnings(record=True) as caught:  # an unclosed connection warns when collected
            warnings.simplefilter("always", ResourceWarning)
            with self.assertRaises(FileNotFoundError):
                self.run_build([choice("missing")])
            gc.collect()
        self.assertEqual([w for w in caught if issubclass(w.category, ResourceWarning)], [])
        self.assertFalse(self.out.exists())
        self.assertEqual(len(list(self.dir.glob("parallel.db.*.part"))), 1)  # left for inspection

    def test_another_builds_working_file_is_left_alone(self):
        self.stage("a", [rec("Mira opened the kitchen window.", "米拉打开了厨房的窗户。")])
        other = self.dir / "parallel.db.part"  # what a concurrent build of this output used to share
        other.write_bytes(b"another build's database")
        self.run_build([choice("a")])
        self.assertEqual(other.read_bytes(), b"another build's database")
        self.assertEqual(list(self.dir.glob("*.part")), [other])  # this build's own working file is gone

    def test_full_text_search_in_both_languages(self):
        self.stage("s", [rec("The florps played tag in the barn.", "弗洛普们在谷仓里玩捉人游戏。"),
                         rec("Lena plays the tuba every evening.", "莉娜每天晚上吹大号。")])
        _, con = self.run_build([choice("s")])
        en = con.execute("SELECT pair.en FROM pair_en JOIN pair ON pair.id = pair_en.rowid WHERE pair_en MATCH 'play'")
        self.assertEqual(len(en.fetchall()), 2)  # stemmed: played, plays
        zh = con.execute("SELECT en FROM pair_zh JOIN pair ON pair.id = pair_zh.rowid WHERE pair_zh MATCH '在谷仓'")
        self.assertEqual(zh.fetchall(), [("The florps played tag in the barn.",)])


if __name__ == "__main__":
    unittest.main()
