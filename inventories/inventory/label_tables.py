"""The label tables: the printed forms of each axis's values (register, attitude, time,
frequency, region, language, use, author, form, kind), the noise words that are not labels, and
the subject-field domains with their abbreviations. inventory/labels.py reads a label against
these; grammar is in label_grammar.py, the Chinese abbreviations in label_zh.py.
"""
from __future__ import annotations

import re
from typing import NamedTuple


class Label(NamedTuple):
    axis: str
    value: str


def _pairs(axis: str, table: str, sep: str = ",") -> dict[str, tuple[Label, ...]]:
    """Parse "value: key1, key2 | value: key3" into {key: (Label(axis, value),)}."""
    out = {}
    for entry in table.split("|"):
        value, _, keys = entry.partition(":")
        if "\n" in value.strip() or ":" in keys:
            raise ValueError(f"{axis} table: an entry is missing its '|': {entry.strip()[:60]!r}")
        for key in (" ".join(k.split()) for k in keys.split(sep)):
            if not key:
                continue
            label = (Label(axis, value.strip()),)
            if out.get(key, label) != label:  # a key given two values: a separator inside a key, usually
                raise ValueError(f"{axis} table: {key!r} is both {out[key][0].value!r} and {value.strip()!r}")
            out[key] = label
    return out


REGISTER = _pairs("register", """
    informal: informal, inf, colloquial, colloq, familiar, fam, very informal, not formal |
    slang: slang, sl, cant, argot, underworld slang, criminal slang, prison slang, schoolboy slang, school slang,
        thieves' cant, rhyming slang,
        cockney rhyming slang, cockney rhyming sl, rhyming sl, black slang, criminals' slang, criminal sl, milit sl,
        mil sl, services' slang, services slang |
    vulgar: vulgar, vulg, coarse, coarse slang, vulgar slang, vulgar sl, crude, very rude |
    taboo: taboo |
    formal: formal, fml, very formal |
    literary: literary, poetic/literary, bookish |
    poetic: poetic, poet, poetry, in poetry |
    technical: technical, specialist, specialized, specialised, tech, term, jargon, commercial jargon |
    spoken: spoken, speech, in speech |
    written: written, in writing |
    nonstandard: non-standard, nonstandard, not standard, substandard, usage problem, often considered nonstandard, incorrect,
        illiterate, uneducated |
    child: child's word, children's word, baby talk, used by children, used to children, nursery, childish |
    journalism: journalism, journalese, journalistic |
    euphemistic: euphemistic, euph, euphemism |
    legal: legal |
    business: business english""")
ATTITUDE = _pairs("attitude", """
    approving: approving, approval, approv, appreciative |
    disapproving: disapproving, disapproval, derogatory, derog, pejorative, pejor, depreciative, depreciatory,
        contemptuous, disparaging, deprecating, often disparaging, usually disparaging, often derogatory, abusive |
    humorous: humorous, facetious, facetiously, jocular, jocularly, joc, humorously, often humorous, ironic humorous,
        playful, jokey |
    ironic: ironic, ironical, ironically, sarcastic |
    offensive: offensive, often offensive, offensive slang, often offensive slang, insulting, racist, very offensive,
        ethnic slur, slur |
    emphasis: emphasis, emphatic, intensifier |
    rude: rude, not polite, impolite |
    feelings: feelings |
    vague: vague, vagueness |
    polite: politeness, polite, formal politeness""")
TIME = _pairs("time", """
    dated: dated, old-fashioned, old, becoming old-fashioned, rather old-fashioned, somewhat dated |
    archaic: archaic, arch, archaism, antiquated, pseudo-archaic, old use |
    obsolete: obsolete, obs, †, now obsolete, no longer used, disused |
    historical: historical, hist, historic, in historical use, in former times, formerly, early |
    new: new, neologism, recent""")
FREQUENCY = _pairs("frequency", "rare: rare, now rare, rarely, very rare, uncommon, seldom, infrequent")
REGION = _pairs("region", """
    GB: british, british english, brit, bre, br, uk, gb, britain, in britain, england, english, in england, in the uk,
        sw eng, south-western, english regional (east anglian), east anglia, manx english,
        english midlands, english regional (south-western), oxford university, cambridge university,
        british and irish, british isles, english regional |
    US: us, u.s, american, american english, ame, am, usa, united states, in the us, us english, amer |
    NAm: north american, north american english, n. amer, n amer, n american, nam, name, n am, north america,
        n. american, north amer |
    CA: canadian, canadian english, canada, can, and canadian, canad, newfoundland |
    AU: australian, australian english, australia, aust, austral, aus, australian slang, australe |
    NZ: new zealand, nz, n.z, new zealand english, nze |
    IE: irish, irish english, ireland, anglo-irish, hiberno-english, ir |
    SC: scottish, scot, scots, scotland, scottish english, scote, sc, shetland, orkney, orkney and shetland |
    ZA: south african, south africa, s. african, s afr, s african, south african english, safr, safre |
    IN: indian, indian english, india, anglo-indian, hinglish, ind, inde |
    CARIB: caribbean, west indian, west indies, jamaica, jamaican, caribbean english, w. indian, w indies, w indian |
    WAL: welsh, wales, south wales |
    N-ENG: northern england, northern english, north of england, northern, north, northeast england, n eng,
        n. english, n english, scottish & n. english,
        yorkshire, lancashire, west yorkshire |
    AFR: africa, east africa, west africa, east african english, west african english, african |
    PH: philippines, philippine english |
    IT: italy |
    S-ASIA: south asian, east india, south asia |
    US-regional: west, southwest, south, midland, south & midland, southern & midland, north & midland, new england,
        upper midwest, northeast, northwest, southern, chiefly midland, chiefly new england, new orleans, louisiana,
        alaska, hawaii, southwestern us |
    dialect: dialect, dialectal, dial, regional, local, provincial, chiefly dialect, chiefly dialectal,
        northern dialect, southern dialect""")  # "dialect british": dialect and GB, read as two
LANGUAGE = _pairs("language", """
    Latin: latin, lat, l, new latin |
    French: french, fr |
    German: german, ger, g |
    Italian: italian, ital, it |
    Spanish: spanish, sp, span |
    Greek: greek, gr |
    Dutch: dutch, du |
    Portuguese: portuguese, port |
    Russian: russian, russ |
    Afrikaans: afrikaans |
    Yiddish: yiddish |
    Hindi: hindi |
    Japanese: japanese, jap |
    Chinese: chinese |
    Arabic: arabic, arab |
    Hebrew: hebrew, heb""")
USE = _pairs("use", """
    figurative: figurative, fig, figuratively, transferred, transf, in extended use, extended use, extended,
        transferred and figurative, figurative and in extended use, by extension, metaphorical, in figurative use |
    literal: literal, literally, lit |
    generic: gen, general, in general use |
    specific: spec, specifically, specific, properly, strictly |
    loose: loosely, loose, popularly, erroneous, erroneously, by confusion |
    figurative: figurative and in figurative contexts, in figurative context, all figurative, personified |
    nonce: nonce-word, nonce word, nonce |
    concrete: concrete, concretely |
    elliptical: elliptical, ellipt, elliptically |
    allusive: allusively, allusive""")
AUTHOR = {a: (Label("author", a),) for a in """shakespeare spenser milton burns keats dickens tennyson browning carlyle
    dryden jonson byron wordsworth coleridge shelley pope swift bacon bunyan thackeray sterne austen fielding kipling
    goldsmith scott lamb herrick cowper southey congreve hardy ruskin sheridan homer walton richardson gray boswell
    berkeley""".split()}
AUTHOR.update({"walter scott": (Label("author", "scott"),), "shakesp": (Label("author", "shakespeare"),),
               "sir walter scott": (Label("author", "scott"),), "bible": (Label("domain", "religion"),)})
FORM = _pairs("form", """
    capitalized: capitalized, capital, often capitalized, usually capitalized, often capital, cap, caps,
        sometimes capitalized, also capitalized, initial capital |
    lowercase: often not capitalized, not capitalized, lowercase, lower case |
    abbreviation: abbreviation, abbr, abbrev |
    plural form: plural in form |
    lowercase: sometimes not capital, often lower case, often not capital, sometimes not capitals |
    capitalized: often capitals, sometimes capitals, capital when part of a name, the c- |
    contraction: 缩约形式, contraction, contracted form |
    third person: third person singular, 3rd person singular |
    first person: first person plural, first person singular |
    combining: in combination, usu. in combination, often in combination, usually in combination,
        attributive and in other combinations, combining form, in comb, combined with adverbs, in adjectives, in nouns,
        in adverbs, in verbs, comb, in combination""")
KIND = _pairs("kind", """
    trademark: trademark, tm, proprietary name, proprietary term, trade name |
    form of address: as form of address, form of address, as a form of address, vocative |
    in names: in names, oft in names, in place names, often in names, usu in names |
    formula: formulae, formula |
    saying: saying, proverb, prov, proverbial, idiom, maxim, proverbs |
    title: as title, title |
    exclamation: exclamation, interjection, exclam, in imprecations, imprecation""")
NOISE = frozenset("""compounds phrases other c- double double- good α β γ δ ε ζ η θ (a) (b) (c) (d) (e) (f)
    (g) i. ii. iii. or and usually chiefly also esp especially mainly often sometimes now orig
    originally derivatives derivative see note usage with usu""".split()) | frozenset({
    "in some classifications", "in former classifications", "general sense", "general arrangement of senses",
    "orig, and still and", "of a book usu; other senses", "also without"})

# Domains: subject fields, lowercase; abbreviations and variants point to them.
_DOMAINS = """
    accounting, advertising, aeronautics, aerospace, agriculture, algebra, american football, anatomy, angling,
    anthropology, archaeology, archery, architecture, arithmetic, art, astrology, astronautics, astronomy, athletics,
    australian rules football, automobiles, aviation, ballet, banking, baseball, basketball, bell-ringing,
    billiards, biochemistry, biology, biotechnology, botany, bowling, bowls, boxing, bridge, buddhism, building,
    business, calculus, cards, carpentry, cartography, chemistry, chess, christianity, christian theology,
    church history, cinematography, civil engineering, climbing, clothing, commerce, computing, construction,
    cookery, cosmetics, cricket, croquet, crystallography, cycling, dance, darts, dentistry, ecclesiastical,
    ecology, economics, education, electrical engineering, electricity, electronics, embryology, engineering,
    english law, entomology, environment, ethics, falconry, farming, fashion, fencing, film, finance, fishing,
    football, forestry, freemasonry, furniture, gambling, games, gardening, genetics, geography, geology,
    geometry, geophysics, golf, government, grammar, greek history, greek mythology, gymnastics, heraldry,
    hinduism, history, hockey, horse racing, horticulture, hunting, hydraulics, ice hockey, immunology,
    information technology, insurance, internet, islam, jewellery, journalism, judaism, knitting, language, law,
    linguistics, literature, logic, management, manufacturing, marketing, mathematics, mechanical engineering,
    mechanics, medicine, metallurgy, meteorology, microbiology, military, military history, mineralogy, mining,
    motor racing, mountaineering, music, mythology, nautical, naval, navigation, needlework, nuclear physics,
    numismatics, nursing, oceanography, optics, ornithology, palaeontology, pathology, pharmacology, pharmacy,
    philately, philosophy, phonetics, photography, physical geography, physics, physiology, poetry, politics,
    printing, prosody, psychiatry, psychoanalysis, psychology, publishing, radio, railways, real estate,
    religion, rhetoric, riding, roman catholic church, roman history, roman law, roman mythology, rowing, rugby,
    sailing, science, scots law, sculpture, shipping, skating, skiing, snooker, soccer, sociology, soil science,
    space, sports, statistics, stock exchange, surfing, surgery, surveying, swimming, technology,
    telecommunications, television, tennis, textiles, theatre, theology, topology, trade, transport, typography,
    veterinary medicine, video games, weightlifting, wrestling, yoga, zoology, ancient greek history,
    chemical engineering, fishing, horse riding, astrophysics, virology, toxicology, paleobotany, zoogeography,
    hydrology, glaciology, seismology, volcanology, horology, lexicography, semantics, phonology, morphology,
    syntax, geomorphology, petrology, histology, cytology, neurology, cardiology, dermatology, obstetrics,
    gynaecology, ophthalmology, orthopaedics, paediatrics, radiology, psychotherapy, anaesthesiology,
    bacteriology, mycology, herpetology, ichthyology, mammalogy, genealogy, graphics, electrical, mechanical,
    """
DOMAIN: dict[str, tuple[Label, ...]] = {
    d: (Label("domain", d),) for d in (x.strip() for x in _DOMAINS.split(",")) if d}
_ALIASES = {
    "med": "medicine", "medical": "medicine", "chem": "chemistry", "bot": "botany", "zool": "zoology",
    "anat": "anatomy", "math": "mathematics", "maths": "mathematics", "mus": "music", "naut": "nautical",
    "electr": "electricity", "elec": "electricity", "comput": "computing", "phys": "physics", "biol": "biology",
    "geol": "geology", "astron": "astronomy", "archit": "architecture", "mil": "military", "econ": "economics",
    "philos": "philosophy", "psychol": "psychology", "ling": "linguistics", "gram": "grammar", "theol": "theology",
    "eccles": "ecclesiastical", "hort": "horticulture", "photog": "photography", "pathol": "pathology",
    "physiol": "physiology", "pharm": "pharmacology", "agric": "agriculture", "archaeol": "archaeology",
    "surg": "surgery", "stats": "statistics", "telecom": "telecommunications", "rc": "roman catholic church",
    "rc church": "roman catholic church", "christian church": "christianity", "church": "christianity",
    "roman catholicism": "roman catholic church", "sports & games": "games", "sport": "sports",
    "computers": "computing", "theater": "theatre", "paleontology": "palaeontology", "jewelry": "jewellery",
    "gr myth": "greek mythology", "greek & roman mythology": "mythology", "track & field": "athletics",
    "stock market": "stock exchange", "cinema": "film", "cooking": "cookery", "motorsports": "motor racing",
    "auto racing": "motor racing", "gr hist": "greek history", "roman hist": "roman history", "eng law": "english law",
    "old testament": "religion", "new testament": "religion", "prayer book": "religion",
    "tv": "television", "elec eng": "electrical engineering", "nuclear eng": "nuclear physics",
    "image technol": "photography", "horse-racing": "horse racing", "veterinary science": "veterinary medicine",
    "natural history": "biology", "go": "games", "poker": "cards", "motoring": "automobiles", "alchemy": "chemistry",
    "fortification": "military", "bookkeeping": "accounting", "property law": "law", "social welfare": "sociology",
    "oil industry": "industry", "coal mining": "mining", "farriery": "riding", "founding": "metallurgy",
    "jazz": "music", "police": "law", "folklore": "mythology", "navy": "military", "firearms": "military",
    "science fiction": "literature", "association football": "football", "telegraphy": "telecommunications",
    "telephony": "telecommunications", "dressage": "riding", "communications": "telecommunications",
    "tax": "finance", "civil eng": "civil engineering", "nuclear phys": "nuclear physics", "badminton": "sports",
    "social sciences": "sociology", "industrial relations": "business", "radar": "electronics", "press": "journalism",
    "oil": "industry", "currency": "finance", "biblical": "religion", "min": "mineralogy", "pharmacol": "pharmacology",
    "biochem": "biochemistry", "masonry": "building", "armour": "military", "judo": "sports", "army": "military",
    "whist": "cards", "ancient hist": "ancient history", "messaging & social media": "internet",
    "roman & civil law": "roman law", "literary theory": "literature", "church of england": "christianity",
}
# A title-case or lowercase name of a field that no table lists: "Cell Biology", "Coal Mining".
_FIELD = re.compile(r"^(?:[a-z-]+ )*(?:[a-z-]*(?:ology|ography|graphy|phony|sophy|onomy|ics|ery|istry|ing|ism|craft|ure|smithing)|"
                    r"history|law|science|engineering|physics|chemistry|biology|industry|medicine|mythology|"
                    r"church|theology|anthropology|trade|technology|arts|art|sport|sports|games|racing|"
                    r"religion|studies|economy|design)$")
for _alias, _name in _ALIASES.items():
    DOMAIN[_alias] = (Label("domain", _name),)
