"""Reading the dictionaries' level marks (invented entries in each one's markup)."""
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from inventory.levels import Level, build, collins, ldoce, med, oald, oed

OALD = """<h1 class="headword" ox3000="y" academic="y" opal_written="y" id="glim_h_1">glim</h1>
<span class="pos" hclass="pos">verb</span><div class="symbols"><a href="x"><span class="ox3ksym_b1"> </span></a></div>
<ol><li class="sense" cefr="b1" ox3000="y">...</li><li class="sense" sensenum="2" cefr="c1">...</li>
<li class="sense" cefr="b1">...</li></ol>
<span class="pv-g"><span class="pv" id="glim_pv_1" ox3000="y" cefr="a2">glim out (of…)</span> <div class="symbols">
<span class="ox3ksymsub_a2"> </span></div><ol><li class="sense" cefr="a2">...</li></ol></span>"""
LDOCE = """<span class="entry" id="glim_1"><span class="entryhead"><span class="hwd">glim</span>
<span class="level tooltip" title="Core vocabulary: High-frequency"> ●●●</span>
<span class="freq" title="Top 2000 spoken words">S2</span><span class="freq" title="Top 3000 written words">W3</span>
<span class="ac" title="Academic Word List">AWL</span><span class="pos"> noun</span></span></span>
<span class="entry" id="glim_2"><span class="entryhead"><span class="hwd">glim</span><span class="pos"> verb</span></span></span>
<span class="entry" id="glim_3"><span class="entryhead"><span class="hwd">GLIM</span>
<span class="freq" title="Top 1000 written words">W1</span></span><span class="Sense">...</span></span>
<span class="entry" id="glim_4"><span class="entryhead"><span class="hwd">glim</span><span class="pos"> adverb</span></span></span>"""
COLLINS = """<div class="word-frequency-img" title="Common"><span class="level level1 roundRed"></span>
<span class="level level2 roundRed"></span><span class="level level3 roundRed"></span><span class="level level4"></span>
<span class="level level5"></span></div>"""
MED = """<span class="BASE">glim</span><div class="stars_grp"><div class="icon_star">★</div><div class="icon_star">★</div>
</div><div id="headbar"> <span class="PART-OF-SPEECH"><span class="SEP"> </span>noun</span> </div>"""
OED = """<span class="hw">glim</span>, <span class="ps">n.<sup class="hm">1</sup></span><a class="frequencyBand3"></a>
<hr class="hr_multi_keys"><span class="hw">glim</span>, <span class="ps">v.</span><a class="frequencyBand2"></a>"""


def _query(path: Path, sql: str) -> list[tuple]:
    with closing(sqlite3.connect(path)) as con:
        return con.execute(sql).fetchall()


class Readers(unittest.TestCase):
    def test_oald(self):
        self.assertEqual(sorted(oald(OALD)), sorted([
            Level("verb", "oxford3000", "b1"), Level("verb", "opal", "written"), Level("verb", "academic", "yes"),
            Level("verb", "cefr", "b1", 2), Level("verb", "cefr", "c1", 1),   # not the phrasal verb's a2 sense
            Level("phrasal verb", "oxford3000", "a2", 0, "glim out"), Level("phrasal verb", "cefr", "a2", 1, "glim out"),
            Level("phrasal verb", "oxford3000", "a2", 0, "glim out of {...}"),   # every form it prints
            Level("phrasal verb", "cefr", "a2", 1, "glim out of {...}")]))

    def test_oald_phrasal_verb_alternatives_are_each_levelled(self):
        body = """<h1 class="headword" id="glim_h_1">glim on</h1><ol></ol>
<span class="pv-g"><span class="pv">glim on/upon something</span><div class="symbols"><span class="ox3ksymsub_b2"> </span>
</div><ol><li class="sense" cefr="b2">...</li></ol></span>"""
        words = {l.word for l in oald(body) if l.scheme == "oxford3000"}
        self.assertEqual(words, {"glim on {sth}", "glim upon {sth}"})

    def test_oald_phrasal_verb_levelled_by_its_senses(self):
        body = """<h1 class="headword" id="glim_h_1">glim</h1><span class="pos">verb</span><ol></ol>
<span class="pv-g" ox3000="y"><div class="webtop"><span class="pv">glim for something</span> </div><ol>
<li class="sense" cefr="b2"><div class="symbols"><span class="ox3ksym_b2"> </span></div></li>
<li class="sense" cefr="b1"><div class="symbols"><span class="ox3ksym_b1"> </span></div></li></ol></span>"""
        self.assertEqual(sorted(oald(body)), sorted([
            Level("phrasal verb", "oxford3000", "b1", 0, "glim for {sth}"), Level("phrasal verb", "cefr", "b2", 1, "glim for {sth}"),
            Level("phrasal verb", "cefr", "b1", 1, "glim for {sth}")]))

    def test_ldoce_by_homograph(self):
        self.assertEqual(list(ldoce(LDOCE)), [
            Level(" noun", "core", "high"), Level(" noun", "spoken", "S2"), Level(" noun", "written", "W3"),
            Level(" noun", "awl", "yes"), Level("", "written", "W1")])  # an abbreviation: no part of speech

    def test_oald_several_entries_in_one_body(self):
        body = OALD.replace("ox3000=\"y\"", "", 1).replace("ox3ksym_b1", "") + OALD.replace("verb</span>", "noun</span>")
        self.assertIn(Level("noun", "oxford3000", "b1"), list(oald(body)))

    def test_ldoce_tiers_are_all_known(self):
        low = LDOCE.replace("High-frequency", "Lower-frequency")
        self.assertEqual(next(ldoce(low)), Level(" noun", "core", "low"))
        with self.assertRaises(ValueError):
            list(ldoce(LDOCE.replace("High-frequency", "Rare-frequency")))

    def test_collins_counts_filled_dots(self):
        self.assertEqual(list(collins(COLLINS)), [Level("", "frequency_band", "3")])

    def test_med_stars(self):
        self.assertEqual(list(med(MED)), [Level("noun", "stars", "2")])

    def test_oed_bands_by_homograph(self):
        self.assertEqual(list(oed(OED)), [Level("n.", "oed_band", "3"), Level("v.", "oed_band", "2")])


class Build(unittest.TestCase):
    def test_a_mark_no_reader_reads_fails_the_build(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            build(iter([("med", "glim", '<div class="stars_grp"></div>')]), Path(tmp) / "levels.db")

    def test_homographs_add_their_senses_and_a_repeated_entry_counts_once(self):
        body = OALD + OALD.replace("glim_h_1", "glim_h_2")   # two verb homographs, each two b1 senses
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "levels.db"
            build(iter([("oald", "glim", body), ("oald", "Glim", body)]), out)
            rows = _query(out, "SELECT value, senses FROM level WHERE word = 'glim' AND scheme = 'cefr' "
                               "ORDER BY value")
        self.assertEqual(rows, [("b1", 4), ("c1", 2)])

    def test_a_phrasal_verb_printed_in_the_entry_of_each_form_counts_once(self):
        block = lambda ids: ('<span class="pv-g"><span class="pv">glim in | glim into something</span><ol>'
                             + "".join(f'<li class="sense" cefr="b2" id="{i}">...</li>' for i in ids) + "</ol></span>")
        other = '<span class="pv-g"><span class="pv">glim into something</span><ol><li class="sense" cefr="b2">...</li></ol></span>'
        head = '<h1 class="headword" id="{0}">{1}</h1><span class="pos">phrasal verb</span><ol></ol>'
        entries = [("oald", "glim in", head.format("a", "glim in") + block(["glim_1", "glim_2", "glim_3"])),
                   # the same block under other sense ids, and a block of its own: two in one body add up
                   ("oald", "glim into", head.format("b", "glim into") + block(["into_1", "into_2", "into_3"]) + other)]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "levels.db"
            build(iter(entries), out)
            rows = dict(_query(out, "SELECT word, senses FROM level WHERE scheme = 'cefr'"))
        self.assertEqual(rows, {"glim in": 3, "glim into {sth}": 4})

    def test_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "levels.db"
            build(iter([("med", "Glim", MED), ("oed", "glim", OED)]), out)
            rows = _query(out, "SELECT * FROM level ORDER BY dictionary, pos")
        self.assertEqual(rows, [("glim", "NOUN", "stars", "2", "med", 0), ("glim", "NOUN", "oed_band", "3", "oed", 0),
                                ("glim", "VERB", "oed_band", "2", "oed", 0)])


if __name__ == "__main__":
    unittest.main()
