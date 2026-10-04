"""MED parser on synthetic records that mirror macmillandictionary.com's markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import med

THES = ('<div class="THES"><div class="synonyms"><span class="synonyms">Synonyms and related words</span></div>'
        '<div class="thessnippet"><span class="h2">SYNONYM HEADING:</span><span class="synonyms">frump, wrangle</span></div></div>')

HTML = f"""
<link rel="stylesheet" type="text/css" href="entry.css">
<span class="BASE" id="grelt_1">grelt</span>
<div id="headbar"><span class="PART-OF-SPEECH"><span class="SEP PART-OF-SPEECH-before"> </span>verb</span>
 <span class="PRONS"><a href="sound://grelt_British_English_pronunciation.mp3"><img src="uk.png"></a>
  <a href="sound://grelt_American_English_pronunciation.mp3"><img src="us.png"></a>
  <span class="PRON show_less"><span class="SEP PRON-before"> /</span>ɡrelt<span class="SEP PRON-after">/</span></span></span>
 <div class="wordforms show_less"><table><tr><td><span class="INFLECTION-TYPE">past tense</span></td>
  <td><span class="INFLECTION-CONTENT"><span class="INFLECTION-ENTRY">grolt</span></span></td></tr></table></div>
</div>
<div class="block_innerleftcol"><div class="block_relatedframe"><div class="entrylist"><ul><li>
 <span class="BASE">RELATED WORD</span><span class="PART-OF-SPEECH">noun</span></li></ul></div></div></div>
<div id="leftContent"><div class="entryBody"><ol class="senses">
 <li><div class="SENSE" id="grelt_1__1"><div class="SENSE-BODY"><div class="SENSE-NUM">1</div>
  <span class="SYNTAX-CODING show_less"><span class="SEP SYNTAX-CODING-before"> [</span>transitive<span class="SEP SYNTAX-CODING-after">]</span></span>
  <span class="STYLE-LEVEL"><span class="SEP STYLE-LEVEL-before"> </span>informal</span>
  <span class="DEFINITION"><span class="SEP DEFINITION-before"> </span>to fold a <a class="QUERY" href="entry://map">map</a> badly</span>
  <div class="EXAMPLES"><strong>grelt something up</strong><span class="SEP EXAMPLE-before">:</span>
   <p class="EXAMPLE">He <span class="EXAMPLE"><a href="entry://grelt">grelted</a></span> it up.</p></div>
  {THES}
  <ol class="SUB-SENSES"><li><div class="SUB-SENSE-BODY"><div class="SENSE-NUM">a.</div><div class="SUB-SENSE-CONTENT">
   <span class="DIALECT"><span class="SEP DIALECT-before"> </span>British</span>
   <span class="DEFINITION">to fold paper badly</span>
   <div class="EXAMPLES show_less"><p class="EXAMPLE">Paper grelts easily.</p></div></div></div></li></ol>
 </div>
 <div class="SENSE-INFO"><div class="SENSE-INFO1"><div class="sidebox"><div class="USAGE-NOTE-HEAD">Usage note</div>
  <div class="sideboxbody"><div class="p">USAGE NOTE TEXT<span class="EX">USAGE EXAMPLE</span></div></div></div></div></div>
 </div></li>
 <li><div class="SENSE" id="grelt_1__5"><div class="greybackground"><span class="textfromopen">From our crowdsourced Open Dictionary</span></div>
  <div class="SENSE-BODY"><div class="SENSE-NUM">2</div><span class="MULTIWORD"><span class="BASE">grelt the lot</span></span>
  <span class="DEFINITION">to fail completely</span>
  <span class="details"><span class="SEP DETAILS-before">Submitted</span><span class="user">by SUBMITTER</span></span></div></div></li>
</ol></div>
<h2 class="TITLE">phrasal verb</h2><div id="PV-HOMOGRAPH"><div class="phrasalverb"><div class="PV-HEAD">
 <h2 class="ENTRY"><span class="BASE">grelt out</span></h2>
 <span class="SYNTAX-CODING"><span class="SEP SYNTAX-CODING-before">[</span>intransitive<span class="SEP SYNTAX-CODING-after">]</span></span></div>
 <div class="SENSE"><div class="phrasalverbsense"><div class="SENSE-NUM">1</div><strong>[grelt out]</strong>
  <span class="DEFINITION">to unfold</span></div></div></div></div>
<div id="phrases_container"><h2 class="TITLE">phrases</h2><ul><li class="PHR-XREF"><a href="entry://grelt away">grelt away</a></li></ul></div>
</div>
<span class="BASE" id="grelt_2">grelt</span>
<div id="headbar"><span class="PART-OF-SPEECH">noun</span></div>
<div id="leftContent"><div class="entryBody"><ol class="senses"><li><div class="SENSE"><div class="SENSE-BODY">
 <span class="DEFINITION">a badly folded map</span></div></div></li></ol></div></div>"""


class MedParser(unittest.TestCase):
    def setUp(self):
        self.e = med.parse("grelt", HTML)

    def test_header_labels_reach_the_homographs_senses(self):
        html = """<span class="BASE" id="frelt_1">frelt</span>
        <div id="headbar"><span class="PART-OF-SPEECH">verb</span>
         <span class="SYNTAX-CODING"><span class="SEP SYNTAX-CODING-before"> [</span>transitive<span class="SEP SYNTAX-CODING-after">]</span></span>
         <span class="STYLE-LEVEL"><span class="SEP STYLE-LEVEL-before"> </span>mainly journalism</span></div>
        <div class="SENSE"><div class="SENSE-BODY"><div class="SENSE-NUM">1</div>
         <span class="DIALECT">British</span><span class="DEFINITION">to fold</span>
         <ol class="SUB-SENSES"><li><div class="SUB-SENSE-BODY"><div class="SENSE-NUM">a.</div><div class="SUB-SENSE-CONTENT">
          <span class="DEFINITION">to crease</span></div></div></li></ol></div></div>
        <div class="SENSE"><div class="SENSE-BODY"><div class="SENSE-NUM">2</div>
         <span class="MULTIWORD"><span class="BASE">frelt the lot</span></span><span class="DEFINITION">to fail</span></div></div>
        <div class="phrasalverb"><div class="PV-HEAD"><h2 class="ENTRY"><span class="BASE">frelt out</span></h2></div>
         <div class="SENSE"><div class="phrasalverbsense"><span class="DEFINITION">to unfold</span></div></div></div>
        <span class="BASE" id="frelt_2">frelt</span><div id="headbar"><span class="PART-OF-SPEECH">noun</span></div>
        <div class="SENSE"><div class="SENSE-BODY"><span class="DEFINITION">a fold</span></div></div>"""
        e = med.parse("frelt", html)
        self.assertEqual([(s.kind, s.number, s.labels) for s in e.senses],
                         [("sense", "1", ("transitive", "mainly journalism", "British")),
                          ("sense", "1a", ("transitive", "mainly journalism", "British")),
                          ("phrase", "2", ("mainly journalism",)),  # the grammar code is the headword's
                          ("phrasal_verb", "", ()), ("sense", "", ())])
        self.assertEqual(problems(e), [])

    def test_every_transcription_of_a_header_keeps_its_own_audio(self):
        html = """<span class="BASE" id="frelt">frelt</span><div id="headbar"><span class="PRONS">
         <a href="sound://frelt_British_English_pronunciation_1.mp3"><img src="uk.png"></a>
         <a href="sound://frelt_American_English_pronunciation.mp3"><img src="us.png"></a>
         <span class="PRON"><span class="SEP PRON-before"> /</span>frelt<span class="SEP PRON-after">/</span></span>
         <a href="sound://frelt_British_English_pronunciation.mp3"><img src="uk.png"></a>
         <a href="sound://frelt_American_English_pronunciation.mp3"><img src="us.png"></a>
         <span class="PRON"><span class="SEP PRON-before"> /</span>frilt<span class="SEP PRON-after">/</span></span></span></div>
        <div class="SENSE"><div class="SENSE-BODY"><span class="DEFINITION">a fold</span></div></div>"""
        e = med.parse("frelt", html)
        self.assertEqual([(p.region, p.ipa, p.audio) for p in e.prons],
                         [("uk", "frelt", "sound://frelt_British_English_pronunciation_1.mp3"),
                          ("us", "", "sound://frelt_American_English_pronunciation.mp3"),
                          ("uk", "frilt", "sound://frelt_British_English_pronunciation.mp3")])

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, med.COVERS))

    def test_headword_pos_prons_forms(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelt", "", ("verb", "noun")))
        self.assertEqual([(p.region, p.ipa, p.audio) for p in self.e.prons],
                         [("uk", "ɡrelt", "sound://grelt_British_English_pronunciation.mp3"),
                          ("us", "", "sound://grelt_American_English_pronunciation.mp3")])
        self.assertEqual(self.e.forms, ("grolt",))

    def test_senses_labels_examples_and_subsenses(self):
        s1, s1a = self.e.senses[:2]
        self.assertEqual((s1.kind, s1.pos, s1.number, s1.labels, s1.definition, [x.text for x in s1.examples]),
                         ("sense", "verb", "1", ("transitive", "informal"), "to fold a map badly", ["He grelted it up."]))
        self.assertEqual((s1a.number, s1a.labels, s1a.definition, s1a.examples[0].text),
                         ("1a", ("transitive", "informal", "British"), "to fold paper badly", "Paper grelts easily."))

    def test_side_boxes_and_related_words_do_not_leak(self):
        everything = repr(self.e)
        for leaked in ("SYNONYM", "frump", "USAGE", "RELATED WORD", "SUBMITTER", "grelt away"):
            self.assertNotIn(leaked, everything)

    def test_multiword_phrase_and_embedded_phrasal_verb(self):
        (phrase,) = [s for s in self.e.senses if s.kind == "phrase"]
        self.assertEqual((phrase.number, phrase.phrase, phrase.definition), ("2", "grelt the lot", "to fail completely"))
        (pv,) = [s for s in self.e.senses if s.kind == "phrasal_verb"]
        self.assertEqual((pv.phrase, pv.pos, pv.labels, pv.definition),
                         ("grelt out", "phrasal verb", ("intransitive",), "to unfold"))

    def test_second_homograph(self):
        self.assertEqual((self.e.senses[-1].pos, self.e.senses[-1].definition), ("noun", "a badly folded map"))

    def test_phrase_record_and_thesaurus_page(self):
        rec = med.parse("grelt the lot", '<span class="BASE" id="grelt-the-lot">grelt the lot</span><div id="headbar">'
                        '<span class="PART-OF-SPEECH">phrase</span></div><div class="SENSE"><div class="SENSE-BODY">'
                        '<span class="DEFINITION">to fail completely</span></div></div>')
        (s,) = rec.senses
        self.assertEqual((rec.homograph, s.kind, s.phrase, s.pos), ("", "phrase", "grelt the lot", "phrase"))
        page = med.parse("Ways of folding", '<h1 class="cattitle">Ways of folding<span class="headword-definition"> - thesaurus</span></h1>'
                         '<div id="leftContent"><div class="entry top"><h3>grelt</h3><span class="part-of-speech">verb</span><p>to fold</p></div></div>')
        self.assertEqual((page.headword, page.senses), ("Ways of folding", ()))

    def test_buzzword_definition_when_nothing_else(self):
        e = med.parse("grelt", '<span class="BASE" id="grelt">grelt</span><div id="wotwentry"><h1><span class="headword">grelt</span></h1>'
                      '<span class="part-of-speech">verb</span><p class="wotwdefinition">to fold badly</p><div id="examples">'
                      '<div class="example"><p>\'They <strong>grelt</strong> it.\'</p><span class="source"><a href="#">Some Paper'
                      ' <span class="sourcedate">1st May 2001</span></a></span></div></div></div><div id="wotwarticle"><p>ESSAY</p></div>')
        (s,) = e.senses
        self.assertEqual((s.definition, s.examples[0].text, s.examples[0].kind, s.examples[0].source, s.examples[0].date),
                         ("to fold badly", "They grelt it.", "quotation", "Some Paper", "1st May 2001"))
        self.assertEqual(problems(e), [])

    def test_stub_reasons_come_from_the_markup(self):
        def page(body):
            return '<span class="BASE" id="frelt">frelt</span><div id="headbar"></div><div id="leftContent">' + body + '</div>'
        cases = {
            "variant": page('<div class="GREF-GROUP"><span class="GREF-TYPE">a British spelling of</span>'
                            '<span class="GREF-ENTRY"><a href="entry://grelt">grelt</a></span></div>'),
            "inflection": page('<div class="GREF-GROUP"><span class="GREF-TYPE">the past tense of</span>'
                               '<span class="GREF-ENTRY"><a href="entry://grelt">grelt</a></span></div>'),
            "xref": page('<div class="SENSE"><div class="SENSE-BODY"><span class="SAMEAS"><span class="SEP SAMEAS-before">same as</span>'
                         '<a href="entry://grelt">grelt</a></span><div class="EXAMPLES"><p class="EXAMPLE">It frelts.</p></div></div></div>'),
            "index": '<h1 class="cattitle">Ways of folding<span class="headword-definition"> - thesaurus</span></h1>',
        }
        for reason, html in cases.items():
            e = med.parse("frelt", html)
            self.assertEqual((e.stub, e.part_of, problems(e)), (reason, "", []), reason)
            self.assertFalse(covered(e, med.COVERS))
        self.assertEqual(self.e.stub, "")
        facts = med.parse("Freltland", '<span class="BASE" id="frelt">Freltland</span><div class="SENSE"><div class="SENSE-BODY">'
                          '<span class="PROPERTIES"><span class="PROPERTY-NAME">Capital</span></span></div></div>')
        self.assertEqual(facts.stub, "")  # no printed reason: a content record, left uncovered

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", "<span class='BASE' id='x_1'>", "<div id='headbar'><div class='SENSE'>"]:
            e = med.parse("x", junk)
            self.assertEqual(problems(e), [])
        self.assertEqual(med.parse("x", "").headword, "x")


if __name__ == "__main__":
    unittest.main()
