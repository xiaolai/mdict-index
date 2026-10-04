"""AHD parser on synthetic records that mirror its markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import ahd

HTML = """<link rel="stylesheet" type="text/css" href="ahd.css">
<div class="results">
<div class="rtseg"><b>flor·p<sup>1</sup></b> also <b>flor·pe</b> <a class="sound" href="sound:///wavs/F0000001.wav"><img src="/images/mini-speaker.png" border="0"></a>
 (fl<span class="MinionNew">\ue013</span>rp<span class="MinionNew">\ue01f</span>, fl<span class="MinionNew">\ue00a</span>ôr<span class="MinionNew">′</span>p)</div>
<div class="pseg"><i>n.</i> <i>pl.</i> <b>flor·ps</b>
 <div class="ds-list"><b>1. </b> A small wooden spoon: <i>stirred the tea with a florp; lost a florp.</i> See Usage Note at <a href="entry://ladle">NOTELINK</a>.</div>
 <div class="ds-list"><b>2. </b><span class="subject">Nautical</span>
  <div class="sds-list"><b>a. </b> A ladle used on ships.</div>
  <div class="sds-list"><b>b. </b> A crew member who stirs: <i>"The florp stirred all night"</i> <i>(Ima Writer).</i></div></div>
 <div class="ds-list"><b>3. </b> A kind of fish <i>(Florpus invented)</i> found in rivers. <span class="seesynonym">See Synonyms at</span> <a href="entry://fish">SYNLINK</a>.</div>
</div>
<div class="pseg"><i>v.</i> <i>tr.</i> <span class="subject">Informal</span>
 <div class="ds-single">To stir with a florp.</div></div>
<div class="runseg"><b>flor<span class="MinionNew">\ue01f</span>p·er</b> <i>n.</i></div>
<b><i>Idiom:</i></b>
<div class="idmseg"><b><i>florp the pot</i></b> <i>Slang</i> <div class="ds-single">To work for nothing.</div></div>
<b><i>Phrasal Verb:</i></b>
<div class="pvseg"><b><i>florp up</i></b> <div class="ds-single">To stir hard.</div></div>
<hr align="left" width="25%">
<div class="etyseg">[Invented, from <i>florpa</i>.]</div>
<div class="syntx"><b>Synonyms:</b> SYNONYM PARAGRAPH</div>
<div class="usen"><b><i>Usage Note:</i></b> USAGE NOTE TEXT</div>
<div class="wrdhst"><b>Word History:</b> WORD HISTORY TEXT</div>
<a class="arts" href="#"><img src="/arts/florp.jpg"></a><div class="figure"></div><div class="scp">Florpus pictus</div>
</div>"""

NOTED = """<div class="results"><div class="rtseg"><b>flen</b> <a class="sound" href="sound:///wavs/F0000002.wav"></a>
 (fl<span class="MinionNew">ĕ</span>n, <i>th</i>ĕn; fl<span class="MinionNew">ə</span>n <i>when unstressed;</i> fl<span class="MinionNew">ā</span>n
 <i>before a vowel</i>)</div><div class="pseg"><i>adv.</i><div class="ds-single">In an invented way.</div></div></div>"""

MID_WORD = """<div class="results"><div class="rtseg"><b>flup</b> (<i>a</i> p<i>-like sound, invented,</i> fl<span class="MinionNew">ŭ</span>p)</div>
<div class="pseg"><i>interj.</i><div class="ds-single">Used in a test.</div></div></div>"""

QUALIFIED = """<div class="results"><div class="rtseg"><b>flab</b> <a class="sound" href="sound:///wavs/F0000003.wav"></a>
 (fl<span class="MinionNew">ă</span>b; <i>British</i> fl<span class="MinionNew">ä</span>b)<span class="subject">Informal</span> <i>Computers</i></div>
<div class="pseg"><i>n.</i><div class="ds-list"><b>1. </b> A soft lump.</div>
<div class="ds-list"><b>2. </b><span class="subject">Slang</span> A lazy person.</div></div>
<div class="idmseg"><b><i>flab out</i></b> <div class="ds-single">To relax.</div></div></div>"""

STANDALONE_IDIOM = """<div class="idmseg"><span></span><b><i>florp around</i></b><span></span>
 <div class="ds-single"><span></span> To idle: <span></span><font><i>florped around all day.</i></font></div></div>
<div class="mainentry">Main Entry: <a href="entry://florp">florp</a></div>"""

ROOT = """<table border="0" cellspacing="5"><tr><td><a name="IR1">‌</a><b><font>florp-</font></b><br>
 Also <span>flerp-</span>.<br>To stir.<br>Derivatives include <a href="entry://florp">florp</a>.<ol><li>ROOT DETAIL</li></ol></td></tr></table>"""


class AhdParser(unittest.TestCase):
    def setUp(self):
        self.e = ahd.parse("florp", HTML)

    def test_valid_and_covered(self):
        for e in (self.e, ahd.parse("florp around", STANDALONE_IDIOM), ahd.parse("Indo-European root: florp-", ROOT)):
            self.assertEqual(problems(e), [])
            self.assertTrue(covered(e, ahd.COVERS))

    def test_head_without_syllable_dots(self):
        e = self.e
        self.assertEqual((e.headword, e.homograph, e.pos), ("florp", "1", ("n.", "v. tr.")))
        self.assertEqual(e.forms, ("florpe", "florps"))
        self.assertEqual(e.etymology, "Invented, from florpa.")

    def test_pronunciation_glyphs_are_mapped(self):
        self.assertEqual([(p.ipa, p.region, p.audio) for p in self.e.prons],
                         [("flo͞orpˈ, flKHôr′p", "", "sound:///wavs/F0000001.wav")])

    def test_pronunciation_variants_and_notes(self):
        e = ahd.parse("flen", NOTED)
        self.assertEqual([(p.ipa, p.audio, p.note) for p in e.prons],
                         [("flĕn, thĕn", "sound:///wavs/F0000002.wav", ""), ("flən", "", "when unstressed"),
                          ("flān", "", "before a vowel")])
        self.assertEqual(problems(e), [])

    def test_a_note_that_starts_mid_word(self):
        (p,) = ahd.parse("flup", MID_WORD).prons
        self.assertEqual((p.ipa, p.note), ("flŭp", "a p-like sound, invented"))

    def test_a_one_word_qualifier_is_a_note_not_a_respelling(self):
        e = ahd.parse("flab", QUALIFIED)
        self.assertEqual([(p.ipa, p.note) for p in e.prons], [("flăb", ""), ("fläb", "British")])
        self.assertEqual(problems(e), [])

    def test_entry_labels_reach_every_ordinary_sense(self):
        e = ahd.parse("flab", QUALIFIED)
        self.assertEqual([(s.kind, s.labels) for s in e.senses],
                         [("sense", ("Informal", "Computers")), ("sense", ("Informal", "Computers", "Slang")),
                          ("phrase", ())])
        self.assertEqual([s.labels for s in self.e.senses if s.kind == "sense"][0], ())

    def test_senses_examples_and_pointers(self):
        s1 = self.e.senses[0]
        self.assertEqual((s1.number, s1.pos, s1.definition), ("1", "n.", "A small wooden spoon"))
        self.assertEqual([x.text for x in s1.examples], ["stirred the tea with a florp", "lost a florp."])
        s3 = [s for s in self.e.senses if s.number == "3"][0]
        self.assertEqual((s3.definition, s3.examples), ("A kind of fish (Florpus invented) found in rivers.", ()))

    def test_subsenses_inherit_labels_and_quotations_get_sources(self):
        subs = {s.number: s for s in self.e.senses if s.number.startswith("2")}
        self.assertEqual(sorted(subs), ["2a", "2b"])
        self.assertEqual((subs["2a"].labels, subs["2a"].definition), (("Nautical",), "A ladle used on ships."))
        (quote,) = subs["2b"].examples
        self.assertEqual((quote.kind, quote.text, quote.source), ("quotation", '"The florp stirred all night"', "Ima Writer"))

    def test_verb_section_label(self):
        verb = [s for s in self.e.senses if s.pos == "v. tr."][0]
        self.assertEqual((verb.labels, verb.definition), (("Informal",), "To stir with a florp."))

    def test_run_on_idiom_and_phrasal_verb(self):
        rest = [(s.kind, s.phrase, s.pos, s.labels, s.definition) for s in self.e.senses if s.kind != "sense"]
        self.assertEqual(rest, [("derivative", "florper", "n.", (), ""),
                                ("phrase", "florp the pot", "", ("Slang",), "To work for nothing."),
                                ("phrasal_verb", "florp up", "", (), "To stir hard.")])

    def test_side_boxes_are_left_out(self):
        blob = repr(self.e)
        for leaked in ("SYNONYM", "USAGE NOTE", "WORD HISTORY", "pictus", "NOTELINK", "SYNLINK", "Synonyms at"):
            self.assertNotIn(leaked, blob)

    def test_standalone_idiom_record(self):
        e = ahd.parse("florp around", STANDALONE_IDIOM)
        (s,) = e.senses
        self.assertEqual((e.headword, s.kind, s.phrase, s.definition, s.examples[0].text),
                         ("florp around", "phrase", "florp around", "To idle", "florped around all day."))

    def test_indo_european_root_gloss(self):
        e = ahd.parse("Indo-European root: florp-", ROOT)
        self.assertEqual([s.definition for s in e.senses], ["To stir."])

    def test_no_stubs(self):
        self.assertEqual(self.e.stub, "")

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", "<div class='pseg'><div class='ds-list'><b>1.", "<<<>>>"]:
            e = ahd.parse("x", junk)
            self.assertEqual((e.headword, problems(e)), ("x", []))


if __name__ == "__main__":
    unittest.main()
