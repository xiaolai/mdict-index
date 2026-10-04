"""Oxford Advanced Learner's English-Chinese Dictionary, 9th edition (OALECD9, 牛津高阶双解 9).

MDict v1.2 build whose markup is Oxford's own XML vocabulary served as custom tags
(no classes): every word is wrapped in <xhtml:a>, which lxml keeps as a literal
tag name, so this parser walks tags by name and never uses XPath on "xhtml:*".

Entry shapes (the root's first element):
  h-g                  a single-part entry
  div.cixing_part      one per part of speech ("take": verb, noun), preceded by a
                       div.cixing_tiaozhuan jump list that is navigation only
  idm-g / pv-g         a standalone idiom / phrasal-verb entry (headword = the phrase)
Inside a part:
  top-g > h            headword (syllable dots "·"), h > hm = homograph number
  pron(-gs) > pron-g-blk > brelabel|namelabel, a[href^=sound://] > audio-gb|audio-us,
                       phon = the IPA (no slashes inside phon); pronform ("strong form")
                       and pronfreq > q ("also") are its printed qualifier (Pron.note)
  pos-g > pos          part of speech; several ("adverb, preposition") share the part's senses
  top-g > gram-g, label-g   labels printed with the headword ([U], business): labels of every
                       ordinary sense of the part (a label inside v-gs / if-gs / res-g is that form's)
  res-g > vp-gs > vp-g[form] > vp      verb forms (form="root" is the headword)
  if-gs > if           irregular inflections;  v-gs > v   variant spellings
  sn-gs > sn-blk > xhtml:ol[@start] > ... > sn-g     numbered sense (number = @start)
          sn-blk-nolist > sn-g                        unnumbered sense
  sn-g > gram-g > gram ([C], [T]),  label-g > geo|reg|subj (register / region labels)
         def (English words, then chnsep + chn = Chinese gloss); a sense with no def
         defines itself by use-blk > use ("used in negative sentences ..."), which is
         then taken as the definition; one entry (SFX) wraps its sn-g inside a def
         x-gs > x-g-blk > x (English, then chn = Chinese translation)
  idm-gs > idm-g > top-g > idm (one or more, idm-l) + sn-gs     idioms
  pv-gs > pvp-g > pv-g > top-g > pv + sn-gs                      phrasal verbs
  dr-gs > dr-g > top-g > dr (+ pos inside pron) + sn-gs          derivatives

Normalisation: headword, forms and phrases drop the syllabification dot "·" and the
stress marks "ˈ ˌ", and "↔" (particle may move) becomes a space; these are
typography, not spelling, and keeping them would break joins with the headword
index ("abo·ri·ginal" is headword "aboriginal"). Every other string is as printed.

Homographs: every numbered homograph in this build shares one MDict entry with its
siblings ("bass" 1 and 2), so `homograph` is filled only when the entry carries
exactly one number, which in practice never happens; the hm digits are still kept
out of the headword.

Left in layer 1: side boxes (unbox: synonyms, which-word, more-about;
unbox_wordfinder, unbox_morelikethis, span.unbox, aunbox), help notes (un),
cross-references (xr-gs, div.seealso), topic tags, the short-cut group headers
(shcut), the disambiguators (dis-g), use-blk when a def is present, collocation
frames (cf), full forms / abbreviations / symbols (v-gs-blk types ff, ab, sym, alt),
pictures, and the example audio. The dictionary has no etymology.

Stubs: a record with no definition is marked by the pointer its senses carry instead:
"inflection" (xr-gs xt ptof/plof/ppof/presptof/ptppof: "past tense of choose"), "xref"
(xt eq/defat/ffndv/see/cp: "= burka", "➡ in absentia"; 87 of them still carry examples,
which are parsed), or "empty" (no def or example at all: the empty duplicate record
"-an" beside "-ian, -an").

Coverage (full run, 54,563 records): 2,028 stubs (xref 1,813, inflection 192, empty 23);
all 52,535 content records are covered (1.0). Uncovered records were read by hand
before being classed (burqa, Cdre, admin, MSM, -acy, -d, sportswoman, SFX, ...).
"""
from __future__ import annotations

import copy
import re

from structured.markup import clean, parse as parse_html, text
from structured.model import Entry, Example, Pron, Sense

KEY = "oalecd"
COVERS = "definitions"
MIN_COVERAGE = 0.99

# subtrees whose content never belongs to a sense of the entry it sits in
_BOXES = frozenset({"unbox", "unbox_wordfinder", "unbox_morelikethis", "aunbox", "un",
                    "shcut-blk", "boxblock"})
# tags stripped out of an English string (Chinese, audio, markers, index anchors)
_NOT_EN = frozenset({"chn", "chnsep", "audio-wr", "xsymb", "symbol", "hkey", "ftindex", "fthzindex",
                     "fthzmark", "drtri", "hm", "homonym"})
_GROUPS = frozenset({"idm-g", "pv-g", "dr-g"})
# (group tag, the tag of its heading, the kind of its senses)
_GROUP_KINDS = (("idm-g", "idm", "phrase"), ("pv-g", "pv", "phrasal_verb"), ("dr-g", "dr", "derivative"))
# blocks printing another form of the word; a label inside one ("NAmE also") is that form's, not the entry's
_FORM_BLOCKS = frozenset({"v-gs-blk", "v-gs", "if-gs-blk", "if-gs", "res-g"})
# v-gs-blk types that are spellings of the headword; "ff" full form, "ab" abbreviation,
# "sym" symbol and "alt" (a sense-specific alternative) are other words
_VARIANT_TYPES = frozenset({"vs", "vf"})
_SPELLING = re.compile(r"[·ˈˌ]")
# xr-gs types that stand in for a definition: "past tense of X" / "= X", "➡ X", "X (full form)"
_INFLECTION_XT = frozenset({"ptof", "plof", "ppof", "presptof", "ptppof"})
_POINTER_XT = frozenset({"eq", "defat", "ffndv", "see", "cp"})


def _is_box(el) -> bool:
    return el.tag in _BOXES or (el.tag == "span" and "unbox" in (el.get("class") or "").split())


def _inside(el, stop, tags=frozenset()) -> bool:
    """Whether `el` has an ancestor (below `stop`) that is a box or one of `tags`."""
    p = el.getparent()
    while p is not None and p is not stop:
        if p.tag in tags or _is_box(p):
            return True
        p = p.getparent()
    return False


def _under(scope, tag: str, exclude=frozenset()):
    """Descendants of `scope` named `tag` that are not inside a box or an `exclude` tag."""
    return [el for el in scope.iter(tag) if el is not scope and not _inside(el, scope, exclude)]


def _en(el) -> str:
    """English text of `el`: its text without Chinese, audio, markers and boxes."""
    if el is None:
        return ""
    el = copy.deepcopy(el)
    for bad in [e for e in el.iter() if isinstance(e.tag, str) and (e.tag in _NOT_EN or _is_box(e)) and e is not el]:
        if bad.getparent() is not None:
            bad.drop_tree()
    return text(el)


def _zh(el) -> str:
    if el is None:
        return ""
    parts = [text(c) for c in el.iter("chn") if not _inside(c, el)]
    return clean(" ".join(p for p in parts if p))


def _spelling(value: str) -> str:
    return clean(_SPELLING.sub("", value).replace("↔", " "))


def _labels(scope, stop_at_senses: bool) -> list[str]:
    """gram and label-g labels of `scope`, not those of examples, nested groups, senses or other forms."""
    exclude = {"x-gs", "def"} | _GROUPS | _FORM_BLOCKS
    if stop_at_senses:
        exclude |= {"sn-gs"}
    out: list[str] = []
    for el in scope.iter("gram", "label-g"):
        if _inside(el, scope, exclude):
            continue
        if el.tag == "gram":
            values = [_en(el).strip("[],; ")]
        else:
            values = _label_group(el)
        for v in values:
            if v and v not in out:
                out.append(v)
    return out


def _label_group(label_g) -> list[str]:
    """The labels of one label-g; an <or> joins its neighbours into one label ("old-fashioned or humorous")."""
    out: list[str] = []
    joining = False
    for c in label_g:
        if not isinstance(c.tag, str):
            continue
        if c.tag == "or":
            joining = bool(out)
        elif value := _en(c).strip(",;() "):
            if joining:
                out[-1] = f"{out[-1]} or {value}"
            else:
                out.append(value)
            joining = False
    return out


def _number(sn) -> str:
    p = sn.getparent()
    while p is not None and p.tag not in _GROUPS | {"sn-gs"}:
        if p.tag == "xhtml:ol":
            return clean(p.get("start") or "")
        p = p.getparent()
    return ""


def _sense(sn, kind: str, phrase: str, pos: str, group_labels: list[str]) -> Sense | None:
    # a "use" note ("used in negative sentences ...") is the definition when there is no def
    defs = _under(sn, "def", {"x-gs"} | _GROUPS) or _under(sn, "use", {"x-gs"} | _GROUPS)
    definition = clean(" ".join(_en(d) for d in defs))
    definition_zh = clean(" ".join(_zh(d) for d in defs))
    examples = []
    for x in _under(sn, "x", _GROUPS):
        ex = Example(text=_en(x), text_zh=_zh(x))
        if ex.text or ex.text_zh:
            examples.append(ex)
    if not (definition or definition_zh or examples):
        return None
    labels = tuple(dict.fromkeys(group_labels + _labels(sn, stop_at_senses=False)))
    return Sense(kind=kind, pos=pos, number=_number(sn), phrase=phrase, labels=labels,
                 definition=definition, definition_zh=definition_zh, examples=tuple(examples))


def _group_senses(group, kind: str, phrase: str, pos: str) -> list[Sense]:
    """Senses of an idm-g / pv-g / dr-g; a derivative with no sense still records the word."""
    if not phrase:
        return []
    top = next((c for c in group if c.tag == "top-g"), None)
    group_labels = _labels(top, stop_at_senses=True) if top is not None else []
    sns = _under(group, "sn-g", _GROUPS)
    out = [s for sn in sns if (s := _sense(sn, kind, phrase, pos, group_labels)) is not None]
    if not out and kind == "derivative":
        labels = group_labels + [lab for sn in sns for lab in _labels(sn, stop_at_senses=False)]
        out.append(Sense(kind=kind, pos=pos, phrase=phrase, labels=tuple(dict.fromkeys(labels))))
    return out


def _groups(part) -> list[Sense]:
    """Idioms, phrasal verbs and derivatives of a part. A group nested in another one ("conventional wisdom"
    under the derivative "conventionally") is read as well; each group keeps to its own senses."""
    out: list[Sense] = []
    for tag, heading, kind in _GROUP_KINDS:
        for group in _under(part, tag):
            head = next(iter(_under(group, heading, _GROUPS | {"sn-gs"})), None)
            pos = _printed_pos(group) if kind == "derivative" else ""
            out += _group_senses(group, kind, _spelling(_en(head)), pos)
    return out


def _pos_of(scope) -> list[str]:
    return [p for p in (_en(e) for e in _under(scope, "pos", _GROUPS | {"x-gs", "sn-gs"})) if p]


def _printed_pos(scope) -> str:
    """The part of speech of `scope`'s senses: every one it prints ("adverb, preposition" share their senses)."""
    return ", ".join(dict.fromkeys(_pos_of(scope)))


def _prons(scope) -> list[Pron]:
    out: list[Pron] = []
    for blk in _under(scope, "pron-g-blk", _GROUPS | {"res-g", "v-gs", "if-gs", "sn-gs", "x-gs"}):
        tags = {e.tag for e in blk.iter() if isinstance(e.tag, str)}
        region = "uk" if tags & {"audio-gb", "brelabel"} else "us" if tags & {"audio-us", "namelabel"} else ""
        ipa = clean(" ".join(_en(p) for p in blk.iter("phon")))
        audio = next((a.get("href") for a in blk.iter("a") if (a.get("href") or "").startswith("sound://")), "")
        # the printed qualifier: pronform "strong form" / "weak form", pronfreq > q "also"
        note = clean(" ".join(_en(q) for q in blk.iter("pronform", "pronfreq")))
        pron = Pron(ipa=ipa.strip("/ "), region=region, audio=audio, note=note)
        if (pron.ipa or pron.audio) and pron not in out:
            out.append(pron)
    return out


def _forms(root, headword: str) -> list[str]:
    out: list[str] = []
    skip = _GROUPS | {"sn-gs"}
    for el in _under(root, "vp", skip) + _under(root, "if", skip) + _under(root, "v", skip):
        if el.tag == "vp" and el.getparent() is not None and el.getparent().get("form") == "root":
            continue
        if el.tag == "v" and next(el.iterancestors("v-gs-blk"), None) is not None \
                and next(el.iterancestors("v-gs-blk")).get("type") not in _VARIANT_TYPES:
            continue
        form = _spelling(_en(el))
        if form and form != headword and form not in out:
            out.append(form)
    return out


def _parts(root):
    """(part element, its pos) for each part-of-speech block of the entry."""
    parts = [el for el in root.iter("div") if "cixing_part" in (el.get("class") or "").split()]
    if not parts:
        parts = [root]
    return [(part, _printed_pos(part)) for part in parts]


def parse(headword: str, html: str) -> Entry:
    root = parse_html(html)
    # an h-l lists several heads ("-ian, -an"): show the one this entry is filed under
    heads = [_spelling(_en(h)) for h in root.iter("h") if not _inside(h, root, _GROUPS)]
    heads = [h for h in heads if h]
    homographs = list(dict.fromkeys(clean(n.get("hm") or "") for n in root.iter("homonym")))
    shown = clean(headword) if clean(headword) in heads else heads[0] if heads else clean(headword)

    pos_list: list[str] = []
    prons: list[Pron] = []
    senses: list[Sense] = []
    for part, pos in _parts(root):
        pos_list += _pos_of(part)
        prons += [p for p in _prons(part) if p not in prons]
        # labels printed with the headword ("[U]", "business") hold for every ordinary sense of the part
        part_labels = [lab for top in _under(part, "top-g", _GROUPS) for lab in _labels(top, stop_at_senses=True)]
        for sn in _under(part, "sn-g", _GROUPS):
            if (s := _sense(sn, "sense", "", pos, part_labels)) is not None:
                senses.append(s)
        for d in _under(part, "def", _GROUPS | {"sn-g", "x-gs"}):  # a def wrapped around its sense
            if (definition := _en(d)) or _zh(d):
                senses.append(Sense(pos=pos, definition=definition, definition_zh=_zh(d)))
        senses += _groups(part)

    has_definition = any(s.definition or s.definition_zh for s in senses)
    return Entry(headword=shown, homograph=homographs[0] if len(homographs) == 1 else "",
                 pos=tuple(dict.fromkeys(pos_list)), prons=tuple(prons), senses=tuple(senses),
                 forms=tuple(_forms(root, shown)), stub="" if has_definition else _stub_reason(root))


def _stub_reason(root) -> str:
    """Why a record without a definition has none: the pointer its senses carry instead."""
    kinds = {xr.get("xt") for xr in root.iter("xr-gs") if not _inside(xr, root, {"def", "x-gs"})}
    if kinds & _INFLECTION_XT:
        return "inflection"
    if kinds & _POINTER_XT:
        return "xref"
    return "empty" if not any(True for _ in root.iter("def", "x")) else ""
