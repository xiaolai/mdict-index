"""Chinese labels: the Chinese abbreviations ("美口" = 美 + 口), with the Chinese keys the other
tables hold, read greedily, longest first, by `_chinese`. The key map is built from
label_tables and label_grammar (the tables inventory/labels.py reads), so this module does not
import labels.
"""
from __future__ import annotations

import re

from inventory.label_grammar import GRAMMAR
from inventory.label_tables import (ATTITUDE, AUTHOR, DOMAIN, FORM, FREQUENCY, KIND, LANGUAGE, REGION, REGISTER,
                                    TIME, USE, Label)

# Chinese abbreviations, read greedily, longest first: "美口" = 美 + 口.
_ZH = {
    # region
    "美": ("region", "US"), "英": ("region", "GB"), "澳": ("region", "AU"), "新西兰": ("region", "NZ"),
    "新": ("region", "NZ"), "加拿大": ("region", "CA"), "加": ("region", "CA"), "苏格兰": ("region", "SC"),
    "苏": ("region", "SC"), "爱尔兰": ("region", "IE"), "爱": ("region", "IE"), "南非": ("region", "ZA"),
    "印度": ("region", "IN"), "北美": ("region", "NAm"), "英格兰北部": ("region", "N-ENG"), "英格兰": ("region", "GB"),
    "方": ("region", "dialect"), "方言": ("region", "dialect"),
    # register, attitude, time, use
    "口": ("register", "informal"), "非正式": ("register", "informal"), "口语": ("register", "informal"),
    "俚": ("register", "slang"), "俚语": ("register", "slang"), "粗": ("register", "vulgar"),
    "粗俗": ("register", "vulgar"), "忌": ("register", "taboo"), "禁忌语": ("register", "taboo"),
    "正式": ("register", "formal"), "书": ("register", "literary"), "文": ("register", "literary"),
    "书面语": ("register", "literary"), "诗": ("register", "poetic"), "诗歌": ("register", "poetic"),
    "术语": ("register", "technical"), "儿": ("register", "child"), "儿语": ("register", "child"),
    "婉": ("register", "euphemistic"), "讳": ("register", "euphemistic"), "委婉": ("register", "euphemistic"),
    "褒": ("attitude", "approving"), "贬": ("attitude", "disapproving"), "蔑": ("attitude", "offensive"),
    "冒犯": ("attitude", "offensive"), "侮": ("attitude", "offensive"), "谑": ("attitude", "humorous"),
    "幽默": ("attitude", "humorous"), "诙谐": ("attitude", "humorous"), "反语": ("attitude", "ironic"),
    "旧": ("time", "dated"), "过时": ("time", "dated"), "古": ("time", "archaic"), "古语": ("time", "archaic"),
    "废": ("time", "obsolete"), "废语": ("time", "obsolete"), "史": ("time", "historical"),
    "罕": ("frequency", "rare"), "罕用": ("frequency", "rare"), "喻": ("use", "figurative"),
    "比喻": ("use", "figurative"), "谚": ("kind", "saying"), "谚语": ("kind", "saying"), "商标": ("kind", "trademark"),
    # language of origin
    "拉": ("language", "Latin"), "法": ("language", "French"), "德": ("language", "German"),
    "意": ("language", "Italian"), "西": ("language", "Spanish"), "希": ("language", "Greek"),
    "俄": ("language", "Russian"), "日": ("language", "Japanese"),
    # grammar
    "复": ("grammar", "N plural"), "用作单": ("grammar", "N plural, sing verb"),
    "用作单或复": ("grammar", "N plural, sing/pl verb"), "单复同": ("grammar", "N sing=plural"),
    "常用被动语态": ("grammar", "usu passive"), "总称": ("grammar", "N coll"),
    # domains
    "医": "medicine", "化": "chemistry", "植": "botany", "动": "zoology", "生": "biology", "物": "physics",
    "律": "law", "法律": "law", "宗": "religion", "音": "music", "数": "mathematics", "计": "computing",
    "军": "military", "建": "architecture", "海": "nautical", "生化": "biochemistry", "政": "politics",
    "解": "anatomy", "解剖": "anatomy", "语": "linguistics", "语言": "linguistics", "语法": "grammar",
    "体": "sports", "矿": "mining", "地": "geology", "地质": "geology", "地理": "geography", "印": "printing",
    "心": "psychology", "哲": "philosophy", "机": "mechanics", "病理": "pathology", "鸟": "ornithology",
    "商": "commerce", "烹": "cookery", "纺": "textiles", "药": "pharmacology", "电子": "electronics",
    "电": "electricity", "昆": "entomology", "金融": "finance", "天": "astronomy", "天文": "astronomy",
    "经": "economics", "生理": "physiology", "农": "agriculture", "教育": "education", "逻": "logic",
    "鱼": "zoology", "摄": "photography", "冶": "metallurgy", "艺术": "art", "气": "meteorology",
    "神话": "mythology", "希神": "greek mythology", "罗神": "roman mythology", "北欧神": "mythology",
    "空": "aviation", "航空": "aviation", "电信": "telecommunications", "板": "cricket", "棒": "baseball",
    "牌": "cards", "圣经": "religion", "神学": "theology", "遗": "genetics", "遗传": "genetics", "统": "statistics",
    "统计": "statistics", "核": "nuclear physics", "戏剧": "theatre", "电影": "film", "电视": "television",
    "会计": "accounting", "古生": "palaeontology", "考古": "archaeology", "人类": "anthropology", "社": "sociology",
    "社会": "sociology", "生态": "ecology", "兽医": "veterinary medicine", "手术": "surgery", "外科": "surgery",
    "高尔夫": "golf", "足": "football", "足球": "football", "美橄": "american football", "橄": "rugby",
    "股": "stock exchange", "服": "clothing", "船": "shipping", "铁": "railways", "渔": "fishing", "猎": "hunting",
    "工": "engineering", "无": "radio", "汽车": "automobiles", "微": "microbiology", "言语": "linguistics",
    "网球": "tennis", "篮": "basketball", "篮球": "basketball", "拳": "boxing", "拳击": "boxing", "马": "riding",
    "赛马": "horse racing", "板球": "cricket", "棒球": "baseball", "桥牌": "bridge", "象棋": "chess",
    "纹": "heraldry", "纹章": "heraldry", "建筑": "architecture", "晶": "crystallography", "矿物": "mineralogy",
    "声": "physics", "光": "optics", "力": "mechanics", "热": "physics", "水": "hydraulics", "测": "surveying",
    "园艺": "horticulture", "园": "horticulture", "动画": "film", "广告": "advertising", "新闻": "journalism",
    "出版": "publishing", "邮": "philately", "邮政": "trade", "宇航": "astronautics", "航海": "nautical",
    "气象": "meteorology", "数学": "mathematics", "物理": "physics", "化学": "chemistry", "生物": "biology",
    "医学": "medicine", "植物": "botany", "动物": "zoology", "宗教": "religion", "音乐": "music",
    "计算机": "computing", "军事": "military", "经济": "economics", "哲学": "philosophy", "心理": "psychology",
    "天主教": "roman catholic church", "基督教": "christianity", "伊斯兰教": "islam", "佛教": "buddhism",
    "犹太教": "judaism", "印度教": "hinduism", "史学": "history", "历史": "history", "数理": "mathematics",
    "文学": "literature", "无线电": "radio", "传媒": "journalism", "缝": "needlework", "缝纫": "needlework",
    "铁路": "railways", "舞": "dance", "舞蹈": "dance", "棋": "games", "保险": "insurance", "游戏": "games",
    "网": "internet", "网络": "internet", "航天": "astronautics", "货币": "finance", "营销": "marketing",
    "科学": "science", "酿酒": "brewing", "马术": "riding", "戏": "theatre", "税": "finance", "占星": "astrology",
    "制陶": "pottery", "测绘": "surveying", "修辞": "rhetoric", "测量": "surveying", "滑雪": "skiing",
    "珠宝": "jewellery", "林": "forestry", "林业": "forestry", "摔": "wrestling", "田径": "athletics",
    "军-防御工事": "military", "防御工事": "military", "短信": "telecommunications", "行业": ("register", "technical"),
    "加勒比": ("region", "CARIB"), "汉": ("language", "Chinese"), "非标准": ("register", "nonstandard"),
    "作定语": ("grammar", "~ n"), "构成名词": ("form", "combining"), "构成形容词": ("form", "combining"),
    "常用以构成复合词": ("form", "combining"), "构成复合词": ("form", "combining"), "美方": ("region", "US"),
    "用在元音字母前": ("grammar", "before vowel"), "用在辅音字母前": ("grammar", "before consonant"),
    "一般作表语": ("grammar", "v-link ADJ"), "作表语": ("grammar", "v-link ADJ"),
    "用作复": ("grammar", "N sing, pl verb"),
    "常用于否定句": ("grammar", "with negative"), "用于否定句": ("grammar", "with negative"),
    "用以加强语气": ("attitude", "emphasis"), "讽": ("attitude", "ironic"), "非术语": ("register", "informal"),
    "非规范": ("register", "nonstandard"), "用以构成复合词": ("form", "combining"), "用以构成名词": ("form", "combining"),
    "用以构成形容词": ("form", "combining"), "希伯来": ("language", "Hebrew"), "美国史": ("time", "historical"),
    "冰": "ice hockey", "画": "art", "绘画": "art", "木工": "carpentry", "登山": "mountaineering", "时装": "fashion",
    "射箭": "archery", "传说": "mythology", "击剑": "fencing", "因特网": "internet", "海洋": "oceanography",
    "火炮学": "military", "牧": "agriculture", "佛": "buddhism", "芭蕾舞": "ballet", "染色工艺": "textiles",
    "细菌学": "bacteriology", "体操": "gymnastics", "集邮": "philately", "织": "textiles",
    "文艺": "literature", "制": "manufacturing", "交": "transport", "交通": "transport",
    "射击": "shooting", "武": "military", "免疫": "immunology", "产科学": "obstetrics", "纸": "papermaking",
    "罗马法": "roman law", "赌博": "gambling", "商标名": ("kind", "trademark"), "书面": ("register", "literary"),
    "泳": "swimming", "羽": "badminton", "葡": ("language", "Portuguese"), "古玩": "antiques", "陶器": "pottery",
    "用作插入语": ("grammar", "parenthetical"), "定冠词": ("grammar", "as DET"), "常用复": ("grammar", "usu N plural"),
    "有时用作单": ("grammar", "N plural, sing verb"), "常用作定语": ("grammar", "~ n"),
    "用作表语形容词时": ("grammar", "v-link ADJ"), "常用于祈使句": ("grammar", "imperative"),
    "化妆品": "cosmetics", "北爱尔兰": ("region", "IE"), "美国": ("region", "US"), "美国州名": ("kind", "in names"),
}
_ZH_QUALIFIERS = ("主", "尤", "常", "多", "亦")
_CJK = re.compile("[㐀-鿿]")


def _zh_labels() -> dict[str, Label]:
    """The Chinese abbreviations, and the Chinese keys the other tables hold (缩约形式): a
    Chinese label is read only from these."""
    out = {k: (Label("domain", v) if isinstance(v, str) else Label(*v)) for k, v in _ZH.items()}
    for table in (REGISTER, ATTITUDE, TIME, FREQUENCY, REGION, LANGUAGE, USE, AUTHOR, FORM, KIND, GRAMMAR, DOMAIN):
        for key, labels in table.items():
            if not _CJK.search(key):
                continue
            if len(labels) != 1 or out.get(key, labels[0]) != labels[0]:
                raise ValueError(f"Chinese label {key!r}: {labels} beside {out.get(key)}")
            out[key] = labels[0]
    return out


_ZH_LABELS = _zh_labels()
_ZH_KEYS = sorted(_ZH_LABELS, key=len, reverse=True)


_ZH_SEPARATORS = "或，、-"


def _chinese(label: str) -> tuple[Label, ...] | None:
    """Chinese abbreviations, read greedily; "古或方" and "军-火炮学" are two labels, but a known
    label with 或 inside is one, whatever else is printed beside it ("美用作单或复，口": 美 +
    用作单或复 + 口)."""
    text = re.sub(r"[\s〈〉〔〕()（）\[\]]", "", label)
    if re.fullmatch(r"[亦常]作[A-Za-z]-", text):  # 亦作 M-: also written with a capital
        return (Label("form", "capitalized"),)
    if text in _ZH_LABELS:
        return (_ZH_LABELS[text],)
    return _chinese_tokens(text)


def _chinese_tokens(text: str) -> tuple[Label, ...] | None:
    """Known abbreviations side by side, longest first, a separator between them or none; None
    when a stretch matches none. A separator is one only where no label starts: cutting at every
    或 first would cut the labels that hold one."""
    out: list[Label] = []
    while text:
        stretch = re.split(f"[{_ZH_SEPARATORS}]", text, maxsplit=1)[0]  # up to the next separator
        if text.startswith(_ZH_QUALIFIERS) and len(stretch) > 1 and stretch not in _ZH_LABELS:
            text = text[1:]
            continue
        key = next((k for k in _ZH_KEYS if text.startswith(k)), None)
        if key is None and text[0] in _ZH_SEPARATORS:
            text = text[1:]
            continue
        if key is None:
            return None
        out.append(_ZH_LABELS[key])
        text = text[len(key):]
    return tuple(out) or None
