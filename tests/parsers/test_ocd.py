"""OCD2 parser on a synthetic entry that mirrors its flat ocd_* markup (text invented)."""
import unittest

from structured.model import covered, problems
from structured.parsers import ocd


def _line(collocations: str, *examples: str) -> str:
    out = f'\t<span class="ocd_m3s"><span class="ocd_m3"><span class="ocd_cc">{collocations}</span></span>'
    if examples:
        out += '\n\t\t<span class="ocd_m4s">' + "".join(
            f'<span class="ocd_m4"><span class="ocd_ex">{e}</span></span>' for e in examples) + "</span>"
    return out + "</span>\n"


def _co(value: str) -> str:
    return f'<span class="ocd_co">{value}</span>'


HTML = (
    '<link rel="stylesheet" href="ocd.css"/>\n<span class="ocd_hw">grelt</span>\n'
    '<hr class="ocd_hr"><span class="ocd_seg">I</span>\n'
    '\t<span class="ocd_class"><span class="ocd_pos">noun</span></span>\n'
    '\t<span class="ocd_m1"><trn>(also <span class="ocd_als">grellt</span>) <span class="ocd_fed">noun</span></span>\n'
    '\t<span class="ocd_m1"><span class="ocd_def"><span class="ocd_li">1</span> a folded map</span></span>\n'
    '\t<span class="ocd_m2"><span class="ocd_ps">ADJECTIVE</span></span>\n'
    + _line(_co("crumpled") + ", " + _co("creased") + ' <span class="ocd_reg">esp. <span class="ocd_bre">BrE</span></span>',
            "A crumpled <u>grelt</u> lay on the seat.")
    + _line(_co("five-fold") + ", " + _co("etc."))
    + '\t<span class="ocd_m2"><span class="ocd_ps">PREPOSITION</span></span>\n'
    + _line(_co("in a") + " " + _co("<u>grelt</u>") + " <i>(= folded up)</i>", "The chart was in a <u>grelt</u>.",
            "Keep it in a <u>grelt</u> (<i>= folded</i>).")
    + '\t<span class="ocd_m1"><span class="ocd_def"><span class="ocd_li">2</span> a hesitation</span></span>\n'
    '\t<span class="ocd_m2"><span class="ocd_ps">VERB + GRELT</span></span>\n'
    + _line(_co("make") + ", " + _co("show") + " (both " + '<span class="ocd_reg"><span class="ocd_ame">AmE</span></span>')
    + '<hr class="ocd_hr"><span class="ocd_seg">II</span>\n'
    '\t<span class="ocd_class"><span class="ocd_pos">verb</span></span>\n'
    '\t<span class="ocd_m2"><span class="ocd_ps">ADVERB</span></span>\n'
    + _line(_co("neatly"), "She <u>grelted</u> it neatly.")
    + '<span class="ocd_psv">PHRASAL VERB</span>\n\t<span class="ocd_hw">grelt up</span>\n'
    '\t<span class="ocd_m2"><span class="ocd_ps">ADVERB</span></span>\n'
    + _line(_co("tightly"))
    + '<span class="ocd_m2_1"><b>Grelt</b> is used with these nouns as the object: <a href="entry://map">map</a>, '
      '<a href="entry://chart">chart</a>, sail</span>\n'
)


class OcdParser(unittest.TestCase):
    def setUp(self):
        self.e = ocd.parse("grelt", HTML)
        self.groups = [s for s in self.e.senses if s.kind == "collocation"]

    def test_valid_and_covered(self):
        self.assertEqual(problems(self.e), [])
        self.assertTrue(covered(self.e, ocd.COVERS))

    def test_headword_pos_and_variant_form(self):
        self.assertEqual((self.e.headword, self.e.homograph, self.e.pos, self.e.forms),
                         ("grelt", "", ("noun", "verb"), ("grellt",)))

    def test_senses_carry_pos_number_and_gloss(self):
        senses = [(s.pos, s.number, s.definition) for s in self.e.senses if s.kind == "sense"]
        self.assertEqual(senses, [("noun", "1", "a folded map"), ("noun", "2", "a hesitation")])

    def test_collocation_groups_with_collocations_then_examples(self):
        adjective = self.groups[0]
        self.assertEqual((adjective.pos, adjective.number, adjective.phrase), ("noun", "1", "ADJECTIVE"))
        self.assertEqual([(x.kind, x.text) for x in adjective.examples], [
            ("collocation", "crumpled"), ("collocation", "creased"), ("collocation", "five-fold"),
            ("example", "A crumpled grelt lay on the seat.")])  # "etc." and "esp. BrE" are not collocations

    def test_parts_joined_by_a_space_are_one_collocation(self):
        preposition = self.groups[1]
        self.assertEqual([x.text for x in preposition.examples if x.kind == "collocation"], ["in a grelt"])
        self.assertEqual([x.text for x in preposition.examples if x.kind == "example"],
                         ["The chart was in a grelt.", "Keep it in a grelt (= folded)."])

    def test_groups_follow_their_sense_and_section(self):
        self.assertEqual([(g.pos, g.number, g.phrase) for g in self.groups[2:4]],
                         [("noun", "2", "VERB + GRELT"), ("verb", "", "ADVERB")])
        self.assertEqual([x.text for x in self.groups[2].examples], ["make", "show"])

    def test_phrasal_verb_owns_the_groups_after_it(self):
        index = next(i for i, s in enumerate(self.e.senses) if s.kind == "phrasal_verb")
        verb, group = self.e.senses[index], self.e.senses[index + 1]
        self.assertEqual(verb.phrase, "grelt up")
        self.assertEqual((group.kind, group.pos, group.phrase, [x.text for x in group.examples]),
                         ("collocation", "", "ADVERB", ["tightly"]))

    def test_used_with_list_is_a_group_of_its_own_and_counted_once(self):
        used = self.groups[-1]
        self.assertEqual((used.phrase, [x.text for x in used.examples]),
                         ("used with these nouns as the object", ["map", "chart", "sail"]))
        everything = [x.text for g in self.groups for x in g.examples]
        self.assertEqual(everything.count("map"), 1)

    def test_labels_belong_to_their_item_or_to_the_whole_bracket(self):
        labels = {x.text: x.labels for g in self.groups for x in g.examples if x.kind == "collocation"}
        self.assertEqual((labels["crumpled"], labels["creased"]), ((), ("esp. BrE",)))
        self.assertEqual((labels["make"], labels["show"]), (("AmE",), ("AmE",)))  # "(both AmE"
        self.assertNotIn("esp. BrE", " ".join(labels))  # the text is free of its label

    def _labels_of(self, line: str) -> dict:
        e = ocd.parse("grelt", '<span class="ocd_hw">grelt</span><span class="ocd_m2"><span class="ocd_ps">ADJECTIVE</span></span>'
                      + _line(line))
        return {x.text: x.labels for x in e.senses[0].examples}

    def test_a_plain_bracket_labels_only_the_item_before_it(self):
        # "lab (informal, esp. AmE, laboratory": the source often omits the ")"; the next item ends it
        labels = self._labels_of(_co("farm") + ", " + _co("lab") + ' (<span class="ocd_fed">informal</span>, '
                                 '<span class="ocd_reg">esp. <span class="ocd_ame">AmE</span></span>, ' + _co("zoo"))
        self.assertEqual(labels, {"farm": (), "lab": ("informal", "esp. AmE"), "zoo": ()})

    def test_both_and_all_brackets_label_the_items_they_count(self):
        both = self._labels_of(_co("far") + ", " + _co("near") + ", " + _co("high") + ' (both <span class="ocd_reg">esp. '
                               '<span class="ocd_bre">BrE</span></span>, ' + _co("low"))
        self.assertEqual(both, {"far": (), "near": ("esp. BrE",), "high": ("esp. BrE",), "low": ()})
        inside = self._labels_of(_co("wild") + ", " + _co("zany") + ' (<span class="ocd_fed">both informal</span>, '
                                 '<span class="ocd_reg">esp. <span class="ocd_ame">AmE</span></span>')
        self.assertEqual(inside, {"wild": ("informal", "esp. AmE"), "zany": ("informal", "esp. AmE")})
        later = self._labels_of(_co("tip") + ", " + _co("top") + ' (<span class="ocd_fed">informal</span>, both '
                                '<span class="ocd_reg"><span class="ocd_ame">AmE</span></span>')
        self.assertEqual(later, {"tip": ("AmE",), "top": ("informal", "AmE")})
        every = self._labels_of(_co("a") + ", " + _co("b") + ", " + _co("c")
                                + ' (all <span class="ocd_reg"><span class="ocd_bre">BrE</span></span>)')
        self.assertEqual(every, {"a": ("BrE",), "b": ("BrE",), "c": ("BrE",)})

    def test_a_later_headword_is_a_phrasal_verb_even_without_its_banner(self):
        # some records print "grelt off" with no "PHRASAL VERB" (ocd_psv) before it
        e = ocd.parse("grelt", '<span class="ocd_hw">grelt</span><span class="ocd_class"><span class="ocd_pos">verb</span></span>'
                      '<span class="ocd_m1"><span class="ocd_def"><span class="ocd_li">3</span> fold twice</span></span>'
                      '<span class="ocd_m2"><span class="ocd_ps">ADVERB</span></span>' + _line(_co("neatly"))
                      + '<span class="ocd_hw">grelt off</span>'
                      '<span class="ocd_m2"><span class="ocd_ps">ADVERB</span></span>' + _line(_co("abruptly")))
        self.assertEqual([(s.kind, s.pos, s.number, s.phrase) for s in e.senses], [
            ("sense", "verb", "3", ""), ("collocation", "verb", "3", "ADVERB"),
            ("phrasal_verb", "", "", "grelt off"), ("collocation", "", "", "ADVERB")])

    def test_a_numbered_header_inside_ocd_m3_starts_a_sense(self):
        # "<span class=ocd_m3><b>2</b> gloss</span>": a phrasal verb's second sense, printed without ocd_def
        e = ocd.parse("grelt", '<span class="ocd_hw">grelt</span><span class="ocd_psv">PHRASAL VERB</span>'
                      '<span class="ocd_hw">grelt up</span>'
                      '<span class="ocd_m1"><span class="ocd_def"><span class="ocd_li">1</span> fail</span></span>'
                      '<span class="ocd_m2"><span class="ocd_ps">ADVERB</span></span>' + _line(_co("completely"))
                      + '<span class="ocd_m3"><b>2</b> start crying</span>'
                      '<span class="ocd_m2"><span class="ocd_ps">PHRASES</span></span>' + _line(_co("grelt up in tears")))
        self.assertEqual([(s.kind, s.number, s.phrase, s.definition) for s in e.senses], [
            ("phrasal_verb", "", "grelt up", ""), ("phrasal_verb", "1", "grelt up", "fail"),
            ("collocation", "1", "ADVERB", ""), ("phrasal_verb", "2", "grelt up", "start crying"),
            ("collocation", "2", "PHRASES", "")])

    def test_field_label_and_gloss_stay_out_of_the_collocation_text(self):
        e = ocd.parse("grelt", '<span class="ocd_hw">grelt</span><span class="ocd_m2"><span class="ocd_ps">PHRASES</span></span>'
                               + _line(_co("a <u>grelt</u> in time") + ' <i>(= a timely fold)</i> <span class="ocd_fed">law</span>'))
        (x,) = e.senses[0].examples
        self.assertEqual((x.text, x.labels), ("a grelt in time", ("law",)))

    def test_stub_reasons_come_from_markup(self):
        empty = ocd.parse("x", '<span class="ocd_hw">greltz</span><span class="ocd_class"><span class="ocd_pos">noun</span></span>')
        xref = ocd.parse("x", '<span class="ocd_hw">GR</span><span class="ocd_m1"><trn>⇨ See <a href="entry://grelt">grelt</a></span>')
        for e, reason in ((empty, "empty"), (xref, "xref")):
            self.assertEqual((e.stub, e.senses, problems(e)), (reason, (), []))
            self.assertFalse(covered(e, ocd.COVERS))
        self.assertEqual(self.e.stub, "")

    def test_garbage_never_raises(self):
        for junk in ["", "<", "<span class='ocd_cc'>", "plain text", "<<<>>>",
                     "<span class='ocd_m2_1'><b>X</b> is used", "<span class='ocd_ex'>lonely example</span>"]:
            e = ocd.parse("x", junk)
            self.assertEqual(e.headword, "x")
            self.assertEqual(problems(e), [])


if __name__ == "__main__":
    unittest.main()
