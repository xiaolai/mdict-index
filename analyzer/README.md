# Text analyzer

Paste English text; get back its phrasal verbs, idioms and other phrases, its collocations,
and for every word its lemma, level, usage labels, likely confusions and spelling problems,
each with character offsets into the text. It applies the lexical inventories
([`inventories/`](../inventories/README.md)) to running text.

Like everything built from the dictionaries, its data (`analyzer/data/analyzer.db`) is
git-ignored and built locally.

```sh
.venv/bin/python inventories/build.py      # the inventories, if not built yet
.venv/bin/python analyzer/build.py         # compile them into analyzer/data/analyzer.db
.venv/bin/python analyzer/analyze.py essay.txt          # a readable report
.venv/bin/python analyzer/analyze.py essay.txt --json   # everything
PYTHONPATH=scripts .venv/bin/python scripts/serve_unified.py   # then http://127.0.0.1:8766/analyze
```

## What it finds

| | How |
|---|---|
| Lemmas | the inventories' lemmas for the form, in the part of speech spaCy tagged (`left` adj. stays *left*; `left` v. is *leave*); spaCy's lemma when they have none |
| Levels | the easiest CEFR level of the lemma in that part of speech, and every level scheme (Oxford 3000/5000, Longman, Macmillan stars, frequency bands) |
| Labels | register, attitude, time, frequency and region labels that most of the word's senses carry |
| Confusions, spelling | commonly confused words (*affect* / *effect*); known misspellings (*accomodation*); unknown words, with known forms one edit away |
| Phrases | every phrase variant, as a pattern with slots: `give {obj} up` matches "gave it up" and "gave the whole plan up"; `make up {poss} mind` matches "made up the old man's mind" |
| Collocations | verb–object, adjective–noun, noun–noun, adverb, preposition and subject–verb collocations through the dependency parse, whatever the order: "made a decision", "a decision was made", "the decision that she made"; the rest as patterns |

Slots are checked against spaCy's parse (`en_core_web_sm`): an object slot must be one
subtree headed by a noun, pronoun, number or gerund; a possessive slot a possessive; and every
match must be one connected piece of the dependency tree, so words that merely sit side by
side do not count. A phrase inside a longer one goes ("make up" in "made up his mind"); phrases
that merely cross are both kept, since which one the writer meant is not the matcher's to know.
Collocations only one dictionary lists are left out by default (`--min-collocation-n 1` keeps
them).

## Measured (2026-10-05)

Every span carries a confidence. **Likely**: a phrasal verb whose particle the parse calls a
particle ("gave it up"), a collocation, or any other phrase with two content words or three
words in all. **Possible**: a verb with a preposition, which may be literal ("standing in his
boat" is not *stand in*), or one content word among function words ("end of"). The command
line shows likely spans unless given `--possible`; `--json` and `POST /api/analyze` return both.

**Recall**, on the dictionaries' own examples (`analysis/evaluate.py`, 2,000 examples per kind;
"words": the phrase's words were marked, under its own inventory item or a duplicate of it):

| | Likely spans only | Likely and possible |
|---|---|---|
| phrasal verbs | 63.2% | 87.7% |
| idioms and other phrases | 58.4% | 72.6% |

**Precision**, on 568,000 words of public-domain and freely licensed prose (three Project
Gutenberg novels, twelve Wikipedia articles; `analysis/precision.py`): 200 phrase and 200
collocation spans drawn at random; each screened by jev (`jev/dockets/analyzer-span.json`);
every flagged span read; and, since the screen passes some errors (an idiom used literally reads
as fluent English), a random 80 of the passed spans read too:

| | Spans | Estimated precision |
|---|---|---|
| collocations | 200 | 96% |
| phrases, likely | 86 | 88% |
| phrases, possible | 114 | 68% |

What still goes wrong is meaning, which a pattern cannot see: an idiom used literally ("clinging
to the gunwales" is not *to the gunwale*, full to the brim; "the Prince of the Powers of the Air"
is not *the prince of*), and a verb with a preposition in its plain sense. Telling those apart
needs the sense, not the structure; that is the next step, not a threshold to tune.

Left out on purpose, after reading what they matched: patterns of one word, or of slots with
only function words around them (`in {obj}`); phrases made only of plain words ("there
are", "of all", "every other"); "be" and one word ("be drawn", "be going"); conversational
formulas except where they stand alone ("I see." but not "I see in him..."); a noun taken for a
phrasal verb's verb ("a few turns on the deck"); and a noun's prepositions (OCD's "in a ~"),
whose sense turns on the article.

## Layout

| File | Role |
|---|---|
| `build.py` | compile `analyzer.db` (`analysis/compile.py`) |
| `analyze.py` | command line |
| `scripts/lookup_ui/analyze.html`, `analyze.js`, `analysis.js` | the Analyze page of the lookup server (`/analyze`) |
| `analysis/lexicon.py` | `analyzer.db` in memory |
| `analysis/match.py` | phrase and collocation matching on the parse |
| `analysis/analyze.py` | tokens, words, spans: the result |
| `analysis/evaluate.py` | recall on the dictionaries' examples |
| `analysis/precision.py` | precision on running text: a sample screened by jev and read |
| `jev/dockets/analyzer-span.json` | the screen's question, versioned with the code |
| `tests/` | on a hand-made lexicon and spaCy's model; no dictionary data |
