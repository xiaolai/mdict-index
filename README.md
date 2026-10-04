# MDict Dictionary Finder

A searchable index of the MDict dictionaries listed at
<https://downloads.freemdict.com/>, published as a static GitHub Pages site.
The site links to freemdict; it hosts no dictionary files.

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
node --test tests/*.test.mjs
```

Tests marked "corpus" run only when `corpus/unified.db` exists locally; on
GitHub they skip, because the dictionaries are never in the repository.

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

## Parallel corpus of example sentences (local only)

An English–Chinese corpus of the example sentences in freemdict's dictionaries,
with the tools that build it, lives in [`parallel_corpus/`](parallel_corpus/README.md).

## Lexical inventories (local only)

Inflections, phrases, collocations, grammar patterns, word families and labels, built
from the parsed dictionaries, live in [`inventories/`](inventories/README.md).

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
