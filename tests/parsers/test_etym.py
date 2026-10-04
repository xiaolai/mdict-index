"""Etymonline parser on synthetic entries that mirror its markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import etym

TWO_WORDS = """
<link rel="stylesheet" type="text/css" href="etymonline.css">
<div class="word"><object><div class="spare">
 <h1 class="word__name">grelt<span class="word_c">v.</span></h1>
 <blockquote class="word_summary--1nri6"><p>SUMMARY REPEAT</p></blockquote>
 <section class="word__defination">
  <p>c. 1620, from Old Florpish <span class="foreign notranslate">*grelta</span> "to fold,"
     &lt; Proto-Florpic root (see <a href="entry://florp" class="crossreference notranslate">florp</a>).</p>
  <blockquote>A grelt, a grelt,   my map for a grelt.</blockquote>
 </section>
 <div class="chart--2x1ib"><div class="chart"><img src="/grelt-1p_l.jpg"></div></div>
</div></object></div>
<div class="word"><object><div class="spare">
 <h1 class="word__name">grelt<span class="word_c">n.2</span></h1>
 <section class="word__defination"><p>1701, from <a href="entry://grelt" class="crossreference notranslate">grelt</a> (v.).</p></section>
</div></object></div>
<div class="related"><h3 class="h3_title">Related Entries</h3><ul class="related__container">
 <li class="related__word"><a href="entry://grelting">grelting</a></li>
 <li class="related__word"><a href="entry://florp">florp</a></li>
 <li class="related__more related__word"><a href="entry://Words related to grelt">See all related words (<!-- -->9<!-- -->)&gt;</a></li>
</ul></div>"""

ONE_WORD = """<div class="word"><object><div class="spare">
 <h1 class="word__name">florp<span class="word_c">adj., n.1</span></h1>
 <section class="word__defination"><p>1850s, of unknown origin.</p><table><tr><td>TABLE</td></tr></table></section>
</div></object></div>"""

ROOT = """<div class="word"><object><div class="spare"><h1 class="word__name">*grel- (2)</h1>
 <section class="word__defination"><p>Invented root meaning "to fold."</p></section></div></object></div>"""

LIST_PAGE = """<div class="word__scrabble"><h2 class="h2_title">Words related to grelt</h2>
<div class="ant-row"><div class="sc_related"><a class="scrabble__node" href="entry://grelting">grelting</a></div></div></div>"""


class EtymParser(unittest.TestCase):
    def setUp(self):
        self.e = etym.parse("grelt", TWO_WORDS)

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, etym.COVERS))

    def test_headword_pos_homograph(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos, self.e.stub), ("grelt", "", ("v.", "n."), ""))

    def test_homographs_are_labelled_in_one_etymology(self):
        self.assertEqual(self.e.etymology,
                         '(v.) c. 1620, from Old Florpish *grelta "to fold," < Proto-Florpic root (see florp). '
                         'A grelt, a grelt, my map for a grelt. (n.2) 1701, from grelt (v.).')

    def test_summary_chart_and_related_stay_out_of_the_etymology(self):
        for leaked in ("SUMMARY", "grelting", "See all", "jpg"):
            self.assertNotIn(leaked, self.e.etymology)
        self.assertEqual(self.e.extra, {"related": "grelting; florp"})

    def test_single_word_is_unlabelled_and_numbered(self):
        e = etym.parse("florp", ONE_WORD)
        self.assertEqual((e.etymology, e.pos, e.homograph), ("1850s, of unknown origin.", ("adj.", "n."), "1"))

    def test_number_printed_in_the_name(self):
        e = etym.parse("*grel-", ROOT)
        self.assertEqual((e.headword, e.homograph, e.etymology), ("*grel-", "2", 'Invented root meaning "to fold."'))

    def test_only_words_matching_the_headword(self):
        e = etym.parse("florp", TWO_WORDS + ONE_WORD)
        self.assertEqual(e.etymology, "1850s, of unknown origin.")

    def test_list_page_is_not_covered(self):
        e = etym.parse("Words related to grelt", LIST_PAGE)
        self.assertEqual((e.headword, e.etymology, e.stub, e.extra),
                         ("Words related to grelt", "", "index", {"related": "grelting"}))
        self.assertFalse(covered(e, etym.COVERS))
        self.assertEqual(problems(e), [])

    def test_garbage_never_raises(self):
        for junk in ["", "<", "<div class='word'><h1 class='word__name'>", "plain text", "<<<>>>"]:
            e = etym.parse("x", junk)
            self.assertEqual(e.headword, "x")
            self.assertEqual(problems(e), [])


if __name__ == "__main__":
    unittest.main()
