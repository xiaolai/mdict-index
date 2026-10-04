"""Stage every dictionary's English-Chinese examples as raw records, before any judging.

    PYTHONPATH=scripts:parallel_corpus .venv/bin/python parallel_corpus/parallel/extract.py [--only ID,ID]

Reads parallel_corpus/data/selected.json (parallel/choose.py) and writes one
parallel_corpus/data/staged/<id>.jsonl.gz per kept dictionary, each line
{"en", "zh", "hw"} exactly as the dictionary prints it. Validity and deduplication are
decided later by the build (parallel/corpus.py rules), so changing a rule never needs a
re-extraction.

Sources:
  layer2    dictionaries with a layer-2 parser: their s_example rows that have a translation
  download  every other kept dictionary: its .mdx is downloaded to parallel_corpus/data/mdx/ (size
            checked against the index) and every record scanned by parallel/text.py in the
            dictionary's order (parallel/choose.py), taking sentence pairs only;
            cross-reference records (@@@LINK=) are skipped
  styled    a downloaded dictionary listed in parallel/extractors.json: its example style is learned
            from a parsed dictionary (parallel/styled.py) and recorded in staged/<id>.styles.json,
            which is published together with the records (see stage)
"""
from __future__ import annotations

import argparse
import fcntl
import gzip
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "parallel_corpus"))
from parallel import DATA as PARALLEL  # noqa: E402
from build_structured import STRUCTURED  # noqa: E402  the parsed dictionaries, where the build writes them

_LAYER2 = """
SELECT e.headword, x.text, x.text_zh FROM s_example x
JOIN s_sense s ON s.id = x.sense_id JOIN s_entry e ON e.entry_id = s.entry_id
WHERE x.text_zh <> '' ORDER BY e.entry_id, s.ord, x.ord
"""


def layer2(db: Path) -> Iterator[dict]:
    """Translated examples of one structured database (corpus/_structured/unified.db/<key>.db)."""
    if not db.exists():
        raise FileNotFoundError(f"{db}: build the structured layer first (build_structured.py)")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        for hw, en, zh in con.execute(_LAYER2):
            yield {"en": en, "zh": zh, "hw": hw}
    finally:
        con.close()


def mdx_pairs(path: Path, order: str = "en-zh") -> Iterator[dict]:
    """Sentence pairs from every record of a local .mdx, read in the dictionary's order."""
    from parallel import mdx, text  # mdx needs the project venv (mdict-utils)
    for headword, markup in mdx.records(path):
        if markup.startswith("@@@LINK="):
            continue
        for en, zh in text.pairs(markup, order=order):
            yield {"en": en, "zh": zh, "hw": headword}


def _styled_entries(path: Path) -> Iterator[tuple[str, str]]:
    from parallel import mdx
    return ((hw, m) for hw, m in mdx.records(path) if not m.startswith("@@@LINK="))


def learn_styles(path: Path, truth_db: Path) -> dict[str, tuple[int, int]]:
    """The example styles of a local .mdx, learned from a parsed dictionary with the same content."""
    from parallel import styled
    if not truth_db.exists():
        raise FileNotFoundError(f"{truth_db}: the ground truth for learning the example style")
    examples, definitions = styled.ground_truth(truth_db)
    learned = styled.learn((m for _, m in _styled_entries(path)), examples, definitions)
    if not learned:
        print(f"{path.name}: no example style learned; nothing staged", file=sys.stderr, flush=True)
    return learned


def styled_pairs(path: Path, learned: dict[str, tuple[int, int]]) -> Iterator[dict]:
    """Pairs printed in the dictionary's learned example styles. The file is read again, after
    learn_styles(), rather than held in memory."""
    from parallel import styled
    for headword, markup in _styled_entries(path) if learned else ():
        for en, zh in styled.pairs(markup, learned):
            yield {"en": en, "zh": zh, "hw": headword}


def download(choice: dict, folder: Path) -> Path:
    """The dictionary's .mdx, downloaded if missing; its size must match the index."""
    from fetch_corpus import file_url
    path = folder / f"{choice['id']}.mdx"
    if path.exists() and path.stat().st_size > choice["bytes"]:
        path.unlink()  # cannot be resumed: start again
    if not (path.exists() and path.stat().st_size == choice["bytes"]):
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-sS", "--fail", "-L", "--retry", "4", "--retry-delay", "3", "-C", "-",
                        "-o", str(path), file_url(choice["folder"], choice["file"])], check=True)
    if path.stat().st_size != choice["bytes"]:
        raise RuntimeError(f"{choice['name']}: got {path.stat().st_size} bytes, the index says {choice['bytes']}")
    return path


def styles_path(out: Path) -> Path:
    """Where the styles a staged file was extracted by are recorded: <id>.styles.json beside <id>.jsonl.gz."""
    return out.with_name(out.name.removesuffix(".jsonl.gz") + ".styles.json")


def lock_path(out: Path) -> Path:
    """The lock publishing into out is serialised by: .<id>.lock beside it. It stays on disk; removing
    a lock file another run may be waiting on would let a third run take a second lock."""
    return out.with_name("." + out.name.removesuffix(".jsonl.gz") + ".lock")


def stage(records: Iterator[dict], out: Path, styles: dict[str, tuple[int, int]] | None = None) -> int:
    """Write records to out atomically; returns how many. A failed run leaves no partial file.

    The records and the styles they were extracted by (a styled dictionary's learned example
    styles; None for any other) are published as a pair: both are written and closed under
    working names first; then, holding an exclusive lock on lock_path(out), the old styles file
    is removed, the records are renamed into place, and the styles after them. The lock keeps a
    second run, of this process or another, from publishing between those steps, so a styles file
    always describes the records beside it, and records extracted without styles have none. A
    failure between the renames leaves records with no styles file, never with another run's.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f"{out.name}.{uuid.uuid4().hex}.part")  # its own, so concurrent runs never share one
    styles_out = styles_path(out)
    styles_tmp = styles_out.with_name(f"{styles_out.name}.{uuid.uuid4().hex}.part")
    n = 0
    try:
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                n += 1
        if styles is not None:
            styles_tmp.write_text(json.dumps({k: {"example_hits": e, "definition_hits": d} for k, (e, d) in styles.items()},
                                             indent=1) + "\n")
        with open(lock_path(out), "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)  # released when the file is closed
            styles_out.unlink(missing_ok=True)
            os.replace(tmp, out)
            if styles is not None:
                os.replace(styles_tmp, styles_out)
    except BaseException:
        tmp.unlink(missing_ok=True)
        styles_tmp.unlink(missing_ok=True)
        raise
    return n


def records_for(choice: dict) -> tuple[Iterator[dict], dict[str, tuple[int, int]] | None]:
    """A dictionary's records, and for a styled one the example styles they are extracted by."""
    if choice["source"] == "layer2":
        return layer2(STRUCTURED / f"{choice['key']}.db"), None
    if choice["source"] == "download" and choice.get("extractor", "text") == "styled":
        path = PARALLEL / "mdx" / f"{choice['id']}.mdx"
        learned = learn_styles(path, STRUCTURED / f"{choice['truth']}.db")
        return styled_pairs(path, learned), learned
    if choice["source"] == "download":
        return mdx_pairs(PARALLEL / "mdx" / f"{choice['id']}.mdx", choice["order"]), None
    raise NotImplementedError(f"source {choice['source']!r} ({choice['name']})")


def fetch_one(choice: dict) -> None:
    """Download one dictionary's .mdx (a thread-pool worker)."""
    download(choice, PARALLEL / "mdx")


def stage_one(choice: dict) -> int:
    """Stage one dictionary (a process-pool worker)."""
    records, styles = records_for(choice)
    return stage(records, PARALLEL / "staged" / f"{choice['id']}.jsonl.gz", styles)


def _run(pool, fn, choices: list[dict], label: str) -> list[str]:
    """Run fn over choices; report each; return the failures instead of stopping at the first."""
    failures = []
    futures = {pool.submit(fn, c): c for c in choices}
    for fut in as_completed(futures):
        c = futures[fut]
        try:
            result = fut.result()
            print(f"{label} {result if isinstance(result, int) else '':>9} {c['source']:8} {c['name'][:60]}",
                  file=sys.stderr, flush=True)
        except Exception as e:  # collected: one broken dictionary must not lose the others' work
            failures.append(f"{c['id']} {c['name'][:50]}: {type(e).__name__}: {e}")
            print(f"FAILED {label} {c['name'][:60]}: {e}", file=sys.stderr, flush=True)
    return failures


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selected", type=Path, default=PARALLEL / "selected.json")
    ap.add_argument("--only", default="", help="comma-separated dictionary ids")
    ap.add_argument("--source", default="", help="only this source kind (layer2, download)")
    ap.add_argument("--redo", action="store_true", help="stage again dictionaries already staged")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--download-jobs", type=int, default=4)
    args = ap.parse_args()
    only = set(filter(None, args.only.split(",")))
    kept = [c for c in json.loads(args.selected.read_text()) if c["keep"]]
    todo = [c for c in kept if (not only or c["id"] in only) and (not args.source or c["source"] == args.source)]
    if only - {c["id"] for c in todo}:
        sys.exit(f"not kept in {args.selected}: {sorted(only - {c['id'] for c in todo})}")
    if not args.redo:
        todo = [c for c in todo if not (PARALLEL / "staged" / f"{c['id']}.jsonl.gz").exists()]
    downloads = [c for c in todo if c["source"] == "download"]
    print(f"{len(todo)} to stage, {len(downloads)} from downloads "
          f"({sum(c['bytes'] for c in downloads) / 1e9:.2f} GB at most)", file=sys.stderr)
    with ThreadPoolExecutor(args.download_jobs) as pool:
        failures = _run(pool, fetch_one, downloads, "downloaded")
    failed = {f.split(" ", 1)[0] for f in failures}
    with ProcessPoolExecutor(args.jobs) as pool:
        failures += _run(pool, stage_one, [c for c in todo if c["id"] not in failed], "staged")
    if failures:
        sys.exit(f"{len(failures)} dictionaries failed:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
