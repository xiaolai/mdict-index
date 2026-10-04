"""LDOCE6 parser on synthetic records that mirror LDOCE6's markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import ldoce

AUDIO = '<a href="sound://exa/bre/x/p1.mp3"><img src="img/spkr_g.png"></a>'

HTML = f"""
<link type="text/css" rel="stylesheet" href="LDOCE6.css">
<div id="LDOCE6_grelt_1"><span class="entry" id="grelt_1"><span class="entryhead">
 <span class="hwd">grelt</span><span class="hyphenation">grelt</span><span class="homnum">1</span>
 <proncodes><span class="neutral"> /</span><span class="pron">ɡrelt</span><span class="amevarpron"><span class="neutral"> $ </span>ɡrɛlt</span><span class="neutral">/</span></proncodes>
 <span class="pos"> verb</span>
 <span class="inflections"><span class="neutral">(</span><span class="pasttense"><span class="infllab">past tense</span> grolt</span>
  <proncodes><span class="pron">ɡrəʊlt</span></proncodes><span class="neutral">)</span></span>
 <a href="sound://hwd/bre/g/grelt1.mp3"><img src="img/spkr_r.png"></a> <a href="sound://hwd/ame/g/grelt1.mp3"><img src="img/spkr_b.png"></a>
 <span class="buttons"><a class="popup-button" href="entry://@etymologies_grelt_1">Word Origin</a></span>
</span>
<span class="sense newline" id="grelt_1_s1"><span class="sensenum">1</span><span class="signpost">fold</span><span class="gram">[transitive]</span>
 <span class="def">to fold a   map badly</span><span class="neutral">: </span>
 <span class="gramexa"><span class="propform">grelt something up</span><span class="example">{AUDIO} He grelted it up.</span></span>
 <span class="example">{AUDIO} She <span class="colloinexa">grelts maps</span> daily <span class="geo">British English</span></span>
 <span class="f2nbox"><span class="heading">Register</span><span class="expl">NOT A DEF<span class="example">· NOT AN EXAMPLE</span></span></span>
 <span class="hint"><span class="warning">►</span>A hint, not an example.</span>
</span>
<span class="sense newline" id="grelt_1_s2"><span class="sensenum">2</span><span class="lexunit">grelt the lot</span><span class="registerlab"> informal</span>
 <span class="subsense"><span class="sensenum">a)</span><span class="def">to fail completely</span><span class="example">{AUDIO} We grelted the lot.</span></span>
 <span class="subsense"><span class="sensenum">b)</span><span class="def">to give up</span></span>
</span>
<span class="tail">
 <span class="thesbox"><span class="heading">THESAURUS</span><span class="section"><span class="exponent"><span class="exp">frump</span>
  <span class="def">THESAURUS DEF</span><span class="example">· THESAURUS EXAMPLE</span></span></span></span>
 <span class="grambox"><span class="heading">GRAMMAR</span><span class="expl"><span class="example">· GRAMMAR EXAMPLE</span></span></span>
 <span class="runon"><span class="deriv"><span>—</span>greltingly</span><span class="pos"> adverb</span></span>
</span>
<span class="phrvbentry" id="grelt_1_s9"><span class="entryhead"><span class="phrvbhwd">grelt <object>something</object> out</span>
 <span class="pos">phrasal verb</span><span class="geo"> British English</span></span>
 <span class="sense" id="grelt_1_s10"><span class="def">to unfold something</span><span class="example">{AUDIO} Grelt it out.</span></span>
</span>
</span></div>
<div id="LDOCE6_grelt_2"><span class="entry" id="grelt_2"><span class="entryhead"><span class="hwd">grelt</span>
 <span class="homnum">2</span><span class="pos"> noun</span><span class="gram"> [countable]</span>
 <a href="sound://hwd/bre/g/grelt1.mp3"><img src="img/spkr_r.png"></a></span>
 <span class="sense" id="grelt_2_s1"><span class="def">a badly folded map</span></span>
</span></div>
<script src="entry.js"></script>"""


class LdoceParser(unittest.TestCase):
    def setUp(self):
        self.e = ldoce.parse("grelt", HTML)

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, ldoce.COVERS))

    def test_headword_pos_and_no_homograph_when_several(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelt", "", ("verb", "noun")))

    def test_prons_skip_inflection_prons_and_audio_duplicates(self):
        self.assertEqual([(p.region, p.ipa, p.audio) for p in self.e.prons],
                         [("uk", "ɡrelt", "sound://hwd/bre/g/grelt1.mp3"), ("us", "ɡrɛlt", "sound://hwd/ame/g/grelt1.mp3")])
        self.assertEqual(self.e.forms, ("grolt",))

    def test_sense_labels_examples_and_box_exclusion(self):
        s1 = self.e.senses[0]
        self.assertEqual((s1.kind, s1.pos, s1.number, s1.labels, s1.definition),
                         ("sense", "verb", "1", ("transitive",), "to fold a map badly"))
        self.assertEqual([x.text for x in s1.examples], ["He grelted it up.", "She grelts maps daily"])
        everything = repr(self.e)
        for leaked in ("NOT A", "THESAURUS", "GRAMMAR EXAMPLE", "hint"):
            self.assertNotIn(leaked, everything)

    def test_lexunit_subsenses_become_numbered_phrases(self):
        a, b = [s for s in self.e.senses if s.kind == "phrase"]
        self.assertEqual((a.number, a.phrase, a.labels, a.definition, a.examples[0].text),
                         ("2a", "grelt the lot", ("informal",), "to fail completely", "We grelted the lot."))
        self.assertEqual((b.number, b.definition), ("2b", "to give up"))

    def test_examples_printed_after_a_subsense_are_kept(self):
        html = f"""<span class="entry"><span class="entryhead"><span class="hwd">frelt</span><span class="pos"> verb</span></span>
         <span class="sense"><span class="sensenum">1</span><span class="gram">[intransitive]</span>
          <span class="example">{AUDIO} A lead example.</span>
          <span class="subsense"><span class="sensenum">a)</span><span class="def">to hum</span><span class="example">{AUDIO} Bees frelt.</span></span>
          <span class="subsense"><span class="sensenum">b)</span><span class="def">to rush about</span></span><span class="neutral">: </span>
          <span class="example">{AUDIO} She frelted around.</span>
          <span class="gramexa"><span class="propform">frelt through</span><span class="example">{AUDIO} News frelted through.</span></span>
         </span></span>"""
        e = ldoce.parse("frelt", html)
        self.assertEqual([(s.number, s.definition, [x.text for x in s.examples]) for s in e.senses],
                         [("1", "", ["A lead example."]), ("1a", "to hum", ["Bees frelt."]),
                          ("1b", "to rush about", ["She frelted around.", "News frelted through."])])
        self.assertEqual(problems(e), [])

    def test_head_labels_reach_ordinary_senses(self):
        noun = self.e.senses[-1]
        self.assertEqual((noun.pos, noun.labels), ("noun", ("countable",)))
        html = """<span class="entry"><span class="entryhead"><span class="hwd">frelt</span><span class="pos"> verb</span>
         <span class="gram"> [transitive]</span><span class="registerlab"> informal</span></span>
         <span class="sense"><span class="sensenum">1</span><span class="gram">[transitive]</span><span class="geo"> British English</span>
          <span class="def">to fold</span></span>
         <span class="sense"><span class="sensenum">2</span><span class="lexunit">frelt the lot</span><span class="def">to fail</span></span>
         <span class="tail"><span class="runon"><span class="deriv">—frelter</span><span class="pos"> noun</span></span></span></span>"""
        self.assertEqual([(s.kind, s.labels) for s in ldoce.parse("frelt", html).senses],
                         [("sense", ("transitive", "informal", "British English")),
                          ("phrase", ("informal",)),  # the head's grammar is the headword's, not the phrase's
                          ("derivative", ())])

    def test_a_head_with_several_parts_of_speech_gives_them_all_to_its_senses(self):
        html = """<span class="entry"><span class="entryhead"><span class="hwd">frelt</span><span class="pos"> determiner</span>
         <span class="pos"><span class="neutral">, </span>pronoun</span><span class="pos"><span class="neutral">, </span>adverb</span></span>
         <span class="sense"><span class="def">every one</span></span></span>"""
        e = ldoce.parse("frelt", html)
        self.assertEqual((e.pos, e.senses[0].pos), (("determiner", "pronoun", "adverb"), "determiner, pronoun, adverb"))

    def test_phrasal_verb_and_derivative(self):
        (pv,) = [s for s in self.e.senses if s.kind == "phrasal_verb"]
        self.assertEqual((pv.phrase, pv.pos, pv.labels, pv.definition),
                         ("grelt something out", "phrasal verb", ("British English",), "to unfold something"))
        (d,) = [s for s in self.e.senses if s.kind == "derivative"]
        self.assertEqual((d.phrase, d.pos), ("greltingly", "adverb"))

    def test_second_homograph_senses_carry_its_pos(self):
        self.assertEqual((self.e.senses[-1].pos, self.e.senses[-1].definition), ("noun", "a badly folded map"))

    def test_popup_records_are_popup_stubs_of_their_entry(self):
        etym = ldoce.parse("@etymologies_grelt_1", '<span class="entry" id="grelt_1"><span class="popheader popetym">WORD ORIGIN</span>'
                           '<span class="hyphenation">grelt</span><span class="etymsense"><span class="etymcentury">1900-2000</span> '
                           '<span class="etymorigin">grelten</span> to crumple</span></span>')
        self.assertEqual((etym.headword, etym.homograph, etym.etymology, etym.stub, etym.part_of),
                         ("grelt", "1", "1900-2000 grelten to crumple", "popup", "grelt"))
        verbs = ldoce.parse("@verbs_grelt_1", '<span class="entry"><div class="verbtable"><div class="lemma">grelt (BrE)</div><table>'
                            '<tr><td><span class="verb_form">grelt</span></td></tr><tr><td><span class="verb_form">grelts</span></td></tr></table></div></span>')
        self.assertEqual((verbs.forms, verbs.part_of), (("grelts",), "grelt"))
        bank = ldoce.parse("@examples_grelt", '<span class="entry"><span class="popheader popexa">EXAMPLES FROM THE CORPUS</span>'
                           '<ul class="exas"><li>They <span class="nodeword">grelt</span> often.</li></ul></span>')
        self.assertEqual((bank.part_of, [x.text for s in bank.senses for x in s.examples]), ("grelt", ["They grelt often."]))
        self.assertFalse(covered(bank, ldoce.COVERS))
        thes = ldoce.parse("@thesaurus_m_grelt", '<span class="entry"><span class="section"><span class="def">SYNONYM DEF</span></span></span>')
        self.assertEqual((thes.stub, thes.part_of, thes.senses), ("popup", "grelt", ()))
        for e in (etym, verbs, bank, thes):
            self.assertEqual(problems(e), [])

    def test_popup_part_of_is_spelled_as_printed(self):
        hyphenated = ldoce.parse("@examples_grelt_proof", '<span class="entry"><ul class="exas"><li>A <span class="nodeword">grelt</span>-proof map.</li></ul></span>')
        self.assertEqual(hyphenated.part_of, "grelt-proof")
        affix = ldoce.parse("@collocations__grelt", '<span class="entry"><span class="popheader popcollo">COLLOCATIONS</span></span>')
        self.assertEqual((affix.stub, affix.part_of), ("popup", "-grelt"))
        quoted = ldoce.parse("@examples_grelter_s_map_the", '<span class="entry"><ul class="exas"><li>The grelter’s map again.</li></ul></span>')
        self.assertEqual(quoted.part_of, "grelter's map")

    def test_popup_part_of_prefers_the_spelling_inside_a_sentence(self):
        bank = ldoce.parse("@examples_grelt", '<span class="entry"><span class="popheader popexa">EXAMPLES FROM OTHER DICTIONARIES</span>'
                           '<ul class="exas"><li>Grelt the map twice.</li><li>They grelt often.</li></ul></span>')
        self.assertEqual((bank.part_of, bank.headword), ("grelt", "grelt"))
        name = ldoce.parse("@examples_grelt", '<span class="entry"><ul class="exas"><li>Grelt is a town.</li></ul></span>')
        self.assertEqual(name.part_of, "Grelt")

    def test_numbered_popups_are_index_stubs(self):
        for key in ("@wordfamilies_0042", "@thesaurus_ws0042", "@thesaurus_wsrefs0042", "@thesaurus_a0042"):
            e = ldoce.parse(key, '<span class="entry"><span class="popheader popwf">WORD FAMILY</span><span class="wfwd">grelt</span></span>')
            self.assertEqual((e.headword, e.stub, e.part_of, problems(e)), (key, "index", "", []))

    def test_cross_reference_record_is_an_xref_stub(self):
        e = ldoce.parse("frelt", '<span class="entry" id="frelt"><span class="entryhead"><span class="hwd">frelt</span></span>'
                        '<span class="tail"><span class="crossref"><span class="neutral"> →</span><a goto="x"> '
                        '<span class="refhwd">grelt out</span></a></span></span></span>')
        self.assertEqual((e.stub, e.senses, problems(e)), ("xref", (), []))
        related = ldoce.parse("frelting", '<span class="entry"><span class="entryhead"><span class="hwd">frelting</span></span>'
                              '<span class="sense"><span class="relatedwd"><span class="neutral">→</span> frelt</span></span></span>')
        self.assertEqual(related.stub, "xref")
        self.assertEqual(self.e.stub, "")

    def test_pron_note_and_example_labels(self):
        e = ldoce.parse("a", '<span class="entry"><span class="entryhead"><span class="hwd">frelt</span><proncodes><span class="neutral">/</span>'
                        '<span class="pron">frəlt</span><span class="pronstrong"><span class="neutral">; </span>strong</span>'
                        '<span class="pron"> frelt</span><span class="neutral">/</span></proncodes></span>'
                        '<span class="sense"><span class="def">a fold</span></span></span>')
        self.assertEqual([(p.region, p.ipa, p.note) for p in e.prons], [("uk", "frəlt", ""), ("us", "frəlt", ""), ("uk", "frelt", "strong")])
        s1 = self.e.senses[0]
        self.assertEqual([x.labels for x in s1.examples], [(), ("British English",)])

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", "<span class='entry'><span class='sense'><span class='def'>", "<<<>>>"]:
            e = ldoce.parse("x", junk)
            self.assertEqual((e.headword, problems(e)), ("x", []))
        self.assertEqual(problems(ldoce.parse("@examples_", "<")), [])


if __name__ == "__main__":
    unittest.main()
