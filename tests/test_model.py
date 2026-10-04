"""The shared layer-2 model: its contract checks, stub rules and coverage rules."""
import unittest

from structured.model import Entry, Example, Pron, Sense, covered, problems, stub_problem


class Contract(unittest.TestCase):
    def test_a_well_formed_entry_has_no_problems(self):
        e = Entry(headword="take", pos=("verb",), prons=(Pron("teɪk", "uk", "sound://t.mp3", "strong form"),),
                  senses=(Sense(number="1", definition="to carry", definition_zh="拿",
                                examples=(Example("Take it.", "拿着。", labels=("informal",)),)),
                          Sense(kind="phrasal_verb", phrase="take off", definition="to leave the ground")))
        self.assertEqual(problems(e), [])

    def test_markup_left_in_text_is_caught(self):
        for dirty in ["<b>bold</b>", 'to <span class="x">carry</span>', "a <br/> b", "x <i>"]:
            self.assertTrue(problems(Entry(headword="w", senses=(Sense(definition=dirty),))), dirty)

    def test_angle_bracket_notation_and_bare_less_than_are_text(self):
        for fine in ["the pair <a, b>", "the ordered set <x y z>", "< Latin tacere", "a < b and c > d"]:
            self.assertEqual(problems(Entry(headword="w", senses=(Sense(definition=fine),))), [], fine)

    def test_printed_markup_skips_only_the_tag_check(self):
        about_html = Entry(headword="tag", senses=(Sense(definition="a label", examples=(Example("a line break, <br>"),)),))
        self.assertTrue(problems(about_html))
        self.assertEqual(problems(about_html, printed_markup=True), [])
        untidy = Entry(headword="tag", senses=(Sense(definition="a  label <br>"),))
        self.assertTrue(problems(untidy, printed_markup=True))  # whitespace is still checked

    def test_untidy_whitespace_and_empty_parts_are_caught(self):
        self.assertTrue(problems(Entry(headword=" take")))
        self.assertTrue(problems(Entry(headword="w", senses=(Sense(definition="two  spaces"),))))
        self.assertTrue(problems(Entry(headword="w", senses=(Sense(),))))
        self.assertTrue(problems(Entry(headword="w", senses=(Sense(examples=(Example(""),)),))))
        self.assertTrue(problems(Entry(headword="")))

    def test_any_uncollapsed_whitespace_is_caught(self):
        for dirty in ["two\twords", "two\rwords", "two\u00a0words", "two\u3000words"]:
            self.assertTrue(problems(Entry(headword=dirty)), repr(dirty))
            self.assertTrue(problems(Entry(headword="w", senses=(Sense(definition=dirty),))), repr(dirty))

    def test_every_entry_level_string_is_checked(self):
        for dirty in [" 1", "<b>x</b>", "a  b"]:
            for e in [Entry(headword="w", homograph=dirty), Entry(headword="w", pos=(dirty,)),
                      Entry(headword="w", forms=(dirty,)), Entry(headword="w", stub="popup", part_of=dirty)]:
                self.assertTrue(problems(e), (dirty, e))

    def test_enumerations_are_enforced(self):
        self.assertTrue(problems(Entry(headword="w", senses=(Sense(kind="meaning", definition="x"),))))
        self.assertTrue(problems(Entry(headword="w", prons=(Pron("x", region="au"),))))
        self.assertTrue(problems(Entry(headword="w", senses=(Sense(definition="x", examples=(Example("e", kind="quote"),)),))))
        self.assertTrue(problems(Entry(headword="w", senses=(Sense(kind="idiom", definition="x"),))))

    def test_phrase_kinds_need_the_phrase(self):
        self.assertTrue(problems(Entry(headword="w", senses=(Sense(kind="phrasal_verb", definition="x"),))))
        self.assertEqual(problems(Entry(headword="w", senses=(Sense(kind="note", definition="x"),))), [])


class Stubs(unittest.TestCase):
    def test_reasons_are_validated(self):
        self.assertEqual(problems(Entry(headword="w", stub="xref")), [])
        self.assertTrue(problems(Entry(headword="w", stub="boring")))

    def test_popups_and_part_of_go_together(self):
        self.assertEqual(problems(Entry(headword="@origin_w", stub="popup", part_of="w")), [])
        self.assertTrue(problems(Entry(headword="@origin_w", stub="popup")))
        self.assertTrue(problems(Entry(headword="w", part_of="x")))

    def test_a_stub_may_not_carry_what_it_is_excused_from(self):
        cheat = Entry(headword="w", stub="xref", senses=(Sense(definition="a real definition"),))
        self.assertTrue(stub_problem(cheat, "definitions"))
        honest = Entry(headword="w", stub="xref", etymology="from x")
        self.assertEqual(stub_problem(honest, "definitions"), "")
        self.assertTrue(stub_problem(honest, "etymology"))


class Coverage(unittest.TestCase):
    def test_each_kind_asks_for_its_own_data(self):
        defined = Entry(headword="w", senses=(Sense(definition_zh="拿"),))
        self.assertTrue(covered(defined, "definitions"))
        self.assertFalse(covered(Entry(headword="w", senses=(Sense(examples=(Example("e"),)),)), "definitions"))
        self.assertTrue(covered(Entry(headword="w", prons=(Pron("x"),)), "pronunciation"))
        self.assertTrue(covered(Entry(headword="w", etymology="from x"), "etymology"))
        colloc = Entry(headword="w", senses=(Sense(kind="collocation", examples=(Example("heavy rain", kind="collocation"),)),))
        self.assertTrue(covered(colloc, "collocations"))
        self.assertFalse(covered(defined, "collocations"))
        self.assertTrue(covered(Entry(headword="w", senses=(Sense(kind="note", examples=(Example("e"),)),)), "notes"))
        with self.assertRaises(ValueError):
            covered(defined, "everything")


if __name__ == "__main__":
    unittest.main()
