"""Classifying the forms dictionaries list."""
import unittest

from inventory.inflection_io import countability
from inventory.inflections import classify, clean_forms


def kinds(lemma, upos, forms, stress=None):
    return {(f.form, f.upos, f.slot, f.kind) for f in classify(lemma, list(upos), forms, stress)}


class Clean(unittest.TestCase):
    def test_alternatives_and_glued_pronunciations(self):
        self.assertEqual(clean_forms(["am/are", "analyses/ənælɪsiːz/"]), ["am", "are", "analyses"])
        self.assertEqual(clean_forms(["lateraling also lateralling", "millihenrys or millihenries", "-brums 或 -bra"]),
                         ["lateraling", "lateralling", "millihenrys", "millihenries", "-brums", "-bra"])


class Classify(unittest.TestCase):
    def test_regular_forms_get_their_slot(self):
        self.assertEqual(kinds("abandon", ["VERB"], ["abandon", "abandons", "abandoned", "abandoning"]), {
            ("abandons", "VERB", "3Sg", "regular"), ("abandoned", "VERB", "Past", "regular"),
            ("abandoned", "VERB", "PastPart", "regular"), ("abandoning", "VERB", "PresPart", "regular")})

    def test_irregular_verbs_split_past_and_participle(self):
        found = kinds("go", ["VERB", "NOUN"], ["goes", "went", "gone", "going"])
        self.assertIn(("went", "VERB", "Past", "irregular"), found)
        self.assertIn(("gone", "VERB", "PastPart", "irregular"), found)
        found = kinds("fly", ["VERB"], ["flies", "flew", "flown", "flying"])
        self.assertIn(("flew", "VERB", "Past", "irregular"), found)
        self.assertIn(("flown", "VERB", "PastPart", "irregular"), found)
        # one irregular form fills both slots
        found = kinds("teach", ["VERB"], ["teaches", "taught", "teaching"])
        self.assertTrue({("taught", "VERB", "Past", "irregular"), ("taught", "VERB", "PastPart", "irregular")} <= found)

    def test_a_lone_participle_beside_a_suppletive_past_is_no_past(self):
        found = kinds("go", ["VERB"], ["goes", "went", "gone", "going"])
        self.assertNotIn(("gone", "VERB", "Past", "irregular"), found)
        found = kinds("be", ["VERB"], ["am", "are", "is", "was", "were", "been", "being"])
        self.assertIn(("been", "VERB", "PastPart", "irregular"), found)
        self.assertNotIn(("been", "VERB", "Past", "irregular"), found)

    def test_an_unchanged_form_printed_among_the_forms_is_a_participle(self):
        found = kinds("glun", ["VERB"], ["glan", "glun", "glunning"])
        self.assertIn(("glun", "VERB", "PastPart", "irregular"), found)
        self.assertIn(("glan", "VERB", "Past", "irregular"), found)
        self.assertNotIn(("glan", "VERB", "PastPart", "irregular"), found)
        found = kinds("glome", ["VERB"], ["glame", "glome", "gloming", "glomes"])
        self.assertEqual({f for f in found if f[2] in ("Past", "PastPart")},
                         {("glame", "VERB", "Past", "irregular"), ("glome", "VERB", "PastPart", "irregular")})
        # alone, it is both (cut, hurt); first, it is the entry's base form (OALD prints it so)
        found = kinds("glut", ["VERB"], ["gluts", "glutting", "glut"])
        self.assertTrue({("glut", "VERB", "Past", "irregular"), ("glut", "VERB", "PastPart", "irregular")} <= found)
        self.assertEqual({f for f in kinds("glim", ["VERB"], ["glim", "glims"]) if f[0] == "glim"}, set())

    def test_the_lemma_listed_again_is_not_always_a_past(self):
        no_slots = lambda lemma, upos, forms: {f for f in kinds(lemma, upos, forms) if f[0] == lemma}
        self.assertEqual(no_slots("glim", ["VERB"], ["glims", "glimmed", "glimming", "glim"]), set())   # a regular past
        self.assertEqual(no_slots("glim", ["VERB"], ["glims", "glimming", "Glim"]), set())   # a capitalized use
        self.assertEqual(no_slots("glim", ["NOUN", "VERB"], ["glims", "glim"]), set())      # a noun's entry
        found = kinds("glin", ["VERB"], ["glan", "glon", "glinnen", "glin"])               # several past forms
        self.assertEqual({f for f in found if f[0] == "glin"}, set())

    def test_a_regular_form_beside_a_suppletive_past_leaves_the_participles_theirs(self):
        found = kinds("go", ["VERB"], ["went", "goed", "gone", "gorn", "going"])   # goed: another way to say went
        self.assertIn(("went", "VERB", "Past", "irregular"), found)
        self.assertEqual({f for f in found if f[0] in ("gone", "gorn")},
                         {("gone", "VERB", "PastPart", "irregular"), ("gorn", "VERB", "PastPart", "irregular")})

    def test_the_lemma_right_after_the_past_is_its_participle(self):
        found = kinds("glome", ["VERB"], ["glame", "glome", "glomed", "glam", "gloming"])   # a regular past beside
        self.assertEqual({f for f in found if f[2] in ("Past", "PastPart") and f[3] == "irregular"},
                         {("glame", "VERB", "Past", "irregular"), ("glome", "VERB", "PastPart", "irregular"),
                          ("glam", "VERB", "Past", "irregular")})
        found = kinds("glid", ["VERB"], ["glade", "glid", "glad", "glidden"])   # the -n form after it too
        self.assertEqual({(f[0], f[2]) for f in found}, {("glade", "Past"), ("glid", "PastPart"), ("glad", "Past"),
                                                          ("glidden", "PastPart")})
        # printed before the participle, the lemma is a past (glat, glatten), not glatten's past
        found = kinds("glat", ["VERB"], ["glatting", "glat", "glatten"])
        self.assertEqual({(f[0], f[2]) for f in found if f[2] in ("Past", "PastPart")},
                         {("glat", "Past"), ("glatten", "PastPart")})
        # one alternative of a past ("glat or glit"), not a participle
        self.assertEqual({f for f in kinds("glit", ["VERB"], ["glat or glit", "glitting", "glitted"]) if f[0] == "glit"},
                         set())

    def test_the_lemma_right_after_the_one_past_printed_since_the_present_participle(self):
        # other spellings of the verb printed before its -ing form (Chambers: a dialect base form)
        for forms in (["glen", "glinning", "glan", "glin"], ["glen", "glyn", "glinning", "glan", "glin"]):
            found = {(f[0], f[2]) for f in kinds("glin", ["VERB"], forms) if f[2] in ("Past", "PastPart")}
            self.assertIn(("glin", "PastPart"), found, forms)
            self.assertIn(("glan", "Past"), found, forms)
            self.assertNotIn(("glan", "PastPart"), found, forms)
        # two pasts printed before the lemma, no -ing between: still not its participle
        found = kinds("glin", ["VERB"], ["glan", "glon", "glin", "glinning"])
        self.assertEqual({f for f in found if f[0] == "glin"}, set())

    def test_a_participle_shaped_en_or_wn_form_is_never_a_past(self):
        # no English past ends in -en or -wn: printed alone, such a form fills the participle only
        for lemma, forms, form in (("glove", ["gloved", "gloven", "gloving"], "gloven"),   # beside a regular past
                                   ("glaw", ["glaws", "glawed", "glawn", "glawing"], "glawn"),
                                   ("gle", ["gleeing", "gleen"], "gleen")):                 # the past printed elsewhere
            found = {(f[0], f[2]) for f in kinds(lemma, ["VERB"], forms) if f[0] == form}
            self.assertEqual(found, {(form, "PastPart")}, lemma)
        # a form no longer than the lemma is no participle of it by that ending (glen, a spelling of glin)
        found = {(f[0], f[2]) for f in kinds("glin", ["VERB"], ["glen", "glinning", "glan"]) if f[0] == "glen"}
        self.assertEqual(found, {("glen", "Past")})
        # a lone past of another shape still fills both (taught)
        found = {(f[0], f[2]) for f in kinds("glun", ["VERB"], ["glunning", "glan"]) if f[0] == "glan"}
        self.assertEqual(found, {("glan", "Past"), ("glan", "PastPart")})

    def test_two_participle_shaped_forms_keep_their_printed_order(self):
        found = kinds("glin", ["VERB"], ["glan", "glun"])
        self.assertIn(("glan", "VERB", "Past", "irregular"), found)
        self.assertIn(("glun", "VERB", "PastPart", "irregular"), found)

    def test_nouns_and_adjectives(self):
        self.assertEqual(kinds("child", ["NOUN"], ["children"]), {("children", "NOUN", "Plur", "irregular")})
        self.assertEqual(kinds("good", ["ADJ", "NOUN"], ["better", "best"]),
                         {("better", "ADJ", "Cmp", "irregular"), ("best", "ADJ", "Sup", "irregular")})

    def test_vowel_changes_are_irregular_forms_not_variants(self):
        for lemma, upos, forms, expected in [
                ("write", ["VERB"], ["writes", "wrote", "written", "writing"], {("wrote", "Past"), ("written", "PastPart")}),
                ("sing", ["VERB"], ["sings", "sang", "sung", "singing"], {("sang", "Past"), ("sung", "PastPart")}),
                ("woman", ["NOUN"], ["women"], {("women", "Plur")}), ("foot", ["NOUN"], ["feet"], {("feet", "Plur")})]:
            found = {(f.form, f.slot) for f in classify(lemma, set(upos), forms, None) if f.kind == "irregular"}
            self.assertTrue(expected <= found, (lemma, found))

    def test_spelling_variants_by_known_alternations(self):
        from inventory.spelling import is_variant
        for a, b in [("colour", "color"), ("centre", "center"), ("organise", "organize"), ("analyse", "analyze"),
                     ("catalogue", "catalog"), ("programme", "program"), ("defence", "defense"),
                     ("judgement", "judgment"), ("catalyser", "catalyzer"), ("homestretch", "home stretch")]:
            self.assertTrue(is_variant(b, a), (a, b))
        self.assertTrue(is_variant("fulfill", "fulfil"))
        for a, b in [("forswear", "foreswear"), ("impale", "empale"), ("inquire", "enquire"), ("grey", "gray")]:
            self.assertTrue(is_variant(b, a), (a, b))
        self.assertTrue(is_variant("fulfillment", "fulfilment"))
        for a, b in [("foot", "feet"), ("write", "wrote"), ("trestle", "tressel")]:
            self.assertFalse(is_variant(b, a), (a, b))

    def test_the_entrys_printed_order_decides_between_noun_and_verb(self):
        self.assertIn(("knives", "NOUN", "Plur", "irregular"), kinds("knife", ["NOUN", "VERB"], ["knives"]))
        self.assertIn(("feet", "NOUN", "Plur", "irregular"), kinds("foot", ["NOUN", "VERB"], ["feet"]))
        self.assertIn(("lay", "VERB", "Past", "irregular"), kinds("lie", ["VERB", "NOUN"], ["lay", "lain"]))

    def test_suppletive_forms_get_their_slots(self):
        found = kinds("be", ["VERB"], ["am", "are", "is", "was", "were", "been", "being"])
        self.assertTrue({("was", "VERB", "Past", "irregular"), ("is", "VERB", "3Sg", "irregular"),
                         ("am", "VERB", "Pres", "irregular"), ("been", "VERB", "PastPart", "irregular")} <= found, found)
        self.assertIn(("geese", "NOUN", "Plur", "irregular"), kinds("goose", ["NOUN", "VERB"], ["geese"]))
        self.assertIn(("bought", "VERB", "Past", "irregular"), kinds("buy", ["VERB", "NOUN"], ["bought"]))

    def test_what_is_not_an_inflection(self):
        self.assertEqual(kinds("colour", ["NOUN", "VERB"], ["color"]), {("color", "", "", "variant")})
        self.assertEqual(kinds("abet", ["VERB"], ["abetter", "abets"]) >= {("abetter", "", "", "derivative")}, True)
        self.assertIn(("isn't", "", "", "contraction"), kinds("be", ["VERB"], ["is", "isn't"]))
        self.assertEqual(kinds("homestretch", ["NOUN"], ["home stretch"]), {("home stretch", "", "", "variant")})

    def test_doubling_is_recognised_either_way(self):
        self.assertIn(("abetted", "VERB", "Past", "regular"), kinds("abet", ["VERB"], ["abetted"]))
        self.assertIn(("travelled", "VERB", "Past", "regular"), kinds("travel", ["VERB"], ["travelled"]))


class Plausible(unittest.TestCase):
    def test_irregular_forms_need_their_shape_or_several_dictionaries(self):
        from inventory.irregulars import plausible_irregular as ok
        for form, lemma, upos, slot in [("criteria", "criterion", "NOUN", "Plur"), ("analyses", "analysis", "NOUN", "Plur"),
                                        ("cacti", "cactus", "NOUN", "Plur"), ("wolves", "wolf", "NOUN", "Plur"),
                                        ("women", "woman", "NOUN", "Plur"), ("flown", "fly", "VERB", "PastPart"),
                                        ("better", "good", "ADJ", "Cmp")]:
            self.assertTrue(ok(form, lemma, upos, slot, n=2), form)
        self.assertTrue(ok("went", "go", "VERB", "Past", n=1))        # suppletion: a closed list
        self.assertTrue(ok("better", "good", "ADJ", "Cmp", n=1))
        self.assertFalse(ok("demist", "defog", "VERB", "PastPart", n=2))
        self.assertTrue(ok("knives", "knife", "NOUN", "Plur", n=17))   # widely attested: trusted
        for form, lemma, upos, slot in [("compulsively", "compulsive", "NOUN", "Plur"), ("doorjamb", "doorpost", "NOUN", "Plur"),
                                        ("gorgeousness", "gorgeous", "ADJ", "Cmp"), ("f", "fluorine", "NOUN", "Plur"),
                                        ("dribbler", "dribble", "VERB", "Past"), ("catalyzer", "catalyser", "NOUN", "Plur"),
                                        ("loculus", "locule", "NOUN", "Plur"), ("bickers", "bickering", "NOUN", "Plur"),
                                        ("odontologists", "odontology", "NOUN", "Plur"), ("feeders", "feed", "VERB", "3Sg")]:
            self.assertFalse(ok(form, lemma, upos, slot, n=2), form)
        for form, lemma in [("children", "child"), ("neurocytomata", "neurocytoma"), ("kronen", "krone"),
                            ("geese", "goose"), ("firemen", "fireman"), ("agents-general", "agent-general"),
                            ("dormice", "dormouse")]:
            self.assertTrue(ok(form, lemma, "NOUN", "Plur", n=1), form)
        for form, lemma in [("penuchle", "pinochle"), ("grenadilla", "granadilla"), ("trustee", "trusty"),
                            ("pita", "pitta"), ("charka", "charkha"), ("agha", "aga"), ("aureola", "aureole"),
                            ("done", "do"), ("hyperkinesia", "hyperkinesis")]:
            self.assertFalse(ok(form, lemma, "NOUN", "Plur", n=5), form)   # respellings, however widely listed
        for form, lemma in [("cellos", "cello"), ("chillies", "chilli"), ("saga", "sagum"), ("beaux", "beau"),
                            ("menschen", "mensch"), ("dayanim", "dayan")]:
            self.assertTrue(ok(form, lemma, "NOUN", "Plur", n=5), form)
        for form, lemma in [("swizzle", "swiz"), ("faggot", "fag"), ("scarpa", "scarper")]:
            self.assertFalse(ok(form, lemma, "VERB", "Past", n=1), form)
        self.assertTrue(ok("lay", "lie", "VERB", "Past", n=18))
        self.assertTrue(ok("forgotten", "forget", "VERB", "PastPart", n=15))
        for form, lemma in [("sang", "sing"), ("wrote", "write"), ("flew", "fly"), ("taught", "teach"), ("sold", "sell"),
                            ("left", "leave"), ("made", "make"), ("fled", "flee"), ("ate", "eat")]:
            self.assertTrue(ok(form, lemma, "VERB", "Past", n=1), form)  # thinly attested, still believable

    def test_another_words_regular_form_is_not_an_irregular_form(self):
        from inventory.inflections import others_regular_forms
        taken = others_regular_forms({("plan", "VERB"), ("plane", "NOUN"), ("feeder", "NOUN"), ("feed", "VERB")})
        self.assertEqual(taken["planned"], {"plan"})
        self.assertEqual(taken["feeders"], {"feeder"})
        self.assertNotIn("fed", taken)


class ZeroPlurals(unittest.TestCase):
    def test_marked_by_same_or_by_listing_the_lemma(self):
        from inventory.inflections import classify_source
        ode = {(f.form, f.upos, f.slot) for f in classify_source("ode", "deer", ["NOUN"], ["same"], None)}
        cobuild = {(f.form, f.upos, f.slot) for f in classify_source("cobuild", "sheep", ["NOUN"], ["sheep"], None)}
        self.assertEqual(ode, {("deer", "NOUN", "Plur")})
        self.assertEqual(cobuild, {("sheep", "NOUN", "Plur")})
        spread = {(f.form, f.slot) for f in classify_source("cobuild", "spread", ["VERB", "NOUN"], ["spread", "spreads"], None)}
        self.assertNotIn(("spread", "Plur"), spread)  # a verb's base form, not a zero plural
        # elsewhere the lemma among its own forms is only the base form
        self.assertEqual(classify_source("oald", "fish", ["NOUN", "VERB"], ["fish", "fishes", "fished"], None) and
                         {f.form for f in classify_source("oald", "fish", ["NOUN", "VERB"], ["fish"], None)}, set())


class ThinEvidence(unittest.TestCase):
    def test_a_single_dictionarys_irregular_form_needs_a_known_pattern(self):
        from inventory.irregulars import supported_by_pattern as ok
        strong = {("built", "build", "VERB", "PastPart"), ("shone", "shine", "VERB", "PastPart"), ("went", "go", "VERB", "Past")}
        for form, lemma, upos, slot in [("collegia", "collegium", "NOUN", "Plur"), ("agalmata", "agalma", "NOUN", "Plur"),
                                        ("donne", "donna", "NOUN", "Plur"), ("genera", "genus", "NOUN", "Plur"),
                                        ("junkmen", "junkman", "NOUN", "Plur"), ("midrashim", "midrash", "NOUN", "Plur"),
                                        ("misbuilt", "misbuild", "VERB", "PastPart"), ("reshone", "reshine", "VERB", "PastPart"),
                                        ("outwent", "outgo", "VERB", "Past")]:
            self.assertTrue(ok(form, lemma, upos, slot, strong), form)
        for form, lemma, upos, slot in [("wourari", "wourali", "NOUN", "Plur"), ("epistoma", "epistome", "NOUN", "Plur"),
                                        ("spinages", "spinach", "NOUN", "Plur"), ("retirant", "retire", "VERB", "Past"),
                                        ("varoom", "vroom", "VERB", "Past"), ("sweel", "sweal", "VERB", "Past")]:
            self.assertFalse(ok(form, lemma, upos, slot, strong), form)


class Sources(unittest.TestCase):
    def test_historical_spellings_are_not_inflections(self):
        from inventory.inflections import classify_source
        found = classify_source("oed", "white", {"ADJ"}, ["quhyit", "whyte"], None)
        self.assertEqual({(f.form, f.kind) for f in found}, {("quhyit", "historical"), ("whyte", "historical")})


class Countability(unittest.TestCase):
    def test_from_labels_and_codes(self):
        self.assertEqual(countability("noun", ["uncountable"]), "Mass")
        self.assertEqual(countability("N-UNCOUNT", []), "Mass")
        self.assertEqual(countability("noun", ["countable"]), "Count")
        self.assertEqual(countability("noun", []), "")


if __name__ == "__main__":
    unittest.main()
