# Lexical inventories

Complete inventories of English lexical facts, built from the 25 parsed dictionaries
(`corpus/_structured/unified.db/`, built by `scripts/build_corpus.py`). Each inventory records which
dictionaries attest each fact, so any use can choose its own evidence threshold. Lookup
(lemmatising running text, finding phrases in it with their positions) is separate work
built on these.

Everything they build lives in `inventories/data/`, which is git-ignored: it is derived
from copyrighted dictionaries and is never committed.

| Inventory | Module | Status |
|---|---|---|
| Parts of speech (shared) | `inventory/pos.py` | done |
| Inflections | `inventory/inflections.py` | done |
| Phrases: idioms, expressions, phrasal verbs, with slots | `inventory/notation.py`, `inventory/phrases.py` | done |
| Collocations | `inventory/collocation_sources.py`, `inventory/collocations.py` | done |
| Usage labels | `inventory/labels.py`, `inventory/usage.py` | done |
| Grammar patterns | `inventory/labels.py`, `inventory/usage.py` | done |
| Levels | `inventory/levels.py` | done |
| Word families and spelling variants | `inventory/families.py` | done |
| Pronunciation by part of speech; stress in word families | `inventory/ipa.py`, `inventory/pronunciation.py` | done |
| Commonly misspelled words; commonly confused words | `inventory/confusables.py` | done |

```sh
.venv/bin/python inventories/build.py                  # every inventory, in order; --from STEP / --only STEP
.venv/bin/python inventories/build.py --without-jev    # where jev is not installed
```

`inventories/build.py` runs the steps in dependency order and stops at the first failure
(`tests/test_build.py` checks the order against the files each module reads).
Build order: `inflections.py` first (the others use its lemmas and forms), then
`evidence.py` (the example index phrases and collocations read ambiguous notation with) and
`usage.py` (its grammar patterns correct some phrase kinds), then any of `phrases.py`,
`collocations.py`, `levels.py`, `families.py`; `pronunciation.py` after `families.py`, then
`sameword.py` (it asks Jev, caching the answers in `data/sameword_cache.json`; with
`--without-jev` it asks nothing, tags the unanswered contrasts "uncertain", and records that in
`pronunciations.db`'s `build_info`, which `check.py` prints), and
`confusables.py` (it needs `levels.db` and `pronunciations.db`). Last, `check.py` runs the
invariants every inventory must hold (no empty fields, no dangling references, shares in
range, known values on every axis, a stress row agreeing with its counts...) and exits 1 on
any violation: a build that quietly writes impossible rows passes its own run but not this.
Accuracy is measured by `evaluate.py` against hand-checked items (see Evaluation).

## Parts of speech

The dictionaries print 743 different part-of-speech strings ("n.", "N-COUNT",
"tr. & intr.v.", "noun plural but singular in construction", 名词…). `pos.normalize` reads
them compositionally and returns Universal POS tags (NOUN, VERB, ADJ, ADV, ADP, CCONJ,
SCONJ, PRON, DET, INTJ, NUM, PROPN, PART, SYM, X) with features: Transitivity, Number,
Agreement (plural in form, singular in agreement: *news*), Countability, and Kind for
abbreviations, affixes, phrases and trademarks. It maps 99.993% of the 8.3 million uses;
the rest (608) are not parts of speech ("informal", "none").

## Inflections

```sh
PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/inflections.py
```

Writes `data/inflections.db` (tables `inflection`, `other`, `lemma`) and `data/inflections.tsv`.
Every row is a form, its lemma, part of speech and slot (`Plur`; `3Sg`, `Past`, `PastPart`,
`PresPart`, and `Pres` for *am/are*; `Cmp`, `Sup`), a region where spelling differs
(`GB` *travelled*, `US` *traveled*), and its evidence:

| source | kind | meaning |
|---|---|---|
| attested | regular | a dictionary lists the form and it is what the rules give |
| attested | irregular | a dictionary lists the form and it fits no rule: *went*, *children*, *criteria*, *sheep* |
| rule | regular | no dictionary lists the slot; the rules give it (lemmas two dictionaries besides the OED give that part of speech) |

`n` is how many dictionaries list the form. Forms that are not inflections go to `other`:
spelling variants (*colour/color*, by known alternations), derivatives (*abetter*),
contractions (*isn't*), the OED's historical spellings (*quhyit* for *white*), nonstandard
forms (*goed* where many dictionaries give *went*), and forms that fit no accepted pattern
(`unclassified`, kept for inspection).

How forms are judged:

- The dictionaries' form lists are untyped; each form is matched against the regular
  forms of its lemma's parts of speech (in the order the entry prints them: *foot* is a
  noun first, so *feet* is its plural). Regular rules handle -es/-ies, e-dropping,
  stress-dependent doubling (from the dictionaries' IPA: *preferred* but *offered*),
  British -ll- (*dialled*), -sis → -ses.
- An irregular form must be believable: suppletion and vowel-change plurals come from
  closed lists (*go/went*, *foot/feet*); nouns must have a plural's shape (*cactus/cacti*,
  *wolf/wolves*, *minimum/minima*); verbs must keep the lemma's consonants (*sing/sang*,
  *write/wrote*). A form one or two dictionaries give must also follow a known pattern
  or be a prefixed form of a well-attested one (*misbuilt* from *built*).
- Zero plurals come from the dictionaries that mark them (ODE's "same", COBUILD).

Measured on the build of 2026-09-30 (190,366 forms of 368,672 lemmas):

| Check | Result |
|---|---|
| 70 well-known forms (irregular verbs and plurals, suppletion, doubling, zero plurals) | 70 found |
| irregular forms, 3+ dictionaries (random 60 read) | about 93% correct |
| irregular forms, 1–2 dictionaries (random 60 read) | about 97% correct |
| generated regular forms (random 40 read) | about 95% correct |
| attested regular forms (random 40 read) | about 97.5% correct |

The remaining errors are mostly spelling variants no alternation covers, taken for an
irregular form.

## Phrases

```sh
PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/phrases.py
```

Needs `data/inflections.db` (it lemmatises the words of each phrase to merge them). Writes
`data/phrases.db` (tables `phrase`, `variant`) and `data/phrases.jsonl`.

`notation.parse` reads each dictionary's phrase notation into variants of words and typed
slots:

| Printed | Variants |
|---|---|
| `be/go out like a light` | be out like a light · go out like a light |
| `as easy as anything/as pie` | as easy as anything · as easy as pie |
| `get (yourself)/be in a stew (about/over sth)` | get in a stew · get {oneself} in a stew · be in a stew · … about {sth} · … over {sth} |
| `pack a (powerful, real, etc.) punch` | pack a punch · pack a powerful punch · pack a real punch |
| `let it drop (或 rest)` | let it drop · let it rest |
| `use something ↔ up` | use {sth} up (separable) |
| `take a ~ at` under *look* | take a look at |

Slots are `{sb}`, `{sth}`, `{sb/sth}`, `{sb's}`, `{sth's}`, `{one's}`, `{oneself}`, `{somewhere}`
and `{...}` (an ellipsis). A phrasal verb whose object slot stands between the verb and its
particle is marked separable.

Some notation reads more than one way: `long-running show/musical/soap opera` (a shared
*opera*, or three alternatives), `in/out of shape`, `there's no rhyme or reason to/for sth`.
The rules list every reading they allow, their most likely first, and `evidence.py`
decides: the rules' reading stands unless the dictionaries' 3.6 million English examples
fail to attest one of its variants and attest every variant of another reading. A run of up
to four words must occur whole; a longer one, every four-word window of it (shorter windows
let garbage through: the index ignores punctuation, so "give get the" matches "give, get
the"). Fragments
of the rules' reading ("bad as {sb/sth}" beside "every bit as bad as {sb/sth}") are
attested too, so a reading made of them is never chosen.

Variants from all dictionaries are merged into one phrase when their keys agree (words
lemmatised, object slots one, possessive slots one). Grouping is anchored: a record joins a
group through its own first reading, so a record that lists near-synonyms ("open the
door/way") cannot chain unrelated idioms together. Each phrase has a canonical text (the
first reading of the most preferred dictionary), its variants with their counts, the
dictionaries and publishers that list it, and a kind: `phrasal_verb`, `idiom`, `formula`
(*thank God*, *mark my words*), `name` (*the North Sea*), `compound` (a noun phrase listed
as a phrase: *the great apes*), or `pattern` (a word with its grammar: *endeavour to do
sth*).

Left out: the OED, etymological and pronouncing dictionaries (their "phrases" are mostly
compounds or headwords), grammar notes ("comparative ..."), a word with its article (*the
woman*). COBUILD prints only the key words of a phrase in bold ("battles it out with"); its
records add evidence to a phrase another dictionary prints, and a phrase only COBUILD
lists is left out (2,892 of them).

NCECD lists technical terms (*pectoralis minor*) and a word's grammar (*impervious to sth*)
among its phrases. An "idiom" only NCECD gives becomes a `compound` when it is noun-shaped
and another dictionary has it as a headword (of 34 such phrases in a hand-labelled sample of
100, 32 are fixed terms or names), and a `pattern` when it is one word with its slots and the
dictionaries give that word that grammar pattern (`impervious to {sth}`: ADJ to n; of a
random 40 such, 37 are). The compound rule is measured on NCECD-only phrases and applied
only there: elsewhere a noun-shaped idiom that is also a headword is often a true idiom (*red
herring*). The pattern rule rests on the grammar inventory, not on the source, so it applies
to every dictionary (LDOCE's *proceed to do sth*); a reflexive in the last slot is a filled
slot, not the word's grammar (*full of {oneself}* is conceited: an idiom). NCECD's free
collocations (*be on trial*) stay idioms: see Evaluation for what was tried.

A phrase filed under a phrasal verb is a `phrasal_verb` only in a phrasal verb's shape: (be,
get, feel, not, never) the entry's verb in any form, its object, one or two particles or
prepositions, an object (*put {sb} up to {sth}*, *be burnt out*, *psych {oneself} up*,
*look forward to doing {sth}*). The rest are idioms filed there (*throw in the towel*, *it
goes without saying*, *not know what {sb} sees in {sb}*): 911, and one a pattern. Of a random 40 moved,
an independent reviewer judged 36 right; the four missed classes (a participle that is a
headword, *strung out*; a leading *never*; *put before*; a generic *you*) were then fixed.

The build of 2026-10-05 has 49,607 phrases from 275,980 records (35 unreadable): 37,213
idioms, 7,629 phrasal verbs, 1,687 compounds, 1,578 names, 876 formulas, 624 patterns.

Fixed on 2026-10-05, found by the text analyzer (`analyzer/`), which turns every variant into a
pattern to match: a gloss glued to a phrase ("a quick buck(easy money)", NCECD) was read as
optional words and run into the phrase ("a quick buckeasy money"); a semicolon between two
alternatives ("do justice to sb; do sb justice") was not a separator, though a proverb's own one
("to err is human; to forgive divine") stays; punctuation stayed glued to a slot ("{sb/sth}!"),
and "someone/thing's" was no possessive slot; "(or around; also about)" was not split; and a
headword's "etc." list was read as spellings ("in his/her/its, etc. (infinite) wisdom" gave
"in wisdom"). 585 variant texts that were garbage went, 34 alternatives that had been fused
came in; held-out notation went from 46/48 to 47/48.
Notation accuracy is in Evaluation.

## Collocations

```sh
PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/collocations.py
```

Needs `data/inflections.db` and `corpus/unified.db` (two sources are read from the raw
HTML, which the parsed layer does not keep). Writes `data/collocations.db` (tables
`collocation`, `pattern`) and `data/collocations.jsonl`.

| Source | What it gives | Records |
|---|---|---|
| OCD (parsed) | collocates under labels: `VERB + DECISION`, `ADJECTIVE`, `… OF RAIN`, `used with these nouns as the object` | 399,070 |
| LDOCE (`@collocations_<word>` pages) | collocations printed whole under headings (verbs, adjectives, phrases); from other entries; bare collocates from its corpus, by part of speech, with examples | 207,961 |
| MED ("Collocates" boxes) | "Verbs frequently used with X as the object", "Nouns frequently used as objects of Y" | 4,498 |
| NCECD (parsed) | collocations among its examples, with Chinese | 26,890 |

OALD's collocation boxes are extracts of the OCD and are not read again.

Each collocation is a pattern with the base written `~`, its relation, and its word order:

| Printed | Pattern | Relation |
|---|---|---|
| OCD `VERB + DECISION`: make | `make ~` | verb_obj |
| OCD `VERB + DECISION`: arrive at | `arrive at ~` | verb_prep |
| LDOCE verbs: `reach/come to/arrive at a decision` | `reach a ~` · `come to a ~` · `arrive at a ~` | verb_obj, verb_prep |
| OCD `RAIN + VERB`: pour down | `~ pour down` | subj_verb |
| OCD `… OF RAIN`: drop | `drop of ~` | quantifier |
| LDOCE corpus, NOUN: maker (examples: "decision makers") | `~ maker` | noun_noun |
| MED Adverbs frequently used with *attack* | `~ openly` (order free) | adv_verb |
| NCECD `to be envious of sth` | `be ~ of {sth}` | prep |
| OCD `VERB + DEATH`: crush sb to | `crush {sb} to ~` | verb_prep |
| LDOCE corpus, NOUN: day (examples: "persisted to this day" 4 of 8) | `~ to this day` | prep |

Relations: adj_noun, verb_obj, subj_verb, noun_noun, quantifier, prep, verb_prep, adv_verb,
adv_adj, verb_adj, verb_verb, adj_adj, phrase, and untyped. The relation comes from the
base's part of speech, the collocate's, and its side; a preposition between them makes it
verb_prep when the collocate is a verb (*agree on ~*), prep otherwise (*a study in ~*).
LDOCE's bare corpus collocates take from their examples the words most of them put between
collocate and base, when those include a preposition, particle or reflexive (*cry
{oneself} to ~*); articles and possessives vary and are not kept (*make (a) ~*). When a source prints the whole collocation, the
base is found in it by its inflections (*came loose* under *come*). When it gives a bare
collocate, the label or heading gives the side. LDOCE's corpus collocates take the side
their examples show. A full collocation without a label is typed by the open-class word
nearest the base (passing over an adverb that modifies another word: *an oddly ~ group*),
and a base of unknown part of speech by where it stands (after an article a noun, before an
object a verb, before a noun an adjective). Where a word can be a noun or an adjective (OCD
lists noun modifiers under ADJECTIVE: *hardback novel*), it is a noun when the
dictionaries make it one at least twice as often (*hardback*, *weather*), else an adjective
(*fancy*, *individual*). Otherwise the relation is untyped. Where no source gives the order (bare
adverbs; Macmillan's "nouns used with" a verb), `word_order` is `free`, and subject or
object is left untyped rather than guessed.

The same collocation from several sources is one row. Patterns match on their lemmas, with
articles and possessives left out: OCD's `make ~` is LDOCE's `make a ~`. LDOCE's
collocations from other entries do not say the base's part of speech. They join the typed
row with the same pattern, or keep an empty `base_pos`.

The build of 2026-10-05 has 516,557 collocations (19,866 untyped; 3,091 records
unreadable, mostly full collocations without their base). Accuracy is in Evaluation.

## Usage labels and grammar patterns

```sh
PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/usage.py
```

Writes `data/labels.db` (table `label`), `data/grammar.db` (table `pattern`) and
`data/labels_unread.tsv` (the label strings no rule reads, with their counts).

The dictionaries print 63,192 different label strings over 2.3 million uses: "informal",
"Brit. informal", "chiefly N. Amer.", "美口", "医", "C", "+ to infinitive", "usu ADJ n",
"†". `labels.normalize` reads each one part by part into (axis, value) pairs:

| Axis | Values (examples) |
|---|---|
| register | informal, slang, vulgar, taboo, formal, literary, poetic, technical, spoken, written, nonstandard, child, euphemistic |
| attitude | approving, disapproving, humorous, ironic, offensive, emphasis, rude |
| time | dated, archaic, obsolete, historical |
| frequency | rare |
| region | GB, US, NAm, CA, AU, NZ, IE, SC, ZA, IN, CARIB, N-ENG, US-regional, dialect |
| domain | medicine, law, botany, cricket ... (a listed field, or a label shaped like one: *Cell Biology*) |
| selection | what the word goes with: `+ person`, `of a horse` |
| language | of a foreign phrase: Latin, French ... |
| use, form, kind, author | figurative, literal; capitalized, combining; trademark, saying; Shakespeare, Spenser (Chambers) |
| grammar | COBUILD's pattern notation: `V n`, `V`, `V to-inf`, `N uncount`, `N count`, `ADJ n`, `v-link ADJ`, `usu passive` |

Qualifiers (chiefly, esp., mainly, 主, 尤) are dropped; a label with a part no rule reads
gives no pairs at all, so nothing is half-read. The OED's structural marks (α., (a),
Compounds, dated cross-references) are recognised as not labels. Grammar codes whose class
depends on the word (`+ to infinitive`, `only before noun`) are written with the sense's
own class: *able* ADJ gets `ADJ to-inf`, *decision* NOUN gets `N to-inf`.

Each `label` row is a word (or a phrase, in the phrase inventory's notation), its part of
speech, one axis and value, the dictionaries that give it, and `share`: of the word's
senses in those dictionaries, the fraction that carries the label (1.0: the word itself is
labelled, not one of its senses). Each `pattern` row counts the senses and the examples
(CALD, COBUILD label their examples) that give the pattern.

The build of 2026-10-03 read 98.3% of 2,283,195 label uses in 6,182,285 senses (the rest
are a tail of strings used under 170 times each): 801,620 label rows and 212,391 grammar
patterns (1,266 distinct). LDOCE, MED and AHD senses now carry their entry head's labels,
which is most of the rise in uses read. A hedge inside a label is dropped, not read as noise: "informal
mainly disapproving", "BrE also", "chiefly British vulgar slang". *Originally* and
*formerly* are not hedges: they say where a word came from or how it was once used, so
"colloquial (originally North American)" is informal only, and "originally U.S." alone is
not read; "originally and chiefly U.S." is, as US. Phrases a splitter would cut are kept
whole first ("+ adverb/preposition", "in questions and negatives"). Accuracy is in Evaluation.

## Levels

```sh
PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/levels.py
```

Writes `data/levels.db` (table `level`: word, part of speech, scheme, value, dictionary,
senses). The marks are read from the raw entries in `corpus/unified.db`:

| Scheme | Dictionary | Values | Words |
|---|---|---|---|
| `oxford3000` | OALD | a1 a2 b1 b2 (the Oxford 3000, with its CEFR level; phrasal verbs too) | 3,917 |
| `oxford5000` | OALD | b2 c1 (the words the Oxford 5000 adds) | 2,139 |
| `cefr` | OALD | a1 ... c2, per sense (`senses` counts them) | 9,688 |
| `opal`, `academic` | OALD | written, spoken; yes | 1,503; 1,822 |
| `core` | LDOCE | high medium low (the Longman Communication 3000) | 10,589 |
| `spoken`, `written` | LDOCE | S1–S3, W1–W3 (top 1000/2000/3000) | 3,550; 3,529 |
| `awl` | LDOCE | yes (the Academic Word List) | 1,762 |
| `frequency_band` | COBUILD, CED | 1 ... 5 (Collins frequency dots; 5 most common) | 131,698 |
| `stars` | MED | 1 2 3 (Macmillan's red words) | 7,368 |
| `oed_band` | OED | 1 ... 8 (8 most frequent) | 214,136 |

Several entries share one page in OALD (*august* adj., *August* n.) and LDOCE (one head
per homograph); each is read with its own part of speech. The build fails if an entry
carries a level mark that no reader reads, so a change in the markup cannot silently drop
words.

## Word families and spelling variants

```sh
PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/families.py
```

Writes `data/families.db` (tables `link`, `family`, `variant`). Links come from the
derivatives the dictionaries list under a headword, OALD's Word Family boxes (with their
opposites: *decision* ≠ *indecision*), the inflection inventory's derivatives and variants,
and headwords printing two spellings ("beedie, beedi", accepted only for a known
alternation). Each link's relation is read from the two words:

| Relation | Example | Links |
|---|---|---|
| suffixed | reserve → reservation, decide → decision, run → runner, synthesis → synthetic | 72,299 |
| compound | fibre → fibreboard, strip → strip map | 46,219 |
| related | listed together, no rule explains how (progenitor → progeny) | 41,382 |
| sibling | two suffixes on one stem: icebreaker → icebreaking, hesiodic → hesiodian | 24,656 |
| conversion | the same word, another part of speech | 18,540 |
| inflection | an inflected form, or two of one lemma (comment → commenting, discouraging → discouraged) | 18,450 |
| variant | colour → color (GB, US), night club → nightclub, twocker → twoccer | 13,101 |
| prefixed | decided → undecided; an entry for a prefix: re- → refocus | 9,034 |
| family, opposite | OALD's boxes | 155, 48 |

A variant is a known alternation (-our/-or, -ise/-ize...), open or hyphenated against
solid spelling, or a respelling: the same once c/k, ph/f and doubled consonants are set
aside, a vowel change counting only beside such a respelling (*cajuput*, *kajeput*; not
*hexane*, *hexene*: another word; not *complement*, *compliment*: a vowel alone is no respelling).

A family is a connected group of words joined by suffixed, prefixed, conversion,
sibling, inflection, opposite, family and variant links: 45,882 families over 156,598 words,
the largest 40 (*sulfur* and its derivatives). Compounds and affix entries join no
family: they would chain *fibre* to *board*, and every *re-* word to the others. Spelling
variants carry their regions where the alternation tells them apart (-our/-or,
-re/-er, -ogue/-og, -ll-/-l-, ae/e).

Accuracy is in Evaluation; of the respelling variants (random 40 read), 39 are spellings of
one word (*acanthus*, *acanthous* is a noun and its adjective).

## Pronunciation: by part of speech, and stress across a word family

```sh
PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/pronunciation.py
```

Needs `data/families.db`. Writes `data/pronunciations.db`:

| Table | What it holds |
|---|---|
| `pron` | every transcription read: word, part of speech (when the source ties it to one), region, IPA, syllables, primary stress |
| `pos_contrast` | one spelling, two parts of speech, two pronunciations |
| `family_stress` | each family link (suffixed, prefixed, sibling) and whether its primary stress moves |
| `family_shift` | the members, with their stress, of every family in which the stress moves |

`pos_contrast` names the change:

| Change | Example | Rows |
|---|---|---|
| stress | object n. ˈɒbdʒɪkt, v. əbˈdʒekt; record, permit, increase, contract | 425 |
| stress (optional) | a part of speech that takes either stress: adept adj. əˈdept, n. ˈædept | 93 |
| vowel | live v. lɪv, adj. laɪv | 79 |
| ate | estimate n. ˈestɪmət, v. ˈestɪmeɪt; separate, graduate, advocate, consummate | 81 |
| voicing | use n. juːs, v. juːz; house, close, abuse, excuse | 25 |
| segment | other sounds, or a syllable more (rite adv. ˈraɪtiː, n. raɪt) | 64 |

Of 39 well-known cases (object, record, present, use, estimate, live, house, permit...), 39
are found, *address* among them: it differs only in American English (n. ˈædres, optional).

`family_stress` compares the primary stress on the shared stem: counted from the start for a
suffix (photograph ˈfəʊtəɡrɑːf 1/3, photography fəˈtɒɡrəfi 2/4, photographic
ˌfəʊtəˈɡræfɪk 3/4), from the end for a prefix. 64,806 links have transcriptions for both
words in one dictionary; in 16,533 the stress moves, across 8,397 families. (LDOCE pages
served under another headword, *actuarial* showing *actuary*'s, no longer lend it their
transcriptions.)

Measured by an independent reviewer on random samples of the build of 2026-10-01: of 50
contrasts, 47 are real differences between the two parts of speech (the rest: a variant
pronunciation, another word's transcription) and the change was named right in 43, before
the two label fixes below; of 40 links marked as shifting, 40 do; of 20 marked as not, 19 do
not. Six of the 50 contrasts are two unrelated words that happen to share a spelling and
differ in part of speech (Latin *rite* adv., *rite* n.): kept, since the request is by
spelling and part of speech; `n` ≥ 2 keeps the 282 contrasts two or more dictionaries show.
After the review, a contrast whose sounds always differ is named by the sounds (consummate
adj./v.: ate, not optional stress), and one with a syllable more or less is a segment change.

Each contrast is tagged (`inventory/sameword.py`, after `pronunciation.py`): one word in two
parts of speech, or two words that share a spelling (Latin *rite* adv., English *rite* n.).
The definitions of the two parts of speech go to a calibrated model as two questions (one
word with related meanings? unrelated words?); `p_same` and `p_unrelated` are kept, and
`word_relation` reads them with thresholds set on 78 hand-labelled contrasts:

| word_relation | Rule | Rows | Right, 40 fresh hand-labelled contrasts |
|---|---|---|---|
| same word | p_same ≥ 0.8, p_unrelated < 0.15 | 526 | 21 of 22 |
| likely different words | p_unrelated ≥ 0.15, p_same < 0.8 | 133 | 7 of 10 |
| uncertain | the rest; or no definitions for both | 108 | (5 different, 3 the same) |

Two signals were tried and dropped: definitions sharing words (AUC 0.66), and whether
the two pronunciations stand in one etymological entry of ODE or the OED (it votes the wrong
way: ODE prints variants inside an entry, the OED gives a noun and its verb separate
entries). The main error left: a part of speech's definitions are not tied to the
pronunciation in the contrast (*lead* n. /led/, the metal, was judged on the definitions of
"the lead", in front).

How it is read:

- **IPA only.** CEPD, LPD, LDOCE, OALD, OALECD, CALD, MED, MWALED, ODE, ODECN, CED, COBUILD,
  NCECD, YHDCD and the OED. AHD's and Merriam-Webster's respellings place stress marks by
  other rules and are left out.
- **Part of speech only where the source gives it.** Most parsed entries carry one
  transcription list for several parts of speech; a transcription counts for a part of
  speech only from an entry with one, or from a homograph block read from the raw page
  (LDOCE's heads, CEPD's blocks, LPD's numbered homographs).
- **Compared within one dictionary and one region**, so transcription conventions never
  mix. LDOCE, CEPD and LPD print an American form only where it differs, so a part of
  speech with none printed takes its British one, for a stress change only (*address* n.
  $ ˈædres, v. əˈdres); one printed in part ("$ -ˈsɔːrs") is not replaced. When one
  dictionary shows a strict stress change and another lets the two share a stress, the row
  says `stress (optional)`: the stress does not always differ (*redress*, *export*). Each row counts the dictionaries that show the change (`n`) and those that compare
  the two and do not (`n_not`).
- `inventory/ipa.py` counts syllable nuclei (vowels; diphthongs as one; a long vowel ends
  its nucleus; syllabic consonants), finds the syllable after ˈ, and rejects transcriptions
  given only in part ("-ˈnɑː.mɪk") or of several syllables without a stress mark.
- **Guards against noise:** case is kept (COO is not coo); a transcription far from the
  spelling's syllable count is another word's and dropped (NCECD gives *palaeoecologic*
  ˈpælətəlɪ; WHO spelled letter by letter); the weak vowels ɪ ᵻ i ə count as one when
  segments are compared, since transcriptions write them variously; affix entries (re-,
  -ology) are not words and are left out; CEPD's usage notes and panels quote other
  transcriptions (*to*: "'to cut' /təˈkʌt/") and are not read. A CEPD label before a
  block's first transcription names the homograph (*wind* n. "air blowing: wɪnd") and is
  kept; one after it restricts a variant to a sense (*present* n. "military term:
  prɪˈzent", *control* n. "in machinery also") and is left out, bar strong and weak forms.

## Commonly misspelled words; commonly confused words

```sh
PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/confusables.py
```

Writes `data/confusables.db`: `misspelling` (word, wrong spellings when the source gives
them, hint, kind, dictionaries), `confusable` (a pair, its kinds, dictionaries, publishers,
the source's note), `confusable_set` (OALD's and PEU's sets of three or more).

Misspellings are taken only where a dictionary says so outright, so the list is short and
sure (104 words):

| Kind | Source | Words |
|---|---|---|
| learner_error | CALD's "Check your spelling! *Accommodation* is one of the 50 words most often spelled wrongly by learners. Remember: the correct spelling has 'cc' and 'mm'" (the Cambridge Learner Corpus); COBUILD's "Be careful with the spelling of this word"; Macmillan's Get It Right! spelling boxes, wrong forms from their ✗ sentences (*accomodation*, *developping*, *independance*) | 69 |
| misspelling | "*barbecue* is often misspelled as *barbeque*"; Chambers' "a misspelling of" (a run-on form with its part of speech, or an entry opening with its own headword; not an etymology's aside such as OK's "a facetious misspelling of all correct"); a spelling "regarded as an error" (*miniscule*) | 4 |
| nonstandard | "a nonstandard spelling of *another*": spellings that represent speech (*'nother*) | 31 |

Of 20 well-known hard spellings (accommodation, separate, definitely, necessary, receive,
embarrass, government, environment, beginning, believe, business, whether, until...), 20 are
in.

Confusable pairs (806; on 2026-10-05, 11 pairs read from things "confused with the oak apple gall" or from a
lost subject, "and are sometimes confused with", were dropped: "confused with the ..." now names a word
only through a word class, "the verb affect"):

| Kind | Source | Pairs |
|---|---|---|
| which_word | OALD's Which Word? boxes (affect / effect; alone / on your own / lonely / lone) | 136 |
| homophone | OALD's Homophones boxes (base \| bass) | 119 |
| confused | "Do not confuse (the adjective) *loose* with (the verb) *lose*", "*appraise* is frequently confused with *apprise*", "For an explanation of the difference between *continual* and *continuous*", CALD's "Common mistake: *than* or *then*?", PEU's entry titles ("allow, permit and let", "alternate(ly) and alternative(ly)"; lists only from its Word Problems part, and no title naming grammar terms or spelling rules); read from notes, examples left out | 411 |
| sound_alike | each word's main pronunciation transcribed alike by two dictionaries or more (weak vowels as one before the stress only; reduced forms set aside), both words common (Oxford 3000/5000, Longman Communication 3000, Macmillan stars, Collins' top three bands), not spellings of one word | 286 |

Of 33 well-known confusable pairs (affect/effect, principal/principle, stationary/stationery,
their/there, its/it's, than/then, lose/loose, ensure/insure, imply/infer, fewer/less, lay/lie,
compose/comprise...), 31 are in. Every dictionary's raw text was searched for the other two:
*personal*/*personnel* meet only in etymologies; *emigrate*/*immigrate* meet in "compare"
cross-references (too loose a signal: they point at opposites and related words alike), a
NOAD usage note that defines both without calling them confused, and NCECD's 词义辨析 boxes,
which are synonym studies (2,409 of them, up to 11 near-synonyms each: *ability, capacity,
talent...*), a thesaurus rather than a list of confusions, and not read. Of a second list of 20 hard spellings, 13 are in: *accommodate*,
*occurrence*, *rhythm*, *conscience*, *Wednesday*, *February* and *calendar* are flagged by
no dictionary, and none is added without one. A pair a dictionary names as confused
is kept even when the two look like one word's spellings (*ensure*, *insure*); sound-alike
pairs that are spellings of one word (*colour*, *color*) are not confusables and are left
out.

Measured by an independent reviewer on random samples, each drawn fresh after the fixes
the previous one prompted:

| Sample | confused | sound_alike | which_word, homophone | misspellings |
|---|---|---|---|---|
| first (fixed: notes read without their examples; anaphors; weak vowels only before the stress; weak forms) | 6/27 | 11/20 | 11/11 | 36/40 |
| second (fixed: PEU titles of two words only; a word's main pronunciation only; diacritics in wrong forms) | 21/30 | 12/20 | | 27/30 |
| third, the current honest measure | 23/30 | 19/20 | | 23/25 |

After the third sample, "not to be confused with" counts only in the learner dictionaries
(OALD, LDOCE, CALD, COBUILD, MED, MW Learner's) and Chambers is not read for confusions:
elsewhere the phrase draws encyclopedic lines (Austin Friars and Black Friars, intaglio and
steel engraving), which made most of the errors left; this last fix is not yet measured on
a fresh sample. Known remaining errors: a nonstandard spelling linked to the wrong standard
word (NOAD's *yer*), and pairs of one word's forms (*was*/*were*) that PEU discusses.

## Evaluation

```sh
PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/evaluate.py      # score (-v: the misses)
PYTHONPATH=scripts:inventories .venv/bin/python inventories/inventory/evaluate.py --sample   # draw candidates
```

`data/gold/` holds real inputs with the output each should give: 120 printed phrases
(drawn from those with notation to read), 120 collocation records (30 per source; LDOCE's
corpus collocates with their examples), 100 labels (60 weighted by use, 40 from the tail),
100 derivative links. The scorer runs today's code on them, so the gold stays valid across
rebuilds; it quotes the dictionaries and is git-ignored.

The gold was made by prefilling each item with the program's output and correcting it by
hand, which risks accepting a wrong output. An independent reviewer audited all 440 items
and flagged 14 clear errors: 8 were corrected as proposed, 5 to a finer relation than
proposed (sibling, not related), 1 was overruled; 2 of its uncertain items were corrected
too. Each changed item carries a note. `data/gold/heldout/` is a second sample (176 items, another
seed), judged by the independent reviewer alone, never used while the rules were changed.

| Check | Before | Gold (after) | Held-out, first measurement | Held-out, after |
|---|---|---|---|---|
| notation readings | 90.0% | 96.7% | 91.7% | 95.8% |
| collocation patterns | 97.5% | 99.2% | 97.9% | 97.9% |
| collocation relations | 73.3% | 91.7% | 87.5% | 91.7% |
| labels | 89.0% | 99.0% | 95.0% | 100% (30/30 without the 10 repeated) |
| family relations | 85.0% | 96.0% | 77.5% | 92.5% |

A second fresh sample (`data/gold/heldout2/`, seed 11, 226 items including 50 phrase kinds),
judged independently after a further round of fixes, is the current honest measure:

| Check | Second held-out | Same items, code of 2026-10-03 | Without items also in earlier gold |
|---|---|---|---|
| notation readings | 87.5% (42/48) | 87.5% (42/48) | 87.0% (40/46) |
| collocation patterns | 97.9% (47/48) | 97.9% (47/48) | 97.9% (47/48) |
| collocation relations | 85.4% (41/48) | 85.4% (41/48) | 85.4% (41/48) |
| labels | 82.5% (33/40); 87.5% counting leaked definitions left unread as right | 87.5% (35/40) | 82.8% (24/29) |
| family relations | 75.0% (30/40) | 72.5% (29/40) | 72.5% (29/40) |
| phrase kinds | 84.0% (42/50) | 84.0% (42/50), blind gold re-labelled by a second reviewer | 84.0% (42/50) |

The second column is not blind: the review fixes since include a stricter vowel rule for
variants (*complement*, *compliment* are two words), which moved family relations by one
item each way (gold 95 → 96 of 100, this sample 30 → 29 of 40). Phrase kinds are now scored
by `evaluate.py` too (`kind`, read from `phrases.db`), against labels a reviewer gave without
seeing the program's.

Both held-out sets turned out to repeat items of the gold the rules were tuned on (heldout:
10 labels; heldout2: 11 labels and 2 printed phrases, and heldout2 also repeats heldout).
`evaluate.py` now scores each held-out set without them and says how many it left out; the
last column above is that score, and the honest one. New samples (`--sample`, `--heldout`)
leave out every input already in a gold set, judged by its source record rather than by what
the program made of it. Stored LDOCE corpus collocates now carry their examples, so the
scorer re-reads them with today's reader instead of trusting a stored reading: on heldout
that exposed one miss (*outweigh* + *effect* read as `~ effect`, expected `effect ~`), and
heldout now scores collocation patterns 47/48 and relations 44/48.

Fresh samples of the 2026-10-01 fixes, each judged by an independent reviewer:

| Sample | Right | Then fixed |
|---|---|---|
| labels with a hedge inside (40 of 347) | 25/40 | "originally and chiefly X", "dialect chiefly British", "+ adverb/preposition", unread grammar prose, *ScotE*, "in the names of": 39/40 after, no longer blind |
| PEU pairs added (40 of 133) | 38/40 | not: two pairs from a list of four that PEU contrasts only crosswise (*into*/*onto*) |
| contrasts the US rule changed (7) | 6/7 real | disagreeing dictionaries make a contrast optional; CEPD's sense labels |
| phrases moved off `phrasal_verb` (40 of 961, before the last fixes) | 36/40 | the four classes, see Phrases |

It is lower than the tuned numbers: the rules generalise only in part. Its misses are new
classes (a shared tail after two verb phrases, "a fit/fits", glued "orafter", labels that
are leaked definitions, formulas and terms among idioms, stem-change suffixes taken for
siblings).

"Before" is the build before this measurement began; "Held-out, first measurement" is the
honest estimate of the rules as tuned on the gold. The held-out items then showed classes
(open and solid spellings, vowel-only "variants", siblings, the preposition relation) that
were fixed, so its last column is no longer blind: a fresh sample is needed for the next
honest number. The misses left are mostly one-offs (a source's typo, a literal
"something", a base whose part of speech the source gives wrongly).

NCECD's phrases that are free collocations, against 100 hand-labelled NCECD-only phrases
(33 free, 67 fixed): matching the collocation inventory is about 55–60% precise (idioms and
names are listed among collocations' phrases too); whether the Chinese gloss is built from
the words' own glosses separates them poorly (AUC 0.62: names are compositional too); a
calibrated model (Jev) ranks well (AUC 0.90) and confirms fixed expressions (at p ≤ 0.1, 33
of 34), but is never confident a phrase is free (none above 0.8; at p ≥ 0.5, 13 of 16). None
is good enough to relabel them, so they stay idioms. What did work is narrower: terms and
patterns (see Phrases).

## Tests

```sh
PYTHONPATH=scripts:inventories .venv/bin/python -m unittest discover -s inventories/tests -t inventories/tests
```
