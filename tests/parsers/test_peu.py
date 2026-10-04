"""PEU parser on synthetic entries that mirror PEU4's markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import peu

HTML = """
<link href="PEU4th.css" rel="stylesheet" type="text/css">
<div id="entryContent" class="peu-contents-full">
<div class="PEU_contents"><a name="PEU_Contents" href="entry://Contents%20overview">Contents overview</a></div>
<span class="grammarEntry" super_section="9" ge_num="512"><span class="institle">grelting :  florp</span>
 <span class="arl"><span class="index">INDEX TERM</span><span class="display"><span class="h">INDEX TERM</span>
  <span class="def">NOT A DEFINITION</span></span></span>
 <span class="breadcrumb"><span class="l1"><a class="Ref" href="entry://x"><span class="bctitle">Breadcrumb</span></a></span></span>
 <span class="title"><span class="hang">512 </span><span class="indent">grelting</span></span>
 <span class="section" section_level="1"><span class="block">Grelting is an   invented habit.</span></span>
 <span class="section" section_level="1" section_num="1" ge_num="512">
  <span class="title"><span class="hang">1</span><span class="indent">grelt + object</span></span>
  <span class="block">We use <span class="example">grelt</span> before an object
   <span class="a"><a class="Ref" href="entry://y"><span class="xref"><span class="ge_num">77</span></span></a></span>.</span>
  <span class="constructGroup"><span class="construct"><span class="pertinent">grelt</span> + noun</span></span>
  <span class="exampleGroupSet"><span class="exampleGroup">
   <span class="example">She <span class="pertinent">grelted</span> the map.
    <span class="deprecated" role="not"><span class="roman">(</span><span class="roman smallCaps">not </span><span class="strikethrough">She grelt map</span><span class="roman">)</span></span></span>
   <span class="example"><span class="exchange" type="run-on"><span class="locution">'Grelt it?'</span><span class="locution">'Never.'</span></span></span>
  </span></span>
  <span class="vocabBox" role="vocabBox">Box words: <span class="example">BOXED</span></span>
  <span class="tabular" tableid="t1"><table><tr><td>TABLE CELL</td></tr></table></span>
  <span class="notes"><span class="note"><span class="block">A note inside section one.</span></span></span>
  <span class="section" section_level="2" subsection="y" section_num="1">
   <span class="title"><span class="hang">a</span><span class="indent">in the evening</span></span>
   <span class="lettered"><span class="li"><span class="roman"><span class="block">Evening grelting is rarer.</span>
    <span class="exampleGroup"><span class="example">We grelt at dusk.</span></span></span></span></span>
  </span>
 </span>
 <span class="notes"><span class="note"><span class="block">For florping, see 513.</span></span></span>
 <span class="peu-btns"><span class="xr-g"><span class="xh"><a class="Ref" href="entry://z">Next</a></span></span></span>
</span></div>"""

STUB = """<link href="PEU4th.css" rel="stylesheet" type="text/css"><h3 class="entry_name">grelt</h3>
<div class="seealso">See also: <a href="entry://grelting%20florp">grelting florp</a></div>
<div class="seealso">See also: <a href="entry://grelt and florp">grelt and florp</a></div>"""


class PeuParser(unittest.TestCase):
    def setUp(self):
        self.e = peu.parse("grelting florp", HTML)

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, peu.COVERS))

    def test_headword_and_article_number(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos, self.e.stub), ("grelting : florp", "", (), ""))
        self.assertEqual(self.e.extra, {"ge_num": "512"})

    def test_every_section_is_a_numbered_note(self):
        self.assertEqual([(s.kind, s.number, s.phrase) for s in self.e.senses],
                         [("note", "", ""), ("note", "1", "grelt + object"), ("note", "a", "in the evening"),
                          ("note", "", "")])
        self.assertEqual(self.e.senses[0].definition, "Grelting is an invented habit.")

    def test_section_prose_constructs_and_examples(self):
        s = self.e.senses[1]
        self.assertEqual(s.definition, "We use grelt before an object 77. grelt + noun A note inside section one.")
        self.assertEqual([x.text for x in s.examples], ["She grelted the map. (not She grelt map)", "'Grelt it?' 'Never.'"])

    def test_subsection_is_not_double_counted(self):
        one, sub = self.e.senses[1], self.e.senses[2]
        self.assertNotIn("Evening", one.definition)
        self.assertEqual((sub.definition, [x.text for x in sub.examples]), ("Evening grelting is rarer.", ["We grelt at dusk."]))

    def test_article_note_is_its_own_sense(self):
        self.assertEqual(self.e.senses[-1].definition, "For florping, see 513.")

    def test_boxes_tables_and_navigation_stay_out(self):
        dump = repr(self.e.senses)
        for leaked in ("BOXED", "Box words", "TABLE CELL", "INDEX TERM", "NOT A DEFINITION", "Breadcrumb", "Next"):
            self.assertNotIn(leaked, dump)

    def test_see_also_stub(self):
        stub = peu.parse("grelt", STUB)
        self.assertEqual((stub.headword, stub.senses), ("grelt", ()))
        self.assertEqual((stub.stub, stub.extra), ("xref", {"see_also": "grelting florp; grelt and florp"}))
        self.assertFalse(covered(stub, peu.COVERS))
        self.assertEqual(problems(stub), [])

    def test_garbage_never_raises(self):
        for junk in ["", "<", "<span class='grammarEntry'><span class='section'>", "plain text", "<<<>>>",
                     "<div class='seealso'><a href='entry://'>"]:
            e = peu.parse("x", junk)
            self.assertEqual(e.headword, "x")
            self.assertEqual(problems(e), [])


if __name__ == "__main__":
    unittest.main()
