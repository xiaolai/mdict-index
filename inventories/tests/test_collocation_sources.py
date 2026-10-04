"""Reading each source's collocation notation (invented fixtures)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from inventory import collocation_sources
from inventory.collocation_sources import (PHRASE, QUANT, UNTYPED, Corpus, Raw, ldoce_heading, ldoce_page, med_entry,
                                           med_header, ncecd, ocd_label, order_in_examples, side_in_examples)


class OcdLabels(unittest.TestCase):
    def test_labels_give_the_collocate_and_its_side(self):
        self.assertEqual(ocd_label("VERB + PLAN", "plan"), ("VERB", "before", "NOUN"))
        self.assertEqual(ocd_label("PLAN + VERB", "plan"), ("VERB", "after", "NOUN"))
        self.assertEqual(ocd_label("PLAN + NOUN", "plan"), ("NOUN", "after", "NOUN"))
        self.assertEqual(ocd_label("ADJECTIVE", "plan"), ("ADJ", "before", "NOUN"))
        self.assertEqual(ocd_label("… OF SNOW", "snow"), (QUANT, "before", "NOUN"))
        self.assertEqual(ocd_label("used with these nouns as the object", "draft"), ("NOUN", "after", "VERB"))
        self.assertEqual(ocd_label("PHRASES", "plan"), (PHRASE, "", ""))

    def test_a_label_naming_a_spelling_variant_or_a_plural(self):
        self.assertEqual(ocd_label("VERB + COLOUR/COLOR", "colour"), ("VERB", "before", "NOUN"))
        self.assertEqual(ocd_label("VERB + PLANS", "plan"), ("VERB", "before", "NOUN"))

    def test_notes_are_not_collocations(self):
        self.assertIsNone(ocd_label("NOTE: Kinds of plan", "plan"))

    def test_a_part_of_speech_label_is_not_the_base(self):
        # "adjective" starts with the base "ad": the label's other side is still the base
        self.assertEqual(ocd_label("ADJECTIVE + AD", "ad"), ("ADJ", "before", "NOUN"))
        self.assertEqual(ocd_label("AD + VERB", "ad"), ("VERB", "after", "NOUN"))


class LdoceHeadings(unittest.TestCase):
    def test_headings(self):
        self.assertEqual(ldoce_heading("verbs", "plan"), ("VERB", ""))
        self.assertEqual(ldoce_heading("phrases", "plan"), (PHRASE, ""))
        self.assertEqual(ldoce_heading("ADJECTIVES/NOUN + snow", "snow"), ("ADJ|NOUN", "before"))
        self.assertEqual(ldoce_heading("snow + NOUN", "snow"), ("NOUN", "after"))
        self.assertIsNone(ldoce_heading("COMMON ERRORS", "snow"))


PAGE = """<span class="entry" type="entry" id="entry_plan"><span class="section">
<span class="secheading">verbs</span>
<span class="collocate"><span class="colloc collo">sketch/devise a plan</span><span class="collgloss"> (=think one up)</span></span>
</span></span>
<span class="entry" type="dictionary" id="dictionary_plan">
<span class="collocate"><span class="colloc collo">a sly plan</span></span></span>
<span class="entry" type="corpus_collos" id="corpus_collos_plan"><span class="section">
<span class="secheading">NOUN</span>
<span class="collocate"><span class="expandable"><span class="colloc collo">pension</span></span><div class="content">
<span class="example">The pension plan was reformed.</span><span class="example">A new pension plan.</span></div></span>
</span></span>"""


class LdocePage(unittest.TestCase):
    def test_the_three_blocks(self):
        raws = list(ldoce_page(PAGE, "plan", "NOUN", {}))  # no inflections needed: "pension plan"
        self.assertEqual(raws, [
            Raw("ldoce", "plan", "NOUN", "VERB", "", "sketch/devise a plan", "think one up"),
            Raw("ldoce", "plan", "", UNTYPED, "", "a sly plan"),  # other entries: any part of speech
            Raw("ldoce", "plan", "NOUN", "NOUN", "before", "pension"),
        ])

    def test_the_words_between_from_examples(self):
        sleep, cry = frozenset({"sleep"}), frozenset({"cry", "cried", "cries"})
        self.assertEqual(order_in_examples(["The twins cried themselves to sleep.", "We cry ourselves to sleep.", "He cried, then slept."],
                                           sleep, cry), ("before", ("oneself", "to")))
        # a clear plurality counts: 2 of 4, the rest scattered
        self.assertEqual(order_in_examples(["cried themselves to sleep", "cried ourselves to sleep", "cried in sleep",
                                            "cried during sleep"], sleep, cry), ("before", ("oneself", "to")))
        # articles and possessives vary: they do not make a pattern
        self.assertEqual(order_in_examples(["cried her eyes", "cried my eyes", "cried his eyes"], frozenset({"eyes"}), cry),
                         ("before", ()))
        # the words too far apart in every example: the side, no gap
        self.assertEqual(order_in_examples(["cried and cried, and much later, at last, sleep came"], sleep, cry),
                         ("before", ()))
        # no dominant reading: the side only
        self.assertEqual(order_in_examples(["cried in her sleep", "cried during sleep"], sleep, cry), ("before", ()))

    def test_the_words_between_come_from_the_winning_side(self):
        # "in" stands between them only in the minority order: it is not read into the majority's
        sleep, cry = frozenset({"sleep"}), frozenset({"cry", "cried"})
        examples = ["sleep came long after she had cried"] * 3 + ["cried in sleep"] * 2
        self.assertEqual(order_in_examples(examples, sleep, cry), ("after", ()))

    def test_the_nearest_pair_in_one_sentence(self):
        # the first "sleep" is in another clause; the pair that goes together is the nearest
        sleep, cry = frozenset({"sleep"}), frozenset({"cry", "cried"})
        self.assertEqual(order_in_examples(["Sleep matters; we cry ourselves to sleep."] * 2, sleep, cry),
                         ("before", ("oneself", "to")))
        # the two in different sentences only: no evidence of order
        self.assertEqual(order_in_examples(["I need sleep. Then I cried."], sleep, cry), ("", ()))

    def test_unread_corpus_collocates_keep_their_examples(self):
        raws = list(ldoce_page(PAGE, "plan", "NOUN", {}, unread=True))
        self.assertEqual(raws[-1], Corpus(Raw("ldoce", "plan", "NOUN", "NOUN", "", "pension"),
                                          ("The pension plan was reformed.", "A new pension plan.")))
        self.assertEqual(raws[:2], list(ldoce_page(PAGE, "plan", "NOUN", {}))[:2])

    def test_side_from_examples(self):
        self.assertEqual(side_in_examples(["The plans were drafted.", "drafting a plan"],
                                          frozenset({"plan", "plans"}), frozenset({"draft", "drafted"})), "after")


BOX = """<div id="headbar"><span class="PART-OF-SPEECH">noun</span></div>
<div class="sidebox"><div class="ONEBOX-HEAD">Collocates: plan</div><div class="sideboxbody">Adjectives frequently
used with <span class="COL-HW">plan</span> <div class="p">▪ <span class="ONE-COLLOCATE">bold</span>,
<span class="ONE-COLLOCATE">rough</span></div>Verbs frequently used with <span class="COL-HW">plan</span> as the object
<div class="p">▪ <span class="ONE-COLLOCATE">shelve</span></div></div></div>"""


class Med(unittest.TestCase):
    def test_the_header_fixes_the_base_part_of_speech(self):
        self.assertEqual(med_header("Adjectives frequently used with worry", "VERB"), ("worry", "NOUN", "ADJ", "before"))
        self.assertEqual(med_header("Adverbs frequently used with worry", "VERB"), ("worry", "VERB", "ADV", ""))

    def test_headers(self):
        self.assertEqual(med_header("Nouns frequently used as objects of shelve", "VERB"), ("shelve", "VERB", "NOUN", "after"))
        self.assertEqual(med_header("Verbs frequently used with plan  as the subject", "NOUN"), ("plan", "NOUN", "VERB", "after"))
        self.assertIsNone(med_header("Synonyms", "NOUN"))

    def test_headers_in_capitals(self):
        self.assertEqual(med_header("Nouns frequently used as OBJECTS of shelve", "VERB"), ("shelve", "VERB", "NOUN", "after"))
        self.assertEqual(med_header("Verbs frequently used with plan as the SUBJECT", "NOUN"), ("plan", "NOUN", "VERB", "after"))

    def test_a_box(self):
        self.assertEqual(list(med_entry(BOX)), [
            Raw("med", "plan", "NOUN", "ADJ", "before", "bold"), Raw("med", "plan", "NOUN", "ADJ", "before", "rough"),
            Raw("med", "plan", "NOUN", "VERB", "before", "shelve")])


class Connections(unittest.TestCase):
    def test_a_reader_stopped_early_closes_its_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ncecd.db"
            con = sqlite3.connect(db)
            con.executescript("""CREATE TABLE s_entry (entry_id INTEGER, headword TEXT);
                CREATE TABLE s_sense (id INTEGER, entry_id INTEGER, pos TEXT);
                CREATE TABLE s_example (sense_id INTEGER, ord INTEGER, kind TEXT, text TEXT, text_zh TEXT);
                INSERT INTO s_entry VALUES (1, 'glim'); INSERT INTO s_sense VALUES (1, 1, 'noun');
                INSERT INTO s_example VALUES (1, 1, 'collocation', 'a bold glim', ''),
                                             (1, 2, 'collocation', 'a glum glim', '');""")
            con.commit()
            con.close()
            opened = []
            real = sqlite3.connect

            def connect(*args, **kwargs):
                opened.append(mock.MagicMock(wraps=real(*args, **kwargs)))
                return opened[-1]
            with mock.patch.object(collocation_sources.sqlite3, "connect", connect):
                reader = ncecd(db)
                next(reader)
                reader.close()
            self.assertEqual(len(opened), 1)
            opened[0].close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
