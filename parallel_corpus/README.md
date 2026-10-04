# English–Chinese parallel corpus of dictionary examples

A second local database collects the English–Chinese example sentences (not
definitions) of every dictionary on freemdict that has them, deduplicated.
Everything it builds lives in `parallel_corpus/data/`, which is git-ignored: it is
derived from copyrighted dictionaries and is never committed.

```sh
.venv/bin/python parallel_corpus/build.py        # all steps; --from STEP / --only STEP
PYTHONPATH=scripts:parallel_corpus .venv/bin/python parallel_corpus/parallel/export.py tmx parallel_corpus/data/parallel.tmx   # or jsonl, tsv
```

| Step | Script | Output |
|---|---|---|
| lexicon | `parallel/lexicon.py` | English → Chinese gloss lexicon from the parsed bilingual dictionaries |
| probe | `parallel/probe.py` | a few record blocks of every .mdx, read by HTTP range requests: pairs in each order (English first, Chinese first), language, lexicon alignment |
| choose | `parallel/choose.py` | the dictionaries whose sampled pairs are English–Chinese translations, and each one's order |
| extract | `parallel/extract.py` | one staged file per dictionary: parsed dictionaries from layer 2, the rest downloaded and scanned |
| audit | `parallel/audit.py` | each dictionary's precision: a jev screen of a sample, then review of the flagged pairs |
| build | `parallel/build.py` | `data/parallel.db`: pairs, clusters, translation variants, every source, full-text search |

What makes a pair (`parallel/corpus.py`, `parallel/text.py`):

- **Examples, not definitions.** Parsed dictionaries give their examples
  directly, phrases included (marked `phrase`). Other dictionaries are scanned
  for sentences only (4+ words, ending . ? !): in an unknown layout a phrase
  followed by Chinese cannot be told from a headword and its gloss. Where a
  dictionary translates its definitions as full sentences (the American
  Heritage English–Chinese editions), `parallel/styled.py` reads its markup
  instead: the style the dictionary prints examples in is learned from a
  parsed dictionary with the same content, whose examples and definitions are
  known, and only text in that style is taken (listed in
  `parallel/extractors.json`).
- **English and Chinese.** Other languages beside Chinese (German, French,
  Spanish, Dutch, pinyin, Japanese, Korean) are rejected by their function
  words, letters and scripts.
- **Translations.** A dictionary is kept only if its pairs align under the
  lexicon (Chinese printed next to English in encyclopedias and blogs does
  not). A pair is rejected if it is a label, a gloss, a note about a word, or
  has an implausible length ratio; dictionary apparatus (grammar labels,
  `(= …)` glosses, usage labels, bullets, icons) is removed.
- **Precision.** A dictionary enters the database only if its audited
  precision is at least 95%: jev flags a sample's doubtful pairs (it caught
  8 of 8 bad pairs in calibration, with 12.5% false alarms), the flags are
  read, and unread flags count as errors.
- **Deduplicated** at three levels: identical after normalising case, width,
  quotes, spacing and traditional/simplified characters (stored once, every
  source kept); identical apart from punctuation (one cluster, exports take
  its representative); the same English with another translation (grouped as
  translation variants).

Results of the build of 2026-10-04 (2,753 dictionaries probed):

| Stage | Count |
|---|---|
| dictionaries whose sampled pairs are English–Chinese translations | 287 (256 English first, 31 Chinese first) |
| dictionaries admitted at audited precision ≥ 95% | 115 (all 8 parsed bilingual dictionaries and 7 American Heritage English–Chinese editions among them) |
| distinct pairs | 1,736,913 (1,480,016 sentences, 256,897 phrases) |
| clusters (one pair each in the exports) | 1,605,327 |
| English sentences with more than one translation | 274,605 |
| audited precision, weighted by contribution | 97.3% |

The audit counts pairs the jev screen did not flag as correct; a read of 150
of them found 2 errors (about 1.3%), so the corpus's precision is estimated at
about 96%. Reviewer labels behind every admitted dictionary were re-read, and
4.5% of "good" labels were overturned before admission.

Compared with the first full build: the probe now samples blocks spread over the whole
file, so dictionaries whose few examples sat in the first blocks may no longer show enough
scored pairs to be chosen (one admitted dictionary, *GRE*, 21 pairs, fell below the minimum of
5); a Longman English–Chinese edition was newly admitted (98.3%; its pairs nearly all already
present from other Longman editions); the 8 newly chosen dictionaries all failed review (blog
articles, wiki headings, term glosses, usage notes). The weighted precision of the first build,
computed the same way, is also 97.3% (it had been reported as 97.6%).

Deliberately excluded: phrase templates with placeholders (`sb`, `sth`, `~`)
and notation for alternatives (`X. or Y.`, `(or with)`). Of the 16 American
Heritage English–Chinese editions, 7 pass the audit; 7 fail it on
mistranslations and synonym-note text, and 2 print no English–Chinese
example pairs.

## Layout

| Path | What |
|---|---|
| `build.py` | runs the steps in order |
| `parallel/` | the tools, one module per step, plus the shared pair rules (`corpus.py`, `text.py`, `styled.py`) |
| `tests/` | tests for every tool, on invented text |
| `data/` | everything built (git-ignored): `parallel.db`, the exports, and working files (`mdx/` downloads, `staged/` pairs, `audit/` samples and review labels) |

The tools also read shared inputs from the rest of the repository: the
freemdict index (`site/data/`), the traditional→simplified table
(`site/t2s.json`), the parsed dictionaries (`corpus/_structured/unified.db/`, built by
`scripts/build_corpus.py`) and the LZO decoder (`scripts/lzo1x.py`).

```sh
PYTHONPATH=scripts:parallel_corpus .venv/bin/python -m unittest discover -s parallel_corpus/tests -t parallel_corpus/tests
```
