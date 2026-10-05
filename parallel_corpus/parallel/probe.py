"""Sample an MDict .mdx through HTTP range requests, without downloading it.

    PYTHONPATH=scripts:parallel_corpus .venv/bin/python parallel_corpus/parallel/probe.py [--blocks 4] [--jobs 6] [--out parallel_corpus/data/probe.jsonl]

An .mdx starts with a header and a small index of its compressed record blocks.
The probe reads the header, walks past the key section using the sizes the
format records, reads the record-block index, then fetches a few blocks spread
through the file (about 0.5 MB per dictionary in all) and measures how much of
their text is English sentences followed by Chinese text: `pairs` requires the
Chinese to end like a sentence (。？！), `pairs_loose` does not (older dictionaries
omit it). Both count only pairs that pass the corpus's language rules (English, and
Chinese without kana or hangul); same-shaped pairs in other languages are counted as
`pairs_foreign`, and up to SAMPLES candidate pairs are kept so the result can be re-judged
without probing again. The probe only decides what to download; telling examples from
definitions is the extractor's job.

This decides which dictionaries are worth downloading for the parallel corpus:
names are not reliable ("English" dictionaries carry Chinese examples, some
"English-Chinese" ones are Chinese-only).
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "parallel_corpus"))
from parallel import DATA  # noqa: E402
from parallel.lexicon import score as lexicon_score  # noqa: E402
from parallel.mdxformat import ProbeError, decode_block, layout, record_blocks  # noqa: E402  (the .mdx format)
from parallel.ranges import HttpRange  # noqa: E402
from parallel.text import ORDERS, candidate_pairs, is_english_chinese, stream  # noqa: E402  (shared with extraction)
HOST = "https://downloads.freemdict.com/"
SAMPLES = 12                  # candidate pairs kept per dictionary, so results can be re-judged offline


# ---- the bilingual-example signal ---------------------------------------------------------

_CJK = re.compile(r"[\u3400-\u9fff]")


def count_pairs(text: str, strict: bool = True) -> int:
    return sum(map(is_english_chinese, candidate_pairs(text, strict)))


MIN_KNOWN = 2  # lexicon words a pair needs before its alignment score counts


def alignment_scores(pairs: list[tuple[str, str]], lexicon=None) -> list[float]:
    """Lexicon alignment of each English-Chinese pair whose English the lexicon knows well enough
    (none without a lexicon: tests and callers that only count)."""
    if lexicon is None:
        return []
    scored = (lexicon_score(en, zh, lexicon) for en, zh in pairs if is_english_chinese((en, zh)))
    return [s for s, known in scored if known >= MIN_KNOWN]


def signal(text: str, lexicon=None) -> dict:
    """Counts for one block of text. English-then-Chinese pairs give `pairs`/`pairs_loose`/
    `pairs_foreign`; Chinese-then-English ones `pairs_zh_en`. `candidates` (both orders, before
    the language check) and `scores` (lexicon alignment per order) are for the probe to gather."""
    segs = stream(text, cuts=True).split("\n")
    joined = "\n".join(segs)
    loose = candidate_pairs(joined, strict=False)
    reverse = candidate_pairs(joined, strict=False, order="zh-en")
    english = sum(map(is_english_chinese, loose))
    return {"segments": len(segs), "pairs": count_pairs(joined), "pairs_loose": english,
            "pairs_foreign": len(loose) - english, "pairs_zh_en": sum(map(is_english_chinese, reverse)),
            "cjk_segments": sum(1 for s in segs if _CJK.search(s)),
            "chars": sum(len(s) for s in segs),
            "candidates": {"en-zh": loose, "zh-en": reverse},
            "scores": {"en-zh": alignment_scores(loose, lexicon), "zh-en": alignment_scores(reverse, lexicon)}}


def spread(items: list, n: int) -> list:
    """n items evenly spaced through the list (all of them if there are no more than n)."""
    if len(items) <= n:
        return list(items)
    return [items[i * len(items) // n] for i in range(n)]


def pick_blocks(blocks: list, n: int) -> list:
    """n blocks, each from the middle of its own n-th of the file (all of them if there are no more than n)."""
    if n < 1:
        raise ValueError(f"the number of blocks to sample must be positive, not {n}")
    if len(blocks) <= n:
        return list(blocks)
    return [blocks[(2 * i + 1) * len(blocks) // (2 * n)] for i in range(n)]


def probe(src, n_blocks: int = 4, lexicon=None) -> dict:
    if n_blocks < 1:  # before any request
        raise ValueError(f"the number of blocks to sample must be positive, not {n_blocks}")
    lay = layout(src)
    blocks = record_blocks(src, lay)
    if not blocks:
        raise ProbeError("no record blocks")
    last_offset, last_size, _ = blocks[-1]
    if src.size is not None and last_offset + last_size > src.size:
        raise ProbeError(f"truncated: the index needs {last_offset + last_size} bytes, the file has {src.size}")
    picked = pick_blocks(blocks, n_blocks)
    total = {"segments": 0, "pairs": 0, "pairs_loose": 0, "pairs_foreign": 0, "pairs_zh_en": 0,
             "cjk_segments": 0, "chars": 0}
    candidates: dict[str, list] = {order: [] for order in ORDERS}
    scores: dict[str, list] = {order: [] for order in ORDERS}
    methods: set[int] = set()
    for offset, comp, decomp in picked:
        raw = src.read(offset, comp)
        if len(raw) != comp:
            raise ProbeError(f"truncated: block at {offset} has {len(raw)} of {comp} bytes")
        methods.add(struct.unpack("<L", raw[:4])[0] & 0xF)
        text = decode_block(raw, decomp).decode(lay.encoding, "replace")
        found = signal(text, lexicon)
        for order in ORDERS:
            candidates[order] += found["candidates"][order]
            scores[order] += found["scores"][order]
        for k, v in found.items():
            if k in ("candidates", "scores"):
                continue
            total[k] += v
    per_100k = round(total["pairs_loose"] * 100_000 / total["chars"], 2) if total["chars"] else 0.0
    return {"version": lay.version, "encoding": lay.encoding, "blocks": len(blocks), "sampled": len(picked),
            "compression": sorted(methods),
            **total, "pairs_per_100k_chars": per_100k,
            **{f"align_{order.replace('-', '_')}": round(sum(scores[order]) / len(scores[order]), 3)
               if scores[order] else None for order in ORDERS},
            **{f"aligned_{order.replace('-', '_')}": len(scores[order]) for order in ORDERS},
            "samples": [{"en": en, "zh": zh, "english_chinese": is_english_chinese((en, zh))}
                        for en, zh in spread(candidates["en-zh"], SAMPLES)],
            "samples_zh_en": [{"en": en, "zh": zh, "english_chinese": is_english_chinese((en, zh))}
                              for en, zh in spread(candidates["zh-en"], SAMPLES)]}


# ---- command line -----------------------------------------------------------------------

def file_url(folder: str, name: str) -> str:
    return HOST + "/".join(urllib.parse.quote(p, safe="") for p in [*folder.split("/"), name] if p)


def candidates() -> list[dict]:
    dicts = json.loads((ROOT / "site" / "data" / "dicts.json").read_text())
    out = []
    for d in dicts:
        if d["k"] != "mdx":
            continue
        loc = d["loc"][0]
        mdx = next((n for n, _ in loc["f"] if n.lower().endswith(".mdx")), None)
        if mdx:
            out.append({"id": d["id"], "name": d["n"], "lang": d["l"], "folder": loc["p"], "file": mdx,
                        "bytes": sum(s for n, s in loc["f"] if n == mdx)})
    return out


def current_rows(previous: list[dict], current_ids: set[str]) -> tuple[list[dict], list[dict]]:
    """Earlier results whose dictionary is still in the index, and the rest. A record the index
    re-identified (its id rules changed) would otherwise be probed again under its new id and kept
    under both, so it would enter the corpus twice."""
    kept = [r for r in previous if r["id"] in current_ids]
    return kept, [r for r in previous if r["id"] not in current_ids]


def run_one(c: dict, n_blocks: int, lexicon=None) -> dict:
    src = HttpRange(file_url(c["folder"], c["file"]))
    try:
        result = {**c, "status": "ok", **probe(src, n_blocks, lexicon)}
    except ProbeError as e:
        result = {**c, "status": "unreadable", "reason": str(e)}
    except Exception as e:  # recorded per dictionary; the run reports how many failed
        result = {**c, "status": "error", "reason": f"{type(e).__name__}: {e}"}
    result["fetched_bytes"] = src.fetched
    return result


def _journal_rows(journal: Path) -> list[dict]:
    """The results in a journal. A run killed while writing leaves a torn last line: it is cut
    off, and that dictionary is probed again."""
    if not journal.exists():
        return []
    text = journal.read_text()
    whole = text[:text.rfind("\n") + 1]
    if whole != text:
        journal.write_text(whole)
    return [json.loads(line) for line in whole.splitlines()]


def _positive(text: str) -> int:
    n = int(text)
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be positive, not {n}")
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", type=_positive, default=4)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--out", type=Path, default=DATA / "probe.jsonl")
    ap.add_argument("--retry-errors", action="store_true", help="probe again every dictionary whose result was not ok")
    ap.add_argument("--redo", type=Path, help="a JSON list of dictionary ids to probe again")
    args = ap.parse_args()
    from parallel.lexicon import _lexicon
    lexicon = _lexicon()  # loaded once, shared by the workers; first, so a missing one changes nothing
    args.out.parent.mkdir(parents=True, exist_ok=True)
    previous = [json.loads(line) for line in args.out.read_text().splitlines()] if args.out.exists() else []
    index = candidates()
    previous, stale = current_rows(previous, {c["id"] for c in index})
    if stale:
        print(f"{len(stale)} earlier results dropped: their ids are no longer in the index "
              f"(re-identified or removed), e.g. {stale[0]['name'][:60]}", file=sys.stderr)
    redo = set(json.loads(args.redo.read_text())) if args.redo else set()
    # Results go to a journal beside the output, which is replaced once, when every probe is in:
    # a row asked for again stays until its replacement and all the others exist, and a run that
    # fails or is stopped loses nothing (the next one continues from the journal).
    journal = args.out.with_name(args.out.name + ".journal")
    again = {r["id"] for r in previous if r["id"] in redo or (args.retry_errors or redo) and r["status"] != "ok"}
    done = ({r["id"] for r in previous} - again) | {r["id"] for r in _journal_rows(journal)}
    todo = [c for c in index if c["id"] not in done]
    print(f"{len(done)} already probed, {len(todo)} to go", file=sys.stderr)
    with ThreadPoolExecutor(args.jobs) as pool, journal.open("a") as out:
        futures = [pool.submit(run_one, c, args.blocks, lexicon) for c in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
            out.flush()
            if i % 50 == 0 or r["status"] != "ok":
                print(f"{i}/{len(todo)} {r['status']:10} {r['name'][:40]} {r.get('reason', '')}", file=sys.stderr)
    new = _journal_rows(journal)
    replaced = {r["id"] for r in new}
    tmp = args.out.with_name(f"{args.out.name}.{uuid.uuid4().hex}.part")
    try:
        tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                               for r in [*(r for r in previous if r["id"] not in replaced), *new]))
        tmp.replace(args.out)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    journal.unlink()


if __name__ == "__main__":
    main()
