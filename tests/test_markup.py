"""HTML helpers shared by the parsers."""
import unittest

from structured.markup import clean, has_cjk, parse, split_en_zh, text


class Text(unittest.TestCase):
    def test_line_breaks_and_blocks_separate_words(self):
        self.assertEqual(text(parse("hello<br>world")), "hello world")
        self.assertEqual(text(parse("<p>one</p><p>two</p>")), "one two")
        self.assertEqual(text(parse("<ul><li>a</li><li>b</li></ul><div>c</div>")), "a b c")

    def test_every_block_level_element_of_the_html_rendering_rules_separates_words(self):
        for tag in ("fieldset", "form", "legend", "center", "dialog", "search", "menu", "dir", "hgroup", "listing",
                    "xmp", "thead", "tbody", "tfoot", "colgroup"):
            self.assertEqual(text(parse(f"hello<{tag}>world</{tag}>again")), "hello world again", tag)

    def test_a_block_holding_no_text_separates_nothing(self):
        # An audio icon's <div>, styled inline by the dictionary, between a word and its comma.
        self.assertEqual(text(parse('CAR<b>pet</b><div class="pron"><a href="sound://x.mp3"><img src="i.png"></a></div>, next')),
                         "CARpet, next")
        self.assertEqual(text(parse("a<div><img src=\"i.png\"></div>b<br>c")), "ab c")

    def test_inline_markup_does_not_split_words(self):
        self.assertEqual(text(parse("un<b>believ</b><i>able</i> <span>x</span>")), "unbelievable x")

    def test_whitespace_collapses_as_in_clean(self):
        self.assertEqual(text(parse("  a \n b  ")), "a b")
        self.assertEqual(text(None), "")
        self.assertEqual(text("  plain\tstring "), clean("  plain\tstring "))

    def test_comments_are_not_text_but_what_follows_them_is(self):
        self.assertEqual(text(parse("a<!-- hidden -->b")), "ab")


class Cjk(unittest.TestCase):
    def test_supplementary_ideographs_are_cjk(self):
        self.assertTrue(has_cjk("𠮷"))
        self.assertEqual(split_en_zh("English 𠮷野"), ("English", "𠮷野"))

    def test_an_opening_bracket_before_spaces_stays_with_the_chinese(self):
        self.assertEqual(split_en_zh("hello （ 中文）"), ("hello", "（ 中文）"))
        self.assertEqual(split_en_zh("hello （打电话）喂"), ("hello", "（打电话）喂"))
        self.assertEqual(split_en_zh("say ( 【中文】"), ("say", "( 【中文】"))
        self.assertEqual(split_en_zh("plain"), ("plain", ""))


if __name__ == "__main__":
    unittest.main()
