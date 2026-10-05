# Making the tools usable: a reproducible build and a text analyzer

Status: Part A done; Part B built and measured (2026-10-05); sense disambiguation is the open step

## Problem

The tools build three local resources: the unified dictionary database, the
lexical inventories and the parallel corpus. A user who clones the repository
cannot get from them to anything they would use:

1. **The inventories cannot be rebuilt from the repository.** The only runner is
   `inventories/data/rebuild_all.sh`. It lives in the git-ignored data folder and
   hard-codes one machine's path.
2. **Two build steps need jev.** `inventories/inventory/sameword.py` asks
   `jev noul`, and `parallel_corpus/parallel/audit.py` asks the `parallel-pair`
   docket. That docket exists only in one user's `~/.config/jev/dockets/`, so
   the audit cannot run anywhere else even with a TypeSafe key.
3. **Nothing applies the inventories to text.** The inventories README says it:
   lemmatising running text and finding its phrases "is separate work built on
   these". A learner or teacher needs exactly that: paste a text and see its
   phrasal verbs, idioms, collocations, word levels and likely confusions.

Dictionary-derived data stays local, as everywhere else in this repository.
Every user builds their own from the dictionaries they download.

## Part A: a build anyone can run

| Item | Change | Done when |
|---|---|---|
| A1 inventory runner | `inventories/build.py`: the steps in dependency order, `--from STEP` / `--only STEP` like `scripts/build_corpus.py`, paths from the repository root, stop at the first failure, `check.py` last. Delete `rebuild_all.sh`. | A test pins the step order to the documented build order. A full rebuild (about 6 minutes) produces databases that match the current ones row for row. |
| A2 sameword without jev | Without jev, `sameword.py` refuses to run unless given `--without-jev`. With the flag, every pair gets the existing `uncertain` relation, and the log and the database record that the step ran degraded. A missing jev never degrades silently. | Tests cover both paths. `check.py` accepts a degraded build and reports it. |
| A3 audit verdicts that travel | Commit `parallel_corpus/verdicts.json`: per dictionary, its id, public name, the `.mdx` file's SHA-256, sample size, flagged, reviewed, bad, precision and admitted. Numbers only, no dictionary text. `audit.py` reuses a verdict when the user's file hash matches. On a mismatch it audits with jev if available; otherwise it excludes the dictionary and says so. | Built without jev from identical files, the corpus is identical to ours. A hash mismatch is excluded loudly, never admitted. |
| A4 the docket | Commit `parallel_corpus/jev/parallel-pair.json` and have `audit.py` pass it explicitly, so a user with a TypeSafe key can audit files whose hashes differ. | `audit.py` no longer depends on a docket being installed in the user's home folder. |
| A5 preflight | `scripts/doctor.py`: Python version, pinned packages installed, FTS5 available in Python's sqlite3 (the macOS `sqlite3` command-line tool lacks it), free disk against the download size from the index, jev present or not and what that means. | Exits non-zero, naming the fix, for each missing prerequisite. |
| A6 one path in the README | A "from zero" section: clone, doctor, fetch, build corpus, build inventories, build parallel corpus, serve. | Followed on a fresh clone, it works. |

### Part A, as built (2026-10-05)

- A1: `inventories/build.py`, with `inventories/tests/test_build.py` pinning the order to the
  files each module reads (four deliberate misorderings each fail). A full rebuild through it
  reproduced all 20 inventory tables row for row.
- A2: `sameword.py --without-jev`; `build_info` in `pronunciations.db`; `check.py` prints it.
- A3: `parallel_corpus/verdicts.json`, pinned to the SHA-256 of each dictionary's staged
  pairs (not of its .mdx: the verdict is about the pairs). Re-extraction under two hash
  seeds gave byte-identical pairs.
- A4: `parallel_corpus/jev/dockets/parallel-pair.json`, passed through `JEV_HOME`.
- A5: `scripts/doctor.py`.
- A6: "From zero" in the README.
- Found on the way and fixed: `probe.py` kept results for ids the index no longer has, so
  three dictionaries re-identified by the site's new record rules were probed, chosen,
  extracted and audited twice, and one of them (a Longman 4th edition) was admitted twice.
  `probe.py` now drops such rows; `choose.py` refuses a file kept under two ids.

## Part B: the text analyzer

### What it does

Input: English text. Output, per token and per span, with character offsets
into the original text:

- **Tokens**: candidate lemmas with part of speech and inflection slot (`went` →
  go, VERB, Past), word level (CEFR, Oxford 3000/5000, Macmillan stars,
  frequency band), usage labels above a share threshold, and flags: a known
  misspelling (`accomodation`), an unknown word with suggestions, a member of a
  confusable set (`affect` / `effect`).
- **Spans**: phrasal verbs, idioms, formulas and compounds from `phrases.db`,
  including separated ones (`gave it up`) as discontinuous spans; collocations
  from `collocations.db` (`made a difficult decision`). Each span carries its
  inventory id, the number of dictionaries and publishers that attest it,
  labels, and the English and Chinese definitions.

Surfaces: a library; a command-line tool (`analyze FILE --json|--html`); a
`POST /api/analyze` route on the existing local server (size-capped,
127.0.0.1 only); and an "Analyze" view in the lookup page, where every span and
word opens the unified lookup.

### How

1. **Tokenize** with offsets: words with internal apostrophes and hyphens,
   clitics split (`don't` → do + n't, `John's` → John + 's, which fills a
   `{poss}` slot), sentences split. Matching uses a normalised copy (NFC,
   straight quotes, lower case); offsets point to the original.
2. **Candidate lemmas** from `inflections.db` (`inflection` and `other`) plus
   the token itself, ranked by attestation (`n`). This is a lattice, not a
   decision: `left` stays {leave VERB Past, left ADJ, left NOUN}.
3. **Phrase matching** over the lattice. The variants are already compiled to
   lemma patterns with typed slots (`give {obj} up`, `pull {poss} leg`,
   `take {obj} for granted`):
   - a literal matches any inflection of its lemma;
   - `{obj}` matches 1 to 4 tokens inside the sentence, with no punctuation;
   - `{poss}` matches a possessive determiner or a token followed by `'s`;
   - `{refl}` matches a reflexive pronoun;
   - a trailing `{...}` matches nothing.

   Each pattern is indexed by its rarest literal lemma. Overlaps resolve to the
   longer span, then the better-attested one.
4. **Collocations**: a base lemma and its collocate lemmas in the pattern's
   order (or either order when `word_order` is free). Up to 3 determiners and
   modifiers may come between them in verb–object and adjective–noun
   patterns. The default evidence threshold is 2 dictionaries (102,441 of
   516,578); it can be changed.
5. **Compile** everything once into `analyzer/data/analyzer.db` (form index,
   compiled patterns, level and label summaries per lemma), so a run never
   opens the large inventory databases.

**Why no part-of-speech tagger, at first.** A multiword pattern constrains
itself: several lemmas in order rarely co-occur by accident, so the lattice
loses little precision on spans. Single tokens stay ambiguous, and the honest
display for them is the candidate set. A tagger (spaCy) would add a large
dependency and its own model. It is worth adding only if the measured
precision below says so. It would plug in at step 2 as a filter on the lattice.

**What it will miss**: collocations whose parts are reordered by syntax
("the decision that she made", passives). Only a parser finds those. They are
reported as a known limitation and counted in the evaluation.

### Measured, not assumed

- **Recall on free gold.** The parsed dictionaries print 57,652 examples under
  phrasal verbs, 157,083 under idioms and phrases, and 66,058 under
  collocations (OCD). Each example illustrates a known item, so recall is
  "does the analyzer find that item in its own example". This is reported per
  kind and per dictionary. One caveat: phrase readings were chosen with the
  help of the same examples (`evidence.py`), which inflates recall slightly.
  The report says so and also gives recall on the dictionaries that did not
  supply a phrase's notation.
- **Precision on neutral text.** Run on public-domain text (Project Gutenberg
  fiction and Wikipedia articles) and read a random 200 spans per kind. jev
  screens the spans and the flagged ones are read, as in the corpus audit.
  Unread flags count as errors.
- **Lemma accuracy**: 300 hand-checked tokens, kept as gold beside the
  inventories' existing gold sets.
- Targets to confirm after the first baseline: phrase recall ≥ 90%, span
  precision ≥ 90% for phrasal verbs and idioms and ≥ 85% for collocations, and
  10,000 words analysed in under a second.

### Layout

`analyzer/` beside `inventories/` and `parallel_corpus/`: `analyzer/analyze/`
(the library), `analyzer/build.py` (compiles `analyzer.db`), `analyzer/tests/`,
and `analyzer/README.md`. `analyzer/data/` is git-ignored. Its tests run in CI
on fixtures written for the tests, never on dictionary text.

## Order and effort

| Step | Nature | Agent time | Clock time |
|---|---|---|---|
| Part A | mostly mechanical | 1 to 2 hours | one inventory rebuild (about 6 minutes), one parallel-corpus build from verdicts |
| B1 tokenizer, lattice, compiled index | mechanical, with care for offsets | 1 to 2 hours | |
| B2 phrase and collocation matching | design-heavy (slots, overlap rules) | 2 to 3 hours | |
| B3 evaluation harness and first baseline | mechanical harness, then reading results | 2 hours | reading 600+ sampled spans |
| B4 command line, API route, Analyze view | mechanical | 2 hours | |
| B5 iterate to the targets | irreducible: depends on what the baseline shows | unknown until B3 | |

### Part B, as built (2026-10-05)

Built as planned, with spaCy: `analyzer/` (compile, lexicon, matcher, result, command line),
`POST /api/analyze` and `/analyze` on the lookup server, recall and precision harnesses. Measured
results and what was left out are in `analyzer/README.md`. Against the targets set above:

| Target | Result |
|---|---|
| phrase recall ≥ 90% | phrasal verbs 87.7%, other phrases 72.6% (every span); 63.2% / 58.4% for the spans shown by default |
| span precision ≥ 90% (phrasal verbs, idioms) | 88% for the spans shown by default ("likely"), 68% for the rest |
| ≥ 85% (collocations) | 96% |
| 10,000 words under a second | missed: 10,152 words in 2.95 s, of which spaCy's parse (small model, one core) is about 2.4 s and matching 0.5 s; a few hundred words, the usual paste, take a fraction of a second after a one-off load of 5 to 13 s |

The precision targets assumed structure decides. It does for collocations; for phrases what
remains is sense (an idiom used literally, a verb with a preposition in its plain meaning). The
next step is choosing between a phrase's senses and its literal reading from context, for which
the dictionaries' own examples of each phrase are the training material.

Found and fixed on the way: notation defects in the phrase inventory and reading defects in the
confusables inventory (both documented in `inventories/README.md`).

## Decisions (2026-10-05)

1. **Part-of-speech tagger: spaCy from the start.** spaCy 3.8.16 publishes
   wheels for this project's Python (3.14, macOS arm64). It goes in as a
   pinned dependency of the analyzer only, so the site build and the other
   tools stay as light as they are. The lattice remains the source of
   candidate lemmas: spaCy's tag and dependency parse choose among them
   instead of replacing them. Its dependency parse also finds collocations
   that syntax reorders ("the decision that she made", passives), which moves
   them from "known limitation" to "measured".
2. **Distribution: local only.** Every user builds their own data. Nothing
   derived from the dictionaries is published.
3. **Order: Part A, then Part B.**
