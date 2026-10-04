"""Reading the dictionaries' usage labels into (axis, value) pairs."""
import unittest

from inventory.label_tables import Label
from inventory.labels import normalize


def read(label):
    return sorted(f"{l.axis}:{l.value}" for l in normalize(label))


class Axes(unittest.TestCase):
    def test_register_region_time_attitude(self):
        self.assertEqual(read("informal"), ["register:informal"])
        self.assertEqual(read("INFORMAL"), ["register:informal"])
        self.assertEqual(read("Brit. informal"), ["region:GB", "register:informal"])
        self.assertEqual(read("chiefly N. Amer."), ["region:NAm"])
        self.assertEqual(read("British English, informal, disapproving"),
                         ["attitude:disapproving", "region:GB", "register:informal"])
        self.assertEqual(read("†"), ["time:obsolete"])
        self.assertEqual(read("becoming old-fashioned"), ["time:dated"])

    def test_domains_listed_and_by_shape(self):
        self.assertEqual(read("Medicine"), ["domain:medicine"])
        self.assertEqual(read("Pathol."), ["domain:pathology"])
        self.assertEqual(read("Cell Biology"), ["domain:cell biology"])
        self.assertEqual(read("slang (chiefly Jazz)"), ["domain:music", "register:slang"])

    def test_chinese_abbreviations(self):
        self.assertEqual(read("美口"), ["region:US", "register:informal"])
        self.assertEqual(read("古或方"), ["region:dialect", "time:archaic"])
        self.assertEqual(read("医-产科学"), ["domain:medicine", "domain:obstetrics"])
        self.assertEqual(read("主英"), ["region:GB"])            # 主: mainly, dropped
        self.assertEqual(read("常用被动语态"), ["grammar:usu passive"])  # 常 here is part of the label
        self.assertEqual(read("亦作 M-"), ["form:capitalized"])

    def test_a_chinese_key_of_another_table_is_read(self):
        self.assertEqual(read("缩约形式"), ["form:contraction"])
        self.assertEqual(read("美缩约形式"), ["form:contraction", "region:US"])

    def test_a_known_label_with_or_inside_is_not_split(self):
        self.assertEqual(read("美用作单或复"), ["grammar:N plural, sing/pl verb", "region:US"])
        self.assertEqual(read("古或方"), ["region:dialect", "time:archaic"])   # 或 between two labels

    def test_a_known_label_with_or_inside_survives_other_separators(self):
        whole = ["grammar:N plural, sing/pl verb", "region:US", "register:informal"]
        for printed in ("美用作单或复，口", "口，美用作单或复", "美用作单或复、口", "口或美用作单或复", "〈美〉用作单或复-口"):
            self.assertEqual(read(printed), whole, printed)
        self.assertEqual(read("古，方"), ["region:dialect", "time:archaic"])
        self.assertEqual(read("古或"), ["time:archaic"])       # a separator with nothing after it
        self.assertEqual(read("古或某某"), [])                  # a stretch no table knows: nothing is read
        self.assertEqual(read("，"), [])

    def test_selection(self):
        self.assertEqual(read("+ person"), ["selection:person"])
        self.assertEqual(read("+of animal"), ["selection:animal"])
        self.assertEqual(read("of a horse"), ["selection:horse"])


class Grammar(unittest.TestCase):
    def test_codes_become_cobuild_patterns(self):
        self.assertEqual(read("C"), ["grammar:N count"])
        self.assertEqual(read("mass noun"), ["grammar:N uncount"])
        self.assertEqual(read("countable, uncountable"), ["grammar:N count/uncount"])
        self.assertEqual(read("with object"), ["grammar:V n"])
        self.assertEqual(read("tr"), ["grammar:V n"])
        self.assertEqual(read("+ to infinitive"), ["grammar:~ to-inf"])
        self.assertEqual(read("only before noun"), ["grammar:~ n"])
        self.assertEqual(read("not usually before noun"), ["grammar:v-link ADJ"])

    def test_cobuild_notations(self):
        self.assertEqual(read("V n"), ["grammar:V n"])
        self.assertEqual(read("V"), ["grammar:V"])
        self.assertEqual(read("usu ADJ n"), ["grammar:ADJ n"])
        self.assertEqual(read("VERB noun"), ["grammar:V n"])
        self.assertEqual(read("Also VERB n PREPOSITION"), ["grammar:V n prep"])
        self.assertEqual(read("V P n (not pron)"), ["grammar:V P n (not pron)"])


class NotLabels(unittest.TestCase):
    def test_oed_structure_is_noise(self):
        self.assertEqual(normalize("α."), (Label("none", "α"),))
        self.assertEqual(read("(b)"), ["none:b"])
        self.assertEqual(read("c1330 [see sense 1a]."), ["none:c1330 [see sense 1a]"])

    def test_noise_never_shadows_a_label(self):
        from inventory.label_tables import NOISE
        from inventory.labels import _TABLES
        self.assertEqual([w for w in NOISE if any(w in t for t in _TABLES)], [])
        self.assertEqual(read("absol."), ["grammar:absolute"])
        self.assertEqual(read("countable + of"), ["grammar:N count", "grammar:~ of"])
        self.assertEqual(read("informal + old-fashioned"), ["register:informal", "time:dated"])

    def test_a_label_with_an_unknown_part_is_not_half_read(self):
        self.assertEqual(normalize("informal, zorblax"), ())
        self.assertEqual(normalize("informal, zorblax slang"), ())
        self.assertEqual(normalize("zorblax slang"), ())
        self.assertEqual(read("comput sl"), ["domain:computing", "register:slang"])
        self.assertEqual(read("British vulgar slang"), ["region:GB", "register:slang", "register:vulgar"])

    def test_conjunctions_split_in_any_case(self):
        self.assertEqual(read("OLD-FASHIONED OR HUMOROUS"), ["attitude:humorous", "time:dated"])
        self.assertEqual(read("US AND AUSTRALIAN ENGLISH"), read("US and Australian English"))
        self.assertEqual(read("US AND AUSTRALIAN ENGLISH"), ["region:AU", "region:US"])


if __name__ == "__main__":
    unittest.main()
