"""Classify a dictionary file path by its language relation to English.

Classes:
  en-en     English monolingual (incl. thesaurus, usage, etymology, specialist)
  en-zh     English <-> Chinese bilingual
  en-other  English <-> a third language (German-English, 英和, ...)
  other     no English side
  unknown   no rule fired; needs a human look

Rules are keyword heuristics over the filename first, then the folder path.
"""
import re
import unicodedata

OTHER_LANG = re.compile(
    r"德|法[汉英语法]|[汉英]法|俄|日[汉中英日语本]|[汉中英]日|英和|和英|英日|韩|韓|意[汉大英语]|[汉英]意|西班牙|西[汉英]|[英汉]西|葡|拉丁|希腊|希英|梵|藏|越南|越[汉英]|泰|阿拉伯|波斯|土耳其|荷|瑞典|挪威|娜威|捷克|匈牙利|波兰|蒙古|印尼|马来|世界语|世汉|满|乌克兰|亚美尼亚|亞美尼亞|塞尔维亚|克罗地亚|爱尔兰|粤|闽|"
    r"german|deutsch|duden|french|fran[cç]ais|larousse|robert|italian|italiano|zingarelli|spanish|espa[nñ]ol|portug|latin|greek|sanskrit|pali|tibetan|dzongkha|russian|japanese|korean|persian|aryanpur|turkish|dutch|swedish|arabic|hebrew|interlingua|esperanto",
    re.I,
)
# Markers that name both languages outright. Abbreviations must be whole tokens:
# "ce" inside "LDOCE 5" or "zhwikisource" is not "C-E".
_ZH_EXPLICIT = r"英汉|汉英|英漢|漢英|英中|中英|英华|華英|双解|雙解|english[- ]?chinese|chinese[- ]?english|(?<![a-z])(?:e-?c|c-?e)\b|(?<![a-z])(?:en[-_]?zh|zh[-_]?en)(?![a-z])"
EN_ZH_EXPLICIT = re.compile(_ZH_EXPLICIT, re.I)
# Explicit markers plus weaker hints: a Chinese title for an English work is
# usually a bilingual edition.
EN_ZH = re.compile(_ZH_EXPLICIT + r"|红宝书|要你命|背单词|单词|英词|小品词|陆谷孙|新英汉|柯林斯|朗文|牛津|剑桥|劍橋|麦克米伦|韦氏|韋氏|美国传统|金山词霸|有道|词根|詞根|英语|英語|英文", re.I)
# English monolingual: "[英-英]", "英英" (but not "英英汉", an English-English-Chinese work).
# It outranks the weak hints above, never an explicit bilingual marker.
EN_MONO = re.compile(r"英-英|英英(?![汉漢])|english[- ]english", re.I)
# Evidence that a foreign-language work has an English side. Strong: the
# language named. Weak: an English publisher ("Duden-Oxford", "Larousse
# Chambers"), which an explicit language tag without English overrules
# ("[其他语种] 牛津…俄语…" is a Russian work). Generic markers (双解,
# "dictionary of", etymology) say nothing about English.
EN_NAMED = re.compile(r"英|english|anglais|englisch|ingl[eé]s|inglese|engels|(?<![a-z])en(?![a-z])", re.I)
EN_PUBLISHER = re.compile(
    r"oxford|chambers|collins|cobuild|cambridge|longman|macmillan|merriam|webster|牛津|柯林斯|剑桥|劍橋|朗文|麦克米伦|韦氏|韋氏",
    re.I,
)
# A bracketed language tag: "[其他语种]", "[俄语]", "[汉-汉]", "[日汉-汉日]".
LANG_TAG = re.compile(r"\[(?:其他语种|[^\]\d]{1,4}[语語]|[一-鿿]{1,3}-[一-鿿]{1,3}(?:-[一-鿿]{1,3})?)\]")
EN = re.compile(
    r"english|oxford|\bo[a-z]{1,3}d\d*\b|oald|ldoce|longman|collins|cobuild|cambridge|macmillan|merriam|webster|\bmw|chambers|wordnet|thesaurus|roget|urban ?dict|etymolog|idiom|phrasal|heritage|\bahd|random ?house|wiktionary|\bnoad|\bode\b|\boed|lexico|vocab|slang|pronounc|\bcoca\b|\bbnc\b|synonym|collocation|usage|word ?power|dictionary\.com|vocabulary\.com|wordsmyth|encarta|kernerman|\blexi|\bnew ?world|\bfunk|glossary|encyclop|britannica|dictionary of|world ?book|mcgraw|routledge|"
    # Well-known English dictionary abbreviations (optionally followed by an edition number).
    r"(?<![a-z])(oalecd|oaled|oald|oele?d|ode|oed|noad|coed|cod|ldoce|laad|lasecd|lpd|ltae|lla|cald|ccald|ccabeld|cced|cide|medal|med|mwaled|mwc|mw|ahd|rhd|wbd|ncecd|ecd|edec|olcc|phcd|cepd|lec|mwcd|webster)\d*(?![a-z])",
    re.I,
)
EN_FOLDER = re.compile(r"/英语/|Oxford Dictionaries|Collins Dictionaries|Longman Dictionaries|Cambridge Dictionaries|Macmillan Dictionaries|Merriam-Webster|Thesaurus series|Idioms Dictionaries|English-Chinese|Audio And Pronunciation|英汉辞书", re.I)
OTHER_FOLDER = re.compile(r"Foreign Dictionaries|Other language|小语种|/(德|法|俄|日|韩|意大利|西班牙|葡萄牙|拉丁|梵|藏|越南|泰|阿拉伯|波斯|土耳其|荷兰|瑞典|挪威|捷克|满|马来|乌克兰|现代希腊|其他语种)语?/|/汉语/|/百科/|06mdict|医学/|美学", re.I)

# Hand-reviewed names the keyword rules cannot place (mostly bare abbreviations).
# Anything not listed here and not matched by a rule stays "unknown" on purpose.
OVERRIDES = {
    **dict.fromkeys([
        "0ED(20200912)", "Anatomy Diagrams", "BBI Combinatory Dictionary",
        "Black's Medical Dictionary, 43rd Edition", "BusinessDictionary", "ColinsCCAD",
        "ComputerHope", "DErivCelex-v2", "DK Eyewitness Books", "DNB00", "DNB01", "DNB12",
        "Descriptionary v1", "EgyptianMyths.Net 2019", "FOLDOC", "FileInfo.Com 2019",
        "FineDictionary2020", "FineDictionary2020OL", "GCIDE", "Geology Collection",
        "Geology Dictionaries", "Interesting stories to learn proverbs", "LCDT", "LDAE5",
        "McHillDic", "Medical Subject Headings(MeSH)", "Microsoft Computer Dictionary",
        "NOPD", "NetLingo", "OBAD_2", "OELDOnline2020(UK)", "OELDOnline2020(US)",
        "OELDOnlineV1-51", "OLT", "Oxf Thes Eng 2019", "PEU4th", "Phonetic Symbol",
        "Photo Dictionary", "PicDic", "Picture Dictionary", "Reader's Digest Use the Right Word",
        "Shorter Wikitionary", "Sound-En", "Sound", "TFD-ACRONYMS", "TFD-FINANCIAL",
        "TFD-LEGAL", "TFD-MEDICAL", "TFD-TheFreeDictionary", "TechTerms.Com 2019",
        "The Describer's Dictionary - David Grambs & Ellen S. Levine",
        "The Macquarie Dictionary 6th", "TheFreeDictionary(8 IN 1)2020", "UD7.1",
        "WeboPedia", "WhatIsTechTarget", "Word Frequency of 170,000 Words",
        "Word Nerd by Barbara Ann", "Word Web", "Word_18W_Sound", "Wordnik2020",
        "wordnik2020", "WwwDictionaryCom2020", "YourdictionaryQuotesbyPeople",
        "bosworth-toller-mdx3", "friends7", "rg_students", "sound++", "thes",
        "visual_dict", "wn31", "Free-Translator2020", "Microsoft Terminology Collection",
    ], "en-en"),
    **dict.fromkeys([
        "CC-CEDICT", "Microsoft Bing CN-EN Dictionary Online", "Microsoft Bing Dictionary",
        "ODECN", "Wang's_Word_Origins_Enzio", "xsjhy20oct", "xsjhy20oct2", "xsjhy20sep",
        "yuanliudict", "CESCD",
        "collinsec",  # Collins E-C: "ec" fused onto the name
    ], "en-zh"),
    **dict.fromkeys(["Il Ragazzini EN-IT", "Il Ragazzini IT-EN", "camen22ge", "camen2ko"], "en-other"),
    **dict.fromkeys([
        "De-De-Langenscheidt-Vokabeln", "De-De-Langenscheidt-Vokabeln2",
        "Diccionario de la Lengua Española V23", "Il Cinese IT-ZH", "Il Devoto Oli 2020",
        "Souyun2014", "ZHHYD_QT", "biaoxianwenxing", "bruks_v82", "dabkrs_v82",
        "jiaoyubuvariants", "jiaoyubuvariants_updated20191123", "shenmeihande",
        "xsjrihanshuangjie_updated20191123", "yuyanxue", "zhwikibooks-20171001",
        "【2】Langenscheidt-e-DaF", "【3】Wahrig", "표준국어대사전",
    ], "other"),
}


def classify(path: str) -> str:
    parts = path.split("/")
    name, folder = parts[-1], "/" + "/".join(parts[:-1]) + "/"
    stem = unicodedata.normalize("NFC", re.sub(r"\.mdx$", "", name, flags=re.I))
    if stem in OVERRIDES:
        return OVERRIDES[stem]
    zh = EN_ZH.search(stem)
    other = OTHER_LANG.search(stem)
    en = EN.search(stem)
    if other:
        if EN_NAMED.search(stem):
            return "en-other"
        return "en-other" if EN_PUBLISHER.search(stem) and not LANG_TAG.search(stem) else "other"
    mono = EN_MONO.search(stem) and not EN_ZH_EXPLICIT.search(stem)
    if zh:
        return "en-en" if mono else "en-zh"
    if en:
        return "en-zh" if re.search(r"[一-鿿]", stem) and re.search(r"英", stem) and not mono else "en-en"
    if EN_FOLDER.search(folder):
        return "en-zh" if re.search(r"英汉|英-汉|汉-英|汉英|English-Chinese|双向|英汉辞书", folder) else "en-en"
    if OTHER_FOLDER.search(folder):
        return "other"
    if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", stem):
        return "other"  # CJK name with no English marker: Chinese/Japanese-only work
    return "unknown"

