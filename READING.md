# Reading the unified dictionary from another program

How a program other than this repository's own server reads `corpus/unified.db` and
`corpus/resources.db`. Both are built locally (README, "From zero") from dictionaries the reader
downloaded, and neither is ever distributed. Everything below is plain SQLite: no MDX parsing, no
RIPEMD-128, no block decompression beyond one zlib stream per entry.

## What to hold on to: keys, not ids

Every integer id is renumbered by a build: layer 1 numbers entries across all 25 dictionaries in
one sequence, and layer 2 offsets senses by the dictionaries merged before. **Never store an id.**
Store a key:

| Key | Form | Table | Holds while |
|---|---|---|---|
| entry | `dictionary:occurrence:headword`, e.g. `oald:1:run`, `noad:2:set` | `entry_key(entry_id, key)` | the dictionary's `records` hash is unchanged |
| sense | the entry key and the sense's position (from 0), e.g. `oald:1:run:0` | view `sense_key(sense_id, key)` | its `senses` hash is unchanged |

`occurrence` counts the headword's records in the dictionary's file order (25,911 headwords occur
more than once in a dictionary, up to 75 times). The headword comes last, so a key splits back
unambiguously: `entry.split(":", 2)`, `sense.rsplit(":", 1)`. `dictionary_version(dict_id, records,
senses)` gives each dictionary two SHA-256 hashes that touch no id: `records` over its headwords and
bodies in file order, `senses` over every sense's key, kind, phrase and definitions. Keep them with
your keys; a changed hash says which of your keys to re-resolve, and only for that dictionary.

To find a key's row: `SELECT entry_id FROM entry_key WHERE key = ?` (unique index), then
`s_sense` by `(entry_id, ord)` (index `s_sense_entry`).

These are this collection's own identities. They do not match Apple's dictionaries: the NOAD here is
the MDX edition of NOAD 3, with no publisher sense ids, and Apple's NOAD is a different file with
different markup. Matching the two means comparing headwords and definitions, not ids.

## Finding a word

1. Normalize the query as the build did, `scripts/build_unified.py: norm()`: drop stress marks and
   syllable dots (`ˈ ˌ · ‧ •`), NFKC, case-fold, NFKD, drop combining marks, NFC, collapse whitespace.
2. `SELECT id, dict_id, headword FROM entry WHERE norm = ?` (index `entry_norm`).
3. Follow cross-references: `SELECT dict_id, target, target_norm FROM redirect WHERE norm = ?`
   (index `redirect_norm`), then look `target_norm` up as in step 2, in that `dict_id`.

Chinese to English: `zh_term(term, sense_id)` for an exact gloss (index `zh_term_term`); for glosses
containing a string of three or more characters, `SELECT term FROM zh_fts WHERE zh_fts MATCH ?`
(a trigram index), then `zh_term` by term. `scripts/serve_unified.py: api_zh()` is the reference.

## What an entry contains

**Parsed (layer 2), the script-free way.** One model for all 25 dictionaries
(`scripts/structured/model.py`), JSON in the columns marked so:

| Table | Columns |
|---|---|
| `s_entry` | `entry_id`, `dict_id`, `headword`, `homograph`, `pos` (JSON list), `etymology`, `forms` (JSON list), `extra` (JSON object, per parser), `stub` (why a record holds no content; '' for content), `part_of`, `merged_into` |
| `s_pron` | `entry_id`, `ord`, `region` (`uk`, `us` or ''), `ipa`, `audio` (a `sound://` reference or a URL), `note` |
| `s_sense` | `id`, `entry_id`, `dict_id`, `ord`, `kind` (`sense`, `phrase`, `phrasal_verb`, `derivative`, `collocation`, `note`), `pos`, `number`, `phrase`, `labels` (JSON list), `definition`, `definition_zh` |
| `s_example` | `sense_id`, `ord`, `kind` (`example`, `collocation`, `quotation`), `text`, `text_zh`, `source`, `date`, `labels` (JSON list) |

Skip entries whose `stub` is not '' (cross-references, pop-ups, index pages) and entries with a
`merged_into`: their senses were folded into that entry. `scripts/lookup_ui/render.js` renders this
model to HTML with no scripts and no links to resolve; it is a pure function and can be ported.

**Original (layer 1), the dictionary's own design.** `entry.body` is the record's UTF-8 HTML,
compressed with zlib *including* its 2-byte header (`78 9C`) and 4-byte Adler-32 trailer. Apple's
`Compression` framework (`COMPRESSION_ZLIB`) decodes raw deflate: drop the first 2 bytes and the
last 4. To display one as the dictionary intended, do what `serve_unified.py: entry_page()` does:

- wrap it with the dictionary's `dictionary.stylesheet` and `dictionary.script`. Nearly every record
  of ten dictionaries (OALD, OALECD, LDOCE, LDOCE-EC, COBUILD, Chambers, ODE, ODECN, OED, NCECD)
  holds `<script>` elements, and eight also ship a script of their own in `dictionary.script`, so a
  view of the originals must run JavaScript;
- turn `entry://word` and `bword://word` links into your own lookups;
- resolve `sound://`, `file://` and `mdd://` references, and root-relative `src`/`href`, through
  `resources.db` (below);
- drop advertising scripts (`googletag`), which some records carry.

`SELECT ... FROM entry` for a common word across all 25 dictionaries returns several MB of HTML
(`run`: about 5.9 MB), so fetch bodies only for what is shown.

## Audio and images

`resources.db`: `resource(dict_id, norm, path, hash)` and `blob(hash, size, data)`, each file
stored once by content hash. A `sound://`, `file://` or `mdd://` reference names an `.mdd` file
literally ("?", "#" and "%" are characters of the name, not URL syntax): drop the scheme, decode
HTML entities, normalize as `build_resources.py: norm_key()` does (`\` to `/`, leading `/` and
`./` dropped, NFC, lower case), then `SELECT b.data FROM resource r JOIN blob b ON b.hash = r.hash
WHERE r.dict_id = ? AND r.norm = ?`. A root-relative `src` or `href` in the HTML is a URL path:
percent-decode it first. In a sample of 20,000 pronunciations this resolves every reference but 9
outside the OED, whose download has no audio at all; `http(s)://` references (Collins English)
play from the publisher's site. Audio is 19.6 GB of the 20.6 GB; a program that speaks with
text-to-speech can ignore it, and the IPA stays in `s_pron`.

## Checking what you opened

- `SELECT count(*) FROM dictionary_version` is 25 on a complete build; a missing `entry_key`,
  `zh_fts` or `dictionary_version` table means a database built before 2026-10-05:
  `PYTHONPATH=scripts .venv/bin/python scripts/build_structured.py --derived-only` adds them in
  under a minute, without reparsing.
- Open read-only (`file:...?mode=ro`); nothing a reader does needs to write.
