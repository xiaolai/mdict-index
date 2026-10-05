# MDict Dictionary Finder

A searchable index of the MDict dictionaries listed at
<https://downloads.freemdict.com/>, published as a static GitHub Pages site.
The site links to freemdict; it hosts no dictionary files.

## What's here

| Part | What you get | Where it runs |
|---|---|---|
| [Dictionary finder](#how-it-works) | search the ~3,500 dictionaries on freemdict by name, alias, language and brand; recommendations; monthly change log | public website |
| [Unified dictionary](#unified-dictionary-database-local-only) | 25 dictionaries in one layout with audio; Chinese-to-English lookup; search by definition | your machine |
| [Lexical inventories](inventories/README.md) | inflections, phrases, collocations, labels, levels, word families, stress, misspellings, confusable words | your machine |
| [Parallel corpus](parallel_corpus/README.md) | 1.7 million English–Chinese example pairs, exportable as JSONL, TSV or TMX | your machine |
| [Text analyzer](analyzer/README.md) | paste English: its phrasal verbs, idioms, collocations, word levels and likely mistakes | your machine |

Only the finder is published. Everything else is built from the dictionaries
you download and stays on your machine ([From zero](#from-zero-building-the-local-tools)
shows how): the dictionaries are mostly commercial, so nothing built from them is
ever committed.

## How it works

| Step | File | Output |
|---|---|---|
| Crawl the public directory listing (no downloads) | `scripts/crawl_index.py` | `data/index.jsonl` |
| Group files into dictionaries, label language, brand, aliases; track first-seen dates and changes | `scripts/build_site.py` (+ `classify.py`, `families.py`) | `site/data/dicts.json`, `site/data/meta.json` |
| Search in the browser (no server, no dependencies) | `site/search.js`, `site/app.js` | — |

`site/t2s.json` (Traditional → Simplified map for search) is generated once on
macOS with `swift scripts/gen_t2s.swift > site/t2s.json`.

A GitHub Actions workflow refreshes the index monthly. It is scheduled on the
1st, 8th and 15th; the first successful run of a month crawls and later runs
that month skip, so a failed crawl is retried a week later. Manual runs
(`gh workflow run update.yml`) always crawl. The build refuses to publish if the
dictionary count drops by more than 20%, which almost always means a partial
crawl rather than real removals; the previous data stays live.

Deployment to Pages is opt-in: set the repository variable `PUBLISH_PAGES` to
`true`. A Pages site is public even when the repository is private.

## Local use

```sh
python3 scripts/crawl_index.py data/index.jsonl   # ~10-15 min
python3 scripts/build_site.py
python3 -m http.server -d site 8000               # open http://localhost:8000
```

## Tests

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # once
PYTHONPATH=scripts .venv/bin/python -m unittest discover -s tests
PYTHONPATH=scripts:parallel_corpus .venv/bin/python -m unittest discover -s parallel_corpus/tests -t parallel_corpus/tests
PYTHONPATH=scripts:inventories .venv/bin/python -m unittest discover -s inventories/tests -t inventories/tests
PYTHONPATH=scripts:analyzer .venv/bin/python -m unittest discover -s analyzer/tests -t analyzer/tests
node --test tests/*.test.mjs
```

Tests marked "corpus" run only when `corpus/unified.db` exists locally; on
GitHub they skip, because the dictionaries are never in the repository.

The 25 recommended dictionaries the local tools are built from, with their editions, the
freemdict copy each build downloads, and its size: [`DICTIONARIES.md`](DICTIONARIES.md).

## From zero: building the local tools

Everything below runs on your machine and builds data that is never committed.
A complete build needs about 78 GB of disk at its peak (67 GB once done) and, on a
10-core Mac with the 21 GB of downloads already in place, about two and a half hours:
the unified dictionary about 35 minutes, the inventories 20, the parallel corpus 90
(it downloads and reads some 280 more dictionaries for their example pairs).

```sh
python3 scripts/doctor.py                     # what is missing, and how to fix it
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/doctor.py            # again, with the project's Python: should say "ready"
PYTHONPATH=scripts .venv/bin/python scripts/build_corpus.py   # download and build the unified dictionary
.venv/bin/python inventories/build.py         # the lexical inventories (add --without-jev if jev is missing)
.venv/bin/python parallel_corpus/build.py     # the parallel corpus
.venv/bin/python analyzer/build.py            # the text analyzer's lexicon
PYTHONPATH=scripts .venv/bin/python scripts/serve_unified.py  # http://127.0.0.1:8766/ and /analyze
```

### No jev? You can still build everything

`jev` is a command-line client for TypeSafe's calibrated-judgment model, and most people
do not have it. You do not need it: every step builds without it, and `doctor.py` says
whether it is installed. Two steps ask it a question; without it, this is what changes:

| Step | Asks jev | Without jev |
|---|---|---|
| Unified dictionary | no | the same |
| Inventories | whether a word whose stress moves with its part of speech ("REcord" the noun, "reCORD" the verb) is one word or two | run `inventories/build.py --without-jev`: those 767 contrasts are tagged "uncertain"; every other inventory is the same. Forget the flag and the build stops before doing anything, saying so |
| Parallel corpus | how accurate each dictionary's example pairs are | nothing to do: the answers are committed in `parallel_corpus/verdicts.json` and reused when your download of a dictionary matches the one they were measured on. If freemdict has since replaced a file, that dictionary is left out, and the build names it |
| Analyzer | no | the same |

So without jev you lose one label on a few hundred stress contrasts, and possibly a
dictionary or two of example sentences if freemdict changes its files.

## Unified dictionary database (local only)

The recommended dictionaries can be merged into one local database. The
downloaded dictionaries and everything built from them live under `corpus/`
and `dev-docs/artifacts/`, which are git-ignored: they are large and mostly
commercial, so nothing built from them is ever committed.

```sh
PYTHONPATH=scripts .venv/bin/python scripts/build_corpus.py   # all steps; --from STEP / --only STEP
PYTHONPATH=scripts .venv/bin/python scripts/serve_unified.py  # http://127.0.0.1:8766/
```

| Step | Script | Output |
|---|---|---|
| fetch | `fetch_corpus.py` | `corpus/<key>/`: every .mdx/.mdd/.css/.js, sizes checked against the index |
| inspect | `inspect_corpus.py` | `corpus/_inspect/report.json`: counts each later step is checked against |
| layer 1 | `build_unified.py` | `corpus/unified.db`: every entry's original HTML, redirects, each dictionary's CSS/JS, a headword index that ignores case, accents, stress marks and syllable dots |
| layer 2 | `build_structured.py` | the same database: pronunciations, senses, definitions (English and Chinese), examples, etymology, forms; a Chinese-to-English index; full-text search over definitions |
| layer 3 | `build_resources.py` | `corpus/resources.db`: every audio/image/stylesheet resource, stored once by content hash |

Layer 2 has one parser per dictionary in `scripts/structured/parsers/`, all
producing the model in `scripts/structured/model.py`. The build fails if a
parser raises, breaks the model's contract, or covers less of its dictionary
than its `MIN_COVERAGE`. Records that cannot hold content (cross-references,
popups, index pages) are marked as stubs from evidence in their markup and are
excluded from coverage; a stub that does hold content fails the build.
`scripts/structured/devtool.py` samples entries and measures a parser's
coverage while writing one.

The lookup server shows every dictionary's entry for a word in one unified
layout rendered from layer 2 (`scripts/lookup_ui/`): the same design for all 25
dictionaries (pronunciations with audio, senses, labels, English and Chinese
definitions, examples, phrases, etymology), styled with the website's design
tokens. Each card can switch to that dictionary's original design (layer 1, with
its own CSS, images and working cross-links). It also does Chinese-to-English
lookup and search by definition.

Chinese-to-English lookup reads two indexes: exact terms by `zh_term`'s index, and terms
containing the query from `zh_fts`, a trigram index of the distinct terms (7.6 ms a query on
average, where scanning the two million gloss rows took 119). A database built before
2026-10-05 lacks it; `PYTHONPATH=scripts .venv/bin/python scripts/build_structured.py
--derived-only` adds it, and the entry and sense keys `READING.md` describes, in under a
minute. The server reads through memory-mapped I/O and, in the background at start, reads
every index a lookup needs, so the first lookups after a restart are warm.

Another program reading these databases (keys that survive rebuilds, encodings, rendering):
[`READING.md`](READING.md).

## Parallel corpus of example sentences (local only)

An English–Chinese corpus of the example sentences in freemdict's dictionaries,
with the tools that build it, lives in [`parallel_corpus/`](parallel_corpus/README.md).

## Lexical inventories (local only)

Inflections, phrases, collocations, grammar patterns, word families and labels, built
from the parsed dictionaries, live in [`inventories/`](inventories/README.md).

## Text analyzer (local only)

Paste English text and get its phrasal verbs, idioms, collocations, word levels, labels,
spelling problems and likely confusions, from the inventories: [`analyzer/`](analyzer/README.md),
and the Analyze page of the lookup server.

## Recommendations

The landing view shows recommendation cards from `data/recommended.json`,
which is edited by hand. Each entry gives the latest real-world edition (with
a source link) and a `pick`: the exact freemdict record name, plus a `folder`
substring when several records share that name. The build resolves every pick
to a record:

- A malformed entry (unknown `status`, non-https `src`, duplicate `key`)
  fails the build.
- A pick that no longer exists on freemdict does not fail the monthly
  update; it shows as "not on freemdict" and logs a workflow warning.
- `test_committed_curation_resolves_every_pick_exactly` fails on typos.

Statuses: `current`, `behind`, `snapshot`, `final`, `unclear`, `missing`.
Update the `reviewed` date when rechecking editions.

## Improving results

- A dictionary is missing an alias (e.g. searching its Chinese name finds nothing):
  add a pattern to `ALIASES` in `scripts/families.py`.
- A dictionary has the wrong language label: add its exact name to `OVERRIDES`
  in `scripts/classify.py`.
