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
PYTHONPATH=scripts python3 -m unittest discover -s tests
node --test tests/search.test.mjs
```

## Improving results

- A dictionary is missing an alias (e.g. searching its Chinese name finds nothing):
  add a pattern to `ALIASES` in `scripts/families.py`.
- A dictionary has the wrong language label: add its exact name to `OVERRIDES`
  in `scripts/classify.py`.
