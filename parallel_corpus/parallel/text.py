"""Find English example sentences and their Chinese translations in dictionary markup.

Shared by the probe (which counts them in sampled blocks) and the generic extractor (which
takes them from every record), so both apply the same rules.

The markup is reduced to a stream of text in which element boundaries are newlines, and
the stream is scanned as alternating Latin and Chinese runs: an English sentence directly
followed by a Chinese sentence is a candidate pair. This works whether the translation sits
in the same element, the next paragraph, or after a <br>, and it is linear in the text (a
single regular expression for "English then Chinese" backtracked for minutes on long blocks).

Only sentences are taken (4+ words ending in . ? !): in an unknown layout a phrase followed
by Chinese is indistinguishable from a headword and its gloss. Phrase examples come from the
parsed dictionaries, whose structure says which is which.
"""
from __future__ import annotations

import html
import math
import re

from parallel.corpus import is_chinese, is_english
from parallel.markup import RAW, TEXT, tokens

_CJK = re.compile(r"[㐀-鿿]")
# Tags (read by parallel/markup.py) and the `N` style markers of MDict "Compact" files. Block
# elements, line breaks, style markers and bullets are boundaries. Inline HTML adds nothing, as in a browser, so a
# highlighted ending stays in its word ("wean<b>ed</b>"). A dictionary's own tags (<chn>, <ebi>)
# may be inline or block: they become a possible cut (CUT), taken only where a sentence starts
# after it, so "<colloc>glow with</colloc> <ex>Maria's face...</ex>" is cut but
# "He <ebi>blurted out</ebi> the answer" is not.
_STYLE_MARKER = re.compile(r"`\d+`")
_INLINE = frozenset("""a abbr b bdi bdo big cite code del dfn em font i img ins kbd mark nobr q rp rt ruby s samp
small span strike strong sub sup tt u var wbr""".split())
_BLOCKS = frozenset("""address article aside blockquote body br caption center dd details div dl dt fieldset
figcaption figure footer form h1 h2 h3 h4 h5 h6 head header hr html li main nav ol p pre section summary table
tbody td tfoot th thead title tr ul""".split())
# Runs of Chinese vs everything else. A Chinese run keeps the punctuation and spaces after it.
CUT = "\ue000"
_CUTS = re.compile(r"\s*\ue000\s*")
# A possible cut followed by a sentence start; not "(= ...)", a gloss.
_SENTENCE_START = re.compile(r"\ue000\s*(?!\(=)(?=[A-Z0-9\"“‘'`(\[]|\.\.\.|…)")
_BULLETS = re.compile(r"[◆•▪►■□◇»]| · ")
_RUNS = re.compile(r"[㐀-鿿][^A-Za-z\n]*|[^㐀-鿿]+")
_EN_END = re.compile(r"[.?!][\"'”’)]?\s*$")
_ZH_END = re.compile(r"[。？！][”」』]?\s*$")
_ZH_SENTENCE = re.compile(r"[。？！!?]+[”」』]?")
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_LATIN = re.compile(r"[A-Za-z]")
# Trailing material that is not part of a sentence: grammar codes ("[ VERB ]", "[V n]"),
# audio icons and bullets ("🔊", "◆"), stray spaces.
_EN_TAIL = re.compile(r"(?:\s*\[[^\]]*\])+\s*$|[^\w.?!\"'”’)]+$")
_ZH_TAIL = re.compile(r"[^㐀-鿿。？！”」』]+$")
_OPENING = re.compile(r"[“‘「『(（《<〈【]\s*$")  # opens the translation, though printed in the English's element
_LATIN_TAIL = re.compile(r"([.?!][\"'”’)]?)\s+([^.?!]+)$")  # text after the last finished sentence
# Chinese characters per English word: median 1.545 over 580,387 sentence pairs of the parsed
# dictionaries (log standard deviation 0.27).
TYPICAL_RATIO = 1.545
RATIO_MARGIN = 0.2
MAX_SENTENCES = 4
_SENTENCE_SPLIT = re.compile(r"(?<=[.?!])\s+(?=[A-Z\"“‘'`(])")
# Full stops that end no sentence: after an initial ("J. K. Rowling"; not "I", the pronoun that
# ends "So do I.") or an abbreviation that
# stands before what it qualifies, which therefore always follows it. Two closed classes, by
# what the words are rather than by the ones seen:
#   titles, civil, religious and military, as English style guides list them, and the words
#     that make compound titles ("Asst. Prof. Smith", "Lt. Col. Jones")
#   the qualifiers written before an item: incl., excl., approx., esp., cf., viz., vs., ca.,
#     e.g., i.e. ("£20 incl. VAT", "cf. Smith 1990")
# In the 14.6 million staged records the titles stand before a capitalised word (Mr 98% of
# uses, Capt 97%, Maj 93%, Sgt 91%) or a number ("Gen. 1:3", "No. 10"), where no sentence is
# split anyway. Not abbreviations that follow what they qualify (etc., Inc., Ltd., Co., Jr.,
# Esq., a.m.): they end sentences ("...at Acme Inc. Smith stayed."), and so does the name a
# title stands before ("We flew to Rome. Smith stayed."). Abbreviations are an open class;
# one of the second kind missing here splits a sentence as before.
_TITLE_END = re.compile(r"\b(?:[A-HJ-Z]|Mr|Mrs|Ms|Mx|Messrs|Mme|Mlle|Dr|Drs|Prof|Rev|Revd|Fr|Msgr|St|Mt|Ft|Capt|Cpt|Col|Lt"
                        r"|Lieut|Gen|Maj|Sgt|Cpl|Pvt|Adm|Cmdr|Cdr|Brig|Gov|Sen|Rep|Pres|Hon|Rt|Supt|Insp|Det|Asst|Assoc"
                        r"|incl|excl|approx|esp|cf|viz|vs|ca|e\.g|i\.e)\.$")


def _boundary(name: str) -> str:
    name = name.lower().rpartition(":")[2]  # xhtml:a -> a
    return "" if name in _INLINE else "\n" if name in _BLOCKS or name in RAW else f" {CUT} "


def _text(markup: str) -> str:
    """markup with its tags replaced by what they mean for the text: nothing, a newline or a possible cut."""
    return "".join(_STYLE_MARKER.sub("\n", value) if kind == TEXT else _boundary(value)
                   for kind, value, _, _ in tokens(markup))


def stream(markup: str, cuts: bool = False) -> str:
    """Text with element boundaries as newlines; entities decoded (&nbsp; often sits between an
    example and its translation), and markup escaped twice removed once decoded. With cuts,
    the possible cuts at a dictionary's own tags are kept as CUT characters."""
    text = _BULLETS.sub("\n", _text(html.unescape(_text(markup))))
    if not cuts:
        text = text.replace(CUT, " ")
    lines = (" ".join(line.split()) for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


_TEMPLATE = re.compile(r"\b(?:sb|sth)\b")  # "to say sth suddenly", "put a tail on sb.": definitions, templates


_LOWER_WORD = re.compile(r"(?<![A-Za-z'’-])[a-z][a-z'’-]*")


def is_english_sentence(text: str) -> bool:
    """4+ words ending in . ? !, not a phrase template (sb/sth), and with at least two lowercase
    words: a name or title ("Advanced Micro Widgets Inc.", "AIR MALTA CO. LTD.") ends in a
    full stop only because of an abbreviation."""
    text = _strip_tail(text)
    return (len(_WORD.findall(text)) >= 4 and bool(_EN_END.search(text)) and not _TEMPLATE.search(text)
            and len(_LOWER_WORD.findall(text)) >= 2)


def is_chinese_sentence(text: str, strict: bool = True) -> bool:
    """4+ Chinese characters; strict also requires sentence-final 。？！ (older dictionaries omit it)."""
    text = _ZH_TAIL.sub("", text)
    return len(_CJK.findall(text)) >= 4 and (not strict or bool(_ZH_END.search(text)))


# The space put in for a dictionary tag must not stand before punctuation or a closing quote
# ("Go for it !", "goal? '"): that is this module's artefact, not the dictionary's text.
_SPACE_BEFORE_PUNCT = re.compile(r"(?<=[\w.?!,;:'\"’”)]) +(?=[.,?!;:](?:\s|$|['\"’”)]))")
_SPACE_BEFORE_CLOSE = re.compile(r"(?<=[.?!,]) +(?=['’”](?:\s|$))")
_SPACE_AFTER_OPEN = re.compile(r"(^|\s)(['\"‘“`]) +(?=\w)")
_SPACE_BEFORE_PAREN = re.compile(r"(?<=\S) +\)")


def _tidy(text: str) -> str:
    text = _SPACE_BEFORE_PAREN.sub(")", _SPACE_BEFORE_PUNCT.sub("", " ".join(text.split())))
    return _SPACE_AFTER_OPEN.sub(r"\1\2", _SPACE_BEFORE_CLOSE.sub("", text))


_OPENING_QUOTE_END = re.compile(r"\s+['\"‘“`(]+\s*$")  # "goal?' '" ends with the next sentence's opening quote


def _ends_sentence(text: str) -> bool:
    return bool(_EN_END.search(_OPENING_QUOTE_END.sub("", _tidy(_CUTS.sub(" ", text)))))


def _inside_sentence(text: str) -> bool:
    """Text that a sentence continues after: an unclosed bracket, or a comma or semicolon at its end."""
    text = _CUTS.sub(" ", text).rstrip()
    return text.count("(") > text.count(")") or text.endswith((",", ";"))


def _strip_tail(text: str) -> str:
    return _EN_TAIL.sub("", _EN_TAIL.sub("", text)).strip()


def _is_short_tail(text: str) -> bool:
    """A few Latin words with no sentence ending: the start of a translation ("goose 的复数")."""
    return len(_WORD.findall(text)) <= 3 and not re.search(r"[.?!]", text)


def _distance(chars: int, words: int) -> float:
    """How far a pair's length ratio is from typical, in log terms."""
    return abs(math.log(chars / words / TYPICAL_RATIO)) if words and chars else math.inf


def _sentences(en: str) -> list[str]:
    """en split at its sentence ends (see _TITLE_END for the full stops that are none)."""
    out: list[str] = []
    for piece in _SENTENCE_SPLIT.split(en):
        if out and _TITLE_END.search(out[-1]):
            out[-1] += " " + piece
        else:
            out.append(piece)
    return out


def _sentences_to_keep(sentences: list[str], zh: str) -> list[str]:
    """At least as many English sentences as the Chinese has; earlier ones only if the length
    ratio then comes clearly closer to typical (translators merge sentences, rarely split them)."""
    chars = len(_CJK.findall(zh))
    low = min(len(sentences), max(1, len(_ZH_SENTENCE.findall(zh))))

    def distance(k: int) -> float:
        return _distance(chars, sum(len(_WORD.findall(s)) for s in sentences[-k:]))

    best = min(range(low, min(len(sentences), MAX_SENTENCES) + 1), key=distance, default=low)
    return sentences[-(best if distance(low) - distance(best) > RATIO_MARGIN else low):]


def _pair(en_run: str, zh_run: str) -> tuple[str, str]:
    """The example and its translation from the runs around a Latin/Chinese switch.

    English: the last element of its run with Latin text in it (earlier elements hold the
    headword or definition), from the last sentence start after one of the dictionary's own
    tags. What follows the finished sentence is not English: an opening quotation mark or
    bracket, a number, or a few Latin words ("goose 的复数形式") begin the Chinese, and grammar
    codes or icons are dropped. The number of sentences kept is _sentences_to_keep's.
    Chinese: up to its element's end.
    """
    pieces = en_run.split("\n")
    lead = ""
    while pieces:
        last = pieces[-1]
        if not _LATIN.search(last):
            lead = last.strip() + lead
        elif not _LATIN.search(_strip_tail(last)):
            pass
        elif len(pieces) > 1 and _is_short_tail(last) and _EN_END.search(_strip_tail(pieces[-2])):
            lead = last.strip() + " " + lead
        else:
            break
        pieces.pop()
    en = pieces[-1] if pieces else ""
    # Cut at the last dictionary tag followed by a sentence start, unless a finished sentence
    # precedes it: then it is the example's own second sentence, for _sentences_to_keep.
    # Where a dictionary wraps words in tags one by one (OALECD's <ftindex>), a tag says nothing
    # about structure, and a capitalised word inside a sentence ("while I make") is no start.
    word_tagged = en.count(CUT) >= 1.5 * len(_WORD.findall(en))  # about two tags a word; LDOCE-style layouts well under one
    for start in [] if word_tagged else reversed(list(_SENTENCE_START.finditer(en))):
        before = en[:start.start()]
        if not _ends_sentence(before) and not _inside_sentence(before):
            quote = _OPENING_QUOTE_END.search(_CUTS.sub(" ", before))  # an opening quote stays with its sentence
            en = (quote.group().strip() if quote else "") + en[start.end():]
            break
    en = _tidy(_CUTS.sub(" ", en))
    opening = _OPENING.search(en)
    if opening:
        lead = opening.group().strip() + lead
        en = en[:opening.start()]
    en = _strip_tail(en)
    tail = _LATIN_TAIL.search(en)
    if tail and _is_short_tail(tail.group(2)) and not _TITLE_END.search(en[:tail.start(1) + 1]):  # not "Dr. Smith"
        lead = tail.group(2).strip() + " " + lead
        en = en[:tail.end(1)]
    zh = " ".join(_ZH_TAIL.sub("", _CUTS.sub("", lead + zh_run.split("\n", 1)[0])).split())
    return " ".join(_sentences_to_keep(_sentences(en), zh)), zh



# Latin text up to the Chinese sentence's end ("...使用Python3.11。"): a . ? ! inside a word is
# part of it, one followed by a space ends an English sentence.
_ZH_LATIN_END = re.compile(r"(?:[^\n\ue000。？！.?!]|[.?!](?=[^\s\ue000]))*[。？！][”」』]?")
# The same with the Latin words in a tag of their own inside the Chinese ("...使用<ebi>Python</ebi>。"):
# one tag opens before them and closes after them, and the sentence end follows at once.
_ZH_TAGGED_END = re.compile(r"(?:[^\n\ue000。？！.?!]|[.?!](?=[^\s\ue000]))*\ue000\s*[。？！][”」』]?")
_ONE_TAG_OPEN = re.compile(r"[^\s\ue000]\s*\ue000\s*$")
_EN_FINISHED = re.compile(r"[.?!][\"'”’)]?(?=\s|$)")
_ZH_START = re.compile(r"\ue000|[。？！；;]")  # where a Chinese example may begin, after a gloss
# No translated example has more Chinese than this; looking further back into a long Chinese
# run (a Chinese dictionary's article) made the Chinese-first reading quadratic.
MAX_EXAMPLE_ZH = 300


def _stranded_lead(before: str) -> str:
    """A number or a few Latin words at the end of the run before a Chinese-first example, after
    its last boundary ("...per cent. 20 " + "多架直升机"): the start of that example, not the end
    of the previous one."""
    tail = re.split(r"[\n\ue000]|[.?!]['\"’”)]?\s", before)[-1].strip()
    return tail + " " if tail and _is_short_tail(tail) and not _CJK.search(tail) else ""


def _pair_zh_en(zh_run: str, en_run: str, lead: str = "") -> tuple[str, str]:
    """The example and its translation when the Chinese comes first.

    English: from the start of its element to its last finished sentence (what follows is the
    next headword or a label). Chinese: the whole run, or its part after a dictionary tag or a
    。？！； if that brings the length ratio clearly closer to typical: a gloss before the
    example drops out, a highlighted word inside it does not cut it. A short gloss separated
    from the example by nothing but a tag (<gl>开启</gl><ex>...) looks locally like a
    highlighted word and stays when the ratio is not clear; the audit sees such residue.
    """
    first = _tidy(_CUTS.sub(" ", en_run.lstrip().split("\n", 1)[0]))
    # an abbreviation's full stop ends the English only where nothing follows it ("... (+V.D.)")
    end = max((m.end() for m in _EN_FINISHED.finditer(first)
               if not (_TITLE_END.search(first[:m.start() + 1]) and first[m.end():].strip())), default=0)
    en = first[:end].strip()
    words = len(_WORD.findall(en))
    if len(zh_run) > MAX_EXAMPLE_ZH:
        window = zh_run[-MAX_EXAMPLE_ZH:]
        first = _ZH_START.search(window)
        zh_run = window[first.end():] if first else window
    options = []
    for start in [0, *(m.end() for m in _ZH_START.finditer(zh_run))]:
        zh = " ".join(_ZH_TAIL.sub("", _CUTS.sub("", zh_run[start:])).split())
        if _CJK.search(zh):
            options.append(zh)
    if not options:
        return en, ""
    options[0] = lead + options[0]  # a stranded number belongs to the whole run's start
    best = min(options, key=lambda zh: _distance(len(_CJK.findall(zh)), words))
    whole = options[0]
    gain = _distance(len(_CJK.findall(whole)), words) - _distance(len(_CJK.findall(best)), words)
    return en, best if gain > RATIO_MARGIN else whole


_ZH_ENDED = re.compile(r"[。？！!?][”」』）)]?\s*$")


def _latin_end(chinese: str, run: str) -> re.Match | None:
    """The start of a Latin run that finishes the Chinese sentence before it, however many words
    it has ("...使用Microsoft Visual Studio Code。"): Latin text up to a 。？！ with no element
    boundary or finished English sentence in between, after Chinese that has not ended its own
    sentence. A 。？！ is Chinese punctuation, so the sentence it ends is Chinese."""
    if _ZH_ENDED.search(chinese):
        return None
    return _ZH_LATIN_END.match(run) or (_ZH_TAGGED_END.match(run) if _ONE_TAG_OPEN.search(chinese) else None)


def _merge_latin_in_chinese(runs: list[str]) -> list[str]:
    """Rejoin Chinese split by Latin text: a Latin run of at most three words, in unbroken text
    (no element boundary or dictionary tag) and not ending a sentence, between two Chinese runs
    ("只有现代X光机"); or Latin words finishing a Chinese sentence ("如何使用Python。", see
    _latin_end), which its 。？！ shows belong to the Chinese. Inside a sentence, longer Latin
    text is not rejoined: an unpunctuated translation, the next phrase and its gloss ("他回家了
    to come back home 回家") have the same shape."""
    merged: list[str] = []
    i = 0
    while i < len(runs):
        run = runs[i]
        end = _latin_end(merged[-1], run) if merged and _CJK.match(merged[-1]) and not _CJK.match(run) else None
        if end:
            merged[-1] += end.group()
            run = run[end.end():]
            if not run:  # the whole run: what follows may continue the Chinese
                if i + 1 < len(runs) and _CJK.match(runs[i + 1]):
                    merged[-1] += runs[i + 1]
                    i += 1
                i += 1
                continue
        if (merged and _CJK.match(merged[-1]) and i + 1 < len(runs) and _CJK.match(runs[i + 1])
                and not _CJK.match(run) and "\n" not in run and CUT not in run and len(_WORD.findall(run)) <= 3
                and not _EN_END.search(_CUTS.sub(" ", run))):
            merged[-1] += run + runs[i + 1]
            i += 2
            continue
        merged.append(run)
        i += 1
    return merged


ORDERS = ("en-zh", "zh-en")


def candidate_pairs(text: str, strict: bool = True, order: str = "en-zh") -> list[tuple[str, str]]:
    """Every English sentence directly followed by a Chinese sentence in a stream() (order
    "en-zh"), or the reverse ("zh-en"); language unchecked. Pairs are (English, Chinese)."""
    if order not in ORDERS:
        raise ValueError(f"order must be one of {ORDERS}")
    runs = _merge_latin_in_chinese(_RUNS.findall(text))
    pairs = []
    for i, (first, second) in enumerate(zip(runs, runs[1:])):
        if order == "en-zh":
            if _CJK.match(first) or not _CJK.match(second):
                continue
            en, zh = _pair(first, second)
        else:
            if not _CJK.match(first) or _CJK.match(second):
                continue
            en, zh = _pair_zh_en(first, second, _stranded_lead(runs[i - 1]) if i else "")
        if is_english_sentence(en) and is_chinese_sentence(zh, strict):
            pairs.append((en, zh))
    return pairs


def is_english_chinese(pair: tuple[str, str]) -> bool:
    """German-, French-, Japanese- or Korean-Chinese dictionaries have the same shape; this tells them apart."""
    return is_english(pair[0]) and is_chinese(pair[1])


def pairs(markup: str, strict: bool = False, order: str = "en-zh") -> list[tuple[str, str]]:
    """The English-Chinese example pairs in one record or block of markup, as (English, Chinese)."""
    return [p for p in candidate_pairs(stream(markup, cuts=True), strict, order) if is_english_chinese(p)]
