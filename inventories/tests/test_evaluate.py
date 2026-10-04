"""The scorer's own checks."""
import io
import json
import random
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from inventory import evaluate
from inventory.collocation_sources import Corpus, Raw
from inventory.evaluate import (_collocation_item, _fresh, _label_inputs, collocation_output, known_inputs, load,
                                without_training)


class Load(unittest.TestCase):
    def test_a_file_that_is_not_gold_is_refused_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "x.jsonl").write_text(json.dumps({"text": "glim", "kind": "idiom"}) + "\n")
            with self.assertRaisesRegex(ValueError, "not a gold item"):
                load(Path(tmp))
            Path(tmp, "x.jsonl").write_text(json.dumps({"inventory": "notation", "input": {"printed": "glim"}}) + "\n")
            with self.assertRaisesRegex(ValueError, "not a gold item"):   # no "expected"
                load(Path(tmp))


class HeldOut(unittest.TestCase):
    def test_a_held_out_score_leaves_out_what_the_training_gold_holds(self):
        label = lambda l, uses: {"inventory": "label", "input": {"label": l, "uses": uses}, "expected": []}
        record = {"dictionary": "ldoce", "base": "glim", "base_upos": "NOUN", "coll": "VERB", "gloss": "", "zh": ""}
        colloc = lambda printed, side: {"inventory": "collocation", "input": {"raw": {**record, "side": side,
                                                                                    "printed": printed}},
                                        "expected": {}}
        training = [label("glim", 9), colloc("glorp to the glim", "")]
        held = [label("glim", 12),                 # the same label, counted again since: the same input
                label("glum", 3),
                colloc("glorp", ""),               # the bare collocate the training item was read from
                colloc("glarp", "before")]
        kept, excluded = without_training(held, training)
        self.assertEqual([i["input"].get("label") or i["input"]["raw"]["printed"] for i in kept], ["glum", "glarp"])
        self.assertEqual(excluded, 2)

    def test_main_scores_each_held_out_set_without_the_training_overlap(self):
        label = lambda l: json.dumps({"inventory": "label", "input": {"label": l, "uses": 1},
                                      "expected": ["register:informal"]})
        with tempfile.TemporaryDirectory() as tmp:
            gold = Path(tmp)
            (gold / "heldout").mkdir()
            (gold / "heldout2").mkdir()
            (gold / "label.jsonl").write_text(label("informal") + "\n")
            (gold / "heldout" / "label.jsonl").write_text(label("informal") + "\n" + label("infml") + "\n")
            # the first held-out set was used to fix rules before the second was drawn
            (gold / "heldout2" / "label.jsonl").write_text(label("infml") + "\n" + label("inf") + "\n")
            out = io.StringIO()
            with mock.patch.object(evaluate, "GOLD", gold), mock.patch.object(evaluate, "context", dict), \
                    mock.patch.object(sys, "argv", ["evaluate.py"]), redirect_stdout(out):
                evaluate.main()
        text = out.getvalue()
        self.assertIn("heldout: 1 of 2 items left out, also in the training gold", text)
        self.assertRegex(text, r"heldout:[^\n]*\nlabel\s+\d+/1 ")
        self.assertIn("heldout2: 1 of 2 items left out, also in the training gold or heldout", text)
        self.assertRegex(text, r"heldout2:[^\n]*\nlabel\s+\d+/1 ")


class Sampling(unittest.TestCase):
    def test_weighted_labels_fill_the_sample(self):
        uses = Counter({"glim": 100000, "glum": 1, "glimmer": 1})
        drawn = _label_inputs(random.Random(1), 3, 0, uses)
        self.assertEqual(sorted(d["label"] for d in drawn), ["glim", "glimmer", "glum"])

    def test_a_held_out_draw_leaves_out_the_other_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            gold = Path(tmp)
            (gold / "heldout" / "candidates").mkdir(parents=True)
            item = lambda label: json.dumps({"inventory": "label", "input": {"label": label, "uses": 9}, "expected": []})
            (gold / "label.jsonl").write_text(item("glim") + "\n")                        # training gold
            (gold / "heldout" / "label.jsonl").write_text(item("glum") + "\n")           # this sample's own gold
            (gold / "heldout" / "candidates" / "label.jsonl").write_text(item("glimmer") + "\n")
            (gold / "notes.jsonl").write_text(json.dumps({"text": "glim", "kind": "idiom"}) + "\n")  # not gold items
            known = known_inputs(gold, gold / "heldout" / "candidates")
            self.assertEqual(dict(known), {"label": {json.dumps("glim")}})
            uses = Counter({"glim": 100, "glum": 50, "glimmer": 10})
            drawn = _label_inputs(random.Random(1), 2, 0, uses, known)
        self.assertEqual(sorted(d["label"] for d in drawn), ["glimmer", "glum"])

    def test_a_collocate_drawn_before_is_known_by_its_record_not_its_reading(self):
        record = {"dictionary": "ldoce", "base": "glim", "base_upos": "NOUN", "coll": "VERB", "gloss": "", "zh": ""}
        unread = lambda printed: {"raw": {**record, "side": "", "printed": printed}}
        with tempfile.TemporaryDirectory() as tmp:
            gold = Path(tmp)
            (gold / "heldout" / "candidates").mkdir(parents=True)
            stored = [{**record, "side": "before", "printed": "glarp"},            # read: the side its examples gave
                      {**record, "side": "", "printed": "glorp to the glim"},      # read: words between it and the base
                      {**record, "side": "", "printed": "glim of the glump"}]
            (gold / "collocation.jsonl").write_text("".join(json.dumps(
                {"inventory": "collocation", "input": {"raw": r}, "expected": {}}) + "\n" for r in stored))
            known = known_inputs(gold, gold / "heldout" / "candidates")
        drawn = [_collocation_item(Corpus(Raw(**unread(p)["raw"]), ("...",))) for p in
                 ("glarp", "glorp", "glump", "the glump", "glurp")]
        fresh = _fresh("collocation", drawn, known)
        self.assertEqual([d["raw"]["printed"] for d in fresh], ["glurp"])
        page = {**record, "side": "after", "printed": "glarp"}   # another source's record is another input
        self.assertEqual(len(_fresh("collocation", [{"raw": {**page, "dictionary": "med"}}], known)), 1)

    def test_an_ldoce_corpus_collocate_is_stored_unread(self):
        raw = Raw("ldoce", "sleep", "NOUN", "VERB", "", "cry")
        item = _collocation_item(Corpus(raw, ("The twins cried themselves to sleep.", "We cry ourselves to sleep.")))
        self.assertEqual(item, {"raw": {"dictionary": "ldoce", "base": "sleep", "base_upos": "NOUN", "coll": "VERB",
                                        "side": "", "printed": "cry", "gloss": "", "zh": ""},
                                "examples": ["The twins cried themselves to sleep.", "We cry ourselves to sleep."]})
        ctx = {"evidence": None, "pos_of": {"cry": {"VERB"}, "sleep": {"NOUN"}}, "lemmas": {"cried": "cry"},
               "forms_of": {"cry": frozenset({"cried"})}}
        self.assertEqual(collocation_output(item, ctx)["patterns"], ["cry {oneself} to ~"])  # read again, today


if __name__ == "__main__":
    unittest.main()
