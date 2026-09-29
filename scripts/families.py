"""Brand families and search aliases for dictionary names.

Names on freemdict use one naming convention each (an abbreviation, an English
title, or a Chinese title), so users searching another convention miss them.
ALIASES adds the other conventions to a record's searchable text; BRANDS
drives the brand filter chips.

Patterns run against the name after `fold` (NFKC, lowercase, Traditional ->
Simplified), so write them in lowercase simplified Chinese.
"""
import re

# Abbreviations must not be part of a longer word: "ode" must not hit "code".
_B = r"(?<![a-z])"
_E = r"\d*(?![a-z])"

BRANDS: list[tuple[str, re.Pattern[str]]] = [
    (label, re.compile(pattern))
    for label, pattern in [
        ("Oxford", rf"oxford|牛津|{_B}(oald|oalecd|oaled|oele?d|ode|oed|noad|coed|olt|nopd|obad|olcc){_E}"),
        ("Longman", rf"longman|朗文|{_B}(l?doce|laad|lasecd|ldae|lpd|ltae|lla|lcdt){_E}"),
        ("Collins", rf"collins|colins|cobuild|柯林斯|{_B}(ccald|ccabeld|cced|ccad){_E}"),
        ("Merriam-Webster", rf"merriam|webster|韦氏|韦伯|{_B}(mw|mwc|mwcd|mwaled|mwu){_E}"),
        ("Cambridge", rf"cambridge|剑桥|{_B}(cald|cide|cepd|camen\w*){_E}"),
        ("Macmillan", rf"macmillan|麦克米伦|{_B}(medal|med){_E}"),
        ("American Heritage", rf"american heritage|美国传统|{_B}ahd{_E}"),
        ("Chambers", r"chambers|钱伯斯"),
        ("WordNet", rf"wordnet|{_B}wn\d"),
        ("Urban Dictionary", rf"urban ?dict|{_B}ud\d"),
        ("TheFreeDictionary", rf"thefreedictionary|{_B}tfd{_E}"),
        ("Wiktionary", r"wiktionary|wikitionary|维基词典"),
        ("Etymology", r"etymolog|etymonline|词源|源流|word origins"),
    ]
]

ALIASES: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(pattern), aliases)
    for pattern, aliases in [
        # "advanced learner's" alone would also tag Cambridge, Collins, Macmillan and MW titles.
        (rf"{_B}(oald|oalecd|oaled){_E}|oxford advanced learner|牛津高阶",
         ["OALD", "Oxford Advanced Learner's Dictionary", "牛津高阶", "牛津高阶英汉双解"]),
        (rf"{_B}ode{_E}|oxford dictionary of english|新牛津英英|新牛津英语",
         ["ODE", "Oxford Dictionary of English", "新牛津英语词典"]),
        (rf"{_B}noad{_E}|new oxford american|新牛津美语",
         ["NOAD", "New Oxford American Dictionary", "新牛津美语词典"]),
        (rf"{_B}0?oed{_E}|oxford english dictionary|牛津英语大词典",
         ["OED", "Oxford English Dictionary", "牛津英语大词典"]),
        (rf"{_B}l?doce{_E}|contemporary english|朗文当代",
         ["LDOCE", "Longman Dictionary of Contemporary English", "朗文当代"]),
        (rf"{_B}laad{_E}|longman advanced american|朗文高阶",
         ["LAAD", "Longman Advanced American Dictionary", "朗文高阶"]),
        (rf"{_B}lpd{_E}|longman pronunciation|朗文发音",
         ["LPD", "Longman Pronunciation Dictionary", "朗文发音词典", "pronunciation"]),
        (rf"{_B}(cepd|epd){_E}|english pronouncing|剑桥发音",
         ["CEPD", "Cambridge English Pronouncing Dictionary", "剑桥发音词典", "pronunciation"]),
        (rf"cobuild|{_B}(ccald|ccabeld|cced|ccad){_E}",
         ["COBUILD", "Collins COBUILD", "柯林斯"]),
        (r"柯林斯", ["Collins", "COBUILD"]),
        (rf"collegiate|{_B}(mwc|mwcd){_E}|韦氏大学",
         ["Merriam-Webster's Collegiate", "MWC", "韦氏大学词典"]),
        # Not bare "unabridged": Random House and Dictionary.com have unabridged editions too.
        (rf"webster'?s third|merriam[- ]webster unabridged|{_B}mwu{_E}",
         ["Webster's Third", "Merriam-Webster Unabridged", "韦氏大词典"]),
        (rf"{_B}cald{_E}|cambridge advanced learner|剑桥高阶",
         ["CALD", "Cambridge Advanced Learner's Dictionary", "剑桥高阶"]),
        (rf"{_B}(medal|med){_E}|macmillan english dictionary|麦克米伦高阶",
         ["MED", "Macmillan English Dictionary", "麦克米伦"]),
        (rf"{_B}ahd{_E}|american heritage|美国传统",
         ["AHD", "American Heritage Dictionary", "美国传统词典"]),
        (r"urban ?dict|俚语", ["Urban Dictionary", "slang", "俚语"]),
        (r"etymolog|etymonline|词源|word origins",
         ["etymology", "etymonline", "词源"]),
        (rf"wordnet|{_B}wn\d", ["WordNet"]),
        (r"thesaurus|同义词|近义词|synonym", ["thesaurus", "synonyms", "同义词", "近义词"]),
        (r"collocation|combinatory|搭配", ["collocations", "搭配"]),
        (r"idiom|习语|成语|惯用语", ["idioms", "习语"]),
        (r"phrasal verb|短语动词", ["phrasal verbs", "短语动词"]),
        # "sound" only as a name of its own (audio packs "Sound-en_GB", "Sound"), not
        # "Pic&Sound" or CSS files like "No.Sound.Icon".
        (r"pronunc|pronouncing|发音|(?<![a-z&])sound(?![a-z])(?!.*icon)", ["pronunciation", "audio", "发音"]),
        (r"英汉大词典|陆谷孙", ["英汉大词典", "陆谷孙", "Lu Gusun"]),
        (r"双解", ["bilingual", "双解", "英汉双解"]),
    ]
]


# Names that match a brand pattern but belong to another publisher.
NOT_BRAND: dict[str, re.Pattern[str]] = {
    "Merriam-Webster": re.compile(r"random house|new world"),  # "Webster's" is not a trademark
}


def brands_of(folded_name: str) -> list[str]:
    return [
        label for label, pattern in BRANDS
        if pattern.search(folded_name) and not (label in NOT_BRAND and NOT_BRAND[label].search(folded_name))
    ]


def aliases_of(folded_name: str) -> list[str]:
    out: list[str] = []
    for pattern, aliases in ALIASES:
        if pattern.search(folded_name):
            out.extend(a for a in aliases if a not in out)
    return out
