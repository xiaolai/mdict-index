"""MWALED parser on synthetic records that mirror learnersdictionary.com's markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import mwaled


def vis(*examples: str) -> str:
    items = "".join(f'<li class="vi"><div class="vi_content">{x}</div></li>' for x in examples)
    return (f'<div class="vis_w"><ul class="vis collapsed">{items}</ul><div class="vi_more d_hidden"><a href="#">'
            '<span class="d_p">[+] more examples</span></a></div></div>')


HEAD = """<span class="hw_txt gfont"><sup class="homograph">1</sup> grelt </span>
 <span class="hpron_word ifont">/<span class="smark">ˈ</span>grɛlt/</span>
 <a href="sound://pronunciations/mp3/g/grelt001.mp3" class="fa fa-volume-up hpron_icon play_pron" data-pron="ˈgrɛlt" data-lang="en_us"></a>
 <span class="hpron_label_b">Brit</span> <span class="hpron_word ifont">/ˈgrelt/</span>
 <span class="fl">verb</span>"""

HTML = f"""
<link href="mwaled.css" rel="stylesheet" type="text/css">
<h1 id="ld_entries_v2_mainh">grelt</h1>
<div id="ld_entries_v2_others_block"><div class="o_count">3 ENTRIES FOUND:</div><ul class="o_list"><li>
 <a href="entry://grelt-up" class="otherwords">OTHER WORD</a></li></ul></div>
<div id="ld_entries_v2_all"><div class="entry entry_v2 boxy">
 <div class="hw_d hw_0 boxy m_hidden">{HEAD}</div>
 <div class="hw_infs_d m_hidden"><span class="i_text">grelts</span><span class="semicolon">;</span><span class="i_text">grolt</span></div>
 <div class="hw_m hw_0 boxy d_hidden"><div class="hw_line">{HEAD}</div></div>
 <div class="hw_infs_m d_hidden"><span class="i_text">MOBILE COPY</span></div>
 <div class="dline m_hidden"><span class="vfont">Learner's definition of GRELT</span></div>
 <div class="sblocks">
  <div class="sblock sblock_entry"><div class="sblock_c"><strong class="sn_block_num">1</strong><div class="scnt">
   <div class="sblock_labels"><span class="sgram">[<span class="sgram_internal">+ object</span>]</span></div>
   <div class="sense"><strong class="sn_letter">a</strong><span class="bc">:</span>
    <span class="def_text">to fold (a map) badly</span><span class="bc">:</span><span class="def_text">to crumple</span>
    {vis('He <em class="mw_spm_it">grelted</em> the map.')}
    <div class="usage_par"><span class="usage_par_h">Usage</span><span class="ud_text">USAGE NOTE</span>{vis('USAGE EXAMPLE')}</div>
   </div>
   <div class="sense"><strong class="sn_letter">b</strong><span class="ssla">informal</span>
    <span class="un_text">used to describe a failure</span>{vis('That was a total grelt.')}
    <span class="dxs dxs_nonl">— <span class="dx">compare <a href="entry://frump" class="dx_link">frump</a></span></span></div>
  </div></div></div>
 </div>
 <div class="dros">
  <div class="dro"><div class="dro_line"><h2 class="dre">grelt out</h2><span class="gram">[<span class="gram_internal">phrasal verb</span>]</span></div>
   <div class="sblocks"><div class="sblock sblock_dro"><div class="sblock_c"><div class="scnt">
    <div class="sblock_labels"><span class="pva">grelt out (something)</span></div>
    <div class="sense"><span class="bc">:</span><span class="def_text">to unfold (something)</span>{vis('Grelt it out.')}</div>
   </div></div></div></div></div>
  <div class="dro"><div class="dro_line"><h2 class="dre">grelt the lot</h2><span class="sl">British, informal</span></div>
   <div class="sblocks"><div class="sblock sblock_dro"><div class="sblock_c"><div class="scnt"><div class="sblock_labels"></div>
    <div class="sense"><span class="snote"><div class="both_text">◊ If you grelt the lot, you fail at everything.</div>{vis('We grelted the lot.')}</span></div>
   </div></div></div></div></div>
 </div>
 <div class="uros"><div class="uro"><div class="uro_line"><h2 class="ure">— greltingly</h2><span class="fl">adverb</span></div>
  <div class="uro_def">{vis('He folded it greltingly.')}</div></div></div>
 <div class="synpar"><div class="synpar_part"><a class="synpar_w" href="entry://grelt">grelt</a>
  <span class="syn_par_t">SYNONYM PARAGRAPH</span></div></div>
</div></div>"""


class MwaledParser(unittest.TestCase):
    def setUp(self):
        self.e = mwaled.parse("grelt", HTML)

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, mwaled.COVERS))

    def test_headword_from_desktop_copy_only(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos), ("grelt", "1", ("verb",)))
        self.assertEqual(self.e.forms, ("grelts", "grolt"))
        self.assertEqual([(p.region, p.ipa, p.audio) for p in self.e.prons],
                         [("us", "ˈgrɛlt", "sound://pronunciations/mp3/g/grelt001.mp3"), ("uk", "ˈgrelt", "")])

    def test_numbered_senses_labels_and_verbal_illustrations(self):
        a, b = [s for s in self.e.senses if s.kind == "sense"]
        self.assertEqual((a.number, a.labels, a.definition, [x.text for x in a.examples]),
                         ("1a", ("+ object",), "to fold (a map) badly : to crumple", ["He grelted the map."]))
        self.assertEqual((b.number, b.labels, b.definition, b.examples[0].text),
                         ("1b", ("+ object", "informal"), "used to describe a failure", "That was a total grelt."))

    def test_side_content_does_not_leak(self):
        everything = repr(self.e)
        for leaked in ("USAGE", "SYNONYM", "OTHER WORD", "MOBILE", "frump"):
            self.assertNotIn(leaked, everything)

    def test_phrasal_verbs_phrases_and_run_ons(self):
        (pv,) = [s for s in self.e.senses if s.kind == "phrasal_verb"]
        self.assertEqual((pv.phrase, pv.pos, pv.definition, pv.examples[0].text),
                         ("grelt out", "phrasal verb", "to unfold (something)", "Grelt it out."))
        (ph,) = [s for s in self.e.senses if s.kind == "phrase"]
        self.assertEqual((ph.phrase, ph.labels, ph.definition, ph.examples[0].text),
                         ("grelt the lot", ("British, informal",), "If you grelt the lot, you fail at everything.",
                          "We grelted the lot."))
        (d,) = [s for s in self.e.senses if s.kind == "derivative"]
        self.assertEqual((d.phrase, d.pos, d.examples[0].text), ("greltingly", "adverb", "He folded it greltingly."))

    def test_main_entry_stub_is_empty(self):
        stub = mwaled.parse("grelts", '<div id="ld_entries_v2_all"><div class="entry entry_v2 boxy">⇒ Main Entry: '
                            '<a href="entry://grelt" class="realmainentry">GRELT</a></div></div>')
        self.assertEqual((stub.headword, stub.senses, problems(stub)), ("grelts", (), []))
        self.assertFalse(covered(stub, mwaled.COVERS))

    def test_run_on_record_takes_the_run_ons_pron_and_pos(self):
        rec = mwaled.parse("greltness", '<div class="entry entry_v2 boxy"><div class="uros"><div class="uro"><div class="uro_line">'
                           '<h2 class="ure">— greltness</h2><span class="pron_w ifont">/ˈgrɛltnəs/</span>'
                           '<a class="play_pron" data-pron="ˈgrɛltnəs" href="sound://pronunciations/mp3/g/grelt05.mp3"></a>'
                           '<span class="fl">noun</span><span class="gram">[<span class="gram_internal">noncount</span>]</span>'
                           '</div></div></div>⇒ Main Entry: <a href="entry://grelt" class="realmainentry">GRELT</a></div>')
        self.assertEqual((rec.headword, rec.pos, [(p.ipa, p.audio) for p in rec.prons]),
                         ("greltness", ("noun",), [("ˈgrɛltnəs", "sound://pronunciations/mp3/g/grelt05.mp3")]))
        (d,) = rec.senses
        self.assertEqual((d.kind, d.phrase, d.labels), ("derivative", "greltness", ("noncount",)))
        self.assertEqual(problems(rec), [])

    def test_stub_reasons_come_from_the_markup(self):
        def rec(body):
            return f'<div id="ld_entries_v2_all"><div class="entry entry_v2 boxy">{body}</div></div>'
        cases = {
            "xref": ("grelts", rec('⇒ Main Entry: <a href="entry://grelt" class="realmainentry">GRELT</a>')),
            "variant": ("greltt", rec('<div class="hw_d"><span class="hw_txt">greltt</span></div>'
                                      '<div class="cxs"><span class="cl">variant spelling of</span> <a class="cx_link">grelt</a></div>')),
            "inflection": ("grolt", rec('<div class="hw_d"><span class="hw_txt">grolt</span></div>'
                                        '<div class="cxs"><span class="cl">past tense of</span> <a class="cx_link">grelt</a></div>')),
            "image": ("IMG_grelt", '<img src="/images/grelt.gif">'),
            "derivative": ("greltness", rec('<div class="uros"><div class="uro"><div class="uro_line"><h2 class="ure">— greltness</h2>'
                                            '<span class="fl">noun</span></div></div></div>⇒ Main Entry: '
                                            '<a href="entry://grelt" class="realmainentry">GRELT</a>')),
        }
        for reason, (hw, html) in cases.items():
            e = mwaled.parse(hw, html)
            self.assertEqual((e.stub, problems(e)), (reason, []), reason)
            self.assertFalse(covered(e, mwaled.COVERS))
        self.assertEqual(self.e.stub, "")

    def test_pron_label_other_than_brit_is_a_note(self):
        e = mwaled.parse("grelt", '<div class="entry"><div class="hw_d"><span class="hw_txt">grelt</span>'
                         '<span class="hpron_word">/ˈgrɛlt/</span><span class="hpron_label_a">or</span>'
                         '<span class="hpron_word">/ˈgrilt/</span></div></div>')
        self.assertEqual([(p.region, p.ipa, p.note) for p in e.prons], [("us", "ˈgrɛlt", ""), ("us", "ˈgrilt", "or")])

    def _head_prons(self, head: str):
        e = mwaled.parse("grelt", f'<div class="entry"><div class="hw_d"><span class="hw_txt">grelt</span>{head}</div></div>')
        self.assertEqual(problems(e), [])
        return [(p.region, p.ipa, p.note) for p in e.prons]

    def test_trailing_pron_label_belongs_to_the_pron_before_it(self):
        w, a, b = '<span class="hpron_word">/{}/</span>', '<span class="hpron_label_a">{}</span>', '<span class="hpron_label_b">{}</span>'
        self.assertEqual(self._head_prons(w.format("grə") + a.format("before consonants") + w.format("gri") + a.format("before vowels")
                                          + w.format("ˈgriː") + a.format("when stressed")),
                         [("us", "grə", "before consonants"), ("us", "gri", "before vowels"), ("us", "ˈgriː", "when stressed")])
        # a leading label (class b) and a trailing one on the same pron; "Brit" leads whichever class it is printed in
        self.assertEqual(self._head_prons(w.format("grɛlt") + b.format("sometimes") + w.format("grɪlt") + a.format("before vowels")
                                          + a.format("Brit") + w.format("grelt")),
                         [("us", "grɛlt", ""), ("us", "grɪlt", "sometimes before vowels"), ("uk", "grelt", "")])

    def test_a_label_opening_with_or_leads_the_pron_after_it(self):
        # "/ˈʌm/ or a prolonged /m/ sound": "or …" qualifies /m/, whichever class prints it
        w, a = '<span class="hpron_word">/{}/</span>', '<span class="hpron_label_a">{}</span>'
        self.assertEqual(self._head_prons(w.format("ˈgrʌm") + a.format("or a long") + w.format("g") + a.format("sound")),
                         [("us", "ˈgrʌm", ""), ("us", "g", "or a long sound")])

    def test_sounds_naming_a_context_are_a_note_not_pronunciations(self):
        w, a, b = '<span class="hpron_word">/{}/</span>', '<span class="hpron_label_a">{}</span>', '<span class="hpron_label_b">{}</span>'
        head = (w.format("əg") + a.format("after") + w.format("k") + a.format("or") + w.format("g")
                + w.format("s") + a.format("after") + w.format("p") + w.format("f") + b.format("or") + w.format("θ")
                + w.format("z") + a.format("after") + w.format("v") + a.format("or a vowel")
                + w.format("g") + a.format("elsewhere") + b.format("exceptions are listed"))
        self.assertEqual(self._head_prons(head), [("us", "əg", "after /k/ or /g/"), ("us", "s", "after /p/ /f/ or /θ/"),
                                                  ("us", "z", "after /v/ or a vowel"), ("us", "g", "elsewhere")])

    def test_garbage_never_raises(self):
        for junk in ["", "<", "plain text", "<div class='entry'><div class='hw_d'>", "<div class='dro'><div class='sense'>"]:
            e = mwaled.parse("x", junk)
            self.assertEqual((e.headword, problems(e)), ("x", []))


if __name__ == "__main__":
    unittest.main()
