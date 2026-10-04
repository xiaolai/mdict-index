"""OALECD9 parser on synthetic entries that mirror the MDict v1.2 markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import oalecd

PRON = """<pron-gs wd="grelt"><pron-g-blk><brelabel><xhtml:a href="help:bre">BrE</xhtml:a></brelabel>
 <a href="sound://grelt__gb_1.mp3"><audio-gb><pron-g><xhtml:a href="help:phonetics"><phon-blk>/<phon>ɡrelt</phon>/</phon-blk><audio name="grelt__gb_1"></audio></xhtml:a></pron-g></audio-gb></a></pron-g-blk>
 <pron-g-blk><xhtml:br></xhtml:br><namelabel><xhtml:a href="help:name">NAmE</xhtml:a></namelabel>
 <a href="sound://grelt__us_1.mp3"><audio-us><pron-g><xhtml:a href="help:phonetics"><phon-blk>/<phon>ɡrɛlt</phon>/</phon-blk></xhtml:a></pron-g></audio-us></a></pron-g-blk></pron-gs>"""

HTML = f"""<head><link rel="stylesheet" href="oalecd9.css"></head><script src="oalecd9.js"></script>
<div class="cixing_tiaozhuan"><div class="cixing_tiaozhuan_part"><a href="#verb">verb</a>,</div></div>
<div id="verb" class="cixing_part">
<top-g><hkey><xhtml:a href="help:keyword"><symbol type="key">K</symbol></xhtml:a></hkey>
 <h>grelt<homonym hm="1"></homonym><hm><xhtml:a href="help:hom1">1</xhtml:a></hm></h>{PRON}
 <v-gs-blk type="vs"> (<v-gs><v-g-blk><v-g><v-blk><vgslabel>also </vgslabel><v><xhtml:a href="d:grelte">grel·te</xhtml:a></v></v-blk></v-g></v-g-blk></v-gs>)</v-gs-blk>
 <v-gs-blk type="ff"><v-gs><v-g-blk><v-g><v-blk><v>great relt</v></v-blk></v-g></v-g-blk></v-gs></v-gs-blk>
</top-g>
<subentry-g><top-g><pos-g><pos-blk><pos onclick="toggle_infl(this)"><xhtml:a href="helpp:v">verb</xhtml:a></pos></pos-blk></pos-g>
 <res-g><vp-gs><vpform>past simple</vpform><vp-g form="root"><vp><xhtml:a href="d:grelt">grelt</xhtml:a></vp>{PRON}</vp-g>
  <vp-g form="past"><vp><xhtml:a href="d:grelted">grelted</xhtml:a></vp>
   <pron><pron-g-blk><brelabel>BrE</brelabel><a href="sound://grelted__gb_1.mp3"><audio-gb><pron-g><phon-blk>/<phon>ˈɡreltɪd</phon>/</phon-blk></pron-g></audio-gb></a></pron-g-blk></pron></vp-g></vp-gs></res-g>
</top-g>
<sn-gs><shcut-blk><sdsymb>➤</sdsymb><shcut>FOLD<chnsep> </chnsep><chn>折叠</chn></shcut></shcut-blk>
 <sn-blk shcut="y"><xhtml:ol start="1"><xhtml:li><licontent><sn-g n="">
  <gram-g><gram-blk> [<gram><xhtml:a href="helpgr:t">T</xhtml:a></gram>, </gram-blk><gram-blk><gram>no passive</gram>] </gram-blk></gram-g>
  <label-g-blk>(<label-g><reg-blk><reg reg="infml"><xhtml:a href="help:infml">informal</xhtml:a></reg>, </reg-blk><geo-blk><geo geo="br"><brelabel>BrE</brelabel></geo></geo-blk></label-g>) </label-g-blk>
  <def neh="n" noblk="y"><xhtml:a href="d:to">to</xhtml:a> <xhtml:a href="d:fold">fold</xhtml:a> a map <xr-gs xt="ndv"><xrlabel></xrlabel><xr-g-blk><xr-g><xh-blk><xh><a href="entry://badly">badly</a></xh></xh-blk></xr-g></xr-g-blk></xr-gs><chnsep> </chnsep><chn><fthzmark></fthzmark>乱折（地图）</chn></def>
  <x-gs><x-g-blk><xsymb><xhtml:a href="addexample:1">◆</xhtml:a></xsymb><cf-blk><cf><exp>~</exp> sth</cf></cf-blk>
   <rx-g><x-wr><x wd="He grelted the map."><xhtml:a href="x:He">He</xhtml:a> grelted the map.  <xhtml:br></xhtml:br><chn><fthzmark></fthzmark>他把地图乱折了。</chn></x>
   <audio-wr><a href="sound://_grelt__gbs_1.mp3"><audio-gbs-liju>A</audio-gbs-liju></a></audio-wr></x-wr></rx-g></x-g-blk></x-gs>
  <unbox type="synonyms" name="grelt"><utitle><titled>grelt</titled></utitle><p><und>BOX TEXT<chnsep> </chnsep><chn>框</chn></und></p>
   <x-gs><x-g-blk><x-wr><x>NOT AN EXAMPLE<chnsep> </chnsep><chn>不是例句</chn></x></x-wr></x-g-blk></x-gs></unbox>
 </sn-g></licontent></xhtml:li></xhtml:ol></sn-blk>
 <sn-blk shcut="n"><xhtml:ol start="2"><xhtml:li><licontent><sn-g n="">
  <use-blk noblk="y"> (<use>used when nobody is looking<chnsep> </chnsep><chn>无人看时用</chn></use>) </use-blk>
  <x-gs><x-g-blk><x-wr><x>Grelt it!<xhtml:br></xhtml:br><chn>折吧！</chn></x></x-wr></x-g-blk></x-gs>
 </sn-g></licontent></xhtml:li></xhtml:ol></sn-blk>
 <sn-blk-nolist><sn-g><xr-gs firstinblock="y" xt="eq"><xrlabel> = </xrlabel><xr-g-blk><xr-g><xh-blk><xh>fold</xh></xh-blk></xr-g></xr-g-blk></xr-gs></sn-g></sn-blk-nolist>
</sn-gs>
<idm-gs-blk><boxblock><img src="idioms.svg"></boxblock><idm-gs>
 <un un="help"><boxtag>HELP</boxtag> Most idioms are elsewhere.<chnsep> </chnsep><chn>帮助</chn></un>
 <idm-g><top-g><idm-l><idm-blk><xsymb>●</xsymb><idm><ftindex word="grelt"></ftindex>grelt the ˈlot</idm></idm-blk>
   <idm-blk><xsymb>●</xsymb><idm>grelt it ˈall</idm></idm-blk></idm-l></top-g>
  <sn-gs><sn-blk><sn-g n=""><label-g-blk>(<label-g><reg-blk><reg reg="infml">informal</reg></reg-blk></label-g>) </label-g-blk>
   <def neh="n">to fail completely<chnsep> </chnsep><chn><fthzmark></fthzmark>彻底失败</chn></def>
   <x-gs><x-g-blk><x-wr><x>We grelted the lot.<xhtml:br></xhtml:br><chn>我们全搞砸了。</chn></x></x-wr></x-g-blk></x-gs></sn-g></sn-blk></sn-gs></idm-g>
</idm-gs></idm-gs-blk>
<pv-gs-blk><pv-gs><pvp-g-blk><pvp-g><pv-g-blk><pv-g><top-g><pv-blk><xsymb>●</xsymb><pv>ˌgrelt sth↔aˈway</pv></pv-blk>
  <gram-g><gram-blk> [<gram>no passive</gram>] </gram-blk></gram-g></top-g>
 <sn-gs><sn-blk shcut="n"><xhtml:ol start="1"><xhtml:li><licontent><sn-g n=""><def>to fold and hide sth<chnsep> </chnsep><chn>折起藏好</chn></def></sn-g></licontent></xhtml:li></xhtml:ol></sn-blk>
  <sn-blk shcut="n"><xhtml:ol start="2"><xhtml:li><licontent><sn-g n=""><def>to forget sth<chnsep> </chnsep><chn>忘记</chn></def></sn-g></licontent></xhtml:li></xhtml:ol></sn-blk></sn-gs>
</pv-g></pv-g-blk></pvp-g></pvp-g-blk></pv-gs></pv-gs-blk>
<dr-gs><dr-g-blk><dr-g><drtri>▸</drtri><top-g><dr-blk><dr>grelt·er</dr></dr-blk>
 <pron wd="grelter"><pron-g-blk><brelabel>BrE</brelabel><a href="sound://grelter__gb_1.mp3"><audio-gb><pron-g><phon-blk>/<phon>ˈɡreltə</phon>/</phon-blk></pron-g></audio-gb></a></pron-g-blk>
  <pos-g><pos-blk><pos>noun</pos></pos-blk></pos-g></pron></top-g>
 <sn-gs><sn-blk-nolist><sn-g><gram-g><gram-blk> [<gram>C</gram>] </gram-blk></gram-g></sn-g></sn-blk-nolist></sn-gs></dr-g></dr-g-blk></dr-gs>
</div>
<div class="seealso">See also <a href="entry://fold">fold</a></div>"""

STANDALONE_IDIOM = """<head></head><idm-g><top-g><idm-blk><xsymb>●</xsymb><idm><ftindex word="a"></ftindex>a ˌgrelt in ˈtime</idm></idm-blk></top-g>
<sn-gs><sn-blk><sn-g n=""><def>a fold made early<chnsep> </chnsep><chn>及时的一折</chn></def></sn-g></sn-blk></sn-gs></idm-g>
<div class="seealso">See also <a href="entry://grelt">grelt</a></div>"""


class OalecdParser(unittest.TestCase):
    def setUp(self):
        self.e = oalecd.parse("grelt", HTML)

    def of(self, kind):
        return [s for s in self.e.senses if s.kind == kind]

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, oalecd.COVERS))

    def test_headword_homograph_pos(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelt", "1", ("verb",)))

    def test_prons_are_the_headword_ones_only(self):
        self.assertEqual([(p.region, p.ipa, p.audio) for p in self.e.prons],
                         [("uk", "ɡrelt", "sound://grelt__gb_1.mp3"), ("us", "ɡrɛlt", "sound://grelt__us_1.mp3")])

    def test_printed_pronunciation_qualifier_is_the_note(self):
        html = ("<h-g><top-g><h>grelt</h><pron-gs><pron-g-blk><brelabel>BrE</brelabel> <pronform>strong form</pronform> "
                '<a href="sound://g1.mp3"><audio-gb><pron-g><phon-blk>/<phon>ɡrelt</phon>/</phon-blk></pron-g></audio-gb></a>'
                "</pron-g-blk><pron-g-blk><pronfreq><q>also</q> </pronfreq><a href=\"sound://g2.mp3\"><audio-us><pron-g>"
                "<phon-blk>/<phon>ɡrɑlt</phon>/</phon-blk></pron-g></audio-us></a></pron-g-blk></pron-gs></top-g>"
                "<sn-gs><sn-blk-nolist><sn-g><def>a fold</def></sn-g></sn-blk-nolist></sn-gs></h-g>")
        e = oalecd.parse("grelt", html)
        self.assertEqual([(p.region, p.ipa, p.note) for p in e.prons], [("uk", "ɡrelt", "strong form"), ("us", "ɡrɑlt", "also")])
        self.assertEqual([p.note for p in self.e.prons], ["", ""])

    def test_forms_are_inflections_and_variant_spellings(self):
        # the root verb form is the headword and "ff" is a full form, not a spelling
        self.assertEqual(self.e.forms, ("grelted", "grelte"))

    def test_sense_with_labels_bilingual_definition_and_examples(self):
        s1 = self.of("sense")[0]
        self.assertEqual((s1.pos, s1.number, s1.labels), ("verb", "1", ("T", "no passive", "informal", "BrE")))
        self.assertEqual((s1.definition, s1.definition_zh), ("to fold a map badly", "乱折（地图）"))
        self.assertEqual([(x.text, x.text_zh) for x in s1.examples], [("He grelted the map.", "他把地图乱折了。")])

    def test_use_note_stands_in_for_a_missing_definition(self):
        s2 = self.of("sense")[1]
        self.assertEqual((s2.number, s2.definition, s2.definition_zh), ("2", "used when nobody is looking", "无人看时用"))
        self.assertEqual(s2.examples[0].text_zh, "折吧！")

    def test_pointer_only_sense_is_not_a_sense(self):
        self.assertEqual(len(self.of("sense")), 2)

    def test_boxes_and_help_notes_do_not_leak(self):
        flat = repr(self.e.senses)
        for leaked in ("NOT AN EXAMPLE", "BOX TEXT", "Most idioms", "FOLD", "折叠"):
            self.assertNotIn(leaked, flat)

    def test_idiom_takes_its_first_phrase_without_stress_marks(self):
        (idiom,) = self.of("phrase")
        self.assertEqual((idiom.phrase, idiom.labels, idiom.definition, idiom.definition_zh),
                         ("grelt the lot", ("informal",), "to fail completely", "彻底失败"))
        self.assertEqual(idiom.examples[0].text, "We grelted the lot.")

    def test_phrasal_verb_senses_share_the_group_labels(self):
        pvs = self.of("phrasal_verb")
        self.assertEqual([(s.phrase, s.number, s.labels, s.definition) for s in pvs],
                         [("grelt sth away", "1", ("no passive",), "to fold and hide sth"),
                          ("grelt sth away", "2", ("no passive",), "to forget sth")])

    def test_derivative_without_definition_still_records_word_and_pos(self):
        (dr,) = self.of("derivative")
        self.assertEqual((dr.phrase, dr.pos, dr.labels, dr.definition), ("grelter", "noun", ("C",), ""))
        self.assertNotIn("noun", self.e.pos)

    def test_entry_level_labels_reach_the_senses_but_a_variants_labels_do_not(self):
        label = "<label-g-blk>(<label-g><reg-blk><reg>{}</reg></reg-blk></label-g>)</label-g-blk>"
        html = ("<h-g><top-g><h>grelt</h><v-gs-blk type=\"vs\"><v-gs><v-g-blk><v-g>" + label.format("NAmE also")
                + "<v-blk><v>grelte</v></v-blk></v-g></v-g-blk></v-gs></v-gs-blk>"
                "<pron><pos-g><pos-blk><pos>noun</pos></pos-blk></pos-g><gram-g><gram-blk>[<gram>U</gram>]</gram-blk></gram-g>"
                + label.format("business") + "</pron></top-g><sn-gs>"
                "<sn-blk><xhtml:ol start=\"1\"><xhtml:li><sn-g><def>a fold</def></sn-g></xhtml:li></xhtml:ol></sn-blk>"
                "<sn-blk><xhtml:ol start=\"2\"><xhtml:li><sn-g><label-g-blk>(<label-g><reg-blk><reg>informal</reg></reg-blk>"
                "<or> or </or><reg-blk><reg>humorous</reg></reg-blk></label-g>)</label-g-blk><def>a crease</def></sn-g>"
                "</xhtml:li></xhtml:ol></sn-blk></sn-gs></h-g>")
        e = oalecd.parse("grelt", html)
        self.assertEqual([(x.number, x.labels) for x in e.senses], [("1", ("U", "business")), ("2", ("U", "business", "informal or humorous"))])
        self.assertEqual((e.forms, problems(e)), (("grelte",), []))

    def test_shared_sense_keeps_every_printed_part_of_speech(self):
        e = oalecd.parse("grelt", "<h-g><top-g><h>grelt</h><pos-g><pos-blk><pos>adverb</pos></pos-blk>, <pos-blk><pos>preposition</pos>"
                         "</pos-blk></pos-g></top-g><sn-gs><sn-blk-nolist><sn-g><def>on a fold</def></sn-g></sn-blk-nolist></sn-gs></h-g>")
        self.assertEqual((e.pos, [x.pos for x in e.senses]), (("adverb", "preposition"), ["adverb, preposition"]))

    def test_idiom_nested_in_another_group_is_kept_apart_from_it(self):
        sense = "<sn-gs><sn-blk-nolist><sn-g><def>{}</def></sn-g></sn-blk-nolist></sn-gs>"
        html = ("<h-g><top-g><h>grelt</h></top-g>" + sense.format("a fold") + "<dr-gs><dr-g><top-g><dr>greltly</dr></top-g>"
                "<sn-gs><sn-blk-nolist><sn-g><def>in folds</def></sn-g></sn-blk-nolist>"
                "<id-g><idm-g><top-g><idm>grelt ˈwisdom</idm></top-g>" + sense.format("what folders know") + "</idm-g></id-g>"
                "</sn-gs></dr-g></dr-gs></h-g>")
        e = oalecd.parse("grelt", html)
        self.assertEqual([(x.kind, x.phrase, x.definition) for x in e.senses],
                         [("sense", "", "a fold"), ("phrase", "grelt wisdom", "what folders know"), ("derivative", "greltly", "in folds")])

    def test_standalone_idiom_entry(self):
        e = oalecd.parse("a grelt in time", STANDALONE_IDIOM)
        self.assertEqual(problems(e), [])
        self.assertEqual((e.headword, e.pos, e.prons), ("a grelt in time", (), ()))
        self.assertEqual([(s.kind, s.phrase, s.definition_zh) for s in e.senses],
                         [("phrase", "a grelt in time", "及时的一折")])

    def test_records_without_a_definition_are_stubs_by_their_pointer(self):
        self.assertEqual(self.e.stub, "")
        sn = '<h-g><top-g><h>grelted</h></top-g><sn-gs><sn-blk-nolist><sn-g>{}</sn-g></sn-blk-nolist></sn-gs></h-g>'
        past = '<xr-gs xt="ptof"><xrlabel> past tense of </xrlabel><xr-g-blk><xr-g><xh>grelt</xh></xr-g></xr-g-blk></xr-gs>'
        same = '<xr-gs xt="eq"><xrlabel> = </xrlabel><xr-g-blk><xr-g><xh>fold</xh></xr-g></xr-g-blk></xr-gs>'
        with_example = same + '<x-gs><x-g-blk><x-wr><x>a grelt map<chn>折坏的地图</chn></x></x-wr></x-g-blk></x-gs>'
        self.assertEqual(oalecd.parse("grelted", sn.format(past)).stub, "inflection")
        self.assertEqual(oalecd.parse("grelted", sn.format(same)).stub, "xref")
        e = oalecd.parse("grelted", sn.format(with_example))
        self.assertEqual((e.stub, e.senses[0].examples[0].text_zh, problems(e)), ("xref", "折坏的地图", []))
        self.assertEqual(oalecd.parse("grelted", '<h-g><top-g><h>grelted</h></top-g><sn-gs></sn-gs></h-g>').stub, "empty")

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", "<sn-g><def>", "<<<>>>", "<idm-g><sn-g><x>", "<dr-g><dr>"]:
            e = oalecd.parse("x", junk)
            self.assertEqual(problems(e), [])
        self.assertEqual(oalecd.parse("x", "").headword, "x")


if __name__ == "__main__":
    unittest.main()
