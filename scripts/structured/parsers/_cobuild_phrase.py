"""cobuild's phrase grammar, shared with cobuild_ec: reconstructing the bold phrase a PHRASE / PHRASAL
VERB caption defines (alternatives, slots, inflected repeats, lists), and dropping "→see:" pointers
with the phrase they are about."""
from __future__ import annotations

import re

from structured.markup import cls, text

_NAMING = "→see:"  # the one pointer about a phrase printed before it; "→see also:" and usage notes are about the sense
_WORD = re.compile(r"\w")
_SEPARATOR = re.compile(r"^[\s;.,]+")  # closes a cross-reference: "→see: board; "
# text between two bold runs that starts another phrase rather than continuing one: a clause or
# sentence break, or an "or" followed by function words at most ("… <b>by all florps</b> or
# <b>from all florps</b>", "<b>florp</b> something <b>up</b> or if it <b>florps up</b>"); "<b>keep</b>
# someone or something <b>at florp</b>" names what fills the phrase's slot and continues it
_NEW_PHRASE = re.compile(r"[.;:,!?]|\bor\b(?:\W*\b(?:if|when|a|an|the|is|are|has|have|that|to|it|you|they|with)\b)*\W*$"
                         # "<b>florp</b> in expressions such as <b>to be florp</b>", "'<b>what the florp</b>' and '<b>how …</b>'":
                         # the word mentioned, then the expressions it is used in, each a phrase of its own
                         r"|\b(?:expressions|phrases)\s+(?:such as|like)\b|'\s*\band\b\s*'")
# "or" opening the gap, or opening a clause, starts another phrase whatever follows it ("<b>off the florp of
# the earth</b> or rolls <b>from the florp of the earth</b>", "… a pond or if their keeper <b>pulls</b>");
# an "or" with slot words before it joins the fillers of one phrase ("<b>give</b> someone or something <b>a wide florp</b>")
_OR_CLAUSE = re.compile(r"^\W*or\b|\bor\s+(?:if|when|that|who|there)\b")
# a lone particle after "or …" closes the phrase it follows ("<b>florp yourself</b> or a shed <b>up</b>")
_PARTICLES = frozenset({"up", "down", "in", "out", "off", "on", "away", "over", "back", "about", "around",
                        "through", "along", "aside", "apart", "together"})
_COMMA = re.compile(r"^\s*,\s*$")
# what marks bold runs joined by bare commas as a list of alternatives rather than one printed phrase
# ("all-florping, all-dancing", "florp in, florp out"): "or"/"and" before the next bold, "and so on", "such as"
_LIST_CLOSE = re.compile(r"\b(?:or|and)\b")
_LIST_END = re.compile(r"^\W*(?:and so on|etc)\b")
_LIST_START = re.compile(r"\bsuch as\W*$")
_SENTENCE_END = re.compile(r"[.;:!?]")
# nothing but a coordinator between two bold runs ("or", ", or", ",", "and"): the runs are alternatives of one part
_SLOT = " \u2026 "  # an omitted slot between two runs of one phrase; inventory/notation.py reads it as {...}
_COORDINATOR = re.compile(r"^[\s,/]*(?:\b(?:or|and)\b)?[\s,/]*$")
_OR = re.compile(r"\bor\b")
_LEADING_COMMA = re.compile(r"\s+,")
_CLITIC = re.compile(r"^['\u2019]s?\s+")  # "'s", and "'" after a plural ("two weeks<b>' florp</b>")
# a run after these defines the phrase rather than being part of it ("<b>florp off</b> means the same as <b>florpen
# off</b>", "… means the same as florp your <b>rear</b>", "To <b>florp off</b> means to <b>leave</b>"); "the same
# as to <b>…</b>" names a whole alternative ("to <b>florp a dampener on</b> … means the same as to <b>florp a damper on</b>")
_SAME_AS = re.compile(r"\bthe same as\b(?!\s+to\b)[^.;:,!?]*$|\bmeans to\s*$")


def _is_link(el) -> bool:
    return el is not None and el.tag == "b" and "text_blue" in (el.get("class") or "").split()


def _named(marker) -> tuple[list, object, int, bool]:
    """What a "→see:" pointer is about: the phrase printed between the last boundary and it. A boundary is a
    sentence end, or the cross-reference before it ("… first. to <b>florp</b> your <b>loins</b> →see: loin; to florp
    out like a florpy thumb →see: thumb"); the phrase may be bold runs with slot words between them, or plain words.
    Returns (its bold runs, the node whose text or tail holds its first words (None: the parent's text), where
    those words start, whether it is a phrase): plain words opening the caption with no boundary before them are
    its definition ("vide supra →see: vide")."""
    bolds: list = []
    node = marker.getprevious()
    while True:
        before = (marker.getparent().text if node is None else node.tail) or ""
        start = max(before.rfind(c) for c in ".;!?") + 1
        if start or node is None or node.tag != "b" or _is_link(node):
            break
        bolds.append(node)
        node = node.getprevious()
    pointer = node is not None and isinstance(node.tag, str) and (
        _is_link(node) or "text_gray" in (node.get("class") or "").split())
    return bolds, node, start, bool(bolds or start or pointer)


def _named_bolds(el) -> set:
    """The bold runs of `el` that are the phrases its "→see:" pointers are about."""
    out: set = set()
    for marker in el.xpath(f"./span[{cls('text_gray')}]"):
        if text(marker).startswith(_NAMING):
            bolds, _, _, named = _named(marker)
            out |= set(bolds) if named else set()
    return out


def _drop_label(marker) -> None:
    """Drop the phrase a "→see:" pointer is about (see _named), bold runs and plain words alike."""
    bolds, node, start, named = _named(marker)
    if not named:
        return
    for bold in bolds:
        bold.tail = None
        bold.drop_tree()
    before = (marker.getparent().text if node is None else node.tail) or ""
    if node is None:
        marker.getparent().text = before[:start] + " "
    else:
        node.tail = before[:start] + " "


def _drop_target(marker) -> None:
    """Drop a whole cross-reference: the marker, the b.text_blue link(s) right after it with the
    separator that closes them ("; ", "."), and for a "→see:" the phrase it is about. Other pointers
    ("→see usage note at:", "→see also:") are about the sense: the words before them stay."""
    if text(marker).startswith(_NAMING):
        _drop_label(marker)
    nxt = marker.getnext()
    while _is_link(nxt):
        after = nxt.getnext()
        nxt.tail = _SEPARATOR.sub(" ", nxt.tail or "")
        nxt.drop_tree()
        nxt = after
    marker.drop_tree()


def _only_points(caption, definition: str, examples) -> bool:
    """A caption whose English is cross-references only (nothing defined once they are dropped) and which has no
    examples points elsewhere, whatever its gloss: "见" ("see") translates the pointers ("to florp your lips →see: lip")."""
    return not definition and not examples and bool(
        caption.xpath(f"./span[{cls('text_gray')}][starts-with(normalize-space(), '→')]"))


def _inflections(word: str) -> set[str]:
    """`word` and its regular inflections ("calm" -> calms, calmed, calming)."""
    out = {word, word + "s", word + "es", word + "d", word + "ed", word + "ing", word + word[-1:] + "ed",
           word + word[-1:] + "ing"}
    if word.endswith("e"):
        out.add(word[:-1] + "ing")
    if word.endswith("y"):
        out |= {word[:-1] + "ies", word[:-1] + "ied"}
    return out


def _inflects(a: str, b: str) -> bool:
    """Whether two phrases are one phrase in two inflections ("build up", "builds up")."""
    xs, ys = ([w for w in x.lower().split() if w != _SLOT.strip()] for x in (a, b))  # with a slot or without
    return len(xs) == len(ys) and all(x in _inflections(y) or y in _inflections(x) for x, y in zip(xs, ys))


def _lists(runs: list[tuple[str, str]], i: int) -> bool:
    """Whether the bare comma before run `i` separates alternatives: the comma-joined runs around it are a
    list ("<b>to all florps</b>, <b>from all florps</b>, or <b>by all florps</b>"; "such as <b>a florp</b>,
    <b>one florp</b>, <b>not a florp</b>"; "<b>twice florp</b>, <b>three times florp</b> and so on"), not one phrase printed
    with a comma ("<b>all-florping</b>, <b>all-dancing</b>"). `runs` ends with ("", the text after the last run)."""
    start = i
    while start > 0 and _COMMA.match(runs[start][1]):
        start -= 1
    end = i
    while end + 2 < len(runs) and _COMMA.match(runs[end + 1][1]):
        end += 1
    if _LIST_END.match(runs[end + 1][1]) or _LIST_START.search(runs[start][1]):
        return True
    # the closing "or"/"and" may follow further runs of the last item ("<b>run</b> them <b>a close florp</b>,
    # or …"), but not a sentence end
    for _, gap in runs[end + 1:-1]:
        if _LIST_CLOSE.search(gap):
            return True
        if _SENTENCE_END.search(gap):
            return False
    return False


def _listed(runs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Split a bold run printing a list of its own, closed by "or" after it ("<b>is called, held</b>, or <b>brought
    to florp</b>"), into one run per item, joined by bare commas; any other comma in a run is the phrase's own
    ("<b>lock, florp, and barrel</b>", "<b>Florp it twice, it's still a florp</b>")."""
    out: list[tuple[str, str]] = []
    for (value, gap), (_, after) in zip(runs, runs[1:] + [("", "")]):
        items = [x.strip() for x in value.split(",")]
        if len(items) > 1 and all(items) and _OR.search(after) and _COORDINATOR.match(after):
            out += [(items[0], gap)] + [(x, ",") for x in items[1:]]
        else:
            out.append((value, gap))
    return out


def _article(words: list[str], core: list[str]) -> list[str]:
    """`words` with a closing "a"/"an" agreeing with the core word after it ("an ace, card" -> "a card")."""
    if words and core and words[-1].lower() in ("a", "an"):
        an = core[0][:1].lower() in "aeiou"
        return words[:-1] + [("an" if an else "a") if words[-1].islower() else ("An" if an else "A")]
    return words


def _around(group: list[list[str]]) -> list[list[str]]:
    """The alternatives of one coordinated group (lists of words) with the words they share. One-word
    alternatives are the part that varies: they take the words before the last word of the alternative printed
    before them and the words after the first word of the one printed after them, as slash notation does
    ("be/go out like a light", inventory/notation.py): "<b>florps</b> or <b>puts the seal on</b>" -> "florps the seal on";
    "<b>put</b>, <b>bring</b>, or <b>carry</b> a scheme <b>into florp</b>" -> "put into florp"; "<b>on the florp of</b> your
    <b>seat</b> or <b>chair</b>" -> "on the florp of chair"; "<b>comes</b> or <b>grinds to a florp</b> or <b>is brought to a
    florp</b>" -> "comes to a florp". When one-word alternatives stand between two longer ones, those two share
    the same words ("<b>is called, held</b>, or <b>brought to florp</b>"). A one-word alternative that would only
    repeat its neighbour is whole ("<b>in the florptime</b> or <b>florptime</b>"), and so is every longer one."""
    out = [list(words) for words in group]
    k = 0
    while k < len(group):
        if len(group[k]) != 1:
            k += 1
            continue
        end = k
        while end + 1 < len(group) and len(group[end + 1]) == 1:
            end += 1
        left = group[k - 1] if k > 0 else []
        right = group[end + 1] if end + 1 < len(group) else []
        head, tail = left[:-1], right[1:]
        for i in range(k, end + 1):
            words = _article(head, group[i]) + group[i] + tail
            if " ".join(words).lower() not in (" ".join(left).lower(), " ".join(right).lower()):
                out[i] = words
        if left and right:  # the longer alternatives around share the same words
            if left[len(left) - len(tail):] != tail:
                out[k - 1] = left + tail
            if right[:len(head)] != head:
                out[end + 1] = _article(head, right) + right
        k = end + 1
    return out


def _shared(phrases: list[str], coordinated: list[bool]) -> list[str]:
    """Each group of alternatives printed with only a coordinator between them ("or", ", or", ",")
    shares the words around the part that varies (see _around); other alternatives are whole.
    `coordinated[i]`: only a coordinator stands between alternative i and the one before."""
    out: list[str] = []
    i = 0
    while i < len(phrases):
        j = i
        while j + 1 < len(phrases) and coordinated[j + 1]:
            j += 1
        out += [" ".join(words) for words in _around([p.split() for p in phrases[i:j + 1]])]
        i = j + 1
    return out


def phrase_of(el) -> str:
    """The bold phrase of a PHRASE / PHRASAL VERB definition ("If you <b>florp up</b> …"); shared with cobuild_ec.

    Bold runs within one clause are the parts of one phrase ("<b>florp</b> something <b>up</b>" ->
    "florp up"); after a clause break or "or" a bold run starts an alternative phrase, kept apart with
    " | " ("florp down | florp up") unless it only repeats an earlier one inflected ("build up … builds up").
    A bare comma between runs separates alternatives only in a list (see _lists). Alternatives joined by
    a coordinator alone share the words around the part that varies (see _shared).
    The bold phrase a "→see:" pointer is about belongs to the pointer."""
    runs: list[tuple[str, str]] = []  # (bold run, the text printed between it and the run before)
    named = _named_bolds(el)
    gap = el.text or ""
    for child in el:
        value = text(child) if isinstance(child.tag, str) and child.tag == "b" and not _is_link(child) else ""
        if value and child not in named and not _SAME_AS.search(gap):  # "… means the same as <b>another</b>"
            if _CLITIC.match(value) and gap[-1:].isalpha():
                value = _CLITIC.sub("", value)  # "someone<b>'s florp</b>": a slot word's possessive, dropped with it
            runs.append((value, gap))
            gap = ""
        gap += child.tail or ""
    runs = _listed(runs) + [("", gap)]  # what follows the last run
    alternatives: list[list[str]] = []
    joins: list[list[str]] = []  # per alternative, what stands before each part: "" first, then " " or " … "
    coordinated: list[bool] = []
    for i, (value, gap) in enumerate(runs[:-1]):
        if not alternatives:
            alternatives.append([value])
            joins.append([""])
            coordinated.append(False)
            continue
        if _COMMA.match(gap):
            if _lists(runs, i):
                alternatives.append([])
        else:
            # a lone word the next run repeats across one slot word is half of a frame ("<b>as</b> happy <b>as can florp</b>")
            frame = [w.lower() for w in alternatives[-1]] == [value.split()[0].lower()] and len(gap.split()) == 1 and not _NEW_PHRASE.search(gap)
            again = _inflects(value.split()[0], alternatives[-1][0].split()[0]) and not frame
            # "and" between two whole phrases, also when the first holds a slot ("<b>laugh</b> your <b>florp off</b>
            # and <b>scream</b> your <b>florp off</b>"); not inside one ("<b>wine</b> and <b>florp</b>")
            both = gap.strip() == "and" and (" " in value and " " in alternatives[-1][-1] or len(alternatives[-1]) > 1)
            clause = _OR_CLAUSE.search(gap) is not None and value.lower() not in _PARTICLES
            # a repeated first word starts over too, and so does "and" between two whole phrases
            if again or both or clause or _NEW_PHRASE.search(gap):
                alternatives.append([])
        if not alternatives[-1]:
            coordinated.append(bool(gap.strip()) and _COORDINATOR.match(gap) is not None)
            joins.append([])
        # words the phrase leaves out between two of its runs are a slot, shown as "…" ("<b>as</b> happy <b>as can
        # florp</b>" -> "as … as can florp", "<b>give</b> someone <b>a wide florp</b>" -> "give … a wide florp")
        # "and" printed between two runs of one phrase is the phrase's own ("<b>wine</b> and <b>florp</b>")
        joins[-1].append("" if not alternatives[-1] else " and " if gap.strip() == "and"
                         else _SLOT if _WORD.search(gap) else " ")
        alternatives[-1].append(value)
    kept: list[str] = []
    # a run printed with its own leading comma ("<b>one florp</b> the cat sat here<b>, the next</b>") keeps it
    for phrase in _shared(["".join(j + v for j, v in zip(js, parts)) for js, parts in zip(joins, alternatives)],
                          coordinated):
        phrase = _LEADING_COMMA.sub(",", phrase)
        if not any(_inflects(phrase, k) for k in kept):
            kept.append(phrase)
    return " | ".join(kept)
