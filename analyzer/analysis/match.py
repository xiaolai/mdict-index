"""Find the inventories' phrases and collocations in parsed text.

A pattern is found from its anchor (its rarest literal) outwards in both directions. A literal
matches a token that may stand for it: the token itself, spaCy's lemma, or a lemma the
inventories give that form in the part of speech spaCy tagged. A slot matches a span the parse
supports:

  {obj}        1-6 tokens forming one subtree, headed by a noun, pronoun, number or gerund that is
               not itself a modifier ("his" in "his letters" is not an object)
  {poss}       a possessive determiner (my, their), or a possessive phrase ending in 's
  {oneself}    a reflexive pronoun
  {somewhere}  1-4 tokens forming one subtree (a place: there, at home, in the garden)
  {...}        0-4 tokens, no punctuation

Up to two modifiers the parse attaches to a literal word may come before it: "made little
headway" is "make headway", "with typical bad grace" is "with bad grace".

Every match must hang together in the dependency tree: the matched tokens, slots included,
form one connected piece of it, or, for words side by side, hang from one word between them
("early on", "now then": both words modify the verb). That keeps out words that merely sit
side by side: "in the main" is not the idiom in "in the main room".

A collocation with a typed relation (verb_obj, adj_noun ...) and one collocate is found through
the parse instead, so syntax may reorder it: "made a decision", "a difficult decision was made",
"the decision that she made". The others are matched as patterns.

A conversational formula, or any phrase that opens with a subject pronoun ("I see", "you
must"), is one only when it stands on its own: punctuation or the sentence's edge on both
sides. "I see." is the formula; "I see in him outrageous strength" is not.
"""
from __future__ import annotations

from dataclasses import dataclass

from analysis import BASE, PLAIN_WORDS, SUBJECTS
from analysis.lexicon import Item, Lexicon

SLOT_LENGTHS = {"{obj}": (1, 6), "{poss}": (1, 5), "{oneself}": (1, 1), "{somewhere}": (1, 4), "{...}": (0, 4)}
REFLEXIVES = frozenset("myself yourself himself herself itself ourselves yourselves themselves oneself".split())
NOMINAL = frozenset({"NOUN", "PROPN", "PRON", "NUM"})
OBJECT_DEPS = frozenset({"dobj", "obj", "nsubjpass", "attr"})
RELATIVES = frozenset("that which who whom whose".split())
VERBS = frozenset({"VERB", "AUX"})
MODIFIER_DEPS = frozenset({"amod", "advmod", "nummod", "compound", "npadvmod"})
NOT_HEADS = frozenset({"poss", "det", "amod", "compound", "nummod", "predet", "case"})  # they modify a noun
MAX_MODIFIERS = 2


@dataclass(frozen=True)
class Tok:
    i: int                     # index in the sentence
    text: str
    lower: str
    start: int                 # character offsets in the analysed text
    end: int
    pos: str
    tag: str
    dep: str
    head: int                  # index in the sentence (itself for the root)
    lemma: str                 # the one chosen for this token
    lemmas: frozenset[str]     # what it may stand for in a pattern
    punct: bool


def confidence(item: Item, variant: tuple[str, ...], literals: tuple[int, ...], sent: list["Tok"]) -> str:
    """"likely" or "possible": how far the words alone vouch for the phrase.

    A phrasal verb is likely when the parse calls its particle a particle ("gave it up"); with a
    preposition and its object it may be literal ("standing in his boat" is not "stand in"). Any
    other phrase is likely with two content words or three words in all; one content word among
    function words ("end of", "of use") is often just those words."""
    words = [t for t in variant if t not in SLOT_LENGTHS]
    content = [t for t in words if t.lstrip(BASE) not in PLAIN_WORDS]
    if item.source == "collocation":
        return "likely"
    if item.kind == "phrasal_verb":
        return "likely" if len(content) >= 2 or any(sent[i].dep == "prt" for i in literals) else "possible"
    return "likely" if len(content) >= 2 or len(words) >= 3 else "possible"


@dataclass(frozen=True)
class Match:
    item: Item
    tokens: tuple[int, ...]    # sentence indices of every matched token, slots included
    literals: tuple[int, ...]  # the indices of the literal words only
    variant: tuple[str, ...]   # the pattern that matched: an item printed "switch sth on/off" matches as either


def _subtree_root(span: list[Tok]) -> Tok | None:
    """The one token of span whose head lies outside it, if the span is a single subtree."""
    inside = {t.i for t in span}
    roots = [t for t in span if t.head not in inside or t.head == t.i]
    return roots[0] if len(roots) == 1 else None


def slot_fits(slot: str, span: list[Tok]) -> bool:
    if slot == "{...}":
        return not any(t.punct for t in span)
    if not span or any(t.punct and t.tag != "POS" for t in span):
        return False
    if slot == "{oneself}":
        return span[0].lower in REFLEXIVES
    if slot == "{poss}":
        if len(span) == 1:
            return span[0].tag == "PRP$"
        return span[-1].tag == "POS" and _subtree_root(span[:-1]) is not None
    root = _subtree_root(span)
    if root is None:
        return False
    if slot == "{obj}":
        return (root.pos in NOMINAL or root.tag == "VBG") and root.dep not in NOT_HEADS
    return True  # {somewhere}


def _literal(token: str) -> str:
    return token[1:] if token.startswith(BASE) and len(token) > 1 else token


def _modifiers(sent: list[Tok], first: int, last: int, bound: int | None) -> bool:
    """Whether sent[first:last] are modifiers of a word at or after bound (the literal beside them,
    or the noun it leads to: "typical" in "with typical bad grace" modifies "grace"). The match's
    connectivity check then requires that word to be part of the match."""
    return bound is not None and all(sent[i].dep in MODIFIER_DEPS and sent[i].head >= bound and sent[i].head > i
                                     for i in range(first, last))


def _align(pattern: tuple[str, ...], k: int, sent: list[Tok], pos: int, step: int,
           prev: int | None = None) -> list[tuple[int | None, int, int]] | None:
    """Match pattern[k], pattern[k+step], ... against the sentence from token pos, moving by step
    (1: rightwards, -1: leftwards); prev is the literal just matched, if the last match was one.
    Each (pattern index, first, last+1) of the alignment; skipped modifiers have index None."""
    if k < 0 or k >= len(pattern):
        return []
    tok = pattern[k]
    if tok in SLOT_LENGTHS:
        low, high = SLOT_LENGTHS[tok]
        for length in range(low, high + 1):
            first, last = (pos, pos + length) if step > 0 else (pos - length + 1, pos + 1)
            if first < 0 or last > len(sent):
                break
            if slot_fits(tok, sent[first:last]):
                rest = _align(pattern, k + step, sent, pos + step * length, step)
                if rest is not None:
                    return [(k, first, last), *rest]
        return None
    for skip in range(MAX_MODIFIERS + 1):
        at = pos + step * skip
        if not 0 <= at < len(sent):
            break
        if skip:  # modifiers before a word attach to it; leftwards, to the literal matched before
            first, last = (pos, at) if step > 0 else (at + 1, pos + 1)
            if not _modifiers(sent, first, last, at if step > 0 else prev):
                continue
        if _literal(tok) in sent[at].lemmas:
            rest = _align(pattern, k + step, sent, at + step, step, at)
            if rest is not None:
                gap = [(None, *((pos, at) if step > 0 else (at + 1, pos + 1)))] if skip else []
                return [*gap, (k, at, at + 1), *rest]
    return None


def connected(indices: set[int], sent: list[Tok]) -> bool:
    """Whether these tokens form one connected piece of the dependency tree; or, when they are
    contiguous, pieces that all hang from one word outside them (siblings)."""
    parent = {i: i for i in indices}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in indices:
        h = sent[i].head
        if h in indices and h != i:
            parent[find(i)] = find(h)
    if len({find(i) for i in indices}) == 1:
        return True
    contiguous = max(indices) - min(indices) + 1 == len(indices)
    outside = {sent[i].head for i in indices if sent[i].head not in indices}
    return contiguous and len(outside) == 1


def standalone(tokens: set[int], sent: list[Tok]) -> bool:
    """Whether the tokens are bounded on both sides by punctuation or the sentence's edges."""
    before, after = min(tokens) - 1, max(tokens) + 1
    return (before < 0 or sent[before].punct) and (after >= len(sent) or sent[after].punct)


def needs_standalone(item: Item, pattern: tuple[str, ...]) -> bool:
    return item.kind == "formula" or (bool(pattern) and pattern[0] in SUBJECTS)


def match_patterns(sent: list[Tok], lex: Lexicon) -> list[Match]:
    found: dict[tuple[int, tuple[int, ...]], Match] = {}
    present = frozenset().union(*(t.lemmas for t in sent))  # every word the sentence may stand for
    for j, t in enumerate(sent):
        if t.punct:
            continue
        for key in t.lemmas:
            for p in lex.by_anchor.get(key, ()):
                if not p.words <= present:
                    continue  # one of its words is nowhere in the sentence
                for a, tok in enumerate(p.tokens):
                    if tok in SLOT_LENGTHS or _literal(tok) != key:
                        continue
                    right = _align(p.tokens, a + 1, sent, j + 1, 1, j)
                    left = _align(p.tokens, a - 1, sent, j - 1, -1, j) if right is not None else None
                    if left is None or right is None:
                        continue
                    parts = [*left, (a, j, j + 1), *right]
                    tokens = {i for _, f, l in parts for i in range(f, l)}
                    literals = {f for k, f, _ in parts if k is not None and p.tokens[k] not in SLOT_LENGTHS}
                    if not connected(tokens, sent):
                        continue
                    if needs_standalone(p.item, p.tokens) and not standalone(tokens, sent):
                        continue
                    if p.item.kind == "phrasal_verb" and sent[min(literals)].pos not in VERBS:
                        continue  # "a few turns on the deck": a noun is no phrasal verb's verb
                    m = Match(p.item, tuple(sorted(tokens)), tuple(sorted(literals)), p.tokens)
                    found.setdefault((p.item.id, m.literals), m)
    return list(found.values())


def _gap(sent: list[Tok], verb: Tok, role: str) -> bool:
    """Whether the noun a relative clause hangs from can fill this role ("object" or "subject") of
    its verb. Labels on the relative pronoun alone mislead (a parse may call "that" the subject of
    "the decision that the court made"), so the test is whether the role is still open:

      object   the pronoun is its object (or a passive's subject: "the decision that was made");
               or, failing that, no other word is its object and another word is its subject
      subject  no other word is the verb's subject ("a method that employs a pigment")
    """
    children = [t for t in sent if t.head == verb.i and t.i != verb.i]
    pronouns = [t for t in children if t.lower in RELATIVES]
    others = [t for t in children if t.lower not in RELATIVES]
    subject = any(t.dep in ("nsubj", "nsubjpass") for t in others)
    if role == "subject":
        return not subject
    if any(t.dep in ("dobj", "obj", "nsubjpass") for t in pronouns):
        return True
    return subject and not any(t.dep in ("dobj", "obj") for t in others)


def _relation_holds(relation: str, b: Tok, c: Tok, sent: list[Tok]) -> bool:
    """Whether base b and collocate c stand in the relation, by the parse. A noun a relative clause
    hangs from fills the role its verb leaves open: "the decision that she made" (object: made has
    none of its own), but not "a method that employs a pigment" (the object is the pigment)."""
    relative = c.head == b.i and c.dep in ("relcl", "acl")
    if relation == "verb_obj":
        return c.pos in ("VERB", "AUX") and (
            (b.head == c.i and b.dep in OBJECT_DEPS) or (relative and _gap(sent, c, "object")))
    if relation == "subj_verb":
        return (b.head == c.i and b.dep == "nsubj") or (relative and _gap(sent, c, "subject"))
    if relation == "adj_noun":
        return (c.head == b.i and c.dep == "amod") or (
            c.dep in ("acomp", "attr") and b.dep == "nsubj" and c.head == b.head)
    if relation == "noun_noun":
        return (c.head == b.i and c.dep == "compound") or (b.head == c.i and b.dep == "compound")
    if relation in ("adv_verb", "adv_adj"):
        return c.head == b.i and c.dep == "advmod"
    if relation == "verb_adj":
        return c.head == b.i and c.dep in ("acomp", "oprd", "xcomp")
    if relation == "verb_prep":
        return c.head == b.i and c.dep in ("prep", "prt", "agent", "dative")
    if relation == "prep":
        return b.head == c.i and b.dep == "pobj"
    return False


def match_collocations(sent: list[Tok], lex: Lexicon) -> list[Match]:
    """The typed collocations of single collocates, found through the parse."""
    found: dict[tuple[int, tuple[int, ...]], Match] = {}
    for b in sent:
        for key in b.lemmas:
            for item, collocate in lex.by_base.get(key, ()):
                for c in sent:
                    if c.i != b.i and collocate in c.lemmas and _relation_holds(item.relation, b, c, sent):
                        literals = tuple(sorted((b.i, c.i)))
                        variant = (collocate, BASE + key) if c.i < b.i else (BASE + key, collocate)
                        found.setdefault((item.id, literals), Match(item, literals, literals, variant))
    return list(found.values())


def resolve(matches: list[Match]) -> list[Match]:
    """Phrases: a phrase whose words all belong to a longer one goes ("make up" inside "make up
    one's mind"); of phrases on the same words, the tighter match (fewer words between them) and
    then the better attested stays. Phrases that merely cross are both kept: which one the writer
    meant is not the matcher's to know ("I can take it back": "take back", and "sb can take it").
    Collocations are kept beside phrases, one per item and set of words."""
    def key(m: Match):
        return (-len(m.literals), len(m.tokens) - len(m.literals), -m.item.n, -m.item.publishers, m.item.id)
    kept: list[Match] = []
    for m in sorted((m for m in matches if m.item.source == "phrase"), key=key):
        if not any(set(m.literals) <= set(k.literals) for k in kept):
            kept.append(m)
    kept += [m for m in matches if m.item.source == "collocation"]
    return kept
