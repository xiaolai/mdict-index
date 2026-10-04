"""Download the recommended dictionaries into corpus/<key>/ for local work.

    python3 scripts/fetch_corpus.py [--max-mdd-mb 50] [--only key,key]

Takes each recommendation's resolved record (site/data/recommended.json +
site/data/dicts.json) and downloads its files from the most complete copy:
every .mdx/.css/.js/font, plus .mdd files up to --max-mdd-mb (small .mdd
files hold stylesheets and images; the large ones are audio).

Resumable (curl -C -; a file larger than the index says starts over), and every file is checked against the size in the
index: a mismatch fails the run. Writes corpus/manifest.json.
corpus/ is git-ignored: these files are large and mostly commercial.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
HOST = "https://downloads.freemdict.com/"
DIRECT = "https://downloads-direct.freemdict.com/"  # freemdict routes .rar here


def file_url(folder: str, name: str) -> str:
    base = DIRECT if name.lower().endswith(".rar") else HOST
    parts = [p for p in folder.split("/") if p] + [name]
    return base + "/".join(urllib.parse.quote(p, safe="") for p in parts)


def plan(max_mdd: int, only: set[str] | None) -> list[dict]:
    dicts = {d["id"]: d for d in json.loads((ROOT / "site/data/dicts.json").read_text())}
    rec = json.loads((ROOT / "site/data/recommended.json").read_text())
    known = {item["key"] for cat in rec["categories"] for item in cat["items"] if item["id"] is not None}
    if only and (unknown := sorted(only - known)):
        raise SystemExit(f"--only: no recommended dictionary {unknown}; known: {', '.join(sorted(known))}")
    jobs = []
    for cat in rec["categories"]:
        for item in cat["items"]:
            if item["id"] is None or (only and item["key"] not in only):
                continue
            record = dicts[item["id"]]
            loc = record["loc"][0]  # most complete copy leads (build_site._settle_copies)
            for name, size in loc["f"]:
                is_mdd = name.lower().endswith(".mdd")
                jobs.append({
                    "key": item["key"], "record": record["n"], "folder": loc["p"], "name": name,
                    "size": size, "skipped": is_mdd and size > max_mdd,
                    "url": file_url(loc["p"], name), "path": str(CORPUS / item["key"] / name),
                })
    return jobs


def fetch(job: dict) -> dict:
    path = Path(job["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > job["size"]:
        path.unlink()  # resuming (curl -C -) only appends: an oversized file must start again from zero
    if not (path.exists() and path.stat().st_size == job["size"]):
        subprocess.run(
            ["curl", "-sS", "--fail", "-L", "--retry", "4", "--retry-delay", "3", "-C", "-", "-o", str(path), job["url"]],
            check=True,
        )
    got = path.stat().st_size
    if got != job["size"]:
        raise RuntimeError(f"{job['key']}/{job['name']}: got {got} bytes, index says {job['size']}")
    return job


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-mdd-mb", type=float, default=50)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    jobs = plan(int(args.max_mdd_mb * 1e6), set(filter(None, args.only.split(","))) or None)
    todo = [j for j in jobs if not j["skipped"]]
    print(f"{len(todo)} files, {sum(j['size'] for j in todo) / 1e9:.2f} GB to fetch; "
          f"{len(jobs) - len(todo)} large .mdd skipped", file=sys.stderr)

    failures = []
    with ThreadPoolExecutor(4) as pool:
        for job, fut in [(j, pool.submit(fetch, j)) for j in todo]:
            try:
                fut.result()
                print(f"ok   {job['key']}/{job['name']}", file=sys.stderr)
            except Exception as e:  # report every failure, then fail the run
                failures.append(f"{job['key']}/{job['name']}: {e}")
                print(f"FAIL {job['key']}/{job['name']}: {e}", file=sys.stderr)

    (CORPUS / "manifest.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=1))
    if failures:
        sys.exit(f"{len(failures)} downloads failed")


if __name__ == "__main__":
    main()
