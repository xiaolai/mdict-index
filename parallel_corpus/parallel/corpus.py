"""The parallel corpus's rules: what a pair is, whether it is valid, and when two are the same.

Pure functions, shared by the extractors and the database build, and tested directly.

Deduplication, three levels:
  exact_key   the same pair once normalised (case, spacing, width, quotes, dashes,
              traditional -> simplified): stored once, every source recorded
  loose_key   the same pair ignoring punctuation and spacing entirely: a cluster with one
              representative; the members stay linked, exports default to representatives
  en_key      the same English with a different Chinese translation: separate pairs
              (real data), grouped as translation variants
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
_CJK = re.compile(r"[㐀-鿿豈-﫿]")
_LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_SENTENCE_END = re.compile(r"[.?!][\"'”’)]?$")
_TAG = re.compile(r"</?[A-Za-z][\w:-]*(?:\s[^<>]*)?/?>")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "‐": "-", "‑": "-", " ": " "})

_KANA_HANGUL = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]")
# Letters English does not use, and pinyin tone marks (a single loanword accent, as in "café", is tolerated).
_FOREIGN_LETTER = re.compile(r"[äöüßàâæçèêëîïôœùûÿñáíóúãõåøìòąćęłńśźżāēīōūǎěǐǒǔǖǘǚǜ]", re.I)
_EN_FUNCTION = frozenset("""the a an of to and in is are was were be been being it its this that these those i you he she
we they me him her us them my your his our their not no do does did have has had will would can could should may might
must shall at on for with from by as or but if so than then there here what which who whom whose when where why how all
any some more most very just also only about into out up down over after before because while""".split())
# Function words of the other Latin-script languages found beside Chinese in these dictionaries,
# leaving out those that are also English words (die, war, den, son, per, me, van, was, met, hay...).
_FOREIGN_FUNCTION = frozenset("""
der das dem des ein eine einen einem und oder ist sind nicht mit zu von auf für sich ich du sie wir ihr es im
bei aus nach weil dass sehr auch noch
le la les un une des du de et ou est sont était être avec pour dans sur par que qui ce cette ces il elle ils
elles nous vous je tu mon ma mes ne pas plus mais parce fait très au aux
el los las una unos unas y del al en por para qué está están era fue ser estar muy mucho más pero porque
como cuando donde se su sus lo les ella él ellos nosotros yo mi te nos hace
gli è di che non con della sono sei lei lui noi voi io molto perché anche
os é da em não ele eles você
het een en zijn niet voor dat ik jij hij zij wij omdat
wa ga ni wo ka mo""".split())
_ROMAJI_VERB = re.compile(r"(?:mashita|masen|masu|deshita|desu)$")  # romanised Japanese verb endings
_ET_AL = re.compile(r"\bet al\b\.?")
# Chinese-made dictionaries write inside English examples 或 for "or" ("(at, in 或 on)") and
# register or region labels ("〈口〉", "〈北美〉", "<英><美>").
_OR_MARKER = re.compile(r"\s*或\s*")
_ZH_LABEL = re.compile(r"\s*[〈<][\u3400-\u9fff]{1,4}[〉>]\s*")
_OPEN_SPACE = re.compile(r"([(（]) ")
_HIGHLIGHT = re.compile(r"\[([A-Za-z][A-Za-z' -]{0,40})\](?=\s+(?:[a-z]|I\b)|,)")  # "[Of course] you should...": brackets as highlighting
_SPACE_BEFORE = re.compile(r"(?<=\w) +(?=[.,?!;:](?:\s|$|[\"'”’)]))")  # "harder ." -> "harder."
# What an example or a translation may begin with besides a letter or a digit; anything else in
# front of it is a bullet or an icon ("· I suspect", "🔊我们", "◆"). See _lead().
_EN_OPENING = frozenset("\"'“‘`([.…")
_ZH_OPENING = frozenset("“‘「『(（《〈【[.…—-+＋−")
_SENSE_MARKS = frozenset(map(chr, range(ord("①"), ord("⑳") + 1)))
_LABEL_ONLY = re.compile(r"^【[^】]*(?:】\s*[：:].*|】?)$")  # "【语法信息】", "【STYLE 标签】：LITERARY 文"
# Notes about words ("Sickness is used for... | sickness 既可指..."): the word discussed stays in
# English inside the Chinese. Translations keep acronyms and names (CE, Palm Springs), which
# are capitalised, not lowercase words.
# "霍普韦尔：弗吉尼亚州...", "擦，拭：用布...": a definition's translation, its headword first (glosses
# of at most six characters, separated by commas). Not reported speech (他说：“..., 他问道：),
# dialogue labels (甲：), or a colon opening a quotation. An example's Chinese colon answers a
# colon, semicolon or dash in its English ("the spawn of chaos: demons"); a definition's does not.
_ZH_DEFINITION = re.compile(r"^(?![甲乙丙丁][：:])[\u3400-\u9fff]{1,6}(?:[，,、·][\u3400-\u9fff]{1,6}){0,2}"
                            r"(?<![说道问答喊叫曰们])：(?!\s*[“「‘\"'])")
_EN_COLON = re.compile(r"[:;—–]|\s-\s")
# "spoil 是损坏...", "Decoy 意为...": a note about a word. A capitalised word only before a definitional
# verb, since a name comes before a plain 是 ("Tom 是我的朋友").
_ZH_WORD_MEANS = re.compile(r"(?<![A-Za-z])(?:[a-z]{3,}\s*(?:是指|是|指|意为|意思是|表示)"
                            r"|[A-Z][a-z]{2,}\s*(?:是指|意为|意思是|指的是))")
_ZH_LOWER_WORD = re.compile(r"(?<![A-Za-z])[a-z][a-z'-]+(?![A-Za-z])")
_ZH_SUBJECT = re.compile(r"^【[\u3400-\u9fff]{1,6}】")  # "【地质】板块...": a subject label
_IPA = re.compile(r"/[^/\s]*[ˈˌəɪʊʌɒɜæθðŋʃʒː][^/]*/")
_TEMPLATE = re.compile(r"\b(?:sb|sth)\b")  # "pin sb. down": "sb" stands in for "somebody" as "~" for the headword
# Found by the audit's reviewers (parallel_corpus/data/review_batches/):
_PLACEHOLDER = re.compile(r"~")
_ALTERNATIVES = re.compile(r"[.?!]['\"’”]?\s*(?:or|/)\s+['\"‘“]?[A-Z]|\(or\s[^)]*\)")  # "X. or Y.", "A. / B.", "(or with)"
_IE_NOTE = re.compile(r"\b(?:ie|eg)\b")  # OALD-style notes; natural English writes "i.e."
_ZH_APPARATUS = re.compile(r"[\[\]［］【】]")
_ZH_CAPS = re.compile(r"(?<![A-Za-z])[A-Z]{4,}(?![A-Za-z])")  # "SYNONYM 同义词"
_MARKUP_LEFTOVER = re.compile(r"[{}]|&(?:amp|lt|gt|quot|nbsp);")
_ETYMOLOGY = re.compile(r"\b(?:Fr|OFr|L|Lat|Ital|Gk|Gr|OE|ME|NL|ON|MF)\s*[<:]\s|<\s*\?")  # "[Fr < Ital bronzo < ?"; not "3 < 5"
_GARBLED = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ue000-\uf8ff\ufffd]")  # control, private-use, replacement
_LATIN_LABEL = re.compile(r"〈拉(?:丁)?〉|<拉(?:丁)?>")
_ZH_FINAL = re.compile(r"[。？！!?][”」』)）]?$")
_GLOSS = re.compile(r"^[（(]|[；;]")  # "（道路）转弯；拐弯": notes and alternatives, the form of a gloss
# A number before an example is a sense number when a sentence starts after it: a capitalised
# function word ("8 He is...", "12 The door..."), not a noun ("3 Americans came..."), and not a
# word joined to the next by a hyphen ("3 A-levels", "2 I-beams"). Measured on the 14.6 million
# staged records: 3,190 start with a number and a capitalised function word, all of them sense
# numbers (every one with "A"/"An", 265, was read). Two of those words are also nouns, and then
# the number is a quantity or a date; the translation tells which, as it translates a word but
# keeps a letter and gives a date its month (see _quantity_or_date):
#   a letter (A, I): kept in the Chinese ("3 A grades..." | "3个A..."), or, in English alone,
#       a plural agreeing with the number ("3 A grades are...")
#   the month May: a date when no word follows ("11 May, ...", "1 May 1990"); before a word,
#       5月, 五月 or 五一 in the Chinese, or in English alone no capitalised word after it ("25
#       May is a holiday"; "1 May I come in?" and "1 May we go?" are the modal)
# Other function words that are nouns too (Will, Can, Down) are not looked for: none of the
# 3,190 is one.
_FUNCTION_WORD_START = re.compile(r"^\s*(\d{1,2})\s+(" + "|".join(sorted({w.capitalize() for w in _EN_FUNCTION}, key=len,
                                                                             reverse=True)) + r")\b(?!-)")
_LETTER_AGREEMENT = re.compile(r"\s+[a-z]+s\s+(?:are|were|have|had|do|did|will|would|can|could|should|may|might|must|shall)\b")
_LATIN_LETTER = r"(?<![A-Za-zＡ-Ｚａ-ｚ]){}(?![A-Za-zＡ-Ｚａ-ｚ])"
_MONTH_MAY = re.compile(r"(?<![\d０-９])[5５]\s*月|(?<![一二三四五六七八九十])五[月一]")  # 五一: May Day


def _quantity_or_date(word: str, rest: str, zh: str) -> bool:
    """Whether a capitalised function word after a leading number is a noun (a letter, the month
    May), so that the number is part of the sentence. rest is the text after the word; zh the
    translation, or "" when it is not known."""
    if len(word) == 1:  # A, I
        # the Chinese keeps the letter more often than the rest of the English has it ("1 I read
        # Volume I." | "我读了第I卷。" is a sense number)
        letter = re.compile(_LATIN_LETTER.format(f"[{word}{chr(ord(word) + 0xFEE0)}]"))
        return (len(letter.findall(zh)) > len(letter.findall(rest))
                or word == "A" and bool(_LETTER_AGREEMENT.match(rest)))
    if word == "May":
        if not re.match(r"\s+[^\W\d_]", rest):  # a date: "11 May, ...", "1 May 1990", "25 May."
            return True
        return bool(_MONTH_MAY.search(zh)) if zh else not re.match(r"\s+[A-Z]", rest)
    return False


# "(as adjective broken) a broken promise", "(as plural noun the rich)", "(also as noun)": a
# dictionary's grammar label, in its grammar: "as", a part of speech named in full (the only
# form in the data: 386 labels in the staged records, none abbreviated), "plural" or "singular"
# only before "noun", grammar notes, then the form of the headword the example uses: one word,
# "the" and a word, a verb and its particle ("left out"), or two words joined by "and" ("toing
# and froing"), every form among the 386. A comparison ("(as singular as it sounds)"), "(as
# usual)" or a clause ("(as noun phrases go)") is part of the sentence. The one shape this
# grammar cannot tell from a label is a parenthesis that names a part of speech in full and
# then one word the sentence repeats ("(as noun phrases)" before "...phrases..."): none of the
# 2,930 "(as ...)" parentheses in the staged records is one.
_PART_OF_SPEECH = (r"(?:(?:plural|singular)\s+noun|adjective|adverb|noun|verb|pronoun|preposition|conjunction"
                   r"|exclamation|interjection|modifier|determiner)")
_GRAMMAR_NOTE = r"(?:usually|mass|count|with\s+submodifier|in\s+combination)"
_PARTICLE = r"(?:about|across|along|around|aside|away|back|by|down|forth|in|off|on|out|over|through|together|up)"
_WORD = r"-?[A-Za-z][A-Za-z'’-]*"
_FORM = rf"(?:the\s+{_WORD}|{_WORD}\s+and\s+{_WORD}|{_WORD}\s+{_PARTICLE}|{_WORD})"
_AS_LABEL = re.compile(r"^\s*\((?:also\s+)?as\s+(?:an?\s+)?(?:" + _GRAMMAR_NOTE + r"[\s,]+)*" + _PART_OF_SPEECH
                       + r"\b(?:[\s,]+(?:" + _GRAMMAR_NOTE + "|" + _PART_OF_SPEECH + r")\b)*(?:[\s,]+(?:"
                       + _GRAMMAR_NOTE + r"[\s,]+)*(" + _FORM + r"))?\s*\)\s*")
_FORM_ARTICLE = re.compile(r"^(?:(?:the|an?)\s+|-)", re.I)
# Dictionary apparatus inside examples: a leading grammar label ("[with object]:",
# "(as adjective broken)", "(+ adv./prep.)", "(~ sth to sb)") and explanatory glosses
# ("(= a person who repairs shoes)").
_EN_APPARATUS = re.compile(r"\s*\[(?:=|w=|with obj|no obj|with object|no object)[^\]]{0,40}\]"
                           r"|\s*\((?:ie|i\.e\.|eg|e\.g\.)\s[^)]*\)"
                           r"|^\s*[a-z0-9]{1,2}\)\s*"
                           r"|^\s*\[[A-Z]{1,4}(?:-[A-Z]{1,2})?(?=[\s,+(\]-])[^\]]{0,40}\]\s*"  # [VN -ing], [V (that)], [NOTE]
                           r"|^\s*\((?:figurative|informal|formal|literary|old-fashioned|humorous|disapproving"
                           r"|approving|slang|offensive|technical|ironic|rare|dated|specialist)\)\s*"  # register labels
                           r"|^\s*(?:\[[^\]]{1,40}\]\s*:"   # "(prep school)" is text: the abbreviations have their full stop
                           r"|\(\s*[+~][^)]{0,40}\)|\([^)]{0,40}(?:\b(?:sth|sb)\b|\b(?:adv|prep)\.)[^)]{0,40}\))\s*|\s*\(=[^)]*\)")
# Usage and subject labels on the Chinese side ("〈喻〉他..."): a closed list, because 〈〉 also
# marks titles (〈背影〉).
_ZH_LABELS = """喻 口 俚 书 谑 古 旧 美 英 澳 方 贬 褒 婉 讽 粗 忌 罕 诗 儿 蔑 废 苏 加 文 正式 非正式 口语 俚语 书面 书面语
方言 古语 旧时 过时 美式 英式 北美 贬义 褒义 戏谑 委婉 诙谐 幽默 反语 讳 蔑称 法 律 医 化 物 数 生 植 动 军 商 经 计 宗 史
语 天 地 船 空 电 体 音 建 矿 冶 纺 农 林 牧 渔 药 解 心 哲 逻 修 摄 戏""".split()
_ZH_LABEL_TAG = re.compile("[〈<](?:" + "|".join(sorted(map(re.escape, _ZH_LABELS), key=len, reverse=True)) + ")[〉>]")

MIN_SENTENCE_WORDS = 4
# Chinese characters per English word in a translation: about 1.5 on average; the bounds only
# reject pairs that cannot be translations of each other (a sentence against one character).
MIN_RATIO, MAX_RATIO = 0.3, 6.0


@lru_cache(maxsize=1)
def _t2s() -> dict[int, str]:
    table = json.loads((ROOT / "site" / "t2s.json").read_text())
    return {ord(k): v for k, v in table.items()}


def clean(text: str) -> str:
    """Whitespace collapsed; the text itself is kept as printed (headwords, and the base of the two below)."""
    return " ".join(text.replace("\u00a0", " ").split())


def _number_at(text: str, i: int) -> bool:
    """Whether a number starts at text[i]: a digit or another numeral ("½"), possibly after a
    decimal point or currency signs ("-.5", "-$5", "+€3")."""
    while i < len(text) and unicodedata.category(text[i]) == "Sc":
        i += 1
    if i < len(text) and text[i] in ".．":
        i += 1
    return i < len(text) and (unicodedata.category(text[i])[0] == "N" or text[i] == "∞")


def _lead(text: str, opening: frozenset[str], marks: frozenset[str] = frozenset()) -> str:
    """text from its first character that is text: a letter, a digit, one of `opening`, a
    currency sign, or a sign in front of a number (see _number_at). By Unicode category, not by
    a list of signs: a dash (Pd), a mathematical sign (Sm) other than an arrow, or "#" is a
    sign, so "－5" (fullwidth), "−5", "-$5", "±2", "<5" and "#1" all keep theirs.
    Before anything else a sign is a bullet ("- I suspect", "+ I suspect"), and so is an arrow
    before anything ("→5 See picture"); so is a sign separated from its number by a space ("- 5
    reasons"), the layout of a list. `marks` are never text (①)."""
    for i, ch in enumerate(text):
        if ch in marks:
            continue
        if ch.isalnum() or ch == "_" or ch in opening:
            return text[i:]
        category = unicodedata.category(ch)
        sign = category == "Pd" or ch in "#＃" or category == "Sm" and "ARROW" not in unicodedata.name(ch, "")
        if category == "Sc" or sign and _number_at(text, i + 1):
            return text[i:]
    return ""


def _without_label(text: str, zh: str) -> str:
    """text without a leading sense number or "(as ...)" grammar label (see _FUNCTION_WORD_START, _AS_LABEL)."""
    m = _FUNCTION_WORD_START.match(text)
    if m and not _quantity_or_date(m[2], text[m.end():], zh):
        return text[m.start(2):]
    m = _AS_LABEL.match(text)
    if m:
        form = (m[1] or "").strip().lower()
        # the form as a word of the example, or the last part of a compound ("well-researched"); a
        # combining form ("-lit") as the end of a word ("moonlit")
        before = "" if form.startswith("-") else r"(?<![\w'’])"
        form = _FORM_ARTICLE.sub("", form)
        if not form or re.search(rf"{before}{re.escape(form)}(?![\w-])", text[m.end():].lower()):
            return text[m.end():]
    return text


def clean_zh(text: str) -> str:
    """The Chinese side: clean(), with usage labels and leading bullets or icons dropped."""
    return _lead(_ZH_SUBJECT.sub("", clean(_ZH_LABEL_TAG.sub("", text))), _ZH_OPENING, _SENSE_MARKS)


def clean_en(text: str, zh: str = "") -> str:
    """The English side: clean(), with 或 written "or", Chinese labels, dictionary apparatus,
    leading bullets and the space some layouts put before punctuation dropped. zh, the
    translation, is evidence on whether a leading number is a sense number (_quantity_or_date);
    without it the English alone decides."""
    text = _lead(clean(_OR_MARKER.sub(" or ", _ZH_LABEL.sub(" ", text))), _EN_OPENING)
    while True:  # apparatus chains ("[VN] (figurative) ..."); a bullet may precede it
        stripped = _lead(clean(_HIGHLIGHT.sub(r"\1", _EN_APPARATUS.sub(" ", _without_label(text, zh)))), _EN_OPENING)
        if stripped == text:
            break
        text = stripped
    return _OPEN_SPACE.sub(r"\1", _SPACE_BEFORE.sub("", text))


def to_simplified(text: str) -> str:
    """Character-by-character traditional -> simplified; context-dependent choices are not made."""
    return text.translate(_t2s())


def norm_en(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).translate(_QUOTES).casefold().split())


def norm_zh(text: str) -> str:
    """Spacing is typographic in Chinese ("12 月" = "12月"), so it is dropped."""
    return "".join(unicodedata.normalize("NFKC", text).translate(_QUOTES).translate(_t2s()).casefold().split())


def _only_content(text: str) -> str:
    return "".join(ch for ch in text if ch.isalnum())


def exact_key(en: str, zh: str) -> str:
    return norm_en(en) + "\t" + norm_zh(zh)


def loose_key(en: str, zh: str) -> str:
    return _only_content(norm_en(en)) + "\t" + _only_content(norm_zh(zh))


def en_key(en: str) -> str:
    return _only_content(norm_en(en))


def is_english(text: str) -> bool:
    """Latin-script text that is English rather than German, French, Spanish, Dutch, pinyin...

    English is assumed unless there is evidence against it: letters English does not use with
    hardly any English function words around them, or other languages' function words (der, le, el, que...) outnumbering English ones (the, of,
    is...). Requiring English function words instead rejected real phrases such as
    "persistently high interest rates". A lone foreign word ("das Auto") passes; foreign
    dictionaries are caught by the dictionary-level share of foreign pairs (parallel/choose.py).
    """
    words = [w.lower() for w in _LATIN_WORD.findall(_ET_AL.sub(" ", text))]
    if not words:
        return False
    en = sum(w in _EN_FUNCTION for w in words)
    foreign = sum(w in _FOREIGN_FUNCTION or bool(_ROMAJI_VERB.search(w)) for w in words)
    if len(_FOREIGN_LETTER.findall(text)) > 1 and en < 2:  # "tête-à-tête by the fire" has English around it
        return False
    return not (foreign >= 2 and foreign > en)


def is_chinese(text: str) -> bool:
    """Contains Chinese characters and no Japanese kana or Korean hangul."""
    return bool(_CJK.search(text)) and not _KANA_HANGUL.search(text)


@dataclass(frozen=True)
class Verdict:
    ok: bool
    kind: str = ""        # "sentence" | "phrase"
    reason: str = ""      # why a pair was rejected: a fixed phrase, so rejections can be counted
    detail: str = ""      # the measurement behind the reason, if any


def judge(en: str, zh: str) -> Verdict:
    """Whether (en, zh) is a usable parallel pair, and whether it is a sentence or a phrase."""
    if _LABEL_ONLY.match(clean(zh)):
        return Verdict(False, reason="a label, not a translation")
    if _GARBLED.search(en) or _GARBLED.search(zh):
        return Verdict(False, reason="garbled text")
    if _LATIN_LABEL.search(zh):
        return Verdict(False, reason="the Latin-script side is not English")
    en, zh = clean_en(en, zh), clean_zh(zh)
    if _ALTERNATIVES.search(en):
        return Verdict(False, reason="alternative versions")
    if not en or not zh:
        return Verdict(False, reason="empty side")
    if _IPA.search(en):
        return Verdict(False, reason="pronunciation in text")
    if _ETYMOLOGY.search(en):
        return Verdict(False, reason="etymology")
    if _TAG.search(en) or _TAG.search(zh) or _MARKUP_LEFTOVER.search(en) or _MARKUP_LEFTOVER.search(zh):
        return Verdict(False, reason="markup in text")
    if _PLACEHOLDER.search(en) or _PLACEHOLDER.search(zh):
        return Verdict(False, reason="a placeholder for the headword")
    if _TEMPLATE.search(en):
        return Verdict(False, reason="a template with placeholders (sb/sth)")
    if _IE_NOTE.search(en):
        return Verdict(False, reason="an explanatory note (ie/eg)")
    if _CJK.search(en):
        return Verdict(False, reason="Chinese on the English side")
    words = _LATIN_WORD.findall(en)
    chars = _CJK.findall(zh)
    if not words:
        return Verdict(False, reason="no English words")
    if len(words) < 2:  # "refugee | 难民", "picornavirus. | 小核醣核酸病毒": a gloss
        return Verdict(False, reason="a single word, not an example")
    if _KANA_HANGUL.search(zh):
        return Verdict(False, reason="Japanese or Korean on the Chinese side")
    if not chars:
        return Verdict(False, reason="no Chinese on the Chinese side")
    if not is_english(en):
        return Verdict(False, reason="the Latin-script side is not English")
    if _ZH_APPARATUS.search(zh) or any(w not in en for w in _ZH_CAPS.findall(zh)):
        return Verdict(False, reason="apparatus in the Chinese")
    if (len(words) >= MIN_SENTENCE_WORDS and _SENTENCE_END.search(en) and not _ZH_FINAL.search(zh)
            and _GLOSS.search(zh)):
        return Verdict(False, reason="a gloss, not a translation")
    if _ZH_DEFINITION.match(zh) and not _EN_COLON.search(en):
        return Verdict(False, reason="a translated definition, not an example")
    en_words = {w.lower() for w in words}
    zh_lower = _ZH_LOWER_WORD.findall(zh)
    if (zh_lower and (_ZH_LOWER_WORD.match(zh) or any(len(w) >= 3 and w in en_words for w in zh_lower))
            or _ZH_WORD_MEANS.search(zh)):
        return Verdict(False, reason="a note about a word, not an example")
    ratio = len(chars) / len(words)
    if not MIN_RATIO <= ratio <= MAX_RATIO:
        return Verdict(False, reason="length ratio implausible for a translation", detail=f"{ratio:.2f}")
    sentence = len(words) >= MIN_SENTENCE_WORDS and bool(_SENTENCE_END.search(en))
    return Verdict(True, kind="sentence" if sentence else "phrase")
