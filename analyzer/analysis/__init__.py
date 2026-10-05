"""Analysis of English text against the lexical inventories (see analyzer/README.md)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent    # the repository: shared inputs live there
INVENTORIES = ROOT / "inventories" / "data"             # what the analyzer is compiled from
DATA = ROOT / "analyzer" / "data"                       # analyzer.db; git-ignored (dictionary content)
MODEL = "en_core_web_sm"                                # spaCy's English model (pinned in requirements-dev.txt)
SLOTS = frozenset({"{obj}", "{poss}", "{oneself}", "{somewhere}", "{...}"})  # what a pattern may leave open
BASE = "~"  # marks a collocation's base word in a compiled pattern: "make a ~decision"

# Words of the closed classes: a pattern made only of these and slots ("in {obj}") would match
# almost any sentence, so it needs a word outside them to be matched at all.
FUNCTION_WORDS = frozenset("""
a an the this that these those my your his her its our their one's
i me you he him she it we us they them myself yourself himself herself itself ourselves yourselves themselves
oneself someone somebody something anyone anybody anything everyone everything no none
of to in into on onto at by for from with without about as than like over under up down out off
through across along around round after before between among against upon within
and or but nor so if because while though although whether
be am is are was were been being do does did done have has had having
can could may might must shall should will would 's n't not
""".split())


# A phrase made only of these is grammar, not a phrase worth marking in running text ("there are",
# "not be", "of all", "every other"): the closed classes and the commonest quantifiers and adverbs.
PLAIN_WORDS = FUNCTION_WORDS | frozenset("""
there here not how what who whom whose which when where why so too very all every each other another more most
less much many few little such own same just only even also then now well some any both either neither
""".split())
SUBJECTS = frozenset("i you he she we they".split())  # a phrase opening with one is a formula: "I see", "you must"


def load_nlp():
    """spaCy with what the analyzer uses: tagger, parser, lemmatizer (named entities left out)."""
    import spacy
    return spacy.load(MODEL, exclude=["ner"])
