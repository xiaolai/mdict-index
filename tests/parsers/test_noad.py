"""NOAD parser on synthetic entries that mirror the DSL-converted NOAD3 markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import noad

HTML = """<link rel="stylesheet" href="NOAD3.css">
<p class="s"><b>I</b> [<span class="t">ɡrelt</span>]</p>
<p class="ss"><b>1.</b> <b><span class="color">grel·ter</span></b> (also grelte or chiefly <span class="p" title="British">Brit.</span> grolt)</p>
<div class="m1"><span class="p" title="verb">v.</span> <span class="color">(<b>grelts</b>, <b>grelting</b>, <b>grelted</b>)</span></div>
<div class="m1">1) <i><span class="color">archaic</span></i> or <i><span class="color">literary</span></i> fold (a map) badly</div>
<div class="m1"><div class="opt"><span class="ex">he grelted the map</span></div></div>
<div class="m1"><div class="opt"><span class="ex">maps get grelted</span></div></div>
<div class="m1"><span class="gray">■</span> [] chiefly <span class="p" title="British">Brit.</span> <i>(<b>grelt something up</b>)</i> fold upward <i>[with <span class="p" title="object">obj.</span>]</i></div>
<div class="m1">2) usually</div>
<div class="m1"><i>[no <span class="p" title="object">obj.</span>]</i></div>
<p class="ss"><b>2.</b> <b><span class="color">grel·ter</span></b></p>
<div class="m1"><span class="p">n. Scottish</span> <span class="color">(<i>pl.</i> <b>grelten</b> <b>(grel·ten)</b>)</span> [<span class="t">-tən</span>] a badly folded map</div>
<div class="m1">See also <a href="entry://fold">fold</a></div>
<div class="m1"><div class="opt">•</div></div>
<div class="m2"><div class="opt">- <a href="entry://grelt%20the%20lot">grelt the lot</a></div></div>
<div class="m1"><div class="opt"><b>Phrasal Verbs:</b></div></div>
<div class="m2"><div class="opt">- <a href="entry://grelt%20up">grelt up</a></div></div>
<div class="m1"><div class="opt"><b>Derivatives:</b></div></div>
<div class="m2"><div class="opt"><b>grelterly</b> <b>(grel·ter·ly)</b> [<span class="t">-lē</span>]</div></div>
<div class="m2"><div class="opt"><i>[as <span class="color">submodifier</span>]</i></div></div>
<div class="m2"><div class="opt"><span class="ex">she smiled grelterly</span></div></div>
<div class="m2"><div class="opt"><span class="ex">grelterly done</span></div></div>
<div class="m1"><div class="opt"><b>Origin:</b></div></div>
<div class="m2"><div class="opt">invented: from <i>grel</i>, see <a href="entry://grel">grel</a></div></div>
<p class="s"><b>II</b></p>
<div class="m1"><span class="p" title="adjective">adj.</span> slightly creased</div>
<div class="opt"><b>Usage:</b>See usage at <a href="entry://crease">crease</a></div>"""

HEADWORD_LINE = """<link rel="stylesheet" href="NOAD3.css"><p>[<span class="t">ˈvôrp</span>]</p>
<div class="m1"><b><span class="color">vorp·ing</span></b></div>
<div class="m1"><span class="p" title="noun">n.</span> <i><span class="color">Heraldry</span></i> a small hill</div>"""

POINTER = """<div class="m1">[<span class="t">ɡrelt</span>] see <a href="entry://grelt">grelt</a></div>"""


class NoadParser(unittest.TestCase):
    def setUp(self):
        self.e = noad.parse("grelter", HTML)

    def of(self, kind):
        return [s for s in self.e.senses if s.kind == kind]

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, noad.COVERS))

    def test_headword_homograph_pos_pron(self):
        self.assertEqual((self.e.headword, self.e.homograph), ("grelter", ""))
        self.assertEqual(self.e.pos, ("verb", "noun", "adjective"))
        self.assertEqual([(p.ipa, p.region, p.audio) for p in self.e.prons], [("ɡrelt", "us", "")])

    def test_forms_are_variants_and_inflections_without_syllable_dots(self):
        self.assertEqual(self.e.forms, ("grelte", "grolt", "grelts", "grelting", "grelted", "grelten"))

    def test_numbered_sense_labels_and_examples(self):
        s1 = self.of("sense")[0]
        self.assertEqual((s1.pos, s1.number, s1.labels, s1.definition),
                         ("verb", "1", ("archaic", "literary", "no object"), "fold (a map) badly"))
        self.assertEqual([x.text for x in s1.examples], ["he grelted the map", "maps get grelted"])

    def test_subsense_with_qualified_label_form_group_and_trailing_grammar(self):
        sub = self.of("sense")[1]
        self.assertEqual((sub.number, sub.labels, sub.definition),
                         ("", ("chiefly British", "with object"), "fold upward"))  # its own label beats the block's

    def test_a_bare_word_definition_is_not_taken_for_a_qualifier(self):
        self.assertEqual(self.of("sense")[2].definition, "usually")

    def test_untitled_abbreviation_is_pos_plus_label(self):
        noun = self.of("sense")[3]
        self.assertEqual((noun.pos, noun.labels, noun.definition), ("noun", ("Scottish",), "a badly folded map"))

    def test_links_notes_and_see_also_do_not_leak(self):
        flat = repr(self.e.senses)
        for leaked in ("grelt the lot", "grelt up", "See also", "usage at"):
            self.assertNotIn(leaked, flat)
        self.assertEqual(len(self.of("sense")), 5)

    def test_derivative_and_etymology(self):
        (dr,) = self.of("derivative")
        self.assertEqual((dr.phrase, [(x.text, x.labels) for x in dr.examples]),
                         ("grelterly", [("she smiled grelterly", ("as submodifier",)), ("grelterly done", ("as submodifier",))]))
        self.assertEqual(self.e.etymology, "invented: from grel, see grel")

    def test_example_labels_reach_only_the_examples_right_after_their_line(self):
        self.assertEqual([x.labels for x in self.of("sense")[0].examples], [(), ()])

    def test_shared_sense_keeps_every_printed_part_of_speech(self):
        e = noad.parse("grelto", '<div class="m1"><b><span class="color">grel·to</span></b></div>'
                       '<div class="m1"><span class="p" title="noun">n.</span> <span class="color">(<i>pl.</i> <b>greltos</b>)</span>, '
                       '<span class="p">adv., &amp; adj.</span> another term for a fold</div>')
        self.assertEqual((e.pos, [s.pos for s in e.senses]), (("noun", "adverb & adjective"), ["noun, adverb & adjective"]))

    def test_block_grammar_label_yields_to_a_sense_and_labels_only_the_examples_it_precedes(self):
        obj = '<i>[{} <span class="p" title="object">obj.</span>]</i>'
        ex = '<div class="m1"><div class="opt"><span class="ex">{}</span></div></div>'
        e = noad.parse("grelt", '<div class="m1"><b><span class="color">grelt</span></b></div>'
                       '<div class="m1"><span class="p" title="verb">v.</span></div>'
                       '<div class="m1">1) fold a map</div>' + ex.format("he grelted it")
                       + '<div class="m1">' + obj.format("no") + '</div>' + ex.format("he grelted twice") + ex.format("she grelts")
                       + '<div class="m1">2) ' + obj.format("no") + ' <i><span class="color">informal</span></i> give up</div>'
                       + '<div class="m1"><span class="gray">■</span> rest a while</div>'
                       + '<div class="m1"><i><span class="color">figurative</span></i></div>' + ex.format("the day grelted")
                       + '<div class="m1">3) crease</div>'
                       + '<div class="m1">' + obj.format("with") + '</div>'
                       + '<div class="m1"><div class="opt"><b>Origin:</b></div></div><div class="m2"><div class="opt">invented</div></div>')
        self.assertEqual([(s.number, s.labels, s.definition) for s in e.senses], [
            ("1", ("with object",), "fold a map"), ("2", ("no object", "informal"), "give up"),
            ("", (), "rest a while"), ("3", ("with object",), "crease")])
        self.assertEqual([[(x.text, x.labels) for x in s.examples] for s in e.senses], [
            [("he grelted it", ()), ("he grelted twice", ("no object",)), ("she grelts", ("no object",))], [],
            [("the day grelted", ("figurative",))], []])
        self.assertEqual(problems(e), [])

    def test_each_label_line_starts_its_own_group_of_examples(self):
        # "[as noun]" + example, then "[as adj.]" + example: the second example is labelled "as adjective" only;
        # label lines printed one after another still add up
        ex = '<div class="m1"><div class="opt"><span class="ex">{}</span></div></div>'
        e = noad.parse("grelt", '<div class="m1"><b><span class="color">grelt</span></b></div>'
                       '<div class="m1"><span class="p" title="noun">n.</span>, <span class="p">adv., & adj.</span> softly</div>'
                       '<div class="m1"><i>[as <span class="color">noun</span>]</i></div>' + ex.format("the grelt of rain")
                       + '<div class="m1"><i>[as <span class="p" title="adjective">adj.</span>]</i></div>' + ex.format("a grelt murmur")
                       + '<div class="m1"><i><span class="color">figurative</span></i></div>'
                       + '<div class="m1"><i>[as <span class="p" title="adverb">adv.</span>]</i></div>' + ex.format("it went grelt"))
        (s,) = e.senses
        self.assertEqual([(x.text, x.labels) for x in s.examples], [
            ("the grelt of rain", ("as noun",)), ("a grelt murmur", ("as adjective",)),
            ("it went grelt", ("figurative", "as adverb"))])

    def test_a_grammar_label_carries_over_to_a_later_group_without_one(self):
        # "[no obj.]" + example, then "figurative" + example: the bracketed grammar label still applies (only a
        # bracketed label replaces it); "figurative" applies to its own group only
        ex = '<div class="m1"><div class="opt"><span class="ex">{}</span></div></div>'
        e = noad.parse("grelt", '<div class="m1"><b><span class="color">grelt</span></b></div>'
                       '<div class="m1"><span class="p" title="verb">v.</span></div>'
                       '<div class="m1">1) <i>[with <span class="p" title="object">obj.</span>]</i> drill</div>'
                       + ex.format("they grelted holes")
                       + '<div class="m1"><i>[no <span class="p" title="object">obj.</span>]</i></div>' + ex.format("it grelts through")
                       + '<div class="m1"><i><span class="color">figurative</span></i></div>' + ex.format("his eyes grelted")
                       + '<div class="m1"><i>[with <span class="p" title="object">obj.</span>]</i></div>' + ex.format("he grelted it"))
        (s,) = e.senses
        self.assertEqual([(x.text, x.labels) for x in s.examples], [
            ("they grelted holes", ()), ("it grelts through", ("no object",)),
            ("his eyes grelted", ("no object", "figurative")), ("he grelted it", ("with object",))])
        # a construction label ("[as modifier]") describes its own examples only
        e = noad.parse("grelt", '<div class="m1"><b><span class="color">grelt</span></b></div>'
                       '<div class="m1"><span class="p" title="noun">n.</span> a season</div>'
                       + '<div class="m1"><i>[as <span class="color">modifier</span>]</i></div>' + ex.format("grelt leaves")
                       + '<div class="m1"><i><span class="color">figurative</span></i></div>' + ex.format("the grelt of life"))
        self.assertEqual([x.labels for x in e.senses[0].examples], [("as modifier",), ("figurative",)])

    def test_an_abbreviation_printed_against_the_word_before_it_is_still_a_word(self):
        # "[with<span>obj.</span>]" (no space in the source) is the label "with object", not "withobject"
        ex = '<div class="m1"><div class="opt"><span class="ex">{}</span></div></div>'
        e = noad.parse("grelt", '<div class="m1"><b><span class="color">grelt</span></b></div>'
                       '<div class="m1"><span class="p" title="verb">v.</span> fold</div>'
                       '<div class="m1"><i>[with<span class="p" title="object">obj.</span>]</i></div>' + ex.format("he grelts it"))
        self.assertEqual(e.senses[0].examples[0].labels, ("with object",))

    def test_headword_line_without_a_header(self):
        e = noad.parse("vorping", HEADWORD_LINE)
        self.assertEqual((e.headword, e.pos, [p.ipa for p in e.prons]), ("vorping", ("noun",), ["ˈvôrp"]))
        self.assertEqual([(s.labels, s.definition) for s in e.senses], [(("Heraldry",), "a small hill")])

    def test_see_pointer_is_not_a_definition(self):
        e = noad.parse("grelting", POINTER)
        self.assertEqual((e.senses, e.stub, problems(e)), ((), "xref", []))
        self.assertEqual(self.e.stub, "")
        self.assertEqual(noad.parse("x", '<div class="m1"><b><span class="color">x</span></b></div>').stub, "empty")
        self.assertFalse(covered(e, noad.COVERS))

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", '<div class="m1"><span class="p">', "<<<>>>",
                     '<div class="m1"><div class="opt"><b>Derivatives:</b>', '<div class="m1">1) <i>[']:
            self.assertEqual(problems(noad.parse("x", junk)), [])
        self.assertEqual(noad.parse("x", "").headword, "x")


if __name__ == "__main__":
    unittest.main()
