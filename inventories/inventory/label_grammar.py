"""Grammar labels: the GRAMMAR table (values in COBUILD's pattern notation, "~" standing for
the word's own class) and COBUILD's own pattern strings ("V n", "usu ADJ n", "VERB noun"),
read by `_cobuild` into the short notation. Used by inventory/labels.py.
"""
from __future__ import annotations

import re

from inventory.label_tables import Label, _pairs


# Grammar. "~" stands for the word's own class: the inventory writes V, N or ADJ for it.
GRAMMAR = _pairs("grammar", """
    N count: c; countable; count; count noun; cn; [c]; n-count; countable noun |
    N uncount: u; uncountable; noncount; mass noun; uncount; [u]; n-uncount; uncountable noun; mass; non-count |
    N count/uncount: countable, uncountable; countable/uncountable; count, noncount; uncountable, countable; c, u; u, c; countable or uncountable; c/u; u/c; count noun and mass noun; mass noun and count noun |
    N sing: s; singular; sing; in singular; in sing; n-sing; singular noun; [s]; only singular |
    N plural: plural; pl; plural noun; in plural; in pl; n-plural; plural in construction; [pl]; plurals; pl n |
    usu N sing: usually singular; usu sing; usually sing; usu. in sing; usually in singular; countable usually singular; countable, usually singular; usu in sing |
    usu N plural: usually plural; usu pl; usually pl; often plural; usu plural; usually in plural; usu in pl; countable usually plural |
    N plural, sing verb: treated as singular; functioning as singular; treated as sing; used with a sing. verb; singular in construction; takes a singular verb |
    N plural, sing/pl verb: treated as singular or plural; functioning as singular or plural; singular or plural verb;
        plural but singular or plural in construction; + sing/pl verb; singular or plural in construction; sing. or pl. in construction; treated as sing. or pl; + singular or plural verb |
    N coll: collective; collective noun; collectively |
    N n: as modifier; usu. as modifier; usually as modifier; often as modifier; modifier; noun modifier; n-var; n n |
    V n: t; when tr; transitive; with object; + object; transitive verb; vt; tr; trans; with obj; [t]; v-t; transitive v |
    V: i; when intr; intransitive; no object; intransitive verb; vi; intr; [i]; no obj; intrans; v-i |
    V/V n: intransitive, transitive; transitive, intransitive; intransitive/transitive; transitive/intransitive; t, i; i, t; transitive and intransitive; intransitive and transitive; tr and intr; i/t; t/i; no object or with object; with or without object; intr & tr; tr & intr; tr, intr; intr, tr |
    usu V n: mainly tr; usually transitive |
    usu V: mainly intr; usually intransitive |
    V pron-refl: reflexive; transitive (reflexive); refl; reflexive verb; v-refl |
    usu passive: usually passive; often passive; oft passive; usu passive; usually in passive; usu. passive; be v-ed; transitive (in passive); be verb-ed; often in passive |
    no passive: no passive; not passive; not usually passive |
    no cont: no cont; not used in the progressive tenses; not progressive; no continuous |
    ~ to-inf: + to infinitive; an infinitive; with infinitive; + to-infinitive; + to inf; with to-infinitive; to-infinitive; + to |
    ~ that: + that; + (that); takes a clause as object; with clause; that-clause; with that-clause; + that clause |
    ~ -ing: + -ing verb; + -ing; with -ing; + v-ing; + ing; -ing |
    ~ wh: + question word; + wh- word; with wh-clause; + wh |
    ~ adv/prep: + adv/prep; always followed by an adverb or preposition; with adverbial; with adverbial of direction; no obj., with adverbial of direction; no object, with adverbial of direction; no obj., with adverbial; no object, with adverbial; intransitive always + adverb/preposition; + adv; + prep; with adv or prep; adverb or preposition |
    V n adv/prep: with obj. and adverbial of direction; with object and adverbial of direction; with obj. and adverbial; with object and adverbial; transitive always + adverb/preposition |
    V n to-inf: with obj. and infinitive; with obj. and usu. infinitive; with object and infinitive |
    V n n: with two objs; with two objects; + two objects; double object |
    V n adj: with object and complement; with obj. and complement; + object + adjective; + obj + adj |
    V n to-inf: with object and infinitive; with obj. and infinitive; + object + to infinitive; + obj + to inf |
    V with quote: with direct speech; + speech; with direct object and speech; + direct speech |
    ~ of: + of; + of person; +of person |
    ~ for: + for |
    ~ with: + with |
    ~ in: + in |
    ~ on: + on |
    ~ to: + to sb |
    ~ about: + about |
    ~ at: + at |
    ~ n: attributive; attrib; before noun; only before noun; always used before a noun; usually before noun; prenominal; usu before noun; only before a noun; adj-attrib |
    v-link ADJ: predicative; predic; after verb; not before noun; usually after verb; never before noun; pred; only after verb; always after a verb; adj-pred |
    n ADJ: postpositive; after noun; postpos; immediately after noun; usually after noun; placed after noun |
    ADV adj: as submodifier; submodifier |
    ~ sentence: sentence adverb; as sentence adverb |
    ~ inflects: v inflects; verb inflects; inflects |
    comparative: comparative; comp; compar |
    superlative: superlative; superl; sup |
    no comparative: no comparative; not gradable; ungradable; not comparable |
    absolute: absolute; absol; absolutely; with object understood |
    V n: withobject |
    N plural, pl verb: treated as pl; treated as plural |
    parenthetical: parenthetical; parenthetically |
    v-link ADJ: as predic. adj |
    imperative: only imper; only imperative |
    v-link ADJ: not usually before noun; not used before a noun; usually predicative; 一般作表语; 作表语 |
    with negative: with negative or in questions; usu. with negative or in questions; usually in negatives or questions;
        usually with negative or in questions; with negative; usu. with negative; often with negative; usually with negative; with brd-neg;
        usu with brd-neg; in negative; in negatives; with a negative; usu neg; in negative sentences |
    with modifier: with modifier; usu. with modifier; often with modifier; usually with modifier; with supp;
        usu with supp; oft with supp |
    with poss: with poss; oft with poss; usu with poss; usually with poss |
    imperative: in imperative; often in imperative; usu. in imperative; usually in imperative; imperative |
    V-link: linking verb; copular; copula; link verb |
    reporting verb: reporting verb |
    ~ complement: with complement; with obj. and complement or object complement |
    ~ adj: with adjective; with adj; + adjective |
    passive: passive; in passive |
    usu cont: usually cont; usu cont; usually continuous; usually progressive; often progressive |
    no cont: not used in progressive tenses; not used in the progressive |
    N plural, sing/pl verb: singular or plural verb; + singular or plural verb; used with a sing. or pl. verb; with singular or plural verb; c + sing./pl. v; + sing./pl. verb;
        + sing or pl verb; used with a singular or plural verb |
    N plural, pl verb: functioning as plural; treated as plural; used with a plural verb; + plural verb |
    V n P: tr, adverb; transitive, adverb; tr, adv |
    V P: intr, adverb; intransitive, adverb; intr, adv |
    V prep n: intr, preposition; intransitive, preposition; intr, prep |
    V n prep n: tr, preposition; transitive, preposition; tr, prep |
    as ADJ: as adjective; as adj; adjective use |
    as ADV: as adverb; as adv; adverb; adverb (or adjective) |
    as N: as noun; as n |
    as PRON: as pronoun; as pron |
    as DET: as determiner; as det |
    as INTJ: as exclamation; as interjection; as exclam |
    as PREP: as preposition; preposition; as prep |
    before vowel: before a vowel; before vowels; used before a vowel |
    before consonant: before a consonant; before consonants |
    no cont: never progressive; not continuous; never continuous; no progressive; not in progressive |
    only cont: only cont; only continuous; only progressive |
    no passive: never passive |
    ~ -ing: with present participle; + present participle |
    V that: with object and clause; may take a clause as object; when tr, may take a clause as object;
        with clause as object |
    N plural, pl verb: used with a pl. verb; with plural verb |
    N sing, sing/pl verb: sing. + sing./pl. v; sing + sing/pl verb |
    ~ sentence: sentence modifier |
    ~ complement: as complement |
    V n adv/prep: with obj. and adverbial of place; with object and adverbial of place |
    ~ adv/prep: no obj., with adverbial of place; no object, with adverbial of place |
    as AUX: verbal auxiliary; auxiliary; modal verb; modal auxiliary; auxiliary verb |
    as DET: determiner |
    as REL: relative; relative pronoun |
    impersonal: impersonal; impersonal verb |
    with modifier: with supplement; usually with supplement; usu with supplement |
    with negative: with neg; usually in negatives; usu with neg; often in negatives""", sep=";")

# COBUILD's own pattern strings: "V n", "usu ADJ n", "VERB noun", "V P n (not pron)", "be V-ed".
_COBUILD_TOKEN = re.compile(r"^(?:V|VERB|N|NOUN|ADJ|ADJECTIVE|ADV|ADVERB|PHR|P|PREP\.?|n|noun|adj|adv|pron|prep|"
                            r"prep\./adv\.|adv\./prep\.|that|to-inf|to-infinitive|-ing|V-ing|VERB-ing|V-ed|VERB-ed|"
                            r"wh|wh-|v-link|verb-link|it|there|so|not|with|of|about|as|for|on|in|to|by|from|into|"
                            r"at|than|like|after|before|be|pl-n|poss|amount|num|ord|colour|supp|cl|quote|inflects|"
                            r"pron-refl|n-proper|sing|pl|det|way|\(not|pron\)|pronoun\)|\(not\s+pron\)|P|and|or|"
                            r"prep/adv|adv/prep|after|before|the|a|supp|brd-neg|inflect|N-COUNT|between|"
                            r"towards|against|over|through|round|around|upon|onto|off|out|up|down|away|back|"
                            r"together|apart|v|n-count|ADJ-GRADED|ADV-GRADED|verb|adjective|group|cl/group|"
                            r"adj/adv|adjective/adverb|adj/adverb|adverb|no|det|pair|a pair of|n-plural)$")
_COBUILD_LONG = [("pronoun-reflexive", "pron-refl"), ("adj.ive", "adj"), ("adjective NOUN", "adj N"),
                 ("ADVERB adjective/adverb", "ADV adj/adv"), ("ADVERB adjective", "ADV adj"), ("VERB", "V"), ("NOUN", "N"), ("ADJECTIVE", "ADJ"), ("ADVERB", "ADV"), ("noun", "n"),
                 ("prep./adv.", "prep/adv"), ("adv./prep.", "adv/prep"), ("PREP.", "prep"), ("PREPOSITION", "prep"),
                 ("prep.", "prep"), ("adv.", "adv"), ("PHRASE", "PHR"),
                 ("to-infinitive", "to-inf"), ("pronoun", "pron"), ("verb-link", "v-link")]
_COBUILD_QUALIFIERS = re.compile(r"^(?:usu|usually|oft|often|also|mainly|always|sometimes)\.?\s+", re.I)


def _cobuild(label: str) -> tuple[Label, ...] | None:
    """A COBUILD grammar pattern, in either of its notations, as the short one."""
    text = _COBUILD_QUALIFIERS.sub("", label.strip()).replace(" + ", " ")
    for long, short in _COBUILD_LONG:
        text = re.sub(rf"(?<![\w-]){re.escape(long)}(?![\w])", short, text)
    words = text.replace("(not pron)", "(not-pron)").split()
    if not words or not any(w in ("V", "N", "ADJ", "ADV", "PHR", "v-link") or w.startswith(("V-", "V ")) for w in words):
        return None
    if not all(_COBUILD_TOKEN.match(w) or w == "(not-pron)" for w in words):
        return None
    return (Label("grammar", " ".join(words).replace("(not-pron)", "(not pron)")),)
