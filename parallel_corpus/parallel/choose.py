"""Choose the dictionaries the parallel corpus is built from, using the probe's results.

    PYTHONPATH=scripts:parallel_corpus .venv/bin/python parallel_corpus/parallel/choose.py [--probe parallel_corpus/data/probe.jsonl]

A dictionary is kept when most of its same-shaped pairs were English rather than another
language beside Chinese, and its sampled pairs are translations: read in its better order
(English then Chinese, or Chinese then English), their mean lexicon alignment
(parallel/lexicon.py) is above MIN_ALIGNMENT with confidence: mean - SPREAD/sqrt(n) over
n >= MIN_ALIGNED scored pairs. Over the probe, alignment is bimodal (noise around 0.1-0.2,
translations around 0.7); a mean over 7 pairs says much less than one over 700, which is
what separates a Chinese-first dictionary with idiomatic English (0.46 over 40 pairs) from
an encyclopedia's stray sentences (0.43 over 7). Chinese
merely printed next to English (encyclopedias, blogs, glossaries) aligns poorly in both
orders. Kept dictionaries that already have a layer-2 parser are read from the structured
database instead of being downloaded again. Writes parallel_corpus/data/selected.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "parallel_corpus"))
from parallel import DATA  # noqa: E402
MIN_ENGLISH_SHARE = 0.5   # of all same-shaped pairs; German-, Japanese-Chinese... fall below
MIN_ALIGNED = 5           # pairs with an alignment score, in the chosen order
MIN_ALIGNMENT = 0.3       # lower bound of the mean: between the noise peak (0.1-0.2) and translations (~0.7)
SPREAD = 0.5              # 1.64 x the per-pair standard deviation (~0.3) of true pairs' scores


@dataclass(frozen=True)
class Choice:
    id: str
    name: str
    keep: bool
    reason: str               # why it was kept or dropped
    source: str = ""          # "layer2" (already parsed) | "download"
    key: str = ""             # the layer-2 parser, for source "layer2"
    folder: str = ""
    file: str = ""
    bytes: int = 0
    order: str = ""           # "en-zh" | "zh-en": which comes first in the dictionary
    extractor: str = "text"   # "text" (parallel/text.py) | "styled" (parallel/styled.py, see extractors.json)
    truth: str = ""           # for "styled": the layer-2 dictionary that teaches the example style
    alignment: float = 0.0    # mean lexicon alignment of the sampled pairs in that order
    aligned: int = 0          # how many sampled pairs were scored
    pairs_per_100k_chars: float = 0.0


ORDERS = ("en-zh", "zh-en")


def _qualifies(alignment: float, aligned: int) -> bool:
    """Enough scored pairs, and a mean above MIN_ALIGNMENT with confidence."""
    return aligned >= MIN_ALIGNED and alignment - SPREAD / math.sqrt(aligned) >= MIN_ALIGNMENT


def choose(row: dict, parsed: dict[str, str]) -> Choice:
    """Decide one probe result. `parsed` maps dictionary id -> layer-2 parser key."""
    base = {"id": row["id"], "name": row["name"], "folder": row["folder"], "file": row["file"], "bytes": row["bytes"]}
    if row["status"] != "ok":
        return Choice(**base, keep=False, reason=f"{row['status']}: {row.get('reason', '')}")
    english, foreign = row["pairs_loose"], row["pairs_foreign"]
    scored = {o: (row[f"align_{o.replace('-', '_')}"] or 0.0, row[f"aligned_{o.replace('-', '_')}"]) for o in ORDERS}
    # The better order is one that qualifies, then the higher mean: a high mean over too few
    # pairs must not hide a qualifying reading in the other order.
    order = max(ORDERS, key=lambda o: (_qualifies(*scored[o]), *scored[o]))
    alignment, aligned = scored[order]
    stats = {"order": order, "alignment": alignment, "aligned": aligned,
             "pairs_per_100k_chars": row["pairs_per_100k_chars"]}
    if english + foreign and english / (english + foreign) < MIN_ENGLISH_SHARE:
        return Choice(**base, **stats, keep=False,
                      reason=f"mostly another language beside Chinese ({foreign} of {english + foreign} pairs)")
    if aligned < MIN_ALIGNED:
        return Choice(**base, **stats, keep=False, reason=f"{aligned} scored pairs in the sample")
    if not _qualifies(alignment, aligned):
        return Choice(**base, **stats, keep=False,
                      reason=f"alignment {alignment:.2f} over {aligned} pairs: not clearly translations")
    why = f"alignment {alignment:.2f} over {aligned} pairs, {order}"
    if row["id"] in parsed:
        return Choice(**base, **stats, keep=True, reason=f"already parsed; {why}", source="layer2",
                      key=parsed[row["id"]])
    return Choice(**base, **stats, keep=True, reason=why, source="download")


EXTRACTORS = Path(__file__).resolve().parent / "extractors.json"


def extractor_overrides(path: Path = EXTRACTORS) -> dict[str, dict]:
    """Dictionary id -> {"extractor", "truth"} for those not read by the generic extractor."""
    return {k: v for k, v in json.loads(path.read_text()).items() if not k.startswith("_")}


def with_extractor(choice: Choice, overrides: dict[str, dict]) -> Choice:
    """A kept dictionary with its extractor; styled ones are kept whatever their alignment, as
    their pairs are chosen by structure (the audit still gates them)."""
    override = overrides.get(choice.id)
    if not override or choice.source == "layer2" or choice.reason.startswith(("unreadable", "error")):
        return choice
    return replace(choice, keep=True, source="download", extractor=override["extractor"], truth=override["truth"],
                   reason=f"{override['extractor']} extractor ({choice.reason})")


def parsed_dictionaries() -> dict[str, str]:
    """Dictionary id -> parser key, for the recommendations that have a layer-2 parser."""
    from structured.parsers import registry
    parsers = registry()
    rec = json.loads((ROOT / "site" / "data" / "recommended.json").read_text())
    return {item["id"]: item["key"] for cat in rec["categories"] for item in cat["items"]
            if item["id"] and item["key"] in parsers}


def kept_twice(choices: list[Choice]) -> list[str]:
    """Files kept under more than one id: each would enter the corpus twice."""
    seen = Counter((c.folder, c.file) for c in choices if c.keep)
    return sorted(f"{folder}/{file}" for (folder, file), n in seen.items() if n > 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", type=Path, default=DATA / "probe.jsonl")
    ap.add_argument("--out", type=Path, default=DATA / "selected.json")
    args = ap.parse_args()
    rows = [json.loads(line) for line in args.probe.read_text().splitlines()]
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        sys.exit(f"{args.probe}: duplicate dictionary ids; rerun the probe with --retry-errors to rewrite it")
    parsed = parsed_dictionaries()
    overrides = extractor_overrides()
    choices = sorted((with_extractor(choose(r, parsed), overrides) for r in rows), key=lambda c: (not c.keep, -c.alignment))
    if twice := kept_twice(choices):
        sys.exit(f"{len(twice)} files kept under two ids (stale probe rows?), e.g. {twice[0]}")
    args.out.write_text(json.dumps([asdict(c) for c in choices], ensure_ascii=False, indent=1) + "\n")
    kept = [c for c in choices if c.keep]
    download = [c for c in kept if c.source == "download"]
    print(f"{len(rows)} probed: {len(kept)} kept ({len(kept) - len(download)} already parsed, "
          f"{len(download)} to download, {sum(c.bytes for c in download) / 1e9:.2f} GB); "
          f"{len(rows) - len(kept)} dropped -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
