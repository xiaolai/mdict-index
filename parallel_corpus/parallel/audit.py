"""Measure each dictionary's precision: how many of its accepted pairs are real translated examples.

    PYTHONPATH=scripts:parallel_corpus .venv/bin/python parallel_corpus/parallel/audit.py [--only ID,ID] [--redo] [--n 60]
    PYTHONPATH=scripts:parallel_corpus .venv/bin/python parallel_corpus/parallel/audit.py --queue    # pairs awaiting review

Two stages, because jev alone cannot measure precision at this level:

1. Screen. A fixed random sample of the pairs the corpus rules accept (parallel/corpus.py)
   goes to jev's `parallel-pair` docket; a pair is flagged when `usable` < SCREEN.
   Calibration on 160 hand-labelled pairs from the 8 parsed bilingual dictionaries:
   the screen caught 8 of 8 bad pairs with 19 false alarms among 152 good ones (12.5%),
   too many to use the flag rate as the error rate against a 5% budget.
2. Review. Flagged pairs are read and labelled in parallel_corpus/data/audit/<id>.review.json
   ({"<sample index>": "good" | "bad"}).

Precision is conservative: 1 - (bad + flagged but not yet reviewed) / n. A dictionary with
few enough flags passes without review; reviews can only raise the figure. Judgments are
kept in parallel_corpus/data/audit/<id>.jsonl, the summaries in parallel_corpus/data/audit.json, which
the build reads (parallel/build.py admits a dictionary at MIN_PRECISION).

Shared verdicts. parallel_corpus/verdicts.json (committed: numbers only, no dictionary text)
holds the verdict our build used for each dictionary, pinned to the SHA-256 of its staged
pairs. A dictionary with no local audit takes its verdict from there when its staged pairs are
byte for byte the ones the verdict was measured on; that needs no jev. Otherwise it is
screened with jev, and without jev it is left unaudited, which the build excludes, and the
run says so. `--export-verdicts` rewrites the file from the local audit.

The docket is parallel_corpus/jev/parallel-pair.json, passed to jev through JEV_HOME, so the
questions are versioned with the code that relies on them.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "parallel_corpus"))
from parallel.corpus import clean, clean_en, clean_zh, judge  # noqa: E402

from parallel import DATA as PARALLEL  # noqa: E402
QUESTIONS = ("usable", "aligned", "residue")  # `usable` decides; the others help the reviewer
SCREEN = 0.5
JEV_HOME = ROOT / "parallel_corpus" / "jev"  # dockets/parallel-pair.json
VERDICTS = ROOT / "parallel_corpus" / "verdicts.json"
SUMMARY = ("n", "flagged", "reviewed", "bad", "precision")

Judge = Callable[[dict], dict[str, float]]


class NothingToAudit(ValueError):
    """A staged dictionary has no pair the corpus rules accept: it fails the audit, it is not skipped."""


def sample(path: Path, n: int, seed: str) -> list[dict]:
    """A uniform sample of n accepted records (reservoir sampling; the same seed gives the same sample)."""
    rng = random.Random(seed)
    chosen: list[dict] = []
    seen = 0
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if not judge(r["en"], r["zh"]).ok:
                continue
            seen += 1
            if len(chosen) < n:
                chosen.append(r)
            else:
                j = rng.randrange(seen)
                if j < n:
                    chosen[j] = r
    return chosen


def jev(record: dict) -> dict[str, float]:
    """Ask the parallel-pair docket about one pair; fails loudly if jev fails."""
    state = f"EN: {clean_en(record['en'], record['zh'])}\nZH: {clean_zh(record['zh'])}"
    if record.get("hw"):
        state += f"\nHEADWORD: {clean(record['hw'])}"
    out = subprocess.run(["jev", "docket", "parallel-pair", "--json", "--retries", "5", "--state", state],
                         capture_output=True, text=True, timeout=120, env={**os.environ, "JEV_HOME": str(JEV_HOME)})
    if out.returncode != 0:
        raise RuntimeError(f"jev exited {out.returncode}: {out.stderr.strip()[:300]}")
    answers = json.loads(out.stdout)["answers"]
    return {q: float(answers[q]["noul"]) for q in QUESTIONS}


def screen(path: Path, seed: str, n: int, ask: Judge, jobs: int = 4) -> list[dict]:
    """Every sampled pair of one staged dictionary with its scores and whether it is flagged."""
    pairs = sample(path, n, seed)
    if not pairs:
        raise NothingToAudit(f"{path}: no accepted pairs to audit")
    with ThreadPoolExecutor(jobs) as pool:
        scores = list(pool.map(ask, pairs))
    return [{**p, **s, "flagged": s["usable"] < SCREEN} for p, s in zip(pairs, scores)]


def summarize(judged: list[dict], review: dict[str, str], excluded: frozenset[str] = frozenset()) -> dict:
    """Conservative precision: flagged pairs count as bad until a review says otherwise.

    `excluded` are sample indices the corpus rules now reject (rules changed after screening):
    they are no longer in the corpus, so they leave the sample. What remains is still a uniform
    sample of what the rules accept, as rules that only remove pairs keep it so.
    """
    flagged = [str(i) for i, j in enumerate(judged) if j["flagged"] and str(i) not in excluded]
    review = {i: label for i, label in review.items() if i not in excluded}
    unknown = set(review) - set(flagged)
    if unknown or set(review.values()) - {"good", "bad"}:
        raise ValueError(f"review labels must be 'good' or 'bad' for flagged pairs only (unexpected: {sorted(unknown)})")
    bad = sum(review.get(i) == "bad" for i in flagged)
    pending = sum(i not in review for i in flagged)
    n = len(judged) - len(excluded)
    if not n:
        return {"n": 0, "flagged": 0, "reviewed": 0, "bad": 0, "precision": 0.0}
    # not rounded: the build admits at a threshold, and 0.94995 must not become 0.95
    return {"n": n, "flagged": len(flagged), "reviewed": len(flagged) - pending, "bad": bad,
            "precision": 1 - (bad + pending) / n}


def needs_review(summary: dict, min_precision: float) -> bool:
    """Whether reading the pending flags could change the verdict."""
    if not summary["n"]:  # nothing accepted: fails, and no review can change that
        return False
    return summary["precision"] < min_precision <= 1 - summary["bad"] / summary["n"]


def import_labels(labels: dict[str, dict[str, str]], folder: Path) -> int:
    """Merge reviewers' labels ({dictionary id: {sample index: "good" | "bad"}}) into the
    dictionaries' review files, checking each against its screened sample. Returns how many."""
    n = 0
    for id, new in labels.items():
        judged = [json.loads(line) for line in (folder / f"{id}.jsonl").read_text().splitlines()]
        path = folder / f"{id}.review.json"
        review = {**(json.loads(path.read_text()) if path.exists() else {}), **new}
        summarize(judged, review)  # raises on a label for an unflagged pair or an unknown value
        path.write_text(json.dumps(review, ensure_ascii=False, indent=1) + "\n")
        n += len(new)
    return n


def jev_installed() -> bool:
    return shutil.which("jev") is not None


def staged_sha256(path: Path) -> str:
    """The hash of a dictionary's staged pairs, decompressed (gzip headers carry a timestamp)."""
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def from_verdict(verdicts: dict, id: str, staged: Path) -> dict | None:
    """The shared verdict for this dictionary if it was measured on exactly these staged pairs."""
    v = verdicts.get(id)
    if v is None or v["staged_sha256"] != staged_sha256(staged):
        return None
    return {**{k: v[k] for k in SUMMARY}, "name": v["name"], "from": "verdicts.json",
            **({"note": v["note"]} if "note" in v else {})}


def export_verdicts(results: dict, kept: list[dict], staged_dir: Path) -> dict:
    """verdicts.json from the local audit: each audited, staged dictionary's summary and hash."""
    out = {}
    for c in sorted(kept, key=lambda c: c["id"]):
        r, path = results.get(c["id"]), staged_dir / f"{c['id']}.jsonl.gz"
        if r is None or not path.exists():
            continue
        out[c["id"]] = {"name": c["name"], "staged_sha256": staged_sha256(path), **{k: r[k] for k in SUMMARY},
                        **({"note": r["note"]} if "note" in r else {})}
    return out


def _review(id: str) -> dict[str, str]:
    path = PARALLEL / "audit" / f"{id}.review.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _judged(id: str) -> list[dict]:
    return [json.loads(line) for line in (PARALLEL / "audit" / f"{id}.jsonl").read_text().splitlines()]


def _excluded(judged: list[dict]) -> frozenset[str]:
    """Sample indices the corpus rules now reject (see summarize)."""
    return frozenset(str(i) for i, j in enumerate(judged) if not judge(j["en"], j["zh"]).ok)


def main() -> None:
    from parallel.build import MIN_PRECISION
    ap = argparse.ArgumentParser()
    ap.add_argument("--selected", type=Path, default=PARALLEL / "selected.json")
    ap.add_argument("--out", type=Path, default=PARALLEL / "audit.json")
    ap.add_argument("--only", default="", help="comma-separated dictionary ids")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--redo", action="store_true", help="screen again (drops earlier reviews of those dictionaries)")
    ap.add_argument("--queue", action="store_true", help="print the flagged pairs whose review could change a verdict")
    ap.add_argument("--import-labels", type=Path, nargs="+", help="reviewers' label files to merge before summarising")
    ap.add_argument("--verdicts", type=Path, default=VERDICTS, help="shared verdicts (committed)")
    ap.add_argument("--export-verdicts", action="store_true", help="write the shared verdicts from the local audit")
    args = ap.parse_args()
    only = set(filter(None, args.only.split(",")))
    results = json.loads(args.out.read_text()) if args.out.exists() else {}
    kept = [c for c in json.loads(args.selected.read_text()) if c["keep"] and (not only or c["id"] in only)]
    if args.queue:
        queue = {}
        for c in kept:
            if c["id"] in results and needs_review(results[c["id"]], MIN_PRECISION):
                review, judged = _review(c["id"]), _judged(c["id"])
                skip = review.keys() | _excluded(judged)  # reviewed, or no longer in the corpus
                queue[c["id"]] = {"name": c["name"], "pairs": {
                    str(i): {k: j[k] for k in ("en", "zh", "hw", *QUESTIONS)}
                    for i, j in enumerate(judged) if j["flagged"] and str(i) not in skip}}
        print(json.dumps(queue, ensure_ascii=False, indent=1))
        return
    if args.export_verdicts:
        verdicts = export_verdicts(results, kept, PARALLEL / "staged")
        args.verdicts.write_text(json.dumps(verdicts, ensure_ascii=False, indent=1) + "\n")
        print(f"{len(verdicts)} verdicts written to {args.verdicts}", file=sys.stderr)
        return
    verdicts = json.loads(args.verdicts.read_text()) if args.verdicts.exists() else {}
    has_jev = jev_installed()
    left_out = []
    (PARALLEL / "audit").mkdir(exist_ok=True)
    for f in args.import_labels or []:
        print(f"{import_labels(json.loads(f.read_text()), PARALLEL / 'audit'):,} labels from {f}", file=sys.stderr)
    for c in kept:
        path = PARALLEL / "staged" / f"{c['id']}.jsonl.gz"
        if not path.exists():
            print(f"not extracted yet: {c['name']}", file=sys.stderr)
            continue
        local = (PARALLEL / "audit" / f"{c['id']}.jsonl").exists()
        if not local and not args.redo and (shared := from_verdict(verdicts, c["id"], path)):
            results[c["id"]] = shared
            args.out.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n")
            print(f"{shared['precision']:.3f} (shared verdict) {c['name'][:60]}", file=sys.stderr)
            continue
        if not has_jev and (args.redo or not local):
            left_out.append(c["name"])
            print(f"UNAUDITED (no matching shared verdict, no jev): {c['name'][:60]}", file=sys.stderr)
            continue
        if args.redo or not local:
            try:
                judged = screen(path, c["id"], args.n, jev, args.jobs)
            except NothingToAudit:  # an empty sample replaces the old one, which no later run may reuse
                judged = []
            (PARALLEL / "audit" / f"{c['id']}.jsonl").write_text(
                "".join(json.dumps(j, ensure_ascii=False) + "\n" for j in judged))
            (PARALLEL / "audit" / f"{c['id']}.review.json").unlink(missing_ok=True)  # indices changed
        judged = _judged(c["id"])
        summary = summarize(judged, _review(c["id"]), _excluded(judged))
        results[c["id"]] = {**summary, "name": c["name"]}
        if not summary["n"]:  # nothing accepted: recorded as failing, not skipped
            results[c["id"]]["note"] = "no accepted pairs to audit"
        args.out.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n")  # after each: resumable
        print(f"{summary['precision']:.3f} ({summary['flagged']} flagged, {summary['reviewed']} reviewed, "
              f"{summary['bad']} bad of {summary['n']}) {c['name'][:60]}", file=sys.stderr)
    if left_out:
        print(f"{len(left_out)} dictionaries left unaudited, so the build will exclude them: their staged pairs "
              f"match no shared verdict and jev is not installed", file=sys.stderr)


if __name__ == "__main__":
    main()
