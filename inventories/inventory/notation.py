"""The dictionaries' phrase notation, read into variants of words and slots.

    be/go out like a light          word alternatives            be | go
    as easy as anything/as pie      alternatives replacing a tail  as easy as pie
    give (somebody) the OK/get the OK  whole alternatives, optional parts
    to jack sth up or to jack up sth   whole alternatives (NCECD), a leading "to"
    take a ~ at                     the headword                 take a look at
    how/what about…?                an open slot                 how about {...}

Placeholders become typed slots: {sb}, {sth}, {sb/sth}, {sb's}, {one's} (your, one's, his/her),
{oneself} (yourself, oneself), {somewhere}, {...}. Words are lowercased. A phrase whose object
slot stands between its verb and a particle (put sth off) is separable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import islice, product

MAX_VARIANTS = 32
PARTICLES = frozenset("up down in out on off away back over through around round about along by forward "
                      "forwards apart aside together across ahead behind under".split())
OBJECT_SLOTS = frozenset({"{sb}", "{sth}", "{sb/sth}"})

_PERSON_POSSESSIVE = re.compile(r"\b(?:his|her|your|one's|my)\b")
_SLOT_PAIRS = [  # before slashes are read: a pair of placeholders is one slot
    (r"\b(?:somebody|someone|sb\.?)\s*/\s*(?:something|sth\.?|thing)(?=\W|$)", "{sb/sth}"),
    (r"\b(?:something|sth\.?)\s*/\s*(?:somebody|someone|sb\.?)(?=\W|$)", "{sb/sth}"),
    (r"\b(?:his|her|its|their|your|one's|my)(?:\s*/\s*(?:his|her|its|their|your|one's|my))+\b",
     lambda m: "{one's}" if _PERSON_POSSESSIVE.search(m.group(0)) else m.group(0)),  # its/their: a thing's, kept
    (r"\b(?:somebody|someone|sb)'s\s*/\s*(?:your|one's|his|her)\b", "{sb's}"),  # enter somebody's/your name
    (r"\b(?:your|one's|his|her)\s*/\s*(?:somebody|someone|sb)'s(?=\W|$)", "{sb's}"),
    (r"\b(?:him|her|them)self(?:\s*/\s*(?:him|her|them|your|one)sel(?:f|ves))+\b", "{oneself}"),
]
_SLOT_WORDS = {
    "somebody": "{sb}", "someone": "{sb}", "sb": "{sb}", "sb.": "{sb}", "sb's": "{sb's}", "sb.'s": "{sb's}",
    "somebody's": "{sb's}", "someone's": "{sb's}", "something": "{sth}", "sth": "{sth}", "sth.": "{sth}",
    "something's": "{sth's}", "sth's": "{sth's}", "somewhere": "{somewhere}", "one's": "{one's}",
    "your": "{one's}", "oneself": "{oneself}", "yourself": "{oneself}", "yourselves": "{oneself}",
}
_ELLIPSIS = re.compile(r"\s*(?:…|\.\.\.)\s*")
_APPARATUS = re.compile(r"\(\s*etc\.?\s*\)|\s*\betc\.?(?=[\s)]|$)|[?!.,;:\uff1f\uff01\u3002\uff0c\uff1b\uff1a]+$", re.I)
_ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\ufeff]")
_LABEL = re.compile("\u3008[^\u3009]*\u3009")               # odecn/yhdcd usage labels in angle brackets
_WHOLE_OR = re.compile(r"\s+or\s+(?=to\s)|\s+\|\s+", re.I)  # NCECD "to x or to y"; OALD "x | y"
_OR_GROUP = re.compile("\\(\\s*(?:or\\s+|also\\s+|\u6216\\s*)([^()]*)\\)")  # "(or rest)", "(also X)", Chinese "or"
_INNER_OR = re.compile("\\(([^()]*?)\\s*\u6216\\s*([^()]*)\\)")  # "(about it or that)": the end of an optional part
_BRACKET_LABEL = re.compile("\u3014[^\u3015]*\u3015")  # odecn subject labels
_NOTE = re.compile("\\((?!\\s*(?:or|also)\\b)(?![^()]*\u6216)[^()]*[\u3400-\u9fff][^()]*\\)")  # a note in Chinese
_LEFTOVER = re.compile(r"[()\[\]<>|=~]|[\u3400-\u9fff]")
_OPTIONAL = re.compile(r"\(([^()]*)\)")
# NCECD's infinitive "to": dropped before a verb, kept before a noun phrase ("to (the best of) my knowledge",
# "to somebody's face": a placeholder is never a verb)
_LEADING_TO = re.compile(r"^to\s+(?![(]|(?:the|a|an|my|your|his|her|its|our|their|this|that|one's|{|"
                         r"somebody|someone|something|sb|sth)\b)(?=\S)")
_POSSESSIVE_SLOT = re.compile(r"\((one's|someone's|somebody's|sb's|sb\.'s)\)")
_PAREN_SLASH = re.compile(r"([\w'{}]+ \([^()]*\))/([\w'{}]+)")  # "get (yourself)/be in a stew"


@dataclass
class Phrase:
    variants: list[tuple[str, ...]] = field(default_factory=list)
    separable: bool = False


_THEN = frozenset("to with for from at into as".split())


def _separable(v: tuple[str, ...]) -> bool:
    """An object between the verb and a particle that ends the phrase or opens a further
    prepositional phrase (put {sth} off; let {sb} off with {sth}); not a preposition with its
    own object (keep {sb} on {one's} toes, do {sth} about {sth}, preserve {sth} in aspic)."""
    return len(v) >= 3 and v[1] in OBJECT_SLOTS and v[2] in PARTICLES and (len(v) == 3 or v[3] in _THEN)


def _optional(text: str) -> list[str]:
    """Every combination of including and leaving out the parenthesised parts."""
    parts = _OPTIONAL.split(text)  # text, optional, text, optional, ...
    choices = [[p] if i % 2 == 0 else ["", p] for i, p in enumerate(parts)]
    return [" ".join("".join(c).split()) for c in islice(product(*choices), MAX_VARIANTS)]


def _inner_or(text: str) -> list[str]:
    """"(about it 或 that)": an optional part whose end has alternatives -> "(about it)", "(about that)"."""
    m = _INNER_OR.search(text)
    if not m:
        return [text]
    first, alt = m.group(1).split(), m.group(2).split()
    options = [first] + ([first[:len(first) - len(alt)] + alt] if 0 < len(alt) <= len(first) else [])
    return [t for o in options for t in _inner_or(text[:m.start()] + "(" + " ".join(o) + ")" + text[m.end():])]


def _paren_slash(text: str) -> list[str]:
    """"get (yourself)/be in a stew": the alternative replaces the word with its optional part."""
    m = _PAREN_SLASH.search(text)
    if not m:
        return [text]
    return [t for alt in m.groups() for t in _paren_slash(text[:m.start()] + alt + text[m.end():])]


def _or_groups(text: str) -> list[str]:
    """"(or X)": X replaces as many words before it as X has (let it drop (or rest) -> let it
    rest; have a monkey on a house (or up the chimney) -> have a monkey up the chimney)."""
    m = _OR_GROUP.search(text)
    if not m:
        return [text]
    before, after = text[:m.start()].rstrip(), text[m.end():]
    words = before.split()
    out = [before + after]
    for alt in re.split("\\s*(?:\u6216|\\bor\\b|,)\\s*", m.group(1)):
        alt_words = alt.replace("etc.", "").split()
        if alt_words and len(alt_words) <= len(words):
            out.append(" ".join(words[:len(words) - len(alt_words)] + alt_words) + after)
        elif alt_words:  # longer than what precedes it: a whole alternative (do... justice (or do justice to...))
            out.append(" ".join(alt_words) + after)
    return list(islice((t for o in out for t in _or_groups(o)), MAX_VARIANTS))


_REPLACING = frozenset("to in into on onto at by for from with of out off up down".split())
_DETERMINERS = frozenset("the a an my your his her its our their one's this that these those".split())
_UNIT_END = PARTICLES | _REPLACING | frozenset(
    "at about with for upon above against past near round around along through over under toward towards across "
    "behind beyond within without onto into from before after like as between among beneath below inside outside "
    "amid throughout".split())
_ADVERB_PARTICLES = frozenset("up down out away back apart aside together forward forwards ahead".split())
_OBJECT_WORDS = frozenset({"somebody", "someone", "sb", "sb.", "something", "sth", "sth."})
_PARTICLE_END = PARTICLES | _REPLACING | frozenset("at about with for upon into onto through over around round like".split())
_ETC_LIST = re.compile(r"\b([\w']+(?:,\s*[\w']+)+),?\s*etc\.?")  # OALD: "come, turn, etc. full circle"


_NOT_VERBS = frozenset("it's that's there's what's it this that there what who how i you we they he she".split())


def _verb_units(words: list[list[str]]) -> bool:
    """Every alternative but the last is a verb or a verb and its particle, one of them with a
    particle; no later alternative starts with a particle, preposition or determiner; and the
    units start with a verb, not "it's" (it's about/high time)."""
    return len(words) >= 2 and all(words) and not any(w[0] in _NOT_VERBS for w in words[:-1]) \
        and any(len(w) == 2 and w[-1] in _UNIT_END for w in words[:-1]) \
        and all(len(w) == 1 or len(w) == 2 and w[-1] in _UNIT_END for w in words[:-1]) \
        and not any(w[0] in _UNIT_END or w[0] in _DETERMINERS or w[0] in ("and", "or", "but") for w in words[1:]) \
        and len(words[-1]) >= 2


def _slashes(text: str) -> list[str]:
    """Read the slashes of one phrase: the first reading the rules allow (see _slash_readings)."""
    return _slash_readings(text)[0]


def _slash_readings(text: str) -> list[list[str]]:
    """Every reading of a phrase's slashes the rules allow, the most likely first; a caller
    with evidence (inventory/evidence.py) chooses among them."""
    if "/" not in text:
        return [[text]]
    segments = [s.strip() for s in text.split("/")]
    words = [s.split() for s in segments]
    readings: list[list[str]] = []
    if len(words) >= 2 and all(len(w) >= 2 for w in words):
        # alternatives sharing a middle, the last carrying the tail: "get up/build up/work up a head of steam"
        mid = words[0][1:]
        if all(w[1:] == mid for w in words[:-1]) and words[-1][1:1 + len(mid)] == mid and len(words[-1]) > len(mid) + 1:
            tail = words[-1][1 + len(mid):]
            readings.append([" ".join([w[0]] + mid + tail) for w in words])
    if _verb_units(words):
        # alternative verbs, some phrasal: "draw up/devise a plan", "reach/come to/arrive at a decision"
        last = words[-1]
        if last[0] == words[0][0]:  # "crammed with/crammed full of something": whole alternatives
            readings.append(segments)
        else:
            # the last alternative keeps its preposition when another ends in one: "come to/arrive at a
            # decision"; not when the others end in adverbs: "come back/return from the dead"
            prepositional = any(len(w) == 2 and w[-1] not in _ADVERB_PARTICLES for w in words[:-1])
            n = 2 if prepositional and last[1] in _PARTICLE_END else 1
            particle = words[0][-1] if len(words[0]) == 2 else ""
            if n < len(last) and (last[n] in _OBJECT_WORDS or last[n].startswith("{")) and particle in last[n + 1:]:
                # "go through/put someone through the wringer": the tail follows the particle
                n = last.index(particle, n + 1) + 1
            readings.append([" ".join(w + last[n:]) for w in words[:-1]] + [" ".join(last)])
    if len(words) == 2 and len(words[1]) > 1 and words[1][0] in _DETERMINERS and len(words[0]) >= len(words[1]) \
            and words[0][-len(words[1])] in _DETERMINERS:
        # "crack a book/the books": a phrase from a determiner on replaces as many words
        readings.append([segments[0], " ".join(words[0][:len(words[0]) - len(words[1])] + words[1])])
    if all(words) and all(len(w) > 1 for w in words[1:]):
        first, later = words[0], words[1:]
        # alternatives replacing a tail: "as easy as anything/as pie/as ABC",
        # "come close to something/to doing something"
        if all(w[0] in first[:-1] for w in later):
            out = [segments[0]]
            for w in later:
                cut = len(first) - 1 - first[::-1].index(w[0])
                out.append(" ".join(first[:cut] + w))
            readings.append(out)
        # a shorter alternative ending like the first replaces its tail: "be well on the way to
        # sth/doing sth" -> "... to doing sth"
        if len(later) == 1 and later[0][-1] == first[-1] and len(later[0]) < len(first) - 1:
            shared = len(_common_suffix(first, later[0]))
            readings.append([segments[0], " ".join(first[:len(first) - shared] + later[0])])
        # whole alternatives, one ending like the first: "give the OK/get the OK", "God/oh my God"
        elif any(w[-1] == first[-1] for w in later):
            readings.append(segments)
        # alternatives to the last word: "rip sb/sth apart/to shreds/to bits", "fall apart/to pieces";
        # a single alternative starting with a content word is a chain ("half as big/much as")
        shared_object = first[-1] in _REPLACING and len(later) == 1 and later[0][0] in _REPLACING and len(later[0]) > 1
        if len(first) > 1 and (len(later) > 1 or later[0][0] in _REPLACING) and not shared_object:
            readings.append([" ".join(first[:-1] + w) for w in [first[-1:]] + later])
    readings.append(_word_chain(text))  # the rules' last resort: word alternatives
    # readings the rules never chose before, for evidence to weigh:
    if len(words) >= 2 and all(1 <= len(w) <= 2 for w in words[:-1]) and len(words[-1]) >= 2:
        # unit alternatives sharing the last one's tail: "give sb/get the push", "in/out of shape",
        # "ahead of/behind the game"
        for n in (1, 2):
            if n < len(words[-1]) and (n == 1 or words[-1][1] == "of"):  # "out of shape"
                readings.append([" ".join(w + words[-1][n:]) for w in words[:-1]] + [segments[-1]])
    if all(len(w) >= 2 for w in words):
        readings.append(segments)  # whole alternatives: "how are things/how's it going/how are you doing"
    return list({tuple(r): r for r in readings if r}.values())


def _common_suffix(a: list[str], b: list[str]) -> list[str]:
    n = 0
    while n < min(len(a), len(b)) and a[-1 - n] == b[-1 - n]:
        n += 1
    return a[len(a) - n:]


def _word_chain(text: str) -> list[str]:
    """Word alternatives, possibly a chain: "half as big/much/good as", "be/go out like a light"."""
    head, tail = text.split("/", 1)
    before, _, left = head.rpartition(" ")
    alternatives = [left]
    rest = tail
    while True:
        word, _, after = rest.partition(" ")
        if "/" in word:
            options = word.split("/")
            alternatives += options[:-1]
            rest = options[-1] + (" " + after if after else "")
            continue
        alternatives.append(word)
        rest = after
        break
    out = []
    for alt in alternatives:
        out += _slashes(" ".join(x for x in (before, alt, rest) if x))
    return out


_PROTECTED = "{sb/sth}"
_STAND_IN = "{sb\x00sth}"  # the slot's own slash must not be read as an alternative


def _tokens(text: str) -> tuple[str, ...]:
    words = (w if w.startswith("{") else w.strip(",;:!?") for w in text.split())
    return tuple(_SLOT_WORDS.get(w, w).replace(_STAND_IN, _PROTECTED) for w in words if w)


def _score(variants: list[str], evidence) -> tuple[float, int]:
    """How well the examples attest a reading: the share of its variants attested (a variant
    too short to look up counts against it: a lone "verse" is a fragment, not a reading), then
    how many words the attested ones cover."""
    if not variants:
        return (0.0, 0)
    found = [(evidence.attested(_tokens(v)), len(v.split())) for v in variants]
    return (sum(1 for a, _ in found if a) / len(found), sum(n for a, n in found if a))


def _choose(readings: list[list[str]], evidence) -> list[str]:
    """The rules' reading, unless the examples fail to attest one of its variants and attest
    every variant of another reading. A reading with a fragment of the rules' reading ("bad as
    {sb/sth}" beside "every bit as bad as {sb/sth}") is never chosen: fragments of real phrases
    are attested too."""
    default = readings[0]
    if evidence is None or len(readings) == 1 or _score(default, evidence)[0] == 1.0:
        return default
    whole = [f" {v} " for v in default if evidence.attested(_tokens(v))]  # a garbled default protects nothing
    for reading in sorted(readings[1:], key=lambda r: -_score(r, evidence)[1]):
        fragment = any(f" {v} " in w and f" {v} " != w for v in reading for w in whole)
        if not fragment and _score(reading, evidence)[0] == 1.0:
            return reading
    return default


def _expand(wholes: list[str], evidence) -> list[str]:
    """The variant strings of whole alternatives: optional parts, "or" groups, slashes."""
    out: list[str] = []
    for whole in wholes:
        whole = _LEADING_TO.sub("", whole.strip())
        if whole.count("(") != whole.count(")") or not re.search("[a-z]", whole):
            continue  # a broken string: "(get", "<"
        for optional in (o for w in _paren_slash(whole) for g in _or_groups(w) for i in _inner_or(g)
                         for o in _optional(i)):
            out += [v for v in _choose(_slash_readings(optional), evidence) if v not in out]
    return out


def parse(printed: str, headword: str = "", evidence=None) -> Phrase:
    """The variants of a printed phrase, and whether it is a separable phrasal verb. With
    evidence (inventory/evidence.py), an ambiguous notation is read the way the examples attest."""
    text = _ZERO_WIDTH.sub("", printed.replace("~", headword)).strip().lower()
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    forms = [f.strip() for f in headword.lower().split(",")]
    if len(forms) >= 2 and all(forms) and ", ".join(forms) in text:  # yhdcd: "hit the bull's-eye, bullseye"
        text = text.replace(", ".join(forms), "/".join(forms))
    separable_mark = "\u2194" in text  # LDOCE marks separable phrasal verbs: use something <-> up
    text = _LABEL.sub("", text.replace("\u2194", " ")).replace("\uff08", "(").replace("\uff09", ")")
    text = _NOTE.sub("", _BRACKET_LABEL.sub("", text))
    text = _POSSESSIVE_SLOT.sub(r"\1", text)  # AHD "work (one's) fingers": a slot, not an optional word
    text = _ETC_LIST.sub(lambda m: "/".join(w.strip() for w in m.group(1).split(",")), text)
    text = _ELLIPSIS.sub(" {...} ", text)
    text = _APPARATUS.sub("", text).strip()
    text = re.sub(r"(?<=\w)\s+/\s+(?=\w)", "/", text)  # "be / go out like a light"
    for pattern, slot in _SLOT_PAIRS:
        text = re.sub(pattern, slot, text)
    text = text.replace(_PROTECTED, _STAND_IN)
    variants: list[tuple[str, ...]] = []
    for piece in _WHOLE_OR.split(text):
        sides = piece.split(" or ")  # "a rap on the knuckles or a rap over the knuckles"; not "sink or swim"
        readings = [_expand([piece], evidence)]
        a, b = (side.split() for side in sides) if len(sides) == 2 else ([], [])
        if len(sides) == 2 and len(a) >= 3 and len(b) >= 3 and (a[0] == b[0] or a[-1] == b[-1] or set(a) == set(b)):  # off and on or on and off
            # which comes first, the rules' guess or the phrase whole ("there's no rhyme or reason")
            readings.insert(0, _expand(sides, evidence))
        for variant in _choose(readings, evidence):
            tokens = _tokens(variant)
            if tokens and tokens not in variants and not _LEFTOVER.search(" ".join(tokens).replace(_PROTECTED, "")):
                variants.append(tokens)
    variants = variants[:MAX_VARIANTS]
    separable = separable_mark or any(_separable(v) for v in variants)
    return Phrase(variants, separable)
